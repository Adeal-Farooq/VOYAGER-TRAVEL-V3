"""Segment planner (PROMPT_3) acceptance tests. Run: pytest tests/ -q"""
import pytest

from backend.services.database import TransitDatabase
from backend.services.gtfs_service import GTFSService
from backend.services.segment_builder import SegmentBuilder, _hav

YELAHANKA_SCHOOL = {"lat": 13.10328923, "lng": 77.57684938, "name": "Govt School Yelahanka 4th Phase"}
WONDERLA = {"lat": 12.8355, "lng": 77.4490, "name": "Wonderla"}
MG_ROAD = {"lat": 12.9757, "lng": 77.6048, "name": "MG Road"}


@pytest.fixture(scope="module")
def builder():
    gtfs = GTFSService()
    gtfs.load()
    db = TransitDatabase()
    return SegmentBuilder(gtfs, db, gh=None)  # no docker dependency


# ---------------------------------------------------------------- T1 Wonderla
def test_t1_segments_return_real_options(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")
    assert len(resp["segments"]) == 2
    seg1, seg2 = resp["segments"][0], resp["segments"][1]
    assert seg1["segmentId"] == 1 and seg2["segmentId"] == 2
    assert seg1["options"] and seg2["options"]
    # every option carries the full contract shape
    for o in seg1["options"] + seg2["options"]:
        assert set(o) >= {"optionId", "destinationStop", "mode", "routeNumber", "fromStop",
                          "distanceKm", "durationMin", "departureTime", "arrivalTime",
                          "fare", "perPersonFare", "geometry", "geometrySource", "status",
                          "isTopRecommended", "connectedFrom", "transitOptionsFromThisStop",
                          "exceedsBudget"}
        assert o["destinationStop"]["name"]
        assert o["geometrySource"] in ("gtfs_shape", "metro_line", "graphhopper", "interpolated")


def test_t1_bus_legs_real_gtfs(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")
    buses = [o for s in resp["segments"] for o in s["options"] if o["mode"] == "bus"]
    assert buses  # real bus options exist
    for o in buses:
        assert o["routeNumber"] and not o["routeNumber"].startswith("Purple")
        assert o["status"] in ("scheduled", "not_running")
        if o["status"] == "scheduled":
            assert o["geometrySource"] == "gtfs_shape" or o["geometry"]


def test_t1_connected_from_chains(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")
    seg1, seg2 = resp["segments"]
    # segment-2 options must connect FROM a segment-1 arrival stop
    seg1_stops = {o["destinationStop"]["name"] for o in seg1["options"]}
    for o in seg2["options"]:
        assert o["connectedFrom"] in seg1_stops


def test_t1_forward_progress_no_backtrack(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")
    dest = (WONDERLA["lat"], WONDERLA["lng"])
    for s in resp["segments"]:
        for o in s["options"]:
            if o["mode"] == "walk":
                continue
            # the chosen arrival stop must be closer to dest than the boarding
            # stop (metro gets the wider tolerance for line siting)
            from_d = _hav(o["_fromLat"], o["_fromLng"], dest[0], dest[1])
            to_d = _hav(o["destinationStop"]["lat"], o["destinationStop"]["lng"], dest[0], dest[1])
            tol = 2500 if o["mode"] == "metro" else 500
            assert to_d < from_d + tol


# ---------------------------------------------------------------- T2 MG Road
def test_t2_multi_bus_to_mg_road(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, MG_ROAD, group_size=1, budget=300,
                                  current_time="2026-07-31T08:30:00+05:30")
    routes = {o["routeNumber"] for s in resp["segments"] for o in s["options"]
              if o["mode"] == "bus" and o["status"] == "scheduled"}
    # real GTFS routes (e.g. 402-B / G-9 family) with scheduled times must exist
    assert routes
    for o in resp["segments"][0]["options"]:
        if o["mode"] == "bus":
            assert o["fare"] > 0 and o["perPersonFare"] > 0


# ---------------------------------------------------------------- T3 chaining
def test_t3_time_chaining_next_segment(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                                  current_time="2026-07-31T15:20:00+05:30")
    seg1 = resp["segments"][0]
    chosen = next(o for o in seg1["options"] if o["isTopRecommended"])
    arrival = chosen["arrivalTime"]
    nxt = builder.build_segment_next(
        journey={"source": YELAHANKA_SCHOOL, "destination": WONDERLA},
        chosen_legs=[{"optionId": chosen["optionId"], "arrivalTime": arrival,
                      "destinationStop": chosen["destinationStop"]["name"]}],
        group_size=2, budget=500)
    assert not nxt["journeyComplete"]
    seg = nxt["segments"][0]
    assert all(o["connectedFrom"] == chosen["destinationStop"]["name"] for o in seg["options"])
    # departures are time-chained: >= arrival + 4min buffer
    arr_min = builder._parse_hhmm(arrival)
    for o in seg["options"]:
        if o["mode"] in ("bus", "metro"):
            dep_min = builder._parse_hhmm(o["departureTime"])
            assert dep_min >= arr_min + 4


# ---------------------------------------------------------------- T4 short hop
def test_t4_short_hop_walk_primary_no_cab(builder):
    near_dest = {"lat": 12.9770, "lng": 77.6070, "name": "Near MG Road"}
    resp = builder.build_segments(MG_ROAD, near_dest, group_size=1, budget=200,
                                  current_time="2026-07-31T09:00:00+05:30")
    seg1 = resp["segments"][0]
    walks = [o for o in seg1["options"] if o["mode"] == "walk"]
    assert walks
    top = next(o for o in seg1["options"] if o["isTopRecommended"])
    assert top["mode"] == "walk"
    assert top["fare"] == 0
    # no ride/cab options for short hops
    assert not any(o["mode"] == "ride" for o in seg1["options"])
    # walk legs all free
    for w in walks:
        assert w["fare"] == 0 and w["perPersonFare"] == 0


# ------------------------------------------------------------- journey complete
def test_segment_next_journey_complete(builder):
    # destination IS a real GTFS stop -> journey completes on arrival
    resolved = builder.gtfs.resolve_stop_name("Majestic")
    c = builder.gtfs.data["stops_by_name"][resolved]
    dest = {"lat": c[0], "lng": c[1], "name": "Majestic area"}
    r = builder.build_segment_next(
        journey={"source": YELAHANKA_SCHOOL, "destination": dest},
        chosen_legs=[{"optionId": "x", "arrivalTime": "16:00", "destinationStop": "Majestic"}],
        group_size=1, budget=500)
    assert r["journeyComplete"] is True
    assert r["arrival"]["message"]
    assert len(r["timeline"]) == 1


# ------------------------------------------------------------- cache & budget
def test_budget_exceeded_flag(builder):
    resp = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=4, budget=5,
                                  current_time="2026-07-31T15:20:00+05:30")
    # walk options never exceed; any paid option over a tiny budget is flagged, not dropped
    for s in resp["segments"]:
        for o in s["options"]:
            assert "exceedsBudget" in o
            if o["fare"] > 0:
                assert o["exceedsBudget"] is True


def test_segments_cached(builder):
    import time
    r1 = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=1, budget=300,
                                current_time="2026-07-31T15:20:00+05:30")
    t0 = time.perf_counter()
    r2 = builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=1, budget=300,
                                current_time="2026-07-31T15:25:00+05:30")  # same 10-min bucket
    assert time.perf_counter() - t0 < 0.05  # served from 5-min cache
    assert r1 == r2


def test_timing_warm(builder):
    import time
    t0 = time.perf_counter()
    builder.build_segments(YELAHANKA_SCHOOL, WONDERLA, group_size=2, budget=500,
                           current_time="2026-07-31T15:20:00+05:30")
    assert time.perf_counter() - t0 < 3.0  # <=3s warm (PROMPT_3 §5)


# -------------------------------------------------------- metro interchange fix
def test_metro_interchange_offers_both_lines(builder):
    """Majestic (Purple+Green hub) must yield metro rides on EITHER line."""
    kbs = next(s for s in builder.db.all_bus_stops() if s.name == "Kempegowda Bus Station")
    opts = builder._options_from_stop(
        {"name": kbs.name, "lat": kbs.lat, "lng": kbs.lng}, MG_ROAD,
        11 * 60 + 10, 1, 300, seg_num=3, connected_from=kbs.name)
    metros = [o for o in opts if o["mode"] == "metro"]
    assert metros  # standing at Majestic metro -> real metro options exist
    lines = {o["routeNumber"] for o in metros}
    assert "Purple" in lines and "Green" in lines
    # the Purple ride actually reaches the MG Road corridor with real distance
    mg = next((o for o in metros if o["destinationStop"]["name"] == "Mahatma Gandhi Road"), None)
    assert mg is not None
    assert mg["distanceKm"] > 1.0 and mg["durationMin"] > 1
    assert mg["geometrySource"] == "metro_line" and mg["geometry"]


# --------------------------------------------------- long-haul bus->metro ride
def test_long_haul_bus_to_metro_transfer(builder):
    """Yelahanka -> MG Road should offer a direct bus to a metro interchange
    (Kempegowda Bus Station / mg road metro etc.) that is metro-transfer
    flagged, then metro to MG Road."""
    resp = builder.build_segments(YELAHANKA_SCHOOL, MG_ROAD, group_size=1, budget=300,
                                  current_time="2026-07-31T08:30:00+05:30")
    transfers = [o for s in resp["segments"] for o in s["options"]
                 if o.get("isMetroTransfer") and o["mode"] == "bus"]
    assert transfers
    # at least one direct ride reaches the Majestic/MG-road metro corridor
    kbs = [o for o in transfers
           if "kempegowda" in o["destinationStop"]["name"].lower()
           or "ananda rao" in o["destinationStop"]["name"].lower()
           or "mg road" in o["destinationStop"]["name"].lower()
           or "mahatma" in o["destinationStop"]["name"].lower()
           or "mysore bank" in o["destinationStop"]["name"].lower()]
    assert kbs
    top = kbs[0]
    assert top["status"] in ("scheduled", "not_running")
    assert top["fare"] > 0
    # geometry is the stop-to-stop slice, never the full route
    assert top["geometrySource"] in ("gtfs_shape", "interpolated")
    # the long ride is real, not a degenerate 1-min stub
    assert top["durationMin"] > 10
    # and it chains into a metro at the interchange
    nxt = builder.build_segment_next(
        journey={"source": YELAHANKA_SCHOOL, "destination": MG_ROAD},
        chosen_legs=[{"optionId": top["optionId"], "arrivalTime": top["arrivalTime"],
                      "destinationStop": top["destinationStop"]["name"]}],
        group_size=1, budget=300)
    # if the long bus already lands at the destination area, that's fine too
    if nxt["journeyComplete"]:
        assert nxt["arrival"]["message"]
        return
    metros = [o for o in nxt["segments"][0]["options"] if o["mode"] == "metro"]
    assert metros
    mg = next((o for o in metros
               if o["destinationStop"]["name"] == "Mahatma Gandhi Road"), None)
    assert mg is not None  # Purple metro directly to MG Road


# ------------------------------------------------- Rajanukunte direct-to-majestic
def test_rajanukunte_direct_285_to_majestic(builder):
    """285 from Rajanukunte rides directly to the Majestic/MG-road metro core;
    long reverse-shape rides must keep real duration (not a 1-min stub)."""
    rk = next(s for s in builder.db.all_bus_stops() if s.name == "Rajanukunte")
    source = {"lat": rk.lat, "lng": rk.lng, "name": "Rajanukunte"}
    dest = {"lat": 12.980973157500646, "lng": 77.59731531148601, "name": "Cubbon Park"}
    resp = builder.build_segments(source, dest, group_size=1, budget=300,
                                  current_time="2026-07-31T09:00:00+05:30")
    transfers = [o for o in resp["segments"][0]["options"]
                 if o.get("isMetroTransfer") and o["mode"] == "bus"]
    assert transfers
    # the 285 ride reaches the Majestic area (KBS / mysore bank / kpcc)
    near_majestic = [o for o in transfers
                     if o["routeNumber"] == "285"
                     and any(k in o["destinationStop"]["name"].lower()
                             for k in ("kempegowda", "mysore bank", "kpcc",
                                       "mahatma", "mg road"))]
    assert near_majestic
    ride = near_majestic[0]
    # long ride, real duration: ~27km at bus speed is far more than 10 min
    assert ride["distanceKm"] > 10 and ride["durationMin"] > 30
    # it chains into metro toward Cubbon Park
    nxt = builder.build_segment_next(
        journey={"source": source, "destination": dest},
        chosen_legs=[{"optionId": ride["optionId"], "arrivalTime": ride["arrivalTime"],
                      "destinationStop": ride["destinationStop"]["name"]}],
        group_size=1, budget=300)
    if nxt["journeyComplete"]:
        return
    metros = [o for o in nxt["segments"][0]["options"] if o["mode"] == "metro"]
    assert metros
