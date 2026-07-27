import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "VOYAGER - Bengaluru Transit Navigator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATA_CACHE_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data_cache")
    PROCESSED_DIR: str = os.path.join(DATA_CACHE_DIR, "processed")

    LLM_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_FALLBACK_MODELS: list[str] = [
        "openai/gpt-4o-mini",
        "openai/gpt-3.5-turbo",
        "anthropic/claude-3-haiku",
        "meta-llama/llama-3-8b-instruct",
        "mistralai/mistral-7b-instruct",
        "google/gemini-1.5-flash",
    ]

    GEMINI_API_KEY: str = ""

    BANGALORE_CENTER_LAT: float = 12.9716
    BANGALORE_CENTER_LNG: float = 77.5946
    BANGALORE_DEFAULT_ZOOM: int = 12

    OSRM_BASE_URL: str = "http://localhost:5000"
    OSRM_FOOT_URL: str = "http://localhost:5001"

    FUEL_PRICE_PER_LITER: float = 110.0
    PETROL_AVG_MILEAGE: float = 15.0

    # Scraping & API Keys
    DATAIMPULSE_USER: str = ""
    DATAIMPULSE_PASS: str = ""
    DATAIMPULSE_HOST: str = ""
    SERPAPI_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_CX: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

if isinstance(settings.OPENROUTER_FALLBACK_MODELS, str):
    import json
    try:
        settings.OPENROUTER_FALLBACK_MODELS = json.loads(settings.OPENROUTER_FALLBACK_MODELS)
    except (json.JSONDecodeError, TypeError):
        settings.OPENROUTER_FALLBACK_MODELS = [settings.OPENROUTER_FALLBACK_MODELS]
