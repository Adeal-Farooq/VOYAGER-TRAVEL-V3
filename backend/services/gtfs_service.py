"""GTFS data loader for BMTC bus routes - provides real bus path geometry."""
import csv, io, zipfile, os, math, pickle
from backend.core.config import settings

_CACHE_PATH = os.path.join(settings.PROCESSED_DIR, "gtfs_cache.pkl")

class GTFSLoader:
    def __init__(self):
        self._shapes = {}         # shape_id -> list of (lat, lng)
        self._route_shapes = {}   # route_short_name -> [shape_id, ...]
        self._stop_to_shapes = {} # stop_name -> [(shape_id, seq), ...]
        self._stops_by_name = {}  # stop_name -> (lat, lng, stop_id)
        self._stop_times = {}     # stop_name_lower -> [(departure_time, route_short_name), ...]
        self._loaded = False

    def _hav(self, a, b):
        R = 6371
        dlat = (b[0] - a[0]) * math.pi / 180
        dlng = (b[1] - a[1]) * math.pi / 180
        x = math.sin(dlat/2)**2 + math.cos(a[0]*math.pi/180) * math.cos(b[0]*math.pi/180) * math.sin(dlng/2)**2
        return 2 * R * math.asin(math.sqrt(x))

    def _try_load_cache(self):
        zip_path = os.path.join(settings.DATA_CACHE_DIR, "bmtc_gtfs.zip")
        if os.path.exists(_CACHE_PATH) and os.path.exists(zip_path):
            zip_mtime = os.path.getmtime(zip_path)
            cache_mtime = os.path.getmtime(_CACHE_PATH)
            if cache_mtime > zip_mtime:
                try:
                    with open(_CACHE_PATH, "rb") as f:
                        data = pickle.load(f)
                    self._shapes = data["shapes"]
                    self._route_shapes = data["route_shapes"]
                    self._stop_to_shapes = data["stop_to_shapes"]
                    self._stops_by_name = data["stops_by_name"]
                    self._stop_times = data["stop_times"]
                    self._loaded = True
                    print(f"[GTFS] Loaded from cache ({len(self._shapes)} shapes, {len(self._stop_times)} stops)")
                    return True
                except Exception as e:
                    print(f"[GTFS] Cache load failed: {e}")
        return False

    def _save_cache(self):
        try:
            os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
            with open(_CACHE_PATH, "wb") as f:
                pickle.dump({
                    "shapes": self._shapes,
                    "route_shapes": self._route_shapes,
                    "stop_to_shapes": self._stop_to_shapes,
                    "stops_by_name": self._stops_by_name,
                    "stop_times": self._stop_times,
                }, f, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"[GTFS] Cache saved to {_CACHE_PATH}")
        except Exception as e:
            print(f"[GTFS] Cache save failed: {e}")

    def load(self):
        if self._loaded:
            return
        if self._try_load_cache():
            return
        path = os.path.join(settings.DATA_CACHE_DIR, "bmtc_gtfs.zip")
        if not os.path.exists(path):
            print("[GTFS] File not found:", path)
            return
        with zipfile.ZipFile(path, "r") as z:
            # Load shapes
            with z.open("shapes.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    sid = row["shape_id"]
                    lat = float(row["shape_pt_lat"])
                    lng = float(row["shape_pt_lon"])
                    seq = int(row["shape_pt_sequence"])
                    if sid not in self._shapes:
                        self._shapes[sid] = []
                    self._shapes[sid].append((lat, lng, seq))

            for sid in self._shapes:
                self._shapes[sid].sort(key=lambda x: x[2])
                self._shapes[sid] = [(c[0], c[1]) for c in self._shapes[sid]]

            # Load stops
            self._stops_by_name_inv = {}
            with z.open("stops.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    name = row["stop_name"].strip().lower()
                    sid = row["stop_id"]
                    self._stops_by_name[name] = (
                        float(row["stop_lat"]), float(row["stop_lon"]), sid
                    )
                    self._stops_by_name_inv[sid] = name

            # Load trips -> shape mapping (moved to later section)
            trip_shape_map = {}
            with z.open("trips.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    sid = row.get("shape_id", "")
                    if sid in self._shapes:
                        trip_shape_map[row["trip_id"]] = sid

            # Load routes -> short_name mapping and build trip_id -> route_short_name
            route_id_to_name = {}
            with z.open("routes.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    rid = row["route_id"]
                    sn = row.get("route_short_name", "").strip().upper()
                    route_id_to_name[rid] = sn

            trip_to_route = {}
            with z.open("trips.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    trip_to_route[row["trip_id"]] = row["route_id"]

            # Load stop_times -> map stops to shapes and capture departure times
            shape_stops = {}
            stop_times_count = 0
            with z.open("stop_times.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    trip_id = row["trip_id"]
                    shape_id = trip_shape_map.get(trip_id)
                    sid = row["stop_id"]
                    seq = int(row["stop_sequence"])
                    if shape_id:
                        if shape_id not in shape_stops:
                            shape_stops[shape_id] = {}
                        if sid not in shape_stops[shape_id]:
                            shape_stops[shape_id][sid] = seq
                    # Capture departure times for all rows up to limit
                    if stop_times_count < 100000:
                        dep_time = row.get("departure_time", "")
                        if dep_time and sid in self._stops_by_name_inv:
                            sname = self._stops_by_name_inv[sid]
                            rid = trip_to_route.get(trip_id, "")
                            rsn = route_id_to_name.get(rid, rid)
                            if sname not in self._stop_times:
                                self._stop_times[sname] = []
                            # Store all departure times for this stop (up to 20 per stop)
                            if len(self._stop_times[sname]) < 20:
                                self._stop_times[sname].append((dep_time, rsn))
                    stop_times_count += 1

            # Build stop_name -> shape_ids index
            for sname, (slat, slng, sid) in self._stops_by_name.items():
                for shape_id, stop_seqs in shape_stops.items():
                    if sid in stop_seqs:
                        if sname not in self._stop_to_shapes:
                            self._stop_to_shapes[sname] = []
                        self._stop_to_shapes[sname].append((shape_id, stop_seqs[sid]))

            # Build route_short_name -> shapes using trip_to_route from above
            for trip_id, shape_id in trip_shape_map.items():
                rid = trip_id.split("-")[0] if "-" in trip_id else trip_id
                short_name = route_id_to_name.get(rid, rid)
                if short_name not in self._route_shapes:
                    self._route_shapes[short_name] = []
                if shape_id not in self._route_shapes[short_name]:
                    self._route_shapes[short_name].append(shape_id)

        print(f"[GTFS] Loaded {len(self._shapes)} shapes, {len(self._route_shapes)} route mappings, {len(self._stop_to_shapes)} stop->shape mappings")
        self._loaded = True
        self._save_cache()

    def get_shape_by_route(self, route_short_name: str):
        key = route_short_name.strip().upper()
        shape_ids = self._route_shapes.get(key)
        if shape_ids:
            coords = self._shapes.get(shape_ids[0])
            if coords and len(coords) >= 2:
                return coords
        return None

    def get_shape_between_stops(self, from_name: str, to_name: str):
        """Find a GTFS shape that goes through both stops, clip to the segment between them."""
        fk = from_name.lower().strip()
        tk = to_name.lower().strip()
        f_stop = self._stop_to_shapes.get(fk, [])
        t_stop = self._stop_to_shapes.get(tk, [])
        if not f_stop or not t_stop:
            return None
        f_shapes = {s[0]: s[1] for s in f_stop}
        t_shapes = {s[0]: s[1] for s in t_stop}
        common = set(f_shapes.keys()) & set(t_shapes.keys())
        for shape_id in common:
            coords = self._shapes.get(shape_id)
            if not coords:
                continue
            f_seq = f_shapes[shape_id]
            t_seq = t_shapes[shape_id]
            start = min(f_seq, t_seq) - 1
            end = max(f_seq, t_seq)
            segment = coords[start:end]
            if len(segment) >= 2:
                if f_seq <= t_seq:
                    return segment
                else:
                    return list(reversed(segment))
        return None

    def get_next_buses(self, stop_name: str, limit: int = 3) -> list:
        key = stop_name.lower().strip()
        times = self._stop_times.get(key, [])
        if not times:
            return []
        from datetime import datetime
        now = datetime.now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        future_times = [(t, r) for t, r in times if time_to_seconds(t) >= current_seconds]
        if not future_times:
            future_times = times
        sorted_times = sorted(future_times, key=lambda x: x[0])
        return [{"departure_time": t[0], "route": t[1]} for t in sorted_times[:limit]]

    def get_common_routes(self, src_name: str, dest_name: str) -> list:
        """Find route short names common to both stops using GTFS stop_times data."""
        sk = src_name.lower().strip()
        dk = dest_name.lower().strip()
        src_routes = set(r for _, r in self._stop_times.get(sk, []))
        dst_routes = set(r for _, r in self._stop_times.get(dk, []))
        if not src_routes or not dst_routes:
            return []
        common = sorted(src_routes & dst_routes)
        return common[:5]

    def get_all_buses_at_stop(self, stop_name: str) -> dict:
        """Get all bus times at a stop, grouped by route number.
        Returns dict of {route_number: [departure_time, ...]} sorted by time."""
        key = stop_name.lower().strip()
        times = self._stop_times.get(key, [])
        if not times:
            return {}
        from datetime import datetime
        now = datetime.now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        grouped = {}
        for dep_time, route in times:
            if time_to_seconds(dep_time) >= current_seconds:
                if route not in grouped:
                    grouped[route] = []
                grouped[route].append(dep_time)
        for route in grouped:
            grouped[route].sort()
        # Sort routes by earliest bus
        return dict(sorted(grouped.items(), key=lambda x: x[1][0] if x[1] else ''))

gtfs_loader = GTFSLoader()
