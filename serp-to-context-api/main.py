import os
from typing import Any, Dict
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis
from app.api.routes import router
from app.utils.logger import logger

load_dotenv()

BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR: str = os.path.join(BASE_DIR, "app/static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    await FastAPILimiter.init(r)
    logger.info("Application starting up...")
    yield
    # Shutdown
    await r.close()
    logger.info("Application shutting down...")

app: FastAPI = FastAPI(
    title="Agent-First SERP Gateway",
    description="A resilient, token-optimized Search-to-LLM context API.",
    version="1.0.0",
    lifespan=lifespan
)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))

app.include_router(router)

@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Application starting up...")

@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}
