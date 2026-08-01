"""News engine (PROMPT_5 §4) — background refresh loop + cached serving.

Loop every NEWS_INTERVAL_MIN (default 8) minutes:
1. Scrape r/bangalore (Reddit JSON via proxy) + Karnataka news via DDG fallback.
2. Classify each item: traffic | weather | event | general.
3. Geo-tag when a known locality/landmark appears -> lat/lng (map marker).
4. LLM summarize each item into <=2 lines (allowed: summary only).
5. Dedup by normalized title, keep max 25, TTL 4h.

Serving: GET /api/search/news?lat=&lng= filters by relevance (geo proximity +
keyword match), sorted by recency. Cache served even when the loop fails; the
UI shows an "Offline" state rather than fake headlines.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone

import requests

from .. import config
from .proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

_TTL_S = 4 * 3600
_MAX_ITEMS = 25
_RND = 3

# Known Bangalore localities/landmarks -> coords (geo-tagging table)
_LOCALITIES = {
    "sil board": (12.9166, 77.6210),
    "majestic": (12.9767, 77.5713),
    "mg road": (12.9758, 77.6065),
    "cubbon park": (12.9767, 77.5929),
    "indiranagar": (12.9719, 77.6412),
    "koramangala": (12.9352, 77.6245),
    "whitefield": (12.9698, 77.7500),
    "electronic city": (12.8452, 77.6602),
    "hebbal": (13.0358, 77.5970),
    "yeshvantpur": (13.0208, 77.5456),
    "rajajinagar": (12.9915, 77.5550),
    "jayanagar": (12.9250, 77.5938),
    "marathahalli": (12.9588, 77.7060),
    "hebbal flyover": (13.0358, 77.5970),
    "outer ring road": (12.9700, 77.6400),
    "namma metro": (12.9716, 77.5946),
    "kempegowda": (12.9611, 77.6393),
    "bannerghatta": (12.8837, 77.6050),
    "hsr layout": (12.9117, 77.6339),
    "bellandur": (12.9298, 77.6745),
    "silk board": (12.9166, 77.6210),
    "byatarayanapura": (13.0333, 77.6167),
    "sarjapur": (12.9123, 77.6676),
    "ecity": (12.8452, 77.6602),
}

_CLASSIFY_KEYWORDS = {
    "traffic": ["traffic", "jam", "congestion", "accident", "road closed", "diversion",
                "snarl", "gridlock", "crashed", "pile-up", "metro delay", "bus strike"],
    "weather": ["rain", "flood", "storm", "cloudburst", "thunderstorm", "heatwave",
                "waterlogging", "drizzle", "downpour"],
    "event": ["festival", "concert", "match", "rally", "protest", "mela", "exhibition",
              "marathon", "fair", "parade"],
}


class NewsEngine:
    def __init__(self, proxy: ProxyManager | None = None, interval_min: int = 8):
        self._proxy = proxy or ProxyManager()
        self._interval_min = interval_min
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._last_run = 0.0
        self._running = False
        self._stop = False
        self._thread: threading.Thread | None = None

    # ---------------------------------------------------------------- store
    def _dedup(self, items: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out = []
        for it in items:
            key = " ".join(it.get("title", "").lower().split())[:80]
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    def _merge(self, fresh: list[dict]) -> None:
        with self._lock:
            combined = fresh + [it for it in self._items
                                if it["title"] not in {f["title"] for f in fresh}]
            now = time.time()
            combined = [it for it in combined if now - it.get("ts", now) < _TTL_S]
            combined.sort(key=lambda it: it.get("ts", 0), reverse=True)
            self._items = combined[:_MAX_ITEMS]

    # ---------------------------------------------------------------- loop
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="news-loop")
        self._thread.start()
        logger.info("[news] background refresh loop started (every %d min)", self._interval_min)

    def stop(self) -> None:
        self._stop = True
        self._running = False

    def _loop(self) -> None:
        while not self._stop:
            try:
                self.refresh_once()
            except Exception as exc:  # noqa: BLE001 — loop must never die
                logger.warning("[news] refresh failed: %s", exc)
            time.sleep(self._interval_min * 60)

    def refresh_once(self) -> int:
        """Scrape + classify + tag + summarize. Returns item count."""
        items = []
        items += self._scrape_reddit()
        items += self._scrape_news_fallback()
        items = self._dedup(items)
        for it in items:
            it["category"] = self._classify(it.get("title", ""))
            geo = self._geo_tag(it.get("title", "") + " " + it.get("text", ""))
            it["geo"] = geo
        self._merge(items)
        self._last_run = time.time()
        return len(self._items)

    # ---------------------------------------------------------------- sources
    def _scrape_reddit(self) -> list[dict]:
        out = []
        url = "https://www.reddit.com/r/bangalore/new.json?limit=25"
        resp = self._proxy.get(url, timeout=10)
        if resp is None:
            return out
        try:
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                title = d.get("title", "").strip()
                if not title:
                    continue
                out.append({
                    "title": title,
                    "text": (d.get("selftext") or "")[:400],
                    "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                    "source": "r/bangalore",
                    "ts": time.time(),
                })
        except (ValueError, KeyError) as exc:
            logger.warning("[news] reddit parse failed: %s", exc)
        return out

    def _scrape_news_fallback(self) -> list[dict]:
        """DuckDuckGo news search via proxy (Karnataka/Bangalore queries)."""
        out = []
        for query in ("Bangalore traffic today", "Karnataka rain alert", "Bengaluru news"):
            items = self._ddg_news(query)
            if items:
                out.extend(items)
        return out

    def _ddg_news(self, query: str) -> list[dict]:
        try:
            resp = self._proxy.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "ia": "news"},
                timeout=10)
            if resp is None:
                return []
            html = resp.text
            titles = []
            import re

            for m in re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.S)[:8]:
                clean = re.sub(r"<[^>]+>", "", m).strip()
                if clean:
                    titles.append(clean)
            return [{"title": t, "text": "", "url": "",
                     "source": "news-aggregate", "ts": time.time()} for t in titles]
        except Exception as exc:  # noqa: BLE001
            logger.warning("[news] ddg(%s) failed: %s", query, exc)
            return []

    # ---------------------------------------------------------------- enrich
    def _classify(self, text: str) -> str:
        low = text.lower()
        for cat, keys in _CLASSIFY_KEYWORDS.items():
            if any(k in low for k in keys):
                return cat
        return "general"

    def _geo_tag(self, text: str) -> dict | None:
        low = text.lower()
        for name, (lat, lng) in _LOCALITIES.items():
            if name in low:
                return {"name": name, "lat": lat, "lng": lng}
        return None

    def summarize_items(self, llm) -> None:
        """LLM-summarize each unsaved item (≤2 lines). Never blocks serving."""
        for it in self._items:
            if it.get("summary"):
                continue
            if not it.get("text") and not it.get("title"):
                continue
            try:
                res = llm.chat_json(
                    "Summarize this Bengaluru news item in <=2 lines, JSON {\"summary\": str}.",
                    f"Title: {it['title']}\nBody: {it.get('text','')}")
                if res and res.get("summary"):
                    it["summary"] = res["summary"][:220]
            except Exception as exc:  # noqa: BLE001
                logger.warning("[news] summarize failed: %s", exc)
        self._merge([])  # persist summaries

    # ---------------------------------------------------------------- serving
    def relevant(self, lat: float | None = None, lng: float | None = None,
                 keyword: str = "", limit: int = 10) -> list[dict]:
        """Items filtered by geo proximity + keyword, newest first."""
        with self._lock:
            items = list(self._items)
        if keyword:
            kw = keyword.lower()
            items = [it for it in items if kw in it["title"].lower()]
        if lat is not None and lng is not None:
            def dist(it):
                g = it.get("geo")
                if not g:
                    return float("inf")
                return _haversine_km(lat, lng, g["lat"], g["lng"])
            items.sort(key=lambda it: (dist(it) == float("inf"), dist(it)))
        else:
            items.sort(key=lambda it: it.get("ts", 0), reverse=True)
        for it in items:
            it.setdefault("summary", "")
        return items[:limit]


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
