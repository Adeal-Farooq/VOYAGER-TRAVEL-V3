"""GraphHopper HTTP client for road routing (PROMPT_1 §4.4).

Local Docker container exposes car + foot profiles. route() returns None on
timeout/connection error — the caller falls back to an interpolated path and
must FLAG it (path_source: "interpolated"). Road routes are cached in memory
for 24h keyed by (mode, rounded coords) so repeated origin/dest pairs never
re-hit the service.
"""
import logging
import threading
import time
from typing import Literal

import requests

from .data_schema import GHResult

logger = logging.getLogger(__name__)

_RND = 4  # round coords to 4 decimals (~11m) for the cache key
_TTL_S = 24 * 3600
_DEFAULT_TIMEOUT = 3.0


class GraphHopperClient:
    def __init__(self, base_url: str = "http://localhost:8080", timeout_s: float = _DEFAULT_TIMEOUT):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._cache: dict[tuple, tuple[float, GHResult | None]] = {}
        self._lock = threading.Lock()

    # --------------------------------------------------------------- cache
    def _cached(self, key: tuple) -> GHResult | None | object:
        now = time.time()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < _TTL_S:
                return hit[1]
            if hit:
                self._cache.pop(key, None)
        return _MISS

    def _store(self, key: tuple, result: GHResult | None) -> None:
        with self._lock:
            self._cache[key] = (time.time(), result)

    # --------------------------------------------------------------- API
    def route(
        self,
        mode: Literal["car", "foot"],
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
    ) -> GHResult | None:
        key = (mode, _r4(lat1), _r4(lng1), _r4(lat2), _r4(lng2))
        cached = self._cached(key)
        if cached is not _MISS:
            return cached
        try:
            resp = requests.get(
                f"{self._base}/route",
                params=[
                    ("profile", mode),
                    ("point", f"{lat1},{lng1}"),
                    ("point", f"{lat2},{lng2}"),
                    ("points_encoded", "false"),
                ],
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            path = data["paths"][0]
            pts = [(p[1], p[0]) for p in path.get("points", {}).get("coordinates", [])]
            result = GHResult(
                geometry=pts,
                distance_m=float(path.get("distance", 0.0)),
                duration_s=float(path.get("time", 0.0)) / 1000.0,
                mode=mode,
                path_source="graphhopper",
            )
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("[graphhopper] route(%s) failed: %s", mode, exc)
            result = None
        self._store(key, result)
        return result

    def is_healthy(self) -> bool:
        try:
            resp = requests.get(f"{self._base}/info", timeout=self._timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False


_MISS = object()


def _r4(v: float) -> float:
    return round(v, _RND)
