# VOYAGER v2 — MASTER KNOWLEDGE BASE

> **Purpose:** A single, complete, plain-language reference for the entire VOYAGER v2 project.
> Read this before starting any future work session. It covers: what the product is, the build
> philosophy, the full 9-prompt roadmap (done + pending), every backend module with contracts,
> every dataset, every integration (SerpAPI / Google Maps / GraphHopper / DataImpulse proxy /
> OpenRouter/Gemini), the hop/segment mechanism in deep detail, everything that was built and
> corrected so far, all tests, and what to do next.
>
> Written: 2026-08-01. Updated: 2026-08-01 (PROMPT_4/5/6 done). Source of truth:
> `C:\Users\len\OneDrive\Desktop\VOYAGER\PROJECT\`

---

## TABLE OF CONTENTS

1. The Elevator Pitch
2. The Golden Build Rule (most important thing)
3. The Three App Modes (the product vision)
4. Tech Stack & Ports
5. Directory Map (project tree)
6. The Roadmap — 9 Build Prompts, status table
7. Data Layer (PROMPT_1) — what is DONE
8. Routing Graph + Route Finder (PROMPT_2) — what is DONE
9. Segment Builder API (PROMPT_3) — what is DONE
10. Search + Reliability + TOPSIS (PROMPT_4) — PLANNED
11. LangGraph Live Layer (PROMPT_5) — PLANNED
12. Frontend (PROMPT_6) — PLANNED
13. ML + Integration Testing (PROMPT_7) — PLANNED
14. Trip Planner (PROMPT_8) — PLANNED
15. Deployment (PROMPT_9) — PLANNED
16. Integrations Deep-Dive
17. The Hop Mechanism Explained (segment builder internals)
18. Data Sources & Datasets Inventory
19. Everything Achieved & Corrected So Far (session log)
20. Tests & QA
21. Known Problems, Honest-Fallbacks, and Deliberate Decisions
22. Performance Budgets & Current Benchmarks
23. Docker & Local Run Guide
24. Secrets & Environment Variables
25. What To Do Next (recommended order)
26. Appendix A — API Endpoints (implemented + planned)
27. Appendix B — Key Constants (radii, speeds, budgets)
28. Appendix C — Error Glossary (past bugs so we never repeat them)

---

## 1. THE ELEVATOR PITCH

**VOYAGER** is a Bengaluru-first "everything you need to move around" travel/navigation app:

- **Search** — find a place, or find things *nearby* (ATM, mall, petrol pump, cafe…), with
  **real Google reviews**, a **reliability score** (green/yellow/red), photos, hours, and prices
  for hotels — because Google Maps results are full of dead/fake/wrong locations.
- **A→B** — plan a trip from A to B **three ways**: Public/Online (direct cab OR a Google-Maps-like
  **multi-hop transit segment window** with real BMTC bus numbers, timings, Namma Metro Purple/Green,
  KIA airport buses, walk transfers), **Drive** (real road-following path + fuel cost), and **Walk**.
  The multi-hop window is the centerpiece: the user picks their own hop-by-hop journey, and every
  hop is *real* — real bus numbers, real scheduled departure times, real geometry, real fares.
- **Trip** — a full multi-day destination-and-itinerary planner (2–5 days) with budget, interests,
  pace, geo-clustered day assignment, per-day map pins, on-demand transport, and Postgres persistence.

**Non-negotiable product rules (from the owner):**
- **No fake data. Ever.** No fabricated bus numbers, timings, fares, reviews, reliability scores,
  news headlines, or prices. If a real source has no data, show nothing or an explicitly labeled
  "Estimated / Approx / Unavailable" state — never invent.
- The backend does **100% of the thinking**. The frontend is a dumb renderer + local filter.
- Real Google Maps quality: "Govt School → Wonderla = take 507-D → Kogilu Cross, then KIA-9 → Majestic,
  then Purple metro → Challaghatta, then walk → 231 bus → Wonderla." That exact kind of journey,
  segmented, with choices at every level.
- Every ride/path/pricing label: **Live vs Estimated** (SerpAPI live = Live; formula = Estimated).
- Only operational metro: **Purple + Green**. **NO Blue Line, NO Yelahanka** (under construction).

---

## 2. THE GOLDEN BUILD RULE (READ EVERY TIME)

> **The current v2 is built FRESH inside `C:\Users\len\OneDrive\Desktop\VOYAGER\PROJECT\`.**
>
> The **parent** `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, `stitch_omnipath_ai_navigation/`,
> `data_cache/`) is **REFERENCE-ONLY for past mistakes**. NEVER import code from it, never read it to
> "implement", never "fix" it. All code, decisions, and data contracts come from the `PROMPT*.md` files
> in `PROJECT/` + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

This is the single most important instruction in the whole project. The parent repo is a 2400-line
monolith that was full of bugs (see Appendix C). The v2 was created specifically to rebuild cleanly.

---

## 3. THE THREE APP MODES (the product vision)

From the master `PROMPT.md`, the app opens on a **map with three bottom tabs**:

1. **SEARCH** — two sub-features:
   - **Search Specific**: type any place (India-wide) → it appears on the map with a pin, and the
     right-side **Discovery Panel** shows: name, rating, reliability score + colored pill, hours,
     photo, review summary (Gemini), real reviews, hotel price range (only for stay-type places),
     plus **Navigate Here** (→ hands off to A→B with destination pre-filled).
   - **Search Nearby**: category chips (ATM, Bank, Hospital, Pharmacy, Restaurant, Cafe, Hotel, Mall,
     Petrol Pump, EV Station, Supermarket, Park, Bus Stop, Metro, Temple, Police, School, Gym, Cinema)
     + a radius slider. Results appear as **green/red pins sized by reliability score**. Each result
     shows a reliability score + review summary. Agentic verification (Google reviews + business status)
     decides which places are real/recommended vs dead/dodgy. For stay-type places, prices shown.
   - When you pin a specific place, a small banner offers "search nearby around it" (new anchor).
2. **A→B** — destination input + **two transport forks**:
   - **Personal / Self-Navigate** (Drive / Walk): driving route with **live petrol cost**
     (₹/litre × distance ÷ mileage, adjustable mileage), road-following path, turn directions,
     nearby petrol pumps/shops along the way; or walking route.
   - **Public/Online (System Orchestrated)**: user fills **group size + budget**, then either
     **Direct Ride** (Uber/Ola/Rapido/Auto cards with live/estimated prices + ETA) or **Multi-Hop
     Transit** (the segment window — see §17).
   - All possible routes shown; the **best 4–5 highlighted** (TOPSIS-ranked, "Best Match" tag), rest in
     a "Show all options" expander.
3. **TRIP** — multi-day destination itinerary planner (see PROMPT_8, §14).

Supporting product demands repeated throughout the master prompt:
- **Dynamic map** — pan/flyTo on selection; hop highlight per selected leg; user blue pin + GPS
  tracking; hover uplift with review summary popup.
- **Header bar** — live clock, weather for current location, dark/light mode toggle.
- **Live news** — Bengaluru news / traffic / weather / road-block popups, REAL and fresh, polled
  every 2 min, geo-tagged map markers.
- **Time-of-day suggestions** — "it's late, cab is safest", rain advisories, etc.
- **LLM (Gemini) explains in plain Hinglish**, never writes numbers.

---

## 4. TECH STACK & PORTS

| Component | Tech | Port | Notes |
|---|---|---|---|
| Backend | FastAPI (Python 3.12, uvicorn) | **8000** | `python -m uvicorn backend.main:app --reload --port 8000` |
| Frontend | Vite + React + TypeScript, Leaflet | **3000** | ✅ BUILT (PROMPT_6): `cd frontend; npx vite --port 3000` |
| GraphHopper | Local Docker (car + foot) | **8080** | Karnataka PBF (~100MB), see `docker-compose.yml` |
| OSRM (legacy) | Local Docker (car / foot) | 5000 / 5001 | v1 thing; v2 uses GraphHopper instead |
| Postgres | Neon (free hosted) via `DATABASE_URL` | — | Trips persistence (PROMPT_8) |

