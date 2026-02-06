import httpx
import os
import random
import urllib.parse
from typing import Optional, Union, Dict
from app.utils.logger import logger
from prometheus_client import Counter, Histogram
import time

from prometheus_client import Counter, Histogram
import time

SCRAPE_REQUESTS = Counter(
    "flux_scrape_requests_total",
    "Total number of scrape requests",
    ["provider", "status"]
)

SCRAPE_DURATION = Histogram(
    "flux_scrape_duration_seconds",
    "Histogram of scrape duration",
    ["provider"]
)

SCRAPE_DURATION = Histogram(
    "flux_scrape_duration_seconds",
    "Histogram of scrape duration",
    ["provider"]
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

class ScraperService:
    def __init__(self):
        self.scrapingbee_key = os.getenv("SCRAPINGBEE_API_KEY")
        self.zenrows_key = os.getenv("ZENROWS_API_KEY")
        self.tavily_key = os.getenv("TAVILY_API_KEY")

        if not any([self.scrapingbee_key, self.zenrows_key, self.tavily_key]):
            logger.warning("No scraping API keys found in environment variables")

    async def _fetch_tavily_extract(self, url: str) -> Optional[Dict]:
        start_time = time.time()
        try:
            logger.info("Attempting Tavily Extract...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/extract",
                    json={
                        "api_key": self.tavily_key,
                        "urls": [url],
                        "include_images": False
                    }
                )
                duration = time.time() - start_time
                SCRAPE_DURATION.labels(provider="tavily_extract").observe(duration)

                if response.status_code == 200:
                    SCRAPE_REQUESTS.labels(provider="tavily_extract", status="success").inc()
                    data = response.json()
                    if data.get("results"):
                        return data["results"][0]
                
                SCRAPE_REQUESTS.labels(provider="tavily_extract", status="error").inc()
                logger.warning(f"Tavily Extract failed with status {response.status_code}: {response.text}")
        except Exception as e:
            SCRAPE_REQUESTS.labels(provider="tavily_extract", status="exception").inc()
            logger.error(f"Tavily Extract error: {e}")
        return None

    async def _fetch_tavily(self, query: str, limit: int = 10) -> Optional[Dict]:
        start_time = time.time()
        try:
            logger.info(f"Attempting Tavily fetch with limit={limit}...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True,
                        "include_images": False,
                        "max_results": limit
                    }
                )
                duration = time.time() - start_time
                SCRAPE_DURATION.labels(provider="tavily_search").observe(duration)

                if response.status_code == 200:
                    SCRAPE_REQUESTS.labels(provider="tavily_search", status="success").inc()
                    return response.json()
                
                SCRAPE_REQUESTS.labels(provider="tavily_search", status="error").inc()
                logger.warning(f"Tavily failed with status {response.status_code}: {response.text}")
        except Exception as e:
            SCRAPE_REQUESTS.labels(provider="tavily_search", status="exception").inc()
            logger.error(f"Tavily error: {e}")
        return None

    async def scrape_url(self, url: str) -> Optional[Union[str, Dict]]:
        if self.tavily_key:
            data = await self._fetch_tavily_extract(url)
            if data: return data

        # Priority 2: Standard Scrapers (return HTML)
        html = None
        if self.scrapingbee_key:
            html = await self._fetch_scrapingbee(url)
        
        if not html and self.zenrows_key:
            html = await self._fetch_zenrows(url)
            
        if not html:
            html = await self._fetch_direct(url)
            
        return html

    async def fetch_results(self, query: str, region: str = "us", language: str = "en", limit: int = 10) -> Optional[Union[str, Dict]]:
        params = {"q": query, "gl": region, "hl": language, "num": limit}
        search_url = f"https://www.google.com/search?{urllib.parse.urlencode(params)}"
        
        if self.tavily_key:
            data = await self._fetch_tavily(query, limit)
            if data: return data

        html = None
        
        debug_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "debug.html")
        
        if self.scrapingbee_key:
            html = await self._fetch_scrapingbee(search_url)
            if html and self._is_valid_html(html): return html
            
        if self.zenrows_key:
            html = await self._fetch_zenrows(search_url)
            if html and self._is_valid_html(html): return html
            
        res = await self._fetch_direct(search_url)
        
        final_html = html if html else res
        if final_html:
            try:
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(final_html)
                logger.info(f"Saved debug HTML to {debug_path}")
            except Exception as e:
                logger.error(f"Failed to save debug HTML: {e}")
                
        return final_html

    async def _fetch_scrapingbee(self, url: str) -> Optional[str]:
        start_time = time.time()
        try:
            logger.info("Attempting ScrapingBee fetch...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    "https://app.scrapingbee.com/api/v1/",
                    params={
                        "api_key": self.scrapingbee_key,
                        "url": url, 
                        "render_js": "true",
                        "premium_proxy": "true",
                        "stealth_proxy": "true",
                        "block_resources": "false",
                        "country_code": "us",
                        "device": "desktop"
                    }
                )
                duration = time.time() - start_time
                SCRAPE_DURATION.labels(provider="scrapingbee").observe(duration)

                if response.status_code == 200:
                    SCRAPE_REQUESTS.labels(provider="scrapingbee", status="success").inc()
                    return response.text
                
                SCRAPE_REQUESTS.labels(provider="scrapingbee", status="error").inc()
                logger.warning(f"ScrapingBee failed with status {response.status_code}")
        except Exception as e:
            SCRAPE_REQUESTS.labels(provider="scrapingbee", status="exception").inc()
            logger.error(f"ScrapingBee error: {e}")
        return None

    async def _fetch_zenrows(self, url: str) -> Optional[str]:
        start_time = time.time()
        try:
            logger.info("Attempting ZenRows fetch...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    "https://api.zenrows.com/v1/",
                    params={
                        "apikey": self.zenrows_key,
                        "url": url, 
                        "js_render": "true",
                        "premium_proxy": "true",
                        "antibot": "true",
                        "location": "United States"
                    }
                )
                duration = time.time() - start_time
                SCRAPE_DURATION.labels(provider="zenrows").observe(duration)

                if response.status_code == 200:
                    SCRAPE_REQUESTS.labels(provider="zenrows", status="success").inc()
                    return response.text
                
                SCRAPE_REQUESTS.labels(provider="zenrows", status="error").inc()
                logger.warning(f"ZenRows failed with status {response.status_code}")
        except Exception as e:
            SCRAPE_REQUESTS.labels(provider="zenrows", status="exception").inc()
            logger.error(f"ZenRows error: {e}")
        return None

    async def _fetch_direct(self, url: str) -> Optional[str]:
        try:
            logger.info("Attempting direct fetch fallback...")
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    if "captcha" in response.text.lower():
                        logger.warning("Direct fetch encountered CAPTCHA")
                        return None
                    return response.text
                logger.warning(f"Direct fetch failed with status {response.status_code}")
        except Exception as e:
            logger.error(f"Direct fetch error: {e}")
        return None

    def _is_valid_html(self, html: str) -> bool:
        if not html:
            return False
        
        if not html:
            return False
        
        failure_markers = [
            "Please click here if you are not redirected",
            "having trouble accessing Google Search",
            "detected unusual traffic",
            "Our systems have detected unusual traffic"
        ]
        
        for marker in failure_markers:
            if marker in html:
                logger.warning(f"Detected invalid HTML with marker: {marker}")
                return False
                
        return True

scraper = ScraperService()
