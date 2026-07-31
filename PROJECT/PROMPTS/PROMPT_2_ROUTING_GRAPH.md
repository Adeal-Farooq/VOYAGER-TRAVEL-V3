# PROMPT 2 — VOYAGER v2 Routing Graph & N-Hop Route Finding

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** A* transit graph sahi se banana hai — bus stops, metro (Purple/Green), rail stations sab nodes, saath me walk-transfer edges (bus↔bus 500m, bus↔metro 1km, bus↔rail 3km). Har hop destination ki taraf hi hona chahiye, aage peeche ghoomna nahi. Route finding dynamic depth ka hona chahiye (fixed 4 leg force nahi) — jo user ki journey ko sahi kare. Bus legs ka geometry GTFS shapes.txt se real road path lena hai, walk/car GraphHopper se. Kabhi fake bus numbers/timings nahi — GTFS schedule hi dikhega. Circular routing band karna hai (800m visited guard). Ye graph PROMPT_1 ke data layer ke upar banta hai.

---

## 1. Goal

Build the **unified transit topology + pathfinder** for VOYAGER v2. This is the *brain* that finds multi-hop routes (bus → walk → bus → metro → walk → dest) using real GTFS schedule data, real geometry, and real fares. It feeds the segment builder (PROMPT_3) and TOPSIS scoring (PROMPT_4).

## 2. Consumed From PROMPT_1

- `TransitDatabase.all_bus_stops() / all_metro_stations() / all_rail_stations()`
- `GTFSService.get_routes_at_stop(stop_name, after_time)` → `RouteDeparture[]`
- `GTFSService.get_stop_to_stop_segment(route_id, from_stop_id, to_stop_id)` → real polyline
- `GTFSService.clean_route_short_name()`, `resolve_stop_name()`
- `FareEngine.bmtc_fare / metro_fare / kia_fare`
- `GraphHopperClient.route(mode, ...)` for walk/car leg geometry
- `data_schema.TransitNode`

## 3. Files

```
backend/services/
├── transit_graph.py    # TransitAstarGraph: node/edge construction + query
├── route_finder.py     # N-hop path enumeration (dynamic depth), schedule lookup, geometry assembly
└── transit_models.py   # Route, Leg, TransitStop dtypes consumed by scoring + segment builder
```

## 4. Graph Construction (`transit_graph.py`)

### 4.1 Nodes
- **Bus stop node** for every GTFS-resolved stop (~2900+ after name resolution from `bmtc_all_stops_master.csv`)
- **Metro node** per station in Purple + Green lines (no Blue/Yelahanka)
- **Rail node** per station in `karnataka_railway_stations.json`

### 4.2 Edges
| Edge type | Condition | Weight basis |
|---|---|---|
| Same-route bus edge | two stops consecutive-ish on same GTFS route/trip (allow 1 skipped stop tolerance) | scheduled travel time from `stop_times.txt`; distance = GTFS shape length |
| Same-line metro edge | adjacent stations on Purple or Green | scheduled metro travel time (line speed); distance = station spacing |
| Bus↔bus walk transfer | ≤ 500m apart | walking time @ 5 km/h + transfer penalty (~4 min) |
| Bus↔metro walk transfer | ≤ 1000m | walking time + transfer penalty |
| Bus↔rail walk transfer | ≤ 3000m | walking time + transfer penalty |
| Metro↔metro interchange | only at documented interchange (e.g. Majestic/Sampige Rd) | fixed 5 min + 1 min buffer |

### 4.3 Distance & Speed
- **Use `_haversine_dist`** (pure math) + `_dist_cache` dict — never `geodesic` in hot loops (this was the 11.6s→2.2s win before; keep it).
- Walk speed **5 km/h** in graph weights (NOT 20 km/h — that was a bug).

### 4.4 Hard Invariants
- **No circular routing:** a candidate next stop is skipped if already within 800m of any node already on the path (`_is_visited` guard).
- **Forward-progress rule (direction filter):** candidate next stop `S` is valid only if
  `haversine(S → final_dest) < haversine(current → final_dest) + 500m_tolerance`.
  This is the absolute check (NOT a relative `*0.9` — that broke valid routes before).
- **Route direction sanity:** for a bus leg, verify the trip's actual direction serves `S` before `dest` on that route (using stop sequence), with the relaxed cosine-angle threshold (0.3) and the early-return-True when the route's endpoint is closer to dest than source.
- **No fake departures:** a bus edge exists only if GTFS actually schedules that route at that stop around the requested time. If GTFS has no data for a stop → the stop is still a node for transfers, but legs from it are marked `real_time: false` with a "scheduled estimate" badge — never a fabricated bus number.

## 5. Route Finding (`route_finder.py`)

### 5.1 API

