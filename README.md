# Agent-First SERP Gateway

A resilient, token-optimized Search-to-LLM context API. This project is designed to scrape Google Search results, extract key information (including AI Overviews), and format it into clean Markdown consumed by Large Language Models. It features:
*   **Agent-Optimized Parsers**: Extracts clean text, removes ads/modals, and formats as Markdown.
*   **Multi-View Interface**: dynamic UI that allows users to view **Markdown context**, **JSON structure**, and **Vector Embeddings** simultaneously or individually with a "Display All" mode.
*   **Vector Embeddings (RAG-Ready)**: Real-time visualization of 384-dimensional vectors (using `all-MiniLM-L6-v2`) for every search result, ready for vector database insertion.
*   **Source Credibility Scoring**: Automatically scores search results (Tier 1-4) based on domain reputation (e.g., Arxiv > Commercial Blogs).
*   **Hybrid Scraping**: Falls back to direct URL scraping (ZenRows/ScrapingBee compatible) for deep content.
*   **Intelligent Deduplication**: Removes redundant information across multiple search results.
*   **Robust Caching**: Utilizes Redis to store results and optimize API calls.

## Project Structure

```text
Flux/
├── .env.example              # Template for environment variables (API keys, Redis URL)
├── docker-compose.yml        # Orchestrates Backend, Worker, Frontend, Redis, DB
├── Dockerfile                # Backend Image
├── requirements.txt          # Python dependencies (Celery, Redis, FastAPI, etc.)
│
├── frontend/                 # Client-side application
│   ├── Dockerfile            # Frontend Image (Node.js)
│   ├── package.json
│   ├── vite.config.ts        # Proxy configured for Docker
│   └── src/
│       ├── main.ts           # Frontend logic (Polling support)
│       └── ...
│
└── serp-to-context-api/      # Core Backend API
    ├── main.py               # Application entry point
    └── app/
        ├── worker.py         # Celery Worker Configuration
        ├── api/routes.py     # Async Task Endpoints
        └── ...
```
## Process Pipeline

```mermaid
graph TD
    A["User Request"] --> B{"Check Redis Cache"}
    B -- Hit --> C["Return Cached Data"]
    B -- Miss --> D["Dispatch Async Task (Push to Redis)"]
    D -.->|Task ID| E["Return HTTP 202 Accepted"]
    D -.->|Queue| F
    E -.->|Trigger| L

    subgraph "Celery Worker"
        F["Queue: Scrape Task"] --> G["Hybrid Scraper"]
        G --> H["Parser & Cleaner"]
        H --> I["Formatter (Markdown)"]
        I --> J["Embedding Service"]
        J --> K["Save Result to Redis"]
    end

    subgraph "Frontend Polling"
        L["Poll Status /tasks/{id}"] --> N{"Check Redis"}
        N -- Ready --> M["Display Result"]
        N -- Pending --> L
    end
```

1.  **Request**: User sends query + config (Region, Language, Limit).
2.  **Cache Layer**: Checks Redis for existing identical requests.
3.  **Scraping**: If fresh, uses the optimal provider (SerpApi/Tavily/etc.) to fetch results.
4.  **Processing**:
    *   **Parsing**: Extracts main content, stripping ads and clutter.
    *   **Formatting**: Converts HTML/Text to clean Markdown.
    *   **Embedding**: Generates 384-d vectors for each result snippet.
5.  **Response**: Returns the structured data (JSON), human-readable context (Markdown), and vector arrays.

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

# Database Configuration
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=flux_db
DATABASE_URL=postgresql://user:password@localhost:5432/flux_db
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


### 2. Frontend (Development)

To run the frontend in development mode with hot-reloading:

```bash
cd frontend
npm install
npm run dev
```

---

## Docker Support

For a production-like environment with all services wired together:

```bash
docker compose up --build
```

## Service Access Points

All services are accessible at the following endpoints:

| Service | URL | Description |
| :--- | :--- | :--- |
| **Frontend** | [http://localhost:5173](http://localhost:5173) | Main User Interface |
| **API API** | [http://localhost:8000](http://localhost:8000) | Backend REST API |
| **API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger Documentation |
| **Grafana** | [http://localhost:3000](http://localhost:3000) | Monitoring Dashboard (`admin`/`admin`) |
| **Prometheus**| [http://localhost:9090](http://localhost:9090) | Metric Collection |
| **Redis** | `localhost:6380` | Cache (TCP) |

## Observability & Monitoring

The system comes with a built-in monitoring stack to track scraping performance, latency, and costs.

### 1. Grafana Dashboards (Visual)
Access Grafana at **[http://localhost:3000](http://localhost:3000)**.
- **Login**: `admin` / `admin`
- **Setup**:
    1. Go to **Connections > Data Sources**.
    2. Add **Prometheus**.
    3. URL: `http://prometheus:9090`.
    4. Save & Test.

### 2. Prometheus Metrics (Data)
The API exposes raw metrics at `http://localhost:8000/metrics`.
- `flux_scrape_duration_seconds`: Histogram of scrape latency (P50, P90, P99).
- `flux_scrape_requests_total`: Counter for scraping success/failure rates per provider.
