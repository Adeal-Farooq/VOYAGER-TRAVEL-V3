# PROMPT 8 — VOYAGER v2 Trip Planner (Feature 3)

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** Third feature hai TRIP PLANNER — poora destination-and-itinerary system. Ye sirf point-to-point routing nahi; ye batata hai *kahan jaana hai, kis order me, kis time pe, aur kis budget me*. Multi-day trips (2–5 din) — **Bengaluru me specific data** (curated places + live Google Places + Reddit/proxy signals), **dusre cities me generic planning** (Google Places + stay). Ek din me cross-town zig-zag travel NAHI — places geographically cluster karke assign honge, travel-cost-aware, budget aur group size ke hisaab se. User jo place choose kare usse arrange sahi se karna hai (selection order me nahi), map pe numbering + per-day color + animated map moves. Transport har hop ke liye ON-DEMAND compute hoga (trip generate hone par nahi — user hop expand kare / din start kare tab) — A→B engine ka top-1 TOPSIS route, thin interface se. Stay sirf doosre cities ke overnight trips me. Sab kuch Postgres me persist (Your Trips reload pe bache) — Render free tier ki ephemeral disk pe SQLite file wipes ho jati hai, isliye free hosted Postgres (Neon/Supabase) use karna hai, `DATABASE_URL` se. LLM sirf "why recommended" lines aur summaries banata hai — place data/numbers KABHI nahi. Fake data kabhi nahi — jo field mile na, `Unknown` aur scoring me neutral.

---

## 1. Goal

Build the **Trip Planner** — a destination-and-itinerary planning system sitting ON TOP of the v2 A→B engine. It decides *what to see, in what order, at what time of day, within what budget*. It NEVER re-derives transport logic — it consumes a thin transport interface that the A→B engine implements.

**Self-containment rule (from user):** This module is "completely new" — it defines its OWN data contracts and its OWN transport interface. It does NOT import parent-module types. The A→B engine adapts to the interface, not the other way around.

## 2. Scope (locked in grilling)

| Decision | Value |
|---|---|
| Trip duration | Multi-day: 2–5 days (date-picker OR "N days" flexible mode) |
| Bengaluru | Specific data: curated ~100-place dataset + live Google Places + Reddit/proxy signals |
| Other cities | Generic: Google Places API only (rating/reviews/hours/coords/price_level/category); missing fields = `Unknown`, scored neutral |
| Stay/Accommodation | **In scope for other cities** (overnight). For Bengaluru multi-day (user is local) stay is optional/skipped, budget note explains why |
| Transport | **On-demand per hop** — never at itinerary generation. Trigger: user expands a hop, starts a specific day, or requests "plan between these two" |
| Persistence | Postgres (free Neon/Supabase) via `DATABASE_URL` |
| Day assignment | Geo-cluster + travel-cost-aware day redistribution (no cross-town days) |
| LLM | "Why recommended" lines + trip summaries ONLY. Never place data, fees, durations, or scores |
| Ranking | Deterministic weighted formula (below) |
| Map | Per-day numbered pins, per-day colors, connecting routes, animated map moves between places |

## 3. Files

```
backend/services/
├── trip_planner.py        # orchestration: inputs → plan → itinerary (deterministic)
├── trip_places.py         # curated Bengaluru dataset loader + Google Places generic enrichment
├── trip_budget.py         # per-place cost estimation, running totals, overspend/surplus
├── trip_assign.py         # geo-clustering + travel-cost-aware day assignment + within-day TSP
├── trip_store.py          # Postgres persistence (trips, days, items, place_cache) via DATABASE_URL
├── transport_interface.py # the contract the A→B engine implements (top-1 route)
└── api/trip.py            # FastAPI endpoints (below)

backend/data/trip_places_bengaluru.json   # curated dataset (seeded, verified)
```

## 4. Data Layer

### 4.1 Curated Bengaluru dataset — `trip_places_bengaluru.json`

