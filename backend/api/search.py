import asyncio
import logging
from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)
from backend.services.geocoding import geocoding_service
from backend.agents.llm_agent import llm_agent
from backend.services.langgraph.tools.review_tools import get_place_reviews
from backend.services.langgraph.agent import voyager_agent


langgraph_router = APIRouter(prefix="/api/langgraph", tags=["LangGraph"])

router = APIRouter(prefix="/api/search", tags=["Search"])


@router.get("/reviews")
async def get_reviews(
    name: str = Query(..., description="Place name"),
    address: str = Query(None, description="Place address")
):
    result = await get_place_reviews(name, address)
    return {"status": "success", "place": name, "reviews": result}


@langgraph_router.post("/ask")
async def langgraph_ask(body: dict):
    query = body.get("query", "")
    context = body.get("context", {})
    result = await voyager_agent.run(query, context)
    return {"status": "success", "result": result}

@router.get("/places")
async def search_places(
    q: str = Query(..., description="Search query"),
    lat: float = Query(None, description="User latitude"),
    lng: float = Query(None, description="User longitude")
):
    results = await geocoding_service.search_places(q, lat, lng)

    return {"status": "success", "results": results, "total": len(results)}

@router.get("/nearby")
async def search_nearby(
    lat: float = Query(..., description="Center latitude"),
    lng: float = Query(..., description="Center longitude"),
    radius_km: float = Query(2.0, description="Search radius in km"),
    place_type: str = Query(None, description="Type of place (mall, hospital, etc.)")
):
    try:
        results = await asyncio.wait_for(
            geocoding_service.get_nearby_places(lat, lng, radius_km, place_type), timeout=20.0
        )
    except asyncio.TimeoutError:
        results = []

    return {
        "status": "success",
        "center": {"lat": lat, "lng": lng},
        "radius_km": radius_km,
        "results": results,
        "total": len(results)
    }

@router.get("/suggestions")
async def get_suggestions(q: str = Query("", description="Partial query")):
    if len(q) < 2:
        return {"status": "success", "suggestions": []}

    suggestions = await geocoding_service.get_suggestions(q)

    return {"status": "success", "suggestions": suggestions}

@router.get("/verify-place")
async def verify_place(
    name: str = Query(..., description="Place name"),
    address: str = Query(None, description="Place address")
):
    result = await geocoding_service.verify_place(name, address)
    return {"status": "success", "place": name, "verification": result}

@router.get("/ai-chat")
async def ai_chat(
    message: str = Query(..., description="User message"),
    lat: float = Query(None),
    lng: float = Query(None)
):
    context = {"lat": lat, "lng": lng} if lat and lng else None
    response = await llm_agent.chat_response(message, context)
    return {"status": "success", "response": response}

@router.post("/enrich-place")
async def enrich_place(body: dict):
    name = body.get("name", "")
    lat = body.get("lat")
    lng = body.get("lng")
    place_type = body.get("place_type", "place")
    address = body.get("address", "")
    try:
        enriched = await asyncio.wait_for(
            geocoding_service.enrich_single_place(name, lat, lng, place_type, address), timeout=25.0
        )
    except asyncio.TimeoutError:
        enriched = {"name": name, "rating": 3.0, "review_summary": "No reviews yet", "reliability_score": 0.5}
    return {"status": "success", "place": enriched}

@router.get("/ride-prices")
async def get_ride_prices(
    source: str = Query(..., description="Source location name"),
    destination: str = Query(..., description="Destination location name"),
    source_lat: float = Query(None, description="Source latitude"),
    source_lng: float = Query(None, description="Source longitude"),
    dest_lat: float = Query(None, description="Dest latitude"),
    dest_lng: float = Query(None, description="Dest longitude"),
):
    if source_lat is not None and source_lng is not None and dest_lat is not None and dest_lng is not None:
        prices = await llm_agent.estimate_ride_prices_coords(source_lat, source_lng, dest_lat, dest_lng)
    else:
        prices = await llm_agent.get_live_prices(source, destination, mode="all")
    mapped = []
    for p in (prices or []):
        mapped.append({
            "provider": p.get("service", p.get("name", "Ride")),
            "mode": p.get("key", p.get("mode", "cab")),
            "price": p.get("fare", p.get("price", 0)),
            "eta_minutes": p.get("duration_min", p.get("eta_minutes", 0)),
            "note": f"{'Live' if p.get('is_live') else 'Estimated'} • {p.get('distance_km', 0):.1f}km" if p.get('distance_km') else None,
            "source": p.get("source", "estimated"),
        })
    return {"status": "success", "source": source, "destination": destination, "prices": mapped}

@router.get("/current-events")
async def current_events(location: str = Query("Bengaluru")):
    events = await llm_agent.get_current_events(location)
    return {"status": "success", "location": location, "events": events}

@router.get("/weather")
async def weather_endpoint(lat: float = Query(...), lng: float = Query(...)):
    try:
        result = await llm_agent.get_weather_impact(lat=lat, lng=lng)
        return {"status": "success", "weather": result}
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return {"status": "error", "weather": {}}
