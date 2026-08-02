# VOYAGER v2 — MASTER KNOWLEDGE BASE (COMPLETE)

> **Purpose:** A single, complete, plain-language reference for the ENTIRE VOYAGER v2 project.
> This file is the source of truth. Read it fully before starting any future work session.
> It explains: what the product is, the non-negotiable rules, the full 9-prompt roadmap (done +
> pending), every backend module with exact contracts, every frontend component, every dataset,
> every integration and WHY we chose it, the proxy system, the hop/segment mechanism in deep
> detail, every problem we hit and the better option we chose so it never regresses, all 84
> tests, performance budgets, the Docker setup, and exactly what to do next.
>
> Written: 2026-08-01. Last updated: 2026-08-01 (PROMPT_1–6 DONE, 84 tests green).
> Source of truth: `C:\Users\len\OneDrive\Desktop\VOYAGER\PROJECT\`
> Git repo root: `C:\Users\len\OneDrive\Desktop\VOYAGER` (the parent dir — `PROJECT/` is the
> v2 build folder; git commits are made from the parent root and always touch only `PROJECT/`).

---

## TABLE OF CONTENTS

1. How To Read This File (mental model)
2. The Elevator Pitch (what VOYAGER is)
3. The Non-Negotiable Product Rules
4. The Golden Build Rule (most important thing)
5. Tech Stack & Ports
6. Directory Map (full current tree)
7. The Roadmap — 9 Build Prompts, status table
8. Architecture Overview (how all the pieces fit)
9. PROMPT_1 — Data Layer (DONE)
10. PROMPT_2 — Routing Graph + Route Finder (DONE)
11. PROMPT_3 — Segment Builder API, the Hop Mechanism (DONE)
12. PROMPT_4 — Search, Reliability, TOPSIS (DONE)
13. PROMPT_5 — LangGraph Live Layer (DONE)
14. PROMPT_6 — Frontend (DONE)
15. Integrations Deep-Dive (SerpAPI, Google Maps, GraphHopper, Open-Meteo, eRail, Reddit, OpenRouter/Gemini, DataImpulse) — WHY each was chosen
16. The Proxy System (DataImpulse) — exactly when it is used and never used
17. Data Sources & Datasets Inventory
18. Environment Variables & Secrets
19. Everything Achieved & Corrected So Far (session log)
20. Problems → Better Options Chosen (error glossary, do-not-regress)
21. Tests & QA (all 84, per file)
22. Performance Budgets & Benchmarks
23. Docker & Local Run Guide
24. What To Do Next — PROMPT_7, 8, 9 in detail
25. Appendix A — Full API Endpoint Reference
26. Appendix B — Key Constants (radii, speeds, fares, budgets)
27. Appendix C — Honest-Fallbacks & Deliberate Decisions (the "no fake data" map)

---

## 1. HOW TO READ THIS FILE (mental model)

This project is built **fresh** from scratch (`PROJECT/`), prompt-by-prompt, in strict order:
PROMPT_1 (data) → PROMPT_2 (graph) → PROMPT_3 (segment builder) → PROMPT_4 (search/scoring) →
PROMPT_5 (live layer) → PROMPT_6 (frontend) → PROMPT_7 (ML/testing, NEXT) → PROMPT_8 (trip
planner) → PROMPT_9 (deploy).

The mental model is a pipeline:

```
DATA (GTFS, metro, rail, fares, logs)
   → GRAPH (bus/metro/rail nodes + walk edges)
   → ROUTE FINDER (best-first A* N-hop search)
   → SEGMENT BUILDER (tree of hop choices — the centerpiece)
   → SEARCH & SCORING (Google Places + SerpAPI reviews + reliability + TOPSIS)
   → LIVE LAYER (LangGraph gathers weather/traffic/news/prices/trains in parallel)
   → FRONTEND (React/TS + Leaflet, dumb renderer, glassmorphism)
   → TRIP PLANNER (PROMPT_8, on top of A→B)
   → DEPLOY (Render + Neon, PROMPT_9)
