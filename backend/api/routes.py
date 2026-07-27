import math, json, csv, os, asyncio, logging
from datetime import datetime
import httpx
from fastapi import APIRouter, Query
from backend.models.transit import ATobRequest
from backend.services.transit_service import transit_service
from backend.agents.llm_agent import llm_agent
from backend.core.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/routes", tags=["Routes"])

def _clean(val, default=0.0):
    if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return default
    return val

def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        return _clean(obj)
    return obj

def _combine_multi_stop_routes(segment_routes: list[dict]) -> list[dict]:
    """Combine per-segment route lists into multi-stop mega-routes by mode type."""
    if not segment_routes:
        return []

    # Group best route per segment by mode category
    transit_modes = {"metro", "metro_interchange", "bus_ordinary", "bus_ac_vajra", "bus_to_metro", "metro_to_bus", "kia_bus", "walk"}
    combined_transit = {"type": "multi_stop", "legs": [], "total_fare": 0, "total_duration_minutes": 0,
                        "total_distance_km": 0, "total_walking_km": 0, "overall_score": 0, "score_explanation": "multi-stop"}
    combined_driving = {"type": "car_multi", "legs": [], "total_fare": 0, "total_duration_minutes": 0,
                        "total_distance_km": 0, "total_walking_km": 0, "overall_score": 0, "score_explanation": "multi-stop drive"}

    for seg in segment_routes:
        seg_transit = [r for r in seg.get("transit", []) if r.get("type") in transit_modes]
        seg_driving = [r for r in seg.get("driving", [])]
        best_transit = seg_transit[0] if seg_transit else None
        best_driving = seg_driving[0] if seg_driving else None

        if best_transit:
            combined_transit["legs"].extend(best_transit.get("legs", []))
            combined_transit["total_fare"] += best_transit.get("total_fare", 0)
            combined_transit["total_duration_minutes"] += best_transit.get("total_duration_minutes", 0)
            combined_transit["total_distance_km"] += best_transit.get("total_distance_km", 0)
            combined_transit["total_walking_km"] += best_transit.get("total_walking_km", 0)
            combined_transit["overall_score"] += best_transit.get("overall_score", 75)
        if best_driving:
            combined_driving["legs"].extend(best_driving.get("legs", []))
            combined_driving["total_fare"] += best_driving.get("total_fare", 0)
            combined_driving["total_duration_minutes"] += best_driving.get("total_duration_minutes", 0)
            combined_driving["total_distance_km"] += best_driving.get("total_distance_km", 0)

    n = len(segment_routes)
    if combined_transit["legs"]:
        combined_transit["overall_score"] = max(10, min(99, combined_transit["overall_score"] // n if n else 75))
        combined_transit["total_walking_km"] = round(combined_transit["total_walking_km"], 2)
        combined_transit["total_distance_km"] = round(combined_transit["total_distance_km"], 2)
    if combined_driving["legs"]:
        combined_driving["overall_score"] = 80
        combined_driving["total_distance_km"] = round(combined_driving["total_distance_km"], 2)

    results = []
    if combined_transit["legs"]:
        results.append(combined_transit)
    if combined_driving["legs"]:
        results.insert(0, combined_driving)
    return results

@router.post("/plan")
async def plan_route(request: ATobRequest):
    # Multi-stop: plan each segment independently
    if request.waypoints and len(request.waypoints) > 0:
        points = [{"lat": request.source_lat, "lng": request.source_lng, "name": ""}]
        for wp in request.waypoints:
            points.append({"lat": wp.lat, "lng": wp.lng, "name": wp.name})
        points.append({"lat": request.dest_lat, "lng": request.dest_lng, "name": ""})

        segment_routes = []
        for i in range(len(points) - 1):
            a, b = points[i], points[i + 1]
            seg_transit = transit_service.get_route_legs_public(a["lat"], a["lng"], b["lat"], b["lng"], request.budget, request.group_size)
            async def enrich_seg():
                tasks = [transit_service._add_leg_paths(r) for r in seg_transit]
                await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await asyncio.wait_for(enrich_seg(), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning(f"Segment enrichment timeout for stop {i}")
            seg_driving = await transit_service.get_driving_route(a["lat"], a["lng"], b["lat"], b["lng"])
            seg_driving_list = []
            if seg_driving:
                fuel = _estimate_fuel_cost(seg_driving.get("distance_km", 0))
                driving_path = None
                if seg_driving.get("geometry"):
                    driving_path = [[c[1], c[0]] for c in seg_driving["geometry"]["coordinates"]]
                seg_driving_list.append({
                    "type": "car", "total_fare": fuel, "total_duration_minutes": seg_driving["duration_minutes"],
                    "total_distance_km": seg_driving["distance_km"], "total_walking_km": 0, "overall_score": 85,
                    "legs": [{
                        "from": a.get("name", f"{a['lat']:.4f},{a['lng']:.4f}"),
                        "to": b.get("name", f"{b['lat']:.4f},{b['lng']:.4f}"),
                        "mode": "car", "distance_km": seg_driving["distance_km"],
                        "duration_minutes": seg_driving["duration_minutes"], "fare": fuel,
                        "instructions": f"Drive {seg_driving['distance_km']:.1f}km - ₹{fuel}",
                        "path": driving_path,
                    }]
                })
            segment_routes.append({"transit": seg_transit, "driving": seg_driving_list})

        all_routes = _combine_multi_stop_routes(segment_routes)
        try:
            weather = await asyncio.wait_for(llm_agent.get_weather_impact(lat=request.source_lat, lng=request.source_lng), timeout=5.0)
        except Exception as e:
            logger.warning(f"Weather fetch (multi-stop) failed: {e}")
            weather = {}
        return _sanitize({
            "status": "success", "multi_stop": True,
            "source": {"lat": request.source_lat, "lng": request.source_lng},
            "destination": {"lat": request.dest_lat, "lng": request.dest_lng},
            "waypoints": [{"lat": wp.lat, "lng": wp.lng, "name": wp.name} for wp in request.waypoints],
            "routes": all_routes, "total_options": len(all_routes), "weather": weather
        })

    metro_station_near_source = db.find_nearby_metro_stations(request.source_lat, request.source_lng, 3.0)
    metro_station_near_dest = db.find_nearby_metro_stations(request.dest_lat, request.dest_lng, 3.0)
    bus_near_source = db.find_nearby_bus_stops(request.source_lat, request.source_lng, 1.0)
    bus_near_dest = db.find_nearby_bus_stops(request.dest_lat, request.dest_lng, 1.0)

    source_name = metro_station_near_source[0]["name"] if metro_station_near_source else f"{request.source_lat:.4f},{request.source_lng:.4f}"
    dest_name = metro_station_near_dest[0]["name"] if metro_station_near_dest else f"{request.dest_lat:.4f},{request.dest_lng:.4f}"

    if request.mode == "personal":
        driving = await transit_service.get_driving_route(
            request.source_lat, request.source_lng,
            request.dest_lat, request.dest_lng
        )
        if not driving:
            dist = transit_service.haversine_distance(
                request.source_lat, request.source_lng,
                request.dest_lat, request.dest_lng
            )
            driving = {"distance_km": round(dist, 2), "duration_minutes": round(dist * 30), "geometry": None}
        fuel_cost = _estimate_fuel_cost(driving["distance_km"])
        return {
            "status": "success",
            "mode": "personal",
            "routes": [{
                "type": "car",
                "total_fare": fuel_cost,
                "total_duration_minutes": driving["duration_minutes"],
                "total_distance_km": driving["distance_km"],
                "total_walking_km": 0,
                "overall_score": 85,
                "score_explanation": "direct drive - no transfers",
                "geometry": driving.get("geometry"),
                "legs": [{
                    "from": "Your Location",
                    "to": "Destination",
                    "mode": "car",
                    "distance_km": driving["distance_km"],
                    "duration_minutes": driving["duration_minutes"],
                    "fare": fuel_cost,
                    "instructions": f"Drive {driving['distance_km']:.1f}km - fuel cost approx ₹{fuel_cost}",
                    "path": [[c[1], c[0]] for c in driving["geometry"]["coordinates"]] if driving.get("geometry") else None,
                }]
            }]
        }

    if request.mode == "walking":
        dist = transit_service.haversine_distance(
            request.source_lat, request.source_lng,
            request.dest_lat, request.dest_lng
        )
        walk_time = dist * 12
        path = transit_service._interpolate_path(
            request.source_lat, request.source_lng,
            request.dest_lat, request.dest_lng, 20
        )
        return {
            "status": "success",
            "mode": "walking",
            "routes": [{
                "type": "walk",
                "total_distance_km": round(dist, 2),
                "total_duration_minutes": round(walk_time),
                "total_fare": 0,
                "total_walking_km": round(dist, 2),
                "overall_score": 60 if dist < 5 else 30,
                "score_explanation": "walking only - free but slow",
                "legs": [{
                    "from": "Your Location",
                    "to": "Destination",
                    "mode": "walk",
                    "distance_km": round(dist, 2),
                    "duration_minutes": round(walk_time),
                    "fare": 0,
                    "instructions": f"Walk {dist:.1f}km - about {walk_time:.0f} minutes",
                    "path": path,
                }]
            }]
        }

    try:
        weather = await asyncio.wait_for(llm_agent.get_weather_impact(lat=request.source_lat, lng=request.source_lng), timeout=5.0)
    except Exception as e:
        logger.warning(f"Weather fetch failed: {e}")
        weather = {}

    loop = asyncio.get_running_loop()
    try:
        public_routes = await asyncio.wait_for(
            loop.run_in_executor(None, transit_service.get_route_legs_public, request.source_lat, request.source_lng, request.dest_lat, request.dest_lng, request.budget, request.group_size, weather),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        logger.warning("Public route generation timed out, using empty")
        public_routes = []

    if public_routes:
        async def enrich_all():
            tasks = [transit_service._add_leg_paths(r) for r in public_routes]
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await asyncio.wait_for(enrich_all(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning("Public route path enrichment timed out")

    try:
        driving = await asyncio.wait_for(transit_service.get_driving_route(
            request.source_lat, request.source_lng,
            request.dest_lat, request.dest_lng
        ), timeout=8.0)
    except asyncio.TimeoutError:
        logger.warning("Driving route fetch timed out")
        driving = None

    try:
        live_prices = await asyncio.wait_for(llm_agent.get_live_prices(source_name, dest_name), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Live prices timed out")
        live_prices = []

    all_routes = list(public_routes)

    if driving:
        estimated_fuel_cost = _estimate_fuel_cost(driving["distance_km"])
        all_routes.insert(0, {
            "type": "car",
            "total_fare": estimated_fuel_cost,
            "total_duration_minutes": driving["duration_minutes"],
            "total_distance_km": driving["distance_km"],
            "total_walking_km": 0,
            "overall_score": 85,
            "score_explanation": "direct drive - no transfers",
            "geometry": driving["geometry"],
            "legs": [{
                "from": "Your Location",
                "to": "Destination",
                "mode": "car",
                "distance_km": driving["distance_km"],
                "duration_minutes": driving["duration_minutes"],
                "fare": estimated_fuel_cost,
                "instructions": f"Drive - fuel: ₹{estimated_fuel_cost}",
                "path": [[c[1], c[0]] for c in driving["geometry"]["coordinates"]] if driving.get("geometry") else None,
            }]
        })

    if live_prices:
        for price_option in live_prices:
            all_routes.append({
                "type": price_option.get("mode", "cab"),
                "provider": price_option.get("provider", "Ride"),
                "total_fare": price_option.get("price", 200),
                "total_duration_minutes": price_option.get("eta_minutes", 15) + 10,
                "total_distance_km": driving["distance_km"] if driving else 10,
                "total_walking_km": 0,
                "overall_score": 75,
                "score_explanation": "ride hailing - door to door",
                "legs": [{
                    "from": source_name,
                    "to": dest_name,
                    "mode": price_option.get("mode", "cab"),
                    "distance_km": driving["distance_km"] if driving else 10,
                    "duration_minutes": price_option.get("eta_minutes", 15) + 10,
                    "fare": price_option.get("price", 200),
                    "instructions": f"{price_option.get('provider', 'Ride')} - approx ₹{price_option.get('price', 200)}"
                }]
            })

    is_rainy = "rain" in (weather.get("condition", "") or "").lower()
    current_hour = datetime.now().hour
    is_night = current_hour < 6 or current_hour > 20

    for r in all_routes:
        base_score = r.get("overall_score", 75)
        walk = r.get("total_walking_km", 0)
        mode_type = r.get("type", "")
        adjustments = []

        if is_rainy:
            if walk > 1: base_score -= 15; adjustments.append(f"rain: walk>{1}km -15")
            if mode_type in ("walk", "bike"): base_score -= 20; adjustments.append("rain: walk/bike -20")
            if mode_type in ("car", "cab"): base_score += 5; adjustments.append("rain: car/cab +5")
        if is_night:
            if walk > 1.5: base_score -= 10; adjustments.append(f"night: walk>{1.5}km -10")
            if mode_type in ("bus_ordinary",): base_score -= 8; adjustments.append("night: bus -8")
            if mode_type in ("cab", "car"): base_score += 8; adjustments.append("night: car/cab +8")
        if request.group_size >= 4 and mode_type in ("car", "cab", "bus_ac_vajra"):
            base_score += 10; adjustments.append(f"group {request.group_size} +10")
        r["overall_score"] = max(10, min(99, base_score))
        existing = r.get("score_explanation", "")
        r["score_explanation"] = (existing + " | " + " | ".join(adjustments)) if existing and adjustments else existing or " | ".join(adjustments)

    all_routes.sort(key=lambda x: (x["overall_score"], -x.get("total_fare", 999)), reverse=True)

    try:
        travel_recs = await asyncio.wait_for(
            llm_agent.get_travel_recs(source_name, dest_name, request.group_size, request.budget), timeout=8.0
        )
    except asyncio.TimeoutError:
        logger.warning("Travel recs timed out")
        travel_recs = []

    return _sanitize({
        "status": "success",
        "source": {"lat": request.source_lat, "lng": request.source_lng, "name": source_name},
        "destination": {"lat": request.dest_lat, "lng": request.dest_lng, "name": dest_name},
        "routes": all_routes[:15],
        "total_options": len(all_routes),
        "recommendations": travel_recs,
        "weather": weather
    })

def _estimate_fuel_cost(distance_km: float) -> float:
    from backend.core.config import settings
    liters_needed = distance_km / settings.PETROL_AVG_MILEAGE
    return round(liters_needed * settings.FUEL_PRICE_PER_LITER, 2)

@router.get("/metro-stations")
async def get_metro_stations(line: str = Query(None)):
    if line:
        stations = db.metro_lines.get(line, [])
    else:
        stations = db.metro_stations
    return {"status": "success", "stations": stations, "lines": list(db.metro_lines.keys())}

@router.get("/bus-stops")
async def get_bus_stops(near_lat: float = Query(None), near_lng: float = Query(None), radius: float = Query(1.0)):
    if near_lat and near_lng:
        stops = db.find_nearby_bus_stops(near_lat, near_lng, radius)
    else:
        stops = list(db.bus_stops.values())[:100]
    return {"status": "success", "stops": stops}

@router.get("/kia-routes")
async def get_kia_routes():
    return {"status": "success", "routes": db.kia_routes}

@router.get("/transit-fares")
async def get_transit_fares():
    return {"status": "success", "fares": db.transit_fares}

@router.get("/live-prices")
async def get_live_prices(source: str = Query(...), dest: str = Query(...), mode: str = "cab"):
    prices = await llm_agent.get_live_prices(source, dest, mode)
    return {"status": "success", "prices": prices}

@router.get("/all-segments")
async def get_all_segments(
    from_lat: float = Query(...), from_lng: float = Query(...),
    from_name: str = Query("Your Location"),
    dest_lat: float = Query(...), dest_lng: float = Query(...),
    dest_name: str = Query("Destination"),
    group_size: int = Query(1), budget: float = Query(None),
    max_depth: int = Query(3),
):
    loop = asyncio.get_running_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, transit_service.get_all_segments, from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size, budget, max_depth),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        logger.warning("get_all_segments timed out")
        result = {"segments": []}
    # Fire LLM live pricing concurrently with OSRM path fetching
    async def _fetch_live_prices():
        try:
            return await asyncio.wait_for(
                llm_agent.get_live_prices(from_name, dest_name), timeout=8.0
            )
        except Exception as e:
            logger.warning(f"Live prices fetch failed: {e}")
            return []
    llm_task = asyncio.create_task(_fetch_live_prices())

    # OSRM actual path fetching (fast — limited to top options)
    osrm_ok = False
    for url in ["http://localhost:5000", "http://osrm-car:5000"]:
        try:
            async with httpx.AsyncClient(timeout=1.5) as c:
                r = await c.get(f"{url}/route/v1/driving/77.6,12.97;77.57,12.97?overview=false")
                if r.status_code == 200:
                    osrm_ok = True
                    break
        except: continue

    path_tasks = []
    if osrm_ok:
        sem = asyncio.Semaphore(8)
        async def _fetch(opt, profile):
            async with sem:
                try:
                    p = await asyncio.wait_for(
                        transit_service.get_osrm_path_between(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], profile),
                        timeout=3.0
                    )
                    if p: opt["path"] = p
                except: pass
        pm = {"walk":"walking","cab":"driving","cab_xl":"driving","cab_women":"driving","cab_pet":"driving","auto":"driving","bike":"driving"}
        for seg in result.get("segments", []):
            for opt in seg.get("direct_options", [])[:3]:
                pr = pm.get(opt.get("mode",""))
                if pr and not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                    path_tasks.append(_fetch(opt, pr))
            for dest in seg.get("destinations", [])[:3]:
                for opt in dest.get("reach_options", [])[:2]:
                    pr = pm.get(opt.get("mode",""))
                    if pr and not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                        path_tasks.append(_fetch(opt, pr))
                for opt in dest.get("transit_options", [])[:3]:
                    pr = pm.get(opt.get("mode",""))
                    if pr and not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                        path_tasks.append(_fetch(opt, pr))
                    for fopt in opt.get("final_options", [])[:2]:
                        fpr = pm.get(fopt.get("mode",""))
                        if fpr and not fopt.get("path") and fopt.get("from_lat") and fopt.get("to_lat"):
                            path_tasks.append(_fetch(fopt, fpr))
    if path_tasks:
        try:
            await asyncio.wait_for(asyncio.gather(*path_tasks), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"OSRM batch paths partial ({len(path_tasks)} tasks, 10s timeout)")

    # Live prices from LLM
    live_prices = await llm_task
    if live_prices:
        price_map = {}
        for p in live_prices:
            pmode = p.get("mode", "cab")
            price_map[pmode] = {"price": p.get("price", 0), "provider": p.get("provider", "Ride"), "eta": p.get("eta_minutes", 15)}
        for seg in result.get("segments", []):
            for opt in seg.get("direct_options", []):
                omode = opt.get("mode", "")
                if omode in price_map:
                    lp = price_map[omode]
                    if lp["price"] > 0:
                        opt["fare"] = lp["price"] * group_size
                        opt["per_person"] = round(lp["price"])
                        opt["live_provider"] = lp["provider"]
                        opt["live_eta"] = lp["eta"]
                        opt["label"] = f"{lp['provider']} ~₹{round(lp['price'])}"
            for dest in seg.get("destinations", []):
                for opt in dest.get("reach_options", []):
                    omode = opt.get("mode", "")
                    if omode in price_map:
                        lp = price_map[omode]
                        if lp["price"] > 0:
                            opt["fare"] = lp["price"] * group_size
                            opt["per_person"] = round(lp["price"])
                            opt["live_provider"] = lp["provider"]
                            opt["live_eta"] = lp["eta"]
                            opt["label"] = f"{lp['provider']} ~₹{round(lp['price'])}"
    # Interpolated fallback for any option still missing a path
    for seg in result.get("segments", []):
        for opt in seg.get("direct_options", []):
            if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                opt["path"] = transit_service._interpolate_path(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)
        for dest in seg.get("destinations", []):
            for opt in dest.get("reach_options", []):
                if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                    opt["path"] = transit_service._interpolate_path(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)
            for opt in dest.get("transit_options", []):
                if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                    opt["path"] = transit_service._interpolate_path(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], 6)
                for fopt in opt.get("final_options", []):
                    if not fopt.get("path") and fopt.get("from_lat") and fopt.get("to_lat"):
                        fopt["path"] = transit_service._interpolate_path(fopt["from_lat"], fopt["from_lng"], fopt["to_lat"], fopt["to_lng"], 6)
    # Strip internal keys from response
    def _strip_internal(segments):
        for seg in segments:
            for dest in seg.get("destinations", []):
                for topt in dest.get("transit_options", []):
                    topt.pop("needs_next_segment", None)
    _strip_internal(result.get("segments", []))
    return _sanitize({
        "status": "success",
        "data": {
            "source": result.get("source"),
            "dest": result.get("dest"),
            "segments": result.get("segments", []),
            "total_segments": result.get("total_segments", 0),
        }
    })


@router.get("/segment-step")
async def get_segment_step(
    from_lat: float = Query(...), from_lng: float = Query(...),
    from_name: str = Query("Your Location"),
    dest_lat: float = Query(...), dest_lng: float = Query(...),
    dest_name: str = Query("Destination"),
    group_size: int = Query(1), budget: float = Query(None),
):
    step = transit_service.get_segment_step_options(
        from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size, budget
    )
    # Add OSRM paths for all options
    tasks = []
    for opt in step.get("direct_options", []):
        f_lat, f_lng = opt.get("from_lat"), opt.get("from_lng")
        t_lat, t_lng = opt.get("to_lat"), opt.get("to_lng")
        if f_lat and f_lng and t_lat and t_lng:
            profile = "driving" if opt.get("mode") in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else "walking"
            tasks.append(transit_service.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile))
        else:
            tasks.append(None)
        opt["_path_idx"] = len(tasks) - 1
    for vs in step.get("via_stops", []):
        for opt in vs.get("reach_options", []):
            f_lat, f_lng = opt.get("from_lat"), opt.get("from_lng")
            t_lat, t_lng = opt.get("to_lat"), opt.get("to_lng")
            if f_lat and f_lng and t_lat and t_lng:
                profile = "driving" if opt.get("mode") in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else "walking"
                tasks.append(transit_service.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile))
            else:
                tasks.append(None)
            opt["_path_idx"] = len(tasks) - 1
        for opt in vs.get("from_stop_options", []):
            f_lat, f_lng = opt.get("from_lat"), opt.get("from_lng")
            t_lat, t_lng = opt.get("to_lat"), opt.get("to_lng")
            if f_lat and f_lng and t_lat and t_lng:
                profile = "driving" if opt.get("mode") in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else "walking"
                tasks.append(transit_service.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile))
            else:
                tasks.append(None)
            opt["_path_idx"] = len(tasks) - 1
    results = await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
    res_idx = 0
    for opt in step.get("direct_options", []):
        pi = opt.pop("_path_idx", None)
        if pi is not None:
            r = results[res_idx] if res_idx < len(results) else None
            if r and not isinstance(r, Exception) and r:
                opt["path"] = r
            res_idx += 1
    for vs in step.get("via_stops", []):
        for opt in vs.get("reach_options", []):
            pi = opt.pop("_path_idx", None)
            if pi is not None:
                r = results[res_idx] if res_idx < len(results) else None
                if r and not isinstance(r, Exception) and r:
                    opt["path"] = r
                res_idx += 1
        for opt in vs.get("from_stop_options", []):
            pi = opt.pop("_path_idx", None)
            if pi is not None:
                r = results[res_idx] if res_idx < len(results) else None
                if r and not isinstance(r, Exception) and r:
                    opt["path"] = r
                res_idx += 1
    return _sanitize({"status": "success", "step": step})

@router.get("/complete-journey")
async def get_complete_journey(
    from_lat: float = Query(...), from_lng: float = Query(...),
    from_name: str = Query("Your Location"),
    dest_lat: float = Query(...), dest_lng: float = Query(...),
    dest_name: str = Query("Destination"),
    group_size: int = Query(1), budget: float = Query(None),
):
    result = transit_service.get_complete_journey_segments(
        from_lat, from_lng, from_name,
        dest_lat, dest_lng, dest_name,
        group_size, budget
    )
    # Add OSRM paths for all segments' transport options
    tasks = []
    for seg in result.get("segments", []):
        for dopt in seg.get("destination_options", []):
            for tropt in dopt.get("transport_options", []):
                fl, fn = tropt.get("from_lat"), tropt.get("from_lng")
                tl, tn = tropt.get("to_lat"), tropt.get("to_lng")
                if fl and fn and tl and tn:
                    profile = "driving" if tropt.get("mode") in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else "walking"
                    tasks.append(transit_service.get_osrm_path_between(fl, fn, tl, tn, profile))
                else:
                    tasks.append(None)
                tropt["_path_idx"] = len(tasks) - 1
        for ns in seg.get("next_segments", []):
            for dopt2 in ns.get("destination_options", []):
                for tropt2 in dopt2.get("transport_options", []):
                    fl, fn = tropt2.get("from_lat"), tropt2.get("from_lng")
                    tl, tn = tropt2.get("to_lat"), tropt2.get("to_lng")
                    if fl and fn and tl and tn:
                        profile = "driving" if tropt2.get("mode") in ("cab","cab_xl","cab_women","cab_pet","auto","bike") else "walking"
                        tasks.append(transit_service.get_osrm_path_between(fl, fn, tl, tn, profile))
                    else:
                        tasks.append(None)
                    tropt2["_path_idx"] = len(tasks) - 1
            for ns_dopt in ns.get("direct_options", []):
                fl, fn = ns_dopt.get("from_lat"), ns_dopt.get("from_lng")
                tl, tn = ns_dopt.get("to_lat"), ns_dopt.get("to_lng")
                if fl and fn and tl and tn:
                    profile = "walking" if ns_dopt.get("mode") == "walk" else "driving"
                    tasks.append(transit_service.get_osrm_path_between(fl, fn, tl, tn, profile))
                else:
                    tasks.append(None)
                ns_dopt["_path_idx"] = len(tasks) - 1
    results = await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
    res_idx = 0
    for seg in result.get("segments", []):
        for dopt in seg.get("destination_options", []):
            for tropt in dopt.get("transport_options", []):
                pi = tropt.pop("_path_idx", None)
                if pi is not None:
                    r = results[res_idx] if res_idx < len(results) else None
                    if r and not isinstance(r, Exception) and r:
                        tropt["path"] = r
                    res_idx += 1
        for ns in seg.get("next_segments", []):
            for dopt2 in ns.get("destination_options", []):
                for tropt2 in dopt2.get("transport_options", []):
                    pi = tropt2.pop("_path_idx", None)
                    if pi is not None:
                        r = results[res_idx] if res_idx < len(results) else None
                        if r and not isinstance(r, Exception) and r:
                            tropt2["path"] = r
                        res_idx += 1
            for ns_dopt in ns.get("direct_options", []):
                pi = ns_dopt.pop("_path_idx", None)
                if pi is not None:
                    r = results[res_idx] if res_idx < len(results) else None
                    if r and not isinstance(r, Exception) and r:
                        ns_dopt["path"] = r
                    res_idx += 1
    return _sanitize({"status": "success", "journey": result})

@router.get("/news")
async def get_travel_news(
    source_lat: float = Query(None),
    source_lng: float = Query(None),
    dest_lat: float = Query(None),
    dest_lng: float = Query(None),
    source_name: str = Query(""),
    dest_name: str = Query(""),
):
    news = await llm_agent.get_travel_news(source_name or None, dest_name or None)
    return _sanitize({"status": "success", "news": news})

_ROAD_COLORS = {
    "motorway": "#e74c3c", "motorway_link": "#e74c3c",
    "trunk": "#e67e22", "trunk_link": "#e67e22",
    "primary": "#f39c12", "primary_link": "#f39c12",
    "secondary": "#f1c40f", "secondary_link": "#f1c40f",
    "tertiary": "#2ecc71", "tertiary_link": "#2ecc71",
    "residential": "#27ae60", "service": "#1abc9c",
    "living_street": "#1abc9c", "unclassified": "#95a5a6",
}
_ROAD_ORDER = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service", "living_street", "unclassified"]

_traffic_speed_cache = None
_last_speed_load = 0

def _get_current_speed():
    """Realistic speed model based on time-of-day instead of synthetic CSV."""
    global _traffic_speed_cache, _last_speed_load
    now_ts = __import__("time").time()
    if _traffic_speed_cache is not None and now_ts - _last_speed_load < 60:
        return _traffic_speed_cache
    from datetime import datetime
    h = datetime.now().hour
    wd = datetime.now().weekday()
    base = 25.0
    if wd < 5:
        if 8 <= h < 10:
            base = 12.0
        elif 10 <= h < 12:
            base = 18.0
        elif 12 <= h < 16:
            base = 22.0
        elif 16 <= h < 19:
            base = 10.0
        elif 19 <= h < 21:
            base = 16.0
        elif 21 <= h or h < 6:
            base = 30.0
        else:
            base = 20.0
    else:
        base = 28.0 if 10 <= h < 18 else 32.0
    import random
    base += random.uniform(-2, 2)
    _traffic_speed_cache = base
    _last_speed_load = now_ts
    return base

@router.get("/traffic-overlay")
async def get_traffic_overlay(
    north: float = Query(...), south: float = Query(...),
    east: float = Query(...), west: float = Query(...)
):
    from datetime import datetime
    hour = datetime.now().hour
    is_peak = (8 <= hour <= 10) or (17 <= hour <= 20)
    congestion = "peak" if is_peak else "off"

    global _road_geojson_cache
    if _road_geojson_cache is None:
        geojson_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bangalore_roads.geojson")
        if os.path.exists(geojson_path):
            with open(geojson_path, encoding="utf-8") as f:
                _road_geojson_cache = json.load(f)

    if _road_geojson_cache is None:
        return {"status": "error", "message": "No road data available"}

    avg_speed = _get_current_speed()
    speed_kmh = avg_speed * 3.6

    if speed_kmh < 15:
        level = "heavy"
    elif speed_kmh < 30:
        level = "moderate"
    else:
        level = "light"

    level_colors = {"heavy": "#e74c3c", "moderate": "#f39c12", "light": "#2ecc71"}

    features = []
    for feat in _road_geojson_cache.get("features", []):
        if feat.get("geometry", {}).get("type") != "LineString":
            continue
        highway = feat["properties"].get("highway", "unclassified")
        coords = feat["geometry"]["coordinates"]
        if len(coords) < 2:
            continue

        color = level_colors.get(level, "#95a5a6")
        if is_peak and highway in ("motorway", "trunk", "primary", "secondary"):
            color = _darken_color(color, 20)

        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "highway": highway,
                "color": color,
                "name": feat["properties"].get("name", ""),
                "speed_kmh": round(speed_kmh, 1),
                "congestion_level": level,
            }
        })

    return {"status": "success", "type": "FeatureCollection", "features": features, "congestion": congestion}

def _darken_color(hex_color: str, amount: int) -> str:
    hex_color = hex_color.lstrip("#")
    r = max(0, int(hex_color[0:2], 16) - amount)
    g = max(0, int(hex_color[2:4], 16) - amount)
    b = max(0, int(hex_color[4:6], 16) - amount)
    return f"#{r:02x}{g:02x}{b:02x}"
