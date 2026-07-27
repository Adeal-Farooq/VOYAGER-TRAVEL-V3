"""Unit tests for transit_config.py — pure functions, no DB deps."""

import math
import pytest
from backend.services.transit_config import (
    _calc_ride_fare, _ride_fare_range, _safe, _haversine_dist,
    _current_hour, _is_metro_operating, _route_goes_toward_dest,
    clean_route_short_name, _RIDE_TYPES, _MAJOR_HUBS,
)


class TestCalcRideFare:
    def test_zero_distance_uses_base(self):
        assert _calc_ride_fare(0, 25, 12, 0) == 25

    def test_short_distance(self):
        assert _calc_ride_fare(5, 25, 12, 0) == 25 + 5 * 12

    def test_within_free_km(self):
        assert _calc_ride_fare(2, 25, 12, 5) == 25

    def test_beyond_free_km(self):
        assert _calc_ride_fare(7, 25, 12, 5) == 25 + (7 - 5) * 12

    def test_auto_fare_10km(self):
        # auto: per_km=9, base=15, free_km=0
        assert _calc_ride_fare(10, 15, 9, 0) == 105

    def test_bike_fare_5km(self):
        # bike: per_km=5, base=10, free_km=0
        assert _calc_ride_fare(5, 10, 5, 0) == 35

    def test_large_distance(self):
        assert _calc_ride_fare(100, 25, 12, 0) == 25 + 100 * 12


class TestRideFareRange:
    def test_range_min_le_max(self):
        fmin, fmax = _ride_fare_range(10, 15, 9, 0)
        assert fmin <= fmax

    def test_range_values(self):
        fmin, fmax = _ride_fare_range(10, 15, 9, 0)
        assert fmin == 105
        assert fmax == round(105 * 1.35)


class TestSafe:
    @pytest.mark.parametrize("val,expected", [
        (0.0, 0.0), (42.5, 42.5), (None, 0.0),
        (float("nan"), 0.0), (float("inf"), 0.0),
        (float("-inf"), 0.0), (-3.14, -3.14),
    ])
    def test_safe_values(self, val, expected):
        result = _safe(val)
        if isinstance(expected, float) and math.isnan(expected):
            assert math.isnan(result)
        else:
            assert result == expected or (math.isnan(expected) and math.isnan(result))


class TestHaversineDist:
    def test_same_point(self):
        assert _haversine_dist(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    def test_majestic_to_mg_road(self):
        d = _haversine_dist(12.9763, 77.5710, 12.9750, 77.6066)
        assert 2.5 < d < 4.0

    def test_yelahanka_to_mg_road(self):
        d = _haversine_dist(13.1008, 77.5963, 12.9750, 77.6066)
        assert 12 < d < 16

    def test_bangalore_to_mysore(self):
        d = _haversine_dist(12.9716, 77.5946, 12.2958, 76.6394)
        assert 120 < d < 140

    def test_commutative(self):
        d1 = _haversine_dist(12.9716, 77.5946, 13.1008, 77.5963)
        d2 = _haversine_dist(13.1008, 77.5963, 12.9716, 77.5946)
        assert abs(d1 - d2) < 0.001


class TestCurrentHour:
    def test_returns_int(self):
        h = _current_hour()
        assert isinstance(h, int)
        assert 0 <= h < 24


class TestIsMetroOperating:
    def test_returns_bool(self):
        assert isinstance(_is_metro_operating(), bool)


class TestCleanRouteShortName:
    @pytest.mark.parametrize("inp,expected", [
        ("MF-28 JKLO-ISROQ-LGRNB", "MF-28"),
        ("500C KBS-MG", "500C"),
        ("  K-2  some extra  ", "K-2"),
        ("123", "123"),
        ("ABC-DEF", "ABC-DEF"),
        ("   ", ""),
        ("", ""),
        ("G-6 EXTRA", "G-6"),
    ])
    def test_cleaning(self, inp, expected):
        assert clean_route_short_name(inp) == expected


class TestMajorHubs:
    def test_contains_expected(self):
        hubs_lower = [h.lower() for h in _MAJOR_HUBS]
        assert "majestic" in hubs_lower
        assert "shivajinagar" in hubs_lower or "shivajinagara" in hubs_lower
        assert "banashankari" in hubs_lower

    def test_all_strings(self):
        for hub in _MAJOR_HUBS:
            assert isinstance(hub, str)
            assert len(hub) > 0
