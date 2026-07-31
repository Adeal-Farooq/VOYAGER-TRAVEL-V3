# PROMPT 3 — VOYAGER v2 Segment Builder API (the Hop Mechanism)

> **⚠ BUILD RULE (read every time):** This project is being built **from scratch** in `PROJECT/`. The parent `VOYAGER` repo (`backend/`, `frontend/`, `ml/`, `scripts/`, etc.) is **reference-only for past mistakes** — NEVER import, read for implementation, or "fix" anything there. All code, all decisions, all data contracts come from these prompt files + `PROJECT/DATA_FOLDER/`. Do not reintroduce old code or old bugs.

> **Hinglish intent line:** YE HAI SABSE CRITICAL PART — segment window jisme user khud choose karta hai ki kaunsa stop, kaunsa transport, har level pe. Google Maps jaisa: "Govt School se 507-D, phir Kogilu Cross pe KIA-9, phir Majestic pe Purple metro, phir 231 bus → Wonderla." Backend pura tree of choices generate karega. IMPORTANT: segment 1 aur 2 ek saath pure aayenge (instant render), phir segment 3+ LAZY fetch hoga — jab user apna choice select karega to uske hisaab se next segment nikalega (kyunki bus timings previous arrival pe chain hoti hai). Har leg pe `connectedFrom` (kis stop se connect ho raha), bus number, departure/arrival time, fare, aur real geometry hona chahiye. Har segment me options sirf wahi jo user ko destination ke KAREE le jaaye. Fake/default/fallback data kabhi nahi — jo GTFS/real source me nahi hai, wo dikhana hi nahi. Short distance (≤1.5km) pe walk primary, cab/bike nahi dikhani. Map pe har hop highlight + breadcrumb timeline + journey complete pe total summary.

---

## 1. Goal

Implement the **interactive segment planner API** — the tree-of-choices that lets a user assemble their own multi-hop public-transit route leg by leg, with real schedules, real fares, real geometry. Backend does 100% of the thinking; frontend filters and renders.

## 2. The Model (corrected from ABOUT_GRAPHHOPPER.md)

**Original doc said:** one call returns ALL segments, frontend filters client-side.
**Reality:** departure times chain from the previous leg's arrival, so Segment N can't be fully computed until Segment N−1's choice is fixed. **Resolution (agreed):**

- `POST /api/routes/segments` → **Segment 1 FULL** + **Segment 2 FULL** (grouped by `connectedFrom`) + **probes** for Segment 3+ (only top suggestions, `isProbe: true`).
- `POST /api/routes/segment-next` → when the user confirms a leg, recompute the next segment **time-chained** from the chosen leg's arrival, returning only options connected from that leg.

This gives instant first paint (2 segments ready) + correctness for deeper hops.

## 3. API Contract

### 3.1 `POST /api/routes/segments`

Request:
```json
{
  "source": {"lat": 13.102, "lng": 77.585, "name": "Govt School Yelahanka 4th Phase"},
  "destination": {"lat": 12.985, "lng": 77.392, "name": "Wonderla"},
  "group_size": 2,
  "budget": 500,
  "current_time": "2026-07-31T15:20:00+05:30"
}
```

