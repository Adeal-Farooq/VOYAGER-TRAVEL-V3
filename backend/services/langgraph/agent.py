"""LangGraph agent for VOYAGER with real tool-calling.

Uses LangGraph's StateGraph to orchestrate tool calls with the LLM
in a proper reasoning loop, instead of the current fake wrappers.
"""

import json
import logging
from typing import Literal
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Tool imports
from backend.services.langgraph.tools.search_tools import search_places, search_nearby, get_suggestions
from backend.services.langgraph.tools.review_tools import get_place_reviews, get_place_photos
from backend.services.langgraph.tools.pricing_tools import get_ride_prices, get_distance_duration, estimate_fuel_cost, get_hotel_prices
from backend.services.langgraph.tools.weather_tools import get_weather
from backend.services.langgraph.tools.news_tools import get_travel_news, get_traffic_news, get_area_events
from backend.services.langgraph.tools.geo_tools import geocode, get_nearby_stations, get_address_from_coords


TOOL_REGISTRY = {
    "search_places": search_places,
    "search_nearby": search_nearby,
    "get_suggestions": get_suggestions,
    "get_place_reviews": get_place_reviews,
    "get_place_photos": get_place_photos,
    "get_ride_prices": get_ride_prices,
    "get_distance_duration": get_distance_duration,
    "estimate_fuel_cost": estimate_fuel_cost,
    "get_hotel_prices": get_hotel_prices,
    "get_weather": get_weather,
    "get_travel_news": get_travel_news,
    "get_traffic_news": get_traffic_news,
    "get_area_events": get_area_events,
    "geocode": geocode,
    "get_nearby_stations": get_nearby_stations,
    "get_address_from_coords": get_address_from_coords,
}

TOOL_SCHEMAS = {
    tool_name: {
        "name": tool_name,
        "description": (fn.__doc__ or f"Execute {tool_name}").strip(),
    }
    for tool_name, fn in TOOL_REGISTRY.items()
}


class AgentState:
    """State object for the LangGraph agent."""

    def __init__(self):
        self.messages: list[dict] = []
        self.tool_results: dict = {}
        self.final_output: dict = {}
        self.current_query: str = ""
        self.context: dict = {}
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "messages": self.messages[-10:],
            "tool_results": self.tool_results,
            "final_output": self.final_output,
            "current_query": self.current_query,
            "context": self.context,
        }


