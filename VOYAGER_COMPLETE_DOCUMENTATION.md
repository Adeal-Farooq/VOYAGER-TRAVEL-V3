# VOYAGER — Complete Project Bible

> **Version**: 1.0.0  
> **Last Updated**: July 26, 2026  
> **Total Sprints Completed**: 4  
> **Status**: Active Development

---

## Table of Contents

1. [Project Overview & Vision](#1-project-overview--vision)
2. [Architecture & System Design](#2-architecture--system-design)
3. [Tech Stack & Why We Chose Each](#3-tech-stack--why-we-chose-each)
4. [Complete Sprint History](#4-complete-sprint-history)
5. [Directory Structure & Every File Explained](#5-directory-structure--every-file-explained)
6. [Backend Services Deep Dive](#6-backend-services-deep-dive)
7. [All API Endpoints Reference](#7-all-api-endpoints-reference)
8. [Frontend Components Deep Dive](#8-frontend-components-deep-dive)
9. [Data Sources & Their Structures](#9-data-sources--their-structures)
10. [Scrapers & External APIs](#10-scrapers--external-apis)
11. [Proxy Infrastructure](#11-proxy-infrastructure)
12. [Docker & OSRM Setup](#12-docker--osrm-setup)
13. [Performance Profile & Optimizations](#13-performance-profile--optimizations)
14. [All Bugs Fixed & Lessons Learned](#14-all-bugs-fixed--lessons-learned)
15. [Testing Infrastructure](#15-testing-infrastructure)
16. [Design System & UI](#16-design-system--ui)
17. [Environment Configuration](#17-environment-configuration)
18. [Future Roadmap & Plans](#18-future-roadmap--plans)
19. [Appendix A: Complete File Reference](#19-appendix-a-complete-file-reference)
20. [Appendix B: Fare Slab Tables](#20-appendix-b-fare-slab-tables)
21. [Appendix C: API Endpoint Quick Reference](#21-appendix-c-api-endpoint-quick-reference)

---

## 1. Project Overview & Vision

### 1.1 What Is VOYAGER?

VOYAGER is a **multi-modal transit navigation web application** purpose-built for **Bengaluru, India**. It combines real-time GTFS bus data, Namma Metro network data, Karnataka railway data, and ride-hailing price estimates to help users plan end-to-end journeys using any combination of:

- **Walking**
- **BMTC City Buses** (Ordinary, AC Vajra, KIA Airport Vayu Vajra)
- **Namma Metro** (Purple Line, Green Line, interchange at Majestic)
- **Indian Railways** (long-distance to Mysuru, Hubballi, Mangaluru, Belagavi, Ballari)
- **Ride-hailing** (Uber Go/Ola Mini, Uber XL/Ola XL, Auto, Rapido Bike/Uber Moto, Uber for Women, Uber Pet)
- **Personal Car** (with fuel cost estimation at ₹110/liter, 15 kmpl mileage)

### 1.2 Core Philosophy

The application follows **three core principles**:

1. **Real Data First** — Never generate fake data. Every route option, fare, review, and price comes from real sources (GTFS, Google Maps API, SerpAPI, Open-Meteo, eRail.in, Karnataka govt mandated rates). When a source fails, return empty — never fabricate.
2. **Progressive Discovery** — Instead of showing pre-computed end-to-end routes, let users discover step-by-step: walk→transit stop→transit→next transit→final mile. This mirrors how people actually plan transit journeys.
3. **Glassmorphism Design** — Modern, clean, translucent UI with backdrop blur, ambient shadows, and a cohesive color system defined by CSS variables.

### 1.3 Target Users

- **Daily commuters** in Bengaluru who use BMTC buses + Metro
- **Occasional travelers** who need point-to-point transit + ride-hailing comparisons
- **Tourists** visiting Bengaluru who need navigation assistance
- **Long-distance travelers** going to/from Mysuru, Hubballi, Mangaluru, etc.

### 1.4 Key Differentiators

| Feature | VOYAGER | Google Maps | Other Transit Apps |
|---------|---------|-------------|-------------------|
| GTFS-based bus routing | ✅ Yes | ✅ Yes | Partial |
| Metro + Bus chaining | ✅ Multi-hop A* | ✅ Yes | ✅ Yes |
| Real ride pricing (Uber/Ola/Rapido) | ✅ Formula + SerpAPI live | ❌ No | Only Uber |
| Genuine Google Reviews | ✅ SerpAPI → Google Places | ✅ Native | ❌ Fake/LLM |
| AI travel insights | ✅ OpenRouter LLM | ❌ No | ❌ No |
| Weather-aware routing | ✅ Open-Meteo | ❌ No | ❌ No |
| Multi-stop waypoints | ✅ Yes | ✅ Yes | ❌ No |
| Segment-by-segment exploration | ✅ Progressive columns | ❌ No | ❌ No |
| Traffic overlay | ✅ GeoJSON + synthetic data | ✅ Native | ✅ Some |
| Open source, self-hostable | ✅ Docker | ❌ Proprietary | Mixed |

### 1.5 Project Timeline

| Sprint | Focus | When | Net Line Change |
|--------|-------|------|----------------|
| Sprint 1 | Fake Data → Real Data | July 2026 | ~+1500 lines |
| Sprint 2 | Frontend Critical Bugs | July 2026 | ~+200 lines |
| Sprint 3 | Backend Refactoring | July 2026 | **-2703 lines** |
| Sprint 4 | Testing & Polish | July 2026 | **-3449 lines** |

---

## 2. Architecture & System Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React/TS)                     │
│                         Port 3000                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐   │
│  │Search    │ │AToB      │ │Trip      │ │Discovery      │   │
│  │Panel     │ │Panel     │ │Panel     │ │Panel          │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘   │
│       └────────────┴────────────┴───────────────┘            │
│                           │                                   │
│                    ┌──────┴──────┐                            │
│                    │  MapView    │  (Leaflet)                  │
│                    │  (Leaflet)  │                            │
│                    └──────┬──────┘                            │
└───────────────────────────┼──────────────────────────────────┘
                            │ HTTP/JSON (Fetch API)
                            │ /api/* → localhost:8000
┌───────────────────────────┼──────────────────────────────────┐
│                    ┌──────┴──────┐                            │
│                    │  FastAPI    │  Backend Port 8000          │
│                    │  (uvicorn)  │                            │
│                    └──────┬──────┘                            │
│                           │                                   │
│              ┌────────────┼────────────┐                      │
│              │            │            │                      │
│         ┌────┴───┐  ┌────┴───┐  ┌────┴────┐                  │
│         │Routes  │  │Search  │  │LangGraph │                  │
│         │API     │  │API     │  │Agent API │                  │
│         └────┬───┘  └────┬───┘  └────┬────┘                  │
│              │            │            │                       │
│         ┌────┴────────────┴────────────┴────┐                  │
│         │         TransitService            │                  │
│         │  (Orchestrator, ~534 lines)       │                  │
│         └────┬────────────┬────────────┬────┘                  │
│              │            │            │                       │
│    ┌─────────┴──┐  ┌──────┴──────┐  ┌─┴──────────────┐        │
│    │Segment    │  │Transit      │  │TransitAstar    │        │
│    │Builder    │  │Config       │  │Graph           │        │
│    │(1216 ln)  │  │(112 ln)     │  │(187 ln)        │        │
│    └─────┬─────┘  └──────┬──────┘  └───────┬────────┘        │
│          │               │                 │                  │
│    ┌─────┴─────┐  ┌──────┴──────┐  ┌───────┴────────┐        │
│    │Fare Engine│  │GTFS Service │  │AStar Engine    │        │
│    │(33 ln)    │  │(586 ln)     │  │(ml/astar move) │        │
│    └───────────┘  └─────────────┘  └────────────────┘        │
│                                                                │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│    │TransitPaths │  │TransitScoring│  │TransitDatabase   │   │
│    │(106 ln)     │  │(53 ln)       │  │(315 lines)       │   │
│    └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                                │
│    ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│    │Geocoding     │  │LLM Agent     │  │Train Service     │   │
│    │(477 ln)      │  │(329 ln)      │  │(174 ln)          │   │
│    └──────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────┴────┐          ┌────┴────┐          ┌─────┴─────┐
   │OSRM Car │          │OSRM Foot│          │External   │
   │Port 5000│          │Port 5001│          │APIs       │
   │Docker   │          │(OOM)    │          │SerpAPI,   │
   └─────────┘          └─────────┘          │GoogleMaps,│
                                             │Open-Meteo │
                                             │eRail.in   │
                                             └───────────┘
```

### 2.2 Data Flow: Route Planning

```
User enters source & dest in AToBPanel
  │
  ▼
POST /api/routes/plan
  ├── mode=transit:
  │     └── TransitService.get_route_legs_public()
  │           ├── A* graph (TransitAstarGraph.find_routes)
  │           ├── Route generators (bus, metro, multi-modal, KIA)
  │           ├── TOPSIS scoring (transit_scoring.topsis_score_routes)
  │           └── LLM: live prices, weather, recommendations
  │
  ├── mode=personal:
  │     └── OSRM driving route → fuel cost estimation
  │
  └── mode=walking:
        └── Haversine distance × 12 min/km

Results sorted by overall_score (descending)
Return top 6 routes with legs, paths, scores
```

### 2.3 Data Flow: Segment Building

```
Frontend calls GET /api/routes/all-segments
  │
  ▼
TransitService.get_all_segments(max_depth=3)
  ├── _clear_caches() — reset per-request caches
  ├── Segment 0: _build_single_segment(source, dest)
  │     ├── _add_direct_options()
  │     ├── find_nearby_bus_stops(2km)
  │     ├── find_nearby_metro_stations(3km)
  │     ├── find_nearby_railway_stations(15km)
  │     ├── For each stop (max 8 bus + 4 metro + 3 metro + 3 railway):
  │     │     ├── _add_reach_options() → walk/cab/auto/bike to stop
  │     │     └── _add_transit_options() → buses (GTFS), metro, train
  │     │           ├── GTFS: get_all_routes_at_stop()
  │     │           ├── GTFS: get_next_buses_with_times()
  │     │           ├── GTFS: find_stops_on_route_toward_dest()
  │     │           ├── GTFS: get_shape_path_for_route()
  │     │           ├── Metro: metro to dest metro station
  │     │           ├── Train: inter-city (if long dist)
  │     │           ├── Bus→metro chaining via _build_next_transit()
  │     │           └── Final mile: walk ≤2km, cab/bike ≥1km
  │     └── Collect transit options with next_segment_index
  │
  ├── Segments 1..N: _build_single_segment(arrival, dest)
  │     └── Same flow, dedup by arrival point
  │
  └── Return { source, dest, segments[], total_segments }
```

### 2.4 Architecture Decisions

| Decision | Choice | Alternative Considered | Why We Chose This |
|----------|--------|----------------------|-------------------|
| Backend Framework | FastAPI | Flask, Django | Async support for OSRM/LLM calls, built-in OpenAPI docs, Pydantic validation |
| Frontend Framework | React 18 + TS | Vue 3, Svelte | Largest ecosystem, Leaflet integration, TS type safety |
| Build Tool | Vite | CRA, Webpack | Faster HMR, better DX, native ESM |
| Mapping | Leaflet (react-leaflet) | Mapbox GL JS, Google Maps | Free, open-source, no API key needed for OSM tiles |
| HTTP Client (FE) | Axios | Fetch API | Interceptors, better error handling, request cancellation via AbortSignal |
| HTTP Client (BE) | httpx | requests, aiohttp | Async-native, connection pooling, timeout support |
| Distance Calc | Custom haversine | geopy.geodesic | 100x faster: 3.7ms vs 374ms for nearby stop search |
| Route Graph | Custom A* | networkx | Control over edge weights, mode tracking, 2939 nodes |
| Multi-Criteria Scoring | TOPSIS (numpy) | WEKA, manual weighted sum | Scientifically proven MCDM method, normalized scoring |
| LLM Provider | OpenRouter (GPT-4o-mini) | Direct OpenAI, Gemini | Fallback chain of 6 models, cost-effective |
| Transit Data | GTFS + CSVs + JSON | PostgreSQL + PostGIS | Simpler setup, in-memory is fast enough for 2972 stops |
| Caching | Pickle files | Redis, SQLite | Simple, fast (0.65s load), no external service needed |
| State Management | React Context (+ useState) | Redux, Zustand | Simple enough for current needs, no boilerplate |
| Proxy Management | Tiered proxy system | Single proxy | Free → DataImpulse → Direct fallback chain |
| Docker OSRM | ghcr.io/project-osrm/osrm-backend | GraphHopper, Valhalla | Standard, well-documented, MLD algorithm for fast routing |

---

## 3. Tech Stack & Why We Chose Each

### 3.1 Backend Technologies

#### FastAPI + uvicorn
- **Why**: Async support is critical for OSRM path fetching (20+ concurrent requests), LLM API calls, and weather data fetching
- **Port**: 8000
- **Key features used**: APIRouter for modular endpoints, Pydantic request validation, async route handlers, CORS middleware, automatic OpenAPI docs at /docs

#### httpx
- **Why**: Only mature async HTTP client for Python. Used in 18+ files across scrapers, API clients, and OSRM path fetching
- **Key features**: AsyncClient with connection pooling, timeout support, HTTP/2 support

#### Pandas + NumPy
- **Pandas**: Loading CSVs for metro network, bus stops, fare slabs (5+ files)
- **NumPy**: TOPSIS algorithm in ml/topsis.py (vectorized operations)

#### geopy (minimal use)
- **Why**: Only used in `transit_service.py:haversine_distance()` as a fallback geodesic calculator for edge cases
- **Replaced for**: Most distance calculations use custom `_haversine()` for 100x speed improvement

#### Pickle
- **Why**: Serialize GTFS cache (67MB) for fast loading (0.65s vs 41s full parse)
- **Cache file**: `data_cache/processed/gtfs_cache.pkl`
- **Contents**: shapes, stop_times, routes, name_map, etc.

#### LLM Agent (Custom)
- **Provider**: OpenRouter (primary), Gemini (fallback)
- **Model**: `openai/gpt-4o-mini` (primary), 5 fallback models
- **Purpose**: Live ride pricing, travel recommendations, weather impact, AI chat, current events
- **Key rule**: NEVER generates fake data. Returns []/None on failure.

### 3.2 Frontend Technologies

#### React 18 + TypeScript
- **Why**: Type safety prevents runtime errors, largest ecosystem for mapping libraries
- **Components**: 6 live components (SearchPanel, AToBPanel, TripPanel, DiscoveryPanel, MapView, MainPage)
- **Deleted**: SegmentPanel.tsx (730 lines, dead code), NewsOverlay.tsx (110 lines, dead code)

#### Vite
- **Why**: Lightning-fast HMR, native ESM, optimized builds
- **Port**: 3000
- **Proxy**: `/api` → `localhost:8000`

#### Leaflet (react-leaflet)
- **Why**: Free, no API key, mature ecosystem, lightweight
- **Features used**: MapContainer, TileLayer, Marker with divIcon, Polyline, Popup, CircleMarker

#### Axios
- **Why**: Interceptors, timeout handling, AbortSignal support (for search cancellation)
- **API base**: `/api` (proxied to backend)

#### React Context
- **Why**: Simple shared state without external dependencies
- **State shape**: mode, userLocation, mapCenter, sourceLocation, destLocation, selectedPlace, routeGeometry, tracking state, etc.

### 3.3 Infrastructure

#### Docker
- **Services**: backend (8000), frontend (3000), osrm-car (5000), osrm-foot (5001)
- **OSRM Foot**: Known OOM issue — needs more RAM or smaller PBF

#### OSRM (Open Source Routing Machine)
- **Car profile**: Working on port 5000 (Docker), uses MLD (Multi-Level Dijkstra) algorithm
- **Foot profile**: OOM during `osrm-customize` — 1.8GB southern-zone PBF too large for 2GB RAM
- **Data**: Southern-zone India PBF from Geofabrik (~1.8GB download)

#### Proxy System
- **Tier 1**: Free proxy lists (TheSpeedX, ShiftyTR, monosans) — rate-limited
- **Tier 2**: DataImpulse residential proxies ($5/5GB) — for IP-blocked sites
- **Tier 3**: Direct connection — for APIs (Reddit, Google Maps, SerpAPI)
- **Note**: DataImpulse requires `.env` config

---

## 4. Complete Sprint History

### 4.1 Sprint 1: Fake Data → Real Data (7 issues)

**Goal**: Replace all fake/LLM-generated data with real data from actual sources.

| # | Issue | Before | After | Files Changed |
|---|-------|--------|-------|-------------|
| 1A | `llm_agent.py` fake fallbacks | LLM generated fake reviews, prices, weather when APIs failed | Returns `[]` or `None` — no fabrication | `llm_agent.py` |
| 1B | Weather returning strings | Open-Meteo returned `"25.5"` (string) | Returns proper `float` values | `weather_client.py` |
| 1C | Google Reviews broken | SerpAPI flow was calling `_parse_place_detail` on search response (wrong method) | SerpAPI: `search_places` → `place_id` → `place_details` → `user_reviews.most_relevant` | `serpapi_client.py`, `review_tools.py` |
| 1D | JustDial scraper → Google Places API | JustDial blocked all httpx requests | Replaced with Google Places Text Search API | `justdial_scraper.py` |
| 1E | Ride pricing `is_live` flag | All rides showed `is_live: True` even though formula-based | Added `source: "estimated"`/`"serpapi"`, `is_live: True/False` flag | `ride_scraper.py`, `transit_service.py` |
| 1F | News → DDG site: search | News was fake/LLM-generated | DuckDuckGo `site:` search for actual traffic news | `news_scraper.py` |
| 1G | 30/42 bare except blocks logged | Silent `except: pass` everywhere | `logger.warning()` on 30 blocks; 11 remaining (controlled fallbacks) | Multiple files |

**Key lesson**: Never trust API responses — validate types, handle failures gracefully, never fabricate.

### 4.2 Sprint 2: Frontend Critical Bugs (7+ issues)

**Goal**: Fix broken frontend interactions discovered during integration testing.

| # | Issue | Before | After |
|---|-------|--------|-------|
| 2A | TransportType toggle not branching | `transportType` state existed but both 'direct' and 'segment' called same code | Direct → only `getRidePrices()`. Segment → `planRoute(mode:'public')` + ride prices |
| 2B | Route selection broke after state changes | Used `selectedRouteIdx` (index-based, unstable) | `getRouteKey()` — stable string-based comparison of route properties |
| 2C | Discovery "Navigate Here" used CustomEvent | `window.dispatchEvent(new CustomEvent(...))` — fragile | `onNavigate` prop passed from MainPage |
| 2D | TripPanel "Create New Trip" stayed on TripPanel | Clicking button did nothing | `setMode('atob')` — switches to A→B tab |
| 2E | SearchPanel used hardcoded center | `const centerLat = 12.9716` | `userLocation?.[0] ?? 12.9716` — uses GPS when available |
| 2F | MapView moveend listener had stale closure | `useEffect` depended on `[map, onCenterChange]` — re-created effect on every re-render | `useRef(cbRef)` stabilizes callback; effect depends on `[map]` only |
| 2G | Glass card + BEST badge | AToBPanel had no glass styling, SegmentPanel had hardcoded dark colors | Glass wrapper, CSS var conversion, "Best Match" badge |

**Bug found during verification**: `AToBPanel.tsx:148` deps array had `[selectedRouteIdx, ...]` — stale variable from rename (2B). Fixed in Sprint 3 Phase 1.

### 4.3 Sprint 3: Backend Refactoring (52 files, -2703 lines)

**Goal**: Break down the 1998-line `transit_service.py` monolith into focused, testable modules.

#### Phase 1: AToBPanel stale dep fix
- **File**: `frontend/src/components/AToBPanel.tsx:148`
- **Fix**: `selectedRouteIdx` → `selectedRouteKey`
- **Impact**: Route selection now triggers useEffect correctly, map geometry updates on click

#### Phase 2: fare_engine.py created
- **New file**: `backend/services/fare_engine.py` (33 lines)
- **Purpose**: Centralized surge multiplier — replaced 12x duplicated `fare_max = round(total * 1.35)` across transit_service.py
- **Functions**:
  - `calc_fare_with_surge(mode_data, distance_km)` → `(fare_min, fare_max)`
  - `get_mode_by_id(mode_id)` → ride type tuple or None
  - `ride_fare_range(mode_id, distance_km)` → convenience wrapper

#### Phase 3: segment_builder.py created
- **New file**: `backend/services/segment_builder.py` (1283 lines → 1216 lines after cleanup)
- **Class**: `TripSegmentBuilder`
- **Methods moved**: 17 methods from transit_service.py:
  - `get_all_segments()` — top-level orchestrator
  - `_build_single_segment()` — one segment builder
  - `_add_direct_options()` — walk/cab/auto/bike direct
  - `_add_reach_options()` — walk/cab/auto/bike to stop
  - `_add_transit_options()` — GTFS buses + metro + train from stop
  - `_build_next_transit()` — recursive chained transit builder
  - `_is_outside_bengaluru()` — distance from city center
  - `_is_hub_or_close_to_dest()` — major hub check
  - `_is_visited()` — circular routing prevention (800m radius)
  - `_coord_key()` — coordinate to string key
  - `_find_farthest_bus_stop_toward_dest()` — out-of-city helper
  - `4× _cached_*()` methods — GTFS route/shape/stop cache
  - `_clear_caches()` — per-request cache reset
  - `get_segment_step_options()` — legacy standalone builder (479 lines)

#### Phase 4: transit_service.py cleanup
- **After extraction**: 1998 → 534 lines
- **What remained**: 13 methods — __init__, haversine_distance, route generators (5 methods), get_route_legs_public, A* graph property, OSRM passthroughs (5 methods)

#### Phase 5: Dead code deletion
| Item | Lines | Reason |
|------|-------|--------|
| `NewsOverlay.tsx` | 110 | Zero imports — dead component |
| `ml/data_preprocessor.py` | 64 | Zero imports — superseded by GTFS loader |
| `scripts/test_*.py` (7 files) | ~200 | Test scripts — not used by CI |
| `_diag*.py`, `_debug*.py` (5 files) | ~250 | Diagnostic scripts |
| `scripts/migrate_to_postgres.py` | 120 | Not in use (app uses SQLite in-memory) |
| `getMiniPathOptions` in `api.ts` | 10 | Dead API function |
| `/mini-path-options` endpoint in `routes.py` | ~60 | Dead endpoint |
| 5 dead TS types | ~30 | `UserPreferences`, `MiniPathOptions`, `MiniPathSegment`, `BuiltRoute`, etc. |
| **TOTAL** | **~844 lines** | |

#### Phase 6: requirements.txt cleaned
- **Removed**: `shapely`, `scikit-learn`, `networkx` (3 packages, never imported)
- **Kept**: `openpyxl` (transitive pandas dep), `lxml` (BS4 parser), `python-dotenv` (implicit use by pydantic-settings)
- **Result**: 15 → 12 packages

### 4.4 Sprint 4: Testing & Polish (56 files, -3449 lines)

**Goal**: Add testing, fix score inconsistency, polish remaining issues.

#### 4A: Score Color Unification
- **Problem**: 4 different color functions with different thresholds:
  - `getScoreColor()`: 4 tiers (80/60/40 → green/yellow/orange/red)
  - `getPinColor()`: 3 tiers (80/60 → green/yellow/red) — no orange
  - `MapView.tsx` inline: 0-1 scale (0.7/0.4 → green/yellow/red)
  - `DiscoveryPanel.tsx` inline: Different hex values (#16a34a, #ca8a04, #dc2626)
- **Fix**: 
  - Deleted `getPinColor()` — unused
  - `MapView.tsx`: `score >= 0.7 ? green...` → `getScoreColor(score * 100)`
  - `DiscoveryPanel.tsx`: inline hex → `getScoreColor(score * 100)`
- **Bug found**: MapView was showing green at 0.7 (= 70/100), but `getScoreColor`'s green threshold is 80+. 70 should be yellow. Fixed.

#### 4B: Bare except fix
- **File**: `backend/core/config.py:55`
- **Fix**: `except:` → `except (json.JSONDecodeError, TypeError):`
- **Why**: Bare except catches `KeyboardInterrupt`, `SystemExit` — dangerous

#### 4C: pytest setup
- **New files**: `tests/__init__.py`, `tests/conftest.py`, `tests/test_fare_engine.py`, `tests/test_segment_builder.py`
- **Tests**: 12 in test_fare_engine, 9 in test_segment_builder — all passing
- **Bug found by tests**: `calc_fare_with_surge` tuple unpacking was wrong:
  - **Before**: `mode_id, label, per_km, base_fare, free_km, icon, seats, min_fare = mode_data`
  - **Actual tuple**: `(mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km)`
  - So `time_per_km` was being treated as `base_fare`, `base_fare` as `free_km`, `free_km` as `min_fare`
  - **Fix**: Corrected unpacking + delegated to `_calc_ride_fare()` in transit_config to avoid future mismatch

#### 4D: AGENTS.md updated
- Sprint 3 & Sprint 4 entries added
- Correct line counts for `transit_service.py` (534), `segment_builder.py` (1216), `fare_engine.py` (33)
- New files listed: `fare_engine.py`, `segment_builder.py`

#### 4E: SegmentPanel.tsx deleted
- **Why**: Zero imports across entire frontend. 730 lines of dead code.
- **What it contained**: Multi-column segment selection UI, card rendering, step navigation
- **Will not be restored**: Frontend routing flow changed to use per-segment API calls

#### 4F: Skipped (Hot el PriceInfo / PlaceReview)
- **Reason**: Both types are actively used via `PlaceResult` interface fields

#### 4G: requirements.txt cleanup
- **Removed**: `scikit-learn==1.3.2`, `networkx==3.2.1`, `shapely==2.0.2`
- **These packages**: Never directly imported in any `.py` file. Verified by grep.

### 4.5 Post-Sprint 4 Cleanup (ml/ folder migration)

- `ml/astar.py` → `backend/services/astar_engine.py`
- `ml/topsis.py` → `backend/services/topsis_engine.py`
- `ml/__init__.py` → deleted
- `ml/` folder → deleted
- Import updates: `transit_graph.py` and `transit_scoring.py` updated

---

## 5. Directory Structure & Every File Explained

```
VOYAGER/
├── AGENTS.md                          # Project summary, architecture, all fix history
├── ISSUES.md                          # Known issues tracker (16 tracked issues)
├── requirements.txt                   # Root requirements (12 packages)
├── docker-compose.yml                 # 4 services: backend, frontend, osrm-car, osrm-foot
├── Dockerfile.backend                 # Python 3.12, uvicorn
├── Dockerfile.frontend                # Node 20, Vite
├── start.ps1                          # Local dev launcher (2 PowerShell windows)
├── test_api.ps1                       # API test script
├── .env                               # API keys (NOT in repo)
├── .env.example                       # Template for .env
│
├── backend/
│   ├── main.py                        # FastAPI app entry: CORS, routers, startup init
│   ├── requirements.txt               # 12 pinned packages
│   │
│   ├── api/
│   │   ├── routes.py                  # 680 lines — ALL route-related endpoints
│   │   │   POST /api/routes/plan      # Main route planner
│   │   │   GET /api/routes/all-segments    # Segment builder
│   │   │   GET /api/routes/segment-step    # Legacy segment
│   │   │   GET /api/routes/metro-stations  # Metro data
│   │   │   GET /api/routes/bus-stops       # Bus stop data
│   │   │   GET /api/routes/kia-routes      # KIA routes
│   │   │   GET /api/routes/transit-fares   # Fare data
│   │   │   GET /api/routes/live-prices     # LLM pricing
│   │   │   GET /api/routes/news            # Travel news
│   │   │   GET /api/routes/traffic-overlay # Traffic GeoJSON
│   │   │
│   │   └── search.py                  # 104 lines — Search & LangGraph endpoints
│   │       GET /api/search/places, /nearby, /suggestions, /verify-place
│   │       GET /api/search/reviews, /ride-prices, /current-events
│   │       GET /api/search/ai-chat
│   │       POST /api/search/enrich-place
│   │       POST /api/langgraph/ask
│   │
│   ├── core/
│   │   ├── config.py                  # 56 lines — Settings class (API keys, OSRM, fuel)
│   │   ├── database.py                # 315 lines — TransitDatabase singleton
│   │   └── spatial_index.py           # Grid-based spatial index for fast nearby queries
│   │
│   ├── models/
│   │   └── transit.py                 # 102 lines — 13 Pydantic models
│   │
│   ├── services/
│   │   ├── __init__.py                # Empty package marker
│   │   │
│   │   │   === Core Transit Services ===
│   │   ├── transit_service.py         # 534 lines — Orchestrator (was 1998)
│   │   ├── transit_config.py          # 112 lines — Constants, pure functions, haversine
│   │   ├── transit_graph.py           # 187 lines — A* graph: 2939 nodes, 54000 edges
│   │   ├── transit_scoring.py         # 53 lines — TOPSIS scoring wrapper
│   │   ├── transit_paths.py           # 106 lines — OSRM path fetching + interpolation
│   │   ├── segment_builder.py         # 1216 lines — TripSegmentBuilder (17 methods)
│   │   ├── fare_engine.py             # 33 lines — Centralized fare + surge
│   │   ├── astar_engine.py            # Migrated from ml/astar.py — A* algorithm
│   │   ├── topsis_engine.py           # Migrated from ml/topsis.py — TOPSIS numpy
│   │   │
│   │   │   === Data Services ===
│   │   ├── gtfs_service.py            # 586 lines — GTFS loader + fuzzy name matching
│   │   ├── geocoding.py               # 477 lines — Place search, verify, enrich
│   │   ├── train_service.py           # 174 lines — eRail.in live train data
│   │   ├── images.py                  # 36 lines — Image processing
│   │   │
│   │   │   === Scrapers ===
│   │   ├── scrapers/
│   │   │   ├── ride_scraper.py        # 172 lines — Karnataka govt rates + SerpAPI
│   │   │   ├── google_reviews_scraper.py  # 146 lines — Google Reviews via Places API
│   │   │   ├── justdial_scraper.py    # 93 lines — Now Google Places API (replaced JD)
│   │   │   ├── news_scraper.py        # 64 lines — DuckDuckGo site:search
│   │   │   └── ddg_scraper.py         # 84 lines — DuckDuckGo generic scraper
│   │   │
│   │   │   === API Clients ===
│   │   ├── clients/
│   │   │   ├── serpapi_client.py      # 170 lines — SerpAPI search/place/details
│   │   │   ├── google_maps_client.py  # 89 lines — Google Places API wrapper
│   │   │   ├── weather_client.py      # 79 lines — Open-Meteo API
│   │   │   └── reddit_client.py       # 165 lines — Reddit API scraper
│   │   │
│   │   │   === LangGraph Agent ===
│   │   ├── langgraph/
│   │   │   ├── agent.py               # 329 lines — VoyagerLangGraph agent
│   │   │   ├── tools/
│   │   │   │   ├── search_tools.py    # 83 lines
│   │   │   │   ├── review_tools.py    # 111 lines
│   │   │   │   ├── geo_tools.py       # 83 lines
│   │   │   │   ├── weather_tools.py   # 11 lines
│   │   │   │   ├── pricing_tools.py   # 64 lines
│   │   │   │   └── news_tools.py      # 37 lines
│   │   │
│   │   ├── proxy_manager.py           # 98 lines — Tiered proxy (free → DataImpulse → direct)
│   │   └── agent.py (LLM Agent)       # 329 lines — OpenRouter/Gemini LLM singleton
│   │
│   ├── agents/
│   │   └── llm_agent.py               # 329 lines — LLMAgent: pricing, search, reviews, chat
│   │
│   └── migrations/                    # Database migrations (empty/unused)
│
├── data_cache/
│   ├── processed/
│   │   └── gtfs_cache.pkl             # 67MB — Pickled GTFS data
│   ├── bmtc_gtfs.zip                  # 47MB — Raw GTFS ZIP
│   ├── bmtc_all_stops_master.csv      # 2MB — 2972 stops with routes
│   ├── bengaluru_metro_network.csv    # 8KB — 26+ metro stations
│   ├── karnataka_railway_stations.json # 2.8KB — 50+ railway stations
│   ├── transit_fares.json             # 3.5KB — Fare slabs
│   ├── kia_routes_fare_full.json      # 22.6KB — KIA airport routes
│   └── traffic_logs.csv               # 7.5MB — Synthetic traffic data (445K rows)
│
├── frontend/
│   └── src/
│       ├── App.tsx                    # Root component with AppProvider
│       ├── main.tsx                   # React entry point
│       ├── index.css                  # 157 lines — Design system (CSS vars, glass, etc.)
│       │
│       ├── context/
│       │   └── AppContext.tsx          # 173 lines — React Context state
│       │
│       ├── components/
│       │   ├── SearchPanel.tsx        # 370 lines — Search + nearby
│       │   ├── AToBPanel.tsx          # 459 lines — Unified A→B planner
│       │   ├── DiscoveryPanel.tsx     # ~100 lines — Results glass panel
│       │   ├── TripPanel.tsx          # ~80 lines — Trip planner
│       │   ├── MapView.tsx            # 165 lines — Leaflet map
│       │   └── (SegmentPanel.tsx)     # DELETED — was 730 lines, dead
│       │   └── (NewsOverlay.tsx)       # DELETED — was 110 lines, dead
│       │
│       ├── pages/
│       │   └── MainPage.tsx           # 179 lines — App orchestrator
│       │
│       ├── services/
│       │   └── api.ts                 # 119 lines — API client (axios)
│       │
│       ├── types/
│       │   └── index.ts               # 228 lines — 20 TypeScript interfaces
│       │
│       └── utils/
│           └── helpers.ts             # 176 lines — Icons, formatting, score colors
│
├── tests/
│   ├── __init__.py                    # Package marker
│   ├── conftest.py                    # Pytest fixtures
│   ├── test_fare_engine.py            # 12 test cases
│   └── test_segment_builder.py        # 9 test cases
│
├── scripts/
│   └── setup_osrm.ps1                 # OSRM setup script
│
├── stitch_omnipath_ai_navigation/     # 10 design reference modules (HTML mockups)
│   ├── DESIGN.md                      # Design specification
│   └── wayfinder_*/                   # 9 modules with code.html + screen.png
│
├── docs/                              # Project documentation
├── images/                            # Screenshots
├── PROJECT_DETAILED_TILL_NOW.md       # Old documentation (pre-Sprint 3)
├── PROJECT_DOCUMENTATION.md           # Auto-generated docs
├── VOYAGER_COMPLETE_DOCUMENTATION.md  # THIS FILE
│
├── osrm-data/                         # OSRM car data (PBF + processed)
└── osrm-data-foot/                    # OSRM foot data (incomplete — OOM)
```

---

## 6. Backend Services Deep Dive

### 6.1 transit_service.py (534 lines) — Orchestrator

**Location**: `backend/services/transit_service.py`
**Role**: Central orchestrator for all routing logic. After Sprint 3 extraction, this file only contains:
- Entry points for route planning (public, personal, walking modes)
- Route generation (bus, metro, metro_interchange, KIA, multi_modal)
- A* graph property (lazy-loaded on first request)
- OSRM passthrough methods (5 thin wrappers)
- Legacy `get_mini_path_options()` (172 lines)

**Methods remaining**:

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__` | 6 | Init `path_service` + `segment_builder` |
| `haversine_distance` | 7 | geodesic wrapper (used only here now) |
| `_find_common_routes` | 5 | Common routes between 2 bus stops |
| `_add_leg_coords` | 21 | Add coordinate paths to route legs |
| `get_route_legs_public` | 28 | Top-level: A* + TOPSIS + weather/pricing |
| `_get_bus_route_nums` | 3 | Extract route numbers from stop |
| `_generate_bus_routes` | 87 | Walk → bus → walk route generation |
| `_generate_metro_routes` | 49 | Walk → metro → walk |
| `_generate_metro_interchange_routes` | 125 | Metro with line change at interchanges |
| `_generate_kia_routes` | 51 | KIA Vayu Vajra airport buses |
| `_generate_multi_modal_routes` | 136 | Bus → Metro and Metro → Bus |
| `get_mini_path_options` | 172 | Legacy lightweight path options |
| `_interpolate_path` | 2 | Passthrough to path_service |
| 5× OSRM methods | 10 | Async path passthroughs |
| `astar_graph` property | 6 | Lazy A* graph initializer |

**Dependencies**:
- `backend.core.database.db` — all transit data
- `backend.services.segment_builder.TripSegmentBuilder` — segment building
- `backend.services.transit_config.*` — constants, fare calcs
- `backend.services.transit_paths.TransitPathService` — OSRM

### 6.2 segment_builder.py (1216 lines) — TripSegmentBuilder

**Location**: `backend/services/segment_builder.py`
**Role**: Builds progressive segments for the multi-hop transit explorer. This is the most complex module.

**Class**: `TripSegmentBuilder`
- Constructor takes: `haversine_fn`, `interpolate_path_fn`, `path_service`
- Maintains per-request instance caches: `_gtfs_route_cache`, `_shape_cache`, `_stops_toward_cache`, `_shape_between_cache`

**17 methods:**

| Method | Lines | Complexity | Description |
|--------|-------|-----------|-------------|
| `_is_outside_bengaluru` | 4 | Low | Distance >35km from center |
| `_find_farthest_bus_stop_toward_dest` | 20 | Low | For out-of-city routes |
| `get_segment_step_options` | 479 | **High** | Legacy standalone builder |
| `_add_direct_options` | 34 | Low | Walk/cab/auto/bike A→B |
| `_add_reach_options` | 40 | Low | Walk/cab/auto/bike to a stop |
| `_add_transit_options` | 281 | **High** | GTFS buses + metro + train from stop |
| `_build_next_transit` | 156 | **High** | Recursive chained transit builder |
| `_build_single_segment` | 111 | Medium | One segment orchestrator |
| `_is_hub_or_close_to_dest` | 5 | Low | Major hub check |
| `get_all_segments` | 69 | Medium | Top-level orchestrator (up to 4 segments) |
| `_coord_key` | 2 | Low | Lat/lng → string key |
| `_is_visited` | 11 | Low | Circular routing prevention |
| `_cached_gtfs_routes` | 8 | Low | Cached GTFS route lookup |
| `_cached_shape_path` | 8 | Low | Cached shape path lookup |
| `_cached_stops_toward` | 8 | Low | Cached stops-toward-destination lookup |
| `_cached_shape_between` | 8 | Low | Cached shape-between-stops lookup |
| `_clear_caches` | 4 | Low | Reset all caches per request |

**Nested functions within methods**:
- `_relevance_score(topt)` — inside `_add_transit_options` — scores transit options
- `_add_final_walk(...)` — inside `_build_next_transit` — adds walk final-mile
- `_make_bus_transit(...)` — inside `_build_next_transit` — creates bus transit hop
- `_dest_score(de)` — inside `_build_single_segment` — scores destination stops

**Data flow within `_add_transit_options()`**:

```
For each destination stop:
  if stop type is bus:
    Get all GTFS routes at this stop (max 8)
      For each route:
        Get shape path
        Find stops on route toward destination
        Calculate distance, fare
        Add bus_ordinary + bus_ac_vajra options
        Check metro at arrival → _build_next_transit()
        Add final_options (walk/ride to dest)

  if stop type is metro:
    Get destination metro station
    Calculate metro fare
    Get metro line path
    Add metro transit option
    Add final_options

  if long distance & stop type is railway:
    Get train options via _get_train_options()
    Add train transit option
```

**Recursive nature of `_build_next_transit()`**:
- Called when a bus arrives at a stop that has a nearby metro station
- Creates a metro "next transit" option from bus arrival to destination metro
- Can recurse: bus → metro → bus → metro (up to depth 2)
- Each level checks `_is_visited()` to prevent circular routing

### 6.3 transit_config.py (112 lines) — Constants & Pure Functions

**Location**: `backend/services/transit_config.py`
**Role**: All module-level constants, ride types, fare functions, helper functions.

**Key constants**:

```python
_RIDE_TYPES = [
    ("cab", "Uber Go / Ola Mini", 12, 3, 25, "🚕", 4, 0),
    #  (mode_id,  label,                per_km, time_per_km, base_fare, icon, seats, free_km)
    ("cab_sedan", "Uber Go Priority / Ola Prime", 24, 3, 50, "🚙", 4, 0),
    ("cab_xl", "Uber XL / Ola XL", 30, 3, 100, "🚐", 6, 0),
    ("auto", "Auto", 9, 5, 15, "🛺", 3, 0),
    ("bike", "Uber Moto / Rapido", 5, 2, 10, "🏍️", 1, 0),
    ("cab_women", "Uber for Women / Ola for Women", 12, 3, 25, "👩", 4, 0),
    ("cab_pet", "Uber Pet / Premier", 18, 3, 50, "🐾", 4, 0),
]
```

**IMPORTANT**: The tuple structure is `(mode_id, label, per_km_rate, time_per_km, base_fare, icon, capacity, free_km)`. The `fare_engine.py` tuple unpacking bug (Sprint 4C) was discovered where it was treating `time_per_km` as `base_fare` and `free_km` as `min_fare`. Fixed by delegating to `_calc_ride_fare()`.

**Key functions**:

| Function | Purpose | Parameters |
|----------|---------|-----------|
| `_ensure_gtfs()` | Lazy-load GTFS data (global singleton) | None |
| `_calc_ride_fare(dist, base, per_km, free_km)` | Calculate ride fare | distance, base fare, per-km rate, free km |
| `_ride_fare_range(dist, base, per_km, free_km)` | Fare range (min, max with 35% surge) | Same as above |
| `_get_train_options(src, dst)` | Get train options (live via eRail.in) | Source/dest station names |
| `_safe(val, default=0.0)` | NaN/None guard | Value, default |
| `_current_hour()` | Current hour (respects test time) | None |
| `_is_metro_operating()` | Metro operating hours check | None (5AM-11PM) |
| `_haversine_dist(lat1, lng1, lat2, lng2)` | Haversine distance | 4 coordinates |
| `_route_goes_toward_dest(shape, ...)` | Direction check via cosine angle | Shape path, coords |
| `_gtfs_buses_at_stop(stop_name)` | Get GTFS buses for a stop | Stop name |
| `_has_gtfs_route(stop_name)` | Check if stop has GTFS data | Stop name |

**Major hubs list** (`_MAJOR_HUBS`):
```
majestic, kempegowda bus station, kr market, kbs, shivajinagara,
shivajinagar, banashankari, jayanagara, k.r. market, city market,
platform 10-14
```

### 6.4 transit_graph.py (187 lines) — TransitAstarGraph

**Location**: `backend/services/transit_graph.py`
**Role**: Builds and queries the A* transit graph.

**Graph sizes**:
- Nodes: 2,939 (metro stations + bus stops)
- Edges: ~54,000
  - Metro-to-metro (same line): all pairs within 50km
  - Bus-to-bus (same GTFS route): sequential stops
  - Bus-to-metro walk edges (within 1.5km)
  - Bus-to-bus walk edges (within 500m, different routes)

**Graph structure**:
```python
self.astar.graph = {
    "metro_Mahatma Gandhi Road": [
        ("metro_Trinity", 1.2, "metro"),
        ("metro_Cubbon Park", 0.8, "metro"),
        ("bus_MG Road Metro Station", 0.3, "walk"),
    ],
    "bus_MG Road Metro Station": [
        ("bus_indian express", 1.5, "bus"),
        ("bus_maniksha parade ground", 2.1, "bus"),
        ("metro_Mahatma Gandhi Road", 0.3, "walk"),
        ("bus_shivajinagar bus station", 1.8, "bus"),
    ],
}
```

**Key methods**:

| Method | Purpose |
|--------|---------|
| `build_graph()` | One-time graph construction |
| `find_routes(slat, slng, dlat, dlng, dist, group_size)` | Find A* paths between source/dest |

**`find_routes()` flow**:
1. Find nearby bus stops (1km) + metro (2km) at source
2. Find nearby bus stops (1km) + metro (2km) at destination
3. For each source→destination node pair:
   - `astar.find_path()` — A* shortest path
   - `astar.find_path_with_modes()` — path with mode labels
4. Calculate total fare using db fare functions
5. Build route legs with durations
6. Classify as `metro_astar` or `multi_modal_astar`

**Performance**: Graph build ~2.2s (uses `_haversine_dist` + `_dist_cache` dict instead of `geodesic`)

### 6.5 transit_scoring.py (53 lines) — TOPSIS Score Wrapper

**Location**: `backend/services/transit_scoring.py`
**Role**: Applies TOPSIS multi-criteria scoring to route options.

**Comfort map**:
```python
metro_interchange: 5, metro: 5, bus_ac_vajra: 4, kia_bus: 4,
bus_ordinary: 2, bus_to_metro: 4, metro_to_bus: 3, car: 5, cab: 4, walk: 1,
metro_astar: 5, multi_modal_astar: 4
```

**Safety map**:
```python
metro_interchange: 5, metro: 5, bus_ac_vajra: 4, kia_bus: 4,
bus_ordinary: 3, bus_to_metro: 4, metro_to_bus: 3, car: 5, cab: 4, walk: 3,
metro_astar: 5, multi_modal_astar: 4
```

**Scoring flow**:
1. Build alternatives from routes (fare, duration, comfort, safety, walking, weather)
2. Call `topsis.evaluate(alternatives)` — numpy TOPSIS
3. Map TOPSIS score (0-1) → 10-99 range
4. Apply budget ratio adjustments:
   - fare/budget ≤ 0.4: +10
   - fare/budget ≤ 0.7: +5
   - fare/budget > 1.0: -15
   - fare/budget > 0.9: -5
5. Apply group size bonus: per_person ≤ 30: +5
6. Clamp: `max(10, min(99, raw_score))`

### 6.6 transit_paths.py (106 lines) — TransitPathService

**Location**: `backend/services/transit_paths.py`
**Role**: OSRM path fetching with caching, timeouts, and interpolation fallback.

**Methods**:

| Method | Purpose |
|--------|---------|
| `get_osrm_path_between(lat1, lng1, lat2, lng2, profile)` | Fetch OSRM path (car/walking) |
| `interpolate_path(lat1, lng1, lat2, lng2, steps)` | Straight-line fallback with bulge |
| `add_leg_paths(route)` | Enrich all route legs with OSRM paths |
| `get_osrm_route(lat1, lng1, lat2, lng2, profile)` | Full OSRM route object |

**OSRM configuration**:
- Car URL: `http://localhost:5000` (Docker) or `https://router.project-osrm.org` (fallback)
- Walking URL: `http://localhost:5001` (Docker — OOM)
- Per-request timeout: 3s
- Semaphore: 15 concurrent requests (in routes.py)
- Batch timeout: 20s (in routes.py)

**Interpolation fallback**: When OSRM fails, generates `n` points along a straight line with a slight bulge (perpendicular offset) to simulate curvature rather than showing a dead-straight line.

### 6.7 fare_engine.py (33 lines) — Centralized Fare Logic

**Location**: `backend/services/fare_engine.py`
**Role**: Single source of truth for ride fare calculation with surge multiplier.

**Why created**: The pattern `fare_max = round(total * 1.35)` was duplicated 12 times across transit_service.py. If the surge multiplier needed to change, all 12 locations had to be updated.

**Functions**:
- `calc_fare_with_surge(mode_data, distance_km)` → `(fare_min, fare_max)`
- `get_mode_by_id(mode_id)` → ride type tuple or None
- `ride_fare_range(mode_id, distance_km)` → convenience wrapper

**Bug history**: The original tuple unpacking was wrong:
```python
# WAS: mode_id, label, per_km, base_fare, free_km, icon, seats, min_fare = mode_data
# ACTUAL STRUCTURE: (mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km)
# FIX: mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km = mode_data
#     total = _calc_ride_fare(distance_km, base_fare, per_km, free_km)
```

### 6.8 gtfs_service.py (586 lines) — GTFS Data Loader

**Location**: `backend/services/gtfs_service.py`
**Role**: Load, cache, and query BMTC GTFS data.

**Data loaded**:
- 7,915 shapes (GPS paths)
- 5,077 unique stop names
- 56,732 trips
- 4,359 routes
- 1,500,000+ stop_times rows

**GTFS file structure**:
```
bmtc_gtfs.zip
├── shapes.txt        — shape_id, lat, lng, sequence → _shapes dict
├── stops.txt         — stop_id, name, lat, lng → _stops_by_name dict
├── trips.txt         — trip_id, route_id, shape_id → _trip_shape_map, _trip_to_route
├── routes.txt        — route_id, route_short_name → _route_id_to_name
└── stop_times.txt    — trip_id, arrival/departure, stop_id → _stop_times, _stop_times_by_route
```

**Key internal data structures**:
- `_shapes`: `{shape_id: [(lat, lng, seq), ...]}` — sorted by sequence
- `_stops_by_name`: `{"stop name": (lat, lng, stop_id)}` — 5077 entries
- `_stop_times`: `{"stop name": [(departure_time, route_short_name), ...]}` — max 200/stop
- `_stop_times_by_route`: `{"route_short_name": [(departure_time, stop_name), ...]}` — max 500/route
- `_stop_to_shapes`: `{"stop name": [(shape_id, sequence), ...]}`
- `_route_shapes`: `{"route_short_name": [shape_id, ...]}`
- `_name_map`: `{"query": "resolved_name"}` — fuzzy match cache

**Fuzzy name resolution (6 strategies)**:
1. Exact lowercase match
2. Cached match from `_name_map`
3. SequenceMatcher fuzzy (cutoff 0.55, substring bonus 0.9)
4. Normalized exact (remove punctuation)
5. Word subset (≥2 words in common)
6. Substring fallback

**Route number cleaning** (`clean_route_short_name`):
- Strips terminal suffixes: `"MF-28 JKLO-ISROQ-LGRNB"` → `"MF-28"`
- Applied at both GTFS load time and CSV bus_stop source

### 6.9 geocoding.py (477 lines) — Search & Geocoding

**Location**: `backend/services/geocoding.py`
**Role**: Place search, verification, enrichment, and suggestions.

**Data sources used (in order)**:
1. Google Places API (primary — Text Search)
2. OpenStreetMap Nominatim (fallback)
3. Local database (bus stops, metro stations, railway stations)

**Search flow**:
1. Check `SearchCache` (TTL: 24 hours)
2. Try Google Places Text Search API
3. If fails → OSM Nominatim
4. Merge with local DB results
5. Enrich with `image_service` (photos)
6. Enrich with `llm_agent` (review summary, reliability score)
7. Cache result

**Key methods**:
- `search_places(query, lat, lng)` — General place search
- `get_nearby_places(lat, lng, radius, place_type)` — Nearby search
- `get_suggestions(query)` — Autocomplete suggestions
- `verify_place(name, address)` — Verify place existence + reliability score
- `enrich_single_place(name, lat, lng, type, address)` — Full enrichment with images, reviews, pricing

### 6.10 train_service.py (174 lines) — Live Train Data

**Location**: `backend/services/train_service.py`
**Role**: Live train schedule scraping via eRail.in API.

**Station codes** (22 Karnataka stations mapped):
```python
"SBC": "KSR Bengaluru", "MYS": "Mysuru Junction", "UBL": "Hubballi Junction",
"MAQ": "Mangaluru Central", "BGM": "Belagavi", "BAY": "Ballari Junction",
"YPR": "Yesvantpur Junction", "SMET": "Shivamogga Town", "MRJN": "Marmagao",
"CLR": "Chittoor", "KPD": "Kadapa", "PAK": "Pakala", "KRNR": "Karanur",
"TAL": "Tumakuru", "ASK": "Arsikere", "DVG": "Davangere", "HRR": "Harihar",
"CT": "Chikjajur", "JRU": "Chitradurga", "RRB": "Birur", "RRGA": "Rayadurga",
"MYS": "Mysuru"  # duplicate — maps to same
```

**7 hardcoded city-pair fallbacks** (when eRail.in fails):
- Bengaluru ↔ Mysuru (5 trains each way)
- Bengaluru ↔ Hubballi (2 trains)
- Bengaluru ↔ Mangaluru (2 trains)
- Bengaluru ↔ Belagavi (1 train)
- Bengaluru ↔ Ballari (1 train)

### 6.11 astar_engine.py (migrated from ml/astar.py)

**Location**: `backend/services/astar_engine.py`
**Role**: Generic A* pathfinding algorithm. The algorithmic core used by `TransitAstarGraph`.

**Key classes/methods**:
- `AStarPathfinder.graph` — adjacency dict: `{node_id: [(neighbor_id, distance, mode), ...]}`
- `find_path(from_node, to_node, node_coords)` — A* search with haversine heuristic
- `find_path_with_modes(from_node, to_node, node_coords)` — Path with mode annotations per step

**Why separate from transit_graph.py**: transit_graph.py handles graph *construction* (domain logic: which stops connect, when to add walk edges). astar_engine.py handles the pure *search algorithm*.

### 6.12 topsis_engine.py (migrated from ml/topsis.py)

**Location**: `backend/services/topsis_engine.py`
**Role**: Numpy-based TOPSIS (Technique for Order Preference by Similarity to Ideal Solution).

**Scoring criteria**:
- `total_fare` (lower is better)
- `total_duration_minutes` (lower is better)
- `comfort` (higher is better) — 1-5 scale
- `safety` (higher is better) — 1-5 scale
- `total_walking_km` (lower is better)
- `overall_score` (higher is better)
- `weather_impact` (lower is better)

**Algorithm**:
1. Normalize decision matrix (vector normalization)
2. Apply weights: fare 25%, duration 30%, walking 15%, comfort 20%, safety 10%
3. Find ideal best and ideal worst
4. Calculate separation from ideal best/worst
5. Calculate relative closeness (TOPSIS score)

---

## 7. All API Endpoints Reference

### 7.1 Route Planning Endpoints

#### POST `/api/routes/plan`
**Purpose**: Main route planner. Returns scored multi-modal route options.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_lat` | float | — | Source latitude |
| `source_lng` | float | — | Source longitude |
| `dest_lat` | float | — | Destination latitude |
| `dest_lng` | float | — | Destination longitude |
| `mode` | string | `"transit"` | `"transit"`, `"personal"`, `"walking"` |
| `budget` | float? | null | Max fare per person |
| `group_size` | int | 1 | Number of passengers |
| `waypoints` | array | [] | Multi-stop waypoints |

**Response**:
```json
{
  "status": "success",
  "source": {"lat": 12.9755, "lng": 77.6068, "name": "MG Road"},
  "destination": {"lat": 12.9768, "lng": 77.5712, "name": "Majestic"},
  "routes": [
    {
      "type": "car",
      "total_fare": 85.33,
      "total_duration_minutes": 15,
      "total_distance_km": 5.2,
      "total_walking_km": 0,
      "overall_score": 85,
      "score_explanation": "direct drive - no transfers | rain: car/cab +5",
      "geometry": {"type": "LineString", "coordinates": [...]},
      "legs": [{"from": "...", "to": "...", "mode": "car", ...}]
    }
  ],
  "total_options": 6,
  "recommendations": {"tips": [...], "best_option": "..."},
  "weather": {"condition": "clear", "temperature": 28}
}
```

**Performance**: <1s (warm), 2-5s (cold GTFS load)

#### GET `/api/routes/all-segments`
**Purpose**: Progressive segment building for multi-hop transit explorer.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `from_lat` | float | — | Source latitude |
| `from_lng` | float | — | Source longitude |
| `from_name` | string | "Your Location" | Source name |
| `dest_lat` | float | — | Dest latitude |
| `dest_lng` | float | — | Dest longitude |
| `dest_name` | string | "Destination" | Dest name |
| `group_size` | int | 1 | Passengers |
| `budget` | float? | null | Max per person |
| `max_depth` | int | 3 | Max segment chain depth |

**Response**: Nested segment structure (see Section 8.3 for full example)

**Performance**: ~20-35s (warm) — OSRM path fetching is the bottleneck

**Processing that happens in this endpoint**:
1. Build segments via `TripSegmentBuilder.get_all_segments()`
2. Fire LLM live pricing concurrently (8s timeout)
3. Check OSRM health (Docker car + foot)
4. Batch-fetch OSRM paths (semaphore 15, gather timeout 20s)
5. Apply live prices from LLM
6. Interpolation fallback for options still missing paths
7. Strip internal keys from response

#### GET `/api/routes/segment-step`
**Purpose**: Legacy single-step segment options (maintained for backward compatibility).

#### GET `/api/routes/mini-path-options` **(DELETED)**
**Why deleted**: Dead endpoint. Frontend never called it. Removed in Sprint 3 Phase 5.

### 7.2 Transit Data Endpoints

#### GET `/api/routes/metro-stations`
**Parameters**: `line` (optional) — filter by line name
**Response**: `{status, stations, lines[]}`

#### GET `/api/routes/bus-stops`
**Parameters**: `near_lat`, `near_lng`, `radius` (optional) — location filter
**Response**: `{status, stops[]}`

#### GET `/api/routes/kia-routes`
**Response**: `{status, routes}` — All KIA Vayu Vajra airport routes

#### GET `/api/routes/transit-fares`
**Response**: `{status, fares}` — Fare slab data (BMTC ordinary, AC, Metro)

### 7.3 Live Data Endpoints

#### GET `/api/routes/live-prices`
**Parameters**: `source`, `dest`, `mode`
**Response**: `{status, prices[]}` — LLM-generated ride prices with provider, fare, ETA

#### GET `/api/routes/news`
**Parameters**: `source_lat`, `source_lng`, `dest_lat`, `dest_lng`, `source_name`, `dest_name`
**Response**: `{status, news[]}` — Travel news via DuckDuckGo search

#### GET `/api/routes/traffic-overlay`
**Parameters**: `north`, `south`, `east`, `west` (bounding box)
**Response**: GeoJSON FeatureCollection with road colors by congestion level

**Traffic logic**:
- Loads synthetic traffic speeds from `data_cache/traffic_logs.csv` (445K rows)
- Determines peak/off-peak based on current hour (8-10AM, 5-8PM = peak)
- Congestion levels: heavy (<15 km/h), moderate (15-30), light (>30)
- Road colors: heavy=red, moderate=amber, light=green
- Peak hour darkening for major roads (motorway, trunk, primary, secondary)

### 7.4 Search Endpoints

#### GET `/api/search/places`
**Parameters**: `q`, `lat?`, `lng?`
**Response**: `{status, results[], total}`

#### GET `/api/search/nearby`
**Parameters**: `lat`, `lng`, `radius_km`, `place_type?`
**Response**: `{status, center, radius_km, results[], total}`

#### GET `/api/search/suggestions`
**Parameters**: `q` (≥2 chars)
**Response**: `{status, suggestions[]}`

#### GET `/api/search/verify-place`
**Parameters**: `name`, `address?`
**Response**: `{status, place, verification}`

#### GET `/api/search/reviews`
**Parameters**: `name`, `address?`
**Response**: `{status, place, reviews[]}` — Via SerpAPI → Google Places API chain

#### GET `/api/search/ai-chat`
**Parameters**: `message`, `lat?`, `lng?`
**Response**: `{status, response}` — LLM-powered chat with travel context

#### GET `/api/search/ride-prices`
**Parameters**: `source`, `destination`
**Response**: `{status, source, destination, prices[]}`

#### GET `/api/search/current-events`
**Parameters**: `location` (default: "Bengaluru")
**Response**: `{status, location, events}`

#### POST `/api/search/enrich-place`
**Body**: `{name, lat, lng, place_type, address}`
**Response**: `{status, place}` — Full place enrichment with images, reviews, pricing

### 7.5 LangGraph Endpoint

#### POST `/api/langgraph/ask`
**Body**: `{query, context}`
**Response**: `{status, result}` — Full LangGraph agent reasoning loop

### 7.6 Health Endpoints

#### GET `/`
**Response**: `{app, version, status, data}` — Root with data stats

#### GET `/health`
**Response**: `{status, database_initialized}`

---

## 8. Frontend Components Deep Dive

### 8.1 MainPage.tsx (179 lines) — App Orchestrator

**Role**: Root layout component with sidebar + map.

**State management**: All state via `AppContext` (173 lines)

**Children components**:
- Sidebar (420px): Shows one of SearchPanel / AToBPanel / TripPanel based on `mode`
- MapView: Full-screen Leaflet map
- DiscoveryPanel: Right-side floating glass panel (conditionally shown)

**Key functions**:
- `handleNavigateToPlace(place)` — Sets source=userLocation, dest=place, switches to A→B
- `handleModeChange(newMode)` — Switches between search/atob/trip tabs
- `handleMarkerClick(place)` — Opens discovery panel for selected marker

### 8.2 AToBPanel.tsx (459 lines) — Unified A→B Planner

**Role**: Source → Destination route planner with 3 sub-modes.

**Sub-modes**:
1. **Direct** — Only ride prices (cab/auto/bike). No transit.
2. **Transport (Segment)** — Full transit + ride prices. Multi-hop segments.
3. **Drive** — Personal car mode
4. **Walk** — Walking only

**Key features**:
- Source/destination search with autocomplete suggestions
- Group size and budget preferences
- Route cards with score colors via `getScoreColor()`
- Per-segment option selection with map geometry updates
- "Show all" toggle for routes beyond top 5

**Route rendering**:
- Each route card shows: mode icon, total fare, duration, distance, score pill
- Score colors: green (≥80), yellow (≥60), orange (≥40), red (<40)
- Score bar with animated fill
- Segments shown as sub-cards with leg details

**Known history**:
- 2B fix: Replaced `selectedRouteIdx` with `getRouteKey()` for stable route identification
- 3P1 fix: `selectedRouteIdx` → `selectedRouteKey` in useEffect deps (line 148)

### 8.3 SearchPanel.tsx (370 lines) — Search + Nearby

**Role**: Search for places and explore nearby.

**Tabs**:
1. **Search** — Text search with debounced suggestions (300ms), place results
2. **Nearby** — Location-based with category chips (all/food/shopping/transport/etc.) and radius slider (1-10km)

**Key features**:
- Search with `AbortController` for cancellation
- `userLocation` from context with fallback to Bangalore center (12.9716, 77.5946)
- Place cards with: image, name, address, score pill (`getScoreColor`), reviews, distance
- "Navigate" button per place → triggers `onNavigate` prop

**Place card scoring**:
```typescript
const score = place.reliability_score || 0.5
// Background color from getScoreColor(score * 100)
// Score label from getScoreLabel(score)
// Icon: verified for score >= 0.6, warning for < 0.6
```

### 8.4 DiscoveryPanel.tsx — Results Glass Panel

**Role**: Right-side floating panel with place details, reviews, images, pricing.

**Features**:
- Reliability score with color-coded badge
- Rating stars
- Review summary (LLM-generated from real Google Reviews)
- Hotel price range (if applicable)
- "Navigate Here" button → `onNavigate` prop
- Price info display

**Score colors**: Uses `getScoreColor(score * 100)` throughout

### 8.5 TripPanel.tsx (~80 lines) — Trip Planner

**Role**: Create and manage multi-stop trips.

**Features**:
- "Create New Trip" button → switches to A→B tab (`setMode('atob')`)
- (Further trip management features planned but not yet implemented)

### 8.6 MapView.tsx (165 lines) — Leaflet Map

**Role**: Full-screen interactive map.

**Features**:
- OpenStreetMap tiles via Leaflet
- User location marker with pulse animation (custom divIcon)
- Place markers with color-coded pins (via `getScoreColor(score * 100)`)
- Route geometry polylines with color/weight/dash options
- Source/destination markers (custom divIcon)
- News event markers (impact-colored: green/red/blue)
- Auto-flyTo on center change
- `useRef` stabilized moveend listener

**Marker pin HTML**:
```html
<div style="position:relative;width:32px;height:32px;">
  <div style="...background:${color};border:2px solid white;...">
    <span class="material-symbols-outlined">${icon}</span>
  </div>
</div>
```

### 8.7 helpers.ts (176 lines) — Utilities

**Role**: Formatting functions, icons, score colors, mode labels.

**Key functions**:
- `getScoreColor(score)` → 4-tier color: `≥80:#22c55e`, `≥60:#eab308`, `≥40:#f97316`, `<40:#ef4444`
- `getScoreLabel(score)` → Labels: Excellent/Good/Fair/Poor/Avoid
- `getPlaceIconName(type)` → Material icon name for place types (28+ mappings)
- `getModeLabel(mode)` → Human-readable mode name
- `formatDuration(minutes)` → "2h 15m" or "45m"
- `formatRupees(amount)` → "₹125.00"
- `getModeIconName(mode)` → Material icon for transport modes (20+ mappings)

### 8.8 AppContext.tsx (173 lines) — Shared State

**Role**: React Context providing global application state.

**State fields**:
| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `mode` | AppMode | `'search'` | Active tab |
| `userLocation` | `[number,number]` | `null` | GPS location |
| `mapCenter` | `[number,number]` | `[12.9716, 77.5946]` | Map camera center |
| `sourceLocation` | `[number,number]` | `null` | A→B source |
| `destLocation` | `[number,number]` | `null` | A→B destination |
| `selectedPlace` | PlaceResult | `null` | Currently selected |
| `routeGeometry` | MapRouteGeometry[] | `null` | Map polylines |
| `trackingActive` | boolean | `false` | GPS live tracking |
| `groupSize` | number | 1 | Passenger count |
| `budget` | number | undefined | Max fare per person |

### 8.9 api.ts (119 lines) — API Client

**Role**: Axios-based API client with typed response handling.

**Functions**: 8 exported functions covering all endpoints:
- `searchPlaces`, `getNearbyPlaces`, `getSuggestions`, `verifyPlace`
- `planRoute`, `getMetroStations`, `getBusStops`, `getRidePrices`
- `enrichPlace`, `getSegmentStep`, `getAllSegments`
- (Deleted: `getMiniPathOptions` — dead)

**Axios config**: baseURL `/api`, timeout 120s

---

## 9. Data Sources & Their Structures

### 9.1 BMTC GTFS ZIP (`data_cache/bmtc_gtfs.zip`)

**Size**: 47.1 MB
**Source**: BMTC Bangalore official GTFS feed
**Contains**:

| File | Records | Purpose |
|------|---------|---------|
| `shapes.txt` | 7,915 shapes | GPS path waypoints for each bus route |
| `stops.txt` | 9,783 stop_ids | Bus stop names, coordinates |
| `trips.txt` | 56,732 trips | Individual bus journeys with route/shape mapping |
| `routes.txt` | 4,359 routes | Route IDs to route short names |
| `stop_times.txt` | 1,500,000+ rows | Every bus arrival/departure at every stop |

**Processing constraints**:
- Max 200 stop_time entries per stop (prevents memory blowup at busy stops)
- Max 500 stop_time entries per route (prevents memory blowup for long routes)

### 9.2 Pickled GTFS Cache (`data_cache/processed/gtfs_cache.pkl`)

**Size**: 67.7 MB
**Cache invalidation**: Auto-rebuilds if pickle is older than ZIP file

**Cache structure**:
```python
{
    "shapes": {shape_id: [(lat, lng), ...]},           # 7,271 entries
    "route_shapes": {route: [shape_ids]},               # 4,359 entries
    "stop_to_shapes": {stop_name: [(sid, seq), ...]},   # Per stop
    "stops_by_name": {name: (lat, lng, sid)},           # 5,077 stops
    "stop_times": {name: [(time, route), ...]},         # 429,882 entries
    "stop_times_by_route": {route: [(time, name), ...]},# Per route
    "name_map": {query: resolved_name},                 # Fuzzy match cache
}
```

### 9.3 BMTC Stop Master (`data_cache/bmtc_all_stops_master.csv`)

**Size**: 2.0 MB
**Records**: 2,972 stops
**Columns**: `Stop Name`, `Latitude`, `Longitude`, `Routes with num trips` (JSON dict)

**Pandas bug**: Column `Routes with num trips` is a Python dict literal `{'key': 'value'}` not JSON. Must use `ast.literal_eval()` instead of `json.loads()`.

**Float name bug**: Pandas CSV parser converts numeric-looking stop names to floats (`245.0`). Fixed by `str()` conversion in `_load_bus_stops()`.

### 9.4 Metro Network (`data_cache/bengaluru_metro_network.csv`)

**Size**: 8.0 KB
**Stations**: 26+ stations (Purple Line: 12, Green Line: 14+)
**Columns**: `Station_Name`, `Line`, `Sequence`, `Latitude`, `Longitude`, `Station_Code`, `Is_Interchange`

**Missing data**: Yelahanka station (Green Line extension) — not yet added to CSV.

**Metro lines**:
- **Purple Line**: Baiyappanahalli → Krishnarajapura →...→ Mahatma Gandhi Road →...→ Majestic →...→ Mysore Road →...→ Challaghatta
- **Green Line**: Nagasandra → Yeshwanthpur →...→ Majestic →...→ Chickpet →...→ Yelachenahalli →...→ Silk Institute
- **Interchange**: Nadaprabhu Kempegowda Station (Majestic) — only interchange

### 9.5 Railway Stations (`data_cache/karnataka_railway_stations.json`)

**Size**: 2.8 KB
**Format**: `[{name, lat, lng}, ...]`
**Records**: 50+ stations across Karnataka
**Key stations**: KSR Bengaluru, Mysuru Junction, Hubballi, Mangaluru Central, Belagavi, Ballari

### 9.6 Transit Fares (`data_cache/transit_fares.json`)

**Size**: 3.5 KB
**Slabs**:

```json
{
  "bmtc_ordinary_slabs": [
    {"min_km": 0, "max_km": 2, "fare": 6},
    {"min_km": 2, "max_km": 5, "fare": 12},
    {"min_km": 5, "max_km": 10, "fare": 16},
    {"min_km": 10, "max_km": 20, "fare": 22},
    {"min_km": 20, "max_km": 30, "fare": 28},
    {"min_km": 30, "max_km": 40, "fare": 32}
  ],
  "bmtc_ac_vajra_slabs": [
    {"min_km": 0, "max_km": 5, "adult_fare": 15, "child_fare": 8},
    {"min_km": 5, "max_km": 10, "adult_fare": 20, "child_fare": 10},
    {"min_km": 10, "max_km": 20, "adult_fare": 35, "child_fare": 18},
    {"min_km": 20, "max_km": 40, "adult_fare": 45, "child_fare": 23}
  ],
  "namma_metro_slabs": [
    {"min_km": 0, "max_km": 2, "fare": 11},
    {"min_km": 2, "max_km": 4, "fare": 16},
    {"min_km": 4, "max_km": 6, "fare": 21},
    {"min_km": 6, "max_km": 8, "fare": 26},
    {"min_km": 8, "max_km": 10, "fare": 32},
    {"min_km": 10, "max_km": 15, "fare": 38},
    {"min_km": 15, "max_km": 20, "fare": 45}
  ]
}
```

### 9.7 KIA Routes (`data_cache/kia_routes_fare_full.json`)

**Size**: 22.6 KB
**Structure**: `{"vayu_vajra_kia_routes": {route_id: {route_info, stops: [...]}}}`

### 9.8 Traffic Logs (`data_cache/traffic_logs.csv`)

**Size**: 7.5 MB
**Records**: 445,843 rows
**Columns**: `time_sim`, `step_time`, `x_position`, `y_position`, `speed_mps`, `live_speed_mps`

**Status**: Synthetic data (not live). Used by `routes.py:_load_traffic_speeds()` for traffic overlay on map.

---

## 10. Scrapers & External APIs

### 10.1 ride_scraper.py — Ride Pricing

**Purpose**: Generate real ride-hailing price estimates.

**Data sources (in order)**:
1. **SerpAPI Google Maps Directions** — Tries to get live ride prices from Google Maps
2. **Formula fallback** — Karnataka govt-mandated rates + surge factor

**Rate structure** (Karnataka govt rates):

| Mode | Base Fare | Per KM | Per Min | Min Fare | Seats |
|------|-----------|--------|---------|----------|-------|
| Uber Go / Ola Mini | ₹25 | ₹12/km | ₹1/min | ₹50 | 3 |
| Ola Mini | ₹25 | ₹12/km | ₹1/min | ₹50 | 3 |
| Uber Priority / Ola Prime | ₹50 | ₹24/km | ₹1.5/min | ₹100 | 3 |
| Uber XL / Ola XL | ₹100 | ₹30/km | ₹2/min | ₹150 | 6 |
| Auto | ₹15 | ₹9/km | ₹0.5/min | ₹25 | 3 |
| Rapido Bike / Uber Moto | ₹10 | ₹5/km | ₹0.5/min | ₹15 | 1 |
| Uber for Women | ₹25 | ₹12/km | ₹1/min | ₹50 | 3 |
| Uber Pet / Premier | ₹50 | ₹18/km | ₹1.5/min | ₹100 | 3 |

**Surge factor calculation**:
1. Check weather (Open-Meteo) — rain adds surge
2. Time-based: Early morning +10%, Peak hours +25%, Weekend +20%, Lunch/dinner +5%

**Distance calculation**:
1. Try Google Maps Distance Matrix API (live traffic-aware)
2. Fallback: `geodesic` straight-line × 2 (rough urban multiplier)

**SerpAPI integration**: When SerpAPI Google Maps Directions is successful, returned prices get `source: "serpapi"` and `is_live: True` flags.

### 10.2 google_reviews_scraper.py — Google Reviews

**Purpose**: Fetch real Google reviews for places.

**Data flow**:
1. `get_place_reviews(name, address)` called
2. Try **SerpAPI**:
   - `search_places(query)` → get `place_id`
   - `place_details(place_id)` → extract `user_reviews.most_relevant`
   - Fields: `username`, `description`, `rating`, `date`
3. Fallback: **Google Places API** → `places/{place_id}/reviews`
4. Return max 5 reviews

**Key fix**: Original code was calling `_parse_place_detail` on search response (wrong method). Fixed to: search → place_id → place_details → reviews.

### 10.3 serpapi_client.py — SerpAPI Wrapper

**Purpose**: Google Search API via SerpAPI for place search, directions, and details.

**Config**: `SERPAPI_API_KEY` in `.env`

**Methods**:
- `search_places(query, lat, lng)` — Text search
- `place_details(place_id)` — Get details + reviews
- `get_directions(origin, dest)` — Google Maps directions

### 10.4 google_maps_client.py — Google Places API

**Purpose**: Direct Google Places API calls (used when SerpAPI is unavailable).

**Config**: `GOOGLE_MAPS_API_KEY` in `.env`

**Methods**:
- `text_search(query, lat, lng)`
- `nearby_search(lat, lng, radius, type)`
- `place_details(place_id)`
- `distance_matrix(origins, destinations)`

### 10.5 news_scraper.py — Travel News

**Purpose**: Fetch travel advisories and news via DuckDuckGo.

**Method**:
- DuckDuckGo `site:` crawl for `bangalore traffic news`
- Uses `ddg_scraper.py` with proxy rotation
- Returns structured news items with title, description, impact, source, timestamp

### 10.6 train_service.py — Live Train Data

**Purpose**: Live train schedules via eRail.in API.

**Fallback**: When eRail.in fails, returns hardcoded data for 7 city pairs.

### 10.7 weather_client.py — Open-Meteo API

**Purpose**: Get weather conditions for route-aware scoring.

**Data**: Temperature, precipitation probability, weather code
**Usage**: Surge multiplier for rides, route score adjustments (rain penalty for walking)

---

## 11. Proxy Infrastructure

### 11.1 ProxyManager (`backend/services/proxy_manager.py`)

**Purpose**: Rotating proxy system for web scraping.

**Tier system**:

| Tier | Type | Source | Use Case | Reliability |
|------|------|--------|----------|-------------|
| 1 | Free HTTP proxies | GitHub proxy lists (TheSpeedX, ShiftyTR, monosans) | DuckDuckGo scraping, low-rate tasks | Low (many dead) |
| 2 | DataImpulse residential | .env config (DATAIMPULSE_USER/PASS/HOST) | IP-blocked sites, high-rate tasks | High ($5/5GB) |
| 3 | Direct (no proxy) | None | API calls (SerpAPI, Google Maps, Reddit) | Highest |

**Free proxy fetching**:
- Sources: 3 GitHub raw lists
- Refresh interval: 5 minutes
- Max 50 proxies per source
- Rotation: Round-robin via `_free_index`

**User-Agent rotation**:
- 5 different UA strings (Chrome Windows/Mac/Linux, Firefox)
- Random selection per request

**Current status**: DataImpulse tier needs `.env` configuration. Without it, the system falls back to free proxies (unreliable for many sites).

---

## 12. Docker & OSRM Setup

### 12.1 Docker Compose (`docker-compose.yml`)

**4 services**:

#### Backend (Port 8000)
- **Image**: Custom Dockerfile.backend (Python 3.12)
- **Mounts**: `data_cache/`, `.env`
- **Depends on**: osrm-car, osrm-foot
- **OSRM URL**: `http://osrm-car:5000`

#### Frontend (Port 3000)
- **Image**: Custom Dockerfile.frontend (Node 20)
- **Depends on**: backend

#### OSRM Car (Port 5000)
- **Image**: `ghcr.io/project-osrm/osrm-backend:latest`
- **Volume**: `./osrm-data:/data`
- **Setup**: Downloads southern-zone PBF from Geofabrik (~1.8GB), runs `osrm-extract` → `osrm-partition` → `osrm-customize` → `osrm-routed`
- **Algorithm**: MLD (Multi-Level Dijkstra)
- **Status**: ✅ Working

#### OSRM Foot (Port 5001)
- **Image**: Same as car
- **Volume**: `./osrm-data-foot:/data`
- **Setup**: Copies PBF from car data, extracts with foot profile
- **Status**: ❌ **OOM during `osrm-customize`** — the foot profile customization runs out of memory on a system with limited RAM. The southern-zone PBF (1.8GB compressed, ~5GB processed) requires ~4GB RAM for foot customization vs ~3GB for car.

**Why OSRM Foot OOM?**: The foot profile (`foot.lua`) creates more edges per node (walking can go anywhere, unlike cars which are constrained to roads). This results in a larger graph that exceeds available memory during the `osrm-customize` step.

**Potential fixes**:
1. **More RAM**: Allocate >4GB to the Docker container (wait, Docker already uses host RAM — system needs more physical RAM)
2. **Smaller PBF**: Use a Bangalore-city PBF instead of southern-zone (much smaller, ~100MB)
3. **Alternative**: Use OSRM's `/foot` endpoint on the car instance (not available — car instance only has car profile)
4. **Skip OSRM foot**: Use interpolated walking paths only (current behavior)

### 12.2 OSRM Data

**File**: `osrm-data/southern-zone.osm.pbf` (~1.8GB download)
**Source**: Geofabrik — Southern Zone India extract (includes Karnataka, Tamil Nadu, Kerala, Andhra Pradesh, Telangana, Goa, Pondicherry)
**Processed files**: `.osrm`, `.osrm.cells`, `.osrm.names`, etc.

### 12.3 Local Dev (`start.ps1`)

**Usage**: `.\start.ps1` or `.\start.ps1 -TestTime` (freezes time at 12:00 PM for GTFS testing)

**What it does**:
1. Kills existing Python/Node processes
2. Starts backend: `python -m uvicorn backend.main:app --reload --port 8000`
3. Starts frontend: `npx vite --port 3000 --host`

---

## 13. Performance Profile & Optimizations

### 13.1 Current Performance Benchmarks

| Operation | Time | Condition |
|-----------|------|-----------|
| GTFS cache load (pickle) | **0.65s** | 7,271 shapes, 5,077 stops, 429K times |
| Bus stop name pre-resolve | **7.7s** | First run only; cached in pickle |
| A* graph build | **2.2s** | 2,939 nodes, ~54,000 edges |
| Total server startup | **~10.6s** | All caches cold |
| API route plan (warm) | **<1s** | All caches loaded |
| API all-segments (warm) | **20-35s** | OSRM batch fetching is bottleneck |
| find_nearby_bus_stops | **3.7ms** | Via SpatialIndex + haversine (was 374ms) |

### 13.2 Optimizations Applied

#### 13.2.1 geodesic → haversine (100x)
- **Problem**: `find_nearby_bus_stops()` used `geodesic()` from geopy — 374ms per call
- **Fix**: Custom `_haversine()` pure math implementation
- **Result**: 3.7ms per call
- **Applied in**: `database.py`, `transit_config.py`, `transit_graph.py`
- **Additional optimization**: `_dist_cache` dict in `transit_graph.py` prevents recalculating same haversine distances

#### 13.2.2 GTFS Cache (60x on startup)
- **Problem**: Full GTFS parse every startup — ~41 seconds
- **Fix**: Pickled cache at `data_cache/processed/gtfs_cache.pkl`
- **Result**: 0.65s load time
- **Cache invalidation**: Auto-rebuilds if ZIP is newer than pickle

#### 13.2.3 Name Resolution Cache (10x on pre-resolve)
- **Problem**: First fuzzy name resolution for 2972 names — 79 seconds
- **Fix**: `_name_map` cache + trigram pre-filter + `get_close_matches` instead of `SequenceMatcher` loop
- **Result**: 7.7s (first run), 0s (subsequent — cached in pickle)

#### 13.2.4 GTFS Lazy Loading (zero startup overhead)
- **Problem**: GTFS loading blocked server startup
- **Fix**: Removed `_ensure_gtfs()` from `main.py` startup; GTFS loads lazily on first route request
- **Result**: Server starts instantly

#### 13.2.5 Stop Times Index (1000x on route lookup)
- **Problem**: `find_stops_on_route_toward_dest()` iterated ALL 5077 stops
- **Fix**: `_stop_times_by_route` dict → O(1) lookup → O(R) scan (R ≤ 500)
- **Result**: Individual call from ~5ms to ~0.001ms

#### 13.2.6 Segment Generation Limits
- Max 8 bus stops per segment (limits search space)
- Max 4 metro stations per segment
- Max 8 transit options per stop
- Max segment depth: 3 (prevents infinite chaining)
- Max 500 entries per route in `_stop_times_by_route`

#### 13.2.7 OSRM Gather Timeout
- **Problem**: `asyncio.gather()` with no timeout could hang indefinitely
- **Fix**: `asyncio.wait_for(gather(), timeout=20.0)` with try/except for both batch and individual requests

#### 13.2.8 Spatial Index for Nearby Queries
- **Problem**: Nearby bus stop queries were O(N) scan of 2972 stops
- **Fix**: Grid-based `SpatialIndex` — pre-bucketed by lat/lng grid cells
- **Result**: O(1) grid lookup + O(K) distance check within cell

### 13.3 Remaining Performance Issues

| Issue | Current | Target | Blocker |
|-------|---------|--------|---------|
| all-segments 20-35s | 20-35s | <5s | OSRM path fetching is serialized per segment; GTFS caches reset per request |
| Bus stop name pre-resolve 7.7s | 7.7s (first run) | 0s | Already cached — this is a one-time cost |
| GTFS cache 0.65s | 0.65s | ~0.1s | Pickle deserialization is I/O bound |

---

## 14. All Bugs Fixed & Lessons Learned

### Bug 14.1: Float Stop Names (Multiple Locations)
**Symptom**: `AttributeError: 'float' object has no attribute 'lower'`  
**Root cause**: Pandas CSV parser converts numeric-looking values to floats  
**Fix**: `str()` conversion + isinstance checks in 5+ locations  
**Lesson**: Never trust CSV data types from pandas — always convert to string explicitly

### Bug 14.2: GTFS Route Number Suffixes
**Symptom**: Route numbers like "MF-28 JKLO-ISROQ-LGRNB" instead of "MF-28"  
**Root cause**: GTFS `route_short_name` contains descriptive suffixes  
**Fix**: `clean_route_short_name()` strips terminal suffix: `re.split(r'\s+', name)[0]`  
**Lesson**: GTFS data is messy — always clean/validate at load time

### Bug 14.3: Station_to_dest_dist UnboundLocalError
**Symptom**: 500 error on `/all-segments`  
**Root cause**: Variable used before assignment in metro→bus loop  
**Fix**: Moved variable initialization before the loop  
**Lesson**: Python's UnboundLocalError is silent until runtime — test all code paths

### Bug 14.4: Wrong GTFS Cache Path
**Symptom**: GTFS cache never found, always re-parses ZIP  
**Root cause**: Cache path was relative `processed/gtfs_cache.pkl` instead of absolute  
**Fix**: `os.path.join(settings.PROCESSED_DIR, "gtfs_cache.pkl")`  
**Lesson**: Always use absolute paths derived from config; never hardcode relative paths

### Bug 14.5: Stale GTFS Cache
**Symptom**: Only 1274 stops loaded (should be 5077)  
**Root cause**: Old cache from early version with 100K row limit on stop_times  
**Fix**: Delete old pickle, trigger full reload  
**Lesson**: Cache invalidation is critical — version your cache or check data integrity

### Bug 14.6: stop_times Empty After Reload
**Symptom**: `_stop_times_by_route` empty despite successful ZIP load  
**Root cause**: Route id → short_name mapping failed for some routes  
**Fix**: Correct `trip_id → route_id → route_short_name` chain via `_trip_to_route` + `_route_id_to_name`  
**Lesson**: GTFS has an indirect 3-hop mapping (trip→route→name); verify each hop

### Bug 14.7: ast.literal_eval() for Route Parsing
**Symptom**: `json.loads()` crashing on CSV route column  
**Root cause**: Routes column uses Python dict literal syntax (`{'key': 'value'}`), not JSON (`{"key": "value"}`)  
**Fix**: `ast.literal_eval()` with JSON fallback  
**Lesson**: Check the actual data format before parsing

### Bug 14.8: Bus `to` Field Static Text
**Symptom**: Bus `to` field showed "towards destination" instead of actual GTFS stop name  
**Root cause**: `find_stops_on_route_toward_dest()` returned source stop (itself) as first match  
**Fix**: Added minimum distance check (>200m from source) + use `_stop_times_by_route` index  
**Lesson**: Iteration over stops can include the source stop — always exclude self-matches

### Bug 14.9: Bare except in config.py
**Symptom**: `KeyboardInterrupt` caught silently  
**Root cause**: `except:` instead of `except (json.JSONDecodeError, TypeError):`  
**Fix**: Explicit exception types  
**Lesson**: Never use bare `except:` — it catches `SystemExit`, `KeyboardInterrupt`, etc.

### Bug 14.10: Score Color Inconsistency (4 different functions)
**Symptom**: Same score showed different colors across components  
**Root cause**: 4 different color functions with different thresholds and hex values  
**Fix**: Unified to `getScoreColor()` with single threshold set (80/60/40)  
**Sub-bug found**: MapView showed green at 0.7 (=70/100), but getScoreColor's green starts at 80 — was showing yellow as green

### Bug 14.11: calc_fare_with_surge Tuple Unpacking
**Symptom**: Fare calculations used wrong tuple fields  
**Root cause**: Tuple structure `(mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km)` was unpacked as `(mode_id, label, per_km, base_fare, free_km, icon, seats, min_fare)` — `time_per_km` was treated as `base_fare`, `base_fare` as `free_km`, `free_km` as `min_fare`  
**Fix**: Corrected unpacking + delegated to `_calc_ride_fare()` to prevent future mismatch  
**Lesson**: Tuple unpacking is fragile — wrap in a function with named parameters

### Bug 14.12: AToBPanel Stale Dep (selectedRouteIdx)
**Symptom**: Route selection didn't update map geometry  
**Root cause**: `useEffect` dep array had `selectedRouteIdx` which was renamed to `selectedRouteKey` — old variable didn't exist  
**Fix**: `selectedRouteIdx` → `selectedRouteKey`  
**Lesson**: Rename variables in sync across all references — TypeScript should catch this (would with noUnusedLocals: true)

### Bug 14.13: Ride Fare Per-Person Double Charge
**Symptom**: `total = pp * group_size` was multiplying an already-per-person fare  
**Root cause**: Wrong formula — was computing vehicle fare × passenger count  
**Fix**: `total = _calc_ride_fare(...)` (vehicle fare) and `pp = round(total / group_size)` (per-person)  
**Lesson**: Cab/auto fare is per-vehicle, not per-person

### Bug 14.14: Metro Direction Filter Too Aggressive
**Symptom**: Valid metro routes not showing (e.g., Cubbon Park → MG Road)  
**Root cause**: `dest_to_dm > nm_dist_to_dest * 1.1` eliminated metro routes where the metro doesn't make linear progress toward destination  
**Fix**: Removed the 1.1 multiplier check  
**Lesson**: Metro routes connect stations — direction toward destination along metro line is valid even if direct line doesn't point exactly at destination

### Bug 14.15: Circular Routing (800m radius)
**Symptom**: Same stop appearing in multiple segments  
**Root cause**: 300m radius was too small — two stops 400m apart weren't recognized as same location  
**Fix**: Increased `_is_visited()` radius from 300m → 800m  
**Lesson**: Bengaluru bus stops are dense — need adequate radius for dedup

### Bug 14.16: 55MB Unused Datasets
**Symptom**: 10 data files taking space, never used  
**WHAT**: `rides_data.csv`, `bangalore_ride_data.csv`, `metro_per_hour*.csv`, `NammaMetro_Ridership_Dataset.csv`, 4× `bangalore-wards-*.csv`, `KIA_stops_fare_incomplete.json`, `metro.csv`  
**Fix**: Deleted all 10 files  
**Lesson**: Clean up experimental datasets — they confuse future developers

### Bug 14.17: SegmentPanel Dark Theme Hardcoded Colors
**Symptom**: SegmentPanel used hardcoded `#0f172a`, `#1a2332` (dark mode colors) in a light theme app  
**Fix**: Replaced with CSS variable references (`var(--surface-container)`, etc.)  
**Lesson**: Never hardcode colors — use CSS custom properties

### Bug 14.18: Metro→Bus Lookup Wrong Station List
**Symptom**: Bus→metro CASE 2 (no metro near source) was using empty list  
**Root cause**: Was searching `metro_stations` (source-nearby list) instead of `db.metro_stations` (full list)  
**Fix**: Switch to `db.metro_stations` — search ALL metro stations  
**Lesson**: Variable shadowing — local `metro_stations` variable hid the db attribute

### Bug 14.19: GTFS ~41s Startup Block
**Symptom**: Server took 41 seconds to start  
**Root cause**: `_ensure_gtfs()` called at import time in `main.py`  
**Fix**: Removed from `main.py` startup; GTFS loads lazily on first route request  
**Lesson**: Lazy loading = instant startup

### Bug 14.20: 300 Bus Stop Walk Edge Limit
**Symptom**: Only first 300 bus stops had bus↔metro walk edges  
**Root cause**: Hardcoded `[:300]` slice in graph building  
**Fix**: Removed limit — all 2933 bus stops get walk edges  
**Lesson**: Sample limits hide bugs — test with full dataset

### Bug 14.21: Google Reviews Broken SerpAPI Flow
**Symptom**: Reviews returned empty even when SerpAPI data was available  
**Root cause**: Called `_parse_place_detail` on search response instead of `search → place_id → place_details → user_reviews`  
**Fix**: Corrected the chain  
**Lesson**: Understand API response structures before parsing

### Bug 14.22: SerpAPI Response Key Mismatch
**Symptom**: Reviews parsed wrong field  
**Root cause**: Used `response["place"]` (wrong key) instead of `response["place_results"]`  
**Fix**: Correct key: `place_results.user_reviews.most_relevant`  
**Lesson**: Check actual API responses — documentation can be wrong

---

## 15. Testing Infrastructure

### 15.1 pytest Setup

**Location**: `tests/`
**Files**:
- `tests/__init__.py` — Package marker
- `tests/conftest.py` — Shared fixtures
- `tests/test_fare_engine.py` — 12 test cases
- `tests/test_segment_builder.py` — 9 integration test cases

**Run command**: `python -m pytest tests/ -v`

### 15.2 test_fare_engine.py (12 tests)

**What it tests**:
1. `calc_fare_with_surge` basic calculation
2. `calc_fare_with_surge` with free km
3. `calc_fare_with_surge` zero distance
4. `calc_fare_with_surge` surge multiplier (1.35x)
5. `get_mode_by_id` found
6. `get_mode_by_id` not found
7. `get_mode_by_id` case sensitivity
8. `ride_fare_range` basic
9. `ride_fare_range` unknown mode
10. `ride_fare_range` zero distance
11. `calc_fare_with_surge` tuple unpacking correctness
12. Surge multiplication precision

**Bug found by tests**: The tuple unpacking bug (Bug 14.11) was discovered by test 11. The old code was unpacking `(mode_id, label, per_km, base_fare, free_km, icon, seats, min_fare)` but the actual tuple structure is `(mode_id, label, per_km, time_per_km, base_fare, icon, capacity, free_km)`.

### 15.3 test_segment_builder.py (9 tests)

**What it tests**:
1. `TripSegmentBuilder` initialization
2. `_coord_key` format
3. `_is_visited` detection
4. `_is_visited` beyond radius
5. `_is_outside_bengaluru` within city
6. `_is_outside_bengaluru` outside city
7. `_is_hub_or_close_to_dest` major hub
8. `_is_hub_or_close_to_dest` close to dest
9. `_is_hub_or_close_to_dest` neither

### 15.4 What's Not Tested

- **Unit tests for `transit_service.py`** — No test coverage for route generation methods
- **Unit tests for `transit_graph.py`** — No A* graph tests
- **Unit tests for `transit_scoring.py`** — No TOPSIS scoring tests
- **Integration tests for API endpoints** — No end-to-end route planning tests
- **Frontend tests** — No Jest/React Testing Library tests

---

## 16. Design System & UI

### 16.1 CSS Variables (`frontend/src/index.css`)

```css
:root {
  --primary: #000666;
  --primary-container: #bdc2ff;
  --on-primary: #ffffff;
  --secondary: #006e1c;
  --secondary-container: #88ff8f;
  --error: #ba1a1a;
  --error-container: #ffdad6;
  --surface: #f9f9f9;
  --surface-dim: #d9d9d9;
  --surface-container: #ededed;
  --surface-container-high: #e7e7e7;
  --surface-container-low: #f3f3f3;
  --surface-variant: #e0e2ec;
  --outline: #74777f;
  --outline-variant: #c6c5d4;
  --inverse-surface: #2f3131;
  --font: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --radius-full: 9999px;
}
```

### 16.2 Glassmorphism

```css
.glass {
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(24px) saturate(1.4);
  border: 1px solid rgba(198,197,212,0.25);
}
.glass-strong {
  background: rgba(255,255,255,0.92);
  backdrop-filter: blur(24px) saturate(1.4);
  box-shadow: 0 8px 40px var(--shadow-primary);
}
```

Note: The Stitch design spec calls for `blur(20px)` — our implementation uses `blur(24px)`. Slight deviation for stronger visual effect.

### 16.3 Score Color System

| Score Range | Color | Hex | Label |
|-------------|-------|-----|-------|
| 80-100 | Green | `#22c55e` | Excellent |
| 60-79 | Yellow | `#eab308` | Good/Fair |
| 40-59 | Orange | `#f97316` | Poor |
| 0-39 | Red | `#ef4444` | Avoid |

**Used in**: MapView (marker pins, popup), AToBPanel (route cards, score bars), DiscoveryPanel (badges, backgrounds), SearchPanel (place cards)

### 16.4 Material Icons

**Library**: Material Symbols (Google) — 20+ transport/place icons mapped
**Key mappings**:
- `walk` → `directions_walk`
- `bus_ordinary` → `directions_bus`
- `metro` → `subway`
- `car` → `directions_car`
- `bike` → `pedal_bike`
- `auto` → `local_taxi`
- `cab` → `local_taxi`
- Place types: `cafe` → `local_cafe`, `mall` → `store_mall`, `hospital` → `local_hospital`, etc.

### 16.5 Stitch Design References

**Location**: `stitch_omnipath_ai_navigation/`
**Contents**: 9 WayFinder design modules + 1 DESIGN.md spec

| Module | Implemented? | Notes |
|--------|-------------|-------|
| A→B Planner | Partial | AToBPanel exists but doesn't match spec exactly |
| Discovery Results | Partial | DiscoveryPanel exists but isn't 360px fixed width |
| Dynamic Search Map | Partial | Map with markers implemented |
| Segment Selection | ❌ Not implemented | Was planned for SegmentPanel (deleted) |
| Trip Itinerary | ❌ Not implemented | Planned for TripPanel |
| Navigation Trigger | ❌ Not implemented | "Start Journey" button exists but is basic |
| Search Map | Partial | Search works but no voice/filter icons |
| Trip Planner | ❌ Not implemented | Only basic "Create New Trip" exists |

**Key unimplemented Stitch features**:
- Bottom Navigation Pill (floating tab bar)
- Interactive map markers (hover scale animation, pulsing ring)
- Electric Blue (#0066FF) for active paths
- Responsive bottom-sheet drawer for mobile
- 4px baseline grid

---

## 17. Environment Configuration

### 17.1 `.env` File Structure

```bash
# === API Keys ===
SERPAPI_API_KEY=your_serpapi_key
GOOGLE_MAPS_API_KEY=your_google_maps_key
GOOGLE_CX=your_google_cx

# === LLM Configuration ===
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_FALLBACK_MODELS='["openai/gpt-4o-mini","openai/gpt-3.5-turbo","anthropic/claude-3-haiku"]'
GEMINI_API_KEY=your_gemini_key  # fallback if OpenRouter fails

# === Proxy Configuration ===
DATAIMPULSE_USER=your_dataimpulse_username
DATAIMPULSE_PASS=your_dataimpulse_password
DATAIMPULSE_HOST=your_dataimpulse_host:port

# === OSRM Configuration ===
OSRM_BASE_URL=http://localhost:5000
OSRM_FOOT_URL=http://localhost:5001

# === Fuel & Vehicle ===
FUEL_PRICE_PER_LITER=110.0
PETROL_AVG_MILEAGE=15.0

# === Test Mode (optional) ===
VOYAGER_TEST_TIME=2024-07-15 12:00:00
```

### 17.2 Settings Class (`backend/core/config.py`)

All env vars loaded via `pydantic-settings.BaseSettings` with `env_file = ".env"`.

Settings are accessible via `from backend.core.config import settings`.

---

## 18. Future Roadmap & Plans

### 18.1 Immediate Remaining Issues (from ISSUES.md)

| ID | Issue | Priority | Plan |
|----|-------|----------|------|
| 1 | OSRM unreachable (remote) | Critical | Use Docker OSRM (port 5000) which is working. Remote fallback is for non-Docker users. |
| 2 | Response time 25-30s for medium routes | **Critical** | **Plan**: Make GTFS caches persistent across requests instead of per-request. Currently `_clear_caches()` in `get_all_segments()` resets 4 caches. Fix: keep caches, only clear when source/dest changes significantly. Target: <5s. |
| 3 | GTFS route numbers internal codes | Major | **Plan**: Add `routes.txt` `route_long_name` mapping. Show human-readable names alongside codes. |
| 4 | Circular routing possible (800m radius) | Major | **Plan**: Implement chain-based visited tracking instead of distance-only. Track which routes/buses were already taken, not just which stops. |
| 5 | Empty bus paths (GTFS shape gaps) | Major | **Plan**: Add fallback interpolation for missing shape segments. Currently returns `[]` silently. |
| 8 | Final-mile walk for distant stops (>2km) | Medium | **Plan**: Filter walk options to only show when <2km. |
| 9 | No real-time bus data | Medium | **Plan**: Integrate BMTC's real-time GPS feed (if available) or scrape transit app data. Big feature. |
| 10 | Fare calculation approximate | Medium | **Plan**: Use actual route-specific fares from GTFS `fare_attributes.txt` instead of distance-based slabs. |
| 11 | No battery/context awareness | Medium | **Plan**: Pass device context (battery level, time constraints) to routing engine. |
| 12 | UI column layout breaks | Low | **Plan**: Responsive CSS fix for small screens. |
| 13 | No loading spinner per column | Low | **Plan**: Add per-segment loading indicators. |
| 16 | Metro interchange stations limited | Low | **Plan**: Add more interchange stations (e.g., Yeshwanthpur, Baiyappanahalli). |

### 18.2 Docker Fixes

| Issue | Plan | Timeline |
|-------|------|----------|
| OSRM Foot OOM | **Option A**: Download Bangalore-only PBF (~100MB) instead of southern-zone. Smaller graph fits in RAM. **Option B**: Increase Docker memory limit in Docker Desktop settings. **Option C**: Skip foot OSRM entirely — use interpolated walking paths (current behavior). | Sprint 5/6 |
| Docker compose startup order | Add `condition: service_healthy` healthchecks | Sprint 5/6 |
| .env not mounted in production | Add proper secret management | Future |

### 18.3 Planned Architecture Improvements

| Improvement | Why | Effort |
|-------------|-----|--------|
| Persistent GTFS segment caches | 20-35s → <5s on all-segments | 2 days |
| Route-specific fares from GTFS | Accurate fares instead of approximate slabs | 3 days |
| Real-time BMTC bus GPS | Live bus positions instead of static schedules | 2 weeks |
| SegmentPanel UI revival | Progressive column navigation was core UX | 1 week |
| Stitch design full integration | Professional UI matching design spec | 1 week |
| Pydantic models for segment data | Type safety instead of raw dicts | 1 day |
| End-to-end API tests | Prevent regression during refactoring | 2 days |
| Frontend Jest/RTL tests | Component-level testing | 3 days |

### 18.4 External API Integration Strategy

| API | Status | Purpose | Why Chosen Over Alternatives |
|-----|--------|---------|------------------------------|
| **SerpAPI** | ✅ Integrated | Google Search, Maps Directions, Place Details | $0.01/query, handles Google blocking, proxy-free |
| **Google Places API** | ✅ Integrated | Place search, details, reviews, photos | $200 free credit/month, reliable |
| **Google Distance Matrix** | ✅ Integrated | Live traffic-aware distances for ride pricing | Pay-as-you-go, accurate ETA |
| **OpenWeatherMap / Open-Meteo** | ✅ Integrated | Weather for route scoring | Free, no key needed for current weather |
| **eRail.in** | ✅ Integrated | Live train schedules | Free, covers Indian Railways |
| **DuckDuckGo** | ✅ Integrated | Travel news scraping | Free, no rate limiting |
| **DataImpulse** | ⏳ Need config | Residential proxies for scraping | $5/5GB, reliable IP rotation |
| **OSRM (self-hosted)** | ✅ Car, ❌ Foot | Road-following paths | Free, self-hosted, no rate limits |

**Why we integrated SerpAPI**: Google Search API directly would cost significantly more. SerpAPI handles the Google proxy layer for us at a fraction of the cost. It also provides structured data extraction (Google Maps directions, place details, reviews) that would otherwise require complex HTML parsing.

**Why we integrated Google Places API directly**: For place search and reviews, Google Places API is more reliable and has better coverage than SerpAPI's Google Search. We use SerpAPI as a fallback.

**Why we use DuckDuckGo for news**: Free, no API key needed, no rate limiting. Perfect for traffic news scraping.

**Why we self-host OSRM**: Remote OSRM (router.project-osrm.org) is unreliable and has rate limits. Docker-based self-hosting gives us control over performance and availability.

### 18.5 Data Handling Strategy

**Current approach**: All data loaded in memory at startup (or lazily):
- GTFS data: ~67MB pickle, lazy-loaded
- Metro/bus/rail data: ~5MB, loaded at startup
- Traffic data: 7.5MB CSV, loaded on demand (every 60s refresh)

**Planned improvements**:
1. **Sharded GTFS cache**: Split pickle into shapes/stops/times chunks for faster partial loading
2. **Incremental GTFS updates**: Poll BMTC for new GTFS ZIP, update cache without restart
3. **Real-time bus data**: WebSocket connection to BMTC's live feed (if available)
4. **Traffic data replacement**: Replace synthetic traffic_logs.csv with Google Maps traffic API data
5. **Query result caching**: Cache `_build_single_segment()` results by (source, dest) coordinate pair — avoid rebuilding segments for repeated searches

### 18.6 2026 Plans (Next Steps)

**Immediate (Sprint 5)**:
1. Performance: Persistent GTFS caches (fix the 20-35s bottleneck)
2. Performance: Parallel segment building (segments 1-N currently serial)
3. Data completeness: Yelahanka metro station
4. Data completeness: Metro interchange expansions
5. Refinement: Bus→metro CASE 2 scoring (reverse-direction filter)
6. Polish: SearchPanel remaining inline score colors
7. Polish: Unused imports cleanup

**Short-term (Sprint 6)**:
1. Docker: OSRM Foot fix (smaller PBF or RAM increase)
2. Testing: Unit tests for transit_service, transit_graph, transit_scoring
3. Testing: API integration tests for /plan and /all-segments
4. Data: Route-specific fares from GTFS
5. DevEx: linting CI pipeline

**Medium-term (Sprint 7+)**:
1. Real-time bus GPS integration
2. Stitch design full implementation (bottom nav pill, interactive markers, mobile responsive)
3. Accessibility mode
4. Multi-language support (Kannada + English)
5. Offline GTFS mode
6. Booking integration (Uber/Ola/Namma Metro)
7. Personalized user preferences

---

## 19. Appendix A: Complete File Reference

### 19.1 Backend Files (58 files, ~7200 lines)

| File | Lines | Purpose |
|------|-------|---------|
| `backend/main.py` | 55 | FastAPI app entry |
| `backend/requirements.txt` | 12 | Dependencies |
| `backend/api/routes.py` | 680 | All route endpoints |
| `backend/api/search.py` | 104 | Search + LangGraph endpoints |
| `backend/core/config.py` | 56 | Settings class |
| `backend/core/database.py` | 315 | TransitDatabase singleton |
| `backend/core/spatial_index.py` | — | Grid-based spatial index |
| `backend/models/transit.py` | 102 | 13 Pydantic models |
| `backend/services/__init__.py` | 0 | Package marker |
| `backend/services/transit_service.py` | 534 | Route orchestrator |
| `backend/services/transit_config.py` | 112 | Constants + pure functions |
| `backend/services/transit_graph.py` | 187 | A* graph builder |
| `backend/services/transit_scoring.py` | 53 | TOPSIS wrapper |
| `backend/services/transit_paths.py` | 106 | OSRM path fetcher |
| `backend/services/segment_builder.py` | 1216 | TripSegmentBuilder |
| `backend/services/fare_engine.py` | 33 | Fare + surge calculator |
| `backend/services/astar_engine.py` | ~122 | A* algorithm |
| `backend/services/topsis_engine.py` | ~64 | TOPSIS numpy |
| `backend/services/gtfs_service.py` | 586 | GTFS data loader |
| `backend/services/geocoding.py` | 477 | Place search/verify |
| `backend/services/train_service.py` | 174 | Live train data |
| `backend/services/images.py` | 36 | Image processing |
| `backend/services/proxy_manager.py` | 98 | Proxy rotation |
| `backend/services/agent.py` (llm_agent) | 329 | LLM agent |
| `backend/services/scrapers/ride_scraper.py` | 172 | Ride pricing |
| `backend/services/scrapers/google_reviews_scraper.py` | 146 | Google Reviews |
| `backend/services/scrapers/justdial_scraper.py` | 93 | Google Places API (replaced JD) |
| `backend/services/scrapers/news_scraper.py` | 64 | Travel news |
| `backend/services/scrapers/ddg_scraper.py` | 84 | DuckDuckGo scraper |
| `backend/services/clients/serpapi_client.py` | 170 | SerpAPI wrapper |
| `backend/services/clients/google_maps_client.py` | 89 | Google Maps API wrapper |
| `backend/services/clients/weather_client.py` | 79 | Open-Meteo |
| `backend/services/clients/reddit_client.py` | 165 | Reddit API |
| `backend/services/langgraph/agent.py` | 329 | LangGraph agent |
| `backend/services/langgraph/tools/search_tools.py` | 83 | Search tool |
| `backend/services/langgraph/tools/review_tools.py` | 111 | Review tool |
| `backend/services/langgraph/tools/geo_tools.py` | 83 | Geo tool |
| `backend/services/langgraph/tools/weather_tools.py` | 11 | Weather tool |
| `backend/services/langgraph/tools/pricing_tools.py` | 64 | Pricing tool |
| `backend/services/langgraph/tools/news_tools.py` | 37 | News tool |

### 19.2 Frontend Files (10 files, ~1900 lines)

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/App.tsx` | — | Root component |
| `frontend/src/main.tsx` | — | Entry point |
| `frontend/src/index.css` | 157 | Design system |
| `frontend/src/context/AppContext.tsx` | 173 | Shared state |
| `frontend/src/components/SearchPanel.tsx` | 370 | Search + nearby |
| `frontend/src/components/AToBPanel.tsx` | 459 | A→B planner |
| `frontend/src/components/DiscoveryPanel.tsx` | ~100 | Results panel |
| `frontend/src/components/TripPanel.tsx` | ~80 | Trip planner |
| `frontend/src/components/MapView.tsx` | 165 | Leaflet map |
| `frontend/src/pages/MainPage.tsx` | 179 | App orchestrator |
| `frontend/src/services/api.ts` | 119 | API client |
| `frontend/src/types/index.ts` | 228 | 20 TS interfaces |
| `frontend/src/utils/helpers.ts` | 176 | Utilities |

### 19.3 Test Files (4 files)

| File | Lines | Purpose |
|------|-------|---------|
| `tests/__init__.py` | 0 | Package marker |
| `tests/conftest.py` | — | Fixtures |
| `tests/test_fare_engine.py` | — | 12 tests |
| `tests/test_segment_builder.py` | — | 9 tests |

### 19.4 Deleted Files (from Sprints 3-4)

| File | Lines | When |
|------|-------|------|
| `frontend/src/components/NewsOverlay.tsx` | 110 | Sprint 3 |
| `frontend/src/components/SegmentPanel.tsx` | 730 | Sprint 4 |
| `ml/data_preprocessor.py` | 64 | Sprint 3 |
| `scripts/test_*.py` (7 files) | ~200 | Sprint 3 |
| `_diag*.py`, `_debug*.py` (5 files) | ~250 | Sprint 3 |
| `scripts/migrate_to_postgres.py` | 120 | Sprint 3 |
| `api.ts` `getMiniPathOptions` | 10 | Sprint 3 |
| `routes.py` `/mini-path-options` | ~60 | Sprint 3 |

---

## 20. Appendix B: Fare Slab Tables

### 20.1 BMTC Ordinary Bus

| Distance (km) | Fare (₹) |
|---------------|----------|
| 0-2 | 6 |
| 2-5 | 12 |
| 5-10 | 16 |
| 10-20 | 22 |
| 20-30 | 28 |
| 30-40 | 32 |

### 20.2 BMTC AC Vajra

| Distance (km) | Adult Fare (₹) | Child Fare (₹) |
|---------------|----------------|-----------------|
| 0-5 | 15 | 8 |
| 5-10 | 20 | 10 |
| 10-20 | 35 | 18 |
| 20-40 | 45 | 23 |

### 20.3 Namma Metro

| Distance (km) | Fare (₹) |
|---------------|----------|
| 0-2 | 11 |
| 2-4 | 16 |
| 4-6 | 21 |
| 6-8 | 26 |
| 8-10 | 32 |
| 10-15 | 38 |
| 15-20 | 45 |

### 20.4 Ride Hailing (Formula-Based)

| Mode | Base | Per KM | Per Min | Min Fare | Seats |
|------|------|--------|---------|----------|-------|
| Uber Go / Ola Mini | ₹25 | ₹12 | ₹1.0 | ₹50 | 3 |
| Ola Mini | ₹25 | ₹12 | ₹1.0 | ₹50 | 3 |
| Uber Priority / Ola Prime | ₹50 | ₹24 | ₹1.5 | ₹100 | 3 |
| Uber XL / Ola XL | ₹100 | ₹30 | ₹2.0 | ₹150 | 6 |
| Auto | ₹15 | ₹9 | ₹0.5 | ₹25 | 3 |
| Rapido Bike / Uber Moto | ₹10 | ₹5 | ₹0.5 | ₹15 | 1 |
| Uber for Women | ₹25 | ₹12 | ₹1.0 | ₹50 | 3 |
| Uber Pet / Premier | ₹50 | ₹18 | ₹1.5 | ₹100 | 3 |

### 20.5 Personal Car

`fuel_cost = (distance_km / 15.0) * 110.0` 
(15 kmpl mileage, ₹110/liter petrol)

### 20.6 Train (Estimated)

`fare = max(15, round(distance_km * 0.8))` per person

### 20.7 Bus Fare Calculation

```python
# Used in segment_builder.py
bus_fare = max(6, round(db.get_bmtc_ordinary_fare(distance_km))) * group_size
ac_bus_fare = max(10, round(db.get_bmtc_ac_fare(distance_km))) * group_size
```

---

## 21. Appendix C: API Endpoint Quick Reference

| Method | Endpoint | Parameters | Timeout | Complexity |
|--------|----------|------------|---------|------------|
| POST | `/api/routes/plan` | `source_lat,source_lng,dest_lat,dest_lng,mode,budget,group_size,waypoints` | 30s (OSRM) | O(N) where N = route options |
| GET | `/api/routes/all-segments` | `from_lat,from_lng,dest_lat,dest_lng,group_size,budget,max_depth` | 20s (OSRM batch) | O(S × T) where S=segments, T=transit options |
| GET | `/api/routes/segment-step` | `from_lat,from_lng,dest_lat,dest_lng,group_size,budget` | 5s | O(N) |
| GET | `/api/routes/metro-stations` | `line?` | 200ms | O(1) |
| GET | `/api/routes/bus-stops` | `near_lat?,near_lng?,radius?` | 200ms | O(1) SpatialIndex |
| GET | `/api/routes/kia-routes` | none | 10ms | O(1) |
| GET | `/api/routes/transit-fares` | none | 10ms | O(1) |
| GET | `/api/routes/live-prices` | `source,dest,mode` | 8s (LLM) | O(1) |
| GET | `/api/routes/news` | `source_lat?,source_lng?,dest_lat?,dest_lng?` | 5s | O(1) |
| GET | `/api/routes/traffic-overlay` | `north,south,east,west` | 500ms | O(R) where R=roads |
| GET | `/api/search/places` | `q,lat?,lng?` | 3s | O(1) |
| GET | `/api/search/nearby` | `lat,lng,radius_km,place_type?` | 3s | O(1) |
| GET | `/api/search/suggestions` | `q` (≥2 chars) | 1s | O(1) |
| GET | `/api/search/verify-place` | `name,address?` | 3s | O(1) |
| GET | `/api/search/reviews` | `name,address?` | 5s | O(1) |
| GET | `/api/search/ride-prices` | `source,destination` | 8s | O(1) |
| GET | `/api/search/current-events` | `location?` | 3s | O(1) |
| GET | `/api/search/ai-chat` | `message,lat?,lng?` | 10s (LLM) | O(1) |
| POST | `/api/search/enrich-place` | `{name,lat,lng,place_type,address}` | 5s | O(1) |
| POST | `/api/langgraph/ask` | `{query,context}` | 30s (LLM chain) | O(T) where T = tool calls |
| GET | `/health` | none | 10ms | O(1) |

---

> **End of VOYAGER Complete Documentation**  
> This document covers all 4 sprints, 30+ bugs fixed, 20+ external APIs/services, 10+ data files, and every architectural decision with full reasoning.  
> **Total pages**: ~55 equivalent  
> **Last updated**: July 26, 2026
