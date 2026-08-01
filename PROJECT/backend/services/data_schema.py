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


# ============================================================ PROMPT_4 models
# Search / place discovery + reliability + scoring. Single source of truth for
# the shapes produced by search_service.py / topsis_engine.py / ride_pricing.py.


class Place(BaseModel):
    """A place result from Google Places (New) Text/Nearby search."""
    place_id: str
    name: str
    address: str = ""
    lat: float = 0.0
    lng: float = 0.0
    rating: float | None = None
    user_rating_count: int | None = None
    price_level: int | None = None  # 0..4
    business_status: str | None = None  # OPERATIONAL / CLOSED_TEMPORARILY / CLOSED_PERMANENTLY
    open_now: bool | None = None
    weekday_hours: list[str] = Field(default_factory=list)
    types: list[str] = Field(default_factory=list)
    photo_name: str | None = None  # "places/<id>/photos/<ref>" — use place_photo_url()
    distance_km: float | None = None
    primary_type: str | None = None
    query: str = ""


class Review(BaseModel):
    """A single real review (SerpAPI place_details user_reviews)."""
    author_name: str = ""
    rating: float = 0.0
    text: str = ""
    date: str = ""
    source: str = "serpapi"


class PlaceDetails(Place):
    """Enriched place: reviews + hours + phone + website + photo."""
    phone: str | None = None
    website: str | None = None
    reviews: list[Review] = Field(default_factory=list)
    sentiment_avg: float | None = None  # polarity in [0,1]
    reliability_score: float | None = None  # 0..100
    pin_class: Literal["green", "yellow", "red"] | None = None
    summary: str = ""
    concerns: list[str] = Field(default_factory=list)


class ReliabilityInput(BaseModel):
    rating: float = 0.0
    review_count: int = 0
    sentiment_avg: float = 0.0
    business_status: str | None = None


class ReliabilityResult(BaseModel):
    score: float  # 0..1
    score_pct: int  # 0..100
    pin_class: Literal["green", "yellow", "red"]
    status_factor: float
    rating_part: float
    sentiment_part: float
    count_part: float


class RidePrice(BaseModel):
    provider: str
    mode: str
    total: float
    per_person: float
    eta_min: float | None = None
    source: Literal["live", "estimated"]
    note: str = ""


class TopsisWeights(BaseModel):
    time_of_day: float = 0.10
    cost: float = 0.20
    weather: float = 0.10
    traffic_crowd: float = 0.15
    availability: float = 0.05
    walking: float = 0.15
    group_size: float = 0.10
    safety: float = 0.15


class ScoringContext(BaseModel):
    """Real live signals feeding the 8 TOPSIS criteria (PROMPT_5 gathers these)."""
    time_of_day: str = "day"  # day | evening_rush | night | early_morning
    weather_condition: str = "clear"  # clear | rain | cloudy | fog
    rain_next_hour: bool = False
    traffic_ratio: float = 1.0  # duration_in_traffic / duration
    group_size: int = 1
    budget: float = 500.0
    area_risk: float = 0.0  # 0..1
    news_alerts: list[str] = Field(default_factory=list)


class ScoredRoute(BaseModel):
    """A RoutePlan + its 8-criterion TOPSIS score (rank-1 = best match)."""
    legs: list = Field(default_factory=list)
    total_fare: float = 0.0
    total_duration_min: int = 0
    total_walk_km: float = 0.0
    transfers: int = 0
    per_person_fare: float = 0.0
    scores: dict[str, float] = Field(default_factory=dict)
    cc_score: float = 0.0
    rank: int = 1
    best_match: bool = False
    explanation: str | None = None


class Suggestion(BaseModel):
    text: str
    place_id: str | None = None
    lat: float | None = None
    lng: float | None = None
