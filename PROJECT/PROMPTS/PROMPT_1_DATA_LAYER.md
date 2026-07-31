# PROMPT 1 — VOYAGER v2 Data Layer

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** Hame BMTC GTFS, bus stops, metro (Purple + Green line, NO Blue Line / Yelahanka), KIA airport buses, railway stations, aur transit fares ka pura data layer ek saath sahi se load karna hai — fake data nahi, real datasets se. GTFS ka 67MB pickle cache REUSE karna hai, dobara 40 second ka startup block nahi chahiye. GraphHopper Docker se car/foot routes ke real road paths nikalne hain. Ye layer sabse pehle banna chahiye kyunki iske bina routing, segment builder, aur search sab tohdi ho jaata hai.

---

## 1. Goal

Build the **single source of truth** for all static transit data in VOYAGER v2. Every downstream module (routing graph, segment builder, search, scoring, pricing) reads from this layer. **No hardcoded route/timing/fare data anywhere else.**

## 2. Directory & Dataset References

All data lives in `PROJECT/DATA_FOLDER/` (do NOT modify these files):

| File | Content | Size | Use |
|---|---|---|---|
| `bmtc_gtfs/` (11 files) | Official BMTC GTFS: stops, routes, trips, stop_times, shapes, calendar, fare_attributes/rules | shapes 112MB, stop_times 80MB | A* graph, bus legs, shapes, scheduled times, route numbers |
| `processed/gtfs_cache.pkl` | 67MB pickle: 7271 shapes, 5077 stops, 429882 stop-times, `name_map` | 67MB | **REUSE** — do not re-derive from raw GTFS |
| `bmtc_all_stops_master.csv` | ~2972 BMTC bus stop names + coords + route lists | 2MB | Stop name → GTFS resolution |
| `bengaluru_metro_network.csv` | Namma Metro Purple + Green line stations | 8KB | Metro nodes/edges. **NO Blue Line, NO Yelahanka** |
| `kia_routes_fare_full.json` | KIA Vayu Vajra airport bus routes + fares | 22KB | KIA bus options |
| `transit_fares.json` | BMTC AC/non-AC/child/senior fare tables | 3.5KB | Bus fare calc |
| `karnataka_railway_stations.json` | 22 Karnataka rail station codes | 2.8KB | Rail nodes; live via eRail.in |
| `traffic_logs.csv` | Quarterly traffic data | 7.5MB | **NOT for this prompt** — ML prompt only |

## 3. Architecture

```
backend/services/
├── gtfs_service.py      # GTFS loader + cache (pickle) + fuzzy name resolution
├── fare_engine.py       # BMTC AC/non-AC/child/senior + metro + KIA fares
├── database.py          # In-memory station DB + spatial indexes (R-tree style)
├── graphhopper_client.py# GraphHopper HTTP client (Docker, car + foot profiles)
└── data_schema.py       # Pydantic models for all data-layer objects
```

## 4. Module Specifications

### 4.1 `gtfs_service.py` — GTFS Loader

**Contract:**
```python
class GTFSService:
    def __init__(self, cache_path: Path = DATA_FOLDER / "processed/gtfs_cache.pkl"): ...

    def load(self) -> None                 # load pickle if valid & fresh; else full load + save
    def get_stops(self) -> list[GtfsStop]
    def get_routes_at_stop(self, stop_name: str, after_time: str | None = None) -> list[RouteDeparture]
    def get_shape_path(self, shape_id: str) -> list[tuple[float, float]]  # [lat, lng] ordered
    def get_stop_to_stop_segment(self, route_id: str, from_stop_id: str, to_stop_id: str) -> list[tuple[float,float]]
    def resolve_stop_name(self, name: str) -> str | None     # fuzzy match using name_map
    def clean_route_short_name(self, raw: str) -> str        # "MF-28 JKLO-ISROQ-LGRNB" → "MF-28"
```

