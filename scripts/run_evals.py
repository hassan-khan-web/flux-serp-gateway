import asyncio
import json
import time
import os
import httpx
import statistics
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_URL = "http://localhost:8000/search"
DATASET_PATH = "backend/tests/evals/dataset.json"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

class LLMJudge:
    def __init__(self, api_key: str, model_name: str = "meta-llama/llama-3-8b-instruct:free"):
        self.api_key = api_key
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000", # Required by OpenRouter for some tiers
            "X-Title": "Flux Search Evals"
        }

    async def _call_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Helper to call OpenRouter API with retries"""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "max_tokens": 1000
        }
        
        retries = 3
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
                        content = response.json()["choices"][0]["message"]["content"]
                        try:
                            # Clean up potential markdown code blocks
                            if "```json" in content:
                                content = content.split("```json")[1].split("```")[0].strip()
                            elif "```" in content:
                                content = content.split("```")[1].split("```")[0].strip()
                                
                            result = json.loads(content)
                            if isinstance(result, list):
                                return result[0] if result else {"score": 0.0, "reasoning": "Empty list"}
                            return result
                        except json.JSONDecodeError:
                            return {"score": 0.0, "reasoning": f"JSON Decode Error: {content[:100]}"}
                    
                    elif response.status_code == 429:
                        wait_time = base_delay * (attempt + 1)
                        print(f"OpenRouter 429 Rate Limit. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"OpenRouter Error {response.status_code}: {response.text}")
                        return {"score": 0.0, "reasoning": f"API Error: {response.status_code}"}
                        
                except Exception as e:
                    print(f"Request Error: {e}")
                    if attempt < retries:
                        await asyncio.sleep(base_delay)
                        continue
                    return {"score": 0.0, "reasoning": f"Exception: {str(e)}"}
        
        return {"score": 0.0, "reasoning": "Max retries exceeded"}

    async def evaluate(self, query: str, snippets: List[str]) -> Dict[str, Any]:
        """
        Evaluates the relevance of snippets to the query using the LLM.
        """
        if not snippets:
            return {"score": 0.0, "reasoning": "No snippets provided."}

        system_prompt = "You are an expert search relevance judge. Output ONLY valid JSON."
        user_prompt = f"""
        Task: Evaluate the OVERALL quality of the search snippets for the query.
        
        User Query: "{query}"

        Search Snippets:
        {json.dumps(snippets, indent=2)}

        Instructions:
        1. Analyze if snippets answer the query.
        2. Assign a score 0.0 (irrelevant) to 1.0 (perfect).
        3. Provide reasoning.
        4. Output JSON: {{ "score": <float>, "reasoning": "<string>" }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self._call_api(messages)

    async def evaluate_credibility(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates the credibility of the sources.
        """
        if not results:
            return {"score": 0.0, "reasoning": "No results provided."}

        sources_text = []
        for i, res in enumerate(results):
            sources_text.append(f"Source {i+1}:\nURL: {res.get('link', 'N/A')}\nSnippet: {res.get('snippet', 'N/A')}\n")
        
        sources_str = "\n".join(sources_text)

        system_prompt = "You are an expert information quality judge. Output ONLY valid JSON."
        user_prompt = f"""
        Task: Evaluate the CREDIBILITY of the sources.

        User Query: "{query}"

        Sources:
        {sources_str}

        Instructions:
        1. Analyze URLs (domain authority) and content quality.
        2. Assign score 0.0 (low trust) to 1.0 (high trust/academic/news).
        3. Provide reasoning.
        4. Output JSON: {{ "score": <float>, "reasoning": "<string>" }}
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        return await self._call_api(messages)



async def run_query(client: httpx.AsyncClient, question: Dict[str, Any]) -> Dict[str, Any]:
    start_time = time.time()
    payload = {
        "query": question["query"],
        "region": "us",
        "language": "en",
        "limit": 5  # Fetch top 5 results
    }
    
    retries = 3
    # Step 1: Submit Task
    task_id = None
    for attempt in range(retries):
        try:
            response = await client.post(API_URL, json=payload, timeout=10.0)
            
            if response.status_code == 202:
                task_id = response.json()["task_id"]
                break
            elif response.status_code == 429:
                wait_time = (2 ** attempt) + 1
                await asyncio.sleep(wait_time)
                continue
            else:
                return {
                    "id": question["id"],
                    "query": question["query"],
                    "status": "error",
                    "error_code": response.status_code,
                    "latency": time.time() - start_time,
                    "result_count": 0
                }
        except Exception as e:
            return {
                "id": question["id"],
                "query": question["query"],
                "status": "exception",
                "error_msg": str(e),
                "latency": time.time() - start_time,
                "result_count": 0
            }

    if not task_id:
         return {
            "id": question["id"],
            "query": question["query"],
            "status": "error",
            "error_code": 429, # Assuming rate limit if no task_id
            "latency": time.time() - start_time,
            "result_count": 0
        }

    # Step 2: Poll for Results
    poll_attempts = 30 # 30 * 2s = 60s max wait
    for _ in range(poll_attempts):
        await asyncio.sleep(2)
        try:
            status_response = await client.get(f"http://localhost:8000/tasks/{task_id}", timeout=10.0)
            if status_response.status_code == 200:
                task_data = status_response.json()
                if task_data["status"] == "completed":
                    latency = time.time() - start_time
                    result = task_data["result"]
                    return {
                        "id": question["id"],
                        "query": question["query"],
                        "status": "success",
                        "latency": latency,
                        "result_count": len(result.get("organic_results", [])),
                        "data": result
                    }
                elif task_data["status"] == "failed":
                    return {
                        "id": question["id"],
                        "query": question["query"],
                        "status": "error",
                        "error_msg": task_data.get("error", "Unknown task failure"),
                        "latency": time.time() - start_time,
                        "result_count": 0
                    }
        except Exception as e:
             pass # Continue polling on transient callback errors
             
    # Timeout
    return {
        "id": question["id"],
        "query": question["query"],
        "status": "timeout",
        "latency": time.time() - start_time,
        "result_count": 0
    }

def calculate_heuristic_score(query: str, results: List[Dict[str, Any]]) -> float:
    """
    Fallback Heuristic: check if query terms appear in title or snippet.
    """
    if not results:
        return 0.0
    
    query_terms = set(query.lower().split())
    if not query_terms:
        return 0.0
        
    total_score = 0
    for res in results:
        text = (res.get("title", "") + " " + res.get("snippet", "")).lower()
        matches = sum(1 for term in query_terms if term in text)
        total_score += matches / len(query_terms)
        
    return min(total_score / len(results), 1.0) 

async def main():
    if not OPENROUTER_API_KEY:
        print("WARNING: OPENROUTER_API_KEY not found in .env. Falling back to heuristic scoring ONLY.")
        judge = None
    else:
        print(f"Initializing LLM Judge with model: meta-llama/llama-3-8b-instruct:free (OpenRouter)...")
        try:
            judge = LLMJudge(api_key=OPENROUTER_API_KEY, model_name="meta-llama/llama-3-8b-instruct:free")
        except Exception as e:
            print(f"Failed to initialize LLM Judge: {e}. Falling back to heuristic.")
            judge = None

    print(f"Loading dataset from {DATASET_PATH}...")
    try:
        with open(DATASET_PATH, "r") as f:
            dataset = json.load(f)
            print(f"FULL MODE: Processing all {len(dataset)} queries.")
    except FileNotFoundError:
        print(f"Error: Dataset not found at {DATASET_PATH}")
        return

    print(f"Running evals for {len(dataset)} questions...")
    
    results = []
    # 1. Run Search
    async with httpx.AsyncClient() as client:
        tasks = [run_query(client, q) for q in dataset]
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            results.extend(await asyncio.gather(*batch))
            print(f"Search: Processed {min(i + batch_size, len(tasks))}/{len(dataset)} queries...")
            await asyncio.sleep(1) 

    # 2. Evaluate Results (Scoring)
    print("\nStarting Evaluation Phase...")
    evaluated_results = []
    
    # Process evaluation sequentially to strictly avoid rate limits
    eval_batch_size = 1
    for i in range(0, len(results), eval_batch_size):
        batch = results[i:i + eval_batch_size]
        eval_tasks = []
        
        for res in batch:
            if res["status"] == "success":
                organic_results = res["data"].get("organic_results", [])
                snippets = [r.get("snippet", "") for r in organic_results]
                
                # Heuristic Score (Always calculate as baseline/fallback)
                heuristic_score = calculate_heuristic_score(res["query"], organic_results)
                res["heuristic_score"] = heuristic_score
                
                if judge:
                    # Parallel calls for Relevance and Credibility
                    relevance_task = judge.evaluate(res["query"], snippets)
                    credibility_task = judge.evaluate_credibility(res["query"], organic_results)
                    eval_tasks.append(relevance_task)
                    eval_tasks.append(credibility_task)
                else:
                    eval_tasks.append(asyncio.sleep(0, result={"score": heuristic_score, "reasoning": "Heuristic fallback"}))
                    eval_tasks.append(asyncio.sleep(0, result={"score": 0.0, "reasoning": "No LLM"}))
            else:
                # Failed search
                res["heuristic_score"] = 0.0
                eval_tasks.append(asyncio.sleep(0, result={"score": 0.0, "reasoning": "Search failed"}))
                eval_tasks.append(asyncio.sleep(0, result={"score": 0.0, "reasoning": "Search failed"}))
        
        # Execute batch evaluation
        eval_outputs = await asyncio.gather(*eval_tasks)
        
        # Merge back (2 outputs per result if judge exists)
        if judge:
            # We have 2 * batch_size outputs
            # Structure: [Rel1, Cred1, Rel2, Cred2, ...]
            for i, res in enumerate(batch):
                rel_idx = i * 2
                cred_idx = i * 2 + 1
                
                rel_out = eval_outputs[rel_idx]
                cred_out = eval_outputs[cred_idx]
                
                res["llm_score"] = rel_out.get("score", 0.0)
                res["llm_reasoning"] = rel_out.get("reasoning", "No description")
                
                res["credibility_score"] = cred_out.get("score", 0.0)
                res["credibility_reasoning"] = cred_out.get("reasoning", "No description")
                
                evaluated_results.append(res)
        else:
            # 2 outputs per result (mock)
            for i, res in enumerate(batch):
                rel_idx = i * 2
                rel_out = eval_outputs[rel_idx]
                
                res["llm_score"] = rel_out.get("score", 0.0)
                res["llm_reasoning"] = rel_out.get("reasoning", "No description")
                # No credibility for heuristic mode
                evaluated_results.append(res)
            
        print(f"Evaluated {min(i + eval_batch_size, len(results))}/{len(results)} queries...")
        if judge:
            await asyncio.sleep(10) # Protect Rate Limits (10s delay between queries)

    # Aggregation
    successes = [r for r in evaluated_results if r["status"] == "success"]
    
    latencies = [r["latency"] for r in successes]
    avg_latency = statistics.mean(latencies) if latencies else 0
    
    llm_scores = [r["llm_score"] for r in successes]
    avg_llm_score = statistics.mean(llm_scores) if llm_scores else 0
    
    heuristic_scores = [r["heuristic_score"] for r in successes]
    avg_heuristic_score = statistics.mean(heuristic_scores) if heuristic_scores else 0
    
    print("\n" + "="*50)
    print("EVALUATION REPORT (OpenRouter - Nemotron-3 Free)")
    print("="*50)
    print(f"Total Queries:      {len(dataset)}")
    print(f"Success Rate:       {len(successes)}/{len(dataset)} ({len(successes)/len(dataset)*100:.1f}%)")
    print(f"Avg Latency:        {avg_latency:.2f}s")
    print(f"Avg Heuristic:      {avg_heuristic_score:.2f}")
    
    cred_scores = [r.get("credibility_score", 0.0) for r in successes]
    avg_cred_score = statistics.mean(cred_scores) if cred_scores else 0
    
    print(f"Avg LLM Relevance:  {avg_llm_score:.2f}")
    print(f"Avg Credibility:    {avg_cred_score:.2f}")
    print("="*50)

    # Save detailed results
    output_path = "backend/tests/evals/last_run_results_llm.json"
    with open(output_path, "w") as f:
        json.dump(evaluated_results, f, indent=2)
    print(f"Detailed results saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
