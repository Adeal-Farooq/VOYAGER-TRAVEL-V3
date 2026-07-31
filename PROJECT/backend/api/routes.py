"""HTTP endpoints for the interactive segment planner (PROMPT_3).

  POST /api/routes/segments      -> Segment 1 FULL + Segment 2 FULL + probes
  POST /api/routes/segment-next  -> next segment time-chained from chosen leg
"""
from pydantic import BaseModel, Field

from fastapi import APIRouter

from backend.services import app_state

router = APIRouter()


class PlaceModel(BaseModel):
    lat: float
    lng: float
    name: str = ""


class SegmentsRequest(BaseModel):
    source: PlaceModel
    destination: PlaceModel
    group_size: int = Field(default=1, ge=1)
    budget: float = Field(default=500.0, ge=0)
    current_time: str | None = None


class ChosenLeg(BaseModel):
    optionId: str = ""
    arrivalTime: str | None = None
    destinationStop: str = ""


class SegmentNextRequest(BaseModel):
    journey: dict
    chosen_legs: list[ChosenLeg]
    group_size: int = Field(default=1, ge=1)
    budget: float = Field(default=500.0, ge=0)


@router.post("/segments")
def segments(req: SegmentsRequest):
    builder = app_state.get_builder()
    return builder.build_segments(
        source=req.source.model_dump(),
        destination=req.destination.model_dump(),
        group_size=req.group_size,
        budget=req.budget,
        current_time=req.current_time,
    )


@router.post("/segment-next")
def segment_next(req: SegmentNextRequest):
    builder = app_state.get_builder()
    return builder.build_segment_next(
        journey=req.journey,
        chosen_legs=[c.model_dump() for c in req.chosen_legs],
        group_size=req.group_size,
        budget=req.budget,
    )
