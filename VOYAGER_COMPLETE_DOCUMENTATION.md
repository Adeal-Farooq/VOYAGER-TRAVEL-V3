# VOYAGER — Bengaluru Route Planner: Complete Documentation

> **Version:** 1.0.0  
> **Last Updated:** July 2026  
> **Location:** `C:\Users\len\OneDrive\Desktop\VOYAGER`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Data Sources & Transit Database](#3-data-sources--transit-database)
4. [Backend Components](#4-backend-components)
5. [Frontend Components](#5-frontend-components)
6. [API Reference](#6-api-reference)
7. [Route Planning Engine](#7-route-planning-engine)
8. [Segment Builder (Mini-Path / Step-by-Step)](#8-segment-builder)
9. [Scoring & Recommendations](#9-scoring--recommendations)
10. [GTFS Bus Route Geometry](#10-gtfs-bus-route-geometry)
11. [Traffic Overlay System](#11-traffic-overlay-system)
12. [ML & Optimization](#12-ml--optimization)
13. [Current State & Known Issues](#13-current-state--known-issues)
14. [Roadmap & Future Work](#14-roadmap--future-work)
15. [Appendix: File Reference](#15-appendix-file-reference)

---

## 1. Project Overview

### 1.1 What is VOYAGER?

VOYAGER is a **multi-modal route planning application** for Bengaluru, India. It helps users plan journeys from point A to point B using any combination of:

- **BMTC city buses** (ordinary, AC Vajra)
- **Namma Metro** (Green Line, Purple Line, interchanges)
- **KIA Vayu Vajra airport buses**
- **Personal car** (with fuel cost estimation)
- **Walking** (for short distances and last-mile connectivity)
- **Ride-hailing** (Uber, Ola, Rapido — price estimates via LLM)
- **Custom multi-stop journeys** via the segment builder

### 1.2 Core Features

| Feature | Status | Description |
|---------|--------|-------------|
| A→B route planning | ✅ Complete | Full multi-modal routes with turn-by-turn legs |
| Direct routes view | ✅ Complete | Scrollable route cards sorted by TOPSIS score |
| Segment builder | ✅ Complete | Step-by-step interactive route construction |
| Bus route geometry | ✅ Complete | Real road paths from GTFS shapes |
| Metro rail paths | ✅ Complete | Station-to-station line paths |
| Walking paths | ✅ Complete | OSRM walking profile with dashed polylines |
| Traffic overlay | ✅ Complete | GeoJSON roads with congestion heatmap |
| Ride price estimates | ✅ Partial | LLM-generated estimates (closed APIs) |
| AI recommendations | ✅ Complete | Route suggestions with weather/traffic context |
| Travel news | ✅ Complete | LLM-generated travel alerts & tips |
| Place search | ✅ Complete | OSM Nominatim + LLM fallback |
| Place enrichment | ✅ Complete | Reviews, images, hotel prices |

### 1.3 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript | UI components |
| Map | Leaflet + react-leaflet | Map rendering |
| HTTP | Axios | API client |
| Build | Vite 5 | Dev server & bundling |
| Backend | Python 3.12 + FastAPI | API server |
| Routing | OSRM (router.project-osrm.org) | Road path geometry |
| Geocoding | OSM Nominatim + LLM | Place search |
| LLM | OpenRouter (GPT-4o-mini) + Gemini | AI features |
| Transit data | GTFS (BMTC), CSV/JSON | Local transit database |
| ML | Custom TOPSIS, A* | Route scoring & optimization |

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (http://localhost:3000)               │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  React App (App.tsx)                                            │ │
│  │  ├── MainPage.tsx (orchestrator)                                │ │
│  │  ├── SearchPanel.tsx (place search)                             │ │
│  │  ├── AToBPanel.tsx (route planner)                             │ │
│  │  ├── MapView.tsx (Leaflet map)                                 │ │
│  │  ├── DiscoveryPanel.tsx (place details)                        │ │
│  │  ├── TripPanel.tsx (multi-destination stub)                    │ │
│  │  └── NewsOverlay.tsx (travel news)                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────────────┘
                         │ Axios /api/* (port 3000 → proxy port 8000)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    VITE PROXY (vite.config.ts)                       │
│                    http://localhost:3000/api/* → :8000               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│                   FASTAPI BACKEND (port 8000)                        │
│                                                                      │
│  main.py ─── router: search.py (/api/search/*)                      │
│          └── router: routes.py (/api/routes/*)                      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │ Services Layer                                                   ││
│  │  ├── transit_service.py   → Route generation, OSRM, GTFS         ││
│  │  ├── gtfs_service.py      → BMTC GTFS loader                     ││
│  │  ├── geocoding.py         → Place search + enrichment            ││
│  │  ├── llm_agent.py         → AI chat, recs, prices                ││
│  │  ├── n8n_service.py       → n8n webhook proxy                    ││
│  │  └── images.py            → Wikipedia image fetching             ││
│  ├──────────────────────────────────────────────────────────────────┤│
│  │ Core Layer                                                       ││
│  │  ├── database.py          → In-memory transit DB                 ││
│  │  └── config.py            → Settings (.env)                      ││
│  ├──────────────────────────────────────────────────────────────────┤│
│  │ ML Layer                                                         ││
│  │  ├── topsis.py            → Multi-criteria scoring               ││
│  │  ├── astar.py             → A* shortest path on transit graph    ││
│  │  └── data_preprocessor.py → CSV cleaning utilities               ││
│  └──────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  Data Files (DATA_CACHE_DIR = ./data_cache/)                         │
│  ├── bengaluru_metro_network.csv   → 52 stations, 2 lines            │
│  ├── bmtc_all_stops_master.csv     → ~9,783 bus stops                │
│  ├── bmtc_gtfs.zip                → GTFS feed (47MB)                 │
│  ├── transit_fares.json           → Fare slabs                       │
│  ├── kia_routes_fare_full.json    → Airport bus routes               │
│  ├── bangalore_roads.geojson      → 18 major roads for traffic       │
│  └── traffic_logs.csv             → Speed data for traffic           │
└─────────────────────────────────────────────────────────────────────┘
                         │
                         ▼ External Services
  ┌──────────┬──────────┬───────────┬──────────────┬──────────────┐
  │ OSRM     │ OSM      │ OpenRouter│ n8n (optional)│ Gemini (fall│
  │ route    │ Nominatim│ GPT-4o    │ (weather,    │ back LLM)   │
  │ profiles │ geocode  │ mini      │ reviews, etc)│             │
  └──────────┴──────────┴───────────┴──────────────┴──────────────┘
```

### 2.2 Directory Structure (Simplified)

```
VOYAGER/
├── backend/                     # FastAPI Python backend
│   ├── main.py                  # App entry point
│   ├── agents/
│   │   └── llm_agent.py        # LLM orchestration
│   ├── api/
│   │   ├── routes.py           # Route planning APIs (570 lines)
│   │   └── search.py           # Search & discovery APIs
│   ├── core/
│   │   ├── config.py           # Settings from .env
│   │   └── database.py         # In-memory transit DB
│   ├── models/
│   │   └── transit.py          # Pydantic models
│   └── services/
│       ├── transit_service.py  # Route engine (1027 lines)
│       ├── gtfs_service.py     # GTFS loader
│       ├── geocoding.py        # Place search
│       ├── n8n_service.py      # n8n proxy
│       └── images.py           # Image fetching
├── frontend/                    # React TypeScript frontend
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       ├── components/
│       │   ├── AToBPanel.tsx   # Main route panel (886 lines)
│       │   ├── MapView.tsx     # Leaflet map (362 lines)
│       │   ├── SearchPanel.tsx # Search UI
│       │   ├── DiscoveryPanel.tsx
│       │   ├── TripPanel.tsx
│       │   └── NewsOverlay.tsx
│       ├── pages/
│       │   └── MainPage.tsx    # App orchestrator
│       ├── services/
│       │   └── api.ts          # Axios API client
│       ├── types/
│       │   └── index.ts        # TypeScript interfaces
│       └── utils/
│           └── helpers.ts      # UI formatting utilities
├── ml/
│   ├── topsis.py               # Multi-criteria decision making
│   ├── astar.py                # A* pathfinding
│   └── data_preprocessor.py    # CSV preprocessing
├── data_cache/                  # Transit data files
├── workflows/                   # n8n workflow JSONs
└── scripts/                     # Test & utility scripts
```

---

## 3. Data Sources & Transit Database

### 3.1 Overview

All transit data is loaded **in-memory** at startup from local files in `DATA_CACHE_DIR` (default: `./data_cache/`). There is no external database (no PostgreSQL, no MongoDB). This makes the app fast to start but means all data must be updated by replacing the source files.

### 3.2 Database Singleton (`backend/core/database.py`)

```python
class TransitDatabase:
    # Singleton pattern via class variable
    _instance = None
    _initialized = False

    # Data structures (all loaded in initialize())
    metro_stations: list[dict]      # 52 stations
    metro_lines: dict[str, list]    # "Purple Line", "Green Line"
    bus_stops: dict[str, dict]      # ~9,783 stops keyed by name
    kia_routes: dict[str, dict]     # Airport bus routes
    transit_fares: dict             # Fare slabs
```

**Key methods:**

| Method | Purpose |
|--------|---------|
| `initialize()` | Loads all data from files |
| `find_nearby_bus_stops(lat, lng, radius_km)` | Returns bus stops within radius |
| `find_nearby_metro_stations(lat, lng, radius_km)` | Returns metro stations within radius |
| `find_stop_by_name(name)` | Fuzzy-match bus stop name |
| `get_metro_line_path(from_name, to_name)` | Returns station-to-station coordinates on same metro line |
| `get_bmtc_ordinary_fare(dist_km)` | Returns fare based on distance slab |
| `get_bmtc_ac_fare(dist_km)` | Returns AC bus fare |
| `get_metro_fare(dist_km)` | Returns metro fare |

### 3.3 Data Files

| File | Source | Size | Contents |
|------|--------|------|----------|
| `bengaluru_metro_network.csv` | Manual/curated | ~5KB | 52 stations with lat/lng, line, station_code |
| `bmtc_all_stops_master.csv` | BMTC GTFS extract | ~1.5MB | 9,783 bus stops with lat/lng |
| `bmtc_gtfs.zip` | Vonter/bmtc-gtfs (GitHub) | 47MB | Full GTFS: shapes, trips, stop_times, routes |
| `transit_fares.json` | Manual/curated | ~2KB | Fare slabs for bus, metro, KIA |
| `kia_routes_fare_full.json` | KIA website | ~20KB | Airport bus routes with stops & fares |
| `bangalore_roads.geojson` | Curated | ~10KB | 18 major roads as LineStrings |
| `traffic_logs.csv` | Simulated | ~50KB | Speed data for traffic overlay |

### 3.4 Metro Network

**56 stations** across 2 lines (with interchange at Majestic):

| Line | Stations | Color | Length |
|------|----------|-------|--------|
| Purple Line | 37 stations | Purple | ~43km (Baiyappanahalli → Kengeri) |
| Green Line | 29 stations | Green | ~30km (Nagasandra → Yelachenahalli) |

Metro rail path data is stored as coordinate sequences per station pair within each line. The `get_metro_line_path(from, to)` method interpolates between consecutive stations on the same line.

### 3.5 BMTC Bus Network

- **9,783 bus stops** across Bengaluru
- **4,359 routes** (from GTFS)
- **~2.4M shape points** (from GTFS)
- Fare slabs: Ordinary (₹5-25 based on distance slab), AC Vajra (₹7-40)

### 3.6 GTFS Feed (`backend/services/gtfs_service.py`)

The GTFS loader reads from `data_cache/bmtc_gtfs.zip` (47MB ZIP containing:

| File | Records | Purpose |
|------|---------|---------|
| `shapes.txt` | ~2.4M points | Bus route road geometry |
| `trips.txt` | ~190K trips | Trip-to-route mapping |
| `stop_times.txt` | ~5M entries | Stop sequences per trip |
| `stops.txt` | ~9,783 stops | Stop metadata |
| `routes.txt` | ~4,359 routes | Route metadata |

**Key methods in GTFSLoader:**

```python
gtfs_loader.load()  # Load all GTFS data (takes ~2-3 seconds on first call)
gtfs_loader.get_shape_between_stops(from_name, to_name)
    # Returns real bus road path between any two stop names
    # Uses stop-to-shape index for O(1) lookups
gtfs_loader.get_shape_by_route(route_short_name)
    # Returns full shape for a given route number
```

**Loading strategy:** Lazy-loaded on first use (called by `_add_leg_paths`). Cached in memory for subsequent calls.

---

## 4. Backend Components

### 4.1 Configuration (`backend/core/config.py`)

**File:** `backend/core/config.py` (49 lines)

Reads settings from `.env` file using `pydantic-settings.BaseSettings`:

```python
class Settings(BaseSettings):
    APP_NAME: str = "Voyager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    DATA_CACHE_DIR: str = "data_cache"
    LLM_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    GEMINI_API_KEY: str = ""
    N8N_WEBHOOK_URL: str = ""
    BANGALORE_CENTER_LAT: float = 12.9716
    BANGALORE_CENTER_LNG: float = 77.5946
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    FUEL_PRICE_PER_LITER: float = 102.0
    PETROL_AVG_MILEAGE: float = 15.0
```

### 4.2 LLM Agent (`backend/agents/llm_agent.py`)

**File:** `backend/agents/llm_agent.py` (~300 lines)

Orchestrates all AI-powered features:

| Feature | Method | Provider | Purpose |
|---------|--------|----------|---------|
| AI Place Search | `search_places_llm()` | OpenRouter | Semantic place search as Nominatim fallback |
| Place Verification | `verify_place()` | n8n → OpenRouter | Verify place exists and get details |
| Travel Recommendations | `get_travel_recommendations()` | OpenRouter | Suggest transport modes and tips |
| Live Prices | `get_live_prices()` | OpenRouter | Estimate Uber/Ola/Rapido fares |
| Weather Impact | `get_weather_traffic_impact()` | n8n → OpenRouter | Weather + traffic conditions |
| Travel News | `get_travel_news()` | OpenRouter | Generate travel alerts |
| Place Enrichment | `enrich_place_info()` | OpenRouter | Generate review summary |
| Current Events | `get_current_events()` | Web Search + LLM | Current events near a place |

**LLM calling strategy:**
1. Try OpenRouter (GPT-4o-mini) → 10s timeout
2. Fall back to Google Gemini → 10s timeout
3. Return cached or None on all failures

**Caching:** 24-hour TTL cache for all LLM responses stored in a module-level dict.

### 4.3 Geocoding Service (`backend/services/geocoding.py`)

**File:** `backend/services/geocoding.py` (~450 lines)

Combines multiple search strategies:

```
search_places(query, lat, lng)
  ├── 1. Check local transit DB (bus stops, metro stations, KIA routes)
  ├── 2. OSM Nominatim API call (with India bounding box filter)
  ├── 3. LLM AI fallback (semantic search)
  └── 4. Merge & deduplicate results
```

**Caching:** `SearchCache` class with 24-hour TTL, keyed by normalized query + location hash.

### 4.4 N8N Service (`backend/services/n8n_service.py`)

**File:** `backend/services/n8n_service.py` (~150 lines)

Proxies requests to optional n8n workflows for:

- **Place verification** → verifies place name/address via web search
- **Hotel price checking** → scrapes hotel prices
- **Weather/traffic check** → current weather + traffic conditions
- **Ride price estimation** → Uber/Ola price scraping (DEPRECATED — now uses LLM)
- **Place reviews** → scrapes review data

**Important:** n8n is **optional** and often unreachable. All n8n calls are wrapped in `asyncio.wait_for(timeout=5.0)` + try/except to prevent 500 errors.

---

## 5. Frontend Components

### 5.1 Component Hierarchy

```
App.tsx
└── MainPage.tsx
    ├── MapView.tsx (always visible)
    ├── SearchPanel.tsx (toggle by mode)
    ├── AToBPanel.tsx (A→B mode)
    │   └── RouteCard.tsx (inline sub-component)
    ├── TripPanel.tsx (Trip mode - stub)
    ├── DiscoveryPanel.tsx (overlay on place select)
    └── NewsOverlay.tsx (overlay)
```

### 5.2 AToBPanel (`frontend/src/components/AToBPanel.tsx`)

**Lines:** 886 — the most complex component.

**State management:**

| State | Type | Purpose |
|-------|------|---------|
| `sourceQuery`, `destQuery` | string | Input field values |
| `sourceSuggestions`, `destSuggestions` | PlaceResult[] | Autocomplete dropdown |
| `sourceLocation`, `destLocation` | [number, number] | Selected lat/lng (via props) |
| `waypoints` | {lat,lng,query}[] | Intermediate stops |
| `routes` | RouteOption[] | Planned routes from API |
| `selectedRoute` | number \| null | Which route is selected |
| `travelMode` | 'public' \| 'personal' \| 'walking' | Transport mode filter |
| `routerView` | 'direct' \| 'segment' | Direct routes vs segment builder |
| `prefs` | {budget?, groupSize} | User preferences |
| `segmentStep` | SegmentStepData \| null | Current segment step data |
| `segmentPath` | SegmentStepOption[] | Built segment path |
| `hoveredSegmentOption` | SegmentStepOption \| null | For map hover |

**Key flows:**

1. **Direct route planning:** User sets source + dest → clicks "Find Routes" → `handlePlanRoute()` → `POST /api/routes/plan` → renders RouteCards sorted by score

2. **Segment building:** User clicks "Segment Builder" → `handleStartSegmentBuilding()` → fetches `GET /api/routes/segment-step` from source → shows all options (direct + transit stops with reach/from-stop options) → user picks → adds to `segmentPath` → if arrives at stop, fetches next step from that stop → repeats until destination reached

3. **News fetching:** After routes loaded, starts polling `GET /api/routes/news` every 30s → renders NewsOverlay

4. **Route geometry:** `useEffect` emits `MapRouteGeometry[]` to parent whenever routes/segment/hover state changes → MapView renders polylines

**RouteCard sub-component:**
- Shows route type icon + label
- Score badge with color (Excellent/Good/Fair/Poor/Avoid)
- Stats: fare, duration, distance, walking distance
- Expandable leg details with per-leg colors
- Score bar visualization
- Recommended ("Best") badge for top route

### 5.3 MapView (`frontend/src/components/MapView.tsx`)

**Lines:** 362

**Rendering layers (bottom to top):**

1. **TileLayer** (OSM standard tiles)
2. **TrafficLayer** (toggleable overlay)
3. **Route outline polylines** (white, thick — for visibility)
4. **Route fill polylines** (colored — solid for transit, dashed for walking)
5. **Transit stop markers** (CircleMarker — green for metro, blue for buses)
6. **News markers** (colored circles with emoji popups)
7. **User location marker** (custom divIcon)
8. **Source/Destination markers** (custom divIcon with glow)
9. **Place markers** (colored pins with popups)
10. **Waypoint markers** (intermediate stop pins)

**Polyline colors:**
- Walk: `#94a3b8` (dashed `8, 6`)
- Walk to bus/metro: `#94a3b8` (dashed)
- Bus: `#3b82f6`
- Metro: `#22c55e`
- Cab/Car: `#f59e0b` / `#f97316`
- Auto: `#ef4444`

### 5.4 API Client (`frontend/src/services/api.ts`)

**Lines:** 122

Axios instance with:
- `baseURL: '/api'` → proxied by Vite to backend
- `timeout: 60000` (60 seconds — increased from 30s for route planning)

### 5.5 TypeScript Types (`frontend/src/types/index.ts`)

**Lines:** 244

Key interfaces:

```typescript
interface RouteOption {
  type: string                    // "bus_ordinary" | "metro" | "cab" | etc.
  total_fare: number
  total_duration_minutes: number
  total_distance_km: number
  total_walking_km: number
  overall_score: number           // 10-99
  legs: RouteLeg[]                // Individual segments
}

interface RouteLeg {
  from: string
  to: string
  mode: string                    // "walk" | "bus_ordinary" | "metro" | etc.
  distance_km: number
  duration_minutes: number
  fare: number
  route_numbers?: string[]
  from_lat/lng?: number
  to_lat/lng?: number
}

interface SegmentStepData {
  from: { lat, lng, name }
  dest: { lat, lng, name }
  direct_options: SegmentStepOption[]    // Walk + all rides
  via_stops: {
    stop: { name, lat, lng, type }       // 'bus' | 'metro'
    reach_options: SegmentStepOption[]   // How to get TO this stop
    from_stop_options: SegmentStepOption[] // What to do FROM this stop
  }[]
}
```

---

## 6. API Reference

### 6.1 Route Planning

#### `POST /api/routes/plan`

Plan a route from source to destination with optional waypoints.

**Request body:**
```json
{
  "source_lat": 12.9716,
  "source_lng": 77.5946,
  "dest_lat": 12.9344,
  "dest_lng": 77.6101,
  "mode": "default",          // "default" | "walking" | "personal"
  "budget": 200,
  "group_size": 2,
  "waypoints": []
}
```

**Response:**
```json
{
  "status": "success",
  "source": { "lat": 12.9716, "lng": 77.5946, "name": "..." },
  "destination": { "lat": 12.9344, "lng": 77.6101, "name": "..." },
  "routes": [ ... ],          // Up to 8 RouteOption objects
  "total_options": 8,
  "travel_insights": "...",
  "recommendations": {
    "recommended_mode": "metro",
    "estimated_cost_min": 30,
    "estimated_cost_max": 50,
    "estimated_time_minutes": 25,
    "safety_rating": 8,
    "tips": [...]
  },
  "weather": { ... }
}
```

**Processing pipeline (inside `handlePlanRoute`):**

```
1. Parse request body (simple or multi-stop with waypoints)
2. Get personal car route (OSRM driving) → estimate fuel cost
3. Get walking route (OSRM walking)
4. Get public transit routes (bus/metro/multi-modal → up to 8)
5. Add OSRM path geometry to all route legs (parallel with 30s timeout)
6. Get live ride prices (LLM)
7. Get weather/traffic info (n8n with 5s timeout, or LLM fallback)
8. Get travel recommendations (LLM)
9. Apply scoring adjustments:
   - Weather impact (rain → prefer metro, add +5 score)
   - Night-time safety (22:00-05:00 → cab scored +10)
   - Group size (larger groups → cheaper per-person routes boosted)
10. Return sorted routes + insights
```

**Timeout configuration:**
- Path enrichment: 30s total (`asyncio.wait_for(gather, 30.0)`)
- n8n weather: 5s per call
- OSRM single call: 5s per call
- Frontend overall: 60s

#### `GET /api/routes/segment-step`

Get available options for the next step in segment building.

**Parameters:**
```
from_lat, from_lng, from_name
dest_lat, dest_lng, dest_name
group_size (default: 1)
budget (optional)
```

**Returns:**
```json
{
  "from": { "lat": 12.9716, "lng": 77.5946, "name": "Your Location" },
  "dest": { "lat": 12.9344, "lng": 77.6101, "name": "Destination" },
  "direct_options": [
    {
      "mode": "walk", "label": "Walk", "icon": "🚶",
      "distance_km": 2.5, "duration_minutes": 30, "fare": 0,
      "from_lat": 12.9716, "from_lng": 77.5946,
      "to_lat": 12.9344, "to_lng": 77.6101
    },
    {
      "mode": "cab", "label": "Uber Go / Ola Mini", "icon": "🚕",
      "distance_km": 2.5, "duration_minutes": 8, "fare": 85,
      "per_person": 85, "group_capacity": 4
    }
  ],
  "via_stops": [
    {
      "stop": { "name": "Majestic", "lat": 12.9763, "lng": 77.5712, "type": "metro" },
      "reach_options": [
        { "mode": "walk", "distance_km": 0.8, "duration_minutes": 10, "fare": 0, ... },
        { "mode": "cab", "distance_km": 0.8, "duration_minutes": 3, "fare": 42, ... }
      ],
      "from_stop_options": [
        { "mode": "metro", "label": "Metro to MG Road", "fare": 30, "per_person": 15, "arrives_at_stop": true, ... },
        { "mode": "cab", "label": "Cab to Destination", "fare": 65, "arrives_at_stop": false, ... }
      ]
    }
  ]
}
```

#### `GET /api/routes/all-segments`

Generate all chained segments for progressive multi-column journey builder.

**Parameters:**
```
from_lat, from_lng, from_name        — current location
dest_lat, dest_lng, dest_name        — destination
group_size (default: 1)              — number of travelers
budget (optional)                    — max total budget ₹
max_depth (default: 3)               — max recursion depth for chained segments
```

**Returns (simplified):**
```json
{
  "status": "success",
  "data": {
    "source": { "lat": 12.97, "lng": 77.59, "name": "MG Road" },
    "dest": { "lat": 12.93, "lng": 77.61, "name": "Lalbagh" },
    "segments": [
      {
        "segment_index": 0,
        "from": { "name": "MG Road", "lat": 12.97, "lng": 77.59 },
        "direct_options": [ ... ],       // Walk + cab/auto/bike to dest
        "destinations": [
          {
            "stop": { "name": "Cubbon Park", "lat": 12.97, "lng": 77.59, "type": "bus" },
            "distance_from_current": 0.3, // km
            "reach_options": [ ... ],     // walk/cab/auto to reach this stop
            "transit_options": [          // what to do FROM this stop
              {
                "mode": "bus_ordinary",
                "route_number": "201A",
                "from": "Cubbon Park",
                "to": "Lalbagh Main Gate",
                "fare": 12,
                "arrives_at_stop": true,
                "final_options": [ ... ],  // last-mile to dest (when close enough)
                "next_segment_index": 1    // points to next segment (when still far)
              }
            ]
          }
        ]
      },
      {
        "segment_index": 1,
        "from": { "name": "BTM Layout", "lat": 12.91, "lng": 77.61 },
        "direct_options": [ ... ],       // from BTM Layout → Lalbagh directly
        "destinations": [ ... ]           // nearby stops from BTM Layout
      }
    ],
    "total_segments": 2
  }
}
```

**Processing pipeline:**

```
1. Build segment 0 from source location:
   a. Calculate direct distance to destination
   b. Add direct options (walk, cab, auto, bike filtered by budget/capacity)
   c. Find nearby bus stops (1km radius, max 6)
   d. Find nearby metro stations (2km radius, max 4)
   e. Find nearby railway stations (15km radius, max 3, only if long-distance)
   f. For each stop: add reach_options (walk + rides to reach stop)
   g. For each stop: add transit_options (buses, metro, trains going toward dest)
   h. For each transit_option: add final_options if arrival is within 2km of dest

2. Collect all transit_option arrival points that are still >2km from dest
3. Build segment 1, 2, ... (up to max_depth) from those arrival points:
   a. Same as step 1 but from the transit arrival location
   b. Each transit_option gets `next_segment_index` linking to next segment
   
4. Return flat segments array with next_segment_index linking
```

**Key data fields per transit_option:**
- `final_options[]` — walk + rides from transit arrival to dest (when arrival ≤ 2km from dest)
- `next_segment_index: number` — points to the next segment (when arrival > 2km from dest)
- `bus_times[]` — GTFS departure timings for bus routes
- `departure_time / arrival_time` — train schedule times
- `route_number` — bus/train number
- `transit_type` — "bus", "metro", or "train"

### 6.2 Complete Endpoint List

| Method | Path | Description | Parameters |
|--------|------|-------------|------------|
| POST | `/api/routes/plan` | Plan route | JSON body |
| GET | `/api/routes/metro-stations` | List metro stations | `line` (optional) |
| GET | `/api/routes/bus-stops` | List bus stops | `near_lat`, `near_lng`, `radius` |
| GET | `/api/routes/kia-routes` | List KIA routes | — |
| GET | `/api/routes/transit-fares` | Get fare slabs | — |
| GET | `/api/routes/live-prices` | Ride price estimates | `source`, `dest`, `mode` |
| GET | `/api/routes/all-segments` | All chained segments | `from_lat/lng/name`, `dest_lat/lng/name`, `group_size`, `budget`, `max_depth` |
| GET | `/api/routes/mini-path-options` | Legacy mini-path | `source_lat/lng`, `dest_lat/lng`, `group_size` |
| GET | `/api/routes/segment-step` | Legacy segment step | `from_lat/lng/name`, `dest_lat/lng/name`, `group_size`, `budget` |
| GET | `/api/routes/news` | Travel news | `source_name`, `dest_name` |
| GET | `/api/routes/traffic-overlay` | Traffic GeoJSON | — |
| GET | `/api/search/places` | Search places | `q`, `lat`, `lng` |
| GET | `/api/search/nearby` | Nearby places | `lat`, `lng`, `radius_km`, `place_type` |
| GET | `/api/search/suggestions` | Autocomplete | `q` |
| GET | `/api/search/verify-place` | Verify place | `name`, `address` |
| GET | `/api/search/ai-chat` | AI chat | `q`, `lat`, `lng` |
| POST | `/api/search/enrich-place` | Enrich place | JSON body |
| GET | `/api/search/ride-prices` | Ride prices | `source`, `destination` |
| GET | `/api/search/current-events` | Current events | `lat`, `lng` |
| GET | `/` | App info | — |
| GET | `/health` | Health check | — |
| GET | `/api/n8n-status` | n8n status | — |

---

## 7. Route Planning Engine

### 7.1 Route Generation (`backend/services/transit_service.py`)

The `TransitService` class generates all possible route combinations between two points.

#### 7.1.1 Public Transit Routes

**Entry point:** `get_route_legs_public(source_lat, source_lng, dest_lat, dest_lng, budget, group_size)`

**Pipeline:**

```
1. Calculate direct distance (haversine)
2. Generate candidate routes:
   ├── _generate_bus_routes()        → up to 2 bus routes (ordinary + AC)
   ├── _generate_metro_routes()       → up to 1 metro route per line
   ├── _generate_metro_interchange()  → up to 2 interchange routes
   ├── _generate_kia_routes()        → up to 1 KIA bus route
   └── _generate_multi_modal()       → up to 3 bus↔metro combos
3. Filter by budget (if set)
4. Score each route via TOPSIS
5. Add leg coordinates from database
6. Sort by score (descending)
7. Return top 8 routes
```

#### 7.1.2 Bus Route Generation

```
_nearby_src_stops = find_nearby_bus_stops(source, 1.0km)
_nearby_dest_stops = find_nearby_bus_stops(dest, 1.0km)

For each source_stop × dest_stop pair:
  1. Walking to source stop (dist × 12 min/km)
  2. Bus from source to dest stop (dist / 25 km/h × 60)
  3. Walking from dest stop to destination
  4. Fare = BMTC slab fare × group_size
  5. Route numbers = _find_common_routes(src_stop, dest_stop)
```

**Two variants per stop pair:**
- **Bus Ordinary:** `bus_ordinary` — cheaper, slower
- **Bus AC Vajra:** `bus_ac_vajra` — premium, slightly faster

#### 7.1.3 Metro Route Generation

```
_nearby_src_stations = find_nearby_metro_stations(source, 2.0km)
_nearby_dest_stations = find_nearby_metro_stations(dest, 2.0km)

For same-line station pairs:
  1. Walking to source station (dist × 12 min/km)
  2. Metro ride (station_count × 2 min + dist / 30 km/h)
  3. Walking from dest station to destination
  4. Fare = metro slab fare × group_size
```

**Interchange routes:** If source and dest are on different lines, creates routes that interchange at Majestic (the only interchange station).

#### 7.1.4 Multi-Modal Routes

```
_bus_to_metro: Walk → Bus → Walk → Metro → Walk
_metro_to_bus: Walk → Metro → Walk → Bus → Walk
```

These combine a bus leg to a metro station (or vice versa) for coverage where no single mode reaches both ends.

#### 7.1.5 Personal Car Route

```
_get_driving_route(source, dest):
  1. OSRM driving profile → duration + distance
  2. Fuel cost = (distance / mileage) × fuel_price
  3. No walking legs
  4. Type: "car"
```

#### 7.1.6 Walking Route

```
_get_walking_route(source, dest):
  1. Only if distance ≤ 10km
  2. OSRM walking profile → duration + path
  3. Type: "walk"
  4. Fare: 0
```

### 7.2 Route Path Enrichment

After routes are generated, each leg gets path geometry for map rendering.

**Method:** `_add_leg_paths(route)` (called from `routes.py` line 86 & 208)

**Processing** (parallelized with `asyncio.gather`):

```
For each leg in route:
  ├── Metro leg → get_metro_line_path(from, to) [DB, instant]
  ├── Bus leg → gtfs_loader.get_shape_between_stops(from, to) [GTFS, instant]
  ├── Walk leg → get_osrm_path_between(...) [OSRM walking, 5s timeout]
  └── Other (driving) → get_osrm_path_between(...) [OSRM driving, 5s timeout]
```

**Parallel execution:** All paths for all routes are fetched simultaneously with a 30-second total timeout.

**OSRM fallback:** If OSRM fails (network error, timeout, rate limit), the system generates an interpolated path with 12 intermediate points along the great-circle route. This ensures paths never appear as straight-line displacements.

### 7.3 Scoring System (TOPSIS)

Each route is scored on multiple criteria:

| Criterion | Weight | Scoring |
|-----------|--------|---------|
| Fare | 25% | `max(0, 100 - fare/10)` — cheaper = higher score |
| Duration | 30% | `max(0, 100 - duration/2)` — faster = higher score |
| Walking | 15% | `max(0, 100 - walk_km×15)` — less walking = higher score |
| Comfort | 20% | Mode-based: car=90, cab=85, metro=85, KIA=75, bus AC=70, bus ordinary=50, walk=40 |
| **Budget bonus** | extra | ≤40% of budget → +10; ≤70% → +5; >90% → -5; over budget → -15 |
| **Group bonus** | extra | Per-person cost ≤₹30 → +5 (for group > 1) |
| **Metro bonus** | extra | +5 for metro routes |
| **Known routes** | extra | +3 if route numbers available |

**Final score:** Range 10-99, clamped.

**Weighting rationale:**
- Time matters most (30%) — users want fast journeys
- Fare is second (25%) — cost matters
- Comfort reflects mode quality (20%)
- Walking is penalized (15%) — less walking preferred

---

## 8. Segment Builder (Progressive Multi-Column)

### 8.1 Overview

The segment builder lets users construct a custom journey **progressively** through a multi-column UI. Each column represents a segment in the journey, and columns appear one by one as the user makes selections. The number of columns varies based on journey complexity:
- **Short journey** (<2km): Just 1 column (direct walk/cab)
- **Medium journey** (2-15km): 3-4 columns (reach stop → transit → final mile)
- **Long journey** (>15km, out-of-city): 4-6 columns with multiple transit hops + trains

### 8.2 Architecture (Current - July 2026)

**Backend:** `get_all_segments()` in `transit_service.py` — generates ALL chained segments at once in a flat array, linked via `next_segment_index`.

**Endpoint:** `GET /api/routes/all-segments` → returns `{ status, data: { source, dest, segments[], total_segments } }`

**Frontend:** `SegmentPanel.tsx` — renders progressive columns:
- `chainState.activeSegIdx` — tracks which segment is currently active
- `chainState.selectedDest` — which stop user picked in the current segment
- `chainState.selectedTransit` — which transit option user picked
- `chainState.selectedFinal` — which final mile option user picked

### 8.3 Data Structure

Each segment is self-contained and reusable:

```json
{
  "segment_index": 0,
  "from": { "name": "MG Road", "lat": 12.97, "lng": 77.59 },
  "direct_options": [
    { "mode": "walk", "fare": 0, "duration_minutes": 30, ... },
    { "mode": "cab", "fare": 176, "duration_minutes": 8, ... }
  ],
  "destinations": [
    {
      "stop": { "name": "Cubbon Park", "lat": 12.97, "lng": 77.59, "type": "bus" },
      "distance_from_current": 0.3,
      "reach_options": [
        { "mode": "walk", "from": "MG Road", "to": "Cubbon Park", "fare": 0, "arrives_at_stop": true, ... },
        { "mode": "cab", "from": "MG Road", "to": "Cubbon Park", "fare": 42, "arrives_at_stop": true, ... }
      ],
      "transit_options": [
        {
          "mode": "metro",
          "from": "Cubbon Park",
          "to": "BTM Layout",
          "fare": 42,
          "arrives_at_stop": true,
          "transit_type": "metro",
          "final_options": [ ... ],           // last-mile from BTM Layout to dest
          "next_segment_index": 1             // if still >2km from dest, link to next segment
        }
      ]
    }
  ]
}
```

### 8.4 Segment Chaining Logic

When a transit option's arrival point is **>2km from destination**:
- A new segment is built from that arrival point
- The transit option gets `next_segment_index: N`
- The new segment has its own `from`, `direct_options`, `destinations[]`, etc.
- The flat segments array can be navigated by following `next_segment_index`

When a transit option's arrival point is **≤2km from destination**:
- `final_options[]` is populated with walk + rides from arrival to destination
- No next segment is generated

### 8.5 Column Layout (Frontend)

The SegmentPanel renders columns left to right as user makes selections:

```
┌─────────────────┐  ┌──────────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│ 🚕 DIRECT       │  │ 🚏 REACH A STOP      │  │ 🚌 TRANSIT:        │  │ 🏁 FINAL MILE    │
│ (from segment)  │  │ (from segment)        │  │ Cubbon Park        │  │ to Lalbagh       │
│                 │  │                       │  │                    │  │                  │
│ Walk 30min ₹0   │  │ 📍 From: MG Road      │  │ Metro to BTM Layt  │  │ Walk 10min ₹0    │
│ Cab 8min ₹176   │  │ ┌─────────────────┐   │  │                   │  │ Auto 5min ₹25    │
│ Auto 22min ₹120 │  │ │ Cubbon Park      │   │  │ 🏁 5 final opts    │  │ Cab 3min ₹42     │
│                 │  │ │ 0.3km away       │   │  │                    │  │                  │
│                 │  │ │ Walk 4min ₹0     │   │  │                    │  │                  │
│                 │  │ │ Cab 2min ₹42     │   │  │                    │  │                  │
│                 │  │ └─────────────────┘   │  │                    │  │                  │
│                 │  │ ┌─────────────────┐   │  │                    │  │                  │
│                 │  │ │ Vidhana Soudha   │   │  │                    │  │                  │
│                 │  │ │ (metro) 1.2km    │   │  │                    │  │                  │
│                 │  │ │ Walk 14min ₹0    │   │  │                    │  │                  │
│                 │  │ └─────────────────┘   │  │                    │  │                  │
└─────────────────┘  └──────────────────────┘  └────────────────────┘  └──────────────────┘
```

**Column visibility rules:**
- **Column 0 (DIRECT):** Always shown when segment has direct_options
- **Column 1 (REACH):** Always shown when segment has destinations
- **Column 2 (TRANSIT):** Appears when user selects a destination → shows its transit_options
- **Column 3 (FINAL):** Appears when user selects a transit with final_options
- **Next Segment columns:** When transit has `next_segment_index`, clicking it switches to that segment's columns (fresh Column 0-1-2 for the new "from" location)

### 8.6 Frontend State Machine

```
IDLE: no data loaded
  → fetch all-segments API → DATA_LOADED

DATA_LOADED:
  Shows Column 0 (Direct) + Column 1 (Destinations)
  User clicks reach_option → DEST_SELECTED

DEST_SELECTED:
  Shows Column 2 (Transit options for that stop)
  User clicks transit_option →
    if has next_segment_index → SEGMENT_CHAIN (switch to next segment)
    if has final_options → TRANSIT_SELECTED

TRANSIT_SELECTED:
  Shows Column 3 (Final mile options)
  User clicks final_option → JOURNEY_COMPLETE

SEGMENT_CHAIN:
  activeSegIdx updates to next_segment_index
  Shows NEW Column 0 (Direct from new from-location)
  + Column 1 (Destinations near new location)
  User repeats the flow

JOURNEY_COMPLETE:
  Shows full journey summary with timeline
  "Start Journey" button enables GPS tracking
```

### 8.7 Go Back / Reset

The user can go back at any point:
- **From Final →** deselects final, shows transit options again
- **From Transit →** deselects transit, shows destinations again
- **From Dest →** deselects dest, shows all destinations
- **From segment N →** goes back to segment N-1

### 8.8 Map Path Display

Each selected option renders on the map:
- **Colored polylines** cycling through SEGMENT_COLORS
- **Circle markers** at transit stops
- **Yellow highlight** on hovered option
- Path coordinates are either OSRM real roads or interpolated paths

### 8.9 Ride Types & Pricing

All rides priced per-person × group_size, filtered by capacity:

| Mode | Label | Base | Per KM | Capacity |
|------|-------|------|--------|----------|
| `walk` | Walk | ₹0 | — | ∞ |
| `cab` | Uber Go / Ola Mini | ₹25 | ₹14/km | 4 |
| `cab_xl` | Uber XL / Ola XL | ₹40 | ₹20/km | 6 |
| `auto` | Auto Rickshaw | ₹15 | ₹10/km | 3 |
| `bike` | Uber Moto / Rapido | ₹10 | ₹6/km | 1 |

**Live pricing overlay:** LLM agent fetches real-time Ola/Uber/Rapido prices (8s timeout). If available, these override the calculated fares and show provider name + ETA.

### 8.10 Transit Types

| Type | Source | Search Radius | Max |
|------|--------|---------------|-----|
| `bus` | `find_nearby_bus_stops()` | 1.0 km | 6 |
| `metro` | `find_nearby_metro_stations()` | 2.0 km | 4 |
| `railway` | `find_nearby_railway_stations()` | 15 km | 3 |

**Transit pricing:**
- **Bus:** `max(6, get_bmtc_ordinary_fare(distance))` per person using slab-based fares
- **Metro:** `distance × ₹3` per person, minimum ₹15
- **Train:** `distance × ₹0.8` per person, minimum ₹15

**Transit filtering:**
- Budget check: skip if `fare × group_size > budget`
- Bus routes: only show when common routes exist between stop and dest-area stop
- Metro: only when stop or dest supports metro connectivity
- Train: only for long-distance journeys (>40km or outside Bengaluru)
- GTFS bus timings: filtered by current time (shows next available buses)

### 8.11 Custom Waypoints

Users can add custom intermediate stops (not just transit stops):
1. Type a place name in the search box
2. Select from suggestions
3. System fetches fresh segment data from that location
4. New columns appear showing options from the custom waypoint

### 8.12 GPS Live Tracking

When journey is complete:
1. User clicks "▶ Start Journey"
2. Browser requests GPS permission (`watchPosition`)
3. Green live marker appears on map
4. Tracks user's progress in real-time
5. Button shows "🟢 Tracking" while active

### 8.13 What's Missing / Next Improvements

1. **Multi-segment chaining isn't working for short routes** — transit options that arrive within 2km of dest show final_options but don't chain to next segment. Need to handle "transit to nearby area, then more transit" for all routes.
2. **Transit options too few** — many bus stops show 0 transit options because no common bus routes found. Need fallback transit (metro, other buses).
3. **Edit previous segment** — user cannot go back and change a choice without resetting.
4. **Route comparison** — compare custom-built route vs auto-generated routes.
5. **Schedule integration** — use GTFS stop_times for departure/arrival predictions.
6. **Multiple route suggestions** — after each step, suggest 2-3 best continuations.
7. **Time constraints** — "arrive by X" or "depart at Y" filtering.
8. **Real-time transit** — GTFS-RT for live bus positions.
9. **Intermediate destinations** — better support for non-transit waypoints.
10. **Visual timeline** — Gantt-chart view of entire journey.

---

## 9. Scoring & Recommendations

### 9.1 TOPSIS Multi-Criteria Scoring

Located in `transit_service.py:_topsis_score()` and `ml/topsis.py`.

The backend `_topsis_score()` computes a composite score (10-99) for each route:

```
score = fareScore × 0.25 + durationScore × 0.30 + walkScore × 0.15 + comfort × 0.20
      + budgetBonus + groupBonus + metroBonus + knownRoutesBonus
```

**Scoring details:**

| Metric | Formula | Max Raw |
|--------|---------|---------|
| Fare | 100 - (fare ÷ 10) | 100 |
| Duration | 100 - (minutes ÷ 2) | 100 |
| Walking | 100 - (walk_km × 15) | 100 |
| Comfort | Mode-based lookup (40-90) | 90 |

**Comfort map:**
```
car=90, cab=85, metro_interchange=85, metro=85,
kia_bus=75, bus_ac_vajra=70, bus_to_metro=70, metro_to_bus=65,
bus_ordinary=50, walk=40
```

**Bonuses:**
- Budget: ≤40% → +10, ≤70% → +5, >90% → -5, >100% → -15
- Group: per-person ≤₹30 and group > 1 → +5
- Metro line route → +5
- Has route_numbers → +3

### 9.2 AI Recommendations

**Method:** `llm_agent.get_travel_recommendations(source_name, dest_name, routes_json)`

The LLM receives:
- Source and destination names
- Top 3 route options with their details
- Current weather conditions (from n8n or LLM fallback)

**Returns:**
```json
{
  "recommended_mode": "metro",
  "estimated_cost_min": 30,
  "estimated_cost_max": 50,
  "estimated_time_minutes": 25,
  "safety_rating": 8,
  "comfort_rating": 7,
  "tips": ["Avoid 9-11 AM peak", "Metro is 15 min faster than bus"]
}
```

### 9.3 Weather Impact Scoring

Applied in `routes.py` `handlePlanRoute`:

- **Bad weather** (rain, storm): Metro routes get +5 score bonus, walking routes penalized
- **Good weather**: Walking routes get +3 bonus
- **Traffic alerts**: Car/cab routes penalized -5

### 9.4 Night Safety Scoring

Between 22:00 and 05:00:
- Cab routes get +10 score bonus
- Walking routes get -15 penalty

### 9.5 Group Scoring

For groups > 1:
- Routes with lower per-person cost are preferred
- "Cheap per person" bonus (+5) for ≤₹30/person

---

## 10. GTFS Bus Route Geometry

### 10.1 File Size & Structure

**File:** `data_cache/bmtc_gtfs.zip` (47 MB)

Contains 5 standard GTFS tables:

| Table | Rows | Columns | Purpose |
|-------|------|---------|---------|
| `shapes.txt` | ~2.4M | `shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence` | Road geometry |
| `trips.txt` | ~190K | `route_id, service_id, trip_id, shape_id` | Trip-to-shape mapping |
| `stop_times.txt` | ~5M | `trip_id, stop_id, stop_sequence` | Stop order per trip |
| `stops.txt` | ~9,783 | `stop_id, stop_name, stop_lat, stop_lon` | Stop locations |
| `routes.txt` | ~4,359 | `route_id, route_short_name, route_long_name` | Route metadata |

### 10.2 GTFSLoader (`backend/services/gtfs_service.py`)

**Loading strategy:**

1. On first `load()` call, opens the ZIP and reads all CSVs
2. Builds indexes:
   - `_shapes`: `{shape_id: [(lat, lng, seq), ...]}` — full shapes
   - `_route_shapes`: `{route_short_name: [shape_id, ...]}` — shapes per route
   - `_stops_by_name`: `{stop_name: stop_info}` — normalize + lowercase
   - `_stop_to_shapes`: `{stop_name: [(shape_id, seq), ...]}` — which shapes pass through which stops

3. `get_shape_between_stops(from_name, to_name)`:
   - Looks up both stop names in index
   - Finds shapes that pass through both stops
   - Clips the shape between the two stop sequences
   - Returns the real bus road path

4. `get_shape_by_route(route_short_name)`:
   - Returns full shape path for a given route number

**Important:** BMTC GTFS route IDs (e.g., `D35G-BVRH`) don't always match user-visible route numbers (e.g., `244-C VSD`). Stop-name-based matching is more reliable.

### 10.3 Integration with Route Planning

```
_add_leg_paths(route):
  For each bus leg (mode in ["bus_ordinary", "bus_ac_vajra", "kia_bus"]):
    shape = gtfs_loader.get_shape_between_stops(leg.from, leg.to)
    if shape:
      leg.path = shape  // Real GTFS road geometry
    else:
      leg.path = get_osrm_path_between(...)  // OSRM fallback
```

**Performance:** GTFS lookups are O(1) after warmup and return instantly (no HTTP call). The initial load takes ~2-3 seconds.

---

## 11. Traffic Overlay System

### 11.1 Overview

Since Overpass API is unreachable from the deployment network, the traffic overlay uses:
1. **Static road GeoJSON** (`bangalore_roads.geojson`) — 18 major Bengaluru roads
2. **Traffic speed logs** (`traffic_logs.csv`) — simulated speed data

### 11.2 Endpoint

**`GET /api/routes/traffic-overlay`**

Returns GeoJSON FeatureCollection with congestion-colored roads:

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "geometry": { "type": "LineString", "coordinates": [[77.5, 12.9], ...] },
    "properties": {
      "name": "MG Road",
      "speed_kmh": 25,
      "congestion": "moderate",
      "color": "#fbbf24"
    }
  }]
}
```

**Congestion levels:**
| Speed | Level | Color |
|-------|-------|-------|
| > 40 km/h | Clear | Green `#22c55e` |
| 25-40 km/h | Moderate | Yellow `#fbbf24` |
| 15-25 km/h | Heavy | Orange `#f97316` |
| < 15 km/h | Jammed | Red `#ef4444` |

Roads are rendered in order of importance (NH → SH → major arterial → other), with 3px colored polylines on the map.

---

## 12. ML & Optimization

### 12.1 TOPSIS Class (`ml/topsis.py`)

An independent implementation of the TOPSIS multi-criteria decision-making algorithm:

```python
class Topsis:
    def __init__(self, weights: dict = None):
        # Default weights: cost=0.3, time=0.25, comfort=0.15,
        # safety=0.1, walking_distance=0.1, availability=0.05,
        # weather_impact=0.05
    def score(self, alternatives: list[dict]) -> list[float]:
        # Normalize → Weight → Ideal best/worst → Distance → Score
```

The backend's `_topsis_score()` is a simpler implementation tuned specifically for Bengaluru transit routes.

### 12.2 A* Pathfinder (`ml/astar.py`)

Builds a transit graph from metro + bus stop data and finds shortest paths:

```python
class AStarPathfinder:
    def build_graph(self, metro_stations, bus_stops):
        # Nodes: all stations and stops
        # Edges: walking between nearby nodes + transit connections
    
    def find_path(self, source_lat, source_lng, dest_lat, dest_lng):
        # A* shortest path with haversine heuristic
        # Returns list of (node, mode, cost) tuples
```

Currently this is a standalone module not yet integrated into the main route planner.

### 12.3 Data Preprocessor (`ml/data_preprocessor.py`)

Cleans raw CSV files and outputs processed versions:

```python
class DataPreprocessor:
    def clean_metro_csv(input_path, output_path)
    def clean_bus_stops_csv(input_path, output_path)
```

Used during initial data setup, not in the live application.

---

## 13. Current State & Known Issues

### 13.1 What Works

- ✅ Full A→B route planning with all transport modes
- ✅ Real road geometry for car routes (OSRM, 575+ coords)
- ✅ Real GTFS bus route geometry (instant, no HTTP)
- ✅ Real metro rail paths (station-to-station line data)
- ✅ Walking paths with OSRM (dashed polylines)
- ✅ Segment-by-segment custom route builder
- ✅ Traffic overlay with congestion colors
- ✅ Ride price estimates (LLM-generated)
- ✅ AI travel recommendations with weather context
- ✅ Place search (OSM + LLM fallback)
- ✅ Place enrichment (reviews, images, hotels)
- ✅ Travel news & alerts
- ✅ Budget filtering (total budget for group)
- ✅ Group size ride capacity filtering

### 13.2 Performance Profile

| Operation | Typical Time | Bottleneck |
|-----------|-------------|------------|
| Route planning | ~22-27s | OSRM calls + GTFS loading + LLM calls |
| Segment step fetch | ~5-10s | OSRM path enrichment for all options |
| Place search | ~2-3s | OSM Nominatim API |
| LLM call | ~3-8s | OpenRouter API rate |
| GTFS load | ~2-3s | ZIP parsing + indexing (once) |

### 13.3 Known Issues

| Issue | Severity | Cause | Status |
|-------|----------|-------|--------|
| Route plan slow (22-27s) | Medium | OSRM rate limits + serialized LLM calls | Mitigated with parallel gather + 30s timeout |
| OSRM rate limits | Medium | Free OSRM public API | Partially mitigated with interpolated fallback paths |
| n8n unreachable | Low | Network block | Wrapped in try/except, harmless |
| GTFS route number mismatch | Low | BMTC internal IDs ≠ user route numbers | Stop-name matching used instead |
| No real-time pricing | Medium | Uber/Ola/Rapido closed APIs | LLM estimation with ~20% accuracy |
| No real-time bus arrival | Medium | No GTFS-RT setup | All bus times are estimated |
| Search returns non-Bengaluru results | Low | OSM searches worldwide | India bbox filter partially helps |
| Segment builder double-call | Fixed | useEffect + onClick collision | Fixed with buildingRef |

### 13.4 Data Gaps

- **Metro fares:** Estimated at ₹15 + ₹3/km, may not match actual Namma Metro pricing
- **BMTC fares:** Uses slab-based fare table, may not reflect current pricing
- **Ride prices:** LLM-generated estimates, not real Uber/Ola API prices
- **Traffic data:** Static GeoJSON + simulated speeds, not real-time
- **GTFS schedule:** Only shapes used (geometry), not stop times (timetables)

---

## 14. Roadmap & Future Work

### 14.1 Recently Added Features (July 2026)

1. **Progressive multi-column segment UI** — Replaced old two-phase segment builder with progressive column layout (1 to N columns based on journey depth)
2. **Chained segments** — Backend generates flat segments array with `next_segment_index` linking; transit arrival points become new segments
3. **LLM live pricing overlay** — Real-time Ola/Uber/Rapido prices fetched via LLM agent and overlaid on direct options and reach options (8s timeout)
4. **GPS live tracking** — "Start Journey" button triggers browser GPS; green live marker tracks position
5. **Custom waypoints** — Search + add intermediate stops; fresh segment data fetched from custom location
6. **GTFS bus timing expansion** — From 5 to 20 departure times per stop (100K stop times global limit)
7. **Railway station integration** — Train transit options for long-distance routes with departure/arrival times
8. **Parallel OSRM path fetching** — All option paths fetched via `asyncio.gather` for speed
9. **Map resize on panel open/close** — `invalidateSize()` call when segment panel toggles
10. **Budget/group-size filtering** — Applied at every transit and reach option

### 14.2 Critical Issues to Fix Now

#### P0 — Must Fix

1. **Transit options too few** — Many bus stops show 0 transit options because no common routes found with dest-area stops. Need fallback: if no direct bus, show nearby metro connectivity, or other area buses, or at minimum a "no transit available" message.
   - Fix: For bus stops without common routes, search for nearby metro stations (1km from stop) and show metro transit instead.
   - Fix: For ANY stop type, always generate at minimum any transit option (don't let transit_options be empty).

2. **Chained segments not generating for short routes** — When transit arrival is within 2km of dest, only final_options are generated. But user may want to see MORE transit from that area going closer. Need to generate next segment even when close, if there are more transit options available.
   - Fix: Change threshold from 2km to 0.5km for chaining, or always generate next segment when any transit option exists from the arrival point.

3. **Backend `needs_next_segment` flag leaking** — This backend-only key should be stripped before returning to frontend.

#### P1 — High Priority

4. **GTFS loading too slow** — 41s synchronous at startup. Need async loading or progress indicator.
5. **OSRM timeout handling** — Some paths fail silently. Need retry logic with fallback interpolation.
6. **Live price reliability** — 8s LLM call sometimes times out. Need caching and fallback pricing.
7. **Frontend state machine bugs** — HandlePickTransit/HandleGoBack logic needs verification with chained segments.
8. **Transit column should always show** — Even when transit_options is empty, show a message instead of hiding the column.

### 14.3 Short Term (Next Sprints)

#### P2 — Important

1. **Segment builder — edit mode**
   - Allow clicking a previous segment to change its option
   - Recalculate downstream when a segment changes
   - Keep all other segments intact

2. **Route comparison**
   - After building a custom route, compare score against auto-generated direct routes
   - Show time/cost differences
   - Highlight which is better and why

3. **GTFS schedule integration**
   - Load GTFS stop_times.txt for actual bus timings
   - Show departure/arrival times for bus legs
   - Filter routes by time of day
   - Show "next 3 buses" with actual times

4. **Better transit coverage**
   - For every bus stop, find alternative transit if no direct bus:
     - Walk to nearest metro station → metro transit
     - Walk to another bus stop with connectivity → bus transit
   - Add KIA bus routes as transit options (for airport routes)
   - Add auto-rickshaw as transit (not just reach)

5. **UI/UX polish**
   - Mobile-responsive column layout
   - Loading skeletons for columns
   - Smooth column appearance animation
   - Route comparison table view
   - Share route link

6. **Search quality**
   - Restrict OSM Nominatim to Bengaluru region
   - Add Bangalore-specific place synonyms
   - Prioritize transit stops in search results

7. **Ride price estimates**
   - Cache LLM price results (5 min TTL)
   - Show price ranges instead of single estimates
   - Add women-only ride options

#### P3 — Medium Priority

8. **Multi-stop trip planning**
   - Complete the TripPanel component
   - Support 3+ destination trips
   - Optimize visit order for multi-stop routes

9. **Time constraints**
   - "Arrive by X" or "depart at Y" filtering
   - Show estimated arrival times based on current time
   - Filter out options that miss the deadline

10. **Multiple route suggestions per step**
    - After each step, suggest 2-3 best continuations based on TOPSIS
    - Show score breakdown for each option

11. **Offline mode**
    - Cache transit data in IndexedDB
    - Basic route planning without backend
    - PWA support

### 14.4 Long Term (Future Versions)

#### P4 — Nice to Have

12. **Real-time features**
    - GTFS-RT for live bus positions
    - Live metro train tracking
    - Real-time traffic from Google Maps API
    - Live ride availability (not just prices)

13. **Advanced routing**
    - Isochrone maps (reachable areas within N minutes)
    - Environmentally-friendly routing (carbon emissions)
    - Accessibility routing (wheelchair-friendly)
    - Scheduled departure optimization

14. **User features**
    - User accounts with saved routes
    - Route history and favorites
    - Recurring commute planning
    - Crowd-sourced route feedback

15. **Data expansion**
    - Add local train (Bengaluru suburban)
    - Add auto-rickshaw stand locations
    - Add cycle sharing stations
    - Expand to other Indian cities (Chennai, Hyderabad, Mumbai)

16. **ML & AI improvements**
    - Train TOPSIS weights from user feedback
    - Predictive traffic modeling
    - Personalized route recommendations
    - Anomaly detection (unusual delays, route disruptions)

### 14.5 Infrastructure Improvements

| Area | Current | Target |
|------|---------|--------|
| Hosting | Local dev only | Docker + cloud deployment |
| Database | In-memory files | SQLite or PostgreSQL |
| Caching | In-memory dicts | Redis |
| Monitoring | None | Structured logging + metrics |
| Testing | Manual | Automated tests (pytest + vitest) |
| CI/CD | None | GitHub Actions |
| Documentation | This file | API docs + component storybook |

---

## 15. Appendix: File Reference

### 15.1 Key Backend Files

| File | Lines | Purpose |
|------|-------|---------|
| `backend/main.py` | 54 | App entry point, CORS, routers |
| `backend/api/routes.py` | ~690 | Route planning + all-segments endpoints |
| `backend/api/search.py` | ~200 | Search & discovery endpoints |
| `backend/services/transit_service.py` | ~1800 | Core route engine, OSRM, chained segment builder |
| `backend/services/gtfs_service.py` | ~200 | BMTC GTFS loader (100K stop times limit) |
| `backend/services/geocoding.py` | ~450 | Place search + enrichment |
| `backend/services/llm_agent.py` | ~350 | LLM orchestration (live pricing, recommendations) |
| `backend/services/n8n_service.py` | ~150 | n8n webhook proxy |
| `backend/services/images.py` | ~50 | Wikipedia image fetcher |
| `backend/core/database.py` | ~300 | In-memory transit DB (bus/metro/railway) |
| `backend/core/config.py` | 49 | Settings from .env |
| `backend/models/transit.py` | ~100 | Pydantic models |

### 15.2 Key Frontend Files

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/App.tsx` | ~50 | Root component |
| `frontend/src/pages/MainPage.tsx` | ~313 | App orchestrator (GPS tracking, map resize) |
| `frontend/src/components/SegmentPanel.tsx` | ~620 | Progressive multi-column segment UI |
| `frontend/src/components/AToBPanel.tsx` | ~500 | Main A→B route panel |
| `frontend/src/components/MapView.tsx` | ~400 | Leaflet map (segment paths, live marker) |
| `frontend/src/components/SearchPanel.tsx` | ~250 | Search UI |
| `frontend/src/components/DiscoveryPanel.tsx` | ~150 | Place details |
| `frontend/src/components/NewsOverlay.tsx` | ~100 | News display |
| `frontend/src/components/TripPanel.tsx` | ~30 | Trip stub |
| `frontend/src/services/api.ts` | ~137 | API client (typed responses) |
| `frontend/src/types/index.ts` | ~290 | TypeScript types (Segment, TransitOption, etc.) |
| `frontend/src/utils/helpers.ts` | ~120 | UI formatters (mode icons, duration, rupees) |

### 15.3 ML & Utility Files

| File | Lines | Purpose |
|------|-------|---------|
| `ml/topsis.py` | 62 | Multi-criteria scoring |
| `ml/astar.py` | 122 | A* pathfinding |
| `ml/data_preprocessor.py` | 64 | CSV cleaning |
| `scripts/test_route_api.py` | ~100 | Route API testing |
| `scripts/test_services.py` | ~100 | Service testing |
| `scripts/test_n8n.py` | ~50 | n8n connectivity test |
| `scripts/create_wf_api.py` | ~50 | n8n workflow creation |

### 15.4 Data Files

| File | Approx Size | Records |
|------|-------------|---------|
| `data_cache/bmtc_gtfs.zip` | 47 MB | GTFS feed |
| `data_cache/bmtc_all_stops_master.csv` | 1.5 MB | 9,783 stops |
| `data_cache/bengaluru_metro_network.csv` | 5 KB | 56 stations |
| `data_cache/kia_routes_fare_full.json` | 20 KB | ~15 routes |
| `data_cache/transit_fares.json` | 2 KB | ~20 fare slabs |
| `data_cache/bangalore_roads.geojson` | 10 KB | 18 roads |
| `data_cache/traffic_logs.csv` | 50 KB | ~500 speed records |

---

## End of Document

*This document covers the complete VOYAGER Bengaluru Route Planner as of July 2026. For questions or contributions, refer to the code files listed above — each file has detailed implementation comments for further exploration.*

*Next major iteration: GTFS schedule integration + segment builder editing mode + route planning speed optimization.*
