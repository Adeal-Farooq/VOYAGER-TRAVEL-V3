"""Tool: train (PROMPT_5 §2.2 tools/train_tools.py).

Real eRail.in live trains; fallback pairs flagged source: "fallback" and only
used when eRail is unreachable. Never fabricated.
"""
from __future__ import annotations

from ...train_service import TrainService


class TrainTool:
    def __init__(self, service: TrainService | None = None):
        self._service = service or TrainService()

    def name(self) -> str:
        return "train"

    def run(self, from_station: str, to_station: str) -> dict:
        fc = self._service.code_for(from_station)
        tc = self._service.code_for(to_station)
        if not fc or not tc:
            return {"trains": [], "source": "none", "note": "no station codes"}
        return self._service.trains_between(fc, tc)
