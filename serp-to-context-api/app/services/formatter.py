from typing import Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.utils.logger import logger

class FormatterService:
    def format_response(self, query: str, parsed_data: Dict) -> Dict:
        organic = parsed_data.get("organic_results", [])
        ai_overview = parsed_data.get("ai_overview")
        
        # Deduplicate
        unique_results = self._deduplicate_results(organic)
        
        # Format as Markdown
        markdown_output = self._generate_markdown(query, ai_overview, unique_results)
        
        # Calculate tokens
        token_count = self._estimate_tokens(markdown_output)

        return {
            "query": query,
            "ai_overview": ai_overview,
            "organic_results": unique_results,
            "formatted_output": markdown_output,
            "token_estimate": token_count
        }

    def _deduplicate_results(self, results: List[Dict], threshold: float = 0.85) -> List[Dict]:
        """
        Removes results that are too similar in content using TF-IDF cosine similarity.
        """
        if not results:
            return []
        
        if len(results) == 1:
            return results

        try:
            snippets = [r.get("snippet", "") for r in results]
            # Handle empty snippets to avoid vectorizer errors
            if all(not s.strip() for s in snippets):
                return results

            vectorizer = TfidfVectorizer().fit_transform(snippets)
            vectors = vectorizer.toarray()
            
            kept_indices = []
            
            for i in range(len(results)):
                is_duplicate = False
                for j in kept_indices:
                    sim = cosine_similarity([vectors[i]], [vectors[j]])[0][0]
                    if sim > threshold:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    kept_indices.append(i)
            
            return [results[i] for i in kept_indices]

        except Exception as e:
            logger.error(f"Deduplication failed: {e}")
            return results # Fail safe: return original list

    def _generate_markdown(self, query: str, ai_overview: str, results: List[Dict]) -> str:
        md = [f"# Search Results for: {query}\n"]
        
        if ai_overview:
            md.append(f"## AI Overview\n> {ai_overview}\n")
            md.append("---\n")
            
        for idx, res in enumerate(results, 1):
            md.append(f"## {idx}. {res.get('title', 'No Title')}")
            md.append(f"URL: {res.get('url', 'No URL')}")
            md.append(f"Snippet: {res.get('snippet', '')}\n")
            
        return "\n".join(md)

    def _estimate_tokens(self, text: str) -> int:
        # Approximate: 1 token ~= 4 chars or 0.75 words
        # Use word count * 1.3 as requested in prompt
        word_count = len(text.split())
        return int(word_count * 1.3)

formatter = FormatterService()
