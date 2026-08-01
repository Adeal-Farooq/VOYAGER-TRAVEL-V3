"""LangGraph agent (PROMPT_5 §2.1).

VoyagerLangGraph: intent detection, parallel tool dispatch, synthesis. The
agent is a DATA GATHERER + EXPLAINER — it never decides routes (deterministic
A*/graph does) and never fabricates fares/timings/reviews/scores.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from ...agents.llm_agent import LLMAgent
from .state import AskInput, AskState, RouteContextInput, RouteContextState
from .tools.news_tools import NewsTool
from .tools.pricing_tools import PricingTool
from .tools.search_tools import GeoTool, SearchTool
from .tools.train_tools import TrainTool
from .tools.traffic_tools import TrafficTool
from .tools.weather_tools import WeatherTool

logger = logging.getLogger(__name__)


class VoyagerLangGraph:
    def __init__(self, llm: LLMAgent | None = None,
                 weather=None, traffic=None, news=None, pricing=None,
                 search=None, geo=None, train=None):
        self._llm = llm or LLMAgent()
        self._weather = weather or WeatherTool()
        self._traffic = traffic or TrafficTool()
        self._news = news or NewsTool()
        self._pricing = pricing or PricingTool()
        self._search = search or SearchTool()
        self._geo = geo or GeoTool()
        self._train = train or TrainTool()
        self._pool = ThreadPoolExecutor(max_workers=5)
        self._lock = threading.Lock()

    # ------------------------------------------------------ route-context graph
    def gather_route_context(self, src: dict, dst: dict, group_size: int = 1,
                             budget: float = 500.0, current_time: str | None = None,
                             place: dict | None = None) -> dict:
        """Parallel fan-out of live tools -> LiveContext dict.

        Best-effort: every gatherer may fail; failures never block the result.
        """
        state = RouteContextState(
            input=RouteContextInput(source=src, destination=dst, group_size=group_size,
                                    budget=budget, current_time=current_time))
        origin = (src.get("lat", 0.0), src.get("lng", 0.0))
        dest = (dst.get("lat", 0.0), dst.get("lng", 0.0))
        news_alerts = []

        jobs = {
            "weather": lambda: self._weather.run(dest[0], dest[1]),
            "traffic": lambda: self._traffic_with_news(origin, dest),
            "news": lambda: self._news.run(dest[0], dest[1], limit=10),
        }
        if group_size:
            jobs["prices"] = lambda: self._pricing.run(origin, dest, group_size)

        results = {}
        with self._pool as pool:
            futures = {pool.submit(fn): key for key, fn in jobs.items()}
            for fut in as_completed(futures):
                key = futures[fut]
                try:
                    results[key] = fut.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[langgraph] %s gather failed: %s", key, exc)
                    results[key] = None

        state.weather = results.get("weather")
        state.traffic = results.get("traffic")
        state.news = results.get("news") or []
        state.prices = results.get("prices") or []

        # destination POI reviews (only when a place is involved)
        if place and place.get("place_id"):
            try:
                state.reviews = self._reviews_for(place)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[langgraph] reviews gather failed: %s", exc)

        state.factors = self._derive_factors(state)
        return self._to_live_context(state)

    def _traffic_with_news(self, origin, dest):
        alerts = self._news.run(dest[0] if dest else 12.9716, dest[1] if dest else 77.5946,
                                keyword="traffic", limit=5)
        return self._traffic.run(origin, dest, news_alerts=alerts)

    # --------------------------------------------------------------- helpers
    def _reviews_for(self, place: dict):
        from ...data_schema import Place
        from .tools.review_tools import ReviewTool

        tool = ReviewTool()
        return tool.run(Place(**place))

    def _derive_factors(self, state: RouteContextState) -> dict:
        hour = datetime.now().hour
        if hour >= 22 or hour < 6:
            tod = "night"
        elif hour < 10:
            tod = "morning_rush"
        elif hour < 17:
            tod = "day"
        else:
            tod = "evening_rush"
        w = state.weather or {}
        traffic = state.traffic or {}
        return {
            "time_of_day": tod,
            "rain_next_hour": bool(w.get("rain_next_hour")),
            "traffic_label": traffic.get("label", "unknown"),
            "safety": "ok" if (tod != "night" or not (state.news)) else "caution",
        }

    def _to_live_context(self, state: RouteContextState) -> dict:
        return {
            "weather": state.weather or {"condition": "unavailable"},
            "traffic": state.traffic or {"label": "unavailable"},
            "news": state.news,
            "prices": state.prices,
            "reviews": state.reviews,
            "factors": state.factors,
            "errors": state.errors,
            "completed_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------ /ask synthesis
    def ask(self, message: str, lat: float | None = None, lng: float | None = None,
            context: dict | None = None) -> dict:
        """Full agent loop: gather + LLM synthesis. Structured JSON out."""
        state = AskState(input=AskInput(message=message, lat=lat, lng=lng, context=context))
        ctx = context or {}
        place = ctx.get("place")
        live = self.gather_route_context(
            src=ctx.get("source", {"lat": lat or 12.9716, "lng": lng or 77.5946, "name": ""}),
            dst=ctx.get("destination", {"lat": lat or 12.9716, "lng": lng or 77.5946, "name": ""}),
            group_size=ctx.get("group_size", 1),
            budget=ctx.get("budget", 500.0),
            place=place)
        synthesis = self._synthesize(message, live)
        return {"live_context": live, "synthesis": synthesis}

    def _synthesize(self, message: str, live: dict) -> dict:
        weather = live.get("weather", {})
        traffic = live.get("traffic", {})
        prices = live.get("prices", [])
        price_bits = [f"{p.get('provider')} {p.get('total')} {p.get('source')}" for p in prices[:3]]
        news_bits = [n.get("title") for n in live.get("news", [])[:3]]
        prompt = (
            f'User asks: "{message}".\n'
            f"Live context: weather={weather}, traffic={traffic}, "
            f"prices=[{', '.join(price_bits)}], "
            f"news={news_bits}.\n"
            'Rules: do NOT invent fares, timings, bus numbers, or scores. Use only the '
            'given data. Reply JSON {"answer": str, "factors": [str]}.'
        )
        res = self._llm.chat_json("You are VOYAGER's travel assistant. Be concise and factual.",
                                  prompt)
        if res is None:
            return {"answer": "Live data partially unavailable.", "factors": ["LLM unavailable"]}
        return {"answer": res.get("answer", ""), "factors": res.get("factors", [])}
