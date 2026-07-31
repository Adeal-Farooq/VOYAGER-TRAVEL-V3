# PROMPT 5 — VOYAGER v2 LangGraph Agent + Live Data Layer (Weather/Traffic/News/Train/Reviews)

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** LangGraph agent ka kaam hai LIVE FACTORS ko parallel me gather karna — weather, traffic, news, reviews, ride prices — aur structured JSON me dena jo TOPSIS weights ko feed kare aur Gemini ko explain karne ke liye. Agent route DECIDE nahi karta (wo deterministic A*/graph karta hai); agent DATA GATHERER + EXPLAINER hai. LLM kabhi fares, timings, bus numbers, reviews, scores NAHI banata. News ke liye background refresh loop (har 5-10 min, DataImpulse proxy se scrape, classify, geo-tag, LLM summarize, cache) + frontend 2-min poll. Traffic factor me Google Directions `duration_in_traffic` ratio + news alerts. Live train data eRail.in se (real, nahi to train option hi mat dikhao).

---

## 1. Goal

The **live/context layer** and the **LangGraph agent** that wires live signals into route scoring (PROMPT_4) and into user-facing explanations — without ever polluting the critical path with fabricated data.

## 2. LangGraph Agent (`backend/services/langgraph/`)

### 2.1 Role (non-negotiable)
- **Gather:** weather, traffic (Directions ratio + news), ride prices, reviews, current events — **in parallel** for a given source/dest/query.
- **Explain:** given a ranked `ScoredRoute` from TOPSIS, produce a plain-language Gemini explanation (WHY this route won, what live factors affected it).
- **Synthesize:** for `/api/langgraph/ask`, combine tool outputs into one structured JSON response.
- **Forbidden:** generating fares, timings, bus numbers, review text, or reliability scores. All numbers come from deterministic code / real APIs.

### 2.2 Architecture

```
backend/services/langgraph/
├── agent.py               # VoyagerLangGraph: intent detection, parallel tool dispatch, synthesis
├── state.py               # LangGraph state schema
├── tools/
│   ├── weather_tools.py   # Open-Meteo → current + forecast
│   ├── traffic_tools.py   # Directions duration_in_traffic ratio + news traffic alerts
│   ├── news_tools.py      # cached news store (background loop)
│   ├── pricing_tools.py   # ride_pricing.get_ride_prices (PROMPT_4)
│   ├── review_tools.py    # real reviews + sentiment + LLM summary (PROMPT_4)
│   ├── search_tools.py    # places search, suggestions, place-details
│   ├── geo_tools.py       # geocode, nearby, reverse-geocode
│   └── train_tools.py     # eRail.in live train data
└── workflows/
    └── route_context.py   # the "gather live context for a route" graph
```

### 2.3 LLM client (`backend/agents/llm_agent.py`)

- **Provider chain:** OpenRouter (primary) → fallback models → Gemini. JSON mode on, 30s timeout per call, cross-model fallback on failure.
- **Allowed outputs only:** summaries, explanations, structured tool-dispatch intents, synthesis. All **numeric data** fields must come from tools, never from the LLM's imagination.
- If ALL LLMs fail → deterministic fallbacks (e.g., "Weather unavailable", plain route explanation with raw numbers). **Never ask the LLM to guess a number.**

### 2.4 The Route-Context Graph (`workflows/route_context.py`)

Input: `{source, dest, group_size, budget, time}`.
Nodes (parallel fan-out):
1. `weather` → current + 3h forecast at src & dest
2. `traffic` → Directions `duration_in_traffic/duration` ratio on the car route
3. `news` → cached recent items relevant to the corridor (geo-tag match or keyword match)
4. `prices` → ride price options src→dest (live/estimated labeled)
5. `reviews` → (only when places are involved, e.g. destination is a POI) top review signals for destination

Aggregate → `LiveContext`:
```json
{
  "weather": {"temp_c": 28, "condition": "clear", "rain_next_hour": false},
  "traffic": {"ratio": 1.25, "label": "moderate", "alerts": ["Heavy at Silk Board"]},
  "news": [{"category": "traffic", "headline": "...", "summary": "...", "geo": {"lat":..,"lng":..}|null}],
  "prices": [{"provider":"Uber Go","total":320,"per_person":160,"source":"estimated"}],
  "factors": {"time_of_day": "evening_rush", "safety": "ok"}
}
```

