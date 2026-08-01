"""HTTP endpoints for the interactive segment planner (PROMPT_3), the
place search / scoring / pricing layer (PROMPT_4), and the live LangGraph
layer (PROMPT_5).

  POST /api/routes/segments        -> Segment 1 FULL + Segment 2 FULL + probes
  POST /api/routes/segment-next    -> next segment time-chained from chosen leg
  GET  /api/search/places          -> Google Places text search
  GET  /api/search/nearby          -> category nearby search
  POST /api/search/enrich          -> real reviews + reliability + summary
  POST /api/search/verify          -> pin a name+coords to a real place
  POST /api/rides/prices           -> live/estimated ride prices for a pair
  POST /api/langgraph/ask          -> full agent loop (chat/synthesis)
  POST /api/langgraph/route-context-> LiveContext for a route
  GET  /api/search/news            -> cached corridor news
  GET  /api/search/weather         -> Open-Meteo current + rain window
  GET  /api/routes/live-trains     -> eRail.in live trains (or flagged fallback)
"""
from pydantic import BaseModel, Field

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from backend.services import app_state
from backend.services.data_schema import Place

router = APIRouter()
search_router = APIRouter()  # /api/search/* + /api/rides/* (no /routes prefix)


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


class NearbyRequest(BaseModel):
    lat: float
    lng: float
    radius_m: int = Field(default=2000, ge=100, le=20000)
    keyword: str = ""
    categories: list[str] = Field(default_factory=list)


class EnrichRequest(BaseModel):
    place: dict


class VerifyRequest(BaseModel):
    name: str
    lat: float
    lng: float


class RidesRequest(BaseModel):
    origin: PlaceModel
    destination: PlaceModel
    group_size: int = Field(default=1, ge=1)


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


# ============================================================ PROMPT_4 search
@search_router.get("/search/places")
def search_places(q: str, lat: float | None = None, lng: float | None = None):
    svc = app_state.get_search()
    places = svc.search_places(q, lat=lat, lng=lng)
    return {"query": q, "places": [p.model_dump(mode="json") for p in places]}


@search_router.get("/search/nearby")
def search_nearby(lat: float, lng: float, radius_m: int = 2000,
                  keyword: str = "", categories: str = ""):
    svc = app_state.get_search()
    cats = [c.strip() for c in categories.split(",") if c.strip()]
    places = svc.nearby(lat, lng, radius_m=radius_m, keyword=keyword, categories=cats)
    return {"places": [p.model_dump(mode="json") for p in places]}


@search_router.post("/search/enrich")
def search_enrich(req: EnrichRequest):
    svc = app_state.get_search()
    try:
        place = Place(**req.place)
    except Exception:  # noqa: BLE001 — client sent a malformed place
        return {"error": "invalid place payload"}
    return svc.enrich(place)


@search_router.post("/search/verify")
def search_verify(req: VerifyRequest):
    svc = app_state.get_search()
    place = svc.verify(req.name, req.lat, req.lng)
    return {"verified": place.model_dump(mode="json") if place else None}


@search_router.post("/rides/prices")
def rides_prices(req: RidesRequest):
    svc = app_state.get_search()
    prices = svc.ride_prices(
        (req.origin.lat, req.origin.lng),
        (req.destination.lat, req.destination.lng),
        group_size=req.group_size,
    )
    return {"prices": [p.model_dump(mode="json") for p in prices]}


# ============================================================ PROMPT_5 live
class RouteContextRequest(BaseModel):
    source: PlaceModel
    destination: PlaceModel
    group_size: int = Field(default=1, ge=1)
    budget: float = Field(default=500.0, ge=0)
    current_time: str | None = None
    place: dict | None = None


class AskRequest(BaseModel):
    message: str
    lat: float | None = None
    lng: float | None = None
    context: dict | None = None


class TrainRequest(BaseModel):
    from_station: str
    to_station: str


@search_router.post("/langgraph/route-context")
def langgraph_route_context(req: RouteContextRequest):
    agent = app_state.get_agent()
    return agent.gather_route_context(
        src=req.source.model_dump(),
        dst=req.destination.model_dump(),
        group_size=req.group_size,
        budget=req.budget,
        current_time=req.current_time,
        place=req.place,
    )


@search_router.post("/langgraph/ask")
def langgraph_ask(req: AskRequest):
    agent = app_state.get_agent()
    return agent.ask(req.message, lat=req.lat, lng=req.lng, context=req.context)


@search_router.get("/search/news")
def search_news(lat: float | None = None, lng: float | None = None,
                keyword: str = "", limit: int = 10):
    engine = app_state.get_news()
    return {"items": engine.relevant(lat=lat, lng=lng, keyword=keyword, limit=limit)}


@search_router.get("/search/weather")
def search_weather(lat: float, lng: float):
    client = app_state.get_weather()
    return client.current(lat, lng) or {"condition": "unavailable"}


@search_router.get("/search/photo")
def search_photo(name: str, max_width: int = 400):
    """Proxy a real Google Places photo (keeps the API key server-side)."""
    svc = app_state.get_search()
    photo_name = name if name.startswith("places/") else f"places/{name}"
    url = svc.maps.place_photo_url("", photo_name, max_width=max_width)
    if not url:
        return {"error": "no photo"}
    return RedirectResponse(url)


@search_router.get("/routes/live-trains")
def live_trains(from_station: str, to_station: str):
    svc = app_state.get_trains()
    fc, tc = svc.code_for(from_station), svc.code_for(to_station)
    if not fc or not tc:
        return {"trains": [], "source": "none", "note": "no station codes mapped"}
    return svc.trains_between(fc, tc)
