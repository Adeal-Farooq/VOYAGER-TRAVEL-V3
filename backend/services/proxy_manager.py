import logging
import random
import httpx
from backend.core.config import settings

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manages rotating proxies for web scraping.

    Tier 1: Free proxy lists (limited, rate-limited use)
    Tier 2: DataImpulse residential proxies (paid, $5/5GB)
    Tier 3: Direct connection (no proxy - for APIs like Reddit, Google Maps API)
    """

    def __init__(self):
        self._free_proxies: list[dict] = []
        self._free_index = 0
        self._last_fetch = 0

        # DataImpulse config — set these in .env
        self.dataimpulse_user = settings.DATAIMPULSE_USER or ""
        self.dataimpulse_pass = settings.DATAIMPULSE_PASS or ""
        self.dataimpulse_host = settings.DATAIMPULSE_HOST or ""

    async def get_proxy(self, tier: int = 1) -> dict | None:
        """Get a proxy. Tier 1=free, Tier 2=DataImpulse, Tier 3=None (direct)."""
        if tier >= 3:
            return None

        if tier == 2 and self.dataimpulse_user:
            return {
                "http": f"http://{self.dataimpulse_user}:{self.dataimpulse_pass}@{self.dataimpulse_host}",
                "https": f"http://{self.dataimpulse_user}:{self.dataimpulse_pass}@{self.dataimpulse_host}",
            }

        # Tier 1: Free proxies
        if not self._free_proxies:
            await self._fetch_free_proxies()
        if not self._free_proxies:
            return None

        proxy = self._free_proxies[self._free_index % len(self._free_proxies)]
        self._free_index += 1
        return {
            "http": f"http://{proxy['ip']}:{proxy['port']}",
            "https": f"http://{proxy['ip']}:{proxy['port']}",
        }

    async def _fetch_free_proxies(self):
        """Fetch free proxy list (updated every 5 min)."""
        import time
        if time.time() - self._last_fetch < 300:
            return

        sources = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        ]

        for url in sources:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, headers={"User-Agent": "curl/8.0"})
                    if resp.status_code == 200:
                        lines = resp.text.strip().splitlines()[:50]
                        for line in lines:
                            parts = line.strip().split(":")
                            if len(parts) == 2:
                                self._free_proxies.append({"ip": parts[0], "port": parts[1]})
            except Exception as e:
                logger.warning(f"Proxy fetch failed for {url}: {e}")
                continue

        self._last_fetch = time.time()

    @staticmethod
    def get_headers() -> dict:
        """Random User-Agent rotation."""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return {
            "User-Agent": random.choice(agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

proxy_manager = ProxyManager()
