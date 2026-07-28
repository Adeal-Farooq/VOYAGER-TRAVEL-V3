import asyncio
import math
import time
from geopy.distance import geodesic
from backend.core.database import db
from backend.agents.llm_agent import llm_agent
from backend.services.images import image_service
from backend.services.clients.google_maps_client import google_maps_client
import logging
logger = logging.getLogger(__name__)


class SearchCache:
    def __init__(self, ttl_seconds: int = 86400):
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        self._ttl = ttl_seconds

    def _make_key(self, query: str, lat: float = None, lng: float = None) -> str:
        if lat and lng:
            return f"{query.strip().lower()}|{round(lat,2)}|{round(lng,2)}"
        return query.strip().lower()

    def get(self, query: str, lat: float = None, lng: float = None):
        key = self._make_key(query, lat, lng)
        entry = self._cache.get(key)
        if entry and (time.time() - entry[0]) < self._ttl:
            return entry[1]
        if entry:
            del self._cache[key]
        return None

    def set(self, query: str, results: list[dict], lat: float = None, lng: float = None):
        key = self._make_key(query, lat, lng)
        self._cache[key] = (time.time(), results)

    def clear(self):
        self._cache.clear()

search_cache = SearchCache()

def _sanitize(val, default=0.0):
    if val is None: return default
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v): return default
        return v
    except (ValueError, TypeError):
        return default

def _score_from_rating(rating: float) -> float:
    r = _sanitize(rating, 3.0)
    return round(min(r, 5.0) / 5, 2)


