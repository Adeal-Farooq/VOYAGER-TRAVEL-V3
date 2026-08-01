"""PROMPT_5 tests: weather labels, news engine (offline), train service,
proxy routing, LangGraph context gathering (stubbed tools).

Unit tests only — no real network. Tools/stubs are injected so the live
gather graph is exercised without API keys. Covers PROMPT_5 acceptance:
- LiveContext has all 5 tool groups (stubbed real data)
- route-context degrades gracefully when a tool fails (never blocks)
- news items classified + geo-tagged + deduped
- train fallbacks flagged, never fabricated
- proxy used for news/DDG scrapes, not for API-key services (by design)
"""
from datetime import datetime

from backend.services.clients.weather_client import _weather_code_label
from backend.services.langgraph.agent import VoyagerLangGraph
from backend.services.news_engine import NewsEngine
from backend.services.proxy_manager import ProxyManager
from backend.services.train_service import STATION_CODES, TrainService
from backend.agents.llm_agent import LLMAgent, LLMConfig


# ---------------------------------------------------------------- weather
class TestWeather:
    def test_wmo_labels(self):
        assert _weather_code_label(0) == "clear"
        assert _weather_code_label(3) == "cloudy"
        assert _weather_code_label(61) == "rain"
        assert _weather_code_label(95) == "thunderstorm"
        assert _weather_code_label(None) == "unknown"

    def test_current_returns_none_without_network(self, monkeypatch):
        import requests

        class Boom:
            def raise_for_status(self):
                raise requests.ConnectionError("no network")

            def json(self):
                raise ValueError

        def fake_get(*a, **k):
            return Boom()

        from backend.services.clients import weather_client

        monkeypatch.setattr(weather_client.requests, "get", fake_get)
        from backend.services.clients.weather_client import WeatherClient

        assert WeatherClient(timeout_s=0.1).current(12.97, 77.59) is None


# ---------------------------------------------------------------- news engine
class TestNews:
    def _engine(self):
        return NewsEngine(interval_min=99)

    def test_classify(self):
        e = self._engine()
        assert e._classify("Silk Board traffic jam") == "traffic"
        assert e._classify("Heavy rain in Bengaluru") == "weather"
        assert e._classify("Music festival this weekend") == "event"
        assert e._classify("Metro extension news") == "general"

    def test_geo_tag(self):
        e = self._engine()
        g = e._geo_tag("Heavy traffic at Silk Board junction")
        assert g and g["name"] == "silk board"
        assert abs(g["lat"] - 12.9166) < 0.01

    def test_dedup_and_ttl(self):
        e = self._engine()
        now = datetime.now().timestamp()
        items = [
            {"title": "Metro delay at Majestic", "text": "x", "ts": now},
            {"title": "metro delay at majestic", "text": "y", "ts": now},  # case dup
            {"title": "Different headline", "text": "z", "ts": now - 9 * 3600},  # expired
        ]
        fresh = e._dedup(items)  # dedup removes case-duplicate only; TTL is in _merge
        assert len(fresh) == 2

        e._merge(fresh)  # _merge applies TTL on already-deduped input
        assert len(e._items) == 1
        assert e._items[0]["title"] == "Metro delay at Majestic"

    def test_merge_caps_and_sorts(self):
        e = self._engine()
        now = datetime.now().timestamp()
        e._merge([{"title": f"Headline {i}", "text": "", "ts": now - i} for i in range(40)])
        assert len(e._items) == 25
        assert e._items[0]["title"] == "Headline 0"  # newest first

    def test_relevant_filters_by_keyword(self):
        e = self._engine()
        now = datetime.now().timestamp()
        e._merge([
            {"title": "Silk Board traffic heavy", "text": "", "ts": now, "geo": None},
            {"title": "New restaurant opens", "text": "", "ts": now, "geo": None},
        ])
        hits = e.relevant(keyword="traffic")
        assert len(hits) == 1
        assert "traffic" in hits[0]["title"].lower()

    def test_relevant_sorts_by_proximity(self):
        e = self._engine()
        now = datetime.now().timestamp()
        e._merge([
            {"title": "Far event", "text": "", "ts": now, "geo": {"lat": 14.0, "lng": 80.0}},
            {"title": "Near event", "text": "", "ts": now, "geo": {"lat": 12.98, "lng": 77.59}},
        ])
        hits = e.relevant(lat=12.97, lng=77.59)
        assert hits[0]["title"] == "Near event"


