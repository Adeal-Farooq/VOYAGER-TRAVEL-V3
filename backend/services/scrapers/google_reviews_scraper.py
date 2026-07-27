"""Google Reviews via SerpAPI (primary) + Google Places API (fallback) + DuckDuckGo (last resort)."""

import httpx, logging
from backend.core.config import settings

logger = logging.getLogger(__name__)


class GoogleReviewsScraper:
    async def get_reviews(self, query: str, limit: int = 5) -> dict | None:
        result = await self._try_google_places_api(query)
        if result:
            return result
        result = await self._try_duckduckgo_fallback(query, limit)
        if result:
            return result
        return None

    async def _try_google_places_api(self, query):
        if not settings.GOOGLE_MAPS_API_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Step 1: textSearch to find place_id
                search_resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={
                        "query": query,
                        "key": settings.GOOGLE_MAPS_API_KEY,
                        "region": "in",
                        "language": "en",
                    },
                )
                if search_resp.status_code != 200:
                    return None
                search_data = search_resp.json()
                if search_data.get("status") != "OK" or not search_data.get("results"):
                    return None

                place = search_data["results"][0]
                place_id = place.get("place_id")
                rating = place.get("rating", 0)
                user_ratings_total = place.get("user_ratings_total", 0)

                # Step 2: Place Details for full reviews
                details_resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/details/json",
                    params={
                        "place_id": place_id,
                        "key": settings.GOOGLE_MAPS_API_KEY,
                        "fields": "name,rating,reviews,photos,formatted_address,price_level,opening_hours",
                        "language": "en",
                        "region": "in",
                    },
                )
                if details_resp.status_code != 200:
                    return None
                details_data = details_resp.json()
                result = details_data.get("result", {})
                reviews = result.get("reviews", [])

                if not reviews and user_ratings_total == 0:
                    return None

                parsed_reviews = [
                    {
                        "author": r.get("author_name", "Anonymous"),
                        "rating": r.get("rating", 0),
                        "text": r.get("text", ""),
                        "date": r.get("relative_time_description", ""),
                        "source": "google_places_api",
                    }
                    for r in (reviews or [])[:limit]
                ]

                photos = [
                    f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={p['photo_reference']}&key={settings.GOOGLE_MAPS_API_KEY}"
                    for p in (result.get("photos", []) or [])[:3]
                ]

                return {
                    "rating": rating or 0,
                    "reviews": parsed_reviews,
                    "review_summary": self._summarize(parsed_reviews),
                    "photos": photos,
                    "source": "google_places_api",
                    "is_recommended": rating >= 3.5 if rating else True,
                    "reliability_score": min(1.0, user_ratings_total / 20) if user_ratings_total > 0 else 0.5,
                    "price_level": result.get("price_level"),
                    "address": result.get("formatted_address", ""),
                }
        except Exception as e:
            logger.warning(f"Google Places API failed for {query}: {e}")
        return None

    async def _try_duckduckgo_fallback(self, query, limit):
        try:
            from backend.services.scrapers.ddg_scraper import ddg_scraper
            snippets = await ddg_scraper.search(f"{query} reviews Bangalore", max_results=limit)
            if snippets:
                parsed = [
                    {"author": "Web", "rating": 0, "text": s.get("snippet", "")[:300], "date": "", "source": "duckduckgo"}
                    for s in snippets if s.get("snippet") and len(s["snippet"]) > 30
                ]
                if parsed:
                    return {
                        "rating": 0,
                        "reviews": parsed,
                        "review_summary": parsed[0]["text"][:150],
                        "photos": [],
                        "source": "web_fallback",
                        "is_recommended": False,
                        "reliability_score": 0.3,
                    }
        except Exception as e:
            logger.warning(f"DuckDuckGo fallback failed for {query}: {e}")
        return None

    def _summarize(self, reviews):
        if not reviews:
            return ""
        texts = [r.get("text", "") for r in reviews if r.get("text")]
        if not texts:
            return ""
        positives = [t for t in texts if any(w in t.lower() for w in ["good", "great", "nice", "excellent", "clean", "friendly", "recommend", "best", "amazing", "love"])]
        negatives = [t for t in texts if any(w in t.lower() for w in ["bad", "poor", "dirty", "expensive", "rude", "worst", "avoid", "crowded", "terrible"])]
        parts = []
        if positives:
            parts.append(f"Praised for: {positives[0][:120]}")
        if negatives:
            parts.append(f"Criticized for: {negatives[0][:120]}")
        return " | ".join(parts) if parts else texts[0][:200]


google_reviews_scraper = GoogleReviewsScraper()
