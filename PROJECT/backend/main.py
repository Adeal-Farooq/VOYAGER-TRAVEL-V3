"""VOYAGER v2 FastAPI app (PROMPT_3 API layer).

Wires the segment builder (PROMPT_3) as HTTP endpoints. The data layer
(GTFS/DB/graphhopper) is built lazily so `uvicorn backend.main:app --reload`
starts instantly and the first request pays the warm-up cost.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.routes import router as routes_router
from backend.services import app_state


@asynccontextmanager
async def lifespan(_app: FastAPI):
    app_state.ensure_loaded()
    yield


app = FastAPI(title="VOYAGER v2", version="0.3.0", lifespan=lifespan)

app.include_router(routes_router, prefix="/api/routes")


@app.get("/api/health")
def health():
    loaded = app_state.is_loaded()
    return {"status": "ok", "services_loaded": loaded}
