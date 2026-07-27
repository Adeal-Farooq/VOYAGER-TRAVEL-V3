"""News/events tools for LangGraph agents."""

from backend.services.scrapers.news_scraper import news_scraper
from backend.services.clients.reddit_client import reddit_client


async def get_travel_news(
    source: str = "", destination: str = "",
    lat: float = None, lng: float = None,
    limit: int = 5,
) -> list[dict]:
    """Get travel news relevant to a source→destination route."""
    query_parts = []
    if source:
        query_parts.append(source)
    if destination:
        query_parts.append(destination)
    query = " ".join(query_parts) if query_parts else "bangalore travel news"

    return await news_scraper.get_news(query, lat, lng, limit)


async def get_traffic_news(limit: int = 3) -> list[dict]:
    """Get traffic-specific news."""
    return await news_scraper.get_traffic_news(limit)


async def get_area_events(area: str = "", limit: int = 4) -> list[dict]:
    """Get events/activities in an area from Reddit."""
    query = f"{area} bangalore events things to do" if area else "bangalore events this weekend"
    results = await reddit_client.search_places(query, limit=limit)
    events = []
    for r in results:
        title = r.get("title", "")
        selftext = r.get("selftext", "")
        if len(title) > 15:
            events.append({
                "title": title[:150],
                "description": selftext[:200] if selftext else "",
                "url": r.get("url", ""),
                "score": r.get("score", 0),
                "comments": r.get("num_comments", 0),
                "source": "reddit",
            })
    return events
