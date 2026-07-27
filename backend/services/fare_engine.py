"""Centralized fare logic — replaces 12x duplicated fare_max = round(total * 1.35) in transit_service.py."""

from backend.services.transit_config import _RIDE_TYPES, _calc_ride_fare


def calc_fare_with_surge(mode_data: tuple, distance_km: float) -> tuple[int, int]:
    """Returns (fare_min, fare_max) with centralized surge multiplier.
    
    mode_data: (mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km)
    """
    mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km = mode_data
    total = _calc_ride_fare(distance_km, base_fare, per_km, free_km)
    return total, round(total * 1.35)


def get_mode_by_id(mode_id: str) -> tuple | None:
    """Look up a ride type tuple by mode string. Returns None if not found."""
    for mt in _RIDE_TYPES:
        if mt[0] == mode_id:
            return mt
    return None


def ride_fare_range(mode_id: str, distance_km: float) -> tuple[int, int]:
    """One-call convenience for getting fare range for a mode + distance."""
    mode_info = get_mode_by_id(mode_id)
    if not mode_info:
        return (0, 0)
    return calc_fare_with_surge(mode_info, distance_km)
