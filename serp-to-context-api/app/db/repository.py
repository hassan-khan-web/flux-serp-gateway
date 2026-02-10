from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import SearchResult
from typing import List, Dict

async def save_search_results(session: AsyncSession, query: str, results: List[Dict]):
    """
    Saves a list of dictionary results to the database.
    Each result dict should have: title, url, snippet, score, embedding (optional).
    """
    for res in results:
        db_item = SearchResult(
            query=query,
            url=res.get("url"),
            title=res.get("title"),
            snippet=res.get("snippet"),
            score=res.get("score", 0.0),
            embedding=res.get("embedding")
        )
        session.add(db_item)
    
    await session.commit()