`LiveContext` feeds: TOPSIS criterion values (weather→#3, traffic→#4, availability→#5, safety→#8) and the Gemini explanation prompt.

## 3. Weather (`weather_client.py`)

- Open-Meteo (free, no key): current + minutely/hourly for route coords. Cache 15 min.
- Endpoint `GET /api/search/weather?lat=&lng=`; header widget shows temp + icon; route scoring uses it.

## 4. News Engine (background loop, no dead popup)

### 4.1 Refresh loop
A background scheduler (e.g. `asyncio` task / APScheduler) every **5–10 min**:
1. Scrape **r/bangalore** (Reddit JSON API) + Karnataka news sources (Times of India / The Hindu / Deccan Herald via **DataImpulse proxy** + DuckDuckGo fallback).
2. **Classify** each item: `traffic | weather | event | general`.
3. **Geo-tag** when a known locality/landmark appears in text → attach coords (map marker).
4. **LLM summarize** each item into ≤2 lines (allowed: summary only).
5. Store in an in-memory store, **dedup by title**, keep max 25, TTL 4h.

### 4.2 Serving
- `GET /api/search/news?lat=&lng=` → items filtered by relevance (geo proximity + keyword match to user's area), sorted by recency. Cache served; frontend polls every 2 min.
- Map markers: small `!` markers colored by category (traffic=red, weather=blue, event=yellow, general=gray); popup shows title + summary.
- Floating LIVE glass panel on map with pulsing dot, dismissible.

### 4.3 Traffic factor wiring
- News `traffic` items relevant to the corridor **feed TOPSIS factor #4** (multiply ratio): e.g. a Silk Board congestion alert within 3km of the route corridor bumps the traffic penalty.
- Primary traffic number is still the Directions `duration_in_traffic` ratio (real measurement).

## 5. Live Train Data (`train_service.py` + `train_tools.py`)

- **eRail.in API** scraped for real live trains across the 22 mapped Karnataka station codes.
- 7 city-pair fallbacks exist but **must be flagged `source: "fallback"` and only used when eRail is unreachable** — never presented as live.
- **No fabricated trains:** if the requested corridor has no scheduled/live train, emit no train leg (PROMPT_2 already requires this).

## 6. Proxies (DataImpulse) — where they belong

| Target | Proxy | Why |
|---|---|---|
| r/bangalore / news sites | DataImpulse residential/datacenter | IP-blockable |
| DuckDuckGo fallback | DataImpulse | rate limits |
| **JustDial** | — | **DROPPED** (confirmed non-functional; place verification uses Places API + SerpAPI instead) |
| SerpAPI / Google Maps / Reddit JSON / Open-Meteo / OpenRouter/Gemini | **no proxy** | API-key auth, not IP-based |

`proxy_manager.py` centralizes session reuse, rotation (if multiple keys), timeouts, and retry backoff. All scraper I/O goes through it.

## 7. Endpoints

```
POST /api/langgraph/ask        # full agent loop (chat/synthesis)
POST /api/langgraph/route-context   # LiveContext for a route (used by /routes/plan internally)
GET  /api/search/news?lat=&lng=
GET  /api/search/weather?lat=&lng=
GET  /api/routes/news           # corridor-relevant news for a route
GET  /api/routes/live-trains?from_code=&to_code=
```

## 8. Performance & Failure Modes

| Case | Behavior |
|---|---|
| Weather API down | factor #3 neutral (weight redistributed), UI shows "Weather unavailable" |
| Directions traffic down | factor #4 falls back to time-of-day crowd model (labeled) |
| News loop failing | serve last-good cache; popup shows "Offline" state, never fake headlines |
| All LLMs down | deterministic explanation (raw numbers), no fabricated prose |
| Agent total failure | route planning still completes — LiveContext is best-effort enrichment, NOT a gate |

**Critical invariant:** the agent can never block or break routing. All live gathering is `gather: true, required: false`.

## 9. Acceptance Criteria

- [ ] `/api/langgraph/ask` returns structured synthesis with real tool data (no hallucinated numbers)
- [ ] `route-context` returns `LiveContext` JSON with all 5 tool groups
- [ ] TOPSIS receives real weather + traffic values (unit test: stub LiveContext → assert criterion values)
- [ ] News loop runs on schedule; items classified + summarized + deduped; frontend poll works
- [ ] Train leg appears only when eRail data exists; fallbacks flagged
- [ ] Proxy used for news/DDG scrapes, NOT for SerpAPI/Maps (test: assert request target)
- [ ] Routing completes in ≤6s even when every live source is down
