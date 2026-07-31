# PROMPT 4 — VOYAGER v2 Search, Place Reliability & 8-Factor TOPSIS Scoring

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** Search acha se karo — Google Places (New) API se places/nearby, jisme business_status (khula/band), opening hours, photos sab dikhana. Reliability score DYNAMIC formula se: rating + review sentiment + review count + status. Green = acha verified (glow, bada), yellow = average, red = band/kharaab (chhota, dim). Reviews real SerpAPI se, sentiment local model se, summary Gemini se. Aur TOPSIS 8 factor (time-of-day, cost, weather, traffic&crowd, transport availability, walking distance, group size, safety) se routes rank karna — user weights change kar sakta hai. Ride pricing SerpAPI live + formula estimated (labeled). Kabhi LLM se fake reviews/fares/scores nahi.

---

## 1. Goal

Two systems:
**(A) Search & Place Discovery** — real place search, nearby search, place details, reliability scoring, reviews, photos, hours.
**(B) Route Scoring** — real 8-factor TOPSIS that ranks the `RoutePlan`s from PROMPT_2.

## 2. Search & Place Discovery

### 2.1 Google Places API (New) — `backend/services/clients/google_maps_client.py`

Enabled APIs (per user): **Places API (New)**, **Geocoding API**, **Directions/Distance Matrix API**.

```python
class GoogleMapsClient:
    def __init__(self, api_key, radius_km=15, ...): ...
    def geocode(self, query: str) -> Place | None
    def search_places(self, query: str, lat, lng, radius_m) -> list[Place]      # Places (New) Text Search
    def nearby_places(self, lat, lng, radius_m, category) -> list[Place]        # Nearby Search
    def place_details(self, place_id: str) -> PlaceDetails
    def place_photos(self, place_id: str, max_width=400) -> str | None          # photo URL (frontend fetches)
    def directions(self, origin, dest, mode) -> DirectionsResult                # incl. duration_in_traffic
```

**Verification & filtering rules:**
- Places search results must satisfy **≥40% keyword overlap** between query and result name/address (kills unrelated hits).
- Coordinates verified within Bangalore (15km radius of center; wider for non-Bangalore queries).
- Deduplicate by rounded coordinates (4 decimals).
- **Business status:** `business_status` from Places API: `OPERATIONAL` / `CLOSED_TEMPORARILY` / `CLOSED_PERMANENTLY`. This drives green/yellow/red pin logic below.
- **Opening hours:** `opening_hours.open_now` + `weekday_text` — always shown on the card.
- **Photos:** `place_photos` returns a real photo reference; frontend displays it. **Never placeholder stock images.** If no photo, show category icon.

### 2.2 Reliability Score (dynamic, deterministic, explainable)

```
status_factor = 0.0 if CLOSED_PERMANENTLY
              = 0.25 if CLOSED_TEMPORARILY
              = 1.0  if OPERATIONAL (and OPEN_NOW preferred)

reliability = ( 0.5 * (rating / 5)
              + 0.3 * sentiment_avg
              + 0.2 * min(1.0, log1p(review_count) / log1p(100)) ) * status_factor

score_pct = round(reliability * 100)
```

- `rating`, `review_count` from Places API / SerpAPI place details (real numbers).
- `sentiment_avg` ∈ [0,1] from review texts (see 2.3).
- **Pin classes:**
  - **Green** (`score ≥ 70`): OPERATIONAL + rating ≥ 3.5 → normal size + glow
  - **Yellow** (`50 ≤ score < 70`): OPERATIONAL + average rating (~3.0–3.5)
  - **Red** (`score < 50`): CLOSED_PERMANENTLY / CLOSED_TEMPORARILY / rating < 3.0 → small + dim
- **Color map (frontend):** green ≥70, yellow ≥50, orange ≥30, red <30 for pills; pins use the three-class rule.
- Always recompute from live inputs — **never trust an external `reliability_score` field.**

### 2.3 Reviews & Sentiment — `backend/services/langgraph/tools/review_tools.py` + `backend/services/sentiment.py`

**Fetch chain (real only):**
1. SerpAPI Google Maps place search → `place_id`
2. SerpAPI place_details → `user_reviews.most_relevant` (fields: `username`, `description`, `rating`, `date`), plus `user_reviews` counts
3. Google Places API reviews (if available via Places (New) details) as secondary
4. **Cache:** keyed `place_id` + `_CACHE_VERSION` (bump on schema change), 24h TTL

**Fetch budget:** best **2 reviews from each star level** (5,4,3,2,1) max ~10 reviews per place, to protect SerpAPI quota (~1250 free searches/mo total across friend keys).

**Sentiment:** local lightweight HuggingFace pipeline (e.g. `distilbert-base-uncased-finetuned-sst-2-english`) loaded once, scored per review → polarity ∈ [0,1], averaged. **Fallback to LLM (Gemini) sentiment only if the local model is unavailable**; LLM is allowed to *judge sentiment* but NOT to invent reviews.

**LLM summary (allowed use):** Gemini summarizes the top 2 reviews per star level into: overall gist + `concerns[]` (negative patterns). Displayed in the Discovery panel. LLM never fabricates review text.

**AI review summary UI block:** colored (green/yellow/red) box with gist + red `concerns` section.

### 2.4 Hotel price range (when applicable)
- SerpAPI Google Hotels search for places whose category is hotel/lodge/room → `min_price`/`max_price` per night + average. **Only for stay-type categories** (hotel/lodge); banks/temples/bus stops etc. never show prices.
- If unavailable → show "Price not available" (no fake numbers).

### 2.5 Endpoints

