"""Place review pipeline (PROMPT_4 §2.3).

Chain: search_places -> place_id -> SerpAPI place_details (real Google Reviews)
       -> top-2-per-star sample -> reliability score -> LLM summary.

Golden rule: reviews are REAL (SerpAPI). The LLM only *summarizes* what the
reviews actually say — it never writes reviews, ratings, or scores. On any
failure the result degrades to what is known (possibly empty reviews), never
to fabricated data.
"""
import logging
from typing import Any

from .clients.serpapi_client import SerpAPIClient
from .data_schema import Place, PlaceDetails, ReliabilityInput, Review
from .reliability import compute_reliability
from .sentiment import sentiment_avg

logger = logging.getLogger(__name__)

_REVIEW_CACHE_VERSION = 2  # bump to invalidate stale cache entries


class ReviewTools:
    def __init__(self, serpapi: SerpAPIClient):
        self._serpapi = serpapi
        self._cache: dict[str, PlaceDetails] = {}

    def enrich_place(self, place: Place, max_reviews: int = 24) -> PlaceDetails:
        """Turn a search Place into enriched PlaceDetails (reviews + reliability)."""
        if not place.place_id:
            return self._degrade(place, "no place_id")
        cached = self._cache.get(place.place_id)
        if cached:
            return cached
        detail = self._serpapi.place_details(place.place_id)
        if not detail:
            return self._degrade(place, "serpapi unavailable")

        reviews = [Review(**{k: r.get(k, v) for k, v in Review().model_dump().items() if k in r})
                   for r in detail.get("reviews", [])][:max_reviews]
        if not reviews and detail.get("user_rating_count"):
            # real count exists but Google returned no review bodies -> honest empty list
            logger.info("[reviews] %s: count=%s but no review bodies from SerpAPI",
                        place.name, detail.get("user_rating_count"))

        sentiment = sentiment_avg([r.text for r in reviews]) if reviews else 0.5
        rel = compute_reliability(ReliabilityInput(
            rating=detail.get("rating") or place.rating or 0.0,
            review_count=detail.get("user_rating_count") or place.user_rating_count or len(reviews),
            sentiment_avg=sentiment,
            business_status=detail.get("business_status") or place.business_status,
        ))

        summary, concerns = self._summarize(reviews, rel.score_pct)

        out = PlaceDetails(
            **place.model_dump(exclude={"place_id"}),
            place_id=place.place_id,
            phone=detail.get("phone"),
            website=detail.get("website"),
            reviews=reviews,
            sentiment_avg=round(sentiment, 3),
            reliability_score=rel.score_pct,
            pin_class=rel.pin_class,
            summary=summary,
            concerns=concerns,
        )
        self._cache[place.place_id] = out
        return out

    def _summarize(self, reviews: list[Review], score_pct: int) -> tuple[str, list[str]]:
        """LLM summary of REAL reviews; empty strings when unavailable.

        The summary text may mention review themes; numbers come only from the
        actual review objects. If no LLM key, return a deterministic headline.
        """
        texts = [r.text for r in reviews if r.text.strip()]
        if not texts:
            return "", []
        try:
            from ..agents import review_summarizer

            result = review_summarizer.summarize(texts, score_pct)
            if result:
                return result.summary, result.concerns
        except Exception as exc:  # noqa: BLE001 — optional
            logger.warning("[reviews] LLM summary unavailable: %s", exc)
        return f"Based on {len(reviews)} Google reviews (reliability {score_pct}%).", []

    @staticmethod
    def _degrade(place: Place, reason: str) -> PlaceDetails:
        logger.info("[reviews] %s: %s — returning base place", place.name, reason)
        return PlaceDetails(**place.model_dump(), reliability_score=None, pin_class="yellow")
