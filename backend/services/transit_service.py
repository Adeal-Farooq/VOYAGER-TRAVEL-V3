import httpx, asyncio, math
from geopy.distance import geodesic
from backend.core.config import settings
from backend.core.database import db

_gtfs = None
def _ensure_gtfs():
    global _gtfs
    if _gtfs is None:
        from backend.services.gtfs_service import gtfs_loader
        gtfs_loader.load()
        _gtfs = gtfs_loader
    return _gtfs

# Common train routes across Karnataka (major pairs with real train data)
# Format: (from_normalized, to_normalized) -> [(number, name, departure, arrival), ...]
_TRAIN_DATA = {
    ("bengaluru", "mysuru"): [
        ("16517", "KSR Bengaluru - Mysuru Kannada Express", "06:45", "09:25"),
        ("12613", "Shatabdi Express", "11:00", "13:00"),
        ("12007", "Shatabdi Express", "14:00", "16:00"),
        ("16535", "Gol Gumbaz Express", "07:45", "10:25"),
        ("16232", "Mysuru Express", "12:30", "15:10"),
    ],
    ("mysuru", "bengaluru"): [
        ("16518", "Mysuru - KSR Bengaluru Kannada Express", "06:00", "08:40"),
        ("12614", "Shatabdi Express", "14:30", "16:30"),
        ("12008", "Shatabdi Express", "06:30", "08:30"),
        ("16536", "Gol Gumbaz Express", "16:00", "18:40"),
        ("16231", "Mysuru Express", "05:30", "08:10"),
    ],
    ("bengaluru", "hubballi"): [
        ("17325", "Vishwamanava Express", "15:00", "22:30"),
        ("16589", "Rani Chennamma Express", "22:00", "06:30"),
    ],
    ("hubballi", "bengaluru"): [
        ("17326", "Vishwamanava Express", "06:00", "13:30"),
        ("16590", "Rani Chennamma Express", "20:00", "04:30"),
    ],
    ("bengaluru", "mangaluru"): [
        ("16511", "KSR Bengaluru - Kannur Express", "23:30", "09:45"),
        ("16585", "Mokashi Express", "22:15", "08:30"),
    ],
    ("mangaluru", "bengaluru"): [
        ("16512", "Kannur - KSR Bengaluru Express", "17:00", "03:15"),
        ("16586", "Mokashi Express", "19:00", "05:15"),
    ],
    ("bengaluru", "belagavi"): [
        ("17309", "Basava Express", "22:00", "08:30"),
    ],
    ("belagavi", "bengaluru"): [
        ("17310", "Basava Express", "19:00", "05:30"),
    ],
    ("bengaluru", "ballari"): [
        ("16545", "KSR Bengaluru - Ballari Express", "22:30", "06:30"),
    ],
    ("ballari", "bengaluru"): [
        ("16546", "Ballari - KSR Bengaluru Express", "23:00", "07:00"),
    ],
}

def _get_train_options(src_name: str, dst_name: str) -> list:
    """Return train options between two railway stations.
    Returns list of (train_number, name, departure, arrival) for known routes.
    For unknown pairs, generates a reasonable generic option."""
    src_lower = src_name.lower().replace("railway station", "").replace("junction", "").strip()
    dst_lower = dst_name.lower().replace("railway station", "").replace("junction", "").strip()

    # Normalize common names
    name_map = {
        "ksr bengaluru": "bengaluru", "bengaluru": "bengaluru",
        "bengaluru city": "bengaluru", "ksr bangalore": "bengaluru",
        "bengaluru cantonment": "bengaluru", "bengaluru cant": "bengaluru",
        "yasvantpur": "bengaluru", "yesvantpur": "bengaluru", "yashwantpura": "bengaluru",
        "krishnarajapuram": "bengaluru", "whitefield": "bengaluru",
        "mysuru": "mysuru", "mysore": "mysuru", "mysuru junction": "mysuru",
        "hubballi": "hubballi", "hubli": "hubballi", "hubballi junction": "hubballi",
        "mangaluru": "mangaluru", "mangalore": "mangaluru",
        "mangaluru junction": "mangaluru", "mangaluru central": "mangaluru",
        "belagavi": "belagavi", "belgaum": "belagavi",
        "ballari": "ballari", "bellary": "ballari",
        "kalaburagi": "kalaburagi", "gulbarga": "kalaburagi", "kalaburagi junction": "kalaburagi",
        "vijayapura": "vijayapura", "bijapur": "vijayapura",
        "hosapete": "hosapete", "hospet": "hosapete", "hosapete junction": "hosapete",
        "shivamogga": "shivamogga", "shimoga": "shivamogga",
    }

    words = src_lower.split()
    sk = name_map.get(src_lower) or (name_map.get(" ".join(words[:2])) if len(words) >= 2 else None) or name_map.get(words[0], src_lower) if words else src_lower
    words = dst_lower.split()
    dk = name_map.get(dst_lower) or (name_map.get(" ".join(words[:2])) if len(words) >= 2 else None) or name_map.get(words[0], dst_lower) if words else dst_lower

    # Check known routes
    key = (sk, dk)
    key_rev = (dk, sk)
    known = _TRAIN_DATA.get(key, _TRAIN_DATA.get(key_rev, []))
    if known:
        return known

    # For any unknown pair, generate a generic option based on distance
    try:
        from geopy.distance import geodesic
        # Get coordinates from the railway stations list
        stations_data = None
        try:
            from backend.core.database import db
            stations_data = getattr(db, 'railway_stations', None)
        except Exception:
            pass
        if not stations_data:
            try:
                import os, json
                from backend.core.config import settings
                path = os.path.join(settings.DATA_CACHE_DIR, "karnataka_railway_stations.json")
                stations_data = json.load(open(path))
            except Exception:
                pass
        src_coords = dst_coords = None
        if stations_data:
            for s in stations_data:
                sn = s.get("name", "").lower()
                if src_name.lower() in sn:
                    src_coords = (s["lat"], s["lng"])
                if dst_name.lower() in sn:
                    dst_coords = (s["lat"], s["lng"])
        if src_coords and dst_coords:
            dist = geodesic(src_coords, dst_coords).km
            if dist > 20:
                dur_hours = max(1, round(dist / 50))
                dep_hour = (6 + abs(hash(sk + dk)) % 10) % 24
                arr_hour = (dep_hour + dur_hours) % 24
                gen_number = f"1{1000 + abs(hash(sk + dk)) % 9000:04d}"
                gen_name = f"Intercity Express ({src_name.split()[0]} - {dst_name.split()[0]})"
                return [(gen_number, gen_name, f"{dep_hour:02d}:00", f"{arr_hour:02d}:00")]
    except Exception:
        pass
    return []

