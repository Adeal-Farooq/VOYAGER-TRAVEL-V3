"""Routing graph + N-hop route finder tests (PROMPT_2 acceptance). Run: pytest tests/ -q"""
import pytest

from backend.services.database import TransitDatabase
from backend.services.gtfs_service import GTFSService
from backend.services.transit_graph import TransitAstarGraph
from backend.services.route_finder import RouteFinder


@pytest.fixture(scope="module")
def gtfs():
    g = GTFSService()
    g.load()
    return g


@pytest.fixture(scope="module")
def db():
    return TransitDatabase()


@pytest.fixture(scope="module")
def graph(gtfs, db):
    return TransitAstarGraph(gtfs, db)


@pytest.fixture(scope="module")
def finder(gtfs, db):
    return RouteFinder(gtfs, db, graphhopper=None)  # no docker dependency in tests


# --------------------------------------------------------------- graph build
def test_graph_node_counts(graph):
    kinds = {}
    for n in graph.nodes.values():
        kinds[n.kind] = kinds.get(n.kind, 0) + 1
    assert kinds.get("bus", 0) > 2000
    assert kinds.get("metro", 0) == 68
    assert kinds.get("rail", 0) >= 22


def test_graph_has_walk_transfer_edges(graph):
    n_walk = 0
    for nbrs in graph.adj.values():
        n_walk += sum(1 for _t, e, _d in nbrs if e == "walk")
    assert n_walk > 0


def test_metro_edges_carry_line(graph):
    for k, etype, edata in graph.neighbors("metro:Mahatma Gandhi Road"):
        if etype == "metro":
            assert edata.get("line") in ("Purple Line", "Green Line")
            assert edata["time_min"] > 0
            assert edata["dist_m"] > 0


def test_bus_nodes_have_bus_edges(graph):
    bus_keys = [k for k, n in graph.nodes.items() if n.kind == "bus"]
    with_bus_edge = 0
    for k in bus_keys[:500]:
        if any(e == "bus" for _t, e, _d in graph.neighbors(k)):
            with_bus_edge += 1
    assert with_bus_edge > 400  # most connected stops have at least one bus edge


# ------------------------------------------------------------- route finding
def test_bus_transfer_paths_mg_koramangala(finder):
    plans = finder.find_routes_by_coords(12.9757, 77.6048, 12.9346, 77.6177,
                                         depart_min=9 * 60 + 15, group_size=2)
    bus_plans = [p for p in plans if any(l.mode == "bus" for l in p.legs)]
    assert len(bus_plans) >= 1
    p = bus_plans[0]
    assert p.total_fare > 0
    for l in p.legs:
        assert l.geometry  # every leg has geometry
        assert l.geometry_source in ("gtfs_shape", "metro_line", "graphhopper", "interpolated")
    # no fabricated bus numbers: any "scheduled" bus leg must carry a real GTFS route number
    for l in p.legs:
        if l.mode == "bus" and l.status == "scheduled":
            assert l.route_number and not l.route_number.startswith("Purple")


def test_pure_metro_interchange_found(finder):
    plans = finder.find_routes_by_coords(12.9757, 77.6048, 12.8963, 77.5700,
                                         depart_min=9 * 60 + 15, group_size=1)
    metro_plans = [p for p in plans if any(l.mode == "metro" for l in p.legs)]
    assert len(metro_plans) >= 1
    # the pure-metro interchange route MG Road -> Kempegowda -> Yelachenahalli must appear
    metro_only = [p for p in metro_plans if all(l.mode in ("walk", "metro") for l in p.legs)]
    assert len(metro_only) >= 1
    lines = {l.line for l in metro_only[0].legs if l.mode == "metro"}
    assert "Purple Line" in lines and "Green Line" in lines


def test_forward_progress_no_backtracking(finder):
    from backend.services.route_finder import _hav_m
    dest = (12.9346, 77.6177)
    plans = finder.find_routes_by_coords(12.9757, 77.6048, dest[0], dest[1],
                                         depart_min=9 * 60 + 15, group_size=1)
    assert plans
    for p in plans:
        # interchange detours (e.g. MG Road -> Majestic to board the Green line)
        # may individually move away from dest; the NET ride progress must still
        # be toward dest. A circular route (net backtrack) fails this.
        net = 0.0
        for l in p.legs:
            if l.mode == "walk":
                continue
            start_d = _hav_m(l.from_lat, l.from_lng, dest[0], dest[1])
            end_d = _hav_m(l.to_lat, l.to_lng, dest[0], dest[1])
            net += start_d - end_d
        assert net > 0  # rides overall move toward dest


def test_walk_only_route_when_close(finder):
    plans = finder.find_routes_by_coords(12.9757, 77.6048, 12.9770, 77.6070,
                                         depart_min=9 * 60 + 15, group_size=1)
    walk = [p for p in plans if len(p.legs) == 1 and p.legs[0].mode == "walk"]
    assert len(walk) >= 1
    assert walk[0].total_fare == 0


def test_ride_route_always_present(finder):
    plans = finder.find_routes_by_coords(12.9757, 77.6048, 12.9346, 77.6177,
                                         depart_min=9 * 60 + 15, group_size=1)
    assert any(p.legs[0].mode == "ride" for p in plans)


def test_timing_warm_route_finding(finder):
    import time
    t0 = time.perf_counter()
    finder.find_routes_by_coords(12.9757, 77.6048, 12.9346, 77.6177,
                                 depart_min=9 * 60 + 15, group_size=2)
    assert time.perf_counter() - t0 < 5.0  # ≤5s warm for known-good pair
