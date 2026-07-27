import json, logging
import csv
import os
import math
import re as _re
import pandas as pd

logger = logging.getLogger(__name__)

_ROUTE_NUM_PATTERN = _re.compile(r'^(?=.*\d)[\dA-Z]+(-[A-Z0-9]+)?$')
def _clean_route_key(key: str) -> str:
    parts = key.strip().upper().split(None, 1)
    if len(parts) >= 2:
        first = parts[0].rstrip('-.,')
        if _ROUTE_NUM_PATTERN.match(first):
            return first
    return key.strip().upper()


from backend.core.config import settings
from backend.core.spatial_index import SpatialIndex

def _haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = (lat2 - lat1) * math.pi / 180
    dlng = (lng2 - lng1) * math.pi / 180
    a = math.sin(dlat/2)**2 + math.cos(lat1*math.pi/180) * math.cos(lat2*math.pi/180) * math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))

class TransitDatabase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def initialize(self):
        if self._initialized:
            return
        self._initialized = True

        self.metro_stations = []
        self.metro_lines = {}
        self.bus_stops = {}
        self.kia_routes = {}
        self.transit_fares = {}
        self.wards_data = {}
        self.railway_stations = []

        self._load_transit_fares()
        self._load_metro_data()
        self._load_bus_stops()
        self._load_kia_routes()
        self._load_railway_stations()

        # Build spatial indexes for fast nearby-stop lookups
        bus_items = [s for s in self.bus_stops.values() if isinstance(s, dict)]
        self._bus_spatial = SpatialIndex()
        self._bus_spatial.build(bus_items)
        self._metro_spatial = SpatialIndex()
        self._metro_spatial.build(self.metro_stations)
        self._rail_spatial = SpatialIndex()
        self._rail_spatial.build(self.railway_stations)

    def _load_transit_fares(self):
        path = os.path.join(settings.DATA_CACHE_DIR, "transit_fares.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                self.transit_fares = json.load(f)

    def _load_metro_data(self):
        path = os.path.join(settings.DATA_CACHE_DIR, "bengaluru_metro_network.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            self._metro_by_code = {}
            for _, row in df.iterrows():
                station = {
                    "name": row.get("station_name", row.get("Station_Name", "")),
                    "line": row.get("line", row.get("Line", "")),
                    "lat": float(row.get("latitude", row.get("Latitude", 0))),
                    "lng": float(row.get("longitude", row.get("Longitude", 0))),
                    "station_code": str(row.get("station_code", "")),
                    "next_station_code": str(row.get("next_station_code", "")),
                    "distance_to_next_km": float(row.get("distance_to_next_km", 0)),
                    "is_interchange": int(row.get("is_interchange", 0)),
                    "sequence": int(row.get("sequence", 0)),
                }
                self.metro_stations.append(station)
                if station["station_code"]:
                    self._metro_by_code[station["station_code"]] = station
                line = station["line"]
                if line not in self.metro_lines:
                    self.metro_lines[line] = []
                self.metro_lines[line].append(station)

            # Build distance lookup between any two stations on same line
            self._metro_distance_cache = {}
            for line_name, stations in self.metro_lines.items():
                stations_sorted = sorted(stations, key=lambda s: s["sequence"])
                station_codes = [s["station_code"] for s in stations_sorted if s["station_code"]]
                for i, sc1 in enumerate(station_codes):
                    cum_dist = 0.0
                    for j in range(i, len(station_codes) - 1):
                        sc_a = station_codes[j]
                        sc_b = station_codes[j + 1]
                        next_s = self._metro_by_code.get(sc_a, {})
                        nlat, nlng = next_s.get("lat", 0), next_s.get("lng", 0)
                        nxt = self._metro_by_code.get(sc_b, {})
                        nxt_lat, nxt_lng = nxt.get("lat", 0), nxt.get("lng", 0)
                        cum_dist += next_s.get("distance_to_next_km", 
                             _haversine(nlat, nlng, nxt_lat, nxt_lng))
                        if sc1 != sc_b:
                            self._metro_distance_cache[(sc1, sc_b)] = round(cum_dist, 2)

    def _load_bus_stops(self):
        path = os.path.join(settings.DATA_CACHE_DIR, "bmtc_all_stops_master.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            df.columns = [c.strip() for c in df.columns]
            for idx, row in df.iterrows():
                stop_id = str(idx)
                name = str(row.get("Stop Name", ""))
                lat = float(row.get("Latitude", 0))
                lng = float(row.get("Longitude", 0))
                if lat == 0 and lng == 0 or not name or name.lower() in ('nan', 'none', 'null'):
                    continue
                routes_raw = row.get("Routes with num trips", "{}")
                routes_list = []
                if isinstance(routes_raw, str) and routes_raw.startswith("{"):
                    try:
                        import ast
                        routes_dict = ast.literal_eval(routes_raw)
                        routes_list = [_clean_route_key(k) for k in routes_dict.keys()]
                    except Exception as e:
                        logger.debug(f"ast parse failed for routes_raw: {e}")
                        try:
                            routes_list = [_clean_route_key(k) for k in json.loads(routes_raw.replace("'", "\"").replace("None", "null")).keys()]
                        except Exception as e2:
                            logger.debug(f"json parse also failed: {e2}")
                self.bus_stops[stop_id] = {
                    "stop_id": stop_id,
                    "name": name,
                    "lat": lat,
                    "lng": lng,
                    "routes": routes_list
                }

    def _load_kia_routes(self):
        path = os.path.join(settings.DATA_CACHE_DIR, "kia_routes_fare_full.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                self.kia_routes = data.get("vayu_vajra_kia_routes", {})

    def get_metro_fare(self, distance_km: float) -> float:
        for slab in self.transit_fares.get("namma_metro_slabs", []):
            if distance_km <= slab["max_km"]:
                return slab["fare"]
        return self.transit_fares.get("namma_metro_slabs", [{}])[-1].get("fare", 95.0)

    def get_bmtc_ordinary_fare(self, distance_km: float, passenger_type: str = "adult") -> float:
        for slab in self.transit_fares.get("bmtc_ordinary_slabs", []):
            if distance_km <= slab["max_km"]:
                fare = slab["fare"]
                if passenger_type == "child":
                    return fare * 0.5
                elif passenger_type == "senior":
                    return fare * 0.75
                return fare
        return 32.0

    def get_bmtc_ac_fare(self, distance_km: float, passenger_type: str = "adult") -> float:
        for slab in self.transit_fares.get("bmtc_ac_vajra_slabs", []):
            if distance_km <= slab["max_km"]:
                if passenger_type == "child":
                    return slab.get("child_fare", slab["adult_fare"])
                elif passenger_type == "senior":
                    return slab.get("senior_fare", slab["adult_fare"])
                return slab["adult_fare"]
        return 65.0

    def find_metro_station(self, name_query: str) -> list:
        query = name_query.lower().strip()
        results = []
        for station in self.metro_stations:
            if query in station["name"].lower():
                results.append(station)
        return results

    def find_bus_stops(self, name_query: str) -> list:
        query = name_query.lower().strip()
        results = []
        for stop_id, stop in self.bus_stops.items():
            if query in stop["name"].lower():
                results.append(stop)
        return results

    def find_nearby_bus_stops(self, lat: float, lng: float, radius_km: float = 1.0) -> list:
        return self._bus_spatial.query(lat, lng, radius_km, max_results=20)

    def _load_railway_stations(self):
        path = os.path.join(settings.DATA_CACHE_DIR, "karnataka_railway_stations.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.railway_stations = json.load(f)

    def find_nearby_railway_stations(self, lat: float, lng: float, radius_km: float = 30.0) -> list:
        return self._rail_spatial.query(lat, lng, radius_km, max_results=10)

    def get_metro_distance_between(self, stn_a_name: str, stn_b_name: str) -> float:
        code_a = code_b = None
        for s in self.metro_stations:
            if s["name"].lower() == stn_a_name.lower(): code_a = s["station_code"]
            if s["name"].lower() == stn_b_name.lower(): code_b = s["station_code"]
        if code_a and code_b:
            dist = self._metro_distance_cache.get((code_a, code_b))
            if dist: return dist
            dist = self._metro_distance_cache.get((code_b, code_a))
            if dist: return dist
        for s in self.metro_stations:
            if s["name"].lower() == stn_a_name.lower():
                for s2 in self.metro_stations:
                    if s2["name"].lower() == stn_b_name.lower():
                        if s["line"] == s2["line"]:
                            return abs(s2["sequence"] - s["sequence"]) * 1.2
        a_s = next((s for s in self.metro_stations if s["name"].lower() == stn_a_name.lower()), {})
        b_s = next((s for s in self.metro_stations if s["name"].lower() == stn_b_name.lower()), {})
        if a_s and b_s:
            return _haversine(a_s["lat"], a_s["lng"], b_s["lat"], b_s["lng"])
        return 0

    def find_nearby_metro_stations(self, lat: float, lng: float, radius_km: float = 2.0) -> list:
        return self._metro_spatial.query(lat, lng, radius_km, max_results=50)

    def get_metro_line_path(self, from_name: str, to_name: str) -> list | None:
        from_name_l = from_name.lower().strip()
        to_name_l = to_name.lower().strip()
        from_candidates = [s for s in self.metro_stations if s["name"].lower().strip() == from_name_l]
        to_candidates = [s for s in self.metro_stations if s["name"].lower().strip() == to_name_l]
        if not from_candidates or not to_candidates:
            return None
        from_stn = to_stn = None
        for fc in from_candidates:
            for tc in to_candidates:
                if fc.get("line") == tc.get("line") and fc.get("line") in self.metro_lines:
                    from_stn = fc
                    to_stn = tc
                    break
            if from_stn and to_stn:
                break
        if not from_stn or not to_stn:
            from_stn = from_candidates[0]
            to_stn = to_candidates[0]
            if from_stn.get("line") != to_stn.get("line"):
                return None
        line_name = from_stn["line"]
        line_stations = self.metro_lines.get(line_name, [])
        seq_from = from_stn["sequence"]
        seq_to = to_stn["sequence"]
        step = 1 if seq_to > seq_from else -1
        coords = []
        for s in line_stations:
            if step == 1 and from_stn["sequence"] <= s["sequence"] <= to_stn["sequence"]:
                coords.append([s["lat"], s["lng"]])
            elif step == -1 and to_stn["sequence"] <= s["sequence"] <= from_stn["sequence"]:
                coords.append([s["lat"], s["lng"]])
        if step == -1:
            coords.reverse()
        return coords if len(coords) >= 2 else None

    def get_kia_route_for_stop(self, stop_name: str) -> list:
        routes_for_stop = []
        for route_id, route_data in self.kia_routes.items():
            for stop in route_data.get("stops", []):
                if stop_name.lower() in stop["stop_name"].lower():
                    routes_for_stop.append({
                        "route_id": route_id,
                        "route_info": route_data["route_info"],
                        "stop_name": stop["stop_name"],
                        "fare": stop["fare"]
                    })
                    break
        return routes_for_stop

    def find_stop_by_name(self, name: str) -> dict | None:
        if not name: return None
        name_lower = name.lower().strip()
        # Check bus stops
        for stop in self.bus_stops.values():
            if not isinstance(stop, dict): continue
            sn = stop.get("name", "")
            if isinstance(sn, str) and sn.lower().strip() == name_lower:
                return stop
        # Check metro stations
        for station in self.metro_stations:
            if not isinstance(station, dict): continue
            sn = station.get("name", "")
            if isinstance(sn, str) and sn.lower().strip() == name_lower:
                return station
        # Partial match as fallback
        for stop in self.bus_stops.values():
            if not isinstance(stop, dict): continue
            sn = stop.get("name", "")
            if isinstance(sn, str) and name_lower in sn.lower():
                return stop
        for station in self.metro_stations:
            if not isinstance(station, dict): continue
            sn = station.get("name", "")
            if isinstance(sn, str) and name_lower in sn.lower():
                return station
        return None

db = TransitDatabase()
