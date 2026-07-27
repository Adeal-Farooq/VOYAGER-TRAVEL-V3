"""Geocoding and spatial tools for LangGraph agents."""

import logging
from backend.services.clients.google_maps_client import google_maps_client

logger = logging.getLogger(__name__)
from backend.core.database import db


async def geocode(query: str) -> dict | None:
    """Geocode a place name or address to coordinates."""
    result = await google_maps_client.geocode(query)
    if result:
        return result
    return await geo_fallback(query)


async def geo_fallback(query: str) -> dict | None:
    """Fallback geocoding using local database."""
    stop = db.find_stop_by_name(query)
    if stop:
        return {
            "lat": stop.get("lat", 0) or stop.get("Latitude", 0),
            "lng": stop.get("lng", 0) or stop.get("Longitude", 0),
            "formatted_address": stop.get("name", query) or stop.get("Stop Name", query),
            "place_id": "",
        }
    # Check railway stations
    for station in db.railway_stations:
        if isinstance(station, dict) and query.lower() in station.get("name", "").lower():
            return {
                "lat": station.get("lat", 0),
                "lng": station.get("lng", 0),
                "formatted_address": station.get("name", query),
                "place_id": "",
            }
    return None


async def get_nearby_stations(lat: float, lng: float, radius_km: float = 1.0) -> list[dict]:
    """Find nearby bus stops, metro stations, railway stations."""
    results = []

    # Bus stops
    bus_stops = db.find_nearby_bus_stops(lat, lng, radius_km)
    for s in bus_stops:
        results.append({
            "name": s.get("name", "") or s.get("Stop Name", ""),
            "type": "bus_stop",
            "lat": s.get("lat", 0) or s.get("Latitude", 0),
            "lng": s.get("lng", 0) or s.get("Longitude", 0),
            "distance_km": _haversine(
                lat, lng,
                s.get("lat", 0) or s.get("Latitude", 0),
                s.get("lng", 0) or s.get("Longitude", 0),
            ),
        })

    # Metro stations
    metro_stations = db.find_nearby_metro_stations(lat, lng, radius_km)
    for s in metro_stations:
        results.append({
            "name": s.get("name", ""),
            "type": "metro_station",
            "lat": s.get("lat", 0),
            "lng": s.get("lng", 0),
            "distance_km": _haversine(lat, lng, s.get("lat", 0), s.get("lng", 0)),
        })

    return results


def _haversine(lat1, lng1, lat2, lng2):
    import math
    R = 6371
    dlat = (lat2 - lat1) * math.pi / 180
    dlng = (lng2 - lng1) * math.pi / 180
    a = math.sin(dlat/2)**2 + math.cos(lat1*math.pi/180) * math.cos(lat2*math.pi/180) * math.sin(dlng/2)**2
    return round(2 * R * math.asin(math.sqrt(a)), 2)


async def get_address_from_coords(lat: float, lng: float) -> str:
    """Reverse geocode coordinates to address."""
    if google_maps_client.api_key:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params={"latlng": f"{lat},{lng}", "key": google_maps_client.api_key, "region": "in"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("results"):
                        return data["results"][0].get("formatted_address", "")
        except Exception as e:
            logger.warning(f"Reverse geocode failed for {lat},{lng}: {e}")
    return f"{lat:.4f}, {lng:.4f}"
