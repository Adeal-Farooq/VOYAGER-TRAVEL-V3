# VOYAGER - Project Summary

## Architecture
- **Backend**: FastAPI (uvicorn) on port 8000
  - `backend/services/transit_service.py` — TransitService facade (~534 lines) composing segment_builder, graph, path, scoring, fare modules
  - `backend/services/transit_config.py` — constants (ride types, train data, hubs) and pure functions (geo math, GTFS helpers)
  - `backend/services/transit_graph.py` — TransitAstarGraph class (A* graph building, route finding)
  - `backend/services/transit_scoring.py` — topsis_score_routes() routing scoring (TOPSIS multi-criteria)
  - `backend/services/transit_paths.py` — TransitPathService class (OSRM path fetching, path interpolation)
  - `backend/services/segment_builder.py` — TripSegmentBuilder (1283 lines, multi-hop transit segment routing with GTFS, bus→metro→walk chaining)
  - `backend/services/fare_engine.py` — Centralized calc_fare_with_surge(), get_mode_by_id(), ride_fare_range()
  - `backend/services/gtfs_service.py` — BMTC GTFS data loader
  - `backend/core/database.py` — bus/metro/railway station data with spatial indexes
  - `backend/services/langgraph/` — LangGraph agent framework (VoyagerLangGraph with tool registry, intent detection, parallel execution)
  - `backend/services/scrapers/` — Real scrapers (ride_scraper, google_reviews_scraper, justdial_scraper, ddg_scraper)
  - `backend/services/clients/` — API clients (Google Maps, SerpAPI, weather, reddit)
  - `backend/agents/llm_agent.py` — LLMAgent singleton (OpenRouter/Gemini) for pricing, search, reviews, AI chat
  - `ml/astar.py` — A* transit graph pathfinder (used by transit_service)
  - `ml/topsis.py` — Proper numpy TOPSIS ranking (used by transit_service)
  - Local OSRM on port 5000 (car) — road-following paths

- **Frontend**: Vite + React/TS on port 3000
  - `src/context/AppContext.tsx` — Shared state via React Context
  - `src/pages/MainPage.tsx` — Orchestrator with sidebar + map layout
  - `src/components/SearchPanel.tsx` — Search nearby with category chips, radius slider
  - `src/components/AToBPanel.tsx` — Unified A→B planner (Public/Transport → Direct/Multi-Hop, Drive, Walk)
  - `src/components/DiscoveryPanel.tsx` — Right-side glass panel with scores, reviews, images
  - `src/components/MapView.tsx` — Leaflet map with colored markers, dynamic geometry
  - `src/components/TripPanel.tsx` — Trip planner with AI insights
  - `src/index.css` — Full design system (glassmorphism, colors, typography)

## API Endpoints
- `POST /api/routes/plan` — A→B route planning
- `GET /api/search/places|nearby|suggestions|verify-place|reviews|ride-prices|current-events|ai-chat`
- `POST /api/search/enrich-place`
- `POST /api/langgraph/ask` — LangGraph full reasoning loop
- `GET /api/routes/news|traffic-overlay|metro-stations|bus-stops|transit-fares|live-prices`

## Key Features
- **Glassmorphism design**: backdrop-filter blur, ambient shadows
- **Reliability scoring**: 0-100% green/yellow/red badges
- **AI review summaries**: Real Google Reviews (SerpAPI → proxy-scrape → fallback chain)
- **Real ride pricing**: Uber/Ola/Rapido via proxy scraping + SerpAPI + formula fallback
- **Real paths**: Local OSRM for actual road-following paths (car)
- **Multi-hop transit**: Bus + Metro + Train routes with A* graph-based routing
- **GPS live tracking**: "Start Journey" triggers watchPosition
- **TOPSIS ranking**: numpy-based multi-criteria decision analysis for route scoring
- **Live factors**: Weather (Open-Meteo), traffic news, crowd density, DL/NL/EV awareness

## Performance Profile (current)
- **GTFS cache load**: 0.65s (pickle deserialize 7271 shapes, 5077 stops, 429882 times)
- **Bus stop name pre-resolve**: 7.7s (2972 names; word-overlap index 0.17s / substring 0.69s / word-subset 1.72s / trigram-filtered get_close_matches 5.2s)
  - *First run only; `name_map` persisted in pickle cache for subsequent startups*
