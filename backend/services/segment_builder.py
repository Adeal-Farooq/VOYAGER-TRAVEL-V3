"""Segment builder extracted from transit_service.py. Handles multi-hop transit routing."""

import logging
import time
from backend.core.database import db
from backend.services.transit_config import (
    _ensure_gtfs, _RIDE_TYPES, _calc_ride_fare, _ride_fare_range,
    _get_train_options, _safe, _current_hour, _is_metro_operating,
    _haversine_dist, _MAJOR_HUBS, _route_goes_toward_dest,
    _gtfs_buses_at_stop, _has_gtfs_route, clean_route_short_name,
)
logger = logging.getLogger(__name__)


class TripSegmentBuilder:
    def __init__(self, haversine_fn, interpolate_path_fn, path_service=None,
                 get_bus_route_nums_fn=None, astar_graph_fn=None):
        self._haversine = haversine_fn
        self._interpolate = interpolate_path_fn
        self._path_service = path_service
        self._get_bus_route_nums_fn = get_bus_route_nums_fn
        self._astar_graph_fn = astar_graph_fn
        self._gtfs_route_cache = {}
        self._shape_cache = {}
        self._stops_toward_cache = {}
        self._shape_between_cache = {}
        self._segments_cache = {}  # key -> (timestamp, result)

    def _find_route_dest_toward(self, rn, from_stop_name, dest_lat, dest_lng):
        """Find the furthest stop on route rn (after from_stop) that is closest to destination."""
        gtfs = _ensure_gtfs()
        from_s_coords = None
        for s in db.bus_stops.values():
            if s.get("name","").lower().strip() == from_stop_name.lower().strip():
                from_s_coords = (s["lat"], s["lng"])
                break
        if not from_s_coords:
            return None, None, 0
        # Returns stops AFTER from_stop along the route shape (ordered by shape sequence)
        route_stops = gtfs.find_stops_on_route_toward_dest(rn, from_s_coords[0], from_s_coords[1], dest_lat, dest_lng, max_stops=50)
        if not route_stops:
            return None, None, 0
        from_dist = _haversine_dist(from_s_coords[0], from_s_coords[1], dest_lat, dest_lng)
        best_stop = None
        best_dist = from_dist
        for st in route_stops:
            sn_lower = st.get("stop_name","").lower().strip()
            sl = from_stop_name.lower().strip()
            if sn_lower == sl or sl in sn_lower:
                continue
            d = _haversine_dist(st["lat"], st["lng"], dest_lat, dest_lng)
            if d < best_dist:
                best_dist = d
                best_stop = st
        if best_stop and best_dist < from_dist:
            return best_stop["stop_name"], (best_stop["lat"], best_stop["lng"]), best_dist
        last = route_stops[-1]
        return last["stop_name"], (last["lat"], last["lng"]), _haversine_dist(last["lat"], last["lng"], dest_lat, dest_lng)

    def _astar_route_paths(self, from_lat, from_lng, dest_lat, dest_lng, group_size, budget):
        """Get A* enriched multi-hop routes and convert to route_path format."""
        if not self._astar_graph_fn:
            return []
        try:
            routes = self._astar_graph_fn(from_lat, from_lng, dest_lat, dest_lng, group_size)
        except Exception as e:
            logger.warning(f"A* route paths failed: {e}")
            return []
        result = []
        for r in routes:
            legs_clean = []
            valid = True
            for leg in r.get("legs", []):
                mode = leg.get("mode", "walk")
                if mode == "walk":
                    dur = round(leg.get("distance_km", 0) * 12)
                    fare = 0
                elif mode == "bus_ordinary":
                    dur = round(leg.get("distance_km", 0) * 3)
                    fare = max(6, round(db.get_bmtc_ordinary_fare(leg.get("distance_km", 0)) or 6)) * group_size
                elif mode == "metro":
                    dur = round(leg.get("distance_km", 0) * 2)
                    fare = round(db.get_metro_fare(leg.get("distance_km", 0)) or 15) * group_size
                else:
                    dur = round(leg.get("distance_km", 0) * 4)
                    fare = 0
                if budget and fare > budget:
                    valid = False
                    break
                legs_clean.append({
                    "from": leg.get("from", ""),
                    "to": leg.get("to", ""),
                    "mode": mode,
                    "route_number": leg.get("route_number", ""),
                    "distance_km": round(leg.get("distance_km", 0), 2),
                    "duration_minutes": round(dur),
                    "fare": round(fare),
                    "per_person": round(fare / max(group_size, 1)),
                    "departure_times": leg.get("departure_times", []),
                    "shape_path": leg.get("shape_path"),
                })
            if not valid or not legs_clean:
                continue
            total_fare = sum(l["fare"] for l in legs_clean)
            total_dur = sum(l["duration_minutes"] for l in legs_clean)
            total_dist = sum(l["distance_km"] for l in legs_clean)
            result.append({
                "legs": legs_clean,
                "total_fare": total_fare,
                "total_duration_minutes": total_dur,
                "total_distance_km": round(total_dist, 1),
                "total_walking_km": round(sum(l["distance_km"] for l in legs_clean if l["mode"] == "walk"), 1),
                "transfers": len([l for l in legs_clean if l["mode"] not in ("walk",)]) - 1,
            })
        result.sort(key=lambda r: (r["total_fare"], r["total_duration_minutes"]))
        return result[:4]

    def _is_outside_bengaluru(self, lat: float, lng: float, threshold_km: float = 35.0) -> bool:
        center = (12.9716, 77.5946)
        dist = self._haversine(center[0], center[1], lat, lng)
        return dist > threshold_km

    def _find_farthest_bus_stop_toward_dest(self, from_lat: float, from_lng: float,
                                              dest_lat: float, dest_lng: float) -> dict | None:
        stops = list(db.bus_stops.values())
        if not stops:
            return None
        dest_dist = {}
        for s in stops:
            d = self._haversine(s["lat"], s["lng"], dest_lat, dest_lng)
            dest_dist[s["stop_id"]] = d
        sorted_stops = sorted(stops, key=lambda s: dest_dist.get(s["stop_id"], 999))
        top3 = sorted_stops[:3]
        farthest_from_center = None
        max_center_dist = 0
        center = (12.9716, 77.5946)
        for s in top3:
            cd = self._haversine(center[0], center[1], s["lat"], s["lng"])
            if cd > max_center_dist:
                max_center_dist = cd
                farthest_from_center = s
        return farthest_from_center

    def get_segment_step_options(self, from_lat: float, from_lng: float, from_name: str,
                                  dest_lat: float, dest_lng: float, dest_name: str,
                                  group_size: int = 1, budget: float = None) -> dict:
        """Return all possible next steps from a location toward destination."""
        from_dist = _safe(self._haversine(from_lat, from_lng, dest_lat, dest_lng))

        # --- Direct to destination (walk + rides) ---
        direct_options = []
        # Walk: show for distances up to 5km
        if 0 < from_dist <= 5:
            direct_options.append({
                "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                "from": from_name, "to": dest_name,
                "distance_km": round(_safe(from_dist), 2),
                "duration_minutes": round(from_dist * 12),
                "fare": 0, "per_person": 0,
                "from_lat": from_lat, "from_lng": from_lng,
                "to_lat": dest_lat, "to_lng": dest_lng,
                "path": self._interpolate(from_lat, from_lng, dest_lat, dest_lng, 6),
            })

        # Smart distance filtering for rides:
        # - < 1km: only walk (no rides needed)
        # - 1-2km: bike and walk only
        # - > 2km: all ride options
        ride_types = _RIDE_TYPES
        if from_dist >= 1.0:
            for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                if group_size > capacity:
                    continue
                # For 1-2km distance, only show bike
                if 1.0 <= from_dist < 2.0 and mode not in ("bike",):
                    continue
                total = _calc_ride_fare(from_dist, base_fare, per_km_rate, free_km)
                pp = round(total / group_size)
                if budget and total > budget:
                    continue
                direct_options.append({
                    "mode": mode, "label": label, "icon": icon,
                    "from": from_name, "to": dest_name,
                    "distance_km": round(_safe(from_dist), 2),
                    "duration_minutes": round(from_dist * time_per_km),
                    "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": capacity,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "path": self._interpolate(from_lat, from_lng, dest_lat, dest_lng, 6),
                })

        # --- Via transit stops ---
        via_stops = []
        nearby_bus = db.find_nearby_bus_stops(from_lat, from_lng, 2.0) or []
        nearby_metro = db.find_nearby_metro_stations(from_lat, from_lng, 3.0) or []

        # Out-of-Bengaluru: BMTC max + cab combo (as a via segment, not direct)
        if self._is_outside_bengaluru(dest_lat, dest_lng) and nearby_bus:
            farthest_stop = self._find_farthest_bus_stop_toward_dest(from_lat, from_lng, dest_lat, dest_lng)
            if farthest_stop:
                bus_to_stop = _safe(self._haversine(from_lat, from_lng, farthest_stop["lat"], farthest_stop["lng"]))
                stop_to_dest = _safe(self._haversine(farthest_stop["lat"], farthest_stop["lng"], dest_lat, dest_lng))
                bus_fare = round(db.get_bmtc_ordinary_fare(bus_to_stop) or 6) * group_size
                cab_fare_pp = round(25 + stop_to_dest * 14)
                cab_total = cab_fare_pp * group_size
                total_fare = bus_fare + cab_total
                # Try to find common routes from any nearby bus stop to the farthest stop
                common_routes = []
                for bs in nearby_bus[:5]:
                    cr = self._get_bus_route_nums_fn(bs, farthest_stop)
                    if cr:
                        common_routes = cr
                        break
                if not common_routes:
                    common_routes = farthest_stop.get("routes", [])[:3]
                via_stops.append({
                    "stop": {"name": farthest_stop["name"], "lat": _safe(farthest_stop.get("lat")), "lng": _safe(farthest_stop.get("lng")), "type": "bus"},
                    "reach_options": [{
                        "mode": "bus_ordinary", "label": f"Bus to {farthest_stop['name']} [{', '.join(common_routes[:3])}]", "icon": "\U0001f68c",
                        "from": from_name, "to": farthest_stop["name"],
                        "distance_km": round(bus_to_stop, 2),
                        "duration_minutes": round(bus_to_stop * 4),
                        "fare": bus_fare, "per_person": round(bus_fare / group_size),
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(farthest_stop.get("lat")), "to_lng": _safe(farthest_stop.get("lng")),
                        "route_numbers": common_routes[:3],
                    }],
                    "from_stop_options": [{
                        "mode": "cab", "label": "Uber Go / Ola Mini", "icon": "\U0001f695",
                        "from": farthest_stop["name"], "to": dest_name,
                        "distance_km": round(stop_to_dest, 2),
                        "duration_minutes": round(stop_to_dest * 3),
                        "fare": cab_total, "per_person": cab_fare_pp,
                        "from_lat": _safe(farthest_stop.get("lat")), "from_lng": _safe(farthest_stop.get("lng")),
                        "to_lat": dest_lat, "to_lng": dest_lng,
                        "arrives_at_stop": False,
                    }]
                })

        dest_nearby_bus = db.find_nearby_bus_stops(dest_lat, dest_lng, 1.0) or []
        dest_nearby_metro = db.find_nearby_metro_stations(dest_lat, dest_lng, 3.0) or []
        stop_to_dest_cutoff = max(2.0, self._haversine(from_lat, from_lng, dest_lat, dest_lng) * 0.8)

        for stop in nearby_bus[:5]:
            stop_name = stop.get("name", "Bus Stop")
            dist = _safe(self._haversine(from_lat, from_lng, stop["lat"], stop["lng"]))
            stop_to_dest_dist = _safe(self._haversine(stop["lat"], stop["lng"], dest_lat, dest_lng))
            # Check if GTFS has data for this stop
            has_gtfs = _has_gtfs_route(stop_name)
            # Get all bus routes at this stop from GTFS
            all_routes = _gtfs_buses_at_stop(stop_name) if has_gtfs else []
            # Skip if no GTFS data and too far to walk AND no cabs would help
            if dist > 2 and not all_routes and stop_to_dest_dist > 10:
                continue
            # Only show if there's some transport connection possible
            if not all_routes and dist > 3:
                continue
            stop_entry = {
                "stop": {"name": stop_name, "lat": _safe(stop.get("lat")), "lng": _safe(stop.get("lng")), "type": "bus"},
                "reach_options": [],
                "from_stop_options": [],
            }
            # Walk to stop (only if within walkable distance)
            if dist <= 2:
                stop_entry["reach_options"].append({
                    "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                    "from": from_name, "to": stop_name,
                    "distance_km": round(dist, 2),
                    "duration_minutes": round(dist * 12),
                    "fare": 0, "per_person": 0,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": _safe(stop.get("lat")), "to_lng": _safe(stop.get("lng")),
                })
            # Ride to stop (only if walk is too far)
            if dist >= 1.0:
                for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                    if group_size > capacity:
                        continue
                    # For 1-2km, only bike makes sense
                    if 1.0 <= dist < 2.0 and mode not in ("bike",):
                        continue
                    total = _calc_ride_fare(dist, base_fare, per_km_rate, free_km)
                    pp = round(total / group_size)
                    if budget and total > budget:
                        continue
                    stop_entry["reach_options"].append({
                        "mode": mode, "label": label, "icon": icon,
                        "from": from_name, "to": stop_name,
                        "distance_km": round(dist, 2),
                        "duration_minutes": round(dist * time_per_km),
                        "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": capacity,
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(stop.get("lat")), "to_lng": _safe(stop.get("lng")),
                    })
            # From this stop: show all available bus routes with timings (individual route cards)
            if all_routes:
                for route_info in all_routes[:10]:
                    rn = route_info["route_number"]
                    next_deps = route_info["next_departures"]
                    route_dest_name, route_dest_coords, route_to_dest = self._find_route_dest_toward(rn, stop_name, dest_lat, dest_lng)
                    if route_dest_coords:
                        transit_dist = _safe(self._haversine(stop["lat"], stop["lng"], route_dest_coords[0], route_dest_coords[1]))
                    else:
                        transit_dist = stop_to_dest_dist * 0.6
                    # Skip if route doesn't progress toward destination
                    if route_to_dest >= stop_to_dest_dist * 0.95 and stop_to_dest_dist > 2:
                        continue
                    bus_fare_pp = max(6, round(db.get_bmtc_ordinary_fare(transit_dist) or 6))
                    total_fare = bus_fare_pp * group_size
                    if budget and total_fare > budget:
                        continue
                    bus_times_list = [{"departure_time": t, "route": rn} for t in next_deps]
                    to_label = route_dest_name or f"{rn} towards destination"
                    stop_entry["from_stop_options"].append({
                        "mode": "bus_ordinary", "label": f"Bus {rn}", "icon": "\U0001f68c",
                        "route_number": rn,
                        "from": stop_name, "to": to_label,
                        "distance_km": round(_safe(transit_dist), 2),
                            "duration_minutes": round(transit_dist * 3),
                        "fare": total_fare, "per_person": bus_fare_pp,
                        "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                        "to_lat": _safe(route_dest_coords[0] if route_dest_coords else stop.get("lat")),
                        "to_lng": _safe(route_dest_coords[1] if route_dest_coords else stop.get("lng")),
                        "arrives_at_stop": True,
                        "bus_times": bus_times_list[:5],
                    })
                    # AC Vajra variant
                    ac_fare_pp = max(10, round(db.get_bmtc_ac_fare(transit_dist) or 10))
                    ac_total = ac_fare_pp * group_size
                    if not budget or ac_total <= budget:
                        stop_entry["from_stop_options"].append({
                            "mode": "bus_ac_vajra", "label": f"Bus {rn} AC", "icon": "\U0001f68c",
                            "route_number": rn,
                            "from": stop_name, "to": to_label,
                            "distance_km": round(_safe(transit_dist), 2),
                            "duration_minutes": round(transit_dist * 2.5),
                            "fare": ac_total, "per_person": ac_fare_pp,
                            "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                            "to_lat": _safe(route_dest_coords[0] if route_dest_coords else stop.get("lat")),
                            "to_lng": _safe(route_dest_coords[1] if route_dest_coords else stop.get("lng")),
                            "arrives_at_stop": True,
                            "bus_times": bus_times_list[:5],
                        })
            # From this stop: metro rides (only if realistic — within 5km of a metro station)
            for dm in dest_nearby_metro[:2]:
                transit_dist = _safe(self._haversine(stop["lat"], stop["lng"], dm["lat"], dm["lng"]))
                if transit_dist < 1.0 or transit_dist > 5.0:
                    continue
                # Verify the bus stop is also closer to destination via this metro
                dm_to_dest = _safe(self._haversine(dm["lat"], dm["lng"], dest_lat, dest_lng))
                if dm_to_dest >= stop_to_dest_dist * 0.95:
                    continue
                metro_fare_pp = round(db.get_metro_fare(transit_dist) or 15)
                total_fare = metro_fare_pp * group_size
                if budget and total_fare > budget:
                    continue
                stop_entry["from_stop_options"].append({
                    "mode": "metro", "label": f"Metro to {dm['name']}", "icon": "\U0001f687",
                    "from": stop_name, "to": dm.get("name", "Metro Station"),
                    "distance_km": round(_safe(transit_dist), 2),
                    "duration_minutes": max(1, round(transit_dist / 35 * 60)),
                    "fare": total_fare, "per_person": metro_fare_pp,
                    "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                    "to_lat": _safe(dm.get("lat")), "to_lng": _safe(dm.get("lng")),
                    "arrives_at_stop": True,
                })
            # From this stop: direct rides to destination
            if stop_to_dest_dist <= 2:
                stop_entry["from_stop_options"].append({
                    "mode": "walk", "label": "Walk to Destination", "icon": "\U0001f6b6",
                    "from": stop_name, "to": dest_name,
                    "distance_km": round(_safe(stop_to_dest_dist), 2),
                    "duration_minutes": round(stop_to_dest_dist * 12),
                    "fare": 0, "per_person": 0,
                    "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                })
            if stop_to_dest_dist >= 1.0:
                for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                    if group_size > capacity:
                        continue
                    total = _calc_ride_fare(stop_to_dest_dist, base_fare, per_km_rate, free_km)
                    pp = round(total / group_size)
                    if budget and total > budget:
                        continue
                    stop_entry["from_stop_options"].append({
                        "mode": mode, "label": label + " to Destination", "icon": icon,
                        "from": stop_name, "to": dest_name,
                        "distance_km": round(_safe(stop_to_dest_dist), 2),
                        "duration_minutes": round(stop_to_dest_dist * time_per_km),
                        "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp,
                        "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                        "to_lat": dest_lat, "to_lng": dest_lng,
                        "arrives_at_stop": False,
                    })
            via_stops.append(stop_entry)

        for station in nearby_metro[:3]:
            station_name = station.get("name", "Metro Station")
            dist = _safe(self._haversine(from_lat, from_lng, station["lat"], station["lng"]))
            dest_metro = db.find_nearby_metro_stations(dest_lat, dest_lng, 3.0) or []
            # Skip if no dest metro nearby and no other meaningful connection
            if not dest_metro and dist > 2 and self._is_outside_bengaluru(dest_lat, dest_lng):
                continue
            stop_entry = {
                "stop": {"name": station_name, "lat": _safe(station.get("lat")), "lng": _safe(station.get("lng")), "type": "metro"},
                "reach_options": [],
                "from_stop_options": [],
            }
            if dist <= 2:
                stop_entry["reach_options"].append({
                    "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                    "from": from_name, "to": station_name,
                    "distance_km": round(dist, 2),
                    "duration_minutes": round(dist * 12),
                    "fare": 0, "per_person": 0,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": _safe(station.get("lat")), "to_lng": _safe(station.get("lng")),
                })
            if dist >= 0.5:
                for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                    if group_size > capacity: continue
                    total = _calc_ride_fare(dist, base_fare, per_km_rate, free_km)
                    pp = round(total / group_size)
                    if budget and total > budget: continue
                    stop_entry["reach_options"].append({
                        "mode": mode, "label": label, "icon": icon,
                        "from": from_name, "to": station_name,
                        "distance_km": round(dist, 2),
                        "duration_minutes": round(dist * time_per_km),
                        "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": capacity,
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(station.get("lat")), "to_lng": _safe(station.get("lng")),
                    })
            # Metro to dest metro station
            for dm in dest_metro[:2]:
                transit_dist = _safe(self._haversine(station["lat"], station["lng"], dm["lat"], dm["lng"]))
                if transit_dist < 0.5: continue
                metro_fare_pp = round(db.get_metro_fare(transit_dist) or 15)
                total_fare = metro_fare_pp * group_size
                if budget and total_fare > budget: continue
                stop_entry["from_stop_options"].append({
                    "mode": "metro", "label": f"Metro to {dm['name']}", "icon": "\U0001f687",
                    "from": station_name, "to": dm.get("name", "Metro Station"),
                    "distance_km": round(_safe(transit_dist), 2),
                    "duration_minutes": max(1, round(transit_dist / 35 * 60)),
                    "fare": total_fare, "per_person": metro_fare_pp,
                    "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                    "to_lat": _safe(dm.get("lat")), "to_lng": _safe(dm.get("lng")),
                    "arrives_at_stop": True,
                })
            # Bus from metro station — individual route cards using GTFS
            station_to_dest_dist = _safe(self._haversine(station["lat"], station["lng"], dest_lat, dest_lng))
            metro_has_gtfs = _has_gtfs_route(station_name)
            metro_all_routes = _gtfs_buses_at_stop(station_name) if metro_has_gtfs else []
            if metro_all_routes:
                for route_info in metro_all_routes[:6]:
                    rn = route_info["route_number"]
                    next_deps = route_info["next_departures"]
                    route_dest_name, route_dest_coords, route_to_dest = self._find_route_dest_toward(rn, station_name, dest_lat, dest_lng)
                    if route_dest_coords:
                        transit_dist = _safe(self._haversine(station["lat"], station["lng"], route_dest_coords[0], route_dest_coords[1]))
                    else:
                        transit_dist = station_to_dest_dist * 0.6
                    if route_to_dest >= station_to_dest_dist * 0.95 and station_to_dest_dist > 2:
                        continue
                    bus_fare_pp = max(6, round(db.get_bmtc_ordinary_fare(transit_dist) or 6))
                    total_fare = bus_fare_pp * group_size
                    if budget and total_fare > budget: continue
                    bus_times_list = [{"departure_time": t, "route": rn} for t in next_deps]
                    to_label = route_dest_name or f"{rn} towards destination"
                    stop_entry["from_stop_options"].append({
                        "mode": "bus_ordinary", "label": f"Bus {rn}", "icon": "\U0001f68c",
                        "route_number": rn,
                        "from": station_name, "to": to_label,
                        "distance_km": round(_safe(transit_dist), 2),
                        "duration_minutes": round(transit_dist * 3),
                        "fare": total_fare, "per_person": bus_fare_pp,
                        "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                        "to_lat": _safe(route_dest_coords[0] if route_dest_coords else station.get("lat")),
                        "to_lng": _safe(route_dest_coords[1] if route_dest_coords else station.get("lng")),
                        "arrives_at_stop": True,
                        "bus_times": bus_times_list[:5],
                    })
                    ac_fare_pp = max(10, round(db.get_bmtc_ac_fare(transit_dist) or 10))
                    ac_total = ac_fare_pp * group_size
                    if not budget or ac_total <= budget:
                        stop_entry["from_stop_options"].append({
                            "mode": "bus_ac_vajra", "label": f"Bus {rn} AC", "icon": "\U0001f68c",
                            "route_number": rn,
                            "from": station_name, "to": to_label,
                            "distance_km": round(_safe(transit_dist), 2),
                            "duration_minutes": round(transit_dist * 2.5),
                            "fare": ac_total, "per_person": ac_fare_pp,
                            "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                            "to_lat": _safe(route_dest_coords[0] if route_dest_coords else station.get("lat")),
                            "to_lng": _safe(route_dest_coords[1] if route_dest_coords else station.get("lng")),
                            "arrives_at_stop": True,
                            "bus_times": bus_times_list[:5],
                        })
            # Direct rides from metro to destination
            if station_to_dest_dist <= 2:
                stop_entry["from_stop_options"].append({
                    "mode": "walk", "label": "Walk to Destination", "icon": "\U0001f6b6",
                    "from": station_name, "to": dest_name,
                    "distance_km": round(_safe(station_to_dest_dist), 2),
                    "duration_minutes": round(station_to_dest_dist * 12),
                    "fare": 0, "per_person": 0,
                    "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                })
            for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                if group_size > capacity:
                    continue
                total = _calc_ride_fare(station_to_dest_dist, base_fare, per_km_rate, free_km)
                pp = round(total / group_size)
                if budget and total > budget:
                    continue
                stop_entry["from_stop_options"].append({
                    "mode": mode, "label": label + " to Destination", "icon": icon,
                    "from": station_name, "to": dest_name,
                    "distance_km": round(_safe(station_to_dest_dist), 2),
                    "duration_minutes": round(station_to_dest_dist * time_per_km),
                    "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp,
                    "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                })
            via_stops.append(stop_entry)

        # Railway stations as via stops (for long-distance / out-of-Bengaluru)
        nearby_rail = db.find_nearby_railway_stations(from_lat, from_lng, 15.0) or []
        dest_rail = db.find_nearby_railway_stations(dest_lat, dest_lng, 30.0) or []
        if nearby_rail and (self._is_outside_bengaluru(dest_lat, dest_lng) or len(nearby_rail) > 0):
            for rail_stn in nearby_rail[:3]:
                rname = rail_stn.get("name", "Railway Station")
                rdist = _safe(self._haversine(from_lat, from_lng, rail_stn["lat"], rail_stn["lng"]))
                stop_entry = {
                    "stop": {"name": rname, "lat": _safe(rail_stn.get("lat")), "lng": _safe(rail_stn.get("lng")), "type": "railway"},
                    "reach_options": [],
                    "from_stop_options": [],
                }
                if rdist <= 2:
                    stop_entry["reach_options"].append({
                        "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                        "from": from_name, "to": rname,
                        "distance_km": round(rdist, 2), "duration_minutes": round(rdist * 12),
                        "fare": 0, "per_person": 0,
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(rail_stn.get("lat")), "to_lng": _safe(rail_stn.get("lng")),
                    })
                for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                    if group_size > capacity: continue
                    total = _calc_ride_fare(rdist, base_fare, per_km_rate, free_km)
                    pp = round(total / group_size)
                    if budget and total > budget: continue
                    stop_entry["reach_options"].append({
                        "mode": mode, "label": label, "icon": icon,
                        "from": from_name, "to": rname,
                        "distance_km": round(rdist, 2), "duration_minutes": round(rdist * time_per_km),
                        "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": capacity,
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(rail_stn.get("lat")), "to_lng": _safe(rail_stn.get("lng")),
                    })
                if dest_rail:
                    for dr in dest_rail[:2]:
                        train_dist = _safe(self._haversine(rail_stn["lat"], rail_stn["lng"], dr["lat"], dr["lng"]))
                        if train_dist < 10: continue
                        train_fare_pp = max(15, round(train_dist * 0.8))
                        total_fare = train_fare_pp * group_size
                        if budget and total_fare > budget: continue
                        train_options = _get_train_options(rname, dr["name"])
                        for tn, tname, dep_time, arr_time in train_options[:3]:
                            dur = int((int(arr_time[:2])*60+int(arr_time[3:5])) - (int(dep_time[:2])*60+int(dep_time[3:5])))
                            if dur <= 0:
                                dur = round(train_dist * 1.2)
                            stop_entry["from_stop_options"].append({
                                "mode": "train", "label": f"Train {tn} {tname}", "icon": "\U0001f686",
                                "from": rname, "to": dr["name"],
                                "distance_km": round(_safe(train_dist), 2),
                                "duration_minutes": dur,
                                "fare": total_fare, "per_person": train_fare_pp,
                                "from_lat": _safe(rail_stn.get("lat")), "from_lng": _safe(rail_stn.get("lng")),
                                "to_lat": _safe(dr.get("lat")), "to_lng": _safe(dr.get("lng")),
                                "arrives_at_stop": True,
                                "train_number": tn,
                                "departure_time": dep_time,
                                "arrival_time": arr_time,
                            })
                    # Last-mile cab from destination rail station to actual dest
                    for dr in dest_rail[:1]:
                        ddist = _safe(self._haversine(dr["lat"], dr["lng"], dest_lat, dest_lng))
                        if ddist <= 2:
                            stop_entry["from_stop_options"].append({
                                "mode": "walk", "label": "Walk to Destination", "icon": "\U0001f6b6",
                                "from": dr["name"], "to": dest_name,
                                "distance_km": round(ddist, 2),
                                "duration_minutes": round(ddist * 12),
                                "fare": 0, "per_person": 0,
                                "from_lat": _safe(dr.get("lat")), "from_lng": _safe(dr.get("lng")),
                                "to_lat": dest_lat, "to_lng": dest_lng,
                                "arrives_at_stop": False,
                            })
                        if ddist > 1:
                            for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types:
                                if group_size > capacity: continue
                                total = _calc_ride_fare(ddist, base_fare, per_km_rate, free_km)
                                pp = round(total / group_size)
                                if budget and total > budget: continue
                                stop_entry["from_stop_options"].append({
                                    "mode": mode, "label": label + " from " + dr["name"], "icon": icon,
                                    "from": dr["name"], "to": dest_name,
                                    "distance_km": round(ddist, 2),
                                    "duration_minutes": round(ddist * time_per_km),
                                    "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp,
                                    "from_lat": _safe(dr.get("lat")), "from_lng": _safe(dr.get("lng")),
                                    "to_lat": dest_lat, "to_lng": dest_lng,
                                    "arrives_at_stop": False,
                                })
                via_stops.append(stop_entry)

        # Add interpolated paths to all options for map display
        for opt in direct_options:
            if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                opt["path"] = self._interpolate(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)
        for vs in via_stops:
            for opt in vs.get("reach_options", []):
                if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                    opt["path"] = self._interpolate(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)
            for opt in vs.get("from_stop_options", []):
                if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                    opt["path"] = self._interpolate(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)

        # Filter via_stops: remove stops with no reach options AND no from_stop options
        via_stops = [vs for vs in via_stops
                     if (vs.get("reach_options") and len(vs["reach_options"]) > 0) or
                        (vs.get("from_stop_options") and len(vs["from_stop_options"]) > 0)]

        # A* enriched multi-hop routes (complete chains, not individual stops)
        route_paths = self._astar_route_paths(from_lat, from_lng, dest_lat, dest_lng, group_size, budget)

        return {
            "from": {"lat": from_lat, "lng": from_lng, "name": from_name},
            "dest": {"lat": dest_lat, "lng": dest_lng, "name": dest_name},
            "direct_options": direct_options,
            "via_stops": via_stops,
            "route_paths": route_paths,
        }

    def _add_direct_options(self, result: list, from_lat: float, from_lng: float, from_name: str,
                             dest_lat: float, dest_lng: float, dest_name: str,
                             group_size: int, budget: float):
        """Add direct options (walk/cab/auto/bike) from from to dest."""
        direct_dist = _safe(self._haversine(from_lat, from_lng, dest_lat, dest_lng))
        ride_types = _RIDE_TYPES
        if direct_dist <= 5:
            result.append({
                "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                "from": from_name, "to": dest_name,
                "distance_km": round(direct_dist, 2), "duration_minutes": round(direct_dist * 12),
                "fare": 0, "per_person": 0,
                "from_lat": from_lat, "from_lng": from_lng,
                "to_lat": dest_lat, "to_lng": dest_lng,
                "arrives_at_stop": False,
            })
        # Smart distance filtering: <1km walk only, 1-2km only bike + walk
        if direct_dist >= 1.0:
            for mode, label, per_km, tpk, base, icon, cap, free_km in ride_types:
                if group_size > cap: continue
                if 1.0 <= direct_dist < 2.0 and mode not in ("bike",):
                    continue
                total = _calc_ride_fare(direct_dist, base, per_km, free_km)
                pp = round(total / group_size)
                if budget and total > budget: continue
                result.append({
                    "mode": mode, "label": label, "icon": icon,
                    "from": from_name, "to": dest_name,
                    "distance_km": round(direct_dist, 2), "duration_minutes": round(direct_dist * tpk),
                    "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": cap,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                })

    def _add_reach_options(self, from_lat: float, from_lng: float, from_name: str,
                            stop_name: str, stop_lat: float, stop_lng: float, stop_type: str,
                            group_size: int, budget: float):
        """Build a single destination entry with reach options."""
        sdist = _safe(self._haversine(from_lat, from_lng, stop_lat, stop_lng))
        ride_types = _RIDE_TYPES
        entry = {
            "stop": {"name": stop_name, "lat": _safe(stop_lat), "lng": _safe(stop_lng), "type": stop_type},
            "distance_from_current": round(sdist, 3),
            "reach_options": [],
            "transit_options": [],
        }
        if sdist <= 2:
            entry["reach_options"].append({
                "mode": "walk", "label": "Walk", "icon": "\U0001f6b6",
                "from": from_name, "to": stop_name,
                "distance_km": round(sdist, 2), "duration_minutes": round(sdist * 12),
                "fare": 0, "per_person": 0,
                "from_lat": from_lat, "from_lng": from_lng,
                "to_lat": _safe(stop_lat), "to_lng": _safe(stop_lng),
                "arrives_at_stop": True,
            })
        if sdist >= 1.0:
            for mode, label, per_km, tpk, base, icon, cap, free_km in ride_types:
                if group_size > cap: continue
                if 1.0 <= sdist < 2.0 and mode not in ("bike",):
                    continue
                total = _calc_ride_fare(sdist, base, per_km, free_km)
                pp = round(total / group_size)
                if budget and total > budget: continue
                entry["reach_options"].append({
                    "mode": mode, "label": label, "icon": icon,
                    "from": from_name, "to": stop_name,
                    "distance_km": round(sdist, 2), "duration_minutes": round(sdist * tpk),
                    "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": cap,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": _safe(stop_lat), "to_lng": _safe(stop_lng),
                    "arrives_at_stop": True,
                })
        return entry

    def _add_transit_options(self, entry: dict, from_lat: float, from_lng: float,
                              dest_lat: float, dest_lng: float, dest_name: str,
                              group_size: int, budget: float, dest_nearby_bus: list, dest_nearby_metro: list,
                              dest_rail: list, is_long_dist: bool):
        """Add transit options to a destination entry. Returns list of transit_option dicts."""
        stop = entry["stop"]
        s_lat, s_lng = stop["lat"], stop["lng"]
        sname = stop["name"] if isinstance(stop.get("name"), str) else str(stop.get("name", ""))
        stop_dist_to_dest = _safe(self._haversine(s_lat, s_lng, dest_lat, dest_lng))

        if stop_dist_to_dest <= 0.1:
            return []

        ride_types = _RIDE_TYPES
        all_transit = []

        # === BUS TRANSIT - Show all available bus routes at this stop ===
        if stop["type"] in ("bus", "metro"):
            gtfs = _ensure_gtfs()
            all_routes = self._cached_gtfs_routes(sname) if gtfs else []
            if all_routes:
                for route_info in all_routes[:10]:
                    rn = route_info["route_number"]
                    next_deps = route_info["next_departures"]

                    full_shape = self._cached_shape_path(rn)
                    if full_shape and not _route_goes_toward_dest(full_shape, s_lat, s_lng, dest_lat, dest_lng, rn, _ensure_gtfs()):
                        continue

                    route_stops = self._cached_stops_toward(rn, s_lat, s_lng, dest_lat, dest_lng, max_stops=3)
                    if route_stops:
                        arrival = route_stops[0]
                        t_lat, t_lng = arrival["lat"], arrival["lng"]
                        arrival_name = arrival["stop_name"]
                        current_to_dest = _safe(self._haversine(s_lat, s_lng, dest_lat, dest_lng))
                        arrival_to_dest = _safe(self._haversine(t_lat, t_lng, dest_lat, dest_lng))
                        if arrival_to_dest > current_to_dest * 0.85:
                            continue
                        arrives_at_stop = True
                        shape_path = self._cached_shape_between(sname, arrival_name)
                    else:
                        # Skip routes where we can't find actual stops toward destination
                        continue

                    transit_dist = self._haversine(s_lat, s_lng, t_lat, t_lng)
                    if transit_dist < 0.5:
                        continue
                    bf = max(6, round(db.get_bmtc_ordinary_fare(transit_dist) or 6))
                    total = bf * group_size
                    if budget and total > budget: continue
                    bus_times_list = [{"departure_time": t, "route": rn} for t in next_deps]

                    # Use GTFS actual timing if available
                    gtfs_travel_time = None
                    if gtfs:
                        try:
                            gtfs_travel_time = gtfs.get_travel_time_between(sname, arrival_name, rn)
                        except Exception:
                            pass
                    bus_duration = gtfs_travel_time if gtfs_travel_time else round(transit_dist * 3)

                    dropoff_dist = _safe(self._haversine(t_lat, t_lng, dest_lat, dest_lng))

                    # === Next transit: bus & metro connections at arrival point ===
                    next_transit = self._build_next_transit(
                        t_lat, t_lng, sname, dest_lat, dest_lng, dest_name,
                        group_size, budget, dest_nearby_metro, ride_types, arrival_name, depth=2
                    )

                    # Build the transit option
                    topt = {
                        "mode": "bus_ordinary", "label": f"Bus {rn}", "icon": "\U0001f68c",
                        "route_number": rn,
                        "from": sname, "to": arrival_name,
                        "distance_km": round(transit_dist, 2),
                        "duration_minutes": round(bus_duration),
                        "fare": total, "per_person": bf,
                        "from_lat": s_lat, "from_lng": s_lng,
                        "to_lat": t_lat, "to_lng": t_lng,
                        "arrives_at_stop": arrives_at_stop,
                        "bus_times": bus_times_list[:5],
                        "transit_type": "bus",
                        "path": shape_path or full_shape or self._interpolate(s_lat, s_lng, t_lat, t_lng),
                        "next_transit": next_transit,
                    }
                    all_transit.append(topt)

                    # AC Vajra variant
                    ac_bf = max(10, round(db.get_bmtc_ac_fare(transit_dist) or 10))
                    ac_total = ac_bf * group_size
                    ac_duration = gtfs_travel_time if gtfs_travel_time else round(transit_dist * 2.5)
                    if not budget or ac_total <= budget:
                        ac_topt = {
                            "mode": "bus_ac_vajra", "label": f"Bus {rn} AC", "icon": "\U0001f68c",
                            "route_number": rn,
                            "from": sname, "to": arrival_name,
                            "distance_km": round(transit_dist, 2),
                            "duration_minutes": round(ac_duration),
                            "fare": ac_total, "per_person": ac_bf,
                            "from_lat": s_lat, "from_lng": s_lng,
                            "to_lat": t_lat, "to_lng": t_lng,
                            "arrives_at_stop": arrives_at_stop,
                            "bus_times": bus_times_list[:5],
                            "transit_type": "bus",
                            "path": shape_path or full_shape or self._interpolate(s_lat, s_lng, t_lat, t_lng),
                            "next_transit": next_transit,
                        }
                        all_transit.append(ac_topt)

        # === KIA BUS (Airport Buses) ===
        if db.kia_routes and stop_dist_to_dest > 3:
            for route_id, route_data in db.kia_routes.items():
                stops_list = route_data.get("stops", [])
                for i, s in enumerate(stops_list):
                    if sname.lower() in s["stop_name"].lower() or s["stop_name"].lower() in sname.lower():
                        next_stops = stops_list[i+1:i+4]
                        if not next_stops:
                            break
                        kia_fare = next_stops[-1].get("fare", 0) - s.get("fare", 0)
                        if kia_fare <= 0:
                            kia_fare = 210
                        total_kia = kia_fare * group_size
                        if budget and total_kia > budget: continue
                        kia_dest_stop = next_stops[-1]
                        all_transit.append({
                            "mode": "bus_ac_vajra", "label": f"KIA {route_id}", "icon": "\U0001f68c",
                            "route_number": route_id,
                            "from": sname, "to": kia_dest_stop["stop_name"],
                            "distance_km": round(stop_dist_to_dest, 2),
                            "duration_minutes": round(stop_dist_to_dest * 3),
                            "fare": total_kia, "per_person": kia_fare,
                            "from_lat": s_lat, "from_lng": s_lng,
                            "to_lat": kia_dest_stop.get("lat", dest_lat),
                            "to_lng": kia_dest_stop.get("lng", dest_lng),
                            "arrives_at_stop": True,
                            "transit_type": "bus",
                        })
                        break

        # === METRO TRANSIT - only show if valid line path exists and within operating hours ===
        if stop["type"] == "metro" and _is_metro_operating():
            seen_dest = set()
            for dm in dest_nearby_metro[:4]:
                dm_name = dm.get("name", "")
                if dm_name in seen_dest:
                    continue
                seen_dest.add(dm_name)
                transit_dist = _safe(self._haversine(s_lat, s_lng, dm["lat"], dm["lng"]))
                if transit_dist < 0.5: continue
                metro_path = db.get_metro_line_path(sname, dm_name)
                if not metro_path:
                    continue
                mf = round(db.get_metro_fare(transit_dist) or 15)
                total = mf * group_size
                if budget and total > budget: continue
                line_used = stop.get("line", dm.get("line", "Metro"))
                # Chain metro→bus transfers from destination metro station
                metro_next_transit = []
                dm_dest_dist = _safe(self._haversine(dm["lat"], dm["lng"], dest_lat, dest_lng))
                if dm_dest_dist > 1.5:
                    metro_next_transit = self._build_next_transit(
                        dm["lat"], dm["lng"], sname, dest_lat, dest_lng, dest_name,
                        group_size, budget, dest_nearby_metro, ride_types, dm_name, depth=2
                    )
                all_transit.append({
                    "mode": "metro", "label": f"Metro to {dm_name}", "icon": "\U0001f687",
                    "route_number": line_used,
                    "from": sname, "to": dm_name,
                    "distance_km": round(transit_dist, 2),
                    "duration_minutes": max(1, round(transit_dist / 35 * 60)),
                    "fare": total, "per_person": mf,
                    "from_lat": _safe(s_lat), "from_lng": _safe(s_lng),
                    "to_lat": _safe(dm.get("lat")), "to_lng": _safe(dm.get("lng")),
                    "arrives_at_stop": True,
                    "transit_type": "metro",
                    "path": metro_path,
                    "next_transit": metro_next_transit,
                })

        # === TRAIN TRANSIT ===
        if stop["type"] == "railway" and dest_rail and is_long_dist:
            for dr in dest_rail[:2]:
                train_dist = _safe(self._haversine(s_lat, s_lng, dr["lat"], dr["lng"]))
                if train_dist < 10: continue
                train_fare_pp = max(15, round(train_dist * 0.8))
                total_fare = train_fare_pp * group_size
                if budget and total_fare > budget: continue
                train_options = _get_train_options(sname, dr["name"])
                for tn, tname_d, dep_time, arr_time in train_options[:3]:
                    dur = int((int(arr_time[:2])*60+int(arr_time[3:5])) - (int(dep_time[:2])*60+int(dep_time[3:5])))
                    if dur <= 0: dur = round(train_dist * 1.2)
                    all_transit.append({
                        "mode": "train", "label": f"Train {tn} {tname_d}", "icon": "\U0001f686",
                        "route_number": tn,
                        "from": sname, "to": dr["name"],
                        "distance_km": round(train_dist, 2), "duration_minutes": dur,
                        "fare": total_fare, "per_person": train_fare_pp,
                        "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                        "to_lat": _safe(dr.get("lat")), "to_lng": _safe(dr.get("lng")),
                        "arrives_at_stop": True, "transit_type": "train",
                        "departure_time": dep_time, "arrival_time": arr_time,
                        "next_transit": [],
                        "final_options": [],
                    })

        # === FINAL MILE for ALL transit options (bus/walk/ride to destination) ===
        for topt in all_transit:
            t_lat, t_lng = topt["to_lat"], topt["to_lng"]
            tname = topt["to"]
            fdist = _safe(self._haversine(t_lat, t_lng, dest_lat, dest_lng))
            topt["final_options"] = []
            topt["dropoff_walk_min"] = round(fdist * 12)
            topt["dropoff_to_dest_km"] = round(fdist, 2)
            # Walk if within 2km
            if fdist <= 2.0:
                topt["final_options"].append({
                    "mode": "walk", "label": "Walk to Destination", "icon": "\U0001f6b6",
                    "from": tname, "to": dest_name,
                    "distance_km": round(fdist, 2), "duration_minutes": round(fdist * 12),
                    "fare": 0, "per_person": 0,
                    "from_lat": t_lat, "from_lng": t_lng,
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                    "path": self._interpolate(t_lat, t_lng, dest_lat, dest_lng, num_points=8),
                })
            # Bus final mile: find buses from drop-off that go toward dest
            if fdist > 0.5 and isinstance(topt.get("transit_type"), str) and topt["transit_type"] in ("bus", "metro") and _ensure_gtfs():
                all_routes_dropoff = self._cached_gtfs_routes(tname)
                for final_route_info in all_routes_dropoff[:2]:
                    frn = final_route_info["route_number"]
                    fr_shape = self._cached_shape_path(frn)
                    if fr_shape and _route_goes_toward_dest(fr_shape, t_lat, t_lng, dest_lat, dest_lng, frn, _ensure_gtfs()):
                        fr_stops = self._cached_stops_toward(frn, t_lat, t_lng, dest_lat, dest_lng, max_stops=2)
                        if fr_stops:
                            fr_arrive = fr_stops[0]
                            fr_dist = _safe(self._haversine(t_lat, t_lng, fr_arrive["lat"], fr_arrive["lng"]))
                            if fr_dist > 0.5 and fr_dist < fdist - 0.5:
                                fr_bf = max(6, round(db.get_bmtc_ordinary_fare(fr_dist) or 6))
                                fr_total = fr_bf * group_size
                                if not budget or fr_total <= budget:
                                    topt["final_options"].append({
                                        "mode": "bus_ordinary", "label": f"Bus {frn}", "icon": "\U0001f68c",
                                        "route_number": frn, "from": tname, "to": fr_arrive["stop_name"],
                                        "distance_km": round(fr_dist, 2), "duration_minutes": round(fr_dist * 4),
                                        "fare": fr_total, "per_person": fr_bf,
                                        "from_lat": t_lat, "from_lng": t_lng,
                                        "to_lat": _safe(fr_arrive["lat"]), "to_lng": _safe(fr_arrive["lng"]),
                                        "arrives_at_stop": True, "transit_type": "bus",
                                        "path": self._cached_shape_between(tname, fr_arrive["stop_name"]) or self._interpolate(t_lat, t_lng, fr_arrive["lat"], fr_arrive["lng"]),
                                        "final_options": [], "next_transit": []})
            # Ride options if distance >= 1km AND not already having a bus final that fits budget
            has_bus_final = any(o.get("mode","").startswith("bus") for o in topt["final_options"])
            if fdist >= 1.0 and (not has_bus_final or not budget):
                for mode, label, per_km, tpk, base, icon, cap, free_km in ride_types:
                    if group_size > cap: continue
                    total = _calc_ride_fare(fdist, base, per_km, free_km)
                    pp = round(total / group_size)
                    if budget and total > budget: continue
                    if budget and has_bus_final and mode not in ("walk",):
                        continue
                    topt["final_options"].append({
                        "mode": mode, "label": label, "icon": icon,
                        "from": tname, "to": dest_name,
                        "distance_km": round(fdist, 2), "duration_minutes": round(fdist * tpk),
                        "fare": total, "fare_min": total, "fare_max": round(total * 1.35), "per_person": pp, "group_capacity": cap,
                        "from_lat": t_lat, "from_lng": t_lng,
                        "to_lat": dest_lat, "to_lng": dest_lng,
                        "arrives_at_stop": False,
                        "path": self._interpolate(t_lat, t_lng, dest_lat, dest_lng, num_points=8),
                    })

        # Sort transit options by relevance: closer to dest + faster + cheaper first
        def _relevance_score(topt):
            dist_to_dest = _safe(self._haversine(topt.get("to_lat", dest_lat), topt.get("to_lng", dest_lng), dest_lat, dest_lng))
            score = 0
            score -= dist_to_dest * 10
            score -= topt.get("duration_minutes", 60) * 0.5
            score -= topt.get("fare", 0) * 0.1
            if topt.get("transit_type") == "metro":
                score += 15
            if topt.get("next_transit"):
                score -= 5
            if topt.get("final_options"):
                walk_final = any(o.get("mode") == "walk" for o in topt.get("final_options", []))
                if walk_final:
                    score += 10
            return score
        all_transit.sort(key=_relevance_score, reverse=True)
        entry["transit_options"] = all_transit
        return all_transit

    def _coord_key(self, lat, lng):
        return f"{round(lat,3)},{round(lng,3)}"

    def _is_visited(self, lat, lng, visited_set):
        """Check if a coordinate is within 300m of any visited point."""
        for v in list(visited_set):
            try:
                parts = v.split(",")
                vlat, vlng = float(parts[0]), float(parts[1])
                if _haversine_dist(lat, lng, vlat, vlng) < 0.8:
                    return True
            except Exception as e:
                logger.warning(f"Failed to parse visited coords from '{v}': {e}")
        return False

    def _cached_gtfs_routes(self, stop_name):
        key = str(stop_name)
        if key not in self._gtfs_route_cache:
            _g = _ensure_gtfs()
            self._gtfs_route_cache[key] = _g.get_all_routes_at_stop(stop_name) if _g else []
        return self._gtfs_route_cache[key]

    def _cached_shape_path(self, route_number):
        key = str(route_number).strip().upper()
        if key not in self._shape_cache:
            _g = _ensure_gtfs()
            self._shape_cache[key] = _g.get_shape_path_for_route(route_number) if _g else None
        return self._shape_cache[key]

    def _cached_stops_toward(self, route_number, from_lat, from_lng, dest_lat, dest_lng, max_stops=3):
        key = f"{route_number}|{round(from_lat,4)}|{round(from_lng,4)}|{round(dest_lat,4)}|{round(dest_lng,4)}|{max_stops}"
        if key not in self._stops_toward_cache:
            _g = _ensure_gtfs()
            self._stops_toward_cache[key] = _g.find_stops_on_route_toward_dest(route_number, from_lat, from_lng, dest_lat, dest_lng, max_stops) if _g else []
        return self._stops_toward_cache[key]

    def _cached_shape_between(self, from_name, to_name):
        key = f"{from_name}|{to_name}"
        if key not in self._shape_between_cache:
            _g = _ensure_gtfs()
            self._shape_between_cache[key] = _g.get_shape_between_stops(from_name, to_name) if _g else None
        return self._shape_between_cache[key]

    def _clear_caches(self):
        self._gtfs_route_cache.clear()
        self._shape_cache.clear()
        self._stops_toward_cache.clear()
        self._shape_between_cache.clear()

    def _build_next_transit(self, t_lat, t_lng, exclude_name, dest_lat, dest_lng, dest_name,
                            group_size, budget, dest_nearby_metro, ride_types, arrival_name="", depth=2,
                            visited_stops=None):
        _ensure_gtfs()
        next_transit = []
        dropoff_dist = _safe(self._haversine(t_lat, t_lng, dest_lat, dest_lng))

        if dropoff_dist <= 1.5:
            return next_transit

        if visited_stops is None:
            visited_stops = set()
        visited_stops.add(self._coord_key(t_lat, t_lng))
        exclude_lower = exclude_name.lower() if exclude_name else ""

        def _add_final_walk(nt2_name, nt2_lat, nt2_lng, nt2_dist):
            return [{
                "mode": "walk", "label": "Walk to Destination", "icon": "\U0001f6b6",
                "from": nt2_name, "to": dest_name, "distance_km": round(nt2_dist, 2),
                "duration_minutes": round(nt2_dist * 12), "fare": 0, "per_person": 0,
                "from_lat": nt2_lat, "from_lng": nt2_lng, "to_lat": dest_lat, "to_lng": dest_lng,
                "arrives_at_stop": False,
                "path": self._interpolate(nt2_lat, nt2_lng, dest_lat, dest_lng, num_points=8),
            }]

        def _make_bus_transit(route_info, stop_name, stop_lat, stop_lng, dest_name_label, n_lat, n_lng, n_name, nt2_dist, depth_left, visited):
            rn2 = route_info["route_number"]
            shape_path2 = self._cached_shape_path(rn2)
            route_stops2 = self._cached_stops_toward(rn2, stop_lat, stop_lng, dest_lat, dest_lng, max_stops=2)
            if not route_stops2:
                return None
            arrive2 = route_stops2[0]
            t2_dist = _safe(self._haversine(stop_lat, stop_lng, arrive2["lat"], arrive2["lng"]))
            if t2_dist < 0.5:
                return None
            next_deps2 = route_info.get("next_departures", [])
            n_lat2, n_lng2 = arrive2["lat"], arrive2["lng"]
            n_name2 = arrive2["stop_name"]
            n_dist2 = _safe(self._haversine(n_lat2, n_lng2, dest_lat, dest_lng))
            arrival_hub = any(h in n_name2.lower() for h in _MAJOR_HUBS)
            if not arrival_hub and n_dist2 >= dropoff_dist - 0.5:
                return None
            bf2 = max(6, round(db.get_bmtc_ordinary_fare(t2_dist) or 6))
            t2_total = bf2 * group_size
            if budget and t2_total > budget:
                return None
            nt2_path = self._cached_shape_between(stop_name, n_name2) or shape_path2 or self._interpolate(stop_lat, stop_lng, n_lat2, n_lng2)
            nt2_final = []
            if n_dist2 <= 2.0:
                nt2_final = _add_final_walk(n_name2, n_lat2, n_lng2, n_dist2)
            nt2_next = []
            if depth_left > 1 and n_dist2 > 1.5:
                nt2_next = self._build_next_transit(
                    n_lat2, n_lng2, n_name2, dest_lat, dest_lng, dest_name,
                    group_size, budget, dest_nearby_metro, ride_types, n_name2, depth=depth_left - 1,
                    visited_stops=visited.copy()
                )
            return {
                "mode": "bus_ordinary", "label": f"Bus {rn2}", "icon": "\U0001f68c",
                "route_number": rn2, "from": stop_name, "to": n_name2,
                "distance_km": round(t2_dist, 2), "duration_minutes": round(t2_dist * 4),
                "fare": t2_total, "per_person": bf2,
                "from_lat": _safe(stop_lat), "from_lng": _safe(stop_lng),
                "to_lat": _safe(n_lat2), "to_lng": _safe(n_lng2),
                "arrives_at_stop": True, "transit_type": "bus",
                "path": nt2_path,
                "bus_times": [{"departure_time": t, "route": rn2} for t in next_deps2[:3]],
                "next_transit": nt2_next,
                "final_options": nt2_final,
            }

        # STEP 1: buses at SAME arrival stop (most common: get off bus A, board bus B at same stop)
        if arrival_name and _ensure_gtfs():
            same_stop_routes = self._cached_gtfs_routes(arrival_name)
            for route_info in same_stop_routes[:4]:
                rn = route_info["route_number"]
                if rn.lower() == exclude_lower:
                    continue
                shape_path = self._cached_shape_path(rn)
                if shape_path and not _route_goes_toward_dest(shape_path, t_lat, t_lng, dest_lat, dest_lng, rn, _ensure_gtfs()):
                    continue
                item = _make_bus_transit(route_info, arrival_name, t_lat, t_lng, dest_name, t_lat, t_lng, "", 0, depth, visited_stops)
                if item:
                    next_transit.append(item)

        # STEP 2: then nearby stops
        nearby_arrival_bus = db.find_nearby_bus_stops(t_lat, t_lng, 0.5) or []
        for abs in nearby_arrival_bus[:3]:
            aname = abs.get("name", "")
            aname_lower = aname.lower()
            if aname_lower == exclude_lower or aname_lower == (arrival_name or "").lower():
                continue
            if self._is_visited(abs["lat"], abs["lng"], visited_stops):
                continue
            visited_stops.add(self._coord_key(abs["lat"], abs["lng"]))
            gtfs_at_arrival = self._cached_gtfs_routes(aname)
            for route_info in gtfs_at_arrival[:2]:
                rn2 = route_info["route_number"]
                shape_path2 = self._cached_shape_path(rn2)
                if shape_path2 and not _route_goes_toward_dest(shape_path2, abs["lat"], abs["lng"], dest_lat, dest_lng, rn2, _ensure_gtfs()):
                    continue
                item = _make_bus_transit(route_info, aname, abs["lat"], abs["lng"], dest_name, abs["lat"], abs["lng"], "", 0, depth, visited_stops)
                if item:
                    next_transit.append(item)

        # STEP 3: Metro at arrival point
        if _is_metro_operating():
            try:
                nearby_metro_at_arrival = db.find_nearby_metro_stations(t_lat, t_lng, 1.5) or []
                for nm in nearby_metro_at_arrival[:1]:
                    nm_line = nm.get("line", "")
                    nm_name = nm["name"]
                    best_dm = None
                    best_dm_dist = float("inf")
                    m_stations = getattr(db, "metro_stations", [])
                    for station in m_stations:
                        if station.get("line") == nm_line and station["name"].lower() != nm_name.lower():
                            s_dist = _safe(self._haversine(station["lat"], station["lng"], dest_lat, dest_lng))
                            if s_dist < best_dm_dist:
                                mpath = db.get_metro_line_path(nm_name, station["name"])
                                if mpath:
                                    best_dm_dist = s_dist
                                    best_dm = station
                    if best_dm:
                        dm = best_dm
                        dm_dist = _safe(self._haversine(nm["lat"], nm["lng"], dm["lat"], dm["lng"]))
                        if dm_dist > 0.5:
                            dm_lat, dm_lng = dm["lat"], dm["lng"]
                            dm_name = dm["name"]
                            dest_to_dm = _safe(self._haversine(dm_lat, dm_lng, dest_lat, dest_lng))
                            dm_fare = round(db.get_metro_fare(dm_dist) or 15)
                            dm_total = dm_fare * group_size
                            if not budget or dm_total <= budget:
                                dm_final = []
                                if dest_to_dm <= 2.0:
                                    dm_final = _add_final_walk(dm_name, dm_lat, dm_lng, dest_to_dm)
                                dm_next_transit = []
                                if depth > 1 and dest_to_dm > 1.5:
                                    dm_next_transit = self._build_next_transit(
                                        dm_lat, dm_lng, dm_name, dest_lat, dest_lng, dest_name,
                                        group_size, budget, dest_nearby_metro, ride_types, dm_name, depth=depth - 1,
                                        visited_stops=visited_stops.copy()
                                    )
                                next_transit.append({
                                    "mode": "metro", "label": f"Metro {nm_name} \u2192 {dm_name}", "icon": "\U0001f687",
                                    "route_number": nm_line, "from": nm_name, "to": dm_name,
                                    "distance_km": round(dm_dist, 2), "duration_minutes": round(dm_dist * 2 + 5),
                                    "fare": dm_total, "per_person": dm_fare,
                                    "from_lat": _safe(nm.get("lat")), "from_lng": _safe(nm.get("lng")),
                                    "to_lat": _safe(dm_lat), "to_lng": _safe(dm_lng),
                                    "arrives_at_stop": True, "transit_type": "metro",
                                    "path": mpath, "final_options": dm_final, "next_transit": dm_next_transit,
                                })
            except Exception as e:
                logger.warning(f"Failed to build next transit metro path: {e}")
        return next_transit

    def _build_single_segment(self, from_lat: float, from_lng: float, from_name: str,
                               dest_lat: float, dest_lng: float, dest_name: str,
                               group_size: int, budget: float, segment_index: int) -> dict:
        """Build a single segment from 'from' location: direct options + nearby stops with reach + transit options."""
        direct_dist = _safe(self._haversine(from_lat, from_lng, dest_lat, dest_lng))
        _ensure_gtfs()
        t0 = time.time()
        segment = {
            "segment_index": segment_index,
            "from": {"name": from_name, "lat": from_lat, "lng": from_lng},
            "direct_options": [],
            "destinations": [],
        }

        # Direct options
        self._add_direct_options(segment["direct_options"], from_lat, from_lng, from_name,
                                  dest_lat, dest_lng, dest_name, group_size, budget)

        # Nearby stops - expanded search radius to 2km for bus, 3km for metro
        nearby_bus = db.find_nearby_bus_stops(from_lat, from_lng, 2.0) or []
        nearby_metro = db.find_nearby_metro_stations(from_lat, from_lng, 3.0) or []
        nearby_rail = db.find_nearby_railway_stations(from_lat, from_lng, 15.0) or []
        dest_rail = db.find_nearby_railway_stations(dest_lat, dest_lng, 30.0) or []
        is_long_dist = self._is_outside_bengaluru(dest_lat, dest_lng) or direct_dist > 40
        dest_nearby_bus = db.find_nearby_bus_stops(dest_lat, dest_lng, 1.0) or []
        dest_nearby_metro = db.find_nearby_metro_stations(dest_lat, dest_lng, 3.0) or []

        processed = set()
        all_entries = []

        # Bus stops - only show stops with actual GTFS transport data
        for stop in nearby_bus[:5]:
            sname = stop.get("name", "Bus Stop")
            key = f"bus_{sname}"
            if key in processed: continue
            processed.add(key)
            # Skip stops with no GTFS data (no buses available)
            stop_dist = _safe(self._haversine(from_lat, from_lng, stop["lat"], stop["lng"]))
            has_gtfs = _has_gtfs_route(sname)
            if not has_gtfs and stop_dist > 2.0:
                continue
            # Skip if stop is much farther from destination AND not a hub
            current_to_dest = _safe(self._haversine(from_lat, from_lng, dest_lat, dest_lng))
            stop_to_dest = _safe(self._haversine(stop["lat"], stop["lng"], dest_lat, dest_lng))
            is_stop_hub = any(h in sname.lower() for h in _MAJOR_HUBS)
            if not is_stop_hub and stop_to_dest > current_to_dest * 1.5 and stop_dist > 1.0:
                continue
            entry = self._add_reach_options(from_lat, from_lng, from_name,
                                             sname, stop["lat"], stop["lng"], "bus",
                                             group_size, budget)
            if entry:
                self._add_transit_options(entry, from_lat, from_lng,
                                           dest_lat, dest_lng, dest_name,
                                           group_size, budget, dest_nearby_bus, dest_nearby_metro,
                                           dest_rail, is_long_dist)
                all_entries.append(entry)

        # Metro stations
        for station in nearby_metro[:6]:
            sname = station.get("name", "Metro Station")
            key = f"metro_{sname}"
            if key in processed: continue
            processed.add(key)
            entry = self._add_reach_options(from_lat, from_lng, from_name,
                                             sname, station["lat"], station["lng"], "metro",
                                             group_size, budget)
            if entry:
                entry["stop"]["line"] = station.get("line", "")
                self._add_transit_options(entry, from_lat, from_lng,
                                           dest_lat, dest_lng, dest_name,
                                           group_size, budget, dest_nearby_bus, dest_nearby_metro,
                                           dest_rail, is_long_dist)
                all_entries.append(entry)

        # Railway stations
        if nearby_rail and is_long_dist:
            for station in nearby_rail[:5]:
                sname = station.get("name", "Railway Station")
                key = f"rail_{sname}"
                if key in processed: continue
                processed.add(key)
                entry = self._add_reach_options(from_lat, from_lng, from_name,
                                                 sname, station["lat"], station["lng"], "railway",
                                                 group_size, budget)
                if entry:
                    self._add_transit_options(entry, from_lat, from_lng,
                                               dest_lat, dest_lng, dest_name,
                                               group_size, budget, dest_nearby_bus, dest_nearby_metro,
                                               dest_rail, is_long_dist)
                    all_entries.append(entry)

        # Filter destinations: remove those with no reach options AND no transit options
        all_entries = [
            d for d in all_entries
            if (d.get("reach_options") and len(d["reach_options"]) > 0) or
               (d.get("transit_options") and len(d["transit_options"]) > 0)
        ]
        # Sort by relevance: closest to source first, then most transit options
        def _dest_score(de):
            dlng = de["stop"]["lng"]
            dlat = de["stop"]["lat"]
            score = 0
            score -= _safe(self._haversine(from_lat, from_lng, dlat, dlng)) * 2
            score -= _safe(self._haversine(dlat, dlng, dest_lat, dest_lng)) * 0.5
            score += len(de.get("transit_options", [])) * 3
            if de.get("stop", {}).get("type") == "metro":
                score += 5
            return score
        all_entries.sort(key=_dest_score, reverse=True)
        max_dest = 6 if segment_index == 0 else 4
        segment["destinations"] = all_entries[:max_dest]
        segment["route_paths"] = self._astar_route_paths(from_lat, from_lng, dest_lat, dest_lng, group_size, budget)
        elapsed = time.time() - t0
        logger.info(f"  _build_single_segment[{segment_index}] from={from_name} {elapsed:.1f}s dests={len(segment['destinations'])} rpaths={len(segment['route_paths'])}")
        return segment

    def _is_hub_or_close_to_dest(self, lat, lng, dest_lat, dest_lng, stop_name=""):
        dist = _safe(self._haversine(lat, lng, dest_lat, dest_lng))
        if dist <= 5.0:
            return True
        return any(h in stop_name.lower() for h in _MAJOR_HUBS)

    def get_all_segments(self, from_lat: float, from_lng: float, from_name: str,
                          dest_lat: float, dest_lng: float, dest_name: str,
                          group_size: int = 1, budget: float = None, max_depth: int = 3) -> dict:
        # Check cache (5-min TTL)
        ck = f"{round(from_lat,4)},{round(from_lng,4)},{round(dest_lat,4)},{round(dest_lng,4)},{group_size},{budget},{max_depth}"
        now = time.time()
        cached = self._segments_cache.get(ck)
        if cached and (now - cached[0]) < 300:
            logger.info(f"get_all_segments cache hit for {ck}")
            return cached[1]

        seg_start = time.time()
        segments = []
        visited_pts = set()

        seg0 = self._build_single_segment(from_lat, from_lng, from_name,
                                           dest_lat, dest_lng, dest_name,
                                           group_size, budget, 0)
        segments.append(seg0)
        next_from_map = {}

        for dest_entry in seg0["destinations"]:
            for topt in dest_entry.get("transit_options", []):
                if topt.get("to_lat") and topt.get("to_lng"):
                    tlat, tlng = topt["to_lat"], topt["to_lng"]
                    ardist = _safe(self._haversine(tlat, tlng, dest_lat, dest_lng))
                    if 0.05 < ardist <= 50:
                        nk = f"{round(tlat,4)},{round(tlng,4)}"
                        stop_name = topt.get("to", "")
                if nk not in visited_pts and nk not in next_from_map and self._is_hub_or_close_to_dest(tlat, tlng, dest_lat, dest_lng, stop_name):
                    if len(next_from_map) < 3:  # Limit to 3 parallel next segments
                        next_from_map[nk] = (tlat, tlng, stop_name)
                        topt["needs_next_segment"] = True

        depth = 1
        logger.info(f"  next_from_map has {len(next_from_map)} entries for depth={depth}")
        while next_from_map and depth < max_depth and len(segments) < 4:
            new_map = {}
            for nk, (nl, ng, nn) in next_from_map.items():
                if nk in visited_pts:
                    continue
                visited_pts.add(nk)
                next_seg = self._build_single_segment(nl, ng, nn,
                                                       dest_lat, dest_lng, dest_name,
                                                       group_size, budget, depth)
                segments.append(next_seg)
                seg_arr_idx = len(segments) - 1

                for prev_seg in segments:
                    if prev_seg["segment_index"] >= depth:
                        continue
                    for de in prev_seg["destinations"]:
                        for topt in de.get("transit_options", []):
                            tmk = f"{round(topt.get('to_lat',0),4)},{round(topt.get('to_lng',0),4)}"
                            if tmk == nk:
                                topt["next_segment_index"] = seg_arr_idx
                                topt.pop("needs_next_segment", None)

                for de in next_seg["destinations"]:
                    for topt in de.get("transit_options", []):
                        if topt.get("to_lat") and topt.get("to_lng"):
                            tlat2, tlng2 = topt["to_lat"], topt["to_lng"]
                            ardist2 = _safe(self._haversine(tlat2, tlng2, dest_lat, dest_lng))
                            if 0.05 < ardist2 <= 50:
                                tmk2 = f"{round(tlat2,4)},{round(tlng2,4)}"
                                stop_name2 = topt.get("to", "")
                                if tmk2 not in visited_pts and tmk2 not in new_map and self._is_hub_or_close_to_dest(tlat2, tlng2, dest_lat, dest_lng, stop_name2):
                                    if len(new_map) < 2:  # Limit deeper builds to 2
                                        new_map[tmk2] = (tlat2, tlng2, stop_name2)
                                        topt["needs_next_segment"] = True

            next_from_map = new_map
            depth += 1

        result = {
            "source": {"lat": from_lat, "lng": from_lng, "name": from_name},
            "dest": {"lat": dest_lat, "lng": dest_lng, "name": dest_name},
            "segments": segments,
            "total_segments": len(segments),
        }
        elapsed = time.time() - seg_start
        logger.info(f"get_all_segments built {len(segments)} segments in {elapsed:.1f}s")
        self._segments_cache[ck] = (time.time(), result)
        return result
