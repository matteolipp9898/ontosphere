# OntoSphere

**Generate OWL/RDF ontologies from documents with LLMs.**

---

## Overview

OntoSphere is an open-source application that transforms unstructured documents into structured ontologies. Upload a PDF, and OntoSphere uses LLMs to extract entities, relationships, and properties -- then assembles them into a navigable knowledge graph that you can explore, edit, and export.

## Features

- **Document upload** -- Upload PDF files; text is extracted and chunked automatically.
- **AI-powered extraction** -- LLMs (Azure OpenAI gpt-4o) identify classes, properties, and relationships with full provenance tracking.
- **Navigable graph** -- Explore ontologies in an interactive Cytoscape.js force-directed graph with pan, zoom, and node inspection.
- **Multi-format export** -- Export to JSON, Turtle (TTL), JSON-LD, and RDF/XML.
- **SHACL validation** -- Validate generated ontologies against SHACL shape constraints.
- **Ontology versioning** -- Every generation creates a version snapshot for comparison and rollback.
- **Real-time progress** -- WebSocket-based progress updates during processing.
- **Background processing** -- Long-running extraction jobs are handled asynchronously via Celery workers.

## Screenshots

![Graph View](docs/screenshots/graph.png)

## Tech Stack

| Layer     | Technology                                              |
|-----------|---------------------------------------------------------|
| Frontend  | React 18, TypeScript, Vite, Cytoscape.js, Tailwind CSS |
| Backend   | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Database  | PostgreSQL 16 + Apache AGE (graph queries)              |
| Queue     | Redis + Celery                                          |
| LLM       | Azure OpenAI / OpenAI / Anthropic (pluggable)           |
| Export    | RDFLib (Turtle, JSON-LD, RDF/XML)                       |
| Validation| pyshacl (SHACL shapes)                                  |

## Architecture

```
                   +---------------------+
                   |     Frontend         |
                   |  React + Vite        |
                   |  Port 5173           |
                   +----------+----------+
                              |
                              | REST / WebSocket
                              v
                   +----------+----------+
                   |     Backend          |
                   |  FastAPI + Uvicorn   |
                   |  Port 8000           |
                   +---+------------+----+
                       |            |
              +--------+--+    +----+--------+
              | PostgreSQL |    |    Redis    |
              | + Apache   |    | (broker +   |
              |   AGE      |    |  pub/sub)   |
              | Port 5432  |    | Port 6379   |
              +------------+    +------+------+
                                       |
                                +------+------+
                                |   Celery    |
                                |   Worker    |
                                +-------------+
```

## Quick Start

### Prerequisites

| Dependency      | Version  | Notes                              |
|-----------------|----------|------------------------------------|
| Docker          | 20.10+   | Required                           |
| Docker Compose  | 2.0+     | Required                           |
| LLM API key     | --       | Azure OpenAI, OpenAI, or Anthropic |

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ontosphere.git
cd ontosphere

# 2. Create your environment file
cp .env.example .env

# 3. Edit .env and set your LLM API key
#    ONTOSPHERE_LLM_API_KEY=your-actual-key
#    ONTOSPHERE_LLM_API_BASE=https://YOUR-RESOURCE.cognitiveservices.azure.com

# 4. Start all services
docker compose up --build

