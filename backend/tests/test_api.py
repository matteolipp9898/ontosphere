"""Integration tests for the OntoSphere REST API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """GET /api/health returns 200 with a status field."""
    response = await async_client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Ontology CRUD via API
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_ontology_api(async_client: AsyncClient):
    """POST /api/ontologies creates a new ontology and returns 201."""
    payload = {
        "name": "API Test Ontology",
        "description": "Created via integration test",
        "namespace_uri": "http://example.org/api-test#",
    }
    response = await async_client.post("/api/ontologies", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "API Test Ontology"
    assert data["description"] == "Created via integration test"
    assert "id" in data
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_list_ontologies_api(async_client: AsyncClient):
    """GET /api/ontologies returns 200 with a list of ontologies."""
    # Seed two ontologies
    await async_client.post(
        "/api/ontologies",
        json={
            "name": "Onto A",
            "description": "First",
            "namespace_uri": "http://example.org/a#",
        },
    )
    await async_client.post(
        "/api/ontologies",
        json={
            "name": "Onto B",
            "description": "Second",
            "namespace_uri": "http://example.org/b#",
        },
    )

    response = await async_client.get("/api/ontologies")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

    names = {item["name"] for item in data}
    assert "Onto A" in names
    assert "Onto B" in names


@pytest.mark.asyncio
async def test_get_ontology_api(async_client: AsyncClient):
    """GET /api/ontologies/{id} returns 200 with the requested ontology."""
    # Create an ontology first
    create_resp = await async_client.post(
        "/api/ontologies",
        json={
            "name": "Fetch Me",
            "description": "To be fetched",
            "namespace_uri": "http://example.org/fetch#",
        },
    )
    assert create_resp.status_code == 201
    ontology_id = create_resp.json()["id"]

    # Fetch it
    response = await async_client.get(f"/api/ontologies/{ontology_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == ontology_id
    assert data["name"] == "Fetch Me"
