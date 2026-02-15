import asyncio
import json
import time
import os
import httpx
import statistics
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

API_URL = "http://localhost:8000/search"
DATASET_PATH = "backend/tests/evals/dataset.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class LLMJudge:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    async def evaluate(self, query: str, snippets: List[str]) -> Dict[str, Any]:
        """
        Evaluates the relevance of snippets to the query using the LLM.
        Returns a dictionary with score (0.0-1.0) and reasoning.
        """
        if not snippets:
            return {"score": 0.0, "reasoning": "No snippets provided."}

        prompt = f"""
        You are an expert search relevance judge. 
        Your task is to evaluate how relevant the following search snippets are to the user's query.

        User Query: "{query}"

        Search Snippets:
        {json.dumps(snippets, indent=2)}

        Instructions:
        1. Analyze if the snippets contain information that directly answers or helps answer the query.
        2. Assign a relevance score between 0.0 (completely irrelevant) and 1.0 (perfect answer).
        3. Provide a brief reasoning for your score.
        4. Output ONLY valid JSON in the following format:
        {{
            "score": <float>,
            "reasoning": "<string>"
        }}
        """

        try:
            # Run in a separate thread to avoid blocking asyncio loop (genai is sync)
            response = await asyncio.to_thread(
                self.model.generate_content, 
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            result = json.loads(response.text)
            return result
        except Exception as e:
            print(f"Error evaluating query '{query}': {e}")
            return {"score": 0.0, "reasoning": f"Evaluation failed: {str(e)}"}

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
    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not found in .env. Falling back to heuristic scoring ONLY.")
        judge = None
    else:
        print(f"Initializing LLM Judge with model: gemini-2.5-flash...")
        try:
            judge = LLMJudge(api_key=GEMINI_API_KEY, model_name="gemini-2.0-flash-exp")
        except Exception as e:
            print(f"Failed to initialize LLM Judge: {e}. Falling back to heuristic.")
            judge = None

    print(f"Loading dataset from {DATASET_PATH}...")
    try:
        with open(DATASET_PATH, "r") as f:
            dataset = json.load(f)
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
    
    # Process evaluation in batches to avoid rate limits on LLM API
    eval_batch_size = 5
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
                    eval_tasks.append(judge.evaluate(res["query"], snippets))
                else:
                    eval_tasks.append(asyncio.sleep(0, result={"score": heuristic_score, "reasoning": "Heuristic fallback"})) # Mock
            else:
                # Failed search
                res["heuristic_score"] = 0.0
                eval_tasks.append(asyncio.sleep(0, result={"score": 0.0, "reasoning": "Search failed"}))
        
        # Execute batch evaluation
        eval_outputs = await asyncio.gather(*eval_tasks)
        
        # Merge back
        for res, eval_out in zip(batch, eval_outputs):
            res["llm_score"] = eval_out.get("score", 0.0)
            res["llm_reasoning"] = eval_out.get("reasoning", "No description")
            evaluated_results.append(res)
            
        print(f"Evaluated {min(i + eval_batch_size, len(results))}/{len(results)} queries...")
        if judge:
            await asyncio.sleep(2) # Protect LLM Rate Limits

    # Aggregation
    successes = [r for r in evaluated_results if r["status"] == "success"]
    
    latencies = [r["latency"] for r in successes]
    avg_latency = statistics.mean(latencies) if latencies else 0
    
    llm_scores = [r["llm_score"] for r in successes]
    avg_llm_score = statistics.mean(llm_scores) if llm_scores else 0
    
    heuristic_scores = [r["heuristic_score"] for r in successes]
    avg_heuristic_score = statistics.mean(heuristic_scores) if heuristic_scores else 0
    
    print("\n" + "="*50)
    print("EVALUATION REPORT (Gemini 2.5 Flash)")
    print("="*50)
    print(f"Total Queries:      {len(dataset)}")
    print(f"Success Rate:       {len(successes)}/{len(dataset)} ({len(successes)/len(dataset)*100:.1f}%)")
    print(f"Avg Latency:        {avg_latency:.2f}s")
    print(f"Avg Heuristic:      {avg_heuristic_score:.2f}")
    print(f"Avg LLM Relevance:  {avg_llm_score:.2f}")
    print("="*50)

    # Save detailed results
    output_path = "backend/tests/evals/last_run_results_llm.json"
    with open(output_path, "w") as f:
        json.dump(evaluated_results, f, indent=2)
    print(f"Detailed results saved to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
