from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Any

class SearchRequest(BaseModel):
    query: str
    region: Optional[str] = "us"
    language: Optional[str] = "en"
    output_format: Optional[str] = "markdown"
    mode: Optional[str] = "search"  # "search" or "scrape"
    limit: Optional[int] = 10

class OrganicResult(BaseModel):
    title: str
    url: str
    snippet: str
    score: Optional[float] = 0.0
    embedding: Optional[List[float]] = None

class SearchResponse(BaseModel):
    query: str
    ai_overview: Optional[str] = None
    organic_results: List[OrganicResult] = []
    formatted_output: str
    token_estimate: int
    cached: bool

class TaskResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[SearchResponse] = None
    error: Optional[str] = None