requirements.txt (as committed):
```
fastapi>=0.115, uvicorn[standard]>=0.30, pydantic>=2.7, python-dotenv>=1.0,
requests>=2.31, psycopg[binary]>=3.1, httpx>=0.27
```

---

## 5. DIRECTORY MAP (PROJECT root)

```
PROJECT/
├── PROMPT.md                     # Master vision (Hinglish, raw)
├── FEATURES.md                   # Feature summary
├── ABOUT_GRAPHHOPPER.md          # Design doc that PROMPT_3 corrected
├── "trip planer prompt.md"       # Notes from the trip-planner grilling session
├── docker-compose.yml            # graphhopper:8080
├── requirements.txt
├── .env.example                  # All keys documented (commit this)
├── .env                          # REAL secrets — NEVER commit
├── PROMPTS/
│   ├── PROMPT_1_DATA_LAYER.md
│   ├── PROMPT_2_ROUTING_GRAPH.md
│   ├── PROMPT_3_SEGMENT_BUILDER_API.md
│   ├── PROMPT_4_SEARCH_SCORING.md
│   ├── PROMPT_5_LANGGRAPH_LIVE_LAYER.md
│   ├── PROMPT_6_FRONTEND.md
│   ├── PROMPT_7_ML_INTEGRATION_TESTING.md
│   ├── PROMPT_8_TRIP_PLANNER.md
│   └── PROMPT_9_DEPLOYMENT.md
├── DATA_FOLDER/                  # Static datasets (see §18)
│   ├── bmtc_gtfs/                # Raw GTFS .txt (NOT committed — 190MB)
│   ├── processed/gtfs_cache.pkl  # 67MB pickle — COMMIT THIS (cold boot)
│   ├── bmtc_all_stops_master.csv
│   ├── bengaluru_metro_network.csv
│   ├── karnataka_railway_stations.json
│   ├── kia_routes_fare_full.json
│   ├── transit_fares.json
│   └── traffic_logs.csv          # 7.5MB, for ML (PROMPT_7)
├── gh-data/                      # GraphHopper data dir (Karnataka PBF + config)
├── backend/
│   ├── main.py                   # FastAPI app, lifespan → app_state.ensure_loaded()
│   ├── config.py                 # Paths + env helpers
│   ├── api/routes.py             # All endpoints (segments, search, langgraph, news, photo proxy)
│   └── services/
│       ├── app_state.py          # Lazy singletons (gtfs, db, gh, builder, news, agent)
│       ├── data_schema.py        # Pydantic models (single source of truth)
│       ├── gtfs_service.py       # GTFS loader/cache/fuzzy-name-resolution
│       ├── fare_engine.py        # BMTC/AC/metro/KIA/ride fares, surge
│       ├── database.py           # In-memory station DB + spatial index
│       ├── graphhopper_client.py # HTTP client for local GraphHopper
│       ├── transit_graph.py      # TransitAstarGraph (static topology)
│       ├── route_finder.py       # Best-first top-K N-hop route search
│       ├── transit_models.py     # Leg, RoutePlan dataclasses
│       ├── segment_builder.py    # THE HOP MECHANISM (tree of choices)
│       ├── search_service.py     # PROMPT_4 place search/nearby/enrich
│       ├── reliability.py        # reliability score formula
│       ├── sentiment.py          # local review sentiment
│       ├── topsis_engine.py      # 8-factor numpy TOPSIS (TopsisWeights)
│       ├── ride_pricing.py       # live + formula ride prices
│       ├── review_tools.py       # SerpAPI review chain + AI summaries
│       ├── news_engine.py        # PROMPT_5 background news loop
│       ├── proxy_manager.py      # DataImpulse proxy helper
│       ├── train_service.py      # eRail.in live trains
│       ├── clients/
│       │   ├── google_maps_client.py  # Places/Geocoding/Directions/photo
│       │   ├── serpapi_client.py      # reviews/place-details (key fixed: place_results)
│       │   ├── weather.py / reddit.py / ddg_scraper.py
│       ├── langgraph/            # agent.py, state.py, tools/, workflows/route_context.py
│       └── scrapers/             # ride_scraper, google_reviews_scraper, justdial (dropped), ddg
├── backend/agents/llm_agent.py  # OpenRouter/Gemini singleton (never writes numbers)
├── frontend/                    # PROMPT_6 (Vite + React + TS + Leaflet)
│   ├── src/context/AppContext.tsx
│   ├── src/pages/MainPage.tsx
│   ├── src/components/{HeaderBar,MapView,SearchPanel,DiscoveryPanel,AToBPanel,
│   │                      SegmentFlowView,TripPanel,NewsPopup}.tsx
│   ├── src/services/api.ts, src/types/index.ts, src/index.css
│   └── vite.config.ts           # :3000, /api proxy → VITE_API_BASE
├── tests/
│   ├── test_fare_engine.py, test_segment_builder.py, test_prompt4.py, test_prompt5.py
└── gh-data/config.yml            # GraphHopper car+foot config
```

---

## 6. THE ROADMAP — 9 BUILD PROMPTS, STATUS TABLE

| # | Prompt | Name | Status |
|---|---|---|---|
| 1 | PROMPT_1 | Data Layer (GTFS, fares, station DB, GraphHopper client) | ✅ **DONE** (commit `b48de93`) |
| 2 | PROMPT_2 | Routing Graph + N-hop route finder | ✅ **DONE** (commit `2e2b8ff`) |
| 3 | PROMPT_3 | Segment Builder API (the hop mechanism) | ✅ **DONE** (commit `5aadb08`, `18c5c8c`, `523197c`, `9c631bd`) |
| 4 | PROMPT_4 | Search, Place Reliability, 8-factor TOPSIS | ✅ **DONE** (84 tests pass) |
| 5 | PROMPT_5 | LangGraph agent + live layer (weather/news/traffic/train) | ✅ **DONE** (84 tests pass) |
| 6 | PROMPT_6 | Frontend rebuild (glassmorphism) | ✅ **DONE** (builds clean, dev server + proxy verified) |
| 7 | PROMPT_7 | ML traffic model + integration tests + fake-data audit | 🔲 PLANNED |
| 8 | PROMPT_8 | Trip Planner (Feature 3) | 🔲 PLANNED (design locked) |
| 9 | PROMPT_9 | Deployment (Render free + Neon) | 🔲 PLANNED (design locked) |

**Current state: prompts 1–6 are fully implemented and tested.**
- Backend: **84 pytest pass** (`pytest tests/ -q`, ~47s): `test_fare_engine.py`,
  `test_segment_builder.py`, `test_prompt4.py`, `test_prompt5.py`.
- Frontend: `npx tsc -b` + `vite build` zero errors; dev server :3000 proxies `/api` → :8000;
  `/api/search/photo` proxy verified (307 → real Google photo URL); news/weather endpoints 200.
- Prompt 7 is next (ML + integration tests + fake-data audit), then PROMPT_8, PROMPT_9.

---

## 7. DATA LAYER (PROMPT_1) — DONE

Five modules, all under `backend/services/`, wired lazily in `app_state.py`.

### 7.1 `gtfs_service.py` — GTFS loader + cache + fuzzy name resolution
- **Reuses the committed 67MB pickle** (`DATA_FOLDER/processed/gtfs_cache.pkl`) — never re-derives
  on startup (was a ~41s block in v1; now **0.65s**).
- Pickle structure (the contract downstream code relies on):
  ```
  shapes:            dict[shape_id] -> [(lat,lng), ...]
  route_shapes:      dict[route_name] -> [shape_id, ...]
  stop_to_shapes:    dict[stop_name] -> [(shape_id, seq), ...]
  stops_by_name:     dict[stop_name] -> (lat, lng, stop_id)      # ~5077 stops
  stop_times:        dict[stop_name] -> [(HH:MM:SS, route_name)]
  stop_times_by_route:dict[route_name] -> [(HH:MM:SS, stop_name)]
  name_map:          dict[master_stop_name] -> resolved_gtfs_name  (persisted)
  route_id_to_name:  dict[route_id] -> cleaned route name
  ```
