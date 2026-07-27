"""JustDial-compatible scraper using Google Places API (since JustDial blocks all scrapers)."""

import httpx, logging
from backend.core.config import settings

logger = logging.getLogger(__name__)


class JustDialScraper:
    """Replaces JustDial scraping with Google Places API.
    
    JustDial's website blocks httpx requests even with proxies.
    Google Places API provides the same data (name, address, phone, rating, reviews)
    without IP blocking since it's API-key authenticated.
    """

    async def search(
        self, query: str, city: str = "Bangalore", limit: int = 5
    ) -> list[dict]:
        """Search for businesses matching query via Google Places API."""
        if not settings.GOOGLE_MAPS_API_KEY:
            logger.warning("No GOOGLE_MAPS_API_KEY configured for JustDial fallback")
            return []

        results = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={
                        "query": f"{query} in {city}",
                        "key": settings.GOOGLE_MAPS_API_KEY,
                        "region": "in",
                        "language": "en",
                    },
                )
                if resp.status_code != 200:
                    return results

                data = resp.json()
                if data.get("status") != "OK":
                    return results

                for place in data.get("results", [])[:limit]:
                    results.append({
                        "name": place.get("name", ""),
                        "url": f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id', '')}",
                        "rating": place.get("rating", 0),
                        "phone": place.get("formatted_phone_number", ""),
                        "address": (place.get("formatted_address", "") or place.get("vicinity", ""))[:150],
                        "place_id": place.get("place_id", ""),
                        "source": "google_places_api",
                        "price_level": place.get("price_level"),
                        "types": place.get("types", []),
                    })

        except Exception as e:
            logger.warning(f"Google Places API search failed for {query}: {e}")

        return results

    async def get_reviews(self, store_url: str, limit: int = 5) -> list[dict]:
        """Fetch reviews for a specific place via Google Places API."""
        if not settings.GOOGLE_MAPS_API_KEY:
            return []

        place_id = self._extract_place_id(store_url)
        if not place_id:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/details/json",
                    params={
                        "place_id": place_id,
                        "key": settings.GOOGLE_MAPS_API_KEY,
                        "fields": "reviews",
                        "language": "en",
                        "region": "in",
                    },
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                result = data.get("result", {})
                reviews = result.get("reviews", [])

                return [
                    {
                        "author": r.get("author_name", "Anonymous"),
                        "rating": r.get("rating", 0),
                        "text": r.get("text", ""),
                        "date": r.get("relative_time_description", ""),
                        "source": "google_places_api",
                    }
                    for r in reviews[:limit]
                ]

        except Exception as e:
            logger.warning(f"Google Places API reviews failed: {e}")

        return []

    def _extract_place_id(self, url: str) -> str | None:
        """Extract place_id from Google Maps URL."""
        if "place_id:" in url:
            return url.split("place_id:")[-1].split("&")[0].split("?")[0]
        return None


justdial_scraper = JustDialScraper()