```
GET  /api/search/places?query=&lat=&lng=
GET  /api/search/nearby?category=&lat=&lng=&radius_km=
GET  /api/search/suggestions?q=            (autocomplete, debounced)
GET  /api/search/place-details?place_id=
POST /api/search/enrich-place              {place_id} → reviews, photos, prices, summary
GET  /api/search/reviews?place_id=
GET  /api/search/weather?lat=&lng=
GET  /api/search/news                      (see PROMPT_5)
```

**Cache:** place search 24h; nearby 24h; place-details 24h; reviews 24h; weather 15min.

## 3. TOPSIS — 8-Factor Route Scoring

### 3.1 `backend/services/topsis_engine.py` (real TOPSIS, numpy)

```python
@dataclass
class TopsisWeights:
    time_of_day: float = 0.10
    cost: float = 0.20
    weather: float = 0.10
    traffic_crowd: float = 0.15
    availability: float = 0.05
    walking: float = 0.15
    group_size: float = 0.10
    safety: float = 0.15

def topsis_score_routes(
    routes: list[RoutePlan],
    weights: TopsisWeights,
    context: ScoringContext,   # time-of-day, weather, traffic ratio, group, budget, area risk
) -> list[ScoredRoute]:
```

Steps (real multi-criteria, NOT fake linear slopes):
1. Build **decision matrix** `routes × 8 criteria`. Criteria direction:
   - **Benefit** (higher better): availability, safety
   - **Cost** (lower better): cost, time, walking, transfers (time-of-day & weather & traffic-crowd act as penalty multipliers — see 3.2)
2. **Vector-normalize**: `r_ij = x_ij / sqrt(sum x_kj²)`.
3. **Weighted** matrix: `v_ij = w_j * r_ij`.
4. **Ideal best** `A*` / **anti-ideal** `A⁻` per criterion (per direction).
5. **Euclidean distances** `D*`, `D⁻`.
6. **Closeness coefficient** `CC_i = D⁻_i / (D*_i + D⁻_i)`, score 0–99, sort desc; tie-break by lower fare.

### 3.2 Criterion computation (all REAL data)

| # | Criterion | Input source | Mapping |
|---|---|---|---|
| 1 | time_of_day | current hour + weekday | rush/night multipliers; night (22–06) → walk & ordinary-bus penalty, cab bonus |
| 2 | cost | `FareEngine` per route + group splitting | per-person fare; budget filter applied upstream |
| 3 | weather | Open-Meteo (free, no key) at route coords | rain → high-walk routes penalized, car/cab boosted |
| 4 | traffic_crowd | **Google Directions `duration_in_traffic / duration` ratio** + ML/time-of-day crowd model (PROMPT_7) + news alerts | ratio ≥1.3 → heavy; penalize drive/cab legs, prefer metro |
| 5 | availability | which modes actually serve (from PROMPT_2/3) | more options > fewer; walk-only route low on availability |
| 6 | walking | sum of walk km across legs | inverse; >1.5km penalized, more so at night/rain |
| 7 | group_size | user input | ≥4 → car/cab boosted (shared cost), per-person fares |
| 8 | safety | time-of-day + walk distance + area-risk heuristic + news warnings | night + long walk → heavy penalty; advisories surfaced |

**Every criterion must trace to a real number** — weather from API, traffic ratio from Directions, fare from engine, times from GTFS. No invented constants for the 8 factors themselves (weights are user-adjustable, and that's the only knob).

### 3.3 Output
```python
@dataclass
class ScoredRoute:
    route: RoutePlan
    scores: dict[str, float]   # per-criterion contribution (for UI explanation)
    cc_score: float            # 0-99
    rank: int
    best_match: bool
    explanation: str | None    # Gemini plain-language (PROMPT_5) — WHY this route
```

Route cards (frontend) show: rank badge, total fare, duration, walk km, transfers, score bar (0-99 colored), per-criterion mini-explanation, and "Best Match" tag on rank 1. Top 5 highlighted, rest in "Show all options" expander.

## 4. Ride Pricing (honest, labeled)

`backend/services/ride_pricing.py` (replaces the old ride_scraper mess):

```python
def get_ride_prices(src, dest, group_size) -> list[RidePrice]:
    # 1) SerpAPI Google Maps directions → parse drive_time + ride options (Live when present)
    # 2) formula fallback: Karnataka govt-mandated rates
    #    Uber Go/Ola Mini ₹24/km, Uber XL ₹32/km, Auto ₹20/km, Rapido Bike ₹5/km
    #    + surge_multiplier(hour, weekday)  # morning 1.4x, evening 1.5x, night 1.2x, late 1.8x
    #    + slab logic (_calc_ride_fare)
    # per-person = vehicle_fare / group_size  (NOT vehicle_fare * group_size — old bug)
```

Every price: `{provider, mode, total, per_person, eta_min, source: "live"|"estimated", note}`. Cache 15 min. **Label `live` vs `estimated` in the UI.**

## 5. Acceptance Criteria

- [ ] `reliability` formula implemented; green/yellow/red classification provable in unit tests (fabricate a PlaceDetails fixture, assert class)
- [ ] Reviews are REAL (SerpAPI), never LLM-generated; sentiment from local model
- [ ] Place cards show open/closed status + hours
- [ ] Photos come from Places API (or icon fallback), never stock placeholders
- [ ] TOPSIS is real numpy vector-normalized (test: monotonic on cost with all else equal)
- [ ] 8 criteria all populated with real data; no fake constants
- [ ] Ride prices labeled live/estimated; per-person math correct for group=4
- [ ] Frontend route card explains the score (per-criterion contributions)

## 6. Hand-off
- `ScoredRoute` list → AToBPanel route cards (PROMPT_6)
- `PlaceDetails` + `reliability` + reviews → SearchPanel / DiscoveryPanel
- `RidePrice[]` → Direct Ride sub-mode