Response:
```json
{
  "journey": {"source": {...}, "destination": {...}, "generated_at": "..."},
  "segments": [
    {
      "segmentId": 1,
      "title": "Segment 1: Getting out of your current location",
      "sourceName": "Govt School Yelahanka 4th Phase",
      "arrivalAtSegmentStart": null,
      "options": [
        {
          "optionId": "s1_walk_puttenahalli",
          "destinationStop": {"name": "Puttenahalli Bus Stop", "lat": ..., "lng": ...},
          "mode": "walk",
          "routeNumber": null,
          "fromStop": "Govt School Yelahanka 4th Phase",
          "distanceKm": 1.4,
          "durationMin": 17,
          "departureTime": "Now",
          "arrivalTime": "15:37",
          "fare": 0,
          "perPersonFare": 0,
          "geometry": [[13.101,77.586],[...]],
          "geometrySource": "graphhopper",
          "status": "scheduled",
          "isTopRecommended": true,
          "connectedFrom": null,
          "transitOptionsFromThisStop": 6,
          "probeNext": [ {"destinationStop": "Rajanukunte", "mode": "bus", "routeNumber": "284-A", "departureTime": "15:50", "fare": 25, "isProbe": true} ]
        },
        {
          "optionId": "s1_bus_puttenahalli",
          "destinationStop": {"name": "Puttenahalli Bus Stop", "lat": ..., "lng": ...},
          "mode": "bus",
          "routeNumber": "401-M",
          "departureTime": "15:35",
          "arrivalTime": "15:43",
          "fare": 15,
          "perPersonFare": 15,
          "geometry": [[...]], "geometrySource": "gtfs_shape",
          "status": "scheduled",
          "isTopRecommended": false,
          "connectedFrom": null
        }
      ]
    },
    {
      "segmentId": 2,
      "title": "Segment 2: Main Transit Leg",
      "sourceName": null,
      "arrivalAtSegmentStart": null,
      "options": [
        {
          "optionId": "s2_284a",
          "connectedFrom": "Puttenahalli Bus Stop",
          "destinationStop": {"name": "Rajanukunte", ...},
          "mode": "bus", "routeNumber": "284-A",
          "departureTime": "15:50", "arrivalTime": "16:15",
          "fare": 25, "perPersonFare": 25,
          "geometrySource": "gtfs_shape", "status": "scheduled",
          "isTopRecommended": true
        },
        {
          "optionId": "s2_walk_majestic",
          "connectedFrom": "Puttenahalli Bus Stop",
          "destinationStop": {"name": "Majestic", ...},
          "mode": "metro", "routeNumber": "Purple",
          "departureTime": "16:02", "arrivalTime": "16:12",
          "fare": 20, "perPersonFare": 20,
          "geometrySource": "metro_line", "status": "scheduled",
          "isTopRecommended": false
        }
      ]
    }
  ],
  "probes": [ ... top suggestions for segment 3+ ... ],
  "warnings": ["Bus service limited after 22:00 — consider cab/auto"]
}
```

### 3.2 `POST /api/routes/segment-next`

Request:
```json
{
  "journey": { "source": {...}, "destination": {...} },
  "chosen_legs": [
    {"optionId": "s1_walk_puttenahalli", "arrivalTime": "15:37", "destinationStop": "Puttenahalli Bus Stop"},
    {"optionId": "s2_284a", "arrivalTime": "16:15", "destinationStop": "Rajanukunte"}
  ],
  "group_size": 2, "budget": 500
}
```

Response: **Segment N** with only options where `connectedFrom === chosen_legs[-1].destinationStop` AND `departureTime >= chosen_legs[-1].arrivalTime + 4min buffer` (catch-the-bus buffer), plus `probes` for the level after. Returns `{ "journeyComplete": true }` when the chosen leg's destination is within ~500m of final destination.

## 4. Generation Rules (the logic that makes it correct)

