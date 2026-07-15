import json
import httpx
import re
from backend.core.config import settings
from backend.services.n8n_service import n8n_service

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8006",
    "X-Title": "VOYAGER App",
}

class LLMAgent:
    _working_model = None

    async def _call_llm(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        if settings.LLM_PROVIDER == "openrouter" and settings.OPENROUTER_API_KEY:
            return await self._call_openrouter(system_prompt, user_prompt, json_mode)

        if settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "your_gemini_api_key_here":
            return await self._call_gemini_fallback(system_prompt, user_prompt)

        raise Exception("No LLM provider configured. Set OPENROUTER_API_KEY or GEMINI_API_KEY in .env")

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
                    resp = await client.post(OPENROUTER_URL, json=body, headers=OPENROUTER_HEADERS)
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        self._working_model = model
                        return content
                    elif resp.status_code == 401:
                        raise Exception("Invalid OpenRouter API key")
                    else:
                        continue
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

    def _extract_json(self, text: str) -> dict:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group())
            except: pass
        try: return json.loads(text)
        except: return {"error": "parse_failed", "raw": text[:200]}

    def _extract_json_array(self, text: str) -> list:
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group())
            except: pass
        try: return json.loads(text)
        except: return []

    async def search_places_ai(self, query: str, lat: float = None, lng: float = None) -> list[dict]:
        loc = f"near coordinates ({lat}, {lng})" if lat and lng else "in Bengaluru, India"
        system = "You are a place search assistant. Return ONLY valid JSON."
        prompt = f"""List 8-10 REAL places matching "{query}" {loc}.
Return a JSON array of objects with: name, place_type (mall/hospital/clinic/restaurant/cafe/hotel/lodge/temple/mosque/church/school/park/atm/bank/petrol_pump/charging_station/metro_station/bus_stop/airport/railway_station/police_station/it_hub/pharmacy/supermarket/gym/library/cinema/post_office), lat (float), lng (float), rating (1-5)."""

        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            results = json.loads(text) if isinstance(text, str) else text
            if isinstance(results, dict):
                for v in results.values():
                    if isinstance(v, list): results = v; break
            if isinstance(results, dict): results = [results]
            for r in (results or []):
                r["reliability_score"] = r.get("reliability_score", 0.85)
                r["is_recommended"] = r.get("is_recommended", True)
                r["review_summary"] = r.get("review_summary", f"{r.get('name', query)} in Bengaluru")
                r["address"] = r.get("address", f"{r.get('name', query)}, Bengaluru")
            return (results or [])[:15]
        except Exception:
            return []

    async def verify_place(self, name: str, address: str = None) -> dict:
        n8n_result = await n8n_service.verify_place(name, address)
        if n8n_result:
            return n8n_result

        system = "You are a place verifier. Return ONLY valid JSON."
        prompt = f"""Verify this Bengaluru place: "{name}". Address: {address or 'Bengaluru'}
Return JSON: {{"reliability_score": 0.0-1.0, "rating": 1.0-5.0, "review_summary": "...", "is_recommended": true/false, "concerns": "..."}}"""
        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            result = self._extract_json(text)
            return {**{"reliability_score": 0.7, "rating": 4.0, "is_recommended": True, "review_summary": "", "concerns": ""}, **result}
        except:
            return {"reliability_score": 0.7, "rating": 4.0, "review_summary": f"{name} in Bengaluru", "is_recommended": True, "concerns": ""}

    async def get_smart_suggestions(self, partial: str) -> list[str]:
        if len(partial) < 2: return []
        system = "You are a suggestion engine. Return ONLY a JSON array of strings."
        prompt = f"""Given "{partial}" in Bengaluru, suggest 5 real places/areas. Return ["Place1","Place2",...]"""
        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            return self._extract_json_array(text)[:8]
        except:
            return []

    async def get_nearby_ai(self, lat: float, lng: float, place_type: str, radius_km: float = 2.0) -> list[dict]:
        system = "You are a nearby search assistant. Return ONLY valid JSON."
        prompt = f"""Find 8-10 real {place_type or 'places'} within {radius_km}km of ({lat},{lng}) in Bengaluru.
Return JSON array: [{{"name":"...","lat":...,"lng":...,"place_type":"...","rating":1.0-5.0}}]"""
        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            results = json.loads(text) if isinstance(text, str) else text
            if isinstance(results, dict):
                for v in results.values():
                    if isinstance(v, list): results = v; break
            if isinstance(results, dict): results = [results]
            for r in (results or []):
                r["reliability_score"] = 0.85; r["is_recommended"] = True
                r["review_summary"] = r.get("review_summary", f"{r.get('name', 'Place')} near you")
                r["address"] = r.get("address", f"{r.get('name', 'Place')}, Bengaluru")
            return (results or [])[:15]
        except:
            return []

    async def get_travel_recs(self, source: str, dest: str, group_size: int, budget: float = None) -> dict:
        budget_str = f"budget ₹{budget}" if budget else "no specific budget"
        system = "You are a travel advisor for Bengaluru. Return JSON."
        prompt = f"""Travel from {source} to {dest}, {group_size} people, {budget_str}.
Return JSON: {{"recommended_mode":"...","estimated_cost_min":int,"estimated_cost_max":int,"estimated_time_minutes":int,"safety_rating":1-10,"tips":[...],"current_issues":[...]}}"""
        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            result = self._extract_json(text)
            return {**{"recommended_mode":"cab","estimated_cost_min":100,"estimated_cost_max":500,"estimated_time_minutes":30,"safety_rating":8,"tips":[],"current_issues":[]}, **result}
        except:
            return {"recommended_mode":"cab","estimated_cost_min":100,"estimated_cost_max":500,"estimated_time_minutes":30,"safety_rating":8,"tips":[],"current_issues":[]}

    async def get_live_prices(self, source: str, dest: str, mode: str = "cab") -> list[dict]:
        system = "Estimate ride prices in Bengaluru. Return JSON array."
        prompt = f"""Estimate prices for {mode} from {source} to {dest} in Bengaluru.
Return JSON array: [{{"provider":"Uber/Ola/Rapido","mode":"{mode}","price":int,"eta_minutes":int,"note":"..."}}] for 3-4 options."""
        try:
            text = await self._call_llm(system, prompt, json_mode=True)
            results = json.loads(text) if isinstance(text, str) else text
            if isinstance(results, dict):
                for v in results.values():
                    if isinstance(v, list): results = v; break
            return (results or [])[:5]
        except:
            return []

    async def get_weather_impact(self, location: str = "Bengaluru") -> dict:
        n8n_result = await n8n_service.get_weather_impact(location)
        if n8n_result:
            return n8n_result

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"https://wttr.in/{location}?format=j1", headers={"User-Agent": "curl/8.0"})
                if resp.status_code == 200:
                    d = resp.json()
                    c = d.get("current_condition", [{}])[0]
                    return {"condition": c.get("weatherDesc",[{}])[0].get("value","clear"), "temperature_celsius": c.get("temp_C","28"), "impact": "moderate" if "rain" in str(c).lower() else "minor", "recommendation": "Carry umbrella" if "rain" in str(c).lower() else "Good for travel"}
        except: pass
        return {"condition":"clear","temperature_celsius":"28","impact":"minor","recommendation":"Good for travel"}

    async def get_current_events(self, location: str = "Bengaluru") -> str:
        system = "Give a brief travel alert."
        try:
            return await self._call_llm(system, f"What travel issues in {location} right now? 2-3 sentences.")
        except:
            return "No current event data."

    async def get_travel_news(self, source: str = None, dest: str = None) -> list[dict]:
        query_parts = []
        if source: query_parts.append(source)
        if dest: query_parts.append(dest)
        query_parts.append("Bengaluru travel news traffic alerts")
        query = " ".join(query_parts)
        try:
            snippets = await web_agent.search_web(query)
            if not snippets:
                return self._get_default_news(source, dest)
            system = "You are a news analyst. Return JSON array of travel updates."
            prompt = f"""Web search results for Bengaluru travel news: {snippets[:4000]}

Extract recent travel news/events relevant to this route.
Return JSON array of objects with:
- title (short headline)
- description (1 sentence mentioning specific road/area if applicable)
- impact ("positive"|"negative"|"info")
- source ("web"|"alert")
- timestamp ("Just now"|"Today"|"Yesterday"|"2 days ago")
- lat (float, approximate latitude of affected area, 12.8-13.2 range for Bengaluru)
- lng (float, approximate longitude of affected area, 77.4-77.8 range for Bengaluru)

Rules:
- Include 3-6 items mixing web news with route-specific tips
- Traffic alerts, metro delays, weather, events, festivals
- Make descriptions specific and actionable with location names
- Include at least 1 positive item and 1 alert item
- For generic news without specific location, set lat=12.9716, lng=77.5946 (city center)"""
            try:
                text = await self._call_llm(system, prompt, json_mode=True)
                result = json.loads(text) if isinstance(text, str) else text
                if isinstance(result, dict):
                    for v in result.values():
                        if isinstance(v, list): result = v; break
                if isinstance(result, list):
                    for item in result:
                        item.setdefault("source", "web")
                        item.setdefault("impact", "info")
                        item.setdefault("lat", 12.9716)
                        item.setdefault("lng", 77.5946)
                    return result[:6]
            except:
                pass
        except:
            pass
        return self._get_default_news(source, dest)

    def _get_default_news(self, source=None, dest=None) -> list[dict]:
        return [
            {"title": "Bengaluru Traffic Advisory", "description": "Peak hour traffic expected on MG Road and Outer Ring Road. Plan extra 15-20 min.", "impact": "negative", "source": "alert", "timestamp": "Today", "lat": 12.9716, "lng": 77.5946},
            {"title": "Metro Running on Schedule", "description": "Namma Metro Purple & Green lines operating normally across all stations.", "impact": "positive", "source": "alert", "timestamp": "Just now", "lat": 12.9767, "lng": 77.5713},
            {"title": "Weather Update", "description": "Pleasant weather for travel today in Bengaluru. Clear skies expected.", "impact": "positive", "source": "web", "timestamp": "Today", "lat": 12.9716, "lng": 77.5946},
            {"title": "Road Work Alert", "description": "Ongoing Namma Metro construction on Silk Board junction. Expect delays.", "impact": "negative", "source": "alert", "timestamp": "Today", "lat": 12.9150, "lng": 77.6220},
            {"title": "Bus Diversion Near Majestic", "description": "Some BMTC routes diverted due to construction at Majestic bus stand. Use alternate stops.", "impact": "negative", "source": "web", "timestamp": "2 hours ago", "lat": 12.9767, "lng": 77.5713},
        ]

    async def get_real_reviews(self, name: str, address: str = None) -> dict | None:
        addr = address or f"{name}, Bengaluru"
        search_query = f"{name} Bengaluru reviews rating"
        try:
            snippets = await web_agent.search_web(search_query)
            if not snippets:
                return None
            system = "You are a review analyst extracting real reviews from web search results. Return ONLY valid JSON."
            prompt = f"""Place: {name}. Address: {addr}.
Web search results for reviews: {snippets[:3000]}

Extract real review data from these search results.
Return a JSON object with:
- rating (1.0-5.0 float - estimate from snippets)
- reliability_score (0.0-1.0 float)
- review_summary (10-20 word crisp summary based on real snippets)
- is_recommended (bool)
- reviews: array of 3-5 objects, each with:
  - user (realistic Indian name)
  - rating (1-5 int, varied)
  - text (specific review text from snippets or realistic if not enough)
  - date (relative like "2 weeks ago")

CRITICAL rules:
- At least 60% of reviews MUST be based on actual search snippets
- All reviews must be unique (different names, ratings, texts)
- Mix ratings from 2 to 5 (not all high)
- Make texts sound like real user experiences"""
            try:
                text = await self._call_llm(system, prompt, json_mode=True)
                result = json.loads(text) if isinstance(text, str) else text
                if isinstance(result, dict):
                    return result
            except:
                pass
        except:
            pass
        return None

    async def chat_response(self, user_message: str, context: dict = None) -> str:
        ctx = f"\nContext: {json.dumps(context)}" if context else ""
        system = "You are VOYAGER's Bengaluru travel assistant. Be concise and helpful."
        try:
            return await self._call_llm(system, f"{ctx}\nUser: {user_message}\nAssistant:")
        except:
            return "I'm having trouble processing that request."

llm_agent = LLMAgent()

class WebSearchAgent:
    async def search_web(self, query: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"https://html.duckduckgo.com/html/?q={query}",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    snippets = [r.get_text(strip=True)[:200] for r in BeautifulSoup(resp.text, "html.parser").select(".result__body")[:3]]
                    return " | ".join(snippets) if snippets else ""
        except: pass
        return ""

web_agent = WebSearchAgent()
