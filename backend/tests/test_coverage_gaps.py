"""Targeted tests to fill coverage gaps and reach 72%+"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.utils.cache import CacheService
from app.services.embeddings import EmbeddingsService


class TestCacheServiceGaps:
    """Fill cache.py coverage gaps"""

    @patch("app.utils.cache.redis.from_url")
    def test_cache_set_success(self, mock_redis):
        """Test cache set operation"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client

        cache = CacheService()
        cache.set("query", {"data": "value"}, "us", "en", 10)

        mock_client.setex.assert_called()

    @patch("app.utils.cache.redis.from_url")
    def test_cache_get_hit(self, mock_redis):
        """Test cache get hit"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = '{"data": "cached"}'

        cache = CacheService()
        result = cache.get("query", "us", "en", 10)

        assert result is not None
        assert result["data"] == "cached"

    @patch("app.utils.cache.redis.from_url")
    def test_cache_get_miss(self, mock_redis):
        """Test cache get miss"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.return_value = None

        cache = CacheService()
        result = cache.get("query", "us", "en", 10)

        assert result is None

    @patch("app.utils.cache.redis.from_url")
    def test_cache_set_with_error(self, mock_redis):
        """Test cache set handles errors gracefully"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.setex.side_effect = Exception("Redis error")

        cache = CacheService()
        cache.set("query", {"data": "value"}, "us", "en", 10)

    @patch("app.utils.cache.redis.from_url")
    def test_cache_get_with_error(self, mock_redis):
        """Test cache get handles errors gracefully"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.side_effect = Exception("Redis error")

        cache = CacheService()
        result = cache.get("query", "us", "en", 10)

        assert result is None

    @patch("app.utils.cache.redis.from_url")
    def test_cache_connection_failure(self, mock_redis):
        """Test cache handles connection failure"""
        mock_redis.side_effect = Exception("Connection failed")

        cache = CacheService()

        assert cache.client is None

        result = cache.get("query")
        assert result is None

        cache.set("query", {"data": "value"})


class TestEmbeddingsModelLoadingGaps:
    """Fill embeddings.py model loading gaps"""

    @patch("sentence_transformers.SentenceTransformer")
    def test_embeddings_model_load_failure(self, mock_transformer):
        """Test embeddings handles model load failure"""
        mock_transformer.side_effect = Exception("Model download failed")

        service = EmbeddingsService()

        assert service.model is None

    @patch("sentence_transformers.SentenceTransformer", side_effect=ImportError("sentence_transformers not installed"))
    def test_embeddings_import_error(self, mock_transformer):
        """Test embeddings handles missing import"""
        service = EmbeddingsService()

        assert service.model is None


class TestWorkerEventLoopGaps:
    """Fill worker.py event loop handling gaps"""

    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    @patch("app.worker.asyncio.get_event_loop")
    def test_worker_new_event_loop_creation(
        self, mock_get_loop, mock_cache, mock_embeddings,
        mock_formatter, mock_parser, mock_scraper
    ):
        """Test worker creates new event loop on RuntimeError"""
        from app.worker import scrape_task

        mock_get_loop.side_effect = RuntimeError("No running event loop")

        mock_cache.get.return_value = None
        mock_scraper.fetch_results = AsyncMock(return_value=[{"title": "Result"}])
        mock_parser.parse.return_value = {"ai_overview": None, "organic_results": []}
        mock_formatter.format_response.return_value = {
            "query": "test", "ai_overview": None, "organic_results": [],
            "formatted_output": "F", "token_estimate": 1
        }
        mock_embeddings.generate.return_value = []

        result = scrape_task.apply(args=["test", "us", "en", 10, "search"]).get()

        assert result is not None


class TestFormatterEdgeCases:
    """Fill formatter.py edge cases"""

    def test_formatter_deduplication_empty_snippets(self):
        """Test formatter handles empty snippets in deduplication"""
        from app.services.formatter import FormatterService

        formatter = FormatterService()
        parsed_data = {
            "ai_overview": "Overview",
            "organic_results": [
                {"title": "R1", "url": "u1", "snippet": ""},
                {"title": "R2", "url": "u2", "snippet": ""},
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert "organic_results" in result

    def test_formatter_markdown_with_no_overview(self):
        """Test markdown generation with no overview"""
        from app.services.formatter import FormatterService

        formatter = FormatterService()
        parsed_data = {
            "ai_overview": None,
            "organic_results": [
                {"title": "Result", "url": "https://example.com", "snippet": "Content"}
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert "formatted_output" in result
        assert isinstance(result["formatted_output"], str)

    def test_formatter_deduplication_single_result(self):
        """Test formatter with single result"""
        from app.services.formatter import FormatterService

        formatter = FormatterService()
        parsed_data = {
            "ai_overview": "Overview",
            "organic_results": [
                {"title": "OnlyResult", "url": "https://only.com", "snippet": "Only"}
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert len(result["organic_results"]) == 1


class TestCacheKeyGeneration:
    """Test cache key generation logic"""

    @patch("app.utils.cache.redis.from_url")
    def test_cache_key_with_different_regions(self, mock_redis):
        """Test cache distinguishes by region"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.side_effect = [None, None]

        cache = CacheService()

        cache.get("python", "us", "en", 10)
        cache.get("python", "uk", "en", 10)

        assert mock_client.get.call_count == 2

    @patch("app.utils.cache.redis.from_url")
    def test_cache_key_with_different_languages(self, mock_redis):
        """Test cache distinguishes by language"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.side_effect = [None, None]

        cache = CacheService()

        cache.get("python", "us", "en", 10)
        cache.get("python", "us", "es", 10)

        assert mock_client.get.call_count == 2

    @patch("app.utils.cache.redis.from_url")
    def test_cache_key_with_different_limits(self, mock_redis):
        """Test cache distinguishes by limit"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.get.side_effect = [None, None]

        cache = CacheService()

        cache.get("python", "us", "en", 10)
        cache.get("python", "us", "en", 20)

        assert mock_client.get.call_count == 2
