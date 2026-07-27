"""Real ride pricing via govt-mandated Karnataka rates + Google Maps traffic."""

import httpx, json
from backend.services.proxy_manager import proxy_manager
from backend.core.config import settings

_RIDE_RATES = {
    "uber_go": {"base": 25, "per_km": 12, "per_min": 1.0, "min_fare": 50, "seats": 3, "name": "Uber Go / Ola Mini", "first_km_free": 0},
    "ola_mini": {"base": 25, "per_km": 12, "per_min": 1.0, "min_fare": 50, "seats": 3, "name": "Ola Mini", "first_km_free": 0},
    "cab_sedan": {"base": 50, "per_km": 24, "per_min": 1.5, "min_fare": 100, "seats": 3, "name": "Uber Priority / Ola Prime", "first_km_free": 0},
    "cab_xl": {"base": 100, "per_km": 30, "per_min": 2.0, "min_fare": 150, "seats": 6, "name": "Uber XL / Ola XL", "first_km_free": 0},
    "auto": {"base": 15, "per_km": 9, "per_min": 0.5, "min_fare": 25, "seats": 3, "name": "Auto", "first_km_free": 0},
    "bike": {"base": 10, "per_km": 5, "per_min": 0.5, "min_fare": 15, "seats": 1, "name": "Rapido Bike / Uber Moto", "first_km_free": 0},
    "cab_women": {"base": 25, "per_km": 12, "per_min": 1.0, "min_fare": 50, "seats": 3, "name": "Uber for Women", "first_km_free": 0},
    "cab_pet": {"base": 50, "per_km": 18, "per_min": 1.5, "min_fare": 100, "seats": 3, "name": "Uber Pet / Premier", "first_km_free": 0},
}


class RideScraper:
    async def get_prices(self, src_lat, src_lng, dest_lat, dest_lng, group_size=1, budget=0):
        real = await self._scrape_serpapi_directions(src_lat, src_lng, dest_lat, dest_lng)
        if real:
            return self._filter_real_prices(real, group_size, budget)

        dist, dur = await self._get_distance_duration(src_lat, src_lng, dest_lat, dest_lng)
        if dist is None:
            return []
        surge = await self._get_surge_factor(src_lat, src_lng)

        estimates = []
        for key, rate in _RIDE_RATES.items():
            if group_size > rate["seats"]:
                continue
            if dist <= rate.get("first_km_free", 0):
                fare = rate["min_fare"]
            else:
                chargeable_km = dist - rate.get("first_km_free", 0)
                base_fare = rate["base"] + (chargeable_km * rate["per_km"]) + (dur * rate["per_min"])
                base_fare = max(base_fare, rate["min_fare"])
                fare = round(max(base_fare * (1.0 + surge), rate["min_fare"]))
                if budget > 0 and fare > budget:
                    continue
                estimates.append({
                    "service": rate["name"], "key": key, "fare": fare,
                    "fare_min": round(base_fare),
                    "fare_max": round(max(base_fare * 1.35, rate["min_fare"])),
                    "distance_km": round(dist, 1), "duration_min": round(dur),
                    "surge": round(surge * 100), "seats": rate["seats"],
                    "type": "ride", "currency": "INR",
                    "source": "estimated", "is_live": False,
                })
        estimates.sort(key=lambda x: x["fare"])
        return estimates

    async def _scrape_serpapi_directions(self, slat, slng, dlat, dlng):
        """Try SerpAPI Google Maps Directions for ride estimates."""
        if not settings.SERPAPI_API_KEY:
            return None
        try:
            params = {
                "engine": "google_maps_directions",
                "start_coord": f"{slat},{slng}",
                "end_coord": f"{dlat},{dlng}",
                "api_key": settings.SERPAPI_API_KEY,
                "travel_mode": "driving",
                "hl": "en", "gl": "in",
            }
            async with httpx.AsyncClient(timeout=12.0) as c:
                resp = await c.get("https://serpapi.com/search", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    routes = data.get("directions", []) or data.get("routes", [])
                    rides = self._parse_serpapi_directions(routes)
                    if rides:
                        return rides
        except Exception:
            pass
        return None

    def _parse_serpapi_directions(self, routes):
        """Extract ride estimates from SerpAPI directions response."""
        if not routes:
            return None
        estimates = []
        seen_keys = set()
        for route in routes[:3]:
            fare_data = route.get("fare", {}) or route.get("cost", {})
            if fare_data:
                fare = fare_data.get("value", 0) if isinstance(fare_data, dict) else fare_data
                try:
                    fare = int(fare)
                except (ValueError, TypeError):
                    fare = 0
                if fare > 0:
                    label = route.get("label", route.get("name", "Taxi")).lower()
                    key = "taxi"
                    if "auto" in label: key = "auto"
                    elif "bike" in label: key = "bike"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        estimates.append({
                            "service": route.get("label", route.get("name", "Taxi")),
                            "key": key, "fare": fare,
                            "distance_km": route.get("distance", {}).get("value", 0) / 1000 if isinstance(route.get("distance"), dict) else route.get("distance", 0),
                            "duration_min": route.get("duration", {}).get("value", 0) / 60 if isinstance(route.get("duration"), dict) else route.get("duration", 0),
                            "surge": 1.0, "seats": 4,
                            "type": "ride", "currency": "INR",
                            "source": "serpapi", "is_live": True,
                        })
        return estimates if estimates else None

    def _filter_real_prices(self, prices, group_size, budget):
        filtered = []
        for p in prices:
            if p["seats"] < group_size:
                continue
            if p.get("fare", 0) <= 0:
                continue
            if budget > 0 and p.get("fare", 0) > budget:
                continue
            filtered.append(p)
        return sorted(filtered, key=lambda x: x.get("fare", 999))

    async def _get_surge_factor(self, lat, lng):
        from backend.services.clients.weather_client import weather_client
        try:
            weather = await weather_client.get_weather_impact(lat, lng)
            if weather and "surge_multiplier" in weather:
                return weather["surge_multiplier"]
        except Exception:
            pass
        from datetime import datetime
        h = datetime.now().hour
        w = datetime.now().weekday()
        surge = 0.0
        if h < 6:
            surge += 0.10
        if w < 5 and (8 <= h < 10 or 17 <= h < 20):
            surge += 0.25
        elif w >= 5 and (10 <= h < 14 or 18 <= h < 22):
            surge += 0.20
        if 12 <= h < 14 or 20 <= h < 23:
            surge += 0.05
        return surge

    async def _get_distance_duration(self, src_lat, src_lng, dest_lat, dest_lng):
        if settings.GOOGLE_MAPS_API_KEY:
            try:
                params = {
                    "origins": f"{src_lat},{src_lng}",
                    "destinations": f"{dest_lat},{dest_lng}",
                    "key": settings.GOOGLE_MAPS_API_KEY,
                    "mode": "driving", "departure_time": "now", "units": "metric",
                }
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(
                        "https://maps.googleapis.com/maps/api/distancematrix/json", params=params
                    )
                    if resp.status_code == 200:
                        d = resp.json()
                        if d.get("status") == "OK" and d.get("rows"):
                            e = d["rows"][0].get("elements", [{}])[0]
                            if e.get("status") == "OK":
                                return e["distance"]["value"] / 1000, e["duration"]["value"] / 60
            except Exception:
                pass
        from geopy.distance import geodesic
        d = geodesic((src_lat, src_lng), (dest_lat, dest_lng)).km
        return d, d * 2


ride_scraper = RideScraper()