"""DataImpulse proxy manager (PROMPT_5 §6).

Centralizes an authenticated session for scrapes that get IP-blocked
(Reddit JSON, news sites, DuckDuckGo). NOT used for API-key services
(SerpAPI / Google Maps / Open-Meteo / OpenRouter) — those are authenticated
directly. Scraper I/O goes through this manager only.
"""
import logging

import requests

from .. import config

logger = logging.getLogger(__name__)


class ProxyManager:
    def __init__(self, user: str | None = None, password: str | None = None,
                 host: str | None = None):
        self._user = user if user is not None else config.env_str("DATAIMPULSE_USER")
        self._password = password if password is not None else config.env_str("DATAIMPULSE_PASS")
        self._host = host if host is not None else config.env_str("DATAIMPULSE_HOST", "gw.dataimpulse.com:823")
        self._session: requests.Session | None = None
        if not (self._user and self._password):
            logger.warning("[proxy] DataImpulse credentials missing — scraping degraded")

    @property
    def available(self) -> bool:
        return bool(self._user and self._password)

    def _session_for(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.proxies = {
                "http": f"http://{self._user}:{self._password}@{self._host}",
                "https": f"http://{self._user}:{self._password}@{self._host}",
            }
            self._session.headers.update({"User-Agent": "Mozilla/5.0 (VOYAGER news engine)"})
        return self._session

    def get(self, url: str, timeout: float = 10.0, retries: int = 2, **kwargs) -> requests.Response | None:
        """GET through the proxy with a small retry/backoff. None on total failure."""
        if not self.available:
            logger.warning("[proxy] skipping %s — no proxy credentials", url)
            return None
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._session_for().get(url, timeout=timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < retries:
                    import time

                    time.sleep(0.5 * (attempt + 1))
        logger.warning("[proxy] GET %s failed after %d retries: %s", url, retries, last_exc)
        return None
