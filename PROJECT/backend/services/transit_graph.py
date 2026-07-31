"""Unified transit topology for VOYAGER v2 (PROMPT_2 §4).

Static graph (built once at init): bus / metro / rail nodes + edges.
Query-time rules (forward-progress, visited guard, direction sanity) live in
route_finder.py — the graph stores pure topology with time/distance weights.

Performance notes (PROMPT_2 §4.3):
  - haversine + _dist_cache dict only (never geodesic in hot loops)
  - walk speed 5 km/h; bus ~22 km/h; metro ~33 km/h
"""
import math
import time

from .data_schema import TransitNode
from .transit_models import Leg

BUS_SPEED_KMH = 18.0
METRO_SPEED_KMH = 36.0
WALK_SPEED_KMH = 5.0
TRANSFER_PENALTY_MIN = 4.0
BUS_DWELL_MIN = 0.3
METRO_DWELL_MIN = 0.25
INTERCHANGE_FIXED_MIN = 5.0

WALK_BUS_BUS_M = 500
WALK_BUS_METRO_M = 1000
WALK_BUS_RAIL_M = 3000

# Radius for metro/rail node entry/exit reach (used by route_finder)
EDGE_KEY = "edge"  # reserved, not used


def _hav_m(lat1: float, lng1: float, lat2: float, lng2: float, cache: dict | None = None) -> float:
    if cache is not None:
        key = (round(lat1, 5), round(lng1, 5), round(lat2, 5), round(lng2, 5))
        if key in cache:
            return cache[key]
        rkey = (key[2], key[3], key[0], key[1])
        if rkey in cache:
            return cache[rkey]
        cache[key] = _hav_m_calc(lat1, lng1, lat2, lng2)
        return cache[key]
    return _hav_m_calc(lat1, lng1, lat2, lng2)


