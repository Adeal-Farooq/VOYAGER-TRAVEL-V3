import logging
import httpx
import random
from typing import Any

logger = logging.getLogger(__name__)


SUB_REDDITS = ["bangalore", "bengaluru", "indiantravel", "india", "bmtc", "IndianAutos"]


class RedditClient:
    """Fetch real reviews, news, travel insights from Reddit.

    Uses public JSON API — no auth needed for reads.
    60 req/min limit, generous.
    """

    def __init__(self):
        self.base_url = "https://www.reddit.com"
        self.session = None

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=10.0,
            headers={
                "User-Agent": random.choice([
                    "VOYAGER/1.0 (India Transit Navigator; +https://github.com/voyager)",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "VOYAGER-BLR/1.0",
                ]),
                "Accept": "application/json",
            },
        )

    async def search_places(
        self, query: str, subreddit: str = "bangalore", limit: int = 5
    ) -> list[dict]:
        """Search for place reviews, recommendations on Reddit."""
        url = f"{self.base_url}/r/{subreddit}/search.json"
        params: dict[str, Any] = {
            "q": query,
            "limit": limit,
            "restrict_sr": "1",
            "sort": "relevance",
            "t": "all",
        }

        async with await self._get_client() as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    return await self._search_across_subreddits(query, limit)
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                return await self._enrich_posts(posts, limit)
            except Exception as e:
                logger.warning(f"Reddit search failed for '{query}': {e}")
                return await self._search_across_subreddits(query, limit)

    async def _search_across_subreddits(
        self, query: str, limit: int = 3
    ) -> list[dict]:
        """Fallback: search across multiple Bengaluru-related subreddits."""
        all_results = []
        for sub in SUB_REDDITS[:4]:
            if len(all_results) >= limit:
                break
            url = f"{self.base_url}/r/{sub}/search.json"
            params = {"q": query, "limit": 2, "restrict_sr": "1", "sort": "relevance"}
            async with await self._get_client() as client:
                try:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        posts = data.get("data", {}).get("children", [])
                        enriched = await self._enrich_posts(posts, 2)
                        all_results.extend(enriched)
                except Exception as e:
                    logger.warning(f"Reddit subreddit search failed for '{query}' in r/{sub}: {e}")
                    continue
        return all_results[:limit]

    async def get_news(self, query: str = "bangalore traffic", limit: int = 5) -> list[dict]:
        """Get latest news from Reddit."""
        url = f"{self.base_url}/r/bangalore/search.json"
        params = {
            "q": query,
            "limit": limit,
            "restrict_sr": "1",
            "sort": "new",
            "t": "week",
        }
        async with await self._get_client() as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("data", {}).get("children", [])
                    results = []
                    for post in posts[:limit]:
                        pdata = post.get("data", {})
                        results.append({
                            "title": pdata.get("title", ""),
                            "score": pdata.get("score", 0),
                            "num_comments": pdata.get("num_comments", 0),
                            "url": f"https://reddit.com{pdata.get('permalink', '')}",
                            "created_utc": pdata.get("created_utc", 0),
                            "selftext": pdata.get("selftext", "")[:300],
                            "subreddit": pdata.get("subreddit", ""),
                            "author": pdata.get("author", ""),
                        })
                    return results
            except Exception as e:
                logger.warning(f"Reddit news fetch failed for '{query}': {e}")
                return []

    async def get_travel_insights(
        self, source: str = "", destination: str = "", limit: int = 4
    ) -> list[dict]:
        """Get travel insights for source→destination route."""
        queries = []
        if source and destination:
            queries.append(f"{source} to {destination} travel")
            queries.append(f"how to go from {source} to {destination} bangalore")
        elif destination:
            queries.append(f"{destination} travel tips bangalore")
            queries.append(f"visiting {destination} bangalore review")

        results = []
        for q in queries:
            batch = await self.search_places(q, limit=3)
            results.extend(batch)
            if len(results) >= limit:
                break
        return results[:limit]

    async def _enrich_posts(self, posts: list[dict], limit: int) -> list[dict]:
        """Convert Reddit API posts to standard format, with top comment."""
        results = []
        for post in posts[:limit]:
            pdata = post.get("data", {})
            entry = {
                "title": pdata.get("title", ""),
                "score": pdata.get("score", 0),
                "num_comments": pdata.get("num_comments", 0),
                "url": f"https://reddit.com{pdata.get('permalink', '')}",
                "created_utc": pdata.get("created_utc", 0),
                "selftext": pdata.get("selftext", "")[:400],
                "subreddit": pdata.get("subreddit", ""),
                "author": pdata.get("author", ""),
                "top_comments": [],
            }
            # Fetch top comment
            permalink = pdata.get("permalink", "")
            if permalink:
                try:
                    async with await self._get_client() as client2:
                        comment_url = f"{self.base_url}{permalink}.json"
                        resp2 = await client2.get(comment_url)
                        if resp2.status_code == 200:
                            comment_data = resp2.json()
                            if len(comment_data) > 1:
                                comments = comment_data[1].get("data", {}).get("children", [])
                                top_comments = []
                                for c in comments[:2]:
                                    cdata = c.get("data", {})
                                    if cdata.get("body"):
                                        top_comments.append({
                                            "body": cdata["body"][:300],
                                            "score": cdata.get("score", 0),
                                            "author": cdata.get("author", ""),
                                        })
                                entry["top_comments"] = top_comments
                except Exception as e:
                    logger.warning(f"Reddit comment fetch failed for {permalink}: {e}")
            results.append(entry)
        return results


reddit_client = RedditClient()
