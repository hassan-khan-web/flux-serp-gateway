from fastapi import APIRouter, HTTPException
from celery.result import AsyncResult
from app.api.schemas import SearchRequest, SearchResponse, TaskResponse
from app.worker import scrape_and_process
from app.utils.logger import logger

router = APIRouter()

@router.post("/search", response_model=TaskResponse, status_code=202)
async def search_endpoint(request: SearchRequest):
    """
    Initiates a background search task.
    Returns a task ID for polling.
    """
    try:
        # Dispatch Celery task
        task = scrape_and_process.delay(
            query=request.query,
            region=request.region,
            language=request.language,
            limit=request.limit,
            mode=request.mode,
            output_format=request.output_format
        )
        
        return TaskResponse(
            task_id=task.id,
            status="pending"
        )

    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: str):
    """
    Poll the status of a background task.
    """
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
                    # Validate against SearchResponse to ensure schema match
                    response.result = SearchResponse(**result_data, cached=False) # Cached flag handling logic might need improvement in worker
            else:
                response.status = "failed"
                response.error = str(task_result.result)
        
        return response

    except Exception as e:
        logger.error(f"Task status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