~100 places (attractions, parks, museums, temples, markets, viewpoints, food spots, malls, offbeat gems). Per place:
```json
{
  "place_id": "bg_017",
  "name": "Lalbagh Botanical Garden",
  "coords": [12.9507, 77.5848],
  "category": "nature",
  "tags": ["nature", "photography", "relaxation"],
  "short_desc": "240-acre botanical garden with 1851 glasshouse and lake.",
  "visit_duration_min": 120,
  "entry_fee": {"adult": 30, "child": 10},
  "best_time": ["morning", "evening"],
  "crowd_by_slot": {"morning": "low", "afternoon": "high", "evening": "medium"},
  "opening_hours": {"mon": ["06:00-19:00"], "..." : "..."},
  "weekly_closure": null,
  "rating": 4.6,
  "review_count": 85000,
  "suitability": {"family_kids": true, "seniors": true, "physical_demand": false},
  "accessibility_notes": "Wheelchair accessible main paths",
  "verified": true
}
```
- **Seeding method:** Google Places API (real rating/reviews/hours/coords) → manual/first-run verification pass → store. Missing fields stay `null` (treated as Unknown/neutral) — never invented.
- **Live merge at plan time:** `trip_places.py` merges curated + live Google Places details for current hours/status/rating (cache 24h).

### 4.2 Generic enrichment (other cities)
- Google Places Text Search + Details (real: name, category, rating, reviews, hours, coords, price_level).
- Missing: visit_duration, entry_fee, best_time, crowd → **all `null` = Unknown**, scored neutral, UI shows "Not available".

### 4.3 Reddit/proxy qualitative signals (Bengaluru, LangGraph-linked)
- `news/review tools` (PROMPT_5/4) scan r/bangalore + Google review scan via DataImpulse proxy for a place → qualitative signals: `best_time_hint`, `suitability_hint`, `crowd_hint`. These are **hints only**, low confidence, merged into scoring as minor adjustments — never hard facts.
- If the scan finds nothing, no hint is added (no fabrication).

### 4.4 Postgres persistence — `trip_store.py`

Schema (Postgres-compatible, created idempotently at startup via `CREATE TABLE IF NOT EXISTS`):
```sql
CREATE TABLE trips (
  id BIGSERIAL PRIMARY KEY,
  destination TEXT NOT NULL,
  dest_lat DOUBLE PRECISION, dest_lng DOUBLE PRECISION,
  is_bengaluru BOOLEAN NOT NULL,
  start_date TEXT, end_date TEXT,   -- NULL in flexible "N days" mode
  num_days INTEGER NOT NULL,
  group_size INTEGER NOT NULL,
  group_type TEXT NOT NULL,          -- solo|couple|friends|family_kids|family_no_kids|seniors
  total_budget DOUBLE PRECISION NOT NULL,
  budget_per_person INTEGER NOT NULL DEFAULT 0,
  budget_split JSONB NOT NULL,       -- {"Stay":35,"Food":25,"Transport":15,"Attractions":20,"Misc":5}
  interests JSONB NOT NULL,          -- JSON array
  pace TEXT NOT NULL,                -- relaxed|balanced|packed
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  status TEXT NOT NULL DEFAULT 'draft'  -- draft|planned|editing
);
CREATE TABLE trip_days (
  id BIGSERIAL PRIMARY KEY,
  trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  day_number INTEGER NOT NULL,
  date TEXT,                         -- null in flexible mode
  title TEXT
);
CREATE TABLE itinerary_items (
  id BIGSERIAL PRIMARY KEY,
  trip_id BIGINT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  day_id BIGINT NOT NULL REFERENCES trip_days(id) ON DELETE CASCADE,
  position INTEGER NOT NULL,
  kind TEXT NOT NULL,                -- place|transport|meal|buffer
  place_id TEXT,
  name TEXT, coords JSONB,           -- JSON [lat,lng]
  category TEXT, tags JSONB,
  start_time TEXT, end_time TEXT,    -- "09:00"
  duration_min INTEGER,
  entry_fee DOUBLE PRECISION, food_cost DOUBLE PRECISION,
  transport JSONB,                   -- transport hint (may be null until on-demand)
  cost DOUBLE PRECISION DEFAULT 0,
  note TEXT                          -- "why recommended" line
);
CREATE TABLE place_cache (
  place_id TEXT PRIMARY KEY,
  payload JSONB NOT NULL,            -- JSON from Google Places / curated merge
  fetched_at TIMESTAMPTZ NOT NULL
);
```

