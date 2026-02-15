from typing import Optional, List, Dict, Union, Any
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str
    region: Optional[str] = "us"
    language: Optional[str] = "en"
    output_format: Optional[str] = "markdown"
    mode: Optional[str] = "search"
    limit: Optional[int] = 10

class OrganicResult(BaseModel):
    title: str
    url: str
    snippet: str
    score: Optional[float] = 0.0
    full_content: Optional[str] = None
    embedding: Optional[List[float]] = None

class SearchResponse(BaseModel):
    query: str
    ai_overview: Optional[str] = None
    organic_results: List[OrganicResult] = []
    formatted_output: str
    token_estimate: int
    relevance_score: Optional[float] = 0.0
    relevance_reasoning: Optional[str] = None
    credibility_score: Optional[float] = 0.0
    credibility_reasoning: Optional[str] = None
    cached: bool

class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[SearchResponse] = None
    error: Optional[str] = None
