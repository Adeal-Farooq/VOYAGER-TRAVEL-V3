# PROMPT 7 — VOYAGER v2 ML (Traffic Model) + Integration & Testing

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** ML me sirf EK real, trainable model — traffic-crowd slowdown index, `traffic_logs.csv` se (time-of-day × area ke hisaab se), jo TOPSIS factor #4 ko feed karega. Fake/unusable model se kuch bhi acha nahi — agar signal weak ho to time-of-day model pe degrade ho jana (honestly labeled). Integration tests: saare modules ek saath chalein, PROMPT_1 se PROMPT_6 tak ka data flow verify ho (Wonderla + Govt School→MG Road end-to-end). `pytest tests/ -q` sab pass, `tsc --noEmit` 0 errors. Performance budgets enforce karna. Yelahanka metro nahi (Blue Line off). JustDial nahi. Fake data detection: kisi bhi response me fabricate bus numbers/timings/reviews/prices nahi.

---

## 1. Goal

**(A)** One real, trainable ML model (traffic-crowd slowdown) feeding TOPSIS.
**(B)** Integration test suite proving every prompt's module works together.
**(C)** Final verification: no fake data anywhere, all performance budgets met.

## 2. ML — Traffic-Crowd Slowdown Model (`ml/traffic_model.py`)

### 2.1 Data
`DATA_FOLDER/traffic_logs.csv` (7.5MB, quarterly logs). Inspect schema first. Fields likely include timestamp, area/locality, speed or congestion. Clean: parse timestamps → `dayofweek`, `hour_bucket`, derive `speed_kmh` and `slowdown = reference_freeflow / observed`.

### 2.2 Model
Predict **slowdown index** `E[slowdown | dayofweek, hour, area]`:

- **Primary:** gradient-boosted regression (LightGBM/XGBoost) or small MLP on engineered features `[dayofweek, hour_bucket, area_id, is_weekend, is_rush]`. Train/validate split by time (no leakage). Target `slowdown` or speed.
- **Fallback (honest):** if `traffic_logs.csv` has too few samples per (hour, area) bucket or MAE is poor, **degrade to the time-of-day crowd model** (fixed rush/off-peak multipliers) and label it `model: "time_of_day"` in the response. This is NOT failure — it's honesty.

### 2.3 Contract
```python
def predict_slowdown(lat: float, lng: float, dt: datetime) -> float:
    """Returns multiplier ~1.0 (free flow) .. 1.8 (heavy). Area matched to nearest log region; returns 1.0 + small default if unknown."""

def model_info() -> dict:
    """{'model': 'lightgbm'|'time_of_day', 'mae': float, 'trained_at': ISO, 'coverage': {hours: N, areas: N}}"""
```

- Serve via `GET /api/routes/traffic-model-info` (transparency: what the model is and its error).
- Feed TOPSIS factor #4 alongside the Directions `duration_in_traffic` ratio (PROMPT_5): `traffic_factor = max(directions_ratio, predicted_slowdown)` when both present.
- Retrain script `scripts/train_traffic_model.py`; model artifact + metrics saved; load lazily (never block server start).

### 2.4 Acceptance
- [ ] Trained model (or documented time-of-day fallback) exists with reported MAE
- [ ] Prediction returns sane range [1.0, 2.0]
- [ ] `model_info()` exposes honestly whether it's ML or heuristic
- [ ] Model load ≤1s, lazy

## 3. Integration & Testing

### 3.1 Test layout
```
tests/
├── conftest.py               # fixtures: gtfs (small), db, graphhopper stub, serpapi stub, weather stub
├── test_data_layer.py        # PROMPT_1: cache reuse, fares, metro no-blue-line, spatial index
├── test_route_finder.py      # PROMPT_2: multi-hop, forward-progress, no-circular, walk-only
├── test_segment_api.py       # PROMPT_3: Wonderla + Govt School→MG Road end-to-end, time chaining
├── test_search_reliability.py# PROMPT_4: reliability formula, green/yellow/red, ride per-person math
├── test_topsis_8factor.py    # PROMPT_4: numpy TOPSIS correctness, monotonicity, weights
├── test_langgraph_live.py    # PROMPT_5: LiveContext wiring, agent never fabricates numbers
├── test_news_loop.py         # PROMPT_5: dedup, classify, serve cache
├── test_traffic_model.py     # PROMPT_7: range, fallback label
└── test_no_fake_data.py      # THE BIG ONE — scan all API payloads for fabricated markers
```

