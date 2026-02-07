import asyncio
import os
from celery import Celery
from app.services.scraper import scraper
from app.services.parser import parser
from app.services.formatter import formatter
from app.services.embeddings import embeddings_service
from app.utils.cache import cache
from app.db.database import AsyncSessionLocal, init_db
from app.db.repository import save_search_results
from app.utils.logger import logger


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
    try:
        cached_data = cache.get(query, region, language, limit)
        if cached_data:
            return cached_data

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
                 return {"error": "Failed to scrape URL"}
            
            parsed_data = parser.parse_url_content(content)
            if parsed_data["organic_results"] and not parsed_data["organic_results"][0]["url"]:
                parsed_data["organic_results"][0]["url"] = query
        else:
            content = loop.run_until_complete(scraper.fetch_results(query, region, language, limit))
            if not content:
                return {"error": "Failed to fetch search results"}
            parsed_data = parser.parse(content)

        formatted_data = formatter.format_response(query, parsed_data)

        result = {
            "query": query,
            "ai_overview": formatted_data["ai_overview"],
            "organic_results": formatted_data["organic_results"],
            "formatted_output": formatted_data["formatted_output"],
            "token_estimate": formatted_data["token_estimate"]
        }

        if output_format and output_format.lower() in ["vector", "vectors"]:
            snippets = [res.get("snippet", "") for res in result["organic_results"]]
            if snippets:
                vectors = embeddings_service.generate(snippets)
                for i, res in enumerate(result["organic_results"]):
                    if i < len(vectors):
                         res["embedding"] = vectors[i]

        # Save to Database
        try:
            # Initialize DB tables (ensure they exist)
            loop.run_until_complete(init_db())
            
            async def _save():
                async with AsyncSessionLocal() as session:
                    await save_search_results(session, query, result["organic_results"])
            
            loop.run_until_complete(_save())
        except Exception as e:
            logger.error(f"Database save error: {e}")

        if result["organic_results"]:
            cache.set(query, result, region, language, limit)

        return result

    except Exception as e:
        print(f"Task failed: {e}")
        return {"error": str(e)}
