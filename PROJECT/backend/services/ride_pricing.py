"""Ride-hailing pricing for A->B (PROMPT_4 §4).

Two sources, always labeled:
  live      -> SerpAPI google_maps_directions ride_options (real prices when shown)
  estimated -> Karnataka govt-mandated rates via fare_engine.ride_fare_range()

`total` is the vehicle fare (never per_person * group_size — that double-charges);
`per_person` = total / group_size. The live price, when present, overrides the
estimate per provider but is still flagged with its true source.
"""
import logging
from datetime import datetime

from .data_schema import RidePrice, ScoringContext
from .fare_engine import ride_fare_range, surge_multiplier

logger = logging.getLogger(__name__)

# (key, provider, mode) for the estimate fallback ladder
_ESTIMATE_LADDER = [
    ("uber_go", "Uber", "cab"),
    ("ola_mini", "Ola", "cab"),
    ("uber_xl", "Uber XL", "cab"),
    ("ola_auto", "Auto", "auto"),
    ("rapido_bike", "Rapido", "bike"),
]


def estimate_ride_prices(
    dist_km: float,
    group_size: int = 1,
    context: ScoringContext | None = None,
) -> list[RidePrice]:
    """Karnataka-rate estimates for every provider. Always returns all 5."""
    context = context or ScoringContext()
    hour = datetime.now().hour
    weekday = datetime.now().weekday() < 5
    surge = surge_multiplier(hour, weekday)
    out: list[RidePrice] = []
    for key, provider, mode in _ESTIMATE_LADDER:
        lo, hi = ride_fare_range(key, dist_km, group_size)
        mid = (lo.amount + hi.amount) / 2.0
        total = round(mid * surge, 2)
        out.append(RidePrice(
            provider=provider,
            mode=mode,
            total=total,
            per_person=round(total / max(1, group_size), 2),
            source="estimated",
            note=f"Karnataka rate estimate x{surge:.1f} surge",
        ))
    return out


def merge_live_prices(
    live_options: list[dict] | None,
    estimated: list[RidePrice],
    group_size: int,
) -> list[RidePrice]:
    """Replace estimate entries with real SerpAPI prices where a provider matches."""
    if not live_options:
        return estimated
    merged: list[RidePrice] = []
    for opt in live_options:
        provider = (opt.get("provider") or opt.get("provider_name") or "").strip()
        price = _extract_price(opt)
        if not provider or price is None:
            continue
        merged.append(RidePrice(
            provider=provider,
            mode=(opt.get("type") or opt.get("vehicle") or "cab"),
            total=price,
            per_person=round(price / max(1, group_size), 2),
            eta_min=opt.get("duration"),
            source="live",
            note="Live Uber/Ola quote from Google Maps",
        ))
    if not merged:
        return estimated
    # keep estimate-only providers not covered by live data
    covered = {m.provider.lower() for m in merged}
    merged.extend(m for m in estimated if m.provider.lower() not in covered)
    return merged


def _extract_price(opt: dict):
    """SerpAPI ride option price -> float, or None (never fabricate)."""
    for key in ("price", "price_value", "total"):
        raw = opt.get(key)
        if raw is None:
            continue
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, dict):
            raw = raw.get("value") or raw.get("amount") or raw.get("display") or ""
        s = str(raw).replace("₹", "").replace(",", "").strip()
        try:
            return float(s)
        except ValueError:
            continue
    return None


def ride_prices_for_distance(
    dist_km: float,
    group_size: int = 1,
    live_options: list[dict] | None = None,
    context: ScoringContext | None = None,
) -> list[RidePrice]:
    """Full pricing ladder: live prices overlaid on Karnataka estimates."""
    estimated = estimate_ride_prices(dist_km, group_size, context)
    return merge_live_prices(live_options, estimated, group_size)


def coord_to_str(coord: tuple[float, float]) -> str:
    """Format a (lat, lng) pair for SerpAPI's directions q/destination params."""
    return f"{coord[0]:.5f},{coord[1]:.5f}"


def fetch_live_prices(serpapi, origin: tuple[float, float],
                      dest: tuple[float, float]) -> tuple[list[dict] | None, float]:
    """Best-effort live ride options + distance from SerpAPI directions.

    Returns (live_options, dist_km). Both are empty/0 when SerpAPI is down or
    has no price data — callers fall back to the Karnataka estimate ladder.
    Never fabricates: only what SerpAPI actually returned is used.
    """
    if not serpapi:
        return None, 0.0
    data = serpapi.directions(coord_to_str(origin), coord_to_str(dest))
    if not data:
        return None, 0.0
    options = data.get("ride_options") or []
    dist_km = (data.get("distance_m") or 0) / 1000.0
    return (options or None), dist_km
