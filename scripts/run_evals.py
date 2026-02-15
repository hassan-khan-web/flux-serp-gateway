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
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
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
        Your task is to evaluate the OVERALL quality of the returned search snippets for the user's query.

        User Query: "{query}"

        Search Snippets:
        {json.dumps(snippets, indent=2)}

        Instructions:
        1. Analyze if the set of snippets contains information that directly answers the query.
        2. Assign a SINGLE aggregate relevance score between 0.0 (completely irrelevant) and 1.0 (perfect answer).
        3. Provide a brief reasoning for your score.
        4. Output ONLY a SINGLE valid JSON object in the following format:
        {{
            "score": <float>,
            "reasoning": "<string>"
        }}
        """

        retries = 3
        base_delay = 15  # Seconds (Free tier bucket refill)

        for attempt in range(retries + 1):
            try:
                # Run in a separate thread to avoid blocking asyncio loop (genai is sync)
                response = await asyncio.to_thread(
                    self.model.generate_content, 
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                result = json.loads(response.text)
                
                # Handle list output (sometimes model returns [ { ... } ])
                if isinstance(result, list):
                    if len(result) > 0 and isinstance(result[0], dict):
                        result = result[0]
                    else:
                        return {"score": 0.0, "reasoning": "Invalid list format from LLM"}
                        
                return result
            
            except Exception as e:
                is_rate_limit = "429" in str(e) or "quota" in str(e).lower()
                if is_rate_limit:
                    if attempt < retries:
                        wait_time = base_delay * (attempt + 1)
                        print(f"Rate limit hit for '{query}'. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return {"score": 0.0, "reasoning": f"Rate limit exceeded after retries: {str(e)}"}
                
                print(f"Error evaluating query '{query}': {e}")
                return {"score": 0.0, "reasoning": f"Evaluation failed: {str(e)}"}

    async def evaluate_credibility(self, query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates the credibility of the sources.
        Returns a dictionary with score (0.0-1.0) and reasoning.
        """
        if not results:
            return {"score": 0.0, "reasoning": "No results provided."}

        # Format sources for the prompt
        sources_text = []
        for i, res in enumerate(results):
            sources_text.append(f"Source {i+1}:\nURL: {res.get('link', 'N/A')}\nSnippet: {res.get('snippet', 'N/A')}\n")
        
        sources_str = "\n".join(sources_text)

        prompt = f"""
        You are an expert information quality judge.
        Your task is to evaluate the CREDIBILITY of the sources retrieved for the user's query.

        User Query: "{query}"

        Sources:
        {sources_str}

        Instructions:
        1. Analyze the URLs (domain authority) and the content quality in the snippets.
        2. Assign a SINGLE aggregate credibility score between 0.0 (low trust/spam) and 1.0 (highly authoritative/academic/verified news).
        3. High scores: .gov, .edu, known news outlets, official documentation.
        4. Low scores: random blogs, forums, unverified user content, spammy domains.
        5. Provide a brief reasoning.
        6. Output ONLY a SINGLE valid JSON object in the following format:
        {{
            "score": <float>,
            "reasoning": "<string>"
        }}
        """

        retries = 3
        base_delay = 15

        for attempt in range(retries + 1):
            try:
                response = await asyncio.to_thread(
                    self.model.generate_content, 
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                result = json.loads(response.text)
                if isinstance(result, list):
                    result = result[0] if result else {"score": 0.0, "reasoning": "Empty list"}
                return result
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    if attempt < retries:
                        wait_time = base_delay * (attempt + 1)
                        print(f"Credibility Rate limit hit for '{query}'. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                print(f"Error checking credibility for '{query}': {e}")
                return {"score": 0.0, "reasoning": f"Error: {str(e)}"}

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
        print(f"Initializing LLM Judge with model: gemini-2.0-flash...")
        try:
            judge = LLMJudge(api_key=GEMINI_API_KEY, model_name="gemini-2.0-flash")
        except Exception as e:
            print(f"Failed to initialize LLM Judge: {e}. Falling back to heuristic.")
            judge = None

    print(f"Loading dataset from {DATASET_PATH}...")
    try:
        with open(DATASET_PATH, "r") as f:
            full_dataset = json.load(f)
            # DEMO LIMIT: Process only first 10 items to stay within free tier limits quickly
            dataset = full_dataset[:10] 
            print(f"DEMO MODE: Processing 10/{len(full_dataset)} queries for rapid verification.")
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
    
    # Process evaluation sequentially (or small batches) to avoid rate limits
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
            await asyncio.sleep(10) # Protect LLM Rate Limits (10s delay between queries)

    # Aggregation
    successes = [r for r in evaluated_results if r["status"] == "success"]
    
    latencies = [r["latency"] for r in successes]
    avg_latency = statistics.mean(latencies) if latencies else 0
    
    llm_scores = [r["llm_score"] for r in successes]
    avg_llm_score = statistics.mean(llm_scores) if llm_scores else 0
    
    heuristic_scores = [r["heuristic_score"] for r in successes]
    avg_heuristic_score = statistics.mean(heuristic_scores) if heuristic_scores else 0
    
    print("\n" + "="*50)
    print("EVALUATION REPORT (Gemini 2.0 Flash)")
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