```

Every stage feeds the next. Each PROMPT's section below documents: **what was built, the exact
file, the exact contract (field names / numbers), the tests that prove it, and the problems we
fixed so they never regress.**

---

## 2. THE ELEVATOR PITCH (what VOYAGER is)

**VOYAGER** is a Bengaluru-first "everything you need to move around" travel/navigation app:

- **SEARCH** — find a place, or find things *nearby* (ATM, mall, petrol pump, cafe…), with
  **real Google reviews**, a **reliability score** (green/yellow/red pill), photos, hours, and
  prices for hotels — because Google Maps results are full of dead/fake/wrong locations.
- **A→B** — plan a trip from A to B **three ways**:
  - **Public/Online** → either a **Direct Ride** (Uber/Ola/Rapido/Auto cards with live or
    estimated prices + ETA) or a Google-Maps-like **multi-hop transit segment window** with real
    BMTC bus numbers, scheduled times, Namma Metro Purple/Green, KIA airport buses, walk
    transfers. The multi-hop window is the **centerpiece**: the user picks their own hop-by-hop
    journey, and every hop is *real* — real bus numbers, real scheduled departure times, real
    geometry, real fares.
  - **Drive** → real road-following path + live petrol cost (₹/litre ÷ mileage).
  - **Walk** → road-following or interpolated path, free.
- **TRIP** (PROMPT_8) — a multi-day destination-and-itinerary planner (2–5 days) with budget,
  interests, pace, geo-clustered day assignment, per-day map pins, on-demand transport, and
  Postgres persistence.

**Non-negotiable product rules (from the owner):**
- **No fake data. Ever.** No fabricated bus numbers, timings, fares, reviews, reliability scores,
  news headlines, or prices. If a real source has no data, show nothing or an explicitly labeled
  "Estimated / Approx / Unavailable" state — never invent.
- The backend does **100% of the thinking**. The frontend is a dumb renderer + local filter.
- Real Google Maps quality: "Govt School → Wonderla = take 507-D → Kogilu Cross, then KIA-9 →
  Majestic, then Purple metro → Challaghatta, then walk → 231 bus → Wonderla." That exact kind of
  journey, segmented, with choices at every level.
- Every ride/path/pricing label: **Live vs Estimated** (SerpAPI live = Live; formula = Estimated).
- Only operational metro: **Purple + Green**. **NO Blue Line, NO Yelahanka** (under construction).

---

## 3. THE NON-NEGOTIABLE PRODUCT RULES (owner's words, locked)

1. **No fake data ever.** Real bus numbers, real schedules, real fares, real reviews, real
   prices, real news. If unavailable → show "Unavailable / Estimated / Approx" clearly labeled.
2. **LLM never writes numbers.** No fares, timings, bus numbers, review text, reliability scores,
   news headlines, or prices come from the LLM. The LLM only *summarizes* and *explains*.
3. **Backend is the source of truth.** Frontend never computes transport, prices, or scores.
4. **Live vs Estimated labeling** on every ride/path/price.
5. **Metro = Purple + Green only.** Yelahanka / Blue line don't exist yet.
6. **Every fallback is labeled.** Interpolated geometry is dashed + "approx path"; fallback
   train schedules say "NOT live"; degraded services say "Unavailable".
7. **Dumb renderer frontend.** Data hygiene: missing field → "Unavailable", never a mock value.

These rules are enforced by tests (especially PROMPT_7's `test_no_fake_data.py`, planned) and by
code review discipline documented in §20.

---

## 4. THE GOLDEN BUILD RULE (READ EVERY TIME)

> **The current v2 is built FRESH inside `C:\Users\len\OneDrive\Desktop\VOYAGER\PROJECT\`.**
>
> The **parent** `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`,
> `stitch_omnipath_ai_navigation/`, `data_cache/`, and the parent `tests/` incl.
> `test_fare_engine.py`) is **REFERENCE-ONLY for past mistakes**. NEVER import code from it,
> never read it to "implement", never "fix" it. All code, decisions, and data contracts come from
> the `PROMPT*.md` files in `PROJECT/` + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or
> old bugs.
>
> Git: the repo root is the parent `VOYAGER` dir (so commits are made there), but **only
> `PROJECT/` files are ever staged/committed**. Legacy parent dirs are untracked/ignored.

This is the single most important instruction in the whole project. The parent repo is a 2400-line
monolith that was full of bugs (see §20). The v2 was created specifically to rebuild cleanly.

---

## 5. TECH STACK & PORTS

| Component | Tech | Port | Notes |
|---|---|---|---|
| Backend | FastAPI (Python 3.12, uvicorn) | **8000** | `python -m uvicorn backend.main:app --reload --port 8000` |
| Frontend | Vite + React 19 + TypeScript + Leaflet/react-leaflet 5 | **3000** | ✅ BUILT (PROMPT_6); `cd frontend; npx vite --port 3000` |
| GraphHopper | Local Docker (car + foot) | **8080** | Karnataka PBF, see `docker-compose.yml`; real road paths |
| OSRM (legacy) | Local Docker (car / foot) | 5000 / 5001 | **v1 ONLY** — v2 does NOT use OSRM. Never reintroduce it. |
| Postgres | Neon (free hosted) via `DATABASE_URL` | — | Trips persistence (PROMPT_8), loaded but unused until then |
| Open-Meteo | free API (no key) | — | weather |
| SerpAPI | API key | — | real reviews + live ride prices |
| Google Maps Platform | API key | — | Places (New), Geocoding, Directions |
| DataImpulse | proxy (IP rotation) | gw.dataimpulse.com:823 | news / DDG / review scrapes |
| OpenRouter / Gemini | API key | — | LLM summaries only |

Frontend deps (`frontend/package.json`): `react ^19.2.8`, `react-dom`, `leaflet ^1.9.4`,
`react-leaflet ^5.0.0`, `axios ^1.19.0`, `@types/leaflet`, dev: `typescript ~6.0.2`, `vite ^8.2.0`,
`@vitejs/plugin-react ^6.0.4`, `oxlint`, `@types/*`. Scripts: `dev` (vite), `build`
(`tsc -b && vite build`), `lint` (oxlint), `preview`.

Backend deps (`requirements.txt`): `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `pydantic>=2.7`,
`python-dotenv>=1.0`, `requests>=2.31`, `psycopg[binary]>=3.1`, `httpx>=0.27`.

---

## 6. DIRECTORY MAP (full current tree)

```
PROJECT/                                          ← THE v2 BUILD ROOT
├── PROMPT.md                     # Master vision (Hinglish, raw)
├── FEATURES.md                   # Feature summary
├── ABOUT_GRAPHHOPPER.md          # Design doc that PROMPT_3 corrected
├── "trip planer prompt.md"       # Notes from the trip-planner grilling session
├── MASTER_KNOWLEDGE_BASE.md      # THIS FILE
├── AGENTS.md                     # Short session cheat-sheet (auto-loaded by opencode)
├── docker-compose.yml            # graphhopper ONLY (8080)
├── requirements.txt
├── .env.example                  # All 12 keys documented (committed)
├── .env                          # REAL secrets — NEVER committed
├── PROMPTS/                      # The 9 build prompts (specs)
│   ├── PROMPT_1_DATA_LAYER.md            … PROMPT_9_DEPLOYMENT.md
├── DATA_FOLDER/                  # Static datasets (see §17)
│   ├── bmtc_gtfs/                # Raw GTFS .txt (11 files, ~190MB, NOT committed)
│   ├── processed/gtfs_cache.pkl  # 76MB pickle — COMMIT THIS (cold boot)
│   ├── bmtc_all_stops_master.csv # ~2972 stops
│   ├── bengaluru_metro_network.csv
│   ├── karnataka_railway_stations.json
│   ├── kia_routes_fare_full.json
│   ├── transit_fares.json
│   └── traffic_logs.csv          # 7.5MB, for ML (PROMPT_7)
├── backend/
│   ├── main.py                   # FastAPI app, lifespan → app_state.ensure_loaded()
│   ├── config.py                 # Paths + env helpers
│   ├── api/routes.py             # ALL endpoints (see Appendix A)
│   ├── agents/
│   │   ├── llm_agent.py          # OpenRouter→Gemini chain, chat_json() only
│   │   └── review_summarizer.py  # LLM review summary + concerns (never invents)
│   └── services/
│       ├── app_state.py          # Lazy singletons (9 services)
│       ├── data_schema.py        # Pydantic models (single source of truth)
│       ├── gtfs_service.py       # GTFS loader/cache/fuzzy-name-resolution
│       ├── fare_engine.py        # BMTC/AC/metro/KIA/ride fares + surge
│       ├── database.py           # In-memory station DB + spatial index
│       ├── graphhopper_client.py # HTTP client for local GraphHopper (8080)
│       ├── transit_graph.py      # TransitAstarGraph (static topology)
│       ├── transit_models.py     # Leg, RoutePlan dataclasses
│       ├── route_finder.py       # Best-first top-K N-hop route search
│       ├── segment_builder.py    # THE HOP MECHANISM (tree of choices)
│       ├── search_service.py     # Search orchestrator (Places + SerpAPI + scoring)
│       ├── reliability.py        # reliability formula + pin classes
│       ├── sentiment.py          # lexicon + optional HF distilbert sentiment
│       ├── topsis_engine.py      # 8-factor numpy TOPSIS (TopsisWeights)
│       ├── ride_pricing.py       # estimate ladder + live merge
│       ├── review_tools.py       # SerpAPI review chain + AI summary + cache
│       ├── news_engine.py        # background news loop (Reddit + DDG, classify/geo)
│       ├── proxy_manager.py      # DataImpulse proxy helper
│       ├── train_service.py      # eRail.in live trains
│       ├── clients/
│       │   ├── google_maps_client.py  # Places(New)/Geocoding/Directions/photo
│       │   ├── serpapi_client.py      # reviews/place-details/directions (place_results fix)
│       │   └── weather_client.py      # Open-Meteo current + rain window
│       └── langgraph/
│           ├── agent.py          # VoyagerLangGraph (parallel gather + synthesis)
│           ├── state.py          # RouteContextState / AskState dataclasses
│           ├── tools/            # news, pricing, review, search+geo, traffic, train, weather
│           └── workflows/route_context.py  # delegate to agent
├── frontend/                     # PROMPT_6 (Vite + React + TS + Leaflet)
│   ├── index.html                # Inter + Material Symbols, title "VOYAGER v2"
│   ├── vite.config.ts            # :3000, /api proxy → VITE_API_BASE
│   ├── src/
│   │   ├── main.tsx / App.tsx    # AppProvider + WeatherLoader
│   │   ├── index.css             # glassmorphism design system (see §14.11)
│   │   ├── context/AppContext.tsx# global state (see §14.1)
│   │   ├── services/api.ts       # typed axios client (see §14.2)
│   │   ├── types/index.ts        # all TS contracts (see §14.3)
│   │   ├── pages/MainPage.tsx    # 3-tab shell + layout
│   │   └── components/           # HeaderBar, MapView, SearchPanel, DiscoveryPanel,
│   │                             # AToBPanel, SegmentFlowView, TripPanel, NewsPopup
│   └── (public/, package.json, tsconfig*, .gitignore)
└── tests/
    ├── test_data_layer.py        # 12 tests
    ├── test_route_finder.py      # 10 tests
    ├── test_segment_builder.py   # 14 tests
    ├── test_prompt4.py           # 28 tests
    └── test_prompt5.py           # 20 tests
    (84 tests total, all green)
```

---

## 7. THE ROADMAP — 9 BUILD PROMPTS, STATUS TABLE

| # | Prompt | Name | Status |
|---|---|---|---|
| 1 | PROMPT_1 | Data Layer (GTFS, fares, station DB, GraphHopper client) | ✅ **DONE** (commit `b48de93`) |
| 2 | PROMPT_2 | Routing Graph + N-hop route finder | ✅ **DONE** (commit `2e2b8ff`) |
| 3 | PROMPT_3 | Segment Builder API (the hop mechanism) | ✅ **DONE** (commits `5aadb08`…`9c631bd`) |
| 4 | PROMPT_4 | Search, Place Reliability, 8-factor TOPSIS | ✅ **DONE** (28 tests) |
| 5 | PROMPT_5 | LangGraph agent + live layer (weather/news/traffic/train) | ✅ **DONE** (20 tests) |
| 6 | PROMPT_6 | Frontend rebuild (glassmorphism) | ✅ **DONE** (build clean, proxy verified) |
| 7 | PROMPT_7 | ML traffic model + integration tests + fake-data audit | ✅ **DONE** (this session) |
| 8 | PROMPT_8 | Trip Planner (Feature 3) | 🔲 PLANNED (design locked in grilling) |
| 9 | PROMPT_9 | Deployment (Render free + Neon) | 🔲 PLANNED (design locked) |

**Current state: prompts 1–7 fully implemented and tested.**
- Backend: **104 pytest pass** (`python -m pytest tests/ -q` in ~26s, no Docker/API required).
  Files: `test_data_layer.py` (12), `test_route_finder.py` (10), `test_segment_builder.py` (14),
  `test_prompt4.py` (33), `test_prompt5.py` (20), `test_traffic_model.py` (9), `test_no_fake_data.py` (6).
- Frontend: `npx tsc -b` + `vite build` zero errors; dev server :3000 proxies `/api` → :8000;
  `/api/search/photo` proxy verified (307 → real Google photo URL); news/weather endpoints 200.
- Prompt 7 (ML + integration + fake-data audit) **DONE**: traffic model + `traffic-model-info` endpoint
  + benchmark all within budget. Prompts 8–9 fully *specified* (see §24) — build order is 8 → 9.

---

## 8. ARCHITECTURE OVERVIEW (how all the pieces fit)

### 8.1 One shared singleton pool — `backend/services/app_state.py`
Module-level lazy singletons, built once in dependency order by `_load_all()`:

```
1. _gtfs     = GTFSService()        .load()     → pickle ~1.2s (parallel with db)
2. _db       = TransitDatabase()                  → 2970 bus stops, 69 metro, 48 rail (parallel with gtfs)
3. _gh       = GraphHopperClient()               → local Docker :8080
4. _builder  = SegmentBuilder(_gtfs, _db, _gh)    → loads TransitAstarGraph topology from
                                                    transit_graph.pkl pickle (~0.2s; ~1.7s rebuild only
                                                    when source files change)
5. _weather  = WeatherClient()                    → Open-Meteo
6. _search   = SearchService(GoogleMapsClient(), SerpAPIClient())
7. _news     = NewsEngine(ProxyManager())         → background thread starts on first use
8. _trains   = TrainService()                     → eRail.in
9. _agent    = VoyagerLangGraph(weather, news, search, train)
```

Public getters: `ensure_loaded()`, `is_loaded()`, `get_builder()`, `get_search()`, `get_news()`,
`get_trains()`, `get_weather()`, `get_agent()`. Every getter triggers a full `_load_all()` if any
slot is unset. `main.py` lifespan calls `ensure_loaded()` at startup (server boots in ~3s, graph
build printed at init).

### 8.2 Request flow
- **A→B transit**: `POST /api/routes/segments` → `builder.build_segments(...)` → Segment 1 FULL +
  Segment 2 FULL + probes. `POST /api/routes/segment-next` → time-chained next segment or
  journey-complete.
- **Search**: `GET /api/search/places|nearby` → `search_service` → Google Places (New) →
  filtered → `Place[]`. `POST /api/search/enrich` → `review_tools.enrich_place` → SerpAPI
  reviews → sentiment → reliability → LLM summary → `PlaceDetails`.
- **Rides**: `POST /api/rides/prices` → `search_service.ride_prices` → Google Directions distance
  → ride_pricing estimate ladder (surge).
- **Live context**: `POST /api/langgraph/route-context` → `agent.gather_route_context` → parallel
  weather/traffic/news/prices (+reviews if place) → `LiveContext` dict.
- **News**: `GET /api/search/news` → `news_engine.relevant` (from background loop cache).
- **Weather**: `GET /api/search/weather` → `weather_client.current`.
- **Trains**: `GET /api/routes/live-trains` → `train_service.trains_between` (live or flagged
  fallback).
- **Photo**: `GET /api/search/photo?name=…` → 307 redirect to real Google photo URL (key stays
  server-side).

---

## 9. PROMPT_1 — DATA LAYER (DONE)

Five modules under `backend/services/`, wired lazily in `app_state.py`.

### 9.1 `gtfs_service.py` — GTFS loader + cache + fuzzy name resolution
- **Reuses the committed 76MB pickle** (`DATA_FOLDER/processed/gtfs_cache.pkl`) — never re-derives
  on startup (was a ~40s block in v1; now **0.65s**).
- Pickle structure (the contract downstream code relies on):
  ```
  shapes:             dict[shape_id] -> [(lat,lng), ...]          (7271 shapes)
  route_shapes:       dict[route_name] -> [shape_id, ...]
  stop_to_shapes:     dict[stop_name] -> [(shape_id, seq), ...]
  stops_by_name:      dict[stop_name] -> (lat, lng, stop_id)      (~5077 stops)
  stop_times:         dict[stop_name] -> [(HH:MM:SS, route_name)]
  stop_times_by_route:dict[route_name] -> [(HH:MM:SS, stop_name)]
  name_map:           dict[master_stop_name] -> resolved_gtfs_name (persisted)
  route_id_to_name:   dict[route_id] -> cleaned route name
  ```
- **Route-name cleaning** (`clean_route_short_name`): strips terminal garbage suffixes —
  `"MF-28 JKLO-ISROQ-LGRNB"` → `"MF-28"`, `"  242-LA "` → `"242-LA"`. Keeps real names with a
  trailing digit token (`"BEL GS-16"`, `"KSRTC-T NARASIPURA-1"`). Applied at GTFS load AND CSV
  stop-source ingestion.
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

### 9.2 `fare_engine.py` — pure fare functions (no I/O inside)
- `bmtc_fare(route_class, dist_km, passenger_type)` — AC Vajra / ordinary / nonac slabs from
  `transit_fares.json`; child = half (ceil, min ₹3), senior = adult − ₹0.75 (min ₹3).
- `metro_fare(dist_km, line)` — single slab table shared by both lines.
- `kia_fare(route_id)` — from `kia_routes_fare_full.json`; uses the max stop fare as the honest
  reference when distance is unknown; `0.0` + `is_estimated` when route unknown.
- `surge_multiplier(hour, weekday)` — 07–10 & 17–21 weekday → **1.5**; 22–06 → **1.8**; else **1.2**.
- `ride_fare_range(ride_type, dist_km, group_size)` — **Karnataka govt-mandated rates**:
  Uber Go/Ola Mini ₹24/km (min ₹85), Uber XL ₹32/km (min ₹130), Ola Auto ₹20/km (min ₹40),
  Rapido Bike ₹5/km (min ₹25). Returns (min, max) with `is_estimated=True`.
  Per-person = vehicle fare / group (NOT ×group — old bug fixed, see §20 #3).

### 9.3 `database.py` — in-memory station DB + spatial index
- Loads: `bmtc_all_stops_master.csv` (~2972 stops, **skips `nan/none/null` names**), metro CSV
  (**Purple + Green only** — Yelahanka/Blue excluded), rail JSON (22 Karnataka stations).
- Spatial index: **sorted-by-lat + binary search + lng window + haversine**, <5ms for ~3000 stops.
- API: `bus_stops_near / metro_near / rail_near(lat, lng, radius_m)`, `all_bus_stops /
  all_metro_stations / all_rail_stations`, `metro_edges()` (adjacent-station pairs with dist+line),
  `routes_for_stop()`.

### 9.4 `graphhopper_client.py` — HTTP client for local Docker GraphHopper
- `route(mode: "car"|"foot", lat1,lng1,lat2,lng2) -> GHResult | None`. Returns `None` on
  timeout/error → caller falls back to interpolated and **flags it** (`path_source`).
- 24h in-memory cache keyed by `(mode, r4(lat), r4(lng), r4(lat), r4(lng))`, thread-safe lock.
- `is_healthy()` checks `/info`.

### 9.5 `data_schema.py` — shared Pydantic models (single source of truth)
Data-layer models: `GtfsStop`, `RouteDeparture`, `BusStop`, `MetroStation`, `RailStation`,
`TransitNode`, `FareResult`, `GHResult`. Plus PROMPT_4 models (`Place`, `Review`, `PlaceDetails`,
`ReliabilityInput/Result`, `RidePrice`, `TopsisWeights`, `ScoringContext`, `ScoredRoute`,
`Suggestion`). All documented in §12 / Appendix B.

---

## 10. PROMPT_2 — ROUTING GRAPH + ROUTE FINDER (DONE)

### 10.1 `transit_graph.py` — TransitAstarGraph (static topology)
- **Nodes**: every GTFS-resolved bus stop (~2900+ bus nodes), every metro station (68 = 2 lines),
  every rail station (≥22). Node keys: `bus:<name>`, `metro:<name>`, `rail:<name>`.
- **Edges** (undirected, stored as adjacency tuples `(neighbor, edge_type, data)`):
  - `bus` — consecutive stops on the same route shape, with 1-skip tolerance (pair-accumulated by
    route, weights computed once per unique pair). Weight = haversine × 1.15 road factor / bus speed
    + dwell (0.3 min).
  - `metro` — adjacent stations same line (from `metro_edges()`). Weight = dist / metro speed + dwell.
  - `walk` — uniform spatial grid (cell ~560m); bus↔bus ≤500m, bus↔metro ≤1000m, bus↔rail ≤3000m.
    Walk time @5 km/h.
- **Speeds (constants)**: bus 18 km/h (edge weights use `BUS_SPEED_KMH = 18.0`), metro 36 km/h,
  walk 5 km/h. Transfer penalty 4 min, interchange fixed 5 min.
- **Performance**: haversine + `_dist_cache` dict only (never `geodesic` in hot loops — this was
  the 11.6s → 2.2s win). Graph builds in ~2.2s, printed at init. Built lazily (server starts
  instantly; first route request warms it).

### 10.2 `route_finder.py` — best-first top-K N-hop search
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

## 11. PROMPT_3 — SEGMENT BUILDER API, THE HOP MECHANISM (DONE — THE CENTERPIECE)

### 11.1 What it is
A **tree of choices**, not a single line. The user builds their journey hop-by-hop; every hop is
real (real bus number, real scheduled time, real geometry, real fare).

### 11.2 `SegmentBuilder` public API
```python
class SegmentBuilder:
    def __init__(self, gtfs, db, gh=None, graph=None): ...   # graph = TransitAstarGraph
    def build_segments(self, source: dict, destination: dict, group_size: int,
                       budget: float, current_time: str | None = None) -> dict
    def build_segment_next(self, journey: dict, chosen_legs: list[dict],
                           group_size: int, budget: float) -> dict
```
- `build_segments` cache key: `(r4 src, r4 dst, now_min//10, group, round(budget))`, TTL 300s.
- Returns: `{"journey": {"source","destination","generated_at"}, "segments":[seg1,seg2],
  "probes":[...], "warnings":[...], "journeyComplete": False, "timeline": []}`.
- `build_segment_next`: time-chains from last leg (`now_min = arrival_min + 4.0`). If last stop
  within **500m** of dest → `journeyComplete: True` + `arrival: {"message":"You have arrived", …}`
  + full timeline. Empty `chosen_legs` → empty response, `journeyComplete: False`.

### 11.3 How Segment 1 is built (`_build_segment_1`)
From the source, enumerate every sensible "get out of here" option:
- **Walk options** to any bus/metro stop within 2km (free). If the closest walk target ≤1.5km,
  that walk is **top-recommended** and no cab/bike is offered.
- **Transit options**: for each boarding stop within 1500m (up to 3 bus stops + 2 metro stations),
  take the **real GTFS next departures** (within 180-min window, ≤4 routes/stop, ≤3 arrival stops
  per route) and ride to forward-progress arrival stops.
- **Metro-transfer rides** (`isMetroTransfer`): for every available route at the stop, look beyond
  the first few stops for a far-forward stop near a metro station (≤1500m) and offer the full
  long-haul ride to that interchange (e.g. "285 → Kempegowda Bus Station, then metro").

Segment 2 (`_build_segment_2`): from distinct arrival stops of Segment 1 (earliest first, ≤6
anchors, ≤40 options), enumerate onward options with the SAME logic, each tagged `connectedFrom` =
its parent stop name, departures **time-chained** (≥ parent arrival + 4 min buffer). Probes
(`_build_probes`): for the level after Segment 2, one cheap onward suggestion per option
(`isProbe: True`, bus/metro only).

### 11.4 Option contract (every hop carries all of this)
```
optionId, destinationStop{name,lat,lng}, mode(walk|bus|metro), routeNumber,
fromStop, distanceKm, durationMin, departureTime, arrivalTime, arrivalMin,
fare, perPersonFare, geometry[], geometrySource(gtfs_shape|metro_line|graphhopper|interpolated),
status(scheduled|estimated|not_running), isTopRecommended, connectedFrom,
transitOptionsFromThisStop, probeNext[], isMetroTransfer(bool), exceedsBudget(bool)
```
(Internal `_fromLat/_fromLng`/`_walkToBoard` are also attached to transit options.)
- Walk: `fare: 0.0`, `status:"estimated"`, `geometrySource:"graphhopper"` or `"interpolated"`.
- Bus: `status:"scheduled"` or `"not_running"` (>45 min wait); fare = `kia_fare` if route starts
  with "KIA" else `bmtc_fare("nonac", dist)`; total fare = `fare * max(1, group_size)`.
- Metro: `routeNumber:"Purple"|"Green"`, `status:"estimated"` (no schedule), geometry =
  metro line polyline, `geometrySource:"metro_line"`, `perPersonFare == fare`.

### 11.5 Top-recommended rule
If a walk ≤ 1500m exists → that walk is top; else `score(o) = (fare or 0)*2 + walk_km*12 +
arrivalMin`, min wins.

### 11.6 Warnings
- hour ≥ 22 or < 6 → `"Bus service limited after 22:00 - consider cab/auto"`.
- any `not_running` option → `"Some stops have no more scheduled buses today - service marked
  not_running"`.

### 11.7 Hard rules that make it correct (all verified by tests)
- **Forward-progress**: `hav(arrival → dest) < hav(anchor → dest) + tol` (500m normal, 2500m metro).
- **No circular routing**: 800m visited guard; candidates within 25m of the anchor dropped.
- **Real data only**: bus options from real GTFS; stop with no GTFS → no transit options (walk may
  still appear). No full-route spiderwebs (geometry = `get_stop_to_stop_segment()` slice only).
- **Time chaining**: Segment N departures ≥ previous arrival + buffer (test: `>= arr_min + 4`).
- **connectedFrom chains exactly**; **budget** → `exceedsBudget` grey-out, never silent drop.
- **Metro hubs**: Majestic carries both lines; both directions offered.
- **Cache**: 5-min TTL; second call <50ms identical.

### 11.8 The frontend contract for this window (PROMPT_6 §9)
Breadcrumb `Source → [bus 507-D] → Kogilu Cross → [KIA-9] → Majestic → [Purple] → … →
Destination`. Columns render from `/api/routes/segments`; selecting a hop filters the NEXT column
client-side by `connectedFrom`; changing an earlier column **resets downstream selections**; deeper
columns lazily call `segment-next`; confirmed hops accumulate geometry on the map;
`journeyComplete` shows the arrival screen with full timeline + total + reset.

---

## 12. PROMPT_4 — SEARCH, RELIABILITY, TOPSIS (DONE)

### 12.1 Google Maps Places client (`clients/google_maps_client.py`)
- Base URLs: `https://places.googleapis.com/v1` (Places API New) + legacy
  `https://maps.googleapis.com/maps/api` (Geocoding/Directions).
- Filters (PROMPT_4 §2.1): **≥40% keyword overlap** (`MIN_KEYWORD_OVERLAP = 0.40`) between query
  and result name/address (applied in `search_places`, NOT nearby), coords within **15km** of
  Bangalore center `(12.9716, 77.5946)` (`BANGALORE_RADIUS_KM = 15.0`), dedup by 4-decimal coords
  (`_DEDUP_RND = 4`, ~11m). 24h cache, 2000-entry bound.
- Methods: `geocode`, `search_places` (searchText + locationBias circle 15km), `nearby_places`
  (searchNearby, maxResultCount 20, `includedPrimaryTypes` from 19-category map), `place_details`,
  `directions` (mode driving/walking/transit, `departure_time=now`, `traffic_model=best_guess`,
  returns `distance_m`, `duration_s`, `duration_in_traffic_s`, `traffic_ratio`, decoded `geometry`,
  `source:"google_maps"`), `place_photo_url(place_id, photo_name, max_width)` → real URL
  `https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx={max_width}&key=…`.
- 19 category → primary-types map: atm, bank, hospital, pharmacy, restaurant, cafe, hotel/mall
  (hotel+lodging), mall (shopping_mall), petrol pump (gas_station), ev station, supermarket,
  park, bus stop, metro (subway_station/metro_station/transit_station), temple, police, school,
  gym, cinema.

### 12.2 Reliability score (`reliability.py`) — dynamic, deterministic, explainable
```
status_factor = 0.0 CLOSED_PERMANENTLY | 0.4 CLOSED_TEMPORARILY | 1.0 OPERATIONAL/None
rating   = clamp(rating, 0, 5);  default rating_part = 0.2 when no rating
sentiment = clamp(sentiment_avg, 0, 1)

rating_part    = 0.5 * (rating / 5.0)
sentiment_part = 0.3 * sentiment
count_part     = 0.2 * min(1.0, log1p(review_count) / log1p(100))    # log1p(100) ≈ 4.615
raw    = (rating_part + sentiment_part + count_part) * status_factor
score  = clamp(raw, 0, 1)
score_pct = int(round(score * 100))
```
Pin classes (order matters): status_factor==0 (CLOSED_PERMANENTLY) → `red`; CLOSED_TEMPORARILY →
`yellow`; `score>=0.7 and status_factor>=0.4` → `green`; `score>=0.5` → `yellow`; else `red`.
`ReliabilityResult`: `score, score_pct, pin_class, status_factor, rating_part, sentiment_part,
count_part`. Always recompute — never trust an external `reliability_score`.

### 12.3 Reviews & sentiment
- **Chain** (`review_tools.py`): `enrich_place(place, max_reviews=24)` → requires `place_id` →
  `serpapi.place_details` → reviews parsed from `user_reviews.most_relevant` (real keys:
  `username`/`description`/`rating`/`date`) → `sentiment_avg` → `compute_reliability` →
  `_summarize` → `PlaceDetails`. Cache: plain dict keyed by `place_id` (no TTL), `_REVIEW_CACHE_VERSION = 2`.
- **SerpAPI key fix** (do-not-regress): parse from `data["place_results"]` (fallback `data["place"]`),
  reviews from `user_reviews.most_relevant`, fields `username`/`description` — NOT the old broken
  `"place"` key / `reviews` int / `user.name`/`snippet`. Cache versioned `detail:{place_id}:v2`,
  24h TTL.
- **Sentiment** (`sentiment.py`): primary = deterministic **AFINN-style lexicon** (offline,
  reproducible, negation-aware, 31 negators), polarity ∈ [0,1] (`0.5 + mean/8` squash of [−4,4]).
  Optional upgrade: HuggingFace `distilbert-base-uncased-finetuned-sst-2-english` pipeline, loaded
  lazily once; fallback to lexicon on any failure. **LLM never computes sentiment.**
- **Summary** (`agents/review_summarizer.py`): `summarize(texts, score_pct)` → `SummaryResult
  (summary, concerns[])`; payload truncated to 14,000 chars; temperature 0.2, `response_format:
  {"type":"json_object"}`, timeout 20s; `None` on empty/no-key/error → deterministic fallback
  `"Based on {n} Google reviews (reliability {p}%)."`. **LLM never invents review text.**

### 12.4 TOPSIS 8-factor (`topsis_engine.py`, real numpy)
- `TopsisWeights` (user-adjustable, sum 1.0, re-normalized):
  `time_of_day .10, cost .20, weather .10, traffic_crowd .15, availability .05, walking .15,
  group_size .10, safety .15`.
- 8 criteria `(name, is_benefit)`: cost(cost)❌, time_of_day❌, walking❌, group_size✅, weather✅,
  traffic_crowd❌, availability✅, safety✅.
- `RouteCriterionValues` @dataclass (per-route raw inputs): `cost, time_of_day, walking,
  group_size=1.0, weather, traffic_crowd, availability, safety`.
- Algorithm: matrix X(n,8) → vector-normalize (`norms = sqrt(sum(X², axis=0))`, zero-norms→1.0)
  → weight-normalize → ideal/anti-ideal (by is_benefit) → `d_plus`/`d_minus` → closeness
  `cc = d_minus/(d_plus+d_minus)` → sort desc, tie-aware ranks (`abs diff < 1e-9` share rank).
- Mutates each `ScoredRoute`: `cc_score`, `rank`, `best_match (rank==1)`, `scores =
  {"reliability": cc, "explained": _explain(...)}` (explain: `₹{fare}`, `{dur} min`, `{walk:.1f} km
  walk`, `{transfers} transfers`, + `"rain expected — prefer covered modes"` if `rain_next_hour`).
- Empty → `[]`; single route → rank 1 best_match; all-identical → all share rank 1.

### 12.5 Ride pricing (`ride_pricing.py`)
- Two sources always labeled: **live** (SerpAPI `google_maps_directions` `ride_options`, note
  "Live Uber/Ola quote from Google Maps") vs **estimated** (Karnataka govt formula, note
  "Karnataka rate estimate x{surge:.1f} surge").
- `_ESTIMATE_LADDER` (always all 5): uber_go/Uber/cab, ola_mini/Ola/cab, uber_xl/Uber XL/cab,
  ola_auto/Auto/auto, rapido_bike/Rapido/bike.
- Formula per provider: `amount = max(min_fare, base + per_km*dist)`; max = `amount*1.1`; surge
  applied to the mid-point: `total = round(mid * surge, 2)`; `per_person = round(total/group, 2)`.
- **`total` = vehicle fare (never `per_person × group`)** — old bug fixed.
- `merge_live_prices(live_options, estimated, group)`: live entries win (provider match); leftover
  providers stay estimated; malformed live entries ignored (`_extract_price` tries price/
  price_value/total, strips ₹ and commas, returns None on failure — never fabricates).
- `ride_prices_for_distance(dist_km, group_size, live_options=None, context=None)` → estimates then
  merge.
- **Note**: `SearchService.ride_prices` and `PricingTool.run` currently pass `live_options=None`
  always, so the live overlay is defined but not yet invoked through these two paths (a known
  future wiring point — see §24).

### 12.6 Search service (`search_service.py`)
Orchestrates Maps + SerpAPI + scoring. `search_places`, `nearby` (first category wins), `enrich`
(delegates to review_tools), `verify` (closest by squared euclidean), `ride_prices`,
`suggestions` (top 5). `_to_place` filters dict to `Place.model_fields` only.

---

## 13. PROMPT_5 — LANGGRAPH LIVE LAYER (DONE)

### 13.1 Role (non-negotiable)
`VoyagerLangGraph` is a **data gatherer + explainer**. It gathers live factors in parallel and
explains them — it **never decides routes** (that is the deterministic A*/graph) and **never writes
numbers** (LLM only synthesizes text).

