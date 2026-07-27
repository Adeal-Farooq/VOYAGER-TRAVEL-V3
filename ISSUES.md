# VOYAGER - Known Issues & Problems

## Critical / Blocking

1. **OSRM unreachable** — `router.project-osrm.org` returns connection errors. All driving/walking paths are interpolated straight-line-with-bulge, not actual road-following paths. No fix possible without a local OSRM instance or alternative routing service (e.g., GraphHopper, Valhalla).

2. **Response time ~25-30s for medium routes** (e.g., Yelahanka → MG Road) — Even with caching, the sheer number of stop/route combinations makes it slow. Root cause: 8 nearby stops × multiple routes per stop × transit options × next-transit options × final-mile options all querying GTFS data.

3. **GTFS route numbers are internal codes** (e.g., "MF-28 JKLO-ISROQ-LGRNB") instead of human-readable names like "500A" or "KBS-1". Need `routes.txt` to `route_short_name`/`route_long_name` mapping.

## High Priority

4. **Circular routing still possible** — `_is_visited()` uses 300m haversine radius, but two stops ~300m apart on different routes can still create loops. Need tighter radius or chain-based visited tracking.

5. **Some bus paths show empty arrays** — when GTFS shape data doesn't cover the specific stop-to-stop segment and interpolation fails (edge cases with missing coordinates).

6. **Metro direction filter too aggressive** — `dest_to_dm > nm_dist_to_dest * 1.1` may skip valid metro routes where the metro doesn't make progress linearly but still connects to onward buses.

7. **GTFS loading takes ~41s at startup** — synchronous, blocks server start. Should be async or lazy-loaded.

## Medium Priority

8. **Final-mile walk/cab options show for distant stops** — a bus arrival 5km from destination still shows "walk" as an option (should only show when <2km).

9. **Historical data only, no real-time** — bus times are based on static GTFS schedules, not live GPS tracking of buses.

10. **Fare calculation is approximate** — bus fares use `max(6, round(db.get_bmtc_ordinary_fare()))` per person, not actual route-specific fares.

11. **No battery/context awareness** — doesn't consider whether the user is low on battery or has specific time constraints.

## Low Priority / Polishing

12. **UI: Column layout breaks for >5 columns** on smaller screens.

13. **No loading spinner per column** — the entire panel shows one loading state even though columns load progressively.

14. **Train data is hardcoded** (only 5 destination cities: Mysuru, Hubballi, Mangaluru, Belagavi, Ballari). No live train queries.

15. **Waypoint stops added by user don't auto-refresh downstream segments** — user must manually trigger a new search.

16. **Metro interchange stations limited** — only Majestic/Sampige Road, Yeshwanthpur, Baiyappanahalli hardcoded as interchange hubs.
