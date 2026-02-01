from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.api.schemas import SearchRequest, SearchResponse
from app.services.scraper import scraper
from app.services.parser import parser
from app.services.formatter import formatter
from app.utils.cache import cache
from app.utils.logger import logger

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    try:
        # Check Cache
        cached_data = cache.get(request.query, request.region, request.language)
        if cached_data:
            return SearchResponse(**cached_data, cached=True)

        if request.mode == "scrape":
            # Direct URL Scraping
            content = await scraper.scrape_url(request.query)
            if not content:
                raise HTTPException(status_code=500, detail="Failed to scrape URL")
            parsed_data = parser.parse_url_content(content)
            # Inject URL if missing from parser (for HTML case)
            if parsed_data["organic_results"] and not parsed_data["organic_results"][0]["url"]:
                parsed_data["organic_results"][0]["url"] = request.query
        else:
            # Standard Search
            content = await scraper.fetch_results(request.query, request.region, request.language)
            if not content:
                raise HTTPException(status_code=500, detail="Failed to fetch search results")
            parsed_data = parser.parse(content)
        
        # Format
        formatted_data = formatter.format_response(request.query, parsed_data)
        
        # Prepare Response Data
        response_data = {
            "query": request.query,
            "ai_overview": formatted_data["ai_overview"],
            "organic_results": formatted_data["organic_results"],
            "formatted_output": formatted_data["formatted_output"],
            "token_estimate": formatted_data["token_estimate"]
        }
        
        # Cache Result (only if we have results)
        if response_data["organic_results"]:
            cache.set(request.query, response_data, request.region, request.language)

        return SearchResponse(**response_data, cached=False)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
