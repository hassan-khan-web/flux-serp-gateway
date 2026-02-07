import pytest
from app.services.parser import ParserService

class TestParserService:
    def test_clean_text_basic(self):
        """Test basic text cleaning functionality."""
        parser = ParserService()
        raw_text = "  Hello   World!  "
        assert parser._clean_text(raw_text) == "Hello World!"

    def test_clean_text_noise_removal(self):
        """Test removal of common noisy phrases."""
        parser = ParserService()
        noise = "Sign in to view more content\nActual content."
        assert parser._clean_text(noise) == "Actual content."

    def test_calculate_credibility(self):
        """Test credibility score calculation."""
        parser = ParserService()
        assert parser._calculate_credibility("https://arxiv.org/abs/1234") == 1.0
        assert parser._calculate_credibility("https://unknown-site.com") == 0.5
        assert parser._calculate_credibility("https://medium.com/post") == 0.4

    def test_parse_minimal_content(self, minimal_html_content):
        """Test parsing of a known minimal HTML structure."""
        parser = ParserService()
        result = parser.parse(minimal_html_content)
        
        # Check structure
        assert "organic_results" in result
        assert "ai_overview" in result
        
        results = result["organic_results"]
        # We expect at least one result from our minimal HTML (the "Test Result Title")
        # The "Ad Result" should be filtered out.
        assert len(results) >= 1
        
        first_result = results[0]
        assert first_result["title"] == "Test Result Title"
        assert first_result["url"] == "https://example.com/result"
        assert "snippet" in first_result

    def test_parse_real_debug_html(self, mock_html_content):
        """
        Test parsing of the actual saved debug.html.
        Even if it returns 0 results (because it's a captcha page),
        it should NOT crash.
        """
        parser = ParserService()
        # This shouldn't raise an exception
        result = parser.parse(mock_html_content)
        
        assert isinstance(result, dict)
        assert "organic_results" in result
