"""Tool: traffic (PROMPT_5 §2.2 tools/traffic_tools.py).

Real number: Google Directions duration_in_traffic / duration ratio, plus
corridor-relevant traffic news alerts. Falls back to a labeled time-of-day
crowd model when Directions is down — never a fabricated ratio.
"""
from __future__ import annotations

from datetime import datetime

from .... import config
from ...clients.google_maps_client import GoogleMapsClient


class TrafficTool:
    def __init__(self, maps: GoogleMapsClient | None = None):
        self._maps = maps or GoogleMapsClient()

    def name(self) -> str:
        return "traffic"

    def run(self, origin: tuple[float, float], dest: tuple[float, float],
            news_alerts: list[dict] | None = None) -> dict:
        direction = self._maps.directions(origin, dest, mode="driving")
        news_alerts = news_alerts or []
        if direction and direction.get("traffic_ratio"):
            ratio = float(direction["traffic_ratio"])
            label = "heavy" if ratio >= 1.3 else ("moderate" if ratio >= 1.1 else "light")
            return {
                "ratio": ratio,
                "label": label,
                "source": "google_directions",
                "alerts": [a["title"] for a in news_alerts if a.get("category") == "traffic"][:3],
            }
        # deterministic time-of-day crowd fallback (labeled)
        hour = datetime.now().hour
        weekday = datetime.now().weekday() < 5
        if weekday and (7 <= hour < 10 or 17 <= hour < 21):
            ratio, label = 1.4, "heavy"
        elif hour >= 22 or hour < 6:
            ratio, label = 1.05, "light"
        else:
            ratio, label = 1.2, "moderate"
        return {
            "ratio": ratio,
            "label": label,
            "source": "time_of_day_model (Directions unavailable)",
            "alerts": [a["title"] for a in news_alerts if a.get("category") == "traffic"][:3],
        }
