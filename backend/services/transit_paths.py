import logging
import math, random, httpx, asyncio
from backend.core.config import settings

logger = logging.getLogger(__name__)
from backend.core.database import db
from backend.services.transit_config import (
    _ensure_gtfs, _haversine_dist,
)


class TransitPathService:

    def __init__(self):
        self._path_cache = {}

    def interpolate_path(self, slat, slng, dlat, dlng, num_points=12):
        # Try OSRM foot for walkable distances first (real road paths)
        if num_points < 8 and _haversine_dist(slat, slng, dlat, dlng) <= 3.0:
            try:
                osrm_url = getattr(settings, 'OSRM_FOOT_URL', 'http://localhost:5001')
                import httpx
                with httpx.Client(timeout=1.5) as client:
                    url = f"{osrm_url}/route/v1/foot/{slng},{slat};{dlng},{dlat}?overview=full&geometries=geojson"
                    resp = client.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("code") == "Ok" and data.get("routes"):
                            coords = data["routes"][0]["geometry"]["coordinates"]
                            path = [[round(c[1], 6), round(c[0], 6)] for c in coords]
                            return path
            except Exception:
                pass
        if num_points < 1:
            return [[round(slat, 6), round(slng, 6)]]
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            lat = slat + (dlat - slat) * t
            lng = slng + (dlng - slng) * t
            points.append([round(lat, 6), round(lng, 6)])
        if num_points >= 4 and _haversine_dist(slat, slng, dlat, dlng) > 1.0:
            mid = num_points // 2
            bulge = _haversine_dist(slat, slng, dlat, dlng) * 0.008
            angle = math.atan2(dlat - slat, dlng - slng) + math.pi / 3
            for idx in [mid - 1, mid, mid + 1]:
                if 0 < idx < len(points):
                    points[idx][0] += math.sin(angle) * bulge * (0.5 if idx != mid else 1.0)
                    points[idx][1] += math.cos(angle) * bulge * (0.5 if idx != mid else 1.0)
        return points

    async def get_osrm_path_between(self, slat, slng, dlat, dlng, profile="driving"):
        key = (round(slat, 4), round(slng, 4), round(dlat, 4), round(dlng, 4), profile)
        if key in self._path_cache:
            return self._path_cache[key]
        try:
            base_url = settings.OSRM_FOOT_URL if profile in ("walking", "foot") else settings.OSRM_BASE_URL
            async with httpx.AsyncClient(timeout=2.0) as client:
                url = f"{base_url}/route/v1/{profile}/{slng},{slat};{dlng},{dlat}?overview=full&geometries=geojson"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        coords = data["routes"][0]["geometry"]["coordinates"]
                        path = [[c[1], c[0]] for c in coords]
                        self._path_cache[key] = path
                        return path
        except Exception as e:
            logger.warning(f"OSRM path fetch failed for {slat},{slng} -> {dlat},{dlng}: {e}")
        fallback = self.interpolate_path(slat, slng, dlat, dlng)
        self._path_cache[key] = fallback
        return fallback

    async def add_leg_paths(self, route: dict):
        _ensure_gtfs()
        tasks = []
        leg_indices = []
        for i, leg in enumerate(route.get("legs", [])):
            mode = leg.get("mode", "")
            f_lat, f_lng = leg.get("from_lat"), leg.get("from_lng")
            t_lat, t_lng = leg.get("to_lat"), leg.get("to_lng")

            if mode == "metro" and leg.get("from") and leg.get("to"):
                rail_path = db.get_metro_line_path(leg["from"], leg["to"])
                if rail_path:
                    route["legs"][i]["path"] = rail_path
                    continue

            if mode in ("bus_ordinary", "bus_ac_vajra", "kia_bus") and leg.get("from") and leg.get("to"):
                shape = _ensure_gtfs().get_shape_between_stops(leg["from"], leg["to"])
                if shape:
                    route["legs"][i]["path"] = [[lat, lng] for lat, lng in shape]
                    continue

            profile = "walking" if mode.startswith("walk") else "driving"

            if f_lat is not None and f_lng is not None and t_lat is not None and t_lng is not None:
                tasks.append(self.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile))
                leg_indices.append(i)
        if tasks:
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=30.0)
            for idx, path in zip(leg_indices, results):
                route["legs"][idx]["path"] = path

    async def get_osrm_route(self, slat, slng, dlat, dlng):
        key = ("route", round(slat, 4), round(slng, 4), round(dlat, 4), round(dlng, 4))
        if key in self._path_cache:
            return self._path_cache[key]
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{slng},{slat};{dlng},{dlat}?overview=full&geometries=geojson&steps=true"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok" and data.get("routes"):
                        route = data["routes"][0]
                        steps_raw = route.get("legs", [{}])[0].get("steps", [])
                        steps = []
                        for s in steps_raw:
                            steps.append({
                                "instruction": s.get("maneuver", {}).get("instruction", ""),
                                "modifier": s.get("maneuver", {}).get("modifier", ""),
                                "name": s.get("name", ""),
                                "distance": round(s.get("distance", 0) / 1000, 2),
                                "duration": round(s.get("duration", 0) / 60, 1),
                                "bearing_after": s.get("maneuver", {}).get("bearing_after", 0),
                                "type": s.get("maneuver", {}).get("type", "")
                            })
                        result = {
                            "distance_km": round(route["distance"] / 1000, 2),
                            "duration_minutes": round(route["duration"] / 60, 1),
                            "geometry": route["geometry"],
                            "steps": steps
                        }
                        self._path_cache[key] = result
                        return result
        except Exception as e:
            logger.warning(f"OSRM route parsing failed for {slat},{slng} -> {dlat},{dlng}: {e}")
        return None

    async def get_driving_route(self, slat, slng, dlat, dlng):
        result = await self.get_osrm_route(slat, slng, dlat, dlng)
        if not result:
            return None
        try:
            from backend.services.clients.google_maps_client import google_maps_client
            traffic = await google_maps_client.get_distance_matrix(slat, slng, dlat, dlng)
            if traffic and "duration_in_traffic_min" in traffic:
                result["duration_minutes"] = round(traffic["duration_in_traffic_min"], 1)
                result["distance_km"] = round(traffic["distance_km"], 2)
                result["traffic_source"] = "google_distance_matrix"
        except Exception:
            pass
        return result
