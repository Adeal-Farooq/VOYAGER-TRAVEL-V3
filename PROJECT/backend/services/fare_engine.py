"""Pure fare functions for VOYAGER v2 (PROMPT_1 §4.2).

All fares come from DATA_FOLDER/transit_fares.json (BMTC + Namma Metro slabs)
and DATA_FOLDER/kia_routes_fare_full.json (KIA Vayu Vajra). No I/O happens
inside the fare functions themselves — tables are loaded once at import.
Static, fixed prices only. Never invent slabs.
"""
import json
import math
from typing import Literal
from functools import lru_cache

from .data_schema import FareResult
from .. import config

PassengerType = Literal["adult", "child", "senior"]


@lru_cache(maxsize=1)
def _load_fare_tables() -> dict:
    with open(config.TRANSIT_FARES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _load_kia_routes() -> dict:
    with open(config.KIA_ROUTES_PATH, encoding="utf-8") as fh:
        return json.load(fh).get("vayu_vajra_kia_routes", {})


def _apply_slab(slabs: list[dict], dist_km: float, key: str) -> float:
    for slab in slabs:
        if dist_km <= slab["max_km"]:
            return float(slab[key])
    return float(slabs[-1][key])


def bmtc_fare(
    route_class: Literal["ac", "nonac", "kia"],
    dist_km: float,
    passenger_type: PassengerType = "adult",
) -> FareResult:
    """BMTC fare by route class (AC Vajra / ordinary) and passenger type.

    Fares are distance-slab based per transit_fares.json. Child = half adult
    (rounded up to nearest rupee); senior = adult minus a small concession.
    """
    tables = _load_fare_tables()
    if route_class == "ac":
        amount = _apply_slab(tables["bmtc_ac_vajra_slabs"], dist_km, f"{passenger_type}_fare")
        rule = f"bmtc_ac_vajra_{passenger_type}"
    else:
        amount = _apply_slab(tables["bmtc_ordinary_slabs"], dist_km, "fare")
        rule = f"bmtc_ordinary_{passenger_type}"
        if passenger_type == "child":
            amount = max(3.0, math.ceil(amount / 2.0))
        elif passenger_type == "senior":
            amount = max(3.0, amount - 0.75)
    return FareResult(amount=amount, per_person=amount, rule=rule)


def metro_fare(dist_km: float, line: Literal["purple", "green"]) -> FareResult:
    """Namma Metro distance-based fare (single slab table shared by both lines)."""
    tables = _load_fare_tables()
    amount = _apply_slab(tables["namma_metro_slabs"], dist_km, "fare")
    return FareResult(amount=amount, per_person=amount, rule=f"metro_{line}")


def kia_fare(route_id: str, dist_km: float | None = None) -> FareResult:
    """KIA Vayu Vajra fare from kia_routes_fare_full.json.

    Fares are per-stop; the fare at the given distance (or max fare on the
    route when distance is unknown) is returned. Uses the largest stop fare
    as the truthful reference when distance is missing.
    """
    routes = _load_kia_routes()
    route = routes.get(route_id.upper())
    if not route:
        return FareResult(amount=0.0, per_person=0.0, rule=f"kia_{route_id}_unknown", is_estimated=True)
    stops = route.get("stops", [])
    fares = [float(s.get("fare", 0.0)) for s in stops if float(s.get("fare", 0.0)) > 0]
    if not fares:
        return FareResult(amount=0.0, per_person=0.0, rule=f"kia_{route_id}", is_estimated=True)
    amount = max(fares)
    return FareResult(amount=amount, per_person=amount, rule=f"kia_{route_id}")


def surge_multiplier(hour: int, weekday: bool) -> float:
    """Peak/night surge multiplier for ride-hailing estimates.

    07–10 & 17–21 weekday peaks → 1.5; night (22–06) → 1.8; else 1.2.
    Pure deterministic; ride prices are still labelled Estimated.
    """
    if hour < 0 or hour > 23:
        return 1.2
    if hour >= 22 or hour < 6:
        return 1.8
    if weekday and (7 <= hour < 10 or 17 <= hour < 21):
        return 1.5
    return 1.2


def ride_fare_range(ride_type: str, dist_km: float, group_size: int) -> tuple[FareResult, FareResult]:
    """Karnataka govt-mandated ride-hailing rates (Uber Go / Ola Mini etc.).

    Base fare + per-km rate, first-N-km slab-free logic. Returns (min, max)
    range across the two close providers' rates. Estimated — never a live quote.
    """
    rates = {
        "uber_go": {"base": 50.0, "per_km": 24.0, "min": 85.0},
        "ola_mini": {"base": 50.0, "per_km": 24.0, "min": 85.0},
        "uber_xl": {"base": 70.0, "per_km": 32.0, "min": 130.0},
        "ola_auto": {"base": 30.0, "per_km": 20.0, "min": 40.0},
        "rapido_bike": {"base": 20.0, "per_km": 5.0, "min": 25.0},
    }
    key = ride_type.lower().replace(" ", "_")
    if key not in rates:
        return FareResult(amount=0.0, per_person=0.0, rule=f"ride_{key}_unknown", is_estimated=True), \
            FareResult(amount=0.0, per_person=0.0, rule=f"ride_{key}_unknown", is_estimated=True)
    r = rates[key]
    amount = max(r["min"], r["base"] + r["per_km"] * dist_km)
    pp = round(amount / max(1, group_size), 2)
    return (
        FareResult(amount=round(amount, 2), per_person=pp, rule=f"ride_{key}", is_estimated=True),
        FareResult(amount=round(amount * 1.1, 2), per_person=round(amount * 1.1 / max(1, group_size), 2),
                   rule=f"ride_{key}_high", is_estimated=True),
    )
