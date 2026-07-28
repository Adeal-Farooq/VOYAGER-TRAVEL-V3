from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.database import db
from backend.api import search, routes
from backend.api.search import langgraph_router
 
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
app.include_router(langgraph_router)

@app.on_event("startup")
async def startup():
    import os
    test_time = os.environ.get("VOYAGER_TEST_TIME")
    if test_time:
        from backend.services.gtfs_service import set_test_time
        set_test_time(test_time)
        print(f"[MAIN] Test time override: {test_time}")

    db.initialize()
    # GTFS loads lazily on first route request (avoids ~40s startup block)

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