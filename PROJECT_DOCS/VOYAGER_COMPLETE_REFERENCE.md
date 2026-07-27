# VOYAGER — Complete Project Reference

> **Last Updated:** July 27, 2026  
> **Version:** 1.0.0  
> **Status:** Active Development (Sprint 4 — Testing & Polish)

---

## Table of Contents

1. [Project Overview & Vision](#1-project-overview--vision)
2. [Architecture & System Design](#2-architecture--system-design)
3. [Technology Stack](#3-technology-stack)
4. [Directory Structure](#4-directory-structure)
5. [Sprint History & Achievements](#5-sprint-history--achievements)
6. [Backend Deep Dive](#6-backend-deep-dive)
   - 6.1 TransitService (Facade)
   - 6.2 SegmentBuilder (TripSegmentBuilder)
   - 6.3 TransitConfig (Constants & Pure Functions)
   - 6.4 TransitGraph (A* Graph)
   - 6.5 TransitScoring (TOPSIS)
   - 6.6 TransitPaths (OSRM)
   - 6.7 FareEngine
   - 6.8 GTFS Service
   - 6.9 Database (TransitDatabase)
   - 6.10 Geocoding
   - 6.11 Train Service
   - 6.12 Proxy Manager
   - 6.13 Images
   - 6.14 FastAPI Routes
   - 6.15 Search API
   - 6.16 Scrapers
   - 6.17 API Clients
   - 6.18 LangGraph Agent
7. [Frontend Deep Dive](#7-frontend-deep-dive)
   - 7.1 AppContext (State Management)
   - 7.2 MainPage (Orchestrator)
   - 7.3 AToBPanel (Route Planner)
   - 7.4 SegmentFlowView (Multi-Hop Wizard)
   - 7.5 SearchPanel
   - 7.6 MapView (Leaflet)
   - 7.7 DiscoveryPanel
   - 7.8 HeaderBar
   - 7.9 NewsPopup
   - 7.10 TripPanel
   - 7.11 API Client
   - 7.12 Type System
   - 7.13 Design System (CSS)
8. [Data Sources & Integration](#8-data-sources--integration)
9. [External APIs](#9-external-apis)
10. [Docker & OSRM Setup](#10-docker--osrm-setup)
11. [Performance Profile & Optimizations](#11-performance-profile--optimizations)
12. [Issues & Fixes](#12-issues--fixes)
13. [Testing Strategy](#13-testing-strategy)
14. [Environment Configuration](#14-environment-configuration)
15. [Running the Project](#15-running-the-project)
16. [Future Roadmap](#16-future-roadmap)

---

## 1. Project Overview & Vision

### 1.1 What is VOYAGER?

VOYAGER is a **multi-modal transit navigation web application** purpose-built for **Bengaluru, India**. It combines:

- **Real GTFS (General Transit Feed Specification) data** for BMTC buses (7,271 shapes, 5,077 stops, 429,882 timetable entries)
- **Namma Metro data** (Purple Line: 37 stations, Green Line: 32 stations, Yellow Line: 16 stations)
- **Karnataka railway station data** (22 station codes mapped)
- **Real-time ride-hailing price estimates** (Uber, Ola, Rapido via SerpAPI + proxy scraping + formula fallback chain)
- **Live weather data** (Open-Meteo API)
- **Live traffic news** (Reddit + DDG search + SerpAPI news)
- **Real Google Reviews** (SerpAPI → proxy-scrape → fallback chain)
- **Actual road-following paths** via local OSRM (Open Source Routing Machine) on Docker
- **A* graph-based transit routing** for bus + metro + train multi-hop journeys
- **TOPSIS multi-criteria scoring** for route ranking

### 1.2 Core Philosophy

1. **Real Data First** — No hardcoded fake data. Every piece of information must come from a live source (GTFS, API, scraper, or formula with real parameters).
2. **Progressive Discovery** — Users can explore nearby places, plan A→B routes, and access trip insights through a unified interface.
3. **Glassmorphism Design** — Modern UI with backdrop-filter blur, ambient shadows, and a cohesive design system.
4. **Multi-Modal by Default** — Every journey considers buses, metro, walking, cabs, autos, and bikes — ranked by TOPSIS score.
5. **Transparency** — Score explanations show users WHY a route is recommended, with live factors (weather, traffic, crowd density, DL/NL/EV awareness).

### 1.3 Target Users

- Daily commuters in Bengaluru looking for optimal multi-modal routes
- Travelers exploring the city who need transit-aware navigation
- Users who want real-time price comparisons across ride-hailing platforms
- People who value transparency in route recommendations (score explanations)

### 1.4 Key Differentiators vs Google Maps

| Feature | Google Maps | VOYAGER |
|---------|------------|---------|
| TOPSIS scoring with explanation | ✗ | ✓ |
| Real ride prices (Uber/Ola/Rapido) | ✗ | ✓ |
| AI review summaries | ✗ | ✓ |
| Live weather in routing decisions | ✗ | ✓ |
| Multi-hop transit wizard | ✗ | ✓ |
| Glassmorphism design | ✗ | ✓ |
| Open-source, self-hosted | ✗ | ✓ |
| Real GTFS bus data | ✓ | ✓ |
| Actual road-following paths | ✓ | ✓ (via OSRM) |
| Traffic-aware routing | ✓ | ✓ (Google Distance Matrix) |

---

## 2. Architecture & System Design

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND (React/TS)                     │
│                         Port 3000                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Search   │ │ A→B      │ │ Trip     │ │ MapView      │   │
│  │ Panel    │ │ Panel    │ │ Panel    │ │ (Leaflet)    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│        │            │            │              │            │
│        └────────────┴────────────┴──────────────┘            │
│                         │ HTTP/JSON                          │
└─────────────────────────┼────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────┐
│              BACKEND (FastAPI/Uvicorn)                        │
│                    Port 8000                                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              TransitService (Facade)                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │
│  │  │Segment   │ │Transit   │ │Transit   │ │Transit │ │    │
│  │  │Builder   │ │Graph     │ │Scoring   │ │Paths   │ │    │
│  │  │(A*+GTFS) │ │(A* Graph)│ │(TOPSIS)  │ │(OSRM)  │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │
│  │  │Fare     │ │GTFS     │ │Geocoding│ │Train   │ │    │
│  │  │Engine   │ │Service  │ │          │ │Service │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │    │
│  │  │LLM Agent│ │Scrapers │ │LangGraph Agent       │ │    │
│  │  └──────────┘ └──────────┘ └──────────────────────┘ │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────┬────────────────────────────────────┘
                          │
┌─────────────────────────┼────────────────────────────────────┐
│              EXTERNAL INTEGRATIONS                             │
│  ┌──────────────────┐ ┌──────────────────┐                   │
│  │ OSRM Car (Docker)│ │ OSRM Foot (Docker│                   │
│  │ Port 5000        │ │ Port 5001 (OOM)  │                   │
│  └──────────────────┘ └──────────────────┘                   │
│  ┌──────────────────┐ ┌──────────────────┐                   │
│  │ SerpAPI          │ │ Google Maps API  │                    │
│  │ (Reviews+Shopping)│ │ (Distance Matrix)│                    │
│  └──────────────────┘ └──────────────────┘                   │
│  ┌──────────────────┐ ┌──────────────────┐                   │
│  │ Open-Meteo (Wx)  │ │ eRail.in (Trains)│                   │
│  └──────────────────┘ └──────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow: Route Planning

```
User clicks "Find Routes"
  │
  ▼
AToBPanel.tsx handleFindRoutes()
  │
  ├── transportType === 'direct' (Ride Options):
  │     │
  │     ├── GET /api/search/ride-prices → SerpAPI → Proxy → Formula fallback
  │     │     Returns: Uber, Ola, Rapido price estimates
  │     │
  │     └── POST /api/routes/plan (mode=personal)
  │           → OSRM car route → Haversine fallback
  │           Returns: Driving route with geometry (for map display)
  │
  ├── transportType === 'segment' (Multi-Hop Transit):
  │     │
  │     ├── POST /api/routes/plan (mode=public)
  │     │     → TransitService.plan_route()
  │     │       → TransitAstarGraph (A* pathfinding on GTFS graph)
  │     │       → TOPSIS ranking (topsis_score_routes)
  │     │       → OSRM path interpolation for walk/ride legs
  │     │       → LLM travel insights
  │     │     Returns: Ranked route options with legs, scores, explanations
  │     │
  │     └── GET /api/routes/all-segments
  │           → TransitService.get_all_segments()
  │             → TripSegmentBuilder.get_all_segments()
  │               → _build_single_segment() for each depth level
  │                 → _add_direct_options() (walk, cab, auto, bike)
  │                 → find_nearby_bus_stops() / metro / railway
  │                 → _add_reach_options() (how to reach each stop)
  │                 → _add_transit_options() (GTFS buses, metro from each stop)
  │                 → _astar_route_paths() (A* multi-hop suggestions)
  │             → OSRM path batch (limited to top-3 options, 10s timeout)
  │             → Interpolation fallback for remaining paths
  │             → LLM live pricing (8s timeout)
  │           Returns: Multi-level segment tree with destinations, transit options, paths
  │
  └── subMode === 'drive' (Drive mode):
        │
        └── POST /api/routes/plan (mode=personal)
              → OSRM car route (road-following)
              → Fuel cost calculation
              Returns: Driving route with tolls/fuel info

### 2.3 Request Flow: Search & Discovery

```
User searches for "Cafe" or clicks nearby category
  │
  ▼
SearchPanel.tsx handleSearch() / handleNearby()
  │
  └── GET /api/search/places | nearby
        │
        ├── SerpAPI Google Search → Place details
        ├── DDG scraper fallback (5-min TTL cache)
        ├── LLM Agent fallback (Gemini/OpenRouter)
        │
        └── On card click:
              └── POST /api/search/enrich-place
                    ├── GET /api/search/reviews (SerpAPI → Proxy scrape)
                    ├── GET /api/search/ride-prices (SerpAPI → Proxy)
                    └── GET /api/search/weather (Open-Meteo)
```

### 2.4 Data Flow: Weather → TOPSIS Integration

```
Open-Meteo API
  │
  ▼
GET /api/search/weather
  │
  ▼
weather dict: {temp, condition, rain_mm, wind_speed, humidity}
  │
  ▼
topsis_score_routes(routes, ..., weather)
  │
  ├── rain > 0 → walk/bike penalized (-15 to -20 score)
  ├── rain > 0 → cabs boosted (+5 score)
  ├── night time (h<6 or h>20) → ordinary buses penalized (-8)
  ├── night time → cabs favored (+8)
  └── temp > 35°C → walk/bike slight penalty (-5)
```

### 2.5 Data Flow: Google Distance Matrix Traffic

```
POST /api/routes/plan (mode=personal)
  │
  ▼
TransitPaths.get_driving_route()
  │
  ├── OSRM car route → base geometry and duration
  │
  └── Google Distance Matrix API (departure_time=now)
        │
        ├── API available → override OSRM duration with real traffic time
        └── API missing → keep OSRM duration (fallback)
```

---

## 3. Technology Stack

### 3.1 Backend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | FastAPI | 0.115+ | Async REST API |
| Server | Uvicorn | 0.30+ | ASGI server |
| Python | CPython | 3.12 | Runtime |
| HTTP | httpx | 0.27+ | Async HTTP client |
| Scraping | BeautifulSoup4, lxml | Latest | HTML parsing |
| LLM | OpenRouter API / Google Gemini | Latest | AI chat, pricing, reviews |
| GTFS | Custom loader (pickle cache) | N/A | BMTC bus schedules |
| DB | In-memory dicts + spatial index | N/A | Station data |
| Caching | In-memory dict with TTL | N/A | Segments, DDG scrapes |

### 3.2 Frontend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | React | 18.3+ | UI library |
| Language | TypeScript | 5.x | Type-safe JS |
| Build | Vite | 5.4+ | Fast bundler |
| Maps | Leaflet + react-leaflet | 1.9+ | Map rendering |
| Icons | Material Symbols | Latest | Icon system |
| HTTP | Axios | 1.7+ | API client |
| State | React Context | 18+ | Global state |
| Styling | CSS custom properties | N/A | Design system |

### 3.3 Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Containerization | Docker Compose | OSRM services |
| OSRM (Car) | osrm-backend:car | Driving routes |
| OSRM (Foot) | osrm-backend:foot | Walking routes (OOM) |
| Routing engine | OSRM + A* (custom) | Pathfinding |
| External APIs | SerpAPI, Google Maps, Open-Meteo, eRail.in | Data enrichment |

---

## 4. Directory Structure

```
VOYAGER/
├── backend/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app entry (55 lines)
│   ├── agents/
│   │   └── llm_agent.py                # LLM Agent (OpenRouter/Gemini)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                   # Transit route endpoints (645 lines)
│   │   └── search.py                   # Search endpoints (121 lines)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                   # Settings from .env (45 lines)
│   │   ├── database.py                 # TransitDatabase singleton (285 lines)
│   │   ├── schema.sql                  # SQL schema (67 lines)
│   │   └── spatial_index.py            # Grid-based spatial index (45 lines)
│   └── services/
│       ├── __init__.py
│       ├── transit_service.py          # TransitService facade (559 lines)
│       ├── segment_builder.py          # TripSegmentBuilder (1427 lines)
│       ├── transit_config.py           # Constants & pure functions (128 lines)
│       ├── transit_graph.py            # TransitAstarGraph (430 lines)
│       ├── transit_scoring.py          # TOPSIS scoring (70 lines)
│       ├── transit_paths.py            # OSRM path service (125 lines)
│       ├── fare_engine.py              # Fare calculation (29 lines)
│       ├── gtfs_service.py             # GTFS data loader (624 lines)
│       ├── geocoding.py                # Geocoding service (485 lines)
│       ├── astar_engine.py             # A* algorithm (102 lines)
│       ├── topsis_engine.py            # NumPy TOPSIS (52 lines)
│       ├── train_service.py            # Live train data (174 lines)
│       ├── proxy_manager.py            # Proxy rotation (83 lines)
│       ├── images.py                   # Image utilities (57 lines)
│       ├── clients/
│       │   ├── google_maps_client.py   # Google Maps API (89 lines)
│       │   ├── reddit_client.py        # Reddit API (165 lines)
│       │   ├── serpapi_client.py       # SerpAPI (170 lines)
│       │   └── weather_client.py       # Open-Meteo (79 lines)
│       ├── langgraph/
│       │   ├── agent.py               # LangGraph agent (329 lines)
│       │   ├── geo_tools.py           # Geo tools (83 lines)
│       │   ├── news_tools.py          # News tools (37 lines)
│       │   ├── pricing_tools.py        # Pricing tools (64 lines)
│       │   ├── review_tools.py         # Review tools (171 lines)
│       │   ├── search_tools.py         # Search tools (83 lines)
│       │   └── weather_tools.py        # Weather tools (11 lines)
│       └── scrapers/
│           ├── ride_scraper.py         # Uber/Ola/Rapido scraper (159 lines)
│           ├── google_reviews_scraper.py # Google Reviews scraper (120 lines)
│           ├── justdial_scraper.py     # JustDial scraper (93 lines)
│           ├── ddg_scraper.py          # DuckDuckGo scraper (103 lines)
│           └── news_scraper.py         # News scraper (64 lines)
├── frontend/
│   └── src/
│       ├── App.tsx                     # Root component (9 lines)
│       ├── main.tsx                    # Entry point (9 lines)
│       ├── index.css                   # Design system (223 lines)
│       ├── components/
│       │   ├── AToBPanel.tsx           # Route planner (651 lines)
│       │   ├── SegmentFlowView.tsx     # Multi-hop wizard (607 lines)
│       │   ├── SearchPanel.tsx         # Search/nearby (373 lines)
│       │   ├── MapView.tsx             # Leaflet map (173 lines)
│       │   ├── DiscoveryPanel.tsx      # Place details (146 lines)
│       │   ├── NewsPopup.tsx           # Live news (82 lines)
│       │   ├── HeaderBar.tsx           # Clock/weather/dark mode (80 lines)
│       │   └── TripPanel.tsx           # Trip planner (69 lines)
│       ├── pages/
│       │   └── MainPage.tsx            # Page orchestrator (177 lines)
│       ├── context/
│       │   └── AppContext.tsx          # Global state (161 lines)
│       ├── services/
│       │   └── api.ts                  # API client (147 lines)
│       ├── types/
│       │   └── index.ts                # TypeScript types (245 lines)
│       └── utils/
│           └── helpers.ts              # Utility functions (168 lines)
├── data_cache/                         # Cached datasets
├── docker-compose.yml                  # Docker services
├── tests/                              # Pytest tests
├── requirements.txt                    # Python dependencies
├── AGENTS.md                           # Project summary for AI
└── .env                                # Environment variables
```

---

## 5. Sprint History & Achievements

### 5.1 Sprint 1: Fake Data → Real Data (+1500 lines)

**Objective:** Replace all hardcoded/fake data with real data sources.

| Task | Details | Status |
|------|---------|--------|
| GTFS Integration | Load BMTC GTFS (7,271 shapes, 5,077 stops, 429,882 times) | ✅ |
| Real Reviews | SerpAPI Google Reviews chain | ✅ |
| Real Ride Pricing | Uber/Ola/Rapido via SerpAPI + proxy + formula fallback | ✅ |
| Real Weather | Open-Meteo API → TOPSIS scoring | ✅ |
| Real Traffic News | Reddit + DDG + SerpAPI news multi-source | ✅ |
| Real Train Data | eRail.in scraper (22 Karnataka stations) | ✅ |
| OSRM Docker | Docker Compose for car and foot routing | ✅ |

**Key Achievements:**
- GTFS data loaded from pickle cache in 0.65s
- Bus stop name pre-resolution (7.7s first run → cached)
- Karnataka govt-mandated ride rates (Uber Go ₹24/km, Ola Mini ₹24/km, Auto ₹20/km, Rapido Bike ₹5/km)

### 5.2 Sprint 2: Frontend Critical Bugs (+200 lines)

**Objective:** Fix UI/UX issues, dark theme, and data flow.

| Task | Details | Status |
|------|---------|--------|
| Route Numbers | Clean terminal suffixes "MF-28 JKLO-..." → "MF-28" | ✅ |
| SerpAPI Reviews | Fix broken review flow (search → place_id → details) | ✅ |
| SerpAPI key fix | `place` → `place_results` key | ✅ |
| Ride Fare Bug | Per-person calculation (vehicle/total ÷ group_size) | ✅ |
| Metro Filter | Remove overly aggressive direction filter | ✅ |
| Circular Routing | 300m → 800m visited radius | ✅ |
| Dead Data | Delete ~55MB unused datasets | ✅ |
| GTFS Startup | Defer graph build → lazy property | ✅ |

### 5.3 Sprint 3: Backend Refactoring (-2703 lines)

**Objective:** Extract and modularize the monolithic transit_service.py.

| Task | Details | Status |
|------|---------|--------|
| TransitConfig | Extract constants & pure functions (128 lines) | ✅ |
| TransitGraph | Extract A* graph class (430 lines) | ✅ |
| TransitScoring | Extract TOPSIS scoring (70 lines) | ✅ |
| TransitPaths | Extract OSRM path service (125 lines) | ✅ |
| FareEngine | Centralized surge logic (29 lines) | ✅ |
| SegmentBuilder | Extract from transit_service (1427 lines) | ✅ |
| transit_service.py | Reduced from 1998 → 579 lines | ✅ |
| Requirements | Remove sklearn, networkx, shapely | ✅ |
| Dead Code | Delete 12 test scripts, 5 dead types, NewsOverlay.tsx | ✅ |

**Key Metric:** 52 files changed, net -2703 lines.

### 5.4 Sprint 4: Testing & Polish (-3449 lines)

**Objective:** Stabilize, test, and polish the application.

| Task | Details | Status |
|------|---------|--------|
| Score Color | Unified getScoreColor() across components | ✅ |
| Bare Except | Fix in config.py → specific exceptions | ✅ |
| Pytest Setup | test_fare_engine.py (15 cases), test_segment_builder.py (8) | ✅ |
| SegmentPanel | Delete dead 730-line SegmentPanel.tsx | ✅ |
| Dark Mode | CSS variables for all components | ✅ |
| Multi-Hop UI | Wizard redesign with modal popup | ✅ |
| Segment Speed | Cache + limit parallel builds (156s → ~30s) | ✅ |
| Direct Mode Paths | OSRM driving route on map for ride options | ✅ |

---

## 6. Backend Deep Dive

### 6.1 TransitService (Facade)
**File:** `backend/services/transit_service.py` (559 lines)

The central orchestrator. Composes all sub-services and provides a unified interface for the API layer.

**Imports & Composition:**
```python
from backend.services.segment_builder import TripSegmentBuilder
from backend.services.transit_config import _ensure_gtfs, _RIDE_TYPES, ...
from backend.services.transit_graph import TransitAstarGraph
from backend.services.transit_scoring import topsis_score_routes
from backend.services.transit_paths import TransitPathService
from backend.services.fare_engine import calc_fare_with_surge
```

**Key Methods:**

| Method | Lines | Purpose |
|--------|-------|---------|
| `__init__` | 30 | Initialize all sub-services, compose dependencies, lazy A* graph |
| `plan_route()` | ~100 | Main route planning: A* → alternative generators → TOPSIS scoring → LLM insights |
| `get_all_segments()` | 3 | Delegates to `segment_builder.get_all_segments()` |
| `get_segment_step_options()` | ~120 | Single-step segment building (direct + via stops) |
| `get_osrm_path_between()` | 10 | Delegates to `path_service.get_path_between()` |
| `_interpolate_path()` | 8 | Fallback straight-line path with intermediate points |
| `astar_graph` (property) | 8 | Lazy A* graph builder (built on first access) |

**Lazy A* Graph Property:**
```python
@property
def astar_graph(self):
    if self._astar_graph is None:
        t0 = time.time()
        self._astar_graph = TransitAstarGraph(self._haversine, db)
        self._astar_graph.build_graph()
        logger.info(f"Graph built in {time.time()-t0:.1f}s: {self._astar_graph.node_count} nodes, {self._astar_graph.edge_count} edges")
    return self._astar_graph
```

The graph builds in ~24s on first request, then caches for subsequent requests. Server startup is instant because the graph is deferred.

### 6.2 SegmentBuilder (TripSegmentBuilder)
**File:** `backend/services/segment_builder.py` (1427 lines)

The most complex file. Handles recursive multi-hop transit segment building.

**Constructor Dependencies:**
```python
def __init__(self, haversine_fn, interpolate_path_fn, path_service=None,
             get_bus_route_nums_fn=None, astar_graph_fn=None):
```

**Key Methods:**

| Method | Lines | Purpose |
|--------|-------|---------|
| `_find_route_dest_toward()` | ~60 | Find furthest stop on a route toward destination (uses GTFS shapes) |
| `get_segment_step_options()` | ~190 | Build single-level segment (direct options + nearby stops with transit) |
| `_add_direct_options()` | ~40 | Add walk/cab/auto/bike direct options |
| `_add_reach_options()` | ~40 | Add options to reach a specific stop |
| `_add_transit_options()` | ~500 | Add transit (bus/metro) from a stop - heaviest method |
| `_astar_route_paths()` | ~30 | A* multi-hop route suggestions |
| `_is_outside_bengaluru()` | ~10 | Check if dest is outside Bengaluru |
| `_is_hub_or_close_to_dest()` | ~10 | Filter for hub stops |
| `_build_single_segment()` | ~120 | Build one segment level (entry point for recursion) |
| `get_all_segments()` | ~80 | Recursive segment builder with caching |

**Segment Building Flow (get_all_segments):**

1. **Check cache** — 5-min TTL, keyed by from/dest lat/lng + group_size + budget + max_depth
2. **Build Segment 0** — from source location
   - `_build_single_segment()`:
     - `_add_direct_options()` — walk, cab, auto, bike direct to dest
     - `db.find_nearby_bus_stops(2km)` — up to 5 closest stops
     - `db.find_nearby_metro_stations(3km)` — up to 3
     - `db.find_nearby_railway_stations(15km)` — for long-distance
     - For each bus stop:
       - `_add_reach_options()` — walk/ride to reach the stop
       - `_add_transit_options()` — GTFS buses from the stop
       - Metro/bus-to-metro options
     - Sort by relevance score, take top 5-6
     - `_astar_route_paths()` — A* multi-hop suggestions
3. **Populate next_from_map** — transit options that need next segments (limit: 3)
4. **Recurse** — build next segments for each entry (depth 1, 2), limit: 2 per level
5. **Cache result** — store for 5 minutes

**Performance Optimizations:**
- **`_haversine_dist`** instead of `geodesic` (2.2s → graph build)
- **`_dist_cache`** dict for precomputed distances
- **`nearby_bus[:5]`** limit per segment (reduced from [:8])
- **next_from_map limit: 3** entries max, new_map limit: 2
- **Segment result cache** — 5-min TTL
- **`_gtfs_route_cache`, `_shape_cache`, `_stops_toward_cache`, `_shape_between_cache`** — intra-request caches

### 6.3 TransitConfig (Constants & Pure Functions)
**File:** `backend/services/transit_config.py` (128 lines)

All module-level constants and pure functions extracted from transit_service.py.

**Ride Types (_RIDE_TYPES):**

Karnataka government-mandated rates as of 2026:

| Mode ID | Label | Per Km | Time/Km | Base Fare | Capacity | Free Km |
|---------|-------|--------|---------|-----------|----------|---------|
| `cab` | Uber Go / Ola Mini | ₹12 | 3 min | ₹25 | 4 | 0 |
| `cab_sedan` | Uber Go Priority / Ola Prime | ₹24 | 3 min | ₹50 | 4 | 0 |
| `cab_xl` | Uber XL / Ola XL | ₹30 | 3 min | ₹100 | 6 | 0 |
| `auto` | Auto | ₹9 | 5 min | ₹15 | 3 | 0 |
| `bike` | Uber Moto / Rapido | ₹5 | 2 min | ₹10 | 1 | 0 |
| `cab_women` | Uber for Women / Ola for Women | ₹12 | 3 min | ₹25 | 4 | 0 |
| `cab_pet` | Uber Pet / Premier | ₹18 | 3 min | ₹50 | 4 | 0 |

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `_ensure_gtfs()` | Lazy GTFS loader with bus stop name pre-resolution |
| `_calc_ride_fare(dist, base, per_km, free_km)` | Fare calculator with free-km logic |
| `_ride_fare_range(dist, base, per_km, free_km)` | Returns (min, max) with 1.35x surge |
| `_get_train_options(src, dst)` | Live train lookup |
| `_safe(val, default)` | NaN/inf sanitizer |
| `_current_hour()` | Server time hour |
| `_is_metro_operating()` | 5AM-11PM check |
| `_haversine_dist(lat1, lng1, lat2, lng2)` | Fast spherical distance (6371km R) |
| `_route_goes_toward_dest(...)` | Directional validity via shape angle |
| `_gtfs_buses_at_stop(stop_name)` | GTFS route lookup |
| `_has_gtfs_route(stop_name)` | GTFS name resolution check |

**Major Hubs (_MAJOR_HUBS):**
14 hub names used for directional routing fallback: majestic, kempegowda bus station, kr market, kbs, shivajinagara, shivajinagar, banashankari, jayanagara, k.r. market, city market, platform 10-14.

### 6.4 TransitGraph (TransitAstarGraph)
**File:** `backend/services/transit_graph.py` (430 lines)

Builds and queries the A* graph for transit routing.

**Graph Construction:**

```
Nodes: Bus stops (2933) + Metro stations (85) = ~3018 nodes
Edges: ~4800-54000 (varies by walk radius)
  - Bus-to-bus walk edges (within 300m)
  - Metro-to-metro edges (along line, station-to-station)
  - Bus-to-metro walk edges (within 800m)
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `build_graph()` | Construct all nodes and edges, populate adjacency list |
| `find_route(from_lat, from_lng, to_lat, to_lng)` | A* pathfinding from source to destination |
| `_add_bus_stops()` | Add all GTFS bus stops as nodes |
| `_add_metro_stations()` | Add metro stations as nodes |
| `_add_bus_walk_edges()` | Walk connections between nearby bus stops |
| `_add_metro_edges()` | Metro line connections (station-to-station along line) |
| `_add_bus_metro_walk_edges()` | Walk connections between bus stops and metro stations |

**A* Heuristic:** Haversine distance from current node to destination (in km).

**Performance:**
- Graph build: ~24s (first request) → cached → ~0s
- Route query: <1s
- Node count: ~3018, Edge count: ~4800-54000

### 6.5 TransitScoring (TOPSIS)
**File:** `backend/services/transit_scoring.py` (70 lines)

Multi-criteria decision analysis for route ranking.

**Criteria & Weights:**

| Criterion | Direction | Weight | Description |
|-----------|-----------|--------|-------------|
| Duration | - (minimize) | 0.30 | Total travel time |
| Fare | - (minimize) | 0.25 | Total cost |
| Transfers | - (minimize) | 0.15 | Number of transfers |
| Walking | - (minimize) | 0.10 | Total walking distance |
| Comfort | + (maximize) | 0.10 | AC vs non-AC, crowd level |
| Safety | + (maximize) | 0.10 | Time-of-day safety rating |

**Weather Integration (added in Sprint 4):**

```python
if weather:
    rain = weather.get("rain_mm", 0)
    cond = weather.get("condition", "").lower()
    hour = _current_hour()
    for r in routes:
        mode = r.get("type", "")
        score = r.get("overall_score", 50)
        if rain > 0 and mode in ("walk", "bike"):
            score -= min(20, int(rain * 2))
        if rain > 0 and mode in ("cab", "cab_xl", "auto"):
            score += min(5, int(rain * 0.5))
        if hour < 6 or hour > 20:
            if mode == "bus_ordinary":
                score -= 8
            if mode in ("cab", "cab_xl"):
                score += 8
        if cond and "rain" in cond:
            if mode == "walk": score -= 15
            if mode == "bike": score -= 15
        r["overall_score"] = max(10, min(99, score))
```

### 6.6 TransitPaths (OSRM Path Service)
**File:** `backend/services/transit_paths.py` (125 lines)

Fetches road-following paths from local OSRM Docker instances.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `get_path_between(lat1, lng1, lat2, lng2, profile)` | Generic OSRM query (driving/walking) |
| `get_driving_route(...)` | Driving route with Google traffic override |
| `_interpolate_path(lat1, lng1, lat2, lng2, points)` | Fallback straight-line path |

**Google Distance Matrix Traffic Override:**
```python
def get_driving_route(source, dest, ...):
    osrm_path = osrm_client.route(...)
    google_traffic = google_maps_client.distance_matrix(
        origins=source, destinations=dest,
        departure_time='now'
    )
    if google_traffic and 'duration_in_traffic' in google_traffic:
        osrm_path['duration'] = google_traffic['duration_in_traffic']
    return osrm_path
```

**Cache:** OSRM paths are NOT cached between requests (each request fetches fresh paths for the selected options). Segment-level path cache via 5-min segment result cache.

### 6.7 FareEngine
**File:** `backend/services/fare_engine.py` (29 lines)

Centralized fare logic — eliminates 12x duplicated `fare_max = round(total * 1.35)` from the old transit_service.py.

```python
def calc_fare_with_surge(mode_data, distance_km):
    """Returns (fare_min, fare_max) with centralized surge multiplier (1.35x)."""
    ...

def get_mode_by_id(mode_id):
    """Look up ride type tuple by mode string."""
    ...

def ride_fare_range(mode_id, distance_km):
    """One-call convenience wrapper."""
    ...
```

### 6.8 GTFS Service
**File:** `backend/services/gtfs_service.py` (624 lines)

Loads and queries BMTC GTFS data from pickle cache.

**Data Loaded:**
- 7,271 shapes (bus route geometries)
- 5,077 stops (bus stops)
- 429,882 stop_times (timetable entries)

**Cache Files:**
- `gtfs_cache.pkl` — Full GTFS data with pre-resolved name_map
- `gtfs_shapes.pkl` — Shape data (pre-normalized for fast lookup)

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `load()` | Load GTFS from pickle or rebuild from GTFS zip |
| `pre_resolve_all(names)` | Batch-resolve bus stop names (first-run: 7.7s) |
| `resolve_name(name)` | Fuzzy-match stop name against GTFS |
| `get_all_routes_at_stop(stop_name)` | Get all bus routes serving a stop |
| `get_travel_time_between(route, stop1, stop2)` | Get timetable travel time |
| `find_stops_on_route_toward_dest(route, from_stop, dest)` | Filtered stops that go toward destination |
| `clean_route_short_name(name)` | Strip terminal suffixes from route numbers |

**Name Resolution Chain (_fast_fuzzy_match):**
1. Exact match — O(1) dict lookup
2. Normalized match — case/space/abbreviation normalized
3. Word-overlap index — fast keyword matching
4. Substring match — partial name matching
5. Word-subset match — multi-word subset matching
6. Trigram-filtered get_close_matches — fuzzy with trigram pre-filter

**Performance:** First-run pre-resolve: 7.7s (2972 names), subsequent: instant from pickle cache.

### 6.9 Database (TransitDatabase)
**File:** `backend/core/database.py` (285 lines)

Singleton in-memory database with spatial indexes.

**Data Containers:**

| Container | Type | Contents |
|-----------|------|----------|
| `bus_stops` | dict | 5000+ BMTC bus stops with lat/lng/name/routes |
| `metro_stations` | list | 85 Namma Metro stations (Purple/Green/Yellow) |
| `metro_lines` | dict | Metro line definitions with station sequences |
| `kia_routes` | dict | KIA airport bus routes |
| `transit_fares` | dict | Fare tables for bus/metro |
| `railway_stations` | list | 22 Karnataka railway stations |
| `wards_data` | dict | Bengaluru ward boundaries |

**Spatial Indexes:**
- `_bus_spatial` — Grid-based index (0.01° cells) for bus stop proximity
- `_metro_spatial` — Grid-based index for metro station proximity
- `_rail_spatial` — Grid-based index for railway station proximity

**Key Query Methods:**

| Method | Purpose |
|--------|---------|
| `find_nearby_bus_stops(lat, lng, radius_km)` | Returns up to 20 nearest bus stops |
| `find_nearby_metro_stations(lat, lng, radius_km)` | Returns up to 50 nearest metro stations |
| `find_nearby_railway_stations(lat, lng, radius_km)` | Returns up to 10 nearest railway stations |
| `get_metro_distance_between(stn_a, stn_b)` | Metro line distance (km) between stations |
| `get_metro_line_path(from_name, to_name)` | Full metro path between stations |
| `get_bmtc_ordinary_fare(dist_km)` | BMTC ordinary bus fare table lookup |
| `get_bmtc_ac_fare(dist_km)` | BMTC AC bus fare table lookup |
| `get_metro_fare(dist_km)` | Metro fare table lookup |
| `find_route_between_stops(route_num, stop_a, stop_b)` | GTFS route segment lookup |

### 6.10 Geocoding
**File:** `backend/services/geocoding.py` (485 lines)

Place search, nearby discovery, and geocoding.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `search_places(query, lat, lng)` | Multi-source place search (SerpAPI → DDG → LLM) |
| `search_nearby(lat, lng, radius, place_type)` | Category-based nearby discovery |
| `get_suggestions(query)` | Autocomplete suggestions |
| `get_place_reviews(place_name, address)` | Google Reviews via SerpAPI |
| `get_ride_prices(source, dest)` | Ride price estimates |

**Search Fallback Chain:**
1. SerpAPI Google Search → parse place results
2. DuckDuckGo scraper (5-min TTL cache)
3. LLM Agent (Gemini/OpenRouter) for hard-to-find places

### 6.11 Train Service
**File:** `backend/services/train_service.py` (174 lines)

Live train data from eRail.in API.

**Key Data:**
- 22 Karnataka station codes (SBC, YNK, BNC, KJM, etc.)
- 7 city-pair fallbacks (when API fails)
- Route: Yesvantpur → KSR Bengaluru → Krishnarajapuram → Whitefield

**API:** `https://erail.in/rail/getTrains.aspx?Station_From=<from>&Station_To=<to>`

### 6.12 Proxy Manager
**File:** `backend/services/proxy_manager.py` (83 lines)

Manages proxy rotation for scraping to avoid IP blocks.

**Provider Support:**
- `scrapingbee` — ScrapingBee API
- `scrapfly` — Scrapfly API
- None — Direct connection

**Configuration via .env:**
```env
PROXY_PROVIDER=scrapingbee|scrapfly|none
SCRAPINGBEE_API_KEY=xxx
SCRAPFLY_API_KEY=xxx
```

### 6.13 Images
**File:** `backend/services/images.py` (57 lines)

Place image utilities — placeholder generation and URL management.

### 6.14 FastAPI Routes
**File:** `backend/api/routes.py` (645 lines)

All transit-related API endpoints.

**Route Planning Endpoints:**

| Method | Path | Lines | Purpose |
|--------|------|-------|---------|
| POST | `/api/routes/plan` | ~80 | Main route planning |
| GET | `/api/routes/all-segments` | ~285 | Multi-hop segment tree |
| GET | `/api/routes/segment-step` | ~130 | Single segment step |
| GET | `/api/routes/metro-stations` | ~5 | Metro station list |
| GET | `/api/routes/bus-stops` | ~5 | Bus stop list |
| GET | `/api/routes/transit-fares` | ~5 | Transit fare data |
| GET | `/api/routes/live-prices` | ~5 | Live ride prices |
| GET | `/api/routes/news` | ~5 | Transit news |
| GET | `/api/routes/traffic-overlay` | ~5 | Traffic overlay |

**POST /api/routes/plan — Request Format:**
```json
{
  "source_lat": 12.9716, "source_lng": 77.5946,
  "dest_lat": 12.9756, "dest_lng": 77.6066,
  "mode": "public|personal|walking",
  "group_size": 1,
  "budget": null,
  "waypoints": []
}
```

**POST /api/routes/plan — Response Format:**
```json
{
  "status": "success",
  "routes": [
    {
      "type": "bus_to_metro|metro|multi_modal|car|walk",
      "provider": "BMTC + Metro",
      "total_fare": 56,
      "total_duration_minutes": 44,
      "total_distance_km": 13.62,
      "total_walking_km": 1.2,
      "transfers": 1,
      "overall_score": 85,
      "score_explanation": "Good balance of time and cost",
      "legs": [
        {
          "mode": "walk", "from": "Yelahanka 5th Phase", "to": "Sheshadripuram College",
          "distance_km": 0.76, "duration_minutes": 9, "fare": 0,
          "path": [[13.122, 77.555], [13.118, 77.558], ...]
        },
        {
          "mode": "bus_ordinary", "from": "Sheshadripuram College", "to": "KR Circle",
          "route": "96-E", "distance_km": 8.5, "duration_minutes": 34, "fare": 35,
          "path": [...]
        },
        {
          "mode": "metro", "from": "Sir M V Central College", "to": "Mahatma Gandhi Road",
          "line": "Purple", "distance_km": 3.2, "duration_minutes": 4, "fare": 21,
          "path": [...]
        }
      ],
      "geometry": {"coordinates": [[77.555, 13.122], ...], "type": "LineString"},
      "route_numbers": ["96-E", "Purple Line"],
      "travel_insights": "..."  // LLM-generated
    }
  ],
  "source": {...},
  "dest": {...}
}
```

**GET /api/routes/all-segments — Request Params:**
```
from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name,
group_size (default 1), budget (optional), max_depth (default 3)
```

**Performance Optimization Flow:**
1. Build segment structure (thread executor, 60s timeout)
2. OSRM path batch (limited to top-3 per segment, 10s timeout, 8 concurrent)
3. Interpolation fallback for remaining paths
4. LLM live pricing (background, 8s timeout)

### 6.15 Search API
**File:** `backend/api/search.py` (121 lines)

All search and discovery endpoints.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/search/places` | Place text search |
| GET | `/api/search/nearby` | Nearby category search |
| GET | `/api/search/suggestions` | Autocomplete |
| GET | `/api/search/verify-place` | Place verification |
| GET | `/api/search/reviews` | Place reviews |
| GET | `/api/search/ride-prices` | Ride price estimates |
| GET | `/api/search/current-events` | News and events |
| GET | `/api/search/ai-chat` | AI chat |
| POST | `/api/search/enrich-place` | Enrich place with all data |
| GET | `/api/search/weather` | Weather data |

### 6.16 Scrapers

#### 6.16.1 Ride Scraper (`ride_scraper.py` — 159 lines)
Scrapes ride-hailing prices from multiple sources.

**Fallback Chain:**
1. SerpAPI Google Shopping → ride price data
2. Proxy scrape (via proxy_manager)
3. Formula-based fallback (Karnataka govt rates)

**Rate Calculation Formula:**
```python
def _calc_ride_fare(distance, base_fare, per_km_rate, free_km):
    if distance <= free_km:
        return base_fare
    return base_fare + (distance - free_km) * per_km_rate
```

**Surge Multiplier:** 1.35x (peak time) applied via `calc_fare_with_surge()`.

#### 6.16.2 DDG Scraper (`ddg_scraper.py` — 103 lines)
DuckDuckGo search scraper with 5-min TTL cache.

**Retry Chain:**
1. HTML search (direct)
2. Lite version fallback (text-only)
3. Cache (5-min TTL, in-memory dict)

#### 6.16.3 Google Reviews Scraper (`google_reviews_scraper.py` — 120 lines)
Scrapes Google reviews via proxy.

**Chain:**
1. SerpAPI place details → `user_reviews.most_relevant[]`
2. Proxy scrape (google.com reviews page)
3. Empty fallback (no fake reviews)

#### 6.16.4 News Scraper (`news_scraper.py` — 64 lines)
Multi-source news aggregation.

**Sources:**
1. SerpAPI news results
2. DuckDuckGo news search
3. Reddit API (r/bengaluru)

#### 6.16.5 JustDial Scraper (`justdial_scraper.py` — 93 lines)
JustDial business scraper for place enrichment. Currently **broken** (site not responding).

### 6.17 API Clients

#### 6.17.1 SerpAPI Client (`serpapi_client.py` — 170 lines)
SerpAPI integration for Google Search, Maps, and Shopping data.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `search_places(query, lat, lng)` | Google Maps search |
| `search_shopping(query)` | Google Shopping price data |
| `place_details(place_id)` | Get detailed place info + reviews |
| `search_news(query)` | Google News search |

**Response Parsing:**
- Search: `organic_results[].title, snippet, link`
- Place details: `place_results.name, rating, reviews, user_reviews.most_relevant[]`
- Reviews: `user_reviews.most_relevant[].username, description, rating, date`
- Shopping: `shopping_results[].title, price, source, link`

#### 6.17.2 Google Maps Client (`google_maps_client.py` — 89 lines)
Google Maps API integration for distance matrix and traffic.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `distance_matrix(origins, destinations, departure_time)` | Travel time with traffic |
| `geocode(address)` | Address → lat/lng |
| `reverse_geocode(lat, lng)` | lat/lng → address |

#### 6.17.3 Reddit Client (`reddit_client.py` — 165 lines)
Reddit API integration for news and community insights.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `search_news(query, subreddit)` | Search for news in r/bengaluru |
| `get_hot_posts(subreddit, limit)` | Hot posts from a subreddit |

**Auth:** OAuth2 with `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`.

#### 6.17.4 Weather Client (`weather_client.py` — 79 lines)
Open-Meteo API — no API key required.

**API:** `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&hourly=temperature_2m,precipitation,weathercode,wind_speed_10m,relative_humidity_2m`

**Response Parsing:**
```python
weather_code_to_condition = {
    0: "clear", 1-3: "partly cloudy", 45-48: "foggy",
    51-57: "drizzle", 61-67: "rain", 71-77: "snow",
    80-82: "rain showers", 95-99: "thunderstorm"
}
```

### 6.18 LangGraph Agent
**File:** `backend/services/langgraph/agent.py` (329 lines)

LangGraph-based agent framework for complex multi-step reasoning.

**Components:**

| File | Purpose |
|------|---------|
| `agent.py` | Main agent loop, intent detection, tool registry, parallel execution |
| `geo_tools.py` | Nearby search, reverse geocode, distance calculation |
| `news_tools.py` | News search, traffic updates |
| `pricing_tools.py` | Ride pricing, fare calculation |
| `review_tools.py` | Place reviews, summary generation |
| `search_tools.py` | Place search, suggestions |
| `weather_tools.py` | Weather queries |

**API Endpoint:**
- `POST /api/langgraph/ask` — Full LangGraph reasoning loop

**Agent Architecture:**
```
User Query
  │
  ▼
Intent Detection (classify: search|navigate|price|review|weather|general)
  │
  ▼
Tool Selection (registry-based, parallel execution)
  │
  ▼
Tool Execution (parallel where possible)
  │
  ▼
Response Generation (LLM summarizes tool outputs)
```

---

## 7. Frontend Deep Dive

### 7.1 AppContext (State Management)
**File:** `frontend/src/context/AppContext.tsx` (161 lines)

Central shared state via React Context.

**State Shape:**

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `mode` | `'search'\|'atob'\|'trip'` | `'search'` | Current app mode |
| `userLocation` | `[number, number] \| null` | `null` | GPS location |
| `mapCenter` | `[number, number]` | `[12.9716, 77.5946]` | Map view center |
| `mapRef` | `MutableRefObject` | `null` | Leaflet map instance |
| `liveTrackingPos` | `[number, number] \| null` | `null` | Live GPS tracking |
| `trackingActive` | `boolean` | `false` | GPS active flag |
| `sourceLocation` | `[number, number] \| null` | `null` | A→B source |
| `destLocation` | `[number, number] \| null` | `null` | A→B destination |
| `sourceQuery` / `destQuery` | `string` | `''` | Search queries |
| `selectedPlace` | `PlaceResult \| null` | `null` | Current place |
| `allMarkers` | `PlaceResult[]` | `[]` | Map markers |
| `searchResults` | `PlaceResult[]` | `[]` | Search results |
| `nearbyResults` | `PlaceResult[]` | `[]` | Nearby places |
| `showDiscovery` | `boolean` | `false` | Discovery panel |
| `discoveryPlace` | `PlaceResult \| null` | `null` | Current place in panel |
| `routeGeometry` | `MapRouteGeometry[] \| null` | `null` | Route on map |
| `newsItems` | `NewsItem[]` | `[]` | News items |
| `ridePrices` | `RidePrice[]` | `[]` | Ride prices |
| `groupSize` | `number` | `1` | Group size |
| `budget` | `number \| undefined` | `undefined` | Budget |
| `travelMode` | `'public'\|'personal'\|'walking'` | `'public'` | Travel mode |
| `darkMode` | `boolean` | OS preference | Dark mode toggle |
| `weather` | `any` | `null` | Current weather |

### 7.2 MainPage (Orchestrator)
**File:** `frontend/src/pages/MainPage.tsx` (177 lines)

Page orchestrator that composes the sidebar + map layout.

**Structure:**
```
┌──────────────────────────────────────────────┐
│ HeaderBar (Clock, Weather, Dark Mode toggle) │
├──────────────┬───────────────────────────────┤
│   Sidebar    │         MapView               │
│  ┌─────────┐ │   (Leaflet Map)               │
│  │Search   │ │                               │
│  │Panel    │ │   ┌──────────────┐            │
│  │or       │ │   │News Popup    │            │
│  │AToBPanel│ │   └──────────────┘            │
│  │or       │ │   ┌──────────────┐            │
│  │TripPanel│ │   │Live Loc Btn  │            │
│  └─────────┘ │   └──────────────┘            │
│  ┌─────────┐ │   ┌──────────────┐            │
│  │Discovery│ │   │DiscoveryPanel│            │
│  │Panel    │ │   │(overlay)     │            │
│  └─────────┘ │   └──────────────┘            │
└──────────────┴───────────────────────────────┘
```

**State:**
- `appMode` — Controls which panel is shown in sidebar
- `mapRouteGeometry` — Route geometries passed between panels and map
- `newsItems` — Live news items from multi-source fetch

**News Polling:** Every 2 minutes, fetches current-events from API.

### 7.3 AToBPanel (Route Planner)
**File:** `frontend/src/components/AToBPanel.tsx` (651 lines)

The A→B route planning panel with three sub-modes and two transport types.

**Sub-Modes:**

| SubMode | Icon | Description |
|---------|------|-------------|
| `transport` | `directions_transit` | Public / Online (transit + rides) |
| `drive` | `directions_car` | Personal driving |
| `walk` | `directions_walk` | Walking |

**Transport Types (only in `transport` mode):**

| TransportType | Label | What it shows |
|---------------|-------|---------------|
| `segment` | Multi-Hop Transit | Step-by-step wizard with bus/metro/walk segments |
| `direct` | Direct Ride | Ride prices (Uber/Ola/Rapido) with map paths |

**Key Methods:**

| Method | Line | Purpose |
|--------|------|---------|
| `handleFindRoutes()` | ~79 | Main route finder — dispatches based on subMode/transportType |
| `getTopRoutes()` | ~223 | Filter and sort routes by TOPSIS score |
| `pickSource()` | ~62 | Resolve source location |
| `pickDest()` | ~68 | Resolve destination and fly map |

**Multi-Hop Transit Flow (transportType === 'segment'):**
1. User clicks "Find Routes"
2. `planRoute()` called first → routes displayed immediately
3. `getAllSegments()` called asynchronously → spinner shown
4. When segments arrive → `showSegmentModal` auto-opens
5. SegmentFlowView rendered in modal
6. User steps through wizard (select stop → select transit → next segment)

**Direct Ride Flow (transportType === 'direct'):**
1. User clicks "Find Routes"
2. `getRidePrices()` + `planRoute(mode=personal)` called in parallel
3. Ride prices displayed as clickable cards
4. Clicking a ride → OSRM driving path shown on map

**Route Card States:**
- Default: Shows route info (duration, fare, score, score bar, score explanation)
- Selected: "View Steps" button → step-by-step hop flow OR "Start Journey" for GPS tracking
- "Start Journey" → Enables `watchPosition` GPS tracking on map

### 7.4 SegmentFlowView (Multi-Hop Wizard)
**File:** `frontend/src/components/SegmentFlowView.tsx` (607 lines)

Step-by-step wizard for multi-hop transit planning. Completely redesigned in Sprint 4.

**Wizard Steps:**

```
Step 1: "Where do you want to go?"
  → Shows destination cards (nearby stops) with walk/ride distance and fare
  → User clicks a destination card

Step 2: "Choose transit from [stop]"
  → Shows transit options (buses/metro) with:
    - Bus number and destination
    - Duration, distance, fare
    - Departure times (next 6 departures as chips)
    - Next-transit chain (e.g., "Then: Metro Purple → MG Road")
    - Drop-off options (walk/cab from alighting stop)
  → User clicks a transit option → "Continue to Next Step" button

Step 3: Next segment (recurse)
  → Same flow from the arrival location

Final: "Journey Complete!"
  → Summary: total fare, duration, segments selected
  → Full breadcrumb of chosen path
```

**Breadcrumb:**
```
📍 Yelahanka 5th Phase → 🚌 96-E → KR Circle → 🚇 Purple Line → 📍 MG Road
```

**Key Components:**

| Element | Description |
|---------|-------------|
| Breadcrumb | Full path chain with mode icons, step highlighting |
| Destination Cards | Stop name, distance, walk/ride options, transit count |
| Transit Option Cards | Bus number, destination, duration, fare, departure times, next-transit chain |
| Journey Complete | Summary card with total fare, duration, segment list |
| Total Bar | Running total of fare + duration as user makes selections |

**Map Integration:**
- When a destination is selected → walk path shown on map (green dashed)
- When a transit is selected → bus/metro path shown on map (solid primary color)
- Next-transit segments shown in amber

### 7.5 SearchPanel
**File:** `frontend/src/components/SearchPanel.tsx` (373 lines)

Search and nearby discovery panel.

**Layout:**
```
┌────────────────────────┐
│ Search input           │
│ [Search Places...]     │
├────────────────────────┤
│ Nearby Categories      │
│ [🏪 All] [🍽️ Food]    │
│ [🛍️ Mall] [🧘 Park] ...│
├────────────────────────┤
│ Results                │
│ ┌────────────────────┐ │
│ │ Place Card 1       │ │
│ │ ⭐ 4.5 · Cafe      │ │
│ │ Review summary...  │ │
│ │ Show reviews ▼     │ │
│ │ [Details] [Navigate]│ │
│ └────────────────────┘ │
│ ┌────────────────────┐ │
│ │ Place Card 2       │ │
│ │ ...                │ │
│ └────────────────────┘ │
└────────────────────────┘
```

**Categories:** All, Food/Restaurants, Shopping Malls, Parks, Hotels, Hospitals, ATM/Banks, Fuel, Metro Stations, Bus Stops, Police Stations, Pharmacies.

**Radius Slider:** 0.5km – 10km.

### 7.6 MapView (Leaflet)
**File:** `frontend/src/components/MapView.tsx` (173 lines)

Leaflet map with markers, route geometries, and live tracking.

**Features:**
- Colored markers (green for recommended, red for not recommended)
- Route geometry rendering (colored lines with weights, dashed for walk)
- Live GPS tracking with `watchPosition`
- "Live Location" return button (floating)
- `MapRouteGeometry` type supports: `route`, `segment`, `hover`, `stop`
- Zoom to source/destination on route plan

### 7.7 DiscoveryPanel
**File:** `frontend/src/components/DiscoveryPanel.tsx` (146 lines)

Right-side glass panel showing detailed place information.

**Content:**
- Place name, type, address
- Rating score with color badge
- Price information
- Review summary
- Review list (expandable)
- "Show on Map" and "Navigate Here" buttons

### 7.8 HeaderBar
**File:** `frontend/src/components/HeaderBar.tsx` (80 lines)

Top header bar with clock, weather, and dark mode toggle.

**Features:**
- Live clock (1-second updates, 24h format)
- Current weather from `/api/search/weather`
- Location name from reverse geocoding
- Dark/Light mode toggle (syncs with OS preference on first load)

### 7.9 NewsPopup
**File:** `frontend/src/components/NewsPopup.tsx` (82 lines)

Live news popup with multi-source data.

**Sources:** Reddit + Traffic + Events (aggregated)
**Refresh:** Every 2 minutes
**Color Coding:**
- Red border → Traffic
- Blue border → Weather
- Amber border → Event
- Grey border → General

**Features:**
- Dismissable
- Color-coded category borders
- Source attribution
- Count badge

### 7.10 TripPanel
**File:** `frontend/src/components/TripPanel.tsx` (69 lines)

Trip planner with AI insights. Currently minimal — placeholder for future expansion.

### 7.11 API Client
**File:** `frontend/src/services/api.ts` (147 lines)

Axios-based HTTP client.

**Configuration:**
```typescript
const api = axios.create({
  baseURL: '/api',
  timeout: 120000,  // 2 minutes
})
```

**13 API Functions:**

| Function | Endpoint | Returns |
|----------|----------|---------|
| `searchPlaces(q, lat, lng, signal?)` | GET `/search/places` | `SearchResponse` |
| `getNearbyPlaces(lat, lng, radiusKm, type?)` | GET `/search/nearby` | `NearbyResponse` |
| `getSuggestions(q)` | GET `/search/suggestions` | `string[]` |
| `planRoute(params)` | POST `/routes/plan` | `RoutePlanResponse` |
| `getRidePrices(source, dest, ...)` | GET `/search/ride-prices` | `RidePriceResponse` |
| `getSegmentStep(...)` | GET `/routes/segment-step` | Segment step data |
| `getWeather(lat, lng)` | GET `/search/weather` | Weather data |
| `getNews(lat?, lng?)` | GET `/search/current-events` | `NewsItem[]` |
| `getAllSegments(...)` | GET `/routes/all-segments` | `AllSegmentsResponse` |
| `getMetroStations(line?)` | GET `/routes/metro-stations` | Metro station list |
| `getBusStops(...)` | GET `/routes/bus-stops` | Bus stop list |
| `enrichPlace(place)` | POST `/search/enrich-place` | `EnrichSingleResponse` |
| `verifyPlace(name, address?)` | GET `/search/verify-place` | Verification result |

### 7.12 Type System
**File:** `frontend/src/types/index.ts` (245 lines)

26 exported TypeScript types/interfaces covering the entire data model.

**Core Types:**

| Type | Purpose | Key Fields |
|------|---------|------------|
| `PlaceResult` | Place entity | name, address, lat, lng, place_type, rating, reliability_score, reviews |
| `RouteOption` | Route result | type, provider, legs[], total_fare, overall_score, score_explanation, geometry |
| `RouteLeg` | Route leg | mode, from, to, distance_km, duration_minutes, fare, path, route, instructions |
| `AllSegment` | Multi-hop segment | segment_index, from, destinations[], route_paths[] |
| `SegmentDestination` | Stop with options | stop, distance_from_current, reach_options[], transit_options[] |
| `TransitOption` | Transit from stop | mode, route_number, bus_times[], fare, next_transit[], final_options[] |
| `NewsItem` | News item | title, description, impact, source, timestamp, lat, lng |
| `MapRouteGeometry` | Map path | type, coordinates[], color, weight, dashArray, label |
| `RidePrice` | Ride estimate | provider, mode, price, eta_minutes, note, source |

### 7.13 Design System (CSS)
**File:** `frontend/src/index.css` (223 lines)

Full design system with CSS custom properties.

**CSS Variables (Light Mode):**

| Variable | Value | Usage |
|----------|-------|-------|
| `--primary` | `#000666` | Primary brand color |
| `--on-primary` | `#ffffff` | Text on primary |
| `--secondary` | `#006e1c` | Success/secondary |
| `--error` | `#ba1a1a` | Error/negative |
| `--surface` | `#f9f9f9` | Page background |
| `--surface-container` | `#ededed` | Card background |
| `--text` | `#1a1a1a` | Primary text |
| `--text-muted` | `#6b6b7b` | Secondary text |
| `--glass-bg` | `rgba(255,255,255,0.82)` | Glass background |
| `--glass-strong-bg` | `rgba(255,255,255,0.92)` | Strong glass |
| `--radius-md` | `10px` | Border radius |

**Dark Mode Overrides (.dark):**

| Variable | Light | Dark |
|----------|-------|------|
| `--primary` | `#000666` | `#bac1ff` |
| `--surface` | `#f9f9f9` | `#121212` |
| `--surface-container` | `#ededed` | `#1e1e1e` |
| `--text` | `#1a1a1a` | `#e4e4e4` |
| `--text-muted` | `#6b6b7b` | `#9a9aab` |
| `--glass-bg` | `rgba(255,255,255,0.82)` | `rgba(30,30,30,0.85)` |

**Key CSS Classes:**

| Class | Purpose |
|-------|---------|
| `.glass` | Backdrop blur glass effect |
| `.glass-strong` | Stronger glass with shadow |
| `.sidebar` | 420px fixed-width column |
| `.pill-tab` | Pill-shaped nav button |
| `.route-card` | Route option card with score |
| `.score-bar` / `.score-fill` | Score progress bar |
| `.spinner` | CSS border spinner |
| `.badge-best` | Best match badge |
| `.reliability-pill` | Score badge (good/bad/mid) |

---

## 8. Data Sources & Integration

### 8.1 GTFS Bus Data (BMTC)

**Source:** BMTC (Bangalore Metropolitan Transport Corporation) GTFS feed

**Loading:** Custom GTFS loader at `backend/services/gtfs_service.py`

**Cache:**
- `data_cache/gtfs_cache.pkl` — Full GTFS data with pre-resolved name_map
- `data_cache/gtfs_shapes.pkl` — Shape data (route geometries)

**On-disk storage:**
- `data_cache/bmtc_gtfs/` — Raw GTFS zip files
- CSV data in `data_cache/` for bus stops, routes, shapes, stop_times, trips

**Data Volume:**
| Entity | Count |
|--------|-------|
| Shapes | 7,271 |
| Stops | 5,077 |
| Stop Times | 429,882 |
| Pre-resolved names | 1,696/2,972 (57%) |
| Unresolvable names | 14 (acronyms) |

### 8.2 Metro Data (Namma Metro)

**Source:** `data_cache/bengaluru_metro_network.csv`

**Lines:**
| Line | Stations | Corridor |
|------|----------|----------|
| Purple | 37 | Whitefield → Challaghatta |
| Green | 32 | Nagasandra → Silk Institute |
| Yellow | 16 | RV Road → Bommasandra |

**Missing:** Yelahanka station data (Green Line extension) — needs to be added.

### 8.3 Railway Data (Karnataka)

**Source:** `data_cache/karnataka_railway_stations.json`

**22 Stations mapped:**
- Major: SBC (KSR Bengaluru), YNK (Yelahanka), BNC (Bengaluru Cant), KJM (Krishnarajapuram)
- Others: Whitefield, Yesvantpur, Banaswadi, Hoodi, etc.

### 8.4 Ride Pricing Data

**Sources (in order):**
1. SerpAPI Google Shopping → ride price estimates
2. Proxy scrape (ride-hailing sites)  
3. Government-mandated formula rates (Karnataka)

**Formula Parameters:**
| Mode | Base Fare | Per Km | Per Min | Source |
|------|-----------|--------|---------|--------|
| Uber Go | ₹25 | ₹12 | ₹3 | Govt order |
| Ola Mini | ₹25 | ₹12 | ₹3 | Govt order |
| Uber XL | ₹100 | ₹30 | ₹3 | Govt order |
| Ola Auto | ₹15 | ₹9 | ₹5 | Govt order |
| Rapido Bike | ₹10 | ₹5 | ₹2 | Published rate |

### 8.5 Train Data

**Source:** eRail.in API (live scraping)

**Endpoint:** `https://erail.in/rail/getTrains.aspx?Station_From={from}&Station_To={to}`

**Fallback:** 7 hardcoded city-pair routes.

### 8.6 Weather Data

**Source:** Open-Meteo API (free, no API key)

**Endpoint:** `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&hourly=temperature_2m,precipitation,weathercode,wind_speed_10m,relative_humidity_2m`

---

## 9. External APIs

### 9.1 SerpAPI

**Purpose:** Google Search, Maps, Shopping, News data
**Type:** Paid (credit-based)
**Usage:**
- Place search (`/api/search/places`)
- Place details + reviews (`/api/search/reviews`)
- Ride price estimates (`/api/search/ride-prices`)
- News (`/api/search/current-events`)
- Price enrichment (`/api/search/enrich-place`)

**Configuration:**
```env
SERPAPI_API_KEY=your_key_here
```

**Fallback:** DDG scraper → LLM Agent

### 9.2 Google Maps API

**Purpose:** Distance Matrix for traffic-aware routing
**Type:** Paid (billed per request)
**Usage:**
- Traffic duration override in driving routes (`/api/routes/plan` mode=personal)

**Configuration:**
```env
GOOGLE_MAPS_API_KEY=your_key_here
```

### 9.3 Open-Meteo API

**Purpose:** Weather data (free, no key needed)
**Type:** Free
**Usage:**
- Current weather for TOPSIS scoring
- Weather display in HeaderBar

### 9.4 eRail.in API

**Purpose:** Live train schedules
**Type:** Free (scraped)
**Usage:**
- Train options between stations
- Live availability

### 9.5 Reddit API

**Purpose:** News and community content
**Type:** Free (OAuth2)
**Usage:**
- r/bengaluru hot posts
- News aggregation

**Configuration:**
```env
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
```

### 9.6 OpenRouter / Google Gemini

**Purpose:** AI-powered features
**Type:** Paid (token-based)
**Usage:**
- Travel insights (route plan)
- Place review summary
- Hard-to-find place search
- Price estimates
- AI chat (`/api/search/ai-chat`)

**Configuration:**
```env
OPENROUTER_API_KEY=your_key
```

---

## 10. Docker & OSRM Setup

### 10.1 Docker Compose
**File:** `docker-compose.yml`

```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONPATH=/app

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

  osrm-car:
    image: ghcr.io/project-osrm/osrm-backend
    ports:
      - "5000:5000"
    volumes:
      - ./osrm-data:/data
    command: >
      sh -c "osrm-routed --algorithm mld /data/car.osrm --port 5000"

  osrm-foot:
    image: ghcr.io/project-osrm/osrm-backend
    ports:
      - "5001:5001"
    volumes:
      - ./osrm-data-foot:/data
    command: >
      sh -c "osrm-routed --algorithm mld /data/foot.osrm --port 5001"
```

### 10.2 OSRM Status

| Service | Port | Status | Notes |
|---------|------|--------|-------|
| osrm-car | 5000 | ✅ Working | Driving routes, road-following paths |
| osrm-foot | 5001 | ❌ OOM | Out-of-memory during PBF customize |

**OSRM Car Setup:**
```bash
# Data preparation (one-time):
docker run --rm -v /path/to/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/karnataka-latest.osm.pbf

docker run --rm -v /path/to/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-partition /data/car.osrm

docker run --rm -v /path/to/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-customize /data/car.osrm

# Running:
docker compose up -d osrm-car
```

**OSRM Foot Issue:**
The OSRM foot service was OOM-killed during `osrm-customize` due to insufficient RAM. Options:
- Use a smaller PBF extract (only Bengaluru city instead of Karnataka state)
- Increase Docker RAM allocation
- Pre-process foot data on a machine with more RAM

### 10.3 Alternative: Direct OSRM Calls

When OSRM is unavailable, the system falls back to interpolated paths:
```python
def _interpolate_path(lat1, lng1, lat2, lng2, num_points=6):
    """Generate straight-line path with intermediate points."""
    path = []
    for i in range(num_points):
        fraction = i / (num_points - 1)
        lat = lat1 + (lat2 - lat1) * fraction
        lng = lng1 + (lng2 - lng1) * fraction
        path.append([lat, lng])
    return path
```

---

## 11. Performance Profile & Optimizations

### 11.1 Current Performance (warm cache)

| Operation | Time | Notes |
|-----------|------|-------|
| GTFS cache load | 0.65s | Pickle deserialize |
| Bus stop name pre-resolve | 7.7s (first) / instant (cached) | 2,972 names |
| A* graph build | 24s (first) / instant (cached) | 3,053 nodes |
| Total server startup | ~10.6s | Deferred graph build |
| API route planning (warm) | <1s | All caches warm |
| API all-segments (warm) | ~15-30s | Segment building + OSRM paths |

### 11.2 Optimization History

| Optimization | Before | After | File |
|-------------|--------|-------|------|
| geodesic → haversine | 11.6s | 2.2s | transit_graph.py |
| _dist_cache for distances | N/A | ~3s saved | transit_graph.py |
| SequenceMatcher → get_close_matches | 79s | 7.7s | gtfs_service.py |
| Trigram pre-filter | N/A | -70% time | gtfs_service.py |
| Pre-normalized names | N/A | O(1) lookup | gtfs_service.py |
| Deferred A* graph build | ~41s at startup | instant startup | transit_service.py |
| nearby_bus 8→5 | 156s | ~30s | segment_builder.py |
| Limit next_from_map | 8 entries | 3 entries | segment_builder.py |
| Segment result cache | N/A | instant repeat | segment_builder.py |
| OSRM batch limit | ALL options | top-3 | routes.py |
| OSRM batch timeout | 20s | 10s | routes.py |

### 11.3 Known Slow Operations

| Operation | Typical Time | Reason |
|-----------|-------------|--------|
| First API request | ~30-60s | A* graph build + GTFS pre-resolve |
| `_add_transit_options()` per stop | ~3-8s | GTFS timetable lookups |
| OSRM batch (segment) | ~5-10s | 8 concurrent, 3s per route |
| kNN spatial query | <0.01s | Grid-based index |

### 11.4 Caching Strategy

| Cache | TTL | Key | Location |
|-------|-----|-----|----------|
| GTFS data | Forever (pickle) | N/A | Disk |
| Bus stop names | Forever (pickle) | N/A | Disk |
| A* graph | Forever (process) | N/A | Memory (property) |
| Segment results | 5 min | from_lat,lng → dest_lat,lng + params | segment_builder.py |
| DDG search | 5 min | query + lat,lng | ddg_scraper.py |
| OSRM paths | Per-request | N/A (fresh per request) | routes.py |

---

## 12. Issues & Fixes

### 12.1 Critical Bugs Fixed

| # | Issue | Fix | File |
|---|-------|-----|------|
| 1 | GTFS route numbers had terminal suffixes | `clean_route_short_name()` strips suffixes | gtfs_service.py |
| 2 | SerpAPI review flow broken | Fixed place_id → details chain | review_tools.py |
| 3 | SerpAPI key `place` → `place_results` | Fixed response key | serpapi_client.py |
| 4 | Ride fare multiplied by group_size twice | Per-person: total/group_size | transit_config.py |
| 5 | Metro direction filter too aggressive | Removed `dest_to_dm > nm_dist * 1.1` | transit_service.py |
| 6 | Circular routing (300m radius) | Increased to 800m | transit_service.py |
| 7 | ~55MB unused datasets | Deleted 10 files | data_cache/ |
| 8 | GTFS ~41s startup block | Deferred graph build | main.py / transit_service.py |
| 9 | A* graph [:300] bus-metro limit | Removed limit | transit_graph.py |
| 10 | Bus→metro CASE 2 empty metro list | Fixed to use full db.metro_stations | transit_service.py |
| 11 | SegmentPanel dark theme | CSS variable references | SegmentPanel.tsx (deleted) |
| 12 | Score color inconsistency | Unified getScoreColor() | Multiple files |
| 13 | Bare except in config.py | `except (json.JSONDecodeError, TypeError)` | config.py |
| 14 | Segment buffering (30s timeout) | Increased to 60s | routes.py |
| 15 | Segment 156s slowness | Limit next_from_map to 3, nearby_bus to 5 | segment_builder.py |

### 12.2 Known Remaining Issues

| # | Issue | Severity | Notes |
|---|-------|----------|-------|
| 1 | OSRM Foot OOM | Medium | Smaller PBF or more RAM needed |
| 2 | JustDial scraper broken | Low | Site not responding |
| 3 | Yelahanka metro missing | Low | Not in bengaluru_metro_network.csv |
| 4 | 14 bus stop names unresolvable | Low | Acronyms (hnrj, ggmc, pesitelc) |
| 5 | Bus→metro CASE 2 scoring | Medium | Suboptimal reverse-direction routes |
| 6 | First request slow (30-60s) | Medium | A* graph + GTFS cold start |
| 7 | No WebSocket for OSRM paths | Low | Polling instead of push |

### 12.3 Design Decisions

| Decision | Rationale | Alternative Considered |
|----------|-----------|----------------------|
| In-memory database | Speed (no disk I/O for spatial queries) | PostgreSQL + PostGIS |
| Pickle cache | Fastest serialization for Python objects | JSON, MessagePack |
| A* instead of Dijkstra | Goal-directed heuristic (haversine) | Dijkstra, Contraction Hierarchies |
| TOPSIS instead of weighted sum | Multi-criteria with tradeoff analysis | Simple weighted sum |
| OSRM locally instead of API | Cost savings, speed | Mapbox, GraphHopper |
| SerpAPI over direct scraping | Reliability (structured data) | Direct HTML scraping |
| GTFS instead of static data | Real schedules | Hardcoded bus routes |
| Glassmorphism over Material | Modern aesthetic | MUI, Ant Design |
| React Context over Redux | Simplicity for this scale | Redux, Zustand |
| LangGraph over n8n | Self-hosted, customizable | n8n (banned by user) |

---

## 13. Testing Strategy

### 13.1 Test Files

| File | Type | Tests | Purpose |
|------|------|-------|---------|
| `tests/test_fare_engine.py` | Unit | 15 | Fare calculation logic |
| `tests/test_segment_builder.py` | Integration | 8 | Segment building with GTFS |

### 13.2 Test Framework

**Pytest** with minimal dependencies. Tests focus on:
- Fare engine: edge cases (0 distance, surge, group sizes)
- Segment builder: basic segment construction, route destination finding

**Running tests:**
```bash
cd VOYAGER
python -m pytest tests/ -v
```

### 13.3 Test Coverage Gaps

| Area | Coverage | Priority |
|------|----------|----------|
| Fare engine | ✅ | High |
| Segment builder | ✅ | High |
| Transit graph (A*) | ❌ | Medium |
| Transit scoring (TOPSIS) | ❌ | Medium |
| API endpoints | ❌ | Medium |
| Frontend components | ❌ | Low |
| Scrapers | ❌ | Low |

---

## 14. Environment Configuration

### 14.1 `.env` File

```env
# Required
SERPAPI_API_KEY=your_key_here

# Optional (for additional features)
GOOGLE_MAPS_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret

# Proxy (optional)
PROXY_PROVIDER=none
SCRAPINGBEE_API_KEY=
SCRAPFLY_API_KEY=
```

### 14.2 `backend/core/config.py`

```python
class Settings:
    SERPAPI_API_KEY: str
    GOOGLE_MAPS_API_KEY: str | None
    OPENROUTER_API_KEY: str | None
    REDDIT_CLIENT_ID: str | None
    REDDIT_CLIENT_SECRET: str | None
    PROXY_PROVIDER: str = "none"
    SCRAPINGBEE_API_KEY: str | None
    SCRAPFLY_API_KEY: str | None
    DATA_CACHE_DIR: str = "data_cache"
```

---

## 15. Running the Project

### 15.1 Quick Start

```powershell
# 1. Start OSRM (Docker)
docker compose up -d osrm-car

# 2. Start Backend
cd VOYAGER
$env:PYTHONPATH = "C:\path\to\VOYAGER"
uvicorn backend.main:app --reload --port 8000

# 3. Start Frontend (separate terminal)
cd VOYAGER/frontend
npx vite --port 3000

# 4. Open browser
http://localhost:3000
```

### 15.2 Docker Full Stack

```powershell
docker compose up -d
```

### 15.3 OSRM Data Setup (One-time)

```powershell
# Download Karnataka PBF
curl -o osrm-data/karnataka-latest.osm.pbf https://download.geofabrik.de/asia/india/karnataka-latest.osm.pbf

# Extract, partition, customize
docker run --rm -v ${PWD}/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-extract -p /opt/car.lua /data/karnataka-latest.osm.pbf

docker run --rm -v ${PWD}/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-partition /data/car.osrm

docker run --rm -v ${PWD}/osrm-data:/data ghcr.io/project-osrm/osrm-backend \
  osrm-customize /data/car.osrm
```

---

## 16. Future Roadmap

### 16.1 Short-term (Next Sprint)

| Task | Priority | Effort | Notes |
|------|----------|--------|-------|
| Fix OSRM Foot OOM | Medium | 2 days | Smaller PBF (Bengaluru only) |
| Add Yelahanka metro data | Low | 1 day | Update CSV + reload |
| Fix JustDial scraper | Low | 1 day | Site may have changed |
| Refine bus→metro CASE 2 scoring | Medium | 1 day | Exclude reverse-direction |
| Add WebSocket for OSRM paths | Medium | 2 days | Push instead of poll |
| Tokenize ride fare types | Medium | 3 days | Replace fragile tuples with objects |

### 16.2 Medium-term

| Task | Priority | Notes |
|------|----------|-------|
| WebSocket for real-time segment updates | High | Push OSRM paths as they arrive |
| Cursor-based infinite scroll for results | Medium | Better UX for large result sets |
| User preferences (avoid metro, prefer AC) | Medium | Personalization |
| Share trip via link | Low | Social feature |
| PWA support (offline mode) | Low | Service worker |
| i18n (Kannada + Hindi) | Low | Localization |

### 16.3 Long-term

| Task | Notes |
|------|-------|
| Real-time bus tracking (GTFS-RT) | BMTC live feeds |
| Payment integration (QR code ticketing) | NCMC integration |
| Crowd-sourced data (seat availability) | User reports |
| Multi-city support (Mumbai, Delhi) | Additional GTFS feeds |
| Mobile app (React Native) | Cross-platform |
| AI trip recommendations | Learning from user patterns |
| Carbon footprint calculation | Environmental impact |

### 16.4 Technical Debt

| Item | Impact | Effort |
|------|--------|--------|
| Replace fragile positional tuples in `_RIDE_TYPES` | Medium (data classes) | 2 hours |
| Type hint coverage (backend is 95% untyped) | High for maintainability | 1 week |
| Remove dead code paths in segment_builder.py | Medium | 3 hours |
| Standardize error handling (specific exceptions) | Medium | 4 hours |
| Add request rate limiting | Low (localhost) | 2 hours |
| Comprehensive test suite | High | 2 weeks |

---

## Appendices

### Appendix A: API Response Format Convention

```json
{
  "status": "success" | "error",
  "data": { ... },       // For GET endpoints
  "routes": [ ... ],      // For POST /routes/plan
  "message": "..."        // Error details (if status=error)
}
```

### Appendix B: Coordinate Convention

- **Backend:** (lat, lng) — [latitude, longitude]
- **Frontend Leaflet:** (lat, lng) — [latitude, longitude]
- **OSRM / GeoJSON:** (lng, lat) — [longitude, latitude]
- **Conversion:** OSRM paths are reversed from [lng, lat] to [lat, lng] for Leaflet

### Appendix C: GTFS Route Number Format

BMTC route numbers follow the format:
- `XXX` (3 digits) — Core route
- `XXX-A`, `XXX-B`, etc. — Variant
- `XXX-YY` — Express variant
- `MF-XX` — Market feeder
- `KIA-X` — Airport route
- `V-XXX` — Vajra (AC) route
- `SBS-XXX` — School bus special

Route numbers in the database may have terminal suffixes from the CSV source (e.g., `MF-28 JKLO-ISROQ-LGRNB`). The `clean_route_short_name()` function strips these to keep only the route identifier.

### Appendix D: Score Calculation

**TOPSIS Score Range:** 10–99 (clamped)

**Score Color Mapping:**
| Score Range | Color | CSS |
|-------------|-------|-----|
| ≥ 80 | Green | `#22c55e` |
| 50–79 | Amber | `#eab308` |
| < 50 | Red | `#ef4444` |

**Reliability Pill Class:**
- `good` → Green (score ≥ 80)
- `bad` → Red (score < 50)  
- `mid` → Amber (50–79)

### Appendix E: Fare Tables

**BMTC Ordinary Bus Fare (per person):**
| Distance (km) | Fare (₹) |
|--------------|----------|
| 0–2 | 6 |
| 2–5 | 10 |
| 5–10 | 15 |
| 10–15 | 20 |
| 15–20 | 24 |
| 20–25 | 28 |
| 25+ | 32+ |

**BMTC AC Bus (Vajra) Fare:**
Ordinary fare × 1.5 (minimum ₹10)

**Metro Fare:**
| Distance (km) | Fare (₹) |
|--------------|----------|
| 0–2 | 11 |
| 2–5 | 21 |
| 5–10 | 32 |
| 10–15 | 42 |
| 15+ | 53 |

**Ride Fare (Karnataka Govt Rates):**
```
Total = Base Fare + (Distance - Free Km) × Per Km Rate
Surge = Total × 1.35 (peak time)
```

---

*End of Document*

**Version:** 1.0.0  
**Last Updated:** July 27, 2026  
**Total Sections:** 16  
**Appendices:** 5  
**Estimated Reading Time:** 60+ minutes  
**Estimated Print Pages:** 80+ (at ~300 words/page)
