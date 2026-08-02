"""Google Maps Platform client (PROMPT_4 §2.1).

Wraps the Places API (New), Geocoding API and Directions API with real,
honest data only. Every method returns `None`/empty on any failure so callers
never see fabricated results — a missing API key or network error simply means
"no data" (the search_service falls back or labels it Unavailable).

- Places (New): Text Search + Nearby + Place Details + photo URL
- Geocoding: query -> lat/lng
- Directions: origin/dest -> polyline + duration_in_traffic ratio

Verification rules (PROMPT_4 §2.1):
- >=40% keyword overlap between query and result name/address
- coordinates within `radius_km` of the reference point (Bangalore default)
- dedup by rounded coordinates (4 decimals)
"""
import json
import logging
import math
import time
from typing import Literal

import requests

from ... import config

logger = logging.getLogger(__name__)

_PLACES_BASE = "https://places.googleapis.com/v1"
_LEGACY_BASE = "https://maps.googleapis.com/maps/api"
_OSM_SEARCH = "https://nominatim.openstreetmap.org/search"

# 40% keyword overlap requirement (PROMPT_4 §2.1)
MIN_KEYWORD_OVERLAP = 0.40
_DEDUP_RND = 4  # dedup places whose coords round to 4 decimals (~11m)
_DEFAULT_TIMEOUT = 4.0
_CACHE_TTL_S = 24 * 3600  # place search/details cache 24h (PROMPT_4 §2.5)
_GOOGLE_DEAD_GRACE_S = 10 * 60  # skip Google entirely for 10min after a 401/403

# Bangalore reference center (search verifies results within this radius)
BANGALORE_CENTER = (12.9716, 77.5946)
BANGALORE_RADIUS_KM = 15.0


def _haversine_km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _tokens(s: str) -> set[str]:
    import re

    return {w.lower() for w in re.findall(r"[a-z0-9]+", s.lower())}


def _keyword_overlap(query: str, name: str, address: str) -> float:
    """Fraction of query tokens present in name/address (PROMPT_4 §2.1)."""
    q = _tokens(query)
    if not q:
        return 1.0
    hay = _tokens(name) | _tokens(address)
    return len(q & hay) / len(q)


