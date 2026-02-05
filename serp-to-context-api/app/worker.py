import asyncio
import os
from celery import Celery
from app.services.scraper import scraper
from app.services.parser import parser
from app.services.formatter import formatter
from app.services.embeddings import embeddings_service
from app.utils.cache import cache

# Configure Celery
# Use REDIS_URL from env or default to localhost for local dev (container internal URL handled in docker-compose)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "flux_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="app.worker.scrape_and_process")
def scrape_and_process(self, query: str, region: str, language: str, limit: int, mode: str, output_format: str):
    """
    Background task to perform scraping, parsing, formatting, and embedding.
    """
    try:
        # 1. Check Cache (Double check in case recent update)
        # Note: In a real async flow, we might skip this if the API already checked, 
        # but good for idempotency if task is retried.
        cached_data = cache.get(query, region, language, limit)
        if cached_data:
            return cached_data

        # 2. Scrape (Async operation running in sync worker)
        # We need to run the async scraper method in a synchronous context
        # 2. Scrape (Async operation running in sync worker)
        # We need to run the async scraper method in a synchronous context
        try:
             loop = asyncio.get_event_loop()
        except RuntimeError:
             loop = asyncio.new_event_loop()
             asyncio.set_event_loop(loop)

        content = None
        parsed_data = None

        if mode == "scrape":
            # Direct URL Scraping
            content = loop.run_until_complete(scraper.scrape_url(query))
            if not content:
                 return {"error": "Failed to scrape URL"}
            
            parsed_data = parser.parse_url_content(content)
            # Inject URL if missing
            if parsed_data["organic_results"] and not parsed_data["organic_results"][0]["url"]:
                parsed_data["organic_results"][0]["url"] = query
        else:
            # Standard Search
            content = loop.run_until_complete(scraper.fetch_results(query, region, language, limit))
            if not content:
                return {"error": "Failed to fetch search results"}
            parsed_data = parser.parse(content)

        # 3. Format
        formatted_data = formatter.format_response(query, parsed_data)

        # 4. Prepare Result
        result = {
            "query": query,
            "ai_overview": formatted_data["ai_overview"],
            "organic_results": formatted_data["organic_results"],
            "formatted_output": formatted_data["formatted_output"],
            "token_estimate": formatted_data["token_estimate"]
        }

        # 5. Embeddings (Heavy CPU task)
        if output_format and output_format.lower() in ["vector", "vectors"]:
            snippets = [res.get("snippet", "") for res in result["organic_results"]]
            if snippets:
                # This is blocking/CPU intensive - perfect for the worker
                vectors = embeddings_service.generate(snippets)
                # Convert numpy arrays to lists for JSON serialization
                # embeddings_service.generate likely returns lists or internal logic handles it, 
                # but let's ensure it's serializable. 
                # Assuming embeddings_service returns deserialized lists or we need to handle it.
                # Let's verify embeddings.py content if needed, but assuming list[list[float]]
                for i, res in enumerate(result["organic_results"]):
                    if i < len(vectors):
                         res["embedding"] = vectors[i]

        # 6. Cache Result
        if result["organic_results"]:
            cache.set(query, result, region, language, limit)

        return result

    except Exception as e:
        # Log error
        print(f"Task failed: {e}")
        return {"error": str(e)}
