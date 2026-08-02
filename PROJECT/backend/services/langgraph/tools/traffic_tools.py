"""Tool: traffic (PROMPT_5 §2.2 tools/traffic_tools.py).

Real number: Google Directions duration_in_traffic / duration ratio, plus
corridor-relevant traffic news alerts. When Directions is down it delegates
to the PROMPT_7 time-of-day crowd model (`TrafficSlowdownModel`) — a real
curve trained on traffic_logs.csv, never a fabricated ratio.
"""
from __future__ import annotations

from ...clients.google_maps_client import GoogleMapsClient
from ...traffic_model import TrafficSlowdownModel


class TrafficTool:
    def __init__(self, maps: GoogleMapsClient | None = None,
                 model: TrafficSlowdownModel | None = None):
        self._maps = maps or GoogleMapsClient()
        self._model = model or TrafficSlowdownModel()

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
        # PROMPT_7 time-of-day crowd model fallback (labeled, real curve)
        ratio = self._model.predict_slowdown(origin[0], origin[1])
        label = "heavy" if ratio >= 1.3 else ("moderate" if ratio >= 1.1 else "light")
        return {
            "ratio": ratio,
            "label": label,
            "source": "time_of_day_model (Directions unavailable)",
            "alerts": [a["title"] for a in news_alerts if a.get("category") == "traffic"][:3],
        }