# 5. Open the application
#    Frontend:  http://localhost:5173
#    API docs:  http://localhost:8000/docs
```

Database tables are created automatically on first startup (`ONTOSPHERE_AUTO_CREATE_TABLES=true`).

To stop all services:

```bash
docker compose down        # keep data
docker compose down -v     # wipe data
```

## Configuration

All configuration is done through environment variables. Copy `.env.example` to `.env` and adjust as needed.

| Variable                          | Default                                                        | Description                                      |
|-----------------------------------|----------------------------------------------------------------|--------------------------------------------------|
| `POSTGRES_USER`                   | `ontosphere`                                                   | PostgreSQL user                                  |
| `POSTGRES_PASSWORD`               | `changeme`                                                     | PostgreSQL password                              |
| `POSTGRES_DB`                     | `ontosphere`                                                   | PostgreSQL database name                         |
| `DATABASE_URL`                    | `postgresql+asyncpg://ontosphere:changeme@postgres:5432/ontosphere` | Async SQLAlchemy connection string          |
| `REDIS_URL`                       | `redis://redis:6379/0`                                         | Redis connection URL for Celery and pub/sub      |
| `ONTOSPHERE_LLM_PROVIDER`        | `azure`                                                        | LLM provider (`openai`, `azure`, `anthropic`)    |
| `ONTOSPHERE_LLM_API_BASE`        | --                                                             | Base URL for the LLM API                         |
| `ONTOSPHERE_LLM_API_KEY`         | --                                                             | API key for the LLM provider                     |
| `ONTOSPHERE_LLM_MODEL`           | `gpt-4o`                                                       | Model / deployment name                          |
| `ONTOSPHERE_LLM_API_VERSION`     | `2024-10-21`                                                   | API version (Azure OpenAI)                       |
| `ONTOSPHERE_LLM_MAX_TOKENS`      | `16384`                                                        | Max output tokens for LLM responses              |
| `ONTOSPHERE_AUTO_CREATE_TABLES`  | `true`                                                         | Auto-create tables on startup                    |
| `CORS_ORIGINS`                    | `http://localhost:5173,http://localhost:3000`                   | Allowed CORS origins                             |
| `SECRET_KEY`                      | `change-me-in-production`                                      | Secret key for signing                           |

## API Documentation

When the backend is running, interactive API documentation is available at:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Core Endpoints

| Method | Endpoint                            | Description                        |
|--------|-------------------------------------|------------------------------------|
| GET    | `/api/health`                       | Health check                       |
| POST   | `/api/ontologies`                   | Create a new ontology              |
| GET    | `/api/ontologies`                   | List all ontologies                |
| GET    | `/api/ontologies/{id}`              | Get ontology details               |
| PUT    | `/api/ontologies/{id}`              | Update an ontology                 |
| DELETE | `/api/ontologies/{id}`              | Delete an ontology                 |
| POST   | `/api/ontologies/{id}/documents`    | Upload a document for processing   |
| POST   | `/api/ontologies/{id}/generate`     | Trigger ontology generation        |
| GET    | `/api/ontologies/{id}/graph`        | Get the ontology graph data        |
| GET    | `/api/ontologies/{id}/export/{fmt}` | Export (json, turtle, jsonld, rdfxml) |

## Development Setup (Without Docker)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start a local PostgreSQL with the AGE extension and Redis, then:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd backend
pytest -v
```

## Project Structure

```
ontosphere/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic (graph, document, LLM, export)
│   │   ├── tasks/          # Celery async tasks
│   │   └── main.py         # FastAPI application entry point
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/     # React UI components
│   │   ├── api/            # API client functions
│   │   ├── hooks/          # Custom React hooks (WebSocket, etc.)
│   │   └── App.tsx
│   ├── Dockerfile
│   └── package.json
├── docs/screenshots/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── LICENSE
└── README.md
```

## Roadmap

- [x] Document upload and text extraction (PDF)
- [x] LLM-based entity/property extraction with provenance
- [x] Automatic ontology assembly
- [x] Apache AGE graph storage
- [x] Interactive graph visualization (Cytoscape.js)
- [x] Multi-format export (JSON, Turtle, JSON-LD, RDF/XML)
- [x] SHACL validation
- [x] Ontology versioning
- [x] Real-time progress via WebSocket
- [x] Docker Compose orchestration
- [ ] Authentication and authorization (OAuth 2.0 / OIDC)
- [ ] Robust WebSocket reconnect handling
- [ ] SHACL violation visualization in graph editor
- [ ] Multi-user / multi-tenant support

## Contributing

Contributions are welcome! Please:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Make your changes and add tests.
4. Ensure all tests pass: `cd backend && pytest -v`.
5. Open a Pull Request against `main`.

## License

This project is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for the full text.
