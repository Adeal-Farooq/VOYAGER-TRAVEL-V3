from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.database import db
from backend.api import search, routes
from backend.services.n8n_service import n8n_service

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(routes.router)

@app.on_event("startup")
async def startup():
    db.initialize()
    # Preload GTFS data synchronously (takes ~40s once)
    from backend.services.transit_service import _ensure_gtfs
    _ensure_gtfs()

@app.get("/api/n8n-status")
async def n8n_status():
    available = await n8n_service.is_available()
    return {
        "status": "available" if available else "unavailable",
        "webhook_url": settings.N8N_WEBHOOK_URL or "not configured",
        "note": "n8n handles: place verification, weather/traffic, ride prices, hotel prices"
    }

@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "data": {
            "metro_stations": len(db.metro_stations),
            "bus_stops": len(db.bus_stops),
            "kia_routes": len(db.kia_routes),
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "database_initialized": db._initialized}
#update
#update