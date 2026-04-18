"""Shared pytest fixtures for the OntoSphere backend test suite."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.database import get_db
from app.main import app
from app.services.graph_service import GraphData, GraphEdge, GraphNode


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# In-memory async SQLite engine + session
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture()
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean async database session backed by in-memory SQLite.

    Tables are created before each test and dropped afterwards so every
    test starts with an empty database.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# FastAPI test client (uses the in-memory DB)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the FastAPI app with the test DB session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Sample ontology record
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def sample_ontology(db_session: AsyncSession):
    """Insert and return a sample Ontology row."""
    from app.models.ontology import Ontology
    from app.models.user import User

    # Create a user first (Ontology requires user_id FK)
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Test User",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()

    ontology = Ontology(
        id=uuid.uuid4(),
        name="Test Ontology",
        description="An ontology created by the test suite",
        namespace_uri="http://example.org/test#",
        status="draft",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(ontology)
    await db_session.commit()
    await db_session.refresh(ontology)
    return ontology


# ---------------------------------------------------------------------------
# Sample graph data (uses graph_service dataclasses, not Pydantic schemas)
# ---------------------------------------------------------------------------
@pytest.fixture()
def sample_graph_data() -> GraphData:
    """Return a small but valid GraphData object for export tests."""
    nodes = [
        GraphNode(
            uri="http://example.org/Building",
            label="Building",
            node_type="class",
            properties={},
            description="A physical building",
        ),
        GraphNode(
            uri="http://example.org/Floor",
            label="Floor",
            node_type="class",
            properties={},
            description="A floor within a building",
        ),
    ]
    edges = [
        GraphEdge(
            source_uri="http://example.org/Building",
            target_uri="http://example.org/Floor",
            edge_type="HAS_FLOOR",
            label="hasFloor",
            properties={},
        ),
    ]
    return GraphData(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Mock LLM client
# ---------------------------------------------------------------------------
@pytest.fixture()
def mock_llm_client() -> MagicMock:
    """Return a mock LLM client whose generate method returns canned JSON.

    The mock simulates the interface expected by ``app.services.llm_service``.
    """
    client = MagicMock()
    client.generate = AsyncMock(
        return_value={
            "nodes": [
                {
                    "id": "1",
                    "uri": "http://example.org/Thing",
                    "label": "Thing",
                    "node_type": "class",
                    "properties": {},
                    "description": "A generic thing",
                }
            ],
            "edges": [],
        }
    )
    return client
