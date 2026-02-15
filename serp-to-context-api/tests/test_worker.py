import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.worker import scrape_task, embed_task
from app.worker import celery_app
import celery.exceptions
import httpx


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

    def test_scrape_task_search_mode(
        self, mock_session, mock_init, mock_cache, mock_save, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_task in search mode"""
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

        result = scrape_task.apply(args=["python", "us", "en", 10, "search"]).get()

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

    def test_scrape_task_scrape_mode(
        self, mock_session, mock_init, mock_cache, mock_save, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_task in scrape mode"""
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

        result = scrape_task.apply(args=["https://example.com", "us", "en", 10, "scrape"]).get()

        assert result is not None
        assert "organic_results" in result

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    def test_scrape_task_cached_result(
        self, mock_cache, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_task returns cached result"""
        cached_result = {"query": "python", "cached": True}
        mock_cache.get.return_value = cached_result

        result = scrape_task.apply(args=["python", "us", "en", 10, "search"]).get()

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

    def test_embed_task_with_vectors(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test embed_task with vector output"""
        # Input result from step 1
        input_result = {
             "query": "test",
             "organic_results": [{"title": "Result", "snippet": "Snippet text"}]
        }

        mock_embeddings.generate.return_value = [[0.1, 0.2, 0.3, 0.4, 0.5]]

        mock_init_db = AsyncMock()
        mock_init.side_effect = lambda: mock_init_db()

        result = embed_task.apply(args=[input_result, "us", "en", 10, "vector"]).get()

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

    def test_scrape_task_error_handling(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_task error handling"""
        mock_cache.get.side_effect = Exception("Cache error")

        # Verify that the exception propagates (so Celery can handle it/fail the task)
        with pytest.raises(Exception, match="Cache error"):
            scrape_task.apply(args=["test", "us", "en", 10, "search"]).get()

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    def test_scrape_task_fetch_fails(
        self, mock_cache, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test scrape_task when fetch returns None"""
        mock_cache.get.return_value = None
        mock_scraper.fetch_results = AsyncMock(return_value=None)

        # Verify that the task retries (Celery raises Retry exception locally)
        with pytest.raises(celery.exceptions.Retry):
            scrape_task.apply(args=["test", "us", "en", 10, "search"]).get()

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.save_search_results")
    @patch("app.worker.cache")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")

    def test_embed_task_database_error_logged(
        self, mock_session, mock_init, mock_cache, mock_save,
        mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test embed_task logs database errors"""
        input_result = {
             "query": "test",
             "organic_results": [{"title": "Result", "snippet": "Snippet text"}]
        }

        mock_init_db = AsyncMock(side_effect=Exception("DB init error"))
        mock_init.side_effect = lambda: mock_init_db()

        result = embed_task.apply(args=[input_result, "us", "en", 10, "json"]).get()

        assert result is not None
        assert "organic_results" in result
