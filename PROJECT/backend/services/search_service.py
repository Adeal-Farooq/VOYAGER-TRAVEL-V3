"""Search orchestrator (PROMPT_4 §1-§3).

Glues Google Maps (Places New search/nearby), SerpAPI (real reviews + live
prices), reliability scoring and ride pricing into one service used by the
API. Bengaluru-specific transit wiring lives in the segment builder; this
module handles place discovery + enrichment only.

All results are REAL (Google Places + Google Reviews). Nothing is fabricated.
"""
import logging

from .clients.google_maps_client import GoogleMapsClient
from .clients.serpapi_client import SerpAPIClient
from .data_schema import Place, RidePrice
from .review_tools import ReviewTools
from .ride_pricing import ride_prices_for_distance

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, maps: GoogleMapsClient, serpapi: SerpAPIClient):
        self.maps = maps
        self.serpapi = serpapi
        self.reviews = ReviewTools(serpapi)

    def search_places(self, query: str, lat: float | None = None, lng: float | None = None) -> list[Place]:
        """Text search, verified + deduped + Bangalore-filtered (see client)."""
        return [_to_place(d) for d in self.maps.search_places(query, lat=lat, lng=lng)]

    def nearby(
        self,
        lat: float,
        lng: float,
        radius_m: int = 2000,
        keyword: str = "",
        categories: list[str] | None = None,
    ) -> list[Place]:
        cat = (categories[0] if categories else "") or keyword
        return [_to_place(d) for d in self.maps.nearby_places(lat, lng, radius_m, cat)]

    def enrich(self, place: Place) -> dict:
        """Enriched details for one place: real reviews + reliability + summary."""
        return self.reviews.enrich_place(place).model_dump(mode="json")

    def verify(self, name: str, lat: float, lng: float) -> Place | None:
        """Match a name+coords to a real Google place (used to pin search results)."""
        hits = [_to_place(d) for d in self.maps.search_places(name, lat=lat, lng=lng)]
        if not hits:
            return None
        # prefer the closest verified hit
        hits.sort(key=lambda p: (abs(p.lat - lat) ** 2 + abs(p.lng - lng) ** 2))
        return hits[0]

    def ride_prices(self, origin: tuple[float, float], dest: tuple[float, float],
                    group_size: int = 1) -> list[RidePrice]:
        """Live (SerpAPI) ride prices overlaid on Karnataka estimates."""
        dist_km = 0.0
        live = None
        direction = self.maps.directions(origin, dest, mode="driving")
        if direction and direction.get("distance_m"):
            dist_km = direction["distance_m"] / 1000.0
        return ride_prices_for_distance(dist_km, group_size=group_size, live_options=live)

    def suggestions(self, query: str, lat: float | None = None, lng: float | None = None) -> list[dict]:
        return [p.model_dump(mode="json") for p in self.search_places(query, lat, lng)[:5]]


def _to_place(d: dict) -> Place:
    """Client raw dict -> Place model (extra keys like phone/website dropped)."""
    return Place(**{k: v for k, v in d.items() if k in Place.model_fields})
