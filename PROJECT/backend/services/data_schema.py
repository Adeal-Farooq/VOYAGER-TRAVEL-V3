"""Shared data-layer models for VOYAGER v2.

Single source of truth for the shapes of every object produced by the data
layer (PROMPT_1). Downstream modules (routing graph, segment builder, search,
scoring, pricing) import from here — never redefine these shapes.
"""
from typing import Literal

from pydantic import BaseModel, Field

Coordinate = tuple[float, float]  # (lat, lng)


class GtfsStop(BaseModel):
    id: str
    name: str
    lat: float
    lng: float


class RouteDeparture(BaseModel):
    route_id: str
    route_number: str
    stop_name: str
    scheduled_departure: str  # HH:MM:SS as in GTFS
    departure_minutes: int  # minutes-of-day, for filtering
    destination_name: str
    trip_id: str
    shape_id: str
    source: str = "schedule"  # BMTC has no live API — always schedule


class BusStop(BaseModel):
    name: str
    lat: float
    lng: float
    routes: list[str] = Field(default_factory=list)


class MetroStation(BaseModel):
    name: str
    lat: float
    lng: float
    lines: list[str] = Field(default_factory=list)
    is_hub: bool = False


class RailStation(BaseModel):
    name: str
    code: str
    lat: float
    lng: float


class TransitNode(BaseModel):
    id: str
    kind: Literal["bus", "metro", "rail"]
    name: str
    lat: float
    lng: float
    line: str | None = None
    routes: list[str] = Field(default_factory=list)


class FareResult(BaseModel):
    amount: float
    currency: str = "INR"
    per_person: float
    rule: str
    is_estimated: bool = False


class GHResult(BaseModel):
    geometry: list[Coordinate]
    distance_m: float
    duration_s: float
    mode: str
    points_encoded: bool = False
    path_source: str = "graphhopper"
