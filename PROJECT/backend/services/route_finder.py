"""N-hop route finder for VOYAGER v2 (PROMPT_2 §5).

Best-first top-K search over the static TransitAstarGraph with
forward-progress + 800m visited guards, then schedule-aware departure
resolution and real-geometry assembly per leg.

No fabricated data: bus legs get real GTFS departures + shape geometry;
metro legs use line polylines (estimated timing); walk legs use GraphHopper
foot with an explicit interpolated fallback. Train legs are emitted only when
a live/scheduled source exists (PROMPT_5) — never invented.
"""
import heapq
import time

from .fare_engine import bmtc_fare, metro_fare, kia_fare, ride_fare_range
from .gtfs_service import GTFSService
from .graphhopper_client import GraphHopperClient
from .transit_models import Leg, RoutePlan
from .transit_graph import (
    TransitAstarGraph,
    _hav_m,
    METRO_SPEED_KMH,
    WALK_SPEED_KMH,
    TRANSFER_PENALTY_MIN,
    INTERCHANGE_FIXED_MIN,
)

# Entry/exit candidate radii (bus / metro / rail) in metres
ENTRY_RADII = {"bus": 2000, "metro": 3000, "rail": 5000}
ENTRY_TOPS = {"bus": 3, "metro": 2, "rail": 1}
MAX_LEGS = 6
MAX_PATHS = 12
MAX_DUP_PER_SIG = 3  # cap near-identical plans sharing a mode combination
VISITED_RADIUS_M = 800
FORWARD_TOLERANCE_M = 500
FORWARD_TOLERANCE_METRO_M = 2500  # metro lines curve between stations
BUDGET_SENSITIVITY = 8.0  # ₹8 ≈ 1 min in the A* weight
SEARCH_DEADLINE_S = 4.0
BUFFER_MIN = 3.0  # min buffer after previous arrival before next departure
MAX_WAIT_MIN = 45.0  # departures farther than this are flagged not_running
WALK_ONLY_KM = 2.0
CACHE_TTL_S = 600  # 10 min route-plan cache


