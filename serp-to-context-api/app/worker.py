import asyncio
import os
from typing import Any, Dict
from celery import Celery
from celery.app.task import Task
from app.services.scraper import scraper
from app.services.parser import parser
from app.services.formatter import formatter
from app.services.embeddings import embeddings_service
from app.utils.cache import cache
from app.db.database import AsyncSessionLocal, init_db
from app.db.repository import save_search_results
from app.utils.logger import logger
import httpx


POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "flux_db")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# Construct the SQLAlchemy connection string
# Format: db+postgresql://user:password@host:port/dbname
DATABASE_URL = f"db+postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Fallback to Redis for Broker only
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app: Celery = Celery(
    "flux_worker",
    broker=REDIS_URL,
    backend=DATABASE_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # SQLAlchemy Result Backend Settings
    database_engine_options={
        'echo': False,  # Set to True for debugging SQL queries
    },
    task_track_started=True,  # Track when the task starts
    task_ignore_result=False, # Ensure we store results

    # Robustness Settings (Commented out for debugging)
    # task_acks_late=True,             # Only ack after task succeeds/fails
    # worker_prefetch_multiplier=1,    # Only take 1 task at a time per worker process
    # task_reject_on_worker_lost=True, # Re-queue task if worker crashes
)

@celery_app.task(
    bind=True,
    name="app.worker.scrape_task",
    queue="scrapers",
    autoretry_for=(httpx.RequestError, httpx.TimeoutException, ConnectionError),
    retry_backoff=True,
    retry_kwargs={'max_retries': 3}
)
def scrape_task(
    self: Task,
    query: str,
    region: str,
    language: str,
    limit: int,
    mode: str
) -> Dict[str, Any]:
    """
    Phase 1: I/O Bound Task
    Scrapes URL/Search Engine, parses content, and formats basic result.
    """
    logger.info("Task msg received: app.worker.scrape_task query=%s", query)

    # Check cache first
    logger.info("Checking cache for query=%s", query)
    cached_data: Dict[str, Any] | None = cache.get(query, region, language, limit)
    if cached_data:
        logger.info("Cache hit!")
        return cached_data

    logger.info("Cache miss. Setting up event loop.")
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    content = None
    parsed_data = None

    if mode == "scrape":
        content = loop.run_until_complete(scraper.scrape_url(query))
        if not content:
            # Raise exception to trigger retry
            raise httpx.RequestError(f"Failed to scrape URL: {query}")
        
        parsed_data = parser.parse_url_content(content)
        if parsed_data["organic_results"] and not parsed_data["organic_results"][0]["url"]:
            parsed_data["organic_results"][0]["url"] = query
    else:
        content = loop.run_until_complete(scraper.fetch_results(query, region, language, limit))
        if not content:
            # Raise exception to trigger retry
            raise httpx.RequestError(f"Failed to fetch search results for query: {query}")
        parsed_data = parser.parse(content)

    formatted_data = formatter.format_response(query, parsed_data)

    result = {
        "query": query,
        "ai_overview": formatted_data["ai_overview"],
        "organic_results": formatted_data["organic_results"],
        "formatted_output": formatted_data["formatted_output"],
        "token_estimate": formatted_data["token_estimate"]
    }

    return result

@celery_app.task(bind=True, name="app.worker.embed_task", queue="embeddings")
def embed_task(
    self: Task,
    result: Dict[str, Any],
    region: str,
    language: str,
    limit: int,
    output_format: str
) -> Dict[str, Any]:
    """
    Phase 2: CPU Bound Task
    Generates embeddings, saves to DB, and updates cache.
    """
    try:
        if "error" in result:
             return result

        query = result.get("query", "")

        # Generate Embeddings (CPU Intensive)
        if output_format and output_format.lower() in ["vector", "vectors"]:
            snippets = [res.get("snippet", "") for res in result.get("organic_results", [])]
            if snippets:
                # This is the blocking CPU part
                vectors = embeddings_service.generate(snippets)
                for i, res in enumerate(result["organic_results"]):
                    if i < len(vectors):
                        res["embedding"] = vectors[i]

        # Save to Database (I/O)
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(init_db())

            async def _save():
                async with AsyncSessionLocal() as session:
                    await save_search_results(session, query, result["organic_results"])

            loop.run_until_complete(_save())
        except Exception as e:
            logger.error("Database save error: %s", e)

        # Update Cache
        if result.get("organic_results"):
            cache.set(query, result, region, language, limit)

        return result

    except Exception as e:
        logger.error("Embed task failed: %s", e)
        return {"error": str(e)}

@celery_app.task(name="app.worker.health_check")
def health_check():
    return "OK"
