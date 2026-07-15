import math, json, csv, os, asyncio
from fastapi import APIRouter, Query
from backend.models.transit import ATobRequest
from backend.services.transit_service import transit_service
from backend.agents.llm_agent import llm_agent
from backend.core.database import db

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
            except:
                pass
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
            weather = await asyncio.wait_for(llm_agent.get_weather_impact(), timeout=5.0)
        except:
            weather = {}
        return _sanitize({
            "status": "success", "multi_stop": True,
            "source": {"lat": request.source_lat, "lng": request.source_lng},
            "destination": {"lat": request.dest_lat, "lng": request.dest_lng},
            "waypoints": [{"lat": wp.lat, "lng": wp.lng, "name": wp.name} for wp in request.waypoints],
            "routes": all_routes, "total_options": len(all_routes), "weather": weather
        })

    metro_station_near_source = db.find_nearby_metro_stations(request.source_lat, request.source_lng, 2.0)
    metro_station_near_dest = db.find_nearby_metro_stations(request.dest_lat, request.dest_lng, 2.0)
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
                    "instructions": f"Walk {dist:.1f}km - about {walk_time:.0f} minutes"
                }]
            }]
        }

    public_routes = transit_service.get_route_legs_public(
        request.source_lat, request.source_lng,
        request.dest_lat, request.dest_lng,
        request.budget, request.group_size
    )

    # Parallel path enrichment for all public routes
    async def enrich_all():
        tasks = [transit_service._add_leg_paths(r) for r in public_routes]
        await asyncio.gather(*tasks, return_exceptions=True)
    try:
        await asyncio.wait_for(enrich_all(), timeout=30.0)
    except:
        pass

    driving = await transit_service.get_driving_route(
        request.source_lat, request.source_lng,
        request.dest_lat, request.dest_lng
    )

    live_prices = await llm_agent.get_live_prices(source_name, dest_name)

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

    try:
        weather = await asyncio.wait_for(llm_agent.get_weather_impact(), timeout=5.0)
    except:
        weather = {}
    is_rainy = "rain" in (weather.get("condition", "") or "").lower()
    from datetime import datetime
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

    travel_recs = await llm_agent.get_travel_recs(
        source_name, dest_name, request.group_size, request.budget
    )

    return _sanitize({
        "status": "success",
        "source": {"lat": request.source_lat, "lng": request.source_lng, "name": source_name},
        "destination": {"lat": request.dest_lat, "lng": request.dest_lng, "name": dest_name},
        "routes": all_routes[:6],
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
    result = transit_service.get_all_segments(
        from_lat, from_lng, from_name, dest_lat, dest_lng, dest_name, group_size, budget, max_depth
    )
    # Fire LLM live pricing concurrently with OSRM path fetching
    async def _fetch_live_prices():
        try:
            return await asyncio.wait_for(
                llm_agent.get_live_prices(from_name, dest_name), timeout=8.0
            )
        except:
            return []
    llm_task = asyncio.create_task(_fetch_live_prices())

    # Collect OSRM paths for non-transit options (direct cabs/auto/walk, reach, final mile)
    # Bus transit uses interpolated paths (instant) — only metro/train get OSRM
    osrm_sem = asyncio.Semaphore(15)
    path_tasks = []
    async def _fetch_osrm(opt, profile):
        async with osrm_sem:
            try:
                p = await transit_service.get_osrm_path_between(opt["from_lat"], opt["from_lng"], opt["to_lat"], opt["to_lng"], profile)
                if p:
                    opt["path"] = p
            except:
                pass
    driving_modes = {"cab","cab_xl","cab_women","cab_pet","auto","bike"}
    for seg in result.get("segments", []):
        for opt in seg.get("direct_options", []):
            if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat") and opt.get("mode") in driving_modes:
                path_tasks.append(_fetch_osrm(opt, "driving"))
        for dest in seg.get("destinations", []):
            for opt in dest.get("reach_options", []):
                if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat") and opt.get("mode") in driving_modes:
                    path_tasks.append(_fetch_osrm(opt, "driving"))
            for opt in dest.get("transit_options", []):
                # Only OSRM for metro/train (not bus)
                if opt.get("mode") not in ("bus_ordinary", "bus_ac_vajra", "kia_bus") and opt.get("mode") in driving_modes:
                    if not opt.get("path") and opt.get("from_lat") and opt.get("to_lat"):
                        path_tasks.append(_fetch_osrm(opt, "driving"))
                for fopt in opt.get("final_options", []):
                    if not fopt.get("path") and fopt.get("from_lat") and fopt.get("to_lat") and fopt.get("mode") in driving_modes:
                        path_tasks.append(_fetch_osrm(fopt, "driving"))
    if path_tasks:
        await asyncio.gather(*path_tasks)

    # Apply live prices if LLM returned them
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


@router.get("/mini-path-options")
async def get_mini_path_options(
    source_lat: float = Query(...),
    source_lng: float = Query(...),
    dest_lat: float = Query(...),
    dest_lng: float = Query(...),
    group_size: int = Query(1)
):
    options = transit_service.get_mini_path_options(
        source_lat, source_lng, dest_lat, dest_lng, group_size
    )
    # Add paths to mini-path options (walking for walk modes, driving for cab/auto, driving for transit rides)
    all_opts = []
    for key in ("source_walk_options", "direct_ride_options"):
        for opt in options.get(key, []):
            all_opts.append(opt)
    for key in ("source_to_transit", "transit_ride_options"):
        if isinstance(options.get(key), dict):
            for mode_list in options.get(key, {}).values():
                all_opts.extend(mode_list)
        elif isinstance(options.get(key), list):
            all_opts.extend(options.get(key))
    for key in ("transit_to_dest",):
        if isinstance(options.get(key), dict):
            for mode_list in options.get(key, {}).values():
                all_opts.extend(mode_list)
    for opt in all_opts:
        f_lat, f_lng = opt.get("from_lat"), opt.get("from_lng")
        t_lat, t_lng = opt.get("to_lat"), opt.get("to_lng")
        if f_lat and f_lng and t_lat and t_lng:
            profile = "driving" if opt.get("mode") in ("cab", "auto", "cab_xl", "cab_women", "cab_pet", "bike") else "walking"
            path = await transit_service.get_osrm_path_between(f_lat, f_lng, t_lat, t_lng, profile)
            if path:
                opt["path"] = path
    return _sanitize({"status": "success", "options": options})

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

_road_geojson_cache = None
_traffic_speeds_cache = None
_last_speed_load = 0

def _load_traffic_speeds():
    global _traffic_speeds_cache, _last_speed_load
    now = __import__("time").time()
    if _traffic_speeds_cache is not None and now - _last_speed_load < 60:
        return _traffic_speeds_cache
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_cache", "traffic_logs.csv")
    speed_map = {}
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                step = int(row["step_time"])
                speed = float(row["live_speed_mps"])
                if step not in speed_map:
                    speed_map[step] = []
                speed_map[step].append(speed)
    avg_speeds = {step: sum(v)/len(v) for step, v in speed_map.items()}
    _traffic_speeds_cache = avg_speeds
    _last_speed_load = now
    return avg_speeds

def _get_current_speed():
    speeds = _load_traffic_speeds()
    if not speeds:
        return 15.0
    latest_step = max(speeds.keys())
    return speeds[latest_step]

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
