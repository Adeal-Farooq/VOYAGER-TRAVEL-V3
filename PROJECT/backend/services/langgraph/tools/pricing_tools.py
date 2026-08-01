"""Tool: pricing (PROMPT_5 §2.2 tools/pricing_tools.py).

Real ride prices via ride_pricing (live SerpAPI + Karnataka estimates labeled).
"""
from __future__ import annotations

from ...ride_pricing import ride_prices_for_distance
from ...clients.google_maps_client import GoogleMapsClient


class PricingTool:
    def __init__(self, maps: GoogleMapsClient | None = None):
        self._maps = maps or GoogleMapsClient()

    def name(self) -> str:
        return "pricing"

    def run(self, origin: tuple[float, float], dest: tuple[float, float],
            group_size: int = 1) -> list[dict]:
        dist_km = 0.0
        live = None
        direction = self._maps.directions(origin, dest, mode="driving")
        if direction and direction.get("distance_m"):
            dist_km = direction["distance_m"] / 1000.0
        return [p.model_dump(mode="json") for p in
                ride_prices_for_distance(dist_km, group_size=group_size, live_options=live)]
