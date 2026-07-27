import logging, csv, io, zipfile, os
from backend.core.database import db
from backend.core.config import settings
from backend.services.transit_config import (
    _ensure_gtfs, _haversine_dist, _safe, _current_hour,
)

logger = logging.getLogger(__name__)

BUS_SPEED_KMH = 22
METRO_SPEED_KMH = 35
WALK_SPEED_KMH = 5
BUS_STOP_DWELL_MIN = 2
METRO_STOP_DWELL_MIN = 1.5
BUS_BUS_TRANSFER_PENALTY = 5
BUS_METRO_TRANSFER_PENALTY = 8
METRO_METRO_TRANSFER_PENALTY = 4

_MINUTES_PER_KM_WALK = 60 / WALK_SPEED_KMH


class TransitAstarGraph:

    def __init__(self):
        self.graph_built = False
        self.astar = None
        self.node_coords = {}
        self.node_names = {}
        self.node_types = {}
        self.name_to_nodes = {}
        self._route_stop_pairs_cache = None

    def _time_weight(self, dist_km, mode):
        if mode == "walk":
            return round(dist_km * _MINUTES_PER_KM_WALK, 2)
        if mode == "bus":
            return round(dist_km / BUS_SPEED_KMH * 60 + BUS_STOP_DWELL_MIN, 2)
        if mode == "metro":
            return round(dist_km / METRO_SPEED_KMH * 60 + METRO_STOP_DWELL_MIN, 2)
        return round(dist_km * _MINUTES_PER_KM_WALK, 2)

    def _load_gtfs_route_stop_pairs(self):
        if self._route_stop_pairs_cache is not None:
            return self._route_stop_pairs_cache
        gtfs = _ensure_gtfs()
        if not gtfs:
            self._route_stop_pairs_cache = {}
            return {}
        if getattr(gtfs, '_route_stop_pairs', None):
            self._route_stop_pairs_cache = gtfs._route_stop_pairs
            return self._route_stop_pairs_cache
        path = os.path.join(settings.DATA_CACHE_DIR, 'bmtc_gtfs.zip')
        if not os.path.exists(path):
            logger.warning("GTFS zip not found at %s", path)
            self._route_stop_pairs_cache = {}
            return {}

        trip_route_map = {}
        trip_shape_map = {}
        with zipfile.ZipFile(path, 'r') as z:
            with z.open('trips.txt') as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
                    trip_route_map[row['trip_id']] = row.get('route_id', '')
                    trip_shape_map[row['trip_id']] = row.get('shape_id', '')

            route_id_to_name = {}
            with z.open('routes.txt') as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
                    from backend.services.gtfs_service import clean_route_short_name
                    route_id_to_name[row['route_id']] = clean_route_short_name(row.get('route_short_name', ''))

            trips = {}
            with z.open('stop_times.txt') as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding='utf-8')):
                    trip_id = row['trip_id']
                    sid = row['stop_id']
                    seq = int(row['stop_sequence'])
                    trips.setdefault(trip_id, []).append((seq, sid))

        route_stop_pairs = {}
        for trip_id, stop_seq in trips.items():
            stop_seq.sort(key=lambda x: x[0])
            route_id = trip_route_map.get(trip_id, '')
            rsn = route_id_to_name.get(route_id, route_id)
            if not rsn:
                continue
            for i in range(len(stop_seq) - 1):
                from_sid = stop_seq[i][1]
                to_sid = stop_seq[i + 1][1]
                route_stop_pairs.setdefault(rsn, set()).add((from_sid, to_sid))

        self._route_stop_pairs_cache = route_stop_pairs
        gtfs._route_stop_pairs = route_stop_pairs
        return route_stop_pairs

    def build_graph(self):
        if self.graph_built:
            return
        self.graph_built = True

        from backend.services.astar_engine import astar
        self.astar = astar
        self.node_coords.clear()
        self.node_names.clear()
        self.node_types.clear()
        self.name_to_nodes.clear()

        import time as _time
        _t0 = _time.time()
        _dist_cache = {}

        def _get_dist(lat1, lng1, lat2, lng2):
            key = (lat1, lng1, lat2, lng2)
            r = _dist_cache.get(key)
            if r is not None:
                return r
            r = _haversine_dist(lat1, lng1, lat2, lng2)
            _dist_cache[key] = r
            return r

        graph = {}
        edge_set = set()
        self._edge_dist = {}

        def _add_edge(fr, to, w, mode, dist_km=None):
            key = (fr, to, mode)
            if key in edge_set:
                return
            edge_set.add(key)
            graph.setdefault(fr, [])
            graph.setdefault(to, [])
            graph[fr].append((to, w, mode))
            graph[to].append((fr, w, mode))
            self._edge_dist[(fr, to, mode)] = dist_km or w
            self._edge_dist[(to, fr, mode)] = dist_km or w

        def _register_node(nid, lat, lng, name, ntype):
            self.node_coords.setdefault(nid, (lat, lng))
            self.node_names.setdefault(nid, name)
            self.node_types.setdefault(nid, ntype)
            nk = name.lower().strip()
            if nk not in self.name_to_nodes:
                self.name_to_nodes[nk] = []
            if nid not in self.name_to_nodes[nk]:
                self.name_to_nodes[nk].append(nid)

        METRO_INTERCHANGE_WALK_KM = 1.5
        BUS_INTERCHANGE_WALK_KM = 0.5

        # --- 1. Metro-to-Metro (adjacent stations along lines only) ---
        for line_name, stations in db.metro_lines.items():
            stations_sorted = sorted(stations, key=lambda s: s["sequence"])
            for i in range(len(stations_sorted) - 1):
                a, b = stations_sorted[i], stations_sorted[i + 1]
                nid_a = f"metro_{a['name']}"
                nid_b = f"metro_{b['name']}"
                _register_node(nid_a, a["lat"], a["lng"], a["name"], "metro")
                _register_node(nid_b, b["lat"], b["lng"], b["name"], "metro")
                d = _get_dist(a["lat"], a["lng"], b["lat"], b["lng"])
                w = self._time_weight(d, "metro")
                _add_edge(nid_a, nid_b, w, "metro", d)

            # Interchange at same station (different lines) — connect with small walk
            for i in range(len(stations_sorted)):
                for j in range(i + 1, len(stations_sorted)):
                    a, b = stations_sorted[i], stations_sorted[j]
                    if a["name"].lower() != b["name"].lower():
                        continue
                    if a.get("line") == b.get("line"):
                        continue
                    nid_a = f"metro_{a['name']}"
                    nid_b = f"metro_{b['name']}"
                    _register_node(nid_a, a["lat"], a["lng"], a["name"], "metro")
                    _register_node(nid_b, b["lat"], b["lng"], b["name"], "metro")
                    w = METRO_METRO_TRANSFER_PENALTY
                    _add_edge(nid_a, nid_b, w, "walk", 0.1)

        # --- 2. Bus-to-Bus from GTFS trip-level stop sequences ---
        route_stop_pairs = self._load_gtfs_route_stop_pairs()
        bus_stops_added = set()
        gtfs_stop_to_db_nodes = {}

        for sid, stop in db.bus_stops.items():
            if not isinstance(stop, dict):
                continue
            name = stop.get("name", "")
            if not name:
                continue
            nid = f"bus_{sid}"
            _register_node(nid, stop["lat"], stop["lng"], name, "bus")
            bus_stops_added.add(sid)
            nk = name.lower().strip()
            if nk not in gtfs_stop_to_db_nodes:
                gtfs_stop_to_db_nodes[nk] = []
            gtfs_stop_to_db_nodes[nk].append(nid)

        # Build mapping from GTFS stop_id → normalized stop_name
        gtfs = _ensure_gtfs()
        gtfs_stop_id_to_name = {}
        if gtfs and hasattr(gtfs, '_stops_by_name') and gtfs._stops_by_name:
            for gname, (glat, glng, gsid) in gtfs._stops_by_name.items():
                gtfs_stop_id_to_name[gsid] = gname

        edge_count = 0
        if route_stop_pairs:
            for rsn, pairs in route_stop_pairs.items():
                for from_sid, to_sid in pairs:
                    from_name = gtfs_stop_id_to_name.get(from_sid)
                    to_name = gtfs_stop_id_to_name.get(to_sid)
                    if not from_name or not to_name:
                        continue
                    from_nk = from_name.lower().strip()
                    to_nk = to_name.lower().strip()
                    from_db_nodes = gtfs_stop_to_db_nodes.get(from_nk, [])
                    to_db_nodes = gtfs_stop_to_db_nodes.get(to_nk, [])
                    if not from_db_nodes or not to_db_nodes:
                        continue
                    for fnid in from_db_nodes:
                        for tnid in to_db_nodes:
                            if fnid == tnid:
                                continue
                            fc = self.node_coords.get(fnid)
                            tc = self.node_coords.get(tnid)
                            if not fc or not tc:
                                continue
                            d = _get_dist(fc[0], fc[1], tc[0], tc[1])
                            if d < 0.05 or d > 20:
                                continue
                            w = self._time_weight(d, "bus")
                            _add_edge(fnid, tnid, w, "bus", d)
                            edge_count += 1

        self._bus_stops_added = bus_stops_added

        # --- 3. Bus↔Metro interchange (within walking distance) ---
        for stn in db.metro_stations:
            mnid = f"metro_{stn['name']}"
            graph.setdefault(mnid, [])
            for sid in bus_stops_added:
                bnid = f"bus_{sid}"
                bc = self.node_coords.get(bnid)
                if not bc:
                    continue
                d = _get_dist(stn["lat"], stn["lng"], bc[0], bc[1])
                if d < METRO_INTERCHANGE_WALK_KM:
                    w = self._time_weight(d, "walk") + BUS_METRO_TRANSFER_PENALTY
                    _add_edge(mnid, bnid, w, "walk", d)

        # --- 4. Bus↔Bus walk transfers (nearby stops on different routes) ---
        bus_ids = list(bus_stops_added)
        for i, sid in enumerate(bus_ids):
            bnid = f"bus_{sid}"
            bc = self.node_coords.get(bnid)
            if not bc:
                continue
            nearby = db.find_nearby_bus_stops(bc[0], bc[1], radius_km=BUS_INTERCHANGE_WALK_KM)
            for other in nearby:
                oid = other.get("stop_id", other.get("_id", ""))
                if not oid or oid == sid:
                    continue
                obnid = f"bus_{oid}"
                if obnid not in self.node_coords:
                    continue
                d = _get_dist(bc[0], bc[1], other["lat"], other["lng"])
                if 0 < d <= BUS_INTERCHANGE_WALK_KM:
                    w = self._time_weight(d, "walk") + BUS_BUS_TRANSFER_PENALTY
                    key = (bnid, obnid, "walk")
                    key2 = (obnid, bnid, "walk")
                    if key not in edge_set and key2 not in edge_set:
                        _add_edge(bnid, obnid, w, "walk", d)
                        edge_count += 1

        self.astar.graph = graph
        _t1 = _time.time()
        logger.info(f"Graph built in {_t1 - _t0:.1f}s: {len(self.node_coords)} nodes, {len(edge_set)} edges")

    def _strip_node_prefix(self, node_id: str) -> str:
        for prefix in ("bus_", "metro_"):
            if node_id.startswith(prefix):
                return node_id[len(prefix):]
        return node_id

    def _node_name(self, node_id: str) -> str:
        return self.node_names.get(node_id, self._strip_node_prefix(node_id))

    def _resolve_to_nodes(self, lat, lng, bus_radius=1.5, metro_radius=3.0):
        nodes = []
        src_bus = db.find_nearby_bus_stops(lat, lng, bus_radius) or []
        src_metro = db.find_nearby_metro_stations(lat, lng, metro_radius) or []
        for s in src_bus[:8]:
            sid = s.get("stop_id", s.get("_id", ""))
            if sid:
                nid = f"bus_{sid}"
                if nid in self.node_coords:
                    nodes.append((nid, _haversine_dist(lat, lng, s["lat"], s["lng"])))
        for s in src_metro[:5]:
            nid = f"metro_{s['name']}"
            if nid in self.node_coords:
                nodes.append((nid, _haversine_dist(lat, lng, s["lat"], s["lng"])))
        nodes.sort(key=lambda x: x[1])
        return [n[0] for n in nodes]

    def find_enriched_routes(self, slat, slng, dlat, dlng, direct_dist, group_size, max_results=6):
        self.build_graph()
        if not self.astar or not self.astar.graph:
            return []

        gtfs = _ensure_gtfs()
        from_nodes = self._resolve_to_nodes(slat, slng)
        to_nodes = self._resolve_to_nodes(dlat, dlng)

        if not from_nodes or not to_nodes:
            return []

        enriched = []
        seen_paths = set()

        for fn in from_nodes:
            for tn in to_nodes:
                path_modes = self.astar.find_path_with_modes(fn, tn, self.node_coords)
                if not path_modes:
                    continue

                path_key = "→".join(f"{l['from']}->{l['to']}@{l['mode']}" for l in path_modes)
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)

                total_dist = 0.0
                total_walk = 0.0
                total_fare = 0
                total_duration = 0
                types_seen = set()
                enriched_legs = []

                for step in path_modes:
                    m = step["mode"]
                    raw_from = step["from"]
                    raw_to = step["to"]
                    leg_dist = self._edge_dist.get((raw_from, raw_to, m), step.get("distance_km", 0))
                    total_dist += leg_dist

                    from_name = self._node_name(raw_from)
                    to_name = self._node_name(raw_to)
                    types_seen.add(m)

                    fare = 0
                    route_numbers = []
                    route_number = ""
                    shape_path = None
                    departure_times = []
                    display_mode = m
                    line_name = ""

                    if m == "walk":
                        total_walk += leg_dist
                        dur = leg_dist * _MINUTES_PER_KM_WALK

                    elif m == "bus":
                        if gtfs:
                            common = gtfs.get_common_routes(from_name, to_name)
                            if common:
                                route_numbers = common[:3]
                                route_number = common[0]
                                shape_path = gtfs.get_shape_path_for_route(common[0])
                                deps = gtfs.get_next_buses_with_times(from_name, route_filter=common[0], limit=3)
                                departure_times = [d["departure_time"] for d in deps]
                        fare = round(db.get_bmtc_ordinary_fare(leg_dist) * group_size)
                        dur = leg_dist / BUS_SPEED_KMH * 60
                        display_mode = "bus_ordinary"

                    elif m == "metro":
                        fare = db.get_metro_fare(leg_dist) * group_size
                        metro_node = next((n for n in db.metro_stations if n["name"].lower() == from_name.lower()), None)
                        if metro_node:
                            line_name = metro_node.get("line", "")
                            route_number = line_name
                            route_numbers = [line_name]
                        dur = leg_dist / METRO_SPEED_KMH * 60
                        display_mode = "metro"

                    total_fare += fare
                    total_duration += dur

                    enriched_legs.append({
                        "from": from_name,
                        "to": to_name,
                        "mode": display_mode,
                        "route_number": route_number,
                        "route_numbers": route_numbers,
                        "line": line_name,
                        "distance_km": round(leg_dist, 2),
                        "duration_minutes": round(dur),
                        "fare": round(fare),
                        "shape_path": shape_path,
                        "departure_times": departure_times,
                    })

                if "metro" in types_seen:
                    route_type = "metro_astar"
                else:
                    route_type = "multi_modal_astar"

                enriched.append({
                    "type": route_type,
                    "total_fare": round(total_fare),
                    "total_duration_minutes": round(total_duration),
                    "total_distance_km": round(total_dist, 1),
                    "total_walking_km": round(total_walk, 1),
                    "legs": enriched_legs,
                    "transfers": len(enriched_legs) - 1,
                    "overall_score": max(60, min(99, 95 - round(total_duration / 5) - round(total_fare / 20))),
                })

        enriched.sort(key=lambda r: (-r["overall_score"], r["total_duration_minutes"]))
        return enriched[:max_results]

    def find_routes(self, slat, slng, dlat, dlng, dist, group_size):
        self.build_graph()
        if not self.astar or not self.astar.graph:
            return []

        routes = []
        from_nodes = self._resolve_to_nodes(slat, slng, bus_radius=1.0)
        to_nodes = self._resolve_to_nodes(dlat, dlng, bus_radius=1.0)

        if not from_nodes or not to_nodes:
            return []

        seen = set()
        for fn in from_nodes:
            for tn in to_nodes:
                if (fn, tn) in seen:
                    continue
                seen.add((fn, tn))
                path = self.astar.find_path(fn, tn, self.node_coords)
                if not path:
                    continue
                path_modes = self.astar.find_path_with_modes(fn, tn, self.node_coords)

                total_dist = sum(l.get("distance_km", 0) for l in path_modes)
                walk_dist = sum(l.get("distance_km", 0) for l in path_modes if l["mode"] == "walk")
                bus_dist = sum(l.get("distance_km", 0) for l in path_modes if l["mode"] == "bus")
                metro_dist = sum(l.get("distance_km", 0) for l in path_modes if l["mode"] == "metro")
                total_duration = bus_dist / BUS_SPEED_KMH * 60 + metro_dist / METRO_SPEED_KMH * 60 + walk_dist * _MINUTES_PER_KM_WALK
                total_fare = 0
                types_seen = set()

                legs = []
                for step in path_modes:
                    m = step["mode"]
                    types_seen.add(m)
                    leg_name = self._node_name(step["from"])
                    leg_to = self._node_name(step["to"])
                    raw_from = step["from"]
                    raw_to = step["to"]
                    leg_d = self._edge_dist.get((raw_from, raw_to, m), step.get("distance_km", 0))
                    fare = 0
                    if m == "metro":
                        fare = db.get_metro_fare(leg_d) * group_size
                    elif m == "bus":
                        fare = db.get_bmtc_ordinary_fare(leg_d) * group_size
                    total_fare += fare
                    dur_per_km = _MINUTES_PER_KM_WALK if m == "walk" else 60 / (BUS_SPEED_KMH if m == "bus" else METRO_SPEED_KMH)
                    legs.append({
                        "from": leg_name,
                        "to": leg_to,
                        "mode": m,
                        "distance_km": leg_d,
                        "duration_minutes": round(leg_d * dur_per_km),
                        "fare": round(fare),
                        "instructions": f"{m}: {leg_name} \u2192 {leg_to} ({leg_d:.1f}km)",
                    })

                if "metro" in types_seen:
                    route_type = "metro_astar"
                else:
                    route_type = "multi_modal_astar"

                routes.append({
                    "type": route_type,
                    "total_fare": round(total_fare),
                    "total_duration_minutes": round(total_duration),
                    "total_distance_km": round(total_dist, 1),
                    "total_walking_km": round(walk_dist, 1),
                    "legs": legs,
                    "route_numbers": [],
                    "transfers": len(legs) - 1,
                })
        return routes
