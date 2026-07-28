import logging
import math
from backend.core.database import db
from backend.services.gtfs_service import clean_route_short_name

logger = logging.getLogger(__name__)

_gtfs = None
def _ensure_gtfs():
    global _gtfs
    if _gtfs is None:
        from backend.services.gtfs_service import gtfs_loader
        gtfs_loader.load()
        _gtfs = gtfs_loader
        # Pre-resolve all bus stop names for fast A* graph building & segment lookups
        try:
            from backend.core.database import db
            db.initialize()
            names = [s.get("name", "") for s in db.bus_stops.values() if s.get("name")]
            _gtfs.pre_resolve_all(names)
        except Exception as e:
            logger.warning(f"GTFS pre-resolve failed: {e}")
    return _gtfs

_RIDE_TYPES = [
    ("cab", "Uber Go / Ola Mini", 12, 3, 25, "🚕", 4, 0),
    ("cab_sedan", "Uber Go Priority / Ola Prime", 24, 3, 50, "🚙", 4, 0),
    ("cab_xl", "Uber XL / Ola XL", 30, 3, 100, "🚐", 6, 0),
    ("auto", "Auto", 9, 5, 15, "🛺", 3, 0),
    ("bike", "Uber Moto / Rapido", 5, 2, 10, "🏍️", 1, 0),
    ("cab_women", "Uber for Women / Ola for Women", 12, 3, 25, "👩", 4, 0),
    ("cab_pet", "Uber Pet / Premier", 18, 3, 50, "🐾", 4, 0),
]

def _calc_ride_fare(dist: float, base: float, per_km: float, free_km: int = 0) -> int:
    if dist <= free_km:
        return round(base)
    return round(base + (dist - free_km) * per_km)

def _ride_fare_range(dist: float, base: float, per_km: float, free_km: int = 0) -> tuple:
    base_fare = _calc_ride_fare(dist, base, per_km, free_km)
    peek_fare = round(base_fare * 1.35)
    return (min(base_fare, peek_fare), max(base_fare, peek_fare))

def _get_train_options(src_name: str, dst_name: str) -> list:
    from backend.services.train_service import get_train_options as _live_trains
    return _live_trains(src_name, dst_name)

def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return default
    return val

def _current_hour() -> int:
    from backend.services.gtfs_service import _now
    return _now().hour

def _is_metro_operating() -> bool:
    h = _current_hour()
    return 5 <= h < 23

def _haversine_dist(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = (lat2 - lat1) * math.pi / 180
    dlng = (lng2 - lng1) * math.pi / 180
    a = math.sin(dlat/2)**2 + math.cos(lat1*math.pi/180) * math.cos(lat2*math.pi/180) * math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))

_MAJOR_HUBS = ["majestic", "kempegowda bus station", "kr market", "kbs",
               "shivajinagara", "shivajinagar", "banashankari", "jayanagara",
               "k.r. market", "city market", "platform 10", "platform 11",
               "platform 12", "platform 13", "platform 14"]

def _route_goes_toward_dest(shape_path: list, stop_lat: float, stop_lng: float, dest_lat: float, dest_lng: float,
                             route_name: str = "", gtfs_ref=None) -> bool:
    if not shape_path or len(shape_path) < 2:
        return True
    end_idx = len(shape_path) - 1
    direct_dist = _haversine_dist(stop_lat, stop_lng, dest_lat, dest_lng)
    start_dist = _haversine_dist(shape_path[0][0], shape_path[0][1], dest_lat, dest_lng)
    end_dist = _haversine_dist(shape_path[end_idx][0], shape_path[end_idx][1], dest_lat, dest_lng)

    # Route endpoint is closer to dest than source
    if start_dist < direct_dist or end_dist < direct_dist:
        return True

    # Source is near route start: check forward direction
    dist_to_start = _haversine_dist(stop_lat, stop_lng, shape_path[0][0], shape_path[0][1])
    dist_to_end = _haversine_dist(stop_lat, stop_lng, shape_path[end_idx][0], shape_path[end_idx][1])

    if dist_to_start < 0.5:
        # Route starts at/near source; check if it goes toward dest
        n = min(3, end_idx)
        sd = (shape_path[n][0] - shape_path[0][0], shape_path[n][1] - shape_path[0][1])
    elif dist_to_end < 0.5:
        # Route ends at/near source; check approach direction
        p = max(end_idx - 3, 0)
        sd = (shape_path[end_idx][0] - shape_path[p][0], shape_path[end_idx][1] - shape_path[p][1])
    else:
        # Source is in middle of route; find closest point and check forward direction
        min_dist = float('inf')
        closest_idx = 0
        for i, (lat, lng) in enumerate(shape_path):
            d = math.sqrt((lat - stop_lat)**2 + (lng - stop_lng)**2)
            if d < min_dist:
                min_dist = d
                closest_idx = i
        n = min(closest_idx + 3, end_idx)
        sd = (shape_path[n][0] - shape_path[closest_idx][0], shape_path[n][1] - shape_path[closest_idx][1])

    dd = (dest_lat - stop_lat, dest_lng - stop_lng)
    s_len = math.sqrt(sd[0]**2 + sd[1]**2)
    d_len = math.sqrt(dd[0]**2 + dd[1]**2)
    if s_len < 0.0001 or d_len < 0.0001:
        return True
    cos_angle = (sd[0]*dd[0] + sd[1]*dd[1]) / (s_len * d_len)
    if cos_angle >= 0.3:
        return True
    # Poor angle: check if route passes through a major hub
    if route_name and gtfs_ref:
        route_stops = gtfs_ref.get_route_stops(route_name, limit=50)
        for rs in route_stops:
            rs_lower = rs.get("stop_name", "").lower()
            for hub in _MAJOR_HUBS:
                if hub in rs_lower:
                    return True
    return False

def _gtfs_buses_at_stop(stop_name) -> list:
    if not isinstance(stop_name, str):
        return []
    gtfs = _ensure_gtfs()
    return gtfs.get_all_routes_at_stop(stop_name)

def _has_gtfs_route(stop_name) -> bool:
    gtfs = _ensure_gtfs()
    if not isinstance(stop_name, str):
        return False
    key = gtfs.resolve_name(stop_name)
    return key is not None

def _get_time_period() -> str:
    """Return 'daytime', 'late_night', or 'early_morning' based on current hour."""
    h = _current_hour()
    if 6 <= h < 22:
        return "daytime"
    elif 22 <= h < 24 or 0 <= h < 1:
        return "late_night"
    else:
        return "early_morning"

def _is_bus_running_now(route_number: str) -> dict:
    """Check if a bus route is currently operating. Returns status dict."""
    gtfs = _ensure_gtfs()
    if not gtfs:
        return {"is_running": True, "message": "", "schedule_known": False}
    try:
        return gtfs.get_route_schedule_status(route_number)
    except Exception:
        return {"is_running": True, "message": "", "schedule_known": False}

def _get_safety_advisory() -> str:
    """Return a contextual safety message based on time of day."""
    period = _get_time_period()
    if period == "late_night":
        return "It's late at night — cab/auto is the safest option right now"
    elif period == "early_morning":
        return "Early morning — public transport may be limited, cabs are reliable"
    return ""
