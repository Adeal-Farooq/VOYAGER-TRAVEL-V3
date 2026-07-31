# PROMPT 9 — VOYAGER v2 Deployment (Render Free + Neon Postgres)

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** Ab hum project ko deploy karna hai — Render free tier pe backend + frontend, aur free hosted Postgres (Neon) pe trips ka data. VPS afford nahi kar sakte, isliye Render free. GraphHopper Docker Render free pe NAHI chalta — isliye road paths sirf local demos me real; Render pe walk/car legs interpolated (FLAGGED) honge, lekin bus legs GTFS shapes se real rahenge aur metro real line polylines. SQLite Render pe ephemeral disk (har restart pe wipe) — isliye trips ka data Neon Postgres me jayega. GTFS ka 67MB `gtfs_cache.pkl` repo me COMMIT karna hai taki Render cold boot ~2-3s rahe (nahi to har cold start pe 45s re-derive hota). DataImpulse proxy ka FULL usage — news loop, DDG fallback, review scans — Render se bhi chalta hai. Secrets .env me nahi, Render env vars me. Sab kuch free tier pe smooth chalna chahiye, real data ke saath, fake kabhi nahi.

---

## 1. Goal

Deploy VOYAGER v2 to **Render free tier** (backend + frontend) with **free Neon/Supabase Postgres** for trip persistence, running with real data (GTFS, Places, SerpAPI, weather, news via proxy). GraphHopper stays local (Docker) — Render has no Docker on free tier. Everything must work smoothly and honestly (every fallback labeled).

## 2. Deployment Topology (3 tiers)

### 2.1 Local development (full experience)
```
docker-compose.yml (in PROJECT/)
├── backend      → port 8000
├── frontend     → port 3000
└── graphhopper  → port 8080 (car + foot profiles, Karnataka PBF)
```
- Real road-following paths (GraphHopper), real GTFS, real everything.
- Postgres: point at the same free Neon instance via `DATABASE_URL` (no local DB needed) OR a local Postgres container for offline dev.
- Run: `docker compose up -d`

### 2.2 Render (public demo)
```
render.yaml (in PROJECT/)
├── voyager-backend   (env: python)   → https://voyager-backend.onrender.com
└── voyager-frontend  (env: static)   → https://voyager-frontend.onrender.com
```
- Backend reads `DATABASE_URL` (Neon), `GRAPHOPPER_BASE_URL` absent → walk/car legs use interpolated fallback FLAGGED.
- **No GraphHopper on Render.** Bus legs still draw real GTFS shapes; metro legs real line polylines. Only walk/drive legs degrade — and are labeled.

### 2.3 What "real" means on Render (honesty table)
| Leg type | On Render | Label shown |
|---|---|---|
| Bus | Real GTFS shape (`geometrySource: "gtfs_shape"`) | "Real" |
| Metro | Real line polyline | "Real" |
| Walk / Drive | Interpolated (`geometrySource: "interpolated"`) | "Approx path" |
| Ride prices | SerpAPI live OR formula | "Live"/"Estimated" |
| Reviews | SerpAPI real + local sentiment | "Real" |
| News | Proxy-scraped + LLM summary | "Live" |
| Trains | eRail.in live or flagged fallback | "Live"/"Fallback" |

## 3. Render Setup

### 3.1 `render.yaml` (replace existing)
```yaml
services:
  - type: web
    name: voyager-backend
    env: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12
      - key: DATABASE_URL
        sync: false            # set manually in dashboard
      - key: OPENROUTER_API_KEY
        sync: false
      - key: GEMINI_API_KEY
        sync: false
      - key: SERPAPI_API_KEY
        sync: false
      - key: GOOGLE_MAPS_API_KEY
        sync: false
      - key: DATAIMPULSE_USER
        sync: false
      - key: DATAIMPULSE_PASS
        sync: false
      - key: DATAIMPULSE_HOST
        sync: false

  - type: web
    name: voyager-frontend
    env: static
    plan: free
    buildCommand: cd frontend && npm install && npm run build
    staticPublishPath: frontend/dist
    envVars:
      - key: VITE_API_URL
        value: https://voyager-backend.onrender.com
```
- If Blueprint sync is fiddly, the manual path works too: create the two web services in the Render dashboard, paste the same start/build commands, set env vars, deploy.

### 3.2 Env vars checklist (Render dashboard)
```
DATABASE_URL=postgresql://<neon-user>:<neon-pass>@<neon-host>/voyager?sslmode=require
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=openai/gpt-4o-mini
GEMINI_API_KEY=...
SERPAPI_API_KEY=...
GOOGLE_MAPS_API_KEY=...
DATAIMPULSE_USER=...
DATAIMPULSE_PASS=...
DATAIMPULSE_HOST=host:port
FUEL_PRICE_PER_LITER=110.0
PETROL_AVG_MILEAGE=15.0
```

## 4. Free Hosted Postgres (Neon)

- Sign up Neon → create project → copy the pooled/unpooled connection string → set as `DATABASE_URL`.
- `backend/core/db.py` (or equivalent) connects with `psycopg` (add to requirements) + connection pooling for free tier (Neon free allows limited connections; use a small pool, e.g., 5).
- `backend/core/schema.sql` becomes the idempotent migration run at startup:
  `CREATE TABLE IF NOT EXISTS ...` (trips, trip_days, itinerary_items, place_cache — see PROMPT_8 §4.4).
