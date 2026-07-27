"""Unit tests for topsis_engine.py — numpy-based TOPSIS multi-criteria scoring."""

import pytest
from backend.services.topsis_engine import TOPSIS


class TestTOPSIS:
    def setup_method(self):
        self.topsis = TOPSIS()

    def test_empty_alternatives(self):
        assert self.topsis.evaluate([]) == []

    def test_single_alternative(self):
        alts = [{"total_fare": 100, "total_duration_minutes": 30, "comfort": 5, "safety": 5,
                  "total_walking_km": 0, "overall_score": 80, "weather_impact": 0}]
        scored = self.topsis.evaluate(alts)
        assert len(scored) == 1
        assert scored[0]["rank"] == 1
        assert 0 <= scored[0]["topsis_score"] <= 1

    def test_two_alternatives_better_wins(self):
        alts = [
            {"total_fare": 50, "total_duration_minutes": 20, "comfort": 5, "safety": 5,
             "total_walking_km": 0, "overall_score": 90, "weather_impact": 0},
            {"total_fare": 200, "total_duration_minutes": 60, "comfort": 2, "safety": 2,
             "total_walking_km": 3, "overall_score": 30, "weather_impact": 0},
        ]
        scored = self.topsis.evaluate(alts)
        assert len(scored) == 2
        assert scored[0]["rank"] == 1
        assert scored[0]["topsis_score"] >= scored[1]["topsis_score"]

    def test_scores_between_0_and_1(self):
        alts = [
            {"total_fare": f, "total_duration_minutes": 30, "comfort": c, "safety": s,
             "total_walking_km": 1, "overall_score": 70, "weather_impact": 0}
            for f, c, s in [(50, 5, 5), (100, 3, 3), (200, 1, 1)]
        ]
        scored = self.topsis.evaluate(alts)
        for s in scored:
            assert 0 <= s["topsis_score"] <= 1, f"Score {s['topsis_score']} out of range"

    def test_alternatives_with_fare_no_score(self):
        alts = [
            {"fare": 50, "duration_minutes": 20, "comfort": 5, "safety": 5,
             "walking_km": 0, "availability": 90, "weather_impact": 0},
            {"fare": 150, "duration_minutes": 45, "comfort": 3, "safety": 3,
             "walking_km": 2, "availability": 50, "weather_impact": 0},
        ]
        scored = self.topsis.evaluate(alts)
        assert len(scored) == 2
        assert scored[0]["rank"] == 1
        assert scored[1]["rank"] == 2

    def test_equal_alternatives_same_score(self):
        alts = [
            {"total_fare": 100, "total_duration_minutes": 30, "comfort": 4, "safety": 4,
             "total_walking_km": 1, "overall_score": 70, "weather_impact": 0},
            {"total_fare": 100, "total_duration_minutes": 30, "comfort": 4, "safety": 4,
             "total_walking_km": 1, "overall_score": 70, "weather_impact": 0},
        ]
        scored = self.topsis.evaluate(alts)
        assert abs(scored[0]["topsis_score"] - scored[1]["topsis_score"]) < 0.001

    def test_set_weights(self):
        self.topsis.set_weights({"cost": 0.5, "time": 0.3, "comfort": 0.2})
        assert self.topsis.criteria_weights["cost"] == 0.5
        assert self.topsis.criteria_weights["time"] == 0.3
        assert self.topsis.criteria_weights["comfort"] == 0.2
        assert self.topsis.criteria_weights["safety"] == 0.15  # unchanged

    def test_handles_zero_denom(self):
        alts = [
            {"total_fare": 0, "total_duration_minutes": 0, "comfort": 5, "safety": 5,
             "total_walking_km": 0, "overall_score": 100, "weather_impact": 0},
        ]
        scored = self.topsis.evaluate(alts)
        assert len(scored) == 1
        assert 0 <= scored[0]["topsis_score"] <= 1
