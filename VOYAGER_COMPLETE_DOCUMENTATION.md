# VOYAGER - Bengaluru Transit Navigator
## Complete Project Documentation

> **Last Updated**: July 14, 2026
> **Author**: AI-Assisted Development
> **Version**: 1.0.0

---

# TABLE OF CONTENTS

1. [PROJECT OVERVIEW](#1-project-overview)
2. [SYSTEM ARCHITECTURE](#2-system-architecture)
3. [PROJECT STRUCTURE](#3-project-structure)
4. [BACKEND CORE](#4-backend-core)
5. [TRANSIT SERVICE - THE ROUTING ENGINE](#5-transit-service---the-routing-engine)
6. [THE SEGMENT BUILDER](#6-the-segment-builder)
7. [GTFS INTEGRATION](#7-gtfs-integration)
8. [FRONTEND COMPONENTS](#8-frontend-components)
9. [API ENDPOINTS](#9-api-endpoints)
10. [DATA LAYER](#10-data-layer)
11. [PRICING AND FARES](#11-pricing-and-fares)
12. [TRAIN INTEGRATION](#12-train-integration)
13. [RAILWAY STATIONS](#13-railway-stations)
14. [METRO INTEGRATION](#14-metro-integration)
15. [BUS INTEGRATION](#15-bus-integration)
16. [RIDE TYPES / CABS / AUTO / BIKE](#16-ride-types--cabs--auto--bike)
17. [SMART FILTERING RULES](#17-smart-filtering-rules)
18. [MULTI-MODAL ROUTES](#18-multi-modal-routes)
19. [LLM / AI INTEGRATION](#19-llm--ai-integration)
20. [n8n WORKFLOW INTEGRATION](#20-n8n-workflow-integration)
21. [ML MODULES (STANDALONE)](#21-ml-modules-standalone)
22. [GEODING / PLACE SEARCH](#22-geocoding--place-search)
23. [MAP AND VISUALIZATION](#23-map-and-visualization)
24. [FRONTEND UI DETAILS](#24-frontend-ui-details)
25. [DEVELOPMENT SETUP AND RUNNING](#25-development-setup-and-running)
26. [KNOWN ISSUES AND LIMITATIONS](#26-known-issues-and-limitations)
27. [NEXT STEPS / ROADMAP](#27-next-steps--roadmap)
28. [WHAT CAN BE ADDED / ENHANCED](#28-what-can-be-added--enhanced)
29. [APPENDIX: CODE CONVENTIONS](#29-appendix-code-conventions)
30. [APPENDIX: FARE TABLES](#30-appendix-fare-tables)

---

# 1. PROJECT OVERVIEW

## 1.1 What is VOYAGER?

VOYAGER is a **multi-modal route planning assistant** for Bengaluru, India. It helps travellers find the best way to get from point A to point B using a combination of:

- **BMTC city buses** (ordinary + AC Vajra)
- **Namma Metro** (Green Line, Purple Line, interchange stations)
- **Indian Railways** (48 Karnataka railway stations)
- **KIA Vayu Vajra airport buses**
- **Ride-hailing** (Uber Go, Ola Mini, Uber XL, Ola XL, Auto, Uber Moto, Rapido, Uber for Women, Uber Pet)
- **Walking** (for last-mile connections)

## 1.2 Core Philosophy

The app uses a **two-phase segment builder** approach:

1. **Phase "init"**: From the user's current location, show ALL available options:
   - Direct options (walk, cab, auto, bike) that go straight to destination
   - Via transit stops (bus stops, metro stations, railway stations) that show how to REACH each stop

2. **Phase "from"**: After picking a transit stop and how to reach it, show what to do FROM that stop:
   - Individual bus route cards with GTFS departure times
   - Metro rides to destination
   - Train options (for railway stations)
   - Walk (if destination is within 2 km)
   - Cab/auto/bike to destination

3. **Phase "direct"**: Journey is complete - the user has picked a direct option or reached their destination.

## 1.3 Target Users

- Daily commuters in Bengaluru looking for optimal multi-modal routes
- Tourists visiting Bengaluru and surrounding Karnataka cities (Mysuru, Hubballi, Mangaluru, etc.)
- Users who want to compare cost, time, and comfort across different transport modes

---

# 2. SYSTEM ARCHITECTURE

## 2.1 High-Level Architecture

```
┌──────────────┐     HTTP/JSON      ┌──────────────────┐     HTTP/Proxy    ┌──────────────────┐
│   Frontend    │ ◄──────────────►  │    Backend API    │ ◄──────────────► │  External APIs    │
│  Vite + React │    localhost:     │   FastAPI +       │    OSRM/n8n/     │  (OSRM, n8n,      │
│  TypeScript   │    3000 ◄─► 8000   │   Python 3.12     │    OpenRouter    │   Wikipedia, etc.) │
└──────────────┘                    └──────────────────┘                   └──────────────────┘
                                           │
                                           ▼
                                    ┌──────────────────┐
                                    │  Data Layer       │
                                    │  - SQLite?        │
                                    │  - JSON/CSV files  │
                                    │  - GTFS zip        │
                                    └──────────────────┘
```

## 2.2 Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| Frontend | React + TypeScript | Vite 5.4 build tool |
| Frontend Map | Leaflet + react-leaflet | OpenStreetMap tiles |
| Backend | FastAPI (Python) | uvicorn server |
| Backend Routing | geopy (geodesic) | Haversine distance calculations |
| Backend HTTP | httpx | Async HTTP client |
| Backend Config | pydantic-settings | `.env` file loading |
| GTFS | Custom loader | Parses GTFS zip, 50k stop_times limit |
| LLM | OpenRouter (primary) | GPT-4o-mini, with Gemini fallback |
| n8n | Self-hosted | Webhook-based workflow automation |
| OSRM | router.project-osrm.org | Open Source Routing Machine |

## 2.3 Port Configuration

| Service | Port | URL |
|---------|------|-----|
| Frontend (Vite) | 3000 | http://localhost:3000 |
| Backend (FastAPI) | 8000 | http://localhost:8000 |
| n8n (optional) | 5678 | http://localhost:5678 |
| Swagger Docs | -- | http://localhost:8000/docs |
| ReDoc | -- | http://localhost:8000/redoc |

---

# 3. PROJECT STRUCTURE

## 3.1 Directory Tree

```
VOYGAR/
├── .env                          # Environment variables (API keys)
├── .gitignore                    # Git ignore rules
├── AGENTS.md                     # AI agent instructions (summary)
├── requirements.txt              # Python dependencies
├── backend/
│   ├── main.py                   # FastAPI entry point (58 lines)
│   ├── api/
│   │   ├── routes.py             # All /api/routes/* endpoints (569 lines)
│   │   └── search.py             # All /api/search/* endpoints (83 lines)
│   ├── core/
│   │   ├── config.py             # Settings class (49 lines)
│   │   └── database.py           # TransitDatabase singleton (286 lines)
│   ├── models/
│   │   └── transit.py            # Pydantic models (102 lines)
│   ├── services/
│   │   ├── transit_service.py    # Core routing engine (1432 lines)
│   │   ├── gtfs_service.py       # GTFS loader (182 lines)
│   │   ├── geocoding.py          # Place search/nearby/enrich (591 lines)
│   │   ├── images.py             # Wikipedia image service (39 lines)
│   │   └── n8n_service.py        # n8n webhook proxy (151 lines)
│   └── agents/
│       └── llm_agent.py          # LLM integration (329 lines)
├── frontend/
│   ├── vite.config.ts            # Vite config (port 3000, proxy)
│   ├── package.json              # Dependencies
│   ├── tsconfig.json             # TypeScript config
│   └── src/
│       ├── main.tsx              # React entry
│       ├── App.tsx               # Root component (84 lines)
│       ├── index.css             # All styles (625 lines)
│       ├── types/index.ts        # TypeScript types (244 lines)
│       ├── utils/helpers.ts      # Utility functions (123 lines)
│       ├── services/api.ts       # API client (122 lines)
│       ├── pages/MainPage.tsx    # Main layout (272 lines)
│       └── components/
│           ├── SearchPanel.tsx    # Place search + nearby (377 lines)
│           ├── AToBPanel.tsx      # A-to-B routing (620 lines)
│           ├── SegmentPanel.tsx   # Two-phase segment builder (663 lines)
│           ├── TripPanel.tsx      # Trip planner placeholder (36 lines)
│           ├── MapView.tsx        # Leaflet map (362 lines)
│           ├── DiscoveryPanel.tsx # Place details (187 lines)
│           └── NewsOverlay.tsx    # Travel news overlay (110 lines)
├── ml/
│   ├── topsis.py                 # TOPSIS scoring (standalone, 62 lines)
│   ├── astar.py                  # A* pathfinding (standalone, 122 lines)
│   └── data_preprocessor.py      # Data preprocessing (standalone)
├── data_cache/
│   ├── bmtc_gtfs.zip             # GTFS data
│   ├── bmtc_all_stops_master.csv # BMTC bus stops (20k+)
│   ├── bengaluru_metro_network.csv # Metro stations/lines
│   ├── karnataka_railway_stations.json # 48 stations
│   ├── kia_routes_fare_full.json # KIA airport routes
│   ├── transit_fares.json        # Fare slabs
│   ├── traffic_logs.csv          # Demo traffic data
│   └── *.csv / *.json            # Other data files
├── workflows/                    # n8n workflow JSON definitions
│   ├── weather_traffic_check.json
│   ├── ride_price_estimation.json
│   ├── place_verification.json
│   ├── place_reviews.json
│   └── hotel_price_check.json
└── scripts/                      # Utility scripts
```

---

# 4. BACKEND CORE

## 4.1 FastAPI Application (`backend/main.py`)

The backend is a FastAPI application with CORS enabled for all origins. On startup:

1. **Database initialization** (`db.initialize()`): Loads all transit data from CSV/JSON files in `data_cache/`. This includes:
   - Metro stations and networks
   - BMTC bus stops (with route lists)
   - KIA Vayu Vajra routes
   - Karnataka railway stations
   - Transit fare slabs (metro, ordinary bus, AC Vajra)

2. **GTFS loading** (`_ensure_gtfs()`): Loads BMTC GTFS data synchronously. This takes ~40 seconds and blocks startup. Loads shapes, stops, stop_times (50k row limit), trips, and routes.

## 4.2 Configuration (`backend/core/config.py`)

Pydantic `BaseSettings` class that reads from `.env` file:

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENROUTER_API_KEY` | "" | OpenRouter API key for LLM access |
| `GEMINI_API_KEY` | "" | Gemini API key (fallback LLM) |
| `N8N_WEBHOOK_URL` | "" | n8n webhook base URL |
| `OSRM_BASE_URL` | "https://router.project-osrm.org" | OSRM routing server |
| `LLM_PROVIDER` | "openrouter" | Primary LLM backend |
| `OPENROUTER_MODEL` | "openai/gpt-4o-mini" | Primary LLM model |
| `FUEL_PRICE_PER_LITER` | 110.0 | Petrol price (₹/liter) |
| `PETROL_AVG_MILEAGE` | 15.0 | Average km/liter |
| `BANGALORE_CENTER_LAT` | 12.9716 | City center latitude |
| `BANGALORE_CENTER_LNG` | 77.5946 | City center longitude |
| `DATA_CACHE_DIR` | "data_cache/" | Data directory path |
| `DEBUG` | True | Debug mode |

## 4.3 Database Singleton (`backend/core/database.py`)

The `TransitDatabase` class is a singleton that loads and provides access to all transit data:

### 4.3.1 Data Loading Methods

| Method | Source File | What It Loads |
|--------|-----------|---------------|
| `_load_transit_fares()` | `transit_fares.json` | Metro, BMTC Ordinary, BMTC AC fare slabs |
| `_load_metro_data()` | `bengaluru_metro_network.csv` | 100+ metro stations, 2 lines, distances, interchanges |
| `_load_bus_stops()` | `bmtc_all_stops_master.csv` | 20,000+ BMTC bus stops with route lists |
| `_load_kia_routes()` | `kia_routes_fare_full.json` | KIA Vayu Vajra airport bus routes with stop-wise fares |
| `_load_railway_stations()` | `karnataka_railway_stations.json` | 48 Karnataka railway stations |

### 4.3.2 Key Query Methods

| Method | Description |
|--------|-------------|
| `find_nearby_bus_stops(lat, lng, radius_km)` | Returns bus stops within radius sorted by distance (max 20) |
| `find_nearby_metro_stations(lat, lng, radius_km)` | Returns metro stations within radius sorted by distance |
| `find_nearby_railway_stations(lat, lng, radius_km)` | Returns railway stations within radius (default 30km) |
| `get_metro_fare(distance_km)` | Returns metro fare from slab table |
| `get_bmtc_ordinary_fare(distance_km, passenger_type)` | Returns ordinary bus fare, supports child(50%) and senior(75%) discounts |
| `get_bmtc_ac_fare(distance_km, passenger_type)` | Returns AC Vajra fare |
| `get_metro_distance_between(stn_a, stn_b)` | Cached metro distance or calculated from sequence |
| `get_metro_line_path(from_name, to_name)` | Returns sequential station coordinates for a metro line segment |
| `find_stop_by_name(name)` | Finds a stop by exact name (bus then metro) |

### 4.3.3 Metro Data Structure

Each metro station has:
- `name`: Station name
- `line`: "Purple" or "Green"
- `sequence`: Position on the line
- `lat`, `lng`: Coordinates
- `is_interchange`: Boolean (e.g., Majestic is interchange)
- `distance_from_prev_km`: Distance from previous station

---

# 5. TRANSIT SERVICE - THE ROUTING ENGINE

## 5.1 Overview (`backend/services/transit_service.py`)

This is the **heart of the application** (1432 lines). The `TransitService` class generates all routing options, including:

1. **Full route plans** (`get_route_legs_public()`)
2. **Segment builder options** (`get_segment_step_options()`)
3. **Mini path options** (`get_mini_path_options()`)
4. **OSRM path enrichment** (async path fetching)
5. **TOPSIS scoring** for route ranking

## 5.2 Helper Functions (Module Level)

### `_safe(val, default=0.0)`
Handles NaN, None, and Infinity values by returning a safe default.

### `_ensure_gtfs()`
Lazy-loads GTFS data on first call. Returns the GTFS loader singleton.

### `_get_train_options(src_name, dst_name)`
Normalizes station names and returns hardcoded train schedules. See Section 12 for details.

## 5.3 Ride Types Pricing Table

Used across multiple methods (`get_segment_step_options`, `get_mini_path_options`, reach_options, from_stop_options):

```python
ride_types = [
    ("cab",       "Uber Go / Ola Mini",     14/km, 3 min/km, ₹25 base, "🚕", 4 seats),
    ("cab_xl",    "Uber XL / Ola XL",       20/km, 3 min/km, ₹40 base, "🚐", 6 seats),
    ("auto",      "Auto",                   10/km, 5 min/km, ₹15 base, "🛺", 3 seats),
    ("bike",      "Uber Moto / Rapido",     6/km,  2 min/km, ₹10 base, "🏍️", 1 seat),
    ("cab_women", "Uber for Women / Ola for Women", 14/km, 3 min/km, ₹25 base, "👩", 4 seats),
    ("cab_pet",   "Uber Pet",               17/km, 3 min/km, ₹30 base, "🐾", 4 seats),
]
```

**Pricing Formula**: `per_person = round(base_fare + distance × per_km_rate)`  
**Total Fare**: `per_person × group_size`  
**Filtering**: Ride is excluded if `group_size > capacity` or `total > budget`

## 5.4 Core Routing Methods

### `get_route_legs_public()`
Generates complete multi-modal routes between source and destination:

1. Calculates direct distance
2. Calls all `_generate_*_routes()` methods:
   - `_generate_bus_routes()` - Walk → bus → walk
   - `_generate_metro_routes()` - Walk → metro → walk
   - `_generate_metro_interchange_routes()` - Walk → metro(Line A) → interchange → metro(Line B) → walk
   - `_generate_kia_routes()` - Walk → KIA bus → walk
   - `_generate_multi_modal_routes()` - Bus → metro OR metro → bus
3. Filters by budget (if specified)
4. Scores each route with `_topsis_score()`
5. Enriches legs with coordinates
6. Sorts by score (descending) and returns top 8

### `_generate_bus_routes()`
Finds nearest bus stop to source and destination, calculates walking distances, bus distance, fare, and creates a 3-leg route: walk → bus → walk. Generates both ordinary and AC Vajra variants.

### `_generate_metro_routes()`
Finds nearest metro station to source and destination, calculates walking distances, metro distance, fare, and creates a 3-leg route: walk → metro → walk. Checks if same line for bonus score.

### `_generate_metro_interchange_routes()`
Only when source and destination are on different metro lines. Finds interchange stations, creates a 4-leg route: walk → metro(L1) → interchange → metro(L2) → walk.

### `_generate_kia_routes()`
Matches source and destination stops against KIA Vayu Vajra route stop lists. Creates routes with stop-index-based fare calculation.

### `_generate_multi_modal_routes()`
Generates bus→metro and metro→bus combination routes. For bus→metro: walks to bus stop, takes bus to metro station area, takes metro to destination metro station. For metro→bus: walks to metro station, takes metro, takes bus to destination area.

## 5.5 TOPSIS Scoring (`_topsis_score()`)

Scoring function used to rank routes (score 10-99):

| Criterion | Weight | Formula |
|-----------|--------|---------|
| Fare | 25% | `max(0, 100 - fare/10)` |
| Time | 30% | `max(0, 100 - duration_minutes/2)` |
| Walking | 15% | `max(0, 100 - walking_km × 15)` |
| Comfort | 20% | Mode-dependent (metro=85, cab=85, bus=50, etc.) |

**Bonuses**:
- Budget savings: +10 if fare ≤ 40% budget, +5 if ≤ 70%
- Over budget: -15 if over, -5 if > 90%
- Cheap per-person (≤ ₹30): +5
- Metro mode: +5
- Known route numbers: +3

**Final**: `max(10, min(99, score))`

## 5.6 OSRM Path Integration

### `get_osrm_path_between(slat, slng, dlat, dlng, profile)`
Async method that:
1. Checks in-memory cache (keyed by rounded coordinates + profile)
2. Makes HTTP GET to OSRM API (5s timeout)
3. Parses GeoJSON geometry from response
4. Falls back to `_interpolate_path()` on failure

### `_interpolate_path()`
Simple linear interpolation between two points. Generates `num_points` evenly spaced coordinates. Used as fallback when OSRM is unavailable.

### `_add_leg_paths(route)`
Async enrichment that adds geometry to each leg of a route:
- **Metro legs**: Uses `db.get_metro_line_path()` for station-to-station path
- **Bus legs**: Uses `gtfs.get_shape_between_stops()` for bus shape geometry
- **Walk legs**: OSRM walking profile
- **Other legs**: OSRM driving profile

---

# 6. THE SEGMENT BUILDER

## 6.1 Concept

The segment builder breaks a journey into step-by-step segments, allowing the user to build a custom multi-modal route one piece at a time. Each step shows:

1. **Where you are now** (current location or last stop)
2. **Where you can go next** (direct to destination or via transit stops)
3. **How to get there** (walk, cab, bus, metro, train)

## 6.2 Backend: `get_segment_step_options()`

### Response Structure

```json
{
  "from": {"lat": 12.97, "lng": 77.59, "name": "MG Road"},
  "dest": {"lat": 12.93, "lng": 77.61, "name": "Koramangala"},
  "direct_options": [
    {"mode": "walk", "label": "Walk", "fare": 0, ...},
    {"mode": "cab", "label": "Uber Go / Ola Mini", "fare": 87, ...},
    {"mode": "auto", "label": "Auto", "fare": 59, ...},
    ...
  ],
  "via_stops": [
    {
      "stop": {"name": "St Joseph Boys High School", "lat": ..., "lng": ..., "type": "bus"},
      "reach_options": [
        {"mode": "walk", "label": "Walk", "fare": 0, ...},
        {"mode": "cab", "label": "Uber Go / Ola Mini to St Joseph Boys High School", "fare": 25, ...},
        ...
      ],
      "from_stop_options": [
        {"mode": "bus_ordinary", "route_number": "201K", "bus_times": [...], "fare": 12, ...},
        {"mode": "bus_ac_vajra", "route_number": "201K", "bus_times": [...], "fare": 20, ...},
        {"mode": "metro", "label": "Metro to {dest_metro}", ...},
        {"mode": "walk", "label": "Walk to Destination", "fare": 0, ...},
        {"mode": "cab", "label": "Uber Go / Ola Mini to Destination", "fare": 45, ...},
        ...
      ]
    },
    ...
  ]
}
```

### 6.2.1 Direct Options Generation (lines 799-837)

1. **Walk** (if distance ≤ 5 km): `fare=0`, `duration=dist×12 min`
2. **All ride types**: Priced using the ride_types table, filtered by group capacity and budget

### 6.2.2 Via Stop Generation Order

Stops are generated in this order:

1. **Out-of-Bengaluru bus+cab combo** (if destination > 35km from Bangalore center): Creates single via stop with BMTC bus to farthest stop + cab rest of way
2. **Nearby bus stops** (up to 4, within 1km): Each with reach + from options
3. **Nearby metro stations** (up to 3, within 2km): Each with reach + from options
4. **Railway stations** (up to 3, within 15km): Each with reach + from options

### 6.2.3 Bus Stop Via Stop Logic (lines 887-1025)

For each nearby bus stop:

**Skip Conditions**:
- Skip if: `dist > 2km AND no common bus routes AND stop-to-destination > 50km`

**Reach Options**:
- **Walk** (if dist ≤ 2 km)
- **All ride types** (always available, filtered by capacity/budget)

**From Stop Options** (in order):
1. **Bus route cards** (if `has_common` routes with destination area):
   - For each common route number → individual card with ordinary + AC Vajra variants
   - GTFS bus timings filtered for this specific route
   - ***NEW: Only shown if bus_times are available (filtered out if no timings)***
2. **Metro** to destination metro station (if within 2km of dest)
3. **Walk** to destination (if dist ≤ 2km)
4. **All ride types** to destination (always available)

### 6.2.4 Metro Station Via Stop Logic (lines 1027-1151)

For each nearby metro station:

**Skip Conditions**:
- Skip if: `no dest metro nearby AND dist > 2km AND destination is outside Bengaluru`

**Reach Options**:
- **Walk** (if dist ≤ 2 km)
- **All ride types** (always available)

**From Stop Options** (in order):
1. **Metro** to destination metro station
2. **Bus route cards** from station to destination bus stops (ordinary + AC Vajra, with GTFS timings)
3. **Walk** to destination (if ≤ 2km)
4. **All ride types** to destination

### 6.2.5 Railway Station Via Stop Logic (lines 1153-1242)

For each nearby railway station (within 15km):

**Reach Options**:
- **Walk** (if dist ≤ 2km)
- **All ride types** (always available)

**From Stop Options** (in order):
1. **Train options** (if destination railway station found within 30km):
   - Each matching train from `_get_train_options()` generates a card with:
     - Train number and name
     - Departure and arrival times
     - Computed duration
     - Per-person fare: `max(15, round(dist × 0.8))`
2. **Last-mile from destination station**:
   - Walk (if dest station to actual dest ≤ 2km)
   - All ride types from dest station to actual destination

## 6.3 Frontend: SegmentPanel.tsx (663 lines)

### 6.3.1 Component State

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

**Endpoint:** `GET /api/routes/segment-step` in `routes.py` (lines 384-449)

**Frontend:** Segment building state in `AToBPanel.tsx`:
- `segmentStep: SegmentStepData` — current step options
- `segmentPath: SegmentStepOption[]` — chosen segments

### 8.3 Step Data Structure

Each step returns:

```json
{
  "from": { "lat": 12.97, "lng": 77.59, "name": "Your Location" },
  "dest": { "lat": 12.93, "lng": 77.61, "name": "Destination" },
  "direct_options": [ ... ],        // Walk + all ride types to destination
  "via_stops": [
    {
      "stop": { "name": "Majestic", "lat": 12.97, "lng": 77.57, "type": "metro" },
      "reach_options": [ ... ],      // How to get TO this stop
      "from_stop_options": [ ... ]   // What to do FROM this stop
    }
  ]
}
```

### 8.4 Ride Types Available

All with per-person pricing × group_size, filtered by capacity:

| Mode | Label | Base Fare | Per KM | Capacity | Icon |
|------|-------|-----------|--------|----------|------|
| `cab` | Uber Go / Ola Mini | ₹25 | ₹14/km | 4 | 🚕 |
| `cab_xl` | Uber XL / Ola XL | ₹40 | ₹20/km | 6 | 🚐 |
| `auto` | Auto Rickshaw | ₹15 | ₹10/km | 3 | 🛺 |
| `bike` | Uber Moto / Rapido | ₹10 | ₹6/km | 1 | 🏍️ |
| `cab_women` | Uber for Women | ₹25 | ₹14/km | 4 | 👩 |
| `cab_pet` | Uber Pet | ₹30 | ₹17/km | 4 | 🐾 |

**Capacity filtering:** If `group_size > capacity`, the option is hidden. E.g., a group of 5 won't see Auto (capacity 3) or Bike (capacity 1).

### 8.5 Transit Stop Types

| Type | Source | Search Radius | Max Shown |
|------|--------|---------------|-----------|
| `bus` | `db.find_nearby_bus_stops()` | 1.0 km | 4 |
| `metro` | `db.find_nearby_metro_stations()` | 2.0 km | 4 |

Each stop provides:
- `reach_options`: Walk (≤2km) + all ride types to reach that stop
- `from_stop_options`: Transit rides (Bus/Metro) to destination area + all ride types direct to destination

### 8.6 Transit Ride Options

**Bus rides:** Between nearby source stop and destination-area stops, using BMTC fare calculation:
- `per_person = max(10, get_bmtc_ordinary_fare(distance))`

**Metro rides:** Between nearby source station and destination-area stations:
- `per_person = max(15, distance × 3)`

### 8.7 Frontend Flow

```
User clicks "Segment Builder" button
  → handleStartSegmentBuilding()
    → fetchStepFrom(source_lat, source_lng, source_name)
      → GET /api/routes/segment-step?from=source&...
      → setSegmentStep(response.step)
    
User sees:
  [Direct Options] [Transit Stop 1] [Transit Stop 2] ...

User clicks "Walk to Majestic" (reach_option)
  → handlePickSegmentOption(option)
    → setSegmentPath([...prev, option])  // adds to path
    → If option.arrives_at_stop == true:
        fetchStepFrom(option.to_lat, option.to_lng, option.to)
        // Loads next step from Majestic station
    → Else (direct to destination):
        setSegmentStep(null)  // route complete

At next step from Majestic:
  User sees options from Majestic to destination
  → Repeat until destination reached
```

### 8.8 Map Integration

- Each chosen segment renders as a colored polyline (cycling through SEGMENT_COLORS)
- Transit stops are shown as CircleMarkers on the map:
  - Green circles for metro stations
  - Blue circles for bus stops
  - Popup shows stop name
- Hovering over an option highlights its path in yellow

### 8.9 State Reset

- User can reset and start over at any time
- Each step's options are independently fetched and cached
- Double-call prevention via `segmentBuildingRef` ref

### 8.10 What's Missing / Improvements Needed

1. **Editable segments**: User cannot go back and change a previous segment's choice
2. **More transit stop info**: Show bus route numbers and metro lines at each stop
3. **Compare vs direct routes**: Show how the custom-built route compares to the automatically planned ones
4. **Intermediate stops**: Allow adding intermediate destinations (not just transit stops)
5. **Timeline view**: Show the route as a timeline with departure/arrival times
6. **GTFS schedule-based transit**: Currently bus/metro times are estimated (distance/speed), not based on actual GTFS schedules
7. **Real-time arrival data**: No GTFS-RT integration yet
8. **Path builder improvement**: After building segments, automatically find the best combined transit route suggestion

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

# 21. ML MODULES (STANDALONE)

## 21.1 TOPSIS (`ml/topsis.py`)

A standalone implementation of the TOPSIS (Technique for Order Preference by Similarity to Ideal Solution) multi-criteria decision-making algorithm.

**Criteria weights** (not used by backend):
- Cost: 0.25
- Time: 0.20
- Comfort: 0.15
- Safety: 0.15
- Walking Distance: 0.10
- Availability: 0.10
- Weather Impact: 0.05

**Status**: NOT connected to the backend. The backend uses its own inline `_topsis_score()` method.

## 21.2 A* Pathfinder (`ml/astar.py`)

A standalone A* pathfinding algorithm that:
- Builds a graph from metro stations (same-line edges weighted by distance)
- Adds bus stop edges (within 15km)
- Adds interchange edges (metro-bus within 1.5km)
- Uses Haversine distance as heuristic

**Status**: NOT connected to the backend. The backend uses a different approach (nearest-stop + common routes).

## 21.3 Data Preprocessor (`ml/data_preprocessor.py`)

Standalone utilities for data preprocessing. Not integrated.

---

# 22. GEOCODING / PLACE SEARCH

## 22.1 GeocodingService (`backend/services/geocoding.py`)

Three-tier place search:

1. **OpenStreetMap (Nominatim)**: Primary source for places
2. **AI (LLM)**: Fallback for OSM failures, also used for smart suggestions
3. **Database (DB bus stops/metro)**: Additional local results

**Search Flow**:
1. Check cache (24-hour TTL by query + lat/lng)
2. Run OSM + AI + DB searches in parallel
3. Deduplicate by coordinate proximity
4. Return combined results

**Nearby Search**:
- Uses Overpass API for OSM data with type-specific tags
- Adds nearby bus stops and metro stations from DB
- Falls back to AI search

**Enrichment**:
- Images via Wikipedia API
- Hotel prices via n8n webhook
- Reviews via n8n → LLM web search → LLM generation

## 22.2 Cache (`SearchCache`)

- TTL-based cache (default 24 hours)
- Keyed by `query` or `query:lat:lng`
- Implemented as simple dict with timestamps

---

# 23. MAP AND VISUALIZATION

## 23.1 Leaflet Map (`MapView.tsx`)

**Features**:
- OpenStreetMap tiles (via Leaflet default tile URL)
- Dark theme (CSS overrides)
- Multiple marker types (colored, emoji-labeled)
- Route polylines with colored segments
- Traffic congestion overlay (color-coded: green < 30%, yellow < 50%, orange < 70%, red ≥ 70%)
- News markers with impact-based coloring

**Controls**:
- Zoom to user location
- Toggle traffic layer
- Marker click for place details
- Route geometry updates via props

## 23.2 Traffic Layer

Fetches from `/api/routes/traffic-overlay` on map move (800ms debounce). Returns GeoJSON with color-coded road segments based on speed/congestion data from `traffic_logs.csv`.

---

# 24. FRONTEND UI DETAILS

## 24.1 Dark Theme (`index.css`)

CSS Variables for the dark theme:
```css
--bg-primary: #0f172a;
--bg-secondary: #1a2332;
--bg-card: #1e293b;
--text-primary: #e2e8f0;
--text-secondary: #94a3b8;
--accent: #3b82f6;
--success: #22c55e;
--warning: #f59e0b;
--danger: #ef4444;
```

## 24.2 Mode Tabs

Three modes in sidebar:
- **Search**: Place search and nearby exploration
- **A-to-B**: Route planning between two points
- **Trip**: Multi-destination trip planner (placeholder)

## 24.3 Responsive Layout

- Sidebar: 420px fixed width
- Map: fills remaining space
- Segment Panel: bottom sheet (max-height 65vh)
- Panels scroll independently

## 24.4 Helper Functions (`helpers.ts`)

| Function | Purpose |
|----------|---------|
| `getModeIcon(mode)` | Maps 30+ mode strings to emojis |
| `getModeLabel(mode)` | Maps mode strings to human labels |
| `getPlaceIcon(placeType, isRecommended)` | Place type to emoji |
| `formatDuration(minutes)` | "Xh Ym" or "X min" |
| `formatRupees(amount)` | "₹X.XX" |
| `getScoreColor(score)` | Color based on score range |
| `getScoreLabel(score)` | Text label for score |
| `getPinColor(isRecommended, score)` | Marker pin color |

---

# 25. DEVELOPMENT SETUP AND RUNNING

## 25.1 Prerequisites

- Python 3.12+
- Node.js 18+
- npm or yarn

## 25.2 Environment Setup

1. Create `.env` file in project root:
```
OPENROUTER_API_KEY=sk-or-v1-...
GEMINI_API_KEY=...
N8N_WEBHOOK_URL=http://localhost:5678
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install frontend dependencies:
```bash
cd frontend
npm install
```

## 25.3 Running the Application

```powershell
# Terminal 1: Backend
cd VOYGAR
python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd VOYGAR/frontend
npx vite --port 3000
```

## 25.4 Access Points

- Frontend UI: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 25.5 Running n8n (Optional)

```bash
n8n start --port=5678
```

Then import workflows from the `workflows/` directory.

---

# 26. KNOWN ISSUES AND LIMITATIONS

## 26.1 Performance Issues

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

### 14.1 Short Term (Next Sprints)

#### P0 — Critical

1. **Route planning speed optimization**
   - Preload GTFS data at startup (not lazy)
   - Add connection pooling to OSRM client
   - Reduce OSRM timeout from 5s to 3s
   - Cache common OSRM routes locally
   - Target: <15s for typical route plan

2. **Segment builder enhancements**
   - Allow editing/removing previous segment choices
   - Show intermediate costs at each step
   - Add "Auto-complete" to find best transit from current path
   - Show bus route numbers and metro lines in stop details
   - Display segment timelines

3. **GTFS schedule integration**
   - Load GTFS stop_times.txt for actual bus timings
   - Show departure/arrival times for bus legs
   - Filter routes by time of day

#### P1 — High

4. **Search quality improvements**
   - Restrict OSM Nominatim to Bengaluru region (current India bbox too broad)
   - Add Bangalore-specific place synonyms database
   - Prioritize transit stops in search results

5. **Path enrichment reliability**
   - Add OSRM request queuing with 200ms delay between calls
   - Cache more aggressively (persistent disk cache)
   - Add more interpolated path points (12 → 24 for smoother curves)

6. **Ride price estimates**
   - Integrate with Ola/Uber affiliate APIs if available
   - Add Rapido bike taxi pricing
   - Show price ranges instead of single estimates
   - Add women-only ride options

#### P2 — Medium

7. **UI/UX polish**
   - Mobile-responsive layout
   - Dark mode consistency
   - Loading skeletons instead of spinners
   - Route comparison table view
   - Share route link functionality

8. **Multi-stop trip planning**
   - Complete the TripPanel component
   - Support 3+ destination trips
   - Optimize visit order for multi-stop routes

9. **Offline mode**
   - Cache transit data in IndexedDB
   - Basic route planning without backend
   - PWA support

### 14.2 Long Term (Future Versions)

#### P3 — Nice to Have

10. **Real-time features**
    - GTFS-RT for live bus positions
    - Live metro train tracking
    - Real-time traffic from Google Maps API
    - Live ride availability (not just prices)

11. **Advanced routing**
    - Isochrone maps (show reachable areas within N minutes)
    - Environmentally-friendly routing (carbon emissions)
    - Accessibility routing (wheelchair-friendly)
    - Scheduled departure optimization

12. **User features**
    - User accounts with saved routes
    - Route history and favorites
    - Recurring commute planning
    - Crowd-sourced route feedback

13. **Data expansion**
    - Add local train (Bengaluru suburban)
    - Add auto-rickshaw stand locations
    - Add cycle sharing stations
    - Expand to other Indian cities (Chennai, Hyderabad, Mumbai)

14. **ML & AI improvements**
    - Train TOPSIS weights from user feedback
    - Predictive traffic modeling
    - Personalized route recommendations
    - Anomaly detection (unusual delays, route disruptions)

### 14.3 Infrastructure Improvements

| Area | Current | Target |
|------|---------|--------|
| Hosting | Local dev only | Docker + cloud deployment |
| Database | In-memory files | SQLite or PostgreSQL |
| Caching | In-memory dicts | Redis |
| Monitoring | None | Structured logging + metrics |
| Testing | Manual | Automated tests (pytest + vitest) |
| CI/CD | None | GitHub Actions |
| Documentation | This file | API docs + component storybook |

### 14.4 Segment Builder — Detailed Roadmap

**Current state:** ✅ Working — user can build multi-stop routes step-by-step with all transport options, filtered by group size and budget

**Next improvements in order:**

1. **Edit mode** — Allow clicking a previous segment to change its option, then recalculate downstream
2. **Route comparison** — After building a custom route, compare its score against the auto-generated direct routes
3. **Intermediate destination support** — Allow adding actual places (not just transit stops) as waypoints
4. **Schedule integration** — Show departure/arrival times if GTFS stop_times are loaded
5. **Multiple route suggestions** — After each step, suggest 2-3 best continuations based on TOPSIS
6. **Price breakdown** — Show running total + per-person with a progress bar against budget
7. **Time constraint** — Allow setting "arrive by" or "depart at" time
8. **Saved segments** — Allow saving a built route as a template for future use
9. **Visual timeline** — Gantt-chart style view of the entire journey timeline
10. **Map integration** — Show only the relevant segment path on hover, highlight stops more prominently

---

## 15. Appendix: File Reference

### 15.1 Key Backend Files

| File | Lines | Purpose |
|------|-------|---------|
| `backend/main.py` | 54 | App entry point, CORS, routers |
| `backend/api/routes.py` | 570 | Route planning endpoints |
| `backend/api/search.py` | ~200 | Search & discovery endpoints |
| `backend/services/transit_service.py` | 1027 | Core route engine, OSRM, segment builder |
| `backend/services/gtfs_service.py` | 141 | BMTC GTFS loader |
| `backend/services/geocoding.py` | ~450 | Place search + enrichment |
| `backend/services/llm_agent.py` | ~300 | LLM orchestration |
| `backend/services/n8n_service.py` | ~150 | n8n webhook proxy |
| `backend/services/images.py` | ~50 | Wikipedia image fetcher |
| `backend/core/database.py` | ~300 | In-memory transit DB |
| `backend/core/config.py` | 49 | Settings from .env |
| `backend/models/transit.py` | ~100 | Pydantic models |

### 15.2 Key Frontend Files

| File | Lines | Purpose |
|------|-------|---------|
| `frontend/src/App.tsx` | ~50 | Root component |
| `frontend/src/pages/MainPage.tsx` | ~200 | App orchestrator |
| `frontend/src/components/AToBPanel.tsx` | 886 | Main route panel |
| `frontend/src/components/MapView.tsx` | 362 | Leaflet map |
| `frontend/src/components/SearchPanel.tsx` | ~250 | Search UI |
| `frontend/src/components/DiscoveryPanel.tsx` | ~150 | Place details |
| `frontend/src/components/NewsOverlay.tsx` | ~100 | News display |
| `frontend/src/components/TripPanel.tsx` | ~30 | Trip stub |
| `frontend/src/services/api.ts` | 122 | API client |
| `frontend/src/types/index.ts` | 244 | TypeScript types |
| `frontend/src/utils/helpers.ts` | 119 | UI formatters |

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

> **END OF DOCUMENTATION**
>
> This document covers the complete VOYAGER Bengaluru Transit Navigator project
> as of July 14, 2026. For the latest updates, refer to AGENTS.md and the
> project issue tracker.
