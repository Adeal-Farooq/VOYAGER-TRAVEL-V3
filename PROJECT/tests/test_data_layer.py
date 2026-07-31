"""Data-layer tests for VOYAGER v2 (PROMPT_1 acceptance). Run: pytest tests/ -q"""
import pytest

from backend.services import fare_engine as fe
from backend.services.database import TransitDatabase
from backend.services.gtfs_service import GTFSService, clean_route_short_name


@pytest.fixture(scope="module")
def gtfs():
    g = GTFSService()
    g.load()
    return g


@pytest.fixture(scope="module")
def db():
    return TransitDatabase()


# ------------------------------------------------------------- route names
def test_clean_route_short_name_strips_terminal_garbage():
    assert clean_route_short_name("MF-28 JKLO-ISROQ-LGRNB") == "MF-28"
    assert clean_route_short_name("  242-LA ") == "242-LA"
    assert clean_route_short_name("BEL GS-16") == "BEL GS-16"  # real name kept
    assert clean_route_short_name("KSRTC-T NARASIPURA-1") == "KSRTC-T NARASIPURA-1"


# --------------------------------------------------------------- gtfs loads
def test_gtfs_pickle_loads_fast(gtfs):
    assert len(gtfs.data["stops_by_name"]) > 4000
    assert len(gtfs.data["shapes"]) > 7000


def test_resolve_majestic(gtfs):
    assert gtfs.resolve_stop_name("Majestic") == "kempegowda bus station(majestic/kbs)"


def test_known_unresolvable_acronym_stays_none(gtfs):
    assert gtfs.resolve_stop_name("hnrj") is None  # one of the 14 known no-match names


def test_routes_at_majestic_real(gtfs):
    routes = gtfs.get_routes_at_stop("Majestic")
    assert len(routes) > 5
    assert all(r.source == "schedule" for r in routes)
    assert all(r.scheduled_departure.count(":") == 2 for r in routes)


def test_stop_to_stop_segment(gtfs):
    seg = gtfs.get_stop_to_stop_segment("244-C", "vidhana soudha", "kempegowda bus station")
    assert seg and len(seg) >= 5
    seg_back = gtfs.get_stop_to_stop_segment("244-C", "kempegowda bus station", "vidhana soudha")
    assert seg_back and len(seg_back) >= 5


# -------------------------------------------------------------- bus stops
def test_no_nan_stop_names(db):
    names = {b.name.lower() for b in db.all_bus_stops()}
    assert not (names & {"nan", "none", "null", ""})
    assert len(db.all_bus_stops()) > 2900


def test_spatial_query_fast(db):
    import time

    t0 = time.perf_counter()
    for _ in range(100):
        db.bus_stops_near(12.97, 77.59, 1000)
    assert (time.perf_counter() - t0) / 100 < 0.005  # <5ms per call


# ------------------------------------------------------------------ metro
def test_metro_only_purple_green(db):
    lines = set()
    for m in db.all_metro_stations():
        lines.update(m.lines)
    assert lines == {"Purple Line", "Green Line"}
    assert not any("yelahanka" in m.name.lower() for m in db.all_metro_stations())


# ------------------------------------------------------------------ fares
def test_fare_spot_checks():
    assert fe.bmtc_fare("nonac", 2.0, "adult").amount == 6.0
    assert fe.bmtc_fare("nonac", 5.0, "adult").amount == 18.0
    assert fe.bmtc_fare("nonac", 5.0, "child").amount == 9.0
    assert fe.bmtc_fare("ac", 3.0, "adult").amount == 20.0
    assert fe.bmtc_fare("ac", 3.0, "senior").amount == 15.0
    assert fe.metro_fare(3.0, "purple").amount == 21.0
    assert fe.metro_fare(12.0, "green").amount == 63.0


def test_surge():
    assert fe.surge_multiplier(8, True) == 1.5
    assert fe.surge_multiplier(2, True) == 1.8
    assert fe.surge_multiplier(13, False) == 1.2


def test_ride_range_per_person_split():
    lo, hi = fe.ride_fare_range("uber_go", 10.0, 4)
    assert abs(lo.per_person * 4 - lo.amount) < 1e-6
    assert lo.is_estimated
