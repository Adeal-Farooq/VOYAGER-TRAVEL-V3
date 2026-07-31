"""In-memory station DB + spatial index for VOYAGER v2 (PROMPT_1 §4.3).

Loads the static datasets once at startup (eager):
  - bus stops: bmtc_all_stops_master.csv  (skip nan/none/null names)
  - metro:     bengaluru_metro_network.csv (Purple + Green ONLY — no Blue/Yellow/Yelahanka)
  - rail:      karnataka_railway_stations.json

Spatial queries use a lat-bisect + lng-window scan over the sorted-by-lat list,
fast enough (<5ms) for the ~3000 bus stops.
"""
import ast
import csv
import json
import math
from bisect import bisect_left, bisect_right

from .data_schema import BusStop, MetroStation, RailStation
from .. import config

_MEAN_LAT = 12.97
_LAT_M_PER_DEG = 110574.0
_LNG_M_PER_DEG = 111320.0 * math.cos(math.radians(_MEAN_LAT))
_TRASH = {"", "nan", "none", "null", "n/a", "na"}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class TransitDatabase:
    def __init__(self):
        self._bus: list[BusStop] = []
        self._metro: list[MetroStation] = []
        self._rail: list[RailStation] = []
        self._bus_by_lat: list[tuple[float, int]] = []  # (lat, index) sorted
        self._metro_by_lat: list[tuple[float, int]] = []
        self._rail_by_lat: list[tuple[float, int]] = []
        self._stop_routes: dict[str, list[str]] = {}
        self._load()

    # ------------------------------------------------------------- loading
    def _load(self) -> None:
        self._load_bus_stops()
        self._load_metro()
        self._load_rail()
        for lst in (self._bus, self._metro, self._rail):
            lst.sort(key=lambda s: s.lat)
        self._bus_by_lat = [(s.lat, i) for i, s in enumerate(self._bus)]
        self._metro_by_lat = [(s.lat, i) for i, s in enumerate(self._metro)]
        self._rail_by_lat = [(s.lat, i) for i, s in enumerate(self._rail)]

    def _load_bus_stops(self) -> None:
        try:
            with open(config.BUS_STOPS_MASTER_PATH, encoding="utf-8-sig") as fh:
                rows = csv.DictReader(fh)
                for r in rows:
                    name = str(r.get("Stop Name", "")).strip()
                    if name.lower() in _TRASH:
                        continue
                    try:
                        lat = float(r["Latitude"])
                        lng = float(r["Longitude"])
                    except (KeyError, ValueError, TypeError):
                        continue
                    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                        continue
                    routes = self._parse_route_dict(r.get("Routes with num trips", ""))
                    self._bus.append(BusStop(name=name, lat=lat, lng=lng, routes=routes))
                    if routes:
                        self._stop_routes[name] = routes
        except FileNotFoundError:
            print(f"[db] missing {config.BUS_STOPS_MASTER_PATH.name} — bus stops empty")
        print(f"[db] loaded {len(self._bus)} bus stops")

    @staticmethod
    def _parse_route_dict(raw: str) -> list[str]:
        from backend.services.gtfs_service import clean_route_short_name

        raw = raw.strip()
        if not raw or raw.startswith("{"):
            try:
                d = ast.literal_eval(raw) if raw else {}
                return [clean_route_short_name(k) for k in (d.keys() if isinstance(d, dict) else [])]
            except (ValueError, SyntaxError):
                return []
        return [clean_route_short_name(t) for t in raw.split(",") if t.strip()]

    def _load_metro(self) -> None:
        try:
            with open(config.METRO_NETWORK_PATH, encoding="utf-8-sig") as fh:
                rows = csv.DictReader(fh)
                for r in rows:
                    line = str(r.get("line", "")).strip()
                    if line not in config.OPERATIONAL_METRO_LINES:
                        continue  # Yellow/Blue under construction — excluded
                    name = str(r.get("station_name", "")).strip()
                    if not name:
                        continue
                    try:
                        lat, lng = float(r["latitude"]), float(r["longitude"])
                    except (KeyError, ValueError):
                        continue
                    self._metro.append(
                        MetroStation(
                            name=name,
                            lat=lat,
                            lng=lng,
                            lines=[line],
                            is_hub=bool(int(r.get("is_interchange", 0) or 0)),
                        )
                    )
        except FileNotFoundError:
            print(f"[db] missing {config.METRO_NETWORK_PATH.name} — metro empty")
        print(f"[db] loaded {len(self._metro)} metro stations (purple+green)")

    def _load_rail(self) -> None:
        try:
            with open(config.RAIL_STATIONS_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
            for entry in data:
                name = str(entry.get("name", "")).strip()
                try:
                    lat, lng = float(entry["lat"]), float(entry["lng"])
                except (KeyError, ValueError, TypeError):
                    continue
                self._rail.append(RailStation(name=name, code=self._derive_code(name), lat=lat, lng=lng))
        except FileNotFoundError:
            print(f"[db] missing {config.RAIL_STATIONS_PATH.name} — rail empty")
        print(f"[db] loaded {len(self._rail)} rail stations")

    @staticmethod
    def _derive_code(name: str) -> str:
        words = [w for w in name.replace("-", " ").split() if w]
        code = "".join(w[0] for w in words)[:4].upper() if words else name[:4].upper()
        return code

    # ---------------------------------------------------------- spatial API
    def _nearby(self, src: list, by_lat: list[tuple[float, int]], lat, lng, radius_m: float) -> list:
        out = []
        dlat = radius_m / _LAT_M_PER_DEG
        lo = bisect_left(by_lat, (lat - dlat, -1))
        hi = bisect_right(by_lat, (lat + dlat, 1 << 60))
        dlng = radius_m / _LNG_M_PER_DEG
        for _lat, i in by_lat[lo:hi]:
            s = src[i]
            if abs(s.lng - lng) > dlng:
                continue
            if _haversine_m(lat, lng, s.lat, s.lng) <= radius_m:
                out.append(s)
        return out

    def bus_stops_near(self, lat, lng, radius_m: float) -> list[BusStop]:
        return self._nearby(self._bus, self._bus_by_lat, lat, lng, radius_m)

    def metro_near(self, lat, lng, radius_m: float) -> list[MetroStation]:
        return self._nearby(self._metro, self._metro_by_lat, lat, lng, radius_m)

    def rail_near(self, lat, lng, radius_m: float) -> list[RailStation]:
        return self._nearby(self._rail, self._rail_by_lat, lat, lng, radius_m)

    def routes_for_stop(self, stop_name: str) -> list[str]:
        return self._stop_routes.get(stop_name, [])

    # ------------------------------------------------------------- accessors
    def metro_stations(self, line: str | None = None) -> list[MetroStation]:
        if line is None:
            return self._metro
        return [s for s in self._metro if line in s.lines]

    def all_bus_stops(self) -> list[BusStop]:
        return self._bus

    def all_metro_stations(self) -> list[MetroStation]:
        return self._metro

    def all_rail_stations(self) -> list[RailStation]:
        return self._rail