### 13.2 `langgraph/agent.py` — `VoyagerLangGraph`
Constructor injects (or defaults) LLMAgent + WeatherTool + TrafficTool + NewsTool + PricingTool +
SearchTool + GeoTool + TrainTool; `ThreadPoolExecutor(max_workers=5)`.

- **`gather_route_context(src, dst, group_size, budget, current_time, place) -> dict`**:
  parallel fan-out jobs: `"weather"` (at dest), `"traffic"` (`_traffic_with_news`: news keyword
  "traffic" first, then TrafficTool with alerts), `"news"` (at dest, limit 10), `"prices"` (only if
  group_size truthy). Each future wrapped in try/except → `results[key] = None` on failure (a
  failing tool **never blocks** the others). Reviews only when `place.get("place_id")`. Then
  `_derive_factors(state)` and `_to_live_context(state)`.
- **`_derive_factors`** (deterministic from `datetime.now().hour`): `time_of_day` ∈
  `night`(≥22 or <6) | `morning_rush`(<10) | `day`(<17) | `evening_rush`; `rain_next_hour` (from
  weather); `traffic_label`; `safety` = `"caution"` only at night with non-empty news else `"ok"`.
- **`_to_live_context` → LiveContext dict** (exact keys):
  ```
  weather, traffic, news, prices, reviews, factors, errors, completed_at (ISO)
  ```
  Degraded fields are honest: `weather or {"condition":"unavailable"}`, `traffic or
  {"label":"unavailable"}`.
