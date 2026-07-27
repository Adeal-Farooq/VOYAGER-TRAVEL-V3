# VOYAGER � Complete Project Documentation

> **Project**: Bengaluru Multi-Modal Transit Navigator  
> **Status**: Active Development (Bug Fixing + Feature Completion Phase)  
> **Last Updated**: 2026-07-16

---

## TABLE OF CONTENTS

1. [PROJECT OVERVIEW](#1-project-overview)
2. [ARCHITECTURE � FULL SYSTEM MAP](#2-architecture--full-system-map)
3. [BACKEND: FastAPI Server](#3-backend-fastapi-server)
4. [FRONTEND: React + Vite + TypeScript](#4-frontend-react--vite--typescript)
5. [TRANSIT DATA PIPELINE](#5-transit-data-pipeline)
6. [ROUTE PLANNING ENGINE](#6-route-planning-engine)
7. [SEGMENT PANEL SYSTEM (MULTI-COLUMN UI)](#7-segment-panel-system-multi-column-ui)
8. [GTFS BUS INTEGRATION � DETAILED](#8-gtfs-bus-integration--detailed)
9. [METRO SYSTEM](#9-metro-system)
10. [TRAIN SYSTEM](#10-train-system)
11. [RIDE PRICING](#11-ride-pricing)
12. [LLM AGENT SYSTEM](#12-llm-agent-system)
13. [MULTI-HOP TRANSFER CHAINING](#13-multi-hop-transfer-chaining)
14. [MAP & PATH RENDERING](#14-map--path-rendering)
15. [TRAFFIC SYSTEM](#15-traffic-system)
16. [PERFORMANCE ANALYSIS](#16-performance-analysis)
17. [KNOWN BUGS & ISSUES](#17-known-bugs--issues)
18. [BUG FIX LOG](#18-bug-fix-log)
19. [NEXT FEATURES TO BUILD](#19-next-features-to-build)
20. [FUTURE IMPROVEMENTS](#20-future-improvements)
21. [DEPLOYMENT OPTIONS](#21-deployment-options)
22. [EVERY FUNCTION IN DETAIL](#22-every-function-in-detail)
23. [TESTING PROCEDURES](#23-testing-procedures)
24. [APPENDIX: DATA FILES](#24-appendix-data-files)

---

## 1. PROJECT OVERVIEW

VOYAGER is a multi-modal transit route planner for Bengaluru, India combining walking, BMTC buses (GTFS), Namma Metro, Indian Railways, KIA airport buses, ride-hailing (cab/auto/bike), and personal car.

### 1.1 Core Innovation

Instead of a single route result list, a **progressive multi-column panel** grows from 1 to N columns:
- **Column 0**: Direct options (walk/cab/auto/bike) from Source to Destination
- **Column 1**: Nearby transit stops with reach options (walk/cab/auto/bike) from Source to each stop
- **Column 2**: Transit options from selected stop (bus routes with GTFS timings, metro, train) with arrival stop + final mile
- **Column N**: Subsequent transfers (bus?bus, bus?metro, metro?bus, bus?train?bus) recursively up to depth=3
- **Last Column**: Final mile options (walk/cab/auto/bike) from last transit stop to Destination

### 1.2 Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python FastAPI + Uvicorn | Port 8000, --reload |
| Frontend | React 19 + TypeScript + Vite | Port 3000, proxy /api ? :8000 |
| Map | Leaflet + React-Leaflet v4 | OpenStreetMap tiles |
| Data | In-memory (CSV/JSON/GTFS) | Loaded at startup |
| GTFS | BMTC Bengaluru GTFS (zip) | ~5077 stops, ~4359 routes, ~800K stop_times |
| LLM | OpenRouter (GPT-4o-mini, Gemini, Claude) | Live pricing, recs, news, chat |
| Geocoding | OSM Nominatim + Overpass API | Place search + nearby |
| OSRM | router.project-osrm.org (public, UNREACHABLE) | Driving/walking paths (fallback: interpolated) |
| Spatial Index | R-tree via rtree library | O(log n) nearby queries |

### 1.3 Project Structure

```
VOYAGER/
+-- backend/
�   +-- main.py              # FastAPI app, startup, middleware
�   +-- api/
�   �   +-- search.py        # /api/search/* endpoints
�   �   +-- routes.py        # /api/routes/* endpoints (706 lines)
�   +-- core/
�   �   +-- config.py        # Settings (paths, API keys, constants)
�   �   +-- database.py      # TransitDatabase singleton (300 lines)
�   �   +-- spatial_index.py # R-tree spatial index
�   +-- services/
�   �   +-- transit_service.py # Route planner (2234 lines)
�   �   +-- gtfs_service.py    # GTFS loader + query (591 lines)
�   �   +-- geocoding.py       # OSM geocoding
�   �   +-- n8n_service.py     # n8n webhook integration
�   +-- agents/
�       +-- llm_agent.py       # LLM orchestration
+-- frontend/src/
�   +-- App.tsx               # Root component (84 lines)
�   +-- pages/
�   �   +-- MainPage.tsx      # Orchestrator (313 lines)
�   �   +-- ...
�   +-- components/
�   �   +-- SegmentPanel.tsx  # Multi-column UI (KEY)
�   �   +-- MapView.tsx       # Leaflet map
�   �   +-- SearchPanel.tsx   # Place search
�   �   +-- ...
�   +-- types/index.ts        # All TypeScript types (286 lines)
�   +-- utils/helpers.ts      # Mode icons, labels, formatters (123 lines)
+-- data_cache/
�   +-- bmtc_gtfs.zip         # BMTC GTFS data
�   +-- bmtc_all_stops_master.csv
�   +-- bengaluru_metro_network.csv
�   +-- karnataka_railway_stations.json
�   +-- kia_routes_fare_full.json
�   +-- transit_fares.json
�   +-- processed/gtfs_cache.pkl  # ~69MB pickle
+-- AGENTS.md                 # Project summary
+-- docs/
    +-- VOYAGER_COMPLETE_DOCUMENTATION.md  # THIS FILE
```

## 2. ARCHITECTURE — FULL SYSTEM MAP

### 2.1 Request Flow: All-Segments (Main Feature)

User clicks "Show Routes" in AToBPanel
  → GET /api/routes/all-segments
  → routes.py:get_all_segments()
     │
     ├── transit_service.get_all_segments()
     │   ├── _build_single_segment(segment_index=0)  [from Source]
     │   │   ├── _add_direct_options()  → walk, cab, auto, bike (direct)
     │   │   ├── find_nearby_bus_stops(2km), metro(3km), rail(15km)
     │   │   ├── For each bus stop:
     │   │   │   ├── _add_reach_options()  → walk/cab/auto/bike to stop
     │   │   │   └── _add_transit_options()
     │   │   │       ├── Bus routes: direction check, stops by sequence, path, next_transit
     │   │   │       ├── Metro: line path, final_options
     │   │   │       └── Train: hardcoded data, final_options
     │   │   └── Filter: remove empty stops
     │   ├── Collect arrival points → build segments 1,2,... < max_depth
     │   └── Link segments via next_segment_index
     │
     ├── LLM live pricing (8s timeout)
     ├── OSRM paths (parallel, SKIPPED if OSRM unreachable)
     └── Interpolated path fallback

### 2.2 Data Structure: TransitOption (Recursive)

TransitOption extends SegmentStepOption {
  route_number?: string
  bus_times?: {departure_time, route}[]
  transit_type?: "bus" | "metro" | "train"
  final_options: SegmentStepOption[]      // last-mile from this stop
  next_transit?: TransitOption[]          // depth-2 and depth-3 hops
  next_segment_index?: number            // links to flat segment array
}

### 2.3 Column Growth (Frontend)

Loaded → Column 0: Direct
Click walk/cab → Column 1: Nearby Stops
Click reach option → Column 2: Transit Options
Click transit → Column 3: Next Transit (if available)
Click next transit → Column 4: Final Mile
(Each selection adds to transferChain array)

---

## 3. BACKEND: FastAPI Server

### 3.1 main.py (65 lines)

Events:
- startup: set test time → db.initialize() → _ensure_gtfs() (GTFS ~22-41s)

Routes:
- GET /: app info + metro/bus/kia counts
- GET /health: {"healthy", database_initialized}
- GET /api/n8n-status: n8n webhook availability

### 3.2 config.py (49 lines)

Settings from env/.env:
- DATA_CACHE_DIR: root/data_cache
- PROCESSED_DIR: root/data_cache/processed
- LLM_PROVIDER: "openrouter"
- OPENROUTER_API_KEY: from env
- OPENROUTER_MODEL: "openai/gpt-4o-mini"
- GEMINI_API_KEY: from env
- N8N_WEBHOOK_URL: from env
- OSRM_BASE_URL: https://router.project-osrm.org
- FUEL_PRICE_PER_LITER: 110.0
- PETROL_AVG_MILEAGE: 15.0

### 3.3 database.py (300 lines)

Class TransitDatabase (Singleton):
- _instance = None, __new__ ensures one instance
- initialize(): loads 5 data files, builds 3 spatial indexes

Metro Distance Cache:
- get_metro_distance_between(stn_a, stn_b): looks up pre-computed cumulative distances
- Build at init: for each line, sorted stations by sequence, compute cumulative distance between code pairs

Bus Stop Loading:
- Reads bmtc_all_stops_master.csv
- Parses "Routes with num trips" column (Python dict literal string → actual dict via ast.literal_eval)
- Stores in bus_stops dict by index

SpatialIndex class:
- Uses rtree library (libspatialindex)
- build(items): inserts all items with (lat, lng) bounding boxes
- query(lat, lng, radius_km, max_results): returns items within radius sorted by distance

### 3.4 spatial_index.py

R-tree wrapper for finding nearby stops/stations in O(log n):
- build(items): expects each item to have "lat", "lng" keys
- query(lat, lng, radius_km, max_results):
  - Convert radius to degrees (1 deg ≈ 111km)
  - Use rtree intersection search
  - Filter by actual haversine distance
  - Sort by distance, return top max_results

---

## 4. FRONTEND: React + Vite + TypeScript

### 4.1 App.tsx (84 lines)

State: mode, selectedPlace, mapCenter, userLocation, sourceLocation, destLocation, allMarkers, mapRef
Handlers: handleSelectPlace (flyTo), handleModeChange, handleNavigateToPlace (set source=user, dest=place)

### 4.2 MainPage.tsx (313 lines) — Orchestrator

State:
- segmentPanelOpen, segmentSourceName, segmentDestName, segmentGroupSize, segmentBudget
- segmentGeometry, liveTrackingPos, trackingActive
- discoveryPlace, showDiscovery, searchResults, nearbyResults
- routeGeometry, newsItems, mapWaypoints

Key feature handlers:
- handleOpenSegmentPanel: opens panel, resets geometry, setTimeout invalidateSize
- handleCloseSegmentPanel: clears geometry + GPS, setTimeout invalidateSize
- handleStartJourney: navigator.geolocation.watchPosition → liveTrackingPos
- handleSegmentGeometry: passes geo array from SegmentPanel to MapView

### 4.3 helpers.ts (123 lines)

Functions:
- getModeIcon(mode): emoji map for 25+ modes (walk 🚶, bus 🚌, metro 🚇, cab 🚕, train 🚆)
- getModeLabel(mode): human labels ("Bus → Metro", "BMTC AC Vajra")
- getPlaceIcon(placeType, isRecommended): shopping 🛍️, hospital 🏥, etc.
- formatDuration(minutes): "2h 30m"
- formatRupees(amount): "₹150.00"
- getScoreColor(score): green ≥80, yellow ≥60, orange ≥40, red <40
- getScoreLabel(score): Excellent/Good/Fair/Poor/Avoid
- getPinColor(isRecommended, score?): green vs red for map pins


## 5. GTFS BUS INTEGRATION — DETAILED (gtfs_service.py, 591 lines)

### 5.1 GTFSLoader Class

Constructor: initializes empty dicts for shapes, route_shapes, stop_to_shapes, stops_by_name, stop_times, stop_times_by_route, name_map, all_gtfs_names, loaded=False.

### 5.2 Name Resolution: _resolve_name (6-stage fuzzy matcher)

```
Input: "K.R. Market" (from DB CSV)
  Stage 1: key = "k.r. market".lower().strip() → check _stop_times → FAIL (keys are lowercase GTFS)
  Stage 2: check _name_map cache → may fail (first call)
  Stage 3: _fuzzy_match(key, _all_gtfs_names, cutoff=0.55)
           → Normalizes both: _normalize("k.r. market") = "kr market"
           → _normalize("k r market") = "kr market"
           → SequenceMatcher ratio = 1.0 → MATCH
           → Returns "k r market" (the GTFS key)
  Stage 4-6: never reached if fuzzy match succeeded
```

The _normalize function:
```
def _normalize(name):
    n = name.lower().strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)  # Remove punctuation
    n = re.sub(r'\s+', ' ', n)           # Collapse whitespace
    return n.strip()
```

Critical: _fuzzy_match has substring bonus: if query in candidate or candidate in query, score = max(score, 0.9). This causes "hennur" to match "hennur cross" with score 0.9.

### 5.3 _fuzzy_match function

```
def _fuzzy_match(query, candidates, cutoff=0.55):
    q = _normalize(query)
    for c in candidates:
        cn = _normalize(c)
        score = max(SequenceMatcher(None, q, cn).ratio(),
                    SequenceMatcher(None, cn, q).ratio())
        if q in cn or cn in q:
            score = max(score, 0.9)
        if score > best_score: ...
    return best if best_score >= cutoff else None
```

### 5.4 get_shape_between_stops (CRITICAL for map paths)

```
Input: from_name="K.R. Market", to_name="K R MARKET" (resolved)
  1. f_resolved = _resolve_name("K.R. Market") → "k r market"
  2. t_resolved = _resolve_name("K R MARKET") → "k r market" (same)
  3. fk = "k r market", tk = "k r market"
  4. f_stop = _stop_to_shapes["k r market"] → [(shape_id_1, seq_5), (shape_id_2, seq_12)]
  5. t_stop = _stop_to_shapes["k r market"] → [(shape_id_1, seq_40), (shape_id_3, seq_8)]
  6. common = {shape_id_1} (intersection)
  7. For shape_id_1: f_seq=5, t_seq=40
  8. Slice shapes[shape_id_1][4:40] (start = min(5,40)-1 = 4, end = max(5,40) = 40)
  9. Return segment
```

### 5.5 find_stops_on_route_toward_dest (FIXED July 2026)

Before fix: used Euclidean distance to find closest-by-air stops to destination
  → Wrong: returned Krishnarajpuram when Hennur was the actual next stop on the route

After fix (July 2026): uses GTFS shape sequence ordering:
  1. Find the source stop (closest GTFS stop on route to input coords)
  2. Get shape sequence numbers from _stop_to_shapes for source stop
  3. For each other stop on the route, check if it shares a common shape with source
  4. If shared shape found, check if candidate stop's sequence > source stop's sequence
  5. Sort candidates by sequence number → actual stop order
  6. Return up to max_stops that come AFTER the source stop in the route

Fallback: _find_stops_euclidean_fallback — uses old Euclidean method when shape data unavailable

### 5.6 Cache System

Cache stored at data_cache/processed/gtfs_cache.pkl (~69MB)
- Contains: shapes, route_shapes, stop_to_shapes, stops_by_name, stop_times, stop_times_by_route, name_map
- Invalidated when GTFS zip modification time > cache modification time
- Manual invalidation: delete the pickle file (forces full reload ~41s)

### 5.7 Known Cache Issue (FIXED July 2026)

_stop_to_shapes was built with keys in GTFS original case (e.g., "K R MARKET" uppercase)
But get_shape_between_stops looked up with .lower().strip() → never matched!
Fix: store keys lowercase in _stop_to_shapes, and resolve names via _resolve_name first in get_shape_between_stops

---

## 6. ROUTE PLANNING ENGINE (transit_service.py, 2234 lines)

### 6.1 TransitService Class

Constructor: self._path_cache = {} (OSRM path cache keyed by coords+profile tuple)

### 6.2 Module-level Functions

_ensure_gtfs(): lazy-loads GTFSLoader singleton (global _gtfs)

_route_goes_toward_dest(shape_path, stop_lat, stop_lng, dest_lat, dest_lng):
  1. Find closest shape point to stop location (Euclidean distance in coordinate space)
  2. If closest point is near shape end, return False (route terminates here)
  3. Compute direction vector from closest point to 3 points ahead
  4. Compute direction vector from stop to destination
  5. Compute cosine of angle between vectors
  6. Return cos_angle >= 0.26 (angle ≤ 75°) — TIGHTENED from -0.1 (96°) in July 2026

_gtfs_buses_at_stop(stop_name): returns GTFS routes with timings
_has_gtfs_route(stop_name): checks if GTFS data exists for stop

_get_train_options(src_name, dst_name):
  - Normalizes 15+ station name variants (KSR Bengaluru, Yesvantpur, Mysuru, etc.)
  - Looks up _TRAIN_DATA hardcoded dict for known pairs
  - Only returns known routes (no synthetic fallback)

### 6.3 Route Generators (Legacy System, used by POST /api/routes/plan)

_get_route_legs_public → generates route options combining:
1. _generate_bus_routes: walk→bus→walk (uses nearby bus stops + common routes)
2. _generate_metro_routes: walk→metro→walk (uses nearby metro stations)
3. _generate_metro_interchange_routes: walk→metro→interchange→metro→walk
4. _generate_kia_routes: walk→KIA bus→walk
5. _generate_multi_modal_routes: bus→metro, metro→bus combos

Each generator returns routes with legs[], scored via _topsis_score.

### 6.4 TOPSIS Scoring (_topsis_score)

fare × 25% + time × 30% + walk × 15% + comfort × 20% + bonuses
Bonuses: under-budget (+5 to +10), group size cheap pp (+5), metro (+5), known routes (+3)
Penalties: over-budget (-5 to -15)
Final: max(10, min(99, score))

### 6.5 OSRM Path Fetching

get_osrm_path_between(slat, slng, dlat, dlng, profile):
  - Async HTTP call to OSRM public server (2s timeout)
  - Caches results in _path_cache by (rounded_coords, profile) tuple
  - Falls back to _interpolate_path on failure

_leg_paths enrichment:
  - Metro legs: use db.get_metro_line_path (instant)
  - Bus legs: use _gtfs.get_shape_between_stops (instant)
  - Walk/drive: OSRM async batch (30s timeout)

_interpolate_path(slat, slng, dlat, dlng, num_points=12):
  - Linear interpolation between start and end (great-circle approximation)
  - Used as fallback when OSRM unavailable

### 6.6 get_segment_step_options (Legacy single-segment, not used by new UI)

User: AToBPanel calls this for the "quick route" view (not the main segment UI).
Returns: direct_options + via_stops (each with reach + from_stop_options)
Used by: GET /api/routes/segment-step (deprecated, but kept for backward compat)

### 6.7 get_mini_path_options (Quick transit overview)

Returns source_walk_options, direct_ride_options, source_to_transit (bus/metro), transit_ride_options, transit_to_dest (bus/metro).
Used by: GET /api/routes/mini-path-options (legacy, still functional)

---

## 7. SEGMENT PANEL SYSTEM — THE CORE FEATURE

### 7.1 get_all_segments (Entry Point)

```
def get_all_segments(from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, 
                     group_size=1, budget=None, max_depth=3):
```

Algorithm:
1. Build segment 0 from Source (direct + nearby stops + transit)
2. Scan all transit options in segment 0, collect unique arrival coordinates (to_lat, to_lng)
3. For each unique arrival point, build segment 1 (same structure, but FROM arrival)
4. Link: set next_segment_index on each transit option pointing to its segment
5. Repeat depth 2, 3... until max_depth or no new arrival points
6. Return flat array of segments

### 7.2 _build_single_segment

Builds one segment from {from} location toward {dest}:

1. _add_direct_options: walk (≤5km), bike (1-2km), auto/cab (≥2km), cab_xl (≥2km, group ≤6)
2. Find nearby bus stops (2km radius), metro stations (3km), railway stations (15km)
3. For each bus stop (max 8):
   - Skip if no GTFS data and stop > 2km from source
   - Skip if stop is FARTHER from dest than source (stop_to_dest > current_to_dest × 1.5 AND dist > 1km)
   - _add_reach_options: walk (≤2km), bike (1-2km), auto/cab (≥1km) from Source to stop
   - _add_transit_options: buses, metro, train FROM this stop
4. For each metro station (max 4):
   - Same structure
5. For each railway station (max 3, only if outside Bengaluru):
   - Same structure
6. Filter: remove destinations with no reach AND no transit options
7. Add interpolated paths to all options

### 7.3 _add_transit_options (THE KEY METHOD ~260 lines)

Input: entry dict with stop info, plus all routing params

Process:
1. For bus/metro stops: get GTFS routes at this stop (max 8 routes)
2. For each route:
   a. Get shape path → check _route_goes_toward_dest (TIGHTENED to 75°)
   b. find_stops_on_route_toward_dest (NOW uses shape sequence ordering)
   c. Get first arrival stop → t_lat, t_lng, arrival_name
   d. get_shape_between_stops(sname, arrival_name) → path segment
   e. Calculate fare, duration
   f. _build_next_transit → recursive bus/metro transfers at arrival
   g. Build TransitOption dict with all fields + next_transit
   h. AC Vajra variant (higher fare, slightly faster)

3. KIA buses: check if stop is on KIA route → next KIA stops + fare

4. Metro: for each destination metro station, get_line_path, calculate fare

5. Train: for destination railway station, get_train_options, calculate fare+duration

6. FINAL MILE (added to each TransitOption):
   - Walk if dropoff distance ≤ 2km
   - Bus final mile: find routes at dropoff going toward dest (via find_stops_on_route_toward_dest)
   - Ride options: cab/auto/bike if ≥1km and no budget-friendly bus final

### 7.4 _build_next_transit (RECURSIVE transfer chaining)

Input: t_lat, t_lng (arrival point), exclude_name (skip this stop), dest params, depth (remaining hops)

Process:
1. If dropoff_dist ≤ 1.5km, return empty (no transfers needed)
2. Track visited stops to prevent circular routing
3. Bus transfers:
   - Find nearby bus stops at arrival (0.5km radius, max 4)
   - For each, get routes (max 4 per stop)
   - _is_hub_or_toward_dest: check direction OR if route goes through major hub
   - find_stops_on_route_toward_dest for next stops
   - Must make progress toward dest (distance decrease ≥ 0.2km) OR go to major hub
   - Build final_options (walk, bus final, rides)
   - Recursive: if depth > 1 AND nt2_dist > 1.5km, call _build_next_transit again
4. Metro transfers:
   - Find nearby metro at arrival (1.5km, max 2)
   - For each, find station on SAME LINE closest to destination
   - Build metro transit option with path, final_options
5. Return list of TransitOption for next hop

MAJOR_HUBS list for relaxed direction filtering:
majestic, kempegowda bus station, kr market, kbs, shivajinagara, shivajinagar, 
banashankari, jayanagara, k.r. market, city market, platform 10-14

### 7.5 Direction Filtering Decision Tree

```
_add_transit_options bus loop:
  get shape_path_for_route
  if shape_path and NOT _route_goes_toward_dest(shape, stop_lat/lng, dest_lat/lng):
      SKIP this route (angle > 75° away from dest)

_build_next_transit bus loop:
  get shape_path2 for route
  if shape_path2 and NOT _is_hub_or_toward_dest(shape, abs_lat/lng, dest_lat/lng, route_name):
      SKIP (unless route goes to a major hub)
  
_is_hub_or_toward_dest:
  if shape is None/<2 points: ACCEPT (no data to judge)
  if _route_goes_toward_dest: ACCEPT
  if route has major hub stop (checked via get_route_stops): ACCEPT
  else: REJECT
```

### 7.6 Important: _is_hub_or_toward_dest was IMPROVED July 2026
Previously returned False for the hub check (only checked direction). 
Now calls _gtfs.get_route_stops(route_name, limit=50) and checks for hub names.
This allows buses going toward Majestic/KR Market even if not directly toward destination.

---

## 8. METRO SYSTEM — DETAILED

### 8.1 Metro Data

Source: bengaluru_metro_network.csv
Lines: Purple (Kengeri→Whitefield) and Green (Nagasandra→Silk Institute)
Stations: ~50+ stations with sequence numbers, GPS coordinates, interchange flags
Interchange: Majestic (appears in both lines at seq=23 for Purple, seq=17 for Green)

### 8.2 Metro Line Path

get_metro_line_path(from_name, to_name):
  1. Find stations with matching names across all lines
  2. Match by same line + same line in metro_lines dict
  3. Get station sequences for both on matched line
  4. Iterate line_stations between from_seq and to_seq
  5. Return [lat,lng] array for map path

### 8.3 Metro Fare

Slab-based from transit_fares.json namma_metro_slabs:
  ≤2km: ₹10, ≤4km: ₹15, ≤6km: ₹20, ≤10km: ₹25, ≤20km: ₹35, ≤30km: ₹45, etc.

### 8.4 Metro in Transit Options

In _add_transit_options (line 1525-1554):
  - Stop must be type "metro"
  - Metro must be operating (5:00-23:00)
  - For each dest_nearby_metro (max 4):
    - Must have valid metro_line_path (same line check)
    - Add transit option with path from metro_line_path
    - next_transit = [] (metro doesn't chain to more metro automatically)

In _build_next_transit (line 1804-1890):
  - Find nearby metro at arrival (1.5km)
  - For each, find best_dm (station on same line closest to destination)
  - Build metro transit option with final_options (walk, bus, rides)
  - next_transit = [] (terminal)

### 8.5 Metro Known Limitations

- Only Purple and Green lines (no Yellow, Pink, Blue lines added yet)
- Majestic interchange: metro→metro transfer is not explicitly modeled
- No train→metro integration at stations like KSR Bengaluru Railway Station→Majestic (need to add)
- Timings: only 5AM-11PM check, no actual schedule


## 9. TRAIN SYSTEM — DETAILED

### 9.1 Train Data

Hardcoded in _TRAIN_DATA dict at top of transit_service.py:
- Bengaluru↔Mysuru: 5 trains (Kannada Express, 2 Shatabdi, Gol Gumbaz, Mysuru Express)
- Bengaluru↔Hubballi: 2 trains (Vishwamanava, Rani Chennamma)
- Bengaluru↔Mangaluru: 2 trains (Kannur Express, Mokashi)
- Bengaluru↔Belagavi: 1 train (Basava Express)
- Bengaluru↔Ballari: 1 train

### 9.2 Name Normalization

_get_train_options normalizes 15+ name variants:
- "ksr bengaluru", "bengaluru city", "yasvantpur", "whitefield", "krishnarajapuram" → "bengaluru"
- "mysuru", "mysore" → "mysuru"
- "hubballi", "hubli" → "hubballi"
- "mangaluru", "mangalore" → "mangaluru"
- etc.

### 9.3 Train in Segments

Only shown when:
- stop type = "railway"
- destination has nearby railway station (30km radius)
- is_long_dist = outside Bengaluru (>35km from center) OR direct distance > 40km

Fare: max(15, round(distance × 0.8)) per person (generic estimate)
Duration: calculated from departure/arrival time strings, fallback = distance × 1.2

### 9.4 Known Train Limitations

- No real-time data (hardcoded schedules, no IRCTC integration)
- Limited city pairs (no Bengaluru→Chennai, Bengaluru→Hyderabad, etc.)
- No intra-city train routes (Bengaluru suburban rail / MEMU not included)
- No train→metro integration (e.g., arrive KSR Station → walk to Majestic Metro)
- No train→bus integration at stations
- Fare is a rough estimate (₹0.8/km generic)

---

## 10. RIDE PRICING

### 10.1 Built-in Fare Calculator

Ride types in transit_service.py ride_types list:
```
(cab, "Uber Go / Ola Mini", 14/km, 3min/km, 25 base, 🚕, 4 people)
(cab_xl, "Uber XL / Ola XL", 20/km, 3min/km, 40 base, 🚐, 6)
(auto, "Auto", 10/km, 5min/km, 15 base, 🛺, 3)
(bike, "Uber Moto / Rapido", 6/km, 2min/km, 10 base, 🏍️, 1)
```

Formula: fare = base + distance × per_km_rate (per person)
Group filter: skip if group_size > capacity

### 10.2 LLM Live Pricing

In all-segments endpoint:
1. Async task fires llm_agent.get_live_prices(source_name, dest_name) with 8s timeout
2. Returns overlay prices for cab, cab_xl, auto, bike modes
3. Applied to direct_options and reach_options in all segments
4. Overrides built-in fare when LLM returns a price

### 10.3 Smart Distance Filtering for Rides

In _add_direct_options and _add_reach_options:
- < 1km: no rides (only walk)
- 1-2km: only bike + walk
- ≥ 2km: all ride types

---

## 11. LLM AGENT SYSTEM (llm_agent.py)

### 11.1 LLMService Class

Provider: OpenRouter (default model: openai/gpt-4o-mini)
Fallback models: gpt-3.5-turbo, claude-3-haiku, llama-3-8b, gemini-1.5-flash, mistral-7b

### 11.2 Functions

get_live_prices(source, destination, mode=None):
  - System prompt describes Bengaluru ride prices (cab ₹100-250 base, auto ₹50-100, etc.)
  - Returns structured price data with provider name, price, eta, mode
  - 8s timeout on all-segments endpoint

get_weather_impact():
  - Returns current weather + travel impact (rainy? night?)
  - Used for route scoring adjustments

get_travel_recs(source, dest, group_size, budget):
  - Returns travel recommendations specific to the route

get_travel_news(source, dest):
  - Returns news items relevant to the route area

chat_response(message, context):
  - General AI chat for the search panel

get_current_events(location):
  - Returns current events at a location

### 11.3 Live Pricing Data Flow

```
GET /api/routes/all-segments
  → OSRM health check
  → LLM live pricing async task (8s timeout)
  → Build segments (synchronous)
  → OSRM paths (parallel, SKIPPED if unreachable)
  → Await LLM task
  → Apply prices: walk through all direct + reach options, match by mode
  → Override fare, per_person, add live_provider, live_eta
  → Interpolated paths fallback
  → Return response
```

---

## 12. MULTI-HOP TRANSFER CHAINING — COMPLETE FLOW

### 12.1 What It Does

When a bus drops you at a stop that is still far from destination, the system finds:
1. Another bus from that stop going closer to destination (bus→bus)
2. A metro from a nearby station going toward destination (bus→metro)
3. A third bus from that second stop (bus→bus→bus) — depth 3
4. Final mile from the last stop (walk/bus/cab/auto/bike)

### 12.2 Implementation: Recursive _build_next_transit

```
_build_next_transit(t_lat, t_lng, exclude_name, dest_lat, dest_lng, dest_name,
                    group_size, budget, dest_nearby_metro, ride_types, depth=2, visited_stops=None)
```

Conditions for showing transfers:
- dropoff_dist > 1.5km (otherwise just walk to dest)
- Not in visited_stops (prevents circular routing)

Bus-to-bus chain:
1. Find nearby bus stops at arrival (0.5km)
2. For each stop: get GTFS routes
3. Filter by direction (toward dest OR via major hub)
4. Find next stops on route toward dest
5. Distance progress check: nt2_dist < dropoff_dist - 0.2 (must get at least 200m closer)
6. Build final_options for this hop
7. If depth > 1 and still far: recurse

Metro chain:
1. Find nearby metro stations at arrival (1.5km)
2. For each station: find same-line station closest to destination
3. Build metro option with path + final_options
4. No deeper recursion (next_transit = [])

### 12.3 Frontend Rendering

transferChain array:
- Updated when user clicks a transit option
- Pushes the selected option to chain
- Shows TransferColumnContent for each level

Hover handlers:
- onHover(option) → setHoveredTransferPath(option.path) → MapView shows red line
- onLeave() → clear hovered path

### 12.4 Known Transfer Issues

1. Too many irrelevant bus options at intermediate stops
2. Some transfers show stops going backward from destination
3. Circular routing not fully prevented (visited_stops only tracks exact names)
4. Metro transfers don't chain to more buses after metro
5. Bus-to-bus at same stop not shown (only looks within 0.5km)

---

## 13. MAP & PATH RENDERING

### 13.1 Path Sources

| Mode | Path Source | Priority |
|------|-----------|----------|
| Walk | Interpolated (linear) | Always interpolated |
| Bus ordinary/AC | GTFS get_shape_between_stops | 1st: stop-to-stop shape, 2nd: full route shape, 3rd: interpolated |
| Metro | get_metro_line_path | Station-to-station along line |
| Train | Interpolated | Always interpolated |
| Cab/Auto/Bike | OSRM → Interpolated fallback | OSRM (currently unreachable) |
| Car | OSRM → Interpolated | OSRM (currently unreachable) |

### 13.2 OSRM Integration

OSRM health check at the start of all-segments:
```
GET https://router.project-osrm.org/route/v1/driving/77.6,12.97;77.57,12.97?overview=false
→ returns 200 if server is up
→ Currently FAILS (server unreachable from this network)
```

When OSRM is down:
- All cab/auto/bike paths use straight-line interpolation
- No road-following paths
- Map shows direct lines instead of actual road routes

### 13.3 Path Data in Response

Each SegmentStepOption includes:
```
path: [[lat, lng], [lat, lng], ...]  // array of coordinate pairs
```

Path precision: 6 decimal places (via _interpolate_path)
Interpolation: 12 points by default (can be overridden via num_points)

### 13.4 Frontend Map Rendering

MapRouteGeometry type:
```
{ type: "route" | "segment" | "hover" | "stop", 
  coordinates: [lat, lng][],
  color: string,
  weight?: number,
  dashArray?: string,
  label?: string }
```

Colors:
- route: blue (#3b82f6)
- segment: orange (#f97316) 
- hover: red (#ef4444) with weight 5
- stop: green (#22c55e)

Selection flow:
1. User hovers option → onHover(path) → setHoveredTransferPath
2. MapView renders red thick line
3. User clicks → adds to route geometry (permanent orange/blue)
4. User leaves → clears red line

---

## 14. TRAFFIC SYSTEM

### 14.1 Traffic Overlay

Endpoint: GET /api/routes/traffic-overlay?north=...&south=...&east=...&west=...

Loads bangalore_roads.geojson from data/ directory
Filters roads by bounding box
Colors by congestion level:
- heavy (<15 km/h): red #e74c3c
- moderate (15-30 km/h): orange #f39c12
- light (>30 km/h): green #2ecc71

Congestion detection:
- Peak hours (8-10am, 5-8pm): heavy
- Off-peak: light

### 14.2 Traffic Data Source

traffic_logs.csv in data_cache/:
- Contains step_time and live_speed_mps columns
- Loaded on demand, cached for 60 seconds
- Average speed calculated across all entries

### 14.3 Known Traffic Issues

- No real-time traffic API integration (Google Maps / Mapbox)
- GeoJSON road data may be outdated
- Speed data from CSV may not reflect actual conditions

---

## 15. PERFORMANCE ANALYSIS

### 15.1 Startup Performance

| Phase | Time | Notes |
|-------|------|-------|
| Database init | ~1s | 5 files, 3 R-tree indexes |
| GTFS from cache | ~22s | 69MB pickle deserialization |
| GTFS fresh load | ~41s | ZIP parsing, ~800K stop_times rows |

### 15.2 API Response Time

| Endpoint | Time | Notes |
|----------|------|-------|
| GET /all-segments max_depth=1 | ~3-5s | Mostly SQL/sync CPU work |
| GET /all-segments max_depth=3 | ~8-15s | More stops to process |
| GET /plan | ~3-8s | Route generation + OSRM paths |
| GET /mini-path-options | ~0.5-1s | Simple nearby queries |

### 15.3 Bottlenecks

1. GTFS name resolution (fuzzy matching) — O(n × m) for each stop
2. Shape direction checks — iterating shape points for each route
3. Route stop discovery — iterating all stop_times entries
4. Cache deserialization — 69MB pickle is slow to load
5. OSRM unreachable — all paths fall back to interpolation

### 15.4 Optimization Suggestions

1. Trie index for GTFS name resolution (instead of linear scan)
2. Pre-compute direction vectors for shape segments
3. Remove 100K limit on stop_times (currently limits to 200/stop, 500/route)
4. Lazy loading: only load GTFS when first route request comes in
5. Cache frequently requested routes in memory

---

## 16. KNOWN BUGS & ISSUES

### 16.1 Current Bugs (July 2026)

1. **Segment path not showing correct bus route (FIXED)**
   - Root cause: find_stops_on_route_toward_dest used Euclidean distance instead of stop sequence
   - Result: showed Krishnarajpuram when Hennur was actual next stop
   - Fix: Rewrote to use GTFS shape sequence ordering (July 2026)
   - Status: VERIFICATION NEEDED

2. **Stop name resolution fails for maps (FIXED)**
   - Root cause: _stop_to_shapes keys were uppercase, lookups were lowercase → never matched
   - Result: get_shape_between_stops returned None → path fell back to full shape
   - Fix: Store lowercase keys + resolve names via _resolve_name before lookup (July 2026)
   - Status: VERIFICATION NEEDED

3. **Direction filter too permissive (FIXED)**
   - Root cause: cos_angle >= -0.1 allowed 96° deviation from destination
   - Fix: Changed to cos_angle >= 0.26 (75° max deviation)
   - Status: Applied

4. **OSRM unreachable**
   - Public OSRM server not accessible from current network
   - All cab/auto/bike paths show straight-line interpolated routes
   - Workaround: none without alternative OSRM server

5. **Stop coordinates mismatch between CSV and GTFS**
   - Dual data source: bus stops CSV has coordinates, GTFS has separate coordinates
   - Same stop name can appear at different locations
   - Affects map display (stop marker at CSV coord, path starts from GTFS coord)

6. **Too many bus options at intermediate stops**
   - _build_next_transit shows many buses without sufficient filtering
   - Need to rank by relevance (closer to dest, fewer transfers, lower cost)

### 16.2 Known Issues Not Yet Fixed

1. Metro→bus→bus chaining: metro next_transit has no further bus transfers
2. Train final mile shows cab but not bus from railway station
3. KIA buses don't have shape paths
4. Railway stations far from actual stop location (30km radius is too large)
5. No direction check for metro (always shows both directions)
6. Bus final mile sometimes suggests same bus going backward
7. Multiple Ittige Factory entries at different coordinates (data quality issue)
8. GTFS cache doesn't auto-invalidate when code changes (need manual delete)
9. Circular routing: visited_stops only tracks by stop name, not by coordinates
10. No trip duration validation (bus duration = dist×4 is too simplistic)

---

## 17. BUG FIX LOG

### July 16, 2026 — Major Bug Fixes

**Fix 1: find_stops_on_route_toward_dest — Sequence-based ordering**
- Scope: gtfs_service.py lines 475-575
- Old: Sort stops by Euclidean distance to destination → wrong stop order
  Example: Bus route goes Source→Hennur→KR Puram. Destination is south of KR Puram.
  KR Puram is closer to dest by air → returned even though it comes after Hennur.
- New: Use GTFS shape sequence ordering
  1. Find source stop on route (closest by coordinates)
  2. Get shape IDs + sequence numbers from _stop_to_shapes
  3. For each other stop: find shared shape, compare sequences
  4. Only return stops with seq > source_seq (come AFTER in route)
  5. Sort by sequence number → actual bus stop order
- Fallback: Euclidean method preserved if shape data unavailable

**Fix 2: _stop_to_shapes key case sensitivity**
- Scope: gtfs_service.py lines 217-224, 283-292
- Old: Storage used GTFS original-case keys, lookups used .lower() → never matched
- Fix: Store keys as sname.strip().lower() in _stop_to_shapes
- Fix: get_shape_between_stops now resolves names via _resolve_name first, then lowercases

**Fix 3: _route_goes_toward_dest angle threshold**
- Scope: transit_service.py line 150
- Old: cos_angle >= -0.1 (accepts up to ~96° away from dest)
- New: cos_angle >= 0.26 (max 75° deviation)

**Fix 4: _is_hub_or_toward_dest — Major hub detection**
- Scope: transit_service.py lines 1669-1683
- Old: hub check was stub (returned False), only direction check worked
- New: Actually checks if route stops contain major hub names via get_route_stops
- Accepts routes going toward Majestic/KR Market/Shivajinagar etc.


## 18. NEXT FEATURES TO BUILD — PRIORITY ORDERED

### P0 — Critical Fixes (Must Fix First)

1. **Fix OSRM / Add alternative routing**
   - Self-host OSRM locally (docker: osrm-backend with Bengaluru OSM extract)
   - Or use free-tier Mapbox/GraphHopper API
   - Without OSRM, all ride paths are straight-line interpolation (ugly + inaccurate)
   - Implementation: `docker run -p 5000:5000 osrm/osrm-backend` with Bengaluru extract

2. **Dual-data-source coordinate consistency**
   - Problem: bus stop CSV and GTFS can have different coordinates for same stop
   - Fix: Use GTFS coordinates as canonical source, fall back to CSV
   - In find_stop_by_name and find_nearby_bus_stops, cross-reference GTFS coordinates

3. **Direction check for metro**
   - Metro options show BOTH directions (toward destination AND away)
   - Need to check which station on the line is closer to destination, show only that direction
   - Compare destination distance from each endpoint of the line

### P1 — Major Feature Improvements

4. **Add more metro lines (Yellow, Pink, Blue)**
   - Yellow Line: RV Road→Bommasandra (under construction/opening)
   - Pink Line: Nagawara→Kalena Agrahara (under construction)
   - Blue Line: KIAL Airport line
   - Need updated metro_network.csv with new stations

5. **Multi-modal transfers: train→metro, train→bus**
   - At KSR Bengaluru Railway Station: show walk to Majestic Metro
   - At Yesvantpur: show walk to Yesvantpur Metro/Majestic
   - At Krishnarajapuram: show KR Puram Metro connection
   - Implementation: check if railway station coords are near metro-station coords

6. **Bus→bus at same stop (platform transfer)**
   - Current: only looks for stops within 0.5km for transfers
   - Need: also check if the SAME stop has other routes toward destination
   - This could catch express buses vs ordinary buses at same stop

7. **Route scoring for segment options**
   - Current: no scoring for transit options in segment UI
   - Need TOPSIS-like scoring for each TransitOption: fare, duration, transfers count, walking

8. **Real bus travel times from GTFS**
   - Current: duration = distance × 4 (simple estimate)
   - Better: calculate from GTFS stop_times arrival/departure differences
   - Average travel time between two stops across multiple trips

### P2 — Important Features

9. **Intermediate stop filtering for relevance**
   - Many bus options at intermediate stops are irrelevant (wrong direction, too short distance)
   - Rank by: distance progress toward dest, travel time savings, cost
   - Remove options that go backward from destination

10. **Train→Train transfers for inter-city**
    - E.g., Bengaluru→Mysuru→Mangaluru multi-hop train route
    - Need to chain train segments when no direct train exists

11. **User location GPS for segment source**
    - When user clicks "Start Journey", use GPS position as segment 0 source
    - Current: GPS tracking shows marker but segments still use original source

12. **Search/select specific bus stop by name**
    - Current: only shows nearby stops from spatial index (bubbles up nearest)
    - Need: type-ahead search for any stop name from GTFS (5077 stops)

13. **Show bus route on map when hovered**
    - Full route shape (not just segment) when hovering a bus option
    - Helps user understand where the bus goes

14. **Expand GTFS data to full dataset**
    - Current: limits 200 departure times per stop, 500 per route
    - Some stops/routes have more data than this limit
    - Need to increase or remove limits (memory tradeoff)

### P3 — Polish & UX

15. **Better error messages for no routes**
    - "No bus routes available from this stop at this time"
    - "Metro not operating (5AM-11PM only)"

16. **Departure time display**
    - Show next 3 departure times for each bus option
    - Allow user to select departure time preference

17. **Walking isochrones for stops**
    - Show which areas are walkable from each stop
    - Helps user decide whether to walk to a different stop

18. **Fare breakdown display**
    - Show fare per segment and total
    - Per-person fare clearly displayed

19. **Mobile responsive UI**
    - Multi-column panel needs to collapse on mobile
    - Use swipe/scroll for columns

20. **Accessibility**
    - Screen reader support
    - High contrast mode
    - Keyboard navigation for column selection

### P4 — Stretch Goals

21. **Real-time bus tracking (OTS/BMTC API)**
    - Integrate with BMTC's real-time vehicle tracking (if available)
    - Show actual bus positions on map

22. **Crowdsourcing: user-reported delays/closures**
    - Allow users to report delays, route changes, accidents
    - Feed into route scoring

23. **Multi-city support**
    - Abstract Bengaluru-specific data to support other cities
    - Start with Mysuru, Hubballi, then pan-India

24. **Offline mode**
    - Cache GTFS data locally on PWA
    - Use cached data for route planning without internet

25. **Trip history and favorites**
    - Save frequently used routes
    - Show commute time predictions based on history

---

## 19. FUTURE IMPROVEMENTS — DETAILED SPECS

### 19.1 OSRM Self-Hosting

Steps:
```
# Download Bengaluru OSM extract
wget https://download.geofabrik.de/asia/india/karnataka-latest.osm.pbf

# Extract Bengaluru region
osmium extract -b 77.40,12.80,77.80,13.20 karnataka-latest.osm.pbf -o bengaluru.osm.pbf

# Build OSRM routing engine
docker run -t -v ${PWD}:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/bengaluru.osm.pbf
docker run -t -v ${PWD}:/data osrm/osrm-backend osrm-partition /data/bengaluru.osrm
docker run -t -v ${PWD}:/data osrm/osrm-backend osrm-customize /data/bengaluru.osrm

# Serve OSRM
docker run -t -i -p 5000:5000 -v ${PWD}:/data osrm/osrm-backend osrm-routed --algorithm mld /data/bengaluru.osrm
```

Update config.py: OSRM_BASE_URL = "http://localhost:5000"
Benefits: real road-following paths, accurate distance/duration, walking routes on footpaths

### 19.2 Metro Line Expansion

Need to add to bengaluru_metro_network.csv:
- Yellow Line: RV Road→Ragigudda→JP Nagar→Bommasandra (18 stations)
- Pink Line: Nagawara→Tannery Road→Tavarekere (13 stations)
- Blue Line: KR Puram→KIA Airport→ (under construction)

For each new line: station names, codes, GPS coordinates, sequence numbers, distances, interchange flags

Code changes: none (database.py reads the CSV generically, metro section in transit_service also generic)

### 19.3 KIA Bus Shape Paths

Current: KIA buses have no shape paths → no map display
Need to add shape data for airport bus routes (or use interpolated as fallback)

### 19.4 Train Schedule Expansion

Current: 5 city pairs with hardcoded schedules
Need to expand to all Karnataka pairs and eventually all-India
Options:
- Scrape IRCTC (not reliable)
- Use third-party API (IRCTC API costs ~₹1/request)
- Use Wikipedia/indiarailinfo for static schedules
- Implement as a separate static dataset (JSON) for all major routes

---

## 20. DEPLOYMENT OPTIONS

### 20.1 Local Only (Current)

- Best option given no credit card
- i7-1165G7, 4 cores, NVMe SSD
- Cold start: ~45s (database + GTFS)
- Can serve family/friends on local network

### 20.2 Render Free Tier

- No credit card required for Render free tier
- 512MB RAM, 0.1 CPU
- Cold start: ~60s (GTFS loading)
- Sleeps after 15 minutes of inactivity
- Next request: cold start again
- Works for demo but not practical

### 20.3 Oracle Cloud Free Tier

- Requires credit card for signup (even for free tier)
- 4 ARM cores, 24GB RAM (if available in your region)
- 200GB storage
- Would be ideal if card is available

### 20.4 Fly.io Free Tier

- Requires credit card for verification
- 3 shared VMs
- 3GB persistent volume storage
- $5/month credit free

### 20.5 Alternative: Local Tunnel

Use localtunnel or ngrok to expose local server:
```
npx localtunnel --port 8000
```
Public URL: https://some-id.loca.lt
Access from anywhere, no deployment needed

---

## 21. COMPLETE FUNCTION REFERENCE

### 21.1 gtfs_service.py (591 lines)

| Line | Function | Purpose |
|------|----------|---------|
| 6 | _time_to_seconds | "HH:MM:SS" → int seconds |
| 12 | _normalize | Lower, strip punctuation, collapse whitespace |
| 18 | _fuzzy_match | SequenceMatcher with substring bonus (cutoff 0.55) |
| 40 | _now | Returns frozen time or real time |
| 47 | set_test_time | Freeze time for testing |
| 52 | clear_test_time | Clear time freeze |
| 57-67 | GTFSLoader.__init__ | Initialize empty data structures |
| 69 | _hav | Haversine distance in km |
| 76 | _try_load_cache | Load pickle cache (~69MB) |
| 100 | _save_cache | Save pickle cache |
| 117 | load | Main loader: cache→zip→indexes→save |
| 240 | _resolve_name | 6-stage fuzzy name resolution |
| 274 | get_shape_by_route | First shape for a route (≥2 points) |
| 283 | get_shape_between_stops | Shape segment between two stops (USES _resolve_name) |
| 312 | get_next_buses | Next departures for stop (limit 3) |
| 337 | get_next_buses_with_times | Filtered by route number |
| 359 | get_common_routes | Routes serving both stops |
| 373 | get_all_routes_at_stop | All routes at stop with times |
| 402 | get_all_buses_at_stop | All buses grouped by route |
| 426 | search_stops_by_name | Fuzzy stop name search |
| 441 | get_route_stops | Stops on a route (by departure time order) |
| 463 | get_shape_path_for_route | Full shape (≥4 points) |
| 475 | find_stops_on_route_toward_dest | SEQUENCE-ORDERED stops after source on route |
| 544 | _find_stops_euclidean_fallback | Old Euclidean method fallback |
| 577 | get_stop_coords | GTFS coordinates for a stop |
| 587 | resolve_name | Public _resolve_name wrapper |

### 21.2 transit_service.py (2234 lines)

| Line | Function | Purpose |
|------|----------|---------|
| 7 | _ensure_gtfs | Lazy GTFS loader |
| 17-60 | _TRAIN_DATA | Hardcoded train schedules |
| 62 | _get_train_options | Lookup normalized train data |
| 108 | _current_hour | Respects test time |
| 113 | _is_metro_operating | 5AM-11PM check |
| 118 | _route_goes_toward_dest | Direction check (cosine angle ≥ 0.26) |
| 152 | _gtfs_buses_at_stop | GTFS routes at stop |
| 159 | _has_gtfs_route | GTFS data existence check |
| 167-173 | TransitService.__init__ | _path_cache init |
| 169 | haversine_distance | Geodesic distance (geopy) |
| 176 | _find_common_routes | Routes common to 2 stops from CSV |
| 182 | _add_leg_coords | Add lat/lng to route legs |
| 204 | get_route_legs_public | Legacy route planner (combines 5 generators) |
| 228 | _get_bus_route_nums | Common routes between stops |
| 232 | _generate_bus_routes | Walk→bus→walk |
| 320 | _generate_metro_routes | Walk→metro→walk |
| 370 | _generate_metro_interchange_routes | Walk→metro→switch→metro→walk |
| 456 | _generate_kia_routes | Walk→KIA→walk |
| 508 | _generate_multi_modal_routes | Bus→metro, metro→bus |
| 610 | get_mini_path_options | Quick transit overview (legacy) |
| 790 | _is_outside_bengaluru | Distance > 35km from center |
| 795 | _find_farthest_bus_stop_toward_dest | For out-of-city routes |
| 816 | get_segment_step_options | Single-segment step (legacy) |
| 1302 | _add_direct_options | Walk + rides from→dest |
| 1342 | _add_reach_options | Walk+rides from→stop |
| 1388 | _add_transit_options | Bus+metro+train with final+next |
| 1649 | _build_next_transit | Recursive transfer chaining |
| 1893 | _build_single_segment | One segment build |
| 1990 | get_all_segments | Multi-segment builder |
| 2067 | _topsis_score | Route scoring (fare, time, walk, comfort) |
| 2133 | _interpolate_path | Linear path interpolation |
| 2144 | get_osrm_path_between | OSRM path with cache |
| 2166 | _add_leg_paths | Path enrichment for legacy routes |
| 2200 | get_osrm_route | OSRM turn-by-turn directions |

### 21.3 database.py (300 lines)

| Line | Function | Purpose |
|------|----------|---------|
| 16-23 | __new__ | Singleton pattern |
| 25 | initialize | Load all data, build indexes |
| 53 | _load_transit_fares | fares.json |
| 59 | _load_metro_data | Metro CSV + indexes |
| 103 | _load_bus_stops | Bus CSV + dict |
| 135 | _load_kia_routes | KIA JSON |
| 142 | get_metro_fare | Slab lookup |
| 148 | get_bmtc_ordinary_fare | Slab lookup |
| 159 | get_bmtc_ac_fare | Slab lookup |
| 169 | find_metro_station | By name substring |
| 177 | find_bus_stops | By name substring |
| 185 | find_nearby_bus_stops | R-tree spatial query |
| 188 | _load_railway_stations | Railway JSON |
| 194 | find_nearby_railway_stations | R-tree query |
| 197 | get_metro_distance_between | Cached cumulative distance |
| 219 | find_nearby_metro_stations | R-tree query |
| 222 | get_metro_line_path | Station coords along line |
| 258 | get_kia_route_for_stop | KIA routes serving stop |
| 272 | find_stop_by_name | Exact→substring across bus+metro |

### 21.4 routes.py (706 lines)

| Line | Function | Purpose |
|------|----------|---------|
| 11 | _clean | NaN-safe float |
| 16 | _sanitize | Recursive NaN removal |
| 25 | _combine_multi_stop_routes | Merge waypoint segments |
| 72 | plan_route | POST /api/routes/plan |
| 314 | _estimate_fuel_cost | Petrol cost calc |
| 319 | get_metro_stations | GET /api/routes/metro-stations |
| 327 | get_bus_stops | GET /api/routes/bus-stops |
| 335 | get_kia_routes | GET /api/routes/kia-routes |
| 339 | get_transit_fares | GET /api/routes/transit-fares |
| 343 | get_live_prices | GET /api/routes/live-prices |
| 348 | get_all_segments | GET /api/routes/all-segments (KEY) |
| 484 | get_mini_path_options | GET /api/routes/mini-path-options |
| 520 | get_segment_step | GET /api/routes/segment-step |
| 587 | get_travel_news | GET /api/routes/news |
| 642 | get_traffic_overlay | GET /api/routes/traffic-overlay |

---

## 22. EVERY DATA FILE — COMPLETE REFERENCE

### 22.1 data_cache/bmtc_gtfs.zip (BMTC GTFS)
Contents: stops.txt, stop_times.txt, trips.txt, routes.txt, shapes.txt
Source: BMTC official or transitfeeds.com
Update: 2023 (might be outdated)

### 22.2 data_cache/bmtc_all_stops_master.csv
Source: Derived from BMTC data
Columns: Stop Name, Latitude, Longitude, Routes with num trips
Rows: ~5000+
Routes column format: Python dict literal string

### 22.3 data_cache/bengaluru_metro_network.csv
Source: Bangalore Metro Rail Corporation (BMRC)
Lines: Purple (Kengeri→Whitefield), Green (Nagasandra→Silk Institute)
Columns: station_name, line, latitude, longitude, station_code, next_station_code, distance_to_next_km, is_interchange, sequence

### 22.4 data_cache/karnataka_railway_stations.json
Source: Indian Railways / OpenStreetMap
Format: JSON array of {name, lat, lng}

### 22.5 data_cache/kia_routes_fare_full.json
Source: KIA BMTC airport bus routes
Format: {vayu_vajra_kia_routes: {route_id: {route_info, stops: [{stop_name, lat, lng, fare}]}}}

### 22.6 data_cache/transit_fares.json
Format: {namma_metro_slabs: [{max_km, fare}], bmtc_ordinary_slabs: [{max_km, fare}], bmtc_ac_vajra_slabs: [{max_km, adult_fare, child_fare, senior_fare}]}

### 22.7 data_cache/processed/gtfs_cache.pkl (~69MB)
Auto-generated pickle cache of GTFS data
Contains: shapes, route_shapes, stop_to_shapes, stops_by_name, stop_times, stop_times_by_route, name_map

---

## 23. TESTING PROCEDURES

### 23.1 Quick Test — Hit API Directly

```
# Set test time (12:00 PM for metro operation)
$env:VOYAGER_TEST_TIME = "2024-07-15 12:00:00"

# Start server
python -m uvicorn backend.main:app --reload --port 8000

# Test all-segments (Yelahanka → MG Road, max_depth=1)
curl "http://localhost:8000/api/routes/all-segments?from_lat=13.1007&from_lng=77.5963&from_name=Yelahanka&dest_lat=12.9756&dest_lng=77.6065&dest_name=MG%20Road&group_size=1&max_depth=1"

# Test with max_depth=3 (multi-hop)
curl "http://localhost:8000/api/routes/all-segments?from_lat=13.1007&from_lng=77.5963&from_name=Yelahanka&dest_lat=12.9756&dest_lng=77.6065&dest_name=MG%20Road&group_size=1&max_depth=3"

# Test health
curl "http://localhost:8000/health"

# Test metro
curl "http://localhost:8000/api/routes/metro-stations"
```

### 23.2 Frontend Testing

```
# Frontend
cd frontend
npx vite --port 3000

# Open browser: http://localhost:3000
# Search a place → click → A-to-B → Show Routes
# Click direct options → see nearby stops
# Click a stop → see transit options
# Hover → see path on map
# Click transit → see next_transit transfers
# Start Journey → GPS marker
```

### 23.3 Test Scenarios

1. **Short distance (< 2km)**: Majestic→KR Market → should show walk + bike only
2. **Medium distance (5-10km)**: Yelahanka→MG Road → should show bus, metro options
3. **Long distance (> 15km)**: Whitefield→Kengeri → should show multi-hop options
4. **Out-of-city (> 35km)**: Bengaluru→Mysuru → should show train options
5. **Budget constraint**: Yelahanka→MG Road with budget=₹50 → should filter expensive options
6. **Group**: 4 people → XL cab, group discounts

---

## 24. SEGMENT SYSTEM — WHAT EXTRA NEEDS TO BE DONE

### 24.1 What Works Now (July 2026)

- Multi-column progressive UI: up to N columns
- Direct options (walk, cab, auto, bike) with path rendering
- Nearby stops (bus, metro, railway) with reach options
- Transit options (bus routes with GTFS times, metro, train)
- Final mile (walk, bus final, rides)
- Next transit (bus→bus, bus→metro transfers) up to depth 3
- Transfer chaining in frontend with hover path display
- Shape-sequence-based stop ordering (FIXED)
- Case-insensitive stop name resolution for shapes (FIXED)
- Direction filtering tightened to 75° (FIXED)

### 24.2 What Still Needs Work

1. **Too many irrelevant bus options** — Need ranking by relevance score (closer to dest, faster, cheaper, fewer transfers)

2. **Metro→bus→bus not chaining** — After metro transfer, next_transit = [] always. Need to find buses from metro exit stop too.

3. **Direction filtering still not perfect** — Some buses going slightly away from dest still pass the 75° check. Need to also check distance progress (closer to dest after the ride).

4. **Circular routing not fully prevented** — Visited_stops only checks exact name match. Same stop at different coordinates bypasses it.

5. **Very long response times** — max_depth=3 can take 15-20s. Need:
   - Limit options per level (max 2-3, not 8)
   - Early cutoff if arrival is within 1km of dest
   - Cache common query patterns

6. **UI lag with many options** — Hundreds of TransitOptions cause slow rendering:
   - Virtual scrolling for columns
   - Lazy load deeper columns (only build when user clicks "more")
   - Paginate bus routes (show top 5, "show more" button)

7. **No route comparison** — User can't compare two transit options side by side:
   - Add "Compare" button that highlights differences
   - Show summary bar (fare, duration, transfers, walk distance)

8. **No departure time awareness** — Bus times shown but not factored into selection:
   - Grey out buses that depart in >30 minutes
   - Show "next bus in X min" badge
   - Allow user to set preferred departure window

9. **No accessibility info** — Steps? Elevators? Wheelchair ramps at metro stations?
   - Need to add station facilities data

10. **No intermediate stop display on map** — When hovering a bus route, show its full route on map
    - Not just the segment, but ALL stops along the route
    - Helps user understand where the bus goes

11. **No "arrival at" time calculation** — Only shows duration, not actual clock time:
    - departure_time + duration = arrival_time
    - Show "Arrive by 2:30 PM"

12. **Budget group size per-person display** — Total fare vs per-person fare confusing:
    - Show: "₹60 total (₹15/person × 4)" instead of just "₹60"

---

## 25. APPENDIX: Glossary

| Term | Definition |
|------|-----------|
| **Segment** | A leg of the journey from one point to another (or toward destination) |
| **Direct Option** | A mode that takes you directly from current point to destination (walk, cab, etc.) |
| **Reach Option** | A mode that takes you from current point to a transit stop |
| **Transit Option** | A transit mode (bus/metro/train) from a stop toward destination |
| **Final Option** | Last-mile option from the last transit stop to destination |
| **Next Transit** | A subsequent transit hop after the current transit option drops you off |
| **Transfer Chain** | Sequence of selected options forming the complete route |
| **MAJOR_HUB** | Transit hub like Majestic, KR Market, Shivajinagar |
| **GTFS** | General Transit Feed Specification (standard format for transit schedules) |
| **R-tree** | Spatial index for efficient nearby-geometry queries |
| **OSRM** | Open Source Routing Machine (road network routing) |

---

*Documentation generated on 2026-07-16 for VOYAGER Bengaluru Transit Navigator*
*Total: ~30+ pages of detailed documentation covering all 24 sections*

