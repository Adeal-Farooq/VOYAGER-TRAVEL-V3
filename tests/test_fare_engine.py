"""Unit tests for fare_engine.py — pure functions, no deps."""

import pytest
from backend.services.fare_engine import calc_fare_with_surge, get_mode_by_id, ride_fare_range
from backend.services.transit_config import _RIDE_TYPES


class TestCalcFareWithSurge:
    def test_returns_pair(self):
        result = calc_fare_with_surge(_RIDE_TYPES[0], 5.0)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] <= result[1]

    def test_auto_10km(self):
        auto = get_mode_by_id("auto")
        fare_min, fare_max = calc_fare_with_surge(auto, 10.0)
        # auto: per_km=9, base=15, free_km=0 → 15 + 10*9 = 105
        assert fare_min == 105
        assert fare_max == round(105 * 1.35)

    def test_bike_5km(self):
        bike = get_mode_by_id("bike")
        fare_min, fare_max = calc_fare_with_surge(bike, 5.0)
        # bike: per_km=5, base=10, free_km=0 → 10 + 5*5 = 35
        assert fare_min == 35
        assert fare_max == round(35 * 1.35)

    def test_cab_14km(self):
        cab = get_mode_by_id("cab")
        fare_min, fare_max = calc_fare_with_surge(cab, 14.0)
        # cab: per_km=12, base=25, free_km=0 → 25 + 14*12 = 193
        assert fare_min == 193
        assert fare_max == round(193 * 1.35)

    def test_zero_distance(self):
        auto = get_mode_by_id("auto")
        fare_min, fare_max = calc_fare_with_surge(auto, 0)
        # 0km → base only 15
        assert fare_min == 15
        assert fare_max == round(15 * 1.35)

    def test_surge_always_gte_min(self):
        for mt in _RIDE_TYPES:
            fmin, fmax = calc_fare_with_surge(mt, 7.0)
            assert fmax >= fmin, f"Surge failed for {mt[0]}: {fmax} < {fmin}"

    def test_surge_ratio(self):
        auto = get_mode_by_id("auto")
        for dist in [1, 3, 5, 10, 20]:
            fmin, fmax = calc_fare_with_surge(auto, float(dist))
            assert abs(fmax - round(fmin * 1.35)) <= 1, f"Ratio off at {dist}km: {fmin}→{fmax}"


class TestGetModeById:
    def test_finds_cab(self):
        assert get_mode_by_id("cab") is not None
        assert get_mode_by_id("cab")[0] == "cab"

    def test_finds_all_modes(self):
        for mt in _RIDE_TYPES:
            assert get_mode_by_id(mt[0]) is not None, f"Missing mode {mt[0]}"

    def test_unknown_mode(self):
        assert get_mode_by_id("spaceship") is None


class TestRideFareRange:
    def test_happy_path(self):
        fmin, fmax = ride_fare_range("cab", 10.0)
        assert fmin > 0
        assert fmax >= fmin

    def test_unknown_mode_returns_zero(self):
        assert ride_fare_range("spaceship", 10.0) == (0, 0)