- **`ask(message, lat, lng, context) -> dict`**: defaults coords to Bengaluru (12.9716,77.5946)
  if none; returns `{"live_context": ..., "synthesis": {"answer", "factors"}}`.
- **`_synthesize`**: builds prompt with the hard rule "do NOT invent fares, timings, bus numbers,
  or scores. Use only the given data. Reply JSON {"answer", "factors"}."; `chat_json` via LLMAgent;
  if `None` → `{"answer":"Live data partially unavailable.","factors":["LLM unavailable"]}`.

### 13.3 Tools (`langgraph/tools/`)
- **NewsTool**: `NewsEngine.relevant(lat, lng, keyword, limit)`.
- **PricingTool**: `maps.directions` → `dist_km` → `ride_prices_for_distance` → `RidePrice[]` dicts.
- **ReviewTool**: `ReviewTools.enrich_place(Place) → PlaceDetails` dict.
- **SearchTool** (+ place_details via enrich) / **GeoTool** (geocode, nearby; reverse_geocode calls
  geocode with "lat,lng").
- **TrafficTool**: `traffic_ratio` from Directions; labels `heavy ≥1.3`, `moderate ≥1.1`, else
  `light`. Fallback (labeled `"time_of_day_model (Directions unavailable)"`): weekday rush → 1.4
  heavy, night → 1.05 light, else 1.2 moderate. Payload: `{ratio, label, source, alerts[≤3]}`.
- **TrainTool**: `code_for` both stations; unknown → `{"trains":[],"source":"none","note":"no
  station codes"}`; else `trains_between`.
- **WeatherTool**: `WeatherClient.current(lat,lng) or {}`.

### 13.4 `state.py`
`RouteContextInput{source, destination, group_size, budget, current_time}`;
`RouteContextState{input, weather, traffic, news[], prices[], reviews, factors{}, errors[],
completed_at}`; `AskInput{message, lat, lng, context}`; `AskState{input, tool_outputs{},
synthesis}`.

### 13.5 `workflows/route_context.py`
`RouteContextWorkflow.run(...)` — pure delegate to `agent.gather_route_context` (all fan-out lives
in the agent).

### 13.6 `news_engine.py` — background loop
- Constants: `_TTL_S = 4h`, `_MAX_ITEMS = 25`, default interval **8 min** (spec 5–10), daemon
  thread `"news-loop"`, `_loop` never dies (refresh wrapped in try/except).
- `refresh_once()`: `_scrape_reddit` (r/bangalore/new.json?limit=25 via proxy, title + text 400
  chars + url + source "r/bangalore" + ts) + `_scrape_news_fallback` (DDG html search for 3 queries:
  "Bangalore traffic today", "Karnataka rain alert", "Bengaluru news", ≤8 titles each) →
  `_dedup` (normalized title key, 80 chars) → classify → geo-tag → `_merge` (fresh + old within TTL,
  sort ts desc, cap 25).
- `_classify` keywords → `traffic | weather | event | general` (e.g. traffic: jam/congestion/
  accident/road closed/diversion/gridlock/crashed/pile-up/metro delay/bus strike).
- `_geo_tag` → 24 known Bangalore localities (silk board, majestic, mg road, cubbon park,
  indiranagar, korangala, whitefield, ecity, hebbal, yeshvantpur, rajajinagar, jayanagar,
  marathahalli, outer ring road, namma metro, kempegowda, bannerghatta, hsr layout, bellandur,
  byatarayanapura, sarjapur, ecity…).
- `summarize_items(llm)`: LLM `chat_json` ≤2-line summary, `[:220]` chars, per-item try/except.
- `relevant(lat, lng, keyword, limit)`: keyword filter → proximity sort (haversine to geo, untagged
  last) or ts desc; `setdefault("summary","")`; cap limit. Served even if loop fails → honest
  empty (never fake headlines).

### 13.7 `train_service.py` — eRail.in live trains
- `_ERAIL = https://erail.in/rail/getTrains.aspx`, `_TIMEOUT=6.0`, 15-min cache.
- **STATION_CODES: 48 entries** (SBC, YPR, BNC, KJM, YNK, WFD, KGI, MYS, UBL, MAJN, MAQ, BGM, BAY,
  DVG, DWR, KLBG, RC, BJP, BWT, TK, ASK, HAS, MYA, HPT, GDG, SMET, HRR, WADI, RRB, LD, YG, BIDR,
  UD, KAWR, HVR, RNR, TTR, DRU, KUDA, KBL, BGK, S, RMGM, CPT, NTW, CMNR, BDVT, BTJL). NOTE:
  AGENTS.md's "22" is stale — the code has 48.
- `trains_between(fc, tc)`: GET with params; parse rows → `{train, name, dep, arr, dur_min,
  source:"live"}`. Return `{"trains", "source": "live"|"fallback", "note"}`.
  - eRail reachable + zero trains → genuinely empty `{"source":"live","note":"eRail.in (no
    services)"}` (NO fallback applied).
  - On failure: if pair in `_FALLBACK_PAIRS` (7 city-pairs, static schedules) → `source:"fallback"`,
    note "eRail unreachable — city-pair schedule (NOT live)". Else keep empty fallback default.
- **Trains appear only when eRail returns real data — never fabricated.**

### 13.8 `llm_agent.py` — OpenRouter → Gemini chain
- `LLMConfig{openrouter_key/base/model, gemini_key/model, temperature=0.2, timeout_s=30,
  fallback_models[]}`. Defaults: OpenRouter `https://openrouter.ai/api/v1`,
  `openai/gpt-4o-mini`; Gemini `https://generativelanguage.googleapis.com/v1beta/openai/`,
  `gemini-2.0-flash`.
- `chat_json(system, user) -> dict | None`: try OpenRouter (if key) → try Gemini (if key) → `None`.
  Each failure logged and skipped (provider chain, not parallel). `_complete` uses
  `response_format={"type":"json_object"}`, temperature 0.2, timeout 30.
- **NEVER allowed**: guessing fares/timings/scores, fabricating anything, deciding routes. `None`
  → caller supplies deterministic fallback.

### 13.9 `proxy_manager.py` — DataImpulse
Covered fully in §16.

---

## 14. PROMPT_6 — FRONTEND (DONE)