## 5. Guided Input Flow (Steps 1–7, one screen per step, summary bar on top to edit previous)

1. **Destination** — autocomplete (city/region/landmark). Toggle: "I know where I want to go" vs "Suggest destinations" (→ ask 2–3 quick Qs: climate, max distance/time, theme → 3–5 suggestions with one-line reason).
2. **Duration** — date picker OR "N days" flexible mode (skip calendar-dependent logic when flexible).
3. **Group** — size + type (Solo/Couple/Friends/Family with kids/Family no kids/Seniors included). Group type **directly filters suitability**: family_with_kids down-ranks nightlife/bars, up-ranks parks/easy-walk; seniors down-rank heavy trekking/adventure.
4. **Budget** — total ₹; toggle "whole group" vs "per person" (normalize to total-group). Optional manual split (Stay/Food/Transport/Attractions/Misc); default 35/25/15/20/5 with sliders to adjust.
5. **Interests** (multi-select, recommend 3–5): Nature & Scenery, History & Heritage, Food & Local Cuisine, Adventure, Shopping, Nightlife, Relaxation/Wellness, Offbeat/Hidden Gems, Religious/Spiritual, Museums & Art, Photography Spots.
6. **Pace** — Relaxed (2–3 places/day), Balanced (3–4/day), Packed (5+/day).
7. **Summary screen** — editable cards for all inputs → **"Generate My Trip"** button (engine never runs on partial data).

## 6. Place Discovery & Ranking

### 6.1 Candidate pool
- Bengaluru: curated dataset ∩ live Google Places nearby (dedup by coords). Other cities: Google Places Text Search by interests/categories.

### 6.2 Relevance score (deterministic, weighted)
```
interest_match  = |place.tags ∩ user.interests| / |user.interests|            (0..1)
rating_norm     = place.rating / 5                                             (0..1)
suitability     = 1.0 fully suitable | 0.5 partially | 0 unsuitable
time_align      = 1.0 if low-crowd slot aligns with scheduled slot else 0.5
hidden_gem_bonus= 0.15 if offbeat tag AND user selected Offbeat else 0

relevance = 0.40*interest_match + 0.25*rating_norm + 0.20*suitability
          + 0.10*time_align + hidden_gem_bonus
```
- **"Why recommended" line** (LLM, allowed): e.g. "Matches your Interest in Heritage + highly rated + good fit for families." LLM NEVER writes scores/numbers — it explains, numbers come from the formula.
- **Diversity cap:** no single category >40% of included places, relaxed only when interests are extremely narrow (still avoid 5 identical cafes back-to-back).

## 7. Day Assignment & Ordering — `trip_assign.py`

1. **Geo-cluster:** k-means (or greedy nearest-neighbor) on place coords, `k = num_days`.
2. **Travel-cost-aware redistribution (KEY):** compute pairwise travel cost (haversine; transport time when hint already cached). Rebalance places across days to **minimize max daily travel distance** — a day must never force a cross-town lap. Budget per-day load also balanced. This is your "should not travel very far places at once in a day" requirement.
3. **Within-day ordering:** small-TSP via nearest-neighbor on travel cost (no crossing paths), then layer **time-of-day constraints**:
   - Sunrise/scenic → early morning
   - Indoor (museums/malls) → afternoon peak heat
   - Sunset/rooftop → evening
   - Nightlife → evening/night, only if selected
   - Conflict rule: time-of-day wins for that place; rest of day re-ordered distance-optimized around it.
4. **User-picked places:** whatever the user selects gets re-arranged by the same optimization (NOT kept in selection order).

## 8. Transport On-Demand — `transport_interface.py`

