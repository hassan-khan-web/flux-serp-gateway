# Agent-First SERP Gateway

A resilient, token-optimized **Just-in-Time Key (JIT) Knowledge Graphing Engine**. 

Flux is not just a search tool; it is **autonomous knowledge acquisition engine**. It solves the "Cold Start" problem for RAG applications by allowing them to build their knowledge base *actively* and *on-demand*.

Instead of staring at an empty Vector DB or relying on stale datasets, Flux allows your application to learn in real-time. When a user asks a question, Flux goes out, fetches the latest state of the world, cleans it, embeds it, and permanently writes that knowledge into your database. It turns a "dumb" database into a **smart, self-learning organism**.

### Key Features
*   **Agent-Optimized Parsers**: Extracts clean text, removes ads/modals, and formats as Markdown (~40% token saving).
*   **Active RAG Infrastructure**: Generates 384-dimensional vectors (`all-MiniLM-L6-v2`) in real-time for every result.
*   **Hybrid Scraping**: Falls back to direct URL scraping (ZenRows/ScrapingBee compatible) for deep content.
*   **Source Credibility Scoring**: Automatically scores search results (Tier 1-4) based on domain reputation.
*   **Intelligent Deduplication**: Removes redundant information across multiple search results.
*   **Robust Observability**: Full Prometheus/Grafana stack to track data ingestion and scrape health.

## The Core Concept: Self-Populating Vector Database

Flux operates on a simple but powerful premise: **Don't scrape the internet. Scrape what your users care about.**

1.  **Day 1, Query 1 Availability**: You don't need to pre-fill your database. The first query populates the first node of knowledge.
2.  **Zero Data Rot**: Unlike CommonCrawl or static datasets, your vectors are generated at the moment of query, guaranteeing freshness.
3.  **Cost-Efficient Scaling**: You only pay to vectorize the specific domains and topics your users actually request.

This transforms your RAG pipeline from a passive retrieval system into an **Active Intelligence Gathering System**.

## Project Structure

```text
Flux/
├── .env.example              # Template for environment variables
├── docker-compose.yml        # Orchestrates services (Backend, Frontend, etc.)
├── Dockerfile                # Backend Docker Image
├── prometheus.yml            # Prometheus Monitoring Config
├── requirements.txt          # Python dependencies
│
├── frontend/                 # Client-side application
│   ├── Dockerfile            # Frontend Docker Image
│   ├── index.html            # Entry HTML
│   ├── package.json          # Node dependencies
│   ├── tsconfig.json         # TypeScript config
│   ├── vite.config.ts        # Vite Build config
│   └── src/
│       ├── main.ts           # Core Application Logic
│       ├── marked.js         # Markdown rendering lib
│       └── style.css         # Global Styles
│
└── serp-to-context-api/      # Core Backend API
    ├── main.py               # FastAPI Entry Point
    └── app/
        ├── worker.py         # Celery Worker Entry Point
        ├── api/
        │   ├── routes.py     # API Endpoints
        │   └── schemas.py    # Pydantic Models
        ├── services/
        │   ├── embeddings.py # Vector Generation (SentenceTransformers)
        │   ├── formatter.py  # Markdown Formatting
        │   ├── parser.py     # HTML Parsing & Cleaning
        │   └── scraper.py    # Hybrid Scraper (Tavily/ScrapingBee)
        └── utils/
            ├── cache.py      # Redis Caching Wrapper
            └── logger.py     # Structured Logging
```
## Process Pipeline



```mermaid
graph TD
    A["User Request"] <--> B{"Check Redis Cache"}
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
        L["Poll Status /tasks/{id}"] <--> N{"Check Redis"}
        N -- Ready --> M["Display Result"]
        N -- Pending --> L
    end

    subgraph "Observability"
        P["Prometheus"] <-.->|Scrape /metrics| D
        P <-.->|Scrape /metrics| G
        O["Grafana"] <--> P
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
6.  **Observability (Background)**: Prometheus scrapes metrics from the API and Worker; Grafana visualizes them.

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

## Future Roadmap

The vision for Flux extends beyond simple scraping. We are building the standard for **Autonomous Knowledge Acquisition**.

*   **Security & Multi-Tenancy**:
    *   [ ] Implement API Key authentication for secure access.
    *   [ ] Multi-tenant vector storage (separate namespaces for different client apps).

*   **Advanced RAG Capabilities**:
    *   [ ] **Recursive Search**: Allow the agent to perform follow-up searches based on initial findings to build deeper context.
    *   [ ] **Graph Construction**: Automatically link related entities across different search sessions to build a true Knowledge Graph.
    *   [ ] **Semantic Cache**: Use vector similarity to serve previous answers even if the exact query wording is different.

*   **Enterprise Integrations**:
    *   [ ] Direct connectors for Pinecone, Weaviate, and Qdrant (Push-to-DB).
    *   [ ] Webhook system to notify external apps when knowledge ingestion is complete.

