"""Tool: pricing (PROMPT_5 §2.2 tools/pricing_tools.py).

Real ride prices via ride_pricing (live SerpAPI + Karnataka estimates labeled).
"""
from __future__ import annotations

from ...ride_pricing import fetch_live_prices, ride_prices_for_distance
from ...clients.google_maps_client import GoogleMapsClient
from ...clients.serpapi_client import SerpAPIClient


class PricingTool:
    def __init__(self, maps: GoogleMapsClient | None = None,
                 serpapi: SerpAPIClient | None = None):
        self._maps = maps or GoogleMapsClient()
        self._serpapi = serpapi or SerpAPIClient()

    def name(self) -> str:
        return "pricing"

    def run(self, origin: tuple[float, float], dest: tuple[float, float],
            group_size: int = 1) -> list[dict]:
        dist_km = 0.0
        direction = self._maps.directions(origin, dest, mode="driving")
        if direction and direction.get("distance_m"):
            dist_km = direction["distance_m"] / 1000.0
        live, live_km = fetch_live_prices(self._serpapi, origin, dest)
        if not dist_km and live_km:
            dist_km = live_km
        return [p.model_dump(mode="json") for p in
                ride_prices_for_distance(dist_km, group_size=group_size, live_options=live)]
