"""Route-context workflow (PROMPT_5 §2.4).

The 'gather live context for a route' graph: parallel fan-out of weather,
traffic, news, prices, reviews -> LiveContext. Delegates to
VoyagerLangGraph.gather_route_context (single-source implementation).
"""
from __future__ import annotations

from ..agent import VoyagerLangGraph


class RouteContextWorkflow:
    def __init__(self, agent: VoyagerLangGraph | None = None):
        self._agent = agent or VoyagerLangGraph()

    def run(self, source: dict, destination: dict, group_size: int = 1,
            budget: float = 500.0, current_time: str | None = None,
            place: dict | None = None) -> dict:
        return self._agent.gather_route_context(
            src=source, dst=destination, group_size=group_size,
            budget=budget, current_time=current_time, place=place)
