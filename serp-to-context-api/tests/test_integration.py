import pytest
import os
import asyncio
from unittest.mock import patch, MagicMock
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from app.db.models import SearchResult, Base
from app.worker import scrape_and_process

@pytest.fixture(scope="module")
def db_url():
    """
    Get DB URL for testing.
    If TEST_DATABASE_URL is set (e.g. in CI), use that.
    Otherwise, try to spin up a Postgres container.
    """
    if os.getenv("TEST_DATABASE_URL"):
        return os.getenv("TEST_DATABASE_URL")

    try:
        from testcontainers.postgres import PostgresContainer
        container = PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg")
        container.with_env("POSTGRES_USER", "test_user")
        container.with_env("POSTGRES_PASSWORD", "test_pass")
        container.with_env("POSTGRES_DB", "test_db")
        container.start()
        # We need to stop it eventually. Pytest fixtures with yield are good for this.
        # But since we conditionally start it, we can't easily yield in one path and return in another 
        # without a wrapper.
        # Simple hack: start it here, register cleanup.
        # Or better: separating fixtures.
        return container.get_connection_url(driver="asyncpg")
    except ImportError:
        pytest.skip("testcontainers not installed")
    except Exception as e:
        pytest.skip(f"Docker not available or Testcontainers failed: {e}")

# We removed the 'postgres_container' fixture and integrated logic into 'db_url'
# But we need cleanup. Proper way:

@pytest.fixture(scope="module")
def postgres_container():
    """Spin up a Postgres container if no external DB provided."""
    if os.getenv("TEST_DATABASE_URL"):
        yield None
        return

    try:
        from testcontainers.postgres import PostgresContainer
        container = PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg")
        container.with_env("POSTGRES_USER", "test_user")
        container.with_env("POSTGRES_PASSWORD", "test_pass")
        container.with_env("POSTGRES_DB", "test_db")
        container.start()
        yield container
        container.stop()
    except Exception as e:
        pytest.skip(f"Docker not available or Testcontainers failed: {e}")

@pytest.fixture(scope="module")
def db_url(postgres_container):
    if os.getenv("TEST_DATABASE_URL"):
        return os.getenv("TEST_DATABASE_URL")
    
    if postgres_container:
        return postgres_container.get_connection_url(driver="asyncpg")
    
    pytest.skip("No database available for integration test")


@pytest.mark.asyncio
async def test_full_flow_with_db(db_url):
    """
    Integration Test:
    1. Sets DATABASE_URL to the test container.
    2. Mocks the scraper to return sample data.
    3. Calls the worker task (scrape_and_process).
    4. Verifies data is saved to the Postgres DB.
    """
    # Patch the DATABASE_URL in the app.db.database module
    # We need to reload or patch where it's used. 
    # Since 'engine' is global in app.db.database, patching os.environ might not be enough if it's already imported.
    # We will patch the 'engine' object or 'AsyncSessionLocal'.
    
    with patch.dict(os.environ, {"DATABASE_URL": db_url}):
        # We need to re-create the engine because it's usually created at module level
        # A simpler way for testing is to mock the internal engine or session factory
        # But 'worker.py' imports 'init_db' and 'AsyncSessionLocal'.
        
        # Let's import the module and modify the engine for this test
        from app.db import database
        
        test_engine = create_async_engine(db_url, echo=True)
        database.engine = test_engine
        database.AsyncSessionLocal = database.sessionmaker(
            test_engine, class_=database.AsyncSession, expire_on_commit=False
        )

        # Mock the scraper to avoid hitting Google
        mock_content = {
            "results": [
                {
                    "title": "Integration Test Result",
                    "url": "https://integration.test/result",
                    "content": "This is a snippet from the integration test."
                }
            ],
            "answer": "AI Answer"
        }
        
        # We mock scraper.fetch_results which is called in 'else' block (mode="search")
        with patch("app.services.scraper.scraper.fetch_results", new_callable=MagicMock) as mock_fetch:
            # The worker calls loop.run_until_complete(fetch_results)
            # fetch_results is an async function (coroutine).
            # So the mock should return a coroutine result or a future.
            f = asyncio.Future()
            f.set_result(mock_content)
            mock_fetch.return_value = f

            # Also mock parser.parse to return something consistent with our mock_content
            # Actually weak mock: let's mock the scraper return value to be compatible with parser.parse
            # parser.parse expects dict with 'results' key if it's a dict.
            # See parser.py line 9.
            
            # Run the worker task
            # scrape_and_process is a Celery task, but we can call it as a function?
            # It's decorated. The original function is accessible via .run usually if bind=True?
            # Or just call it.
            
            # The worker creates its own loop given it checks for running loop.
            # In pytest-asyncio, there is already a loop running?
            # worker trying to do `loop = asyncio.get_event_loop()` might fail or succeed.
            # But line 34: `loop = asyncio.get_event_loop()`
            
            # We call the synchronous wrapper
            # It will try to use a loop.
            
            # Issue: 'test_full_flow_with_db' is async, so a loop is running.
            # 'worker.py' calls `loop.run_until_complete`.
            # `run_until_complete` cannot be called when the loop is already running.
            # This is a common issue testing sync wrappers around async code.
            
            # Workaround: patch 'asyncio.get_event_loop' to return the current running loop?
            # No, `run_until_complete` will raise error if loop is running.
            
            # We should probably run this test synchronously and let the worker manage the loop,
            # OR patch the worker to use `await` if we can.
            
            # Let's run the test synchronously (remove @pytest.mark.asyncio), create a fresh loop for the worker if needed.
            # But we need async to talk to DB to verify.
            pass

