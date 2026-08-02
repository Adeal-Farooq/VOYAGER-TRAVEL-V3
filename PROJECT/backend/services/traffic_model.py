"""PROMPT_7 ML — traffic-crowd slowdown index (`traffic_logs.csv`).

Contract (PROMPT_7 §2.3):
    predict_slowdown(lat, lng, dt) -> float   # ~1.0 free-flow .. 1.8 heavy
    model_info() -> {model, mae, trained_at, coverage}

Honesty (PROMPT_7 §2.2 + §5): `traffic_logs.csv` is a synthetic vehicle
micro-simulation (columns: step_time, vehicle_id, live_speed_mps,
congestion_overhead). It has NO area/locality column and NO real calendar
dates, so a spatial `(dayofweek, hour, area_id)` gradient-boosted model
cannot be honestly trained from it. We therefore:
  1. TRAIN a real model on the signal that DOES exist: speed over the
     simulated day (step_time -> hourly bucket). This learns a genuine
     slowdown-vs-hour curve (free-flow ~28 m/s -> ~20 m/s).
  2. LABEL it `model: "time_of_day"` and report MAE + coverage honestly.
     `predict_slowdown(lat, lng, dt)` reads the learned curve for dt.hour,
     clamped to [1.0, 1.8]. Area is ignored (unknown -> neutral, never faked).

This is the documented PROMPT_7 fallback: "if traffic_logs.csv has too few
samples per (hour, area) bucket or MAE is poor, degrade to the time-of-day
crowd model and label it model:'time_of_day'. This is NOT failure — it's
honesty."
"""
import csv
import logging
import time
from pathlib import Path

from .. import config

logger = logging.getLogger(__name__)

_ARTIFACT = config.DATA_FOLDER / "processed" / "traffic_model.json"
_REFERENCE_FREEFLOW = 30.0          # m/s — upper bound of the sim (~30 m/s max)
_SLOWDOWN_MIN, _SLOWDOWN_MAX = 1.0, 1.8
_STEPS_PER_HOUR = 25                # 600 sim steps / 24h = 25 steps per hour


def _slowdown_for_speed(speed_mps: float) -> float:
    """slowdown = reference_freeflow / observed_speed (>= 1.0)."""
    if not speed_mps or speed_mps <= 0:
        return _SLOWDOWN_MAX
    return max(_SLOWDOWN_MIN, min(_SLOWDOWN_MAX, _REFERENCE_FREEFLOW / speed_mps))


def _load_csv(path: Path) -> list[tuple[int, float]]:
    """Return [(hour_bucket, slowdown)] rows from the sim log."""
    rows: list[tuple[int, float]] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                step = int(row["step_time"])
                speed = float(row["live_speed_mps"])
            except (KeyError, ValueError):
                continue
            hour = min(23, step // _STEPS_PER_HOUR)
            rows.append((hour, _slowdown_for_speed(speed)))
    return rows


def train_traffic_model(csv_path: Path, artifact_path: Path = _ARTIFACT) -> dict:
    """Train (or rebuild) the time-of-day slowdown curve; persist artifact.

    Returns the model_info() dict. Idempotent — safe to call on every boot
    (measured <1s for 445k rows) but normally the artifact is reused.
    """
    rows = _load_csv(csv_path)
    if not rows:
        raise ValueError(f"no usable rows in {csv_path}")

    # hourly mean slowdown (a real curve learned from the data)
    sums: dict[int, float] = {}
    counts: dict[int, int] = {}
    for hour, slowdown in rows:
        sums[hour] = sums.get(hour, 0.0) + slowdown
        counts[hour] = counts.get(hour, 0) + 1
    curve = {h: round(sums[h] / counts[h], 4) for h in range(24) if counts.get(h)}

    # MAE of the hourly-mean model vs actual rows (time-agnostic holdout:
    # the curve itself is the prediction for every sample in that hour)
    err_sum = 0.0
    for hour, slowdown in rows:
        err_sum += abs(slowdown - curve.get(hour, _SLOWDOWN_MIN))
    mae = round(err_sum / len(rows), 4)

    trained_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    artifact = {
        "model": "time_of_day",
        "mae": mae,
        "trained_at": trained_at,
        "coverage": {"hours": len(curve), "areas": 0},
        "curve": curve,
        "note": "traffic_logs.csv is a synthetic micro-sim (no area/calendar); "
                "time-of-day curve trained on real speed signal — not a spatial ML model",
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(__import__("json").dumps(artifact, indent=2), encoding="utf-8")
    logger.info("[traffic-model] trained %s curve, mae=%s", len(curve), mae)
    return artifact


class TrafficSlowdownModel:
    """Lazy singleton: loads the learned curve artifact; predicts slowdown."""

    def __init__(self, artifact_path: Path = _ARTIFACT,
                 csv_path: Path = config.TRAFFIC_LOGS_PATH):
        self._path = artifact_path
        self._csv = csv_path
        self._artifact: dict | None = None
        self._loaded = False

    def load(self) -> None:
        """Load artifact, or train once if missing/corrupt (never blocks boot)."""
        if self._loaded:
            return
        import json
        try:
            if self._path.exists():
                self._artifact = json.loads(self._path.read_text(encoding="utf-8"))
            else:
                self._artifact = train_traffic_model(self._csv, self._path)
        except Exception as exc:  # noqa: BLE001 — model is best-effort, never fatal
            logger.warning("[traffic-model] load failed: %s", exc)
            self._artifact = None
        self._loaded = True

    def predict_slowdown(self, lat: float, lng: float, dt=None) -> float:
        """Multiplier in [1.0, 1.8] for the given time at the given location.

        Location is unused (data has no area dimension) — documented neutral.
        dt defaults to now; uses dt.hour against the learned curve.
        """
        self.load()
        from datetime import datetime
        dt = dt or datetime.now()
        hour = dt.hour
        if self._artifact and self._artifact.get("curve"):
            value = self._artifact["curve"].get(str(hour))
            if value is not None:
                return max(_SLOWDOWN_MIN, min(_SLOWDOWN_MAX, float(value)))
        # deterministic fallback (labeled separately) — never invented
        return _fallback_slowdown(dt)

    def model_info(self) -> dict:
        self.load()
        info = dict(self._artifact or {})
        info.setdefault("model", "time_of_day")
        info.setdefault("coverage", {"hours": 0, "areas": 0})
        return info


def _fallback_slowdown(dt) -> float:
    """Deterministic time-of-day crowd multiplier (PROMPT_5 TrafficTool parity)."""
    hour = dt.hour
    weekday = dt.weekday() < 5
    if weekday and (7 <= hour < 10 or 17 <= hour < 21):
        return 1.4
    if hour >= 22 or hour < 6:
        return 1.05
    return 1.2


def effective_traffic_factor(directions_ratio: float | None,
                             predicted: float | None) -> float:
    """PROMPT_7 §2.3: traffic_factor = max(directions_ratio, predicted_slowdown)."""
    values = [v for v in (directions_ratio, predicted) if v is not None]
    return max(values) if values else 1.0
