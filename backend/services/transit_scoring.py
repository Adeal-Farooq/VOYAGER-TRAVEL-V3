import math


def topsis_score_routes(routes: list[dict], budget: float = None, group_size: int = 1,
                         weather: dict = None) -> None:
    if not routes:
        return

    comfort_map = {
        "metro_interchange": 5, "metro": 5, "bus_ac_vajra": 4,
        "kia_bus": 4, "bus_ordinary": 2, "bus_to_metro": 4,
        "metro_to_bus": 3, "car": 5, "cab": 4, "walk": 1,
        "metro_astar": 5, "multi_modal_astar": 4,
    }
    safety_map = {
        "metro_interchange": 5, "metro": 5, "bus_ac_vajra": 4,
        "kia_bus": 4, "bus_ordinary": 3, "bus_to_metro": 4, "metro_to_bus": 3,
        "car": 5, "cab": 4, "walk": 3,
        "metro_astar": 5, "multi_modal_astar": 4,
    }

    weather = weather or {}
    is_rainy = "rain" in (weather.get("condition", "") or "").lower()
    is_night = False
    from datetime import datetime
    h = datetime.now().hour
    is_night = h < 6 or h > 20

    from backend.services.topsis_engine import topsis

    alternatives = []
    for r in routes:
        rtype = r.get("type", "")
        walk_km = r.get("total_walking_km", 0)
        wi = 0
        if is_rainy:
            if walk_km > 1: wi -= 15
            if rtype in ("walk", "bike"): wi -= 20
            if rtype in ("car", "cab"): wi += 5
        if is_night:
            if walk_km > 1.5: wi -= 10
            if rtype in ("bus_ordinary",): wi -= 8
            if rtype in ("cab", "car"): wi += 8
        alt = {
            "total_fare": r.get("total_fare", 100),
            "total_duration_minutes": r.get("total_duration_minutes", 60),
            "comfort": comfort_map.get(rtype, 3),
            "safety": safety_map.get(rtype, 3),
            "total_walking_km": walk_km,
            "overall_score": r.get("overall_score", 50),
            "weather_impact": wi,
        }
        alternatives.append(alt)

    scored = topsis.evaluate(alternatives)

    for r, s in zip(routes, scored):
        ts = s.get("topsis_score", 0.5)
        if ts is None or (isinstance(ts, float) and (math.isnan(ts) or math.isinf(ts))):
            ts = 0.5
        raw_score = int(max(0, min(1, ts)) * 90) + 10

        if budget and budget > 0:
            fare = r.get("total_fare", 100)
            ratio = fare / budget
            if ratio <= 0.4:
                raw_score += 10
            elif ratio <= 0.7:
                raw_score += 5
            elif ratio > 1.0:
                raw_score -= 15
            elif ratio > 0.9:
                raw_score -= 5

        if group_size > 1:
            pp = r.get("total_fare", 100) / group_size
            if pp <= 30:
                raw_score += 5

        r["overall_score"] = max(10, min(99, raw_score))
        r["score_explanation"] = f"topsis {ts:.3f} | rank {s.get('rank', '?')}"
