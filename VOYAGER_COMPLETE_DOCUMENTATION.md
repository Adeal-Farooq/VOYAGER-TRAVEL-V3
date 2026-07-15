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
const [segmentStep, setSegmentStep] = useState<SegmentStepData | null>(null)
const [segmentLoading, setSegmentLoading] = useState(false)
const [hoveredOption, setHoveredOption] = useState<SegmentStepOption | null>(null)
const [builtPath, setBuiltPath] = useState<SegmentStepOption[]>([])     // User's chosen steps
const [columns, setColumns] = useState<ColumnCard[]>([])                 // UI columns
const [currentFromName, setCurrentFromName] = useState(sourceName)       // Current "you are here"
const [phase, setPhase] = useState<'init' | 'from' | 'direct'>('init')  // Current phase
```

### 6.3.2 Phase Flow

**Phase = "init"** (default):
- Backend is called to get all options from current location
- Columns are built:
  - Column 0: "🏁 Direct to Destination" (walk + all ride types)
  - Column 1..N: Each via stop's reach options 🚏 StopName (walk + rides to stop)
- User can:
  - Click a direct option → calls `handlePickDirect()`
  - Click a reach option → calls `handlePickReach()`

**Phase = "from"** (transitioned by `handlePickReach`):
- A new column appears showing from_stop_options for the selected stop
- User can:
  - Click a from option that arrives_at_stop=false → calls `handlePickFrom()` → journey complete
  - Click a from option that arrives_at_stop=true → goes to next init phase from that stop

**Phase = "direct"** (journey complete):
- `isComplete = true`
- "✅ Full Journey Path" section shows at bottom with all steps
- Budget bar, duration, distance totals displayed

### 6.3.3 `handlePickDirect` (Direct Option Selected)

```typescript
const handlePickDirect = useCallback((opt: SegmentStepOption) => {
    setBuiltPath(prev => [...prev, opt])
    setCurrentFromName(destName)
    setSegmentStep(null)
    setPhase('direct')
    // *** FIXED: Only keep the direct column with selection ***
    setColumns(prev => prev.filter(c => c.type === 'direct').map(c => ({ ...c, selectedOption: opt })))
}, [destName])
```

When user clicks a direct option (walk, cab, auto, bike), the journey is complete. The other columns (via_stop reach options) are removed so the user doesn't see confusing "next step" options.

### 6.3.4 `handlePickReach` (Reach Option Selected)

```typescript
const handlePickReach = useCallback((vi: number, opt: SegmentStepOption, fromStep: SegmentStepData) => {
    const vs = fromStep.via_stops[vi]
    setBuiltPath(prev => [...prev, opt])
    setCurrentFromName(opt.to)
    setPhase('from')
    // Mark reach column as selected
    setColumns(prev => prev.map(c => {
        if (c.stageIdx === vi && c.type === 'reach') return { ...c, selectedOption: opt }
        return c
    }))
    // Add new column for from_stop_options
    const newCol: ColumnCard = {
        stageIdx: vi,
        fromName: vs.stop.name,
        options: vs.from_stop_options,
        label: `🚀 From ${vs.stop.name}`,
        type: 'from',
    }
    setColumns(prev => [...prev, newCol])
}, [])
```

### 6.3.5 `handlePickFrom` (From Option Selected)

```typescript
const handlePickFrom = useCallback((opt: SegmentStepOption, colIdx: number) => {
    setBuiltPath(prev => [...prev, opt])
    if (opt.arrives_at_stop && opt.to_lat && opt.to_lng) {
        // Go to next stop (transit leg) - fetch new segment step from arrival location
        setCurrentFromName(opt.to)
        fetchStepFrom(opt.to_lat, opt.to_lng, opt.to)
    } else {
        // Reached destination! Journey complete
        setCurrentFromName(opt.to)
        setSegmentStep(null)
        setPhase('direct')
    }
}, [fetchStepFrom])
```

### 6.3.6 Column `isNext` Logic

```typescript
columns.map((col, colIdx) => {
    const isNext = colIdx > 0 && !columns[colIdx - 1].selectedOption
    if (isNext) return null  // Hide this column
    return <ColumnComponent ... />
})
```

This creates a sequential flow:
- Column 0 is always shown (direct options)
- Column 1 (first via_stop) is shown only AFTER column 0 is selected
- Column 2 (from options) is shown only AFTER column 1 is selected
- And so on...

**Important**: When a direct option is selected, `handlePickDirect` now filters columns to only keep type='direct', so the sequential flow doesn't show via stops after completing the journey.

### 6.3.7 UI Components

**Timeline Bar**: Horizontal scrollable bar showing:
- Source location (blue circle)
- For each step: mode icon + stop name + cost
- Destination flag (green when complete)
- Clickable previous steps to go back (via `handleGoBack()`)

**Summary Bar**: Shows total fare (with budget progress bar), total duration, total distance, step count

**Option Cards**: Color-coded by mode:
- Walk: green border
- Cab: orange border
- Auto: yellow border
- Bike: purple border
- Bus: blue border
- Metro: green border
- Train: purple border

**Card Content**:
- Mode icon + label
- Route number badge (for buses)
- Train number (for trains)
- Duration + distance
- Fare (total + per-person)
- Bus departure times (up to 4)
- Sub-legs (for combo routes)

**"Schedule data not available"**: Shown for bus cards that have no GTFS timings (but bus cards WITHOUT timings are now filtered out on backend).

**Custom Stop**: Search input to add an arbitrary waypoint mid-route using the places API.

### 6.3.8 Go-Back Functionality

`handleGoBack(stepIndex)`:
- Truncates `builtPath` to the given index
- Clears columns and re-fetches from the truncated location
- If stepIndex < 0, resets to the beginning

### 6.3.9 Map Geometry

Every chosen option emits geometry to the parent component via `onGeometryChange`:
- `type: 'segment'` for route paths (colored by step index)
- `type: 'stop'` for intermediate stops
- `type: 'hover'` for hovered options (yellow highlight)

---

# 7. GTFS INTEGRATION

## 7.1 GTFS Loader (`backend/services/gtfs_service.py`)

### 7.1.1 Loading Process

The `GTFSLoader.load()` method reads `bmtc_gtfs.zip` from the data cache directory:

1. **shapes.txt**: Reads shape_id + lat/lng sequence → builds shape coordinates
2. **stops.txt**: Reads stop_id + stop_name + lat/lng → indexes by stop_name
3. **trips.txt + routes.txt**: Maps route_id → route_short_name, route_short_name → shape_ids
4. **stop_times.txt**: Reads stop_id + departure_time + trip_id (limited to 50,000 rows) → maps by stop_name → list of (departure_time, route_short_name)

### 7.1.2 Key Data Structures

```python
self.stops_by_name: Dict[str, {"lat": float, "lng": float, "stop_id": str}]
self.stop_times: Dict[str, List[{"departure_time": str, "route": str}]]  # Route short name
self.route_shapes: Dict[str, List[str]]  # route_short_name -> [shape_ids]
self.shapes: Dict[str, List[Tuple[float, float]]]  # shape_id -> [(lat, lng)]
self.stop_to_shapes: Dict[str, List[Tuple[str, int]]]  # stop_name -> [(shape_id, seq)]
```

### 7.1.3 Key Methods

**`get_next_buses(stop_name, limit=3)`**:
- Gets all stored departure times for this stop
- Filters by current time (HH:MM:SS comparison)
- Returns `[{departure_time: "HH:MM:SS", route: "201K"}, ...]` (max `limit` items)
- If no future times found, returns all times (both past and future)

**`get_shape_between_stops(from_name, to_name)`**:
- Finds a shape that passes through both stops
- Clips the shape to the segment between the two stops
- Returns `[(lat, lng), ...]` or None

## 7.2 Integration Points

### In transit_service.py:
- `_ensure_gtfs()`: Lazy-loads GTFS on first call
- `get_segment_step_options()`: Calls `_ensure_gtfs().get_next_buses(stop_name, 20)` to get bus timings for all route cards
- `_add_leg_paths()`: Calls `_gtfs.get_shape_between_stops()` for bus leg geometry

## 7.3 Performance

- Loading takes ~40 seconds (synchronous, blocks startup)
- Limited to 50,000 stop_times rows
- Per stop, only 5 departure times stored
- First request may trigger GTFS loading (lazy initialization)

---

# 8. FRONTEND COMPONENTS

## 8.1 App.tsx (Root)

**Purpose**: Root React component that manages top-level state and renders MainPage.

**States**:
- `mode`: 'search' | 'atob' | 'trip' (switches between panels)
- `userLocation`: Browser geolocation coordinates
- `sourceLocation`, `destLocation`: For A-to-B routing
- `selectedPlace`, `allMarkers`: For map display

**On Mount**: Requests browser geolocation, defaults to Bangalore center (12.9716, 77.5946).

## 8.2 MainPage.tsx (Main Layout)

**Layout**: Sidebar (420px) + Map container

**Sidebar Content**:
- Header with app name + location button
- Mode tabs: Search / A-to-B / Trip
- Content panel (switches based on mode)

**Map Overlays**:
- `SegmentPanel` (conditional, appears when segment builder is open)
- `DiscoveryPanel` (conditional, shows place details)
- `NewsOverlay` (conditional, shows travel news)

**State**: Manages route geometry, news items, segment panel visibility, segment geometry for map display.

## 8.3 SearchPanel.tsx

**Props**: Search/nearby callbacks, map center, view details handler

**Two modes**:
1. **Search**: Debounced text input (300ms), autocomplete suggestions, results grid
2. **Nearby**: Radius slider (0.5-10km), 26 category tags, results grid

**PlaceCard**: Shows image, name, type badge, address, distance, rating, reliability score, review summary, action buttons (View Details, Navigate, Nearby Here).

## 8.4 AToBPanel.tsx

**Props**: Source/dest locations, route geometry callback, news callback, waypoints, segment builder opener

**A-to-B Routing Interface**:
- Source and destination search inputs with debounced autocomplete
- Waypoint system: up to 5 intermediate stops, each with search
- Travel mode selector: Public/Online, Drive, Walk
- Preferences: group size (1-6), budget
- **"🔧 Open Segment Builder"** button (calls `handleOpenSegmentPanel`)
- "Find Routes" button → calls `planRoute()` API

**After Route Planning**:
- AI recommendation box
- Weather/traffic info
- Ride price estimates
- Route cards with score bar, leg breakdown, expandable details
- Auto-refresh news every 30 seconds

## 8.5 TripPanel.tsx

Placeholder component showing "coming soon" message.

## 8.6 MapView.tsx

**Leaflet Map Features**:
- OpenStreetMap tile layer
- User location marker (glowing 📍 pin)
- Source/destination markers (green/red)
- Place markers (colored by reliability)
- Transit stop markers (green circles)
- News markers (colored by impact)
- Waypoint markers (orange, numbered)
- Route polylines: white outline + colored fill, dashed for walking
- **TrafficLayer**: Toggleable overlay with color-coded road congestion
- **MapController**: Syncs map ref, handles clicks

## 8.7 DiscoveryPanel.tsx

**Props**: Place data, close handler

**Content**: Image, name, recommendation badge, rating, reliability score, address, type, review summary, expandable reviews (up to 4, with source indicator), price info, hotel prices, distance.

## 8.8 NewsOverlay.tsx

**Props**: News items, loading state, location handler

Collapsible overlay at top of map with 4 tabs: All, Alerts, Info, Positive. Shows up to 5 news items with impact icon, title, description, timestamp.

---

# 9. API ENDPOINTS

## 9.1 Search Endpoints (`/api/search/`)

| Method | Endpoint | Parameters | Returns |
|--------|----------|------------|---------|
| GET | `/api/search/places` | q, lat, lng | Place search results |
| GET | `/api/search/nearby` | lat, lng, radius_km, place_type | Nearby places |
| GET | `/api/search/suggestions` | q | Autocomplete suggestions |
| GET | `/api/search/verify-place` | name, address | Place verification |
| GET | `/api/search/ai-chat` | message, lat, lng | AI chat response |
| POST | `/api/search/enrich-place` | body: name, lat, lng, place_type, address | Enriched place data |
| GET | `/api/search/ride-prices` | source, destination | Ride price estimates |
| GET | `/api/search/current-events` | location | Current events text |

## 9.2 Route Endpoints (`/api/routes/`)

| Method | Endpoint | Parameters | Returns |
|--------|----------|------------|---------|
| POST | `/api/routes/plan` | ATobRequest body | Route plan with routes + weather + recommendations |
| GET | `/api/routes/metro-stations` | line (optional) | Metro station list |
| GET | `/api/routes/bus-stops` | near_lat, near_lng, radius | Nearby bus stops |
| GET | `/api/routes/kia-routes` | -- | KIA Vayu Vajra routes |
| GET | `/api/routes/transit-fares` | -- | Fare slabs |
| GET | `/api/routes/live-prices` | source, dest, mode | LLM ride price estimates |
| GET | `/api/routes/mini-path-options` | source_lat/lng, dest_lat/lng, group_size | Mini path breakdown |
| GET | `/api/routes/segment-step` | from_lat/lng/name, dest_lat/lng/name, group_size, budget | Segment step data |
| GET | `/api/routes/news` | source/dest lat/lng + names | Travel news |
| GET | `/api/routes/traffic-overlay` | north, south, east, west | Traffic GeoJSON |

## 9.3 Segment Step API Detail

**Endpoint**: `GET /api/routes/segment-step`

**Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| from_lat | float | Current latitude |
| from_lng | float | Current longitude |
| from_name | string | Current location name |
| dest_lat | float | Destination latitude |
| dest_lng | float | Destination longitude |
| dest_name | string | Destination name |
| group_size | int | Number of travellers (default: 1) |
| budget | float | Max budget (optional) |

**Response**: `{ status: "success", step: SegmentStepData }` (see Section 6.2 for structure)

---

# 10. DATA LAYER

## 10.1 Data Files in `data_cache/`

| File | Source/Format | Content | Size |
|------|-------------|---------|------|
| `bmtc_gtfs.zip` | BMTC GTFS feed | shapes, stops, stop_times, trips, routes | ~50MB zipped |
| `bmtc_all_stops_master.csv` | Derived from GTFS | 20,000+ bus stops with route lists | Large CSV |
| `bengaluru_metro_network.csv` | Manual/compiled | Metro stations with lines, sequences, distances | ~150 rows |
| `karnataka_railway_stations.json` | Compiled | 48 railway stations with coordinates | JSON array |
| `kia_routes_fare_full.json` | KIA website/manual | Airport bus routes with stop-wise fares | JSON |
| `transit_fares.json` | Compiled from sources | Fare slabs for metro, ordinary bus, AC bus | JSON |
| `traffic_logs.csv` | Demo data | Simulated traffic speed logs | CSV |

## 10.2 Transit Fares (`transit_fares.json`)

Contains three fare systems:

1. **Namma Metro**: Distance-based slabs (e.g., 0-2km: ₹10, 2-5km: ₹15, etc.)
2. **BMTC Ordinary Bus**: Distance-based slabs with discounts for child (50%) and senior (75%)
3. **BMTC AC Vajra (Vajra)**: Higher distance-based slabs

---

# 11. PRICING AND FARES

## 11.1 Ride-Hailing Pricing

All ride types use the same formula:
- `per_person = round(base_fare + distance × per_km_rate)`
- `total = per_person × group_size`

| Mode | Base Fare | Per KM | Per Minute | Capacity |
|------|-----------|--------|-----------|----------|
| Cab (Uber Go / Ola Mini) | ₹25 | ₹14/km | 3 min/km | 4 |
| Cab XL (Uber XL / Ola XL) | ₹40 | ₹20/km | 3 min/km | 6 |
| Auto | ₹15 | ₹10/km | 5 min/km | 3 |
| Bike (Uber Moto / Rapido) | ₹10 | ₹6/km | 2 min/km | 1 |
| Cab for Women | ₹25 | ₹14/km | 3 min/km | 4 |
| Cab Pet | ₹30 | ₹17/km | 3 min/km | 4 |

## 11.2 Bus Fares

- **Ordinary**: `max(6, round(db.get_bmtc_ordinary_fare(distance)))` per person
  - Child discount: 50%
  - Senior discount: 75%
- **AC Vajra**: `round(db.get_bmtc_ac_fare(distance))` per person
  - No artificial floor (removed in a recent fix)

## 11.3 Metro Fares

- `db.get_metro_fare(distance)`: Returns fare from slab table
- Typically ₹10-₹40 depending on distance

## 11.4 Train Fares

- `max(15, round(distance × 0.8))` per person
- Hardcoded approximate (not actual IRCTC pricing)

## 11.5 Fuel Cost (for personal driving)

- `fuel_cost = (distance / 15) × 110` (15 km/l mileage, ₹110/liter petrol)

---

# 12. TRAIN INTEGRATION

## 12.1 Hardcoded Routes (`_TRAIN_DATA`)

```python
_TRAIN_DATA = {
    ("bengaluru", "mysuru"): [
        ("16517", "KSR Bengaluru - Mysuru Kannada Express", "06:45", "09:25"),
        ("12613", "Shatabdi Express", "11:00", "13:00"),
        ("12007", "Shatabdi Express", "14:00", "16:00"),
        ("16535", "Gol Gumbaz Express", "07:45", "10:25"),
        ("16232", "Mysuru Express", "12:30", "15:10"),
    ],
    ("mysuru", "bengaluru"): [
        ("16518", "Mysuru - KSR Bengaluru Kannada Express", "06:00", "08:40"),
        ("12614", "Shatabdi Express", "14:30", "16:30"),
        ("12008", "Shatabdi Express", "06:30", "08:30"),
        ("16536", "Gol Gumbaz Express", "16:00", "18:40"),
        ("16231", "Mysuru Express", "05:30", "08:10"),
    ],
    ("bengaluru", "hubballi"): [
        ("17325", "Vishwamanava Express", "15:00", "22:30"),
        ("16589", "Rani Chennamma Express", "22:00", "06:30"),
    ],
    ("hubballi", "bengaluru"): [
        ("17326", "Vishwamanava Express", "06:00", "13:30"),
        ("16590", "Rani Chennamma Express", "20:00", "04:30"),
    ],
    ("bengaluru", "mangaluru"): [
        ("16511", "KSR Bengaluru - Kannur Express", "23:30", "09:45"),
        ("16585", "Mokashi Express", "22:15", "08:30"),
    ],
    ("mangaluru", "bengaluru"): [
        ("16512", "Kannur - KSR Bengaluru Express", "17:00", "03:15"),
        ("16586", "Mokashi Express", "19:00", "05:15"),
    ],
    ("bengaluru", "belagavi"): [
        ("17309", "Basava Express", "22:00", "08:30"),
    ],
    ("belagavi", "bengaluru"): [
        ("17310", "Basava Express", "19:00", "05:30"),
    ],
    ("bengaluru", "ballari"): [
        ("16545", "KSR Bengaluru - Ballari Express", "22:30", "06:30"),
    ],
    ("ballari", "bengaluru"): [
        ("16546", "Ballari - KSR Bengaluru Express", "23:00", "07:00"),
    ],
}
```

Currently covers only 5 city pairs. No trains within Bengaluru or to other Karnataka cities covered.

## 12.2 Station Name Normalization (`_get_train_options`)

Maps 20+ station name variants to canonical names:

| Variant | Canonical |
|---------|-----------|
| KSR Bengaluru, Bengaluru City, KSR Bangalore, Bengaluru Cantonment, Yesvantpur, Krshnarajapuram, Whitefield | bengaluru |
| Mysuru, Mysore, Mysuru Junction | mysuru |
| Hubballi, Hubli, Hubballi Junction | hubballi |
| Mangaluru, Mangalore, Mangaluru Junction, Mangaluru Central | mangaluru |
| Belagavi, Belgaum | belagavi |
| Ballari, Bellary | ballari |
| Kalaburagi, Gulbarga, Kalaburagi Junction | kalaburagi |
| Vijayapura, Bijapur | vijayapura |
| Hosapete, Hospet, Hosapete Junction | hosapete |
| Shivamogga, Shimoga | shivamogga |

## 12.3 Unknown Route Generation

For city pairs not in `_TRAIN_DATA`, generates a generic option:
- Duration: `max(1, round(distance / 50))` hours
- Departure: deterministic pseudo-random from station names
- Train number: pseudo-random `1XXXX` format
- Name: "Intercity Express ({from} - {to})"

---

# 13. RAILWAY STATIONS

## 13.1 Station Coverage

48 Karnataka railway stations are loaded from `karnataka_railway_stations.json`. These cover major stations across Karnataka including:

- Bengaluru area: KSR Bengaluru, Yesvantpur, Krishnarajapuram, Whitefield, Yelahanka, Banaswadi, Bengaluru Cantonment, Heelalige, etc.
- Mysuru area: Mysuru Junction, Chamarajanagar, etc.
- Other cities: Mangaluru, Udupi, Hubballi, Dharwad, Belagavi, Ballari, Hosapete, Shivamogga, Davanagere, Tumakuru, Chitradurga, etc.

## 13.2 Finding Railway Stations

Two approaches in the code:

1. **`db.find_nearby_railway_stations(lat, lng, radius_km)`**: Finds stations within a given radius (default 30km). Used in `get_segment_step_options` for creating via stops (15km from source, 30km from dest).

2. **`_get_train_options()`**: Matches station names to find train routes between pairs.

## 13.3 Railway Via Stop Creation

Railway via stops are created in `get_segment_step_options()` when:
- Source has a railway station within 15km
- AND (destination is outside Bengaluru OR any railway station found)

For each railway stop:
- **Reach**: Walk + rides to the station
- **From**: 
  - Train options to destination railway station (if dest station within 30km)
  - Last-mile cab/walk from destination station to actual destination

---

# 14. METRO INTEGRATION

## 14.1 Network Coverage

Namma Metro (Bengaluru) with two operational lines:
- **Purple Line**: Baiyappanahalli ↔ Mysuru Road (and extending to Whitefield/Kengeri)
- **Green Line**: Nagasandra ↔ Silk Institute
- **Interchange**: Majestic (Kempegowda Station)

Each station has: name, line, sequence number, coordinates, interchange flag, distance_from_prev_km.

## 14.2 Integration Points

### In `get_segment_step_options()` (Segment Builder):
- Metro stations are included as via stops (up to 3, within 2km)
- From options include:
  - Metro ride to destination metro station (if within 2km of dest)
  - Bus routes from station to destination bus stops (with GTFS timings)
  - Walk to destination (if ≤ 2km)
  - Rides to destination

### In Route Generation:
- `_generate_metro_routes()`: Direct walk→metro→walk routes
- `_generate_metro_interchange_routes()`: Metro with line change at interchange
- `_generate_multi_modal_routes()`: Bus→metro and metro→bus combinations

### Metro Distance Cache:
`db.get_metro_distance_between()` caches station-to-station distances for performance. Uses Haversine as fallback when sequence-based calculation fails.

---

# 15. BUS INTEGRATION

## 15.1 BMTC Bus Stop Data

20,000+ BMTC bus stops are loaded from `bmtc_all_stops_master.csv`. Each stop has:
- `stop_id`: Unique identifier
- `name`: Stop name
- `lat`, `lng`: Coordinates
- `routes`: List of route numbers serving this stop (parsed from CSV)

## 15.2 Route Number Matching

Common routes between two stops are found using `_find_common_routes()`:
```python
def _find_common_routes(self, src_stop, dest_stop):
    src_routes = set(src_stop.get("routes", []))
    dest_routes = set(dest_stop.get("routes", []))
    return sorted(src_routes & dest_routes)[:5]