**Rules (NO exceptions):**
- **Reuse `gtfs_cache.pkl`.** Only rebuild from raw GTFS if the pickle is missing/corrupt or a rebuild flag is set. First-load of raw GTFS may take ~40s; do it once, save pickle.
- `name_map` (1696/2972 pre-resolved names) must be read from the pickle. On first-ever run, re-run pre-resolution with the fast path: word-overlap index → trigram-filtered `get_close_matches` → substring fallback. Persist result.
- 14 stop names have NO GTFS match (e.g. "hnrj", "ggmc", "pesitelc"). These stay unresolved; downstream marks them "No real-time data" — **never fabricate a match**.
- Route number cleaning: strip terminal whitespace/hyphen garbage via regex, applied at both GTFS load AND csv stop-source ingestion.
- All time handling: `HH:MM:SS` strings in GTFS; convert to minutes-of-day ints for filtering. Provide both.
- Scheduled times only. **Label everything as `source: "schedule"`.** BMTC has no official live API — do not pretend otherwise.

### 4.2 `fare_engine.py` — Fares (pure functions, no I/O)

**Contract:**
```python
@dataclass
class FareResult:
    amount: float          # rupees
    currency: str = "INR"
    per_person: float      # amount / group_size when relevant
    rule: str              # which fare rule applied (e.g. "bmtc_nonac_adult", "metro_purple")
    is_estimated: bool = False

def bmtc_fare(route_class: Literal["ac","nonac","kia"], dist_km: float,
              passenger_type: Literal["adult","child","senior"]) -> FareResult
def metro_fare(dist_km: float, line: Literal["purple","green"]) -> FareResult
def kia_fare(route_id: str) -> FareResult                      # from kia_routes_fare_full.json
def surge_multiplier(hour: int, weekday: bool) -> float         # peak/night surge for rides
def ride_fare_range(ride_type: str, dist_km: float, group_size: int) -> tuple[FareResult, FareResult]
```

**Fare tables (from `transit_fares.json`):**
- BMTC non-AC: adult / child (half) / senior (adult − ₹0.75), distance-slab based
- BMTC AC: separate slabs (adult/child/senior)
- KIA: from `kia_routes_fare_full.json`
- Metro: distance-based per line
- These are **static, fixed prices** — always truthful to the JSON. Do not invent slabs.

### 4.3 `database.py` — In-Memory Station DB

**Contract:**
```python
class TransitDatabase:
    def __init__(self): ...   # load metro CSV, bmtc_all_stops_master.csv, rail json, kia json
    def metro_stations(self, line: str | None = None) -> list[MetroStation]
    def bus_stops_near(self, lat, lng, radius_m: float) -> list[BusStop]       # spatial index
    def metro_near(self, lat, lng, radius_m: float) -> list[MetroStation]
    def rail_near(self, lat, lng, radius_m: float) -> list[RailStation]
    def routes_for_stop(self, stop_name: str) -> list[str]
    def all_bus_stops(self) -> list[BusStop]
    def all_metro_stations(self) -> list[MetroStation]
    def all_rail_stations(self) -> list[RailStation]
```

**Rules:**
- Bus stops from `bmtc_all_stops_master.csv`; **skip any stop whose name is `nan`/`none`/`null`** (data hygiene).
- Spatial indexes: grid or simple sorted-lat/lng binary-search buckets; must support "nearest N within radius" in <5ms for 3000 stops.
- Metro: **Purple + Green lines only.** Yelahanka and any Blue Line entries MUST be excluded (line under construction, not operational).
- Every station object: `name, lat, lng, line(s), zone/hub_flag`.

### 4.4 `graphhopper_client.py` — Road Routing (Docker)

**Setup (docker-compose addition):**
```yaml
graphhopper:
  image: ghcr.io/graphhopper/graphhopper:latest
  ports: ["8080:8989"]
  volumes:
    - ./osrm-data:/data          # or a new gh-data dir with Karnataka PBF
  command: ["/data/karnataka-latest.osm.pbf"]
  profiles: car, foot            # configured in config.yml
```
Use a Karnataka/India-extract PBF (~100MB — NOT the 50GB India full extract). Add `config.yml` with `graphhopper.datareader.file`, `graph.flag_encoders=car,foot`, elevation off.

