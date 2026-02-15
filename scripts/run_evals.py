import asyncio
import json
import time
import httpx
from typing import List, Dict, Any
import statistics

API_URL = "http://localhost:8000/search"
DATASET_PATH = "tests/evals/dataset.json"

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
    Simple heuristic: check if query terms appear in title or snippet.
    Score = (matches / total_terms) * (1 if any result else 0)
    This is a VERY basic proxy for relevance.
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
        
    # Normalize by number of results (avg relevance per result)
    return min(total_score / len(results), 1.0) 

async def main():
    print(f"Loading dataset from {DATASET_PATH}...")
    with open(DATASET_PATH, "r") as f:
        dataset = json.load(f)
        
    print(f"Running evals for {len(dataset)} questions...")
    
    results = []
    async with httpx.AsyncClient() as client:
        tasks = [run_query(client, q) for q in dataset]
        # Run with some concurrency control if needed, but for 50 items direct gather is minimal load
        # Batching to avoid overwhelming the local worker if concurrency is low
        batch_size = 5
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            results.extend(await asyncio.gather(*batch))
            print(f"Processed {min(i + batch_size, len(tasks))}/{len(dataset)} queries...")
            await asyncio.sleep(1) # Rate limit protection

    # Aggregation
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] != "success"]
    
    latencies = [r["latency"] for r in successes]
    avg_latency = statistics.mean(latencies) if latencies else 0
    
    relevance_scores = []
    for r in successes:
        score = calculate_heuristic_score(r["query"], r["data"].get("organic_results", []))
        relevance_scores.append(score)
        
    avg_relevance = statistics.mean(relevance_scores) if relevance_scores else 0
    
    print("\n" + "="*40)
    print("EVALUATION REPORT (Baseline v11.9)")
    print("="*40)
    print(f"Total Queries: {len(dataset)}")
    print(f"Success Rate:  {len(successes)}/{len(dataset)} ({len(successes)/len(dataset)*100:.1f}%)")
    print(f"Avg Latency:   {avg_latency:.2f}s")
    print(f"Avg Relevance: {avg_relevance:.2f} (Heuristic)")
    print("="*40)

    # Save detailed results
    with open("tests/evals/last_run_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Detailed results saved to tests/evals/last_run_results.json")

if __name__ == "__main__":
    asyncio.run(main())
