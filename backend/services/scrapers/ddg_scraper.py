"""DuckDuckGo web scraper with proxy support."""

import logging, time
import httpx

logger = logging.getLogger(__name__)
from bs4 import BeautifulSoup
from backend.services.proxy_manager import proxy_manager


class DuckDuckGoScraper:
    """Search DuckDuckGo for reviews, news, and web content.

    Uses rotating proxies, user-agents, and 5-min result cache to avoid blocks.
    """

    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300

    async def search(
        self, query: str, max_results: int = 5, use_proxy: bool = True
    ) -> list[dict]:
        ck = f"{query}|{max_results}"
        now = time.time()
        cached = self._cache.get(ck)
        if cached and now - cached["ts"] < self._cache_ttl:
            return cached["data"]

        proxies_to_try = ["html", "lite"]
        for attempt in proxies_to_try:
            try:
                if attempt == "html":
                    result = await self._search_html(query, max_results, use_proxy)
                else:
                    result = await self._scrape_lite(query, max_results)
                if result:
                    self._cache[ck] = {"data": result, "ts": now}
                    return result
            except Exception as e:
                logger.debug(f"DDG {attempt} failed for '{query}': {e}")
                continue

        self._cache[ck] = {"data": [], "ts": now}
        return []

    async def _search_html(self, query, max_results, use_proxy):
        proxy = await proxy_manager.get_proxy(tier=2 if use_proxy else 1)
        headers = proxy_manager.get_headers()
        headers["Referer"] = "https://duckduckgo.com/"

        async with httpx.AsyncClient(
            timeout=12.0, proxies=proxy, verify=False
        ) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
            )

            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for result in soup.select(".result")[:max_results]:
                title_el = result.select_one(".result__title a")
                snippet_el = result.select_one(".result__snippet")
                url_el = result.select_one(".result__url")
                if title_el:
                    href = title_el.get("href", "")
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": self._clean_url(href),
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        "domain": url_el.get_text(strip=True) if url_el else "",
                        "source": "duckduckgo",
                    })
            return results if results else None

    async def _scrape_with_browser(self, query: str, max_results: int) -> list[dict]:
        """Fallback: scrape DuckDuckGo lite (simpler HTML)."""
        return await self._scrape_lite(query, max_results)

    async def _scrape_lite(self, query: str, max_results: int) -> list[dict]:
        """DuckDuckGo Lite version — very simple HTML, hard to block."""
        results = []
        headers = proxy_manager.get_headers()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers=headers,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for link in soup.select('a[href^="http"]')[:max_results]:
                        text = link.get_text(strip=True)
                        if text and len(text) > 10:
                            results.append({
                                "title": text[:150],
                                "url": link.get("href", ""),
                                "snippet": "",
                                "source": "duckduckgo_lite",
                            })
        except Exception as e:
            logger.warning(f"DuckDuckGo Lite search failed for '{query}': {e}")

        return results

    @staticmethod
    def _clean_url(url: str) -> str:
        """Extract actual URL from DuckDuckGo redirect."""
        if "uddg=" in url:
            import urllib.parse
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            return parsed.get("uddg", [""])[0]
        return url


ddg_scraper = DuckDuckGoScraper()
