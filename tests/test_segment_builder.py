"""Integration tests for TripSegmentBuilder."""

from backend.services.transit_config import _haversine_dist, _safe


def test_haversine_dist_within_bengaluru():
    """Yelahanka NE Town to MG Road ~14km."""
    d = _safe(_haversine_dist(13.1008, 77.5963, 12.9750, 77.6066))
    assert 12 < d < 16  # ~14km


def test_haversine_dist_same_point():
    d = _safe(_haversine_dist(12.9716, 77.5946, 12.9716, 77.5946))
    assert d == 0.0


def test_haversine_dist_majestic_to_mg_road():
    """Majestic to MG Road ~2km on Green Line."""
    d = _safe(_haversine_dist(12.9763, 77.5710, 12.9750, 77.6066))
    assert 2.5 < d < 4.0


def test_haversine_dist_outside_bengaluru():
    """Bangalore to Mysore ~128km."""
    d = _safe(_haversine_dist(12.9716, 77.5946, 12.2958, 76.6394))
    assert 120 < d < 140


class TestGetSegmentStepOptions:
    """Lightweight integration — tests the builder's ability to return valid structure."""

    def test_returns_expected_keys(self, builder):
        result = builder.get_segment_step_options(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=1,
        )
        assert "from" in result
        assert "dest" in result
        assert "direct_options" in result
        assert "via_stops" in result

    def test_direct_options_populated(self, builder):
        result = builder.get_segment_step_options(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=1,
        )
        assert len(result["direct_options"]) >= 1
        walk_opts = [o for o in result["direct_options"] if o["mode"] == "walk"]
        assert len(walk_opts) >= 1  # ~3km, so walk should show

    def test_via_stops_is_list(self, builder):
        result = builder.get_segment_step_options(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=2,
        )
        assert isinstance(result["via_stops"], list)
        # Majestic is a hub with metro+bus nearby, so should have via stops
        if len(result["via_stops"]) > 0:
            vs = result["via_stops"][0]
            assert "stop" in vs
            assert "reach_options" in vs
            assert "from_stop_options" in vs


class TestGetAllSegments:


    def test_returns_segments_list(self, builder):
        result = builder.get_all_segments(
            12.9716, 77.5946, "Majestic",
            12.9750, 77.6066, "MG Road",
            group_size=1, max_depth=2,
        )
        assert "segments" in result
        assert len(result["segments"]) >= 1
        seg0 = result["segments"][0]
        assert seg0["segment_index"] == 0
        assert "direct_options" in seg0
        assert "destinations" in seg0

    def test_returns_source_dest(self, builder):
        result = builder.get_all_segments(
            13.1008, 77.5963, "Yelahanka NE Town",
            12.9750, 77.6066, "MG Road",
            group_size=1, max_depth=2,
        )
        assert result["source"]["name"] == "Yelahanka NE Town"
        assert result["dest"]["name"] == "MG Road"
