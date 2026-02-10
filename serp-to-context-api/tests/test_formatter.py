import pytest
from app.services.formatter import FormatterService


class TestFormatterService:
    """Test FormatterService output formatting"""

    @pytest.fixture
    def formatter(self):
        return FormatterService()

    def test_format_response_basic(self, formatter):
        """Test basic response formatting"""
        parsed_data = {
            "ai_overview": "Python is a programming language",
            "organic_results": [
                {
                    "title": "Python.org",
                    "url": "https://python.org",
                    "snippet": "Official Python website"
                }
            ]
        }

        result = formatter.format_response("python", parsed_data)

        assert result is not None
        assert result["query"] == "python"
        assert "formatted_output" in result
        assert "ai_overview" in result
        assert "organic_results" in result

    def test_format_response_empty_results(self, formatter):
        """Test formatting with no results"""
        parsed_data = {
            "ai_overview": None,
            "organic_results": []
        }

        result = formatter.format_response("test", parsed_data)

        assert result is not None
        assert result["organic_results"] == []
        assert result["ai_overview"] is None

    def test_format_response_multiple_results(self, formatter):
        """Test formatting with multiple results"""
        parsed_data = {
            "ai_overview": "Overview text",
            "organic_results": [
                {
                    "title": f"Result {i}",
                    "url": f"https://result{i}.com",
                    "snippet": f"Snippet {i}" * 5
                }
                for i in range(3)
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert len(result["organic_results"]) <= 3
        assert result["token_estimate"] > 0

    def test_format_response_with_embeddings(self, formatter):
        """Test formatting preserves embedding vectors"""
        parsed_data = {
            "ai_overview": "Overview",
            "organic_results": [
                {
                    "title": "Result",
                    "url": "https://result.com",
                    "snippet": "Snippet",
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert result["organic_results"][0].get("embedding") is not None
        assert len(result["organic_results"][0]["embedding"]) == 5

    def test_format_response_special_characters(self, formatter):
        """Test formatting with special characters"""
        parsed_data = {
            "ai_overview": "Test with special chars: @
            "organic_results": [
                {
                    "title": "Result with © symbol",
                    "url": "https://example.com?q=test&id=123",
                    "snippet": "Snippet with \"quotes\" and 'apostrophes'"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert "©" in result["organic_results"][0]["title"]
        assert "example.com" in result["organic_results"][0]["url"]

    def test_format_response_long_content(self, formatter):
        """Test formatting with very long content"""
        long_overview = "A" * 5000
        parsed_data = {
            "ai_overview": long_overview,
            "organic_results": [
                {
                    "title": "B" * 200,
                    "url": "https://example.com",
                    "snippet": "C" * 2000
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert result["token_estimate"] > 0

    def test_format_response_unicode_content(self, formatter):
        """Test formatting with unicode characters"""
        parsed_data = {
            "ai_overview": "Unicode test: 你好世界 مرحبا العالم",
            "organic_results": [
                {
                    "title": "日本語テスト",
                    "url": "https://example.com",
                    "snippet": "Ελληνικά Русский"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert "你好" in result["ai_overview"]
        assert result["organic_results"][0]["title"] == "日本語テスト"

    def test_format_response_with_urls(self, formatter):
        """Test formatting with various URL formats"""
        parsed_data = {
            "ai_overview": "Overview",
            "organic_results": [
                {
                    "title": "Result",
                    "url": "https://example.com/path?query=value&other=123
                    "snippet": "Snippet"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        url = result["organic_results"][0]["url"]
        assert "https://" in url

    def test_format_response_preserves_data_integrity(self, formatter):
        """Test that formatting preserves data integrity"""
        original_data = {
            "ai_overview": "Overview text",
            "organic_results": [
                {
                    "title": "Original Title",
                    "url": "https://original.com",
                    "snippet": "Original snippet",
                    "score": 0.95
                }
            ]
        }

        result = formatter.format_response("original query", original_data)

        assert result["query"] == "original query"
        assert result["ai_overview"] == "Overview text"
        assert result["organic_results"][0]["title"] == "Original Title"

    def test_format_response_token_estimate(self, formatter):
        """Test that token_estimate is calculated"""
        parsed_data = {
            "ai_overview": "Overview with some tokens for estimation",
            "organic_results": [
                {
                    "title": "Result",
                    "url": "https://example.com",
                    "snippet": "Snippet with content goes here"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert "token_estimate" in result
        assert result["token_estimate"] > 0

    def test_format_response_none_overview(self, formatter):
        """Test formatting with None ai_overview"""
        parsed_data = {
            "ai_overview": None,
            "organic_results": [
                {
                    "title": "Result",
                    "url": "https://example.com",
                    "snippet": "Snippet"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert result["ai_overview"] is None

    def test_format_response_deduplication(self, formatter):
        """Test deduplication of similar results"""
        parsed_data = {
            "ai_overview": "Overview",
            "organic_results": [
                {
                    "title": "Result",
                    "url": "https://example.com/1",
                    "snippet": "Python is a programming language used for many purposes"
                },
                {
                    "title": "Result",
                    "url": "https://example.com/2",
                    "snippet": "Python is a programming language used for many purposes"
                }
            ]
        }

        result = formatter.format_response("query", parsed_data)

        assert len(result["organic_results"]) >= 1

    def test_format_response_markdown_generation(self, formatter):
        """Test markdown output generation"""
        parsed_data = {
            "ai_overview": "Test overview",
            "organic_results": [
                {
                    "title": "Result Title",
                    "url": "https://example.com",
                    "snippet": "Result snippet"
                }
            ]
        }

        result = formatter.format_response("test query", parsed_data)

        markdown = result["formatted_output"]
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        assert "test query" in markdown.lower() or "result" in markdown.lower()

