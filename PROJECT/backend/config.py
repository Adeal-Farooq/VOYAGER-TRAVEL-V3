from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FOLDER = PROJECT_ROOT / "DATA_FOLDER"
GTFS_CACHE_PATH = DATA_FOLDER / "processed" / "gtfs_cache.pkl"
GTFS_RAW_FOLDER = DATA_FOLDER / "bmtc_gtfs"
TRANSIT_FARES_PATH = DATA_FOLDER / "transit_fares.json"
KIA_ROUTES_PATH = DATA_FOLDER / "kia_routes_fare_full.json"
METRO_NETWORK_PATH = DATA_FOLDER / "bengaluru_metro_network.csv"
BUS_STOPS_MASTER_PATH = DATA_FOLDER / "bmtc_all_stops_master.csv"
RAIL_STATIONS_PATH = DATA_FOLDER / "karnataka_railway_stations.json"
TRAFFIC_LOGS_PATH = DATA_FOLDER / "traffic_logs.csv"

ENV_PATH = PROJECT_ROOT / ".env"

# Metro lines considered operational. Yelahanka + Blue/Yellow lines are NOT.
OPERATIONAL_METRO_LINES = ("Purple Line", "Green Line")


def load_env() -> None:
    """Load .env if present (secrets stay out of git). No-op when missing."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ENV_PATH)
    except ImportError:  # pragma: no cover
        pass


def env_str(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def env_float(key: str, default: float) -> float:
    import os

    try:
        return float(os.environ.get(key, "").strip() or default)
    except ValueError:
        return default


load_env()

FUEL_PRICE_PER_LITER = env_float("FUEL_PRICE_PER_LITER", 110.0)
PETROL_AVG_MILEAGE = env_float("PETROL_AVG_MILEAGE", 15.0)
DATABASE_URL = env_str("DATABASE_URL")
