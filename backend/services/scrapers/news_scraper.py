"""Multi-source news scraper for Bengaluru-specific news."""

import httpx, logging
from backend.services.clients.reddit_client import reddit_client
from backend.services.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)


class NewsScraper:
    """Aggregate news from:
    - Reddit r/bangalore (primary)
    - DuckDuckGo search for TOI/The Hindu (replaces fragile URL scraping)
    """

    async def get_news(
        self, query: str = "", lat: float = None, lng: float = None,
        limit: int = 5
    ) -> list[dict]:
        """Get latest Bengaluru news from all sources."""
        all_news = []
        seen_urls = set()

        # 1. Reddit (primary)
        try:
            reddit_news = await reddit_client.get_news(query or "bangalore traffic news", limit)
            for item in reddit_news:
                if item.get("url") not in seen_urls:
                    seen_urls.add(item["url"])
                    item["source_type"] = "reddit"
                    all_news.append(item)
        except Exception as e:
            logger.warning(f"Reddit news failed: {e}")

        # 2. DuckDuckGo News search (replaces fragile TOI/The Hindu URL scraping)
        try:
            web_news = await self._search_via_ddg(query or "bangalore", limit)
            for item in web_news:
                if item.get("url") not in seen_urls:
                    seen_urls.add(item["url"])
                    item["source_type"] = "web"
                    all_news.append(item)
        except Exception as e:
            logger.warning(f"DDG news search failed: {e}")

        all_news.sort(key=lambda x: x.get("score", 0) if x.get("source_type") == "reddit" else 0, reverse=True)
        return all_news[:limit]

    async def _search_via_ddg(self, query: str, limit: int) -> list[dict]:
        """Search news using DuckDuckGo (bypasses fragile direct site scraping)."""
        from backend.services.scrapers.ddg_scraper import ddg_scraper
        search_query = f"{query} site:timesofindia.indiatimes.com OR site:thehindu.com OR site:deccanherald.com"
        results = await ddg_scraper.search(search_query, max_results=limit, use_proxy=True)
        return [
            {
                "title": r.get("title", "")[:200],
                "url": r.get("href", ""),
                "score": 0,
                "num_comments": 0,
                "source": r.get("source", "Web"),
            }
            for r in results if r.get("title") and len(r.get("title", "")) > 20
        ]

    async def get_traffic_news(self, limit: int = 3) -> list[dict]:
        """Get traffic-specific news."""
        return await self.get_news("bangalore traffic road jam", limit)

    async def get_event_news(
        self, area: str = "", limit: int = 3
    ) -> list[dict]:
        """Get area-specific event news."""
        query = f"bangalore {area} event news" if area else "bangalore events"
        return await self.get_news(query, limit)


news_scraper = NewsScraper()
