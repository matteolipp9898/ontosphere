# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-19

### Added

- PDF document upload with automatic text extraction and chunking.
- LLM-powered entity and property extraction (Azure OpenAI, OpenAI, Anthropic).
- Automatic ontology assembly with deduplication and hierarchy inference.
- Apache AGE graph storage with per-ontology named graphs.
- Interactive Cytoscape.js force-directed graph visualization.
- Multi-format export: JSON, Turtle (TTL), JSON-LD, RDF/XML.
- SHACL validation of generated ontologies via pyshacl.
- Ontology versioning with snapshot creation on each generation.
- Real-time WebSocket progress updates during processing.
- Background task processing via Celery + Redis.
- Docker Compose orchestration for all services (frontend, backend, PostgreSQL + AGE, Redis).

### Known Issues

- No authentication or authorization; intended for local / trusted-network use only.
- WebSocket reconnection after network interruption is not yet handled gracefully.
- SHACL violation details are not yet surfaced in the graph editor UI.
