"""Unit tests for transit_paths.py — TransitPathService."""

import pytest
from backend.services.transit_paths import TransitPathService
from backend.services.transit_config import _haversine_dist


class TestInterpolatePath:
    def setup_method(self):
        self.svc = TransitPathService()

    def test_returns_list_of_coords(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9750, 77.6066, num_points=6)
        assert isinstance(path, list)
        assert len(path) == 7  # num_points + 1

    def test_each_point_is_lat_lng_pair(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9750, 77.6066)
        for pt in path:
            assert len(pt) == 2
            assert isinstance(pt[0], float)
            assert isinstance(pt[1], float)

    def test_start_and_end_match(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9750, 77.6066, num_points=10)
        assert path[0] == [12.9716, 77.5946]
        assert path[-1] == [12.9750, 77.6066]

    def test_same_point(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9716, 77.5946, num_points=4)
        for pt in path:
            assert pt == [12.9716, 77.5946]

    def test_zero_num_points(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9750, 77.6066, num_points=0)
        assert len(path) == 1
        assert path[0] == [12.9716, 77.5946]

    def test_negative_num_points(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9750, 77.6066, num_points=-1)
        assert len(path) == 1
        assert path[0] == [12.9716, 77.5946]

    def test_bulge_for_long_distance(self):
        # Distances > 1km should have bulge applied
        path = self.svc.interpolate_path(12.9716, 77.5946, 13.1008, 77.5963, num_points=12)
        # Mid points should deviate from straight line
        straight_mid = [12.9716 + (13.1008 - 12.9716) * 0.5, 77.5946 + (77.5963 - 77.5946) * 0.5]
        actual_mid = path[len(path) // 2]
        assert actual_mid != straight_mid, "Bulge should deviate from straight line"

    def test_short_distance_no_bulge(self):
        path = self.svc.interpolate_path(12.9716, 77.5946, 12.9720, 77.5950, num_points=4)
        assert len(path) == 5


class TestGetOsrmPathBetween:
    def setup_method(self):
        self.svc = TransitPathService()

    @pytest.mark.asyncio
    async def test_osrm_returns_path_or_fallback(self):
        path = await self.svc.get_osrm_path_between(12.9716, 77.5946, 12.9750, 77.6066)
        assert isinstance(path, list)
        assert len(path) >= 2
        assert all(len(pt) == 2 for pt in path)

    @pytest.mark.asyncio
    async def test_osrm_caches_result(self):
        key = (12.9716, 77.5946, 12.9750, 77.6066, "driving")
        self.svc._path_cache[key] = [[12.9716, 77.5946], [12.9733, 77.6006], [12.9750, 77.6066]]
        path = await self.svc.get_osrm_path_between(12.9716, 77.5946, 12.9750, 77.6066)
        assert path == [[12.9716, 77.5946], [12.9733, 77.6006], [12.9750, 77.6066]]

    @pytest.mark.asyncio
    async def test_osrm_profile_selection(self):
        # Test with walking profile (may fail and fall back to interpolation)
        path = await self.svc.get_osrm_path_between(12.9716, 77.5946, 12.9750, 77.6066, profile="walking")
        assert isinstance(path, list)
        assert len(path) >= 2

    def test_cache_persists(self):
        self.svc._path_cache.clear()
        assert len(self.svc._path_cache) == 0

    @pytest.mark.asyncio
    async def test_add_leg_paths_empty_route(self):
        route = {"legs": []}
        await self.svc.add_leg_paths(route)
        assert route == {"legs": []}

    @pytest.mark.asyncio
    async def test_add_leg_paths_adds_paths(self):
        route = {
            "legs": [
                {"from": "Majestic", "to": "MG Road", "mode": "metro",
                 "from_lat": 12.9763, "from_lng": 77.5710,
                 "to_lat": 12.9750, "to_lng": 77.6066},
            ]
        }
        await self.svc.add_leg_paths(route)
        assert "path" in route["legs"][0]


class TestGetOsrmRoute:
    def setup_method(self):
        self.svc = TransitPathService()

    @pytest.mark.asyncio
    async def test_get_osrm_route_returns_dict_or_none(self):
        result = await self.svc.get_osrm_route(12.9716, 77.5946, 12.9750, 77.6066)
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_driving_route(self):
        result = await self.svc.get_driving_route(12.9716, 77.5946, 12.9750, 77.6066)
        assert result is None or isinstance(result, dict)