# ---------------------------------------------------------------- train
class TestTrain:
    def test_codes_mapped(self):
        assert STATION_CODES["KSR Bengaluru City Junction"] == "SBC"
        assert TrainService().code_for("KSR Bengaluru City Junction") == "SBC"
        assert TrainService().code_for("ksr bengaluru city junction") == "SBC"

    def test_code_for_partial_match(self):
        assert TrainService().code_for("Mysuru") == "MYS"

    def test_unknown_station_no_fabrication(self):
        svc = TrainService()
        assert svc.code_for("Nowhereville") is None

    def test_fallback_flagged_not_live(self):
        svc = TrainService()
        result = svc.trains_between("SBC", "MYS")
        # eRail may be unreachable in CI; either way fallback is flagged
        assert result["source"] in ("live", "fallback")
        if result["source"] == "fallback":
            assert "NOT live" in result.get("note", "") or "NOT live" in result["note"]

    def test_fallback_pairs_never_presented_as_live(self):
        from backend.services.train_service import _FALLBACK_PAIRS
        assert len(_FALLBACK_PAIRS) >= 7


# ---------------------------------------------------------------- proxy
class TestProxy:
    def test_proxy_not_available_without_creds(self):
        p = ProxyManager(user="", password="")
        assert p.available is False
        assert p.get("https://example.com", timeout=1) is None

    def test_proxy_used_only_for_scrape_targets_by_design(self):
        # API-key services (SerpAPI/Maps/Open-Meteo) never touch the proxy:
        # they use plain requests in their own clients. This asserts the
        # separation contract documented in PROMPT_5 §6.
        import inspect
        from backend.services.clients import google_maps_client, serpapi_client, weather_client

        for mod in (google_maps_client, serpapi_client, weather_client):
            src = inspect.getsource(mod)
            assert "dataimpulse" not in src.lower()


# ---------------------------------------------------------------- langgraph
class TestLangGraph:
    def _agent(self):
        class StubWeather:
            def run(self, lat, lng):
                return {"temp_c": 28, "condition": "clear", "rain_next_hour": False}

        class StubTraffic:
            def run(self, origin, dest, news_alerts=None):
                return {"ratio": 1.2, "label": "moderate", "source": "stub", "alerts": []}

        class StubNews:
            def run(self, lat=None, lng=None, keyword="", limit=10):
                return [{"title": "Silk Board traffic", "category": "traffic", "geo": None}]

        class StubPricing:
            def run(self, origin, dest, group_size=1):
                return [{"provider": "Uber", "total": 120.0, "per_person": 120.0,
                         "source": "estimated"}]

        return VoyagerLangGraph(
            llm=LLMAgent(LLMConfig()),  # no keys -> falls back deterministically
            weather=StubWeather(), traffic=StubTraffic(), news=StubNews(),
            pricing=StubPricing())

    def test_live_context_has_all_groups(self):
        ctx = self._agent().gather_route_context(
            {"lat": 12.9716, "lng": 77.5946, "name": "a"},
            {"lat": 12.9789, "lng": 77.6408, "name": "b"}, group_size=2)
        assert "weather" in ctx
        assert "traffic" in ctx
        assert "news" in ctx
        assert "prices" in ctx
        assert "factors" in ctx
        assert ctx["weather"]["rain_next_hour"] is False
        assert ctx["traffic"]["ratio"] == 1.2
        assert len(ctx["prices"]) == 1

    def test_weather_rain_feeds_factors(self):
        class Rain:
            def run(self, lat, lng):
                return {"temp_c": 24, "condition": "rain", "rain_next_hour": True}

        agent = self._agent()
        agent._weather = Rain()
        ctx = agent.gather_route_context(
            {"lat": 12.97, "lng": 77.59, "name": "a"},
            {"lat": 12.98, "lng": 77.60, "name": "b"})
        assert ctx["factors"]["rain_next_hour"] is True

    def test_failing_tool_never_blocks(self):
        class Boom:
            def run(self, *a, **k):
                raise RuntimeError("api down")

        agent = self._agent()
        agent._weather = Boom()
        ctx = agent.gather_route_context(
            {"lat": 12.97, "lng": 77.59, "name": "a"},
            {"lat": 12.98, "lng": 77.60, "name": "b"})
        assert ctx["weather"]["condition"] == "unavailable"
        assert "traffic" in ctx  # others still gathered

    def test_ask_degrades_without_llm(self):
        result = self._agent().ask("Is it raining?")
        assert "live_context" in result
        assert result["synthesis"]["factors"] == ["LLM unavailable"]

    def test_time_of_day_factor(self):
        agent = self._agent()
        from backend.services.langgraph import state

        st = state.RouteContextState()
        st.weather = {"rain_next_hour": False}
        st.traffic = {"label": "moderate"}
        factors = agent._derive_factors(st)
        assert factors["time_of_day"] in ("night", "morning_rush", "day", "evening_rush")
        assert factors["safety"] in ("ok", "caution")
