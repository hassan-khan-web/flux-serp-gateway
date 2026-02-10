import pytest
from pydantic import ValidationError
from app.api.schemas import (
    SearchRequest,
    SearchResponse,
    OrganicResult,
    TaskResponse
)


class TestSearchRequestSchema:
    """Test SearchRequest Pydantic model validation"""

    def test_search_request_minimal(self):
        """Test creating SearchRequest with only required field"""
        request = SearchRequest(query="python")
        
        assert request.query == "python"
        assert request.region == "us"  # default
        assert request.language == "en"  # default
        assert request.limit == 10  # default
        assert request.mode == "search"  # default
        assert request.output_format == "markdown"  # default

    def test_search_request_full(self):
        """Test creating SearchRequest with all fields"""
        request = SearchRequest(
            query="machine learning",
            region="uk",
            language="es",
            output_format="json",
            mode="scrape",
            limit=20
        )
        
        assert request.query == "machine learning"
        assert request.region == "uk"
        assert request.language == "es"
        assert request.limit == 20
        assert request.mode == "scrape"
        assert request.output_format == "json"

    def test_search_request_missing_query(self):
        """Test validation error when query is missing"""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest()
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("query",) for error in errors)

    def test_search_request_query_not_string(self):
        """Test validation error when query is not string"""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(query=123)
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("query",) for error in errors)

    def test_search_request_limit_negative(self):
        """Test that negative limit is accepted (validation not enforced)"""
        # Pydantic doesn't validate negative by default
        request = SearchRequest(query="test", limit=-5)
        assert request.limit == -5

    def test_search_request_empty_query(self):
        """Test empty query string is accepted"""
        request = SearchRequest(query="")
        assert request.query == ""


class TestOrganicResultSchema:
    """Test OrganicResult Pydantic model"""

    def test_organic_result_minimal(self):
        """Test creating OrganicResult with required fields"""
        result = OrganicResult(
            title="Example Title",
            url="https://example.com",
            snippet="This is a snippet"
        )
        
        assert result.title == "Example Title"
        assert result.url == "https://example.com"
        assert result.snippet == "This is a snippet"
        assert result.score == 0.0  # default
        assert result.embedding is None  # default

    def test_organic_result_full(self):
        """Test OrganicResult with all fields"""
        result = OrganicResult(
            title="ML Article",
            url="https://ml.example.com",
            snippet="About machine learning",
            score=0.95,
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
        )
        
        assert result.score == 0.95
        assert result.embedding == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_organic_result_missing_title(self):
        """Test validation error when title missing"""
        with pytest.raises(ValidationError):
            OrganicResult(url="https://example.com", snippet="test")

    def test_organic_result_missing_url(self):
        """Test validation error when url missing"""
        with pytest.raises(ValidationError):
            OrganicResult(title="Title", snippet="test")

    def test_organic_result_missing_snippet(self):
        """Test validation error when snippet missing"""
        with pytest.raises(ValidationError):
            OrganicResult(title="Title", url="https://example.com")

    def test_organic_result_score_bounds(self):
        """Test that score outside 0-1 range is accepted"""
        # Pydantic float doesn't enforce bounds by default
        result = OrganicResult(
            title="Test",
            url="https://test.com",
            snippet="test",
            score=1.5
        )
        assert result.score == 1.5


class TestSearchResponseSchema:
    """Test SearchResponse Pydantic model"""

    def test_search_response_minimal(self):
        """Test creating SearchResponse with required fields"""
        response = SearchResponse(
            query="test",
            formatted_output="# Test\nFormatted output",
            token_estimate=100,
            cached=False
        )
        
        assert response.query == "test"
        assert response.formatted_output == "# Test\nFormatted output"
        assert response.token_estimate == 100
        assert response.cached is False
        assert response.ai_overview is None  # optional
        assert response.organic_results == []  # default

    def test_search_response_full(self):
        """Test SearchResponse with all fields"""
        results = [
            OrganicResult(
                title="Result 1",
                url="https://one.com",
                snippet="First result",
                score=0.9
            ),
            OrganicResult(
                title="Result 2",
                url="https://two.com",
                snippet="Second result",
                score=0.8
            )
        ]
        
        response = SearchResponse(
            query="python programming",
            ai_overview="Python is a versatile language",
            organic_results=results,
            formatted_output="# Python Programming\nDetails...",
            token_estimate=250,
            cached=True
        )
        
        assert response.query == "python programming"
        assert response.ai_overview == "Python is a versatile language"
        assert len(response.organic_results) == 2
        assert response.cached is True

    def test_search_response_missing_query(self):
        """Test validation error when query missing"""
        with pytest.raises(ValidationError):
            SearchResponse(
                formatted_output="test",
                token_estimate=100,
                cached=False
            )

    def test_search_response_missing_formatted_output(self):
        """Test validation error when formatted_output missing"""
        with pytest.raises(ValidationError):
            SearchResponse(
                query="test",
                token_estimate=100,
                cached=False
            )

    def test_search_response_token_estimate_negative(self):
        """Test negative token_estimate is accepted"""
        response = SearchResponse(
            query="test",
            formatted_output="output",
            token_estimate=-50,
            cached=False
        )
        assert response.token_estimate == -50

    def test_search_response_large_organic_results(self):
        """Test SearchResponse with many results"""
        results = [
            OrganicResult(
                title=f"Result {i}",
                url=f"https://result{i}.com",
                snippet=f"Snippet {i}",
                score=0.9 - (i * 0.05)
            )
            for i in range(100)
        ]
        
        response = SearchResponse(
            query="large test",
            organic_results=results,
            formatted_output="Large output",
            token_estimate=5000,
            cached=False
        )
        
        assert len(response.organic_results) == 100


class TestTaskResponseSchema:
    """Test TaskResponse Pydantic model"""

    def test_task_response_pending(self):
        """Test TaskResponse for pending task"""
        response = TaskResponse(
            task_id="task-123",
            status="pending"
        )
        
        assert response.task_id == "task-123"
        assert response.status == "pending"
        assert response.result is None
        assert response.error is None

    def test_task_response_completed(self):
        """Test TaskResponse for completed task"""
        search_result = SearchResponse(
            query="test",
            formatted_output="output",
            token_estimate=100,
            cached=False
        )
        
        response = TaskResponse(
            task_id="task-456",
            status="completed",
            result=search_result
        )
        
        assert response.status == "completed"
        assert response.result is not None
        assert response.result.query == "test"

    def test_task_response_failed(self):
        """Test TaskResponse for failed task"""
        response = TaskResponse(
            task_id="task-789",
            status="failed",
            error="Network timeout error"
        )
        
        assert response.status == "failed"
        assert response.error == "Network timeout error"
        assert response.result is None

    def test_task_response_missing_task_id(self):
        """Test validation error when task_id missing"""
        with pytest.raises(ValidationError):
            TaskResponse(status="pending")

    def test_task_response_missing_status(self):
        """Test validation error when status missing"""
        with pytest.raises(ValidationError):
            TaskResponse(task_id="task-123")

    def test_task_response_all_fields(self):
        """Test TaskResponse with result and error (edge case)"""
        search_result = SearchResponse(
            query="test",
            formatted_output="output",
            token_estimate=100,
            cached=False
        )
        
        response = TaskResponse(
            task_id="task-999",
            status="completed",
            result=search_result,
            error="Warning: partial results"
        )
        
        assert response.result is not None
        assert response.error is not None
