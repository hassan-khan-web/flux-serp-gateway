import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.scraper import ScraperService

class TestScraperCoverage:
    """Test ScraperService coverage gaps"""

    @pytest.fixture
    def scraper(self):
        with patch.dict('os.environ', {
            'TAVILY_API_KEY': 'test-tavily',
            'SCRAPINGBEE_API_KEY': 'test-bee',
            'ZENROWS_API_KEY': 'test-zenrows'
        }):
            return ScraperService()

    @pytest.mark.asyncio
    async def test_scrape_url_fallback_chain(self, scraper):
        """Test fallback: Tavily -> ScrapingBee -> ZenRows -> Direct"""
        
        # 1. Tavily fails
        with patch.object(scraper, '_fetch_tavily_extract', new_callable=AsyncMock) as mock_tavily:
            mock_tavily.return_value = None
            
            # 2. ScrapingBee fails
            with patch.object(scraper, '_fetch_scrapingbee', new_callable=AsyncMock) as mock_bee:
                mock_bee.return_value = None
                
                # 3. ZenRows fails
                with patch.object(scraper, '_fetch_zenrows', new_callable=AsyncMock) as mock_zenrows:
                    mock_zenrows.return_value = None
                    
                    # 4. Direct succeeds
                    with patch.object(scraper, '_fetch_direct', new_callable=AsyncMock) as mock_direct:
                        mock_direct.return_value = "<html>Direct Content</html>"
                        
                        result = await scraper.scrape_url("http://test.com")
                        
                        assert result == "<html>Direct Content</html>"
                        mock_tavily.assert_called_once()
                        mock_bee.assert_called_once()
                        mock_zenrows.assert_called_once()
                        mock_direct.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_scrapingbee_success(self, scraper):
        """Test successful ScrapingBee fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Bee Content</html>"
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await scraper._fetch_scrapingbee("http://test.com")
            
            assert result == "<html>Bee Content</html>"

    @pytest.mark.asyncio
    async def test_fetch_scrapingbee_failure(self, scraper):
        """Test failed ScrapingBee fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await scraper._fetch_scrapingbee("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_scrapingbee_exception(self, scraper):
        """Test ScrapingBee exception"""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection error")
            
            result = await scraper._fetch_scrapingbee("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_zenrows_success(self, scraper):
        """Test successful ZenRows fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>ZenRows Content</html>"
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await scraper._fetch_zenrows("http://test.com")
            
            assert result == "<html>ZenRows Content</html>"

    @pytest.mark.asyncio
    async def test_fetch_zenrows_failure(self, scraper):
        """Test failed ZenRows fetch"""
        mock_response = MagicMock()
        mock_response.status_code = 403
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await scraper._fetch_zenrows("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_zenrows_exception(self, scraper):
        """Test ZenRows exception"""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Timeout")
            
            result = await scraper._fetch_zenrows("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_direct_captcha(self, scraper):
        """Test Direct fetch detects CAPTCHA"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Please verify you are human (captcha)</html>"
        
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await scraper._fetch_direct("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_direct_exception(self, scraper):
        """Test Direct fetch exception"""
        with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            result = await scraper._fetch_direct("http://test.com")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_results_debug_html_saving(self, scraper):
        """Test that debug HTML is saved when fetch succeeds"""
        # Mock successful direct fetch
        with patch.object(scraper, '_fetch_tavily', return_value=None):
            with patch.object(scraper, '_fetch_scrapingbee', return_value=None):
                with patch.object(scraper, '_fetch_zenrows', return_value=None):
                    with patch.object(scraper, '_fetch_direct', return_value="<html>Debug Content</html>"):
                        
                        with patch('builtins.open', new_callable=MagicMock) as mock_open:
                             # Mock the file handle returned by open()
                            mock_file = MagicMock()
                            mock_open.return_value.__enter__.return_value = mock_file
                            
                            await scraper.fetch_results("query")
                            
                            # Verify file was opened for writing
                            mock_open.assert_called()
                            args, _ = mock_open.call_args
                            assert "debug.html" in args[0]
                            assert args[1] == "w"
                            
                            # Verify content was written
                            mock_file.write.assert_called_with("<html>Debug Content</html>")

    @pytest.mark.asyncio
    async def test_fetch_results_debug_html_error(self, scraper):
         """Test error handling during debug HTML saving"""
         with patch.object(scraper, '_fetch_tavily', return_value=None):
             with patch.object(scraper, '_fetch_direct', return_value="<html>Content</html>"):
                 with patch('builtins.open', side_effect=OSError("Permission denied")):
                     # Should not raise exception
                     await scraper.fetch_results("query")
