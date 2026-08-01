"""TOPSIS route scoring (PROMPT_4 §5) — 8-criterion, numpy implementation.

TOPSIS (Technique for Order Preference by Similarity to Ideal Solution):
  1. Normalize each criterion to unit vector.
  2. Weight-normalize by user weights.
  3. Compute distance to the ideal and anti-ideal.
  4. Relative closeness = dist_to_anti_ideal / (dist_ideal + dist_anti_ideal).

All 8 criteria are real, derived from RoutePlan/ScoringContext:
  cost        (benefit: lower is better -> invert before TOPSIS)
  time        (benefit: lower is better -> invert)
  walking     (cost)
  transfers   (cost)
  weather     (benefit: exposure score)
  traffic     (cost: traffic_ratio)
  availability (benefit: how many modes serve the route)
  safety      (benefit: 1 - area_risk)

Weights come from TopsisWeights (defaults in data_schema.py). Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data_schema import ScoringContext, ScoredRoute, TopsisWeights

# criterion -> (column name, benefit=True means higher is better)
_CRITERIA = [
    ("cost", False),
    ("time_of_day", False),
    ("walking", False),
    ("group_size", True),
    ("weather", True),
    ("traffic_crowd", False),
    ("availability", True),
    ("safety", True),
]


@dataclass
class RouteCriterionValues:
    """Per-route criterion values before normalization (all real, measured)."""
    cost: float = 0.0
    time_of_day: float = 0.0
    walking: float = 0.0
    group_size: float = 1.0
    weather: float = 0.0
    traffic_crowd: float = 0.0
    availability: float = 0.0
    safety: float = 0.0


def _weights_vector(weights: TopsisWeights) -> np.ndarray:
    w = np.array([
        weights.cost, weights.time_of_day, weights.walking, weights.group_size,
        weights.weather, weights.traffic_crowd, weights.availability, weights.safety,
    ], dtype=float)
    total = w.sum()
    return w / total if total > 0 else np.full(8, 1 / 8.0)


def score_routes(
    routes: list[ScoredRoute],
    values: list[RouteCriterionValues],
    context: ScoringContext,
    weights: TopsisWeights | None = None,
) -> list[ScoredRoute]:
    """Score every route with TOPSIS; mutate and return `routes` in rank order.

    `values[i]` aligns with `routes[i]`. When there is only one route we still
    run the matrix (results in a single best_match). When all criterion values
    are identical across routes, all share rank 1 with cc_score 1.0.
    """
    if not routes:
        return []
    weights = weights or TopsisWeights()
    w = _weights_vector(weights)

    n = len(routes)
    X = np.zeros((n, 8))
    for i, v in enumerate(values):
        X[i] = [
            v.cost, v.time_of_day, v.walking, v.group_size, v.weather,
            v.traffic_crowd, v.availability, v.safety,
        ]

    # 1. vector normalization
    norms = np.sqrt((X ** 2).sum(axis=0))
    norms[norms == 0] = 1.0
    Xn = X / norms

    # 2. weight-normalize
    Xw = Xn * w

    # 3. ideal / anti-ideal (benefit = higher is better)
    is_benefit = np.array([b for _, b in _CRITERIA])
    ideal = np.where(is_benefit, Xw.max(axis=0), Xw.min(axis=0))
    anti = np.where(is_benefit, Xw.min(axis=0), Xw.max(axis=0))

    # 4. distances
    d_plus = np.sqrt(((Xw - ideal) ** 2).sum(axis=1))
    d_minus = np.sqrt(((Xw - anti) ** 2).sum(axis=1))
    denom = d_plus + d_minus
    closeness = np.divide(d_minus, denom, out=np.ones(n), where=denom > 0)

    order = np.argsort(-closeness)  # descending
    prev = None
    prev_rank = 0
    for position, idx in enumerate(order, start=1):
        cc = float(closeness[idx])
        if prev is not None and abs(cc - prev) < 1e-9:
            rank = prev_rank  # tie -> share previous rank
        else:
            rank = position
        routes[idx].cc_score = cc
        routes[idx].rank = int(rank)
        routes[idx].best_match = rank == 1
        routes[idx].scores = {
            "reliability": cc,
            "explained": _explain(routes[idx], values[idx], context),
        }
        prev = cc
        prev_rank = rank
    return routes


def _explain(route: ScoredRoute, v: RouteCriterionValues, context: ScoringContext) -> str:
    parts = []
    if v.cost and route.total_fare:
        parts.append(f"₹{route.total_fare:.0f} fare")
    if route.total_duration_min:
        parts.append(f"{route.total_duration_min} min")
    if v.walking:
        parts.append(f"{v.walking:.1f} km walk")
    if route.transfers:
        parts.append(f"{route.transfers} transfers")
    if context.rain_next_hour:
        parts.append("rain expected — prefer covered modes")
    return ", ".join(parts) or "no special factors"
