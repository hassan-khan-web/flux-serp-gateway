import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from app.services.scraper import ScraperService


class TestScraperService:
    """Test ScraperService class"""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance with mocked API keys"""
        with patch.dict('os.environ', {
            'TAVILY_API_KEY': 'test-tavily-key',
            'SCRAPINGBEE_API_KEY': 'test-bee-key',
            'ZENROWS_API_KEY': 'test-zenrows-key'
        }):
            return ScraperService()

    @pytest.fixture
    def scraper_no_keys(self):
        """Create scraper instance with no API keys"""
        with patch.dict('os.environ', {}, clear=True):
            return ScraperService()

    def test_scraper_initialization_with_keys(self):
        """Test scraper initializes with API keys"""
        with patch.dict('os.environ', {
            'TAVILY_API_KEY': 'tavily-123',
            'SCRAPINGBEE_API_KEY': 'bee-456',
            'ZENROWS_API_KEY': ''
        }, clear=False):
            scraper = ScraperService()
            assert scraper.tavily_key == 'tavily-123'
            assert scraper.scrapingbee_key == 'bee-456'

    def test_scraper_initialization_no_keys(self):
        """Test scraper initializes without API keys"""
        with patch.dict('os.environ', {}, clear=True):
            with patch('app.services.scraper.logger.warning') as mock_warning:
                scraper = ScraperService()
                assert scraper.tavily_key is None
                mock_warning.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_tavily_success(self, scraper):
        """Test successful Tavily search"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Python Guide",
                    "url": "https://python.org",
                    "content": "Learn Python"
                }
            ],
            "answer": "Python is a programming language"
        }

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await scraper._fetch_tavily("python", limit=5)

            assert result is not None
            assert result["answer"] == "Python is a programming language"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_tavily_error(self, scraper):
        """Test Tavily error handling"""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = Exception("API error")

            with patch('app.services.scraper.logger.error') as mock_error:
                result = await scraper._fetch_tavily("query")

                assert result is None
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_tavily_timeout(self, scraper):
        """Test Tavily timeout handling"""
        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = asyncio.TimeoutError("Request timeout")

            with patch('app.services.scraper.logger.error') as mock_error:
                result = await scraper._fetch_tavily("query", limit=10)

                assert result is None
                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_tavily_failed_status(self, scraper):
        """Test Tavily failed status code"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with patch('app.services.scraper.logger.warning') as mock_warning:
                result = await scraper._fetch_tavily("query")

                assert result is None
                mock_warning.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_tavily_extract_success(self, scraper):
        """Test Tavily Extract API success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Article",
                    "content": "Full article content"
                }
            ]
        }

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await scraper._fetch_tavily_extract("https://example.com")

            assert result is not None
            assert result["title"] == "Article"

    @pytest.mark.asyncio
    async def test_fetch_tavily_extract_no_results(self, scraper):
        """Test Tavily Extract with no results"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await scraper._fetch_tavily_extract("https://example.com")

            assert result is None

    @pytest.mark.asyncio
    async def test_scrape_url_with_tavily(self, scraper):
        """Test scrape_url prefers Tavily Extract"""
        mock_extract_data = {"title": "Article", "content": "Content"}

        with patch.object(scraper, '_fetch_tavily_extract', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = mock_extract_data

            result = await scraper.scrape_url("https://example.com")

            assert result == mock_extract_data
            mock_extract.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_scrape_url_fallback_to_scrapingbee(self, scraper):
        """Test scrape_url falls back to ScrapingBee"""
        mock_html = "<html><body>Test HTML</body></html>"

        with patch.object(scraper, '_fetch_tavily_extract', new_callable=AsyncMock) as mock_extract:
            with patch.object(scraper, '_fetch_scrapingbee', new_callable=AsyncMock) as mock_bee:
                mock_extract.return_value = None
                mock_bee.return_value = mock_html

                result = await scraper.scrape_url("https://example.com")

                assert result == mock_html

    @pytest.mark.asyncio
    async def test_fetch_results_search_success(self, scraper):
        """Test fetch_results for search query"""
        mock_tavily_result = {
            "results": [
                {"title": "Result 1", "url": "https://one.com", "content": "Content 1"}
            ]
        }

        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = mock_tavily_result

            result = await scraper.fetch_results("python programming", limit=5)

            assert result == mock_tavily_result
            mock_tavily.assert_called_once_with("python programming", 5)

    @pytest.mark.asyncio
    async def test_fetch_results_with_region_and_language(self, scraper):
        """Test fetch_results respects region and language parameters"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            await scraper.fetch_results(
                "query",
                region="uk",
                language="es",
                limit=20
            )

            mock_tavily.assert_called_once_with("query", 20)

    @pytest.mark.asyncio
    async def test_fetch_results_network_error(self, scraper):
        """Test fetch_results handles network error"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            with patch.object(scraper, '_fetch_direct', new_callable=AsyncMock) as mock_direct:
                mock_tavily.side_effect = Exception("Network error")
                mock_direct.return_value = None


    @pytest.mark.asyncio
    async def test_fetch_results_rate_limit_handling(self, scraper):
        """Test fetch_results handles rate limiting (429 status)"""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"

        with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with patch('app.services.scraper.logger.warning') as mock_warning:
                result = await scraper._fetch_tavily("query")

                assert result is None
                mock_warning.assert_called()


class TestScraperEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.fixture
    def scraper(self):
        with patch.dict('os.environ', {'TAVILY_API_KEY': 'test'}):
            return ScraperService()

    @pytest.mark.asyncio
    async def test_empty_query(self, scraper):
        """Test scraper with empty query string"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            result = await scraper.fetch_results("")

            mock_tavily.assert_called_once()

    @pytest.mark.asyncio
    async def test_very_long_query(self, scraper):
        """Test scraper with very long query"""
        long_query = "python " * 1000
        
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            result = await scraper.fetch_results(long_query)

            mock_tavily.assert_called_once()

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self, scraper):
        """Test scraper with special characters"""
        query = "python @"
        
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            result = await scraper.fetch_results(query)

            mock_tavily.assert_called_once()

    @pytest.mark.asyncio
    async def test_limit_zero(self, scraper):
        """Test with limit=0"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            await scraper.fetch_results("query", limit=0)

            mock_tavily.assert_called_once()

    @pytest.mark.asyncio
    async def test_limit_very_large(self, scraper):
        """Test with very large limit"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            await scraper.fetch_results("query", limit=10000)

            mock_tavily.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, scraper):
        """Test concurrent scraper requests"""
        with patch.object(scraper, '_fetch_tavily', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = {"results": []}

            tasks = [
                scraper.fetch_results(f"query{i}") for i in range(5)
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert mock_tavily.call_count == 5