```python
@dataclass
class RoutePlan:
    legs: list[Leg]
    total_fare: float
    total_duration_min: int
    total_walk_km: float
    transfers: int
    per_person_fare: float   # for group

@dataclass
class Leg:
    mode: Literal["walk","bus","metro","train","ride"]
    route_number: str | None        # "500-A", "G-9", "KIA-9", "Purple"
    from_stop: str; to_stop: str
    from_lat, from_lng, to_lat, to_lng: float
    depart_time: str | None         # scheduled (schedule source)
    arrive_time: str | None
    duration_min: int
    fare: float
    geometry: list[tuple[float,float]]  # REAL path
    geometry_source: Literal["gtfs_shape","metro_line","graphhopper","interpolated"]
    status: Literal["scheduled","estimated","not_running"]  # "not_running" if outside service window
```

### 5.2 Algorithm

1. Resolve source/dest coordinates (from geocoding or user pin).
2. Find candidate entry nodes: **top 3 bus stops + top 2 metro + top 1 rail** within configurable radii (bus 2km, metro 3km, rail 5km).
3. Find candidate exit nodes near dest symmetrically.
4. Run **modified A\* (or best-first) that enumerates top-K paths** (K ≈ 8–15) across the graph, with:
   - edge weights = `time + transfer_penalty + fare_penalty(per-person fare / budget_sensitivity)`
   - a soft cap on legs, but **NOT a hard fixed 4** — allow up to N=6 legs; prune any branch that doesn't strictly reduce `haversine(→dest)` (forward-progress rule).
   - visited guard 800m.
5. For each path, **resolve actual departures:** walk the legs in order; at each bus/metro leg, query `get_routes_at_stop(stop, after_time=prev_arrival + buffer)`; pick the earliest valid departure (allow ±15min window). If the exact route from the graph is unavailable at that time, try alternate routes serving the same stop→dest progression.
6. Assemble geometry per leg:
   - bus → `get_stop_to_stop_segment()` (GTFS shape), fallback `GraphHopper car route` flagged `geometry_source: "graphhopper"`
   - metro → line polyline
   - walk → `GraphHopper foot route`, fallback interpolated FLAGGED
7. Compute fares per leg via `FareEngine`; total = sum; per-person = total/group_size for shared modes.
8. Return top-K `RoutePlan`s **unsorted** (sorting/TOPSIS is PROMPT_4's job).

### 5.3 Edge Cases (MUST handle)

- **Metro with no metro near source:** search ALL metro stations for the optimal bus→metro transfer (score by `bus_d + metro_d + walk_m`); this was a fixed bug before — keep the fix.
- **Metro→bus chaining:** from the arrival metro station, allow onward bus leg to dest.
- **Walk-only:** if `haversine(src→dest) ≤ 2km`, always include a walk-only route (free, `mode: "walk"`).
- **Direct ride:** always also emit a `"ride"` leg suggestion (Uber/Ola/Rapido pricing is PROMPT_4; here just the drive geometry + distance via GraphHopper car).
- **Train:** rail leg only when dest is within 5km of a rail station AND live/scheduled train data exists (eRail.in via PROMPT_5). If no train data → **do not invent a train leg.**
- **Late night / early morning:** if no schedule exists in window, mark bus legs `status: "not_running"` and prefer walk/ride.

## 6. Performance Budgets

| Operation | Budget (warm caches) |
|---|---|
| Graph build at init | ≤ 3s |
| Top-K route finding (≤6 legs) | ≤ 3s |
| Per-leg geometry assembly | ≤ 300ms/leg |
| Total `/routes/plan` call | ≤ 5s |
| In-memory cache hit (same src/dest within 10 min) | ≤ 100ms |

Cache: route plans keyed by `(src_hash, dest_hash, time_bucket_10min, group, budget_hash)` for 10 min TTL.

## 7. Acceptance Criteria

- [ ] Graph builds with ~2900+ bus + 50+ metro + 22 rail nodes, walk edges present
- [ ] `find_routes("Govt School Yelahanka 4th Phase" → "Wonderla")` returns real multi-hop paths: bus(507-D/…) → bus(KIA-9) → metro(Purple) → walk/bus — i.e., paths that actually exist in schedule
- [ ] `find_routes("MG Road" → "Koramangala")` returns bus↔bus transfer paths (walk edges work)
- [ ] Every leg has real geometry (GTFS shape / metro line / GraphHopper) — **no straight-line displacement legs** unless GraphHopper down AND flagged
- [ ] No route makes the user "go backwards" (forward-progress rule verified by test)
- [ ] No circular routes (visited guard verified)
- [ ] No fabricated bus numbers/timings anywhere in output
- [ ] Walk-only route appears when ≤2km
- [ ] Route finding for a known-good pair returns in ≤5s warm

## 8. Hand-off Contract (for PROMPT_3)

Consumed by segment builder:
- `RoutePlan`, `Leg` types (shared schema in `transit_models.py`)
- `RouteFinder.find_routes(...)` → `list[RoutePlan]`
- Ability to compute **leg-by-leg with time chaining** (needed by segment-next lazy fetch)
