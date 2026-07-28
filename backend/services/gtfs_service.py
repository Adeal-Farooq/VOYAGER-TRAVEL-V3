"""GTFS data loader for BMTC bus routes - provides real bus path geometry."""
import csv, io, zipfile, os, math, pickle, re
from difflib import SequenceMatcher
from backend.core.config import settings

_ROUTE_NUM_PATTERN = re.compile(r'^(?=.*\d)[\dA-Z]+(-[A-Z0-9]+)?$')

def clean_route_short_name(short_name: str) -> str:
    parts = short_name.strip().upper().split(None, 1)
    if len(parts) >= 2:
        first = parts[0].rstrip('-.,')
        if _ROUTE_NUM_PATTERN.match(first):
            return first
    return short_name.strip().upper()

def _time_to_seconds(t):
    parts = t.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0

_CACHE_PATH = os.path.join(settings.PROCESSED_DIR, "gtfs_cache.pkl")

def _normalize(name):
    n = name.lower().strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n)
    return n.strip()

# Word-level inverted index for fast fuzzy matching
_GTFS_WORD_INDEX = {}  # word -> [normalized_name, ...]
_GTFS_NORM_NAMES = []  # [normalized_name, ...] in same order as _all_gtfs_names

def _build_word_index(names: list):
    global _GTFS_NORM_NAMES
    _GTFS_WORD_INDEX.clear()
    _GTFS_NORM_NAMES = []
    for n in names:
        nn = _normalize(n)
        _GTFS_NORM_NAMES.append(nn)
        for w in set(nn.split()):
            if len(w) >= 3:
                _GTFS_WORD_INDEX.setdefault(w, []).append(nn)

def _fast_fuzzy_match(query: str, candidates: list) -> str | None:
    qn = _normalize(query)
    q_words = set(qn.split())

    if not q_words:
        return None

    # 1) Word-overlap scoring using pre-built index
    if _GTFS_WORD_INDEX:
        scores = {}
        for w in q_words:
            if len(w) < 3:
                continue
            for cn in _GTFS_WORD_INDEX.get(w, []):
                scores[cn] = scores.get(cn, 0) + 1
        if scores:
            best_cn = max(scores, key=scores.get)
            if scores[best_cn] >= 2:
                idx = _GTFS_NORM_NAMES.index(best_cn) if best_cn in _GTFS_NORM_NAMES else -1
                if idx >= 0 and idx < len(candidates):
                    return candidates[idx]
                return best_cn

    # 2) Substring match against pre-normalized names
    for i, nn in enumerate(_GTFS_NORM_NAMES):
        if qn in nn or nn in qn:
            if i < len(candidates):
                return candidates[i]

    # 3) Word-subset match
    if len(q_words) >= 2:
        for i, nn in enumerate(_GTFS_NORM_NAMES):
            cn_words = set(nn.split())
            common = q_words & cn_words
            if len(common) >= min(2, len(q_words)) and len(common) >= min(2, len(cn_words)):
                if i < len(candidates):
                    return candidates[i]

    # 4) Trigram pre-filter (require 2+ matching trigrams) + get_close_matches
    q_trigrams = set(qn[i:i+3] for i in range(len(qn)-2))
    candidates_norm = [nn for nn in _GTFS_NORM_NAMES
                       if sum(1 for t in q_trigrams if t in nn) >= 2]
    if not candidates_norm:
        candidates_norm = [nn for nn in _GTFS_NORM_NAMES
                           if any(w in nn for w in q_words if len(w) >= 3)]
    if not candidates_norm:
        candidates_norm = _GTFS_NORM_NAMES[:100]

    from difflib import get_close_matches
    matches = get_close_matches(qn, candidates_norm, n=1, cutoff=0.55)
    if matches:
        idx = _GTFS_NORM_NAMES.index(matches[0])
        if idx < len(candidates):
            return candidates[idx]
    return None

# Test override: set to a datetime string like "2024-01-01 12:00:00" to freeze time
_TEST_TIME_OVERRIDE = None

