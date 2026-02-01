from bs4 import BeautifulSoup, Tag
from typing import Dict, List, Optional, Union, Union
import re
from app.utils.logger import logger

class ParserService:
    def parse(self, content: Union[str, Dict]) -> Dict:
        """
        Parses content to extract AI Overview and organic results.
        Handles both raw HTML (ScrapingBee/ZenRows) and structured JSON (Tavily).
        """
        # Case 1: Structured Data (Tavily)
        if isinstance(content, dict):
            # Map Tavily format
            organic_results = [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "snippet": self._clean_text(result.get("content")) # Clean noise
                }
                for result in content.get("results", [])
            ]
            
            return {
                "ai_overview": content.get("answer"),
                "organic_results": organic_results
            }

        # Case 2: Raw HTML (ScrapingBee/ZenRows/Direct)
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove known junk to clean up the DOM
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()

        return {
            "ai_overview": self._extract_ai_overview(soup),
            "organic_results": self._extract_organic_results(soup)
        }

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Removes common scraping noise like login prompts, cookie notices, and navigation text.
        """
        if not text:
            return None
            
        noise_patterns = [
            # LinkedIn / Social Walls
            r"Create your free account or sign in",
            r"New to LinkedIn\? Join now",
            r"Sign in to view more content",
            r"agree to LinkedIn’s User Agreement",
            
            # Common Cookie/Nav junk
            r"See our Cookie Policy",
            r"Manage your preferences",
            r"Skip to main content",
            r"Skip to top",
            r"Download chart",
            
            # Generic Actions
            r"Share on Twitter",
            r"Share on Facebook",
            r"Open the app",
            r"Click here to subscribe",
            r"Subscribe to our newsletter",
            
            # Legal / Footer
            r"All rights reserved",
            r"Terms of Service",
            r"Privacy Policy",
            r"Copyright \u00a9 \d{4}",
            r"Copyright\s+[-–]\s+.*?[\d{4}]", # "Copyright - Site 2026"
            
            # Content Gating / Ads
            r"Advertisement",
            r"Sponsored Content",
            r"Read more",
            r"Continue reading",
            r"Subscriber only",
            
            # Social / App Prompts (Markdown & Text)
            r"Follow .*? on WhatsApp",
            r"Download the .*? app",
            r"Join .*? channel",
            
            # Markdown specific noise
            r"!\[.*?Logo.*?\]\(.*?\)",  # Images with 'Logo' in alt text
            r"!\[.*?representational.*?\]\(.*?\)", # Generic stock images
            r"## Related Stories",
            r"\*\*\[.*?\]\(.*?\)\*\*" # Aggressive: Remove bolded links typically used for CTAs at bottom
        ]
        
        cleaned_text = text
        for pattern in noise_patterns:
            # Case insensitive replacement
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
            
        # Clean up extra whitespace created by deletions
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return cleaned_text

    def parse_url_content(self, content: Union[str, Dict]) -> Dict:
        """
        Parses content from a specific URL (scraped/extracted).
        """
        # Case 1: Structured Data (Tavily Extract)
        if isinstance(content, dict):
            return {
                "ai_overview": None,
                "organic_results": [{
                    "title": "Extracted Content",
                    "url": content.get("url", ""),
                    "snippet": self._clean_text(content.get("content") or content.get("raw_content", ""))
                }]
            }
            
        # Case 2: Raw HTML (ScrapingBee/ZenRows/Direct)
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove known junk
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()
            
        # Basic text extraction
        text = soup.get_text(separator=' ', strip=True)
        # Apply cleaner
        cleaned_text = self._clean_text(text)
        
        return {
            "ai_overview": None,
            "organic_results": [{
                "title": soup.title.string if soup.title else "Scraped Page",
                "url": "", # We don't have the URL here in content, handled by caller if needed
                "snippet": cleaned_text[:10000] # Cap output length
            }]
        }

    def _extract_ai_overview(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Heuristic: Look for a dense block of text near the top that isn't a standard result.
        Often contains multiple paragraphs and 'Generative AI' or 'Overview' indicators.
        """
        # Strategy 1: Look for semantic markers if they exist (rare in raw HTML but worth a shot)
        # Strategy 2: Top-heavy dense text block detection
        
        body = soup.find('body')
        if not body:
            return None

        # Iterate through top-level containers
        # We are looking for a container that has substantial text length but low link density compared to regular results
        
        candidates = []
        
        # Traversing first few substantial children
        for child in body.find_all(recursive=False):
            if not isinstance(child, Tag):
                continue
                
            text = child.get_text(strip=True)
            if len(text) < 100:
                continue
                
            # Check for AI signal words in the container's rough text
            if re.search(r"(AI Overview|Generative AI|Summarized by AI)", text, re.IGNORECASE):
                return self._clean_text(text)
            
            # Density Check: High text count, identifying it as a potential summary
            # Simple heuristic score: length of text
            candidates.append((len(text), text))

        # If we found explicit markers, we returned.
        # Otherwise, if we have a very large block at position 0 or 1 that doesn't look like a link list, take it.
        # This is risky without specific DOM signatures, so we'll be conservative.
        
        # Improved Heuristic: Search for the block *immediately* preceding the first organic result
        # (This depends on _extract_organic_results logic implicitly, but let's do independent scan logic)
        
        return None  # Return None if no strong signal found to avoid false positives

    def _extract_organic_results(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Anchor & Pivot Logic:
        1. Find <a> tags that contain <h3> or <h4> (the Title).
        2. From that <a>, pivot up to the result container.
        3. Extract snippet from the container's text, excluding the title/url.
        """
        results = []
        seen_urls = set()

        # Find all link titles (h3 is standard for Google, Bing, etc.)
        title_tags = soup.find_all('h3')
        
        for h3 in title_tags:
            # Find parent anchor
            a_tag = h3.find_parent('a')
            if not a_tag:
                continue
                
            href = a_tag.get('href', '')
            
            # Clean generic google redirect/tracking trash if present
            url = self._clean_url(href)
            
            if not url or url.startswith('/') or url in seen_urls:
                continue
            
            # Filter ads based on simple heuristics
            # If the container has "Ad" marker or strange URL pattern
            if "googleadservices" in url:
                continue

            seen_urls.add(url)
            
            title = h3.get_text(strip=True)
            
            # Pivot: Get snippet
            # Usually snippet is in a div following the link, or inside a parent container
            snippet = ""
            
            # Attempt 1: Look at parent container text, subtracting title/url
            # Iterate up maximum 2-3 levels to find a container that wraps the whole result
            container = a_tag.parent
            for _ in range(3):
                if container and container.name == 'div':
                    # Check if this container looks like "the result block"
                    if len(container.get_text()) > len(title) + 20: 
                        break
                if container.parent:
                    container = container.parent
            
            if container:
                # Naive text extraction: remove title, get remaining text
                full_text = container.get_text(" ", strip=True)
                # Simple string replace of title to try and isolate snippet
                snippet = full_text.replace(title, "").replace(url, "").strip()
                # Truncate clean up
                snippet = " ".join(snippet.split())
            
            # Basic validation
            if title and url:
                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet[:300] + "..." if len(snippet) > 300 else snippet
                })
                
        return results

    def _clean_url(self, href: str) -> Optional[str]:
        if not href:
            return None
        # Handle '/url?q=...' format
        if href.startswith('/url?q='):
            match = re.search(r'q=([^&]+)', href)
            if match:
                return urllib.parse.unquote(match.group(1))
        return href



parser = ParserService()
