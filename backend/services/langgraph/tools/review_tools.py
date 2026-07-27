"""Review analysis tools for LangGraph agents — with caching, clean fallback chain."""

import logging, time
from backend.services.clients.serpapi_client import serpapi_client
from backend.core.config import settings

logger = logging.getLogger(__name__)
from backend.services.clients.reddit_client import reddit_client
from backend.services.scrapers.google_reviews_scraper import google_reviews_scraper

_REVIEW_CACHE = {}
_CACHE_TTL = 3600

def _cache_key(name, address):
    return f"{name.lower().strip()}|{(address or '').lower().strip()}"

def _get_cached(key):
    entry = _REVIEW_CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None

def _set_cache(key, data):
    _REVIEW_CACHE[key] = {"data": data, "ts": time.time()}

async def get_place_reviews(name: str, address: str = None) -> dict | None:
    """Get real reviews for a place with caching and clean fallback chain."""
    ck = _cache_key(name, address)
    cached = _get_cached(ck)
    if cached is not None:
        return cached

    addr = address or f"{name}, Bengaluru"

    # 1. SerpAPI (Google Reviews) — primary source
    if serpapi_client.api_key:
        try:
            places = await serpapi_client.search_places(f"{name} {addr}", limit=1)
            if places:
                pid = places[0].get("place_id")
                if pid:
                    detail = await serpapi_client.place_details(pid)
                    if detail and detail.get("reviews") is not None:
                        raw = detail["reviews"]
                        if raw:
                            result = {
                                "rating": detail["rating"],
                                "reviews": raw,
                                "review_summary": _summarize_reviews(raw),
                                "photos": detail.get("photos", []),
                                "source": "google_maps",
                                "is_recommended": detail.get("rating", 0) >= 3.5,
                                "reliability_score": min(1.0, detail.get("review_count", 10) / 100) if detail.get("review_count") else 0.5,
                            }
                            _set_cache(ck, result)
                            return result
        except Exception as e:
            logger.warning(f"SerpAPI review search failed for {name}: {e}")

    # 2. Google Places API (direct, no justdial wrapper)
    if settings.GOOGLE_MAPS_API_KEY:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                search_resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={"query": f"{name} {addr}", "key": settings.GOOGLE_MAPS_API_KEY, "region": "in", "language": "en"},
                )
                if search_resp.status_code == 200:
                    search_data = search_resp.json()
                    if search_data.get("status") == "OK" and search_data.get("results"):
                        place = search_data["results"][0]
                        pid = place.get("place_id")
                        rating = place.get("rating", 0)
                        if pid:
                            details_resp = await client.get(
                                "https://maps.googleapis.com/maps/api/place/details/json",
                                params={"place_id": pid, "key": settings.GOOGLE_MAPS_API_KEY,
                                        "fields": "name,rating,reviews,photos,formatted_address", "language": "en", "region": "in"},
                            )
                            if details_resp.status_code == 200:
                                result = details_resp.json().get("result", {})
                                raw_reviews = result.get("reviews", [])
                                parsed = [{
                                    "author": r.get("author_name", "Anonymous"),
                                    "rating": r.get("rating", 0),
                                    "text": r.get("text", ""),
                                    "date": r.get("relative_time_description", ""),
                                    "source": "google_places_api",
                                } for r in raw_reviews[:5]]
                                if parsed:
                                    photos = [
                                        f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={p['photo_reference']}&key={settings.GOOGLE_MAPS_API_KEY}"
                                        for p in (result.get("photos", []) or [])[:3]
                                    ]
                                    result_data = {
                                        "rating": rating or 0,
                                        "reviews": parsed,
                                        "review_summary": _summarize_reviews(parsed),
                                        "photos": photos,
                                        "source": "google_places_api",
                                        "is_recommended": rating >= 3.5 if rating else True,
                                        "reliability_score": min(1.0, len(raw_reviews) / 10) if raw_reviews else 0.5,
                                    }
                                    _set_cache(ck, result_data)
                                    return result_data
        except Exception as e:
            logger.warning(f"Google Places API failed for {name}: {e}")

    # 3. Reddit reviews
    reviews_data = []
    try:
        reddit_results = await reddit_client.search_places(f"{name} review", limit=4)
        for r in reddit_results:
            top_comments = r.get("top_comments", [])
            for comment in top_comments:
                reviews_data.append({
                    "author": comment.get("author", "RedditUser"),
                    "rating": 0, "text": comment.get("body", ""), "date": "", "source": "reddit",
                })
            selftext = r.get("selftext", "")
            if selftext and not reviews_data:
                reviews_data.append({
                    "author": r.get("author", "RedditUser"),
                    "rating": 0, "text": selftext[:300], "date": "", "source": "reddit",
                })
    except Exception as e:
        logger.warning(f"Reddit review search failed for {name}: {e}")

    if reviews_data:
        avg_rating = sum(r.get("rating", 3) for r in reviews_data if r.get("rating", 0) > 0) / max(len([r for r in reviews_data if r.get("rating", 0) > 0]), 1)
        result = {
            "rating": avg_rating or 3.5,
            "reviews": reviews_data[:8],
            "review_summary": _summarize_reviews(reviews_data),
            "photos": [],
            "source": "mixed",
            "is_recommended": avg_rating >= 3.0,
            "reliability_score": min(0.7, len(reviews_data) / 10),
        }
        _set_cache(ck, result)
        return result

    # 4. Last resort: DuckDuckGo web fallback
    try:
        from backend.services.scrapers.ddg_scraper import ddg_scraper
        snippets = await ddg_scraper.search(f"{name} reviews Bangalore", max_results=4)
        if snippets:
            parsed = [{"author": "Web", "rating": 0, "text": s.get("snippet", "")[:300], "date": "", "source": "duckduckgo"}
                      for s in snippets if s.get("snippet") and len(s["snippet"]) > 30]
            if parsed:
                result = {
                    "rating": 0, "reviews": parsed,
                    "review_summary": parsed[0]["text"][:150],
                    "photos": [], "source": "web_fallback",
                    "is_recommended": False, "reliability_score": 0.3,
                }
                _set_cache(ck, result)
                return result
    except Exception as e:
        logger.warning(f"DuckDuckGo fallback failed for {name}: {e}")

    _set_cache(ck, None)
    return None


async def get_place_photos(name: str) -> list[str]:
    """Get photos for a place."""
    if serpapi_client.api_key:
        detail = await serpapi_client.place_details(name)
        if detail and detail.get("photos"):
            return detail["photos"]
    return []


def _summarize_reviews(reviews: list[dict]) -> str:
    if not reviews:
        return ""
    texts = [r.get("text", "") for r in reviews if r.get("text")]
    if not texts:
        return ""
    positives = [t for t in texts if any(w in t.lower() for w in ["good", "great", "nice", "excellent", "clean", "friendly", "recommend", "best"])]
    negatives = [t for t in texts if any(w in t.lower() for w in ["bad", "poor", "dirty", "expensive", "rude", "worst", "avoid", "crowded"])]
    parts = []
    if positives:
        parts.append(f"Praised for: {positives[0][:120]}")
    if negatives:
        parts.append(f"Criticized for: {negatives[0][:120]}")
    return " | ".join(parts) if parts else (texts[0][:200] if texts else "")
