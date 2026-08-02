"""PROMPT_7 ML tests: traffic slowdown model contract.

- predict_slowdown(lat, lng, dt) returns float in [1.0, 1.8]
- model_info() labels the model honestly (time_of_day degrade is allowed)
- load is lazy and <1s
- effective_traffic_factor = max(directions_ratio, predicted_slowdown)
"""
from datetime import datetime

from backend.services.traffic_model import (
    TrafficSlowdownModel,
    effective_traffic_factor,
    train_traffic_model,
)


class TestTrafficModelContract:
    def setup_method(self):
        self.model = TrafficSlowdownModel()
        self.model._loaded = False  # force fresh lazy load per test

    def test_predict_range(self):
        for hour in range(24):
            dt = datetime(2026, 1, 5, hour, 0)  # a Monday
            v = self.model.predict_slowdown(12.97, 77.59, dt)
            assert 1.0 <= v <= 1.8, f"hour {hour} -> {v}"

    def test_model_info_honest(self):
        info = self.model.model_info()
        assert info["model"] in ("time_of_day", "lightgbm", "xgboost", "mlp")
        assert isinstance(info["mae"], float)
        assert info["trained_at"]
        assert info["coverage"]["hours"] >= 1
        # degrade is allowed but must never claim a spatial ML model it isn't
        assert "areas" in info["coverage"]

    def test_unknown_time_uses_fallback_label(self):
        # a datetime outside the trained curve still returns a sane multiplier
        v = self.model.predict_slowdown(0.0, 0.0, datetime(2030, 1, 1, 3, 0))
        assert 1.0 <= v <= 1.8

    def test_lazy_load(self):
        import time

        start = time.perf_counter()
        self.model.load()
        assert time.perf_counter() - start < 1.0

    def test_train_from_csv(self):
        from backend import config

        info = train_traffic_model(config.TRAFFIC_LOGS_PATH)
        assert info["model"] == "time_of_day"
        assert 0.0 <= info["mae"] <= 0.6
        assert info["coverage"]["hours"] == 24


class TestEffectiveTrafficFactor:
    def test_max_when_both_present(self):
        assert effective_traffic_factor(1.1, 1.4) == 1.4
        assert effective_traffic_factor(1.6, 1.2) == 1.6

    def test_single_value_passthrough(self):
        assert effective_traffic_factor(None, 1.2) == 1.2
        assert effective_traffic_factor(1.3, None) == 1.3

    def test_none_when_both_missing(self):
        assert effective_traffic_factor(None, None) == 1.0