### 14.1 `context/AppContext.tsx` — global state
`Mode = "search" | "atob" | "trip"`. `JourneyState{segments, chosenLegs, active, position}`.
`AppState`: mode/setMode, dark/toggleDark (initial `prefers-color-scheme`, toggles `html.dark`),
userLoc, source, dest, setSource/setDest, swap, weather, places, selected, showDiscovery, prices,
liveContext, news, journey (setJourney merges partials), flyTo. `scoreClass(score)`: null→yellow,
≥70 green, ≥50 yellow, ≥30 orange, else red. `scoreColor(score)` → CSS var. `useApp()` throws
outside provider.

### 14.2 `services/api.ts` — typed axios client
`http` instance: `baseURL = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api"`,
timeout 120s. AbortController signal support in `searchPlaces`, `searchNearby`, `routeSegments`.
Methods (exact paths):
- `searchPlaces(q, lat?, lng?, signal?)` → GET `/search/places`
- `searchNearby(lat, lng, radiusM, categories=[], keyword="", signal?)` → GET `/search/nearby`
- `enrichPlace(place)` → POST `/search/enrich`
- `verifyPlace(name, lat, lng)` → POST `/search/verify`
- `weather(lat, lng)` → GET `/search/weather` (null if condition "unavailable")
- `news(lat?, lng?, keyword="", limit=15)` → GET `/search/news`
- `ridePrices(origin, dest, groupSize)` → POST `/rides/prices`
- `routeSegments(src, dst, groupSize, budget, currentTime=null, signal?)` → POST `/routes/segments`
- `segmentNext(journey, chosenLegs, groupSize, budget)` → POST `/routes/segment-next`
- `routeContext(src, dst, groupSize, budget, place=null)` → POST `/langgraph/route-context`
- `liveTrains(from, to)` → GET `/routes/live-trains`

### 14.3 `types/index.ts` — all contracts
`Coord=[number,number]`, `ScoreClass`, `LatLng`, `WeatherNow`, `NewsItem`, `PlaceResult`,
`Review`, `PlaceDetails extends PlaceResult` (+phone/website/reviews/sentiment_avg/
reliability_score/pin_class/summary/concerns), `RidePrice`, `PlaceModel`, `StopRef`, `HopOption`,
`ProbeOption`, `Segment`, `SegmentResponse`, `JourneyComplete`, `LiveContext`, `ScoredRoute`.
(No `any` for API payloads — gate.)

### 14.4 `App.tsx` / `main.tsx`
`AppProvider` wraps app; `WeatherLoader` calls `api.weather` (defaults to Bengaluru if no userLoc),
stores via setWeather. `main.tsx` mounts StrictMode + App with `index.css`.

### 14.5 `pages/MainPage.tsx` + `.css` — 3-tab shell
Tabs: Search / A→B / Trip (bottom pill nav, active = primary bg + glow). Layout: HeaderBar on top;
`.app-body` = sidebar (`380px`, `.glass`) + map-wrap (flex:1) + DiscoveryPanel overlay. Geolocation
on mount (6s timeout, fallback Bengaluru). Mobile ≤768px: body becomes column, sidebar 42vh, map
45vh, icon-only tabs. Exports helper `flyToPoint(map, point, zoom=15)`.

### 14.6 `components/HeaderBar.tsx` + `.css`
Brand, live clock, weather chip (temp + condition, `rain soon` badge when rain_next_hour), dark
toggle, location.

### 14.7 `components/MapView.tsx` — Leaflet map
- `NUM_COLORS` (10) for numbered pins; `MODE_COLOR` = bus #6c5ce7, metro #00cec9, train #e17055,
  walk #95a5a6, ride #f39c12, connecting #f39c12, dropoff #fd79a8.
