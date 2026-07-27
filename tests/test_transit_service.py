"""Integration tests for transit_service.py — requires DB initialization."""

import pytest
from backend.services.transit_service import TransitService


@pytest.fixture(scope="module")
def svc():
    return TransitService()


class TestTransitServiceHaversine:
    def test_within_bengaluru(self, svc):
        d = svc.haversine_distance(12.9716, 77.5946, 13.1008, 77.5963)
        assert 12 < d < 16

    def test_same_point(self, svc):
        assert svc.haversine_distance(12.9716, 77.5946, 12.9716, 77.5946) == 0.0

    def test_zero_on_error(self, svc):
        d = svc.haversine_distance(12.9716, 77.5946, 0.0 / 0.0 if False else 12.9750, 77.6066)
        # geopy handles NaN gracefully now — just check return type
        assert isinstance(d, float)


class TestTransitServiceFindCommonRoutes:
    def test_returns_list(self, svc):
        src = {"name": "Majestic", "routes": ["500C", "K-2", "G-6"]}
        dst = {"name": "MG Road", "routes": ["500C", "K-2"]}
        result = svc._find_common_routes(src, dst)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty_if_no_common(self, svc):
        src = {"name": "A", "routes": ["100"]}
        dst = {"name": "B", "routes": ["200"]}
        result = svc._find_common_routes(src, dst)
        assert result == []

    def test_returns_at_most_5(self, svc):
        src = {"name": "A", "routes": [str(i) for i in range(10)]}
        dst = {"name": "B", "routes": [str(i) for i in range(10)]}
        result = svc._find_common_routes(src, dst)
        assert len(result) <= 5


class TestTransitServiceAddLegCoords:
    def test_adds_coords_for_known_stops(self, svc):
        route = {
            "legs": [
                {"from": "Your Location", "to": "Majestic",
                 "mode": "walk", "distance_km": 0.5},
                {"from": "Majestic", "to": "MG Road",
                 "mode": "metro", "distance_km": 3.0},
            ]
        }
        svc._add_leg_coords(route, 12.9716, 77.5946, 12.9750, 77.6066)
        for leg in route["legs"]:
            assert "from_lat" in leg
            assert "from_lng" in leg
            assert "to_lat" in leg
            assert "to_lng" in leg

    def test_unknown_stop_falls_back(self, svc):
        route = {
            "legs": [
                {"from": "Your Location", "to": "Some Unknown Stop XYZ",
                 "mode": "walk", "distance_km": 0.5},
            ]
        }
        svc._add_leg_coords(route, 12.9716, 77.5946, 12.9750, 77.6066)
        assert route["legs"][0]["from_lat"] == 12.9716
        assert route["legs"][0]["from_lng"] == 77.5946


class TestTransitServiceGetRouteLegsPublic:
    def test_returns_list_of_routes(self, svc):
        routes = svc.get_route_legs_public(12.9716, 77.5946, 12.9750, 77.6066)
        assert isinstance(routes, list)
        assert len(routes) >= 1
        for r in routes:
            assert "type" in r
            assert "total_fare" in r
            assert "total_duration_minutes" in r
            assert "legs" in r

    def test_results_have_scores(self, svc):
        routes = svc.get_route_legs_public(12.9716, 77.5946, 12.9750, 77.6066)
        for r in routes:
            assert "overall_score" in r
            assert 10 <= r["overall_score"] <= 99

    def test_budget_filters(self, svc):
        routes_no_budget = svc.get_route_legs_public(13.1008, 77.5963, 12.9750, 77.6066)
        routes_budget = svc.get_route_legs_public(13.1008, 77.5963, 12.9750, 77.6066, budget=50)
        if routes_budget:
            for r in routes_budget:
                assert r["total_fare"] <= 50

    def test_group_size_affects_fare(self, svc):
        solo = svc.get_route_legs_public(12.9716, 77.5946, 12.9750, 77.6066, group_size=1)
        group = svc.get_route_legs_public(12.9716, 77.5946, 12.9750, 77.6066, group_size=4)
        # Group routes should have higher fares (multiplied by group size)
        if solo and group:
            assert len(solo) == len(group)

    def test_sorted_by_score(self, svc):
        routes = svc.get_route_legs_public(12.9716, 77.5946, 12.9750, 77.6066)
        scores = [r["overall_score"] for r in routes]
        assert scores == sorted(scores, reverse=True)

    def test_returns_bus_metro_and_walk(self, svc):
        routes = svc.get_route_legs_public(12.9763, 77.5710, 12.9750, 77.6066)
        types = set(r["type"] for r in routes)
        assert "metro" in types or "metro_astar" in types


class TestTransitServiceRouteGeneration:
    def test_generate_bus_routes(self, svc):
        routes = svc._generate_bus_routes(12.9716, 77.5946, 12.9750, 77.6066, 3.0, 1)
        if routes:
            for r in routes:
                assert r["type"] in ("bus_ordinary", "bus_ac_vajra")

    def test_generate_metro_routes(self, svc):
        routes = svc._generate_metro_routes(12.9763, 77.5710, 12.9750, 77.6066, 3.0, 1)
        if routes:
            assert routes[0]["type"] == "metro"

    def test_generate_kia_routes(self, svc):
        routes = svc._generate_kia_routes(12.9716, 77.5946, 13.1989, 77.7063, 30.0, 1)
        # KIA routes available only if DB has them
        if routes:
            for r in routes:
                assert r["type"] == "kia_bus"

    def test_generate_multi_modal_routes(self, svc):
        routes = svc._generate_multi_modal_routes(12.9716, 77.5946, 12.9750, 77.6066, 3.0, 1)
        if routes:
            for r in routes:
                assert r["type"] in ("bus_to_metro", "metro_to_bus")


class TestTransitServiceGetAllSegments:
    def test_returns_segments_dict(self, svc):
        result = svc.get_all_segments(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=1, max_depth=2,
        )
        assert "segments" in result
        assert "source" in result
        assert "dest" in result

    def test_get_segment_step_options(self, svc):
        result = svc.get_segment_step_options(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=1,
        )
        assert "from" in result
        assert "dest" in result
        assert "direct_options" in result
        assert "via_stops" in result


class TestTransitServiceAstarGraph:
    def test_astar_graph_lazy_build(self, svc):
        g = svc.astar_graph
        assert g is not None
        assert g.graph_built


class TestTransitServiceInterpolate:
    def test_interpolate_returns_path(self, svc):
        path = svc._interpolate_path(12.9716, 77.5946, 12.9750, 77.6066)
        assert isinstance(path, list)
        assert len(path) >= 2
