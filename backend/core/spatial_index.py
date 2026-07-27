"""In-memory spatial index (R-tree) for fast nearby-stop lookups.
Replaces O(n) full scans with O(log n) nearest-neighbor queries.
Drop-in replacement for PostgreSQL/PostGIS when that's deployed."""

from rtree import index as rtree_index
import math

def _haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = (lat2 - lat1) * math.pi / 180
    dlng = (lng2 - lng1) * math.pi / 180
    a = math.sin(dlat/2)**2 + math.cos(lat1*math.pi/180) * math.cos(lat2*math.pi/180) * math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))

class SpatialIndex:
    def __init__(self):
        self._idx = None
        self._items = []  # (id, item_dict)

    def build(self, items: list, lat_key: str = "lat", lng_key: str = "lng"):
        """Build R-tree index from a list of dict items."""
        self._items = list(items)
        self._idx = rtree_index.Index()
        for i, item in enumerate(self._items):
            lat = item[lat_key]
            lng = item[lng_key]
            self._idx.insert(i, (lng, lat, lng, lat))

    def query(self, lat: float, lng: float, radius_km: float, max_results: int = 20) -> list:
        """Return items within radius_km, sorted by distance, capped at max_results."""
        if not self._idx or not self._items:
            return []
        # Approximate degree-to-km conversion at Bengaluru's latitude (~13°N)
        # 1° lat ≈ 111km, 1° lng ≈ 111*cos(13°) ≈ 108km
        dlat = radius_km / 111.0
        dlng = radius_km / (111.0 * math.cos(lat * math.pi / 180))
        bbox = (lng - dlng, lat - dlat, lng + dlng, lat + dlat)
        candidates = list(self._idx.intersection(bbox, objects=False))
        results = []
        for i in candidates:
            item = self._items[i]
            dist = _haversine(lat, lng, item["lat"], item["lng"])
            if dist <= radius_km:
                entry = {**item, "distance_km": round(dist, 3)}
                results.append(entry)
        results.sort(key=lambda x: x["distance_km"])
        return results[:max_results]

    @property
    def count(self):
        return len(self._items)