class GeocodingService:

    async def search_places(self, query: str, lat: float = None, lng: float = None) -> list[dict]:
        cached = search_cache.get(query, lat, lng)
        if cached is not None:
            return cached

        results = []
        seen_coords = set()
        center_lat = lat or 12.9716
        center_lng = lng or 77.5946
        is_blr = lat is not None and lng is not None and self._in_bangalore(lat, lng)
        max_dist = 15 if is_blr else 50

        # Primary: Google Maps Places API
        gm_results = await google_maps_client.search_places(query, center_lat, center_lng, limit=10)
        query_words = set(query.lower().split())
        for r in gm_results:
            key = (round(r["lat"], 4), round(r["lng"], 4))
            if key in seen_coords:
                continue
            seen_coords.add(key)
            d = round(geodesic((center_lat, center_lng), (r["lat"], r["lng"])).km, 2)
            if d > max_dist:
                continue
            r_name_words = set(r.get("name", "").lower().split())
            r_addr_words = set(r.get("address", "").lower().split())
            overlap = query_words & (r_name_words | r_addr_words)
            if len(overlap) < max(1, len(query_words) * 0.4):
                continue
            r["distance_km"] = d
            r["reliability_score"] = _score_from_rating(r.get("rating", 4.0))
            results.append(r)

        # Supplement: local bus stop DB
        query_lower = query.lower().strip()
        for stop_id, stop in db.bus_stops.items():
            if not isinstance(stop, dict): continue
            name = stop.get("name", "")
            if isinstance(name, str) and query_lower in name.lower():
                key = (round(stop["lat"], 4), round(stop["lng"], 4))
                if key not in seen_coords:
                    seen_coords.add(key)
                    d = round(geodesic((center_lat, center_lng), (stop["lat"], stop["lng"])).km, 2)
                    if not is_blr or d <= 50:
                        results.append(self._make_result(name, stop["lat"], stop["lng"], "bus_stop",
                            "", 0.9, 4.0, distance_km=d))

        # Supplement: local metro DB
        for station in db.metro_stations:
            if not isinstance(station, dict): continue
            name = station.get("name", "")
            if isinstance(name, str) and query_lower in name.lower():
                key = (round(station["lat"], 4), round(station["lng"], 4))
                if key not in seen_coords:
                    seen_coords.add(key)
                    d = round(geodesic((center_lat, center_lng), (station["lat"], station["lng"])).km, 2)
                    if not is_blr or d <= 50:
                        results.append(self._make_result(name, station["lat"], station["lng"], "metro_station",
                            "", 0.95, 4.3, distance_km=d))

        for r in results:
            r["lat"] = _sanitize(r.get("lat"))
            r["lng"] = _sanitize(r.get("lng"))
            r["rating"] = _sanitize(r.get("rating", 4.0), 4.0)
            rr = _sanitize(r.get("rating", 4.0), 4.0)
            r["reliability_score"] = _sanitize(r.get("reliability_score", _score_from_rating(rr)), _score_from_rating(rr))

        results.sort(key=lambda x: x.get("distance_km", 999))
        out = results[:15]
        search_cache.set(query, out, lat, lng)
        return out

    async def get_nearby_places(self, lat: float, lng: float, radius_km: float = 2.0,
                                 place_type: str = None) -> list[dict]:
        results = []
        seen_coords = set()
        in_blr = self._in_bangalore(lat, lng)

        # Primary: Google Maps Nearby Search
        gm_results = await google_maps_client.get_nearby_places(lat, lng, radius_km, place_type)
        for r in gm_results:
            key = (round(r["lat"], 4), round(r["lng"], 4))
            if key in seen_coords:
                continue
            seen_coords.add(key)
            r["distance_km"] = round(geodesic((lat, lng), (r["lat"], r["lng"])).km, 2)
            r["reliability_score"] = _score_from_rating(r.get("rating", 4.0))
            results.append(r)

        # Retry wider if empty
        if not results and radius_km < 5:
            wider = min(radius_km * 2.5, 10.0)
            gm_retry = await google_maps_client.get_nearby_places(lat, lng, wider, place_type)
            for r in gm_retry:
                key = (round(r["lat"], 4), round(r["lng"], 4))
                if key in seen_coords:
                    continue
                seen_coords.add(key)
                r["distance_km"] = round(geodesic((lat, lng), (r["lat"], r["lng"])).km, 2)
                r["reliability_score"] = _score_from_rating(r.get("rating", 4.0))
                results.append(r)

        # Supplement: local bus stops (Bangalore only)
        if in_blr:
            if not place_type or place_type == "bus_stop":
                for stop in db.find_nearby_bus_stops(lat, lng, radius_km):
                    key = (round(stop["lat"], 4), round(stop["lng"], 4))
                    if key not in seen_coords:
                        seen_coords.add(key)
                        results.append(self._make_result(stop["name"], stop["lat"], stop["lng"], "bus_stop",
                            "", rating=4.0, distance_km=stop["distance_km"]))

            if not place_type or place_type == "metro_station":
                for station in db.find_nearby_metro_stations(lat, lng, radius_km):
                    key = (round(station["lat"], 4), round(station["lng"], 4))
                    if key not in seen_coords:
                        seen_coords.add(key)
                        results.append(self._make_result(station["name"], station["lat"], station["lng"], "metro_station",
                            "", rating=4.3, distance_km=station["distance_km"]))

        for r in results:
            r["lat"] = _sanitize(r.get("lat"))
            r["lng"] = _sanitize(r.get("lng"))
            r["rating"] = _sanitize(r.get("rating", 4.0), 4.0)
            rr2 = _sanitize(r.get("rating", 4.0), 4.0)
            r["reliability_score"] = _sanitize(r.get("reliability_score", _score_from_rating(rr2)), _score_from_rating(rr2))
            if "distance_km" in r:
                r["distance_km"] = _sanitize(r["distance_km"])

        results.sort(key=lambda x: x.get("distance_km", 999))
        enriched = await self._enrich_results(results[:12], light=True)
        return enriched[:20]

    async def get_suggestions(self, partial: str) -> list[str]:
        if len(partial) < 2:
            return []
        suggestions = set()

        # Primary: Google Places Autocomplete
        gm_suggestions = await google_maps_client.get_suggestions(partial)
        for s in gm_suggestions:
            suggestions.add(s)

        # Supplement: local bus stops
        q = partial.lower()
        for stop in db.bus_stops.values():
            n = stop.get("name", "")
            if isinstance(n, str) and q in n.lower():
                suggestions.add(n)
                if len(suggestions) >= 10:
                    break

        return list(suggestions)[:10]

    async def verify_place(self, name: str, address: str = None) -> dict:
        return await llm_agent.verify_place(name, address)

    async def _enrich_results(self, results: list[dict], light: bool = False) -> list[dict]:
        if not results:
            return results

        if not light:
            try:
                import asyncio
                sem = asyncio.Semaphore(3)

                async def enrich_place(r: dict):
                    async with sem:
                        try:
                            web_reviews = await llm_agent.get_real_reviews(r["name"], r.get("address"))
                            if web_reviews:
                                if web_reviews.get("rating"):
                                    r["rating"] = float(web_reviews["rating"])
                                r_rating = r.get("rating", 4.0) or 4.0
                                r["reliability_score"] = _score_from_rating(r_rating)
                                if web_reviews.get("review_summary"): r["review_summary"] = web_reviews["review_summary"]
                                if web_reviews.get("is_recommended") is not None: r["is_recommended"] = bool(web_reviews["is_recommended"])
                                if web_reviews.get("reviews"): r["reviews"] = web_reviews.get("reviews", [])[:4]
                                photos = web_reviews.get("photos", [])
                                if photos and photos[0]:
                                    r["image_url"] = photos[0]
                                r["review_source"] = "web"
                        except Exception as e:
                            logger.warning(f"Web reviews failed for {r.get('name')}: {e}")

                        if not r.get("image_url"):
                            try:
                                if r.get("place_type") not in ("bus_stop", "metro_station"):
                                    r["image_url"] = await image_service.get_place_image(r["name"], r.get("place_type"))
                            except Exception as e:
                                logger.warning(f"Image fallback failed for {r.get('name')}: {e}")

                        try:
                            if r.get("place_type") in ("hotel", "lodge") and not r.get("price_info"):
                                hp = await llm_agent.get_hotel_prices(r["name"])
                                if hp and hp.get("avg_price", 0) > 0:
                                    r["price_info"] = f"₹{hp.get('avg_price', 0)}/night (₹{hp.get('min_price',0)}-₹{hp.get('max_price',0)})"
                                    r["hotel_prices"] = hp
                        except Exception as e:
                            logger.warning(f"Prices failed for {r.get('name')}: {e}")

                tasks = [enrich_place(r) for r in results[:8]]
                await asyncio.gather(*tasks)
            except Exception as e:
                logger.warning(f"Enrich results gather failed: {e}")

        for r in results:
            r3_rating = r.get("rating", 4.0) or 4.0
            r.setdefault("rating", 4.0)
            r["reliability_score"] = _score_from_rating(r.get("rating", r3_rating) or 4.0)
            r.setdefault("review_summary", "")
            r.setdefault("is_recommended", r.get("reliability_score", 0.6) > 0.6)
            r.setdefault("address", f"{r['name']}, Bengaluru")

        return results

    async def enrich_single_place(self, name: str, lat: float, lng: float, place_type: str, address: str) -> dict:
        result = self._make_result(name, lat, lng, place_type, "", rating=4.0)
        result["address"] = address or f"{name}, Bengaluru"

        try:
            web_reviews = await llm_agent.get_real_reviews(name, address)
            if web_reviews:
                if web_reviews.get("rating"): result["rating"] = float(web_reviews["rating"])
                enriched_rating = float(web_reviews.get("rating", result.get("rating", 4.0)))
                result["reliability_score"] = _score_from_rating(enriched_rating)
                if web_reviews.get("review_summary"): result["review_summary"] = web_reviews["review_summary"]
                if web_reviews.get("is_recommended") is not None: result["is_recommended"] = bool(web_reviews["is_recommended"])
                if web_reviews.get("reviews"): result["reviews"] = web_reviews.get("reviews", [])[:4]
                photos = web_reviews.get("photos", [])
                if photos and photos[0]:
                    result["image_url"] = photos[0]
                result["review_source"] = "web"
        except Exception as e:
            logger.warning(f"Enrich single place reviews failed for {name}: {e}")

        if not result.get("image_url"):
            try:
                if place_type not in ("bus_stop", "metro_station"):
                    result["image_url"] = await image_service.get_place_image(name, place_type)
            except Exception as e:
                logger.warning(f"Image fetch fallback failed for {name}: {e}")

        try:
            if place_type in ("hotel", "lodge") and not result.get("price_info"):
                hp = await llm_agent.get_hotel_prices(name)
                if hp and hp.get("avg_price", 0) > 0:
                    result["price_info"] = f"₹{hp.get('avg_price', 0)}/night (₹{hp.get('min_price',0)}-₹{hp.get('max_price',0)})"
                    result["hotel_prices"] = hp
        except Exception as e:
            logger.warning(f"Enrich single place prices failed for {name}: {e}")
        return result

    def _make_result(self, name: str, lat: float, lng: float, place_type: str,
                      review: str, reliability: float = None, rating: float = None,
                      address: str = None, distance_km: float = None) -> dict:
        r_rating = _sanitize(rating, 4.0) if rating is not None else 4.0
        r_rel = _sanitize(reliability, _score_from_rating(r_rating)) if reliability is not None else _score_from_rating(r_rating)
        r = {
            "name": name, "lat": _sanitize(lat), "lng": _sanitize(lng),
            "place_type": place_type,
            "rating": r_rating, "review_summary": review,
            "address": address or f"{name}, Bengaluru",
            "reliability_score": r_rel,
            "is_recommended": r_rel > 0.6,
        }
        if distance_km is not None:
            r["distance_km"] = round(_sanitize(distance_km), 2)
        return r

    def _in_bangalore(self, lat: float, lng: float) -> bool:
        return 12.8 <= lat <= 13.2 and 77.4 <= lng <= 77.8

geocoding_service = GeocodingService()
