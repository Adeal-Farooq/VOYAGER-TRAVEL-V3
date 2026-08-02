"""PROMPT_7 retrain script — rebuild the traffic slowdown model artifact.

Usage:
    python -m scripts.train_traffic_model            # from PROJECT/
    python scripts/train_traffic_model.py            # same thing

Reads DATA_FOLDER/traffic_logs.csv, trains the time-of-day slowdown curve
(see backend/services/traffic_model.py for the honest-degrade rationale),
writes the artifact to DATA_FOLDER/processed/traffic_model.json and prints
model_info() + sample predictions.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.traffic_model import (  # noqa: E402
    TrafficSlowdownModel,
    _ARTIFACT,
    train_traffic_model,
)
from backend import config  # noqa: E402


def main() -> int:
    info = train_traffic_model(config.TRAFFIC_LOGS_PATH, _ARTIFACT)
    model = TrafficSlowdownModel()
    print("model_info():")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print("\nsample predictions:")
    for hour in (8, 12, 18, 23):
        dt = datetime(2026, 1, 5, hour, 0)
        print(f"  dt={dt:%H:%M} -> {model.predict_slowdown(12.97, 77.59, dt)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
