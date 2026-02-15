import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from app.worker import scrape_task, embed_task
from app.services.parser import parser

class TestCoverageImprovements:
    
    @patch("app.worker.scraper")
    @patch("app.worker.parser")
    @patch("app.worker.formatter")
    @patch("app.worker.embeddings_service")
    @patch("app.worker.cache")
    @patch("asyncio.get_event_loop")
    def test_worker_loop_creation_runtime_error(
        self, mock_get_loop, mock_cache, mock_embeddings, mock_formatter, mock_parser, mock_scraper
    ):
        """Test that worker creates a new loop if get_event_loop raises RuntimeError"""
        mock_get_loop.side_effect = RuntimeError("No event loop")
        mock_cache.get.return_value = None
        
        # We need to mock asyncio.new_event_loop and set_event_loop to avoid actually messing with the test runner's loop
        with patch("asyncio.new_event_loop") as mock_new_loop, \
             patch("asyncio.set_event_loop") as mock_set_loop:
            
            mock_loop_instance = MagicMock()
            mock_new_loop.return_value = mock_loop_instance
            
            # Mock the run_until_complete to return something so the task proceeds
            mock_loop_instance.run_until_complete.return_value = [{"title": "test"}]
            
            # Fix: mock parser to return valid structure to avoid downstream errors
            mock_parser.parse.return_value = {"ai_overview": None, "organic_results": []}
            mock_formatter.format_response.return_value = {
                "query": "test", "ai_overview": None, "organic_results": [], "formatted_output": "", "token_estimate": 0
            }

            try:
                scrape_task.apply(args=["test", "us", "en", 10, "search"]).get()
            except Exception:
                pass # We just want to verify loop creation logic
            
            mock_new_loop.assert_called_once()
            mock_set_loop.assert_called_with(mock_loop_instance)

    @patch("app.worker.embeddings_service")
    @patch("app.worker.init_db")
    @patch("app.worker.AsyncSessionLocal")
    @patch("app.worker.save_search_results")
    @patch("app.worker.logger")
    def test_embed_task_database_save_error(
        self, mock_logger, mock_save, mock_session, mock_init, mock_embeddings
    ):
        """Test that database save errors are logged and swallowed in embed_task"""
        result_input = {
            "query": "test", 
            "organic_results": [{"title": "test"}]
        }
        
        # Mock successful embedding generation
        mock_embeddings.generate.return_value = [[0.1, 0.2]]
        
        # Mock init_db to succeed
        mock_init_db_coro = AsyncMock()
        mock_init.return_value = mock_init_db_coro
        
        # Mock save_search_results to raise exception
        mock_save.side_effect = Exception("DB Save Failed")
        
        # We need to mock the loop behavior in embed_task or rely on the logic
        # The task uses: loop.run_until_complete(_save())
        # Since we are mocking save_search_results, we need to ensure it's called
        
        # Note: In the actual task, it creates a local async function `_save` and runs it.
        # We can simulate the exception bubbling up from `loop.run_until_complete`
        
        with patch("asyncio.get_event_loop") as mock_get_loop:
             mock_loop = MagicMock()
             mock_get_loop.return_value = mock_loop
             # First call is init_db, second is _save
             # We make the second call raise the exception
             mock_loop.run_until_complete.side_effect = [None, Exception("DB Save Failed")]
             
             res = embed_task.apply(args=[result_input, "us", "en", 10, "vector"]).get()
             
             assert res is not None
             # Verify logger error was called
             mock_logger.error.assert_called()
             assert "Database save error" in str(mock_logger.error.call_args)


    def test_parser_clean_url_redirect(self):
        """Test _clean_url logic for google redirects"""
        # We access the private method via the instance or helper if needed, 
        # but since it's used in _extract_organic_results, we can test it there or directly if accessible (it is in python)
        
        redirect_url = "/url?q=https://real-site.com&sa=U&ved=2ahUKEwj"
        cleaned = parser._clean_url(redirect_url)
        assert cleaned == "https://real-site.com"
        
        # Test None
        assert parser._clean_url(None) is None
        
        # Test normal url
        assert parser._clean_url("https://normal.com") == "https://normal.com"


    def test_traverse_up_logic_in_extract_organic(self):
        """Test the logic where it traverses up parents to find the container"""
        # Construct HTML where the A tag is deep
        from bs4 import BeautifulSoup
        html = """
        <div>
            <div class="result-container">
                This should be the snippet text extracted.
                <a href="/url?q=https://test.com">
                    <h3>Title</h3>
                </a>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        results = parser._extract_organic_results(soup)
        
        assert len(results) == 1
        assert results[0]["title"] == "Title"
        assert "snippet text extracted" in results[0]["snippet"]

    @patch("app.services.parser.trafilatura.extract")
    def test_parse_url_content_fallback(self, mock_extract):
        """Test fallback to BeautifulSoup when trafilatura returns None"""
        mock_extract.return_value = None
        
        html_content = "<html><body><p>Fallback content here</p></body></html>"
        
        result = parser.parse_url_content(html_content)
        
        assert result["organic_results"][0]["snippet"] == "Fallback content here"

    def test_parse_url_content_with_dict(self):
        """Test parse_url_content when content is a dictionary with raw_content"""
        content = {
            "url": "https://example.com/api",
            "raw_content": "<html><body><p>API Content</p></body></html>",
            "content": None
        }
        
        result = parser.parse_url_content(content)
        
        assert len(result["organic_results"]) == 1
        assert result["organic_results"][0]["url"] == "https://example.com/api"
        assert "API Content" in result["organic_results"][0]["snippet"]
        assert result["organic_results"][0]["title"] == "Extracted Content"

    def test_scraper_is_valid_html(self):
        """Test the _is_valid_html method in ScraperService"""
        from app.services.scraper import scraper
        
        # Valid HTML
        assert scraper._is_valid_html("<html><body>Valid content</body></html>") is True
        
        # Invalid inputs
        assert scraper._is_valid_html(None) is False
        assert scraper._is_valid_html("") is False
        
        # Failure markers
        assert scraper._is_valid_html("Please click here if you are not redirected") is False
        assert scraper._is_valid_html("We have detected unusual traffic") is False
        assert scraper._is_valid_html("content... having trouble accessing Google Search ...content") is False