class GoogleMapsClient:
    def __init__(self, api_key: str | None = None, radius_km: float = BANGALORE_RADIUS_KM,
                 center: tuple[float, float] = BANGALORE_CENTER, timeout_s: float = _DEFAULT_TIMEOUT):
        self._key = api_key or config.env_str("GOOGLE_MAPS_API_KEY")
        self._radius_km = radius_km
        self._center = center
        self._timeout = timeout_s
        self._cache: dict[str, tuple[float, object]] = {}
        self._google_dead_until = 0.0  # set after 401/403 so fallback is instant
        self._lock = None  # single-threaded FastAPI sync handlers
        if not self._key:
            logger.warning("[maps] GOOGLE_MAPS_API_KEY missing — place/directions data unavailable")

    # ------------------------------------------------------------- caching
    def _cached(self, key: str):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL_S:
            return hit[1]
        return None

    def _store(self, key: str, value) -> None:
        self._cache[key] = (time.time(), value)
        if len(self._cache) > 2000:  # bound memory
            oldest = min(self._cache.items(), key=lambda kv: kv[1][0])
            self._cache.pop(oldest[0], None)

    # --------------------------------------------------------------- helpers
    def _places_headers(self) -> dict:
        return {"X-Goog-Api-Key": self._key, "Content-Type": "application/json"}

    @staticmethod
    def _photo_url(photo_name: str | None, max_width: int = 400) -> str | None:
        if not photo_name:
            return None
        return (f"https://places.googleapis.com/v1/{photo_name}/media"
                f"?maxWidthPx={max_width}&key=PLACEHOLDER")

    def place_photo_url(self, place_id: str, photo_name: str | None, max_width: int = 400) -> str | None:
        """Real Google Places photo URL (requires API key in query param at fetch time)."""
        if not photo_name:
            return None
        return (f"https://places.googleapis.com/v1/{photo_name}/media"
                f"?maxWidthPx={max_width}&key={self._key}")

    # --------------------------------------------------------------- geocode
    def geocode(self, query: str) -> dict | None:
        """Query -> {lat, lng, name, address} via Geocoding API (OSM fallback)."""
        key = f"geocode:{query.strip().lower()}"
        cached = self._cached(key)
        if cached is not None:
            return cached
        out = None
        if self._key and time.time() >= self._google_dead_until:
            try:
                resp = requests.get(
                    f"{_LEGACY_BASE}/geocode/json",
                    params={"address": query, "key": self._key},
                    timeout=self._timeout,
                )
                if resp.status_code in (401, 403):
                    self._google_dead_until = time.time() + _GOOGLE_DEAD_GRACE_S
                resp.raise_for_status()
                data = resp.json()
                loc = data["results"][0]["geometry"]["location"]
                out = {
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "name": data["results"][0].get("formatted_address", query),
                    "address": data["results"][0].get("formatted_address", ""),
                }
            except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
                logger.warning("[maps] geocode(%s) failed: %s", query, exc)
                out = None
        if not out:
            out = self._osm_geocode(query)
        self._store(key, out)
        return out

    def _osm_geocode(self, query: str) -> dict | None:
        """OpenStreetMap Nominatim geocode -> {lat, lng, name, address}."""
        try:
            resp = requests.get(
                _OSM_SEARCH, params={"q": query, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": "VOYAGER-v2/0.3 (college transit project)"},
                timeout=6.0)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            r = data[0]
            return {
                "lat": float(r.get("lat", 0.0)),
                "lng": float(r.get("lon", 0.0)),
                "name": r.get("name") or r.get("display_name", query),
                "address": r.get("display_name", ""),
            }
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[osm] geocode(%s) failed: %s", query, exc)
            return None

    # ---------------------------------------------------------------- search
    def search_places(self, query: str, lat: float | None = None, lng: float | None = None,
                      radius_m: int = 15000) -> list[dict]:
        """Text Search (New) -> OSM Nominatim fallback. Verified + deduped."""
        key = f"search:{query.strip().lower()}:{lat}:{lng}"
        cached = self._cached(key)
        if cached is not None:
            return list(cached)
        if not self._key or time.time() < self._google_dead_until:
            out = self._osm_places(query, lat, lng, radius_m)
            self._store(key, list(out))
            return out
        body: dict = {"textQuery": query}
        clat, clng = (lat, lng) if lat is not None else self._center
        body["locationBias"] = {
            "circle": {"center": {"latitude": clat, "longitude": clng}, "radius": radius_m}
        }
        out = []
        try:
            resp = requests.post(
                f"{_PLACES_BASE}/places:searchText",
                headers=self._headers_with_mask(
                    "places.id,places.displayName,places.formattedAddress,"
                    "places.location,places.rating,places.userRatingCount,"
                    "places.priceLevel,places.businessStatus,places.types,"
                    "places.primaryType,places.photos,places.regularOpeningHours,"
                    "places.nationalPhoneNumber,places.websiteUri"),
                json=body, timeout=self._timeout)
            if resp.status_code in (401, 403):
                self._google_dead_until = time.time() + _GOOGLE_DEAD_GRACE_S
            resp.raise_for_status()
            data = resp.json()
            seen = set()
            for p in data.get("places", []):
                if not self._keyword_ok(query, p):
                    continue
                loc = p.get("location", {})
                plat, plng = loc.get("latitude"), loc.get("longitude")
                if plat is None or plng is None:
                    continue
                if not self._in_radius(plat, plng):
                    continue
                coord_key = (round(plat, _DEDUP_RND), round(plng, _DEDUP_RND))
                if coord_key in seen:
                    continue
                seen.add(coord_key)
                out.append(self._to_place_dict(p, query))
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[maps] search_places(%s) failed: %s", query, exc)
        if not out:
            out = self._osm_places(query, lat, lng, radius_m)
        self._store(key, list(out))
        return out

    def nearby_places(self, lat: float, lng: float, radius_m: int, category: str) -> list[dict]:
        """Nearby Search (New) -> OSM Nominatim fallback. Verified + deduped."""
        key = f"nearby:{round(lat,4)}:{round(lng,4)}:{radius_m}:{category.lower()}"
        cached = self._cached(key)
        if cached is not None:
            return list(cached)
        if not self._key or time.time() < self._google_dead_until:
            return self._osm_nearby(lat, lng, radius_m, category)
        body = {
            "locationRestriction": {
                "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": radius_m}
            },
            "maxResultCount": 20,
        }
        if category and category.lower() not in ("all", "nearby", ""):
            body["includedPrimaryTypes"] = self._category_primary_types(category)
        out = []
        try:
            resp = requests.post(
                f"{_PLACES_BASE}/places:searchNearby",
                headers=self._headers_with_mask(
                    "places.id,places.displayName,places.formattedAddress,"
                    "places.location,places.rating,places.userRatingCount,"
                    "places.priceLevel,places.businessStatus,places.types,"
                    "places.primaryType,places.photos,places.regularOpeningHours,"
                    "places.dist"),
                json=body, timeout=self._timeout)
            if resp.status_code in (401, 403):
                self._google_dead_until = time.time() + _GOOGLE_DEAD_GRACE_S
            resp.raise_for_status()
            data = resp.json()
            seen = set()
            for p in data.get("places", []):
                loc = p.get("location", {})
                plat, plng = loc.get("latitude"), loc.get("longitude")
                if plat is None or plng is None:
                    continue
                coord_key = (round(plat, _DEDUP_RND), round(plng, _DEDUP_RND))
                if coord_key in seen:
                    continue
                seen.add(coord_key)
                d = self._to_place_dict(p, category)
                d["distance_km"] = round(_haversine_km(lat, lng, plat, plng), 2)
                out.append(d)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[maps] nearby_places(%s) failed: %s", category, exc)
        if not out:
            out = self._osm_nearby(lat, lng, radius_m, category)
        self._store(key, list(out))
        return out

    # --------------------------------------------------------------- OSM (fallback)
    def _osm_places(self, query: str, lat: float | None, lng: float | None, radius_m: int) -> list[dict]:
        """OpenStreetMap Nominatim search -> same place-dict shape. Real POIs."""
        params = {
            "q": query,
            "format": "jsonv2",
            "limit": 8,
            "addressdetails": 1,
            "accept-language": "en",
        }
        if lat is None or lng is None:
            lat, lng = self._center
        if lat is not None and lng is not None:
            # bound results to a box around the reference point
            deg_lat = radius_m / 111320.0
            deg_lng = radius_m / (111320.0 * max(0.1, math.cos(math.radians(lat))))
            params["viewbox"] = f"{lng - deg_lng},{lat + deg_lat},{lng + deg_lng},{lat - deg_lat}"
            params["bounded"] = 1
        try:
            resp = requests.get(
                _OSM_SEARCH, params=params,
                headers={"User-Agent": "VOYAGER-v2/0.3 (college transit project)"},
                timeout=6.0)
            resp.raise_for_status()
            return [self._to_osm_place_dict(r, query) for r in resp.json()]
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[osm] search(%s) failed: %s", query, exc)
            return []

    def _osm_nearby(self, lat: float, lng: float, radius_m: int, category: str) -> list[dict]:
        """OpenStreetMap Nominatim category search around a point."""
        q = category or "nearby"
        out = self._osm_places(q, lat, lng, radius_m)
        for d in out:
            d["distance_km"] = round(_haversine_km(lat, lng, d["lat"], d["lng"]), 2)
        return out

    @staticmethod
    def _to_osm_place_dict(r: dict, query: str) -> dict:
        return {
            "place_id": f"osm:{r.get('osm_type', 'n')}{r.get('osm_id', '')}",
            "name": r.get("name") or r.get("display_name", "").split(",")[0],
            "address": r.get("display_name", ""),
            "lat": float(r.get("lat", 0.0)),
            "lng": float(r.get("lon", 0.0)),
            "rating": None,
            "user_rating_count": None,
            "price_level": None,
            "business_status": None,
            "open_now": None,
            "weekday_hours": [],
            "types": [r.get("type", "")] if r.get("type") else [],
            "photo_name": None,
            "distance_km": None,
            "primary_type": r.get("type") or r.get("class") or None,
            "query": query,
        }

    def place_details(self, place_id: str) -> dict | None:
        """Place Details (New) -> enriched dict incl. hours/status/phone/website."""
        key = f"details:{place_id}"
        cached = self._cached(key)
        if cached is not None:
            return cached
        if not self._key:
            return None
        try:
            resp = requests.get(
                f"{_PLACES_BASE}/places/{place_id}",
                headers=self._headers_with_mask(
                    "id,displayName,formattedAddress,location,rating,userRatingCount,"
                    "priceLevel,businessStatus,types,primaryType,photos,"
                    "regularOpeningHours,currentOpeningHours,"
                    "nationalPhoneNumber,websiteUri,reviews"),
                timeout=self._timeout)
            resp.raise_for_status()
            d = self._to_place_dict(resp.json(), "")
            d["reviews"] = [
                {"author_name": r.get("authorAttribution", {}).get("displayName", ""),
                 "rating": float(r.get("rating", 0.0)),
                 "text": r.get("text", {}).get("text", ""),
                 "date": r.get("publishTime", ""),
                 "source": "google_places"}
                for r in resp.json().get("reviews", [])
            ]
            out = d
        except (requests.RequestException, ValueError) as exc:
            logger.warning("[maps] place_details(%s) failed: %s", place_id, exc)
            out = None
        self._store(key, out)
        return out

    # -------------------------------------------------------------- directions
    def directions(self, origin: tuple[float, float], dest: tuple[float, float],
                   mode: Literal["driving", "walking", "transit"] = "driving") -> dict | None:
        """Directions (legacy) incl. duration_in_traffic ratio. None on failure."""
        key = f"dir:{mode}:{round(origin[0],4)}:{round(origin[1],4)}:{round(dest[0],4)}:{round(dest[1],4)}"
        cached = self._cached(key)
        if cached is not None:
            return cached
        if not self._key:
            return None
        params = {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{dest[0]},{dest[1]}",
            "mode": mode,
            "departure_time": "now",
            "traffic_model": "best_guess",
            "key": self._key,
        }
        if mode != "driving":
            params.pop("departure_time", None)
            params.pop("traffic_model", None)
        out = None
        try:
            resp = requests.get(f"{_LEGACY_BASE}/directions/json", params=params, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("routes"):
                return None
            leg = data["routes"][0]["legs"][0]
            normal_s = leg.get("duration", {}).get("value")
            traffic_s = leg.get("duration_in_traffic", {}).get("value", normal_s)
            pts = []
            for step in leg.get("steps", []):
                if "polyline" in step:
                    pts.extend(_decode_polyline(step["polyline"]["points"]))
            out = {
                "distance_m": leg.get("distance", {}).get("value", 0),
                "duration_s": normal_s,
                "duration_in_traffic_s": traffic_s,
                "traffic_ratio": round(float(traffic_s) / float(normal_s), 3) if normal_s else 1.0,
                "geometry": pts,
                "source": "google_maps",
            }
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            logger.warning("[maps] directions(%s) failed: %s", mode, exc)
        self._store(key, out)
        return out

    # ---------------------------------------------------------------- private
    def _headers_with_mask(self, field_mask: str) -> dict:
        h = self._places_headers()
        h["X-Goog-FieldMask"] = field_mask
        return h

    def _keyword_ok(self, query: str, place: dict) -> bool:
        name = (place.get("displayName") or {}).get("text", "")
        addr = place.get("formattedAddress", "")
        return _keyword_overlap(query, name, addr) >= MIN_KEYWORD_OVERLAP

    def _in_radius(self, lat: float, lng: float) -> bool:
        c_lat, c_lng = self._center
        return _haversine_km(lat, lng, c_lat, c_lng) <= self._radius_km

    @staticmethod
    def _to_place_dict(p: dict, query: str) -> dict:
        loc = p.get("location", {})
        photos = p.get("photos", []) or []
        photo = photos[0].get("name") if photos else None
        hours = p.get("openingHours") or p.get("currentOpeningHours") or p.get("regularOpeningHours") or {}
        types = p.get("types", [])
        return {
            "place_id": p.get("id", ""),
            "name": (p.get("displayName") or {}).get("text", ""),
            "address": p.get("formattedAddress", ""),
            "lat": loc.get("latitude", 0.0),
            "lng": loc.get("longitude", 0.0),
            "rating": p.get("rating"),
            "user_rating_count": p.get("userRatingCount"),
            "price_level": p.get("priceLevel"),
            "business_status": p.get("businessStatus"),
            "open_now": hours.get("openNow") if isinstance(hours, dict) else None,
            "weekday_hours": hours.get("weekdayDescriptions", []) if isinstance(hours, dict) else [],
            "types": types,
            "primary_type": p.get("primaryType"),
            "photo_name": photo,
            "phone": p.get("nationalPhoneNumber"),
            "website": p.get("websiteUri"),
            "query": query,
        }

    @staticmethod
    def _category_primary_types(category: str) -> list[str]:
        """Map the 19 user-facing category chips to Places (New) primary types."""
        mapping = {
            "atm": ["atm"],
            "bank": ["bank"],
            "hospital": ["hospital"],
            "pharmacy": ["pharmacy", "drugstore"],
            "restaurant": ["restaurant"],
            "cafe": ["cafe"],
            "hotel": ["hotel", "lodging"],
            "mall": ["shopping_mall"],
            "petrol pump": ["gas_station"],
            "ev station": ["electric_vehicle_charging_station"],
            "supermarket": ["supermarket", "grocery_store"],
            "park": ["park"],
            "bus stop": ["bus_stop", "transit_station"],
            "metro": ["subway_station", "metro_station", "transit_station"],
            "temple": ["place_of_worship", "hindu_temple"],
            "police": ["police"],
            "school": ["school", "secondary_school", "primary_school"],
            "gym": ["gym", "fitness_center"],
            "cinema": ["movie_theater", "cinema"],
        }
        return mapping.get(category.lower(), [category])


def _decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode Google polyline -> [(lat, lng), ...]."""
    out = []
    i, lat, lng = 0, 0, 0
    length = len(encoded)
    while i < length:
        shift, result = 0, 0
        while True:
            b = ord(encoded[i]) - 63
            result |= (b & 0x1F) << shift
            shift += 5
            i += 1
            if b < 0x20:
                break
        lat += (~(result >> 1) if (result & 1) else (result >> 1))
        shift, result = 0, 0
        while True:
            b = ord(encoded[i]) - 63
            result |= (b & 0x1F) << shift
            shift += 5
            i += 1
            if b < 0x20:
                break
        lng += (~(result >> 1) if (result & 1) else (result >> 1))
        out.append((lat / 1e5, lng / 1e5))
    return out
