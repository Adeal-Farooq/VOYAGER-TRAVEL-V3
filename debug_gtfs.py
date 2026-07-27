import os, sys
sys.path.insert(0, '.')
os.environ['NUMEXPR_MAX_THREADS'] = '1'
from backend.core.database import db
from backend.services.transit_config import _ensure_gtfs, _has_gtfs_route

db.initialize()
gtfs = _ensure_gtfs()

stops = db.find_nearby_bus_stops(13.105, 77.595, 2.0)
print(f"Stops near Yelahanka 5th Phase: {len(stops)}")
for s in stops:
    name = s.get('name','')
    has = _has_gtfs_route(name)
    routes = s.get('routes', [])
    print(f"  {name:45s} lat={s['lat']:.4f} lng={s['lng']:.4f} GTFS={has} routes_in_db={len(routes)}")
    if routes:
        print(f"    routes: {routes[:5]}")

print()
print("GTFS stops near Yelahanka (by lat/lng):")
count = 0
for stop_id, stops_data in gtfs._stops.items():
    sname = stops_data.get('stop_name','')
    lat = float(stops_data.get('stop_lat', 0))
    lng = float(stops_data.get('stop_lon', 0))
    dist = ((lat-13.105)**2 + (lng-77.595)**2)**0.5 * 111
    if dist < 2.0:
        print(f"  {sname:45s} ({lat:.4f},{lng:.4f}) dist={dist:.2f}km")
        count += 1
print(f"Total GTFS stops within 2km: {count}")
