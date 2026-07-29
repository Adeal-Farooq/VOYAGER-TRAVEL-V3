"""Enrich transit options with LLM-generated contextual explanations."""

import json
import logging
from datetime import datetime

from backend.core.config import settings

logger = logging.getLogger(__name__)


def _flatten(segments: list) -> list[tuple[str, dict]]:
    """Flatten all transit options (incl. nested next_transit) into [(id, ref), ...]."""
    flat = []

    for si, seg in enumerate(segments):
        for di, dest in enumerate(seg.get("destinations", [])):
            for oi, opt in enumerate(dest.get("transit_options", [])):
                oid = f"s{si}d{di}o{oi}"
                flat.append((oid, opt))
                _walk_nested(opt, oid, flat)

    return flat


def _walk_nested(opt: dict, parent_id: str, flat: list):
    for ni, nt in enumerate(opt.get("next_transit", [])):
        nid = f"{parent_id}_n{ni}"
        flat.append((nid, nt))
        _walk_nested(nt, nid, flat)


def _summarize(oid: str, opt: dict) -> str:
    mode = opt.get("mode", "?")
    route = opt.get("route_number", "")
    fr = opt.get("from", "")
    to = opt.get("to", "")
    dist = opt.get("distance_km", 0)
    dur = opt.get("duration_minutes", 0)
    fare = opt.get("fare", 0)
    pp = opt.get("per_person", 0)
    times = opt.get("bus_times", [])
    ts = ", ".join(t["departure_time"] for t in times[:3]) if times else ""

    parts = [f"[{oid}]"]
    parts.append(f"{mode} {route} {fr} -> {to}")
    parts.append(f"{dist}km {dur}min Rs{fare} (Rs{pp}/pp)")
    if ts:
        parts.append(f"@{ts}")
    return " | ".join(parts)


def _build_prompt(items: list, weather: dict, news: list, hour: int) -> str:
    w = weather or {}
    cond = w.get("condition", "Unknown")
    temp = w.get("temperature", "?")
    rain = w.get("rain_probability", 0)
    weather_line = f"Weather: {cond}, {temp}C, rain {rain}%"

    news_items = []
    for n in (news or []):
        if isinstance(n, dict):
            news_items.append(n.get("title", ""))
    news_line = f"News: {'; '.join(news_items[:3])}" if news_items else "News: none"

    opt_lines = "\n".join(_summarize(oid, opt) for oid, opt in items)

    return f"""You are a Bengaluru transit assistant. For each option below give ONE short sentence explaining why a traveler might choose or avoid it.

Time: {hour}:00
{weather_line}
{news_line}

Options:
{opt_lines}

Return ONLY JSON: {{"explanations":{{"ID":"sentence","ID":"sentence"...}}}}"""


async def _call_llm(prompt: str) -> dict:
    if not settings.OPENROUTER_API_KEY:
        logger.warning("No OpenRouter key — skipping transit explain")
        return {}

    import httpx
    models = [settings.OPENROUTER_MODEL] + settings.OPENROUTER_FALLBACK_MODELS

    for model in models:
        try:
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "Output only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 4096,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8006",
                        "X-Title": "VOYAGER Transit Explain",
                    },
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return parsed.get("explanations", parsed)
        except Exception as e:
            logger.warning(f"LLM explain failed {model}: {e}")
            continue

    return {}


async def enrich_segments(segments: list, lat: float = 12.9716, lng: float = 77.5946):
    """Generate contextual explanations for all transit options. Mutates segments in-place."""
    from backend.services.clients.weather_client import weather_client
    from backend.services.langgraph.tools.news_tools import get_travel_news

    weather, news = await _gather_context(lat, lng)
    hour = datetime.now().hour

    items = _flatten(segments)
    if not items:
        return segments

    prompt = _build_prompt(items, weather, news, hour)
    explanations = await _call_llm(prompt)

    applied = 0
    for oid, opt in items:
        exp = explanations.get(oid, "")
        if exp:
            opt["explanation"] = exp
            applied += 1

    logger.info(f"Applied {applied}/{len(items)} transit explanations")
    return segments


async def _gather_context(lat: float, lng: float):
    import asyncio
    from backend.services.clients.weather_client import weather_client
    from backend.services.langgraph.tools.news_tools import get_travel_news

    wf = weather_client.get_weather_impact(lat, lng)
    nf = get_travel_news("", "", limit=3)
    results = await asyncio.gather(wf, nf, return_exceptions=True)
    return (
        results[0] if not isinstance(results[0], Exception) else {},
        results[1] if not isinstance(results[1], Exception) else [],
    )
