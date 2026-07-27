import logging
from geopy.distance import geodesic
from backend.core.database import db
from backend.services.segment_builder import TripSegmentBuilder

logger = logging.getLogger(__name__)
from backend.services.transit_config import (
    _ensure_gtfs, _RIDE_TYPES, _calc_ride_fare,
    _get_train_options, _safe, _current_hour, _is_metro_operating,
    _haversine_dist, _MAJOR_HUBS, _route_goes_toward_dest,
    _gtfs_buses_at_stop, _has_gtfs_route, clean_route_short_name,
)

class TransitService:

    def haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        try:
            d = geodesic((lat1, lng1), (lat2, lng2)).km
            return _safe(d, 0.0)
        except Exception as e:
            logger.warning(f"geodesic failed for ({lat1},{lng1})→({lat2},{lng2}): {e}")
            return 0.0

    def _find_common_routes(self, src_stop: dict, dest_stop: dict) -> list:
        src_routes = set(clean_route_short_name(r) for r in src_stop.get("routes", []))
        dest_routes = set(clean_route_short_name(r) for r in dest_stop.get("routes", []))
        common = sorted(src_routes & dest_routes)
        return common[:5]

    def _add_leg_coords(self, route: dict, slat: float, slng: float, dlat: float, dlng: float):
        for leg in route.get("legs", []):
            fname = leg.get("from", "").lower()
            tname = leg.get("to", "").lower()
            # Look up coordinates from transit database
            if "your location" in fname or fname == slat:
                leg["from_lat"] = slat; leg["from_lng"] = slng
            else:
                stop = db.find_stop_by_name(fname)
                if stop:
                    leg["from_lat"] = stop["lat"]; leg["from_lng"] = stop["lng"]
                else:
                    leg["from_lat"] = slat; leg["from_lng"] = slng
            if "destination" in tname or tname == dlat:
                leg["to_lat"] = dlat; leg["to_lng"] = dlng
            else:
                stop = db.find_stop_by_name(tname)
                if stop:
                    leg["to_lat"] = stop["lat"]; leg["to_lng"] = stop["lng"]
                else:
                    leg["to_lat"] = dlat; leg["to_lng"] = dlng

    def get_route_legs_public(self, source_lat: float, source_lng: float,
                               dest_lat: float, dest_lng: float,
                               budget: float = None, group_size: int = 1,
                               weather: dict = None) -> list:
        direct_dist = self.haversine_distance(source_lat, source_lng, dest_lat, dest_lng)

        possible_routes = []

        # PRIMARY: A* enriched multi-hop routes — no distance limit, real GTFS data
        astar_routes = []
        try:
            astar_routes = self.astar_graph.find_enriched_routes(
                source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size
            )
        except Exception as e:
            logger.warning(f"A* enriched routing failed: {e}")
        possible_routes.extend(astar_routes)

        # FALLBACK: old generators only if A* found nothing
        if not astar_routes:
            possible_routes.extend(self._generate_bus_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
            possible_routes.extend(self._generate_metro_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
            possible_routes.extend(self._generate_metro_interchange_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
            possible_routes.extend(self._generate_kia_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
            possible_routes.extend(self._generate_multi_modal_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))

        if budget:
            possible_routes = [r for r in possible_routes if r["total_fare"] <= budget]

        from backend.services.transit_scoring import topsis_score_routes
        topsis_score_routes(possible_routes, budget, group_size, weather)
        for r in possible_routes:
            self._add_leg_coords(r, source_lat, source_lng, dest_lat, dest_lng)

        possible_routes.sort(key=lambda x: (x["overall_score"], -x.get("total_fare", 999)), reverse=True)
        return possible_routes[:30]

    def _get_bus_route_nums(self, src_stop: dict, dest_stop: dict, max_routes: int = 3) -> list:
        common = self._find_common_routes(src_stop, dest_stop)
        return common[:max_routes]

    def _generate_bus_routes(self, slat, slng, dlat, dlng, dist, group_size):
        routes = []
        nearby_src_stops = db.find_nearby_bus_stops(slat, slng, 1.0)
        nearby_dest_stops = db.find_nearby_bus_stops(dlat, dlng, 1.0)

        if nearby_src_stops and nearby_dest_stops:
            src_stop = nearby_src_stops[0]
            dest_stop = nearby_dest_stops[0]
            walking_to_stop = self.haversine_distance(slat, slng, src_stop["lat"], src_stop["lng"])
            walking_from_stop = self.haversine_distance(dlat, dlng, dest_stop["lat"], dest_stop["lng"])
            bus_dist = self.haversine_distance(src_stop["lat"], src_stop["lng"], dest_stop["lat"], dest_stop["lng"])
            bus_fare = db.get_bmtc_ordinary_fare(bus_dist) * group_size
            total_walk = walking_to_stop + walking_from_stop
            common_routes = self._get_bus_route_nums(src_stop, dest_stop)
            route_str = ", ".join(common_routes) if common_routes else "Multiple routes available"

            routes.append({
                "type": "bus_ordinary",
                "total_fare": bus_fare,
                "total_duration_minutes": round((bus_dist / 25) * 60 + total_walk * 12),
                "total_distance_km": round(bus_dist + total_walk, 2),
                "total_walking_km": round(total_walk, 2),
                "overall_score": 80 - (bus_dist * 0.5) + (group_size == 1) * 10,
                "route_numbers": common_routes,
                "legs": [
                    {
                        "from": "Your Location", "to": src_stop["name"],
                        "mode": "walk",
                        "distance_km": round(walking_to_stop, 2),
                        "duration_minutes": round(walking_to_stop * 12),
                        "fare": 0
                    },
                    {
                        "from": src_stop["name"], "to": dest_stop["name"],
                        "mode": "bus_ordinary",
                        "distance_km": round(bus_dist, 2),
                        "duration_minutes": round((bus_dist / 25) * 60),
                        "fare": bus_fare,
                        "route_numbers": common_routes,
                        "instructions": f"Board bus {route_str} from {src_stop['name']}"
                    },
                    {
                        "from": dest_stop["name"], "to": "Your Destination",
                        "mode": "walk",
                        "distance_km": round(walking_from_stop, 2),
                        "duration_minutes": round(walking_from_stop * 12),
                        "fare": 0
                    }
                ]
            })

            ac_fare = db.get_bmtc_ac_fare(bus_dist) * group_size
            routes.append({
                "type": "bus_ac_vajra",
                "total_fare": ac_fare,
                "total_duration_minutes": round((bus_dist / 30) * 60 + total_walk * 12),
                "total_distance_km": round(bus_dist + total_walk, 2),
                "total_walking_km": round(total_walk, 2),
                "overall_score": 75 - (bus_dist * 0.4) + (group_size == 1) * 10,
                "route_numbers": common_routes,
                "legs": [
                    {
                        "from": "Your Location", "to": src_stop["name"],
                        "mode": "walk",
                        "distance_km": round(walking_to_stop, 2),
                        "duration_minutes": round(walking_to_stop * 12),
                        "fare": 0
                    },
                    {
                        "from": src_stop["name"], "to": dest_stop["name"],
                        "mode": "bus_ac_vajra",
                        "distance_km": round(bus_dist, 2),
                        "duration_minutes": round((bus_dist / 30) * 60),
                        "fare": ac_fare,
                        "route_numbers": common_routes,
                        "instructions": f"Board AC bus {route_str} from {src_stop['name']}"
                    },
                    {
                        "from": dest_stop["name"], "to": "Your Destination",
                        "mode": "walk",
                        "distance_km": round(walking_from_stop, 2),
                        "duration_minutes": round(walking_from_stop * 12),
                        "fare": 0
                    }
                ]
            })
        return routes

    def _generate_metro_routes(self, slat, slng, dlat, dlng, dist, group_size):
        routes = []
        nearby_src = db.find_nearby_metro_stations(slat, slng, 3.0)
        nearby_dest = db.find_nearby_metro_stations(dlat, dlng, 3.0)

        if nearby_src and nearby_dest:
            src_metro = nearby_src[0]
            dest_metro = nearby_dest[0]
            metro_dist = self.haversine_distance(src_metro["lat"], src_metro["lng"], dest_metro["lat"], dest_metro["lng"])
            # Skip metro if source and dest stations are same (<0.5km apart) or route is too short for metro
            if metro_dist < 0.5 or dist < 1.0:
                return routes
            walking_to = self.haversine_distance(slat, slng, src_metro["lat"], src_metro["lng"])
            walking_from = self.haversine_distance(dlat, dlng, dest_metro["lat"], dest_metro["lng"])
            metro_fare = db.get_metro_fare(metro_dist) * group_size
            total_walk = walking_to + walking_from
            same_line = src_metro.get("line") == dest_metro.get("line")

            routes.append({
                "type": "metro",
                "total_fare": metro_fare,
                "total_duration_minutes": round((metro_dist / 35) * 60 + total_walk * 12 + (5 if not same_line else 0)),
                "total_distance_km": round(metro_dist + total_walk, 2),
                "total_walking_km": round(total_walk, 2),
                "overall_score": 85 - (metro_dist * 0.3) + (10 if same_line else 0),
                "legs": [
                    {
                        "from": "Your Location", "to": src_metro["name"],
                        "mode": "walk",
                        "distance_km": round(walking_to, 2),
                        "duration_minutes": round(walking_to * 12),
                        "fare": 0
                    },
                    {
                        "from": src_metro["name"], "to": dest_metro["name"],
                        "mode": "metro",
                        "line": src_metro.get("line"),
                        "distance_km": round(metro_dist, 2),
                        "duration_minutes": round((metro_dist / 35) * 60),
                        "fare": metro_fare,
                        "instructions": f"Take {src_metro.get('line')} from {src_metro['name']} to {dest_metro['name']}"
                    },
                    {
                        "from": dest_metro["name"], "to": "Your Destination",
                        "mode": "walk",
                        "distance_km": round(walking_from, 2),
                        "duration_minutes": round(walking_from * 12),
                        "fare": 0
                    }
                ]
            })
        return routes

    def _generate_metro_interchange_routes(self, slat, slng, dlat, dlng, dist, group_size):
        routes = []
        nearby_src = db.find_nearby_metro_stations(slat, slng, 3.0)
        nearby_dest = db.find_nearby_metro_stations(dlat, dlng, 3.0)

        if not nearby_src or not nearby_dest:
            return routes

        src_metro = nearby_src[0]
        dest_metro = nearby_dest[0]

        if src_metro.get("line") == dest_metro.get("line"):
            return routes

        interchanges = [s for s in db.metro_stations if s.get("is_interchange")]
        if not interchanges:
            return routes

        # Phase 1: Try single-interchange route (same station on both lines)
        src_name = src_metro["name"].lower()
        src_all_lines = set(s["line"] for s in db.metro_stations if s["name"].lower() == src_name)
        for ic in interchanges:
            if ic.get("line") not in src_all_lines:
                continue
            src_on_ic_line = next((s for s in db.metro_stations if s["name"].lower() == src_name and s["line"] == ic.get("line")), src_metro)
            walking_to = self.haversine_distance(slat, slng, src_on_ic_line["lat"], src_on_ic_line["lng"])
            leg1_dist = db.get_metro_distance_between(src_on_ic_line["name"], ic["name"]) or self.haversine_distance(src_on_ic_line["lat"], src_on_ic_line["lng"], ic["lat"], ic["lng"])
            leg2_dist = db.get_metro_distance_between(ic["name"], dest_metro["name"]) or self.haversine_distance(ic["lat"], ic["lng"], dest_metro["lat"], dest_metro["lng"])
            walking_from = self.haversine_distance(dlat, dlng, dest_metro["lat"], dest_metro["lng"])
            total_metro_dist = leg1_dist + leg2_dist
            metro_fare = db.get_metro_fare(total_metro_dist) * group_size
            total_walk = walking_to + walking_from

            dest_line_stations = [s for s in db.metro_stations if s.get("line") == dest_metro.get("line")]
            dest_ic = None
            for s in dest_line_stations:
                if s.get("is_interchange"):
                    sn = s["name"].lower()
                    icn = ic["name"].lower()
                    if sn == icn or sn in icn or icn in sn:
                        dest_ic = s
                        break

            if not dest_ic:
                continue

            routes.append({
                "type": "metro_interchange",
                "total_fare": metro_fare,
                "total_duration_minutes": round((leg1_dist / 35) * 60 + (leg2_dist / 35) * 60 + total_walk * 12 + 10),
                "total_distance_km": round(total_metro_dist + total_walk, 2),
                "total_walking_km": round(total_walk, 2),
                "overall_score": 82 - (total_metro_dist * 0.2),
                "legs": [
                    {"from": "Your Location", "to": src_on_ic_line["name"], "mode": "walk", "distance_km": round(walking_to, 2), "duration_minutes": round(walking_to * 12), "fare": 0},
                    {"from": src_on_ic_line["name"], "to": ic["name"], "mode": "metro", "line": ic.get("line"), "distance_km": round(leg1_dist, 2), "duration_minutes": round((leg1_dist / 35) * 60), "fare": round(metro_fare * 0.5, 2), "instructions": f"Take {ic.get('line')} from {src_on_ic_line['name']} to {ic['name']} (interchange)"},
                    {"from": ic["name"], "to": dest_metro["name"], "mode": "metro", "line": dest_metro.get("line"), "distance_km": round(leg2_dist, 2), "duration_minutes": round((leg2_dist / 35) * 60), "fare": round(metro_fare * 0.5, 2), "instructions": f"Switch to {dest_metro.get('line')} at {ic['name']} to {dest_metro['name']}"},
                    {"from": dest_metro["name"], "to": "Your Destination", "mode": "walk", "distance_km": round(walking_from, 2), "duration_minutes": round(walking_from * 12), "fare": 0},
                ]
            })

        # Phase 2: Try double-interchange (e.g. Purple→Majestic→Green→RVR→Yellow)
        if not any(r["type"] == "metro_interchange" for r in routes):
            hub_map = {}
            for ic in interchanges:
                name = ic["name"].lower()
                line = ic["line"]
                if name not in hub_map:
                    hub_map[name] = []
                hub_map[name].append(line)

            for hub_name, lines in hub_map.items():
                if len(lines) < 2:
                    continue
                conn_line = None
                for l in lines:
                    if l != src_metro.get("line") and l != dest_metro.get("line"):
                        conn_line = l
                        break
                if not conn_line:
                    continue
                ic1 = None
                ic2 = None
                for ic in interchanges:
                    if ic["name"].lower() == hub_name:
                        if ic["line"] == src_metro.get("line"):
                            ic1 = ic
                        elif ic["line"] == conn_line:
                            ic2 = ic
                if not ic1 or not ic2:
                    continue
                # Find second interchange on conn_line → dest_line
                for ic3 in interchanges:
                    if ic3.get("line") != conn_line:
                        continue
                    ic3_name = ic3["name"].lower()
                    ic3_on_dest = [s for s in db.metro_stations if s.get("line") == dest_metro.get("line") and s.get("name").lower() == ic3_name and s.get("is_interchange")]
                    if not ic3_on_dest:
                        continue
                    ic4 = ic3_on_dest[0]
                    walking_to = self.haversine_distance(slat, slng, src_metro["lat"], src_metro["lng"])
                    leg1 = db.get_metro_distance_between(src_metro["name"], ic1["name"]) or self.haversine_distance(src_metro["lat"], src_metro["lng"], ic1["lat"], ic1["lng"])
                    leg2 = db.get_metro_distance_between(ic2["name"], ic3["name"]) or self.haversine_distance(ic2["lat"], ic2["lng"], ic3["lat"], ic3["lng"])
                    leg3 = db.get_metro_distance_between(ic4["name"], dest_metro["name"]) or self.haversine_distance(ic4["lat"], ic4["lng"], dest_metro["lat"], dest_metro["lng"])
                    walking_from = self.haversine_distance(dlat, dlng, dest_metro["lat"], dest_metro["lng"])
                    total = leg1 + leg2 + leg3
                    mfare = db.get_metro_fare(total) * group_size
                    twalk = walking_to + walking_from
                    routes.append({
                        "type": "metro_interchange",
                        "total_fare": mfare,
                        "total_duration_minutes": round((leg1 / 35) * 60 + (leg2 / 35) * 60 + (leg3 / 35) * 60 + twalk * 12 + 15),
                        "total_distance_km": round(total + twalk, 2),
                        "total_walking_km": round(twalk, 2),
                        "overall_score": 80 - (total * 0.15),
                        "legs": [
                            {"from": "Your Location", "to": src_metro["name"], "mode": "walk", "distance_km": round(walking_to, 2), "duration_minutes": round(walking_to * 12), "fare": 0},
                            {"from": src_metro["name"], "to": ic1["name"], "mode": "metro", "line": src_metro.get("line"), "distance_km": round(leg1, 2), "duration_minutes": round((leg1 / 35) * 60), "fare": round(mfare * 0.35, 2), "instructions": f"Take {src_metro.get('line')} to {ic1['name']}"},
                            {"from": ic2["name"], "to": ic3["name"], "mode": "metro", "line": conn_line, "distance_km": round(leg2, 2), "duration_minutes": round((leg2 / 35) * 60), "fare": round(mfare * 0.3, 2), "instructions": f"Switch to {conn_line} at {ic2['name']} towards {ic3['name']}"},
                            {"from": ic4["name"], "to": dest_metro["name"], "mode": "metro", "line": dest_metro.get("line"), "distance_km": round(leg3, 2), "duration_minutes": round((leg3 / 35) * 60), "fare": round(mfare * 0.35, 2), "instructions": f"Switch to {dest_metro.get('line')} at {ic4['name']} to {dest_metro['name']}"},
                            {"from": dest_metro["name"], "to": "Your Destination", "mode": "walk", "distance_km": round(walking_from, 2), "duration_minutes": round(walking_from * 12), "fare": 0},
                        ]
                    })
                    break  # one double-interchange route is enough
        return routes

    def _generate_kia_routes(self, slat, slng, dlat, dlng, dist, group_size):
        routes = []
        if not db.kia_routes:
            return routes
        nearby_src_stops = db.find_nearby_bus_stops(slat, slng, 2.0)
        nearby_dest_stops = db.find_nearby_bus_stops(dlat, dlng, 2.0)
        if not nearby_src_stops or not nearby_dest_stops:
            return routes
        src_stop = nearby_src_stops[0]
        dest_stop = nearby_dest_stops[0]
        src_stop_name = src_stop["name"].lower()
        dest_stop_name = dest_stop["name"].lower()
        for route_id, route_data in db.kia_routes.items():
            stops = route_data.get("stops", [])
            src_idx = None
            dest_idx = None
            for i, s in enumerate(stops):
                sn = s["stop_name"].lower()
                if src_stop_name in sn or sn in src_stop_name:
                    src_idx = i
                if dest_stop_name in sn or sn in dest_stop_name:
                    dest_idx = i
            if src_idx is not None and dest_idx is not None and src_idx < dest_idx:
                src_s = stops[src_idx]
                dest_s = stops[dest_idx]
                kia_fare = dest_s.get("fare", 0) - src_s.get("fare", 0)
                if kia_fare <= 0 and dest_s.get("fare", 0) > 0:
                    kia_fare = dest_s.get("fare", 210)
                walking_to = 0
                walking_from = 0
                kia_dist = dist * 0.8
                routes.append({
                    "type": "kia_bus",
                    "total_fare": max(kia_fare, 50) * group_size,
                    "total_duration_minutes": round((kia_dist / 40) * 60 + (walking_to + walking_from) * 12),
                    "total_distance_km": round(kia_dist + walking_to + walking_from, 2),
                    "total_walking_km": round(walking_to + walking_from, 2),
                    "overall_score": 82,
                    "route_id": route_id,
                    "route_info": route_data.get("route_info", ""),
                    "legs": [
                        {"from": "Your Location", "to": src_s["stop_name"], "mode": "walk",
                         "distance_km": round(walking_to, 2), "duration_minutes": round(walking_to * 12), "fare": 0},
                        {"from": src_s["stop_name"], "to": dest_s["stop_name"], "mode": "bus_ac_vajra",
                         "distance_km": round(kia_dist, 2), "duration_minutes": round((kia_dist / 40) * 60),
                         "fare": max(kia_fare, 50) * group_size, "line": route_id, "instructions": f"Board {route_id}: {route_data.get('route_info', '')}"},
                        {"from": dest_s["stop_name"], "to": "Your Destination", "mode": "walk",
                         "distance_km": round(walking_from, 2), "duration_minutes": round(walking_from * 12), "fare": 0}
                    ]
                })
        return routes[:2]

    def _generate_multi_modal_routes(self, slat, slng, dlat, dlng, dist, group_size):
        routes = []
        bus_stops = db.find_nearby_bus_stops(slat, slng, 1.0)
        metro_stations = db.find_nearby_metro_stations(slat, slng, 3.0)
        dest_bus_stops = db.find_nearby_bus_stops(dlat, dlng, 1.0)
        dest_metro = db.find_nearby_metro_stations(dlat, dlng, 3.0)

        # Bus -> Metro
        if bus_stops and dest_metro:
            for src_bus in bus_stops[:2]:
                for dst_m in dest_metro[:2]:
                    walking_to_bus = self.haversine_distance(slat, slng, src_bus["lat"], src_bus["lng"])
                    metro_near_src = None
                    for m in metro_stations:
                        d = self.haversine_distance(src_bus["lat"], src_bus["lng"], m["lat"], m["lng"])
                        if d < 3.0:
                            metro_near_src = m
                            break

                    def _emit_bus_to_metro(via_name, bus_stop_dict, bus_d, metro_d, walk_m_c, w_from_m):
                        fr = walking_to_bus
                        bf = db.get_bmtc_ordinary_fare(bus_d)
                        mf = db.get_metro_fare(metro_d) * group_size
                        tw = fr + walk_m_c + w_from_m
                        td = (bus_d / 25) * 60 + (metro_d / 35) * 60 + tw * 12 + 5
                        bus_to_name = bus_stop_dict.get("name", "")
                        cr = self._get_bus_route_nums(src_bus, bus_stop_dict) or []
                        rs = ", ".join(cr[:2]) if cr else "Multiple"
                        routes.append({
                            "type": "bus_to_metro",
                            "total_fare": round(bf + mf, 2),
                            "total_duration_minutes": round(td),
                            "total_distance_km": round(bus_d + metro_d + tw, 2),
                            "total_walking_km": round(tw, 2),
                            "overall_score": max(60, min(99, 98 - round(bus_d + metro_d + walk_m_c))),
                            "legs": [
                                {"from": "Your Location", "to": src_bus["name"], "mode": "walk",
                                 "distance_km": round(fr, 2), "duration_minutes": round(fr * 12), "fare": 0},
                                {"from": src_bus["name"], "to": bus_to_name, "mode": "bus_ordinary",
                                 "distance_km": round(bus_d, 2), "duration_minutes": round(bus_d / 25 * 60),
                                 "fare": round(bf * group_size, 2), "route_numbers": cr,
                                 "instructions": f"Bus {rs} to {bus_to_name}"},
                            ]
                        })
                        if metro_d > 0.5:
                            routes[-1]["legs"].append(
                                {"from": via_name, "to": dst_m["name"], "mode": "metro", "line": dst_m.get("line"),
                                 "distance_km": round(metro_d, 2), "duration_minutes": round(metro_d / 35 * 60), "fare": mf}
                            )
                        else:
                            routes[-1]["legs"].append(
                                {"from": bus_to_name, "to": dst_m["name"], "mode": "walk",
                                 "distance_km": round(walk_m_c, 2), "duration_minutes": round(walk_m_c * 12), "fare": 0}
                            )
                        routes[-1]["legs"].append(
                            {"from": dst_m["name"], "to": "Your Destination", "mode": "walk",
                             "distance_km": round(w_from_m, 2), "duration_minutes": round(w_from_m * 12), "fare": 0}
                        )

                    walk_to_metro = 0.0
                    if metro_near_src:
                        # CASE 1: Metro station near source bus stop
                        bus_d = self.haversine_distance(src_bus["lat"], src_bus["lng"], metro_near_src["lat"], metro_near_src["lng"])
                        metro_d = db.get_metro_distance_between(metro_near_src["name"], dst_m["name"]) or self.haversine_distance(metro_near_src["lat"], metro_near_src["lng"], dst_m["lat"], dst_m["lng"])
                        w_from_m = self.haversine_distance(dlat, dlng, dst_m["lat"], dst_m["lng"])
                        _emit_bus_to_metro(metro_near_src["name"], metro_near_src, bus_d, metro_d, 0.0, w_from_m)
                    else:
                        # CASE 2: No metro near source — find TOP 3 bus→metro transfers
                        candidates = []
                        all_ms = getattr(db, "metro_stations", metro_stations)
                        src_to_dest = self.haversine_distance(src_bus["lat"], src_bus["lng"], dlat, dlng)
                        for m_test in all_ms:
                            ns = db.find_nearby_bus_stops(m_test["lat"], m_test["lng"], 0.5)
                            if not ns:
                                continue
                            ds = ns[0]
                            stop_to_dest = self.haversine_distance(ds["lat"], ds["lng"], dlat, dlng)
                            # Skip if bus goes away from destination (reverse direction)
                            if stop_to_dest > src_to_dest * 0.95:
                                continue
                            metro_d = db.get_metro_distance_between(m_test["name"], dst_m["name"]) or self.haversine_distance(m_test["lat"], m_test["lng"], dst_m["lat"], dst_m["lng"])
                            if metro_d < 0.5:
                                continue
                            bus_d = self.haversine_distance(src_bus["lat"], src_bus["lng"], ds["lat"], ds["lng"])
                            if bus_d < 0.5 or bus_d > dist:
                                continue
                            walk_m = self.haversine_distance(ds["lat"], ds["lng"], m_test["lat"], m_test["lng"])
                            # Skip if total detour exceeds 1.5x direct distance
                            if bus_d + metro_d + walk_m > dist * 1.5:
                                continue
                            score = bus_d + metro_d + walk_m
                            candidates.append((score, m_test, ds, bus_d, metro_d, walk_m))
                        candidates.sort(key=lambda x: x[0])
                        for score, m_test, ds, bus_d, metro_d, walk_m in candidates[:12]:
                            w_from_m = self.haversine_distance(dlat, dlng, dst_m["lat"], dst_m["lng"])
                            _emit_bus_to_metro(m_test["name"], ds, bus_d, metro_d, walk_m, w_from_m)

        # Metro -> Bus
        if metro_stations and dest_bus_stops:
            for src_m in metro_stations[:2]:
                for dst_bus in dest_bus_stops[:2]:
                    walking_to_metro = self.haversine_distance(slat, slng, src_m["lat"], src_m["lng"])
                    metro_near_dest = None
                    for m in dest_metro:
                        d = self.haversine_distance(dst_bus["lat"], dst_bus["lng"], m["lat"], m["lng"])
                        if d < 3.0:
                            metro_near_dest = m
                            break
                    if not metro_near_dest:
                        continue
                    metro_dist_via = db.get_metro_distance_between(src_m["name"], metro_near_dest["name"]) or dist * 0.5
                    metro_to_name = metro_near_dest["name"]
                    bus_from_metro = self.haversine_distance(src_m["lat"], src_m["lng"], dst_bus["lat"], dst_bus["lng"])
                    walking_from_bus = self.haversine_distance(dlat, dlng, dst_bus["lat"], dst_bus["lng"])
                    metro_fare = db.get_metro_fare(metro_dist_via)
                    bus_fare = db.get_bmtc_ordinary_fare(bus_from_metro)
                    total_walk = walking_to_metro + walking_from_bus
                    total_dur = (metro_dist_via / 35) * 60 + (bus_from_metro / 25) * 60 + total_walk * 12 + 5
                    metro_near_stops = db.find_nearby_bus_stops(src_m["lat"], src_m["lng"], 0.5) or []
                    bus_near_metro = metro_near_stops[0] if metro_near_stops else dst_bus
                    common_routes = self._get_bus_route_nums(bus_near_metro, dst_bus)
                    route_str = ", ".join(common_routes[:2]) if common_routes else "Multiple"
                    routes.append({
                        "type": "metro_to_bus",
                        "total_fare": round(metro_fare * group_size + bus_fare * group_size, 2),
                        "total_duration_minutes": round(total_dur),
                        "total_distance_km": round(metro_dist_via + bus_from_metro + total_walk, 2),
                        "total_walking_km": round(total_walk, 2),
                        "overall_score": 73,
                        "legs": [
                            {"from": "Your Location", "to": src_m["name"], "mode": "walk",
                             "distance_km": round(walking_to_metro, 2), "duration_minutes": round(walking_to_metro * 12), "fare": 0},
                            {"from": src_m["name"], "to": metro_to_name, "mode": "metro", "line": src_m.get("line"),
                             "distance_km": round(metro_dist_via, 2), "duration_minutes": round(metro_dist_via / 35 * 60), "fare": round(metro_fare * group_size, 2)},
                            {"from": metro_to_name, "to": dst_bus["name"], "mode": "bus_ordinary",
                             "distance_km": round(bus_from_metro, 2), "duration_minutes": round(bus_from_metro / 25 * 60),
                             "fare": round(bus_fare * group_size, 2), "route_numbers": common_routes,
                             "instructions": f"Bus {route_str} to {dst_bus['name']}"},
                            {"from": dst_bus["name"], "to": "Your Destination", "mode": "walk",
                             "distance_km": round(walking_from_bus, 2), "duration_minutes": round(walking_from_bus * 12), "fare": 0}
                        ]
                     })
        return routes[:3]

    def __init__(self):
        from backend.services.transit_paths import TransitPathService
        self._astar_graph_instance = None
        self.path_service = TransitPathService()
        self.segment_builder = TripSegmentBuilder(
            haversine_fn=self.haversine_distance,
            interpolate_path_fn=self._interpolate_path,
            path_service=self.path_service,
            get_bus_route_nums_fn=self._get_bus_route_nums,
            astar_graph_fn=lambda slat, slng, dlat, dlng, gs: self.astar_graph.find_enriched_routes(
                slat, slng, dlat, dlng, self.haversine_distance(slat, slng, dlat, dlng), gs
            ),
        )

    def get_all_segments(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size=1, budget=None, max_depth=3):
        return self.segment_builder.get_all_segments(
            from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name,
            group_size, budget, max_depth,
        )

    def get_segment_step_options(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size=1, budget=None):
        return self.segment_builder.get_segment_step_options(
            from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name,
            group_size, budget,
        )

    @property
    def astar_graph(self):
        if self._astar_graph_instance is None:
            from backend.services.transit_graph import TransitAstarGraph
            g = TransitAstarGraph()
            g.build_graph()
            self._astar_graph_instance = g
        return self._astar_graph_instance

    def _interpolate_path(self, slat, slng, dlat, dlng, num_points=12):
        return self.path_service.interpolate_path(slat, slng, dlat, dlng, num_points)

    async def get_osrm_path_between(self, slat, slng, dlat, dlng, profile="driving"):
        return await self.path_service.get_osrm_path_between(slat, slng, dlat, dlng, profile)

    async def _add_leg_paths(self, route: dict):
        await self.path_service.add_leg_paths(route)

    async def get_osrm_route(self, slat, slng, dlat, dlng):
        return await self.path_service.get_osrm_route(slat, slng, dlat, dlng)

    async def get_driving_route(self, slat, slng, dlat, dlng):
        return await self.path_service.get_driving_route(slat, slng, dlat, dlng)

transit_service = TransitService()
