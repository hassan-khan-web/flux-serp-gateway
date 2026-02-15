import os
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from app.utils.logger import logger

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class LLMJudgeService:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "meta-llama/llama-3-8b-instruct:free"):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Flux Search Agent"
        }

    async def _call_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Helper to call OpenRouter API with retries"""
        if not self.api_key:
            return {"score": 0.0, "reasoning": "Missing API Key"}

        payload = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 1000
        }
        
        retries = 2
        base_delay = 5

        async with httpx.AsyncClient() as client:
            for attempt in range(retries + 1):
                try:
                    response = await client.post(
                        OPENROUTER_URL, 
                        headers=self.headers, 
                        json=payload, 
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
                        try:
                            # Clean up potential markdown code blocks
                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0].strip()
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0].strip()
                                
                            result = json.loads(content)
                            return result
                        except json.JSONDecodeError:
                            logger.error("JSON Decode Error in LLM result: %s", content)
                            return {"score": 0.0, "reasoning": "Parse Error"}
                    
                    elif response.status_code == 429:
                        wait_time = base_delay * (attempt + 1)
                        logger.warning("OpenRouter 429 Rate Limit. Retrying in %ss...", wait_time)
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("OpenRouter Error %s: %s", response.status_code, response.text)
                        return {"score": 0.0, "reasoning": f"API Error {response.status_code}"}
                        
                except Exception as e:
                    logger.error("Request Error in LLMJudgeService: %s", e)
                    if attempt < retries:
                        await asyncio.sleep(base_delay)
                        continue
                    return {"score": 0.0, "reasoning": str(e)}
        
        return {"score": 0.0, "reasoning": "Max retries exceeded"}

    async def evaluate_relevance(self, query: str, snippets: List[str]) -> Dict[str, Any]:
        """Evaluates the relevance of snippets to the query."""
        system_prompt = "You are a helpful assistant that evaluates search relevance. Output ONLY valid JSON."
        user_prompt = f"""
        Task: Rate the semantic RELEVANCE of the search results to the User Query.
        
        User Query: "{query}"
        
        Results:
        {json.dumps(snippets, indent=2)}
        
        Instructions:
        1. Rate from 0.0 (Irrelevant) to 1.0 (Highly Relevant).
        2. Provide a 1-sentence reasoning.
        3. Output JSON: {{ "score": <float>, "reasoning": "<string>" }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._call_api(messages)

    async def evaluate_credibility(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluates the credibility of the sources."""
        sources_text = []
        for i, res in enumerate(results):
            sources_text.append(f"Source {i+1}:\nURL: {res.get('url', res.get('link', 'N/A'))}\nSnippet: {res.get('snippet', 'N/A')}\n")
        
        sources_str = "\n".join(sources_text)
        system_prompt = "You are an expert information quality judge. Output ONLY valid JSON."
        user_prompt = f"""
        Task: Evaluate the CREDIBILITY of these sources for the query.
        
        User Query: "{query}"
        
        Sources:
        {sources_str}
        
        Instructions:
        1. Analyze URLs (domain authority) and content.
        2. Rate from 0.0 (Low trust) to 1.0 (High trust/Academic/Government).
        3. Provide 1-sentence reasoning.
        4. Output JSON: {{ "score": <float>, "reasoning": "<string>" }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._call_api(messages)

llm_judge = LLMJudgeService()
