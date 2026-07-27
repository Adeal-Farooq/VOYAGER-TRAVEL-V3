import logging
import httpx
import urllib.parse
from typing import Any

logger = logging.getLogger(__name__)
from backend.core.config import settings


PLACE_TYPES_MAP = {
    "atm": "ATM",
    "hospital": "Hospital",
    "mall": "Shopping Mall",
    "restaurant": "Restaurant",
    "hotel": "Hotel",
    "pharmacy": "Pharmacy",
    "school": "School",
    "college": "College",
    "police_station": "Police Station",
    "fire_station": "Fire Station",
    "bus_stop": "Bus Stop",
    "metro_station": "Metro Station",
    "railway_station": "Railway Station",
    "park": "Park",
    "gym": "Gym",
    "bank": "Bank",
    "supermarket": "Supermarket",
    "cinema": "Cinema",
    "petrol_pump": "Petrol Pump",
    "mosque": "Mosque",
    "temple": "Temple",
    "church": "Church",
}


class SerpAPIClient:
    """Fetch real Google reviews, ratings, photos via SerpAPI."""

    def __init__(self):
        self.api_key = settings.SERPAPI_API_KEY
        self.base_url = "https://serpapi.com/search"

    async def search_places(
        self, query: str, lat: float = None, lng: float = None, limit: int = 8
    ) -> list[dict]:
        """Search places on Google Maps via SerpAPI."""
        if not self.api_key:
            return []

        params: dict[str, Any] = {
            "engine": "google_maps",
            "q": query,
            "api_key": self.api_key,
            "hl": "en",
            "gl": "in",
            "type": "search",
            "num": limit,
        }
        if lat and lng:
            params["ll"] = f"@{lat},{lng},14z"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_places(data.get("local_results", []))
        except Exception as e:
            logger.warning(f"SerpAPI search_places failed for '{query}': {e}")
            return []

    async def nearby_places(
        self, lat: float, lng: float, place_type: str = "", radius: float = 2.0,
        limit: int = 8
    ) -> list[dict]:
        """Find nearby places by type."""
        query = place_type.replace("_", " ") if place_type else "places"
        params: dict[str, Any] = {
            "engine": "google_maps",
            "q": query,
            "api_key": self.api_key,
            "hl": "en",
            "gl": "in",
            "type": "search",
            "num": limit,
            "ll": f"@{lat},{lng},{14 - int(radius / 2)}z",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_places(data.get("local_results", []))
        except Exception as e:
            logger.warning(f"SerpAPI nearby_places failed for {place_type} at {lat},{lng}: {e}")
            return []

    async def place_details(self, place_id: str) -> dict | None:
        """Fetch reviews and photos for a specific place."""
        params = {
            "engine": "google_maps",
            "api_key": self.api_key,
            "hl": "en",
            "gl": "in",
            "type": "place",
            "place_id": place_id,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return self._parse_place_detail(data)
        except Exception as e:
            logger.warning(f"SerpAPI place_details failed for {place_id}: {e}")
            return None

    def _parse_places(self, results: list[dict]) -> list[dict]:
        parsed = []
        for r in results:
            parsed.append({
                "name": r.get("title", ""),
                "address": r.get("address", ""),
                "rating": r.get("rating", 0),
                "reviews": r.get("reviews", 0),
                "reviews_link": r.get("reviews_link", ""),
                "type": r.get("type", ""),
                "phone": r.get("phone", ""),
                "website": r.get("website", ""),
                "lat": r.get("gps_coordinates", {}).get("latitude", 0),
                "lng": r.get("gps_coordinates", {}).get("longitude", 0),
                "thumbnail": (r.get("thumbnail") or ""),
                "place_id": r.get("place_id", ""),
                "operating_hours": r.get("operating_hours", {}),
                "service_options": r.get("service_options", {}),
                "price_range": r.get("price_range", ""),
            })
        return parsed

    def _parse_place_detail(self, data: dict) -> dict | None:
        if not data:
            return None
        place_data = data.get("place_results") or data.get("place") or data.get("local_results", {})
        if not place_data:
            return None

        # Reviews: could be list (old format) or int (count) with actual reviews in user_reviews.most_relevant
        raw_reviews = place_data.get("reviews", [])
        if isinstance(raw_reviews, int):
            user_reviews_data = place_data.get("user_reviews", {})
            if isinstance(user_reviews_data, dict):
                raw_reviews = user_reviews_data.get("most_relevant", []) or []
            else:
                raw_reviews = []
        elif not isinstance(raw_reviews, list):
            raw_reviews = []

        photos_meta = place_data.get("photos", [])

        return {
            "name": place_data.get("title", ""),
            "rating": place_data.get("rating", 0),
            "review_count": place_data.get("reviews", 0) if isinstance(place_data.get("reviews"), int) else len(raw_reviews),
            "reviews": [
                {
                    "author": r.get("username") or r.get("user", {}).get("name", "Anonymous"),
                    "rating": r.get("rating", 0),
                    "text": r.get("description") or r.get("snippet") or r.get("text", ""),
                    "date": r.get("date", ""),
                    "likes": r.get("likes", 0),
                }
                for r in (raw_reviews or [])[:8]
            ],
            "photos": [
                p.get("image", "")
                for p in (photos_meta or [])[:6]
                if p.get("image")
            ],
            "address": place_data.get("address", ""),
            "phone": place_data.get("phone", ""),
            "website": place_data.get("website", ""),
            "price_range": place_data.get("price_range", ""),
            "hours": place_data.get("operating_hours", {}),
            "place_id": place_data.get("place_id", ""),
        }


serpapi_client = SerpAPIClient()
