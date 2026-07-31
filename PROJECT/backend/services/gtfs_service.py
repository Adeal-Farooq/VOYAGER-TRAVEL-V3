"""GTFS loader + cache + fuzzy name resolution for VOYAGER v2 (PROMPT_1 §4.1).

The committed 67MB pickle (DATA_FOLDER/processed/gtfs_cache.pkl) is REUSED —
never re-derive on startup. Raw GTFS load is a cold-path fallback only and
saves the pickle once.

Pickle structure (as committed):
    shapes: dict[shape_id] -> list[(lat, lng)]
    route_shapes: dict[route_name] -> list[shape_id]
    stop_to_shapes: dict[stop_name] -> list[(shape_id, seq)]
    stops_by_name: dict[stop_name] -> (lat, lng, stop_id)
    stop_times: dict[stop_name] -> list[(HH:MM:SS, route_name)]
    stop_times_by_route: dict[route_name] -> list[(HH:MM:SS, stop_name)]
    name_map: dict[master_stop_name] -> resolved_gtfs_name   (built on first run)
    route_id_to_name: dict[route_id] -> route_name (cleaned)

All times are schedule times. BMTC has no official live API — every departure
is labelled source: "schedule".
"""
import csv
import re
import time
from difflib import get_close_matches
from pathlib import Path
from typing import Iterable

from .data_schema import GtfsStop, RouteDeparture
from .. import config

_NORM_WS = re.compile(r"\s+")
_TRASH_NAME = {"", "nan", "none", "null", "n/a", "na"}


def _normalize(name: str) -> str:
    return _NORM_WS.sub(" ", str(name).strip().lower())


def clean_route_short_name(raw: str) -> str:
    """Strip terminal garbage from a route name.

    "MF-28 JKLO-ISROQ-LGRNB" -> "MF-28", "  242-LA " -> "242-LA".
    A trailing token is kept only if it contains a digit (e.g. "BEL GS-16",
    "KSRTC-T NARASIPURA-1" are real route names).
    """
    name = _NORM_WS.sub(" ", str(raw).strip())
    tokens = name.split(" ")
    while len(tokens) > 1 and not re.search(r"\d", tokens[-1]):
        tokens.pop()
    return " ".join(tokens)


