"""Tool: news (PROMPT_5 §2.2 tools/news_tools.py)."""
from __future__ import annotations

from ...news_engine import NewsEngine


class NewsTool:
    def __init__(self, engine: NewsEngine | None = None):
        self._engine = engine or NewsEngine()

    def name(self) -> str:
        return "news"

    def run(self, lat: float | None = None, lng: float | None = None,
            keyword: str = "", limit: int = 10) -> list[dict]:
        return self._engine.relevant(lat=lat, lng=lng, keyword=keyword, limit=limit)
