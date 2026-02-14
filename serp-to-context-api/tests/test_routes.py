import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from celery.result import AsyncResult
from app.api.routes import router
from fastapi import FastAPI
from app.api.schemas import SearchRequest, SearchResponse, TaskResponse

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestSearchEndpoint:
    """Test POST /search endpoint"""

    @patch("fastapi_limiter.depends.RateLimiter.__call__", new_callable=AsyncMock)
    def test_search_endpoint_success(self, mock_limiter):
        """Test successful search request creates a task"""
        with patch("app.api.routes.chain") as mock_chain:
            mock_task = MagicMock()
            mock_task.id = "test-task-123"
            
            # chain returns an object that has apply_async
            mock_chain_instance = MagicMock()
            mock_chain_instance.apply_async.return_value = mock_task
            mock_chain.return_value = mock_chain_instance

            response = client.post(
                "/search",
                json={
                    "query": "python programming",
                    "region": "us",
                    "language": "en",
                    "limit": 10,
                    "mode": "search",
                    "output_format": "json"
                }
            )

            assert response.status_code == 202
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "pending"

    @patch("fastapi_limiter.depends.RateLimiter.__call__", new_callable=AsyncMock)
    def test_search_endpoint_with_defaults(self, mock_limiter):
        """Test search with minimal parameters (uses defaults)"""
        with patch("app.api.routes.chain") as mock_chain:
            mock_task = MagicMock()
            mock_task.id = "task-456"
            
            mock_chain_instance = MagicMock()
            mock_chain_instance.apply_async.return_value = mock_task
            mock_chain.return_value = mock_chain_instance

            response = client.post(
                "/search",
                json={"query": "test query"}
            )

            assert response.status_code == 202
            assert response.json()["task_id"] == "task-456"
            
            mock_chain.assert_called_once()
            # Validating args deeper is complex with chain, verifying call happened is enough for now

    @patch("fastapi_limiter.depends.RateLimiter.__call__", new_callable=AsyncMock)
    def test_search_endpoint_error_handling(self, mock_limiter):
        """Test error handling in search endpoint"""
        with patch("app.api.routes.chain") as mock_chain:
            mock_chain.side_effect = Exception("Connection failed")

            response = client.post(
                "/search",
                json={"query": "test"}
            )

            assert response.status_code == 500
            assert "Internal Server Error" in response.json()["detail"]

    @patch("fastapi_limiter.depends.RateLimiter.__call__", new_callable=AsyncMock)
    def test_search_endpoint_missing_query(self, mock_limiter):
        """Test validation: query is required"""
        response = client.post(
            "/search",
            json={
                "region": "us"
            }
        )

        assert response.status_code == 422


class TestGetTaskStatus:
    """Test GET /tasks/{task_id} endpoint"""

    def test_get_task_pending(self):
        """Test getting status of pending task"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.status = "PENDING"
            mock_result.ready.return_value = False
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "pending"
            assert data["result"] is None

    def test_get_task_completed_success(self):
        """Test getting status of completed successful task"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.status = "SUCCESS"
            mock_result.ready.return_value = True
            mock_result.successful.return_value = True
            mock_result.get.return_value = {
                "query": "python",
                "ai_overview": "Python is a programming language",
                "organic_results": [
                    {
                        "title": "Python.org",
                        "url": "https://python.org",
                        "snippet": "Official Python website",
                        "score": 0.9
                    }
                ],
                "formatted_output": "",
                "token_estimate": 150
            }
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == "test-task-123"
            assert data["status"] == "completed"
            assert data["result"] is not None
            assert data["result"]["query"] == "python"
            assert data["error"] is None

    def test_get_task_failed_with_error(self):
        """Test getting status of failed task"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.status = "SUCCESS"
            mock_result.ready.return_value = True
            mock_result.successful.return_value = True
            mock_result.get.return_value = {
                "error": "Network timeout"
            }
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["error"] == "Network timeout"

    def test_get_task_failed_exception(self):
        """Test getting status when task raised exception"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.status = "FAILURE"
            mock_result.ready.return_value = True
            mock_result.successful.return_value = False
            mock_result.result = Exception("Database error")
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert "Database error" in data["error"]

    def test_get_task_status_exception_handling(self):
        """Test error handling in get_task_status"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_async_result.side_effect = Exception("Redis connection failed")

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 500
            assert "Redis connection failed" in response.json()["detail"]

    def test_get_task_in_progress(self):
        """Test getting status of in-progress task"""
        with patch("app.api.routes.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_result.status = "STARTED"
            mock_result.ready.return_value = False
            mock_async_result.return_value = mock_result

            response = client.get("/tasks/test-task-123")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"