def _hav_m_calc(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class TransitAstarGraph:
    """Static topology. Nodes keyed by stable ids, adjacency lists per node.

    Edge types stored in adjacency tuples: (neighbor_key, edge_type, data)
      edge_type: "bus" | "metro" | "walk" | "interchange"
      data: dict with time_min, dist_m and type-specific fields.
    """

    def __init__(self, gtfs, db):
        self.gtfs = gtfs
        self.db = db
        self.nodes: dict[str, TransitNode] = {}
        self.adj: dict[str, list[tuple[str, str, dict]]] = {}
        self._dist_cache: dict = {}
        self._build()

    # ------------------------------------------------------------ building
    def _build(self) -> None:
        t0 = time.perf_counter()
        self.gtfs.pre_resolve_names(s.name for s in self.db.all_bus_stops())
        self._add_bus_nodes()
        self._add_metro_nodes()
        self._add_rail_nodes()
        self._add_bus_edges()
        self._add_metro_edges()
        self._add_walk_edges()
        print(f"[graph] {len(self.nodes)} nodes, {sum(len(v) for v in self.adj.values()) // 2} edges "
              f"in {time.perf_counter() - t0:.2f}s")

    def _node(self, key: str, kind: str, name: str, lat: float, lng: float,
              line: str | None = None, routes: list[str] | None = None) -> TransitNode:
        node = self.nodes.get(key)
        if node is None:
            node = TransitNode(id=key, kind=kind, name=name, lat=lat, lng=lng,
                               line=line, routes=routes or [])
            self.nodes[key] = node
            self.adj[key] = []
        else:
            if line and line not in node.line:
                node.line = (node.line + "," + line) if node.line else line
            for r in routes or []:
                if r not in node.routes:
                    node.routes.append(r)
        return node

    def _add_bus_nodes(self) -> None:
        n = 0
        stops = self.gtfs.data["stops_by_name"]
        seen: set[str] = set()
        for sid in self.gtfs.data["shapes"]:
            for _pos, name in self.gtfs.shape_stop_sequence(sid):
                if f"bus:{name}" not in self.nodes and name in stops:
                    seen.add(name)
        for name in seen:
            coords = stops[name]
            self._node(f"bus:{name}", "bus", name, coords[0], coords[1])
            n += 1
        self._bus_count = n
        print(f"[graph] {n} bus nodes")

    def _add_metro_nodes(self) -> None:
        for st in self.db.all_metro_stations():
            self._node(f"metro:{st.name}", "metro", st.name, st.lat, st.lng, line=st.lines[0])
        print(f"[graph] {sum(1 for n in self.nodes.values() if n.kind == 'metro')} metro nodes")

    def _add_rail_nodes(self) -> None:
        for st in self.db.all_rail_stations():
            self._node(f"rail:{st.name}", "rail", st.name, st.lat, st.lng)

    def _add_bus_edges(self) -> None:
        """Connect consecutive graph-represented stops on each shape (1-skip tolerance).

        Edge weight = haversine distance * 1.15 road factor / bus speed + dwell.
        Pair accumulation is done first (set of routes per stop pair), geometry
        weights computed once per unique pair — not per shape occurrence.
        """
        routes_of_shape: dict[str, set[str]] = {}
        for route, shapes in self.gtfs.data["route_shapes"].items():
            for sid in shapes:
                routes_of_shape.setdefault(sid, set()).add(route)

        bus_keys = {k for k, n in self.nodes.items() if n.kind == "bus"}
        pair_routes: dict[tuple[str, str], set[str]] = {}
        for sid, seq_stops in self._shape_sequences():
            present = [(pos, name) for pos, name in seq_stops if f"bus:{name}" in bus_keys]
            routes = routes_of_shape.get(sid, set())
            if not present:
                continue
            for i in range(len(present) - 1):
                _add_bus_pair_routes(present[i][1], present[i + 1][1], routes, pair_routes)
                if i + 2 < len(present):  # 1-skip tolerance
                    _add_bus_pair_routes(present[i][1], present[i + 2][1], routes, pair_routes)

        for (a, b), routes in pair_routes.items():
            na, nb = self.nodes[f"bus:{a}"], self.nodes[f"bus:{b}"]
            d = _hav_m(na.lat, na.lng, nb.lat, nb.lng, self._dist_cache) * 1.15
            tm = d / (BUS_SPEED_KMH * 1000) * 60 + BUS_DWELL_MIN
            self._add_undirected(f"bus:{a}", f"bus:{b}", "bus",
                                 {"time_min": tm, "dist_m": d, "routes": sorted(routes)})
        print(f"[graph] {len(pair_routes)} bus route edges")

    def _shape_sequences(self):
        seen: set[str] = set()
        for sid in self.gtfs.data["shapes"]:
            if sid in seen:
                continue
            seen.add(sid)
            seq = self.gtfs.shape_stop_sequence(sid)
            if len(seq) >= 2:
                yield sid, seq

    def _add_metro_edges(self) -> None:
        for a, b, dist_km, line in self.db.metro_edges():
            tm = dist_km / METRO_SPEED_KMH * 60 + METRO_DWELL_MIN
            self._add_undirected(f"metro:{a}", f"metro:{b}", "metro",
                                 {"time_min": tm, "dist_m": dist_km * 1000, "line": line})

    def _add_walk_edges(self) -> None:
        """Connect nearby stops with walk-transfer edges.

        Uses a uniform spatial grid (cell ~560 m) over all graph nodes so we
        never pay a DB spatial query per bus node (~5000 nodes x 3 queries
        would blow the graph-build budget). Metro/rail nodes query the grid
        (fewer of them), each expanding only the ring of cells in range.
        """
        CELL_LAT = 0.005  # ~556 m
        CELL_LNG = 0.006  # ~660 m at 13 deg N
        grid: dict[tuple[int, int], list[str]] = {}
        for key, node in self.nodes.items():
            grid.setdefault((int(node.lat / CELL_LAT), int(node.lng / CELL_LNG)), []).append(key)

        def ring(lat: float, lng: float, radius_m: float):
            span_lat = int(radius_m / (CELL_LAT * 111000)) + 1
            span_lng = int(radius_m / (CELL_LNG * 111000 * 0.97)) + 1
            cx, cy = int(lat / CELL_LAT), int(lng / CELL_LNG)
            for ix in range(cx - span_lat, cx + span_lat + 1):
                for iy in range(cy - span_lng, cy + span_lng + 1):
                    for k in grid.get((ix, iy), ()):
                        yield k

        cache = self._dist_cache
        n_walk = 0

        def connect(a: str, b: str, radius: float) -> None:
            nonlocal n_walk
            if a == b or self._has_edge(a, b):
                return
            na, nb = self.nodes[a], self.nodes[b]
            d = _hav_m(na.lat, na.lng, nb.lat, nb.lng, cache)
            if d <= radius:
                self._add_undirected(a, b, "walk", {"time_min": d / (WALK_SPEED_KMH * 1000) * 60, "dist_m": d})
                n_walk += 1

        for key, node in list(self.nodes.items()):
            if node.kind != "bus":
                continue
            for other in ring(node.lat, node.lng, WALK_BUS_BUS_M):
                if self.nodes[other].kind == "bus":
                    connect(key, other, WALK_BUS_BUS_M)
        for st in self.db.all_metro_stations():
            mkey = f"metro:{st.name}"
            if mkey not in self.nodes:
                continue
            for other in ring(st.lat, st.lng, WALK_BUS_METRO_M):
                if self.nodes[other].kind == "bus":
                    connect(mkey, other, WALK_BUS_METRO_M)
        for st in self.db.all_rail_stations():
            rkey = f"rail:{st.name}"
            if rkey not in self.nodes:
                continue
            for other in ring(st.lat, st.lng, WALK_BUS_RAIL_M):
                if self.nodes[other].kind == "bus":
                    connect(rkey, other, WALK_BUS_RAIL_M)
        print(f"[graph] {n_walk} walk transfer edges")

    def _has_edge(self, a: str, b: str) -> bool:
        return any(neigh == b for neigh, _t, _d in self.adj[a])

    def _add_undirected(self, a: str, b: str, etype: str, data: dict) -> None:
        self.adj.setdefault(a, []).append((b, etype, data))
        self.adj.setdefault(b, []).append((a, etype, data))

    # ------------------------------------------------------------ queries
    def neighbors(self, key: str) -> list[tuple[str, str, dict]]:
        return self.adj.get(key, [])

    def node(self, key: str) -> TransitNode | None:
        return self.nodes.get(key)

    def bus_nodes_near(self, lat: float, lng: float, radius_m: float) -> list[tuple[str, float]]:
        out = []
        for stop in self.db.bus_stops_near(lat, lng, radius_m):
            k = f"bus:{self.gtfs.resolve_stop_name(stop.name)}"
            if k and k in self.nodes:
                n = self.nodes[k]
                out.append((k, _hav_m(lat, lng, n.lat, n.lng, self._dist_cache)))
        out.sort(key=lambda t: t[1])
        return out

    def metro_nodes_near(self, lat: float, lng: float, radius_m: float) -> list[tuple[str, float]]:
        out = []
        for st in self.db.metro_near(lat, lng, radius_m):
            k = f"metro:{st.name}"
            if k in self.nodes:
                n = self.nodes[k]
                out.append((k, _hav_m(lat, lng, n.lat, n.lng, self._dist_cache)))
        out.sort(key=lambda t: t[1])
        return out

    def rail_nodes_near(self, lat: float, lng: float, radius_m: float) -> list[tuple[str, float]]:
        out = []
        for st in self.db.rail_near(lat, lng, radius_m):
            k = f"rail:{st.name}"
            if k in self.nodes:
                n = self.nodes[k]
                out.append((k, _hav_m(lat, lng, n.lat, n.lng, self._dist_cache)))
        out.sort(key=lambda t: t[1])
        return out


def _add_bus_pair_routes(name_a: str, name_b: str, routes: set[str],
                         pair_routes: dict[tuple[str, str], set[str]]) -> None:
    if name_a == name_b:
        return
    key = (name_a, name_b) if name_a < name_b else (name_b, name_a)
    pair_routes.setdefault(key, set()).update(routes)