class GTFSService:
    def __init__(self, cache_path: Path = config.GTFS_CACHE_PATH):
        self._cache_path = Path(cache_path)
        self._data: dict | None = None
        self._resolve_cache: dict[str, str | None] = {}
        self._word_index: dict[str, set[str]] | None = None
        self._termini_cache: dict[str, str] = {}
        self._shape_stops: dict[str, list[tuple[int, str]]] | None = None

    # ------------------------------------------------------------- loading
    @property
    def data(self) -> dict:
        if self._data is None:
            self.load()
        return self._data

    def load(self) -> None:
        if self._cache_path.is_file():
            try:
                t0 = time.perf_counter()
                with open(self._cache_path, "rb") as fh:
                    self._data = pickle_load(fh)
                print(f"[gtfs] loaded pickle {self._cache_path.name} in {time.perf_counter() - t0:.2f}s")
                self._rebuild_name_map()
                return
            except Exception as exc:  # corrupt cache -> fall through to raw load
                print(f"[gtfs] pickle load failed ({exc}); rebuilding from raw GTFS")
        self._load_raw_gtfs()
        self.save_pickle()

    def save_pickle(self, path: Path | None = None) -> None:
        import pickle

        target = Path(path) if path else self._cache_path
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            pickle.dump(self._data, fh, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[gtfs] saved pickle -> {target}")

    def _rebuild_name_map(self) -> None:
        """Persist name_map from master stop CSV if not already in the pickle."""
        if self._data.get("name_map"):
            return
        self._data["name_map"] = self._resolve_master_names()
        try:
            self.save_pickle()
        except Exception as exc:  # never fatal
            print(f"[gtfs] could not persist name_map ({exc})")

    def _resolve_master_names(self) -> dict[str, str]:
        names = self._master_stop_names()
        t0 = time.perf_counter()
        resolved: dict[str, str] = {}
        for raw in names:
            got = self._fast_fuzzy_match(raw)
            if got:
                resolved[_normalize(raw)] = got
        print(f"[gtfs] pre-resolved {len(resolved)}/{len(names)} master stop names in "
              f"{time.perf_counter() - t0:.2f}s")
        return resolved

    def _master_stop_names(self) -> list[str]:
        try:
            with open(config.BUS_STOPS_MASTER_PATH, encoding="utf-8-sig") as fh:
                return [r["Stop Name"] for r in csv.DictReader(fh)]
        except FileNotFoundError:
            return []

    # ------------------------------------------------------------ raw load
    def _load_raw_gtfs(self) -> None:
        """Cold path: parse raw GTFS txt files, build the same structure.

        Runs once (~40s), then the pickle carries everything.
        """
        base = config.GTFS_RAW_FOLDER
        t0 = time.perf_counter()
        stops_by_name: dict[str, tuple[float, float, str]] = {}
        route_id_to_name: dict[str, str] = {}
        trip_route: dict[str, str] = {}
        trip_shape: dict[str, str] = {}
        trip_times: dict[str, list[tuple[str, str, str, str]]] = {}  # trip -> rows
        shapes: dict[str, list[tuple[float, float]]] = {}

        for row in csv.DictReader(open(base / "stops.txt", encoding="utf-8")):
            name = _normalize(row["stop_name"])
            if name in _TRASH_NAME:
                continue
            stops_by_name.setdefault(name, (float(row["stop_lat"]), float(row["stop_lon"]), row["stop_id"]))

        for row in csv.DictReader(open(base / "routes.txt", encoding="utf-8")):
            route_id_to_name[row["route_id"]] = clean_route_short_name(row.get("route_short_name", ""))

        for row in csv.DictReader(open(base / "trips.txt", encoding="utf-8")):
            trip_route[row["trip_id"]] = route_id_to_name.get(row["route_id"], row["route_id"])
            trip_shape[row["trip_id"]] = row.get("shape_id", "")

        for row in csv.DictReader(open(base / "stop_times.txt", encoding="utf-8")):
            trip_times.setdefault(row["trip_id"], []).append(
                (row["stop_sequence"], row["stop_id"], row.get("departure_time", ""),
                 row.get("arrival_time", ""))
            )

        for row in csv.DictReader(open(base / "shapes.txt", encoding="utf-8")):
            shapes.setdefault(row["shape_id"], []).append(
                (float(row["shape_pt_lat"]), float(row["shape_pt_lon"])))
        # shapes.txt is emitted in pt_sequence order already; keep as read.

        stop_times: dict[str, list[tuple[str, str]]] = {}
        stop_times_by_route: dict[str, list[tuple[str, str]]] = {}
        stop_to_shapes: dict[str, list[tuple[str, str, int]]] = {}
        route_shapes: dict[str, set[str]] = {}

        id_to_name = {sid: name for name, (_lat, _lng, sid) in stops_by_name.items()}
        for trip_id, rows in trip_times.items():
            route = trip_route.get(trip_id, "")
            shape_id = trip_shape.get(trip_id, "")
            rows.sort(key=lambda r: int(r[0]))
            for idx, (_seq, stop_id, dep, _arr) in enumerate(rows):
                stop_name = id_to_name.get(stop_id)
                if not stop_name:
                    continue
                if dep:
                    stop_times.setdefault(stop_name, []).append((dep, route))
                    stop_times_by_route.setdefault(route, []).append((dep, stop_name))
                if shape_id:
                    stop_to_shapes.setdefault(stop_name, []).append((shape_id, idx))
                    route_shapes.setdefault(route, set()).add(shape_id)

        self._data = {
            "shapes": shapes,
            "route_shapes": {k: sorted(v) for k, v in route_shapes.items()},
            "stop_to_shapes": stop_to_shapes,
            "stops_by_name": stops_by_name,
            "stop_times": stop_times,
            "stop_times_by_route": stop_times_by_route,
            "name_map": {},
            "route_id_to_name": route_id_to_name,
        }
        self._rebuild_name_map()
        print(f"[gtfs] raw load done in {time.perf_counter() - t0:.2f}s")

    # ------------------------------------------------------------ queries
    def get_stops(self) -> list[GtfsStop]:
        out = []
        for name, (lat, lng, sid) in self.data["stops_by_name"].items():
            out.append(GtfsStop(id=sid, name=name, lat=lat, lng=lng))
        return out

    def get_shape_path(self, shape_id: str) -> list[tuple[float, float]] | None:
        return self.data["shapes"].get(shape_id)

    def resolve_stop_name(self, name: str) -> str | None:
        norm = _normalize(name)
        if norm in self._resolve_cache:
            return self._resolve_cache[norm]
        got = self._resolve_stop_name_inner(norm)
        self._resolve_cache[norm] = got
        return got

    def _resolve_stop_name_inner(self, norm: str) -> str | None:
        stops = self.data["stops_by_name"]
        if norm in stops:
            return norm
        mapped = self.data.get("name_map", {}).get(norm)
        if mapped and mapped in stops:
            return mapped
        return self._fast_fuzzy_match(norm)

    def _fast_fuzzy_match(self, name: str) -> str | None:
        stops = self.data["stops_by_name"]
        if not stops:
            return None
        norm = _normalize(name)
        if norm in stops:
            return norm
        words = set(w for w in norm.split(" ") if len(w) > 2)
        if not words:
            return None
        idx = self._word_index or self._build_word_index()
        best: str | None = None
        best_score = 0.0
        for w in words:
            for candidate in idx.get(w, ()):
                overlap = len(words & candidate[1])
                score = overlap / (len(candidate[1]) + len(words) - overlap + 1e-9)
                if score > best_score:
                    best_score = score
                    best = candidate[0]
        if best and best_score >= 0.5:
            return best
        trig = {norm[i : i + 3] for i in range(max(0, len(norm) - 2))}
        if trig:
            pool = [s for s in stops if trig & {s[i : i + 3] for i in range(max(0, len(s) - 2))}]
            cands = get_close_matches(norm, pool, n=1, cutoff=0.80)
            if cands:
                return cands[0]
        if len(norm) >= 4:
            for s in stops:
                if norm in s:
                    return s
        return None

    def _build_word_index(self) -> dict[str, list[tuple[str, set[str]]]]:
        stops = self.data["stops_by_name"]
        idx: dict[str, list[tuple[str, set[str]]]] = {}
        for s in stops:
            sw = {w for w in s.split(" ") if len(w) > 2}
            for w in sw:
                idx.setdefault(w, []).append((s, sw))
        self._word_index = idx
        return idx

    def get_routes_at_stop(
        self, stop_name: str, after_time: str | None = None
    ) -> list[RouteDeparture]:
        resolved = self.resolve_stop_name(stop_name)
        if not resolved:
            return []
        after_min = _to_minutes(after_time) if after_time else None
        out: list[RouteDeparture] = []
        for time_str, route in self.data["stop_times"].get(resolved, ()):
            mins = _to_minutes(time_str)
            if after_min is not None and mins < after_min:
                continue
            shape_ids = self.data["route_shapes"].get(route, ())
            out.append(
                RouteDeparture(
                    route_id=route,
                    route_number=route,
                    stop_name=resolved,
                    scheduled_departure=time_str,
                    departure_minutes=mins,
                    destination_name=self._route_terminus(route),
                    trip_id="",
                    shape_id=shape_ids[0] if shape_ids else "",
                )
            )
        out.sort(key=lambda d: (d.departure_minutes, d.route_number))
        return out

    def _route_terminus(self, route: str) -> str:
        if route in self._termini_cache:
            return self._termini_cache[route]
        term = ""
        for shape_id in self.data["route_shapes"].get(route, ()):
            shape_stops = self._shape_stops_index().get(shape_id)
            if shape_stops:
                term = shape_stops[-1][1]
                break
        self._termini_cache[route] = term
        return term

    def _shape_stops_index(self) -> dict[str, list[tuple[int, str]]]:
        if self._shape_stops is not None:
            return self._shape_stops
        idx: dict[str, list[tuple[int, str]]] = {}
        for stop_name, entries in self.data["stop_to_shapes"].items():
            for shape_id, seq in entries:
                idx.setdefault(shape_id, []).append((seq, stop_name))
        for shape_id in idx:
            idx[shape_id].sort(key=lambda t: t[0])
        self._shape_stops = idx
        return idx

    def get_stop_to_stop_segment(
        self, route_id: str, from_stop_name: str, to_stop_name: str
    ) -> list[tuple[float, float]] | None:
        """Slice the bus shape between two stops on the same route trip.

        Stops are projected onto each candidate shape (nearest vertex within
        threshold); the polyline between the two projected indices is returned.
        The committed stop_to_shapes seq is a trip stop-position, NOT a shape
        point index — so we never slice by it.

        Returns None when both stops land on no shape of this route — the
        caller must flag it (never fall back to drawing the full route).
        """
        frm = self.resolve_stop_name(from_stop_name)
        to = self.resolve_stop_name(to_stop_name)
        if not frm or not to:
            return None
        fcoords = self.data["stops_by_name"].get(frm)
        tcoords = self.data["stops_by_name"].get(to)
        if not fcoords or not tcoords:
            return None
        fl, flng, tl, tlng = fcoords[0], fcoords[1], tcoords[0], tcoords[1]
        best: tuple[float, list[tuple[float, float]]] | None = None
        for shape_id in self.data["route_shapes"].get(route_id, ()):
            pts = self.data["shapes"].get(shape_id)
            if not pts:
                continue
            a, da = _project_on_shape(pts, fl, flng)
            b, db = _project_on_shape(pts, tl, tlng)
            if da <= _PROJ_M and db <= _PROJ_M and a != b:
                seg = list(pts[a : b + 1]) if a < b else list(reversed(pts[b : a + 1]))
                if len(seg) >= 2:
                    worst = max(da, db)
                    if best is None or worst < best[0]:
                        best = (worst, seg)
        return best[1] if best else None


_PROJ_M = 400.0  # max stop->shape nearest-vertex distance to accept a match


def _hav(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _project_on_shape(pts: list[tuple[float, float]], lat: float, lng: float) -> tuple[int, float]:
    """Return (index of nearest vertex, distance in metres)."""
    best_i, best_d = 0, float("inf")
    for i, (plat, plng) in enumerate(pts):
        d = _hav(lat, lng, plat, plng)
        if d < best_d:
            best_d = d
            best_i = i
    return best_i, best_d


def _to_minutes(hhmmss: str | None) -> int:
    if not hhmmss:
        return 0
    parts = hhmmss.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    s = int(parts[2]) if len(parts) > 2 else 0
    return h * 60 + m + (1 if s else 0)


def pickle_load(fh) -> dict:
    import pickle

    return pickle.load(fh)