- **Route-name cleaning** (`clean_route_short_name`): strips terminal garbage suffixes —
  `"MF-28 JKLO-ISROQ-LGRNB"` → `"MF-28"`, `"  242-LA "` → `"242-LA"`. Keeps real names with a
  trailing digit token (`"BEL GS-16"`, `"KSRTC-T NARASIPURA-1"`). Applied at GTFS load AND CSV
  stop-source ingestion (commit `a456261` re-cleaned 9 leaked names in the pickle).
- **Fuzzy name resolution chain** (`_fast_fuzzy_match`): exact → word-overlap inverted index
  (≥0.5 score) → trigram-filtered `get_close_matches` (cutoff 0.80) → substring → `None`.
  `name_map` pre-resolved **1696/2972** master stop names; 14 names have **no** match (e.g.
  `hnrj`, `ggmc`, `pesitelc`) and correctly stay `None` → "No real-time data".
- **Fast queries**: `get_routes_at_stop()`, `earliest_departures()` (per-stop cached sorted
  minutes list, early break), `get_stop_to_stop_segment()` (real shape slice between two stops,
  never the full route).
- **`get_stop_to_stop_segment`** projects both stops onto each candidate shape (nearest vertex
  within 400m) and returns the polyline slice; returns `None` if both stops don't land on a shape
  → caller must flag, never draw the full route.

### 7.2 `fare_engine.py` — pure fare functions (no I/O inside)
- `bmtc_fare(route_class, dist_km, passenger_type)` — AC Vajra / ordinary / nonac slabs from
  `transit_fares.json`; child = half (ceil, min ₹3), senior = adult − ₹0.75 (min ₹3).
- `metro_fare(dist_km, line)` — single slab table shared by both lines.
- `kia_fare(route_id)` — from `kia_routes_fare_full.json`; uses the max stop fare as the honest
  reference when distance is unknown; `0.0` + `is_estimated` when route unknown.
- `surge_multiplier(hour, weekday)` — 07–10 & 17–21 weekday → 1.5; 22–06 → 1.8; else 1.2.
- `ride_fare_range(ride_type, dist_km, group_size)` — **Karnataka govt-mandated rates**:
  Uber Go/Ola Mini ₹24/km (min ₹85), Uber XL ₹32/km (min ₹130), Ola Auto ₹20/km (min ₹40),
  Rapido Bike ₹5/km (min ₹25). Returns (min, max) with `is_estimated=True`.
  Per-person = vehicle fare / group (NOT ×group — old bug fixed).

### 7.3 `database.py` — in-memory station DB + spatial index
- Loads: `bmtc_all_stops_master.csv` (~2972 stops, skips `nan/none/null` names), metro CSV
  (**Purple + Green only** — Yelahanka/Blue excluded), rail JSON (22 Karnataka stations).
- Spatial index: **sorted-by-lat + binary search + lng window + haversine**, <5ms for ~3000 stops
  (verified by test: 100 queries in <0.5s).
- API: `bus_stops_near / metro_near / rail_near(lat, lng, radius_m)`, `all_bus_stops /
  all_metro_stations / all_rail_stations`, `metro_edges()` (adjacent-station pairs with dist+line),
  `routes_for_stop()`.

### 7.4 `graphhopper_client.py` — HTTP client for local Docker GraphHopper
- `route(mode: "car"|"foot", lat1,lng1,lat2,lng2) -> GHResult | None`. Returns `None` on
  timeout/error → caller falls back to interpolated and **flags it** (`path_source`).
- 24h in-memory cache keyed by `(mode, r4(lat), r4(lng), r4(lat), r4(lng))`.
- `is_healthy()` checks `/info`.

### 7.5 `data_schema.py` — shared Pydantic models
Single source of truth: `GtfsStop, RouteDeparture, BusStop, MetroStation, RailStation, TransitNode,
FareResult, GHResult`. Downstream modules import these; never redefine.

---

## 8. ROUTING GRAPH + ROUTE FINDER (PROMPT_2) — DONE

### 8.1 `transit_graph.py` — TransitAstarGraph (static topology)
- **Nodes**: every GTFS-resolved bus stop (2000+ bus nodes), every metro station (68 = 2 lines),
  every rail station (≥22). Node keys: `bus:<name>`, `metro:<name>`, `rail:<name>`.
- **Edges** (undirected, stored as adjacency tuples `(neighbor, edge_type, data)`):
  - `bus` — consecutive stops on the same route shape, with 1-skip tolerance (pair-accumulated by
    route, weights computed once per unique pair). Weight = haversine × 1.15 road factor / bus speed
    + dwell (0.3 min).
  - `metro` — adjacent stations same line (from `metro_edges()`). Weight = dist / metro speed + dwell.
  - `walk` — uniform spatial grid (cell ~560m); bus↔bus ≤500m, bus↔metro ≤1000m, bus↔rail ≤3000m.
    Walk time @5 km/h.
- **Speeds (constants)**: bus 18 km/h (edge weight; graph uses 18, docs say 22 — the edge weights
  use `BUS_SPEED_KMH = 18.0`), metro 36 km/h, walk 5 km/h. Transfer penalty 4 min, interchange
  fixed 5 min.
- **Performance**: haversine + `_dist_cache` dict only (never `geodesic` in hot loops — this was the
  11.6s → 2.2s win). Graph builds in ~2.2s, printed at init.

### 8.2 `route_finder.py` — best-first top-K N-hop search
- Public API: `find_routes_by_coords(src_lat, src_lng, dest_lat, dest_lng, depart_min, group_size,
  budget_pp, max_paths) -> list[RoutePlan]`. 10-min in-memory cache keyed by rounded coords +
  10-min time bucket + group + budget.
- **Algorithm** (`_plan` → `_search`):
  1. Walk-only route when `direct_km ≤ 2.0` (free).
  2. Always add a ride route (Uber Go pricing, GraphHopper car geometry for real road).
  3. Entry nodes: top 3 bus (≤2km) + top 2 metro (≤3km) + top 1 rail (≤5km). Symmetric exits.
  4. **Best-first search (A*-like)** on the graph, up to `MAX_LEGS=6`, `MAX_PATHS=12`, heap keyed
     `g + h` (h = haversine-to-dest / metro speed).
  5. **Hard guards**: 800m `near_visited` (anti-circular, metro exempt), forward-progress rule
     `hav(nb→dest) < hav(node→dest) + tol` (tol = 500m normal, 2500m metro because lines curve).
  6. Edge cost = time + transfer/interchange penalties + `fare_pp / BUDGET_SENSITIVITY` (₹8 ≈ 1 min).
  7. Mode-signature dedup: max 3 plans per mode-combo (e.g. `("bus",)`); per-node labels bounded to 6.
