from typing import Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.utils.logger import logger

class FormatterService:
    def format_response(self, query: str, parsed_data: Dict) -> Dict:
        organic = parsed_data.get("organic_results", [])
        ai_overview = parsed_data.get("ai_overview")
        
        unique_results = self._deduplicate_results(organic)
        
        markdown_output = self._generate_markdown(query, ai_overview, unique_results)
        
        token_count = self._estimate_tokens(markdown_output)

        return {
            "query": query,
            "ai_overview": ai_overview,
            "organic_results": unique_results,
            "formatted_output": markdown_output,
            "token_estimate": token_count
        }

    def _deduplicate_results(self, results: List[Dict], threshold: float = 0.85) -> List[Dict]:
        if not results:
            return []
        
        if len(results) == 1:
            return results

        try:
            snippets = [r.get("snippet", "") for r in results]
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
            return results 

    def _generate_markdown(self, query: str, ai_overview: str, results: List[Dict]) -> str:
        md = [f"# Search Results for: {query}\n"]
        
        if ai_overview:
            md.append(f"## AI Overview\n{ai_overview}\n")
            md.append("---\n")
            
        sorted_results = sorted(results, key=lambda x: x.get("score", 0.0), reverse=True)
            
        for idx, res in enumerate(sorted_results, 1):
            score = res.get("score", 0.0)
            score_label = f"(Credibility Score: {score})" if score > 0 else ""
            
            md.append(f"### {idx}. {res.get('title', 'No Title')} {score_label}")
            md.append(f"URL: {res.get('url', 'No URL')}")
            md.append(f"Snippet: {res.get('snippet', '')}\n")
            
        return "\n".join(md)

    def _estimate_tokens(self, text: str) -> int:
        word_count = len(text.split())
        return int(word_count * 1.3)

formatter = FormatterService()
