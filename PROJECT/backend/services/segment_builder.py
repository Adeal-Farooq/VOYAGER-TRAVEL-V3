"""Interactive segment planner (PROMPT_3) — the hop mechanism.

Builds the tree-of-choices for a multi-hop public-transit journey:
  - `build_segments()` -> Segment 1 FULL + Segment 2 FULL (grouped by
    connectedFrom) + probes for Segment 3+.
  - `build_segment_next()` -> recompute the next segment time-chained from
    the user's chosen leg.

Every leg carries REAL data only: GTFS bus departures + stop-to-stop shape
slices, metro line rides (estimated timing), GraphHopper foot walks. No
fabricated routes/times/fares. If GTFS has no service for a stop it gets no
transit options (walk may still appear, and is excluded when pointless).

Forward-progress hard rule: a candidate arrival stop is kept only when
hav(candidate -> dest) < hav(anchor -> dest) + tolerance. Users are never
routed away from the destination.
"""
import time
from datetime import datetime, timezone

from .data_schema import MetroStation
from .gtfs_service import GTFSService
from .graphhopper_client import GraphHopperClient
from .transit_graph import TransitAstarGraph, WALK_SPEED_KMH, BUS_SPEED_KMH, METRO_SPEED_KMH, _hav_m

# Candidate radii (bus/metro/rail) around the current anchor, metres
BUS_CAND_RADIUS_M = 3000
METRO_CAND_RADIUS_M = 3000
RAIL_CAND_RADIUS_M = 5000
# Walk-to-boarding reach around the anchor
WALK_TO_BOARD_M = 1500
# Hard forward-progress tolerance; metro stations may sit off the beeline
FORWARD_TOLERANCE_M = 500
FORWARD_TOLERANCE_METRO_M = 2500
# Buffers / windows
BUFFER_MIN = 4.0          # catch-the-bus buffer after arrival (PROMPT_3 §3.2)
MAX_WAIT_MIN = 45.0       # departures farther than this -> not_running
DEP_WINDOW_MIN = 180      # departure scan window
# Bounds so the tree stays responsive (PROMPT_3 §5)
MAX_WALK_OPTIONS = 5
MAX_BOARD_BUS = 3
MAX_BOARD_METRO = 2
MAX_ROUTES_PER_STOP = 4
MAX_ARRIVAL_STOPS_PER_ROUTE = 3
MAX_METRO_TRANSFER = 2      # long-haul bus->metro interchange rides offered
MAX_ANCHORS_SEG2 = 6
MAX_SEG2_OPTIONS = 40
MAX_PROBES = 6
CACHE_TTL_S = 300         # 5 min segments cache (PROMPT_3 §5)

WALK_OPTION_MAX_M = 2000   # walk option always present for any stop <= 2km
WALK_PRIMARY_M = 1500      # distance <= 1.5km -> WALK is primary (no cab/bike)


