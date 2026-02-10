import os
from typing import Any, Dict
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from app.api.routes import router
from app.utils.logger import logger

load_dotenv()

BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR: str = os.path.join(BASE_DIR, "app/static")

app: FastAPI = FastAPI(
    title="Agent-First SERP Gateway",
    description="A resilient, token-optimized Search-to-LLM context API.",
    version="1.0.0"
)

from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def read_index() -> FileResponse:
    """Read and return the index.html file."""
    return FileResponse(os.path.join(STATIC_DIR, 'index.html'))

app.include_router(router)

@app.on_event("startup")
async def startup_event() -> None:
    """Execute on application startup."""
    logger.info("Application starting up...")

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