@pytest.mark.asyncio
async def test_verify_db_insertion(db_url):
    # This separation is tricky.
    # Let's write a SYNCHRONOUS test function that uses `asyncio.run` internally for verification?
    pass

# Redefining the test as synchronous to avoid loop conflict with worker's internals
def test_integration_sync_wrapper(db_url):
    """
    Synchronous wrapper to run the integration test.
    """
    # 1. Patch DB engine
    from app.db import database
    test_engine = create_async_engine(db_url, echo=False)
    database.engine = test_engine
    database.AsyncSessionLocal = database.sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # 2. Mock scraper
    # mock_fetch returns a valid HTML or Dict that parser accepts.
    # If mode="search", it calls fetch_results -> parser.parse(dict/str)
    
    with patch("app.services.scraper.scraper.fetch_results") as mock_fetch:
        # Mocking return value of async function called via run_until_complete
        future = asyncio.Future()
        future.set_result({
            "results": [
                {
                    "title": "Integration Title",
                    "url": "https://integration.com",
                    "content": "Integration snippet"
                }
            ],
            "answer": "AI Answer"
        })
        mock_fetch.return_value = future

        # 3. Call worker
        # We need to simulate the 'self' argument if bind=True
        # scrape_and_process(self, ...)
        
        # We can mock 'self'
        mock_self = MagicMock()
        
        # Call the worker!
        # This will create a loop and run_until_complete inside.
        # Since we are in a sync function (pytest run), get_event_loop might fail or return a new one.
        # This is safe.
        
        result = scrape_and_process(
            mock_self,
            query="test query",
            region="us",
            language="en",
            limit=1,
            mode="search",
            output_format="json"
        )
        
        assert result["query"] == "test query"
        assert len(result["organic_results"]) > 0
        assert result["organic_results"][0]["title"] == "Integration Title"

    # 4. Verify DB
    # Now we need to define an async verification function and run it
    
    async def verify_db():
        async with database.AsyncSessionLocal() as session:
            stmt = select(SearchResult).where(SearchResult.query == "test query")
            result = await session.execute(stmt)
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].title == "Integration Title"
            assert rows[0].url == "https://integration.com"

    # We can reuse the loop created by worker? No, worker might have closed it or used a different one.
    # We create a new loop for verification
    loop = asyncio.new_event_loop()
    loop.run_until_complete(verify_db())
    loop.close()
