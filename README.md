# Agent-First SERP Gateway

A resilient, token-optimized Search-to-LLM context API. This project is designed to scrape Google Search results, extract key information (including AI Overviews), and format it into clean Markdown consumed by Large Language Models. It features a hybrid scraping strategy, intelligent parsing, deduplication, and caching to ensure high-quality context retrieval.

## Project Structure

```text
Flux/
├── .env.example              # Template for environment variables (API keys, Redis URL)
├── docker-compose.yml        # Orchestrates Backend (API) + Redis services
├── Dockerfile                # Production-ready Docker image for FastAPI backend
├── requirements.txt          # Python dependencies (FastAPI, Uvicorn, BeautifulSoup, etc.)
│
├── frontend/                 # Client-side application (Vite + TypeScript)
│   ├── package.json          # Node dependencies & scripts
│   ├── vite.config.ts        # Build config (outputs to backend static folder)
│   └── src/
│       ├── main.ts           # Frontend logic (Search UI code, Markdown rendering)
│       └── style.css         # Styling for the chat/search interface & tables
│
└── serp-to-context-api/      # Core Backend API
    ├── main.py               # Application entry point & static file serving
    └── app/
        ├── api/
        │   ├── routes.py     # API endpoints (/search, /health)
        │   └── schemas.py    # Pydantic models for request/response validation
        │
        ├── services/
        │   ├── scraper.py    # Hybrid scraping logic (SerpApi/Tavily/ScrapingBee)
        │   ├── parser.py     # HTML parsing & content extraction heuristics
        │   └── formatter.py  # Cleans & structures data into Markdown for LLMs
        │
        └── utils/
            ├── cache.py      # Redis caching wrapper implementation
            └── logger.py     # Centralized logging configuration
```


## Setup & Configuration

### Environment Variables

Create a `.env` file in the root directory. You can copy the example content:

```bash
cp .env.example .env
```

**Environment Variables Required:**

```ini
SCRAPINGBEE_API_KEY=
ZENROWS_API_KEY=
TAVILY_API_KEY=
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
```

## Running Locally

### 1. Backend API

Ensure you have a Redis instance running locally (default port `6379`).

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
cd serp-to-context-api
uvicorn main:app --reload
```

**App will be available at:**

- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

### 2. Frontend (Development)

To run the frontend in development mode with hot-reloading:

```bash
cd frontend
npm install
npm run dev
```

**Frontend**: http://localhost:5173 (typical Vite default)

---

## Docker Support

For a production-like environment with all services wired together:

```bash
docker compose up --build
```

**Docker Services:**

- **App**: http://localhost:8000
- **Redis**: localhost:6380 (mapped from container 6379)
