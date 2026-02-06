from bs4 import BeautifulSoup, Tag
from typing import Dict, List, Optional, Union, Union
import re
import trafilatura
from app.utils.logger import logger

class ParserService:
    def parse(self, content: Union[str, Dict]) -> Dict:
        if isinstance(content, dict):
            organic_results = [
                {
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "snippet": self._clean_text(result.get("content")),
                    "score": self._calculate_credibility(result.get("url"))
                }
                for result in content.get("results", [])
            ]
            
            return {
                "ai_overview": content.get("answer"),
                "organic_results": organic_results
            }

        soup = BeautifulSoup(content, 'html.parser')
        
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            tag.decompose()

        return {
            "ai_overview": self._extract_ai_overview(soup),
            "organic_results": self._extract_organic_results(soup)
        }

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        noise_patterns = [
            r"Create your free account or sign in",
            r"New to LinkedIn\? Join now",
            r"Sign in to view more content",
            r"agree to LinkedIn’s User Agreement",
            
            r"See our Cookie Policy",
            r"Manage your preferences",
            r"Skip to main content",
            r"Skip to top",
            r"Download chart",
            
            r"Share on Twitter",
            r"Share on Facebook",
            r"Open the app",
            r"Click here to subscribe",
            r"Subscribe to our newsletter",
            r"We'd love you to become a subscriber",
            r"Start your free trial",
            
            r"All rights reserved",
            r"Terms of Service",
            r"Privacy Policy",
            r"Copyright \u00a9 \d{4}",
            r"Copyright\s+[-–]\s+.*?[\d{4}]",
            
            r"Advertisement",
            r"Sponsored Content",
            r"Read more",
            r"Continue reading",
            r"Subscriber only",
            
            r"News • .*? \d{1,2}:\d{2} [AP]M ET",  
            r"Updated: .*? \d{4}",
            r"\d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} [AP]M",
            
            r"Follow .*? on WhatsApp",
            r"Download the .*? app",
            r"Join .*? channel",
            
            r"!\[.*?Logo.*?\]\(.*?\)",  
            r"!\[.*?representational.*?\]\(.*?\)",
            r"Credit:.*", 
            r"Image:.*",
            r"Source:.*",
            r"## Related Stories",
            r"## Want to \?",
            r"## Click below to access",
            r"\*\*\[.*?\]\(.*?\)\*\*" 
        

        
        cleaned_text = text
        for pattern in noise_patterns:
            cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE)
            
        ui_phrases = ["Sign up", "Log in", "Login", "Get Started", "Subscribe", "Create account", "Continue reading"]
        lines = cleaned_text.split('\n')
        filtered_lines = []
        for line in lines:
            if any(phrase.lower() in line.lower() for phrase in ui_phrases):
                continue
            filtered_lines.append(line)
        cleaned_text = "\n".join(filtered_lines)

        cleaned_text = cleaned_text.strip()
        if cleaned_text and cleaned_text[-1] not in ['.', '!', '?', '"', "'", ')']:
            last_period = max(cleaned_text.rfind('.'), cleaned_text.rfind('!'), cleaned_text.rfind('?'))
            if last_period != -1:
                cleaned_text = cleaned_text[:last_period+1]
            
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
        
        if "arxiv.org" in url_lower: return 1.0
        if ".edu" in url_lower: return 0.95
        if ".gov" in url_lower: return 0.95
        if "nih.gov" in url_lower: return 0.95
        
        if "github.com" in url_lower: return 0.8
        if "github.io" in url_lower: return 0.8
        if "huggingface.co" in url_lower: return 0.8
        if "stackoverflow.com" in url_lower: return 0.75
        if "readthedocs.io" in url_lower: return 0.8
        if "python.org" in url_lower: return 0.85
        if "developer.mozilla.org" in url_lower: return 0.85
        if "nvidia.com" in url_lower: return 0.85
        if "acm.org" in url_lower: return 0.95 
        if "kaggle.com" in url_lower: return 0.75
        if "deepseek.com" in url_lower: return 0.85 
        
        if "medium.com" in url_lower: return 0.4
        if "linkedin.com" in url_lower: return 0.3
        if "businessinsider" in url_lower: return 0.4
        if "forbes.com" in url_lower: return 0.4
        
        logger.info(f"Default score 0.5 assigned to: {url}")
        return 0.5

    def parse_url_content(self, content: Union[str, Dict]) -> Dict:
        """
        Parses content from a specific URL (scraped/extracted).
        """
        if isinstance(content, dict):
            text_content = content.get("content") or content.get("raw_content", "")
            if content.get("raw_content"):
                 extracted = trafilatura.extract(content["raw_content"])
                 if extracted:
                     text_content = extracted
            
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
            
        extracted_text = trafilatura.extract(content)
        
        if not extracted_text:
            soup = BeautifulSoup(content, 'html.parser')
            extracted_text = soup.get_text(separator=' ', strip=True)

        cleaned_snippet = self._clean_text(extracted_text)

        return {
            "ai_overview": None,
            "organic_results": [{
                "title": "Scraped Page", 
                "url": "", 
                "snippet": cleaned_snippet[:15000],
                "score": 0.5 
        }

    def _extract_ai_overview(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Heuristic: Look for a dense block of text near the top that isn't a standard result.
        Often contains multiple paragraphs and 'Generative AI' or 'Overview' indicators.
        """
        
        body = soup.find('body')
        if not body:
            return None

        
        candidates = []
        
        for child in body.find_all(recursive=False):
            if not isinstance(child, Tag):
                continue
                
            text = child.get_text(strip=True)
            if len(text) < 100:
                continue
                
            if re.search(r"(AI Overview|Generative AI|Summarized by AI)", text, re.IGNORECASE):
                return self._clean_text(text)
            
            candidates.append((len(text), text))

        
        return None 

    def _extract_organic_results(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Anchor & Pivot Logic:
        1. Find <a> tags that contain <h3> or <h4> (the Title).
        2. From that <a>, pivot up to the result container.
        3. Extract snippet from the container's text, excluding the title/url.
        """
        results = []
        seen_urls = set()

        title_tags = soup.find_all('h3')
        
        for h3 in title_tags:
            a_tag = h3.find_parent('a')
            if not a_tag:
                continue
                
            href = a_tag.get('href', '')
            
            url = self._clean_url(href)
            
            if not url or url.startswith('/') or url in seen_urls:
                continue
            
            if "googleadservices" in url:
                continue

            seen_urls.add(url)
            
            title = h3.get_text(strip=True)
            
        
            snippet = ""
            
            
            container = a_tag.parent
            for _ in range(3):
                if container and container.name == 'div':
                    if len(container.get_text()) > len(title) + 20: 
                        break
                if container.parent:
                    container = container.parent
            
            if container:
                full_text = container.get_text(" ", strip=True)
                snippet = full_text.replace(title, "").replace(url, "").strip()
                snippet = " ".join(snippet.split())
            
            if title and url:
                final_snippet = self._clean_text(snippet)
                if final_snippet: 
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
        if href.startswith('/url?q='):
            match = re.search(r'q=([^&]+)', href)
            if match:
                return urllib.parse.unquote(match.group(1))
        return href



parser = ParserService()