- **Assembly** (`_assemble_chain`): merges consecutive same-mode edges (`_merge_edges`), then builds
  `Leg`s with **time chaining** (each leg's departure ≥ previous arrival + 3min buffer):
  - `_bus_leg`: real GTFS departure via `earliest_departures(from_stop, after, route_filter)`;
    alternate routes fallback; `status="not_running"` if >45min wait; KIA vs BMTC fare; geometry =
    GTFS shape slice → GraphHopper car → interpolated (flagged).
  - `_metro_leg`: line polyline through intermediates, `status="estimated"`, `metro_fare`.
  - `_walk_leg`: GraphHopper foot → interpolated (flagged).
  - `_ride_route`: GraphHopper car geometry + `ride_fare_range("uber_go", ...)`.
- Results sorted by (count of not_running legs, total_duration_min). TOPSIS re-ranking is PROMPT_4.

---

## 9. SEGMENT BUILDER API (PROMPT_3) — DONE (THE CENTERPIECE)

This is the **hop mechanism**. See §17 for the deep-dive. Summary of the API contract:

### 9.1 `POST /api/routes/segments`
- Request: `{source:{lat,lng,name}, destination:{lat,lng,name}, group_size, budget, current_time}`.
- Response: `{journey, segments:[Segment1, Segment2], probes[], warnings[], journeyComplete:false, timeline[]}`.
- **Segment 1 FULL** (all options out of the source) + **Segment 2 FULL** (grouped by
  `connectedFrom`) + **probes** (top onward suggestions, `isProbe:true`) — so the frontend paints
  two columns instantly. Deeper segments are LAZY via segment-next (because departure times chain
  from previous arrival — you can't precompute Segment N until N−1 is chosen).

### 9.2 `POST /api/routes/segment-next`
- Request: `{journey, chosen_legs:[{optionId, arrivalTime, destinationStop}, ...], group_size, budget}`.
- Response: Segment N where every option `connectedFrom == last chosen stop` AND
  `departureTime >= arrival + 4min buffer`, plus probes. `journeyComplete:true` when last stop is
  within ~500m of dest → returns full `timeline` + "You have arrived".

### 9.3 Option contract (every hop carries all of this)
```
optionId, destinationStop{name,lat,lng}, mode(walk|bus|metro), routeNumber,
fromStop, distanceKm, durationMin, departureTime, arrivalTime, arrivalMin,
fare, perPersonFare, geometry[], geometrySource(gtfs_shape|metro_line|graphhopper|interpolated),
status(scheduled|estimated|not_running), isTopRecommended, connectedFrom,
transitOptionsFromThisStop, probeNext[], isMetroTransfer(bool), exceedsBudget(bool)
```
(Internal `_fromLat/_fromLng`/`_walkToBoard` are also attached to transit options.)

### 9.4 Key behaviors already implemented
- Walk options ≤2km, **walk is primary (top-recommended) when ≤1.5km** and no cab/bike shown.
- Transit = walk-to-board a bus/metro stop then ride to a forward stop. Forward-progress hard rule
  (`hav(→dest) < hav(anchor→dest) + tol`).
- **Bus→metro interchange rides** (`isMetroTransfer`): for long-haul routes (e.g. 285 from
  Rajanukunte), the builder searches the route's far-forward stops for one near a metro station and
  offers the full ride to that interchange (previously capped to first few stops only).
- **Metro rides** on EITHER line at hubs (Majestic carries "Purple Line,Green Line").
- Top recommendation heuristic: fewest transfers + lowest fare + shortest walk + earliest arrival.
- Budget: `exceedsBudget` flag (grey-out), never silent-drop.
- Warnings for late night (22–06) and `not_running` stops.

---

## 10. SEARCH + RELIABILITY + TOPSIS (PROMPT_4) — DONE

Implemented (all contracts live in `PROMPT_4_SEARCH_SCORING.md`, all covered by `test_prompt4.py`):

### 10.1 Google Places API (New) — `backend/services/clients/google_maps_client.py`
- Enabled APIs: Places (New), Geocoding, Directions/Distance Matrix.
- Methods: `geocode`, `search_places` (Text Search), `nearby_places`, `place_details`,
  `place_photos` (real photo URL), `directions` (incl. `duration_in_traffic`).
- Filters: ≥40% keyword overlap query↔result; coords within 15km of Bangalore center (wider for
  non-Bengaluru); dedup by 4-decimal coords.

### 10.2 Reliability score (dynamic, deterministic, explainable)
```
status_factor = 0.0 CLOSED_PERMANENTLY | 0.25 CLOSED_TEMPORARILY | 1.0 OPERATIONAL
reliability = ( 0.5*(rating/5) + 0.3*sentiment_avg + 0.2*min(1, log1p(reviews)/log1p(100)) ) * status_factor
score_pct = round(reliability*100)
```
Pin classes: **Green ≥70** (operational, rating≥3.5, glow+big) · **Yellow 50–69** · **Red <50**
(closed/rating<3.0, small+dim). Always recompute — never trust an external `reliability_score`.

### 10.3 Reviews & sentiment
- Chain: SerpAPI place search → place_id → place_details `user_reviews.most_relevant`
  (`username`, `description`, `rating`, `date`). Cache 24h keyed `place_id` + `_CACHE_VERSION`.
- Budget: best 2 reviews per star level, ~10 max (SerpAPI quota ~1250/mo across friend keys).
- Sentiment: local lightweight HuggingFace `distilbert-...-sst-2-english` → polarity avg; LLM
  (Gemini) sentiment only if local unavailable. **LLM never invents review text.**
- LLM allowed: summary (gist + `concerns[]`).

### 10.4 TOPSIS 8-factor (`topsis_engine.py`, real numpy)
- Weights (user-adjustable): time_of_day .10, cost .20, weather .10, traffic_crowd .15,
  availability .05, walking .15, group_size .10, safety .15.
- Steps: decision matrix → vector-normalize → weight → ideal/anti-ideal → Euclidean distances →
  closeness coefficient CC in [0,99]; tie-break lower fare.
- Every criterion traces to real data (weather API, Directions ratio, fare engine, GTFS times).

### 10.5 Ride pricing (`ride_pricing.py`)
- SerpAPI Google Maps directions → live; else formula (Karnataka govt rates + surge + slab),
  labeled `source: "live"|"estimated"`. Per-person = vehicle / group. 15-min cache.

---

## 11. LANGGRAPH LIVE LAYER (PROMPT_5) — DONE

Implemented (all contracts live in `PROMPT_5_LANGGRAPH_LIVE_LAYER.md`, covered by `test_prompt5.py`):

- **Role (non-negotiable)**: the agent GATHERS live factors in parallel and EXPLAINS — it never
  decides routes and never writes numbers. All numbers come from deterministic code / real APIs.
- `backend/services/langgraph/` — `agent.py` (VoyagerLangGraph: intent, parallel dispatch,
  synthesis), `state.py`, `tools/` (weather, traffic, news, pricing, review, search, geo, train),
  `workflows/route_context.py`.
- **Route-context graph**: parallel fan-out → weather (Open-Meteo), traffic (Directions
  `duration_in_traffic/duration` ratio), news (cached store), prices (ride pricing), reviews (only
  when a POI is the destination) → aggregated `LiveContext` JSON that feeds TOPSIS criteria + the
  Gemini explanation.
- **News engine**: background loop every 5–10 min scrapes r/bangalore + Karnataka news via
  DataImpulse proxy + DDG fallback; classify (`traffic|weather|event|general`), geo-tag, LLM-summarize
  (≤2 lines), dedup by title, keep max 25, TTL 4h. Served via `GET /api/search/news?lat=&lng=`;
  frontend polls every 2 min.
- **Live trains**: eRail.in scrape for 22 mapped Karnataka codes; 7 city-pair fallbacks **flagged**
  `source:"fallback"` only when eRail unreachable. Never fabricate a train leg.
- **Proxy rules**: DataImpulse for news/DDG/review-scans; **never** for SerpAPI/Google Maps/Reddit
  JSON/Open-Meteo/OpenRouter/Gemini (API-key auth).
- **Critical invariant**: live gathering is `gather:true, required:false` — routing always completes
  even if every live source is down (≤6s).

---

## 12. FRONTEND (PROMPT_6) — DONE

Built in `PROJECT/frontend/` (spec: `PROMPT_6_FRONTEND.md`). Verified: `npx tsc -b` + `vite build`
zero errors, dev server boots on :3000, `/api` proxy → :8000, photo/news/weather endpoints verified live.

- Vite + React + TS, Leaflet, Material Symbols, Inter. `AppContext` global state. Typed API client.
  **Gate: `npx tsc --noEmit` = 0 errors.**
- Layout: HeaderBar (clock/weather/location/dark-mode) | Sidebar (Search/A→B/Trip) | Map | Discovery
  panel (right) | bottom pill nav (SEARCH | A→B | TRIP).
- MapView: blue pulsing user dot, green/yellow/red reliability pins, numbered nearby pins, colored
  per-mode polylines (real geometry only; interpolated rendered dashed + "approx path" tag),
  hover uplift popups, flyTo/fitBounds, accumulated hop geometry.
- SearchPanel: Search Specific + Search Nearby (19 category chips, radius slider 0.5–10km),
  autocomplete ≥2 chars / 300ms debounce, location-pinned banner, reliability pills, hotel prices.
- DiscoveryPanel: hero photo, reliability pill, hours, AI review summary box (colored, red
  `concerns[]`), up to 5 real reviews, Show on Map + Navigate Here, loading skeleton.
- AToBPanel: Public/Online → Direct Ride (Live/Estimated badges) or **SegmentFlowView** (multi-hop);
  Drive (fuel cost w/ adjustable mileage); Walk. Group + budget inputs. Route cards with score bars,
  per-criterion explanation, Best Match tag, View Steps, Start Journey (GPS), Show All Options.
- SegmentFlowView (centerpiece): 3-column hop window, breadcrumb trail, per-column hop cards, gold
  star top-recommended, client-side `connectedFrom` filtering, downstream reset on earlier change,
  lazy `segment-next` fetch with spinner, map highlight per hop, journey-complete screen with
  timeline, time-of-day advisories, loading skeletons per column.
- NewsPopup: floating LIVE glass panel, pulsing dot, 2-min poll, category borders, dedup max 15.
- TripPanel: AI insight box, Create New Trip, Your Trips, Active Journey, day tabs.
- **Data hygiene**: render exactly what backend sends; no mock/default/fallback sample data; missing
  field → "Unavailable"; always label Estimated/Approx; AbortController to kill stale requests.

---

## 13. ML + INTEGRATION TESTING (PROMPT_7) — PLANNED (spec summary)

- **One real trainable model**: traffic-crowd slowdown index from `traffic_logs.csv`
  (dayofweek × hour × area), LightGBM/XGBoost/MLP → `predict_slowdown(lat,lng,dt)` in [1.0, 1.8];
  honest `time_of_day` fallback labeled `model:"time_of_day"` if data is weak; `model_info()` exposes
  truth. Feeds TOPSIS factor #4 as `max(directions_ratio, predicted_slowdown)`.
- Integration tests (new files listed in the prompt), key ones:
  - Wonderla end-to-end: segments → time chaining → segment-next.
  - Govt School → MG Road multi-bus transfer (507-D → G-9/SBS → 349-K) AND direct G-9.
  - **test_no_fake_data.py** — scans all payloads for fabricated route numbers/fares/reviews/prices.
  - Live-failure resilience (all stubs raising → still ≤6s, no fake values).
  - Reliability determinism; TOPSIS monotonicity; graph forward-progress correctness.
- Performance verification table (see §22). `scripts/benchmark.py`.

---

## 14. TRIP PLANNER (PROMPT_8) — PLANNED (design locked in grilling)

- A destination-and-itinerary system **on top of** the A→B engine. It never re-derives transport —
  it consumes a thin `TripTransportInterface.top1_route(src,dest,time,group,budget) -> TransportHint`
  that the A→B engine implements. **Self-containment rule**: the module defines its OWN contracts,
  does NOT import parent-module types.
- Scope (locked): multi-day 2–5 days; **Bengaluru** = curated ~100-place dataset + live Google Places
  + Reddit/proxy signals; **other cities** = generic Google Places only (missing fields = `Unknown`,
  neutral); stay/accommodation **only for other cities** (Bengaluru local = skip stay); transport
  **on-demand only** (expand hop / start day / plan-between — never at generation); Postgres
  persistence (`DATABASE_URL`); geo-clustered + travel-cost-aware day assignment (no cross-town lap
  days); within-day TSP + time-of-day constraints; LLM only writes "why recommended" lines + summaries.
- Files: `trip_planner.py, trip_places.py, trip_budget.py, trip_assign.py, trip_store.py,
  transport_interface.py, api/trip.py`, data `trip_places_bengaluru.json`.
- Postgres schema (idempotent `CREATE TABLE IF NOT EXISTS`): `trips, trip_days, itinerary_items,
  place_cache` (full SQL in the prompt).
- Guided input flow Steps 1–7 (Destination, Duration, Group, Budget, Interests, Pace, Summary) →
  "Generate My Trip" (engine never runs on partial data).
- Relevance score (deterministic): `0.40*interest_match + 0.25*rating_norm + 0.20*suitability +
  0.10*time_align + hidden_gem_bonus`.
- Budget engine: per-place cost, running day totals widget, overspend alternatives side-by-side with
  deltas (never silent downgrade), surplus → optional upgrades.
- Output: day-by-day timeline, per-day numbered pins with day colors + animated map moves, summary
  donuts + top banner recommendation (LLM sentence).
- Endpoints: `POST /api/trip/plan`, `GET/PUT /api/trip/{id}`, `PUT /api/trip/{id}/items`,
  `POST /api/trip/transport-hint`, `GET /api/trip/places`, `POST /api/trip/places/suggest`,
  `GET /api/trip/{id}/summary`.

---

## 15. DEPLOYMENT (PROMPT_9) — PLANNED (design locked)

- **3 tiers**: Local (full experience — backend:8000, frontend:3000, graphhopper:8080) · **Render**
  (backend + frontend free tier) · Neon Postgres (trips).
- **No GraphHopper on Render** (no Docker on free tier) → walk/drive legs interpolated **flagged**
  "Approx path"; bus legs stay real GTFS shapes; metro real polylines. Honesty table in the prompt.
- **Commit the 67MB `gtfs_cache.pkl`** (≤100MB GitHub limit) so Render cold boot is ~2–3s instead of
  ~45s re-derive. `.gitignore` the raw `bmtc_gtfs/` (~190MB). Rebuild path: `scripts/build_gtfs_cache.py`.
- `render.yaml` for both services; secrets as Render env vars (never `.env` in git).
- Cold-start accepted: frontend shows "Waking up…" splash; optional cron-job.org ping to `/health`.
- DataImpulse proxy works identically from Render (~3.3GB/mo within 5GB pool budget).
- In-memory caches are ephemeral on Render (fine — only Postgres is durable).
- **Demo story**: demo locally for real road paths; point judges at the Render URL for the live public app.

---

## 16. INTEGRATIONS DEEP-DIVE

### 16.1 SerpAPI (Google Maps reviews + ride prices + directions)
- Purpose: real Google Reviews (`user_reviews.most_relevant`), Google Maps search for place_id,
  Google Hotels prices, directions for ride pricing.
- Auth: `SERPAPI_API_KEY` (API-key, no proxy needed). Free tier ~250 searches/mo per key; owner has
  multiple friend keys (~1250/mo).
- **Past critical bug (v1, FIXED in v1 codebase but must not regress)**: `_parse_place_detail()` used
  the wrong response key `"place"` instead of `"place_results"`; reviews read from
  `place_results.reviews` (an **int count**) instead of `place_results.user_reviews.most_relevant`;
  fields were `user.name`/`snippet` instead of actual `username`/`description`.

### 16.2 Google Maps Platform
- APIs enabled: **Places API (New), Geocoding API, Directions/Distance Matrix API**.
- Auth: `GOOGLE_MAPS_API_KEY` (API-key, no proxy).
- Uses (PROMPT_4): search/nearby/details/photos/hours/`business_status`, `duration_in_traffic` for
  the traffic factor.

### 16.3 GraphHopper (road routing — replaces v1's OSRM)
- Local Docker on **8080** (image `israelhikingmap/graphhopper:latest`, car + foot, Karnataka PBF).
- Why not OSRM: v1 used OSRM (5000/5001) with public-URL fallback bugs and OOM issues; v2 spec
  chose GraphHopper. `docker-compose.yml`:
  ```yaml
  services:
    graphhopper:
      image: israelhikingmap/graphhopper:latest
      ports: ["8080:8989"]
      volumes: ["./gh-data:/data"]
      entrypoint: ["bash","-c"]
      command: ["java -Xmx2g -Xms1g -jar graphhopper-web-12.0-SNAPSHOT.jar server /data/config.yml"]
  ```
- Behavior: `route()` returns `None` on any failure → caller interpolates and FLAGS it. 24h cache.

### 16.4 DataImpulse proxy (scraping — news, DDG fallback, review scans)
- Credentials: `DATAIMPULSE_USER/PASS/HOST` (default `gw.dataimpulse.com:823`).
- Pools: Datacenter 10GB/$5, Mobile 2.5GB/$5, Residential 5GB/$5 (owner can afford ~$5).
- **Where used (v1 reality)**: ddg_scraper (Tier 2), news_scraper (Times of India/The Hindu),
  justdial_scraper (tried, site blocked → **DROPPED** in v2 spec). Uber/Ola/Rapido scraping attempted
  but blocked → v2 uses formula + SerpAPI instead.
- **v2 rule**: proxy for IP-blockable targets (news, DDG, review scans); NEVER for API-key services.

### 16.5 OpenRouter / Gemini (LLM)
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL=openai/gpt-4o-mini`, `GEMINI_API_KEY`.
- Allowed: summaries, explanations ("why recommended"), plain-Hinglish route explanations, news
  summarization, sentiment judgment (fallback). **Never**: fares, timings, bus numbers, review text,
  reliability scores, or any number. If all LLMs fail → deterministic fallback text with raw numbers.

### 16.6 Open-Meteo (weather)
- Free, no key. Current + hourly/forecast at route coords. Cache 15 min. Feeds TOPSIS weather factor
  + header widget. `GET /api/search/weather?lat=&lng=`.

### 16.7 eRail.in (live trains)
- Scraped API for 22 Karnataka station codes (SBC, BNC, YPR, MYS, UBL, MAQ, BGM, BAY, SMET, DVG,
  HAS, GR, BJP, HPT, UD, CTA, TK…). 7 city-pair fallbacks flagged `source:"fallback"`.

### 16.8 Reddit (news + place signals)
- r/bangalore JSON API (no proxy). News loop input + trip-planner qualitative hints (low confidence,
  merged as minor adjustments, never hard facts).

---

## 17. THE HOP MECHANISM EXPLAINED (segment builder internals)

This is what the owner cares about most. How it works, end to end:

### 17.1 The model: a tree of choices, NOT a single line
`build_segments(source, destination, group_size, budget, current_time)`:
1. **Segment 1** — from the source, enumerate every sensible "get out of here" option:
   - Walk options to any bus/metro stop within 2km (free). If the closest walk target ≤1.5km,
     that walk is **top-recommended** and no cab/bike is offered.
   - Transit options: for each boarding stop within 1500m (up to 3 bus stops + 2 metro stations),
     take the **real GTFS next departures** (within 180-min window, ≤4 routes/stop, ≤3 arrival stops
     per route) and ride to forward-progress arrival stops.
   - Plus **metro-transfer rides**: for every available route at the stop, look beyond the first few
     stops for a far-forward stop near a metro station (≤1500m) and offer the full long-haul ride to
     that interchange (`isMetroTransfer:true`) — e.g. "285 → Kempegowda Bus Station, then metro".
2. **Segment 2** — from the distinct arrival stops of Segment 1 (earliest first, ≤6 anchors, ≤40
   options), enumerate onward options using the SAME logic, each tagged `connectedFrom` = its parent
   stop name, with departures **time-chained** (≥ parent arrival + 4 min buffer).
3. **Probes** — for the level after Segment 2, a cheap single onward suggestion per option
   (`isProbe:true`), so the UI shows what could come next.
4. **`segment-next`** — when the user confirms a leg, rebuild the next segment from that exact stop
   at that exact arrival time (correctness for deep hops).

### 17.2 The hard rules that make it correct (all verified by tests)
- **Forward-progress**: `hav(arrival → dest) < hav(anchor → dest) + tol` (500m normal, 2500m metro).
  A user is never routed away from the destination. Test asserts this on every non-walk option.
- **No circular routing**: 800m visited guard in the route finder; candidates within 25m of the
  anchor are dropped (no zero-distance walks).
- **Real data only**: bus options come from `earliest_departures()`/`get_routes_at_stop()` (real GTFS
  route numbers + times). If a stop has no GTFS service → no transit options (walk may still appear).
- **No full-route spiderwebs**: bus geometry = `get_stop_to_stop_segment()` slice. The "draw the whole
  40km route" bug is explicitly banned.
- **Short-hop rule**: ≤1.5km → walk primary, no cab/bike; ≤2km → walk option always present.
- **Time chaining**: Segment N departures ≥ previous arrival + buffer. Test: `dep_min >= arr_min + 4`.
- **connectedFrom chains exactly**: every Segment-2+ option's `connectedFrom` is a real Segment-1
  arrival stop (test asserts this).
- **Budget**: `exceedsBudget` flag (grey out), never silent drop (test asserts walk never exceeds and
  paid options flag correctly).
- **Metro hubs**: nodes at Majestic carry both lines; both directions offered (test: Purple AND Green
  from KBS). Metro rides to MG Road corridor have real distance/duration.
- **Long-haul bus→metro**: 285 from Rajanukunte rides directly to the Majestic area (test asserts
  `distanceKm > 10`, `durationMin > 30`, real geometry slice, chains into metro).
- **Cache**: `segments` cached 5 min keyed `(r4 coords × 2, 10-min time bucket, group, budget)`.
  Test: second call <50ms, identical result.

### 17.3 The frontend contract for this window (PROMPT_6 §9)
- Breadcrumb: `Source → [bus 507-D] → Kogilu Cross → [KIA-9] → Majestic → [Purple] → ... → Destination`.
- Columns render from `/api/routes/segments`; selecting a hop filters the NEXT column client-side by
  `connectedFrom`; changing an earlier column **resets downstream selections** (no ghost paths);
  deeper columns lazily call `segment-next`; confirmed hops accumulate geometry on the map;
  `journeyComplete` shows the arrival screen with full timeline + total + reset.

---

## 18. DATA SOURCES & DATASETS INVENTORY

| File | Size | Content | Used by |
|---|---|---|---|
| `bmtc_gtfs/` (11 .txt) | ~190MB | Official BMTC GTFS: stops, routes, trips, stop_times, shapes, calendar, fare_attributes/rules | raw-load cold path only (NOT committed) |
| `processed/gtfs_cache.pkl` | 67MB | 7271 shapes, 5077 stops, 429882 stop-times, `name_map` | **committed**, reused at startup (0.65s) |
| `bmtc_all_stops_master.csv` | 2MB | ~2972 bus stop names + coords + route lists | stop DB + name resolution |
| `bengaluru_metro_network.csv` | 8KB | Purple + Green stations, edges, dist | metro nodes/edges (NO Blue/Yelahanka) |
| `kia_routes_fare_full.json` | 22KB | KIA Vayu Vajra routes + fares | KIA bus options |
| `transit_fares.json` | 3.5KB | BMTC AC/nonAC + metro slabs | fare engine |
| `karnataka_railway_stations.json` | 2.8KB | 22 Karnataka rail codes | rail nodes; live via eRail.in |
| `traffic_logs.csv` | 7.5MB | Quarterly traffic/crowd data | ML model (PROMPT_7), NOT routing |

---

## 19. EVERYTHING ACHIEVED & CORRECTED SO FAR (session log)

Git log (main, newest first) tells the v2 story:

- **PROMPT_6 session (frontend)** — `frontend/` scaffolded (Vite react-ts), `index.css` glassmorphism
  design system, `types/index.ts` contracts, `services/api.ts` typed client, `context/AppContext.tsx`
  global state, `MainPage` (3-tab bottom-nav), `HeaderBar` (clock/weather/dark), `MapView` (Leaflet
  pins/polylines/flyTo), `SearchPanel`, `DiscoveryPanel` (+ `/api/search/photo` proxy 307-verified),
  `AToBPanel` (+ SegmentFlowView), `SegmentFlowView` (3-column hop window, breadcrumb, lazy
  segment-next, map pan, complete screen), `TripPanel` (GPS journey), `NewsPopup` (LIVE 2-min poll),
  `vite.config.ts` `/api` proxy → `VITE_API_BASE`. Verified: build clean, dev server + proxy + 84
  backend tests all green.
- **PROMPT_5 session (live layer)** — weather client (Open-Meteo), news engine (r/bangalore +
  DDG/DataImpulse background loop, classify/geo-tag/summarize), `proxy_manager.py`, eRail train
  scraper, `backend/services/langgraph/` package (VoyagerLangGraph: intent, parallel dispatch,
  synthesis, route-context workflow), 5 new endpoints. **84 tests pass.**
- **PROMPT_4 session (search/scoring)** — `google_maps_client.py` (Places New/Geocoding/Directions),
  reliability formula + `_score_from_rating` (never trusts external), SerpAPI review chain (real
  `user_reviews.most_relevant`), local sentiment, `topsis_engine.py` (8-factor numpy, `TopsisWeights`),
  `ride_pricing.py` (SerpAPI live + Karnataka govt formula), search/nearby/enrich/verify/reviews/
  ride-prices endpoints.
- **PROMPT_3 era commits** (segment builder):
- `9c631bd` — Offer long-haul bus→metro rides on ALL routes (fix capped-route skip) + fix
  reverse-shape duration slice producing 1-min stubs; add Rajanukunte direct-285-to-Majestic
  regression test (**36 tests pass**).
- `523197c` — Add long-haul bus→metro interchange rides: 285 from Yelahanka now offered directly to
  Kempegowda Bus Station (Majestic), then Purple metro to MG Road (2 hops, ₹60); regression test (35).
- `18c5c8c` — Fix metro interchange options: split combined hub lines, dedup metro stations, cap
  forward walk at 16, fix metro path prefix double-bug; regression test (34).
- `5aadb08` — **Build PROMPT_3 segment builder API**: interactive hop planner (`segments` +
  `segment-next`), FastAPI app (main/api), 5-min cache, 11 acceptance tests (T1–T4, chaining,
  journey-complete, budget).
- `2e2b8ff` — **Build PROMPT_2 routing graph + N-hop route finder**: full GTFS bus topology (5077
  nodes), metro/rail, grid walk edges, best-first A* with schedule resolution.
- `a456261` — Apply route-name cleaning at GTFS pickle load (9 leaked suffix names), re-save pickle.
- `bfaa8b0` — Wire Neon `DATABASE_URL` + run GraphHopper (Bangalore crop, car+foot): fix duplicate
  point param bug, add docker-compose + config.
- `b48de93` — **Build PROMPT_1 data layer**: GTFS loader (pickle reuse, name resolution,
  shape-projected segments), fare engine, station DB, GraphHopper client.
- `b940991` — Add VOYAGER v2 fresh-build PROJECT folder: 9 build prompts, data assets, GTFS pickle.
- (older) — v1 history: monolith fixes, SerpAPI key fix, ride pricing real rates, per-person bug,
  name-resolution perf (79s→7.7s), geodesic→haversine (graph 11.6s→2.2s), GTFS startup lazy,
  OSRM foot OOM, metro direction filter, 800m circular guard, 55MB unused datasets deleted, etc.

Current working-tree state (in `PROJECT/`):
- PROMPT_4/5 backend modules + `frontend/` are uncommitted/new; `gtfs_cache.pkl` re-saved (route-name
  cleaning). Everything else committed. All 84 tests + frontend build green.

Verified end-to-end example journeys (from tests, real GTFS):
- **Yelahanka 4th Phase (Govt School) → MG Road**: 285 bus → Kempegowda Bus Station (Majestic),
  then Purple metro → Mahatma Gandhi Road = **2 hops, ₹60**.
- **Rajanukunte → Cubbon Park**: direct 285 ride to Majestic corridor, then metro = ₹41.
- **Govt School → Wonderla**: the classic multi-hop (507-D → Kogilu Cross, KIA-9 → Majestic, Purple →
  Challaghatta, walk → 231 → Wonderla) is the acceptance target; the tree offers real chained options.
- **MG Road → Koramangala**: bus↔bus transfer paths via walk edges (route finder).

---

## 20. TESTS & QA

Current: **84 tests pass** (`pytest tests/ -q` in ~47s, no Docker/API required).

| File | Covers |
|---|---|
| `test_fare_engine.py` (~15) | BMTC/metro/KIA fares, surge windows, ride per-person split, ride type ranges |
| `test_segment_builder.py` (~8) | segment builder integration paths (bus→metro, fares, real GTFS) |
| `test_prompt4.py` | search/verify/enrich/reviews/reliability/sentiment/TOPSIS/ride pricing contracts |
| `test_prompt5.py` | weather/news/train/langgraph live layer contracts |

QA commands:
- Backend tests: `python -m pytest tests/ -q` (in `PROJECT/`) → **84 passed**
- Backend compiles: `python -c "from backend.api.routes import search_photo; print('ok')"`
- Frontend: `cd frontend; npx tsc -b` and `npm run build` → 0 errors
- Server: `python -m uvicorn backend.main:app --port 8000` → health `GET /api/health`
- Dev frontend: `cd frontend; npx vite --port 3000` → `GET http://localhost:3000/` 200, `/api/*` proxied

---

## 21. KNOWN PROBLEMS, HONEST-FALLBACKS, DELIBERATE DECISIONS

1. **BMTC has no live API.** Every bus time is a **schedule** time, labeled `source:"schedule"` /
   status `scheduled`. Never pretend live.
2. **14 bus stop names have no GTFS match** (acronyms like `hnrj`, `ggmc`). They resolve to `None` →
   "No real-time data", never a fabricated match.
3. **Uber/Ola/Rapido block scrapers.** v2 uses SerpAPI directions when available + Karnataka
   govt-mandated formula, both **labeled estimated** when not live.
4. **JustDial is dropped.** Confirmed non-functional; place verification uses Google Places +
   SerpAPI instead (PROMPT_5 decision).
5. **Metro Yelahanka / Blue Line don't exist yet** — excluded everywhere. Only Purple + Green.
6. **GraphHopper down / not deployed** → walk/drive legs interpolated and **flagged**; bus/metro legs
   stay real (GTFS shapes / line polylines).
7. **Trains**: only shown when eRail.in has real data; fallback city-pairs flagged. Never invented.
8. **Reviews**: never LLM-generated. Real SerpAPI + local sentiment; LLM only summarizes.
9. **Reliability score**: always recomputed from live inputs; never trusts an external field.
10. **Render free tier**: no Docker → no GraphHopper; ephemeral disk → Postgres for durable data;
    cold starts → "Waking up…" splash.
11. **Budget overrun** → `exceedsBudget` grey-out (never silent omit, so the user understands why).
12. **Interpolated geometry** is always visually distinguished (dashed + "approx path").

---

## 22. PERFORMANCE BUDGETS & CURRENT BENCHMARKS

| Operation | Budget (spec) | Current v2 measured |
|---|---|---|
| GTFS load from pickle | ≤1s | **0.65s** |
| Name pre-resolve (first run) | — | **7.7s** (then 0s from pickle `name_map`; 1696/2972 cached) |
| A* graph build | ≤3s | **~2.2s** (2000+ bus / 68 metro / ≥22 rail nodes, ~54k edges) |
| Server startup | ≤3s | ~3s (lazy) |
| `segments` first call warm | ≤3s | test asserts <3s |
| `segment-next` warm | ≤2s | ✓ |
| Route finding warm | ≤5s | test asserts <5s |
| Spatial query | ≤5ms | test: <0.005s avg |
| `segments` cache hit | — | <50ms (test) |
| Route-plan cache hit | ≤100ms | ✓ (10-min TTL) |

---

## 23. DOCKER & LOCAL RUN GUIDE

```powershell
# 1) GraphHopper (car + foot, Karnataka PBF). First start builds ~a few min.
cd PROJECT
docker compose up -d graphhopper          # port 8080

# 2) Backend
cd PROJECT
python -m uvicorn backend.main:app --reload --port 8000
#    → GET http://localhost:8000/api/health   → {"status":"ok","services_loaded":true}
#    → POST /api/routes/segments  |  POST /api/routes/segment-next

# 3) Frontend (when PROMPT_6 lands)
cd frontend; npx vite --port 3000

# 4) Tests
python -m pytest tests/ -q                # 36 passed
```

docker-compose.yml is **graphhopper only** (backend/frontend run locally per spec; OSRM from v1 is
no longer used — don't start it for v2).

---

## 24. SECRETS & ENVIRONMENT VARIABLES

`.env.example` (committed) — real values go in `.env` (never committed):
```
OPENROUTER_API_KEY / OPENROUTER_MODEL=openai/gpt-4o-mini / GEMINI_API_KEY
GOOGLE_MAPS_API_KEY
SERPAPI_API_KEY
DATAIMPULSE_USER / DATAIMPULSE_PASS / DATAIMPULSE_HOST=gw.dataimpulse.com:823
DATABASE_URL=postgresql://user:pass@host/voyager?sslmode=require
FUEL_PRICE_PER_LITER=110.0
PETROL_AVG_MILEAGE=15.0
VOYAGER_TEST_TIME=            # optional time override for testing
```
`config.py` reads `.env` via python-dotenv at import; `DATABASE_URL` currently loaded but unused
until PROMPT_8. `GRAPHOPPER_BASE_URL` is defaulted to `http://localhost:8080` in the client.

---

## 25. WHAT TO DO NEXT (recommended order)

1. **PROMPT_7 — ML + integration tests + `test_no_fake_data.py`** audit. One real trainable model
   (traffic-crowd slowdown from `traffic_logs.csv` → `predict_slowdown`), integration tests incl.
   Wonderla end-to-end, `test_no_fake_data.py` (scans all payloads for fabricated route numbers/
   fares/reviews/prices), performance verification table + `scripts/benchmark.py`.
2. **PROMPT_8 — Trip Planner** (A→B engine must implement `TripTransportInterface.top1_route`).
3. **PROMPT_9 — Deploy to Render + Neon**, commit the pickle, verify the checklist.
4. Long-running reminders: keep GraphHopper only local; never reintroduce OSRM; never let the LLM
   write numbers; keep every fallback labeled; run `pytest tests/ -q` + frontend `tsc -b` before every
   commit.

---

## 26. APPENDIX A — API ENDPOINTS

**Implemented (v2):**
```
GET  /api/health
POST /api/routes/segments        → Segment 1 FULL + Segment 2 FULL + probes
POST /api/routes/segment-next    → next segment time-chained from chosen leg
GET  /api/search/places           (PROMPT_4)
GET  /api/search/nearby           (PROMPT_4)
GET  /api/search/suggestions      (PROMPT_4)
GET  /api/search/verify-place     (PROMPT_4)
GET  /api/search/reviews          (PROMPT_4)
GET  /api/search/ride-prices      (PROMPT_4)
POST /api/search/enrich-place     (PROMPT_4)
GET  /api/search/photo?name=…     (PROMPT_6 photo proxy → 307 to real Google photo URL)
GET  /api/search/weather?lat=&lng= (PROMPT_5 Open-Meteo)
GET  /api/search/news?lat=&lng=   (PROMPT_5 background loop)
GET  /api/routes/live-trains      (PROMPT_5 eRail)
GET  /api/routes/transit-fares | live-prices | metro-stations | bus-stops (PROMPT_5)
POST /api/langgraph/ask           (PROMPT_5)
POST /api/langgraph/route-context (PROMPT_5)
```

**Planned (per prompts):**
```
GET  /api/routes/traffic-overlay           (PROMPT_7)
GET  /api/routes/traffic-model-info        (PROMPT_7)
POST /api/trip/plan                                (PROMPT_8)
GET  /api/trip/{id}  ·  PUT /api/trip/{id}/items
POST /api/trip/transport-hint
GET  /api/trip/places?city=&interests=&limit=
POST /api/trip/places/suggest
GET  /api/trip/{id}/summary
```

---

## 27. APPENDIX B — KEY CONSTANTS

**Graph (transit_graph.py):** BUS_SPEED 18 km/h, METRO_SPEED 36, WALK_SPEED 5, TRANSFER_PENALTY 4 min,
BUS_DWELL 0.3, METRO_DWELL 0.25, INTERCHANGE_FIXED 5 min; walk radii bus↔bus 500m, bus↔metro 1000m,
bus↔rail 3000m.

**Route finder (route_finder.py):** entry radii bus 2km / metro 3km / rail 5km; entry tops 3/2/1;
MAX_LEGS 6, MAX_PATHS 12, MAX_DUP_PER_SIG 3; VISITED_RADIUS 800m; FORWARD_TOL 500m / metro 2500m;
BUDGET_SENSITIVITY ₹8/min; search deadline 4s; BUFFER 3 min; MAX_WAIT 45 min; WALK_ONLY_KM 2.0;
cache TTL 600s.

**Segment builder (segment_builder.py):** bus/metro candidate radius 3000m, rail 5000m; walk-to-board
1500m; forward tol 500m/2500m; BUFFER 4 min; DEP_WINDOW 180 min; caps: 5 walk, 3 bus board, 2 metro
board, 4 routes/stop, 3 arrival stops/route, 2 metro-transfers, 6 seg2 anchors, 40 seg2 options,
6 probes; WALK_OPTION_MAX 2000m; WALK_PRIMARY 1500m; cache TTL 300s.

**Fares:** BMTC nonAC slabs; AC slabs; metro slab; KIA per-stop max; rides UberGo/OlaMini 24/km(min85),
XL 32/km(min130), Auto 20/km(min40), Rapido 5/km(min25); surge 1.2/1.5/1.8.

---

## 28. APPENDIX C — ERROR GLOSSARY (past bugs — do NOT regress)

1. **OSRM public URL** (`router.project-osrm.org`) used instead of local — all paths became
   interpolated straight lines. v2 uses GraphHopper local.
2. **LLM-generated fake reviews** with fake Indian names when scraping failed. **Banned** — no LLM
   review text ever.
3. **Ride price `total = pp * group`** double-charged a vehicle fare by passenger count.
   Correct: `total = vehicle_fare`, `pp = total / group`.
4. **GTFS route garbage** `"MF-28 JKLO-ISROQ-LGRNB"` uncut. Fixed by `clean_route_short_name`.
5. **`_gtfs` import-by-value bug** — `from transit_config import _gtfs` captured `None` at load;
   every GTFS call returned empty. v2 uses `app_state` live singletons.
6. **geodesic in hot loops** → 11.6s graph build. v2: haversine + `_dist_cache` → 2.2s.
7. **SequenceMatcher loop** → 79s name pre-resolve. v2: word-overlap + trigram `get_close_matches` → 7.7s.
8. **Aggressive metro direction filter** (`dest_to_dm > nm_dist_to_dest * 1.1`) blocked valid routes
   (Cubbon Park→MG Road). v2 uses absolute +tolerance.
9. **300m circular guard** let routes loop. v2: 800m.
10. **Full-route shape fallback** drew the entire bus route (40km lines) instead of stop-to-stop
    slices. v2: `get_stop_to_stop_segment()` only.
11. **GTFS 41s startup block.** v2: lazy via `app_state`.
12. **Hardcoded dark hexes** in components (theme clash). v2 rule: CSS variables only.
13. **Shape-slice stub** — reverse-shape duration slice produced 1-min stubs on long rides (285).
    Fixed in `9c631bd` (real duration for long reverse rides).
14. **Metro path prefix double-bug** — interchange path built with a duplicated prefix node.
    Fixed in `18c5c8c`.
15. **Capped-route skip** — routes whose transfer stop lay beyond the first few stops were dropped.
    Fixed in `9c631bd` (metro-transfer search over ALL routes).
16. **`justdial_scraper` site blocking** → DROPPED in v2; verified alternatives (Places + SerpAPI).

---

*End of VOYAGER v2 Master Knowledge Base.*
