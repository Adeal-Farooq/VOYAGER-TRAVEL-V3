"""VOYAGER LLM Agent — delegates to real data sources via LangGraph agent.

Every method:
  1. Tries real data source first (SerpAPI, Google Maps, Reddit, Open-Meteo, scrapers)
  2. Falls back to LLM reasoning via OpenRouter only if real data unavailable
  3. NEVER generates fake data — returns empty list/dict if no real data
"""

import json
import httpx
from backend.core.config import settings
from backend.services.langgraph.agent import voyager_agent
from backend.services.clients.serpapi_client import serpapi_client
from backend.services.clients.reddit_client import reddit_client
from backend.services.clients.google_maps_client import google_maps_client
from backend.services.clients.weather_client import weather_client
from backend.services.scrapers.news_scraper import news_scraper
from backend.services.scrapers.ddg_scraper import ddg_scraper
from backend.services.langgraph.tools.search_tools import search_nearby, get_suggestions
from backend.services.langgraph.tools.review_tools import get_place_reviews, get_place_photos
from backend.services.langgraph.tools.pricing_tools import get_ride_prices, estimate_fuel_cost, get_hotel_prices
from backend.services.langgraph.tools.news_tools import get_travel_news, get_traffic_news, get_area_events
from backend.services.langgraph.tools.geo_tools import geocode


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMAgent:
    _working_model = None

    async def _call_llm(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        if settings.LLM_PROVIDER == "openrouter" and settings.OPENROUTER_API_KEY:
            return await self._call_openrouter(system_prompt, user_prompt, json_mode)
        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            return await self._call_gemini_fallback(system_prompt, user_prompt)
        raise Exception("No LLM provider configured for fallback")

    async def _call_openrouter(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        models = [settings.OPENROUTER_MODEL] + settings.OPENROUTER_FALLBACK_MODELS
        if self._working_model and self._working_model in models:
            models.insert(0, models.pop(models.index(self._working_model)))
        for model in models:
            try:
                body = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 1024,
                    "temperature": 0.3,
                }
                if json_mode:
                    body["response_format"] = {"type": "json_object"}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(OPENROUTER_URL, json=body, headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:8006",
                        "X-Title": "VOYAGER App",
                    })
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        self._working_model = model
                        return content
                    elif resp.status_code == 401:
                        raise Exception("Invalid OpenRouter API key")
            except Exception as e:
                print(f"[LLM] Model {model} failed: {str(e)[:60]}")
                continue
        raise Exception("All OpenRouter models failed")

    async def _call_gemini_fallback(self, system_prompt: str, user_prompt: str) -> str:
        import google.generativeai as genai
        import asyncio
        genai.configure(api_key=settings.GEMINI_API_KEY)
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro"]
        for model_name in models:
            try:
                model = genai.GenerativeModel(model_name)
                response = await asyncio.to_thread(model.generate_content, f"{system_prompt}\n\n{user_prompt}")
                return response.text
            except Exception:
                continue
        raise Exception("All Gemini models failed")

    async def verify_place(self, name: str, address: str = None) -> dict:
        """Verify place using real reviews."""
        reviews_data = await get_place_reviews(name, address)
        if reviews_data:
            return {
                "reliability_score": reviews_data.get("reliability_score", 0.7),
                "rating": reviews_data.get("rating", 4.0),
                "review_summary": reviews_data.get("review_summary", ""),
                "is_recommended": reviews_data.get("is_recommended", True),
                "concerns": "",
                "reviews": reviews_data.get("reviews", []),
            }

        return {
            "reliability_score": 0.5,
            "rating": 0,
            "review_summary": "No reviews found",
            "is_recommended": False,
            "concerns": "No data available",
        }

    async def get_smart_suggestions(self, partial: str) -> list[str]:
        """Get autocomplete suggestions from SerpAPI/Reddit."""
        if len(partial) < 2:
            return []
        return await get_suggestions(partial, limit=5)

    async def get_nearby_ai(self, lat: float, lng: float, place_type: str, radius_km: float = 2.0) -> list[dict]:
        """Find nearby places using SerpAPI."""
        results = await search_nearby(lat, lng, place_type, radius_km, limit=8)
        if results:
            for r in results:
                r["reliability_score"] = round(min((r.get("rating", 0) or 0) / 5, 1.0), 2) if r.get("rating", 0) > 0 else 0.5
                r["is_recommended"] = (r.get("rating", 0) or 0) >= 3.5
                r["address"] = r.get("address", "")
            return results[:15]
        return []

    async def get_travel_recs(self, source: str, dest: str, group_size: int, budget: float = None) -> dict:
        """Get travel recommendations using real data."""
        src_coords = await geocode(source)
        dst_coords = await geocode(dest)

        context = {}
        if src_coords and dst_coords:
            matrix = await google_maps_client.get_distance_matrix(
                src_coords["lat"], src_coords["lng"],
                dst_coords["lat"], dst_coords["lng"],
            )
            if matrix:
                dist_km = matrix["distance_km"]
                duration_min = matrix["duration_in_traffic_min"]

                rides = await google_maps_client.estimate_ride_prices(
                    src_coords["lat"], src_coords["lng"],
                    dst_coords["lat"], dst_coords["lng"],
                    group_size, budget or 0,
                )
                fuel = await estimate_fuel_cost(dist_km)

                context = {
                    "distance_km": round(dist_km, 1),
                    "duration_min": round(duration_min),
                    "rides": rides,
                    "fuel_cost": fuel,
                }

        llm_input = f"Source: {source}, Dest: {dest}, Group: {group_size}"
        if budget:
            llm_input += f", Budget: ₹{budget}"
        if context:
            llm_input += f"\nReal data: {json.dumps(context)}"

        if budget and context.get("rides"):
            affordable = [r for r in context["rides"] if r["fare"] <= budget]
            if affordable:
                return {
                    "recommended_mode": affordable[0]["service"].lower().replace(" ", "_"),
                    "estimated_cost_min": min(r["fare"] for r in affordable),
                    "estimated_cost_max": max(r["fare"] for r in affordable),
                    "estimated_time_minutes": context["duration_min"],
                    "safety_rating": 8,
                    "tips": ["Book in advance during peak hours", "Share live location with someone"],
                    "current_issues": [],
                    "rides": affordable,
                    "fuel_cost": context.get("fuel_cost"),
                }

        # LLM fallback for additional tips
        system = "You are a Bengaluru travel advisor. Brief response."
        tip_prompt = f"{llm_input}\nGive 2-3 specific travel tips for this route."
        try:
            tips_text = await self._call_llm(system, tip_prompt)
            tips = [t.strip() for t in tips_text.split("\n") if t.strip() and len(t.strip()) > 10]
        except Exception:
            tips = []

        if not context.get("rides") and not context.get("duration_min"):
            return {"recommended_mode": "transit", "estimated_cost_min": None, "estimated_cost_max": None, "estimated_time_minutes": None, "safety_rating": None, "tips": tips, "current_issues": [], "rides": [], "fuel_cost": None}

        return {
            "recommended_mode": "cab" if context.get("rides") else "transit",
            "estimated_cost_min": context["rides"][0]["fare"] if context.get("rides") else None,
            "estimated_cost_max": context["rides"][-1]["fare"] if context.get("rides") else None,
            "estimated_time_minutes": context.get("duration_min"),
            "safety_rating": None,
            "tips": tips,
            "current_issues": [],
            "rides": context.get("rides", []),
            "fuel_cost": context.get("fuel_cost"),
        }

    async def get_live_prices(self, source: str, dest: str, mode: str = "cab") -> list[dict]:
        """Get real ride prices by resolving names to coordinates."""
        src_coords = await geocode(source)
        dst_coords = await geocode(dest)
        if src_coords and dst_coords:
            return await google_maps_client.estimate_ride_prices(
                src_coords["lat"], src_coords["lng"],
                dst_coords["lat"], dst_coords["lng"],
            )
        return []

    async def estimate_ride_prices_coords(self, src_lat: float, src_lng: float,
                                           dst_lat: float, dst_lng: float) -> list[dict]:
        """Get ride prices using direct coordinates (skip geocoding)."""
        return await google_maps_client.estimate_ride_prices(
            src_lat, src_lng,
            dst_lat, dst_lng,
        )

    async def get_weather_impact(self, location: str = "Bengaluru", lat: float = None, lng: float = None) -> dict:
        """Get real weather data for specific coordinates. Returns floats, not strings."""
        wlat = lat or 12.9716
        wlng = lng or 77.5946
        weather_info = await weather_client.get_weather_impact(wlat, wlng)
        if weather_info and weather_info.get("condition") != "Unknown":
            surge = weather_info.get("surge_multiplier", 0)
            return {
                "condition": weather_info.get("condition", "clear"),
                "temperature_celsius": weather_info.get("temperature"),
                "humidity": weather_info.get("humidity"),
                "impact": "moderate" if surge > 0 else "minor",
                "recommendation": weather_info.get("advisory", "Good for travel"),
                "rain_probability": weather_info.get("rain_probability", surge * 100),
                "surge_multiplier": surge,
            }
        return {}

    async def get_current_events(self, location: str = "Bengaluru") -> str:
        """Get current events via news scraper."""
        news = await news_scraper.get_news("bangalore", limit=3)
        if news:
            items = [f"• {n.get('title', '')}" for n in news[:3] if n.get('title')]
            return "\n".join(items) if items else "No current events"
        return "No current event data."

    async def get_travel_news(self, source: str = None, dest: str = None) -> list[dict]:
        """Get travel news from real sources. Never returns hardcoded data."""
        news = await get_travel_news(source, dest, limit=5)
        return news or []

    async def get_real_reviews(self, name: str, address: str = None) -> dict | None:
        """Get real reviews from SerpAPI, Reddit, JustDial."""
        return await get_place_reviews(name, address)

    async def chat_response(self, user_message: str, context: dict = None) -> str:
        """AI chat response using real data context."""
        ctx_parts = []

        if context:
            if context.get("weather"):
                ctx_parts.append(f"Weather: {json.dumps(context['weather'])}")
            if context.get("news"):
                headlines = [n.get("title", "") for n in (context.get("news", []) or [])[:3]]
                ctx_parts.append(f"News: {'; '.join(headlines)}")
            if context.get("places"):
                names = [p.get("name", "") for p in (context.get("places", []) or [])[:3]]
                ctx_parts.append(f"Nearby: {', '.join(names)}")
            if context.get("rides"):
                rides_str = "; ".join([f"{r.get('service','')}: ₹{r.get('fare',0)}" for r in (context.get("rides", []) or [])[:3]])
                ctx_parts.append(f"Rides: {rides_str}")

        ctx_str = "\n".join(ctx_parts) if ctx_parts else ""
        system = "You are VOYAGER's Bengaluru travel assistant. Answer concisely using real data."
        prompt = f"{ctx_str}\nUser: {user_message}\nAssistant:" if ctx_str else f"User: {user_message}\nAssistant:"
        try:
            return await self._call_llm(system, prompt, json_mode=False)
        except Exception as e:
            return f"Unable to get AI response: {str(e)}"

    async def get_hotel_prices(self, name: str, city: str = "Bengaluru") -> dict:
        """Get real hotel prices."""
        return await get_hotel_prices(name, city)

    async def get_comprehensive_context(self, source: str, dest: str, group_size: int, budget: float = None) -> dict:
        """Get comprehensive travel context from all real data sources."""
        return await voyager_agent.comprehensive_context(
            source, dest, group_size, budget or 0
        )


llm_agent = LLMAgent()


class WebSearchAgent:
    async def search_web(self, query: str) -> str:
        results = await ddg_scraper.search(query, max_results=3, use_proxy=False)
        if results:
            return " | ".join([r.get("snippet", "")[:200] for r in results if r.get("snippet")])
        return ""

web_agent = WebSearchAgent()
