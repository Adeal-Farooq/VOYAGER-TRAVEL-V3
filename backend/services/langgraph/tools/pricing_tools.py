"""Pricing/ride fare tools for LangGraph agents."""

from backend.services.clients.google_maps_client import google_maps_client
from backend.services.scrapers.ddg_scraper import ddg_scraper


async def get_ride_prices(
    source_lat: float, source_lng: float,
    dest_lat: float, dest_lng: float,
    group_size: int = 1, budget: float = 0,
) -> list[dict]:
    """Get real ride prices (Uber/Ola/Rapido) using Google Maps API + fare rules."""
    return await google_maps_client.estimate_ride_prices(
        source_lat, source_lng, dest_lat, dest_lng, group_size, budget
    )


async def get_distance_duration(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> dict | None:
    """Get real distance and duration using Google Maps API."""
    return await google_maps_client.get_distance_matrix(
        origin_lat, origin_lng, dest_lat, dest_lng
    )


async def estimate_fuel_cost(distance_km: float) -> dict:
    """Estimate fuel cost for personal vehicle."""
    from backend.core.config import settings
    fuel_price = settings.FUEL_PRICE_PER_LITER
    mileage = settings.PETROL_AVG_MILEAGE
    liters = distance_km / mileage
    total_cost = liters * fuel_price
    return {
        "distance_km": round(distance_km, 1),
        "fuel_liters": round(liters, 1),
        "fuel_cost": round(total_cost),
        "fuel_price_per_liter": fuel_price,
        "mileage_kmpl": mileage,
        "currency": "INR",
    }


async def get_hotel_prices(name: str, city: str = "Bengaluru") -> dict:
    """Get hotel price estimates from web search."""
    results = await ddg_scraper.search(f"{name} {city} hotel room price per night", max_results=4)
    snippets = [r.get("snippet", "") for r in results if r.get("snippet")]

    import re
    prices = []
    for s in snippets:
        nums = re.findall(r'(?:rs|inr|₹)\s*(\d{3,5})', s.lower())
        prices.extend(int(n) for n in nums)

    if prices:
        avg_price = sum(prices) // len(prices)
        return {
            "name": name,
            "city": city,
            "avg_price": avg_price,
            "min_price": min(prices),
            "max_price": max(prices),
            "currency": "INR",
            "source": "web_search",
        }

    return {
        "name": name,
        "city": city,
        "avg_price": 0,
        "min_price": 0,
        "max_price": 0,
        "currency": "INR",
        "source": "unavailable",
    }
