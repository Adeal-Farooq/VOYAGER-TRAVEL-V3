"""Open-Meteo weather client (PROMPT_5 §3).

Free, no API key. Returns current + short-term forecast for route coords.
Cache 15 min. None/neutral on failure — weather is a best-effort TOPSIS input,
never a gate.
"""
import logging
import time

import requests

from ... import config

logger = logging.getLogger(__name__)

_BASE = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 4.0
_TTL_S = 15 * 60
_RND = 3  # ~110m grid, plenty for weather


class WeatherClient:
    def __init__(self, timeout_s: float = _TIMEOUT):
        self._timeout = timeout_s
        self._cache: dict[str, tuple[float, dict | None]] = {}

    def current(self, lat: float, lng: float) -> dict | None:
        """Current weather + rain-in-next-hour at a point. None on failure."""
        key = f"{round(lat, _RND)}:{round(lng, _RND)}"
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < _TTL_S:
            return hit[1]
        try:
            resp = requests.get(_BASE, params={
                "latitude": lat,
                "longitude": lng,
                "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m,is_day",
                "minutely_15": "precipitation_probability",
                "forecast_minutely_15": 8,
                "timezone": "auto",
            }, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            # rain within next hour = max precip prob over the 15-min window
            rain_next_hour = False
            probs = data.get("minutely_15", {}).get("precipitation_probability", [])
            if probs:
                rain_next_hour = any((p or 0) >= 30 for p in probs[:4])
            out = {
                "temp_c": current.get("temperature_2m"),
                "condition": _weather_code_label(current.get("weather_code")),
                "weather_code": current.get("weather_code"),
                "humidity": current.get("relative_humidity_2m"),
                "wind_kmh": current.get("wind_speed_10m"),
                "is_day": bool(current.get("is_day", 1)),
                "rain_next_hour": rain_next_hour,
                "source": "open-meteo",
            }
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[weather] current(%s,%s) failed: %s", lat, lng, exc)
            out = None
        self._cache[key] = (time.time(), out)
        return out


def _weather_code_label(code) -> str:
    """Open-Meteo WMO code -> plain label."""
    if code is None:
        return "unknown"
    if code == 0:
        return "clear"
    if code <= 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 80, 81, 82):
        return "drizzle"
    if code in (61, 63, 65, 66, 67):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "thunderstorm"
    return "unknown"
