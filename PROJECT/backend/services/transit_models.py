"""Shared route/leg dtypes for VOYAGER v2 routing (PROMPT_2 §5.1).

Consumed by the routing graph (transit_graph.py), route finder (route_finder.py),
and later by the segment builder (PROMPT_3) and TOPSIS scoring (PROMPT_4).
"""
from dataclasses import dataclass, field
from typing import Literal

Mode = Literal["walk", "bus", "metro", "train", "ride"]
LegStatus = Literal["scheduled", "estimated", "not_running"]
GeomSource = Literal["gtfs_shape", "metro_line", "graphhopper", "interpolated"]


@dataclass
class Leg:
    mode: Mode
    route_number: str | None = None
    from_stop: str = ""
    to_stop: str = ""
    from_lat: float = 0.0
    from_lng: float = 0.0
    to_lat: float = 0.0
    to_lng: float = 0.0
    line: str | None = None  # "Purple"/"Green" for metro legs
    depart_time: str | None = None
    arrive_time: str | None = None
    depart_time_min: int | None = None  # minutes from midnight (for chaining)
    arrive_time_min: int | None = None
    duration_min: int = 0
    distance_m: float = 0.0
    fare: float = 0.0
    per_person_fare: float = 0.0
    geometry: list[tuple[float, float]] = field(default_factory=list)
    geometry_source: GeomSource = "interpolated"
    status: LegStatus = "estimated"
    # extra routes that also serve this leg (used when the primary has no departure)
    alternate_routes: list[str] = field(default_factory=list)

    def __repr__(self) -> str:  # compact for debugging
        return (f"Leg({self.mode}"
                + (f" {self.route_number}" if self.route_number else "")
                + f" {self.from_stop}->{self.to_stop}"
                + (f" {self.depart_time}" if self.depart_time else "")
                + f" {self.duration_min}m {self.status})")


@dataclass
class RoutePlan:
    legs: list[Leg] = field(default_factory=list)
    total_fare: float = 0.0
    total_duration_min: int = 0
    total_walk_km: float = 0.0
    transfers: int = 0
    per_person_fare: float = 0.0
    score: float | None = None  # filled by TOPSIS (PROMPT_4)

    @property
    def summary(self) -> str:
        return " → ".join(
            (f"{l.mode}{':' + l.route_number if l.route_number else ''}" if l.mode in ("bus", "metro")
             else l.mode)
            for l in self.legs
        )