def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return default
    return val

class TransitService:

    def haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        try:
            d = geodesic((lat1, lng1), (lat2, lng2)).km
            return _safe(d, 0.0)
        except:
            return 0.0

    def _find_common_routes(self, src_stop: dict, dest_stop: dict) -> list:
        src_routes = set(src_stop.get("routes", []))
        dest_routes = set(dest_stop.get("routes", []))
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
                               budget: float = None, group_size: int = 1) -> list:
        direct_dist = self.haversine_distance(source_lat, source_lng, dest_lat, dest_lng)

        possible_routes = []
        possible_routes.extend(self._generate_bus_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
        possible_routes.extend(self._generate_metro_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
        possible_routes.extend(self._generate_metro_interchange_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
        possible_routes.extend(self._generate_kia_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))
        possible_routes.extend(self._generate_multi_modal_routes(source_lat, source_lng, dest_lat, dest_lng, direct_dist, group_size))

        if budget:
            possible_routes = [r for r in possible_routes if r["total_fare"] <= budget]

        for r in possible_routes:
            score, expl = self._topsis_score(r, budget, group_size)
            r["overall_score"] = score
            r["score_explanation"] = expl
            self._add_leg_coords(r, source_lat, source_lng, dest_lat, dest_lng)

        possible_routes.sort(key=lambda x: (x["overall_score"], -x.get("total_fare", 999)), reverse=True)
        return possible_routes[:8]

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
                "total_duration_minutes": (bus_dist / 25) * 60 + total_walk * 12,
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
                "total_duration_minutes": (bus_dist / 30) * 60 + total_walk * 12,
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
        nearby_src = db.find_nearby_metro_stations(slat, slng, 2.0)
        nearby_dest = db.find_nearby_metro_stations(dlat, dlng, 2.0)

        if nearby_src and nearby_dest:
            src_metro = nearby_src[0]
            dest_metro = nearby_dest[0]
            walking_to = self.haversine_distance(slat, slng, src_metro["lat"], src_metro["lng"])
            walking_from = self.haversine_distance(dlat, dlng, dest_metro["lat"], dest_metro["lng"])
            metro_dist = self.haversine_distance(src_metro["lat"], src_metro["lng"], dest_metro["lat"], dest_metro["lng"])
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
        nearby_src = db.find_nearby_metro_stations(slat, slng, 2.0)
        nearby_dest = db.find_nearby_metro_stations(dlat, dlng, 2.0)

        if not nearby_src or not nearby_dest:
            return routes

        src_metro = nearby_src[0]
        dest_metro = nearby_dest[0]

        if src_metro.get("line") == dest_metro.get("line"):
            return routes

        interchanges = [s for s in db.metro_stations if s.get("is_interchange") and s.get("line") in (src_metro.get("line"), dest_metro.get("line"))]
        if not interchanges:
            return routes

        for ic in interchanges:
            if ic.get("line") != src_metro.get("line"):
                continue
            walking_to = self.haversine_distance(slat, slng, src_metro["lat"], src_metro["lng"])
            leg1_dist = db.get_metro_distance_between(src_metro["name"], ic["name"]) or self.haversine_distance(src_metro["lat"], src_metro["lng"], ic["lat"], ic["lng"])
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
                    {
                        "from": "Your Location", "to": src_metro["name"],
                        "mode": "walk",
                        "distance_km": round(walking_to, 2),
                        "duration_minutes": round(walking_to * 12),
                        "fare": 0
                    },
                    {
                        "from": src_metro["name"], "to": ic["name"],
                        "mode": "metro",
                        "line": src_metro.get("line"),
                        "distance_km": round(leg1_dist, 2),
                        "duration_minutes": round((leg1_dist / 35) * 60),
                        "fare": round(metro_fare * 0.5, 2),
                        "instructions": f"Take {src_metro.get('line')} from {src_metro['name']} to {ic['name']} (interchange)"
                    },
                    {
                        "from": ic["name"], "to": dest_metro["name"],
                        "mode": "metro",
                        "line": dest_metro.get("line"),
                        "distance_km": round(leg2_dist, 2),
                        "duration_minutes": round((leg2_dist / 35) * 60),
                        "fare": round(metro_fare * 0.5, 2),
                        "instructions": f"Switch to {dest_metro.get('line')} at {ic['name']} to {dest_metro['name']}"
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
        return routes[:2]

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
        metro_stations = db.find_nearby_metro_stations(slat, slng, 2.0)
        dest_bus_stops = db.find_nearby_bus_stops(dlat, dlng, 1.0)
        dest_metro = db.find_nearby_metro_stations(dlat, dlng, 2.0)

        # Bus -> Metro
        if bus_stops and dest_metro:
            for src_bus in bus_stops[:2]:
                for dst_m in dest_metro[:2]:
                    walking_to_bus = self.haversine_distance(slat, slng, src_bus["lat"], src_bus["lng"])
                    bus_dist = self.haversine_distance(src_bus["lat"], src_bus["lng"], dst_m["lat"], dst_m["lng"])
                    metro_near_src = None
                    for m in metro_stations:
                        d = self.haversine_distance(src_bus["lat"], src_bus["lng"], m["lat"], m["lng"])
                        if d < 2.0:
                            metro_near_src = m
                            break
                    if metro_near_src:
                        metro_dist_via = db.get_metro_distance_between(metro_near_src["name"], dst_m["name"]) or bus_dist * 0.7
                        metro_from_name = metro_near_src["name"]
                    else:
                        metro_dist_via = bus_dist * 0.7
                        metro_from_name = dst_m["name"]
                    walking_from_metro = self.haversine_distance(dlat, dlng, dst_m["lat"], dst_m["lng"])
                    bus_fare = db.get_bmtc_ordinary_fare(bus_dist)
                    metro_fare = db.get_metro_fare(metro_dist_via) * group_size
                    total_walk = walking_to_bus + walking_from_metro
                    total_dur = (bus_dist / 25) * 60 + (metro_dist_via / 35) * 60 + total_walk * 12 + 5
                    common_routes = self._get_bus_route_nums(src_bus, dst_m) if not metro_near_src else self._get_bus_route_nums(src_bus, {})
                    route_str = ", ".join(common_routes[:2]) if common_routes else "Multiple"
                    routes.append({
                        "type": "bus_to_metro",
                        "total_fare": round(bus_fare + metro_fare, 2),
                        "total_duration_minutes": round(total_dur),
                        "total_distance_km": round(bus_dist + metro_dist_via + total_walk, 2),
                        "total_walking_km": round(total_walk, 2),
                        "overall_score": 75,
                        "legs": [
                            {"from": "Your Location", "to": src_bus["name"], "mode": "walk",
                             "distance_km": round(walking_to_bus, 2), "duration_minutes": round(walking_to_bus * 12), "fare": 0},
                            {"from": src_bus["name"], "to": dst_m["name"], "mode": "bus_ordinary",
                             "distance_km": round(bus_dist, 2), "duration_minutes": round(bus_dist / 25 * 60),
                             "fare": round(bus_fare * group_size, 2), "route_numbers": common_routes,
                             "instructions": f"Bus {route_str} to {dst_m['name']}"},
                            {"from": metro_from_name, "to": dst_m["name"], "mode": "metro", "line": dst_m.get("line"),
                             "distance_km": round(metro_dist_via, 2), "duration_minutes": round(metro_dist_via / 35 * 60), "fare": metro_fare},
                            {"from": dst_m["name"], "to": "Your Destination", "mode": "walk",
                             "distance_km": round(walking_from_metro, 2), "duration_minutes": round(walking_from_metro * 12), "fare": 0}
                        ]
                    })

        # Metro -> Bus
        if metro_stations and dest_bus_stops:
            for src_m in metro_stations[:2]:
                for dst_bus in dest_bus_stops[:2]:
                    walking_to_metro = self.haversine_distance(slat, slng, src_m["lat"], src_m["lng"])
                    metro_near_dest = None
                    for m in dest_metro:
                        d = self.haversine_distance(dst_bus["lat"], dst_bus["lng"], m["lat"], m["lng"])
                        if d < 2.0:
                            metro_near_dest = m
                            break
                    if metro_near_dest:
                        metro_dist_via = db.get_metro_distance_between(src_m["name"], metro_near_dest["name"]) or dist * 0.5
                        metro_to_name = metro_near_dest["name"]
                    else:
                        metro_dist_via = dist * 0.5
                        metro_to_name = src_m["name"]
                    bus_from_metro = self.haversine_distance(src_m["lat"], src_m["lng"], dst_bus["lat"], dst_bus["lng"])
                    walking_from_bus = self.haversine_distance(dlat, dlng, dst_bus["lat"], dst_bus["lng"])
                    metro_fare = db.get_metro_fare(abs(src_m.get("sequence", 0) - dst_bus.get("sequence", 0)) * 1.5) if metro_stations else db.get_metro_fare(dist)
                    if metro_fare < 11:
                        metro_fare = db.get_metro_fare(dist * 0.6)
                    bus_fare = db.get_bmtc_ordinary_fare(bus_from_metro)
                    total_walk = walking_to_metro + walking_from_bus
                    total_dur = (metro_dist_via / 35) * 60 + (bus_from_metro / 25) * 60 + total_walk * 12 + 5
                    common_routes = self._get_bus_route_nums(dst_bus, {})
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
                            {"from": src_m["name"], "to": dst_bus["name"], "mode": "bus_ordinary",
                             "distance_km": round(bus_from_metro, 2), "duration_minutes": round(bus_from_metro / 25 * 60),
                             "fare": round(bus_fare * group_size, 2), "route_numbers": common_routes,
                             "instructions": f"Bus {route_str} to {dst_bus['name']}"},
                            {"from": dst_bus["name"], "to": "Your Destination", "mode": "walk",
                             "distance_km": round(walking_from_bus, 2), "duration_minutes": round(walking_from_bus * 12), "fare": 0}
                        ]
                    })
        return routes[:3]

    def get_mini_path_options(self, source_lat: float, source_lng: float,
                               dest_lat: float, dest_lng: float,
                               group_size: int = 1) -> dict:
        direct_dist = _safe(self.haversine_distance(source_lat, source_lng, dest_lat, dest_lng))
        nearby_bus = db.find_nearby_bus_stops(source_lat, source_lng, 1.0) or []
        nearby_metro = db.find_nearby_metro_stations(source_lat, source_lng, 2.0) or []

        walking_options = []
        if 0 < direct_dist <= 5:
            walk_time = direct_dist * 12
            walking_options.append({
                "mode": "walk",
                "from": "Your Location",
                "to": "Destination",
                "distance_km": round(_safe(direct_dist), 2),
                "duration_minutes": round(_safe(walk_time)),
                "fare": 0,
                "instructions": f"Walk {direct_dist:.1f}km to destination",
                "from_lat": source_lat, "from_lng": source_lng,
                "to_lat": dest_lat, "to_lng": dest_lng,
            })

        bus_options = []
        for stop in nearby_bus[:3]:
            dist = _safe(self.haversine_distance(source_lat, source_lng, stop["lat"], stop["lng"]))
            stop_name = stop.get("name", "Bus Stop")
            bus_options.append({
                "mode": "walk_to_bus",
                "from": "Your Location",
                "to": stop_name,
                "distance_km": round(dist, 2),
                "duration_minutes": round(dist * 12),
                "fare": 0,
                "stop_name": stop_name,
                "stop_lat": _safe(stop.get("lat")),
                "stop_lng": _safe(stop.get("lng")),
                "from_lat": source_lat, "from_lng": source_lng,
                "to_lat": _safe(stop.get("lat")), "to_lng": _safe(stop.get("lng")),
            })

        metro_options = []
        for station in nearby_metro[:3]:
            dist = _safe(self.haversine_distance(source_lat, source_lng, station["lat"], station["lng"]))
            station_name = station.get("name", "Metro Station")
            metro_options.append({
                "mode": "walk_to_metro",
                "from": "Your Location",
                "to": station_name,
                "distance_km": round(dist, 2),
                "duration_minutes": round(dist * 12),
                "fare": 0,
                "station_name": station_name,
                "station_lat": _safe(station.get("lat")),
                "station_lng": _safe(station.get("lng")),
                "from_lat": source_lat, "from_lng": source_lng,
                "to_lat": _safe(station.get("lat")), "to_lng": _safe(station.get("lng")),
            })

        dest_bus = db.find_nearby_bus_stops(dest_lat, dest_lng, 1.0) or []
        dest_metro = db.find_nearby_metro_stations(dest_lat, dest_lng, 2.0) or []

        dest_bus_options = []
        for stop in dest_bus[:3]:
            dist = _safe(self.haversine_distance(dest_lat, dest_lng, stop["lat"], stop["lng"]))
            stop_name = stop.get("name", "Bus Stop")
            dest_bus_options.append({
                "mode": "walk_from_bus",
                "from": stop_name,
                "to": "Destination",
                "distance_km": round(dist, 2),
                "duration_minutes": round(dist * 12),
                "fare": 0,
                "stop_name": stop_name,
                "stop_lat": _safe(stop.get("lat")),
                "stop_lng": _safe(stop.get("lng")),
                "from_lat": _safe(stop.get("lat")), "from_lng": _safe(stop.get("lng")),
                "to_lat": dest_lat, "to_lng": dest_lng,
            })

        dest_metro_options = []
        for station in dest_metro[:3]:
            dist = _safe(self.haversine_distance(dest_lat, dest_lng, station["lat"], station["lng"]))
            station_name = station.get("name", "Metro Station")
            dest_metro_options.append({
                "mode": "walk_from_metro",
                "from": station_name,
                "to": "Destination",
                "distance_km": round(dist, 2),
                "duration_minutes": round(dist * 12),
                "fare": 0,
                "station_name": station_name,
                "station_lat": _safe(station.get("lat")),
                "station_lng": _safe(station.get("lng")),
                "from_lat": _safe(station.get("lat")), "from_lng": _safe(station.get("lng")),
                "to_lat": dest_lat, "to_lng": dest_lng,
            })

        # Transit ride options (bus/metro between nearby stops)
        transit_ride_options = {"bus": [], "metro": []}
        for src_stop in nearby_bus[:2]:
            for dst_stop in dest_bus[:2]:
                transit_dist = _safe(self.haversine_distance(src_stop["lat"], src_stop["lng"], dst_stop["lat"], dst_stop["lng"]))
                if transit_dist < 0.5:
                    continue
                bus_fare_pp = db.get_bmtc_ordinary_fare(transit_dist) or 10
                bus_fare_pp = max(10, round(bus_fare_pp))
                transit_ride_options["bus"].append({
                    "mode": "bus",
                    "from": src_stop.get("name", "Bus Stop"),
                    "to": dst_stop.get("name", "Bus Stop"),
                    "distance_km": round(_safe(transit_dist), 2),
                    "duration_minutes": round(transit_dist * 4),
                    "fare": bus_fare_pp * group_size,
                    "per_person": bus_fare_pp,
                    "from_lat": _safe(src_stop.get("lat")), "from_lng": _safe(src_stop.get("lng")),
                    "to_lat": _safe(dst_stop.get("lat")), "to_lng": _safe(dst_stop.get("lng")),
                    "instructions": f"Bus ~₹{bus_fare_pp * group_size} (₹{bus_fare_pp}/person)",
                })
        for src_station in nearby_metro[:2]:
            for dst_station in dest_metro[:2]:
                transit_dist = _safe(self.haversine_distance(src_station["lat"], src_station["lng"], dst_station["lat"], dst_station["lng"]))
                if transit_dist < 0.5:
                    continue
                metro_fare_pp = round(db.get_metro_fare(transit_dist) or 15)
                transit_ride_options["metro"].append({
                    "mode": "metro",
                    "from": src_station.get("name", "Metro Station"),
                    "to": dst_station.get("name", "Metro Station"),
                    "distance_km": round(_safe(transit_dist), 2),
                    "duration_minutes": round(transit_dist * 2),
                    "fare": metro_fare_pp * group_size,
                    "per_person": metro_fare_pp,
                    "from_lat": _safe(src_station.get("lat")), "from_lng": _safe(src_station.get("lng")),
                    "to_lat": _safe(dst_station.get("lat")), "to_lng": _safe(dst_station.get("lng")),
                    "instructions": f"Metro ~₹{metro_fare_pp * group_size} (₹{metro_fare_pp}/person)",
                })

        # Add direct ride options (filtered by group capacity)
        ride_options = []
        ride_types = [
            ("cab", "Uber Go / Ola Mini", 14, 3, 25, "🚕", 4),
            ("cab_xl", "Uber XL / Ola XL", 20, 3, 40, "🚐", 6),
            ("auto", "Auto", 10, 5, 15, "🛺", 3),
            ("bike", "Uber Moto / Rapido", 6, 2, 10, "🏍️", 1),
            ("cab_women", "Uber for Women / Ola for Women", 14, 3, 25, "👩", 4),
            ("cab_pet", "Uber Pet", 17, 3, 30, "🐾", 4),
        ]
        for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity in ride_types:
            if group_size > capacity:
                continue
            pp = round(base_fare + direct_dist * per_km_rate)
            total = pp * group_size
            ride_options.append({
                "mode": mode,
                "label": label,
                "icon": icon,
                "from": "Your Location", "to": "Destination",
                "distance_km": round(_safe(direct_dist), 2),
                "duration_minutes": round(direct_dist * time_per_km),
                "fare": total,
                "per_person": pp,
                "group_capacity": capacity,
                "instructions": f"{label} ~₹{total} (₹{pp}/person, seats {capacity})",
                "from_lat": source_lat, "from_lng": source_lng,
                "to_lat": dest_lat, "to_lng": dest_lng,
            })



        return {
            "source_walk_options": walking_options,
            "direct_ride_options": ride_options,
            "source_to_transit": {"bus": bus_options, "metro": metro_options},
            "transit_ride_options": transit_ride_options,
            "transit_to_dest": {"bus": dest_bus_options, "metro": dest_metro_options},
            "direct_distance_km": round(_safe(direct_dist), 2),
            "source_lat": source_lat, "source_lng": source_lng,
            "dest_lat": dest_lat, "dest_lng": dest_lng,
        }

    def _is_outside_bengaluru(self, lat: float, lng: float, threshold_km: float = 35.0) -> bool:
        center = (12.9716, 77.5946)
        dist = self.haversine_distance(center[0], center[1], lat, lng)
        return dist > threshold_km

    def _find_farthest_bus_stop_toward_dest(self, from_lat: float, from_lng: float,
                                             dest_lat: float, dest_lng: float) -> dict | None:
        stops = list(db.bus_stops.values())
        if not stops:
            return None
        dest_dist = {}
        for s in stops:
            d = self.haversine_distance(s["lat"], s["lng"], dest_lat, dest_lng)
            dest_dist[s["stop_id"]] = d
        sorted_stops = sorted(stops, key=lambda s: dest_dist.get(s["stop_id"], 999))
        top3 = sorted_stops[:3]
        farthest_from_center = None
        max_center_dist = 0
        center = (12.9716, 77.5946)
        for s in top3:
            cd = self.haversine_distance(center[0], center[1], s["lat"], s["lng"])
            if cd > max_center_dist:
                max_center_dist = cd
                farthest_from_center = s
        return farthest_from_center

    def get_segment_step_options(self, from_lat: float, from_lng: float, from_name: str,
                                  dest_lat: float, dest_lng: float, dest_name: str,
                                  group_size: int = 1, budget: float = None) -> dict:
        from_dist = _safe(self.haversine_distance(from_lat, from_lng, dest_lat, dest_lng))

        direct_options = []
        via_stops = {}
        ride_types = [
            ("cab", "Uber Go / Ola Mini", 14, 3, 25, "🚕", 4),
            ("cab_xl", "Uber XL / Ola XL", 20, 3, 40, "🚐", 6),
            ("auto", "Auto", 10, 5, 15, "🛺", 3),
            ("bike", "Uber Moto / Rapido", 6, 2, 10, "🏍️", 1),
            ("cab_women", "Uber for Women / Ola for Women", 14, 3, 25, "👩", 4),
            ("cab_pet", "Uber Pet", 17, 3, 30, "🐾", 4),
        ]

        def _add_via_stop(slat, slng, sname, stype):
            key = (round(slat, 4), round(slng, 4))
            if key not in via_stops:
                via_stops[key] = {
                    "stop": {"name": sname, "lat": slat, "lng": slng, "type": stype},
                    "from_stop_options": [],
                }
            return via_stops[key]

        # 1. Ride options (cab/auto/bike) — direct door-to-door to destination
        for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity in ride_types:
            if group_size > capacity:
                continue
            pp = round(base_fare + from_dist * per_km_rate)
            total = pp * group_size
            if budget and total > budget:
                continue
            direct_options.append({
                "mode": mode, "label": label, "icon": icon,
                "from": from_name, "to": dest_name,
                "distance_km": round(from_dist, 2),
                "duration_minutes": round(from_dist * time_per_km),
                "fare": total, "per_person": pp, "group_capacity": capacity,
                "from_lat": from_lat, "from_lng": from_lng,
                "to_lat": dest_lat, "to_lng": dest_lng,
                "path": self._interpolate_path(from_lat, from_lng, dest_lat, dest_lng, 6),
            })

        nearby_bus = db.find_nearby_bus_stops(from_lat, from_lng, 1.0) or []
        dest_bus = db.find_nearby_bus_stops(dest_lat, dest_lng, 1.0) or []

        # 3. Out-of-Bengaluru: bus then cab
        if self._is_outside_bengaluru(dest_lat, dest_lng) and nearby_bus:
            farthest_stop = self._find_farthest_bus_stop_toward_dest(from_lat, from_lng, dest_lat, dest_lng)
            if farthest_stop:
                bus_to_stop = _safe(self.haversine_distance(from_lat, from_lng, farthest_stop["lat"], farthest_stop["lng"]))
                stop_to_dest = _safe(self.haversine_distance(farthest_stop["lat"], farthest_stop["lng"], dest_lat, dest_lng))
                bus_fare_pp = round(db.get_bmtc_ordinary_fare(bus_to_stop) or 6)
                bus_total = bus_fare_pp * group_size
                cab_fare_pp = round(25 + stop_to_dest * 14)
                cab_total = cab_fare_pp * group_size
                common_routes = []
                for bs in nearby_bus[:5]:
                    cr = self._get_bus_route_nums(bs, farthest_stop)
                    if cr:
                        common_routes = cr
                        break
                if not common_routes:
                    common_routes = farthest_stop.get("routes", [])[:3]
                direct_options.append({
                    "mode": "bus_ordinary", "label": f"Bus+Cab to {dest_name}", "icon": "🚌",
                    "route_numbers": common_routes[:3],
                    "from": from_name, "to": dest_name,
                    "distance_km": round(bus_to_stop + stop_to_dest, 2),
                    "duration_minutes": round(bus_to_stop * 4 + stop_to_dest * 3),
                    "fare": bus_total + cab_total, "per_person": bus_fare_pp + cab_fare_pp,
                    "from_lat": from_lat, "from_lng": from_lng,
                    "to_lat": dest_lat, "to_lng": dest_lng,
                    "arrives_at_stop": False,
                    "sub_legs": [
                        {"mode": "bus_ordinary", "routes": common_routes[:3], "from": from_name, "to": farthest_stop["name"], "distance_km": round(bus_to_stop, 2), "fare": bus_fare_pp},
                        {"mode": "cab", "from": farthest_stop["name"], "to": dest_name, "distance_km": round(stop_to_dest, 2), "fare": cab_fare_pp},
                    ],
                })

        # 4. Bus routes — combined walk-to-stop + bus-ride (first-class options from origin)
        for stop in nearby_bus[:4]:
            stop_name = stop.get("name", "Bus Stop")
            walk_dist = _safe(self.haversine_distance(from_lat, from_lng, stop["lat"], stop["lng"]))
            if not dest_bus:
                continue
            for ds in dest_bus[:2]:
                transit_dist = _safe(self.haversine_distance(stop["lat"], stop["lng"], ds["lat"], ds["lng"]))
                if transit_dist < 0.5:
                    continue
                common_routes = self._get_bus_route_nums(stop, ds)
                if not common_routes:
                    continue
                ds_name = ds.get("name", "Bus Stop")
                all_bus_timings = _ensure_gtfs().get_next_buses(stop.get("name", ""), 20)
                for route_num in common_routes[:5]:
                    bus_fare_pp = round(db.get_bmtc_ordinary_fare(transit_dist) or 6)
                    bus_total = bus_fare_pp * group_size
                    if budget and bus_total > budget:
                        continue
                    route_times = [bt for bt in all_bus_timings if route_num in bt.get("route", "")] if all_bus_timings else []
                    if not route_times:
                        continue
                    total_dist = walk_dist + transit_dist
                    direct_options.append({
                        "mode": "bus_ordinary", "label": f"Bus {route_num} via {stop_name}", "icon": "🚌",
                        "route_number": route_num,
                        "from": from_name, "to": ds_name,
                        "distance_km": round(total_dist, 2),
                        "duration_minutes": round(walk_dist * 12 + transit_dist * 4),
                        "fare": bus_total, "per_person": bus_fare_pp,
                        "from_lat": from_lat, "from_lng": from_lng,
                        "to_lat": _safe(ds.get("lat")), "to_lng": _safe(ds.get("lng")),
                        "arrives_at_stop": True,
                        "bus_times": route_times[:5],
                        "sub_legs": [
                            {"mode": "walk", "from": from_name, "to": stop_name, "distance_km": round(walk_dist, 2), "duration_minutes": round(walk_dist * 12)},
                            {"mode": "bus_ordinary", "route": route_num, "from": stop_name, "to": ds_name, "distance_km": round(transit_dist, 2), "duration_minutes": round(transit_dist * 4), "fare": bus_fare_pp},
                        ],
                    })
                    vs = _add_via_stop(ds["lat"], ds["lng"], ds_name, "bus")
                    stop_to_dest = _safe(self.haversine_distance(ds["lat"], ds["lng"], dest_lat, dest_lng))
                    if stop_to_dest <= 2:
                        vs["from_stop_options"].append({
                            "mode": "walk", "label": "Walk to Destination", "icon": "🚶",
                            "from": ds_name, "to": dest_name,
                            "distance_km": round(stop_to_dest, 2),
                            "duration_minutes": round(stop_to_dest * 12),
                            "fare": 0, "per_person": 0,
                            "from_lat": _safe(ds.get("lat")), "from_lng": _safe(ds.get("lng")),
                            "to_lat": dest_lat, "to_lng": dest_lng,
                            "arrives_at_stop": False,
                        })
                    via_ride_opts = [r for r in ride_types if r[6] >= group_size]
                    for m, lb, pk, tp, bf, ic, cap in via_ride_opts:
                        pp = round(bf + stop_to_dest * pk)
                        total = pp * group_size
                        if budget and total > budget:
                            continue
                        vs["from_stop_options"].append({
                            "mode": m, "label": f"{lb} to Destination", "icon": ic,
                            "from": ds_name, "to": dest_name,
                            "distance_km": round(stop_to_dest, 2),
                            "duration_minutes": round(stop_to_dest * tp),
                            "fare": total, "per_person": pp,
                            "from_lat": _safe(ds.get("lat")), "from_lng": _safe(ds.get("lng")),
                            "to_lat": dest_lat, "to_lng": dest_lng,
                            "arrives_at_stop": False,
                        })
                    # AC variant
                    ac_fare_pp = round(db.get_bmtc_ac_fare(transit_dist) or 10)
                    ac_total = ac_fare_pp * group_size
                    if not budget or ac_total <= budget:
                        direct_options.append({
                            "mode": "bus_ac_vajra", "label": f"Bus {route_num} AC via {stop_name}", "icon": "🚌",
                            "route_number": route_num,
                            "from": from_name, "to": ds_name,
                            "distance_km": round(total_dist, 2),
                            "duration_minutes": round(walk_dist * 12 + transit_dist * 3.5),
                            "fare": ac_total, "per_person": ac_fare_pp,
                            "from_lat": from_lat, "from_lng": from_lng,
                            "to_lat": _safe(ds.get("lat")), "to_lng": _safe(ds.get("lng")),
                            "arrives_at_stop": True,
                            "bus_times": route_times[:5],
                            "sub_legs": [
                                {"mode": "walk", "from": from_name, "to": stop_name, "distance_km": round(walk_dist, 2)},
                                {"mode": "bus_ac_vajra", "route": route_num, "from": stop_name, "to": ds_name, "distance_km": round(transit_dist, 2), "fare": ac_fare_pp},
                            ],
                        })

        # Walk to destination from bus stop (already handled in from_stop_options within bus options above)

        # Sort: rides first, then buses by fare
        direct_options.sort(key=lambda o: (
            0 if o["mode"] in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else
            1 if o["mode"].startswith("bus_") else 2,
            o.get("fare", 0)
        ))

        for opt in direct_options:
            if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                opt["path"] = self._interpolate_path(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)

        return {
            "from": {"lat": from_lat, "lng": from_lng, "name": from_name},
            "dest": {"lat": dest_lat, "lng": dest_lng, "name": dest_name},
            "direct_options": direct_options,
            "via_stops": list(via_stops.values()),
        }

    def _topsis_score(self, route: dict, budget: float = None, group_size: int = 1) -> tuple[int, str]:
        fare = route.get("total_fare", 100)
        duration = route.get("total_duration_minutes", 60)
        walk = route.get("total_walking_km", 0)
        distance = route.get("total_distance_km", 10)
        route_type = route.get("type", "")

        fare_score = max(0, 100 - (fare / 10))
        time_score = max(0, 100 - (duration / 2))
        walk_score = max(0, 100 - (walk * 15))

        comfort_map = {
            "metro_interchange": 85, "metro": 85, "bus_ac_vajra": 70,
            "kia_bus": 75, "bus_ordinary": 50, "bus_to_metro": 70,
            "metro_to_bus": 65, "car": 90, "cab": 85, "walk": 40
        }
        comfort = comfort_map.get(route_type, 60)

        parts = []
        parts.append(f"fare {fare_score:.0f}/100 × 25%")
        parts.append(f"time {time_score:.0f}/100 × 30%")
        parts.append(f"walk {walk_score:.0f}/100 × 15%")
        parts.append(f"comfort {comfort:.0f}/100 × 20%")

        final_score = int(fare_score * 0.25 + time_score * 0.30 + walk_score * 0.15 + comfort * 0.20)

        # Budget bonus: prefer routes well under budget
        bonus_parts = []
        if budget and budget > 0:
            budget_ratio = fare / budget
            if budget_ratio <= 0.4:
                final_score += 10
                bonus_parts.append("budget save +10")
            elif budget_ratio <= 0.7:
                final_score += 5
                bonus_parts.append("budget save +5")
            elif budget_ratio > 1.0:
                final_score -= 15
                bonus_parts.append("over budget -15")
            elif budget_ratio > 0.9:
                final_score -= 5
                bonus_parts.append("near limit -5")

        # Group size: cheaper per-person = better
        if group_size > 1 and fare > 0:
            pp = fare / group_size
            if pp <= 30:
                final_score += 5
                bonus_parts.append(f"cheap pp ₹{round(pp)} +5")

        if route_type in ("metro", "metro_interchange"):
            final_score += 5
            bonus_parts.append("metro +5")
        if route.get("route_numbers"):
            final_score += 3
            bonus_parts.append("known routes +3")

        explanation = " + ".join(parts)
        if bonus_parts:
            explanation += " | " + " + ".join(bonus_parts)

        return max(10, min(99, final_score)), explanation

    def get_complete_journey_segments(self, from_lat, from_lng, from_name,
                                       dest_lat, dest_lng, dest_name,
                                       group_size=1, budget=None):
        step = self.get_segment_step_options(
            from_lat, from_lng, from_name,
            dest_lat, dest_lng, dest_name,
            group_size, budget
        )
        all_opts = step.get("direct_options", [])
        via_stops = step.get("via_stops", [])

        # Split into two top-level groups: Bus (with walk-to-stop baked in) and Ride (direct)
        bus_opts = [o for o in all_opts if o.get("mode", "").startswith("bus_")]
        ride_opts = [o for o in all_opts if o.get("mode", "") in ("cab","cab_xl","cab_women","cab_pet","auto","bike")]

        def _make_mode_dest(group_key, opts_list, via_stops, dest_lat, dest_lng, dest_name):
            entries = []
            seen = set()
            for opt in opts_list:
                to_key = (round(opt.get("to_lat", 0), 4), round(opt.get("to_lng", 0), 4))
                if to_key in seen:
                    continue
                seen.add(to_key)
                from_stops = []
                if opt.get("arrives_at_stop", False):
                    for vs in via_stops:
                        vs_key = (round(vs["stop"]["lat"], 4), round(vs["stop"]["lng"], 4))
                        if vs_key == to_key:
                            from_stops = vs.get("from_stop_options", [])
                            break
                entries.append({
                    "to": {"name": opt.get("to", dest_name), "lat": opt.get("to_lat", dest_lat), "lng": opt.get("to_lng", dest_lng), "type": group_key},
                    "transport_options": [opt],
                    "next": None,
                    "from_stops": from_stops,
                })
            return entries

        bus_dests = _make_mode_dest("bus", bus_opts, via_stops, dest_lat, dest_lng, dest_name)
        ride_dests = _make_mode_dest("ride", ride_opts, via_stops, dest_lat, dest_lng, dest_name)

        # Build mode-level segment — exactly two choices: Bus and Ride
        mode_destinations = []
        if bus_dests:
            mode_destinations.append({
                "to": {"name": "Bus", "type": "mode_choice", "lat": from_lat, "lng": from_lng},
                "transport_options": bus_opts,
                "next": {"from": {"name": "Bus Options", "lat": from_lat, "lng": from_lng}, "destinations": bus_dests},
                "from_stops": [],
            })
        if ride_dests:
            mode_destinations.append({
                "to": {"name": "Ride (Cab/Auto/Bike)", "type": "mode_choice", "lat": from_lat, "lng": from_lng},
                "transport_options": ride_opts,
                "next": {"from": {"name": "Ride Options", "lat": from_lat, "lng": from_lng}, "destinations": ride_dests},
                "from_stops": [],
            })

        # Flatten tree into segments
        segments = []
        def _flatten(node, parent_idx=None):
            if node is None:
                return
            seg = {
                "segment_index": len(segments),
                "from": node["from"],
                "destinations": node["destinations"],
                "parent_via_index": parent_idx,
            }
            segments.append(seg)
            for di, dest in enumerate(node["destinations"]):
                if dest.get("next"):
                    _flatten(dest["next"], di)
        _flatten({"from": {"name": from_name, "lat": from_lat, "lng": from_lng}, "destinations": mode_destinations})

        return {
            "from": {"lat": from_lat, "lng": from_lng, "name": from_name},
            "dest": {"lat": dest_lat, "lng": dest_lng, "name": dest_name},
            "segments": segments,
            "direct_options": all_opts,
        }

    def __init__(self):
        self._path_cache = {}

    def _interpolate_path(self, slat, slng, dlat, dlng, num_points=12):
        """Generate interpolated points along great circle if OSRM fails."""
        import math
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            lat = slat + (dlat - slat) * t
            lng = slng + (dlng - slng) * t
            points.append([round(lat, 6), round(lng, 6)])
        return points

    async def get_osrm_path_between(self, slat, slng, dlat, dlng, profile="driving"):
        key = (round(slat, 4), round(slng, 4), round(dlat, 4), round(dlng, 4), profile)
        if key in self._path_cache:
            return self._path_cache[key]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"{settings.OSRM_BASE_URL}/route/v1/{profile}/{slng},{slat};{dlng},{dlat}?overview=full&geometries=geojson"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        coords = data["routes"][0]["geometry"]["coordinates"]
                        path = [[c[1], c[0]] for c in coords]
                        self._path_cache[key] = path
                        return path
        except:
            pass
        # Fallback: interpolated path
        fallback = self._interpolate_path(slat, slng, dlat, dlng)
        self._path_cache[key] = fallback
        return fallback

    async def _add_leg_paths(self, route: dict):
        _ensure_gtfs()
        tasks = []
        leg_indices = []
        for i, leg in enumerate(route.get("legs", [])):
            mode = leg.get("mode", "")
            f_lat, f_lng = leg.get("from_lat"), leg.get("from_lng")
            t_lat, t_lng = leg.get("to_lat"), leg.get("to_lng")

            # Metro legs: use station-to-station rail path from DB
            if mode == "metro" and leg.get("from") and leg.get("to"):
                rail_path = db.get_metro_line_path(leg["from"], leg["to"])
                if rail_path:
                    route["legs"][i]["path"] = rail_path
                    continue

            # Bus legs: try GTFS shape between stops (instant, no HTTP call)
            if mode in ("bus_ordinary", "bus_ac_vajra", "kia_bus") and leg.get("from") and leg.get("to"):
                shape = _gtfs.get_shape_between_stops(leg["from"], leg["to"])
                if shape:
                    route["legs"][i]["path"] = [[lat, lng] for lat, lng in shape]
                    continue

            # Walking legs: OSRM walking profile; others: driving
            profile = "walking" if mode.startswith("walk") else "driving"

            if f_lat is not None and f_lng is not None and t_lat is not None and t_lng is not None:
                tasks.append(self.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile))
                leg_indices.append(i)
        if tasks:
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=30.0)
            for idx, path in zip(leg_indices, results):
                route["legs"][idx]["path"] = path

    async def get_osrm_route(self, slat, slng, dlat, dlng):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{slng},{slat};{dlng},{dlat}?overview=full&geometries=geojson&steps=true"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        route = data["routes"][0]
                        steps_raw = route.get("legs", [{}])[0].get("steps", [])
                        steps = []
                        for s in steps_raw:
                            steps.append({
                                "instruction": s.get("maneuver", {}).get("instruction", ""),
                                "modifier": s.get("maneuver", {}).get("modifier", ""),
                                "name": s.get("name", ""),
                                "distance": round(s.get("distance", 0) / 1000, 2),
                                "duration": round(s.get("duration", 0) / 60, 1),
                                "bearing_after": s.get("maneuver", {}).get("bearing_after", 0),
                                "type": s.get("maneuver", {}).get("type", "")
                            })
                        return {
                            "distance_km": round(route["distance"] / 1000, 2),
                            "duration_minutes": round(route["duration"] / 60, 1),
                            "geometry": route["geometry"],
                            "steps": steps
                        }
        except Exception:
            pass
        return None

    async def get_driving_route(self, slat, slng, dlat, dlng):
        return await self.get_osrm_route(slat, slng, dlat, dlng)

transit_service = TransitService()