def _now():
    if _TEST_TIME_OVERRIDE:
        from datetime import datetime
        return datetime.strptime(_TEST_TIME_OVERRIDE, "%Y-%m-%d %H:%M:%S")
    from datetime import datetime
    return datetime.now()

def set_test_time(time_str: str):
    global _TEST_TIME_OVERRIDE
    _TEST_TIME_OVERRIDE = time_str
    print(f"[GTFS] Test time set to {time_str}")

def clear_test_time():
    global _TEST_TIME_OVERRIDE
    _TEST_TIME_OVERRIDE = None
    print("[GTFS] Test time cleared")

class GTFSLoader:
    def __init__(self):
        self._shapes = {}
        self._route_shapes = {}
        self._stop_to_shapes = {}
        self._stops_by_name = {}
        self._stop_times = {}
        self._stop_times_by_route = {}
        self._name_map = {}
        self._all_gtfs_names = []
        self._word_index_built = False
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
                    self._shapes = data.get("shapes", {})
                    self._route_shapes = data.get("route_shapes", {})
                    self._stop_to_shapes = data.get("stop_to_shapes", {})
                    self._stops_by_name = data.get("stops_by_name", {})
                    self._stop_times = data.get("stop_times", {})
                    self._stop_times_by_route = data.get("stop_times_by_route", {})
                    self._name_map = data.get("name_map", {})
                    self._route_id_to_name = data.get("route_id_to_name", {})
                    self._all_gtfs_names = list(self._stop_times.keys())
                    self._build_word_index()
                    self._loaded = True
                    print(f"[GTFS] Loaded from cache ({len(self._shapes)} shapes, {len(self._stop_times)} stops, {sum(len(v) for v in self._stop_times.values())} times)")
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
                    "stop_times_by_route": self._stop_times_by_route,
                    "name_map": self._name_map,
                    "route_id_to_name": getattr(self, '_route_id_to_name', {}),
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

            # Load trips -> shape mapping
            trip_shape_map = {}
            with z.open("trips.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    sid = row.get("shape_id", "")
                    if sid in self._shapes:
                        trip_shape_map[row["trip_id"]] = sid

            # Load routes -> short_name mapping
            route_id_to_name = {}
            with z.open("routes.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    rid = row["route_id"]
                    sn = clean_route_short_name(row.get("route_short_name", ""))
                    route_id_to_name[rid] = sn

            trip_to_route = {}
            with z.open("trips.txt") as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
                for row in reader:
                    trip_to_route[row["trip_id"]] = row["route_id"]

            # Load stop_times - process ALL rows with generous per-stop limits
            shape_stops = {}
            stop_times_count = 0
            next_progress = 200000
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
                    dep_time = row.get("departure_time", "")
                    if dep_time and sid in self._stops_by_name_inv:
                        sname = self._stops_by_name_inv[sid]
                        rid = trip_to_route.get(trip_id, "")
                        rsn = route_id_to_name.get(rid, rid)
                        if not rsn:
                            continue
                        if sname not in self._stop_times:
                            self._stop_times[sname] = []
                        if len(self._stop_times[sname]) < 200:
                            self._stop_times[sname].append((dep_time, rsn))
                        if rsn not in self._stop_times_by_route:
                            self._stop_times_by_route[rsn] = []
                        if len(self._stop_times_by_route[rsn]) < 500:
                            self._stop_times_by_route[rsn].append((dep_time, sname))
                    stop_times_count += 1
                    if stop_times_count >= next_progress:
                        print(f"[GTFS] Loading stop_times: {stop_times_count} rows...")
                        next_progress += 200000

            print(f"[GTFS] Loaded {stop_times_count} stop_times rows, {len(self._stop_times)} stops indexed")

            # Build stop_name -> shape_ids index (all keys lowercase for case-insensitive lookups)
            for sname, (slat, slng, sid) in self._stops_by_name.items():
                sk = sname.strip().lower()
                for shape_id, stop_seqs in shape_stops.items():
                    if sid in stop_seqs:
                        if sk not in self._stop_to_shapes:
                            self._stop_to_shapes[sk] = []
                        self._stop_to_shapes[sk].append((shape_id, stop_seqs[sid]))

            # Build route_short_name -> shapes (using trip_to_route mapping)
            for trip_id, shape_id in trip_shape_map.items():
                rid = trip_to_route.get(trip_id, trip_id)
                short_name = route_id_to_name.get(rid, rid)
                if short_name not in self._route_shapes:
                    self._route_shapes[short_name] = []
                if shape_id not in self._route_shapes[short_name]:
                    self._route_shapes[short_name].append(shape_id)

        self._route_id_to_name = route_id_to_name
        self._all_gtfs_names = list(self._stop_times.keys())
        self._build_word_index()
        print(f"[GTFS] Loaded {len(self._shapes)} shapes, {len(self._stop_times)} stops with times, {len(self._stop_times_by_route)} routes indexed")
        self._loaded = True
        self._save_cache()

    def _build_word_index(self):
        _build_word_index(self._all_gtfs_names)
        self._word_index_built = True

    def pre_resolve_all(self, names: list):
        for n in names:
            self._resolve_name(n)

    def _resolve_name(self, name: str) -> str | None:
        key = name.lower().strip()
        if key in self._stop_times:
            return key
        if key in self._name_map:
            return self._name_map[key]
        match = _fast_fuzzy_match(key, self._all_gtfs_names)
        if match:
            self._name_map[key] = match
            return match
        return None

    def get_shape_by_route(self, route_short_name: str):
        key = route_short_name.strip().upper()
        shape_ids = self._route_shapes.get(key)
        if shape_ids:
            coords = self._shapes.get(shape_ids[0])
            if coords and len(coords) >= 2:
                return coords
        return None

    def get_shape_between_stops(self, from_name: str, to_name: str):
        # Resolve names through _resolve_name for normalized GTFS keys, then lowercase for lookup
        f_resolved = self._resolve_name(from_name)
        t_resolved = self._resolve_name(to_name)
        fk = f_resolved.strip().lower() if f_resolved else from_name.strip().lower()
        tk = t_resolved.strip().lower() if t_resolved else to_name.strip().lower()
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
        """Get next bus departures for a stop using fuzzy name matching."""
        key = self._resolve_name(stop_name)
        if not key:
            return []
        times = self._stop_times.get(key, [])
        if not times:
            return []
        now = _now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        future_times = [(t, r) for t, r in times if time_to_seconds(t) >= current_seconds]
        if not future_times:
            future_times = times
        sorted_times = sorted(future_times, key=lambda x: x[0])
        seen_routes = set()
        result = []
        for t, r in sorted_times:
            if r not in seen_routes or len(result) < limit:
                result.append({"departure_time": t, "route": r})
                seen_routes.add(r)
        return result[:limit]

    def get_next_buses_with_times(self, stop_name: str, route_filter: str = None, limit: int = 5) -> list:
        """Get next bus departure times for a stop, optionally filtered by route.
        Returns list of {departure_time, route}."""
        key = self._resolve_name(stop_name)
        if not key:
            return []
        times = self._stop_times.get(key, [])
        if not times:
            return []
        now = _now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        filtered = [(t, r) for t, r in times 
                     if (not route_filter or r == route_filter.upper() or route_filter.upper() in r or r in route_filter.upper())
                     and time_to_seconds(t) >= current_seconds]
        if not filtered:
            filtered = [(t, r) for t, r in times if not route_filter or r == route_filter.upper() or route_filter.upper() in r or r in route_filter.upper()]
        sorted_times = sorted(filtered, key=lambda x: x[0])
        return [{"departure_time": t, "route": r} for t, r in sorted_times[:limit]]

    def get_common_routes(self, src_name: str, dest_name: str) -> list:
        """Find route short names common to both stops using GTFS stop_times data.
        Uses fuzzy name matching."""
        sk = self._resolve_name(src_name)
        dk = self._resolve_name(dest_name)
        if not sk or not dk:
            return []
        src_routes = set(r for _, r in self._stop_times.get(sk, []))
        dst_routes = set(r for _, r in self._stop_times.get(dk, []))
        if not src_routes or not dst_routes:
            return []
        common = sorted(src_routes & dst_routes)
        return common[:10]

    def get_all_routes_at_stop(self, stop_name: str) -> list:
        """Get all unique route numbers serving a stop, sorted by next departure time."""
        key = self._resolve_name(stop_name)
        if not key:
            return []
        times = self._stop_times.get(key, [])
        if not times:
            return []
        now = _now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        route_times = {}
        for dep_time, route in times:
            secs = time_to_seconds(dep_time)
            if secs >= current_seconds:
                if route not in route_times:
                    route_times[route] = []
                route_times[route].append(dep_time)
        if not route_times:
            route_times = {}
            for dep_time, route in times:
                if route not in route_times:
                    route_times[route] = []
                route_times[route].append(dep_time)
        sorted_routes = sorted(route_times.items(), key=lambda x: x[1][0] if x[1] else '')
        result = []
        for rn, times_list in sorted_routes:
            result.append({
                "route_number": rn,
                "next_departures": times_list[:5],
            })
        return result

    def get_all_buses_at_stop(self, stop_name: str) -> dict:
        """Get all bus times at a stop, grouped by route number.
        Uses fuzzy name matching."""
        key = self._resolve_name(stop_name)
        if not key:
            return {}
        times = self._stop_times.get(key, [])
        if not times:
            return {}
        now = _now()
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
        return dict(sorted(grouped.items(), key=lambda x: x[1][0] if x[1] else ''))

    def search_stops_by_name(self, query: str, limit: int = 10) -> list:
        """Find GTFS stop names that match a query string."""
        q = _normalize(query)
        results = []
        for gname in self._all_gtfs_names:
            gn = _normalize(gname)
            if q in gn or gn in q:
                score = 1.0
            else:
                score = SequenceMatcher(None, q, gn).ratio()
            if score > 0.6:
                results.append((gname, score))
        results.sort(key=lambda x: -x[1])
        return [r[0] for r in results[:limit]]

    def get_route_stops(self, route_number: str, limit: int = 30) -> list:
        """Get stops for a given route number from stop_times_by_route index."""
        key = route_number.upper().strip()
        entries = self._stop_times_by_route.get(key, [])
        if not entries:
            return []
        now = _now()
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        def time_to_seconds(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0
        seen = set()
        result = []
        for dep_time, sname in sorted(entries, key=lambda x: x[0]):
            if time_to_seconds(dep_time) >= current_seconds:
                if sname not in seen:
                    seen.add(sname)
                    result.append({"stop_name": sname, "next_departure": dep_time})
                    if len(result) >= limit:
                        break
        return result

    def get_shape_path_for_route(self, route_number: str):
        """Get the full shape path for a bus route (returns [[lat,lng],...] or None)."""
        key = route_number.strip().upper()
        shape_ids = self._route_shapes.get(key, [])
        if not shape_ids:
            return None
        for sid in shape_ids:
            coords = self._shapes.get(sid)
            if coords and len(coords) >= 4:
                return [[c[0], c[1]] for c in coords]
        return None

    def find_stops_on_route_toward_dest(self, route_number: str, from_lat: float, from_lng: float,
                                         dest_lat: float, dest_lng: float, max_stops: int = 3):
        """Find up to max_stops along a route, ordered by actual GTFS shape sequence order.
        Returns list of {stop_name, lat, lng, distance_to_dest}."""
        key = route_number.strip().upper()
        shape_ids = self._route_shapes.get(key, [])
        if not shape_ids:
            return []

        # Get all unique stops for this route with their GTFS coordinates
        route_entries = self._stop_times_by_route.get(key, [])
        stops_on_route = {}
        seen = set()
        for dep_time, sname in route_entries:
            sk = sname.strip().lower()
            if sk not in seen:
                seen.add(sk)
                coords = self._stops_by_name.get(sname)
                if coords:
                    stops_on_route[sk] = (sname, coords[0], coords[1])
        if not stops_on_route:
            return []

        # Find which GTFS stop on this route is closest to the source coordinates
        from_sk = min(stops_on_route.keys(),
            key=lambda sk: self._hav((stops_on_route[sk][1], stops_on_route[sk][2]), (from_lat, from_lng)))

        # Get shape sequence entries for the source stop
        from_shape_map = {}
        for sid, seq in self._stop_to_shapes.get(from_sk, []):
            from_shape_map[sid] = seq

        if not from_shape_map:
            return self._find_stops_euclidean_fallback(key, from_lat, from_lng, dest_lat, dest_lng, max_stops)

        # Find all route stops that come AFTER the source stop in a common shape
        stop_seqs = []  # [(seq, shape_id, lat, lng, display_name)]
        for sk, (sname, slat, slng) in stops_on_route.items():
            if sk == from_sk:
                continue
            stop_shape_map = {}
            for sid, seq in self._stop_to_shapes.get(sk, []):
                stop_shape_map[sid] = seq
            common = set(from_shape_map.keys()) & set(stop_shape_map.keys())
            if not common:
                continue
            shape_id = next(iter(common))
            s_seq = stop_shape_map[shape_id]
            f_seq = from_shape_map[shape_id]
            if s_seq > f_seq:
                stop_seqs.append((s_seq, shape_id, slat, slng, sname))

        if not stop_seqs:
            return self._find_stops_euclidean_fallback(key, from_lat, from_lng, dest_lat, dest_lng, max_stops)

        # Sort by shape sequence number (actual stop order along the route)
        stop_seqs.sort(key=lambda x: x[0])

        result = []
        for seq, sid, slat, slng, sname in stop_seqs[:max_stops]:
            dist_to_dest = self._hav((slat, slng), (dest_lat, dest_lng))
            result.append({
                "stop_name": sname,
                "lat": slat,
                "lng": slng,
                "distance_to_dest_km": round(dist_to_dest, 3)
            })
        return result

    def _find_stops_euclidean_fallback(self, key: str, from_lat: float, from_lng: float,
                                        dest_lat: float, dest_lng: float, max_stops: int = 3):
        """Fallback: find stops using Euclidean distance when shape sequence data is unavailable."""
        route_entries = self._stop_times_by_route.get(key, [])
        stops_on_route = []
        seen = set()
        for dep_time, sname in route_entries:
            sk = sname.strip().lower()
            if sk not in seen:
                seen.add(sk)
                coords = self._stops_by_name.get(sname)
                if coords:
                    stops_on_route.append((sname, coords[0], coords[1]))
        if not stops_on_route:
            return []
        from_dist = math.sqrt((dest_lat - from_lat)**2 + (dest_lng - from_lng)**2)
        candidates = []
        for sname, slat, slng in stops_on_route:
            sdist = math.sqrt((dest_lat - slat)**2 + (dest_lng - slng)**2)
            if sdist < from_dist * 0.9:
                candidates.append((sname, slat, slng, sdist))
            elif self._hav((from_lat, from_lng), (slat, slng)) > 0.2:
                candidates.append((sname, slat, slng, sdist))
        candidates.sort(key=lambda x: x[3])
        result = []
        seen = set()
        for sname, slat, slng, sdist in candidates[:max_stops]:
            sk = sname.strip().lower()
            if sk not in seen:
                seen.add(sk)
                result.append({"stop_name": sname, "lat": slat, "lng": slng, "distance_to_dest_km": round(self._hav((slat, slng), (dest_lat, dest_lng)), 3)})
        return result

    def get_travel_time_between(self, from_stop: str, to_stop: str, route_filter: str = None) -> float | None:
        """Estimate travel time in minutes between two stops on the same route
        using average of actual GTFS stop_times differences."""
        from_resolved = self._resolve_name(from_stop)
        to_resolved = self._resolve_name(to_stop)
        if not from_resolved or not to_resolved:
            return None
        fk = from_resolved.strip().lower()
        tk = to_resolved.strip().lower()

        from_times = self._stop_times.get(from_resolved, [])
        to_times = self._stop_times.get(to_resolved, [])
        if not from_times or not to_times:
            return None

        def _to_sec(t):
            parts = t.split(':')
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2]) if len(parts) == 3 else 0

        route_diffs = {}
        for dep_time, rn in from_times:
            if route_filter and rn != route_filter.upper() and route_filter.upper() not in rn:
                continue
            f_sec = _to_sec(dep_time)
            for to_time, rn2 in to_times:
                if rn2 != rn:
                    continue
                t_sec = _to_sec(to_time)
                diff = (t_sec - f_sec) % 86400
                if 30 <= diff <= 7200:
                    if rn not in route_diffs:
                        route_diffs[rn] = []
                    route_diffs[rn].append(diff)

        all_diffs = []
        for rn, diffs in route_diffs.items():
            if diffs:
                all_diffs.extend(diffs)
        if not all_diffs:
            return None
        avg = sum(all_diffs) / len(all_diffs)
        return avg / 60

    def get_stop_coords(self, stop_name: str):
        """Get (lat, lng) for a GTFS stop."""
        resolved = self._resolve_name(stop_name)
        if not resolved:
            return None
        coords = self._stops_by_name.get(resolved)
        if coords:
            return (coords[0], coords[1])
        return None

    def resolve_name(self, name: str) -> str | None:
        """Public method to resolve a stop name to its GTFS key."""
        return self._resolve_name(name)

    def get_route_operating_hours(self, route_number: str) -> dict:
        """Get first and last departure times for a route across all stops.
        Returns {first_departure, last_departure} or empty dict if no data."""
        rn = route_number.strip().upper()
        times = self._stop_times_by_route.get(rn, [])
        if not times:
            return {}
        all_secs = []
        for dep_time, _ in times:
            secs = _time_to_seconds(dep_time)
            if 0 <= secs < 86400:
                all_secs.append(secs)
        if not all_secs:
            return {}
        first_sec = min(all_secs)
        last_sec = max(all_secs)
        def _fmt(s):
            h = s // 3600
            m = (s % 3600) // 60
            return f"{h:02d}:{m:02d}"
        return {
            "first_departure": _fmt(first_sec),
            "last_departure": _fmt(last_sec),
        }

    def get_route_schedule_status(self, route_number: str, current_time_str: str = None) -> dict:
        """Check whether a bus route is currently operating.
        Returns {is_running, first_bus, last_bus, next_departure, message}."""
        hours = self.get_route_operating_hours(route_number)
        if not hours:
            return {"is_running": True, "message": "", "schedule_known": False}
        now = _now()
        current_sec = now.hour * 3600 + now.minute * 60 + now.second
        first_sec = _time_to_seconds(hours["first_departure"] + ":00")
        last_sec = _time_to_seconds(hours["last_departure"] + ":00")
        is_running = first_sec <= current_sec <= last_sec
        # Find next departure
        times = self._stop_times_by_route.get(route_number.strip().upper(), [])
        next_dep = None
        for dep_time, _ in sorted(times, key=lambda x: x[0]):
            if _time_to_seconds(dep_time) >= current_sec:
                next_dep = dep_time
                break
        msg = ""
        if not is_running:
            if current_sec < first_sec:
                msg = f"First bus on this route is at {hours['first_departure']}"
            else:
                msg = f"Last bus on this route was at {hours['last_departure']}"
        return {
            "is_running": is_running,
            "first_bus": hours["first_departure"],
            "last_bus": hours["last_departure"],
            "next_departure": next_dep,
            "message": msg,
            "schedule_known": True,
        }

gtfs_loader = GTFSLoader()
