"""Place reliability scoring (PROMPT_4 §2).

Score = 0.5*(rating/5) + 0.3*sentiment_avg + 0.2*min(1, log1p(count)/log1p(100))
        x business_status_factor

Pin classes:
  green  -> OPERATIONAL / null status, score >= 0.7
  yellow -> score 0.5..0.7 (or CLOSED_TEMPORARILY)
  red    -> CLOSED_PERMANENTLY or score < 0.5

Deterministic, explainable — never fabricated.
"""
import math

from .data_schema import ReliabilityInput, ReliabilityResult

_STATUS_FACTOR = {
    "OPERATIONAL": 1.0,
    "CLOSED_TEMPORARILY": 0.4,
    "CLOSED_PERMANENTLY": 0.0,
}


def _status_factor(status: str | None) -> float:
    if not status:
        return 1.0  # unknown status does not penalize (Google may omit it)
    return _STATUS_FACTOR.get(status.upper(), 1.0)


def compute_reliability(inp: ReliabilityInput) -> ReliabilityResult:
    rating = max(0.0, min(5.0, inp.rating))
    count = max(0, inp.review_count)
    sentiment = max(0.0, min(1.0, inp.sentiment_avg))

    rating_part = 0.5 * (rating / 5.0 if rating else 0.4)
    sentiment_part = 0.3 * sentiment
    count_part = 0.2 * min(1.0, math.log1p(count) / math.log1p(100))
    status_factor = _status_factor(inp.business_status)

    raw = (rating_part + sentiment_part + count_part) * status_factor
    score = max(0.0, min(1.0, raw))
    score_pct = int(round(score * 100))

    if status_factor == 0.0:
        pin_class = "red"
    elif (inp.business_status or "").upper() == "CLOSED_TEMPORARILY":
        pin_class = "yellow"
    elif score >= 0.7 and status_factor >= 0.4:
        pin_class = "green"
    elif score >= 0.5:
        pin_class = "yellow"
    else:
        pin_class = "red"

    return ReliabilityResult(
        score=round(score, 4),
        score_pct=score_pct,
        pin_class=pin_class,
        status_factor=status_factor,
        rating_part=round(rating_part, 4),
        sentiment_part=round(sentiment_part, 4),
        count_part=round(count_part, 4),
    )


def pin_class_of(score: float, business_status: str | None = None) -> str:
    """Quick classifier for a plain score (used by frontend pins)."""
    factor = _status_factor(business_status)
    if factor == 0.0:
        return "red"
    if (business_status or "").upper() == "CLOSED_TEMPORARILY":
        return "yellow"
    if score >= 0.7 and factor >= 0.4:
        return "green"
    if score >= 0.5:
        return "yellow"
    return "red"
