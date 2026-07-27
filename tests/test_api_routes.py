"""Integration tests for offline-friendly API endpoints only.
Skips tests that require OSRM, LLM, or external services."""

import pytest
from fastapi.testclient import TestClient
from backend.core.database import db
from backend.main import app

if not db._initialized:
    db.initialize()

client = TestClient(app)


class TestLightEndpoints:
    def test_plan_invalid_params_returns_422(self):
        resp = client.post("/api/routes/plan", json={"source_lat": "invalid"})
        assert resp.status_code == 422

    def test_metro_stations(self):
        resp = client.get("/api/routes/metro-stations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "stations" in data

    def test_metro_stations_filtered_by_line(self):
        resp = client.get("/api/routes/metro-stations?line=Purple")
        assert resp.status_code == 200
        data = resp.json()
        assert "stations" in data
        assert isinstance(data["stations"], list)

    def test_bus_stops(self):
        resp = client.get("/api/routes/bus-stops")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "stops" in data

    def test_transit_fares(self):
        resp = client.get("/api/routes/transit-fares")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_kia_routes(self):
        resp = client.get("/api/routes/kia-routes")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_live_prices(self):
        resp = client.get("/api/routes/live-prices?source=Majestic&dest=MG+Road&mode=cab")
        assert resp.status_code in (200, 404)

    def test_root(self):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "app" in data
        assert "status" in data
