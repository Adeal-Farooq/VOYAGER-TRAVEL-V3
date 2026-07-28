import logging
import httpx
from backend.core.config import settings

logger = logging.getLogger(__name__)
from backend.services.scrapers.ride_scraper import ride_scraper


_PLACE_TYPE_MAP = {
    "mall": "shopping_mall", "hospital": "hospital", "clinic": "hospital",
    "atm": "atm", "bank": "bank", "restaurant": "restaurant", "cafe": "cafe",
    "hotel": "lodging", "lodge": "lodging",
    "temple": "place_of_worship", "mosque": "mosque", "church": "church",
    "school": "school", "park": "park", "petrol_pump": "gas_station",
    "charging_station": "electric_vehicle_charging_station",
    "police": "police", "bus_stop": "transit_station",
    "metro_station": "subway_station", "airport": "airport",
    "railway_station": "train_station", "pharmacy": "pharmacy",
    "supermarket": "supermarket", "gym": "gym", "library": "library",
    "cinema": "movie_theater", "post_office": "post_office",
    "it_hub": "local_government_office", "college": "university",
    "institute": "university",
}

_BACKWARD_TYPE_MAP = {
    "shopping_mall": "mall", "hospital": "hospital",
    "atm": "atm", "bank": "bank", "restaurant": "restaurant",
    "cafe": "cafe", "lodging": "hotel", "place_of_worship": "temple",
    "school": "school", "park": "park", "gas_station": "petrol_pump",
    "electric_vehicle_charging_station": "charging_station",
    "police": "police_station", "transit_station": "bus_stop",
    "subway_station": "metro_station", "airport": "airport",
    "train_station": "railway_station", "pharmacy": "pharmacy",
    "supermarket": "supermarket", "gym": "gym", "library": "library",
    "movie_theater": "cinema", "post_office": "post_office",
    "local_government_office": "it_hub", "university": "college",
    "mosque": "mosque", "church": "church",
}


