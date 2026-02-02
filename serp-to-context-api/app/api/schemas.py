from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union

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

class SearchResponse(BaseModel):
    query: str
    ai_overview: Optional[str] = None
    organic_results: List[OrganicResult] = []
    formatted_output: str
    token_estimate: int
    cached: bool
