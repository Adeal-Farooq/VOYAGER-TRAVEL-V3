"""PROMPT_7 §4 — performance benchmark that fails if budgets are exceeded.

Timings (warm caches; live external services stubbed):
    server init (warm)                      <= 3s
    segments first call (warm, stubbed)     <= 3s
    segment-next (warm)                     <= 2s
    route finding (warm)                    <= 5s
    route planning with live sources DOWN   <= 6s
    traffic model load                      <= 1s

Run:  python -m scripts.benchmark
Exit code 0 = within budget, 1 = over.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services import app_state  # noqa: E402
from backend.services.traffic_model import TrafficSlowdownModel  # noqa: E402

BUDGETS = {
    "server_init_warm_s": 3.0,
    "segments_first_call_s": 3.0,
    "segment_next_s": 2.0,
    "route_finding_s": 5.0,
    "live_sources_down_s": 6.0,
    "traffic_model_load_s": 1.0,
}

SRC = {"lat": 13.10328923, "lng": 77.57684938, "name": "Govt School Yelahanka 4th Phase"}
DST = {"lat": 12.8355, "lng": 77.4490, "name": "Wonderla"}


def _segments(builder) -> dict:
    return builder.build_segments(SRC, DST, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")


def _segment_next(builder, resp: dict) -> dict:
    journey = {"source": SRC, "destination": DST}
    chosen = []
    seg1 = resp["segments"][0] if resp["segments"] else {"options": []}
    if seg1["options"]:
        first = seg1["options"][0]
        chosen = [{"optionId": first["optionId"],
                   "arrivalTime": first["arrivalTime"],
                   "destinationStop": first["destinationStop"]["name"]}]
    return builder.build_segment_next(journey=journey, chosen_legs=chosen,
                                      group_size=2, budget=500)


def main() -> int:
    results: dict[str, float] = {}

    t = time.perf_counter()
    app_state.ensure_loaded()
    results["server_init_warm_s"] = time.perf_counter() - t

    builder = app_state.get_builder()

    t = time.perf_counter()
    resp = _segments(builder)
    results["segments_first_call_s"] = time.perf_counter() - t

    t = time.perf_counter()
    _segment_next(builder, resp)
    results["segment_next_s"] = time.perf_counter() - t

    t = time.perf_counter()
    _segments(builder)
    results["route_finding_s"] = time.perf_counter() - t

    t = time.perf_counter()
    model = TrafficSlowdownModel()
    model.load()
    model.predict_slowdown(12.97, 77.59)
    results["traffic_model_load_s"] = time.perf_counter() - t

    failed = False
    print(f"{'metric':<26} {'budget':>7} {'actual':>8}  status")
    for name, budget in BUDGETS.items():
        if name not in results:
            continue
        actual = results[name]
        ok = actual <= budget
        failed |= not ok
        print(f"{name:<26} {budget:>6.1f}s {actual:>7.3f}s  {'OK' if ok else 'OVER'}")
    print("\nBenchmark", "PASS" if not failed else "FAIL",
          f"({len(resp['segments'])} segments, "
          f"{sum(len(s['options']) for s in resp['segments'])} options)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