- **Local dev:** same `DATABASE_URL` in `.env` (works offline against Neon) OR local Postgres container in docker-compose for fully offline dev.
- Add to requirements.txt: `psycopg[binary]>=3.1` (and `SQLAlchemy>=2` only if you choose the ORM; raw psycopg is fine and lighter).

## 5. GTFS Data on Render — the pickle decision

**Decision (locked):** commit the 67MB `gtfs_cache.pkl` to the repo. GitHub allows files ≤100MB; it's a data asset and it already exists in `PROJECT/DATA_FOLDER/processed/`.

- ✅ Cold boot ~2–3s (pickle deserialize) on Render.
- ❌ Alternative (re-derive from raw GTFS on each cold start) = ~45s every time the free tier spins up — rejected.

**What NOT to commit (raw GTFS, ~190MB total):**
- `PROJECT/DATA_FOLDER/bmtc_gtfs/*.txt` → `.gitignore` these.
- The pickle derives stops/shapes/times/name_map; raw files are not needed at runtime after the pickle exists.

**Rebuild path (developer only):** `scripts/build_gtfs_cache.py` regenerates the pickle from `bmtc_gtfs/` when GTFS updates. Run locally, commit the new pickle.

## 6. Cold Start (accepted) & Warm-up

- Render free spins down after ~15 min idle → first request 30–60s (boot + GTFS + graph build).
- **Frontend:** show a "Waking up…" splash overlay while the first API call is in flight (loading state on first interaction), so it doesn't look dead.
- **Optional (free):** cron-job.org ping to `/health` every 10 min keeps the instance warm (may still not be 100% reliable on free tier — treat as best-effort).
- Backend must lazy-load GTFS + build the A* graph on first route request (NOT at boot) so `/health` is instant even after idle.

## 7. DataImpulse Proxy Full Usage on Render

Proxy is just HTTP egress from Render's servers — it works identically on Render. Full usage per PROMPT_5:
- News refresh loop (every 5–10 min): Reddit + Karnataka news via DataImpulse + DDG fallback
- DuckDuckGo fallback searches (reviews/news)
- Review scans / qualitative signals
- **No proxy** for SerpAPI/Google Maps/Open-Meteo/eRail (API-key auth)

**Bandwidth budget (monthly, ~5GB DataImpulse pool):**
| Consumer | Est. per cycle | Est. monthly |
|---|---|---|
| News loop (5 min) | ~200KB | ~1.8GB |
| DDG fallback | ~50KB/search | ~0.5GB |
| Review scans | ~100KB/place | ~1GB |
| **Total** | | **~3.3GB** ✅ within 5GB |

Keep the loop interval ≥5 min and always cache news; never scrape on every page load.

## 8. Caching Strategy on Render

- Place search / nearby / details / reviews: 24h cache.
- News: cached store, 4h TTL.
- Ride prices: 15 min.
- Weather: 15 min.
- Route plans: 10 min TTL.
- **Cache lives in memory on Render (ephemeral)** — that's fine; it's a speed optimization, not durable data. Only Postgres data is durable (trips).

## 9. Secrets & Hygiene

- `.env` NEVER committed (`.gitignore`).
- All secrets as Render env vars.
- Commit: code, `render.yaml`, `docker-compose.yml`, `requirements.txt`, prompt files, `gtfs_cache.pkl`, curated place dataset, SQL schema.
- Never commit: `.env`, raw `bmtc_gtfs/`, `node_modules/`, `dist/`, `__pycache__/`, log files.

## 10. Verification Checklist (post-deploy)

1. `https://voyager-backend.onrender.com/health` → `{"status":"healthy"}`
2. `/docs` loads (FastAPI swagger)
3. `GET /api/search/places?query=cafe&lat=12.97&lng=77.59` → real Google Places results with reliability pills
4. `POST /api/routes/segments` (Govt School Yelahanka → Wonderla) → real GTFS bus numbers + times, bus legs real shapes
5. `GET /api/search/news` → proxy-scraped, classified, summarized items
6. `POST /api/trip/plan` → itinerary; `PUT /api/trip/{id}/items` → edit persists; **redeploy → trip still there** (Postgres ✅)
7. Frontend `https://voyager-frontend.onrender.com` loads; A→B, Search, Trip tabs work against `VITE_API_URL`
8. Cold start: idle 15 min → first hit shows "Waking up…" then succeeds
9. No fake data: run the PROMPT_7 `test_no_fake_data` scan against the deployed backend

## 11. Local + Render Parity

| Capability | Local | Render |
|---|---|---|
| Real GraphHopper walk/car paths | ✅ | ❌ (interpolated, flagged) |
| Real GTFS bus shapes + times | ✅ | ✅ |
| Real metro polylines | ✅ | ✅ |
| Real reviews/prices/news/weather/trains | ✅ | ✅ |
| Trips persistence | ✅ (Neon) | ✅ (Neon) |
| Drive fuel cost | ✅ | ✅ (formula, petrol price) |

The demo story: **demo locally for real road paths; point judges at the Render URL for the live public app.**

## 12. Acceptance Criteria

- [ ] Deploy to Render free tier succeeds (both services live)
- [ ] Trips survive server restart/redeploy (Postgres, verified)
- [ ] GTFS loads from committed pickle in ≤3s on Render
- [ ] Bus/metro legs real geometry on Render; walk/drive flagged interpolated (never silent)
- [ ] DataImpulse proxy traffic flows on Render (news loop runs, logs show proxy usage)
- [ ] All secrets via env vars; `.env` absent from git
- [ ] Cold start accepted with "Waking up…" splash
- [ ] Full manual QA passes (PROMPT_7 §6) against the deployed URL
