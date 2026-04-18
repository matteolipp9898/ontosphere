# OntoSphere

**Auto-generate rich ontologies from documents using Large Language Models.**

---

## Overview

OntoSphere is an open-source application that transforms unstructured documents into structured ontologies. Upload a PDF, Word document, or plain text file, and OntoSphere will use LLMs to extract entities, relationships, and properties -- then assemble them into a standards-compliant ontology that you can explore, edit, and export.

The generated ontologies are stored as property graphs in Apache AGE (a PostgreSQL extension), visualized in an interactive force-directed graph, and exportable to industry-standard formats such as RDF/OWL (Turtle), JSON-LD, and RDF/XML.

## Key Features

- **Document ingestion** -- Upload PDF, DOCX, TXT, and Markdown files for processing.
- **LLM-powered extraction** -- Leverage OpenAI, Azure OpenAI, or Anthropic models to identify classes, properties, and relationships.
- **Interactive graph visualization** -- Explore ontologies in a force-directed graph with pan, zoom, and node inspection.
- **Multi-format export** -- Export to Turtle (TTL), JSON-LD, RDF/XML, or raw JSON.
- **SHACL validation** -- Validate generated ontologies against configurable SHACL shape constraints.
- **Iterative refinement** -- Ask the LLM to expand, merge, or restructure parts of the ontology conversationally.
- **Background processing** -- Long-running extraction jobs are handled asynchronously via Celery workers.
- **Version history** -- Every ontology mutation is recorded so you can diff and rollback.

## Architecture

```
                   +---------------------+
                   |     Frontend         |
                   |   (React + Vite)     |
                   |   Port 5173          |
                   +----------+----------+
                              |
                              | REST API
                              v
                   +----------+----------+
                   |     Backend          |
                   |  (FastAPI + Uvicorn) |
                   |   Port 8000          |
                   +---+------------+----+
                       |            |
              +--------+--+    +----+--------+
              |  PostgreSQL |    |    Redis    |
              | + Apache AGE|    | (broker +   |
              |  Port 5432  |    |  cache)     |
              +-------------+    |  Port 6379  |
                                 +------+------+
                                        |
                                 +------+------+
                                 |   Celery    |
                                 |   Worker    |
                                 +-------------+
```

## Prerequisites

| Dependency      | Version  | Notes                          |
|-----------------|----------|--------------------------------|
| Docker          | 20.10+   | Required                       |
| Docker Compose  | 2.0+     | Required                       |
| LLM API key     | --       | OpenAI, Azure OpenAI, or Anthropic |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ontosphere.git
cd ontosphere

# 2. Create your environment file
cp .env.example .env

# 3. Add your LLM API key
#    Edit .env and set ONTOSPHERE_LLM_API_KEY to a valid key

# 4. Start all services
docker compose up --build

# 5. Open the application
#    Frontend:  http://localhost:5173
#    API docs:  http://localhost:8000/docs
```

To stop all services:

```bash
docker compose down
```

To stop and remove all data (including the database volume):

```bash
docker compose down -v
```

## Configuration

All configuration is done through environment variables. Copy `.env.example` to `.env` and adjust as needed.

| Variable                      | Default                                                        | Description                                      |
|-------------------------------|----------------------------------------------------------------|--------------------------------------------------|
| `DATABASE_URL`                | `postgresql+asyncpg://ontosphere:ontosphere@postgres:5432/ontosphere` | Async SQLAlchemy database connection string      |
| `REDIS_URL`                   | `redis://redis:6379/0`                                         | Redis connection URL for Celery and caching      |
| `ONTOSPHERE_LLM_API_BASE`    | `https://api.openai.com/v1`                                    | Base URL for the LLM API                         |
| `ONTOSPHERE_LLM_API_KEY`     | `sk-your-key-here`                                             | API key for the LLM provider                     |
| `ONTOSPHERE_LLM_MODEL`       | `gpt-4o`                                                       | Model identifier                                 |
| `ONTOSPHERE_LLM_PROVIDER`    | `openai`                                                       | LLM provider (`openai`, `azure`, `anthropic`)    |
| `ONTOSPHERE_LLM_API_VERSION` | `2024-10-21`                                                   | API version (used by Azure OpenAI)               |
| `SECRET_KEY`                  | `change-me-in-production`                                      | Secret key for signing tokens and sessions       |
| `CORS_ORIGINS`                | `http://localhost:5173,http://localhost:3000`                   | Comma-separated list of allowed CORS origins     |

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
| GET    | `/api/ontologies/{id}/export/{fmt}` | Export ontology (turtle, jsonld, rdfxml) |

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

## Tech Stack

| Layer     | Technology                                              |
|-----------|---------------------------------------------------------|
| Frontend  | React 18, TypeScript, Vite, Zustand, React Flow, Tailwind CSS |
| Backend   | Python 3.11, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Database  | PostgreSQL 16 + Apache AGE (graph queries)              |
| Queue     | Redis + Celery                                          |
| LLM       | OpenAI / Azure OpenAI / Anthropic (pluggable)           |
| Export    | RDFLib (Turtle, JSON-LD, RDF/XML)                       |
| Validation| pyshacl (SHACL shapes)                                  |

## Project Structure

```
ontosphere/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── core/           # Configuration, database, security
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic (ontology, document, LLM, export)
│   │   ├── tasks.py        # Celery async tasks
│   │   └── main.py         # FastAPI application entry point
│   ├── tests/              # Pytest test suite
│   ├── shapes.ttl          # SHACL validation shapes
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/     # React UI components
│   │   ├── pages/          # Route-level page components
│   │   ├── store/          # Zustand state management
│   │   ├── api/            # API client functions
│   │   ├── types/          # TypeScript type definitions
│   │   └── App.tsx         # Root application component
│   ├── Dockerfile
│   └── package.json
├── examples/               # Sample documents and expected outputs
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Roadmap

### Phase 1 -- MVP (current)
- [x] Document upload and text extraction
- [x] LLM-based ontology generation
- [x] Interactive graph visualization
- [x] Multi-format export (Turtle, JSON-LD, RDF/XML)
- [x] SHACL validation
- [x] Background job processing with Celery

### Phase 2 -- Connectors
- [ ] SharePoint document connector
- [ ] Confluence page connector
- [ ] Google Drive integration
- [ ] Batch processing for document collections

### Phase 3 -- Enterprise
- [ ] Authentication and authorization (OAuth 2.0 / OIDC)
- [ ] Multi-tenant workspace support
- [ ] Role-based access control
- [ ] Audit logging
- [ ] LDAP / Active Directory integration

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`.
3. Make your changes and add tests.
4. Ensure all tests pass: `cd backend && pytest -v`.
5. Commit with a clear message: `git commit -m "Add my feature"`.
6. Push to your fork: `git push origin feature/my-feature`.
7. Open a Pull Request against `main`.

Please make sure your code:
- Passes all existing tests.
- Includes tests for new functionality.
- Follows the existing code style (run `ruff check` for Python, `npm run lint` for TypeScript).

## License

This project is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for the full text.
