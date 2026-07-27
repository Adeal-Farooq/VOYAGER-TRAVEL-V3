"""pytest configuration for VOYAGER."""

import pytest
from backend.core.database import db


@pytest.fixture(scope="session")
def _init_db():
    """Initialize the TransitDatabase singleton once per test session."""
    if not db._initialized:
        db.initialize()
    return db


@pytest.fixture(scope="session")
def builder(_init_db):
    """Shared TripSegmentBuilder instance (session scope)."""
    from backend.services.transit_paths import TransitPathService
    from backend.services.segment_builder import TripSegmentBuilder
    from backend.services.transit_config import _haversine_dist
    instance = TripSegmentBuilder(
        haversine_fn=_haversine_dist,
        interpolate_path_fn=lambda *a, **kw: [[a[0], a[1]], [a[2], a[3]]],
        path_service=TransitPathService(),
        get_bus_route_nums_fn=lambda bs, fs: bs.get("routes", [])[:3],
    )
    return instance
