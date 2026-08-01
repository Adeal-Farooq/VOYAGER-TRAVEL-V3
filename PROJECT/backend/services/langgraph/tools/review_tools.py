"""Tool: reviews (PROMPT_5 §2.2 tools/review_tools.py).

Real SerpAPI reviews + reliability for a destination POI. Degrades to base
place on failure — never fabricated.
"""
from __future__ import annotations

from ...data_schema import Place
from ...review_tools import ReviewTools


class ReviewTool:
    def __init__(self, reviews: ReviewTools | None = None):
        from ...clients.serpapi_client import SerpAPIClient

        self._reviews = reviews or ReviewTools(SerpAPIClient())

    def name(self) -> str:
        return "reviews"

    def run(self, place: Place) -> dict:
        return self._reviews.enrich_place(place).model_dump(mode="json")