**Contract:**
```python
class GraphHopperClient:
    def __init__(self, base_url: str = "http://localhost:8080", timeout_s: float = 3.0): ...
    def route(self, mode: Literal["car","foot"], lat1, lng1, lat2, lng2) -> GHResult | None
    def is_healthy(self) -> bool

@dataclass
class GHResult:
    geometry: list[tuple[float, float]]   # [lat, lng] ordered polyline
    distance_m: float
    duration_s: float
    mode: str
    points_encoded: bool = False
```

**Rules:**
- `route()` returns `None` on timeout/connection error — caller falls back (interpolated path **only when GraphHopper is down**, and the response must be flagged `path_source: "interpolated"`).
- Cache road routes in-memory keyed by `(mode, rnd(lat,lng,4), rnd(lat,lng,4))` for 24h to avoid re-hitting GraphHopper for repeated origin/dest pairs.
- Health check on startup; log a clear warning if unreachable so you never silently serve straight lines as real roads.

### 4.5 `data_schema.py` — Shared Pydantic Models

```python
class GtfsStop(BaseModel): id, name, lat, lng
class RouteDeparture(BaseModel): route_id, route_number, stop_name, scheduled_departure, destination_name, trip_id, shape_id
class BusStop(BaseModel): name, lat, lng, routes: list[str]
class MetroStation(BaseModel): name, lat, lng, lines: list[str], is_hub: bool
class RailStation(BaseModel): name, code, lat, lng
class TransitNode(BaseModel):            # union node for the routing graph
    id: str, kind: Literal["bus","metro","rail"], name: str, lat: float, lng: float, line: str | None, routes: list[str]
```

## 5. Performance Budgets

| Operation | Budget |
|---|---|
| GTFS load from pickle | ≤ 1.0s |
| GTFS full load (cold, first-ever) | ≤ 45s, happens once, then pickle saved |
| Bus stop name resolve (cached) | ≤ 10ms per name |
| Nearest-stops spatial query (3000 stops) | ≤ 5ms |
| GraphHopper route (warm, local) | ≤ 500ms |
| Full data layer init at server startup | ≤ 3s (lazy GTFS, eager DB) |

## 6. Fallback Chains (in priority order)

1. **GTFS cache:** pickle → raw GTFS full load → (never fabricate)
2. **GraphHopper:** local Docker → in-memory cache → interpolated (FLAGGED)
3. **Bus stop resolution:** exact match → name_map fuzzy → trigram fuzzy → `None` (marked "No real-time data")

## 7. Acceptance Criteria

- [ ] Server starts ≤3s with warm cache; GTFS loads ≤1s on first route request
- [ ] `get_routes_at_stop("Majestic")` returns real BMTC route numbers with scheduled times (post-cleaning)
- [ ] Route numbers are clean: no `MF-28 JKLO-ISROQ-LGRNB` garbage anywhere
- [ ] Metro DB has **no** Blue Line / Yelahanka entries
- [ ] GraphHopper Docker container runs; `route("foot", ...)` returns road-following polyline for a 2km walk
- [ ] No `nan`/`none`/`null` bus stop names in DB
- [ ] Fares match `transit_fares.json` slabs exactly (spot-check 5 cases)
- [ ] All modules compile: `python -c "from backend.services import gtfs_service, fare_engine, database, graphhopper_client, data_schema"`

## 8. Hand-off Contract (for PROMPT_2)

After this prompt, the routing prompt consumes:
- `TransitDatabase.all_bus_stops() / all_metro_stations() / all_rail_stations()`
- `GTFSService.get_routes_at_stop()` and `get_stop_to_stop_segment()`
- `GraphHopperClient.route()` for walk/car leg geometry
- `FareEngine.*` for per-leg fares