def _hav(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return _hav_m(lat1, lng1, lat2, lng2)


def _fmt(minutes: int) -> str:
    minutes = max(0, int(minutes)) % 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _parse_current_time(iso: str | None):
    if iso:
        try:
            dt = datetime.fromisoformat(iso)
            return dt.hour * 60 + dt.minute, iso
        except (ValueError, TypeError):
            pass
    now = datetime.now().astimezone()
    return now.hour * 60 + now.minute, now.isoformat()


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


class SegmentBuilder:
    """Stateless-per-request builder (cache = read-through only)."""

    def __init__(self, gtfs: GTFSService, db, gh: GraphHopperClient | None = None,
                 graph: TransitAstarGraph | None = None):
        self.gtfs = gtfs
        self.db = db
        self.gh = gh
        self.graph = graph or TransitAstarGraph(gtfs, db)
        self._cache: dict[tuple, tuple[float, dict]] = {}

    # ============================================================ public API
    def build_segments(self, source: dict, destination: dict, group_size: int,
                       budget: float, current_time: str | None = None) -> dict:
        now_min, iso = _parse_current_time(current_time)
        key = (round(source["lat"], 4), round(source["lng"], 4),
               round(destination["lat"], 4), round(destination["lng"], 4),
               now_min // 10, group_size, round(budget))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            return hit[1]

        journey = {"source": source, "destination": destination, "generated_at": iso or _generated_at()}
        seg1 = self._build_segment_1(source, destination, now_min, group_size, budget)
        seg2 = self._build_segment_2(source, destination, seg1["options"], now_min,
                                     group_size, budget)
        probes = self._build_probes(source, destination, seg2, now_min, group_size, budget)

        warnings = self._warnings(now_min, seg1["options"] + seg2["options"])
        resp = {
            "journey": journey,
            "segments": [seg1, seg2],
            "probes": probes,
            "warnings": warnings,
            "journeyComplete": False,
            "timeline": [],
        }
        self._cache[key] = (time.time(), resp)
        return resp

    def build_segment_next(self, journey: dict, chosen_legs: list[dict],
                           group_size: int, budget: float) -> dict:
        """Recompute the next segment time-chained from the last chosen leg.

        `chosen_legs` = [{"optionId", "arrivalTime", "destinationStop"}, ...]
        in travel order. Returns Segment N (options only connected from the
        last chosen stop, departures >= arrival + buffer) + probes. Returns
        `journeyComplete: true` when the last stop is within ~500m of dest.
        """
        dest = journey["destination"]
        if not chosen_legs:
            return {"journey": journey, "segments": [], "probes": [], "warnings": [],
                    "journeyComplete": False, "timeline": []}

        last = chosen_legs[-1]
        stop_name = last["destinationStop"]
        anchor = self._resolve_stop(stop_name)
        arrival_min = self._parse_hhmm(last.get("arrivalTime")) or 0
        now_min = int(arrival_min + BUFFER_MIN)

        if anchor is not None:
            d = _hav(anchor["lat"], anchor["lng"], dest["lat"], dest["lng"])
        else:
            d = 1e9
        if d <= 500.0:  # within ~500m of final destination
            timeline = [self._timeline_item(c) for c in chosen_legs]
            return {"journey": journey, "segments": [], "probes": [], "warnings": [],
                    "journeyComplete": True, "timeline": timeline,
                    "arrival": {"message": "You have arrived", "destination": dest}}

        seg = self._build_segment_from_anchor(
            anchor_lat=anchor["lat"] if anchor else dest["lat"],
            anchor_lng=anchor["lng"] if anchor else dest["lng"],
            anchor_name=anchor["name"] if anchor else stop_name,
            dest_lat=dest["lat"], dest_lng=dest["lng"],
            now_min=now_min, group_size=group_size, budget=budget,
            seg_num=len(chosen_legs) + 1, connected_from=stop_name,
        )
        probes = self._probes_for_segment(seg, dest, group_size, budget)
        return {"journey": journey, "segments": [seg], "probes": probes,
                "warnings": self._warnings(now_min, seg["options"]),
                "journeyComplete": False, "timeline": []}

    # ============================================================ segment 1
    def _build_segment_1(self, source, destination, now_min, group_size, budget) -> dict:
        cand = self._candidate_stops(source["lat"], source["lng"],
                                     destination["lat"], destination["lng"])
        options: list[dict] = []

        # walk options (always present for any stop <= 2km; primary <= 1.5km)
        walk_cands = [c for c in cand if c["dist_m"] <= WALK_OPTION_MAX_M][:MAX_WALK_OPTIONS]
        for c in walk_cands:
            opt = self._walk_option(source, c, now_min, group_size, budget,
                                    connected_from=None, seg_num=1)
            if opt:
                options.append(opt)

        # transit options: board a stop near the source, ride to a forward stop
        options.extend(self._transit_options(
            source["lat"], source["lng"], destination["lat"], destination["lng"],
            now_min, group_size, budget, connected_from=None, seg_num=1))

        for opt in options:
            self._fill_transit_count(opt, now_min)
        self._mark_top_recommended(options, now_min, walk_cands)
        for opt in options:
            if opt["mode"] == "walk" and not opt["probeNext"]:
                p = self._probe_from_stop(opt["destinationStop"], destination,
                                          int((opt.get("arrivalMin") or now_min) + BUFFER_MIN),
                                          group_size, budget)
                if p:
                    opt["probeNext"] = [p]
        return {"segmentId": 1, "title": "Segment 1: Getting out of your current location",
                "sourceName": source.get("name"), "arrivalAtSegmentStart": None,
                "options": options}

    # ============================================================ segment 2
    def _build_segment_2(self, source, destination, seg1_options, now_min,
                         group_size, budget) -> dict:
        """Segment 2 = options chained from each segment-1 arrival stop."""
        arrivals: dict[str, dict] = {}
        for opt in seg1_options:
            stop = opt["destinationStop"]
            name = stop["name"]
            arr = opt.get("arrivalMin") or 0
            if name not in arrivals or arr < arrivals[name]["arrivalMin"]:
                arrivals[name] = {"stop": stop, "arrivalMin": arr}
        anchors = sorted(arrivals.values(), key=lambda a: a["arrivalMin"])
        anchors = anchors[:MAX_ANCHORS_SEG2]

        options: list[dict] = []
        for a in anchors:
            opts = self._options_from_stop(
                a["stop"], destination, int(a["arrivalMin"] + BUFFER_MIN),
                group_size, budget, seg_num=2, connected_from=a["stop"]["name"])
            options.extend(opts)
        options = options[:MAX_SEG2_OPTIONS]
        for opt in options:
            self._fill_transit_count(opt, opt.get("arrivalMin") or now_min)
        self._mark_top_recommended(options, now_min, None)
        return {"segmentId": 2, "title": "Segment 2: Main Transit Leg",
                "sourceName": None, "arrivalAtSegmentStart": None, "options": options}

    # ======================================================= general builders
    def _options_from_stop(self, stop: dict, destination, now_min, group_size,
                           budget, seg_num, connected_from) -> list[dict]:
        """Options whose anchor is an actual stop (segment 2+)."""
        cand = self._candidate_stops(stop["lat"], stop["lng"],
                                     destination["lat"], destination["lng"])
        options: list[dict] = []
        walk_shown = 0
        for c in cand:
            if c["dist_m"] <= WALK_OPTION_MAX_M and walk_shown < 3:
                opt = self._walk_option(stop, c, now_min, group_size, budget,
                                        connected_from=connected_from, seg_num=seg_num)
                if opt:
                    options.append(opt)
                    walk_shown += 1
        options.extend(self._transit_options(
            stop["lat"], stop["lng"], destination["lat"], destination["lng"],
            now_min, group_size, budget, connected_from=connected_from, seg_num=seg_num))
        return options

    def _build_segment_from_anchor(self, anchor_lat, anchor_lng, anchor_name,
                                   dest_lat, dest_lng, now_min, group_size,
                                   budget, seg_num, connected_from) -> dict:
        anchor_pt = {"name": anchor_name, "lat": anchor_lat, "lng": anchor_lng}
        cand = self._candidate_stops(anchor_lat, anchor_lng, dest_lat, dest_lng)
        opts = []
        walk_shown = 0
        for c in cand:
            if c["dist_m"] <= WALK_OPTION_MAX_M and walk_shown < 3:
                w = self._walk_option(anchor_pt, c, now_min, group_size, budget,
                                      connected_from=connected_from, seg_num=seg_num)
                if w:
                    opts.append(w)
                    walk_shown += 1
        opts.extend(self._transit_options(anchor_lat, anchor_lng, dest_lat, dest_lng,
                                          now_min, group_size, budget,
                                          connected_from=connected_from, seg_num=seg_num))
        for opt in opts:
            self._fill_transit_count(opt, now_min)
        self._mark_top_recommended(opts, now_min, cand[:3] if walk_shown else None)
        return {"segmentId": seg_num,
                "title": f"Segment {seg_num}: Onward connections",
                "sourceName": anchor_name, "arrivalAtSegmentStart": _fmt(now_min),
                "options": opts}

    # ------------------------------------------------------------ candidates
    def _candidate_stops(self, lat, lng, dest_lat, dest_lng) -> list[dict]:
        """Nearby bus/metro/rail stops passing the forward-progress rule."""
        base = _hav(lat, lng, dest_lat, dest_lng)
        out: list[dict] = []

        def add(kind, name, slat, slng):
            dist = _hav(lat, lng, slat, slng)
            if dist < 25:  # the anchor itself / noise — no zero-distance walks
                return
            if kind == "metro":
                tol = FORWARD_TOLERANCE_METRO_M
            else:
                tol = FORWARD_TOLERANCE_M
            if _hav(slat, slng, dest_lat, dest_lng) < base + tol:
                out.append({"kind": kind, "name": name, "lat": slat, "lng": slng,
                            "dist_m": dist})

        for s in self.db.bus_stops_near(lat, lng, BUS_CAND_RADIUS_M):
            add("bus", s.name, s.lat, s.lng)
        for m in self.db.metro_near(lat, lng, METRO_CAND_RADIUS_M):
            add("metro", m.name, m.lat, m.lng)
        for r in self.db.rail_near(lat, lng, RAIL_CAND_RADIUS_M):
            add("rail", r.name, r.lat, r.lng)

        out.sort(key=lambda c: (c["dist_m"], c["kind"]))
        # cap per kind to keep the tree bounded
        capped: list[dict] = []
        counts = {"bus": 0, "metro": 0, "rail": 0}
        caps = {"bus": 8, "metro": 5, "rail": 3}
        for c in out:
            if counts[c["kind"]] >= caps[c["kind"]]:
                continue
            counts[c["kind"]] += 1
            capped.append(c)
        return capped

    # ------------------------------------------------------------ walk
    def _walk_option(self, from_pt, cand: dict, now_min, group_size, budget,
                     connected_from, seg_num) -> dict | None:
        dist_m = cand["dist_m"]
        if dist_m > WALK_OPTION_MAX_M:
            return None
        duration = max(1, int(round(dist_m / (WALK_SPEED_KMH * 1000) * 60)))
        geometry, geo_src = self._walk_geometry(from_pt, cand)
        arrival_min = now_min + duration
        return {
            "optionId": f"s{seg_num}_walk_{self._slug(cand['name'])}",
            "destinationStop": {"name": cand["name"], "lat": cand["lat"], "lng": cand["lng"]},
            "mode": "walk", "routeNumber": None,
            "fromStop": from_pt.get("name") if isinstance(from_pt, dict) else str(from_pt),
            "distanceKm": round(dist_m / 1000.0, 2),
            "durationMin": duration,
            "departureTime": "Now",
            "arrivalTime": _fmt(arrival_min),
            "arrivalMin": arrival_min,
            "fare": 0.0, "perPersonFare": 0.0,
            "geometry": geometry, "geometrySource": geo_src,
            "status": "estimated",
            "isTopRecommended": False,
            "connectedFrom": connected_from,
            "transitOptionsFromThisStop": 0,
            "probeNext": [],
            "exceedsBudget": False,
        }

    def _walk_geometry(self, from_pt, to_pt) -> tuple[list, str]:
        f = from_pt
        if self.gh is not None:
            try:
                gh = self.gh.route("foot", f["lat"], f["lng"], to_pt["lat"], to_pt["lng"])
                if gh:
                    return gh.geometry, "graphhopper"
            except Exception:
                pass
        return [(f["lat"], f["lng"]), (to_pt["lat"], to_pt["lng"])], "interpolated"

    # ------------------------------------------------------------ transit
    def _transit_options(self, lat, lng, dest_lat, dest_lng, now_min, group_size,
                         budget, connected_from, seg_num) -> list[dict]:
        """Bus + metro rides that move toward the destination.

        A ride = walk to a boarding stop/station (implied, added to the wait
        buffer), take a real route/line, get off at a forward-progress stop.
        """
        options: list[dict] = []

        bus_board = self.graph.bus_nodes_near(lat, lng, WALK_TO_BOARD_M)[:MAX_BOARD_BUS]
        for board_key, board_dist in bus_board:
            board_node = self.graph.node(board_key)
            if board_node is None:
                continue
            walk_to_board = max(1, int(round(board_dist / (WALK_SPEED_KMH * 1000) * 60)))
            board_after = now_min + walk_to_board + int(BUFFER_MIN)
            for opt in self._bus_rides(board_node, board_after, dest_lat, dest_lng,
                                       group_size, budget, connected_from, seg_num):
                opt["_walkToBoard"] = walk_to_board
                opt["_fromLat"], opt["_fromLng"] = board_node.lat, board_node.lng
                options.append(opt)

        metro_board = self.graph.metro_nodes_near(lat, lng, METRO_CAND_RADIUS_M)[:MAX_BOARD_METRO]
        for station_key, station_dist in metro_board:
            station_node = self.graph.node(station_key)
            if station_node is None:
                continue
            walk_to_board = max(1, int(round(station_dist / (WALK_SPEED_KMH * 1000) * 60)))
            board_after = now_min + walk_to_board + int(BUFFER_MIN)
            for mopt in self._metro_rides(station_node, board_after, dest_lat, dest_lng,
                                          group_size, budget, connected_from, seg_num):
                mopt["_walkToBoard"] = walk_to_board
                mopt["_fromLat"], mopt["_fromLng"] = station_node.lat, station_node.lng
                options.append(mopt)

        # dedupe by (mode, route, destStop)
        seen: set[tuple] = set()
        deduped: list[dict] = []
        for o in options:
            key = (o["mode"], o.get("routeNumber"), o["destinationStop"]["name"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(o)
        return deduped

    def _bus_rides(self, board_node, board_after, dest_lat, dest_lng, group_size,
                   budget, connected_from, seg_num) -> list[dict]:
        """Real GTFS departures from the boarding stop, riding to forward stops."""
        from .fare_engine import bmtc_fare, kia_fare

        dep = self.gtfs.earliest_departures(board_node.name, _fmt(board_after),
                                            max_n=12, window_min=DEP_WINDOW_MIN)
        if not dep:
            dep = self.gtfs.get_routes_at_stop(board_node.name, _fmt(board_after))
        # distinct routes first, keep the earliest per route
        by_route: dict[str, dict] = {}
        for d in dep:
            if d.route_number not in by_route:
                by_route[d.route_number] = d
        all_routes = list(by_route.values())
        routes = all_routes[:MAX_ROUTES_PER_STOP]

        out: list[dict] = []
        for d in routes:
            # departures farther than MAX_WAIT from the anchor are not live
            not_running = (d.departure_minutes - board_after) > MAX_WAIT_MIN
            # walk along the route shape in the direction that heads toward dest
            forward = self._route_forward_stops(d.route_number, board_node.name,
                                                dest_lat, dest_lng)
            # cap: only real stop-to-stop slices, never the full route
            for i, stop_name in enumerate(forward[:MAX_ARRIVAL_STOPS_PER_ROUTE]):
                if not self._forward_progress(board_node.lat, board_node.lng,
                                              dest_lat, dest_lng, forward[i][1], forward[i][2]):
                    continue
                opt = self._bus_ride_option(board_node, d, forward[i], dest_lat, dest_lng,
                                            group_size, budget, connected_from, seg_num,
                                            not_running=not_running)
                if opt:
                    out.append(opt)
        # long-haul bus -> metro interchange rides (checked over ALL routes, not
        # just the short-hop-capped ones) — e.g. 285-M -> Kempegowda Bus Station
        # (Majestic), then metro to dest. Kept deliberately small (earliest first).
        transfer_added = 0
        for d in all_routes:
            if transfer_added >= MAX_METRO_TRANSFER:
                break
            if d.route_number in {r.route_number for r in routes}:
                continue
            not_running = (d.departure_minutes - board_after) > MAX_WAIT_MIN
            forward = self._route_forward_stops(d.route_number, board_node.name,
                                                dest_lat, dest_lng)
            transfer = self._metro_transfer_stop(forward, board_node, dest_lat, dest_lng)
            if transfer:
                opt = self._bus_ride_option(board_node, d, transfer, dest_lat, dest_lng,
                                            group_size, budget, connected_from, seg_num,
                                            not_running=not_running)
                if opt:
                    opt["isMetroTransfer"] = True
                    out.append(opt)
                    transfer_added += 1
        return out

    def _metro_transfer_stop(self, forward, board_node, dest_lat, dest_lng):
        """Farthest forward stop on a route that sits near a metro station.

        Lets a user ride the bus to a metro interchange (then metro to dest),
        instead of only seeing the first few stops of the ride.
        """
        best = None
        for i in range(MAX_ARRIVAL_STOPS_PER_ROUTE, len(forward)):
            name, slat, slng = forward[i]
            if not self._forward_progress(board_node.lat, board_node.lng,
                                          dest_lat, dest_lng, slat, slng):
                continue
            near = self.db.metro_near(slat, slng, WALK_TO_BOARD_M)
            if near:
                best = (name, slat, slng)
        return best

    def _bus_ride_option(self, board_node, dep, fwd, dest_lat, dest_lng,
                         group_size, budget, connected_from, seg_num,
                         not_running: bool = False) -> dict | None:
        """One bus ride: depart board_node on dep.route_number, get off at fwd stop."""
        from .fare_engine import bmtc_fare, kia_fare

        dest_stop, dlat, dlng = fwd[0], fwd[1], fwd[2]
        wait = dep.departure_minutes
        # ride duration via graph edges between board and dest (same route)
        duration, dist_m = self._route_ride_duration(board_node.name, dest_stop,
                                                     dep.route_number)
        arrive = wait + duration
        status = "not_running" if not_running else "scheduled"

        # fare
        if dep.route_number.upper().startswith("KIA"):
            fare = kia_fare(dep.route_number, dist_m / 1000.0).amount or 0.0
        else:
            fare = bmtc_fare("nonac", dist_m / 1000.0).amount or 0.0
        pp = fare
        total = pp * max(1, group_size)
        exceeds = total > budget and fare > 0

        geometry, geo_src = self._bus_geometry(dep.route_number, board_node.name, dest_stop)

        return {
            "optionId": f"s{seg_num}_bus_{self._slug(dep.route_number)}_{self._slug(dest_stop)}",
            "destinationStop": {"name": dest_stop, "lat": dlat, "lng": dlng},
            "mode": "bus", "routeNumber": dep.route_number,
            "fromStop": board_node.name,
            "distanceKm": round(dist_m / 1000.0, 2),
            "durationMin": duration,
            "departureTime": _fmt(wait),
            "arrivalTime": _fmt(arrive),
            "arrivalMin": arrive,
            "fare": round(fare, 2), "perPersonFare": round(pp, 2),
            "geometry": geometry, "geometrySource": geo_src,
            "status": status,
            "isTopRecommended": False,
            "connectedFrom": connected_from,
            "transitOptionsFromThisStop": 0,
            "probeNext": [],
            "isMetroTransfer": False,
            "exceedsBudget": exceeds,
        }

    def _metro_rides(self, station_node, board_after, dest_lat, dest_lng, group_size,
                     budget, connected_from, seg_num) -> list[dict]:
        """Ride a metro line from the boarding station to forward stations."""
        from .fare_engine import metro_fare

        # Interchange stations (e.g. Majestic) carry "Purple Line,Green Line" on the
        # node; edges store a single line, so try each line the node serves.
        lines = [ln.strip() for ln in (station_node.line or "Purple Line").split(",")]
        out: list[dict] = []
        for line in lines:
            for fwd in self._metro_forward_stations(station_node, line, dest_lat, dest_lng):
                dest_station, dlat, dlng = fwd[0], fwd[1], fwd[2]
                duration, dist_m, path = self._metro_ride_duration(station_node.name,
                                                                   dest_station, line)
                depart = board_after  # metro has no schedule -> estimated timing
                arrive = depart + duration
                fare = metro_fare(dist_m / 1000.0,
                                  "purple" if "Purple" in line else "green").amount or 0.0
                total = fare * max(1, group_size)
                geo = self._metro_polyline(path)
                out.append({
                    "optionId": f"s{seg_num}_metro_{self._slug(dest_station)}",
                    "destinationStop": {"name": dest_station, "lat": dlat, "lng": dlng},
                    "mode": "metro", "routeNumber": "Purple" if "Purple" in line else "Green",
                    "fromStop": station_node.name,
                    "distanceKm": round(dist_m / 1000.0, 2),
                    "durationMin": duration,
                    "departureTime": _fmt(depart),
                    "arrivalTime": _fmt(arrive),
                    "arrivalMin": arrive,
                    "fare": round(fare, 2), "perPersonFare": round(fare, 2),
                    "geometry": geo, "geometrySource": "metro_line",
                    "status": "estimated",
                    "isTopRecommended": False,
                    "connectedFrom": connected_from,
                    "transitOptionsFromThisStop": 0,
                    "probeNext": [],
                    "exceedsBudget": total > budget and fare > 0,
                })
        return out

    # ------------------------------------------------------- route geometry
    def _bus_geometry(self, route_id, from_stop, to_stop) -> tuple[list, str]:
        seg = self.gtfs.get_stop_to_stop_segment(route_id, from_stop, to_stop)
        if seg:
            return seg, "gtfs_shape"
        coords = self.gtfs.data["stops_by_name"]
        a = coords.get(self.gtfs.resolve_stop_name(from_stop) or from_stop)
        b = coords.get(self.gtfs.resolve_stop_name(to_stop) or to_stop)
        if a and b:
            return [(a[0], a[1]), (b[0], b[1])], "interpolated"
        return [], "interpolated"

    def _metro_polyline(self, path: list[str]) -> list:
        geo = []
        for key in path:
            n = self.graph.node(key)
            if n:
                geo.append((n.lat, n.lng))
        return geo or []

    # ----------------------------------------------------- route line helpers
    def _route_forward_stops(self, route, from_stop, dest_lat, dest_lng):
        """[(stop_name, lat, lng), ...] after `from_stop` on `route` toward dest.

        Uses the GTFS shape stop sequence so the direction is real, not guessed.
        The chosen direction is the one whose first stop is closer to dest.
        """
        stops = self.gtfs.data["stops_by_name"]
        for shape_id in self.gtfs.data["route_shapes"].get(route, ()):
            seq = self.gtfs.shape_stop_sequence(shape_id)
            names = [n for _p, n in seq]
            if from_stop not in names:
                continue
            idx = names.index(from_stop)
            fwd = names[idx + 1:]
            bwd = names[:idx][::-1]

            def first_closer(lst):
                for n in lst:
                    c = stops.get(n)
                    if c:
                        return n, c
                return None

            f_c = first_closer(fwd)
            b_c = first_closer(bwd)
            df = _hav(dest_lat, dest_lng, f_c[1][0], f_c[1][1]) if f_c else 1e9
            db = _hav(dest_lat, dest_lng, b_c[1][0], b_c[1][1]) if b_c else 1e9
            chosen = fwd if df <= db else bwd
            out = []
            for n in chosen:
                c = stops.get(n)
                if not c:
                    continue
                out.append((n, c[0], c[1]))
            return out
        return []

    def _route_ride_duration(self, from_stop, to_stop, route) -> tuple[int, float]:
        """Estimate ride time/dist via the graph's bus edges along the route."""
        total_t, total_d = 0.0, 0.0
        cur = from_stop
        path = [from_stop]
        stops = self.gtfs.data["stops_by_name"]
        # walk the route shape between the two stops
        for shape_id in self.gtfs.data["route_shapes"].get(route, ()):
            seq = self.gtfs.shape_stop_sequence(shape_id)
            names = [n for _p, n in seq]
            if from_stop in names and to_stop in names:
                i, j = names.index(from_stop), names.index(to_stop)
                step = 1 if i < j else -1
                path = names[i:j + step:step]
                break
        for a, b in zip(path, path[1:]):
            ka, kb = f"bus:{a}", f"bus:{b}"
            edge = self._find_bus_edge(ka, kb, route)
            if edge:
                total_t += edge["time_min"]
                total_d += edge["dist_m"]
            else:
                ca = stops.get(a) or (0, 0)
                cb = stops.get(b) or (0, 0)
                d = _hav(ca[0], ca[1], cb[0], cb[1]) * 1.15
                total_d += d
                total_t += d / (BUS_SPEED_KMH * 1000) * 60
        return max(1, int(round(total_t))), total_d

    def _find_bus_edge(self, ka: str, kb: str, route: str) -> dict | None:
        for nb, etype, edata in self.graph.neighbors(ka):
            if nb == kb and etype == "bus" and route in edata.get("routes", ()):
                return edata
        return None

    def _metro_forward_stations(self, station_node, line, dest_lat, dest_lng):
        """[(station_name, lat, lng), ...] after this station on the same line."""
        out = []
        # walk the metro adjacency along the same line
        seen = {station_node.name}
        frontier = [station_node.name]
        while frontier and len(out) < 16:
            nxt = []
            for name in frontier:
                for nb, etype, edata in self.graph.neighbors(f"metro:{name}"):
                    if etype != "metro" or edata.get("line") != line:
                        continue
                    n2 = nb.removeprefix("metro:")
                    if n2 in seen:
                        continue
                    seen.add(n2)
                    node = self.graph.node(nb)
                    if node:
                        out.append((n2, node.lat, node.lng))
                    nxt.append(n2)
            frontier = nxt
        # keep stations that move toward dest (forward progress)
        kept = []
        for name, lat, lng in out:
            if self._forward_progress(station_node.lat, station_node.lng,
                                      dest_lat, dest_lng, lat, lng,
                                      tol=FORWARD_TOLERANCE_METRO_M):
                kept.append((name, lat, lng))
        return kept

    def _metro_ride_duration(self, from_station, to_station, line) -> tuple[int, float, list[str]]:
        from .fare_engine import metro_fare

        path = self._metro_path(from_station, to_station, line)
        total_t, total_d = 0.0, 0.0
        for a, b in zip(path, path[1:]):
            for nb, etype, edata in self.graph.neighbors(a):
                if nb == b and etype == "metro" and edata.get("line") == line:
                    total_t += edata["time_min"]
                    total_d += edata["dist_m"]
                    break
        return max(1, int(round(total_t))), total_d, path

    def _metro_path(self, from_station, to_station, line) -> list[str]:
        path = [f"metro:{from_station}"]
        cur = f"metro:{from_station}"
        seen = {cur}
        for _ in range(70):
            if cur == f"metro:{to_station}":
                break
            for nb, etype, edata in self.graph.neighbors(cur):
                if etype == "metro" and edata.get("line") == line and nb not in seen:
                    seen.add(nb)
                    path.append(nb)
                    cur = nb
                    break
            else:
                break
        return path

    # ------------------------------------------------------------- helpers
    def _forward_progress(self, from_lat, from_lng, dest_lat, dest_lng, to_lat, to_lng,
                          tol: float | None = None) -> bool:
        tol = FORWARD_TOLERANCE_M if tol is None else tol
        return _hav(to_lat, to_lng, dest_lat, dest_lng) < _hav(from_lat, from_lng, dest_lat, dest_lng) + tol

    def _fill_transit_count(self, opt: dict, after_min: int) -> None:
        """Count real onward routes at the option's arrival stop."""
        try:
            name = opt["destinationStop"]["name"]
            after = _fmt(after_min)
            routes = self.gtfs.get_routes_at_stop(name, after)
            opt["transitOptionsFromThisStop"] = len(routes)
        except Exception:
            opt["transitOptionsFromThisStop"] = 0

    def _mark_top_recommended(self, options: list[dict], now_min: int, walk_cands) -> None:
        if not options:
            return
        # rule: if a walk <= 1.5km exists, walk is primary (short hop, no cab/bike)
        if walk_cands and walk_cands[0]["dist_m"] <= WALK_PRIMARY_M:
            walk_opt = next((o for o in options
                             if o["mode"] == "walk" and o["destinationStop"]["name"] == walk_cands[0]["name"]), None)
            if walk_opt:
                walk_opt["isTopRecommended"] = True
                return
        # heuristic: fewest transfers + lowest fare + shortest walk + earliest arrival
        def score(o):
            walk_km = o["distanceKm"] if o["mode"] == "walk" else 0.0
            return (o.get("fare") or 0) * 2 + walk_km * 12 + (o.get("arrivalMin") or now_min)
        best = min(options, key=score)
        best["isTopRecommended"] = True

    def _probes_for_segment(self, seg: dict, destination: dict, group_size, budget) -> list[dict]:
        """Top suggestions for the level after this segment (isProbe: true)."""
        probes: list[dict] = []
        seen: set[tuple] = set()
        for opt in seg["options"]:
            if len(probes) >= MAX_PROBES:
                break
            if opt["mode"] not in ("bus", "metro"):
                continue
            stop = opt["destinationStop"]
            now = opt.get("arrivalMin") or 0
            p = self._probe_from_stop(stop, destination, int(now + BUFFER_MIN), group_size, budget)
            if p:
                key = (p["mode"], p.get("routeNumber"), p["destinationStop"]["name"])
                if key not in seen:
                    seen.add(key)
                    probes.append(p)
        return probes

    def _build_probes(self, source, destination, seg2, now_min, group_size, budget) -> list[dict]:
        return self._probes_for_segment(seg2, destination, group_size, budget)

    def _probe_from_stop(self, stop, destination, after_min, group_size, budget) -> dict | None:
        """A single cheapest/earliest onward transit suggestion from a stop."""
        from .fare_engine import bmtc_fare, metro_fare

        if stop.get("kind") == "metro" or self.graph.node(f"metro:{stop['name']}") is not None:
            node = self.graph.node(f"metro:{stop['name']}")
            if node is None:
                return None
            line = node.line or "Purple Line"
            for fwd in self._metro_forward_stations(node, line,
                                                    destination["lat"], destination["lng"]):
                dur, dist, _path = self._metro_ride_duration(node.name, fwd[0], line)
                fare = metro_fare(dist / 1000.0, "purple" if "Purple" in line else "green").amount
                return {"destinationStop": {"name": fwd[0], "lat": fwd[1], "lng": fwd[2]},
                        "mode": "metro",
                        "routeNumber": "Purple" if "Purple" in line else "Green",
                        "departureTime": _fmt(after_min),
                        "arrivalTime": _fmt(after_min + dur),
                        "fare": round(fare, 2), "perPersonFare": round(fare, 2),
                        "isProbe": True}
            return None
        # bus stop: earliest real departure with a forward stop
        resolved = self.gtfs.resolve_stop_name(stop["name"])
        if not resolved:
            return None
        node = self.graph.node(f"bus:{resolved}")
        if node is None:
            return None
        deps = self.gtfs.earliest_departures(node.name, _fmt(after_min),
                                             max_n=6, window_min=DEP_WINDOW_MIN)
        for d in deps:
            fwd = self._route_forward_stops(d.route_number, node.name,
                                            destination["lat"], destination["lng"])
            if not fwd:
                continue
            f0 = fwd[0]
            if not self._forward_progress(node.lat, node.lng, destination["lat"],
                                          destination["lng"], f0[1], f0[2]):
                continue
            dur, dist = self._route_ride_duration(node.name, f0[0], d.route_number)
            fare = bmtc_fare("nonac", dist / 1000.0).amount
            return {"destinationStop": {"name": f0[0], "lat": f0[1], "lng": f0[2]},
                    "mode": "bus", "routeNumber": d.route_number,
                    "departureTime": _fmt(d.departure_minutes),
                    "arrivalTime": _fmt(d.departure_minutes + dur),
                    "fare": round(fare, 2), "perPersonFare": round(fare, 2),
                    "isProbe": True}
        return None

    # ------------------------------------------------------------ warnings
    def _warnings(self, now_min: int, options: list[dict]) -> list[str]:
        warnings: list[str] = []
        hour = (now_min // 60) % 24
        if hour >= 22 or hour < 6:
            warnings.append("Bus service limited after 22:00 - consider cab/auto")
        not_running = any(o.get("status") == "not_running" for o in options)
        if not_running:
            warnings.append("Some stops have no more scheduled buses today - service marked not_running")
        return warnings

    # ------------------------------------------------------ stop resolution
    def _resolve_stop(self, name: str) -> dict | None:
        """Locate a stop/station by name -> {name, lat, lng}."""
        if not name:
            return None
        resolved = self.gtfs.resolve_stop_name(name)
        if resolved:
            c = self.gtfs.data["stops_by_name"].get(resolved)
            if c:
                return {"name": resolved, "lat": c[0], "lng": c[1], "kind": "bus"}
        for m in self.db.all_metro_stations():
            if m.name.lower() == name.lower():
                return {"name": m.name, "lat": m.lat, "lng": m.lng, "kind": "metro"}
        for r in self.db.all_rail_stations():
            if r.name.lower() == name.lower():
                return {"name": r.name, "lat": r.lat, "lng": r.lng, "kind": "rail"}
        return None

    @staticmethod
    def _parse_hhmm(value) -> int | None:
        if not value:
            return None
        s = str(value)
        if ":" in s:
            h, m = s.split(":", 1)
            try:
                return int(h) * 60 + int(m.split()[0])
            except ValueError:
                return None
        return None

    @staticmethod
    def _slug(name: str) -> str:
        keep = "".join(ch.lower() for ch in str(name) if ch.isalnum() or ch in " -_")
        return keep.replace(" ", "_")[:48] or "stop"

    @staticmethod
    def _timeline_item(leg: dict) -> dict:
        return {
            "optionId": leg.get("optionId"),
            "mode": leg.get("mode"),
            "routeNumber": leg.get("routeNumber"),
            "destinationStop": leg.get("destinationStop"),
            "arrivalTime": leg.get("arrivalTime"),
            "fare": leg.get("fare"),
            "perPersonFare": leg.get("perPersonFare"),
        }
