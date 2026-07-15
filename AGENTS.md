# VOYAGER - Project Summary

## Architecture
- **Backend**: FastAPI (uvicorn) on port 8000
  - `backend/services/transit_service.py` — routing logic (segment builder, train data, smart filtering, live prices)
  - `backend/services/gtfs_service.py` — BMTC GTFS data loader (synchronous at startup, ~41s, 100K stop times limit)
  - `backend/core/database.py` — bus/metro/railway station data
- **Frontend**: Vite + React/TS on port 3000 (proxies `/api` to backend)
  - `src/components/SegmentPanel.tsx` — progressive multi-column segment UI (direct → reach stops → transit → final mile)
  - `src/utils/helpers.ts` — mode icons/labels
  - `src/pages/MainPage.tsx` — orchestrator with GPS tracking, map resize on panel open/close

## Key Features Built
1. **Progressive multi-column segment UI** — Column layout grows from 1 to N columns as user makes selections:
   - Column 0: Direct options (cab/auto/bike/walk to destination)
   - Column 1: Nearby stops with reach options (walk/cab/auto to each stop)
   - Column 2: Transit options from selected stop (buses with GTFS timings, metro)
   - Column 3: Next transit from train arrival (bus/metro transfer)
   - Last column: Final mile options (walk/cab/auto to destination)
2. **Railway stations + Trains** — `find_nearby_railway_stations()`, train from_stop_options with numbers/times, last-mile transfers
3. **Train integration** — `_get_train_options()` maps Bengaluru↔Mysuru/Hubballi/Mangaluru/Belagavi/Ballari with departure/arrival times
4. **GTFS bus departure times** — synchronous load at server start (`stop_times.txt`, 100K limit, 20 per stop), `get_next_buses()` filters by current time
5. **Last-mile walk** — walk option when transit arrival is within 2 km of destination
6. **Interpolated + OSRM paths** — all options include `path` coordinates for map display; OSRM fetched in parallel batch
7. **Bus fares** — `transit_fares.json` slab data, `max(6, round(db.get_bmtc_ordinary_fare()))` per-person
8. **Smart filtering** — budget/group-size respected; reach only walk when dist < 0.5 km; transit only has_common; railway only for long-distance
9. **LLM live pricing** — live ride prices overlaid on direct + reach options via `llm_agent.get_live_prices()` (8s timeout)
10. **GPS live tracking** — "Start Journey" button triggers `watchPosition`, green live marker on map
11. **Custom waypoints** — search + add intermediate stops with fresh segment data

## Train Data (hardcoded)
- `_TRAIN_DATA` in transit_service.py — Bengaluru↔Mysuru/Hubballi/Mangaluru/Belagavi/Ballari
- `_get_train_options()` — normalizes 15+ station name variants, generates generic options for unknown pairs

## Route Data Structure
```
GET /api/routes/all-segments
  → { status, data: { source, dest, segments: [{
        segment_index, type, from,
        direct_options: [{mode, label, fare, duration, path...}],
        destinations: [{
          stop: {name, lat, lng, type},
          reach_options: [{mode, from→stop, fare, duration...}],
          transit_options: [{mode, route_number, bus_times, departure/arrival_time,
                            final_options: [{mode, to→dest...}],
                            next_transit?: [{mode, ...}]  // bus/metro from train arrival
                          }],
          all_buses?: {route: [times...]}
        }]
      }], total_segments }
  }]
```

## Performance Notes
- GTFS loading ~41s synchronously at server startup
- DB init fast (~1s)
- API response ~3-5s
- OSRM paths fetched in parallel via asyncio.gather

## Running
```powershell
cd VOYAGER
python -m uvicorn backend.main:app --reload --port 8000
cd frontend; npx vite --port 3000
```
