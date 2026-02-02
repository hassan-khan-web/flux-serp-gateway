from bs4 import BeautifulSoup, Tag
from typing import Dict, List, Optional, Union, Union
import re
import trafilatura
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
                    "snippet": self._clean_text(result.get("content")), # Clean noise
                    "score": self._calculate_credibility(result.get("url")) # Calculate score
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
            r"We'd love you to become a subscriber",
            r"Start your free trial",
            
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
            
            # News Tickers / Meta
            r"News • .*? \d{1,2}:\d{2} [AP]M ET",  # "News • Feb. 1, 2026, 3:18 PM ET"
            r"Updated: .*? \d{4}",
            r"\d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} [AP]M",
            
            # Social / App Prompts (Markdown & Text)
            r"Follow .*? on WhatsApp",
            r"Download the .*? app",
            r"Join .*? channel",
            
            # Markdown specific noise
            r"!\[.*?Logo.*?\]\(.*?\)",  # Images with 'Logo' in alt text
            r"!\[.*?representational.*?\]\(.*?\)", # Generic stock images
            r"Credit:.*", # "Credit: incamerastock..."
            r"Image:.*",
            r"Source:.*",
            r"## Related Stories",
            r"## Want to \?",
            r"## Click below to access",
            r"\*\*\[.*?\]\(.*?\)\*\*" # Aggressive: Remove bolded links typically used for CTAs at bottom
        ]
        

        
        # 1. Regex Cleaning (Marketing/Noise Removal)
        cleaned_text = text
        for pattern in noise_patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
            
        # 2. Strict Line Filtering (UI Phrases)
        # Filter whole lines if they contain specific "UI" keywords
        ui_phrases = ["Sign up", "Log in", "Login", "Get Started", "Subscribe", "Create account", "Continue reading"]
        lines = cleaned_text.split('\n')
        filtered_lines = []
        for line in lines:
            if any(phrase.lower() in line.lower() for phrase in ui_phrases):
                continue
            filtered_lines.append(line)
        cleaned_text = "\n".join(filtered_lines)

        # 3. Truncation Handling
        # If the text ends abruptly without punctuation, trim the last sentence fragment.
        # Check if the last character is not a sentence ender (., !, ?)
        cleaned_text = cleaned_text.strip()
        if cleaned_text and cleaned_text[-1] not in ['.', '!', '?', '"', "'", ')']:
            # Find the last sentence boundary
            last_period = max(cleaned_text.rfind('.'), cleaned_text.rfind('!'), cleaned_text.rfind('?'))
            if last_period != -1:
                cleaned_text = cleaned_text[:last_period+1]
            # If no punctuation at all, keep it as is (rare case) or discard if it looks like a fragment?
            # User said "discard or trim cleanly". Let's trim.

        # Clean up whitespace
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return cleaned_text

    def _calculate_credibility(self, url: str) -> float:
        """
        Calculates a credibility score based on the URL domain.
        ArXiv > Edu/Gov > Tech Docs > General > Low Quality
        """
        if not url:
            return 0.0
            
        url_lower = url.lower()
        
        # Tier 1: Gold Standard (1.0 - 0.9)
        if "arxiv.org" in url_lower: return 1.0
        if ".edu" in url_lower: return 0.95
        if ".gov" in url_lower: return 0.95
        if "nih.gov" in url_lower: return 0.95
        
        # Tier 2: Reputable Tech / Documentation (0.8 - 0.7)
        if "github.com" in url_lower: return 0.8
        if "github.io" in url_lower: return 0.8
        if "huggingface.co" in url_lower: return 0.8
        if "stackoverflow.com" in url_lower: return 0.75
        if "readthedocs.io" in url_lower: return 0.8
        if "python.org" in url_lower: return 0.85
        if "developer.mozilla.org" in url_lower: return 0.85
        if "nvidia.com" in url_lower: return 0.85
        if "acm.org" in url_lower: return 0.95 # Academic/Pro
        if "kaggle.com" in url_lower: return 0.75
        if "deepseek.com" in url_lower: return 0.85 # Official source for this query
        
        # Tier 3: Low Quality / Marketing / Paywalls (0.4 - 0.3)
        if "medium.com" in url_lower: return 0.4
        if "linkedin.com" in url_lower: return 0.3
        if "businessinsider" in url_lower: return 0.4
        if "forbes.com" in url_lower: return 0.4
        
        # Tier 4: General Web (0.5 Baseline)
        logger.info(f"Default score 0.5 assigned to: {url}")
        return 0.5

    def parse_url_content(self, content: Union[str, Dict]) -> Dict:
        """
        Parses content from a specific URL (scraped/extracted).
        """
        # Case 1: Structured Data (Tavily Extract)
        if isinstance(content, dict):
            # Try to use Trafilatura on raw content if available for consistency, otherwise fallback
            text_content = content.get("content") or content.get("raw_content", "")
            if content.get("raw_content"):
                 # If we have raw HTML, try to extract better text
                 extracted = trafilatura.extract(content["raw_content"])
                 if extracted:
                     text_content = extracted
            
            # Apply our elite cleaning on top of whatever we got
            cleaned_snippet = self._clean_text(text_content)
            
            return {
                "ai_overview": None,
                "organic_results": [{
                    "title": "Extracted Content",
                    "url": content.get("url", ""),
                    "snippet": cleaned_snippet,
                    "score": self._calculate_credibility(content.get("url", "")) # Add score
                }]
            }
            
        # Case 2: Raw HTML (ScrapingBee/ZenRows/Direct)
        # Use Trafilatura to extract the main text body cleanly
        extracted_text = trafilatura.extract(content)
        
        if not extracted_text:
            # Fallback to simple soup extraction if Trafilatura fails
            soup = BeautifulSoup(content, 'html.parser')
            extracted_text = soup.get_text(separator=' ', strip=True)

        # Apply elite cleaning
        cleaned_snippet = self._clean_text(extracted_text)

        return {
            "ai_overview": None,
            "organic_results": [{
                "title": "Scraped Page", # Title is hard to get from just raw HTML str in trafilatura without re-parsing, but we can try
                "url": "", 
                "snippet": cleaned_snippet[:15000], # Cap output length, allowing more since it's cleaner
                "score": 0.5 # Default score since we don't have URL here easily unless passed down
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
                # Clean snippet using elite purity rules
                final_snippet = self._clean_text(snippet)
                if final_snippet: # Only add if snippet survived cleaning
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": final_snippet[:300] + "..." if len(final_snippet) > 300 else final_snippet,
                        "score": self._calculate_credibility(url)
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
