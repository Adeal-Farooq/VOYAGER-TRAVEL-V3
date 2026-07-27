"""Unit tests for gtfs_service.py — pure functions and GTFSLoader methods."""

import pytest
from backend.services.gtfs_service import (
    clean_route_short_name, _normalize, _time_to_seconds,
    _fast_fuzzy_match, _build_word_index,
    set_test_time, clear_test_time,
)


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
        ("K-1", "K-1"),
        ("MULTI WORD HERE", "MULTI WORD HERE"),
        ("123A-2", "123A-2"),
    ])
    def test_cleaning(self, inp, expected):
        assert clean_route_short_name(inp) == expected

    def test_already_clean(self):
        assert clean_route_short_name("500C") == "500C"

    def test_numeric_only(self):
        assert clean_route_short_name("123") == "123"

    def test_uppercase_conversion(self):
        assert clean_route_short_name("abc-1") == "ABC-1"


class TestNormalize:
    @pytest.mark.parametrize("inp,expected", [
        ("Hello World", "hello world"),
        ("HELLO  WORLD", "hello world"),
        ("hello, world!", "hello world"),
        ("  spaced  out  ", "spaced out"),
        ("Majestic Bus Stand", "majestic bus stand"),
        ("City Market (K.R. Market)", "city market kr market"),
        ("", ""),
    ])
    def test_normalize(self, inp, expected):
        assert _normalize(inp) == expected


class TestTimeToSeconds:
    @pytest.mark.parametrize("time_str,expected", [
        ("00:00:00", 0),
        ("01:00:00", 3600),
        ("01:30:00", 5400),
        ("23:59:59", 86399),
        ("12:00:00", 43200),
        ("00:00:01", 1),
    ])
    def test_conversion(self, time_str, expected):
        assert _time_to_seconds(time_str) == expected

    def test_invalid_format_returns_zero(self):
        assert _time_to_seconds("invalid") == 0


class TestFastFuzzyMatch:
    def setup_method(self):
        _build_word_index(["majestic bus stand", "kempegowda bus station majastic",
                           "mg road", "city market", "shivajinagar bus stop"])

    def test_exact_match(self):
        result = _fast_fuzzy_match("majestic bus stand", ["majestic bus stand", "mg road"])
        assert result == "majestic bus stand"

    def test_fuzzy_match_word_overlap(self):
        result = _fast_fuzzy_match("majestik bus", ["majestic bus stand", "mg road", "city market"])
        assert result is not None

    def test_substring_match(self):
        full_list = ["majestic bus stand", "kempegowda bus station majastic", "mg road", "city market", "shivajinagar bus stop"]
        result = _fast_fuzzy_match("mg road", full_list)
        assert result == "mg road"

    def test_unknown_no_match(self):
        result = _fast_fuzzy_match("xyzzy none", ["majestic bus stand", "mg road"])
        assert result is None

    def test_empty_query(self):
        result = _fast_fuzzy_match("", ["majestic bus stand"])
        assert result is None

    def test_empty_candidates(self):
        _build_word_index([])
        result = _fast_fuzzy_match("test", [])
        assert result is None


class TestTestTimeOverride:
    def teardown_method(self):
        clear_test_time()

    def test_set_and_clear(self):
        set_test_time("2024-01-01 12:00:00")
        from backend.services.gtfs_service import _now
        now = _now()
        assert now.hour == 12
        assert now.minute == 0
        clear_test_time()
        from datetime import datetime
        assert abs((datetime.now() - _now()).total_seconds()) < 5
