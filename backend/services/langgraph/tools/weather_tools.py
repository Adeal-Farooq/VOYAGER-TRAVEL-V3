"""Weather tools for LangGraph agents."""

from backend.services.clients.weather_client import weather_client


async def get_weather(lat: float, lng: float) -> dict:
    """Get current weather for coordinates."""
    return await weather_client.get_weather_impact(lat, lng)


async def get_weather_forecast(lat: float, lng: float, hours: int = 12) -> dict:
    """Get weather forecast for next N hours."""
    weather = await weather_client.get_weather(lat, lng)
    if not weather:
        return {"condition": "Unknown", "hourly": []}
    return weather
