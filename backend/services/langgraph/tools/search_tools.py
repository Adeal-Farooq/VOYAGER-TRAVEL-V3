"""Search tools for LangGraph agents."""

import logging
from backend.services.clients.serpapi_client import serpapi_client

logger = logging.getLogger(__name__)
from backend.services.clients.reddit_client import reddit_client
from backend.services.scrapers.ddg_scraper import ddg_scraper


async def search_places(query: str, lat: float = None, lng: float = None, limit: int = 8) -> list[dict]:
    """Search for places using SerpAPI (Google Maps) with Reddit fallback."""
    # Primary: SerpAPI
    results = await serpapi_client.search_places(query, lat, lng, limit)
    if results:
        return results

    # Fallback: Reddit
    reddit_results = await reddit_client.search_places(query, limit=limit)
    if reddit_results:
        return [
            {
                "name": r.get("title", ""),
                "address": "",
                "rating": r.get("score", 0) / 100 if r.get("score") else 0,
                "reviews": r.get("num_comments", 0),
                "source": "reddit",
                "review_summary": r.get("selftext", "")[:200],
            }
            for r in reddit_results
        ]

    # Final fallback: DuckDuckGo
    web_results = await ddg_scraper.search(f"{query} Bangalore", limit)
    if web_results:
        return [
            {
                "name": r.get("title", ""),
                "address": "",
                "rating": 0,
                "reviews": 0,
                "source": "web",
                "review_summary": r.get("snippet", "")[:200],
                "url": r.get("url", ""),
            }
            for r in web_results
        ]

    return []


async def search_nearby(lat: float, lng: float, place_type: str, radius: float = 2.0, limit: int = 8) -> list[dict]:
    """Search for nearby places by type and location."""
    results = await serpapi_client.nearby_places(lat, lng, place_type, radius, limit)
    if results:
        return results
    return []


async def get_suggestions(query: str, lat: float = None, lng: float = None, limit: int = 5) -> list[str]:
    """Get autocomplete suggestions for a partial query."""
    suggestions = set()

    # Try SerpAPI Google Maps autocomplete
    if serpapi_client.api_key:
        import urllib.parse
        params = {
            "engine": "google_maps",
            "q": query,
            "api_key": serpapi_client.api_key,
            "hl": "en",
            "gl": "in",
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://serpapi.com/search", params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("local_results", [])[:limit]:
                        name = r.get("title", "")
                        if name and len(name) > 3:
                            suggestions.add(name)
        except Exception as e:
            logger.warning(f"SerpAPI suggestions failed for '{query}': {e}")

    # Fallback: Reddit suggestions
    if len(suggestions) < limit:
        reddit_results = await reddit_client.search_places(query, limit=limit)
        for r in reddit_results:
            title = r.get("title", "").split("?")[0].split(":")[0][:40]
            if title and len(title) > 3:
                suggestions.add(title)

    return list(suggestions)[:limit]
