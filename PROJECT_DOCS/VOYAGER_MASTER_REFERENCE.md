# VOYAGER — Master Project Reference

> **Last Updated:** July 29, 2026
> **Version:** 2.0.0
> **Status:** Active Development (Sprint 5 — Route Fixes & Hop Improvements)

---

## Table of Contents

1. [Project Overview & Vision](#1-project-overview--vision)
2. [Architecture & System Design](#2-architecture--system-design)
3. [Technology Stack](#3-technology-stack)
4. [Directory Structure](#4-directory-structure)
5. [Running the Project](#5-running-the-project)
6. [Quality Assurance](#6-quality-assurance)
7. [Performance Profile](#7-performance-profile)
8. [Sprint History & All Changes](#8-sprint-history--all-changes)
   - 8.1 Sprint 1 — Foundation & GTFS
   - 8.2 Sprint 2 — A* Graph & Real Paths
   - 8.3 Sprint 3 — Backend Refactoring
   - 8.4 Sprint 4 — Testing & Polish
   - 8.5 Sprint 5 — Route Fixes & Hop Improvements
   - 8.6 Sprint 5.1 — Latest Fixes (Jul 29)
9. [Complete Bug Fix Log](#9-complete-bug-fix-log)
10. [Backend Modules](#10-backend-modules)
11. [Frontend Components](#11-frontend-components)
12. [API Endpoints](#12-api-endpoints)
13. [Data Sources](#13-data-sources)
14. [Known Issues & Remaining Work](#14-known-issues--remaining-work)

---

## 1. Project Overview & Vision

VOYAGER is a comprehensive multi-modal transit navigation application specifically designed for Bengaluru, India. It provides real-time route planning across buses (BMTC), metro (Namma Metro), trains (Karnataka Railways), KIA airport buses, ride-hailing services (Uber/Ola/Rapido), personal vehicles, and walking routes.

**Core Mission:** To provide citizens of Bengaluru with a single unified platform that:
- Computes optimal multi-hop transit routes using real GTFS bus data, metro network data, and A* graph-based routing
- Shows live pricing from Uber, Ola, and Rapido via web scraping + Karnataka govt mandated rates
- Displays genuine Google Reviews for places (real SerpAPI data, not fake LLM-generated)
- Factors in live weather, traffic, crowd density, and time of day
- Uses proper multi-criteria decision analysis (TOPSIS) for route ranking
- Provides real driving/walking paths via OSRM (Open Source Routing Machine)
- Features a glassmorphism UI with dark theme, live GPS tracking, and multi-hop journey wizard

---

## 2. Architecture & System Design

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (Vite + React/TS)                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │SearchPanel│  │AToBPanel │  │Discovery │  │  MapView    │  │
│  │          │  │SegmentFlow│  │Panel     │  │  (Leaflet)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│                       AppContext (Shared State)              │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (localhost:8000)
┌──────────────────────────▼───────────────────────────────────┐
│                    Backend (FastAPI / uvicorn)                │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐   │
│  │ TransitService │  │ SegmentBuilder  │  │ TransitConfig   │   │
│  │ (Facade, 534L)  │  │ (1283L, 17 fns) │  │ (Consts + Pure) │   │
│  └──────┬──────┘  └──────┬───────┘  └────────┬──────────┘   │
│         │               │                    │              │
│  ┌──────▼──────┐  ┌─────▼──────┐  ┌─────────▼────────┐    │
│  │ TransitGraph  │  │ TransitPaths │  │ TransitScoring   │    │
│  │ (A* Astar)    │  │ (OSRM paths)  │  │ (TOPSIS)         │    │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────┘    │
│         │               │                                   │
│  ┌──────▼──────────────▼──────────┐                         │
│  │       GTFS Service              │                        │
│  │  (7271 shapes, 5077 stops,     │                         │
│  │   429882 times, pickle cache)   │                         │
│  └─────────────────────────────────┘                         │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ FareEngine   │  │ Database     │  │ LangGraph Agent   │  │
│  │ (Surge calc)  │  │ (Spatial idx) │  │ (Tool registry)  │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Scrapers     │  │ API Clients  │  │ TrainService     │  │
│  │ (Ride, Rev)  │  │ (GMaps,Serp) │  │ (eRail.in live)  │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                           │
                ┌──────────┴──────────┐
                │  OSRM (localhost)    │
                │  5000 = car         │
                │  5001 = foot        │
                └─────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Backend | Python 3.10+ | FastAPI, uvicorn |
| Frontend | Vite 5 + React 18 | TypeScript strict |
| Map | Leaflet | Custom markers, dynamic geometry |
| Routing | OSRM | Car (5000), Foot (5001) |
| GTFS | BMTC Bangalore | Pickle-cached (0.65s load) |
| ML | NumPy TOPSIS | Multi-criteria route ranking |
| A* Graph | Custom | 2939 nodes, ~54000 edges |
| Container | Docker Compose | Backend, Frontend, OSRM |
| ORM | SQLAlchemy 2.x | Pydantic v2 models |
| Scraping | httpx, BeautifulSoup | Ride pricing, reviews |
| API Clients | Google Maps, SerpAPI, Open-Meteo | Async HTTP |

---

## 4. Directory Structure

```
VOYAGER/
├── backend/
│   ├── main.py                          # FastAPI entry point
│   ├── models/
│   │   ├── route_models.py              # Pydantic request/response models
│   │   └── search_models.py             # Search request/response models
│   ├── core/
│   │   ├── config.py                    # Settings (env vars, pydantic)
│   │   ├── database.py                  # TransitDatabase (spatial indexes)
│   │   └── deps.py                      # FastAPI dependencies
│   ├── services/
│   │   ├── transit_service.py           # TransitService facade (~534 lines)
│   │   ├── segment_builder.py           # TripSegmentBuilder (1283 lines)
│   │   ├── transit_config.py            # Constants, geo math, GTFS helpers
│   │   ├── transit_graph.py             # TransitAstarGraph (A* routing)
│   │   ├── transit_scoring.py           # TOPSIS multi-criteria scoring
│   │   ├── transit_paths.py             # OSRM path fetching, interpolation
│   │   ├── fare_engine.py               # Surge pricing, fare calculations
│   │   ├── gtfs_service.py              # BMTC GTFS loader (752 lines)
│   │   ├── train_service.py             # eRail.in live train scraper
│   │   ├── geocoding.py                 # Place search, reverse geocode
│   │   ├── review_tools.py              # Google Reviews via SerpAPI
│   │   ├── cache_manager.py             # Async file cache
│   │   ├── langgraph/                   # LangGraph agent framework
│   │   │   ├── graph.py                 # VoyagerLangGraph
│   │   │   └── tools/                   # Tool registry
│   │   ├── scrapers/
│   │   │   ├── ride_scraper.py          # Uber/Ola/Rapido pricing
│   │   │   ├── google_reviews_scraper.py
│   │   │   ├── justdial_scraper.py      # BROKEN (site not responding)
│   │   │   └── ddg_scraper.py
│   │   └── clients/
│   │       ├── google_maps_client.py    # Distance matrix, geocode
│   │       ├── serpapi_client.py        # Place search, details, reviews
│   │       ├── weather_client.py        # Open-Meteo
│   │       └── reddit_client.py         # News scraping
│   ├── agents/
│   │   └── llm_agent.py                 # LLMAgent (OpenRouter/Gemini)
│   └── routes/
│       ├── routes_router.py             # /api/routes/*
│       └── search_router.py             # /api/search/*
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css                    # Design system (glassmorphism)
│   │   ├── types/                       # TypeScript type definitions
│   │   ├── context/
│   │   │   └── AppContext.tsx           # Shared state
│   │   ├── pages/
│   │   │   └── MainPage.tsx             # Orchestrator
│   │   ├── components/
│   │   │   ├── SearchPanel.tsx          # Search + nearby categories
│   │   │   ├── AToBPanel.tsx            # A→B planning orchestrator
│   │   │   ├── SegmentFlowView.tsx      # Multi-hop wizard (hop-by-hop)
│   │   │   ├── MapView.tsx              # Leaflet map + markers
│   │   │   ├── DiscoveryPanel.tsx        # Place details, reviews, scores
│   │   │   ├── HeaderBar.tsx            # Top bar
│   │   │   ├── TripPanel.tsx            # AI trip planner
│   │   │   └── NewsPopup.tsx            # News/traffic overlay
│   │   └── api/
│   │       └── client.ts                # API client
│   ├── package.json
│   └── vite.config.ts
├── ml/
│   ├── astar.py                         # A* transit graph pathfinder
│   └── topsis.py                        # NumPy TOPSIS ranking
├── tests/
│   ├── test_fare_engine.py              # 15 test cases
│   └── test_segment_builder.py           # 8 integration tests
├── data_cache/
│   ├── bengaluru_metro_network.csv      # Metro station data
│   ├── bangalore_bus_stops.csv          # Bus stop locations
│   ├── bmtc_gtfs.zip                    # Raw GTFS ZIP
│   └── gtfs_cache.pkl                   # Pickle cache (shapes, stops, times)
├── PROJECT_DOCS/
│   ├── VOYAGER_COMPLETE_REFERENCE.md
│   ├── VOYAGER_DOCUMENTATION.md
│   └── VOYAGER_MASTER_REFERENCE.md      # THIS FILE
├── AGENTS.md                            # AI assistant guide
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 5. Running the Project

```powershell
# Backend
cd VOYAGER
python -m uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend; npx vite --port 3000

# OSRM (Docker)
docker compose up -d osrm-car

# Override test time (for daytime bus schedules):
$env:VOYAGER_TEST_TIME = "2024-01-01 11:00:00"
```

---

## 6. Quality Assurance

| Check | Command | Status |
|-------|---------|--------|
| Backend tests | `pytest tests/ -q` | 21/21 pass |
| Frontend typecheck | `npx tsc --noEmit` | Zero errors |
| Backend imports | `python -c "from backend.services...import..."` | All compile |
| Backend startup | `python -m uvicorn backend.main:app` | ~10.6s total |

---

## 7. Performance Profile

| Metric | Value | Notes |
|--------|-------|-------|
| GTFS cache load | 0.65s | Pickle deserialize (7271 shapes, 5077 stops, 429882 times) |
| Bus stop pre-resolve | 7.7s | First run only; cached in gtfs_cache.pkl afterward |
| A* graph build | 2.2s | 2939 nodes, ~54000 edges (haversine + dist cache) |
| Server startup | ~10.6s | All caches warm |
| API route plan | <1s | With warm caches |
| Pre-resolved names | 1696/2972 | In gtfs_cache.pkl:name_map |
| Unresolvable names | 14/2972 | Acronyms like "hnrj", "ggmc", "pesitelc" |

---

## 8. Sprint History & All Changes

### 8.1 Sprint 1 — Foundation & GTFS

- Initial GTFS data loader for BMTC Bangalore buses
  - Parses routes.txt, trips.txt, stop_times.txt, shapes.txt
  - Pickle-based caching (~0.65s load)
  - 7271 shapes, 5077 stops, 429882 time entries
- CSV-based bus stop database with spatial indexing (KDTree)
- Metro network data from bengaluru_metro_network.csv
- Basic fare calculation (ordinary, AC Vajra, metro)
- Route plan API (`POST /api/routes/plan`)
- TransitService facade with segment building

### 8.2 Sprint 2 — A* Graph & Real Paths

- Custom A* transit graph (2939 nodes, ~54000 edges)
  - Bus → bus transfers, bus → metro walk edges
  - Haversine distance + distance cache (no geodesic bottleneck)
  - Pre-built at startup for instant API responses
- OSRM car integration (port 5000, road-following driving paths)
- TOPSIS multi-criteria route ranking (numpy-based)
- Ride pricing via Uber/Ola/Rapido scraping
- Train data via eRail.in API scraping (22 Karnataka station codes)
- Metro direction filter and circular stop detection

### 8.3 Sprint 3 — Backend Refactoring

**52 files changed, net -2703 lines**

- Extracted module-level constants & pure functions from transit_service.py into `transit_config.py` (~209 lines)
- Created `segment_builder.py` (1283 lines, 17 methods extracted from transit_service.py)
- Created `fare_engine.py` (33 lines, centralized surge multiplier)
- Created `transit_graph.py` (TransitAstarGraph)
- Created `transit_scoring.py` (TOPSIS scoring)
- Created `transit_paths.py` (OSRM path service)
- Reduced transit_service.py from 2422→1917→579 lines (facade pattern)
- Fixed critical `_gtfs` import-by-value bug (all GTFS caches were returning empty)
- **Dead code deleted:**
  - NewsOverlay.tsx (unused component)
  - ml/data_preprocessor.py (unused)
  - 12 test/diagnostic scripts
  - mini-path-options endpoint + frontend function
  - 5 dead TypeScript types
  - requirements.txt cleaned (scikit-learn, networkx, shapely removed)
- A* graph [:300] bus-metro walk limit removed — all 2933 bus stops now connected for transfers

### 8.4 Sprint 4 — Testing & Polish

- **pytest setup**: test_fare_engine.py (15 test cases) + test_segment_builder.py (8 integration tests) = 21 tests
- Score color unified: MapView.tsx, DiscoveryPanel.tsx now call `getScoreColor(score*100)`
- Bare except fixed: `except:` → `except (json.JSONDecodeError, TypeError):`
- SegmentPanel.tsx deleted (730 lines, zero imports, dead code)
- **~55MB unused datasets deleted:**
  - rides_data.csv, bangalore_ride_data.csv
  - metro_per_hour*.csv (4 files)
  - NammaMetro_Ridership_Dataset.csv
  - bangalore-wards-*.csv (4 files)
  - KIA_stops_fare_incomplete.json
  - metro.csv
- **GTFS ~41s startup block removed**: `_ensure_gtfs()` removed from `main.py`; TransitService defers graph build via lazy `astar_graph` property
- **SegmentPanel dark theme**: Hardcoded dark colors replaced with CSS variable references
- **bus_nan names filtered**: database.py skips stops with name "nan"/"none"/"null"
- **Bus→metro CASE 2 fix**: When source has no nearby metro, now searches ALL metro stations instead of just source-nearby list

### 8.5 Sprint 5 — Route Fixes & Hop Improvements

- **Walk as standalone transit hop**: Walk option (≤2km, free) added alongside bus/metro/train in transit options
- **Metro→bus chaining**: Metro options now include `_build_next_transit()` for onward transit from arrival metro station
- **GTFS name variant fallback**: `_cached_shape_path` falls back to stripping space-delimited suffix; `_cached_shape_between` uses `_resolve_name()` on first miss
- **Search place verification**: `search_places()` tightened Bangalore radius 50→15km, added ≥40% keyword overlap filter
- **Cache invalidation**: review_tools.py `_CACHE_VERSION = 2` invalidates stale reliability scores
- **Always recompute reliability_score from rating**: Never blindly trusts external score
- **Dead import removed**: `google_reviews_scraper` import removed from review_tools.py

- **Real reviews via SerpAPI**: review_tools.py fixed broken SerpAPI flow (was calling `_parse_place_detail` on search response instead of `search_places` → `place_id` → `place_details`)
- **SerpAPI key fix**: Response key `"place"` → `"place_results"`; review data is in `place_results.user_reviews.most_relevant` not `place_results.reviews` (which is an int count)
- **Real ride pricing**: Updated with Karnataka govt-mandated rates (Uber Go/Ola Mini ₹24/km, Uber XL ₹32/km, Auto ₹20/km, Rapido Bike ₹5/km) + first-N-km-free slab logic
- **Ride fare per-person bug fixed**: Was multiplying vehicle fare by passenger count (`total = pp * group_size`); now `total = _calc_ride_fare(...)` (vehicle fare) and `pp = round(total / group_size)` (per-person share)

- **Metro direction filter too aggressive (Issue 9)**: Removed `dest_to_dm > nm_dist_to_dest * 1.1` check; valid metro routes (e.g., Cubbon Park→MG Road) now appear
- **Circular routing via 300m radius (Issue 10)**: `_is_visited()` radius increased 300m→800m

### 8.6 Sprint 5.1 — Latest Fixes (Jul 29)

- **Path coordinate format bug**: SegmentFlowView.tsx was swapping `[lat,lng]`→`[lng,lat]` in 9 places; Leaflet expects `[lat,lng]` which is what backend already returns
- **Real OSRM walk paths**: `transit_paths.py:interpolate_path()` now tries synchronous OSRM foot (port 5001) first for walkable distances ≤3km
- **Path shown after each segment confirm**: `SegmentFlowView.tsx:handleConfirmTransit()` now calls `onRouteGeometry(accGeo)` immediately after each confirmation, not just at journey end
- **Destination marker on card click**: `MainPage.tsx:onSelectPlace` calls `setDstLoc` + `setDstQ` so clicking a search result card sets the red destination pin
- **Full-shape fallback removed**: `segment_builder.py` removed `full_shape` from path fallback chain (lines 882, 907, 1218); was drawing entire bus route (e.g., NES Office→Doddaballapura, 29 stops, 265 coordinate points) instead of stop-to-stop segment
- **GTFS time filter fallback**: `gtfs_service.py:get_all_routes_at_stop()` falls back to all departures when future-departure filtering returns empty
- **Direction filter rewritten**: `transit_config.py:_route_goes_toward_dest()` rewritten with:
  - Early-return True when either route endpoint is closer to destination than source
  - Handles routes that start/end at the source stop
  - Uses approach direction when closest shape point is at endpoint
  - cos_angle threshold relaxed 0.5→0.3
- **Distance check absolute**: `segment_builder.py` direction distance check changed from relative `* 0.90` to absolute `+ 0.5` tolerance

---

## 9. Complete Bug Fix Log

| # | Issue | Fix | File(s) | Sprint |
|---|-------|-----|---------|--------|
| 1 | GTFS caches returning empty | Fixed `_gtfs` import-by-value bug (was referencing stale module-level var) | transit_service.py, transit_config.py | S3 |
| 2 | A* graph only connected 300 bus stops | Removed `[:300]` limit; now adds walk edges for all 2933 bus stops | transit_graph.py | S3 |
| 3 | Bus→metro CASE 2 empty results | Was using empty `metro_stations` (source-nearby list); now uses full `db.metro_stations` | transit_service.py | S3 |
| 4 | GTFS 41s startup block | Removed `_ensure_gtfs()` from main.py; lazy `astar_graph` property | main.py, transit_service.py | S4 |
| 5 | 55MB unused datasets | Deleted 10 files (old CSVs, JSONs) | data_cache/ | S4 |
| 6 | SegmentPanel dark colors hardcoded | Replaced with CSS variable references | SegmentPanel.tsx | S4 |
| 7 | bus_nan names in database | Filters stops with name "nan"/"none"/"null" | database.py | S4 |
| 8 | Score colors inconsistent | Unified via `getScoreColor(score*100)` | MapView.tsx, DiscoveryPanel.tsx | S4 |
| 9 | Bare except catching too much | `except:` → `except (json.JSONDecodeError, TypeError)` | config.py | S4 |
| 10 | Metro routes filtered out incorrectly | Removed `dest_to_dm > nm_dist_to_dest * 1.1` check | transit_service.py | S5 |
| 11 | Circular routing (infinite loop) | `_is_visited()` radius 300m→800m | transit_service.py | S5 |
| 12 | SerpAPI reviews always empty | Fixed flow: `search_places` → `place_id` → `place_details` (was calling wrong method) | review_tools.py | S5 |
| 13 | SerpAPI key `"place"` wrong | Changed to `"place_results"`; review fields `username`/`description` not `user.name`/`snippet` | serpapi_client.py | S5 |
| 14 | Ride pricing not showing | Updated with Karnataka govt rates + slab logic + SerpAPI fallback | ride_scraper.py, transit_service.py | S5 |
| 15 | Ride fare * passenger count bug | `total = pp * group_size` → `total = _calc_ride_fare(...); pp = total / group_size` | transit_service.py | S5 |
| 16 | LLM generating fake reviews | Removed LLM fallback; real SerpAPI only | review_tools.py | S5 |
| 17 | Name resolution slow (79s) | Replaced SequenceMatcher with trigram-filtered `get_close_matches` | gtfs_service.py | S5 |
| 18 | A* graph build slow (11.6s) | Replaced `geodesic` with `_haversine_dist` + `_dist_cache` dict | transit_graph.py | S5 |
| 19 | Path coords swapped (lat↔lng) | Fixed 9 occurrences of `[c[1], c[0]]` → `[c[0], c[1]]` | SegmentFlowView.tsx | S5.1 |
| 20 | Map shows entire bus route | Removed `full_shape` fallback; uses stop-to-stop `shape_path` or interpolated only | segment_builder.py | S5.1 |
| 21 | Walk paths straight lines | Added OSRM foot (port 5001) synchronous call for walkable distances ≤3km | transit_paths.py | S5.1 |
| 22 | Path not shown until journey end | `onRouteGeometry(accGeo)` called after each confirmation | SegmentFlowView.tsx | S5.1 |
| 23 | Destination pin not set on card click | `setDstLoc` + `setDstQ` added to `onSelectPlace` | MainPage.tsx | S5.1 |
| 24 | GTFS time filter returns empty | `get_all_routes_at_stop()` falls back to all departures | gtfs_service.py | S5.1 |
| 25 | Routes terminating at source filtered out | `_route_goes_toward_dest()` rewritten with endpoint check, approach direction, relaxed angle 0.5→0.3 | transit_config.py | S5.1 |
| 26 | Distance check too aggressive | `* 0.90` (10% improvement) → `+ 0.5` (absolute 0.5km tolerance) | segment_builder.py | S5.1 |

---

## 10. Backend Modules

### TransitService (`backend/services/transit_service.py`) — ~534 lines
Facade that composes all sub-modules. Entry point for route planning. Methods:
- `get_segments(from, to)` — Build multi-hop segments
- `get_segment_step_options(...)` — Get options for a specific step
- `get_route_legs_public(...)` — Return route legs for direct display
- `get_all_segments(...)` — Full multi-hop segment building pipeline

### SegmentBuilder (`backend/services/segment_builder.py`) — 1283 lines, 17 methods
Core routing engine. Key methods:
- `_add_transit_options()` — Add bus, metro, train, walk options at a stop
- `_build_next_transit()` — Recursively build onward transit from arrival stop
- `_cached_shape_path()` / `_cached_shape_between()` — GTFS shape lookup with caching
- `_astar_route_paths()` — A* enriched multi-hop route conversion
- `get_segment_step_options()` — Main entry: build all options for a segment step
- `_add_final_walk()` — Add walk options for reaching destination
- `_add_direct_ride_options()` — Uber/Ola/Rapido options

### TransitConfig (`backend/services/transit_config.py`) — ~250 lines
Constants (ride types, train data, metro hubs) and pure functions:
- `_haversine_dist()` — Fast haversine distance
- `_route_goes_toward_dest()` — Direction filter using shape path and cosine angle
- `_is_bus_running_now()` — Check if bus route is currently operating
- `_is_metro_operating()` — Check metro hours (05:00–23:30)
- `_ensure_gtfs()` — Lazy GTFS loader singleton

### TransitGraph (`backend/services/transit_graph.py`)
- `TransitAstarGraph` — Builds A* graph with bus→bus and bus→metro walk edges
- Uses haversine + distance cache for edge weights

### TransitScoring (`backend/services/transit_scoring.py`)
- `topsis_score_routes()` — Rank routes by distance, duration, fare (equal weights)

### TransitPaths (`backend/services/transit_paths.py`) — 138 lines
- `interpolate_path()` — Synchronous: tries OSRM foot first (≤3km), falls back to interpolated
- `get_osrm_path_between()` — Async OSRM path fetching with cache
- `add_leg_paths()` — Resolve paths for all legs in a route
- `get_driving_route()` — Full OSRM driving route with turn-by-turn steps

### FareEngine (`backend/services/fare_engine.py`) — 33 lines
- `calc_fare_with_surge()` — Apply time-based surge multiplier
- `get_mode_by_id()` — Map mode ID to name/icon
- `ride_fare_range()` — Per-km pricing for ride types

### GTFS Service (`backend/services/gtfs_service.py`) — 752 lines
- Loads BMTC GTFS ZIP → pickle cache (7271 shapes, 5077 stops, 429882 times)
- `get_shape_path_for_route()` — Full route shape
- `get_shape_between_stops()` — Shape segment between two stops
- `get_route_stops()` — Stops along a route with departure times
- `find_stops_on_route_toward_dest()` — Find stops ordered by shape sequence toward destination
- `get_all_routes_at_stop()` — All routes serving a stop
- `_fast_fuzzy_match()` — Trigram-filtered get_close_matches for name resolution
- `clean_route_short_name()` — Strips terminal suffixes (e.g., "MF-28 ..." → "MF-28")

### Database (`backend/core/database.py`)
- KDTree spatial index for bus stops and metro stations
- `find_nearby_bus_stops(lat, lng, radius_km)`
- `find_nearby_metro_stations(lat, lng, radius_km)`
- `get_metro_line_path(from_name, to_name)` — Metro line segment
- `get_bmtc_ordinary_fare(dist)` / `get_bmtc_ac_fare(dist)` / `get_metro_fare(dist)`

### Train Service (`backend/services/train_service.py`)
- eRail.in API live scraping for 22 Karnataka station codes
- 7 city-pair fallbacks for common routes
- Cached async fetching

### Review Tools (`backend/services/review_tools.py`)
- `get_place_reviews()` — SerpAPI → proxy-scrape → fallback chain
- Versioned cache (`_CACHE_VERSION = 2`)
- Reliability score from rating (no LLM fake reviews)

### Geocoding (`backend/services/geocoding.py`)
- `search_places()` — Combined OSM Nominatim + Google Maps + cache
- Bangalore radius 15km, ≥40% keyword overlap filter
- `_score_from_rating()` — Converts rating to 0-1 reliability score

---

## 11. Frontend Components

### MainPage (`src/pages/MainPage.tsx`)
Orchestrator with sidebar + map layout. Manages source/destination state via `AppContext`.
- `onSelectPlace` — Sets destination lat/lng + query
- Routes: plan → show segments → step through SegmentFlow

### AToBPanel (`src/components/AToBPanel.tsx`)
A→B planner with tabs: Public/Transport, Direct, Drive, Walk.
- Fetches route plan, segments, ride prices
- `handleRouteGeometry` — Renders paths on map (OSRM routes, segment paths)
- `SegmentFlowView` — Multi-hop step-through wizard

### SegmentFlowView (`src/components/SegmentFlowView.tsx`)
Multi-hop journey wizard. Shows hop-by-hop options:
- `handleSelectTransit` — Pick a transit option for current segment
- `handleConfirmTransit` — Confirm choice, advance to next segment, accumulate path on map
- Shows walk → bus/metro/train → walk chain for each segment

### MapView (`src/components/MapView.tsx`)
Leaflet map with:
- Colored markers (blue=source, red=dest, green=user GPS)
- Dynamic geometry layers (walks, bus paths, metro lines)
- GPS live tracking via watchPosition
- Score-based color badges

### DiscoveryPanel (`src/components/DiscoveryPanel.tsx`)
Right-side glass panel with place details, reviews, reliability scores, images.

### SearchPanel (`src/components/SearchPanel.tsx`)
Search nearby with category chips (restaurants, hospitals, etc.) and radius slider.

### TripPanel (`src/components/TripPanel.tsx`)
AI trip planner with itinerary suggestions.

### Design System (`src/index.css`)
- Glassmorphism (backdrop-filter blur, ambient shadows)
- CSS variables for dark theme
- Transition-based score colors (green/yellow/red at 0.7/0.4 thresholds)

---

## 12. API Endpoints

### Route Planning
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/routes/plan` | A→B route planning (legs, modes, fares) |
| GET | `/api/routes/all-segments` | Multi-hop transit segments |
| GET | `/api/routes/extend-segment` | Extend segment with onward transit |
| GET | `/api/routes/ride-prices` | Uber/Ola/Rapido pricing |
| GET | `/api/routes/news` | Traffic news |
| GET | `/api/routes/traffic-overlay` | Traffic overlay data |
| GET | `/api/routes/metro-stations` | Metro station list |
| GET | `/api/routes/bus-stops` | Bus stop list |
| GET | `/api/routes/transit-fares` | Transit fare table |
| GET | `/api/routes/live-prices` | Live ride prices |

### Search
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/search/places` | Search places by name |
| GET | `/api/search/nearby` | Nearby places (categories, radius) |
| GET | `/api/search/suggestions` | Autocomplete suggestions |
| GET | `/api/search/verify-place` | Verify place coordinates |
| GET | `/api/search/reviews` | Google Reviews for a place |
| GET | `/api/search/ride-prices` | Ride price estimate |
| GET | `/api/search/current-events` | Current events / traffic news |
| GET | `/api/search/ai-chat` | AI chat about places |
| POST | `/api/search/enrich-place` | Enrich place with reviews + scores |

### LangGraph
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/langgraph/ask` | Full reasoning loop with tool registry |

---

## 13. Data Sources

| Source | Data | Format | Frequency |
|--------|------|--------|-----------|
| BMTC GTFS | Bus routes, stops, times, shapes | ZIP → Pickle | Static (loaded at startup) |
| Namma Metro Network | Metro stations, lines, positions | CSV | Static |
| Bangalore Bus Stops | Bus stop names + coordinates | CSV | Static |
| OSRM Car | Driving routes, turn-by-turn | Docker (port 5000) | On demand |
| OSRM Foot | Walking paths | Docker (port 5001) | On demand |
| Uber/Ola/Rapido | Live ride pricing | Proxy scraping + formula fallback | On demand |
| SerpAPI | Place details, Google Reviews | HTTP API | On demand (cached) |
| Google Maps | Geocoding, distance matrix | HTTP API | On demand (cached) |
| Open-Meteo | Weather data | HTTP API | On demand |
| eRail.in | Live train schedules | HTTP scraping | On demand |
| OpenStreetMap | Place search | Nominatim API | On demand |

---

## 14. Known Issues & Remaining Work

### Current Issues
- **OSRM Foot OOM**: Container gets OOM-killed during PBF customize. Current workaround: sync HTTP request with 1.5s timeout — works for small walks ≤3km. Need smaller PBF extract or more RAM.
- **JustDial scraper broken**: Site not responding; no fix expected (external).
- **Yelahanka metro station missing**: Green Line extension (Yelahanka station) not in bengaluru_metro_network.csv. Need to add coordinates and line path.
- **Bus→metro CASE 2 scoring**: Reverse-direction routes (bus past destination then metro back) not excluded effectively. Scoring needs refinement.

### Fixed/Running
- OSRM foot container IS running (port 5001) — responds in ~6.8s for 9.5km walks
- All 21 backend tests pass
- Frontend TypeScript compiles with zero errors
- GTFS loads in 0.65s (pickle cache)
- A* graph builds in 2.2s (2939 nodes)
- Direction filter handles routes at source/destination stops
- Walk paths use real OSRM road-following geometry
- Bus paths show stop-to-stop segments (not full route)

### Monitoring
- Reddit news scraper failing: `'NoneType' object is not iterable` — non-critical, degrades gracefully
- AI suggestions failing: All OpenRouter models fail — fallback to basic text matching works
- Travel recs timing out occasionally — graceful timeout handling in place
