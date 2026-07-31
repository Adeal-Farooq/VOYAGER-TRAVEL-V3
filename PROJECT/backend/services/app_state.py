"""Lazy singleton service holders for the VOYAGER v2 API.

GTFS (0.65s pickle), graph build (~2s) and GraphHopper client are created
once and shared by every request. `ensure_loaded()` warms everything at
startup; endpoints may also call it defensively.
"""
from .database import TransitDatabase
from .gtfs_service import GTFSService
from .graphhopper_client import GraphHopperClient
from .segment_builder import SegmentBuilder

_gtfs: GTFSService | None = None
_db: TransitDatabase | None = None
_gh: GraphHopperClient | None = None
_builder: SegmentBuilder | None = None


def _load_all():
    global _gtfs, _db, _gh, _builder
    if _gtfs is None:
        _gtfs = GTFSService()
        _gtfs.load()
    if _db is None:
        _db = TransitDatabase()
    if _gh is None:
        _gh = GraphHopperClient()  # local Docker on :8080
    if _builder is None:
        _builder = SegmentBuilder(_gtfs, _db, _gh)
    return _gtfs, _db, _gh, _builder


def ensure_loaded():
    return _load_all()


def is_loaded() -> bool:
    return all(x is not None for x in (_gtfs, _db, _gh, _builder))


def get_builder() -> SegmentBuilder:
    return _load_all()[3]