- Icons (all `L.divIcon`): userIcon (blue pulsing dot, `.marker-user`), pinIcon(cls) (`.marker-pin`
  green/yellow/red, letter G/Y/R), numIcon(n), starIcon (selected), newsIcon(cat) (traffic #e74c3c,
  weather #3498db, event #f1c40f, general #95a5a6).
- `FlyController` — `map.flyTo([lat,lng], max(zoom,14), {duration:0.9})` when target set.
- `legGeometry(opt)` maps `[lng,lat]→[lat,lng]` (backend returns `[lat,lng]`; this swap keeps
  Leaflet correct — the SegmentFlowView previously swapped the other way, the old bug).
- `RoutePolylines` — one `<Polyline>` per option geometry (skips <2 pts); `approx` =
  `geometrySource==="interpolated" || status==="estimated"` → `dashArray "6 6"` (walk always
  dashed); weight 3 (walk) / 5; opacity 0.85. Connecting dashed line between source/dest when both.
- `Pins` — numbered places hidden during active journey; source = green pin, dest = red pin, star
  for selected; numbered pins colored by `business_status==="CLOSED_PERMANENTLY" ? red :
  scoreClass(rating*20)`; news pins only if `geo`; JourneyPosition = blue CircleMarker (radius 7).
- `fitBounds` on journey segments (padding 40). OSM tiles.
- Hover = CSS only (`.marker-pin:hover` scale 1.15). Hop-card hover pans the map (in
  SegmentFlowView).

### 14.8 `components/SearchPanel.tsx` + `.css`
Two tabs: **Search specific** (text input, Enter/icon runs search; suggestions debounced 300ms when
≥2 chars, AbortController, top 5 in glass-strong dropdown) and **Nearby** (pinned-banner when a
place is pinned, 19 category chips in scrollable wrap — default "Restaurant", radius slider
0.5–10km step 0.5 default 2, "Find nearby" → `api.searchNearby`). `PlaceCard`: numbered marker,
name, primary_type, status pill (open/closed/unknown), address, ★ rating (count), distance km,
`badge live/est` for open/closed, **Details** + **Navigate** buttons. Click → pin + flyTo; Details
→ enrich + DiscoveryPanel; Navigate → setDest + mode atob.

### 14.9 `components/DiscoveryPanel.tsx` + `.css` — right-side glass panel
Shows (when showDiscovery): hero photo (`/api/photo?name=…`, onError hides), header + close,
reliability score pill (`selected.pin_class ?? scoreClass(rating*20)`), name, type, address,
★ rating (count) + distance, business-status pill, opening hours (`<details>`), **AI review
summary** box tinted by class + **Concerns** (red bullets), first 5 real reviews, buttons "Show on
map" (flyTo) + "Navigate here" (dest + atob). Loading skeleton. Position: absolute right 28px,
340px wide; mobile right 8px width min(340px,92vw).

### 14.10 `components/AToBPanel.tsx` + `.css`
- Travel-mode chips **Public / Drive / Walk** (default public); public sub-chips **Multi-hop
  transit** (default) / **Direct ride**.
- Autocomplete source/dest (green/red dots; debounced 300ms suggestions via `api.searchPlaces`,
  top 5; "Current location" entry uses userLoc; picking sets source/dest + flyTo).
- Params: group (1–20, default 1), budget ₹ (default 500), mileage km/L (drive only, 5–40, default
  15). Swap button.
- `findRoutes`: public+ride → `api.ridePrices` → RideCards; public+transit → SegmentFlowView; drive
  → `api.ridePrices(src,dst,1)` for the estimate + fuel; walk → SegmentFlowView. Sets places [] and
  hides flow each new search.
- **startDrive**: `fetch("http://localhost:8080/route?…&profile=car&points_encoded=false")` (real
  GraphHopper) → `fuel = (110.0 * distKm) / mileage` → fuel card "Fuel cost ₹X at ₹110/L, Y km/L —
  approximate".
- RideCard: provider, mode, `badge live|est`, ₹total (0dp), ₹pp/person, `• {eta_min} min`, note.
- Primary button: "Estimate drive" / "Get ride prices" / "Find routes", disabled without src+dst.

### 14.11 `components/SegmentFlowView.tsx` + `.css` — the multi-hop window
- `MODE_META`: bus/metro/train/walk/ride → icon + color + label.
- Loads `api.routeSegments(source,dest,1,500)` on mount if empty; state: segments, confirmed,
  loadingNext, complete, selectedPerColumn.
- **connectFilter(colIdx)**: if previous column has a selection, filter options where `connectedFrom`
  absent or `=== prev.destinationStop.name` (case-insensitive). Column visibility: col 0 always;
  later cols only if prior filtered col has ≥1 option.
- **confirmHop(colIdx, opt)**: clears downstream selections + confirmed beyond colIdx, sets
  selection, updates breadcrumb; **map pan** to `opt.geometry` last point; **lazy segmentNext** if
  colIdx is last && !complete → `api.segmentNext(journey, chosen, 1, 500)`, append segments,
  spinner skeleton while loading.
- Breadcrumb: `Source → {routeNumber} {mode} → {destinationStop.name} → … → dest.name` with colored
  crumb-dots.
- Hop card: mode icon, routeNumber/Walk, `★ Top` gold badge when isTopRecommended, → stop, minutes,
  km, ⏱ departure, ₹fare/"Free"/"—", ↻ onward options count. `onMouseEnter` pans to geometry last
  point. Walk cards dashed border.
- Complete banner: `"You reached {dest}!"` + total min + ₹ total + legs count + **Reset**; else if
  confirmed>0 **Start journey** → setJourney({active:true}); when active a live-banner shows.
- `totalTime/totalFare` from confirmed reduce.

### 14.12 `components/TripPanel.tsx` + `.css`
AI Travel Insights card, **Start journey / End** (watchPosition enableHighAccuracy, timeout 10s,
live coords), Create new trip (→ atob), Your Trips (empty state), Day Plan chips Day 1–3.

### 14.13 `components/NewsPopup.tsx` + `.css`
Floating LIVE glass panel (absolute left 12 bottom 12, 280px). Polls `api.news(…, 15)` on mount +
every **2 min**; expands/collapses; dismiss ×. Items bordered by category color, title + summary +
category badge. Dark-mode override for item bg.

### 14.14 `index.css` — design system (this is the app's look, do not delete)
CSS vars: brand (primary #6c5ce7, secondary #00cec9, accent #fd79a8, error #e74c3c, warn #f39c12,
success #27ae60), surfaces (`--bg #eef1f7`, panel rgba white, text #1e2536 + 2 shades), score
colors (green/yellow/orange/red), glass blur 18px, radius 16px, font Inter 15px.
Dark mode via `html.dark` overrides. Body = two radial gradients (purple top-right, teal
bottom-left).
Classes: `.glass`, `.glass-strong`, `.hover-lift`, `.score-pill .green/.yellow/.orange/.red`,
`.score-bar`, `.badge .live/.est/.approx/.best/.gold`, `.skeleton` (shimmer), `.spinner`,
`.pulse-dot`, animations `.anim-up/.anim-in/.anim-scale`, keyframes `shimmer/slide-up/fade-in/
scale-in/pulse-ring/pulse-dot/spin`, Leaflet overrides, `.marker-pin` (rotated teardrop, green
glow/yellow 30px/red 24px dim), `.marker-num`, `.marker-user` (pulse ring), `.marker-star`, utils
(muted/truncate/row/spread/mt8/mt12), `.btn` (+ghost/full/small), `.text-input`, `.chip`,
`.full-map`.

### 14.15 `vite.config.ts`
`server.port 3000`, proxy `/api` → `process.env.VITE_API_BASE || http://localhost:8000`,
changeOrigin.

---

## 15. INTEGRATIONS DEEP-DIVE — WHAT, WHY, AND WHEN EACH IS USED

### 15.1 SerpAPI — Google Maps reviews + live ride prices (WHY: real reviews & live prices)
- **Why integrated**: BMTC has no live API; Google's own review data is the only honest source of
  "is this place real/recommended". SerpAPI wraps Google Maps search/directions so we get
  **real reviews** (`user_reviews.most_relevant`) and **live Uber/Ola quotes**
  (`ride_options`) without a full Google Places billing scare.
- Auth: `SERPAPI_API_KEY` (API-key, **no proxy**). Free tier ~250 searches/mo; owner has friend
  keys (~1250/mo) — budget-sensitive (reviews capped ~10/place).
- **Past critical bug (FIXED, do-not-regress)**: `_parse_place_detail` used wrong response key
  `"place"` instead of `"place_results"`; reviews read from `place_results.reviews` (an **int
  count**) instead of `user_reviews.most_relevant`; fields `user.name`/`snippet` instead of
  `username`/`description`. See §20 #17.
- Where used: `clients/serpapi_client.py` (search_place, place_details, directions/ride_options).
  Caches: reviews 24h (`detail:{id}:v2`), prices 15 min.

### 15.2 Google Maps Platform — Places (New), Geocoding, Directions (WHY: canonical places + traffic)
- **Why integrated**: canonical place search/nearby/details/photos/hours/business_status, plus
  `duration_in_traffic` for the TOPSIS traffic factor and real driving geometry via Directions.
- Auth: `GOOGLE_MAPS_API_KEY` (API-key, **no proxy**). APIs enabled: Places API (New), Geocoding,
  Directions/Distance Matrix.
- Where used: `clients/google_maps_client.py` (search_places, nearby_places, place_details,
  place_photo_url, directions, geocode). 24h cache. Photo served through the **server-side proxy**
  (`GET /api/search/photo`) so the API key never leaks to the browser.

### 15.3 GraphHopper — real road routing (WHY: replaces v1's OSRM)
- **Why GraphHopper over OSRM**: v1 used OSRM (5000/5001) with public-URL fallback bugs and OOM
  issues. v2 spec chose local GraphHopper on **8080** (car + foot, Karnataka PBF) for real
  road-following walk/drive geometry + driving distances.
- `docker-compose.yml` (ONLY service in the file): image `israelhikingmap/graphhopper:latest`,
  ports `8080:8989`, volume `./gh-data:/data`, `java -Xmx2g -Xms1g -jar
  graphhopper-web-12.0-SNAPSHOT.jar server /data/config.yml`, restart unless-stopped.
- Behavior: `route()` returns `None` on any failure → caller interpolates and **flags**
  `path_source:"interpolated"` (dashed on map). 24h cache. `is_healthy()` via `/info`.

### 15.4 Open-Meteo — weather (WHY: free, no key, honest)
- Free API, no key. `current(lat,lng)` returns temp_c, WMO condition label, weather_code, humidity,
  wind_kmh, is_day, `rain_next_hour` (any of first 4 fifteen-min precip probs ≥30). 15-min cache;
  failures cached as None. Feeds header widget + TOPSIS weather factor + LangGraph factors.

### 15.5 eRail.in — live trains (WHY: real train data or nothing)
- Scraped eRail API for **48 mapped Karnataka station codes** (NOT 22 — code is ahead of docs).
  Live trains flagged `source:"live"`; if eRail unreachable and the pair is in the 7 static
  city-pair fallbacks → `source:"fallback"` + note "NOT live". Never invented.

### 15.6 Reddit r/bangalore — news + place signals (WHY: fresh community signal)
- JSON API via DataImpulse proxy. Input to the news loop + (PROMPT_8) qualitative hints only.

### 15.7 OpenRouter / Gemini — LLM (WHY: summaries & explanations only)
- **Why**: the product wants AI "why recommended" + review summaries + plain Hinglish route
  explanations. Chain: OpenRouter (`openai/gpt-4o-mini`) → Gemini (`gemini-2.0-flash`). JSON mode,
  temp 0.2, timeout 30.
- **Hard rule**: NEVER fares/timings/bus numbers/review text/reliability/news/scores. If both fail →
  deterministic fallback text. `review_summarizer` uses the same providers (timeout 20, 14k chars).

### 15.8 DataImpulse proxy — IP rotation for scraping (see §16)

---

## 16. THE PROXY SYSTEM (DataImpulse) — exactly when it IS and IS NOT used

### 16.1 What it is
`backend/services/proxy_manager.py`. Credentials: `DATAIMPULSE_USER/PASS`, host default
`gw.dataimpulse.com:823`. Builds the session lazily:
```
proxies = {"http": "http://{user}:{pass}@{host}", "https": "http://{user}:{pass}@{host}"}
header User-Agent: "Mozilla/5.0 (VOYAGER news engine)"
```
`available` = bool(user and pass). `get(url, timeout=10, retries=2)` → `requests.Response | None`;
returns None immediately if creds missing; retries with backoff 0.5s then 1.0s; None on total
failure.

### 16.2 The rule (tested in `test_prompt5.py::TestProxy`)
- **USED for IP-blockable targets**: Reddit r/bangalore JSON, DDG html search (news fallback),
  news sites, review scans. These are anonymous GET scrapes where the site can block datacenter IPs.
- **NEVER used for API-key services**: SerpAPI, Google Maps, Open-Meteo, OpenRouter/Gemini, eRail
  — they authenticate by key, so a proxy adds nothing and risks breaking auth. The test
  inspects `google_maps_client`, `serpapi_client`, `weather_client` and asserts none reference
  "dataimpulse".

### 16.3 Bandwidth budget (Render, monthly ~5GB pool)
- news loop ~200KB/cycle → ~1.8GB; DDG fallback ~50KB/search → ~0.5GB; review scans ~100KB/place →
  ~1GB. Total **~3.3GB ✅ within 5GB**. Keep loop interval ≥5 min, always cache news, never scrape
  on every page load.

---

## 17. DATA SOURCES & DATASETS INVENTORY

| File | Size | Content | Used by |
|---|---|---|---|
| `bmtc_gtfs/` (11 .txt) | ~190MB | Official BMTC GTFS: agency, calendar, fare_attributes, fare_rules, feed_info, routes, shapes, stops, stop_times, translations, trips | raw-load cold path only (NOT committed) |
| `processed/gtfs_cache.pkl` | **76MB** | 7271 shapes, 5077 stops, 429882 stop-times, `name_map`, `route_id_to_name` | **committed**, reused at startup (0.65s) |
| `bmtc_all_stops_master.csv` | 2MB | ~2972 bus stop names + coords + route lists | stop DB + name resolution |
| `bengaluru_metro_network.csv` | 8KB | Purple + Green stations, edges, dist | metro nodes/edges (NO Blue/Yelahanka) |
| `kia_routes_fare_full.json` | 22KB | KIA Vayu Vajra routes + fares | KIA bus options |
| `transit_fares.json` | 3.5KB | BMTC AC/nonAC + metro slabs | fare engine |
| `karnataka_railway_stations.json` | 2.8KB | 22 Karnataka rail codes | rail nodes; live via eRail.in |
| `traffic_logs.csv` | 7.5MB | Quarterly traffic/crowd data | ML model (PROMPT_7), NOT routing |

Paths (from `config.py`): `DATA_FOLDER`, `GTFS_CACHE_PATH`, `GTFS_RAW_FOLDER`,
`TRANSIT_FARES_PATH`, `KIA_ROUTES_PATH`, `METRO_NETWORK_PATH`, `BUS_STOPS_MASTER_PATH`,
`RAIL_STATIONS_PATH`, `TRAFFIC_LOGS_PATH`, `ENV_PATH`. `OPERATIONAL_METRO_LINES =
("Purple Line","Green Line")`.

---

## 18. ENVIRONMENT VARIABLES & SECRETS

`.env.example` (committed, 12 vars) — real values go in `.env` (never committed):
```
# LLM Provider
OPENROUTER_API_KEY / OPENROUTER_MODEL=openai/gpt-4o-mini / GEMINI_API_KEY
# Google Maps
GOOGLE_MAPS_API_KEY
# SerpAPI
SERPAPI_API_KEY
# DataImpulse proxy
DATAIMPULSE_USER / DATAIMPULSE_PASS / DATAIMPULSE_HOST=gw.dataimpulse.com:823
# Postgres (PROMPT_8)
DATABASE_URL=postgresql://user:pass@host/voyager?sslmode=require
# Fuel & defaults
FUEL_PRICE_PER_LITER=110.0 / PETROL_AVG_MILEAGE=15.0
# Test time override (optional)
VOYAGER_TEST_TIME=15:30
```
`config.py` reads via python-dotenv at import (`load_env()`); `env_str`/`env_float` helpers. Runtime
constants: `FUEL_PRICE_PER_LITER` (110.0), `PETROL_AVG_MILEAGE` (15.0), `DATABASE_URL` (unused
until PROMPT_8). Frontend: `VITE_API_BASE` (default `http://localhost:8000/api`); PROMPT_9 uses
`VITE_API_URL` for the deployed backend URL.

---

## 19. EVERYTHING ACHIEVED & CORRECTED SO FAR (session log)

Git log (main, newest first) tells the v2 story (all commits staged from `PROJECT/`):

- `a5348d3` — **PROMPT_4/5/6**: search+reliability+TOPSIS, LangGraph live layer, glassmorphism
  frontend (**84 tests pass**, `tsc -b` + `vite build` clean). Big one — see the four sections below.
- `6f29acf` — "worked till the 3rd prompt file" (PROMPT_3 era wrap-up).
- `9c631bd` — Long-haul bus→metro rides on ALL routes (fix capped-route skip) + fix reverse-shape
  duration slice producing 1-min stubs; Rajanukunte direct-285-to-Majestic regression test.
- `523197c` — Long-haul bus→metro interchange rides: 285 from Yelahanka → Kempegowda Bus Station
  (Majestic) → Purple metro to MG Road (2 hops, ₹60).
- `18c5c8c` — Fix metro interchange options: split combined hub lines, dedup metro stations, cap
  forward walk at 16, fix metro path prefix double-bug.
- `5aadb08` — **PROMPT_3 segment builder API**: interactive hop planner (`segments` +
  `segment-next`), FastAPI app (main/api), 5-min cache, 11 acceptance tests.
- `2e2b8ff` — **PROMPT_2 routing graph + N-hop route finder**: full GTFS bus topology, metro/rail,
  grid walk edges, best-first A* with schedule resolution.
- `013cf4d` — Apply route-name cleaning at GTFS pickle load (9 leaked suffix names), re-save pickle.
- `b50e180` — Wire Neon `DATABASE_URL` + run GraphHopper (Bangalore crop, car+foot): fix duplicate
  point param bug, add docker-compose + config.
- `b48de93` — **PROMPT_1 data layer**: GTFS loader (pickle reuse, name resolution, shape-projected
  segments), fare engine, station DB, GraphHopper client.
- `3f442e2` — **VOYAGER v2 fresh-build PROJECT folder**: 9 build prompts, data assets, GTFS pickle.

**PROMPT_4 session (search/scoring)** — `google_maps_client.py` (Places New/Geocoding/Directions,
≥40% keyword overlap, 15km radius, 4-decimal dedup), reliability formula + `_score_from_rating`
(never trusts external), SerpAPI review chain (real `user_reviews.most_relevant`), local sentiment
(lexicon + optional HF), `topsis_engine.py` (8-factor numpy, `TopsisWeights`), `ride_pricing.py`
(SerpAPI live + Karnataka govt formula), endpoints search/nearby/enrich/verify/reviews/ride-prices,
`test_prompt4.py` (28 tests).

**PROMPT_5 session (live layer)** — weather client (Open-Meteo), news engine (r/bangalore + DDG via
DataImpulse background loop, classify/geo-tag/LLM-summarize), `proxy_manager.py`, eRail train
scraper (48 codes), `backend/services/langgraph/` package (VoyagerLangGraph: parallel dispatch,
synthesis, route-context workflow), `test_prompt5.py` (20 tests).

**PROMPT_6 session (frontend)** — `frontend/` scaffolded (Vite react-ts), `index.css` glassmorphism
design system, `types/index.ts` contracts, `services/api.ts` typed client, `context/AppContext.tsx`
global state, `MainPage` (3-tab bottom-nav), `HeaderBar` (clock/weather/dark), `MapView` (Leaflet
pins/polylines/flyTo), `SearchPanel`, `DiscoveryPanel` (+ `/api/search/photo` proxy 307-verified),
`AToBPanel` (+ SegmentFlowView), `SegmentFlowView` (3-column hop window, breadcrumb, lazy
segment-next, map pan, complete screen), `TripPanel` (GPS journey), `NewsPopup` (LIVE 2-min poll),
`vite.config.ts` `/api` proxy → `VITE_API_BASE`. Verified: build clean, dev server + proxy + 84
backend tests all green.

---

## 20. PROBLEMS → BETTER OPTIONS CHOSEN (error glossary — DO NOT REGRESS)

1. **OSRM public URL** (`router.project-osrm.org`) used instead of local — all paths became
   interpolated straight lines. **Better choice**: v2 uses **local GraphHopper (8080)**; when it's
   down the interpolated path is *flagged* (dashed), never silent. OSRM is banned.
2. **LLM-generated fake reviews** with fake Indian names when scraping failed. **Banned** — no LLM
   review text ever; summaries only of real reviews.
3. **Ride price `total = pp * group`** double-charged a vehicle fare by passenger count.
   **Correct**: `total = vehicle_fare`, `pp = total / group`. Tested.
4. **GTFS route garbage** `"MF-28 JKLO-ISROQ-LGRNB"` uncut. **Fix**: `clean_route_short_name`
   at load + ingestion.
5. **`_gtfs` import-by-value bug** — `from transit_config import _gtfs` captured `None` at load;
   every GTFS call returned empty. **Fix**: v2 uses `app_state` live singletons.
6. **geodesic in hot loops** → 11.6s graph build. **Fix**: haversine + `_dist_cache` → 2.2s.
7. **SequenceMatcher loop** → 79s name pre-resolve. **Fix**: word-overlap + trigram
   `get_close_matches` → 7.7s (then 0s from pickle `name_map`).
8. **Aggressive metro direction filter** (`dest_to_dm > nm_dist_to_dest * 1.1`) blocked valid
   routes (Cubbon Park→MG Road). **Fix**: absolute `+ tolerance` (500m/2500m metro).
9. **300m circular guard** let routes loop. **Fix**: 800m `_is_visited`.
10. **Full-route shape fallback** drew the entire bus route (40km lines) instead of stop-to-stop
    slices. **Banned**: `get_stop_to_stop_segment()` only.
11. **GTFS 41s startup block**. **Fix**: lazy via `app_state`; pickle reuse (0.65s).
12. **Hardcoded dark hexes** in components (theme clash). **Rule**: CSS variables only.
13. **Shape-slice stub** — reverse-shape duration slice produced 1-min stubs on long rides (285).
    **Fix**: real duration for long reverse rides.
14. **Metro path prefix double-bug** — interchange path built with a duplicated prefix node. **Fix**.
15. **Capped-route skip** — routes whose transfer stop lay beyond the first few stops were dropped.
    **Fix**: metro-transfer search over ALL routes.
16. **`justdial_scraper` site blocking** → **DROPPED** in v2; place verification uses Google Places +
    SerpAPI instead.
17. **SerpAPI place_details key bug** — used `"place"` instead of `"place_results"`; reviews read
    from an int count instead of `user_reviews.most_relevant`; fields `user.name`/`snippet` instead
    of `username`/`description`. **Fix**: correct keys + field mapping + `_CACHE_VERSION=2`
    invalidates stale cache.
18. **Per-person vs vehicle fare confusion in the frontend** — `SegmentFlowView.tsx` previously
    swapped `[lat,lng]→[lng,lat]` in 9 places; Leaflet needs `[lat,lng]` (what the backend
    returns). **Fix**: single `legGeometry()` swap keeps it right.
19. **Path shown only at journey end** — geometry wasn't drawn per confirmed hop. **Fix**: map
    updates after each hop confirm.
20. **Full-shape fallback in path chain** (NES Office→Doddaballapura random lines). **Fix**:
    removed `full_shape` from the fallback chain entirely.
21. **GTFS time filter returning empty** — future-departure filtering emptied results. **Fix**:
    fallback to all departures.
22. **Direction filter** handling routes starting/ending at source stop — relaxed cos_angle
    0.5→0.3, early-returns True when route endpoint closer to dest; distance check absolute (+0.5).
23. **No CORS middleware** — noted: the frontend relies on the Vite dev proxy (`/api` → :8000);
    Render deploy must set the proxy or CORS explicitly (PROMPT_9).

---

## 21. TESTS & QA (all 84, per file)

Command: `python -m pytest tests/ -q` from `PROJECT/` → **84 passed** (~47s, no Docker/API).

### `test_data_layer.py` (12)
route-name cleaning (incl. leaked-suffix regression), pickle fast-load, Majestic name resolution,
known-unresolvable acronym (`hnrj`), real routes at Majestic, stop-to-stop segment both directions,
no-nan stop names, spatial query <5ms, metro Purple+Green only, fare spot-checks, surge,
ride per-person split.

### `test_route_finder.py` (10)
graph node counts (2000+ bus / 68 metro / ≥22 rail), walk edges present, metro edges carry line,
bus nodes have bus edges, bus-transfer paths MG→Koramangala, pure-metro interchange MG
Road→Yelachenahalli (both lines), forward-progress no-backtracking, walk-only when close, ride
always present, warm timing ≤5s.

### `test_segment_builder.py` (14)
T1 Wonderla (real options, full contract shape, real GTFS bus legs, connectedFrom chains,
forward-progress), T1 bus legs real GTFS, T2 multi-bus to MG Road, T3 time chaining
(`>= arrival + 4min`), T4 short-hop walk-primary-no-cab, segment-next journey-complete, budget
exceeded flag (₹5 → every paid option exceeds, walk never), segments cached (<50ms identical),
timing warm ≤3s, metro interchange both lines (Purple + Green from KBS, real distance/duration,
metro_line geometry), long-haul bus→metro transfer (285 → metro corridor, >10km, >30min, chains
into Purple), Rajanukunte direct-285-to-Majestic (distance >10km, duration >30min).

### `test_prompt4.py` (28)
Reliability (high scores green, negative drag, permanently-closed always red, temporarily-closed
capped yellow, unknown status no penalty, no-reviews explainable, pin_class edges), Sentiment
(positive >0.6, negative <0.4, negation flips, neutral 0.5, empty average, average over reviews),
TOPSIS (best-on-cost, best-on-time, weather prefers covered mode in rain, single route best-match,
identical share rank 1, cc normalized, empty → [], custom weights normalize), RidePricing (total
== vehicle fare not pp×group, all 5 providers estimated, fare grows with distance, live overrides
estimate, bad live ignored, labels, surge never zero/negative).

### `test_prompt5.py` (20)
Weather (WMO labels, None on network failure), News (classify, geo_tag silk board, dedup+TTL, merge
caps 25 sorts, relevant keyword filter, relevant proximity sort), Train (codes mapped, partial
match, unknown → None, fallback flagged NOT live, fallback pairs ≥7), Proxy (not available without
creds, never referenced by API-key clients), LangGraph (live context all groups, rain feeds
factors, failing tool never blocks, ask degrades without LLM, time_of_day factor).

### QA commands
- Backend tests: `python -m pytest tests/ -q` (in `PROJECT/`) → **84 passed**
- Backend compiles: `python -c "from backend.api.routes import search_photo; print('ok')"`
- Frontend: `cd frontend; npx tsc -b` and `npm run build` → 0 errors
- Server: `python -m uvicorn backend.main:app --port 8000` → `GET /api/health`
- Dev frontend: `cd frontend; npx vite --port 3000` → `GET http://localhost:3000/` 200, `/api/*` proxied
- (Planned, PROMPT_7) `scripts/benchmark.py` + `test_no_fake_data.py`

---

## 22. PERFORMANCE BUDGETS & BENCHMARKS

| Operation | Budget (spec) | Current v2 measured |
|---|---|---|
| GTFS load from pickle | ≤1s | **0.65s** |
| Name pre-resolve (first run) | — | **7.7s** (then 0s from pickle `name_map`; 1696/2972 cached) |
| A* graph build | ≤3s | **~2.2s** (2900+ bus / 68 metro / ≥22 rail nodes, ~54k edges) |
| Server startup | ≤3s | ~3s (lazy) |
| `segments` first call warm | ≤3s | test asserts <3s |
| `segment-next` warm | ≤2s | ✓ |
| Route finding warm | ≤5s | test asserts <5s |
| Spatial query | ≤5ms | test: <0.005s avg |
| `segments` cache hit | — | <50ms (test) |
| Route-plan cache hit | ≤100ms | ✓ (10-min TTL) |
| LangGraph live gather | ≤6s worst (live down) | ✓ (per-tool timeouts, failing tools None) |
| Frontend `tsc -b` | 0 errors | ✓ |
| Frontend bundle | — | 426 KB JS / 30 KB CSS (gzip ~131 KB) |

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

# 3) Frontend
cd PROJECT\frontend
npx vite --port 3000                       # http://localhost:3000 (proxies /api → :8000)

# 4) Tests
cd PROJECT
python -m pytest tests/ -q                # 84 passed
```

`docker-compose.yml` is **graphhopper only** (backend/frontend run locally per spec; OSRM from v1
is no longer used — don't start it for v2).

---

## 24. WHAT TO DO NEXT — PROMPT_7, 8, 9 in detail

### 24.1 PROMPT_7 — ML + integration tests + fake-data audit (NEXT)
**ML model (exactly ONE real trainable model):** a **traffic-crowd slowdown index**
`E[slowdown | dayofweek, hour, area]` from `traffic_logs.csv` (7.5MB quarterly), feeding **TOPSIS
factor #4**. Primary: gradient-boosted regression (LightGBM/XGBoost) or small MLP on features
`[dayofweek, hour_bucket, area_id, is_weekend, is_rush]`, time-split train/validate. Honest
fallback: if too few samples / poor MAE → time-of-day crowd model labeled `model:"time_of_day"`.
Contract: `predict_slowdown(lat,lng,dt) -> float` in [1.0, 1.8]; `model_info() -> dict {model, mae,
trained_at, coverage}`. Served `GET /api/routes/traffic-model-info`;
`traffic_factor = max(directions_ratio, predicted_slowdown)`. Lazy load ≤1s, never blocks startup.

**Integration tests:** `conftest.py` (small gtfs, db, graphhopper stub, serpapi stub, weather
stub), plus **7 required**: (1) Wonderla end-to-end (walk→Puttenahalli bus→Rajanukunte chains,
departure ≥ arrival+4, deep segment-next connected-only); (2) Govt School→MG Road multi-bus
(507-D→G-9/SBS→349-K) AND direct G-9; (3) **`test_no_fake_data.py` "THE BIG ONE"** — walker over
every API payload: routeNumber ∈ GTFS routes, fares match fare engine, no unlabeled estimated,
no LLM-copied review text, no bus at zero-departure stop unless `not_running`; (4) live-failure
resilience (all stubs raise → ≤6s, no fake values); (5) reliability determinism; (6) TOPSIS sanity;
(7) graph correctness. Test doubles: GraphHopper stub (real Docker opt-in `GH_LIVE=1`), live APIs
stub with `LIVE_API=1`; full-cache test marked `@pytest.mark.slow`.

**`scripts/benchmark.py`** — fails if over budget: server init warm ≤3s; segments first call ≤3s;
segment-next ≤2s; route finding ≤5s; all-live-down planning ≤6s; `tsc --noEmit` 0 errors; pytest
green.

**Data hygiene audit (8 checks)** over every endpoint's real output: bus = real cleaned GTFS
numbers/times; metro = Purple/Green only; trains only when eRail data (fallbacks flagged); ride
prices live OR labeled Estimated; reviews real + local sentiment + LLM summary (no fabricated
text); news background-scraped/classified/summarized (never hardcoded); reliability formula output
(never random/LLM); photos from Google Places or icon (no stock placeholders); paths = GTFS
shape/metro line/GraphHopper (straight lines only when flagged).

### 24.2 PROMPT_8 — Trip Planner (design locked in grilling)
A destination-and-itinerary system **on top of** the A→B engine. Self-containment rule: defines
OWN contracts + OWN `TripTransportInterface` (`top1_route(src,dest,time,group,budget) ->
TransportHint`), never imports parent-module types; the A→B engine implements the interface.
Locked scope: multi-day 2–5 days; **Bengaluru** = curated ~100-place dataset + live Google Places +
Reddit/proxy signals; **other cities** = generic Google Places only (missing = `Unknown` neutral);
stay/accommodation **only for other cities**; transport **on-demand only** (never at generation);
Postgres persistence (`DATABASE_URL`); geo-cluster + travel-cost-aware day assignment; within-day
TSP + time-of-day constraints; LLM writes only "why recommended" + summaries.
Files: `trip_planner.py, trip_places.py, trip_budget.py, trip_assign.py, trip_store.py,
transport_interface.py, api/trip.py`, data `trip_places_bengaluru.json`. Postgres: 4 idempotent
tables (`trips`, `trip_days`, `itinerary_items`, `place_cache`). Guided input Steps 1–7 →
"Generate My Trip" (never on partial data). Relevance =
`0.40*interest_match + 0.25*rating_norm + 0.20*suitability + 0.10*time_align + hidden_gem_bonus`.
Budget engine with running totals + overspend alternatives (side-by-side deltas, never silent
downgrade) + surplus upgrades. Output: day-by-day timeline, numbered pins w/ day colors + animated
moves, summary donuts + LLM banner. 8 endpoints (see Appendix A). Budgets: generation ≤8s,
transport-hint ≤3s, recompute ≤4s, Postgres <50ms.

### 24.3 PROMPT_9 — Deployment (Render free + Neon) (design locked)
3 tiers: **Local** (full experience — backend:8000, frontend:3000, graphhopper:8080) · **Render**
(backend + frontend free tier, `render.yaml`: `voyager-backend` env python on
`https://voyager-backend.onrender.com`, `voyager-frontend` env static →
`https://voyager-frontend.onrender.com`, build `cd frontend && npm install && npm run build`,
`staticPublishPath frontend/dist`, env `VITE_API_URL`) · **Neon Postgres** (trips).
**No GraphHopper on Render** (no Docker on free tier) → walk/drive legs interpolated **flagged**
"Approx path"; bus legs stay real GTFS shapes; metro real polylines (honesty table in the prompt).
**Commit the 76MB `gtfs_cache.pkl`** (≤100MB GitHub limit) so Render cold boot ~2–3s; `.gitignore`
raw `bmtc_gtfs/` (~190MB); rebuild path `scripts/build_gtfs_cache.py`. Cold start accepted:
frontend shows "Waking up…" splash; optional cron-job.org ping to `/health` every 10 min.
DataImpulse works identically from Render (~3.3GB/mo within 5GB). In-memory caches ephemeral on
Render (only Postgres durable). Env var checklist (11): DATABASE_URL, OPENROUTER_API_KEY,
OPENROUTER_MODEL, GEMINI_API_KEY, SERPAPI_API_KEY, GOOGLE_MAPS_API_KEY, DATAIMPULSE_USER/PASS/HOST,
FUEL_PRICE_PER_LITER, PETROL_AVG_MILEAGE. Post-deploy checklist (9 items): /health, /docs,
search places real, segments real GTFS, news proxy-scraped, trip edit persists across redeploy,
frontend works, cold start splash, `test_no_fake_data` scan. **Demo story**: demo locally for real
road paths; point judges at Render URL.

### 24.4 Immediate next steps (right after this doc)
1. Start **PROMPT_7**: `scripts/train_traffic_model.py` + `predict_slowdown`/`model_info`,
   `test_no_fake_data.py`, `conftest.py`, integration tests, `scripts/benchmark.py`.
2. Wire the **live SerpAPI ride overlay** (`merge_live_prices`) into `SearchService.ride_prices`
   and `PricingTool.run` (currently `live_options=None` — the live path exists but is unused).
3. Add `VITE_API_URL`/CORS for the future Render deploy.

---

## 25. APPENDIX A — FULL API ENDPOINT REFERENCE

**Routers:** `routes_router` mounted at `/api/routes`, `search_router` mounted at `/api`.

| # | Method | Path | Request | Returns |
|---|---|---|---|---|
| 1 | POST | `/api/routes/segments` | `{source, destination, group_size, budget, current_time?}` | `{journey, segments[2], probes[], warnings[], journeyComplete:false, timeline[]}` |
| 2 | POST | `/api/routes/segment-next` | `{journey, chosen_legs:[{optionId,arrivalTime,destinationStop}], group_size, budget}` | next segment OR `journeyComplete:true` + `arrival` + timeline |
| 3 | GET | `/api/search/places` | `q`, `lat?`, `lng?` | `{query, places:[Place]}` |
| 4 | GET | `/api/search/nearby` | `lat`, `lng`, `radius_m=2000`, `keyword=""`, `categories=""` (CSV) | `{places:[Place]}` |
| 5 | POST | `/api/search/enrich` | `{place}` | `PlaceDetails` (or `{"error":"invalid place payload"}`) |
| 6 | POST | `/api/search/verify` | `{name, lat, lng}` | `{verified: Place\|null}` |
| 7 | POST | `/api/rides/prices` | `{origin, destination, group_size}` | `{prices:[RidePrice]}` |
| 8 | POST | `/api/langgraph/route-context` | `{source, destination, group_size, budget, current_time?, place?}` | `LiveContext` dict (weather/traffic/news/prices/reviews/factors/errors/completed_at) |
| 9 | POST | `/api/langgraph/ask` | `{message, lat?, lng?, context?}` | `{live_context, synthesis:{answer, factors}}` |
| 10 | GET | `/api/search/news` | `lat?`, `lng?`, `keyword=""`, `limit=10` | `{items:[news]}` |
| 11 | GET | `/api/search/weather` | `lat`, `lng` | weather dict or `{"condition":"unavailable"}` |
| 12 | GET | `/api/search/photo` | `name`, `max_width=400` | 307 Redirect to real Google photo URL, or `{"error":"no photo"}` |
| 13 | GET | `/api/routes/live-trains` | `from_station`, `to_station` | `{trains[], source: live\|fallback\|none, note}` |
| — | GET | `/api/health` | — | `{status:"ok", services_loaded}` |

**Planned (PROMPT_7/8/9):** `GET /api/routes/traffic-model-info`, `POST /api/trip/plan`,
`GET/PUT /api/trip/{id}` + `/api/trip/{id}/items`, `POST /api/trip/transport-hint`,
`GET /api/trip/places`, `POST /api/trip/places/suggest`, `GET /api/trip/{id}/summary`.

---

## 26. APPENDIX B — KEY CONSTANTS

**Graph (transit_graph.py):** BUS_SPEED 18 km/h, METRO_SPEED 36, WALK_SPEED 5, TRANSFER_PENALTY 4
min, BUS_DWELL 0.3, METRO_DWELL 0.25, INTERCHANGE_FIXED 5 min; walk radii bus↔bus 500m, bus↔metro
1000m, bus↔rail 3000m.

**Route finder (route_finder.py):** entry radii bus 2km / metro 3km / rail 5km; entry tops 3/2/1;
MAX_LEGS 6, MAX_PATHS 12, MAX_DUP_PER_SIG 3; VISITED_RADIUS 800m; FORWARD_TOL 500m / metro 2500m;
BUDGET_SENSITIVITY ₹8/min; search deadline 4s; BUFFER 3 min; MAX_WAIT 45 min; WALK_ONLY_KM 2.0;
cache TTL 600s.

**Segment builder (segment_builder.py):** bus/metro candidate radius 3000m, rail 5000m;
walk-to-board 1500m; forward tol 500m/2500m; BUFFER 4 min; DEP_WINDOW 180 min; caps: 5 walk, 3 bus
board, 2 metro board, 4 routes/stop, 3 arrival stops/route, 2 metro-transfers, 6 seg2 anchors, 40
seg2 options, 6 probes; WALK_OPTION_MAX 2000m; WALK_PRIMARY 1500m; cache TTL 300s; journey-complete
radius 500m.

**Fares:** BMTC nonAC/AC slabs; metro slabs (both lines); KIA per-stop max; rides UberGo/OlaMini
24/km (min 85), XL 32/km (min 130), Auto 20/km (min 40), Rapido 5/km (min 25); surge 1.2/1.5/1.8.

**Search/scoring:** BANGALORE_CENTER (12.9716,77.5946); BANGALORE_RADIUS_KM 15.0;
MIN_KEYWORD_OVERLAP 0.40; DEDUP_RND 4; nearby maxResultCount 20; review cap 24 (slice 5 on frontend);
reliability weights 0.5/0.3/0.2; pin thresholds 70/50; TOPSIS weights listed in §12.4.

**Caches (all in-memory):** GTFS pickle 0.65s load; graph built at init ~2.2s; Maps/Serp 24h (2000
entries); ride prices 15min; weather 15min; trains 15min; route plans 10min; segments 5min; news TTL
4h (max 25).

**Frontend:** NEARBY_CATEGORIES = 19 chips; radius slider 0.5–10km default 2; suggestion debounce
300ms ≥2 chars; news poll 2 min; axios timeout 120s; fuel ₹110/L; mileage default 15 km/L.

---

## 27. APPENDIX C — HONEST-FALLBACKS & DELIBERATE DECISIONS (the "no fake data" map)

1. **BMTC has no live API.** Every bus time is a **schedule**, labeled `source:"schedule"` /
   `status:"scheduled"`. Never pretend live.
2. **14 bus stop names have no GTFS match** (acronyms like `hnrj`, `ggmc`). They resolve to `None`
   → "No real-time data", never a fabricated match.
3. **Uber/Ola/Rapido block scrapers.** v2 uses SerpAPI directions when available + Karnataka
   govt-mandated formula, both **labeled estimated** when not live. (Live merge implemented, not yet
   wired into the two service paths — next steps.)
4. **JustDial is dropped.** Place verification uses Google Places + SerpAPI instead.
5. **Metro Yelahanka / Blue Line don't exist yet** — excluded everywhere. Only Purple + Green.
6. **GraphHopper down / not deployed** → walk/drive legs interpolated and **flagged**; bus/metro
   legs stay real (GTFS shapes / line polylines).
7. **Trains**: only shown when eRail.in has real data; 7 city-pair fallbacks flagged
   `source:"fallback"` + "NOT live". Never invented.
8. **Reviews**: never LLM-generated. Real SerpAPI + local sentiment; LLM only summarizes.
9. **Reliability score**: always recomputed from live inputs; never trusts an external field.
10. **Render free tier**: no Docker → no GraphHopper; ephemeral disk → Postgres for durable data;
    cold starts → "Waking up…" splash.
11. **Budget overrun** → `exceedsBudget` grey-out (never silent omit, so the user understands why).
12. **Interpolated geometry** is always visually distinguished (dashed + "approx path").
13. **LiveContext** degrades per-source: failing tool → `{"condition":"unavailable"}` /
    `{"label":"unavailable"}` — routing always completes (gather:true, required:false).
14. **LLM gone** → deterministic fallback text ("Live data partially unavailable.",
    "Based on N Google reviews (reliability P%).").
15. **News loop down** → `relevant()` serves last-good cache (honest empty if never ran); frontend
    shows "No news items yet." Never hardcoded headlines.

---

*End of VOYAGER v2 Master Knowledge Base. Next session: build PROMPT_7 per §24.1, then wire the
live SerpAPI ride overlay, then PROMPT_8, then PROMPT_9. Run `pytest tests/ -q` + `npx tsc -b`
before every commit.*
