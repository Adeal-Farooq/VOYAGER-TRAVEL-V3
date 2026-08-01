"""LLM review summarizer (PROMPT_4 §2.3).

Golden rule: the LLM summarizes ONLY the real review texts it is handed. It
never fabricates reviews, ratings, or scores. If no API key or the call fails,
it returns None and the caller falls back to a deterministic headline.

Uses OpenRouter (OpenAI-compatible) or Google Gemini via the `openai` SDK
base-url switch. Pure explainer — no business logic here.
"""
import json
import logging
from dataclasses import dataclass

from .. import config

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    summary: str
    concerns: list[str]


def summarize(review_texts: list[str], score_pct: int) -> SummaryResult | None:
    if not review_texts:
        return None
    api_key = config.env_str("OPENROUTER_API_KEY") or config.env_str("GEMINI_API_KEY")
    if not api_key:
        logger.info("[llm] no API key — skipping review summary")
        return None
    try:
        return _call_openai_compat(review_texts, score_pct, api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[llm] summary failed: %s", exc)
        return None


def _call_openai_compat(review_texts, score_pct, api_key) -> SummaryResult:
    import openai

    base = config.env_str("OPENROUTER_BASE_URL", "")
    client_kwargs: dict = {"api_key": api_key}
    if base:
        client_kwargs["base_url"] = base
    model = config.env_str("LLM_MODEL", "gpt-4o-mini")

    if config.env_str("GEMINI_API_KEY") and not config.env_str("OPENROUTER_API_KEY"):
        client_kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = config.env_str("LLM_MODEL", "gemini-2.0-flash")

    client = openai.OpenAI(**client_kwargs)
    blob = json.dumps([{"text": t} for t in review_texts], ensure_ascii=False)[:14000]

    system = (
        "You summarize Google Maps reviews. Rules:\n"
        "1. Use ONLY the reviews given. Never invent a review, rating, or fact.\n"
        "2. Output JSON: {\"summary\": \"2-3 sentences, specific themes\", "
        "\"concerns\": [\"recurring complaints\"]}.\n"
        "3. Keep it factual and concise."
    )
    user = f"Reviews (reliability {score_pct}%):\n{blob}"
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=20,
    )
    content = resp.choices[0].message.content or "{}"
    data = json.loads(content)
    return SummaryResult(
        summary=str(data.get("summary", "")).strip(),
        concerns=[str(c).strip() for c in data.get("concerns", []) if str(c).strip()],
    )
