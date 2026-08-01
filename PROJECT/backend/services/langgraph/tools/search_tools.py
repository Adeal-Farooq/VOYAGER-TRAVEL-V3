"""Tool: search + geo (PROMPT_5 §2.2 tools/search_tools.py, geo_tools.py).

search_tools: places search, suggestions, place-details (real Google Places).
geo_tools: geocode, nearby, reverse-geocode.
"""
from __future__ import annotations

from ...clients.google_maps_client import GoogleMapsClient
from ...clients.serpapi_client import SerpAPIClient
from ...search_service import SearchService, _to_place
from ...data_schema import Place


class SearchTool:
    def __init__(self, search: SearchService | None = None):
        self._search = search or SearchService(GoogleMapsClient(), SerpAPIClient())

    def name(self) -> str:
        return "search"

    def run(self, query: str, lat: float | None = None, lng: float | None = None) -> list[dict]:
        return [p.model_dump(mode="json") for p in self._search.search_places(query, lat, lng)]

    def place_details(self, place_id: str) -> dict | None:
        return self._search.enrich(Place(place_id=place_id, name="", lat=0.0, lng=0.0))


class GeoTool:
    def __init__(self, maps: GoogleMapsClient | None = None):
        self._maps = maps or GoogleMapsClient()

    def name(self) -> str:
        return "geo"

    def geocode(self, query: str) -> dict | None:
        return self._maps.geocode(query)

    def nearby(self, lat: float, lng: float, radius_m: int = 2000, category: str = "") -> list[dict]:
        return self._maps.nearby_places(lat, lng, radius_m, category)

    def reverse_geocode(self, lat: float, lng: float) -> dict | None:
        return self._maps.geocode(f"{lat},{lng}")
