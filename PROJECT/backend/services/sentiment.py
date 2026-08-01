"""Review sentiment analysis (PROMPT_4 §2.3).

Primary: deterministic English lexicon scorer (AFINN-165 subset) — honest,
offline, reproducible, no model download. Returns polarity in [0,1].

If `transformers` + a small distilbert SST-2 pipeline is installed it is used
instead (higher quality); otherwise the lexicon is the real model (never fake).

The LLM is NOT used to fabricate sentiment scores — it may only summarize
(PROMPT_4 §2.3); sentiment numbers always come from this module.
"""
import logging
import re

logger = logging.getLogger(__name__)

# AFINN-165 style word -> score (subset covering travel/review vocabulary)
_LEXICON: dict[str, float] = {
    # strong negative
    "terrible": -4, "horrible": -4, "awful": -4, "worst": -4, "disgusting": -4,
    "atrocious": -4, "appalling": -4, "furious": -4, "scam": -4, "abusive": -4,
    "dirty": -3, "filthy": -3, "unhygienic": -3, "rotten": -3, "broken": -3,
    "rude": -3, "arrogant": -3, "worse": -3, "hate": -3, "hated": -3,
    "useless": -3, "refused": -3, "fraud": -3, "cheated": -3, "waste": -3,
    "stale": -3, "mouldy": -3, "overpriced": -3, "dishonest": -3, "threatening": -3,
    # mild negative
    "bad": -2, "poor": -2, "slow": -2, "dirty": -2, "crowded": -2, "noisy": -2,
    "expensive": -2, "disappointed": -2, "disappointing": -2, "unfriendly": -2,
    "cold": -2, "lukewarm": -2, "mediocre": -2, "average": -1, "okay": -1,
    "bland": -2, "tasteless": -2, "waiting": -1, "delay": -2, "delayed": -2,
    "late": -1, "missing": -1, "unavailable": -1, "closed": -2, "shut": -2,
    "noisy": -2, "damp": -2, "dark": -1, "small": -1, "tight": -1,
    # neutral-leaning-negative
    "ok": 0, "fine": 1, "decent": 1, "acceptable": 1,
    # mild positive
    "good": 2, "great": 3, "nice": 2, "clean": 3, "fresh": 2, "tasty": 3,
    "delicious": 3, "yummy": 3, "flavorful": 3, "fast": 2, "quick": 2,
    "friendly": 3, "helpful": 3, "polite": 3, "comfortable": 3, "spacious": 2,
    "convenient": 2, "affordable": 2, "reasonable": 2, "value": 2, "worth": 2,
    "enjoyed": 3, "enjoy": 2, "love": 4, "loved": 4, "awesome": 4,
    "amazing": 4, "fantastic": 4, "excellent": 4, "superb": 4, "wonderful": 4,
    "best": 4, "perfect": 4, "brilliant": 4, "outstanding": 4, "impressive": 3,
    "beautiful": 4, "gorgeous": 4, "peaceful": 3, "calm": 2, "relaxing": 3,
    "organized": 2, "well-maintained": 3, "spotless": 4, "hygienic": 3,
    "courteous": 3, "recommend": 3, "recommended": 3, "must-visit": 4,
    # negation flips handled in code
}

_WORD_RE = re.compile(r"[a-z]+")
_NEGATORS = {"not", "no", "never", "neither", "nor", "hardly", "barely", "can't", "cant",
             "won't", "wont", "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt",
             "weren't", "werent", "didn't", "didnt", "don't", "dont", "doesn't", "doesnt",
             "shouldn't", "shouldnt", "couldn't", "couldnt", "wouldn't", "wouldnt"}

# Optional HuggingFace pipeline (higher quality when installed)
_HF_PIPELINE = None
_HF_ATTEMPTED = False


def _load_hf():
    global _HF_PIPELINE, _HF_ATTEMPTED
    if _HF_ATTEMPTED:
        return _HF_PIPELINE
    _HF_ATTEMPTED = True
    try:
        from transformers import pipeline

        _HF_PIPELINE = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
        )
        logger.info("[sentiment] huggingface distilbert SST-2 pipeline ready")
    except Exception as exc:  # noqa: BLE001 — optional dependency
        logger.warning("[sentiment] HF pipeline unavailable, using lexicon: %s", exc)
        _HF_PIPELINE = None
    return _HF_PIPELINE


def _lexicon_polarity(text: str) -> float:
    """Score a review with the lexicon + negation handling -> [0,1]."""
    words = _WORD_RE.findall(text.lower())
    if not words:
        return 0.5
    total = 0.0
    count = 0
    negated = False
    for w in words:
        if w in _NEGATORS:
            negated = True
            continue
        score = _LEXICON.get(w)
        if score is None:
            continue
        total += -score if negated else score
        count += 1
        negated = False
    if count == 0:
        return 0.5
    # map [-4,4] -> [0,1] with a logistic-ish squash
    mean = total / count
    return max(0.0, min(1.0, 0.5 + mean / 8.0))


def _hf_polarity(text: str) -> float:
    try:
        result = _load_hf()([text])[0]
        label = result["label"].lower()
        score = float(result["score"])
        return score if "pos" in label else 1.0 - score
    except Exception:  # noqa: BLE001
        return _lexicon_polarity(text)


def review_polarity(text: str) -> float:
    """Sentiment of a single review text -> polarity in [0,1] (0 negative, 1 positive).

    Uses the HF pipeline when installed; otherwise the deterministic lexicon.
    Never calls the LLM and never fabricates.
    """
    if not text or not text.strip():
        return 0.5
    if _load_hf() is not None:
        return _hf_polarity(text)
    return _lexicon_polarity(text)


def sentiment_avg(reviews: list[str]) -> float:
    """Average polarity over review texts; neutral (0.5) when none."""
    if not reviews:
        return 0.5
    vals = [review_polarity(t) for t in reviews if t and t.strip()]
    return sum(vals) / len(vals) if vals else 0.5