class GoogleMapsClient:
    """Google Maps API client for places, geocoding, distance matrix."""

    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY

    async def search_places(self, query: str, lat: float = None, lng: float = None, limit: int = 10) -> list[dict]:
        if not self.api_key:
            return []
        params = {
            "query": query,
            "key": self.api_key,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address,geometry,types,rating",
            "region": "in",
        }
        if lat and lng:
            params["locationbias"] = f"point:{lat},{lng}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/findplacefromtext/json", params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for c in data.get("candidates", data.get("results", [])):
                        loc = c.get("geometry", {}).get("location", {})
                        types = c.get("types", [])
                        ptype = self._map_place_type(types)
                        results.append({
                            "name": c.get("name", query),
                            "lat": loc.get("lat", 0),
                            "lng": loc.get("lng", 0),
                            "place_type": ptype,
                            "rating": c.get("rating", 4.0) or 4.0,
                            "address": c.get("formatted_address", f"{query}, Bengaluru"),
                            "place_id": c.get("place_id", ""),
                            "source": "google_maps",
                        })
                    return results[:limit]
        except Exception as e:
            logger.warning(f"Google Maps findplacefromtext failed for '{query}': {e}")

        # Fallback: textsearch
        try:
            search_params = {
                "query": query,
                "key": self.api_key,
                "region": "in",
            }
            if lat and lng:
                search_params["location"] = f"{lat},{lng}"
                search_params["radius"] = 50000
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json", params=search_params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for r in data.get("results", []):
                        loc = r.get("geometry", {}).get("location", {})
                        types = r.get("types", [])
                        ptype = self._map_place_type(types)
                        results.append({
                            "name": r.get("name", query),
                            "lat": loc.get("lat", 0),
                            "lng": loc.get("lng", 0),
                            "place_type": ptype,
                            "rating": r.get("rating", 4.0) or 4.0,
                            "address": r.get("formatted_address", f"{query}, Bengaluru"),
                            "place_id": r.get("place_id", ""),
                            "source": "google_maps",
                        })
                    return results[:limit]
        except Exception as e:
            logger.warning(f"Google Maps textsearch failed for '{query}': {e}")
        return []

    async def get_suggestions(self, partial: str, lat: float = None, lng: float = None) -> list[str]:
        if not self.api_key or len(partial) < 2:
            return []
        params = {
            "input": partial,
            "key": self.api_key,
            "types": "establishment|geocode",
            "region": "in",
            "components": "country:in",
        }
        if lat and lng:
            params["location"] = f"{lat},{lng}"
            params["radius"] = 50000
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/autocomplete/json", params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return [p["description"] for p in data.get("predictions", [])[:8]]
        except Exception as e:
            logger.warning(f"Google Maps autocomplete failed for '{partial}': {e}")
        return []

    async def get_nearby_places(self, lat: float, lng: float, radius_km: float = 2.0,
                                 place_type: str = None) -> list[dict]:
        if not self.api_key:
            return []
        radius_m = min(int(radius_km * 1000), 50000)
        gm_type = _PLACE_TYPE_MAP.get(place_type) if place_type else None

        params = {
            "location": f"{lat},{lng}",
            "radius": radius_m,
            "key": self.api_key,
        }
        if gm_type:
            params["type"] = gm_type
        else:
            # No type filter - use keyword and nearbysearch
            params["keyword"] = "place in Bengaluru"

        results = []
        seen_ids = set()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/place/nearbysearch/json", params=params
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for r in data.get("results", []):
                        pid = r.get("place_id", "")
                        if pid in seen_ids:
                            continue
                        seen_ids.add(pid)
                        loc = r.get("geometry", {}).get("location", {})
                        types = r.get("types", [])
                        ptype = self._map_place_type(types)
                        results.append({
                            "name": r.get("name", "Place"),
                            "lat": loc.get("lat", 0),
                            "lng": loc.get("lng", 0),
                            "place_type": ptype,
                            "rating": r.get("rating", 4.0) or 4.0,
                            "address": r.get("vicinity", f"Bengaluru"),
                            "place_id": pid,
                            "source": "google_maps",
                        })
                    # Try next page if available
                    next_token = data.get("next_page_token")
                    if next_token and len(results) < 20:
                        import asyncio
                        await asyncio.sleep(1)
                        resp2 = await client.get(
                            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                            params={"pagetoken": next_token, "key": self.api_key}
                        )
                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            for r in data2.get("results", []):
                                pid = r.get("place_id", "")
                                if pid in seen_ids:
                                    continue
                                seen_ids.add(pid)
                                loc = r.get("geometry", {}).get("location", {})
                                types = r.get("types", [])
                                ptype = self._map_place_type(types)
                                results.append({
                                    "name": r.get("name", "Place"),
                                    "lat": loc.get("lat", 0),
                                    "lng": loc.get("lng", 0),
                                    "place_type": ptype,
                                    "rating": r.get("rating", 4.0) or 4.0,
                                    "address": r.get("vicinity", f"Bengaluru"),
                                    "place_id": pid,
                                    "source": "google_maps",
                                })
        except Exception as e:
            logger.warning(f"Google Maps nearbysearch failed for {lat},{lng} type={place_type}: {e}")
        return results[:20]

    def _map_place_type(self, types: list) -> str:
        for t in types:
            if t in _BACKWARD_TYPE_MAP:
                return _BACKWARD_TYPE_MAP[t]
        if "food" in types:
            return "restaurant"
        if "health" in types:
            return "hospital"
        if "store" in types:
            return "supermarket"
        return types[0] if types else "place"

    async def get_distance_matrix(
        self, origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
    ) -> dict | None:
        """Get distance, duration, and traffic duration between two points."""
        if not self.api_key:
            return None

        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{dest_lat},{dest_lng}",
            "key": self.api_key,
            "mode": "driving",
            "departure_time": "now",
            "units": "metric",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/distancematrix/json",
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("rows"):
                        elements = data["rows"][0].get("elements", [])
                        if elements and elements[0].get("status") == "OK":
                            elem = elements[0]
                            return {
                                "distance_km": elem["distance"]["value"] / 1000,
                                "distance_text": elem["distance"]["text"],
                                "duration_min": elem["duration"]["value"] / 60,
                                "duration_text": elem["duration"]["text"],
                                "duration_in_traffic_min": elem.get("duration_in_traffic", {}).get("value", elem["duration"]["value"]) / 60,
                                "duration_in_traffic_text": elem.get("duration_in_traffic", {}).get("text", elem["duration"]["text"]),
                            }
        except Exception as e:
            logger.warning(f"Google Maps distance matrix failed for {origin_lat},{origin_lng} -> {dest_lat},{dest_lng}: {e}")
            return None
        return None

    async def estimate_ride_prices(
        self, origin_lat: float, origin_lng: float,
        dest_lat: float, dest_lng: float,
        group_size: int = 1, budget: float = 0,
    ) -> list[dict]:
        """Get ride prices using proxy scraping + Google Maps traffic data."""
        return await ride_scraper.get_prices(
            origin_lat, origin_lng, dest_lat, dest_lng, group_size, budget
        )

    async def geocode(self, query: str) -> dict | None:
        """Geocode an address or place name."""
        if not self.api_key:
            return None

        params = {
            "address": query,
            "key": self.api_key,
            "region": "in",
            "components": "administrative_area:Bangalore|country:IN",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://maps.googleapis.com/maps/api/geocode/json",
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "OK" and data.get("results"):
                        result = data["results"][0]
                        location = result["geometry"]["location"]
                        return {
                            "lat": location["lat"],
                            "lng": location["lng"],
                            "formatted_address": result.get("formatted_address", query),
                            "place_id": result.get("place_id", ""),
                        }
        except Exception as e:
            logger.warning(f"Google Maps geocode failed for '{query}': {e}")
            return None
        return None


google_maps_client = GoogleMapsClient()
