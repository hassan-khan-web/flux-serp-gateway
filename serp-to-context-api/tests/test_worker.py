import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.worker import scrape_and_process


class TestWorkerTask:
    """Test Celery worker tasks"""

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    def test_scrape_and_process_search_mode(
        self, mock_session, mock_init, mock_cache, mock_save, 
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process in search mode"""
        mock_cache.get.return_value = None
        
        mock_scraper.fetch_results = AsyncMock(return_value=[
            {"title": "Result", "url": "https://result.com", "snippet": "Test"}
        ])
        
        mock_parser.parse.return_value = {
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result", "url": "https://result.com", "snippet": "Test"}]
        }
        
        mock_formatter.format_response.return_value = {
            "query": "test",
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result", "url": "https://result.com"}],
            "formatted_output": "Formatted",
            "token_estimate": 100
        }
        
        mock_embeddings.generate.return_value = [[0.1, 0.2, 0.3]]
        
        mock_init_db = AsyncMock()
        mock_init.side_effect = lambda: mock_init_db()
        
        result = scrape_and_process("python", "us", "en", 10, "search", "json")
        
        assert result is not None
        assert "organic_results" in result
        assert result["query"] == "python"

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    def test_scrape_and_process_scrape_mode(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process in scrape mode"""
        mock_cache.get.return_value = None
        
        mock_scraper.scrape_url = AsyncMock(return_value="<html>content</html>")
        
        mock_parser.parse_url_content.return_value = {
            "ai_overview": "Scraped",
            "organic_results": [{"title": "Scraped", "url": "https://example.com"}]
        }
        
        mock_formatter.format_response.return_value = {
            "query": "https://example.com",
            "ai_overview": "Scraped",
            "organic_results": [{"title": "Scraped", "url": "https://example.com"}],
            "formatted_output": "Formatted",
            "token_estimate": 50
        }
        
        mock_embeddings.generate.return_value = [[0.1, 0.2]]
        
        mock_init_db = AsyncMock()
        mock_init.side_effect = lambda: mock_init_db()
        
        result = scrape_and_process("https://example.com", "us", "en", 10, "scrape", "json")
        
        assert result is not None
        assert "organic_results" in result

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    def test_scrape_and_process_cached_result(
        self, mock_cache, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process returns cached result"""
        cached_result = {"query": "python", "cached": True}
        mock_cache.get.return_value = cached_result
        
        result = scrape_and_process("python", "us", "en", 10, "search", "json")
        
        assert result == cached_result
        mock_scraper.fetch_results.assert_not_called()

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    def test_scrape_and_process_with_vectors(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process with vector output"""
        mock_cache.get.return_value = None
        
        mock_scraper.fetch_results = AsyncMock(return_value=[
            {"title": "Result", "snippet": "Snippet text"}
        ])
        
        mock_parser.parse.return_value = {
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result", "snippet": "Snippet text"}]
        }
        
        mock_formatter.format_response.return_value = {
            "query": "test",
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result", "snippet": "Snippet text"}],
            "formatted_output": "Formatted",
            "token_estimate": 100
        }
        
        mock_embeddings.generate.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]
        
        mock_init_db = AsyncMock()
        mock_init.side_effect = lambda: mock_init_db()
        
        result = scrape_and_process("test", "us", "en", 10, "search", "vector")
        
        assert result is not None
        assert result["organic_results"][0].get("embedding") is not None

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    def test_scrape_and_process_error_handling(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process error handling"""
        mock_cache.get.side_effect = Exception("Cache error")
        
        result = scrape_and_process("test", "us", "en", 10, "search", "json")
        
        assert "error" in result

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    def test_scrape_and_process_fetch_fails(
        self, mock_cache, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process when fetch returns None"""
        mock_cache.get.return_value = None
        mock_scraper.fetch_results = AsyncMock(return_value=None)
        
        result = scrape_and_process("test", "us", "en", 10, "search", "json")
        
        assert result is not None
        assert "error" in result

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    def test_scrape_and_process_database_error_logged(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_and_process logs database errors"""
        mock_cache.get.return_value = None
        
        mock_scraper.fetch_results = AsyncMock(return_value=[
            {"title": "Result"}
        ])
        
        mock_parser.parse.return_value = {
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result"}]
        }
        
        mock_formatter.format_response.return_value = {
            "query": "test",
            "ai_overview": "Overview",
            "organic_results": [{"title": "Result"}],
            "formatted_output": "Formatted",
            "token_estimate": 100
        }
        
        mock_init_db = AsyncMock(side_effect=Exception("DB init error"))
        mock_init.side_effect = lambda: mock_init_db()
        
        result = scrape_and_process("test", "us", "en", 10, "search", "json")
        
        assert result is not None
        assert "organic_results" in result