### 4.1 Which stops/options appear in a segment
1. From the current position, find candidate next stops: **top bus stops (≤3km), metro (≤3km), rail (≤5km)** via spatial index.
2. **Forward-progress hard rule:** `haversine(candidate → final_dest) < haversine(current → final_dest) + 500m`. A candidate that fails this is dropped — "user ko destination ke paas hi laana hai, ghoomana nahi."
3. For each candidate stop, gather REAL transit options via `GTFSService.get_routes_at_stop(stop, after_time)` — real bus numbers, real scheduled times. **If GTFS has nothing for a stop, it does not get transit options** (it may still appear as a walk destination with `transitOptionsFromThisStop: 0` and a "no real-time data" flag — but it's then pointless, so usually excluded).
4. **Mode thresholds:**
   - `distance ≤ 1.5km` → WALK is primary (fare 0). **No cab/bike suggestions for short hops** (not worth it).
   - `distance > 1.5km` → transit options (bus/metro/train) + (if budget allows) ride options at the next segment level.
   - Walk option always present for any stop ≤ 2km (free).
5. **No fake modes:** if no metro within 3km, no metro option. If no rail within 5km, no train option. Only show what actually serves the stop.

### 4.2 Time chaining
- Segment start time = arrival time of previous chosen leg + buffer.
- Query departures `>= start_time` and `<= start_time + 45min` (time window). Order by departure ascending.
- If future-departure filtering returns empty → mark `status: "not_running"` for that stop/route (do NOT silently show all departures as if they were future). Show a "no more buses today" state instead.
- KIA buses (airport): same mechanism, from `kia_routes_fare_full.json` + GTFS route numbers; include AC and ordinary BMTC options with their own timings.

### 4.3 Geometry per leg (NO spiderwebs)
- bus → `GTFSService.get_stop_to_stop_segment(route_id, from_stop_id, to_stop_id)` — the ACTUAL stop-to-stop slice of the route shape. **Never the full route shape.**
- metro → metro line polyline
- walk → `GraphHopperClient.route("foot", ...)`
- fallback only when GH down → interpolated, flagged `geometrySource: "interpolated"`.
- Every confirmed leg's geometry accumulates on the map (`onRouteGeometry`).

### 4.4 Group size & budget filtering
- Per-person fare displayed (`perPersonFare`); total = per-person × group for shared transit.
- Any option whose total fare > budget is dropped (or shown greyed-out with a "exceeds budget" tag — choose grey-out; never silently omit, so the user understands why).

### 4.5 Top recommendation
- Within each segment, mark ONE `isTopRecommended` option using heuristic: fewest transfers + lowest fare + shortest walk + earliest arrival (before TOPSIS full scoring in PROMPT_4). This is a *fast pre-rank* only.

## 5. Response Time & Caching

| Case | Budget |
|---|---|
| `segments` first call (segment 1+2 full + probes) | ≤ 3s warm |
| `segment-next` call | ≤ 2s warm |
| Both with live external calls (weather/traffic/pricing via PROMPT_5) | ≤ 6s |

- Cache `segments` by `(src_hash, dest_hash, time_bucket_10min)` 5 min TTL; `segment-next` recomputes fresh (time chained).

## 6. Acceptance Tests (these EXACT examples from your spec)

### T1 — Wonderla journey
From **Govt School Yelahanka 4th Phase → Wonderla**, the tree must offer a viable path approximating: bus 507-D → Kogilu Cross, KIA-9 → Kempegowda/Majestic, Purple line metro → Challaghatta, walk → Rajarajeshwari hospital stop, bus 231 → Wonderla (or 226-N → Manchanayakanahalli Gate → walk). Verification: every leg has a real route number + scheduled time from GTFS, geometry is GTFS-shape/metro-line, and `connectedFrom` chains exactly.

### T2 — Govt School → MG Road
Must include multi-bus transfers like: 507-D → Seshadripuram college, change to G-9/SBS → Shivajinagar, 349-K → MG Road. Also the direct G-9 option (5th phase → MG Road). Both must be real GTFS routes with scheduled times.

### T3 — Time chaining
Choosing "walk to Puttenahalli, arrive 15:37" must filter Segment 2 to departures ≥15:41; changing Segment 1 choice instantly recomputes the filtered Segment 2 set (client-side filter from pre-fetched data; `segment-next` only for deeper hops).

### T4 — Short hop
Source→stop ≤1.5km shows walk primary, no cab options.

## 7. Edge Cases

- User selects a **custom intermediate stop** (typed place between source & dest): recompute from that stop onward toward final dest, keep it on the journey timeline.
- **Journey complete** when within 500m of final dest; return full timeline: ordered legs, times, fares, total, count of segments, and a final "You have arrived" payload.
- **Reset:** a client reset simply abandons the tree; backend is stateless per request.
- **Late night (22:00–06:00):** walk/bus legs get `status` warnings; the API returns `warnings` for safety advisories (shown by frontend).

## 8. Hand-off Contract (for PROMPT_4/6)

- Emits: `segments`, `probes`, `warnings`, `journeyComplete`, `timeline`
- Scoring (TOPSIS 8-factor) in PROMPT_4 re-ranks the *probes* and multi-leg suggestions; frontend (PROMPT_6) renders the 3-column hop window with breadcrumb + map highlight per hop.
