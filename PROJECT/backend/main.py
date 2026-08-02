"""VOYAGER v2 FastAPI app (PROMPT_3 API layer).

Wires the segment builder (PROMPT_3) as HTTP endpoints. The data layer
(GTFS/DB/graphhopper) is built lazily so `uvicorn backend.main:app --reload`
starts instantly and the first request pays the warm-up cost.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as routes_router
from backend.api.routes import search_router
from backend.services import app_state


@asynccontextmanager
async def lifespan(_app: FastAPI):
    app_state.ensure_loaded()
    yield


app = FastAPI(title="VOYAGER v2", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_router, prefix="/api/routes")
app.include_router(search_router, prefix="/api")


@app.get("/api/health")
def health():
    loaded = app_state.is_loaded()
    return {"status": "ok", "services_loaded": loaded}
