import logging
import httpx

logger = logging.getLogger(__name__)


class WeatherClient:
    """Real weather data from Open-Meteo (free, no API key needed)."""

    async def get_weather(self, lat: float, lng: float) -> dict | None:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": ["temperature_2m", "relative_humidity_2m", "apparent_temperature", "weather_code", "wind_speed_10m", "precipitation"],
            "hourly": ["temperature_2m", "precipitation_probability", "weather_code"],
            "timezone": "Asia/Kolkata",
            "forecast_hours": 12,
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current", {})
                    hourly = data.get("hourly", {})

                    weather_code = current.get("weather_code", 0)
                    times = hourly.get("time", [])[:12]
                    temps = hourly.get("temperature_2m", [])[:12]
                    rain_probs = hourly.get("precipitation_probability", [])[:12]

                    return {
                        "temperature": current.get("temperature_2m"),
                        "feels_like": current.get("apparent_temperature"),
                        "humidity": current.get("relative_humidity_2m"),
                        "wind_speed": current.get("wind_speed_10m"),
                        "precipitation": current.get("precipitation", 0),
                        "weather_code": weather_code,
                        "condition": self._code_to_condition(weather_code),
                        "rain_probability": max(rain_probs) if rain_probs else 0,
                        "hourly": [
                            {"time": t, "temp": tmp, "rain_prob": rp}
                            for t, tmp, rp in zip(times, temps, rain_probs)
                        ] if times else [],
                    }
        except Exception as e:
            logger.warning(f"Weather API failed for {lat},{lng}: {e}")
            return None
        return None

    @staticmethod
    def _code_to_condition(code: int) -> str:
        if code == 0: return "Clear"
        if code <= 3: return "Partly Cloudy"
        if code <= 48: return "Foggy"
        if code <= 57: return "Drizzle"
        if code <= 67: return "Rain"
        if code <= 77: return "Snow"
        if code <= 82: return "Rain Showers"
        if code <= 86: return "Snow Showers"
        return "Thunderstorm"

    async def get_weather_impact(
        self, lat: float, lng: float
    ) -> dict:
        """Get weather impact on travel."""
        weather = await self.get_weather(lat, lng)
        if not weather:
            return {"surge_multiplier": 0, "advisory": "", "condition": "Unknown"}

        is_rainy = weather["condition"] in ("Rain", "Drizzle", "Thunderstorm", "Rain Showers")
        surge = 0.3 if is_rainy else 0.0

        advisory = ""
        if weather["rain_probability"] > 70:
            advisory = "High chance of rain. Expect traffic delays and surge pricing."
        elif weather["rain_probability"] > 40:
            advisory = "Possible rain. Carry an umbrella."
        elif weather["temperature"] and weather["temperature"] > 35:
            advisory = "Very hot. Stay hydrated, prefer AC transport."

        return {
            "surge_multiplier": surge,
            "advisory": advisory,
            "condition": weather.get("condition", "Unknown"),
            "temperature": weather.get("temperature"),
            "humidity": weather.get("humidity"),
        }


weather_client = WeatherClient()
