"""LangGraph state schema (PROMPT_5 §2.2).

The live-context graph gathers real tool data in parallel and emits a
LiveContext dict that feeds TOPSIS criterion values + the Gemini explanation.
No fabricated numbers — every field maps to a real API/tool result.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RouteContextInput:
    source: dict = field(default_factory=dict)  # {lat, lng, name}
    destination: dict = field(default_factory=dict)
    group_size: int = 1
    budget: float = 500.0
    current_time: str | None = None


@dataclass
class RouteContextState:
    input: RouteContextInput = field(default_factory=RouteContextInput)
    weather: dict | None = None
    traffic: dict | None = None
    news: list[dict] = field(default_factory=list)
    prices: list[dict] = field(default_factory=list)
    reviews: dict | None = None
    factors: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    completed_at: float | None = None


@dataclass
class AskInput:
    message: str
    lat: float | None = None
    lng: float | None = None
    context: dict | None = None


@dataclass
class AskState:
    input: AskInput = field(default_factory=AskInput)
    tool_outputs: dict[str, Any] = field(default_factory=dict)
    synthesis: dict | None = None
