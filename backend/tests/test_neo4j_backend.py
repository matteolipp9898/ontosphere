"""Integration tests for the Neo4j graph backend.

These tests require a running Neo4j instance (e.g. via docker compose --profile neo4j).
They are automatically skipped if Neo4j is not available or the `neo4j` package
is not installed.

Run with:
    GRAPH_BACKEND=neo4j NEO4J_URI=bolt://localhost:7687 pytest tests/test_neo4j_backend.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio

# Skip entire module if neo4j package is not installed
neo4j = pytest.importorskip("neo4j")

from neo4j import AsyncGraphDatabase

from app.services.graph_backend import GraphData, GraphEdge, GraphNode
from app.services.neo4j_backend import Neo4jBackend

pytestmark = pytest.mark.asyncio


NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "ontosphere")


@pytest_asyncio.fixture
async def driver():
    """Create an async Neo4j driver for each test."""
    drv = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        async with drv.session() as session:
            await session.run("RETURN 1")
    except Exception:
        pytest.skip(f"Neo4j not available at {NEO4J_URI}")
    yield drv
    await drv.close()


@pytest_asyncio.fixture
async def backend(driver) -> Neo4jBackend:
    return Neo4jBackend(driver)


@pytest.fixture
def ontology_id() -> uuid.UUID:
    """Generate a unique ontology ID for test isolation."""
    return uuid.uuid4()


@pytest_asyncio.fixture(autouse=True)
async def cleanup(backend, ontology_id):
    """Clean up the test graph after each test."""
    yield
    await backend.drop_graph(None, ontology_id)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_graph(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test graph creation (index creation)."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    # Should not raise


@pytest.mark.asyncio
async def test_add_and_get_class(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test adding a class and retrieving it."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    await backend.add_class(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/Building",
        label="Building",
        description="A structure",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.nodes) == 1
    assert graph.nodes[0].uri == "http://example.org/Building"
    assert graph.nodes[0].label == "Building"
    assert graph.nodes[0].node_type == "class"


@pytest.mark.asyncio
async def test_add_class_with_parent(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test adding a class with a parent relationship."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    await backend.add_class(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/Structure",
        label="Structure",
    )
    await backend.add_class(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/Building",
        label="Building",
        parent_uri="http://example.org/Structure",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].edge_type == "SUBCLASS_OF"
    assert graph.edges[0].source_uri == "http://example.org/Building"
    assert graph.edges[0].target_uri == "http://example.org/Structure"


@pytest.mark.asyncio
async def test_get_class_uris(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test retrieving class URIs."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    await backend.add_class(None, ontology_id, uri="http://example.org/A", label="A")  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/B", label="B")  # type: ignore[arg-type]

    uris = await backend.get_class_uris(None, ontology_id)  # type: ignore[arg-type]
    assert set(uris) == {"http://example.org/A", "http://example.org/B"}


@pytest.mark.asyncio
async def test_update_class(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test updating class properties."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/X", label="X")  # type: ignore[arg-type]

    await backend.update_class(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/X",
        label="Updated",
        description="New desc",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    node = graph.nodes[0]
    assert node.label == "Updated"
    assert node.description == "New desc"


@pytest.mark.asyncio
async def test_delete_class(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test deleting a class."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/X", label="X")  # type: ignore[arg-type]

    await backend.delete_class(None, ontology_id, uri="http://example.org/X")  # type: ignore[arg-type]

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.nodes) == 0


@pytest.mark.asyncio
async def test_add_property(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test adding a property with domain and range."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    await backend.add_class(None, ontology_id, uri="http://example.org/Building", label="Building")  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/Floor", label="Floor")  # type: ignore[arg-type]

    await backend.add_property(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/hasFloor",
        label="hasFloor",
        domain_uri="http://example.org/Building",
        range_uri="http://example.org/Floor",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    # 2 classes + 1 property node
    assert len(graph.nodes) == 3
    # DOMAIN + RANGE edges
    domain_edges = [e for e in graph.edges if e.edge_type == "DOMAIN"]
    range_edges = [e for e in graph.edges if e.edge_type == "RANGE"]
    assert len(domain_edges) == 1
    assert len(range_edges) == 1


@pytest.mark.asyncio
async def test_add_property_xsd_range(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test adding a property with an XSD datatype range."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/Building", label="Building")  # type: ignore[arg-type]

    await backend.add_property(
        None,  # type: ignore[arg-type]
        ontology_id,
        uri="http://example.org/name",
        label="name",
        domain_uri="http://example.org/Building",
        range_uri="xsd:string",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    # 1 class + 1 property node
    assert len(graph.nodes) == 2
    # Only DOMAIN edge (no RANGE since it's XSD)
    domain_edges = [e for e in graph.edges if e.edge_type == "DOMAIN"]
    assert len(domain_edges) == 1
    range_edges = [e for e in graph.edges if e.edge_type == "RANGE"]
    assert len(range_edges) == 0


@pytest.mark.asyncio
async def test_add_and_delete_relationship(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test adding and deleting a relationship."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    await backend.add_class(None, ontology_id, uri="http://example.org/A", label="A")  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/B", label="B")  # type: ignore[arg-type]

    await backend.add_relationship(
        None,  # type: ignore[arg-type]
        ontology_id,
        source_uri="http://example.org/A",
        target_uri="http://example.org/B",
        rel_type="SUBCLASS_OF",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.edges) == 1
    assert graph.edges[0].edge_type == "SUBCLASS_OF"

    await backend.delete_relationship(
        None,  # type: ignore[arg-type]
        ontology_id,
        source_uri="http://example.org/A",
        target_uri="http://example.org/B",
        rel_type="SUBCLASS_OF",
    )

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.edges) == 0


@pytest.mark.asyncio
async def test_build_from_llm_output(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test bulk build from LLM assembly output."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]

    assembled = {
        "classes": [
            {"uri": "Building", "label": "Building", "description": "A building"},
            {"uri": "Floor", "label": "Floor", "description": "A floor", "parent": "Building"},
            {"uri": "Room", "label": "Room", "description": "A room"},
        ],
        "properties": [
            {"uri": "hasFloor", "label": "hasFloor", "domain": "Building", "range": "Floor"},
            {"uri": "name", "label": "name", "domain": "Building", "range": "xsd:string"},
        ],
        "relationships": [
            {"source_uri": "Room", "target_uri": "Floor", "type": "RELATES_TO"},
        ],
    }

    await backend.build_from_llm_output(None, ontology_id, assembled)  # type: ignore[arg-type]

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]

    # 3 classes + 2 property nodes = 5 nodes
    assert len(graph.nodes) == 5

    class_uris = await backend.get_class_uris(None, ontology_id)  # type: ignore[arg-type]
    assert set(class_uris) == {"Building", "Floor", "Room"}

    # Edges: SUBCLASS_OF (Floor->Building) + DOMAIN (hasFloor->Building) + RANGE (hasFloor->Floor)
    #       + DOMAIN (name->Building) + RELATES_TO (Room->Floor)
    assert len(graph.edges) >= 4


@pytest.mark.asyncio
async def test_invalid_relationship_type(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test that invalid relationship types raise ValueError."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/A", label="A")  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/B", label="B")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Invalid relationship type"):
        await backend.add_relationship(
            None,  # type: ignore[arg-type]
            ontology_id,
            source_uri="http://example.org/A",
            target_uri="http://example.org/B",
            rel_type="INVALID_TYPE",
        )


@pytest.mark.asyncio
async def test_drop_graph(backend: Neo4jBackend, ontology_id: uuid.UUID):
    """Test dropping a graph removes all nodes."""
    await backend.create_graph(None, ontology_id)  # type: ignore[arg-type]
    await backend.add_class(None, ontology_id, uri="http://example.org/X", label="X")  # type: ignore[arg-type]

    await backend.drop_graph(None, ontology_id)  # type: ignore[arg-type]

    graph = await backend.get_graph(None, ontology_id)  # type: ignore[arg-type]
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0