```python
class TripTransportInterface(Protocol):
    def top1_route(self, src: Coord, dest: Coord, time: str, group: int, budget: float) -> TransportHint | None:
        """Implemented by the A→B engine (PROMPT_2/3/4): returns TOPSIS rank-1 route."""
```
```python
@dataclass
class TransportHint:
    mode: str                 # bus|metro|train|cab|auto|walk|bike
    route_number: str | None
    duration_min: int
    fare: float
    per_person_fare: float
    geometry: list[tuple[float, float]] | None
    source: Literal["live","scheduled","estimated"]  # honestly labeled
    label: str               # e.g. "BMTC 500-A · 25 min · ₹18"
```
- **When computed:** (a) user expands a hop in the timeline, (b) user starts a day, (c) user taps "plan between these two". NEVER at itinerary generation.
- Transport blocks inserted visually between place blocks (Section 10). If `top1_route` returns None → honest gap: "No transport data available between these points" (no fake time/cost), prompt user to specify or skip.

## 9. Budget Engine — `trip_budget.py`

### 9.1 Per-place cost
```
entry_fee_total = entry_fee(adult) * adults + entry_fee(child) * children
food_cost       = avg_person_cost_in_tier * group_size   (only if place spans a mealtime)
transport_cost  = top1_route().fare                       (on-demand; 0 until computed)
```
- Food tier from Google `price_level` (1–4) mapped to ₹/person; if unknown → `Unknown` (treated as ₹0 with a "not estimated" note, never fabricated).

### 9.2 Running day totals (live-updating widget)
- Places count, total sightseeing time, total transit time, free/buffer remaining, running cost.

### 9.3 Overspend handling (proactive, side-by-side)
Per overspend instance, present concrete alternative pairs with cost deltas:
1. Swap paid attraction → free/cheaper same-theme nearby
2. Cheaper transport (bus over cab) if time budget allows
3. Lower-cost food option nearby
4. Trim lowest-ranked place from the day
Never silently downgrade — user picks.

### 9.4 Surplus handling
Suggest optional upgrades: better-rated restaurant, premium/guided experience, extra offbeat place. Clearly optional, never auto-added.

## 10. Stay / Accommodation (other cities only)

- Recommend stay location minimizing **average daily travel distance** to that day's cluster (not cheapest/highest-rated in isolation).
- Multi-stay allowed when zones are distant — flagged with packing/checkout friction; prefer single-stay when tradeoff small.
- Cost per night → "Stay" budget category.
- Bengaluru multi-day: user is local → stay skipped, note explains, budget share reallocated with a note.

## 11. Customization & Recalculation

- **Swap place** → replace with same-category/cluster alternative → recompute day order + transport + budget (no full regen).
- **Add custom place** → search/type → insert into most geographically sensible day/slot → recompute.
- **Remove place** → free time+budget; proactively suggest a replacement from ranked pool (only applied if accepted).
- **Reorder within day** → allowed; if new order meaningfully raises travel time/cost vs optimized → inline warning with delta ("This order adds ~25 min more travel — keep anyway?"), non-blocking.
- **End-to-end propagation:** any upstream change recomputes downstream day totals/budget — no stale numbers.

## 12. Output / Final View

### 12.1 Day-by-day timeline
`place block (timing e.g. "9:00 AM – 10:30 AM") → time spent → transport segment → next place` per day, clear day dividers. Same visual language as the A→B segment builder.

### 12.2 Map view
- Per selected day: **numbered pins** (1,2,3…) matching timeline order, connecting routes drawn, per-day color.
- Day toggle + "full trip" view (all days, distinct color per day).
- **Animated map moves** between places (flyTo as timeline advances / user steps through).

### 12.3 Final summary
- Budget donut by category vs set budget
- Sightseeing-vs-transit ratio bar/donut
- Top banner recommendation: "Best overall plan for your ₹X budget and interests" + one-sentence takeaway (LLM, allowed).

## 13. Edge Cases (explicit)

