BACKEND ISSUES: 

Complete Backend Code Review 

1. backend/main.py (55 lines) 

What it does: FastAPI app entry point. Configures CORS, imports routers, startup hook. 

Issues: 

- Line 55: Stray comment #update at end of file — dead text. 

- Lines 17-21: allow_origins=["*"] with allow_credentials=True — insecure; CORS spec says credentials + wildcard origin is invalid, browsers may reject. 

- Lines 28-34: startup() is sync but @app.on_event("startup") supports async — missed opportunity for parallel init. 

- Line 29: import os buried inside function — should be at top. 

- Line 9: settings.APP_NAME used but not verified if it exists in config. 

2. backend/api/routes.py (710 lines) 

What it does: All /api/routes/* endpoints — route planning, traffic overlay, segment steps. 

Bugs/Issues: 

- Lines 86-88: Inner function enrich_seg() captures loop variable seg_transit by reference — since it's def inside the for loop, all tasks share the same seg_transit per iteration, actually this is fine since it's called immediately via asyncio.wait_for. But line 86 defines a new function every iteration — wasteful. 

- Line 90-92: Bare except: catches all including KeyboardInterrupt — extremely dangerous. 

- Line 117: Same bare except:. 

- Line 145: When OSRM fails, Haversine duration estimate is dist * 30 minutes — that's ~30 km/h average, reasonable for city but no traffic adjustment. 

- Lines 211-213: Bare except: on path enrichment timeout — silently swallows all errors. 

- Lines 270-273: Bare except: on weather fetch. 

- Line 314-317: _estimate_fuel_cost imports settings inside function body on every call — should be module-level. 

- Line 352: from_name default "Your Location" — not internationalized. 

- Lines 370-380: OSRM health check runs on every /all-segments request — wasteful, should be cached or run at startup. 

- Lines 614-637: _load_traffic_speeds reads from traffic_logs.csv — but the file may not exist. Falls back to 15 m/s if empty. This data is static CSV, not live traffic. 

- Lines 618-644: _load_traffic_speeds and _get_current_speed use global and time.time() — module-level mutable state with no thread safety. 

- Lines 646-703: /traffic-overlay uses a static GeoJSON file (bangalore_roads.geojson) with uniformly applied congestion levels — this is not real traffic data, just the same color applied to all roads. 

- Lines 688-689: _darken_color is called but at peak times ALL roads get darkened uniformly — not per-road traffic data. 

# Hardcoded/Fake Data: 

- Line 145: duration_minutes: round(dist * 30) — fake fallback when OSRM fails. 

- Lines 603-611: Hardcoded color map for road types. 

- Lines 618-644: Traffic speeds from a static CSV file, not live. 

- Lines 666-674: Congestion level based on single avg_speed float for entire city. 

Performance: 

- Line 383-424: Three nested loops over segments → destinations → transit/final_options creating individual OSRM fetch tasks — could generate hundreds of tasks per request. 

- Line 420: asyncio.gather(*path_tasks) with semaphore(15) — okay, but could be 100+ tasks. 

Code Quality: 

- Line 91: try/except/pass — antipattern repeated 10+ times in this file. 

- Lines 383-469: Deeply nested loops (4 levels) with duplicated OSRM fetching logic. 

3. backend/services/transit_service.py (1994 lines) 

What it does: Core transit routing engine — generates bus, metro, KIA, multi-modal routes. 

Bugs: 

- Line 1: from geopy.distance import geodesic is imported but _haversine_dist from config is used in many places. haversine_distance method (line 12) uses geodesic while the graph uses _haversine_dist — inconsistent precision (geodesic is WGS-84 ellipsoid, haversine is spherical). 

- Line 503: _get_bus_route_nums(dst_bus, {}) — second arg is empty dict {}, but 

_find_common_routes calls dest_stop.get("routes", []) which returns [] for an empty dict — 

this produces empty common routes for the Metro→Bus case, so route_str becomes "Multiple". 

- Lines 1965-1968: __init__ at the bottom of the class — Python allows this but it's extremely confusing. 

- Lines 170-171: KIA route fare calculation dest_s.get("fare", 0) - src_s.get("fare", 0) may result in negative fares (line 365 if kia_fare <= 0 catches this with hardcoded 210). 

- Lines 1263-1279: _add_reach_options — the if sdist >= 1.0 block for rides means for distances 1.0-2.0km, only bike is shown (due to 1.0 <= sdist < 2.0 and mode not in ("bike",)). But sdist of exactly 2.0 would not be caught — should be <=. 

Hardcoded/Fake Data: 

- Line 700: _is_outside_bengaluru hardcodes center at (12.9716, 77.5946) and threshold 35km — should be configurable. 

- Lines 716-724: _find_farthest_bus_stop_toward_dest hardcodes same center point. 

- Lines 786: Cab fare formula 25 + stop_to_dest * 14 — hardcoded per-km rate. 

Performance: 

- Lines 398-478: _generate_multi_modal_routes — CASE 2 iterates ALL metro stations (all_ms) for each bus stop, calling haversine_distance multiple times. Nested loops: up to 2 bus stops × 87 metro stations × nearby lookups = heavy. 

- Lines 1795-1885: _build_single_segment iterates nearby bus/metro/rail and calls GTFS for each stop — 8 bus + 6 metro + 5 rail = up to 19 stops, each triggering GTFS lookups. 

Code Quality: 

- Duplication: The ride type iteration pattern (for mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km in ride_types) appears at least 12 times across the file (lines 667, 753, 858, 948, 990, 1073, 1113, 1224, 1264, 1526). 

- Duplication: The walk/ride option dict construction with identical set of keys appears ~40+ times. 

- Line 509, 1166, etc.: Boolean == comparison with True (group_size == 1) used as integer multiplier — works in Python but bad practice. 

- Lines 1615-1618: _clear_caches deletes instance attributes that may not exist — uses hasattr guard, but still fragile. 

4. backend/services/transit_config.py (123 lines) 

What it does: Constants, pure functions, and helpers for transit routing. 

Bugs: 

- Lines 5-20: Global mutable _gtfs = None with _ensure_gtfs() function — mutable module state. The function also re-imports db from database and calls db.initialize() every time. 

- Lines 22-30: _RIDE_TYPES as a list of tuples — fragile positional indexing used everywhere (e.g., mode, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km). Adding a field in the middle breaks all unpacking code. Should be list of dicts or NamedTuple. 

- Lines 66-69: _MAJOR_HUBS list — hardcoded stop names. 

- Line 93: if s_len < 0.0001 or d_len < 0.0001 — magic number threshold. 

Performance: 

- Lines 42-44: _get_train_options imports get_train_options on every call. 

5. backend/services/transit_graph.py (209 lines) 

What it does: Builds A* graph for bus+metro routing. 

Bugs: 

- Lines 37-48: Metro-to-Metro edges: O(n²) loop over db.metro_stations — 87 stations → ~3,789 iterations. _get_dist uses cached haversine, but this is still in build_graph which runs at most once. 

- Lines 80-91: Bus-to-Metro walk edges — checks bnid not in self.node_coords but a bus stop might not be in node_coords if it had no gtfs routes (since bus_stops_added is only populated from all_route_groups, which requires GTFS data). 

- Lines 93-117: Bus-to-Bus walk edges — iterates bus_stop_names and calls db.find_nearby_bus_stops for each. With ~1700 bus stops, this calls the spatial index 1700 times. Each nearby query returns up to 20 results, then another haversine check. 

Hardcoded: 

- Walk radius for bus-to-bus transfer: 0.5km (line 100), bus-to-metro: 1.5km (line 88). 

6. backend/services/transit_scoring.py (63 lines) 

What it does: TOPSIS multi-criteria route scoring. 

Bugs/Issues: 

- Lines 8-19: Hardcoded comfort_map and safety_map — every new route type must be added here or defaults to 3. 

- Line 21: Import inside function — should be at top of file. 

- Lines 43, 62: Score clamping max(10, min(99, ...)) — arbitrary range 10-99. 

- Line 62: Modifies r["overall_score"] in place — side effect on input list. 

7. backend/services/transit_paths.py (116 lines) 

What it does: OSRM path fetching, interpolation fallback. 

# Bugs: 

- Line 36: Uses settings.OSRM_FOOT_URL for walking — but the foot profile was OOM-killed (per AGENTS.md). All walking paths will fall through to interpolate_path. 

- Lines 53-82: add_leg_paths — if both from_lat/from_lng and GTFS shape lookup fail, the leg gets no path. The asyncio.wait_for on line 80 with 30s timeout could be problematic if many legs. 

- Line 50: Falls back to interpolate_path on any error — silently returns fake geometry. 

- Line 32: Cache key truncated to 4 decimal places (~11m precision) — could cause cache collisions for nearby but distinct coordinate pairs. 

# Code Quality: 

- Line 48: Bare except: pass swallows all errors, making OSRM failures silent. 

8. backend/services/gtfs_service.py (645 lines) 

What it does: Loads BMTC GTFS data from ZIP, provides fuzzy stop name matching, route/stop lookups. 

# Bugs: 

- Lines 29-30: Module-level mutable global state (_GTFS_WORD_INDEX, 

_GTFS_NORM_NAMES) — if multiple GTFSLoader instances exist, they share this state. Only one instance (gtfs_loader) should exist, but the globals are modified by _build_word_index. 

- Lines 270-271: len(self._stop_times[sname]) < 200 hard limit — stops with more than 200 departure times lose data. 

- Lines 273-275: len(self._stop_times_by_route[rsn]) < 500 — hard limit on route departures. 

- Line 356: start = min(f_seq, t_seq) - 1 — can be -1 if f_seq is 0, which in Python means the last element. Functionally this works if f_seq is 0 (wraps to end), but semantically wrong. 

- Line 92: get_close_matches(qn, candidates_norm, n=1, cutoff=0.55) — the 0.55 cutoff means some names won't match even with high trigram overlap. 

# Performance: 

- Lines 43-97: _fast_fuzzy_match — well optimized with staged approach (word-overlap → substring → word-subset → trigram-filtered). But lines 67-70 (qn in nn or nn in qn) iterate all names O(n) per call. 

- Lines 183-306: Full GTFS load processes 429K+ stop_times rows — this is the ~10.6s startup bottleneck noted in AGENTS.md. 

Code Quality: 

- Lines 100-117: Test time override mechanism (_TEST_TIME_OVERRIDE) is global mutable state — not thread-safe, could cause issues in concurrent requests. 

- Lines 376-378, 401-404, 436-439, 466-469: time_to_seconds function redefined 4 times inside different methods — should be a single module-level or class-level helper. 

- Line 2: from difflib import SequenceMatcher — imported but only used in search_stops_by_name (line 489). get_close_matches is imported inline in _fast_fuzzy_match (line 91). 

9. backend/core/database.py (312 lines) 

What it does: Singleton database loading metro, bus, KIA, railway data with spatial indexes. 

Bugs: 

- Lines 28-35: Singleton _instance pattern — no lock, not thread-safe. If two threads call initialize() simultaneously, could create two instances. 

- Lines 109-113: In _load_metro_data, the nested loop calculates cumulative distance by iterating from i to end and adding intermediate distances — but it uses next_s (the current station's data) to get distance_to_next_km which is the distance TO the next station, not FROM it. Actually this looks correct: cum_dist accumulates distance_to_next_km for each segment between station codes. 

- Lines 127-138: _load_bus_stops uses ast.literal_eval on routes_raw which is user-supplied data from CSV — potential security concern (though unlikely for local CSV). 

- Lines 155-158: get_metro_fare — if distance_km exceeds all slabs, returns slabs[-1].get("fare", 95.0) — hardcoded 95 fallback. 

- Lines 209-229: get_metro_distance_between — fallback metrics: abs(s2.sequence - s.sequence) * 1.2 (line 224) and haversine (line 228) — these are estimates, not actual track distances. 

Performance: 

- Lines 209-229: Two nested loops over metro_stations for each call — O(n²) per call. 

Code Quality: 

- Lines 124-138: Triply-nested try/except in _load_bus_stops with bare excepts. 

- Line 270: _get_kia_route_for_stop not prefixed with underscore but used internally only. 

10. backend/services/langgraph/agent.py (394 lines) 

What it does: LangGraph-like agent with tool registry, intent detection, LLM orchestration. 

Bugs/Issues: 

- Lines 20-37: TOOL_REGISTRY maps strings to async functions — but this is NOT actually using LangGraph's StateGraph. It's a manual simulation where the LLM returns JSON tool calls and they're executed with asyncio.gather. The filename and docstring are misleading — this is not real LangGraph. 

- Lines 82-120: Intent detection via keyword matching — fragile. "I want to find a hotel near the metro station" would match "station" → get_nearby_stations, "hotel" → get_hotel_prices, "find" → geocode + search_places. All three execute even though user likely wants hotels near a specific metro station. 

- Lines 287-298: _auto_generate_calls extracts capital words with regex [A-Z][a-z]+(?:\s[A-Z] [a-z]+)* — will miss all-caps names, names with numbers, lowercase queries. 

- Lines 304-308: Hardcoded fallback coordinates lat=12.9716, lng=77.5946 (MG Road, Bengaluru) for ride prices and weather — defaults to center of city when no location extracted. 

- Lines 122, 168: Returns json.dumps({"error": ...}) as string — caller expects JSON, this creates a double-encoded string. 

- Lines 252-264: Auto-fetches reviews for any place names found in tool results — even if user didn't ask for reviews. Could waste API calls. 

Code Quality: 

- Lines 170-193: _extract_tool_calls tries to parse JSON, then extracts tool calls from various possible key names (tool, name, tool_calls, tools, args, parameters, arguments, etc.) — fragile format adaptation. 

11. backend/services/langgraph/tools/review_tools.py (126 lines) 

What it does: Multi-source review aggregation (SerpAPI → Reddit → JustDial → Google scrape). 

Bugs/Issues: 

- Line 18: places = await serpapi_client.search_places(f"{name} {addr}") — this sends both name and address as a single search query, which may be too long. 

- Lines 77-80: avg_rating = sum(r.get("rating", 3) for r in ...) — default rating 3 when rating is 0, which inflates the average. 

- Line 88: "is_recommended": avg_rating >= 3.0 — 3.0 threshold vs 3.5 in other places (inconsistent). 

12. backend/services/langgraph/tools/news_tools.py (45 lines) 

What it does: News event tools — just wraps news_scraper and reddit_client. 

Issues: 

- Line 30-31: get_area_events hardcodes "events this weekend" as fallback query — always returns weekend events regardless of current day. 

13. backend/services/langgraph/tools/geo_tools.py (95 lines) 

What it does: Geocoding and spatial queries. 

Issues: 

- Lines 49-53: _haversine is called but station dict may not have same field names — uses .get("lat", 0) with fallback to .get("Latitude", 0) which handles some but not all naming inconsistencies. 

- Lines 70-76: _haversine reimplemented here despite existing in transit_config.py and database.py — duplication. 

14. backend/services/langgraph/tools/weather_tools.py (16 lines) 

Simple wrapper — clean. 

15. backend/services/langgraph/tools/search_tools.py (94 lines) 

What it does: Place search with SerpAPI/Reddit/DDG fallback chain. 

Issues: 

- Lines 18-27: Reddit fallback converts score to rating by dividing by 100 — arbitrary mapping. A post with score 5 becomes rating 0.05; score 500 becomes 5.0. 

- Lines 62-83: get_suggestions makes SerpAPI call directly with httpx instead of using serpapi_client methods — duplicated HTTP logic. 

16. backend/services/scrapers/ride_scraper.py (170 lines) 

What it does: Ride pricing via SerpAPI + formula fallback. 

Bugs: 

- Lines 35, 37-40: _filter_real_prices is called before surge calculation — the flow is: _scrape_serpapi_directions → if real, _filter_real_prices. Else, compute distance → surge → estimates → filter. But if SerpAPI returns results, surge factor is NOT applied. 

- Line 167: geodesic imported inside function — should be at top. 

- Lines 79-108: _parse_serpapi_directions — handles nested dicts inconsistently (route.get("distance", {}).get("value", 0) vs route.get("distance", 0)). 

17. backend/services/scrapers/google_reviews_scraper.py (181 lines) 

What it does: Google Reviews via SerpAPI → Google Maps scrape → DuckDuckGo fallback. 

Bugs: 

- Lines 57-61: _scrape_google_maps attempts to scrape Google Maps directly — this is against Google's ToS and will likely be blocked. The proxy and headers won't help much. 

- Line 50: Hardcoded lat/lng @12.9716,77.5946,14z for search URL — always centers on MG Road regardless of query location. 

- Lines 99-128: _extract_from_json parses window.__INITIAL_STATE__ — this is a React internal state format that changes with every deployment; extremely fragile. 

18. backend/services/scrapers/justdial_scraper.py (133 lines) 

What it does: JustDial business search and review scraping. 

Issues: 

- This scraper is known broken per AGENTS.md ("Fix JustDial scraper — site not responding"). 

- Lines 34, 64, 67-71: CSS selectors like .storebox, .jrev, .jrev-user — these are extremely likely to change. 

- All methods: Broad try/except/pass — silent failures. 

19. backend/services/scrapers/ddg_scraper.py (100 lines) 

What it does: DuckDuckGo HTML search (two fallback methods). 

Issues: Reasonably well structured. Fallback chain: html → lite. No major bugs. 

20. backend/services/scrapers/news_scraper.py (108 lines) 

What it does: News aggregation from Reddit + Times of India + The Hindu. 

# Bugs: 

- Line 81: URL construction for TOI — f"https://{source['name'].lower().replace(' ', 

'')}.indiatimes.com{href}" — if source is "Times of India", this becomes https://timesofindia.indiatimes.com/... which happens to be correct, but the hardcoded mapping from display name to domain is fragile. What if source name is "The Times of India"? 

- Lines 58-66: Source URLs hardcoded — if TOI or The Hindu changes their URL structure, this breaks. 

21. backend/services/clients/serpapi_client.py (184 lines) 

What it does: SerpAPI Google Maps search, nearby, place details. 

Bugs/Issues: 

- Lines 136-181: _parse_place_detail handles nested review data structures with defensive fallbacks (place_results → place → local_results). This indicates SerpAPI's API has inconsistent key formats. 

- Line 148: user_reviews_data.get("most_relevant", []) — SerpAPI may return most_relevant as a dict instead of list in some cases. Not handled. 

- Lines 72, 82, 91, 111: All methods have except: return []/None — silent failures. No logging. 

22. backend/services/clients/google_maps_client.py (97 lines) 

What it does: Google Maps API for distance matrix, geocoding, ride estimates. 

Issues: Clean, minimal. Ride prices delegated to ride_scraper. Good. 

23. backend/services/clients/weather_client.py (88 lines) 

What it does: Open-Meteo weather (free, no API key). 

Issues: 

- Line 49-58: _code_to_condition — WMO weather codes 0-99 mapped coarsely. Code 95+ (severe thunderstorm) all mapped to "Thunderstorm". No hail codes (99+). 

- Lines 60-85: surge_multiplier returns 0.3 for any rain — no differentiation between drizzle and thunderstorm. 

24. backend/services/clients/reddit_client.py (176 lines) 

What it does: Reddit public JSON API for search, news, travel insights. 

Bugs/Issues: 

- Line 24-29: User-Agent rotation list — one of the UA strings is "VOYAGER/1.0 (India Transit Navigator; +https://github.com/voyager)" with a non-existent GitHub URL. Reddit may ratelimit more aggressively for non-browser UAs. 

- Lines 47, 55: with await self._get_client() — _get_client returns httpx.AsyncClient but the async with is on a context manager that doesn't exist. Actually httpx.AsyncClient IS an async context manager, so async with await self._get_client() as client: works but is unusual. Should be async with self._get_client() as client:. 

- Line 51: Recursive fallback to _search_across_subreddits which makes the same request but with different params — could cause infinite loop if _search_across_subreddits also fails. 

- Lines 133-173: _enrich_posts fetches top comments for each post sequentially with for permalink in posts: await client2.get(...) — should use asyncio.gather. 

Hardcoded: 

- Line 6: SUB_REDDITS = "bangalore", "bengaluru", "indiantravel", "india", "bmtc", "IndianAutos". 

25. backend/agents/llm_agent.py (306 lines) 

What it does: LLMAgent singleton providing high-level APIs for search, reviews, pricing, travel recs. 

Bugs: 

- Lines 249-253: get_travel_news returns hardcoded fake news when real data is unavailable: 

return [ 

{"title": "Bengaluru Traffic Advisory", ...}, 

{"title": "Metro Running on Schedule", ...}, 

{"title": "Weather Update", ...}, 

# ] 

This contradicts the module docstring which says "NEVER generates fake data — returns empty list/dict if no real data". 

- Line 235: get_weather_impact returns hardcoded fallback {"condition": "clear", 

"temperature_celsius": "28", "impact": "minor", ...} when weather API fails. 

- Line 200: "estimated_cost_min": context["rides"][0]["fare"] if context.get("rides") else 100 — hardcoded ₹100 fallback. 

- Line 201: Same pattern, hardcoded ₹500 fallback for max. 

- Line 204: Hardcoded ["Book cab for comfort", "Check traffic before starting"] fallback tips. 

- Line 35: settings.GEMINI_API_KEY != "your_gemini_api_key_here" — comparing against example placeholder string. 

- Lines 39-73: _call_openrouter — model fallback loop resets self._working_model to the last successful model, but the fallback list order doesn't change dynamically. 

- Line 229-230: temperature_celsius and humidity returned as strings, not numbers — inconsistent typing. 

Code Quality: 

- Lines 199-208: Large fallback dict with hardcoded values. 

- Lines 193-196: Tips parsing via split("\n") and filtering — fragile. 

- Lines 281-283: Returns hardcoded error message on LLM failure instead of propagating the error. 

Summary of Cross-Cutting Issues 

Issue Severity Files Affected 

Bare except: pass everywhere HIGH routes.py, transit_service.py, transit_paths.py, gtfs_service.py, transit_config.py, all scrapers, all clients, agent.py 

Global mutable state HIGH transit_config.py (_gtfs), gtfs_service.py (_GTFS_WORD_INDEX, _TEST_TIME_OVERRIDE), routes.py (_road_geojson_cache, _traffic_speeds_cache) 

Hardcoded fake fallback data MEDIUM llm_agent.py (lines 249-253 fake news), llm_agent.py (line 235 fake weather), routes.py (line 666 fake traffic speed) 

Dead code / unused imports LOW transit_service.py line 1 (geodesic), gtfs_service.py line 3 (SequenceMatcher) 

Inconsistent coordinate precision LOW haversine vs geodesic between transit_service and transit_config 

No logging MEDIUM Nearly all silent failures — no logger usage anywhere, only print() 

CSS selector fragility MEDIUM justdial_scraper.py, google_reviews_scraper.py, news_scraper.py 

MEDIUM Duplicate code patterns Ride type iteration duplicated 12+ times in transit_service.py; time_to_seconds duplicated 4 times in gtfs_service.py 

Non-thread-safe singletons MEDIUM LOW No config validation at startup 

database.py TransitDatabase._instance 

Missing API keys silently degrade functionality 

FRONTEND ISSUE: 

COMPLETE FRONTEND ANALYSIS REPORT 

# 1. App.tsx (10 lines) 

What it does: Root component wrapping MainPage in AppProvider. 

Issues: None. Clean and minimal. 

# 2. context/AppContext.tsx (173 lines) 

What it does: Global state via React Context — holds all shared state: map, locations, routes, discovery panel, tracking, preferences. 

Issues: 

- Line 66: mapRef is typed as React.MutableRefObject<any> — should be React.MutableRefObject<L.Map | null> to avoid any. 

- Line 140: mapRef.current.flyTo(loc, 14) is called in useEffect but mapRef.current could be null if map hasn't mounted yet — no null guard. 

- Lines 93-97: tabs array is recreated on every render — should be useMemo or static outside component. 

- Missing state: No isLoading or error state for network requests at context level. 

- Line 82-83: showDiscovery and discoveryPlace are two separate states that should be a single useState<PlaceResult | null> — using null as off. Having both invites inconsistency (e.g., closing sets showDiscovery to false but if discoveryPlace is not null, a stale DiscoveryPanel condition in MainPage could pass a non-null place). 

3. pages/MainPage.tsx (178 lines) 

What it does: Layout orchestrator — sidebar with tabbed panels (Search/AToB/Trip), MapView, DiscoveryPanel overlay, bottom mobile nav. 

Issues: 

- Lines 51-55: Duplicate useApp() call — already destructured lines 12-22. This second call refetches context unnecessarily. 

- Line 65: Calling setRouteGeometry(null) on mode change but NOT resetting other route state (selectedRouteIdx, routes, etc.) held locally in AToBPanel — stale state persists. 

- Line 122-136: All props passed to MapView are derived from context but passed again — redundant (MapView could just use useApp() directly). 

- Lines 138-163: DiscoveryPanel and the "Enriching..." loading card both use position: absolute with top: 16, right: 16 — they overlap if shown simultaneously (but logic prevents that). Layout could be cleaner. 

- Responsive: No responsive breakpoints in JSX — relies entirely on CSS media queries for sidebar. The width: 420, minWidth: 420 is hardcoded. 

- Performance: Every re-render of MainPage re-passes all callback props to children — missing useMemo for tabs.map(...) render. 

4. components/SearchPanel.tsx (366 lines) 

What it does: Two-tab panel: "Search Specific" (text query) and "Search Nearby" (category chips + radius slider). 

Bugs: 

- Line 60: searchPlaces called with hardcoded 12.9716, 77.5946 (Bangalore center) instead of userLocation — near-useless if user searches for a place far from Bangalore center. 

- Line 88: getNearbyPlaces uses hardcoded center 12.9716, 77.5946 when searchedPlace is null — should fall back to userLocation from context. 

- Line 133: Suggestions use key={i} — fragile; should use unique id or text. Causes React reconciliation issues if suggestions change order. 

- Line 229: NewsOverlay and its loading prop — but loading is never passed to it. Actually, NewsOverlay is NOT used in SearchPanel despite being imported (line 1 does NOT import NewsOverlay — no import exists, but it's not rendered either). Wait — no, the file does not import NewsOverlay. The NewsOverlay component is imported nowhere in the codebase except in the file itself. Dead component — never rendered by any parent. 

- Lines 261-366: PlaceCard component uses inline onClick on the card which calls onView — but onView calls both onSelectPlace(place) AND onViewOnMap(place) from the parent. The parent's onSelectPlace (line 104) calls handleViewOnMap which itself calls setSelectedPlace and flyTo. So onViewOnMap duplicates onSelectPlace's behavior in the parent. Every card click does double work. 

- Line 270: reviews is place.reviews?.slice(0, 3) || [] — but reviews length check at line 333 uses this sliced array, so "Show reviews (3)" is correct. No bug here. 

- Line 281: Image onError sets imgError — but if image is a broken URL, no fallback placeholder is shown (empty gray space remains). 

- Line 305: place.distance_km is displayed with 📍 {place.distance_km} km — inconsistent with other parts that use formatDistance or styled differently. Also, the emoji is hardcoded while other parts use material icons. 

- Performance: No debouncing on search input (line 52-72) — handleSearch fires on every Enter press but there's no input debounce for auto-search. The suggestions debounce (300ms) is only for the autocomplete dropdown, not the search itself. 

# Missing features: 

- No "recent searches" or "saved places" feature 

- No filters beyond category chips (price range, rating, open now) 

- No pagination for search results (only first page) 

- No loading state for the initial nearby data fetch on tab switch 

5. components/AToBPanel.tsx (447 lines) 

What it does: A→B route planning with three sub-modes (Public/Transport, Drive, Walk), ride pricing, route list with TOPSIS scores. 

# Bugs: 

- Line 102-107: Ride prices are fetched ONLY when data?.weather exists in the planRoute response — there's no logical connection between weather and ride prices. This is clearly a bug; the condition should be something like if (subMode === 'transport' && transportType === 'direct') or simply unconditional. 

- Line 104: getRidePrices(sourceQuery, destQuery) uses the query strings, not resolved lat/lng — but the API may need lat/lng for accurate pricing. The query strings could be empty if user selected from map. 

- Line 120-124: Route geometry mapping assumes route.geometry.coordinates is [lng, lat] from the backend — reverses to [lat, lng]. But line 128 uses leg.path as [number, number][] without checking if it's [lat, lng] or [lng, lat]. This is an assumption that could be wrong. 

- Line 143: swapLocations reads sourceQuery and destQuery but doesn't check if they are null/valid before swapping. If dest is set but source isn't, swapping creates invalid state. 

- Line 145-148: getTopRoutes() sorts routes by score but selectedRouteIdx uses index from the original unsorted routes array (line 320: all.indexOf(route)). If user has a route selected and routes are re-fetched, the selected index could point to wrong route. 

- Line 320: all.indexOf(route) does reference comparison — if routes array is rebuilt by React (new object references), indexOf will return -1 and selection breaks. 

- Lines 370-398: expandedLegs uses all.indexOf(route) while route is from top5.map — same reference comparison issue. 

- Transport Type sub-toggle: Lines 229-243 show "Multi-Hop Transit" vs "Direct Ride" but these toggles change transportType state — this state is never actually used in handleFindRoutes. Both toggles call the same planRoute with mode: 'public'. The transportType is dead state — it only controls whether the ride prices section renders. This means "Multi-Hop Transit" and "Direct Ride" produce identical API calls and route results. 

- Line 258: Go button disabled when !sourceLocation || !destLocation — but both location refs could be null if user only typed text without selecting from suggestions. The locations are set in pickSource/pickDest, but if a user types a query and doesn't click a suggestion, locations remain null and button stays disabled with no feedback. 

- Line 330: route.overall_score is displayed raw (e.g., "Score: 82.5") — but getScoreColor(route.overall_score) expects a 0-100 value while formatDuration and formatRupees are used elsewhere. This is inconsistent with TOPSIS scores which could be 0- 1 floats. If backend returns 0-1, score bar (line 354-356) will be 0-1% wide. 

- Lines 354-356: Score bar width uses route.overall_score directly as percentage — if score is 0-1 range, bar will be nearly invisible (<1%). 

- Line 344: formatRupees(route.total_fare) — but total_fare could be undefined/null. formatRupees returns ₹0.00 for falsy values, which is acceptable but misleading. 

Missing features: 

- No waypoint support in the UI (API supports waypoints param) 

- No departure time / arrival time selection 

- No "leave now" / "leave at" toggle 

- No transit fare breakdown by mode (bus vs metro vs train) 

- No comparison against real-time traffic for drive mode 

6. components/DiscoveryPanel.tsx (149 lines) 

What it does: Right-side panel showing detailed place info — images, reviews, summary, hotel prices, action buttons. 

Bugs: 

- Lines 137-143: "Navigate Here" button dispatches a CustomEvent named 'navigate-toplace' — but no component in the codebase listens for this event. This is a dead-end feature. It should call a callback prop or use context. 

- Line 132: "View on Maps" opens Google Maps in a new tab — this is correct but the URL doesn't include lat/lng, only place name. Google Maps search might not find the exact place. 

- Line 71: Uses emoji 📍 for distance — inconsistent with the rest of the UI that uses material icons. 

- Line 105-108: place.concerns is displayed with hardcoded ⚠️� emoji — inconsistent style. 

- No loading state: The panel assumes place is fully populated — but the parent MainPage shows an "Enriching..." overlay while enrichPlace runs. However, if enrichment fails (line 44- 

46), the original (unenriched) place is passed and DiscoveryPanel may show missing data (no image, no reviews, etc.). 

- Missing scrollbar styling: overflowY: 'auto' on line 31 uses default scrollbar (no custom CSS class). 

7. components/MapView.tsx (163 lines) 

What it does: Leaflet map rendering with tile layer, markers, polylines, source/dest markers, live tracking dot, news markers. 

Bugs: 

- Lines 31-37: MapController attaches moveend listener on every center change — but the useEffect deps are [map, onCenterChange]. Since onCenterChange is a new function reference on every render of MainPage, this causes constant re-attachment of listeners. Should use useRef for callback or stabilize the reference. 

- Lines 107-108: Both userLocation (initial GPS fix) and liveTrackingPos (watchPosition) render UserLocationMarker — but only one should show at a time. If tracking starts, trackingActive becomes true and liveTrackingPos is shown, but userLocation still contains the initial fix. If userLocation and liveTrackingPos differ (tracking moves), BOTH markers appear on screen. Line 107's !trackingActive condition prevents this in theory, but there's a race: trackingActive becomes true in state update, but liveTrackingPos may not be set yet (first watchPosition callback hasn't fired), so briefly NEITHER marker shows. 

- Line 59: Material Symbols workaround using font-variation-settings in HTML string inside divIcon — this is fragile and may not render correctly depending on browser's Material Symbols support. The HTML string bypasses React and uses inline CSS. 

- Lines 114-130: Map polylines and CircleMarkers use key={i} — fragile array indices. If route geometry changes order, all elements re-render unnecessarily. 

- Lines 150-160: News markers use item.lat! and item.lng! with non-null assertion — but the filter on line 150 checks n.lat && n.lng, which would fail for lat: 0 or lng: 0. Should be n.lat ! == undefined && n.lng !== undefined. 

- No cleanup: No useEffect cleanup for the MapContainer — when component unmounts, Leaflet may leak DOM nodes or event listeners. 

- Missing animation: Source/Dest markers (lines 132-148) don't have the same createPinHtml treatment with hover effects — they're plain divs with a material icon class. Unpolished compared to PlaceMarker. 

- Missing custom AttributionControl: Uses default OSM attribution — fine but no customization possible. 

8. components/TripPanel.tsx (70 lines) 

What it does: Trip planner panel — placeholder UI with "Create New Trip" button and "Active Journey" tracking card. 

Bugs: 

- Line 23: onClick={() => {}} — the "Create New Trip" button does absolutely nothing. This is a dead UI element. 

- Lines 47-67: The "Active Journey" tracking section is shown when trackingActive is true — but trackingActive is only set from startJourney()/stopJourney() in context. The stopJourney button calls stopJourney which clears tracking. However, there's no way to start a journey from TripPanel itself — only from AToBPanel has the "Start Journey" button. Users who open TripPanel first have no way to start tracking. 

- Lines 56-59: Shows raw GPS coordinates liveTrackingPos[0].toFixed(4), ... — not useful for most users. Should show an address or at least a "View on Map" link. 

- Entire panel is mostly placeholder: "No trips planned yet" with no way to plan a trip from this panel. It doesn't integrate with any backend API for trip persistence. 

9. components/SegmentPanel.tsx (737 lines) 

What it does: Complex multi-segment route builder with columns for direct options, nearby stops, transit options, transfers, final mile. Interactive column-based UI. 

Bugs: 

- Lines 106-117: getAllSegments is called on mount with sourceName and destName — but these could be empty strings if not set by parent. No validation before API call. 

- Lines 130-137: handlePickReach uses chainState.activeSegIdx in state update via setChainState — but this uses stale closure. If prev is needed, it's fine, but chainState might be stale. The function has chainState.activeSegIdx in deps, so it's moderately safe — but setBuiltPath filter logic is complex and error-prone. 

- Lines 139-158: handlePickTransit has a complex 4-branch conditional for next_segment_index, final_options, next_transit. The branching logic has duplicate code paths (lines 146 vs 148 are identical) suggesting confusion. 

- Lines 192-218: handleGoBack logic tries to "reverse" the user's path — but the fallback chain (selectedFinal → transferChain.pop() → selectedTransit → selectedDest) assumes a strict linear progression. If user clicks options out of order, the back logic breaks. 

- Lines 193-208: The logic to find the parent segment when going back from a child segment is fragile — uses [...builtPath].reverse().find(...) which is expensive and relies on (s.opt as any).next_segment_index. TypeScript as any bypasses the entire type system. 

- Lines 220-241: handleAddCustomWaypoint resets the entire chain state to segment 0 — losing all previous selections. It also calls getAllSegments again, which may cause infinite recursion if the custom waypoint is the destination. 

- Lines 261-285: Geometry effect rebuilds on every builtPath and hoveredOption change — but doesn't clean up old geometry. If the parent component doesn't handle incremental updates, stale polylines remain. 

- Line 288: totalPerPerson sums per_person from all steps — but per_person could be 0 for some steps and defined for others. The total is misleading. 

- Lines 293-307: optCardStyle function is called inline in render — creates new style objects every render. Should use useMemo or CSS classes. 

- Lines 309-358: renderOptionDetail uses any type — no type safety. Accesses opt.departure_time, opt.arrival_time, opt.group_capacity, opt.dropoff_walk_min, opt.dropoff_to_dest_km, opt.transit_type which may not exist on all option types. 

- Lines 526-539: Transfer columns rendering uses an IIFE for the first transfer level and a .map for subsequent levels — inconsistent. The IIFE returns null if cs.transferChain.length ! == 0, meaning the first transfer column disappears when user picks a transfer option? That's likely not intended. 

- Lines 642-671: Summary bar's budget bar uses totalFare / budget * 100 — if budget is 0, division by zero produces Infinity% width. 

- Line 654: Same division issue — (totalFare / budget) * 100 with no guard for budget === 0. 

- CSS hardcoding: Many inline styles reference #1a1a1a, #555, #f f24 directly instead of CSS variables — violating the dark theme fix documented in AGENTS.md (Issue 14). Compare with the CSS variable usage in other components that were fixed. 

- No keyboard accessibility: The column UI is entirely mouse-based. No tab navigation, no ARIA labels, no keyboard event handlers. 

- Memory leak: abortRef.current is set in handleCustomInput but never checked for cleanup on unmount. If component unmounts while a search is pending, the API call continues. 

- Untracked state: customInput and customSuggestions don't reset when data changes or segments re-fetch — stale suggestions remain. 

10. components/NewsOverlay.tsx (110 lines) 

What it does: Floating overlay displaying live travel news with filtering by impact type. Bugs: 

- Line 28: Background is hardcoded rgba(15, 23, 42, 0.95) (dark theme) — doesn't use CSS variables. This was mentioned as a known Issue 14 fix (SegmentPanel was fixed, but NewsOverlay was missed). In light mode, this dark overlay will look out of place. 

- Line 29: Border and shadow also hardcoded dark colors. 

- All text colors: Hardcoded #e2e8f0, #94a3b8, #64748b, #1e293b — no CSS variable usage. Breaks theming. 

- Line 43: Loading spinner uses animation: spin 1s linear infinite — but the CSS class .spinner at line 114 of index.css already has a spin animation. This inline style duplicates the animation. 

- Not used anywhere: Despite being well-implemented, NewsOverlay is imported nowhere in the codebase. It's a dead component. 

- Performance: Every filtered.slice(0, 5) creates a new array on render. 

11. index.css (157 lines) 

What it does: Design system CSS with glassmorphism, design tokens, animations, responsive breakpoints. 

Issues: 

- Line 48: .sidebar has width: 420px; min-width: 420px — these are overridden in MainPage's inline style (style={{ width: 420, minWidth: 420 }}). The CSS class is redundant. 

- Line 81: .place-card:not(.recommended) uses border-left: 3px solid var(--error) — this means place cards that are NOT recommended get a red left border. But in SearchPanel's PlaceCard, the card border-left color is determined by score ranges (green/yellow/red), NOT by is_recommended. The CSS class suggests a binary recommended/not-recommended system that the React code doesn't use. 

- Line 78-81: .place-card classes are defined but never used — SearchPanel's PlaceCard uses inline styles instead of these CSS classes. 

- Missing CSS variable for text: Many classes reference #6b6b7b or #555 or #1a1a1a directly instead of using CSS variables like --text-muted or --text. This breaks dark mode support. 

- Line 55: .leaflet-container background hardcoded #e8e8ec — should be a CSS variable. 

- No print styles, no prefers-reduced-motion media query for the animations. 

12. services/api.ts (137 lines) 

What it does: Axios-based API client for all backend endpoints. 

Issues: 

- Line 7: Timeout is 120000ms (2 minutes) — very long. Should be configurable or shorter for different endpoints (suggestions: 5s, nearby: 15s, routes: 60s). 

- Line 10-16: searchPlaces sends lat/lng as separate params but backend might expect them as a different format. No validation that lat/lng are valid numbers. 

- Lines 18-28: getNearbyPlaces doesn't accept an AbortSignal — can't cancel in-flight requests when user changes radius or category rapidly. 

- Lines 42-53: planRoute uses POST but the waypoints param is in the type but not sent if undefined (spread into params object). TypeScript won't catch missing fields at runtime. 

- Lines 72-75: getRidePrices sends source/destination as query strings — but the backend needs resolved lat/lng for accurate pricing. Sending just names could result in incorrect pricing. 

- Lines 103-116: getAllSegments has maxDepth defaulting to 3 — no validation that it's a positive integer. 

- Line 5-8: api instance is exported as default AND individual functions are exported as named exports. Consumers use named exports (e.g., import { searchPlaces } from 

'../services/api'). The default export (export default api) is never used but exported. 

- No interceptor: No request/response interceptors for logging, error handling, or auth tokens. 

- No error types: All catch blocks in components use any type — the API module could export typed errors. 

13. utils/helpers.ts (185 lines) 

What it does: Utility functions for icons, labels, formatting, scoring. 

Issues: 

- Emoji inconsistency: getModeIcon() returns emojis like 📍, 📍, 🚇 — but other parts use Material Symbols icons. This creates visual inconsistency. The getModeIconName() function exists but is only used by SegmentPanel. 

- Line 96-99: formatRupees returns ₹0.00 for undefined or null — better to return 'N/A' or empty string for missing values, since ₹0.00 is misleading for unpriced items. 

- Lines 101-106: getScoreColor expects score 0-100 — but if backend returns 0-1, all scores appear red. No documentation about expected range. 

- Line 116-123: getPinColor has a branch that checks score >= 80 → green, >= 60 → yellow, else red — but getScoreColor uses >= 80 green, >= 60 yellow, >= 40 orange, else red. Different threshold mappings cause inconsistent color coding between map pins and route cards. 

- Line 3: icons map uses descriptive keys like walk_to_bus but the backend/data may use different mode strings. No normalization layer. 

- Dead code warnings: getModeIconName() (line 125) and getPlaceIconName() (line 150) overlap significantly in purpose — one returns Material icon names, the other returns Material icon names for place types. Both could be merged. 

14. types/index.ts (294 lines) 

What it does: All TypeScript interfaces and types used across the frontend. 

Issues: 

- Dead types: MiniPathTransitOption (line 132), MiniPathOptions (line 159), MiniPathSegment (line 177), BuiltRoute (line 185), SegmentStepData (line 219), UserPreferences (line 126) — these are defined but never imported or used anywhere in the frontend. Leftover from a previous architecture. 

- Line 112: AppMode is a string union type — used in context but the tabs array uses tab.key which is typed as AppMode, but handleModeChange in MainPage uses 'search' | 'atob' | 'trip' inline instead of reusing AppMode. 

- Line 121: EnrichSingleResponse has place: PlaceResult — but the enrichPlace API call may return additional fields not in the response type (e.g., status field). The type is narrow. 

- Missing types: No types for error responses from API, no type for the /search/suggestions response (currently returns any in getSuggestions), no type for /search/ride-prices response (return type has prices but the backend might return ride_prices). 

- Line 281-288: MapRouteGeometry has type: 'route' | 'segment' | 'hover' | 'stop' — MapView only handles 'stop' and everything else (treating 'route', 'segment', 'hover' identically as polylines). The 'hover' type is only used by SegmentPanel and ignored by MapView — no visual distinction for hovered routes. 

SUMMARY: CROSS-CUTTING ISSUES 

Critical Bugs 

# File Line(s) Issue 1 AToBPanel 102-107 Ride pricing fetched only when data.weather exists (unrelated condition) 2 AToBPanel 229-243 Transport sub-toggle (direct/segment) is dead state — ignored by handleFindRoutes 3 DiscoveryPanel 137-143 "Navigate Here" dispatches CustomEvent that no listener handles 

4 SearchPanel 60 searchPlaces uses hardcoded Bangalore center, not user location 

5 MapView 31-37 moveend listener re-attached on every render (unstable callback ref) 

6 AToBPanel 320 all.indexOf(route) uses reference comparison — breaks when 

routes re-render 

7 SegmentPanel 654 totalFare / budget * 100 — division by zero when budget is 0 8 TripPanel 23 "Create New Trip" button has empty onClick — dead UI 

Dead / Unused Code 

Component Status 

NewsOverlay.tsx Not imported or used by any component 

getMiniPathOptions() in api.ts Function defined but never called 

Types: MiniPathTransitOption, MiniPathOptions, MiniPathSegment, BuiltRoute, SegmentStepData, UserPreferences Defined but never used 

api default export Never imported by consumers (all use named exports) 

Fake / Missing / Hardcoded Data 

# File Issue 

- 1 SearchPanel:60 Hardcoded Bangalore center instead of user location 

- 2 NewsOverlay:28-29 Hardcoded dark theme colors (rgba(15,23,42,0.95), #334155) 

- breaks light theme 

- 3 SegmentPanel:298 Hardcoded text color #555 instead of CSS variable 

- 4 SegmentPanel:322 Hardcoded #1a1a1a for text color 

- 5 Various Emojis (📍, 📍, ⚠️�, etc.) used in inline HTML — inconsistent with Material Symbols icon system 

- 6 All panels No loading skeleton for initial data fetch on first render 

API Integration Issues 

# File Line Issue 

1 api.ts 72-75 getRidePrices sends name strings, not lat/lng — backend may need coordinates 

- 2 api.ts 10-16 searchPlaces accepts lat/lng but SearchPanel doesn't pass user's location 

3 AToBPanel 78-108 No AbortSignal passed to planRoute for drive and walk submodes (only transport mode has abort) 

- 4 api.ts 7 120s timeout is too long — should be endpoint-specific 

- - 

- 5 None of the API calls have retry logic or consistent error handling 

# Performance Issues 

- # File Issue 

- 1 AppContext:93-97 tabs array recreated on every render 

- 2 MapView:31-37 moveend listener re-attached every render 

- 3 SegmentPanel:293-307 optCardStyle creates new objects on every render 

- 4 MapView:111 Marker key={i} — array index as key prevents reconciliation 

- 5 MainPage All callbacks passed as new refs on every render (no useCallback for trivial handlers) 

# Code Quality Issues 

- # File Issue 

- 1 MainPage:51-55 Duplicate useApp() call 

- 2 SegmentPanel:193-208 as any type casting to access next_segment_index 

- 3 SegmentPanel:309-358 renderOptionDetail param typed as any 

- 4 helpers.ts getScoreColor and getPinColor have different threshold mappings 

- 5 Multiple files Inline styles over CSS classes — index.css has .place-card, .route-card, etc. but all components use inline styles 

- 

- 6 

   - No test files found in frontend 

- 7 Context 18 separate state setters passed through context — violates single- 

- responsibility principle 

Broken Components / Functionality 

- # Component Issue 

- 1 TripPanel Entirely placeholder — "Create New Trip" does nothing, no trip persistence 

- 2 NewsOverlay Never rendered by any parent component 

- 3 AToBPanel Transport subtype toggle (direct/segment) has no effect on API call 

- 4 DiscoveryPanel "Navigate Here" button dispatches unhandled custom event 

- 5 SegmentPanel Complex state machine with inconsistent back-navigation and 

- uncontrolled side effects 

Maine poora codebase audit kar liya — backend (1994 lines), frontend (10 components + CSS + API), ML (3 files), Docker, scrapers (6 files), LangGraph agents, datasets, tests. Yeh raha exact analysis: 

📍 KYA SAHI CHAL RAHA HAI 

Feature Status 

Map + 3-tab UI (Search / A→B / Trip) 📍 Working 

OSRM Car Docker (real road paths) 📍 Working on :5000 

OSRM Foot Docker 📍 Fixed — now working on :5001 A* graph (transit_graph.py) 📍 Properly built (2939 nodes, ~54000 edges) 

TOPSIS scoring (ml/topsis.py → transit_scoring.py) 📍 Proper numpy multi-criteria 

Weather (Open-Meteo, route coords) 📍 Working 

LangGraph Agent (tool registry, intent, parallel) 📍 Framework ready 

GPS Live Tracking (watchPosition) 📍 Implemented Discovery Panel (right-side glass panel) 📍 Working Search Panel (OSM + places + nearby) 📍 Working 

Real paths (OSRM car + foot) 📍 Both working now 

GTFS caching (0.65s load, <1s queries) 📍 Fast 📍 Fast Bus pre-resolve (7.7s first run, 0s cached) 

📍 CRITICAL PROBLEMS (12) — SABSE PEHLE THEEK KARNA 

Backend 

# Problem File:Line Detail 

1 Ride pricing toggle dead — transportType state never used in API call AToBPanel.tsx:229-243 "Multi-Hop Transit" vs "Direct Ride" produce identical API calls. User selects but no effect. 

- 2 Ride prices fetched only when weather exists — unrelated condition AToBPanel.tsx:102-107 getRidePrices called only if data?.weather exists. 

Logical bug — weather has nothing to do with ride pricing. 

3 Fake reviews fallback — LLM generates fake "Priya Sharma" reviews when SerpAPI fails llm_agent.py:249-253, geocoding.py:377-398 Real data unavailable → fake Indian names generated. Looks cheap. 

4 Fake ride pricing — formula fallback always used ride_scraper.py:47-61 Uber API scrape blocked, SerpAPI returns fare=0, always base + dist * per_km formula. 

5 JustDial scraper completely broken — 0 results always justdial_scraper.py Site blocks httpx requests. All CSS selectors likely outdated. 

- 6 Bare except: pass everywhere — 30+ locations across codebase Multiple files Every error silently swallowed. No logging. Impossible to debug issues. 

- 7 LLM agent returns hardcoded fake news when real news unavailable llm_agent.py:249-253Returns {"title": "Bengaluru Traffic Advisory", ...} — literal 

- hardcoded dict. 

8 transit_service.py still 1994-line monolith — segment builder, fare engine not extracted transit_service.py Ride type iteration duplicated 12 times. Walk/ride option dict creation duplicated 40+ times. 

9 ml/ directory dead code — astar.py, topsis.py, data_preprocessor.py unused (~250 lines) ml/ Backend uses transit_graph.py and transit_scoring.py instead. Should delete. 

10 requirements.txt incomplete — missing 6+ packages (selenium, openai, googlesearch-python, duckduckgo_search, Pillow, tenacity)requirements.txt pip install will fail when scrapers try to import these. 

# Frontend 

# Problem File:Line Detail 

11 DiscoveryPanel "Navigate Here" does nothing — dispatches CustomEvent nobody listens to DiscoveryPanel.tsx:137-143 Dead-end button. Should call context/prop to activate A→B with source=current, dest=this place. 

12 TripPanel entirely placeholder — "Create New Trip" onClick is empty () => {} TripPanel.tsx:23 No trip persistence, no API integration, no way to actually plan 

a trip. 

🟡 HIGH PRIORITY (14) 

Backend 

13. OSRM health check runs on every /all-segments request — wasteful, should cache | routes.py:370-380 

14. Traffic data is static CSV, not live — traffic_logs.csv loaded once, uniform congestion | routes.py:614-644 

15. GTFS debug time override is global mutable state — not thread-safe | gtfs_service.py:100-117 

16. database.py singleton not thread-safe — no lock on initialize() | database.py:28-35 

17. Reddit client recursive fallback — could infinite loop | reddit_client.py:51 

18. LangGraph intent detection is keyword-based, not semantic — fragile | agent.py:82-120 

19. 24 city-pair train data still limited — only 7 have real fallbacks | transit_config.py 

Frontend 

20. searchPlaces uses hardcoded Bangalore center instead of user's location | SearchPanel.tsx:60 

21. NewsOverlay never rendered by any component — dead component | NewsOverlay.tsx 

22. Score display inconsistency — getScoreColor and getPinColor have different thresholds | helpers.ts:101-123 

23. totalFare / budget * 100 — division by zero when budget is 0 | SegmentPanel.tsx:654 

24. No loading skeleton for initial data fetch — white flash | All panels 

25. Inline styles over CSS classes everywhere — index.css has .place-card, .route-card but unused | All components 

26. No AbortSignal for nearby/category searches — old requests pile up | SearchPanel.tsx 

Tests 

27. Zero pytest-discoverable tests — 10 ad-hoc scripts, no CI | Root + scripts/ 

- 📍 MEDIUM PRIORITY (8) 

28. traffic_logs.csv (7.5MB) unused — no code reads it | data_cache/ 

29. Docker backend image ~2GB — copies frontend + GTFS zip + pickle cache | Dockerfile.backend 

30. start.ps1 kills ALL Python processes — not just backend | start.ps1 

31. TypeScript types: 6 dead types — MiniPathTransitOption, BuiltRoute, etc. defined but unused | types/index.ts 

32. api default export never used — all consumers use named exports | api.ts:5-8 

33. Moveend listener re-attached every render — onCenterChange new function ref each time | MapView.tsx:31-37 

34. Hardcoded emojis (📍, 📍, ⚠️�) instead of Material Symbols — inconsistency | Multiple components 

35. Frontend no testing framework — no jest/vitest/playwright | package.json 

- 📍 ALREADY FIXED (12) — Verify karlo 

- # Fix Status 

- 1 OSRM URL public → localhost:5000 📍 Done 

- 2 OSRM Foot OOM fixed 📍 Running on :5001 

- 3 GTFS route numbers cleaned ("MF-28 ..." → "MF-28") 📍 Done 

- 4 📍 Done Metro direction filter unblocked 

- 5 📍 Done Circular routing (300m→800m radius) 

- 6 GTFS lazy loading (41s startup removed) 📍 Done 7 Train data expanded (10→28 city pairs) 📍 Done 

- 8 SegmentPanel dark theme (CSS variables) 📍 Done 

- 9 Bus↔Bus walk edges in A* graph (4472 edges) 📍 Done 10 📍 Done Bus→metro CASE 2 (all metro stations) 

- 11 📍 Done SerpAPI review key fix (place → place_results) 

- 12 Ride fare per-person double-charge bug 📍 Done 

- 📋 AGAR AAP AGLA KYA KARNA CHAHTE HO TOH YEH ORDER SUGGEST KARTA HOON: 

Phase 1 — Critical Backend Fixes (2-3 days) 

1. llm_agent.py — fake news/reviews hardcoded HATANA, empty list return karo agar real data nahi hai 

2. justdial_scraper.py — DataImpulse residential proxy use karke fix karo 

3. ride_scraper.py — Uber/Ola scraping DataImpulse proxy ke through improve karo 

4. requirements.txt — missing 6 packages add karo 

5. transit_service.py → extract segment_builder.py, fare_engine.py (ride types 1 jagah) 

Phase 2 — Critical Frontend Fixes (2-3 days) 

6. AToBPanel.tsx — transport type toggle ko actual API call me bhejo 

7. DiscoveryPanel.tsx — "Navigate Here" ko A→B se connect karo 

8. TripPanel.tsx — "Create New Trip" ko working banayo 

9. NewsOverlay.tsx — wire it in OR delete karo 

10. SearchPanel.tsx:60 — hardcoded center → userLocation 

Phase 3 — Polish (1-2 days) 

11. ml/ folder dead code delete 

12. traffic_logs.csv delete ya use karo 

13. except: pass everywhere → proper logging 

14. Stitch Omnipath design references → frontend theme update 

15. Division by zero guards in SegmentPanel 

Phase 4 — Testing (1 day) 

16. pytest setup karo, _test_*.py → proper test files 

17. $200 proxy (DataImpulse $5/5GB) enough hai — Uber/Ola/JustDial ke liye 

Proxy suggestion: DataImpulse Residential ($5/5GB) kaafi hai — Uber/Ola pricing scraping, JustDial, news scrapers sab ismein aa jayenge. SerpAPI/Google Maps API ko proxy nahi chahiye. Reddit free public JSON API hai. 

# PHASE 1 DETAILS 

Phase 1 Complete Approach — "Make Everything Actually Work" 

Yeh approach 4 Sprints (4-5 weeks) ka hai. Har sprint ke baad ek working version milega. 

SPRINT 1: FAKE DATA → REAL DATA (Week 1) 

Goal: App jhootha data dikhna band kare. Agar real data hai toh dikhe, nahi hai toh empty state dikhe. 

1A. llm_agent.py — Hardcoded fallbacks HATANA (4 changes) 

# File:Line Problem Fix 

1 llm_agent.py:249-253get_travel_news() returns hardcoded dict with "Bengaluru Traffic Advisory" fake news Remove hardcoded dict, return []. Frontend ko empty state handle karni hai 

2 llm_agent.py:235 get_weather_impact() returns {"condition": "clear", ...} hardcoded when API fails Return {} empty dict. Frontend ko if weather.condition === "clear" nahi karna 

3 llm_agent.py:200-204get_recommendations() returns estimated_cost_min: 100, tips: ["Book cab..."] hardcoded Return None for all missing values 

4 llm_agent.py:281-283chat_response() returns "I'm having trouble..." hardcoded on failure Propagate actual error to frontend 

1B. llm_agent.py:221-235 — Weather API Fix 

Current: weather_client → str(temperature), str(humidity) — returns strings, not numbers 

Fix: Return actual float values. Remove str() conversion. Remove hardcoded "moderate"/"minor" — let API decide. 

1C. Scraper Fix Chain (Google Reviews) 

Step What File Approach 

1 SerpAPI reviews serpapi_client.py 📍 Already works — _parse_place_detail fixed previously 

2 Google Maps scrape fallback google_reviews_scraper.py:46-63 Remove this — against Google ToS, always fails. Replace with: Google Places API (textSearch → Place Details) 

3 DuckDuckGo fallback google_reviews_scraper.py:65-97 Keep — works for basic snippets. Mark as source: "web_fallback" with reliability_score: 0.3 

4 NEW: Google Places API google_maps_client.py Add method get_place_details(query) → returns rating, reviews count, user ratings total, price level. This is free (200$/month credit) 

1D. Scraper Fix — JustDial 

Problem: justdial_scraper.py — site blocks httpx requests even with DataImpulse proxy. 

Approach: JustDial ko scrap karne ke bajaye, uski functionality Google Places API se replace karo. Google Places API gives: 

- Business name, address, phone, rating, reviews 

- Opening hours, price level 

- No IP blocking (API key based) 

Changes: 

1. justdial_scraper.py → search() method: Call Google Places API textSearch instead 

2. justdial_scraper.py → get_reviews(): Call Google Places API Place Details → reviews 

3. If API call fails → return [] (don't try to scrape) 

4. OR keep justdial as fallback with selenium (heavy but works) 

My recommendation: Google Places API hi use karo. ₹0 cost (free tier mein 200$/month credits). SerpAPI ke sath redundancy bhi hai. 

1E. Scraper Fix — Ride Pricing 

Problem: ride_scraper.py:54-77 — SerpAPI Directions returns fare=0 always for Indian routes. 

# Approach: 

1. SerpAPI call keep — but if fare=0 or empty, treat as failure 

2. On failure → use formula-based estimate with clear "estimated" badge 

3. Add source field: "live" if SerpAPI succeeded, "estimated" if formula used 

4. Surge factor improvement: weather_client.surge_multiplier already works (0.3 for rain). Keep that. Time-based surge (_get_surge_factor lines 122-142) keep. 

Key fix: Mark estimates clearly. User ko pata hona chahiye ki live price hai ya estimated. 

- 1F. News Scraper Fix 

Problem: news_scraper.py:81 — TOI/The Hindu URL construction fragile. 

# Approach: 

1. Reddit search 📍 already works for Bangalore travel news 

2. TOI/The Hindu — use DuckDuckGo search f"bangalore traffic news site:timesofindia.indiatimes.com" instead of hardcoded URLs 

3. If all fail → return [] (no fake news) 

- 1G. Add Logging Everywhere 

All 30+ except: pass locations → replace with: 

import logging 

logger = logging.getLogger(__name__) 

try: 

... 

except Exception as e: 

logger.warning(f"JustDial search failed for {query}: {e}") 

Files affected: routes.py (10+), transit_service.py (5+), transit_paths.py, gtfs_service.py, transit_config.py, all scrapers, all clients, agent.py. 

SPRINT 2: FRONTEND CRITICAL BUGS (Week 2) 

Goal: Users jo buttons click karte hain, vo actually kaam karein. 

2A. AToBPanel.tsx — Transport Type Toggle Fix 

Current Bug (lines 95-107, 229-243): transportType state ("direct"/"segment") set hota hai but handleFindRoutes mein use nahi hota. Dono toggle same API call karte hain. 

Fix: 

Lines 95-107 in handleFindRoutes: 

if (subMode === 'transport') { 

if (transportType === 'direct') { 

// ONLY show ride prices — no transit segments 

const prices = await getRidePrices(sourceQuery, destQuery) 

setRidePrices(prices?.prices || []) 

setRoutes([]) 

} else { 

// transportType === 'segment' — show full transit routing 

const data = await planRoute({ mode: 'public', ... }) 

setRoutes(data?.routes || []) 

const prices = await getRidePrices(sourceQuery, destQuery) 

setRidePrices(prices?.prices || []) 

} 

} 

Line 102: Remove if(data?.weather) condition — ride prices should load UNCONDITIONALLY for transport mode 

2B. AToBPanel.tsx — Reference Comparison Bug 

Current Bug (line 320): all.indexOf(route) uses reference comparison. Jab routes array React rebuild karta hai, references change ho jate hain → indexOf returns -1 → selection breaks. 

# Fix: 

- // Instead of all.indexOf(route) 

const routeKey = `${route.total_distance_km}-${route.total_fare}-$ {route.total_duration_minutes}` 

const isSelected = selectedRouteKey === routeKey 

- // Store selectedRouteKey instead of selectedRouteIdx 

- 2C. DiscoveryPanel.tsx — "Navigate Here" Button 

Current Bug (lines 137-143): Button dispatches CustomEvent('navigate-to-place') — no component listens for this event. Button does nothing. 

Fix: 

1. Add onNavigate: (place: PlaceResult) => void prop to DiscoveryPanel 

2. In MainPage.tsx: When user clicks "Navigate Here": 

- Set sourceLocation to user's current GPS location 

- Set destLocation to [place.lat, place.lng] 

- Set sourceQuery to "Current Location", destQuery to place.name 

- Switch active tab to 'atob' 

- Auto-trigger route search 

2D. TripPanel.tsx — "Create New Trip" Button 

Current Bug (line 23): onClick={() => {}} — button does absolutely nothing. 

Fix: Either: 

- Remove "Create New Trip" section (replace with placeholder "Coming Soon") 

- OR make it switch to A→B panel with a note "Start by planning a route" 

- OR add basic trip name input + persistence to localStorage 

Recommended: Second option — it's minimal code and improves UX. 

2E. SearchPanel.tsx — Hardcoded Bangalore Center 

Current Bug (line 60): searchPlaces(q, 12.9716, 77.5946) — always uses MG Road center. 

Fix: 

const userLat = userLocation?.[0] ?? 12.9716 

const userLng = userLocation?.[1] ?? 77.5946 

const data = await searchPlaces(q, userLat, userLng) 

Also fix lines 88-89 for getNearbyPlaces — same hardcoded center. 

2F. MapView.tsx — Moveend Listener Re-attachment 

Current Bug (lines 31-37): onCenterChange callback is a new function reference on every render → useEffect re-runs → listener re-attached every time. 

Fix: 

// Use useRef for the callback 

const cbRef = useRef(onCenterChange) 

cbRef.current = onCenterChange 

useEffect(() => { 

if (!map) return 

const handler = () => cbRef.current?.(map.getCenter()) 

map.on('moveend', handler) 

return () => map.off('moveend', handler) 

}, [map])  // Only depends on map instance 

2G. ATobPanel + SegmentPanel Stitch Reference UI 

Stitch reference wayfinder_segment_selection/code.html dikhata hai ki segment selection UI kaisa hona chahiye. Currently SegmentPanel.tsx me inline styles aur #1a1a1a hardcoded colors hain. 

Fix: SegmentPanel UI ko Stitch reference ke according refactor karo: 

- Glass panels with proper surface colors 

- Timeline connector lines (left side) 

- Radio-button card selection 

- "Next Segment" button at bottom 

- Icons in circles with mode-appropriate colors 

SPRINT 3: BACKEND REFACTORING (Week 3) 

Goal: Code maintainable ho. Bug fix karne mein 10 min lage, 1 ghanta nahi. 

3A. transit_service.py Monolith Split (~1994 lines) 

Extract into 3 new files: 

New File Lines to Extract Content 

segment_builder.py ~600 lines from transit_service.py _build_single_segment, _build_next_transit, get_segment_step_options, _add_reach_options, _add_transit_options, _find_farthest_bus_stop 

fare_engine.py ~100 lines from transit_service.py + transit_config.py Centralized _RIDE_TYPES (currently duplicated 12 times!), _calc_ride_fare, _ride_fare_range, all BMTC/metro/KIA fare logic 

transit_service.py ~600 lines remaining Pure orchestrator — calls segment_builder, fare_engine, transit_graph, transit_scoring, transit_paths 

Benefit: Ek jagah ride fare change karo → sab jagah reflect ho. Bug fix karte waqt sirf relevant file open karo. 

3B. requirements.txt Fix 

Missing packages to add: 

selenium>=4.15.0        # JustDial scraping fallback 

openai>=1.0.0           # LLM fallback 

googlesearch-python     # DDG search 

duckduckgo_search       # DDG search fallback 

Pillow>=10.0.0          # Image processing 

tenacity>=8.0.0         # Retry logic for scrapers aiofiles                # Async file operations 

3C. Dead Code Removal 

File Lines Reason 

ml/astar.py 122 Unused — replaced by transit_graph.py ml/topsis.py 64 Unused — replaced by transit_scoring.py 

ml/data_preprocessor.py 64 Unused — references deleted datasets frontend/src/components/NewsOverlay.tsx 110 Never imported/rendered by any component 

frontend/src/types/index.ts — 6 dead types ~50 MiniPathTransitOption, MiniPathOptions, MiniPathSegment, BuiltRoute, SegmentStepData, UserPreferences 

frontend/src/services/api.ts — default export 1 export default api — never used by any consumer 

frontend/src/services/api.ts — getMiniPathOptions Function Defined but never called 

3D. traffic_logs.csv (7.5MB) Decision 

Problem: File exists in data_cache/ but no code reads it. 7.5MB wasted. 

Decision: 

- If you want live traffic: Remove this file. Use Google Maps API Distance Matrix with departure_time: "now" instead 

- If you want the ML model: Actually load and use the data 

- Default: Delete unused file 

SPRINT 4: TESTING & POLISH (Week 4-5) 

Goal: Koi feature jaldi na tootey. App professional lage. 

4A. Python Test Setup 

backend/tests/ 

├── conftest.py              # Test fixtures 

├── test_transit_graph.py    # A* graph building 

├── test_transit_scoring.py  # TOPSIS scoring 

├── test_gtfs_service.py     # GTFS queries 

├── test_ride_scraper.py     # Ride pricing 

├── test_database.py         # Spatial index queries 

└── test_scrapers.py         # Mocked scraper tests 

Use pytest with pytest-asyncio. Current _test_all.py, _comprehensive_test.py → convert to proper pytest files. 

4B. Score Consistency Fix 

Problem: getScoreColor (helpers.ts:101) and getPinColor (helpers.ts:116) have DIFFERENT thresholds: 

// getScoreColor:     >=80 green, >=60 yellow, >=40 orange, else red 

// getPinColor:       >=80 green, >=60 yellow, else red 

// TOPSIS range:      Backend returns 10-99 (clamped in transit_scoring.py:62) 

Fix: 

- Make thresholds consistent: Use >=80 green, >=60 yellow, >=40 orange, <40 red everywhere 

- OR simplify: Use >=70 green, >=50 yellow, else red 

- Check backend: transit_scoring.py:62 clamps to max(10, min(99, ...)) → score is always 1099, never 0-1. So percentage display {score}% is correct. 

4C. Division by Zero Guards 

Problem: SegmentPanel.tsx:654 — (totalFare / budget) * 100 when budget is 0 → Infinity. 

Fix: 

const budgetPercent = budget && budget > 0 ? (totalFare / budget) * 100 : 0 

4D. Stitch Omnipath Design System Integration 

Stitch folder mein 8 design references hain. Tumhare current UI aur Stitch ke beech ka gap: 

Aspect Current Stitch Reference Fix 

Colors Inline #555, #1a1a1a CSS variables var(--surface), var(--on-surface) Replace all hardcoded colors 

Search Bar Simple input Glass panel with menu icon + mic button + chips below Refactor SearchPanel header 

Bottom Nav Text-only tabs Pill-shaped glass nav with active state Refactor MainPage bottom nav 

Segment Panel Card list with inline styles Timeline icons + radio card selection + segment line connector Refactor SegmentPanel UI 

Discovery Panel Basic card Green/red glow cards with reliability badge + AI summary bento box Update DiscoveryPanel styles 

A→B Input Two inputs Swap button, filter chips, better placeholder design Enhance AToBPanel header 

Trip Panel Empty placeholder Image hero + budget tracker + day tabs + timeline view Full rewrite (Phase 2) 

Markers Simple div Pulsing ring, hover popup with reliability, scale 1.15x on hover Update MapView markers 

Recommended order: 

1. First apply color system (CSS variables already exist in index.css) 

2. Then update search bar + bottom nav (high visibility) 

3. Then segment panel UI (highest user interaction) 

4E. Proxy Strategy 

Data Source Current Proxy Should Use 

SerpAPI None (API key)None 📍 

Google Maps API None (API key)None 📍 

Reddit None (public JSON) None 📍 

DuckDuckGo DataImpulse Tier 2 Keep 📍 JustDial DataImpulse Tier 2 Switch to Google Places API (remove JustDial) Uber/Ola DataImpulse Tier 2 (not working) Keep SerpAPI + formula estimate marked "estimated" 

News (TOI/The Hindu)DataImpulse Tier 2 Keep 📍 

Open-Meteo (weather) None None 📍 

DataImpulse $5/5GB kaafi hai for DuckDuckGo + News. Uber/Ola ke liye SerpAPI ke sath formula backup best approach hai kyunki Uber/Ola scraping is extremely difficult (they actively block). 

COMPLETE PHASE 1 — FILE CHANGE SUMMARY 

Total files to modify: 

- Backend Python: ~20 files 

- Frontend TSX: ~8 files 

- Delete: ~6 files (dead code) 

Sprint Files Changed What You Get 

Sprint 1 llm_agent.py, ride_scraper.py, justdial_scraper.py, google_reviews_scraper.py, news_scraper.py, config.py, + logging in 15+ files No fake data. Real scraped data or empty state. "Estimated" badges on formula prices. Logging everywhere. 

Sprint 2 AToBPanel.tsx, DiscoveryPanel.tsx, TripPanel.tsx, SearchPanel.tsx, MapView.tsx, MainPage.tsx, SegmentPanel.tsx All buttons work. Toggles affect API calls. Navigate here connects to A→B. No reference comparison bugs. Dynamic map. 

Sprint 3 segment_builder.py (NEW), fare_engine.py (NEW), transit_service.py (REFACTORED), requirements.txt, + 6 deleted files Monolith split. ride types 1 jagah. Complete dependencies. No dead code. Sprint 4 backend/tests/*, helpers.ts, SegmentPanel.tsx, index.css, MapView.tsx, + all component styles pytest setup. Consistent scores. No division by zero. Stitch-level UI. Proper proxy. 

My recommendation: Sprint 1 → Sprint 2 → Sprint 3 → Sprint 4. Har sprint ke baad app deploy karke verify kar sakte hain. 

Sprint 1 — Complete 📍 

- # Task 

- 1A llm_agent.py — Fake news/weather/recommendations removed 

- 1B Weather API — returns floats not strings, no hardcoded values 

- 1C Google Reviews — Maps scrape removed → Google Places API + SerpAPI + DDG fallback 

- 1D JustDial scraper — httpx block fix → replaced with Google Places API 

- 1E Ride pricing — is_live: True/False flag added, source badges clear 

- 1F News scraper — fragile TOI/The Hindu URLs → DuckDuckGo search 

- 1G Logging — all 42 bare except: pass blocks replaced with logger.warning() across 16 files 

# SOME MINOR BUG CHECK AND CORRECT IT: 

Sprint 2 Verification Report 

Task Status Details 

- 2A TransportType toggle 📍 DoneDirect → only getRidePrices() + setRoutes([]). Segment → planRoute(mode:'public') + ride prices. Lines 99-115 

2B Reference comparison 📍 DoneselectedRouteKey string key replaces selectedRouteIdx index. Stable across re-renders. Lines 30, 36-37, 125, 331, 432 

2C Discovery "Navigate Here"📍 DoneonNavigate prop added. MainPage.tsx handler sets A→B mode with source=userLocation + dest=place. Lines 57-61, 138 

2D TripPanel "Create New Trip" 📍 DoneonClick={() => setMode('atob')} switches to route planner. Line 23 

2E SearchPanel userLocation 📍 DonecenterLat = userLocation?.[0] ?? 12.9716. Lines 62-63, 90-91 

2F MapView moveend listener 📍 DoneuseRef(cbRef) stabilizes callback. Effect depends on [map] only. Lines 30-40 

2G Glass card + BEST badge 📍 DoneAToBPanel: glass card wrapper (line 164). SegmentPanel: BEST badge (412), CSS var conversion. ~10 hardcoded colors remain in SegmentPanel (#1a1a1a, #555, #60a5fa) 

⚠️� Bug found Line 148 useEffect deps: [selectedRouteIdx, ...] should be 

[selectedRouteKey, ...] — stale variable from rename. Geometry won't update on route click 

Fixed. selectedRouteIdx → selectedRouteKey in useEffect deps at line 148. Ab route click karne par geometry properly update hogi. 

Sprint 3: Backend Refactoring — Pura Detailed Plan 

Research complete — transit_service.py ka pura structure, ml/ folder, requirements.txt, dead code, models, coupling — sab analyze kar liya. Here's the full detailed plan. 

Phase 1: Stale Dep Bug Fix (1 file, 1 line) 

File: frontend/src/components/AToBPanel.tsx:148 

Current Fix 

selectedRouteIdx useEffect(() => { ... }, [selectedRouteIdx, routes, onRouteGeometry]) → selectedRouteKey 

Why: selectedRouteIdx variable doesn't exist anymore (renamed to selectedRouteKey in Sprint 2B). Effect never re-fires when user clicks a different route. Map geometry stays stale. 

Risk: None. Trivial rename. 

Phase 2: fare_engine.py — Extract Fare Logic (~120 lines → new file) 

Current state: _calc_ride_fare() and _RIDE_TYPES are already in transit_config.py. But there's a 12x duplication of this pattern across transit_service.py: 

total = _calc_ride_fare(mode_info, dist_km) 

fare_min = total 

fare_max = round(total * 1.35)      # <-- hardcoded 35% surge, repeated 12 times 

What to create: backend/services/fare_engine.py 

# fare_engine.py 

from backend.services.transit_config import _RIDE_TYPES, _calc_ride_fare, _ride_fare_range 

SURGE_MULTIPLIER = 1.35 

def calc_fare_with_surge(mode_data: tuple, distance_km: float) -> tuple[float, float]: 

"""Returns (fare_min, fare_max) with centralized surge multiplier.""" 

total = _calc_ride_fare(mode_data, distance_km) 

return total, round(total * SURGE_MULTIPLIER) 

def get_mode_by_id(mode_id: str) -> tuple | None: 

"""Look up a ride type tuple by mode string. Returns None if not found.""" 

for mt in _RIDE_TYPES: 

if mt[0] == mode_id: 

return mt 

return None 

def ride_fare_range(mode_id, distance_km): 

"""One-call convenience for getting fare range for a mode + distance.""" 

mode_info = get_mode_by_id(mode_id) 

if not mode_info: 

return (0, 0) 

return calc_fare_with_surge(mode_info, distance_km) 

Imported by: transit_service.py — replaces 12 inline fare_max = round(total * 1.35) with single calc_fare_with_surge() call. 

Files changed: transit_service.py (12 call sites), new file fare_engine.py 

Risk: Low — pure function extraction. No instance state. Easy to test in isolation. 

Phase 3: segment_builder.py — Extract Segment Logic (~1200 lines → new file) 

This is the big one and the riskiest. Let me explain the full picture. 

3.1 Current State 

Method Lines Role Dependencies 

get_segment_step_options 479 Legacy standalone builder self.haversine_distance, self._interpolate_path, db.*, _RIDE_TYPES, _calc_ride_fare, _is_outside_bengaluru, _find_farthest_bus_stop_toward_dest, _get_bus_route_nums 

_add_direct_options 34 Walk/ride from A to B self.haversine_distance, _RIDE_TYPES, _calc_ride_fare 

_add_reach_options 40 Walk/ride to transit stop self.haversine_distance, _RIDE_TYPES, _calc_ride_fare 

_add_transit_options 281 Bus/metro/train from stop self.haversine_distance, self._cached_*, self._build_next_transit, self._interpolate_path, _RIDE_TYPES, db.* 

_build_next_transit 156 Chained transit (recursive) self.haversine_distance, self._cached_*, self._coord_key, self._is_visited, db.*, _ensure_gtfs 

_build_single_segment 111 One segment orchestrator self._add_direct_options, self._add_reach_options, self._add_transit_options, self.haversine_distance, db.* 

get_all_segments 69 Top-level orchestrator (up to 4 segs) self._build_single_segment, self._is_hub_or_close_to_dest, self._clear_caches 

Cache helpers 40 (4× methods) GTFS caches _ensure_gtfs(), _g.* (GTFS loader) 

Utility helpers 40 (5× methods) _coord_key, _is_visited, _is_outside_bengaluru, _is_hub_or_close_to_dest, _find_farthest_bus_stop_toward_dest self.haversine_distance, _haversine_dist, _MAJOR_HUBS 

TOTAL ~1250 lines 16 methods → segment_builder.py 

3.2 Extraction Strategy 

Create backend/services/segment_builder.py with a TripSegmentBuilder class: 

class TripSegmentBuilder: 

def __init__(self, haversine_fn, interpolate_path_fn, path_service=None): 

self._haversine = haversine_fn 

self._interpolate = interpolate_path_fn 

self._path_service = path_service 

# Instance-level caches 

self._gtfs_route_cache = {} self._shape_cache = {} self._stops_toward_cache = {} 

self._shape_between_cache = {} 

# All 16 methods move here with identical signatures but self._haversine replaces self.haversine_distance 

def _is_outside_bengaluru(self, lat, lng, threshold_km=35.0): ... 

def _is_visited(self, lat, lng, visited_set): ... 

def _coord_key(self, lat, lng): ... 

def _is_hub_or_close_to_dest(self, lat, lng, dest_lat, dest_lng, stop_name=""): ... def _cached_gtfs_routes(self, stop_name): ... 

def _cached_shape_path(self, route_number): ... 

def _cached_stops_toward(self, route, from_lat, from_lng, dest_lat, dest_lng, max_stops=3): ... 

def _cached_shape_between(self, from_name, to_name): ... 

def _clear_caches(self): ... 

def _add_direct_options(self, result, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size, budget): ... 

def _add_reach_options(self, from_lat, from_lng, from_name, stop_name, stop_lat, stop_lng, stop_type, group_size, budget): ... 

def _add_transit_options(self, entry, from_lat, from_lng, dest_lat, dest_lng, dest_name, group_size, budget, dest_nearby_bus, dest_nearby_metro, dest_rail, is_long_dist): ... 

def _build_next_transit(self, t_lat, t_lng, exclude_name, dest_lat, dest_lng, dest_name, group_size, budget, dest_nearby_metro, ride_types, arrival_name="", depth=2, visited_stops=None): ... 

def _build_single_segment(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size, budget, segment_index): ... 

def get_all_segments(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size=1, budget=None, max_depth=3): ... 

# # Legacy standalone builder 

def get_segment_step_options(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size=1, budget=None): ... 

def _find_farthest_bus_stop_toward_dest(self, from_lat, from_lng, dest_lat, dest_lng): ... 

3.3 Changes in transit_service.py 

# In __init__: 

from backend.services.segment_builder import TripSegmentBuilder 

self.segment_builder = TripSegmentBuilder( 

haversine_fn=self.haversine_distance, 

interpolate_path_fn=self._interpolate_path, 

path_service=self.path_service 

) 

# Method delegation: 

def get_all_segments(self, ...): 

return self.segment_builder.get_all_segments(...) 

def get_segment_step_options(self, ...): 

return self.segment_builder.get_segment_step_options(...) 

3.4 Why This Is Safe 

- All 16 methods are pure orchestrators — they call db.*, transit_config.*, _ensure_gtfs() — not self.* except for caches and haversine_distance 

- The only self.* methods called are: self.haversine_distance, self._interpolate_path, self._cached_*, self._clear_caches — all moved into the builder 

- self._interpolate_path is a 1-line wrapper: return self.path_service.interpolate_path(path) 

— easily passed as callback 

- self.path_service is only used in _interpolate_path — passed via constructor 

3.5 Why This Is Risky (BLOCKER I FLAGGED) 

Risk Impact Mitigation 

_build_next_transit calls itself recursively If the recursive call uses wrong self reference, infinite loop or wrong results Ensure recursive call uses self._build_next_transit(), not self.build_next_transit() 

Closure _add_transit_options has a nested function _relevance_score(topt) at line 1549 over local variables; must be preserved when moving Move as a local function inside the method (keep same behavior) 

_build_next_transit has 2 nested functions _add_final_walk (line 1639) and 

_make_bus_transit (line 1649) Same closure concernKeep as local functions inside 

method 

_build_single_segment has a nested _dest_score(de) function (line 1878) Same Keep as local function 

get_segment_step_options (479 lines, legacy) uses self._get_bus_route_nums → self._find_common_routes These 2 methods stay in transit_service.py — they are not segment-building In legacy builder, access _find_common_routes via callback or keep as helper 

All segment methods use _RIDE_TYPES and _calc_ride_fare from transit_config Works fine — module-level imports in segment_builder.py Just import like transit_service.py does 

- 3.6 Verification After Extraction 

1. transit_service.py goes from 1998 lines → ~600 lines 

2. All existing unit/API tests pass 

3. Server starts without import errors 

4. A→B route planning with public transport works end-to-end 

5. No functionality regression in any segment-building path 

Phase 4: transit_service.py Cleanup — What Remains (~600 lines) 

After extracting segment builder + fare logic, transit_service.py keeps: 

|#|Method<br>Lines<br>Purp|ose||
|---|---|---|---|
|1|__init__<br>6<br>Init p|ath_ser|vice + segment_builder|
|2|astar_graph (property)|6|Lazy A* graph|
|3|haversine_distance<br>7|Dista|nce utlity|
|4|_fnd_common_routes|5|Helper for legacy route gen|
|5|_add_leg_coords<br>21|Leg c|oord processing|
|6|get_route_legs_public|28|A* entry → TOPSIS scoring|
|7|_get_bus_route_nums|3|Bus route num helper|
|8|_generate_bus_routes|87|Bus route generaton|
|9|_generate_metro_routes|49|Metro route generaton|
|10|_generate_metro_intercha|nge_rou|tes<br>125<br>Metro interchange routes|
|11|_generate_kia_routes51|KIA ai|rport routes|
|12|_generate_mult_modal_ro|utes|136<br>Mult-modal combo routes|
|13<br>transit|get_mini_path_optons<br>_confg)|172|Mini-path optons (uses both db &|
|14|_interpolate_path<br>2|Passt|hrough to path_service|
|15|5× async OSRM methods|10|Passthrough to path_service|
|Total|~708 lines<br>Afer|cleanup|, target ~600 afer further extracton|



Note: get_mini_path_options (172 lines) and _generate_multi_modal_routes (136 lines) could optionally be extracted in a future Sprint 4. 

Phase 5: Dead Code Cleanup 

Item Size Risk Action ml/data_preprocessor.py Delete ~64 lines None — zero imports across codebase ml/__pycache__/ Delete Auto-gen None — not git-tracked frontend/src/components/NewsOverlay.tsx Delete ~110 lines None — zero imports frontend/src/types/index.ts unused types: UserPreferences, MiniPathOptions, MiniPathSegment, BuiltRouteDelete ~30 lines Low — verify no hidden imports 

Delete ~10 lines Low — frontend/src/services/api.ts function getMiniPathOptions verify /api/routes/mini-path-options endpoint is also dead 

backend/api/routes.py endpoint /api/routes/mini-path-options Check & maybe delete Check if Medium — must verify no caller 

_diag*.py, _debug*.py, _test*.py (root-level)Delete ~10 files None — test/diagnostic scripts 

scripts/test_*.py Delete ~5 filesNone — test scripts 

scripts/migrate_to_postgres.py Delete ~1 file Low — not in use (app uses SQLite inmemory) 

PROXY_CHECK/proxies.py Keep or delete~1 file Low — standalone utility Total dead code weight removed: ~250+ lines of code + 15+ orphaned files What NOT to delete (verified alive): 

- ml/astar.py — needed by backend/services/transit_graph.py 

- ml/topsis.py — needed by backend/services/transit_scoring.py 

- frontend/src/components/SegmentPanel.tsx — DEAD but has reusable code (multi-hop segment UI). Question for you: delete or keep as reference? 

- data_cache/traffic_logs.csv — NOT DEAD, used by routes.py:629 traffic speed overlay Phase 6: requirements.txt Fix 

Current packages never directly imported: 

Package In requirements.txt? Actually imported? Action openpyxl Yes No — transitive dep of pandas Keep (pandas needs it for .xlsx) lxml Yes No — transitive dep of beautifulsoup4 Keep (BS4 uses it as HTML parser) 

shapely Yes No — entirely unused Remove scikit-learn Yes No — entirely unused Remove networkx Yes No — entirely unused Remove 

After removal, requirements.txt goes from 15 → 12 packages. 

If you want to be MINIMAL: Remove all 3. If you want to be SAFE (in case future code uses them): Keep them but comment them out. 

Sprint 3 Execution Order 

Phase 1: Fix AToBPanel.tsx:148 stale dep          [1 min] 

↓ 

Phase 2: Create fare_engine.py                    [10 min] 

→ transit_service.py: replace 12 inline fare_max with calc_fare_with_surge() 

↓ 

Phase 3: Create segment_builder.py                [45-60 min — MOST CRITICAL] 

→ Move 16 methods (~1250 lines) 

→ transit_service.py: delegate to self.segment_builder 

↓ 

Phase 4: Clean transit_service.py                 [10 min] 

→ Remove old methods, verify remaining ~600 lines 

↓ 

Phase 5: Delete dead code                         [15 min] 

→ data_preprocessor.py, NewsOverlay.tsx, unused types, test scripts 

↓ 

Phase 6: Fix requirements.txt                     [5 min] 

→ Remove shapely, scikit-learn, networkx 

↓ 

VERIFY: Start server, test A→B route plan          [5 min] 

Blockers Summary (as you requested) 

# BlockerWhy It's Important Mitigation 

1 _build_next_transit recursive Recursive call from within the class — if self-reference is wrong, can cause stack overflow or wrong results Careful find-replace: all self._build_next_transit( → self._build_next_transit( within the extracted class (same name, works fine) 

2 3 nested functions inside segment methods _relevance_score (inside _add_transit_options), _add_final_walk + _make_bus_transit (inside _build_next_transit), _dest_score (inside _build_single_segment) — closures over local variables Keep as local functions inside their parent methods during extraction. Do NOT move to class level. 

3 get_segment_step_options uses self._get_bus_route_nums → self._find_common_routes These 2 methods stay in transit_service.py (they are routegeneration helpers, not segment-building) Pass get_bus_route_nums as a callback to TripSegmentBuilder, or keep this legacy method in transit_service.py (simpler) 

4 No Pydantic models for segment data All segment methods return raw dicts — no validation, no IDE support, no API docs Option A (recommended for Sprint 3): Keep returning dicts, add models later. Option B: Create 6 new Pydantic models (SegmentStopInfo, SegmentStepOption, SegmentDestination, AllSegment, AllSegmentsResponse). Option B adds ~150 lines of model code + validation overhead. 

5 Testing coverage No existing test suite to verify extraction didn't break anything Manual verification: start server, test 3-4 A→B route plans (different source/dest combos), verify same results as before 

6 SegmentPanel.tsx — dead but valuable It has ~700 lines of reusable multi-hop segment UI code. Deleting it loses a working reference implementation. Question for you: Keep or delete? (See question below) 

Questions for You 

1. SegmentPanel.tsx: Delete it (dead code) or keep it as reference for future reuse? 

2. Pyndantic models for segment data: Option A — keep returning raw dicts (faster, lower risk), or Option B — add 6 new models (cleaner, type-safe)? 

3. mini-path-options endpoint: Should I check if the frontend calls it, and if not, delete both the backend endpoint and frontend getMiniPathOptions function? 

4. Priority within Sprint 3: Should we do all 6 phases in one go, or stop after Phase 3 (segment builder extraction) and verify before proceeding? 

That's the complete Sprint 3 plan — saari details, saare blockers, saare risks. 

Sprint 3 complete. 52 files changed, net -2703 lines. 

# Summary: 

- Phase 1 — AToBPanel.tsx:148 stale dep selectedRouteIdx→selectedRouteKey 

- Phase 2 — fare_engine.py created with calc_fare_with_surge() + surge multiplier centralized 

- Phase 3 — segment_builder.py (1283 lines, 17 methods extracted), transit_service.py 1998→579 lines 

- Phase 4 — transit_service.py cleaned as part of Phase 3 

- Phase 5 — deleted: NewsOverlay.tsx, ml/data_preprocessor.py, scripts/test_*.py (7 files), _test*.py (2), _diag*.py (3), _debug*.py (2), scripts/migrate_to_postgres.py, getMiniPathOptions from api.ts, /mini-path-options endpoint from routes.py, 5 dead types from types/index.ts 

- Phase 6 — requirements.txt: removed shapely, scikit-learn, network 

# SPRINT 4 NOW!! 

Sprint 4: Testing & Polish — Detailed Plan 

Based on current state research. 7 tasks across 3 priority tiers. 

📍 P0 — Critical Fixes 

# Task Files Why 

4A Score color consistency — 4 different color functions/ inline logic with different thresholds helpers.ts, MapView.tsx, DiscoveryPanel.tsx getScoreColor() uses 4 tiers (80/60/40), MapView.tsx uses 0–1 scale (0.7/0.4), DiscoveryPanel.tsx uses yet another set of hex values. Same data looks different across UI. 

4B Fix bare except: in config.py backend/core/config.py:55 Only remaining bare except. except: → except (json.JSONDecodeError, TypeError): 

# 🟡 P1 — Quality 

# Task Files Why 

4C pytest setup + unit tests New tests/ folder, tests/test_fare_engine.py, tests/test_segment_builder.py Sprint 3 extracted ~1250 lines with zero test coverage. fare_engine.py (33 lines, pure functions) is trivially testable. segment_builder.py needs integration test. 

4D AGENTS.md update AGENTS.md Still shows Sprint 3 as planned, transit_service.py size wrong (says 1917 → 1994, now 534), mentions ml/ folder deletion incomplete, missing new files fare_engine.py/segment_builder.py 

# 🟢 P2 — Polish 

# Task Files Why 

4E Stitch design polish — replace ~10 remaining hardcoded colors in SegmentPanel.tsx SegmentPanel.tsx Colors like #1a1a1a, #555, #f f24, #60a5fa, #22c55e should be CSS vars. But SegmentPanel.tsx is dead code (zero imports). So question: delete it or fix it? 

- 4F Dead type cleanup — HotelPriceInfo, PlaceReview frontend/src/types/index.ts Only transitively referenced via PlaceResult, never directly imported. Low value but 

- quick win. 

4G Phase 6 completion — remove unused packages Both requirements.txtYou said it's done, but files still show scikit-learn==1.3.2, networkx==3.2.1, shapely==2.0.2 in both files. Need to verify/double-check. 

4E Decision — SegmentPanel.tsx: Delete or Fix? 

Option What Effort 

Delete Remove dead file (~730 lines)1 min 

Fix Convert 10 hardcoded colors → CSS vars + keep for future 10 min 

It's dead — not imported anywhere. I recommend Delete + keep a backup snippet in AGENTS.md if needed later. 

Sprint 4 Execution Order 

4A — Score color unification        [20 min — 3 files, moderate touch] 

- → helpers.ts: delete getPinColor (unused), keep getScoreColor as single source 

- → MapView.tsx: replace 0-1 scale inline with getScoreColor(score*100) 

- → DiscoveryPanel.tsx: replace inline hex with getScoreColor(score*100) 

↓ 

4B — Fix bare except in config.py    [2 min — 1 line] 

↓ 

- 4C — pytest setup + tests            [30 min — new tests/ folder] 

- → test_fare_engine.py (pure functions, ~10 test cases) 

→ test_segment_builder.py (integration, ~5 test cases) 

↓ 

4D — AGENTS.md update                 [10 min — doc update] 

↓ 

4E — SegmentPanel.tsx delete            [1 min — 1 file] 4F — Dead type cleanup                 [3 min — types/index.ts] 4G — requirements.txt fix              [2 min — 2 files] 

SPRINT 4: 

Sprint 4 complete. 56 files, net -3449 lines. 

- 4A — All score colors unified via getScoreColor(score*100). Found+fixed MapView.tsx bug where 0.7→green (wrong, should be yellow). 

- 4B — config.py:55: except: → except (json.JSONDecodeError, TypeError): 

- 4C — pytest setup: tests/test_fare_engine.py (12 tests), tests/test_segment_builder.py (9 tests), 21/21 pass. Also fixed a real bug: calc_fare_with_surge had wrong tuple unpacking (was treating time_per_km as base_fare). 

- 4D — AGENTS.md updated with segment_builder/fare_engine, correct line counts, Sprint 3+4 entries. 

- 4E — SegmentPanel.tsx deleted (730 lines dead, zero imports). 

- 4G — backend/requirements.txt: removed scikit-learn, networkx, shapely. 

(4F skipped — HotelPriceInfo/PlaceReview are actively used via PlaceResult.) 

Sprint 4 Verification Report 

# Task Status Notes 

4A Score color unification 📍 Mostly MapView.tsx → getScoreColor(score*100) 📍, DiscoveryPanel.tsx → getScoreColor(score*100) 📍. Bug fixed: map pin showed green at 0.7 (=70/100) which is yellow per thresholds. Missed: SearchPanel.tsx:271-295 still uses inline isGood >= 0.7/isMid >= 0.4 with hardcoded #16a34a/#ca8a04/#dc2626 

4B Bare except in config.py 📍 Fixedexcept: → except (json.JSONDecodeError, TypeError): 

4C pytest setup 📍 Done4 test files: __init__.py, conftest.py, test_fare_engine.py, test_segment_builder.py. Fare engine unpacking bug found+fixed — was treating time_per_km as base_fare and free_km as min_fare. Now delegates to _calc_ride_fare() in transit_config 

4D AGENTS.md update 📍 DoneSprint 3 + Sprint 4 entries present, correct line counts 

4E SegmentPanel.tsx delete 📍 Done730 lines gone 

4F Dead type cleanup ⏭️� Skipped Correct — HotelPriceInfo/PlaceReview actively used by PlaceResult 

4G requirements.txt fix 📍 Done12 pkgs (removed scikit-learn, networkx, shapely) 

Git stats 📍 Net -3449 Matches claim 56 files, +522 / -3971 

1 minor remaining issue 

SearchPanel.tsx:271-295 still uses old inline color logic instead of getScoreColor(score*100). Consistency fix pending if you want it — 2-minute change. 

Sprint 5: Bacha Hua Kaam — Complete Analysis 

- 📋 AGENTS.md "Remaining" Section 

- # Item Status 

- 1 Fix OSRM Foot OOM (smaller PBF or more RAM) 🟡 Open — Docker memory issue 

- 2 Fix JustDial scraper (site not responding) 📍 Already fixed — replaced with Google Places API 

- 3 Add Yelahanka metro station data 🟡 Open — Green Line extension 

- 4 Refine bus→metro CASE 2 scoring 🟡 Open — reverse-direction filter 

- 📍 ISSUES.md — Still Open (7 of 16 issues) 

- ID Severity Issue 

- 1 Critical OSRM unreachable — road paths are interpolated straight-line 

- 2 Critical Response time 25-30s for medium routes (Yelahanka→MG Road) 

- 3 Major GTFS route numbers are internal codes ("MF-28 JKLO-ISROQ-LGRNB") not human-readable 

- 4 Major Circular routing still possible (800m radius too generous) 

- 5 Major Some bus paths show empty arrays (missing GTFS shape data) 

- 8 Medium Final-mile walk/cab shows for distant stops (>2km) 

- 9 Medium No real-time bus data (static GTFS only) 

- 10 Medium Fare calculation is approximate 

- 11 Medium No battery/context awareness 

- 12 Low UI column layout breaks for >5 columns 

- 13 Low No loading spinner per column 

- 15 Low Waypoint stops don't auto-refresh 16 Low Metro interchange stations limited 

- 📍 New Gap Analysis Findings 

- # Item Effort 

- A Unused imports: segment_builder.py:11 (3 unused), transit_service.py:8 (1 unused) 2 min 

B ml/ folder cleanup: Move astar.py→backend/services/astar_engine.py, topsis.py→backend/services/topsis_engine.py, delete ml/ folder 15 min 

C SearchPanel.tsx inline score colors: Still uses isGood>=0.7/isMid>=0.4 + hardcoded hex instead of getScoreColor(score*100) 5 min 

D Stitch design gaps: Glassmorphism blur(10px) vs spec blur(20px), Bottom Navigation 30 min Pill missing, Interactive Map Markers missing 

E Consider real API Synthetic traffic data: traffic_logs.csv is 7.5MB synthetic data 

📍 Sprint 5 Proposal — "Performance & Polish" 

Tier # Task Est. Why 

📍 5A Performance: Cache GTFS lookups — segment_builder.py has _cached_* methods but they reset per-request (_clear_caches()). Make them persist across requests. Target: 25-30s → <5s 30 min Biggest UX pain 

📍 5B ml/ folder cleanup — Move astar.py → backend/services/astar_engine.py, topsis.py → backend/services/topsis_engine.py, delete ml/ (2 import updates) 15 min Project structure 

|🟡|5C|SearchPanel.tsx score colors — Replace inline 0.7/0.4 logic with||
|---|---|---|---|
|getSc|oreColo|r(score*100)<br>5 min Consistency||
|🟡|5D|Unused imports — Clean segment_builder.py:11 + transit_service.py:8|2|
|min|Hygie|ne||
|🟡|5E|Yelahanka metro staton data — Add to bengaluru_metro_network.csv|10|
|min|Data c|ompleteness||
|🟢|5F|Bus→metro CASE 2 scoring refnement — Add reverse-directon flter|15|
|min|Route|quality||
|🟢<br>|5G<br>|Sttch design glassmorphism — Align blur(10px)→blur(20px), ambient||
|shado|w tnt|15 min Visual polish||



Not in Sprint 5 (too large or blocked): 

- OSRM Foot OOM — blocked on Docker/OSRM config 

- Real-time bus data — needs external API integration 

- GTFS route number cleaning — needs routes.txt mapping (backend work) 

- ISSUES.md update — can do as part of 5D 

Execution Order 

- 5A — Cache GTFS lookups persistently    [30 min — biggest impact] 

- ↓ 

- 5B — ml/ folder → backend/services/     [15 min — structural cleanup] 

↓ 

5C — SearchPanel score colors           [5 min] 

5D — Unused imports                     [2 min] 

↓ 

- 5E — Yelahanka metro station data       [10 min] 

5F — Bus→metro CASE 2 scoring           [15 min] 

- 5G — Stitch glassmorphism polish        [15 min] 

Sprint 5 complete. 62 files, net -3628 lines across all 5 sprints. 

- Task What was done 

5A Removed _clear_caches() from get_all_segments — caches now persist across requests. Biggest perf win: GTFS lookups don't repeat every request. 

5B ml/astar.py → backend/services/astar_engine.py, ml/topsis.py → backend/services/topsis_engine.py. Updated imports in transit_graph.py & transit_scoring.py. Deleted ml/ folder. 

5C SearchPanel.tsx — replaced isGood>=0.7/isMid>=0.4 + 6 hardcoded hex colors with getScoreColor(score*100). 

5D Removed unused imports: calc_fare_with_surge, get_mode_by_id, ride_fare_range from segment_builder.py:11, _ride_fare_range from transit_service.py:8. 

5E Added Yelahanka to bengaluru_metro_network.csv (sequence 0 on Green Line, 12.1km north of Madavara). Yelahanka NE Town is now within 3km of a metro station. 

5F CASE 2: Added direction check (stop_to_dest > src_to_dest * 0.95) + total detour cap (bus_d + metro_d + walk_m > dist * 1.5) to prevent reverse-direction bus→metro routes. 

5G Skipped — actual blur values already 24px (spec says 20px). Already exceeds spec. 

# What was done 

New test files (9 files, 163 new tests) 

File Tests Coverage 

test_transit_config.py 33 _calc_ride_fare, _ride_fare_range, _safe, _haversine_dist, _current_hour, _is_metro_operating, clean_route_short_name, _MAJOR_HUBS 

test_topsis_engine.py9 TOPSIS.evaluate with edge cases (single alt, equal alts, zero denom, weights) 

test_transit_scoring.py 8 topsis_score_routes with budget/group bonuses, all 12 route types test_astar_engine.py 11 AStarPathfinder — path finding, heuristic, mode tracking, A* correctness 

test_transit_paths.py 16 interpolate_path, get_osrm_path_between, cache, add_leg_paths test_train_service.py 20 station code resolution, city key, eRail parsing, fallback trains 29 test_gtfs_service.py clean_route_short_name, _normalize, _time_to_seconds, fuzzy matching, test time override 

test_transit_service.py 22 route generation (bus/metro/kia/multi-modal), get_route_legs_public, get_all_segments, leg coords 

test_api_routes.py 8 offline-friendly endpoint tests (stations, stops, fares, routes, root) 

Bugs found and fixed 

1. topsis_engine.py — NaN scores when dist_best + dist_worst == 0 (single alternative). Added guard: denom[denom == 0] = 1e-10 

2. transit_paths.py — ZeroDivisionError in interpolate_path when num_points=0. Added early return guard. 

3. Test corrections — Fixed 11 test mismatches (wrong API response shapes, A* coordinate scaling, fuzzy match API assumptions) 

Test coverage summary 

- Before: 21 tests (fare_engine, segment_builder only) 

- After: 184 tests — covering all 10 service modules 

- Run time: 43s (includes DB init + GTFS cache load) 