```

This is used in:
- `_get_bus_route_nums()`: Returns common routes between any two stops
- `has_common` check in segment builder: Whether a stop has common routes with destination area

## 15.3 Bus Route Card Generation

In the segment builder's from_stop_options, each common route number gets its own individual card with:
- Route number badge
- Per-route bus timing pills (from GTFS)
- Per-route fare calculation
- Both ordinary and AC Vajra variants

**Important**: Bus cards are now ONLY shown if they have available bus_timings (filtered out when empty/null).

## 15.4 Bus Fare Calculation

- **Ordinary**: `db.get_bmtc_ordinary_fare(transit_dist)` → `max(6, round(fare))` per person
- **AC Vajra**: `db.get_bmtc_ac_fare(transit_dist)` → `max(10, round(fare))` per person
- Total: per_person × group_size

---

# 16. RIDE TYPES / CABS / AUTO / BIKE

## 16.1 Available Ride Types

Six ride types are supported across the application:

1. **Cab** (Uber Go / Ola Mini): Standard 4-seater, ₹14/km
2. **Cab XL** (Uber XL / Ola XL): 6-seater, ₹20/km
3. **Auto** (Auto): 3-seater, ₹10/km
4. **Bike** (Uber Moto / Rapido): 1-seater, ₹6/km
5. **Cab for Women** (Uber for Women / Ola for Women): 4-seater, ₹14/km
6. **Cab Pet** (Uber Pet): 4-seater, ₹17/km

## 16.2 Where Rides Appear

1. **Direct Options** (Segment Builder Column 0): Always all ride types (filtered by capacity and budget)
2. **Reach Options** (in via_stops): Always all ride types to reach the transit stop
3. **From Stop Options** (in via_stops): Always all ride types to destination from the transit stop

## 16.3 Filtering Rules

- Group capacity: Ride excluded if `group_size > capacity`
- Budget: Ride excluded if `total_fare > budget`
- No distance-based minimum (rides now available even for very short distances)

---

# 17. SMART FILTERING RULES

## 17.1 Distance Thresholds

| Rule | Threshold | Location |
|------|-----------|----------|
| Walk show limit | ≤ 5 km for direct walk | transit_service.py:801 |
| Walk to stop | ≤ 2 km | transit_service.py:903 |
| Near bus search radius | 1.0 km | transit_service.py:841 |
| Near metro search radius | 2.0 km | transit_service.py:842 |
| Near rail search radius | 15 km (source), 30 km (dest) | transit_service.py:1154-1155 |
| Transit ride skip | < 0.5 km | transit_service.py:934 |
| Bengaluru boundary | 35 km from center (12.9716, 77.5946) | transit_service.py:768 |

## 17.2 Bus Stop Skip Logic

A bus stop is skipped as a via stop if ALL of:
- Distance > 2 km from source
- No common bus routes with destination area
- Stop-to-destination distance > 50 km

## 17.3 Metro Station Skip Logic

A metro station is skipped if ALL of:
- No destination metro nearby (within 2km of dest)
- Distance > 2 km from source
- Destination is outside Bengaluru

## 17.4 Bus Timing Filtering (NEW)

Bus route cards in from_stop_options are now filtered:
- **Only shown if GTFS timings are available** for that specific route at that stop
- If `route_times` is empty → skip the bus card entirely (both ordinary and AC Vajra)
- User sees only ride/cab/auto options instead of dead bus cards

## 17.5 Ride Filtering for Reach Options (UPDATED)

Rides in reach_options are now **always available** (removed the ≥ 0.5 km restriction):
- Previously: only if `dist >= 0.5`
- Now: rides shown for all distances (even 0 km)

## 17.6 Budget Filtering

- Direct options: `if budget and total > budget: continue`
- Reach options: `if budget and total > budget: continue`
- From options: `if budget and total_fare > budget: continue`

---

# 18. MULTI-MODAL ROUTES

## 18.1 Route Types Generated

| Route Type | Legs | Description |
|------------|------|-------------|
| bus_ordinary | walk→bus→walk | Ordinary BMTC bus |
| bus_ac_vajra | walk→bus→walk | AC Vajra bus |
| metro | walk→metro→walk | Direct metro |
| metro_interchange | walk→metro(L1)→interchange→metro(L2)→walk | Metro with line change |
| kia_bus | walk→KIA bus→walk | Airport bus |
| bus_to_metro | walk→bus→metro→walk | Bus then metro |
| metro_to_bus | walk→metro→bus→walk | Metro then bus |
| driving | direct drive | Personal car route |

## 18.2 Bus + Cab Combo (Out-of-Bengaluru)

For destinations outside Bengaluru (>35km from center):
1. Find the farthest BMTC bus stop en route to the destination
2. Create a bus_then_cab via stop with:
   - Reach: bus_ordinary to the farthest stop
   - From: cab from farthest stop to destination

## 18.3 Train + Last-Mile (Railway)

For railway via stops:
1. Train from source station to destination station
2. Last-mile: walk (if ≤2km) or cab from destination station to actual destination

---

# 19. LLM / AI INTEGRATION

## 19.1 Architecture

```
┌─────────────┐     HTTP API Key    ┌─────────────────┐
│  LLMAgent    │ ──────────────────►│   OpenRouter     │
│  (primary)   │     gpt-4o-mini    │   (API Key: .env) │
├─────────────┤                    └─────────────────┘
│ LLMAgent    │     HTTP API Key    ┌─────────────────┐
│ (fallback)  │ ──────────────────►│   Gemini         │
│             │     gemini-1.5-flash│   (API Key: .env) │
└─────────────┘                    └─────────────────┘
```

## 19.2 LLMAgent Methods

| Method | Uses | Fallback |
|--------|------|----------|
| `search_places_ai(query, lat, lng)` | OpenRouter → Gemini models | None |
| `verify_place(name, address)` | n8n webhook → OpenRouter → Gemini | Returns default |
| `get_smart_suggestions(partial)` | OpenRouter → Gemini | None |
| `get_nearby_ai(lat, lng, type, radius)` | OpenRouter → Gemini | None |
| `get_travel_recs(source, dest, group_size, budget)` | OpenRouter → Gemini | None |
| `get_live_prices(source, dest, mode)` | OpenRouter → Gemini | Returns empty |
| `get_weather_impact(location)` | n8n → wttr.in → OpenRouter → defaults | Default weather |
| `get_current_events(location)` | WebSearchAgent → OpenRouter → Gemini | Default text |
| `get_travel_news(source, dest)` | WebSearchAgent → OpenRouter → Gemini → defaults | Default items |
| `get_real_reviews(name, address)` | WebSearchAgent → OpenRouter → Gemini → generated | Generated reviews |
| `chat_response(user_message, context)` | OpenRouter → Gemini | Error response |

## 19.3 OpenRouter Model Fallback Chain

1. `openai/gpt-4o-mini` (primary working model)
2. `openai/gpt-3.5-turbo`
3. `anthropic/claude-3-haiku`
4. `meta-llama/llama-3-8b-instruct`
5. `mistralai/mistral-7b-instruct`
6. `google/gemini-1.5-flash`

## 19.4 WebSearchAgent

Scrapes DuckDuckGo HTML results for web search capabilities. Used for travel news and place reviews.

---

# 20. n8n WORKFLOW INTEGRATION

## 20.1 Overview

n8n is a self-hosted workflow automation tool. If running at the configured webhook URL, workflows can provide:
- Weather and traffic data
- Ride price estimates
- Place verification
- Place reviews
- Hotel price estimates

## 20.2 Workflow Files (in `workflows/`)

| File | Webhook Endpoint | Purpose |
|------|-----------------|---------|
| `weather_traffic_check.json` | `/webhook/weather-traffic` | Weather + traffic impact |
| `ride_price_estimation.json` | `/webhook/ride-prices` | Ride price estimates |
| `place_verification.json` | `/webhook/verify-place` | Place verification |
| `place_reviews.json` | `/webhook/place-reviews` | Real place reviews |
| `hotel_price_check.json` | `/webhook/hotel-prices` | Hotel price range |
| `test_wf.json` | -- | Test workflow |
| `test_format.json` | -- | Test format |

## 20.3 Service Layer (`n8n_service.py`)

All methods:
1. Check if `N8N_WEBHOOK_URL` is configured
2. Make HTTP POST to n8n webhook (5s timeout)
3. Parse response (handles OpenAI-style LLM response format)
4. Return structured data or None on failure

All methods return `None` if n8n is not configured or unreachable.

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

| Issue | Impact | Severity |
|-------|--------|----------|
| GTFS loading takes ~41s at startup | Delays first API request | P1 |
| First request may trigger lazy GTFS load | Blocks event loop | P1 |
| `find_nearby_bus_stops` iterates ALL 20k+ stops | Slow for repeated queries | P3 |
| Route planning path enrichment has 30s timeout | Silent failures | P2 |
| Metro distance cache rebuilds every startup | Redundant computation | P3 |

## 26.2 Data Limitations

| Limitation | Details |
|------------|---------|
| Bus stop data is static CSV | Not live/updated, route lists may be stale |
| Only 48 railway stations | Missing many Karnataka stations |
| Train data is hardcoded (only 5 city pairs) | Not comprehensive, no live schedules |
| GTFS data is a point-in-time snapshot | Not updated periodically |
| Traffic data is demo/simulated | Not from real-time sources |
| Per stop only 5 GTFS departure times stored | May miss some bus timings |

## 26.3 Feature Gaps

| Gap | Location | Impact |
|-----|----------|--------|
| Trip Panel is placeholder | TripPanel.tsx | No multi-destination trip planning |
| ML modules not connected | ml/topsis.py, ml/astar.py | Advanced scoring and pathfinding not used |
| No live GTFS refresh | gtfs_service.py | Data becomes stale over time |
| No real-time bus tracking | -- | Can't show "bus is X minutes away" |
| No payment integration | -- | Can't book rides directly |
| No user accounts/saved routes | -- | No personalization |

## 26.4 Code Quality Issues

| Issue | Location |
|-------|----------|
| Duplicated TOPSIS logic | transit_service.py + routes.py plan endpoint |
| Many `except: pass` blocks | Throughout backend |
| No automated tests | -- |
| CORS allows all origins (`*`) | main.py |
| API keys in plaintext .env | Not production-safe |

## 26.5 Port and Proxy Issues

- Frontend port was previously 5173, now 3000 (AGENTS.md updated)
- n8n expected on port 5678 (optional)
- Backend port 8000

---

# 27. NEXT STEPS / ROADMAP

## 27.1 Immediate Fixes (P0/P1)

1. **GTFS Loading**: Make async or move to background thread so startup isn't blocked for 41s
2. **Bus Stop Search**: Optimize by using spatial index (R-tree) instead of iterating all 20k+ stops
3. **Error Handling**: Replace bare `except: pass` with proper logging

## 27.2 Short-Term Improvements (P2)

1. **Segment Builder UX**:
   - Add clear visual distinction between direct options and reach options
   - Show via_stop reach options alongside direct options from the start (not hidden by `isNext`)
   - Add loading skeleton for column transitions
   - Highlight cheapest / fastest option in each column

2. **Route Planning**:
   - Add sorting/filtering options (cheapest, fastest, fewest transfers)
   - Add real-time traffic impact on duration estimates
   - Show next bus/metro departure times in route cards

3. **Data Refresh**:
   - Auto-download latest GTFS on startup
   - Cache busting for static data files
   - Add fallback to historical GTFS if download fails

## 27.3 Medium-Term Features (P3)

1. **ML Integration**:
   - Connect `ml/topsis.py` to replace inline scoring
   - Connect `ml/astar.py` as alternative pathfinder for complex routes
   - Add ML-based:
     - ETA prediction using historical traffic
     - Route recommendation personalization
     - Travel time reliability scoring
   - Detect optimal interchange points

2. **Trip Planner**:
   - Multi-destination trip building
   - Day-trip itinerary planning
   - Circular routes (return to origin)
   - Save and share trips

3. **Real-Time Features**:
   - Live bus tracking (if BMTC API available)
   - Live train running status
   - Cab fare comparison from actual APIs (Uber, Ola)
   - Traffic-aware ETA adjustments

4. **Payment Integration**:
   - In-app cab booking (Rapido, Uber Rickshaw API)
   - Auto/rickshaw fare negotiation assistant
   - BMTC bus pass/digital ticket info

## 27.4 Long-Term Vision (P4)

1. **User System**:
   - User accounts and authentication
   - Saved routes and favorites
   - Commute history and analytics
   - Personalized recommendations
   - Trip history with cost tracking

2. **Expanded Coverage**:
   - All Karnataka towns and cities
   - Inter-state bus routes (KSRTC, APSRTC, TNSTC)
   - Indian Railways full schedule integration
   - Flight options for long-distance
   - Auto-rickshaw stands and walkability data

3. **Mobile App**:
   - React Native / Flutter mobile version
   - Push notifications for bus/train departure alerts
   - Offline maps and schedules
   - Voice-guided navigation

4. **Advanced Features**:
   - Carbon footprint calculation per route
   - Safety scoring (lighting, crowd density, crime data)
   - Accessibility routing (wheelchair-friendly)
   - Weather-adaptive routing
   - Group splitting (different people travel by different modes)

---

# 28. WHAT CAN BE ADDED / ENHANCED

## 28.1 Segment Builder Enhancements

### Already Implemented
- ✅ Two-phase column system (init→from→direct)
- ✅ Individual bus route cards with timing pills
- ✅ AC Vajra variants alongside ordinary buses
- ✅ Go-back / edit previous segments
- ✅ Budget progress bar
- ✅ Per-person cost display
- ✅ Timeline with mode icons and fares
- ✅ Direct cab/auto/bike options always available
- ✅ Bus cards filtered out when no timings available
- ✅ Reach rides removed distance minimum restriction

### To Be Added
- ❌ Show via_stop reach options alongside direct options from start (not hidden by `isNext`)
- ❌ Highlight cheapest route per column
- ❌ Highlight fastest route per column
- ❌ Sorting options (sort by cost, time, transfers)
- ❌ Show total trip summary before committing
- ❌ "Express" mode (auto-select cheapest/fastest path)
- ❌ Favorites / recent routes
- ❌ Multiple simultaneous comparisons (side-by-side columns)
- ❌ Shared ride / carpool options

## 28.2 Route Pricing Enhancements

### Current System
- Ride pricing: base + per-km rates (hardcoded)
- Bus pricing: slab-based from `transit_fares.json`
- Metro pricing: slab-based from `transit_fares.json`
- Train pricing: `max(15, round(dist × 0.8))` (approximate)

### To Be Added
- ❌ Actual Uber/Ola API pricing (requires API access)
- ❌ Actual IRCTC train fares
- ❌ KSRTC bus fares for inter-city routes
- ❌ Dynamic pricing based on demand/time
- ❌ Toll costs for personal driving
- ❌ Parking costs at transit stations
- ❌ Combined fare discounts (monthly passes, etc.)
- ❌ Ride-sharing splits

## 28.3 Transport Mode Additions

### Current Modes
- ✅ BMTC Ordinary Bus
- ✅ BMTC AC Vajra
- ✅ Namma Metro
- ✅ Ride-hailing (cab, cab_xl, auto, bike, cab_women, cab_pet)
- ✅ Walking
- ✅ Indian Railways (limited)
- ✅ KIA Vayu Vajra (airport)
- ✅ Bus + cab combo (out-of-Bengaluru)

### To Be Added
- ❌ KSRTC bus services
- ❌ Electric auto-rickshaws
- ❌ E-bike / cycle rental
- ❌ Shared cabs / carpool
- ❌ School/office shuttle services
- ❌ Boat/ferry (if applicable for Bengaluru lakes)
- ❌ Night bus services
- ❌ EV charging stations along route

## 28.4 GTFS Improvements

### Current
- 50,000 stop_times limit
- Synchronous load at startup (~41s)
- Per stop: only 5 stored times

### To Be Added
- ❌ Async loading with progress indicator
- ❌ Background refresh every N hours
- ❌ Full stop_times load (remove limit)
- ❌ Trip direction filtering (outbound vs inbound)
- ❌ Route variant detection (express vs limited stop)
- ❌ Service calendar (weekday/weekend/holiday schedules)
- ❌ Real-time vehicle positions (if GTFS-RT available)

## 28.5 Data Sources to Integrate

| Source | Type | What It Provides |
|--------|------|-----------------|
| OpenTripPlanner | Open Source | Multi-modal routing engine (alternative to our custom engine) |
| GraphHopper | Open Source | Routing with traffic and elevation |
| HERE Maps API | Commercial | Real-time traffic, transit schedules |
| Google Maps API | Commercial | Comprehensive transit data |
| BMTC Open Data | Government | Official bus routes and schedules |
| IRCTC API | Government | Train schedules and fares |
| OSMnx | Python lib | Walk/bike network analysis |
| Weather API | Various | Real-time weather for routing impact |

## 28.6 AI/ML Enhancements

### Current LLM Integration
- Place search
- Travel news
- Reviews
- Ride price estimation
- Chat assistant

### To Be Added
- ❌ Personalized route recommendations based on user history
- ❌ Natural language trip planning ("I want to go from MG Road to the airport at 5pm")
- ❌ Predictive traffic patterns (ML model trained on logs)
- ❌ Anomaly detection (unusual delays, route disruptions)
- ❌ Chat-based route refinement ("make it cheaper", "avoid buses")
- ❌ Image-based location recognition
- ❌ Voice interface

---

# 29. APPENDIX: CODE CONVENTIONS

## 29.1 Python Backend

- **File encoding**: UTF-8
- **Imports**: Standard lib → third-party → local
- **Docstrings**: Google-style (brief)
- **Type hints**: Minimal, focused on function signatures
- **Error handling**: `try/except` with specific exceptions (avoid bare `except:` for new code)
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Constants**: UPPER_CASE module-level
- **Async**: Use `async/await` for I/O operations (HTTP calls)

## 29.2 TypeScript Frontend

- **File encoding**: UTF-8
- **Components**: Default exports, functional with hooks
- **State**: useState for local, useReducer for complex state
- **Effects**: useEffect with explicit dependency arrays
- **Callbacks**: useCallback for memoized handlers
- **Styling**: Inline `style={}` objects (no CSS modules)
- **Naming**: `PascalCase` for components, `camelCase` for functions/variables
- **Types**: Defined in `types/index.ts`, imported with `interface`

## 29.3 API Conventions

- **Endpoint format**: `/api/{resource}/{action}`
- **HTTP methods**: GET for reads, POST for writes
- **Response format**: `{ status: "success"|"error", data: {...} }`
- **Error responses**: `{ status: "error", error: "message" }`
- **Query parameters**: snake_case (Python backend convention)
- **Timeout**: 60s for frontend API calls

---

# 30. APPENDIX: FARE TABLES

## 30.1 Namma Metro Fares

Based on distance slabs from `transit_fares.json`:

| Distance (km) | Fare (₹) |
|---------------|----------|
| 0-2 | 10 |
| 2-5 | 15 |
| 5-10 | 20 |
| 10-15 | 25 |
| 15-20 | 30 |
| 20-25 | 35 |
| 25+ | 40 |

## 30.2 BMTC Ordinary Bus Fares

Distance-based slabs:

| Distance (km) | Fare (₹) | Child (50%) | Senior (75%) |
|---------------|----------|-------------|--------------|
| 0-2 | 6 | 3 | 4.5 |
| 2-4 | 8 | 4 | 6 |
| 4-6 | 10 | 5 | 7.5 |
| 6-8 | 12 | 6 | 9 |
| 8-10 | 14 | 7 | 10.5 |
| ... | ... | ... | ... |

Minimum fare: ₹6 (floor applied in code)

## 30.3 BMTC AC Vajra Fares

Higher slab rates for air-conditioned Vajra buses.

## 30.4 Ride-Hailing (Soft Estimates)

These are estimated fares, not actual API prices:

| Mode | Sample Fare (5km) | Sample Fare (10km) |
|------|-------------------|--------------------|
| Cab | ₹95 | ₹165 |
| Cab XL | ₹140 | ₹240 |
| Auto | ₹65 | ₹115 |
| Bike | ₹40 | ₹70 |
| Cab Women | ₹95 | ₹165 |
| Cab Pet | ₹115 | ₹200 |

---

> **END OF DOCUMENTATION**
>
> This document covers the complete VOYAGER Bengaluru Transit Navigator project
> as of July 14, 2026. For the latest updates, refer to AGENTS.md and the
> project issue tracker.
