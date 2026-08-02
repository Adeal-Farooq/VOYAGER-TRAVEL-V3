"""Shared fixtures (PROMPT_7 §3.1/3.3).

Real, reusable data-layer fixtures (GTFS cache, transit DB) shared by the
integration suites. External services (GraphHopper, SerpAPI, Google Maps,
Open-Meteo, Reddit, eRail) are STUBBED by default — set LIVE_API=1 or
GH_LIVE=1 to opt into real network calls (never required for green tests).
"""
import os

import pytest

from backend.services.database import TransitDatabase
from backend.services.gtfs_service import GTFSService
from backend.services.segment_builder import SegmentBuilder


def _live_api() -> bool:
    return os.environ.get("LIVE_API", "0") == "1"


@pytest.fixture(scope="module")
def gtfs():
    g = GTFSService()
    g.load()
    return g


@pytest.fixture(scope="module")
def db():
    return TransitDatabase()


@pytest.fixture(scope="module")
def builder(gtfs, db):
    return SegmentBuilder(gtfs, db, gh=None)  # no docker dependency by default


class _GraphHopperStub:
    """Stub GraphHopper: straight-line geometry + flag (PROMPT_7 §3.3)."""

    def route(self, profile: str, lat1, lng1, lat2, lng2):
        return _RouteStub(lat1, lng1, lat2, lng2)


class _RouteStub:
    def __init__(self, lat1, lng1, lat2, lng2):
        self.geometry = [(lat1, lng1), (lat2, lng2)]
        # rough duration so chained segments still progress
        self.duration_s = int(_haversine_m(lat1, lng1, lat2, lng2) / 1.4)


def _haversine_m(lat1, lng1, lat2, lng2):
    import math

    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@pytest.fixture(scope="module")
def gh_stub():
    return _GraphHopperStub()


class _SerpapiStub:
    """Stub SerpAPI (search/details/directions) with tiny honest fixtures."""

    def __init__(self):
        self.place_id = "stub_place_1"

    def search_place(self, query, lat=None, lng=None):
        return {"place_id": self.place_id, "title": query}

    def place_details(self, place_id):
        return {
            "place_results": {
                "rating": 4.2,
                "reviews": 37,
                "user_reviews": {
                    "most_relevant": [
                        {"username": "a", "description": "Nice clean place"},
                        {"username": "b", "description": "Good food"},
                    ]
                },
            }
        }

    def directions(self, origin, dest):
        return {"duration_s": 1200, "ride_options": []}


@pytest.fixture(scope="module")
def serpapi_stub():
    return _SerpapiStub()


class _WeatherStub:
    def current(self, lat, lng):
        return {"condition": "clear", "temperature_c": 27.0, "rain_next_hour": False}


@pytest.fixture(scope="module")
def weather_stub():
    return _WeatherStub()


@pytest.fixture
def live_api():
    """Skip a test unless LIVE_API=1 (opt-in real network integration)."""
    if not _live_api():
        pytest.skip("set LIVE_API=1 to run real network tests")
    return True
