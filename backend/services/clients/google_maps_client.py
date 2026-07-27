import logging
import httpx
from backend.core.config import settings

logger = logging.getLogger(__name__)
from backend.services.scrapers.ride_scraper import ride_scraper


class GoogleMapsClient:
    """Google Maps API client for distance matrix and traffic data."""

    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY

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