def _fmt_time(minutes: float | int) -> str:
    minutes = max(0, int(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _hav_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return _hav_m(lat1, lng1, lat2, lng2) / 1000.0


class RouteFinder:
    def __init__(self, gtfs: GTFSService, db, graphhopper: GraphHopperClient | None = None,
                 budget_pp: float = 150.0):
        self.gtfs = gtfs
        self.db = db
        self.graph = TransitAstarGraph(gtfs, db)
        self.gh = graphhopper
        self.default_budget = budget_pp
        self._cache: dict[tuple, tuple[float, list[RoutePlan]]] = {}

    # ------------------------------------------------------------ public
    def find_routes_by_coords(
        self,
        src_lat: float, src_lng: float,
        dest_lat: float, dest_lng: float,
        depart_min: int,
        group_size: int = 1,
        budget_pp: float | None = None,
        max_paths: int = MAX_PATHS,
    ) -> list[RoutePlan]:
        budget_pp = budget_pp or self.default_budget
        cache_key = (
            round(src_lat, 4), round(src_lng, 4), round(dest_lat, 4), round(dest_lng, 4),
            depart_min // 10,  # 10-min bucket
            group_size, round(budget_pp),
        )
        hit = self._cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]

        t0 = time.perf_counter()
        plans = self._plan(src_lat, src_lng, dest_lat, dest_lng,
                           depart_min, group_size, budget_pp, max_paths)
        print(f"[finder] {len(plans)} routes in {time.perf_counter() - t0:.2f}s")
        self._cache[cache_key] = (time.time(), plans)
        return plans

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------ planning
    def _plan(self, src_lat, src_lng, dest_lat, dest_lng,
              depart_min, group_size, budget_pp, max_paths) -> list[RoutePlan]:
        plans: list[RoutePlan] = []
        direct_km = _hav_km(src_lat, src_lng, dest_lat, dest_lng)

        if direct_km <= WALK_ONLY_KM:
            plans.append(self._walk_only_route(src_lat, src_lng, dest_lat, dest_lng, depart_min))

        plans.append(self._ride_route(src_lat, src_lng, dest_lat, dest_lng, group_size, depart_min))

        entries = self._candidate_nodes(src_lat, src_lng)
        exits = self._candidate_nodes(dest_lat, dest_lng)
        if not entries or not exits:
            return plans

        chains = self._search(entries, exits, dest_lat, dest_lng, depart_min, budget_pp, max_paths)
        for chain in chains:
            plan = self._assemble_chain(chain, entries, exits, src_lat, src_lng,
                                        dest_lat, dest_lng, depart_min, group_size)
            if plan and plan.legs:
                plans.append(plan)

        plans.sort(key=lambda p: (
            sum(1 for l in p.legs if l.status == "not_running"),
            p.total_duration_min,
        ))
        return plans

    # ------------------------------------------------------------ search
    def _candidate_nodes(self, lat: float, lng: float) -> list[tuple[str, float]]:
        """Top bus/metro/rail nodes near a coordinate with entry-walk distance."""
        out: list[tuple[str, float]] = []
        out.extend(self.graph.bus_nodes_near(lat, lng, ENTRY_RADII["bus"])[: ENTRY_TOPS["bus"]])
        out.extend(self.graph.metro_nodes_near(lat, lng, ENTRY_RADII["metro"])[: ENTRY_TOPS["metro"]])
        out.extend(self.graph.rail_nodes_near(lat, lng, ENTRY_RADII["rail"])[: ENTRY_TOPS["rail"]])
        return out

    def _search(self, entries, exits, dest_lat, dest_lng, depart_min, budget_pp, max_paths):
        """Best-first top-K search over the graph.

        Returns a list of chains; each chain is a list of hops
        (from_key, to_key, edge_type, edge_data) in travel order.
        """
        exit_set = {k for k, _d in exits}
        heap: list[tuple[float, int, _SearchState]] = []
        counter = 0
        labels: dict[str, dict[tuple, float]] = {}  # node -> {sig: best g_time}
        paths: list[list[tuple[str, str, str, dict]]] = []
        found_sigs: dict[tuple, int] = {}  # mode-combination signature -> count
        deadline = time.time() + SEARCH_DEADLINE_S

        for key, d in entries:
            if key in exit_set:
                continue
            node = self.graph.node(key)
            if node is None:
                continue
            g_time = d / (WALK_SPEED_KMH * 1000) * 60
            h = _hav_m(node.lat, node.lng, dest_lat, dest_lng) / (METRO_SPEED_KMH * 1000) * 60
            labels.setdefault(key, {})[()] = g_time
            state = _SearchState(key, None, g_time, 0.0, 0, (node.lat, node.lng),
                                 "entry", None, None, {}, None, ())
            heapq.heappush(heap, (g_time + h, counter, state))
            counter += 1

        while heap and len(paths) < max_paths and time.time() < deadline:
            _f, _c, st = heapq.heappop(heap)
            if st.node_key in exit_set:
                sig = st.sig or ("walk",)
                if found_sigs.get(sig, 0) >= MAX_DUP_PER_SIG:
                    continue  # already have enough plans for this mode combo
                found_sigs[sig] = found_sigs.get(sig, 0) + 1
                paths.append(st.chain())
                continue
            if st.depth >= MAX_LEGS:
                continue
            node = self.graph.node(st.node_key)
            if node is None:
                continue
            dist_to_dest = _hav_m(node.lat, node.lng, dest_lat, dest_lng)
            for nb_key, etype, edata in self.graph.neighbors(st.node_key):
                if nb_key == st.node_key:
                    continue
                nb = self.graph.node(nb_key)
                if nb is None:
                    continue
                if etype != "metro" and st.near_visited(nb.lat, nb.lng):
                    continue  # 800m visited guard (metro is linear — can't loop)
                tol = FORWARD_TOLERANCE_METRO_M if etype == "metro" else FORWARD_TOLERANCE_M
                if _hav_m(nb.lat, nb.lng, dest_lat, dest_lng) >= dist_to_dest + tol:
                    continue  # forward-progress rule

                w = edata["time_min"]
                penalty = 0.0
                fare_pp = 0.0
                metro_line = st.metro_line
                if etype == "metro":
                    edge_line = edata.get("line")
                    if st.metro_line and edge_line and edge_line != st.metro_line:
                        penalty += INTERCHANGE_FIXED_MIN + 1.0  # line switch at hub
                    metro_line = edge_line
                    fare_pp = metro_fare(edata["dist_m"] / 1000, _line_kind(edge_line)).per_person
                elif etype == "bus":
                    fare_pp = bmtc_fare("nonac", edata["dist_m"] / 1000).per_person
                elif etype == "walk":
                    if st.prev_type in ("bus", "metro"):
                        penalty += TRANSFER_PENALTY_MIN
                penalty += fare_pp / BUDGET_SENSITIVITY

                ng_time = st.g_time + w + penalty
                if etype == "walk":
                    ident = "walk"
                elif etype == "bus":
                    ident = "bus"
                else:
                    ident = edata.get("line") or "metro"
                new_depth = st.depth + (0 if ident == st.seg_id else 1)
                new_sig = st.sig + (ident,) if ident != st.seg_id else st.sig
                lbl = labels.setdefault(nb_key, {})
                prev = lbl.get(new_sig)
                if prev is not None and prev <= ng_time:
                    continue  # same signature already reached faster
                lbl[new_sig] = ng_time
                if len(lbl) > 6:  # bound per-node labels; drop worst time
                    worst = max(lbl, key=lbl.get)
                    del lbl[worst]

                nh = _hav_m(nb.lat, nb.lng, dest_lat, dest_lng) / (METRO_SPEED_KMH * 1000) * 60
                new_state = _SearchState(nb_key, st, ng_time, st.g_fare + fare_pp, new_depth,
                                         (nb.lat, nb.lng), etype, metro_line, st.metro_line,
                                         edata, ident, new_sig)
                heapq.heappush(heap, (ng_time + nh, counter, new_state))
                counter += 1
        return paths

    # ------------------------------------------------------------ assembly
    def _assemble_chain(self, chain, entries, exits, src_lat, src_lng, dest_lat, dest_lng,
                        depart_min, group_size) -> RoutePlan | None:
        entry_key, entry_dist = self._best_entry(chain, entries)
        exit_key, exit_dist = self._best_exit(chain, exits)
        if self.graph.node(entry_key) is None:
            return None

        legs: list[Leg] = []
        t = depart_min

        if entry_dist > 40:
            en = self.graph.node(entry_key)
            legs.append(self._walk_leg(src_lat, src_lng, en.lat, en.lng, depart_min, entry_dist))
            t += entry_dist / (WALK_SPEED_KMH * 1000) * 60

        merged = self._merge_edges(chain)
        for from_key, to_key, etype, edata, intermediates in merged:
            fnode, tnode = self.graph.node(from_key), self.graph.node(to_key)
            if fnode is None or tnode is None:
                continue
            if etype == "walk":
                legs.append(self._walk_leg(fnode.lat, fnode.lng, tnode.lat, tnode.lng,
                                           int(round(t)), edata["dist_m"],
                                           from_stop=fnode.name, to_stop=tnode.name))
                t += edata["time_min"]
            elif etype == "bus":
                leg = self._bus_leg(fnode, tnode, edata, t, group_size)
                legs.append(leg)
                t = leg.arrive_time_min or (t + edata["time_min"])
            elif etype == "metro":
                leg = self._metro_leg(fnode, tnode, edata, t, group_size, intermediates)
                legs.append(leg)
                t = leg.arrive_time_min or (t + edata["time_min"])

        if exit_dist > 40:
            xn = self.graph.node(exit_key)
            legs.append(self._walk_leg(xn.lat, xn.lng, dest_lat, dest_lng,
                                       int(round(t)), exit_dist))

        if not legs:
            return None
        total_fare = sum(l.fare for l in legs if l.mode in ("bus", "metro"))
        arrival = max(l.arrive_time_min or 0 for l in legs)
        total_dur = max(0, int(arrival - depart_min))
        total_walk = sum(l.distance_m for l in legs if l.mode == "walk") / 1000
        transfers = sum(1 for a, b in zip(legs, legs[1:])
                        if a.mode in ("bus", "metro") and b.mode in ("bus", "metro"))
        per_person = round(total_fare / max(1, group_size), 2)
        return RoutePlan(legs=legs, total_fare=total_fare, total_duration_min=total_dur,
                         total_walk_km=total_walk, transfers=transfers, per_person_fare=per_person)

    def _merge_edges(self, chain) -> list[tuple[str, str, str, dict, list]]:
        """Collapse consecutive same-mode ride edges (bus-bus, metro-metro) into one leg.

        Chain hops are (from_key, to_key, edge_type, edge_data). The merged
        tuple gains a 5th element: intermediate node keys (metro station
        polyline), empty for bus/walk.
        """
        out: list[tuple[str, str, str, dict, list]] = []
        for fk, tk, etype, edata in chain:
            if out and out[-1][2] == etype:
                pfk, _ptk, _pt, pedata, pinter = out[-1]
                if etype == "metro" and pedata.get("line") == edata.get("line"):
                    out[-1] = (pfk, tk, etype, {
                        "time_min": pedata["time_min"] + edata["time_min"],
                        "dist_m": pedata["dist_m"] + edata["dist_m"],
                        "line": edata.get("line"),
                        "routes": sorted(set(pedata.get("routes", [])) | set(edata.get("routes", []))),
                    }, pinter + [fk])
                    continue
                if etype == "bus":
                    inter = set(pedata.get("routes", [])) & set(edata.get("routes", []))
                    if inter:
                        out[-1] = (pfk, tk, etype, {
                            "time_min": pedata["time_min"] + edata["time_min"],
                            "dist_m": pedata["dist_m"] + edata["dist_m"],
                            "routes": sorted(inter),
                        }, [])
                        continue
            out.append((fk, tk, etype, edata, []))
        return out

    # ------------------------------------------------------------ leg builders
    def _bus_leg(self, fnode, tnode, edata, t_min, group_size) -> Leg:
        from_stop, to_stop = fnode.name, tnode.name
        dist_km = edata["dist_m"] / 1000
        after = _fmt_time(int(round(t_min + BUFFER_MIN)))
        wanted = set(edata.get("routes", []))
        deps = self.gtfs.earliest_departures(from_stop, after, max_n=6, route_filter=wanted)
        route_id = None
        depart = int(round(t_min + BUFFER_MIN))
        status = "scheduled"
        alternate: list[str] = []
        if deps:
            dep = deps[0]
            route_id = dep.route_number
            depart = dep.departure_minutes
            alternate = [d.route_number for d in deps[1:]]
        else:
            any_deps = self.gtfs.earliest_departures(from_stop, after, max_n=6)
            if any_deps:
                dep = any_deps[0]
                route_id = dep.route_number
                depart = dep.departure_minutes
                alternate = [d.route_number for d in any_deps[1:]]
            else:
                status = "not_running"

        duration = int(round(edata["time_min"]))
        arrive = depart + duration

        if status == "scheduled" and (depart - int(round(t_min + BUFFER_MIN))) > MAX_WAIT_MIN:
            status = "not_running"  # next departure is hours away — not a live option

        if route_id and route_id.upper().startswith("KIA"):
            fare = kia_fare(route_id, dist_km).amount
        else:
            fare = bmtc_fare("nonac", dist_km).amount
        pp = round(fare / max(1, group_size), 2)

        geometry = None
        geo_src = "interpolated"
        for rid in [route_id] + alternate:
            if not rid:
                continue
            seg = self.gtfs.get_stop_to_stop_segment(rid, from_stop, to_stop)
            if seg:
                geometry, geo_src = seg, "gtfs_shape"
                break
        if geometry is None and self.gh is not None:
            try:
                gh = self.gh.route("car", fnode.lat, fnode.lng, tnode.lat, tnode.lng)
                if gh:
                    geometry, geo_src = gh.geometry, "graphhopper"
            except Exception:
                pass

        return Leg(mode="bus", route_number=route_id, from_stop=from_stop, to_stop=to_stop,
                   from_lat=fnode.lat, from_lng=fnode.lng, to_lat=tnode.lat, to_lng=tnode.lng,
                   depart_time=_fmt_time(depart), arrive_time=_fmt_time(arrive),
                   depart_time_min=depart, arrive_time_min=arrive,
                   duration_min=duration, distance_m=edata["dist_m"], fare=fare,
                   per_person_fare=pp,
                   geometry=geometry or [(fnode.lat, fnode.lng), (tnode.lat, tnode.lng)],
                   geometry_source=geo_src, status=status, alternate_routes=alternate)

    def _metro_leg(self, fnode, tnode, edata, t_min, group_size, intermediates=()) -> Leg:
        line = edata.get("line") or "Purple Line"
        depart = int(round(t_min + BUFFER_MIN))
        duration = int(round(edata["time_min"]))
        arrive = depart + duration
        dist_km = edata["dist_m"] / 1000
        fare = metro_fare(dist_km, _line_kind(line)).amount
        pp = round(fare / max(1, group_size), 2)
        geo: list[tuple[float, float]] = [(fnode.lat, fnode.lng)]
        for k in intermediates:
            n = self.graph.node(k)
            if n is not None:
                geo.append((n.lat, n.lng))
        geo.append((tnode.lat, tnode.lng))
        return Leg(mode="metro", route_number=_line_short(line), line=line,
                   from_stop=fnode.name, to_stop=tnode.name,
                   from_lat=fnode.lat, from_lng=fnode.lng, to_lat=tnode.lat, to_lng=tnode.lng,
                   depart_time=_fmt_time(depart), arrive_time=_fmt_time(arrive),
                   depart_time_min=depart, arrive_time_min=arrive,
                   duration_min=duration, distance_m=edata["dist_m"], fare=fare, per_person_fare=pp,
                   geometry=geo, geometry_source="metro_line", status="estimated")

    def _walk_leg(self, lat1, lng1, lat2, lng2, t_min, dist_m, from_stop: str = "", to_stop: str = "") -> Leg:
        duration = max(1, int(round(dist_m / (WALK_SPEED_KMH * 1000) * 60)))
        geometry = None
        geo_src = "interpolated"
        if self.gh is not None:
            try:
                gh = self.gh.route("foot", lat1, lng1, lat2, lng2)
                if gh:
                    geometry, geo_src = gh.geometry, "graphhopper"
            except Exception:
                pass
        return Leg(mode="walk", from_stop=from_stop, to_stop=to_stop,
                   from_lat=lat1, from_lng=lng1, to_lat=lat2, to_lng=lng2,
                   depart_time=_fmt_time(t_min), arrive_time=_fmt_time(t_min + duration),
                   depart_time_min=int(round(t_min)), arrive_time_min=int(round(t_min + duration)),
                   duration_min=duration, distance_m=dist_m, fare=0.0,
                   geometry=geometry or [(lat1, lng1), (lat2, lng2)],
                   geometry_source=geo_src, status="estimated")

    def _walk_only_route(self, src_lat, src_lng, dest_lat, dest_lng, depart_min) -> RoutePlan:
        dist = _hav_m(src_lat, src_lng, dest_lat, dest_lng)
        leg = self._walk_leg(src_lat, src_lng, dest_lat, dest_lng, depart_min, dist)
        return RoutePlan(legs=[leg], total_fare=0.0, total_duration_min=leg.duration_min,
                         total_walk_km=dist / 1000, transfers=0, per_person_fare=0.0)

    def _ride_route(self, src_lat, src_lng, dest_lat, dest_lng, group_size, depart_min) -> RoutePlan:
        dist_km = _hav_km(src_lat, src_lng, dest_lat, dest_lng)
        duration = max(1, int(round(dist_km / 30 * 60)))
        lo, hi = ride_fare_range("uber_go", dist_km, group_size)
        geometry = None
        geo_src = "interpolated"
        if self.gh is not None:
            try:
                gh = self.gh.route("car", src_lat, src_lng, dest_lat, dest_lng)
                if gh:
                    geometry, geo_src = gh.geometry, "graphhopper"
                    duration = max(1, int(round(gh.duration_s / 60)))
            except Exception:
                pass
        leg = Leg(mode="ride", from_stop="", to_stop="",
                  from_lat=src_lat, from_lng=src_lng, to_lat=dest_lat, to_lng=dest_lng,
                  depart_time=_fmt_time(depart_min),
                  arrive_time=_fmt_time(depart_min + duration),
                  depart_time_min=int(depart_min), arrive_time_min=int(depart_min + duration),
                  duration_min=duration, distance_m=dist_km * 1000, fare=lo.amount,
                  per_person_fare=lo.per_person,
                  geometry=geometry or [(src_lat, src_lng), (dest_lat, dest_lng)],
                  geometry_source=geo_src, status="estimated")
        return RoutePlan(legs=[leg], total_fare=lo.amount, total_duration_min=duration,
                         total_walk_km=0.0, transfers=0, per_person_fare=lo.per_person)

    def _best_entry(self, chain, entries) -> tuple[str, float]:
        first_from = chain[0][0]
        for k, d in entries:
            if k == first_from:
                return k, d
        return entries[0]

    def _best_exit(self, chain, exits) -> tuple[str, float]:
        last_to = chain[-1][1]
        for k, d in exits:
            if k == last_to:
                return k, d
        return exits[0]


class _SearchState:
    __slots__ = ("node_key", "parent", "g_time", "g_fare", "depth",
                 "pos", "prev_type", "metro_line", "prev_line", "prev_edata", "seg_id", "sig")

    def __init__(self, node_key, parent, g_time, g_fare, depth, pos, prev_type,
                 metro_line, prev_line, prev_edata, seg_id, sig):
        self.node_key = node_key
        self.parent = parent
        self.g_time = g_time
        self.g_fare = g_fare
        self.depth = depth
        self.pos = pos
        self.prev_type = prev_type
        self.metro_line = metro_line
        self.prev_line = prev_line
        self.prev_edata = prev_edata
        self.seg_id = seg_id
        self.sig = sig

    def near_visited(self, lat: float, lng: float) -> bool:
        s = self
        while s is not None:
            if _hav_m(s.pos[0], s.pos[1], lat, lng) < VISITED_RADIUS_M:
                return True
            s = s.parent
        return False

    def chain(self) -> list[tuple[str, str, str, dict]]:
        """Reconstruct hops (from_key, to_key, edge_type, edge_data) in travel order."""
        hops: list[tuple[str, str, str, dict]] = []
        cur, parent = self, self.parent
        while parent is not None:
            hops.append((parent.node_key, cur.node_key, cur.prev_type, cur.prev_edata))
            cur, parent = parent, parent.parent
        hops.reverse()
        return hops


def _line_kind(line: str | None) -> str:
    return ("green" if line and "Green" in line else "purple")


def _line_short(line: str | None) -> str | None:
    if not line:
        return None
    return "Green" if "Green" in line else "Purple"
