"""Tool: weather (PROMPT_5 §2.2 tools/weather_tools.py)."""
from __future__ import annotations

from ...clients.weather_client import WeatherClient


class WeatherTool:
    def __init__(self, client: WeatherClient | None = None):
        self._client = client or WeatherClient()

    def name(self) -> str:
        return "weather"

    def run(self, lat: float, lng: float) -> dict:
        """Current weather + rain-next-hour at a point. {} on failure."""
        return self._client.current(lat, lng) or {}