| Case | Behavior |
|---|---|
| Destination has too few matching places | Auto-widen interest filter to adjacent categories, tell the user |
| Duration > quality places available | Don't force-fill with low-score filler; suggest relaxed pace or a nearby secondary destination |
| Budget unrealistically low | State realistic minimum estimate; let user adjust or accept bare-bones plan (never a silent broken plan) |
| Contradictory inputs (Nightlife + family with kids) | Quick clarifying toggle ("Include nightlife for the adults?") before finalizing |
| No transport between two places | Honest gap in itinerary; prompt user to specify or skip |
| Weather/holiday/closures unknown | State assumptions plainly ("Assuming open — verify before your trip"); never confident guesses |
| Real-time factors (rain on an outdoor day) | Reorder/suggest indoor alternative when weather API says rain (via PROMPT_5 LiveContext) |

## 14. Endpoints

```
POST /api/trip/plan            {inputs} → itinerary (places assigned, no transport yet)
GET  /api/trip/{id}            full trip (timeline, days, totals)
PUT  /api/trip/{id}/items      swap/add/remove/reorder → recomputed day+budget
POST /api/trip/transport-hint  {trip_id, from_item_id, to_item_id} → TransportHint (on-demand)
GET  /api/trip/places?city=&interests=&limit=   candidate pool (+ "why recommended")
POST /api/trip/places/suggest  {q: climate, max_dist, theme} → 3–5 destination suggestions
GET  /api/trip/{id}/summary    budget donut + ratio + banner recommendation
```

## 15. Performance Budgets

| Operation | Budget |
|---|---|
| Itinerary generation (places only, no transport) | ≤ 8s (Bengaluru curated), ≤ 6s (generic) |
| Transport-hint per hop | ≤ 3s warm |
| swap/add/remove/reorder recompute | ≤ 4s |
| Postgres read/write | < 50ms |
| Place pool (Bengaluru, cached) | ≤ 2s |

## 16. Acceptance Criteria

- [ ] Guided input flow (Steps 1–7) works; summary editable; "Generate" never fires on partial data
- [ ] Bengaluru plan uses curated dataset + live merge; other cities use generic Google Places with `Unknown` fields neutral
- [ ] Day assignment: no day has a cross-town travel explosion (verified by a test measuring max daily travel distance)
- [ ] Within-day order honors time-of-day constraints and minimizes backtracking
- [ ] User-selected places are re-optimized (not kept in selection order)
- [ ] Transport appears ONLY on-demand (expand hop / start day / plan-between); generation makes zero transport calls
- [ ] TransportHint labeled live/scheduled/estimated; `None` → honest gap, never fabricated
- [ ] Budget engine: running totals, overspend alternatives side-by-side with deltas, surplus upgrades optional
- [ ] Postgres: trip survives reload AND server restart/redeploy; edit propagates end-to-end (no stale totals)
- [ ] Map: numbered pins per day, day colors, animated moves, full-trip view
- [ ] LLM only writes "why recommended" lines + summaries — never place data/numbers (tested)
- [ ] No fake place data anywhere; `Unknown` treated neutral
- [ ] `pytest tests/test_trip_planner.py` green (new test file); `tsc --noEmit` 0 errors

## 17. Build Order (per spec — do NOT one-pass)

1. Input flow (Steps 1–7) + summary screen
2. Place discovery + ranking (static/curated first, live later)
3. Day clustering + within-day ordering (no transport yet)
4. Transport interface + A→B engine adapter + on-demand wiring
5. Budget engine (estimation + overspend/surplus)
6. Stay logic (other cities)
7. Customization/recalculation (swap/add/remove/reorder)
8. Final timeline + map view + summary
9. Postgres persistence + reload (Neon free instance; tables auto-created at startup)
10. Integration tests + perf checks

## 18. Hand-off Contract

The A→B engine (PROMPT_2/3/4) must implement `TripTransportInterface.top1_route(...)` returning `TransportHint`. The trip planner never calls route-finding directly — only through this interface, on demand. Frontend (PROMPT_6) builds `TripPanel.tsx` against the endpoints above.