### 3.2 Key integration tests (must exist)

1. **Wonderla end-to-end:** `POST /api/routes/segments` from Govt School Yelahanka 4th Phase → Wonderla returns Segment 1+2 with real route numbers/times; choosing walk→Puttenahalli then bus→Rajanukunte chains `departureTime ≥ arrival + 4min`; deep `segment-next` returns connected options only.
2. **Govt School → MG Road:** returns multi-bus transfer (507-D → G-9/SBS → 349-K) AND direct G-9 option, both from real GTFS.
3. **No fake data scan:** a walker that asserts across route/segment/search/news/price responses: every `routeNumber` exists in GTFS routes; every `fare` matches `transit_fares.json` or the fare engine; no `"source": "estimated"` missing its label; no review text identical to another place's (LLM-copy detection heuristic); no bus at a stop with zero GTFS departures unless `status: "not_running"`.
4. **Live failure resilience:** with every external stub raising errors, `/routes/plan` still returns in ≤6s and no fake values appear.
5. **Reliability determinism:** given fixture `PlaceDetails`, `reliability` output is stable and classifies green/yellow/red correctly.
6. **TOPSIS sanity:** two routes identical except cost → cheaper ranks higher; adding a weight change reorders appropriately; scores in [0,99].
7. **Graph correctness:** forward-progress rule — for every returned path, each intermediate stop strictly (within +500m tolerance) reduces distance-to-dest; visited guard prevents revisits.

### 3.3 Test doubles
- **GraphHopper:** stub returning a simple polyline + flag; a separate opt-in test hits real Docker when `GH_LIVE=1`.
- **SerpAPI / Google Maps / Open-Meteo / Reddit / eRail:** stub classes with fixtures; live calls only when `LIVE_API=1`.
- GTFS: use a **subset fixture** (a few routes) for speed; full-cache test marked `@pytest.mark.slow`.

## 4. Performance Verification (CI-friendly)

| Check | Threshold |
|---|---|
| Server init (warm) | ≤3s |
| `segments` first call (warm, stubbed live) | ≤3s |
| `segment-next` (warm) | ≤2s |
| Route finding (warm) | ≤5s |
| Route planning with all live sources DOWN | ≤6s |
| `tsc --noEmit` | 0 errors |
| pytest | all green |

Add a `scripts/benchmark.py` that times these and fails if over budget.

## 5. Data Hygiene Audit (final pass before "done")

Walk EVERY endpoint's real output and confirm:
- [ ] Bus route numbers = real GTFS numbers (cleaned), bus timings = real schedule
- [ ] Metro = Purple/Green only; **no Blue Line, no Yelahanka**
- [ ] Train legs only when eRail data exists; fallback city-pairs flagged
- [ ] Ride prices = SerpAPI-live OR labeled Estimated (formula)
- [ ] Reviews = real (SerpAPI), sentiment = local model, summary = LLM (allowed), **no LLM-fabricated review text**
- [ ] News = background scraped, classified, summarized; never hardcoded headlines
- [ ] Reliability = formula output, never random/LLM-guessed
- [ ] Place photos = Google Places or icon; no stock placeholders
- [ ] Paths = GTFS shape / metro line / GraphHopper; straight lines only when flagged

## 6. Definition of Done (full project)

1. All 7 prompts implemented and merged in order (1→7).
2. Backend compiles clean; frontend `tsc --noEmit` 0 errors.
3. `pytest tests/ -q` green including `test_no_fake_data.py`.
4. Benchmark within budgets.
5. Manual QA on live API keys: one real Search, one real Nearby, one real A→B Direct, one real Multi-Hop (Wonderla), one real Drive with fuel cost, live news popup, GPS journey start/stop.
6. Local + Render demo deploy working (GraphHopper local; Render uses fallback-to-interpolated with flags OR a small VPS for GraphHopper if the demo must show real road paths remotely).
