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
from app.services.llm_judge import llm_judge
from app.utils.logger import logger
import httpx
from prometheus_client import Counter

TOKEN_USAGE = Counter(
    "flux_token_usage_total",
    "Total estimated token usage",
    ["model", "context"]
)


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

    # Robustness Settings
    task_acks_late=True,             # Only ack after task succeeds/fails
    worker_prefetch_multiplier=1,    # Only take 1 task at a time per worker process
    task_reject_on_worker_lost=True, # Re-queue task if worker crashes
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

    # Phase 1.5: Deep Scrape Enrichment (Parallel)
    if mode != "scrape" and formatted_data.get("organic_results"):
        logger.info("Enriching organic results with deep scraping...")
        urls = [res.get("url") for res in formatted_data["organic_results"] if res.get("url")]
        
        if urls:
            try:
                # Limit URLs to avoid massive parallel overhead if user requested 50
                urls_to_scrape = urls[:10] 
                raw_contents = loop.run_until_complete(scraper.scrape_multiple_urls(urls_to_scrape))
                
                for i, raw in enumerate(raw_contents):
                    if raw:
                        # Parse and filter full content using trafilatura logic
                        enriched = parser.parse_url_content(raw)
                        # Store in the result
                        if enriched["organic_results"]:
                            text = enriched["organic_results"][0].get("snippet", "")
                            formatted_data["organic_results"][i]["full_content"] = text
                            # Also update snippet if snippet was too short before
                            if len(text) > len(formatted_data["organic_results"][i].get("snippet", "")):
                                formatted_data["organic_results"][i]["snippet"] = text[:300] + "..."
            except Exception as e:
                logger.error("Deep scrape enrichment failed: %s", e)

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
    # Check if previous task failed
    if "error" in result:
            return result

    query = result.get("query", "")
    token_estimate = result.get("token_estimate", 0)
    TOKEN_USAGE.labels(model="unknown", context="embedding_input").inc(token_estimate)
    
    # Generate Embeddings (CPU Intensive)

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

@celery_app.task(bind=True, name="app.worker.score_task", queue="scrapers")
def score_task(
    self: Task,
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Phase 3: Scoring Task
    Evaluates relevance and credibility using LLM.
    """
    if "error" in result:
        return result

    query = result.get("query", "")
    organic_results = result.get("organic_results", [])
    snippets = [r.get("snippet", "") for r in organic_results]

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run scoring in parallel
    async def _score():
        rel_task = llm_judge.evaluate_relevance(query, snippets)
        cred_task = llm_judge.evaluate_credibility(query, organic_results)
        return await asyncio.gather(rel_task, cred_task)

    try:
        rel_out, cred_out = loop.run_until_complete(_score())
        
        result["relevance_score"] = rel_out.get("score", 0.0)
        result["relevance_reasoning"] = rel_out.get("reasoning", "No reasoning provided.")
        result["credibility_score"] = cred_out.get("score", 0.0)
        result["credibility_reasoning"] = cred_out.get("reasoning", "No reasoning provided.")
        
        logger.info("Scoring complete for query=%s. Relevance: %s, Credibility: %s", 
                    query, result["relevance_score"], result["credibility_score"])
    except Exception as e:
        logger.error("Scoring task error: %s", e)
        result["relevance_score"] = 0.0
        result["credibility_score"] = 0.0

    return result

@celery_app.task(name="app.worker.health_check")
def health_check():
    return "OK"
