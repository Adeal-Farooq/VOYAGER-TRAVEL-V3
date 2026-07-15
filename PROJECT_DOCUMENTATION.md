# VOYAGER — Complete Project Documentation

> **Bengaluru Multi-Modal Transit App**  
> Covers: Architecture, Feature Builds, Workflows, Code Structure, Data Flow, Known Issues, Roadmap  
> Last Updated: July 14, 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Backend Core](#4-backend-core)
5. [Database Layer](#5-database-layer)
6. [GTFS Integration](#6-gtfs-integration)
7. [Segment Builder System](#7-segment-builder-system)
8. [Frontend Architecture](#8-frontend-architecture)
9. [Route Planning (POST /api/routes/plan)](#9-route-planning)
10. [Live Pricing via LLM](#10-live-pricing-via-llm)
11. [OSRM Path Integration](#11-osrm-path-integration)
12. [Train Integration](#12-train-integration)
13. [KIA Bus Integration](#13-kia-bus-integration)
14. [Metro Integration](#14-metro-integration)
15. [Performance Optimization](#15-performance-optimization)
16. [GPS Live Tracking](#16-gps-live-tracking)
17. [Custom Waypoints](#17-custom-waypoints)
18. [Smart Filtering](#18-smart-filtering)
19. [Progressive Multi-Column UI](#19-progressive-multi-column-ui)
20. [Current Issues & Known Bugs](#20-current-issues--known-bugs)
21. [Next Steps & Roadmap](#21-next-steps--roadmap)
22. [Testing Guide](#22-testing-guide)
23. [Environment Setup](#23-environment-setup)
24. [Appendix: API Reference](#24-appendix-api-reference)
25. [Appendix: Data Structures](#25-appendix-data-structures)

---

## 1. Project Overview

### 1.1 What is VOYAGER?

VOYAGER is a **multi-modal transit planning web application** for Bengaluru, India. It helps users find the best route from point A to point B by combining:

- **Direct rides**: Cab (Uber/Ola), Auto, Bike (Rapido/Uber Moto), Walking
- **BMTC Buses**: Ordinary and AC Vajra with real GTFS departure times
- **Namma Metro**: With fare slabs
- **Indian Railways**: Long-distance trains (Bengaluru↔Mysuru/Hubballi/Mangaluru/Belagavi/Ballari)
- **KIA Airport Buses**: Vayu Vajra services to/from Kempegowda International Airport
- **Multi-modal chains**: Walk → Bus → Metro → Walk, Walk → Cab → Train → Auto, etc.

### 1.2 Core Philosophy

The app presents a **progressive disclosure** UI: instead of showing a single best route, it shows all practical options organized as columns. The user makes selections progressively:

1. **Column 0**: Direct door-to-door options (cab, auto, bike, walk)
2. **Column 1**: Nearby bus stops / metro stations / railway stations with reach options
3. **Column 2**: Transit options from the selected stop (buses with GTFS timings, metro, trains)
4. **Column N**: Next transit from arrival point (chained segments)
5. **Last Column**: Final mile options (walk, cab, auto to destination)

### 1.3 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | React 18, TypeScript, Vite 5 |
| Mapping | Leaflet (react-leaflet) |
| Styling | CSS Modules |
| GIS/Paths | OSRM public API (router.project-osrm.org) |
| Transit Data | BMTC GTFS (ZIP), CSV stop master, JSON fares |
| AI/LLM | OpenRouter (meta-llama/Llama 3.1 8B) or Gemini |
| Async | Python asyncio, httpx |
| Caching | Pickle (GTFS), in-memory dict (OSRM paths) |

---

## 2. System Architecture

### 2.1 High-Level Flow

```
User Browser (React)                     FastAPI Server (Python)
┌─────────────────────┐                ┌────────────────────────────┐
│  MainPage.tsx       │  HTTP /api/*   │  routes.py                 │
│  ┌───────────────┐  │ ◄────────────► │  ├── /all-segments        │
│  │ SearchBox     │  │                │  ├── /plan                │
│  ├───────────────┤  │                │  ├── /live-prices         │
│  │ Map (Leaflet) │  │                │  ├── /places              │
│  ├───────────────┤  │                │  └── /stops               │
│  │ SegmentPanel  │  │                │                             │
│  │  ┌─Col 0────┐ │  │                │  transit_service.py         │
│  │  │ Direct   │ │  │                │  ├── get_all_segments()     │
│  │  ├─Col 1────┤ │  │                │  ├── _build_single_segment  │
│  │  │ Stops    │ │  │                │  ├── _add_transit_options   │
│  │  ├─Col 2────┤ │  │                │  ├── _add_reach_options     │
│  │  │ Transit  │ │  │                │  └── get_osrm_path_between  │
│  │  ├─Col 3────┤ │  │                │                             │
│  │  │ Final    │ │  │                │  gtfs_service.py            │
│  │  └──────────┘ │  │                │  ├── load()                 │
│  └───────────────┘  │                │  ├── get_next_buses()       │
└─────────────────────┘                │  └── get_common_routes()    │
                                       │                             │
                                       │  database.py                │
                                       │  ├── Bus stops (CSV)       │
                                       │  ├── Metro stations        │
                                       │  ├── Railway stations      │
                                       │  └── Transit fares         │
                                       │                             │
                                       │  llm_agent.py               │
                                       │  └── get_live_prices()      │
                                       └────────────────────────────┘
```

### 2.2 Request Lifecycle (all-segments)

```
1. User selects A→B on map/search
2. Frontend calls GET /api/routes/all-segments?from_lat&from_lng&dest_lat&dest_lng...
3. routes.py get_all_segments():
   a. transit_service.get_all_segments() → builds segment tree (synchronous)
      i.  Find nearby bus stops (1.0km radius), metro stations (3.0km), railway stations (10km)
      ii. For each stop, build a segment entry with reach options
      iii. For each reachable stop, find transit options (buses with common routes, metro, trains)
      iv.  For each transit option, if arrival is >0.5km from dest, create next segment
      v.   Recurse for next segments (up to max_depth)
   b. Fire LLM live pricing concurrently → task
   c. Collect OSRM path requests → run with semaphore (max 15 concurrent, 3s timeout)
   d. Apply live prices to direct/reach options
   e. Interpolated fallback for any option still missing path
   f. Strip internal keys (needs_next_segment)
   g. Return sanitized response
4. Frontend renders segment columns based on chainState
```

### 2.3 Ports

| Service | Port | Notes |
|---------|------|-------|
| Backend (FastAPI) | 8000 | `python -m uvicorn backend.main:app --reload --port 8000` |
| Frontend (Vite) | 3000 | Proxies `/api` → `localhost:8000` |
| N8N (optional) | 5678 | Webhook for external automations |

---

## 3. Directory Structure

```
VOYAGER/
├── backend/
│   ├── main.py                    # FastAPI app entry, CORS, lifespan
│   ├── api/
│   │   └── routes.py              # ALL API endpoints (650+ lines)
│   ├── services/
│   │   ├── transit_service.py     # Core routing logic (1800+ lines)
│   │   ├── gtfs_service.py        # GTFS loader, cache, bus timings (248 lines)
│   │   └── n8n_service.py         # N8N webhook integration (lightweight)
│   ├── agents/
│   │   └── llm_agent.py           # LLM integration (OpenRouter/Gemini) (329 lines)
│   ├── core/
│   │   ├── database.py            # Transit data (bus stops, metro, rail, fares) (286 lines)
│   │   └── config.py              # Settings from .env (pydantic-settings)
│   ├── models/
│   │   └── transit.py             # Pydantic request models
│   └── data/
│       ├── bmtc_gtfs.zip          # GTFS data (stops.txt, routes.txt, stop_times.txt, trips.txt, shapes.txt)
│       ├── bmtc_all_stops_master.csv  # 20K+ bus stops with route counts
│       ├── bengaluru_metro_network.csv # Metro stations
│       ├── transit_fares.json     # Fare slabs (BMTC, Metro)
│       ├── railway_stations.json  # Railway stations
│       └── kia_routes_fare_full.json # KIA Vayu Vajra routes
│   └── processed/
│       └── gtfs_cache.pkl         # Pickled GTFS data (~5MB, loads instantly)
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Router setup
│   │   ├── main.tsx               # Entry point
│   │   ├── types/
│   │   │   └── index.ts           # All TypeScript interfaces
│   │   ├── services/
│   │   │   └── api.ts             # API client functions
│   │   ├── components/
│   │   │   ├── SegmentPanel.tsx   # Progressive multi-column UI (core component)
│   │   │   ├── MapView.tsx        # Leaflet map with markers, routes, live tracking
│   │   │   ├── SearchBox.tsx      # Location search with suggestions
│   │   │   └── WeatherWidget.tsx  # Weather impact display
│   │   ├── pages/
│   │   │   └── MainPage.tsx       # Main orchestrator (map + panel + search)
│   │   ├── utils/
│   │   │   └── helpers.ts         # Mode icons, labels, formatting
│   │   └── styles/
│   │       ├── MainPage.css
│   │       ├── SegmentPanel.css
│   │       └── MapView.css
│   ├── index.html
│   ├── vite.config.ts             # Proxy /api → 8000
│   └── package.json
├── .env                           # API keys, provider selection
├── AGENTS.md                      # Project summary for AI assistants
└── PROJECT_DOCUMENTATION.md       # THIS FILE
```

---

## 4. Backend Core

### 4.1 main.py

**Path**: `backend/main.py`

Responsibilities:
- Create FastAPI app with CORS (allow all origins for dev)
- Mount API routers under `/api`
- Initialize database on startup (via `db.initialize()`)
- Expose `/health` endpoint
- Serve static frontend build in production

Key Code:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.database import db
from backend.api.routes import router as api_router

app = FastAPI(title="VOYAGER API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
app.include_router(api_router)

@app.on_event("startup")
async def startup():
    db.initialize()
```

### 4.2 config.py

**Path**: `backend/core/config.py`

Uses `pydantic-settings` to read `.env`:

```python
class Settings(BaseSettings):
    LLM_PROVIDER: str = "openrouter"           # "openrouter" | "gemini"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    OPENROUTER_FALLBACK_MODELS: list = [...]
    GEMINI_API_KEY: str = ""
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    DATA_CACHE_DIR: str = "backend/data"
    PROCESSED_DIR: str = "backend/processed"
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook"
    DEBUG: bool = False
```

### 4.3 routes.py

**Path**: `backend/api/routes.py` (688 lines)

All API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/routes/all-segments` | GET | Main endpoint — returns complete segment tree |
| `/api/routes/plan` | POST | Route plan with scored options |
| `/api/routes/mini-path-options` | GET | Simplified path options |
| `/api/routes/segment-step` | GET | Single step of segment building |
| `/api/routes/bus-stops` | GET | Search bus stops by name |
| `/api/routes/metro-stations` | GET | All metro stations |
| `/api/routes/kia-routes` | GET | KIA bus routes data |
| `/api/routes/transit-fares` | GET | Fare slab data |
| `/api/routes/live-prices` | GET | LLM-estimated ride prices |
| `/api/routes/traffic-overlay` | GET | Traffic data overlay |
| `/api/routes/news` | GET | Transit news |
| `/api/n8n-status` | GET | N8N webhook status |
| `/api/search/places` | GET | AI place search |
| `/api/search/nearby` | GET | Nearby places search |
| `/api/search/suggestions` | GET | Search suggestions |
| `/api/search/ai-chat` | GET | AI chat for transit queries |
| `/api/search/ride-prices` | GET | Ride price estimation |
| `/api/search/current-events` | GET | Current events in Bengaluru |
| `/api/search/verify-place` | GET | Place verification |
| `/api/search/enrich-place` | GET | Place data enrichment |
| `/health` | GET | Health check |

---

## 5. Database Layer

### 5.1 database.py

**Path**: `backend/core/database.py` (286 lines)

Class: `TransitDatabase` (Singleton)

#### Datasets Loaded:

| Dataset | File | Records | Fields |
|---------|------|---------|--------|
| Bus Stops | `bmtc_all_stops_master.csv` | ~20,000 | stop_id, name, lat, lng, routes (dict of route_id→trip_count) |
| Metro Stations | `bengaluru_metro_network.csv` | ~60 | name, line, lat, lng, station_code, next_station, distance_to_next, is_interchange |
| Railway Stations | `railway_stations.json` | ~30 | name, lat, lng, code, zone |
| KIA Routes | `kia_routes_fare_full.json` | ~30 routes | route_id, stops, fare, schedule |
| Transit Fares | `transit_fares.json` | — | bmtc_ordinary_slabs, namma_metro_slabs |

#### Key Methods:

```python
def find_nearby_bus_stops(self, lat, lng, radius_km=1.0) -> list[dict]
    # Returns stops sorted by distance, filtered by radius

def find_nearby_metro_stations(self, lat, lng, radius_km=3.0) -> list[dict]
    # Returns metro stations sorted by distance

def find_nearby_railway_stations(self, lat, lng, radius_km=10.0) -> list[dict]
    # Returns railway stations sorted by distance

def find_stop_by_name(self, name) -> dict | None
    # Fuzzy matches stop by name (case-insensitive, substring)

def get_bmtc_ordinary_fare(self, distance_km) -> float
    # Returns fare from slab table (max 6 minimum)

def get_bmtc_ac_fare(self, distance_km) -> float
    # AC Vajra fare (2x ordinary, minimum 12)

def get_metro_fare(self, distance_km) -> float
    # Namma Metro fare slab
```

#### Stop Data Structure (from CSV):

```python
{
    "stop_id": "1234",
    "name": "Yelahanka Old Town",
    "lat": 13.108,
    "lng": 77.595,
    "routes": ["289-D", "PHS-34", "YHKOT-TMK-KMT", "PTN-YHKOT", "GKVK-YHKOT", ...]
}
```

⚠️ **Important**: CSV route IDs (like "YHKOT-TMK-KMT") are **point-to-point identifiers** from BMTC's internal system. They do NOT match GTFS `route_short_name` values (like "290-EB", "407-E"). The CSV has ~20K stops, GTFS only has ~1,274 stops (100K stop_times limit).

---

## 6. GTFS Integration

### 6.1 gtfs_service.py

**Path**: `backend/services/gtfs_service.py` (259 lines)

Class: `GTFSLoader`

#### Data Loaded from `bmtc_gtfs.zip`:

| GTFS File | What We Extract |
|-----------|----------------|
| `stops.txt` | stop_id, stop_name, stop_lat, stop_lon → `_stops_by_name` dict |
| `shapes.txt` | shape_id, lat, lon, sequence → `_shapes` dict of coord arrays |
| `routes.txt` | route_id → route_short_name mapping → `route_id_to_name` |
| `trips.txt` | trip_id → route_id mapping |
| `stop_times.txt` | trip_id, stop_id, departure_time (limited to 100K rows) |
| `trips.txt` + `shapes.txt` | trip_id → shape_id mapping |

#### In-Memory Structures:

```python
_stops_by_name: dict      # "stop name" → (lat, lng, stop_id)
_stop_times: dict          # "stop_name" → [(departure_time, route_short_name), ...]  (max 20 per stop)
_stop_to_shapes: dict      # "stop_name" → [(shape_id, stop_sequence), ...]
_route_shapes: dict        # "route_short_name" → [shape_id, ...]
_shapes: dict              # shape_id → [(lat, lng), ...]
```

#### Key Methods:

```python
def get_next_buses(stop_name, limit=3) -> list[dict]
    # Returns [{"departure_time": "14:30:00", "route": "290-EB"}, ...]
    # Filters by current time (only future buses), sorted ascending

def get_all_buses_at_stop(stop_name) -> dict
    # Returns {"290-EB": ["14:30:00", "15:00:00"], "407-E": ["14:45:00"], ...}
    # Grouped by route, sorted by earliest departure

def get_shape_between_stops(from_name, to_name) -> list[list[float]] | None
    # Finds a shape that goes through both stops, clips segment between them

def get_common_routes(src_name, dest_name) -> list[str]
    # Finds route_short_names common to both stops using _stop_times data

def get_shape_by_route(route_short_name) -> list[list[float]] | None
    # Returns shape coordinates for a given route
```

### 6.2 GTFS Caveats

1. **100K row limit**: Only first 100,000 rows of `stop_times.txt` are loaded (~1,274 stops, ~158 unique routes)
2. **20 per stop limit**: Only 20 departure times stored per stop
3. **Name mismatches**: GTFS stop names may not match CSV stop names exactly (spelling, abbreviations like "STN" vs "Station")
4. **Cache**: After first load (~45s), data is pickled to `gtfs_cache.pkl` for instant startup (~1s)
5. **Incomplete coverage**: Many bus stops exist in CSV but have no GTFS data (missing from the 100K limit)
6. **Route short names**: GTFS uses route_short_name like "290-EB", "407-E" which are user-friendly bus numbers. CSV uses different internal route IDs.

### 6.3 GTFS Cache Mechanism

```python
_CACHE_PATH = "backend/processed/gtfs_cache.pkl"

def _try_load_cache(self) -> bool:
    if os.path.exists(_CACHE_PATH):
        with open(_CACHE_PATH, "rb") as f:
            data = pickle.load(f)
            self.__dict__.update(data)
        return True
    return False

def _save_cache(self):
    with open(_CACHE_PATH, "wb") as f:
        pickle.dump({k: v for k, v in self.__dict__.items() if k != "_loaded"}, f)
```

- **First run**: Loads GTFS ZIP (~45s), saves cache
- **Subsequent runs**: Loads pickle instantly (~1s)
- **Cache invalidation**: Delete `gtfs_cache.pkl` to force reload

---

## 7. Segment Builder System

### 7.1 Overview

The segment builder is the **core algorithm** in VOYAGER. It builds a recursive tree of travel segments, where each segment represents a decision point:

- **Segment 0**: Starting point (user's location or source address)
  - Direct options (cab, auto, bike, walk to destination)
  - Nearby stops with reach options (how to get to each stop)
- **Segment 1..N**: Transit arrival points
  - Direct options from this arrival to destination
  - Nearby stops around this arrival
  - Transit options from those stops

### 7.2 Entry Point

**File**: `backend/services/transit_service.py`

```python
def get_all_segments(self, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name,
                     group_size=1, budget=None, max_depth=3) -> dict
```

**Flow**:
1. Gather nearby stops (bus, metro, railway) from source
2. Build first segment with `_build_single_segment()`
3. For transit options that arrive >0.5km from dest, create new segments recursively
4. Limit to `max_depth` levels
5. Return segment tree with `total_segments` count

### 7.3 _build_single_segment()

```python
def _build_single_segment(self, from_lat, from_lng, from_name, dest_lat, dest_lng,
                          dest_name, group_size, budget, depth=0, max_depth=3,
                          next_from_map=None, seen_stops=None, is_long_dist=False) -> dict
```

**Parameters**:
- `next_from_map`: Dict of `{stop_key: segment_index}` to avoid recreating segments for already-visited stops
- `seen_stops`: Set of stop keys to avoid infinite loops
- `depth`: Current recursion depth

**Returns**:
```python
{
    "segment_index": 0,
    "type": "source",
    "from": {"name": "Yelahanka 5th Phase", "lat": 13.101, "lng": 77.596},
    "next_from_map": {"yelahanka old town__13.108_77.595": 1, ...},
    "direct_options": [...],
    "destinations": [...]
}
```

### 7.4 Direct Options (_add_direct_options)

Generated for every segment:

| Mode | Label | Fare Calc | Duration Calc |
|------|-------|-----------|---------------|
| `cab` | Uber Go / Ola Mini | 14 + dist×12 | dist×2 + 5 |
| `cab_xl` | Uber XL / Ola XL | 20 + dist×18 | dist×2 + 5 |
| `auto` | Auto | 10 + dist×8 | dist×2 + 8 |
| `bike` | Uber Moto / Rapido | 6 + dist×6 | dist×1.5 + 3 |
| `walk` | Walk | 0 | dist×12 |

**Smart filter**: When distance < 0.5km, only walk is shown.  
**Smart filter**: When distance > 2km, cab/auto/bike include extra fee.

### 7.5 Reach Options (_add_reach_options)

For each nearby stop, generate options to reach it:

| Mode | Condition |
|------|-----------|
| `walk` | Always when dist < 2km |
| `cab` | When dist > 0.3km |
| `auto` | When dist > 0.3km |
| `bike` | When dist > 0.5km |

**Smart filter**: When dist < 0.3km, only walk is shown.  
**Smart filter**: When group_size > 3, bike is hidden.

### 7.6 Transit Options (_add_transit_options)

#### For Bus Stops/Metro Stations:

For each destination bus stop (up to 3 nearest to destination):

1. Skip if transit distance < 0.5km
2. Find common route numbers using GTFS: `_gtfs.get_common_routes(src_name, dest_name)`
3. If GTFS finds no common routes, fall back to CSV route matching: `_get_bus_route_nums(stop, dest_stop)`
4. If common routes found → show each route as separate option with GTFS departure times
5. If no common routes → show ALL available GTFS routes from the source stop with timings
   (each route as a separate option with its bus number and departure times)

**Each transit option includes**:
```python
{
    "mode": "bus_ordinary",
    "label": "Bus 407-E",
    "route_number": "407-E",
    "from": "Yelahanka Old Town",
    "to": "Yediyurappanagara",
    "distance_km": 3.5,
    "duration_minutes": 14,
    "fare": 24,          # total for group
    "per_person": 6,
    "from_lat": 13.108,
    "from_lng": 77.595,
    "to_lat": 13.151,
    "to_lng": 77.559,
    "arrives_at_stop": True,
    "bus_times": [
        {"departure_time": "14:30:00", "route": "407-E"},
        {"departure_time": "15:00:00", "route": "407-E"}
    ],
    "transit_type": "bus",
    "dropoff_walk_min": 8,        # walk time from drop-off stop to final destination
    "dropoff_to_dest_km": 0.6,    # distance from drop-off to final destination
    "path": [[13.108, 77.595], ...],  # optional, interpolated or OSRM
    "next_segment_index": 1,      # array index of next segment (if chaining needed)
}
```

#### For Pure Metro Stations:

If stop type is "metro", show metro transit options to destination metro stations:
- Uses metro fare slabs
- Distance × 2 min travel time
- Only shown if metro is practical (within city limits)

#### For Railway Stations:

If stop type is "railway" AND `is_long_dist` is True:
- Shows train options using `_get_train_options()`
- Minimum 10km distance
- Includes departure/arrival times

### 7.7 Final Mile Options

For transit options that arrive within 2km of the destination:
- Walk option is added (if <2km)
- Cab/auto/bike options added (if >0.3km)

These are stored in `transit_option["final_options"]` array.

### 7.8 Segment Chaining

When a transit option arrives >0.5km from the destination:
1. A new `next_segment_index` is set to the array index of the next segment
2. A new segment is created with the arrival point as its source
3. The segment is added to the segments array
4. The `next_from_map` dict prevents duplicate segments for the same stop

**Chaining threshold**: 0.5km (lowered from 2km to generate more useful mini-segments)

**Max depth**: 3 (configurable via `max_depth` parameter)

### 7.9 Key Code Flow

```
transit_service.py:
┌─────────────────────────────────────────────────┐
│ get_all_segments()                               │
│   ├── Find nearby stops (bus/metro/rail)          │
│   ├── _build_single_segment(depth=0, ...)         │
│   │   ├── _add_direct_options()                   │
│   │   ├── For each nearby stop:                   │
│   │   │   ├── _add_reach_options()                │
│   │   │   └── _add_transit_options()             │
│   │   │       ├── GTFS common route lookup        │
│   │   │       ├── CSV route fallback              │
│   │   │       ├── All GTFS routes fallback        │
│   │   │       └── Final mile options              │
│   │   └── For each transit with arrival>0.5km:    │
│   │       └── _build_single_segment(depth+1, ...) │
│   └── Return {segments, total_segments}            │
└─────────────────────────────────────────────────┘
```

---

## 8. Frontend Architecture

### 8.1 Types (types/index.ts)

```typescript
interface Stop {
  name: string; lat: number; lng: number;
  type: "bus" | "metro" | "railway";
  distance_km?: number;
}

interface DirectOption {
  mode: string; label: string; icon: string;
  fare: number; per_person: number;
  duration_minutes: number; distance_km: number;
  from_lat: number; from_lng: number;
  to_lat: number; to_lng: number;
  path?: number[][];
  live_provider?: string; live_eta?: number;
  from_name?: string; to_name?: string;
}

interface ReachOption extends DirectOption {
  from_stop_name?: string;
  to_stop_name?: string;
}

interface TransitOption {
  mode: string; label: string; icon: string;
  route_number?: string;
  from: string; to: string;
  distance_km: number; duration_minutes: number;
  fare: number; per_person: number;
  from_lat: number; from_lng: number;
  to_lat: number; to_lng: number;
  arrives_at_stop: boolean;
  bus_times?: { departure_time: string; route: string }[];
  transit_type: "bus" | "metro" | "train";
  dropoff_walk_min?: number;
  dropoff_to_dest_km?: number;
  next_segment_index?: number;
  final_options?: DirectOption[];
  next_transit?: TransitOption[];
  path?: number[][];
  departure_time?: string;
  arrival_time?: string;
}

interface Destination {
  stop: Stop;
  reach_options: ReachOption[];
  transit_options: TransitOption[];
  all_buses?: Record<string, string[]>;
}

interface Segment {
  segment_index: number;
  type: "source" | "transit" | "intermediate";
  from: { name: string; lat: number; lng: number; type?: string };
  direct_options: DirectOption[];
  destinations: Destination[];
}

interface SegmentResponse {
  status: string;
  data: {
    source: { name: string; lat: number; lng: number };
    dest: { name: string; lat: number; lng: number };
    segments: Segment[];
    total_segments: number;
  };
}
```

### 8.2 MainPage.tsx

**Path**: `frontend/src/pages/MainPage.tsx`

Responsibilities:
- Manages state: source, dest, segments, map markers/paths, GPS tracking
- Handles search → segment fetch flow
- Resizes map when segment panel opens/closes (adjusts map height)
- GPS "Start Journey" button → `watchPosition`
- Custom waypoints (intermediate stops)

Key State:
```typescript
const [source, setSource] = useState<[number, number] | null>(null);
const [dest, setDest] = useState<[number, number] | null>(null);
const [segments, setSegments] = useState<Segment[]>([]);
const [chainState, setChainState] = useState<Record<number, any>>({});
const [mapPaths, setMapPaths] = useState<any[]>([]);
const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
const [waypoints, setWaypoints] = useState<Waypoint[]>([]);
```

### 8.3 SegmentPanel.tsx

**Path**: `frontend/src/components/SegmentPanel.tsx`

This is the **most complex frontend component** (~500+ lines). It renders the progressive multi-column UI.

#### State Management:

```typescript
const [chainState, setChainState] = useState<Record<number, any>>({});
// chainState[segmentIndex] = {
//   pickedDestination: number,   // which destination was selected
//   pickedTransit: number,       // which transit option was selected
//   builtPath: TransitOption|ReachOption  // the actual option picked
// }
```

#### Column Rendering:

```
Column 0 (Segment 0)          Column 1 (Segment 0 dest)    Column 2 (Segment 1)
┌─────────────────────┐      ┌──────────────────────┐     ┌──────────────────────┐
│ Direct to Dest      │      │ Stop: Yelahanka OT   │     │ Stop: Yelahanka RTO  │
│ ├── Cab ~₹150       │      │ Reach Options:       │     │ Reach Options:       │
│ ├── Auto ~₹88       │      │ ├── Walk 8min        │     │ ├── Walk 3min        │
│ ├── Bike ~₹54       │      │ └── Auto ₹45          │     │ └── Auto ₹35         │
│ └── Walk 52min      │      │ Transit:             │     │ Transit:             │
│                      │      │ ├── Bus 407-E 🚌    │     │ ├── Bus 285-H 🚌    │
│ Nearby Stops:        │      │ │   ─ 14:30, 15:00  │     │ │   ─ 14:45, 15:15  │
│ ├── Yelahanka OT  🚏│      │ │   Walk 8min→Dest  │     │ │   Walk 5min→Dest  │
│ │   Walk 8min       │      │ ├── Bus 285-D 🚌    │     │ └── Cab ₹35 🚕     │
│ │   Auto ₹45        │      │ └── Cab ₹55 🚕      │     │                     │
│ ├── Yelahanka 5th   │      └──────────────────────┘     └──────────────────────┘
└─────────────────────┘
```

#### Key Handlers:

```typescript
handlePickDirect(segIdx, optIdx):
  // Marks a direct option as picked for this segment
  // Sets builtPath showing the direct option details

handlePickReach(segIdx, destIdx, optIdx):
  // Marks a reach option as picked
  // Sets builtPath showing walk/auto/cab to the stop

handlePickTransit(segIdx, destIdx, transitIdx):
  // Marks a transit option as picked
  // If next_segment_index exists, shows the next segment column
  // If final_options exist, shows final mile options
  // Updates builtPath with transit details

handleGoBack(segIdx):
  // Clears chainState for this segment and all following segments
  // Finds the correct parent segment using builtPath matching
  // Recalculates visible columns
```

#### Recommendation Card Display:

Each selected option is displayed with:
- Mode icon + label
- Walk time to stop (for reach options)
- From→To stops (for transit options)
- Dropoff walk time (for transit options)
- Fare details
- Next actions

#### Visual Design (CSS):

**File**: `frontend/src/styles/SegmentPanel.css`

- Horizontal scrollable columns
- Each column is 320px wide
- Selected options highlighted with accent color
- Cards have hover/active states
- Loading skeleton while fetching segments
- Scroll snapping between columns

---

## 9. Route Planning (POST /api/routes/plan)

### 9.1 Endpoint

```http
POST /api/routes/plan
Content-Type: application/json

{
  "source_lat": 12.971,
  "source_lng": 77.594,
  "dest_lat": 12.934,
  "dest_lng": 77.610,
  "budget": 500,
  "group_size": 1,
  "preferences": {
    "avoid_traffic": true
  }
}
```

### 9.2 Response

Returns scored route options combining multiple transport modes:

```json
{
  "status": "success",
  "data": {
    "routes": [
      {
        "type": "bus_mixed",
        "total_fare": 24,
        "total_duration_minutes": 35,
        "total_distance_km": 8.2,
        "overall_score": 85.5,
        "legs": [
          {"from": "Your Location", "to": "Bus Stop A", "mode": "walk", ...},
          {"from": "Bus Stop A", "to": "Bus Stop B", "mode": "bus_ordinary", "route_numbers": ["290-EB"], ...},
          {"from": "Bus Stop B", "to": "Your Destination", "mode": "walk", ...}
        ]
      }
    ]
  }
}
```

### 9.3 Route Generators

`get_route_legs_public()` calls these generators:

1. **`_generate_bus_routes()`** — Walk→Bus→Walk (1km radius for source/dest stops)
2. **`_generate_metro_routes()`** — Walk→Metro→Walk
3. **`_generate_metro_interchange_routes()`** — Walk→Metro→Metro→Walk (via interchanges)
4. **`_generate_kia_routes()`** — Walk→KIA Bus→Walk (for airport routes)
5. **`_generate_multi_modal_routes()`** — Complex chains: Walk→Bus→Metro→Walk etc.

### 9.4 Scoring (TOPSIS)

Each route is scored using TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution):
- Lower fare = better
- Lower duration = better
- Fewer transfers = better
- Score range: 0–100

---

## 10. Live Pricing via LLM

### 10.1 How It Works

1. Frontend calls `GET /api/routes/live-prices?source=...&dest=...&mode=cab`
2. Backend calls `llm_agent.get_live_prices(source, dest, mode)`
3. LLM returns estimated prices for Uber/Ola/Rapido
4. Prices are overlaid on direct and reach options in the segment UI

### 10.2 LLM Agent

**File**: `backend/agents/llm_agent.py`

```python
async def get_live_prices(self, source, dest, mode="cab") -> list[dict]:
    prompt = f"Estimate prices for {mode} from {source} to {dest} in Bengaluru..."
    text = await self._call_llm(system, prompt, json_mode=True)
    # Returns [{"provider":"Uber","mode":"cab","price":150,"eta_minutes":12}, ...]
```

### 10.3 Provider Selection

From `.env`:
```env
LLM_PROVIDER=openrouter    # or "gemini"
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
```

The `_call_llm` method:
1. If `LLM_PROVIDER == "openrouter"` and key exists → tries OpenRouter models
2. If `GEMINI_API_KEY` exists → tries Gemini models
3. Falls back through model list on failure

### 10.4 Integration in all-segments

Live pricing runs **concurrently** with OSRM path fetching:
```python
llm_task = asyncio.create_task(_fetch_live_prices())
# ... OSRM path fetching ...
live_prices = await llm_task
if live_prices:
    # Overlay prices on direct and reach options
```

If the LLM fails or times out (8s), prices simply aren't overlaid. Calculated fare from distance formula is used as fallback.

---

## 11. OSRM Path Integration

### 11.1 Service

**Function**: `transit_service.get_osrm_path_between(slat, slng, dlat, dlng, profile)`

- **Profile**: "driving" (for cab, auto, bike) or "walking" (for walk options)
- **URL**: `{OSRM_BASE_URL}/route/v1/{profile}/{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson`
- **Timeout**: 3 seconds per request
- **Cache**: In-memory dict `_path_cache` keyed by `(lat,lng,lat,lng,profile)`

### 11.2 Path Flow in all-segments

1. All **driving-mode options** (cab, auto, bike) in direct, reach, and final collect OSRM paths
2. **Walking options** use interpolated paths (straight lines) — OSRM for short walks is unnecessary
3. **Bus transit** uses interpolated paths (buses follow roads but GTFS shapes are preferred)
4. **Metro/train** use interpolated paths
5. **Concurrency**: Limited to 15 simultaneous requests via `asyncio.Semaphore(15)`
6. **Fallback**: If OSRM fails or times out, interpolated path is used

### 11.3 Endpoint

```http
GET /api/routes/plan?source=...&dest=...  (POST version uses OSRM for car routes)
```

### 11.4 Known Issue

The public OSRM server at `router.project-osrm.org` is rate-limited. With 15 concurrent requests:
- Each request takes ~1-3s
- ~8-10 requests total → ~5-8s total
- Timeouts cause fallback to interpolated paths

---

## 12. Train Integration

### 12.1 Hardcoded Train Data

**Location**: `transit_service.py` `_get_train_options()`

Routes covered:

| From | To | Example Train | Departure | Arrival |
|------|-----|---------------|-----------|---------|
| Bengaluru (SBC/BNC/YPR) | Mysuru (MYS) | Shatabdi, Mysore Exp | Multiple | ~2.5h |
| Bengaluru | Hubballi (UBL) | Golgumbaz Exp, etc. | Multiple | ~7h |
| Bengaluru | Mangaluru (MAQ) | Mangalore Exp | Multiple | ~8h |
| Bengaluru | Belagavi (BGM) | Rani Chennamma Exp | Multiple | ~7h |
| Bengaluru | Ballari (BAY) | Hampi Exp | Multiple | ~6h |

### 12.2 Station Name Normalization

15+ station name variants are normalized:
- "Yeshwantpur", "yeshwanthpur", "ypr", "yeshwantapur" → "Yeshwantpur"
- "KSR Bengaluru", "sbc", "bangalore city" → "KSR Bengaluru"
- "Mysuru", "mysore" → "Mysuru"

The `_get_train_options()` method first checks for known pairs, then returns generic defaults for unknown pairs.

### 12.3 Integration

Trains appear when:
- User selects a source/dest near a railway station (within 10km)
- `is_long_dist` flag is True (>30km between source and dest)
- Railway stop type is selected in segment builder

---

## 13. KIA Bus Integration

### 13.1 Data Source

**File**: `kia_routes_fare_full.json`

Contains ~30 KIA Vayu Vajra routes with:
- Route ID (e.g., "KIA-1", "KIA-2", "KIA-6", "KIA-6A")
- Route info / description
- Fare per person
- Stops (array of stop names)

### 13.2 Usage in Route Plan

`_generate_kia_routes()` finds KIA routes where:
- Source is within 2km of a KIA route stop
- Destination is within 2km of a KIA route stop (or is the airport)
- Route is built as: Walk→KIA Bus→Walk

### 13.3 Current Limitations

- No real-time tracking
- No departure timings from GTFS (KIA not in BMTC GTFS)
- Static fare data only
- Only recommended as airport transfer option

### 13.4 Future Enhancement Needed

- Fetch real-time KIA bus locations via API (if available)
- Add KIA bus stop locations to the stop database
- Show KIA buses in the segment UI alongside BMTC buses
- Display KIA route paths on map

---

## 14. Metro Integration

### 14.1 Data

**File**: `bengaluru_metro_network.csv`

Contains Namma Metro (Purple Line, Green Line) station data:
- Station name, code, line
- lat/lng coordinates
- Next station with distance
- Interchange flag

### 14.2 Fare Calculation

Slab-based: `transit_fares.json` → `namma_metro_slabs`
```json
[
  {"max_km": 2, "fare": 10},
  {"max_km": 5, "fare": 15},
  {"max_km": 10, "fare": 25},
  {"max_km": 15, "fare": 35},
  {"max_km": 20, "fare": 40},
  {"max_km": 50, "fare": 60}
]
```

### 14.3 Integration

- Metro appears when user is near a metro station (3km radius)
- Direct metro transit: Walk→Metro→Walk
- Metro interchange chains: Walk→Metro→Metro→Walk
- Segment builder: Metro stops are treated similarly to bus stops
- **No fake metro data**: When stop type is "metro", only real metro transit is shown (removed the hack where bus stops pretended to have metro departures)

---

## 15. Performance Optimization

### 15.1 Initial Performance (Before Optimization)

- GTFS loading: ~45s at startup (blocking)
- all-segments API: ~82s (OSRM + LLM)
- OSRM: 20+ sequential requests × 5s timeout = slow

### 15.2 Optimizations Applied

| Optimization | Impact | Technique |
|-------------|--------|-----------|
| GTFS Pickle Cache | 45s → 1s | Pickle serialization to `gtfs_cache.pkl` |
| OSRM Concurrency | 82s → 30s | `asyncio.Semaphore(15)` for parallel requests |
| OSRM Timeout Reduction | — | 5s → 3s per request |
| Only Driving OSRM | Reduces requests by ~60% | Walking uses interpolated paths |
| Bus Transit: No OSRM | Reduces requests | Interpolated paths for bus routes |
| LLM Concurrent with OSRM | — | `asyncio.create_task()` |
| LLM Timeout | — | 8s (configurable) |
| Free LLM Model | — | llama-3.1-8b-instruct (fast, free) |

### 15.3 Current Performance (After Optimization)

| Route | Before | After | Notes |
|-------|--------|-------|-------|
| Yelahanka 5th Phase → Sai Vidya | ~82s | ~13-15s | All features enabled |
| Yelahanka Old Town → MG Road | ~80s | ~10-12s | Fewer OSRM calls |
| Near stops → Near stops | ~70s | ~8-10s | Minimal OSRM |

### 15.4 Remaining Bottlenecks

1. **LLM call**: 8s timeout even when model works (llama-3.1-8b takes ~3-5s)
2. **OSRM rate limiting**: Public server at router.project-osrm.org is unreliable
3. **Segment building**: Synchronous DB lookups for ~20K stops (not a major issue ~2s)
4. **JSON serialization**: Large response (200K+ bytes) takes ~1-2s to serialize

### 15.5 Future Optimizations

1. **Response streaming**: Send initial segment data immediately, stream OSRM/LLM updates
2. **OSRM self-hosting**: Deploy local OSRM instance for Bengaluru
3. **LLM response caching**: Cache price estimates by route name pair
4. **Response compression**: Enable gzip in uvicorn
5. **Lazy GTFS loading**: Only load GTFS when first segment API is called
6. **Use connection pooling**: Reuse httpx client across requests

---

## 16. GPS Live Tracking

### 16.1 Implementation

**File**: `frontend/src/pages/MainPage.tsx`

```typescript
const [isJourneyStarted, setIsJourneyStarted] = useState(false);
const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
const watchIdRef = useRef<number | null>(null);

const handleStartJourney = () => {
  if (!isJourneyStarted && "geolocation" in navigator) {
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => setUserLocation([pos.coords.latitude, pos.coords.longitude]),
      (err) => console.warn("GPS error:", err.message),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );
    setIsJourneyStarted(true);
  }
};
```

### 16.2 Visual

- Green marker for live location (distinct from blue source marker)
- Path from source to current location
- Option to re-center map on user location
- "Stop Journey" button to clear watch

---

## 17. Custom Waypoints

### 17.1 Implementation

Users can add intermediate stops:

1. Search for a place
2. Click "Add as Waypoint"
3. A new segment is fetched from the last selected option to the waypoint
4. Waypoint appears on map as a distinct marker
5. Multiple waypoints can be added sequentially

### 17.2 Data Structure

```typescript
interface Waypoint {
  name: string;
  lat: number;
  lng: number;
  segments?: Segment[];
}
```

### 17.3 API Call

When a waypoint is added:
```
GET /api/routes/all-segments?from_lat={current}&from_lng={current}&dest_lat={waypoint}&dest_lng={waypoint}&...
```

---

## 18. Smart Filtering

### 18.1 Filters Applied

| Context | Filter | Logic |
|---------|--------|-------|
| Direct options | Distance < 0.5km | Only show walk |
| Direct options | Budget set | Skip options where fare > budget |
| Direct options | Group size > 3 | Hide bike |
| Reach options | Distance < 0.3km | Only show walk |
| Reach options | Budget set | Skip if fare > budget |
| Reach options | Group size > 3 | Hide bike |
| Transit options | Distance < 0.5km | Skip (too short for transit) |
| Transit options | Budget set | Skip if total > budget |
| Transit options | Common routes | Only show routes matching both stops |
| Transit options | GTFS fallback | Show all routes from source with timings |
| Train | Distance < 10km | Skip (too short for train) |
| Train | `is_long_dist` | Only shown for 30km+ journeys |

### 18.2 Ordering

- Direct options sorted by: fare ascending (for group_size 1) or duration ascending
- Reach options sorted by: distance ascending
- Transit options sorted by: duration ascending, then fare ascending
- Each list limited to top 5-8 options

---

## 19. Progressive Multi-Column UI

### 19.1 Concept

The UI progressively grows from 1 to N columns as the user makes selections:

1. **Initial**: Only Column 0 visible (direct options + nearby stops)
2. **After picking a stop**: Column 1 appears (reach options for that stop)
3. **After picking a reach option**: Column 2 appears (transit options from that stop)
4. **After picking a transit**: Next column appears (next segment or final mile)
5. **Maximum**: Limited by available chain depth

### 19.2 Implementation Details

**File**: `frontend/src/components/SegmentPanel.tsx`

```typescript
// Calculate which columns to show
const visibleColumns = useMemo(() => {
  const cols: { segIdx: number; type: string }[] = [];
  
  // Column 0 is always visible
  cols.push({ segIdx: 0, type: 'segment' });
  
  // If user picked a destination in segment 0, show reach options
  if (chainState[0]?.pickedDestination !== undefined) {
    cols.push({ segIdx: 0, type: 'reach' });
    
    // If user picked a transit option, show its transit details
    if (chainState[0]?.pickedTransit !== undefined) {
      const transit = segments[0]?.destinations[chainState[0].pickedDestination]
        ?.transit_options[chainState[0].pickedTransit];
      
      if (transit?.next_segment_index !== undefined) {
        cols.push({ segIdx: transit.next_segment_index, type: 'segment' });
      }
      if (transit?.final_options?.length) {
        cols.push({ segIdx: transit.next_segment_index, type: 'final' });
      }
    }
  }
  
  return cols;
}, [chainState, segments]);
```

### 19.3 Scroll Behavior

- Columns horizontally scrollable
- Auto-scroll to latest column when new one appears
- Each column has fixed width (320px)
- Container has `overflow-x: auto` with smooth scrolling

---

## 20. Current Issues & Known Bugs

### 20.1 High Priority

| # | Issue | Impact | Root Cause | Fix |
|---|-------|--------|------------|-----|
| 1 | **All-segments takes 10-30s** | Poor UX | OSRM rate limiting + LLM timeout | ⚠️ Partially fixed. Still need: OSRM self-hosting, response streaming |
| 2 | **Bus route numbers empty for many stops** | No bus number shown | GTFS only covers 1274 stops. Most destination stops have no GTFS data. | ✅ Partially fixed. Now shows all GTFS routes from source. Need: CSV→GTFS route mapping |
| 3 | **No AC bus option** | Users can't choose AC Vajra | `_add_transit_options` only adds `bus_ordinary` mode | Need: Add `bus_ac_vajra` mode with separate fare |
| 4 | **KIA buses not in segment UI** | Airport users can't see KIA options | KIA routes are only in route_plan, not in segment builder | Need: Add KIA stops to `find_nearby_bus_stops` or separate KIA segment |

### 20.2 Medium Priority

| # | Issue | Impact | Root Cause |
|---|-------|--------|------------|
| 5 | **Interpolated paths for buses** | Bus routes show straight lines, not road-following | OSRM skipped for bus transit. GTFS shape matching is incomplete |
| 6 | **Name mismatches between CSV and GTFS** | GTFS common route lookup fails for many stops | "Yelahanka Old Town" in CSV vs GTFS slight variations |
| 7 | **Segment chaining duplicates** | Same stop may appear in multiple segments | `next_from_map` logic doesn't catch all duplicates |
| 8 | **handleGoBack edge cases** | Multi-level chain navigation breaks | Complex state management in SegmentPanel |
| 9 | **No ride-hailing for short distances** | Uber/Ola shown for 0.5km walks | Needs: filter ride-hailing for <2km |
| 10 | **Budget filter too aggressive** | Single option may eat entire budget | Budget check applied per-option, not per-journey |

### 20.3 Low Priority

| # | Issue | Impact |
|---|-------|--------|
| 11 | **No KIA bus tracking** | Users can't see where KIA bus is |
| 12 | **No KIA departure timings** | Static data only |
| 13 | **No traffic overlay** | Duration estimates don't consider traffic |
| 14 | **No multi-language support** | Kannada/Hindi interface needed |
| 15 | **No PWA/offline mode** | Requires internet connection |
| 16 | **Map re-centers on every selection** | Disorienting for users exploring options |
| 17 | **CSS not responsive for mobile** | Fixed-width columns overflow on small screens |
| 18 | **No loading states on segment cards** | Users don't know which columns are still loading |

---

## 21. Next Steps & Roadmap

### 21.1 Immediate (Critical)

- [ ] **Fix all-segments speed**:
  - Self-host OSRM server (Docker: `ghcr.io/project-osrm/osrm-backend`) for Bengaluru
  - Or use local OSRM with Bengaluru OSM extract
  - Expected: 15s → 3-4s
  
- [ ] **Add AC Vajra buses**:
  - In `_add_transit_options`, add `bus_ac_vajra` mode alongside `bus_ordinary`
  - Use `db.get_bmtc_ac_fare()` for fare calculation
  - Mark AC buses with different icon/color in UI
  
- [ ] **KIA bus in segment UI**:
  - Add KIA stops to the nearby stops search
  - Create KIA bus transit options similar to BMTC
  - Show KIA route numbers and static fare info
  
- [ ] **Ride-hailing filter for short distances**:
  - Remove Uber/Ola/Rapido when direct distance < 2km
  - Only show walk (and maybe auto for 1-2km)

### 21.2 Short Term (Next Sprint)

- [ ] **GTFS→CSV route mapping**:
  - Build a mapping table from CSV route IDs to GTFS route_short_names
  - Use route descriptions/stop names to cross-reference
  - This will show bus numbers for ALL stops, not just GTFS-covered ones
  
- [ ] **OSRM path caching across requests**:
  - Current cache is per-request (in-memory dict)
  - Add persistent OSRM cache (file-based SQLite or JSON)
  - So common routes (like Majestic→KR Market) are instant on subsequent visits
  
- [ ] **Better segment chaining UI**:
  - Fix handleGoBack for all edge cases
  - Show which segment chain the user has built so far as a breadcrumb
  - Allow user to jump back to any previous step

- [ ] **Live tracking improvements**:
  - Show ETA to destination based on selected route
  - Re-route if user deviates from chosen path
  - Push notifications for bus departure times

### 21.3 Medium Term

- [ ] **Multi-language support**: Kannada, Hindi, Tamil
- [ ] **Progressive Web App (PWA)**: Offline cache of recent routes
- [ ] **User accounts**: Save favorite routes, recent searches
- [ ] **Route sharing**: Share route as link/screenshot
- [ ] **Traffic overlay**: Real-time traffic from Google Maps API or OSRM
- [ ] **Voice navigation**: Turn-by-turn instructions
- [ ] **Ticket booking**: Integration with BMTC/Namma Metro ticketing
- [ ] **Bus crowding data**: Show how crowded a bus is likely to be
- [ ] **Alternative routes**: Show 3-4 route options sorted by preference
- [ ] **Accessibility**: Wheelchair-friendly route option

### 21.4 Long Term

- [ ] **Inter-city travel**: Extend to other cities (Chennai, Hyderabad, Mumbai)
- [ ] **Auto-rickshaw tracking**: Real-time auto availability near stops
- [ ] **Carbon footprint**: Show emissions per route option
- [ ] **Subscription**: Premium features (no ads, priority support)
- [ ] **Partner integrations**: Uber/Ola direct booking API
- [ ] **ML-based predictions**: Predict bus arrival times using historical GTFS data
- [ ] **Community features**: Route ratings, driver reviews, safety reports

---

## 22. Testing Guide

### 22.1 Backend Testing

```bash
# Start backend
cd VOYAGER
python -m uvicorn backend.main:app --reload --port 8000

# Test all-segments endpoint
curl "http://localhost:8000/api/routes/all-segments?from_lat=13.101&from_lng=77.596&from_name=Yelahanka+5th+Phase&dest_lat=13.1575&dest_lng=77.5608&dest_name=Sai+Vidya&group_size=1"

# Test route plan
curl -X POST "http://localhost:8000/api/routes/plan" \
  -H "Content-Type: application/json" \
  -d '{"source_lat":12.971,"source_lng":77.594,"dest_lat":12.934,"dest_lng":77.610}'

# Test bus stops search
curl "http://localhost:8000/api/routes/bus-stops?q=yelahanka"

# Test metro stations
curl "http://localhost:8000/api/routes/metro-stations"

# Test live prices
curl "http://localhost:8000/api/routes/live-prices?source=Yelahanka&dest=MG+Road&mode=cab"

# Test GTFS bus timings
python -c "
from backend.services.gtfs_service import gtfs_loader
gtfs_loader.load()
print(gtfs_loader.get_next_buses('Yelahanka Old Town', 5))
"
```

### 22.2 Frontend Testing

```bash
# Start frontend dev server
cd VOYAGER/frontend
npx vite --port 3000

# Check if it loads
curl "http://localhost:3000"

# Common test flows:
# 1. Open http://localhost:3000
# 2. Search "Yelahanka 5th Phase" as source
# 3. Search "Sai Vidya" as destination
# 4. Wait for segments to load (~10-15s)
# 5. Click transit option → see bus timings
# 6. Click another transit → see chained segments
```

### 22.3 Test Routes (Known Working)

| Route | Status | Notes |
|-------|--------|-------|
| Yelahanka 5th Phase → Sai Vidya | ✅ Works | 407-E, 283-D buses available |
| Yelahanka Old Town → MG Road | ✅ Works | 290-EB, 298 YHKOT-BYNH |
| Puttenahalli → Rajanukunte | ✅ Works | Generic bus fallback |
| Majestic → KR Market | ✅ Works | Metro connection |
| Yelahanka → Kempegowda Airport | 🟡 Partial | No KIA in segment UI |
| Bengaluru → Mysuru | 🟡 Partial | Train shown but chaining needs work |

### 22.4 Debugging Tips

```bash
# Check if LLM is working
python -c "
from backend.agents.llm_agent import llm_agent
import asyncio
prices = asyncio.run(llm_agent.get_live_prices('Yelahanka', 'MG Road'))
print(prices)
"

# Check GTFS stop times
python -c "
from backend.services.gtfs_service import gtfs_loader
gtfs_loader.load()
times = gtfs_loader._stop_times.get('yelahanka old town', [])
print(f'Total times: {len(times)}')
for t, r in times[:5]:
    print(f'  {t} - {r}')
"

# Check common routes between two stops
python -c "
from backend.services.gtfs_service import gtfs_loader
gtfs_loader.load()
common = gtfs_loader.get_common_routes('Yelahanka Old Town', 'Yelahanka RTO Office')
print(f'Common routes: {common}')
"
```

---

## 23. Environment Setup

### 23.1 Prerequisites

```bash
# Python 3.12+
python --version

# Node.js 18+
node --version

# For Gemini LLM
pip install google-generativeai
```

### 23.2 Installation

```bash
# Clone and setup
git clone <repo-url>
cd VOYAGER

# Python virtual environment
python -m venv venv
.\venv\Scripts\Activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install Python deps
pip install fastapi uvicorn httpx pandas pydantic-settings python-dotenv
# For Gemini: pip install google-generativeai

# Install frontend deps
cd frontend
npm install
cd ..
```

### 23.3 Configuration

Create `.env` in root:

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
OPENROUTER_FALLBACK_MODELS=["meta-llama/llama-3.1-8b-instruct","mistralai/mistral-7b-instruct","google/gemini-2.0-flash-lite-001"]

# OR for Gemini:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your-gemini-key-here

N8N_WEBHOOK_URL=http://localhost:5678/webhook
DEBUG=true
```

### 23.4 Running

```powershell
# Terminal 1: Backend
cd VOYAGER
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd VOYAGER/frontend
npx vite --port 3000
```

### 23.5 LLM Model Costs (OpenRouter)

| Model | Cost/1M tokens | Speed | Quality |
|-------|---------------|-------|---------|
| meta-llama/llama-3.1-8b-instruct | Free | Fast | Good |
| mistralai/mistral-7b-instruct | Free | Fast | Good |
| google/gemini-2.0-flash-lite-001 | Free | Fast | Good |
| openai/gpt-4o-mini | $0.15/$0.60 | Medium | Excellent |
| openai/gpt-4o | $2.50/$10.00 | Slow | Best |

**Recommendation**: Use free models for development. Switch to GPT-4o-mini for production.

---

## 24. Appendix: API Reference

### 24.1 GET /api/routes/all-segments

**Purpose**: Main endpoint. Returns complete segment tree for multi-modal route discovery.

**Parameters**:
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| from_lat | float | ✅ | — | Source latitude |
| from_lng | float | ✅ | — | Source longitude |
| from_name | string | ❌ | "Your Location" | Source display name |
| dest_lat | float | ✅ | — | Destination latitude |
| dest_lng | float | ✅ | — | Destination longitude |
| dest_name | string | ❌ | "Destination" | Destination display name |
| group_size | int | ❌ | 1 | Number of passengers |
| budget | float | ❌ | null | Max budget per person |
| max_depth | int | ❌ | 3 | Max segment chaining depth |

**Response**: See Section 7 for full structure.

### 24.2 POST /api/routes/plan

**Purpose**: Returns scored multi-modal route plans.

**Request Body**:
```json
{
  "source_lat": 12.971,
  "source_lng": 77.594,
  "dest_lat": 12.934,
  "dest_lng": 77.610,
  "budget": 500,
  "group_size": 1,
  "preferences": {}
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "routes": [
      {
        "type": "bus_ordinary",
        "total_fare": 24,
        "total_duration_minutes": 35,
        "total_distance_km": 8.2,
        "overall_score": 85.5,
        "score_explanation": "Budget-friendly with moderate travel time",
        "legs": [...]
      }
    ]
  }
}
```

### 24.3 GET /api/routes/bus-stops

**Parameters**: `q` (string, required) — Search query

**Response**: List of matching stops with name, lat, lng, routes.

### 24.4 GET /api/routes/live-prices

**Parameters**: `source`, `dest`, `mode` (default: "cab")

**Response**: Array of price estimates from LLM.

### 24.5 GET /api/routes/transit-fares

**Response**: Fare slab data for BMTC and Metro.

---

## 25. Appendix: Data Structures

### 25.1 Full Segment Response

```json
{
  "status": "success",
  "data": {
    "source": {
      "name": "Yelahanka 5th Phase",
      "lat": 13.101,
      "lng": 77.596
    },
    "dest": {
      "name": "Sai Vidya Institute",
      "lat": 13.1575,
      "lng": 77.5608
    },
    "segments": [
      {
        "segment_index": 0,
        "type": "source",
        "from": {
          "name": "Yelahanka 5th Phase",
          "lat": 13.101,
          "lng": 77.596
        },
        "direct_options": [
          {
            "mode": "cab",
            "label": "Uber Go / Ola Mini",
            "icon": "🚕",
            "fare": 150,
            "per_person": 150,
            "duration_minutes": 12,
            "distance_km": 6.5,
            "from_lat": 13.101,
            "from_lng": 77.596,
            "to_lat": 13.1575,
            "to_lng": 77.5608,
            "path": [[13.101, 77.596], ...],
            "live_provider": "Uber",
            "live_eta": 8
          }
        ],
        "destinations": [
          {
            "stop": {
              "name": "Yelahanka Old Town",
              "lat": 13.108,
              "lng": 77.595,
              "type": "bus"
            },
            "reach_options": [
              {
                "mode": "walk",
                "label": "Walk to Yelahanka Old Town",
                "icon": "🚶",
                "fare": 0,
                "duration_minutes": 8,
                "distance_km": 0.6,
                "from_lat": 13.101,
                "from_lng": 77.596,
                "to_lat": 13.108,
                "to_lng": 77.595,
                "path": [[13.101, 77.596], [13.108, 77.595]]
              }
            ],
            "transit_options": [
              {
                "mode": "bus_ordinary",
                "label": "Bus 407-E",
                "icon": "🚌",
                "route_number": "407-E",
                "from": "Yelahanka Old Town",
                "to": "Yediyurappanagara",
                "distance_km": 3.5,
                "duration_minutes": 14,
                "fare": 24,
                "per_person": 6,
                "from_lat": 13.108,
                "from_lng": 77.595,
                "to_lat": 13.151,
                "to_lng": 77.559,
                "arrives_at_stop": true,
                "bus_times": [
                  {"departure_time": "14:30:00", "route": "407-E"},
                  {"departure_time": "15:00:00", "route": "407-E"}
                ],
                "transit_type": "bus",
                "dropoff_walk_min": 8,
                "dropoff_to_dest_km": 0.6,
                "path": [[13.108, 77.595], ..., [13.151, 77.559]],
                "next_segment_index": 1,
                "final_options": [
                  {
                    "mode": "walk",
                    "label": "Walk to Destination",
                    "icon": "🚶",
                    "fare": 0,
                    "duration_minutes": 8,
                    "distance_km": 0.6,
                    "from_lat": 13.151,
                    "from_lng": 77.559,
                    "to_lat": 13.1575,
                    "to_lng": 77.5608,
                    "path": [[13.151, 77.559], [13.1575, 77.5608]]
                  }
                ]
              }
            ],
            "all_buses": {
              "290-EA": ["14:15:00", "14:45:00"],
              "407-E": ["14:30:00", "15:00:00"],
              "285-D": ["14:20:00"]
            }
          }
        ]
      },
      {
        "segment_index": 1,
        "type": "transit",
        "from": {
          "name": "Yediyurappanagara",
          "lat": 13.151,
          "lng": 77.559
        },
        "direct_options": [...],
        "destinations": [...]
      }
    ],
    "total_segments": 2
  }
}
```

### 25.2 GTFS Cache Structure (pickle)

```python
{
    "_shapes": {"shape_1": [[12.97, 77.59], ...], ...},
    "_route_shapes": {"407-E": ["shape_1", "shape_3"], ...},
    "_stop_to_shapes": {"yelahanka old town": [("shape_1", 5), ...], ...},
    "_stops_by_name": {"yelahanka old town": (13.108, 77.595, "22640"), ...},
    "_stop_times": {"yelahanka old town": [("14:30:00", "407-E"), ...], ...},
    "_stops_by_name_inv": {"22640": "yelahanka old town", ...},
}
```

### 25.3 Chain State (Frontend)

```typescript
// Example: User picked walk to Yelahanka Old Town, then Bus 407-E
chainState = {
  0: {
    pickedDestination: 0,  // Index of Yelahanka Old Town in destinations array
    pickedReach: 0,        // Index of Walk option in reach_options array
    pickedTransit: 0,      // Index of Bus 407-E in transit_options array
    builtPath: {
      // The actual transit option object
      mode: "bus_ordinary",
      route_number: "407-E",
      from: "Yelahanka Old Town",
      to: "Yediyurappanagara",
      dropoff_walk_min: 8,
      ...
    }
  },
  1: {
    builtPath: {
      mode: "walk",
      from: "Yediyurappanagara",
      to: "Sai Vidya Institute",
      duration_minutes: 8,
      ...
    }
  }
}
```

---

## End of Documentation

*This document is a living reference for the VOYAGER project. Update it as features change.*
