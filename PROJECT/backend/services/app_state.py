"""Lazy singleton service holders for the VOYAGER v2 API.

GTFS (0.65s pickle), graph build (~2s) and GraphHopper client are created
once and shared by every request. `ensure_loaded()` warms everything at
startup; endpoints may also call it defensively.
"""
from .database import TransitDatabase
from .gtfs_service import GTFSService
from .graphhopper_client import GraphHopperClient
from .segment_builder import SegmentBuilder
from .clients.google_maps_client import GoogleMapsClient
from .clients.serpapi_client import SerpAPIClient
from .clients.weather_client import WeatherClient
from .search_service import SearchService
from .news_engine import NewsEngine
from .train_service import TrainService
from .proxy_manager import ProxyManager
from .langgraph.agent import VoyagerLangGraph

_gtfs: GTFSService | None = None
_db: TransitDatabase | None = None
_gh: GraphHopperClient | None = None
_builder: SegmentBuilder | None = None
_search: SearchService | None = None
_news: NewsEngine | None = None
_trains: TrainService | None = None
_weather: WeatherClient | None = None
_agent: VoyagerLangGraph | None = None


def _load_all():
    global _gtfs, _db, _gh, _builder, _search, _news, _trains, _weather, _agent
    if _gtfs is None:
        _gtfs = GTFSService()
        _gtfs.load()
    if _db is None:
        _db = TransitDatabase()
    if _gh is None:
        _gh = GraphHopperClient()  # local Docker on :8080
    if _builder is None:
        _builder = SegmentBuilder(_gtfs, _db, _gh)
    if _weather is None:
        _weather = WeatherClient()
    if _search is None:
        _search = SearchService(GoogleMapsClient(), SerpAPIClient())
    if _news is None:
        _news = NewsEngine(ProxyManager())
    if _trains is None:
        _trains = TrainService()
    if _agent is None:
        _agent = VoyagerLangGraph(
            weather=_weather,
            news=_news,
            search=_search,
            train=_trains,
        )
    return _gtfs, _db, _gh, _builder, _search, _news, _trains, _weather, _agent


def ensure_loaded():
    return _load_all()


def is_loaded() -> bool:
    return all(x is not None for x in
               (_gtfs, _db, _gh, _builder, _search, _news, _trains, _weather, _agent))


def get_builder() -> SegmentBuilder:
    return _load_all()[3]


def get_search() -> SearchService:
    return _load_all()[4]


def get_news() -> NewsEngine:
    return _load_all()[5]


def get_trains() -> TrainService:
    return _load_all()[6]


def get_weather() -> WeatherClient:
    return _load_all()[7]


def get_agent() -> VoyagerLangGraph:
    return _load_all()[8]