- **A* graph build**: 2.2s (2939 nodes, ~54000 edges; uses `_haversine_dist` + `_dist_cache` dict instead of `geodesic`)
- **Total server startup**: ~10.6s
- **API route planning**: <1s (all caches warm)
- **Pre-resolve cache**: 1696/2972 names resolved, stored in `gtfs_cache.pkl:name_map`
- **Known**: 14/2972 bus stop names have no GTFS match at all (e.g. acronyms like "hnrj", "ggmc", "pesitelc")

## Data Sources

## Docker Setup
- backend (port 8000), frontend (port 3000)
- osrm-car (port 5000) — driving routes **working**
- osrm-foot (port 5001) — walking routes **OOM-killed during customize**

## Running
```powershell
# Backend
cd VOYAGER
python -m uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend; npx vite --port 3000

# OSRM
docker compose up -d osrm-car
```

## Quality Assurance
- Tests: `pytest tests/ -q` (21 tests: test_fare_engine.py + test_segment_builder.py)
- Frontend: `npx tsc --noEmit` must pass with zero errors
- Backend: `python -c "from backend.services... import ..."` must compile cleanly

## Recent Fixes
- ✅ **GTFS route number cleaning** — `gtfs_service.py:clean_route_short_name()` strips terminal suffixes (e.g., "MF-28 JKLO-ISROQ-LGRNB" → "MF-28"), applied at both GTFS load time and CSV bus_stop source
- ✅ **Real reviews via SerpAPI** — `review_tools.py:get_place_reviews()` fixed broken SerpAPI flow (was calling `_parse_place_detail` on search response instead of using `search_places` → `place_id` → `place_details`); removed LLM fake review generation entirely
- ✅ **SerpAPI place_details key fix** — `serpapi_client.py:_parse_place_detail()` response key fixed from `"place"` to `"place_results"` (actual SerpAPI key); review data is in `place_results.user_reviews.most_relevant` (not `place_results.reviews` which is an int count); review fields are `username`/`description` (not `user.name`/`snippet`)
- ✅ **Real ride pricing** — `ride_scraper.py` and `transit_service.py:_RIDE_TYPES` both updated with Karnataka govt-mandated rates (Uber Go/Ola Mini ₹24/km, Uber XL ₹32/km, Auto ₹20/km, Rapido Bike ₹5/km) + first-N-km-free slab logic via `_calc_ride_fare()`; added SerpAPI directions engine fallback; `get_segment_step_options` bug fixed (undefined `ride_types`)
- ✅ **Ride fare per-person bug fixed** — `total = pp * group_size` was multiplying vehicle fare by passenger count; now `total = _calc_ride_fare(...)` (vehicle fare) and `pp = round(total / group_size)` (per-person share), matching how real cabs charge
- ✅ **transit_service.py refactored** — extracted module-level constants & pure functions (~209 lines) to `transit_config.py`; fixed critical `_gtfs` import-by-value bug that would have made all GTFS caches return empty
- ✅ **A* graph, TOPSIS, OSRM extracted** — `transit_graph.py` (TransitAstarGraph), `transit_scoring.py` (topsis_score_routes), `transit_paths.py` (TransitPathService) all extracted via composition; transit_service.py reduced from 2422 → 1917 lines
- ✅ **Name resolution performance (25-30s → <1s)** — replaced `geodesic` with `_haversine_dist` + `_dist_cache` in `transit_graph.py` (A* graph build: 11.6s → 2.2s); replaced SequenceMatcher loop with `get_close_matches` + trigram pre-filter in `gtfs_service.py:_fast_fuzzy_match` (pre-resolve: 79s → 7.7s); pre-normalized `_GTFS_NORM_NAMES` list avoids repeated `_normalize()` calls; A* graph pre-built at `TransitService.__init__` so first API request is instant
- ✅ **Metro direction filter too aggressive (Issue 9)** — removed `dest_to_dm > nm_dist_to_dest * 1.1` from `transit_service.py:1672`; valid metro routes (e.g., Cubbon Park→MG Road) now appear
- ✅ **Circular routing via 300m radius (Issue 10)** — `_is_visited()` radius increased 300m→800m in `transit_service.py:1494`
- ✅ **~55MB unused datasets deleted (Issue 11)** — 10 files removed: rides_data.csv, bangalore_ride_data.csv, metro_per_hour*.csv, NammaMetro_Ridership_Dataset.csv, 4×bangalore-wards-*.csv, KIA_stops_fare_incomplete.json, metro.csv
- ✅ **GTFS ~41s startup block (Issue 12)** — removed `_ensure_gtfs()` from `main.py`; `TransitService.__init__` defers graph build via lazy `astar_graph` property; server starts instantly
- ✅ **Live train data via eRail.in scraper (Issue 13)** — replaced hardcoded `_TRAIN_DATA` in `transit_config.py` with `train_service.py` scraping eRail.in API; 22 Karnataka station codes mapped; 7 city-pair fallbacks
- ✅ **SegmentPanel dark theme (Issue 14)** — all hardcoded dark colors (#0f172a, #1a2332, etc.) replaced with CSS variable references in `SegmentPanel.tsx`
- ✅ **bus_nan names filtered** — `database.py` skips stops with name `nan`/`none`/`null`
- ✅ **A* graph [:300] bus-metro walk limit removed** — `transit_graph.py` now adds walk edges for all 2933 bus stops (was limited to first 300); enables bus→metro transfers from any bus stop
- ✅ **Bus→metro CASE 2 (no metro near source)** — `transit_service.py` now searches ALL metro stations to find optimal bus→metro transfer when source has no nearby metro; picks best score (lowest bus_d+metro_d+walk_m); was using empty `metro_stations` (source-nearby list) instead of full `db.metro_stations`
- ✅ **Sprint 3 (Backend Refactoring)** — 52 files changed, net -2703 lines
  - `fare_engine.py` created (33 lines, centralized surge multiplier)
  - `segment_builder.py` created (1283 lines, 17 methods extracted from transit_service.py)
  - `transit_service.py` reduced from 1998→579 lines (delegates to segment_builder)
  - Dead code deleted: NewsOverlay.tsx, ml/data_preprocessor.py, 12 test/diag scripts, mini-path-options endpoint + frontend function, 5 dead types
  - requirements.txt cleaned (scikit-learn, networkx, shapely removed)
- ✅ **Sprint 4 (Testing & Polish)**
  - Score color unified: MapView.tsx, DiscoveryPanel.tsx now call getScoreColor(score*100) instead of inline 0.7/0.4 thresholds
  - Bare except in config.py fixed: `except:` → `except (json.JSONDecodeError, TypeError):`
  - pytest setup with test_fare_engine.py (~15 test cases) + test_segment_builder.py (~8 integration tests)
  - SegmentPanel.tsx deleted (zero imports, 730 lines dead)
- ✅ **Sprint 5 (Route fixes & hop improvements)**
  - **Walk as standalone transit hop** — `_add_transit_options()` now adds a `"walk"` transit option (≤2km, free) alongside bus/metro/train options; includes interpolated path, `transit_type: "walk"`, zero fare
  - **Metro→bus chaining** — metro options in `get_segment_step_options()` (bus stop→metro→dest) now include `_build_next_transit()` for onward transit from the arrival metro station
  - **GTFS name variant fallback** — `_cached_shape_path` falls back to stripping space-delimited suffix; `_cached_shape_between` uses `_resolve_name()` if first attempt returns nothing
  - **Search place coordinate verification** — `geocoding.py:search_places()` tightened Bangalore radius 50→15km, added ≥40% keyword overlap filter between query and result name/address
  - **Cache invalidation** — `review_tools.py` added `_CACHE_VERSION = 2` to cache key; all stale `reliability_score` entries from old `min(1.0, review_count/100)` formula are invalidated
  - **Always recompute `reliability_score` from rating** — `geocoding.py:_enrich_results()` never blindly trusts external `reliability_score`; always calls `_score_from_rating(rating)`
  - **Dead import removed** — `google_reviews_scraper` import removed from `review_tools.py` (unused)
  - Verified: 21/21 pytest pass, frontend `tsc --noEmit` zero errors, all backend modules compile

## Remaining
- Fix OSRM Foot OOM (smaller PBF or more RAM)
- Fix JustDial scraper (site not responding)
- Add Yelahanka metro station data (missing from bengaluru_metro_network.csv — Green Line extension)
- Refine bus→metro CASE 2 scoring to exclude clearly suboptimal reverse-direction routes (bus past destination then metro back)