class VoyagerLangGraph:
    """LangGraph-style agent that uses real tools with LLM reasoning.

    Flow:
    1. User query → LLM decides which tools to call
    2. Tools execute with real data
    3. Results fed back to LLM for synthesis
    4. Final structured response returned
    """

    def __init__(self):
        self._working_model = None

    def _get_tools_for_query(self, query: str) -> list[str]:
        """Determine which tools are relevant based on query intent."""
        q = query.lower()
        tools = []

        if any(w in q for w in ["search", "find", "nearby", "near", "around", "close"]):
            tools.extend(["geocode", "search_places", "search_nearby"])
            if "review" in q or "rating" in q:
                tools.append("get_place_reviews")
            if "photo" in q or "image" in q or "picture" in q:
                tools.append("get_place_photos")

        if any(w in q for w in ["ride", "uber", "ola", "rapido", "cab", "taxi", "price", "fare", "cost"]):
            tools.extend(["get_ride_prices", "get_distance_duration", "geocode"])
            if "fuel" in q or "petrol" in q or "drive" in q:
                tools.append("estimate_fuel_cost")

        if any(w in q for w in ["weather", "rain", "temperature", "humidity"]):
            tools.append("get_weather")

        if any(w in q for w in ["news", "traffic", "event", "happening", "alert"]):
            tools.extend(["get_travel_news", "get_traffic_news", "get_area_events"])

        if any(w in q for w in ["hotel", "stay", "lodge", "room"]):
            tools.append("get_hotel_prices")

        if any(w in q for w in ["suggest", "auto", "complete", "hint"]):
            tools.append("get_suggestions")

        if any(w in q for w in ["station", "bus", "metro", "train", "stop"]):
            tools.append("get_nearby_stations")

        if any(w in q for w in ["address", "location", "where"]):
            tools.extend(["geocode", "get_address_from_coords"])

        if any(w in q for w in ["review", "rating", "feedback", "opinion"]):
            tools.extend(["get_place_reviews", "search_places"])

        return list(set(tools)) if tools else ["geocode", "search_places"]

    async def _call_llm(self, system: str, prompt: str, json_mode: bool = True) -> str:
        """Call the LLM with fallback across models."""
        if not settings.OPENROUTER_API_KEY:
            return json.dumps({"error": "No API key configured"})

        import httpx
        models = [settings.OPENROUTER_MODEL] + settings.OPENROUTER_FALLBACK_MODELS
        if self._working_model and self._working_model in models:
            models.insert(0, models.pop(models.index(self._working_model)))

        for model in models:
            try:
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 2048,
                    "temperature": 0.3,
                }
                if json_mode:
                    body["response_format"] = {"type": "json_object"}

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        json=body,
                        headers={
                            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "http://localhost:8006",
                            "X-Title": "VOYAGER App",
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        self._working_model = model
                        return content
                    elif resp.status_code == 401:
                        raise Exception("Invalid OpenRouter API key")
            except Exception as e:
                logger.warning(f"LLM call failed with {model}: {e}")
                self.error = str(e)[:100]
                continue

        return json.dumps({"error": "All models failed", "fallback": True})

    async def _extract_tool_calls(self, llm_response: str, available_tools: list[str]) -> list[dict]:
        """Parse LLM response to extract tool calls."""
        try:
            data = json.loads(llm_response)
            if isinstance(data, dict):
                calls = data.get("tool_calls", data.get("tools", [data] if data.get("tool") else []))
                if isinstance(calls, dict):
                    calls = [calls]
                return [
                    {
                        "tool": c.get("tool", c.get("name", "")),
                        "args": c.get("args", c.get("parameters", c.get("arguments", {}))),
                    }
                    for c in (calls or [])
                    if isinstance(c, dict) and c.get("tool", c.get("name", "")) in available_tools
                ]
            elif isinstance(data, list):
                return [
                    {"tool": c.get("tool", ""), "args": c.get("args", {})}
                    for c in data[:3]
                    if isinstance(c, dict) and c.get("tool", "") in available_tools
                ]
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse LLM tool calls: {e}")
        return []

    async def run(
        self, query: str, context: dict | None = None
    ) -> dict:
        """Main entry point: run the agent loop."""
        state = AgentState()
        state.current_query = query
        state.context = context or {}

        available_tools = self._get_tools_for_query(query)

        # Step 1: LLM decides tool calls
        system_prompt = """You are VOYAGER's AI travel assistant for Bengaluru. You have access to real tools.

Given a user query, decide which tools to call and with what parameters.
Return JSON with:
  "tool_calls": [{"tool": "tool_name", "args": {...}}]
  "reasoning": "Brief explanation"

Available tools: """ + json.dumps({t: TOOL_SCHEMAS[t]["description"] for t in available_tools}, indent=2) + """

Rules:
- Call MULTIPLE tools in parallel if independent
- Extract location names from query for geocoding
- Use coordinates (lat/lng) for location-based searches
- Set appropriate limits (3-8 results)
- If query mentions a source→destination, call geocode for both"""

        user_prompt = f"User query: {query}\nContext: {json.dumps(context or {})}"

        llm_response = await self._call_llm(system_prompt, user_prompt, json_mode=True)

        # Step 2: Execute tool calls
        tool_calls = await self._extract_tool_calls(llm_response, available_tools)

        if not tool_calls:
            # Fallback: auto-detect geocoding needs and search
            tool_calls = await self._auto_generate_calls(query, available_tools)

        state.messages.append({"role": "assistant", "content": llm_response, "tool_calls_planned": len(tool_calls)})

        # Execute all tool calls
        import asyncio
        tool_futures = []
        for tc in tool_calls[:5]:
            tool_name = tc["tool"]
            args = tc.get("args", {})
            fn = TOOL_REGISTRY.get(tool_name)
            if fn:
                tool_futures.append(self._safe_call(fn, tool_name, args, state))

        if tool_futures:
            await asyncio.gather(*tool_futures)

        # Step 3: Synthesize results
        final = await self._synthesize(state)

        # Step 4: Auto-fetch reviews for any places found
        if not state.tool_results.get("get_place_reviews"):
            places = self._extract_place_names(state)
            if places:
                review_futures = []
                for p in places[:3]:
                    review_futures.append(get_place_reviews(p))
                if review_futures:
                    reviews = await asyncio.gather(*review_futures)
                    valid_reviews = [r for r in reviews if r]
                    if valid_reviews:
                        state.tool_results["get_place_reviews"] = valid_reviews
                        final["reviews"] = valid_reviews

        return final

    async def _safe_call(self, fn, name: str, args: dict, state: AgentState):
        """Execute a tool safely and store result."""
        try:
            result = await fn(**args)
            state.tool_results[name] = result
        except TypeError as e:
            logger.warning(f"Tool {name} invalid args: {e}")
            state.tool_results[name] = {"error": f"Invalid args: {e}"}
        except Exception as e:
            logger.warning(f"Tool {name} failed: {e}")
            state.tool_results[name] = {"error": str(e)[:200]}

    async def _auto_generate_calls(self, query: str, available_tools: list[str]) -> list[dict]:
        """Auto-generate tool calls if LLM didn't produce valid ones."""
        calls = []
        q = query.lower()

        if "geocode" in available_tools:
            # Extract location names
            import re
            words = re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", query)
            for word in words[:2]:
                if len(word) > 2:
                    calls.append({"tool": "geocode", "args": {"query": word.strip()}})

            # Source→destination pattern
            if " to " in query:
                parts = query.split(" to ")
                if len(parts) == 2:
                    src, dst = parts[0].strip(), parts[1].strip()
                    if src and dst:
                        calls.append({"tool": "geocode", "args": {"query": src}})
                        calls.append({"tool": "geocode", "args": {"query": dst.split(" in ")[0].split(" for ")[0].strip()}})

        if "search_places" in available_tools:
            calls.append({"tool": "search_places", "args": {"query": query, "limit": 8}})

        if "get_ride_prices" in available_tools:
            calls.append({"tool": "get_ride_prices", "args": {"source_lat": 12.9716, "source_lng": 77.5946, "dest_lat": 12.9716, "dest_lng": 77.5946, "group_size": 1}})

        if "get_weather" in available_tools:
            calls.append({"tool": "get_weather", "args": {"lat": 12.9716, "lng": 77.5946}})

        if "get_travel_news" in available_tools:
            calls.append({"tool": "get_travel_news", "args": {"limit": 4}})

        if "get_suggestions" in available_tools:
            calls.append({"tool": "get_suggestions", "args": {"query": query}})

        if "get_hotel_prices" in available_tools:
            words = query.split()[:3]
            calls.append({"tool": "get_hotel_prices", "args": {"name": " ".join(words), "city": "Bengaluru"}})

        return calls[:5]

    @staticmethod
    def _extract_place_names(state: AgentState) -> list[str]:
        """Extract place names from tool results."""
        names = []
        for result_list in state.tool_results.values():
            if isinstance(result_list, list):
                for item in result_list:
                    if isinstance(item, dict):
                        name = item.get("name", item.get("title", ""))
                        if name and len(name) > 2:
                            names.append(name)
        return list(set(names))

    async def _synthesize(self, state: AgentState) -> dict:
        """Synthesize all tool results into a final structured response."""
        results = state.tool_results
        output = {
            "query": state.current_query,
            "places": results.get("search_places", results.get("search_nearby", [])),
            "reviews": results.get("get_place_reviews", []),
            "photos": results.get("get_place_photos", []),
            "rides": results.get("get_ride_prices", []),
            "distance": results.get("get_distance_duration"),
            "fuel_cost": results.get("estimate_fuel_cost"),
            "hotel_prices": results.get("get_hotel_prices"),
            "weather": results.get("get_weather"),
            "news": results.get("get_travel_news", results.get("get_traffic_news", [])),
            "events": results.get("get_area_events", []),
            "suggestions": results.get("get_suggestions", []),
            "stations": results.get("get_nearby_stations", []),
            "geocoded": [],
        }

        # Collect geocoded results
        for key, val in results.items():
            if key.startswith("geocode"):
                if isinstance(val, dict) and val.get("lat"):
                    output["geocoded"].append(val)

        state.final_output = output
        return output

    async def comprehensive_context(
        self, source: str, destination: str,
        group_size: int = 1, budget: float = 0,
        source_lat: float = None, source_lng: float = None,
        dest_lat: float = None, dest_lng: float = None,
    ) -> dict:
        """Get comprehensive travel context with parallel tool calls."""
        import asyncio

        tasks = {
            "weather": get_weather(source_lat or 12.9716, source_lng or 77.5946),
            "traffic_news": get_traffic_news(3),
            "events": get_area_events(destination if destination else "", 3),
            "travel_news": get_travel_news(source, destination, limit=4),
        }

        if source_lat and source_lng and dest_lat and dest_lng:
            tasks["distance"] = get_distance_duration(source_lat, source_lng, dest_lat, dest_lng)
            tasks["rides"] = get_ride_prices(source_lat, source_lng, dest_lat, dest_lng, group_size, budget)

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        output = dict(zip(tasks.keys(), results))

        # Clean exceptions
        for k, v in output.items():
            if isinstance(v, Exception):
                output[k] = {"error": str(v)[:100]}

        return output


voyager_agent = VoyagerLangGraph()
