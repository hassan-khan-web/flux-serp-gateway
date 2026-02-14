from typing import Any
from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from celery import chain
from app.api.schemas import SearchRequest, SearchResponse, TaskResponse
from app.worker import scrape_task, embed_task
from app.utils.logger import logger

router: APIRouter = APIRouter()

@router.post("/search", response_model=TaskResponse, status_code=202)
async def search_endpoint(request: SearchRequest) -> TaskResponse:
    try:
        # Chain the tasks: Scrape -> Embed
        task_chain = chain(
            scrape_task.s(
                query=request.query,
                region=request.region,
                language=request.language,
                limit=request.limit,
                mode=request.mode
            ),
            embed_task.s(
                region=request.region,
                language=request.language,
                limit=request.limit,
                output_format=request.output_format
            )
        )
        
        task = task_chain.apply_async()
        
        return TaskResponse(
            task_id=task.id,
            status="pending"
        )

    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str) -> TaskResponse:
    try:
        task_result = AsyncResult(task_id)
        
        response = TaskResponse(
            task_id=task_id,
            status=task_result.status.lower()
        )

        if task_result.ready():
            if task_result.successful():
                result_data = task_result.get()
                if "error" in result_data:
                    response.status = "failed"
                    response.error = result_data["error"]
                else:
                    response.status = "completed"
                    response.result = SearchResponse(**result_data, cached=False)
            else:
                response.status = "failed"
                response.error = str(task_result.result)
        
        return response

    except Exception as e:
        logger.error(f"Task status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
