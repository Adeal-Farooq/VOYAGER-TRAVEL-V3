"""Unit tests for train_service.py — station code resolution, fallback trains."""

import pytest
from backend.services.train_service import (
    _resolve_station_code, _city_key, _parse_erail_response,
    get_train_options,
)


class TestResolveStationCode:
    def test_known_station(self):
        assert _resolve_station_code("KSR Bengaluru") == "sbc"
        assert _resolve_station_code("Yesvantpur") == "ypr"
        assert _resolve_station_code("Mysuru Junction") == "mys"
        assert _resolve_station_code("Hubballi") == "ubl"

    def test_case_insensitive(self):
        assert _resolve_station_code("ksr bengaluru") == "sbc"
        assert _resolve_station_code("MANGALURU") == "maq"

    def test_with_suffixes(self):
        assert _resolve_station_code("KSR Bengaluru Railway Station") == "sbc"
        assert _resolve_station_code("Bangalore Cant Station") == "bnc"

    def test_unknown_station(self):
        assert _resolve_station_code("Some Random Place") is None

    def test_empty_name(self):
        assert _resolve_station_code("") is None
        assert _resolve_station_code(None) is None

    def test_partial_match(self):
        assert _resolve_station_code("KSR Bengaluru City") == "sbc"
        assert _resolve_station_code("Mysore Palace Road") == "mys"


class TestCityKey:
    def test_known_city(self):
        assert _city_key("KSR Bengaluru") == "bengaluru"
        assert _city_key("Mysuru") == "mysuru"
        assert _city_key("Hubballi Junction") == "hubballi"

    def test_unknown_city(self):
        assert _city_key("Tokyo") == "tokyo"

    def test_empty_name(self):
        assert _city_key("") is None
        assert _city_key(None) is None

    def test_suffix_cleaning(self):
        assert _city_key("Mangalore Railway Station") == "mangaluru"


class TestParseErailResponse:
    def test_parses_valid_line(self):
        text = "12613|Shatabdi Express|KSR BENGALURU|MYSURU|11:00|13:00|...|...|...|...|...|..."
        trains = _parse_erail_response(text)
        assert len(trains) == 1
        assert trains[0][0] == "12613"
        assert "KSR BENGALURU → MYSURU" in trains[0][1]
        assert trains[0][2] == "11:00"
        assert trains[0][3] == "13:00"

    def test_multiple_trains(self):
        text = (
            "12613|Shatabdi|SBC|MYS|11:00|13:00|...|...|...|...|...|...\n"
            "12007|Shatabdi2|SBC|MYS|14:00|16:00|...|...|...|...|...|..."
        )
        trains = _parse_erail_response(text)
        assert len(trains) == 2

    def test_filters_invalid_train_numbers(self):
        text = "AB|Some Train|A|B|00:00|01:00|...|...|...|...|...|..."  # too short
        assert _parse_erail_response(text) == []

    def test_skip_empty_lines(self):
        text = "\n\n"
        assert _parse_erail_response(text) == []

    def test_skip_lines_without_pipe(self):
        text = "no pipe here"
        assert _parse_erail_response(text) == []

    def test_too_few_fields(self):
        text = "12613|Shatabdi|SBC|MYS|11:00"
        assert _parse_erail_response(text) == []


class TestGetTrainOptions:
    def test_fallback_for_bengaluru_mysuru(self):
        trains = get_train_options("KSR Bengaluru", "Mysuru")
        assert len(trains) >= 1
        assert any("12613" in t[0] for t in trains)

    def test_fallback_for_bengaluru_hubballi(self):
        trains = get_train_options("KSR Bengaluru", "Hubballi")
        assert len(trains) >= 1
        assert any("17325" in t[0] for t in trains)

    def test_fallback_reversed_order(self):
        trains = get_train_options("Mysuru", "KSR Bengaluru")
        assert len(trains) >= 1

    def test_unknown_stations(self):
        trains = get_train_options("Unknown Place", "Somewhere")
        assert trains == []

    def test_empty_names(self):
        assert get_train_options("", "") == []
        assert get_train_options(None, None) == []
