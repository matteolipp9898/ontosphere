"""Graph service factory — backward-compatible façade.

Provides the ``GraphService`` class with the same static/classmethod
interface that the rest of the codebase already imports.  Internally it
delegates to the configured backend (AGE or Neo4j) selected via
``settings.GRAPH_BACKEND``.

Also re-exports the shared DTOs so existing imports continue to work:
    from app.services.graph_service import GraphService, GraphData, GraphNode, GraphEdge
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.graph_backend import (
    GraphBackend,
    GraphData,
    GraphEdge,
    GraphNode,
    sanitize_rel_type,
    validate_rel_type,
)

logger = logging.getLogger(__name__)

# Re-export DTOs for backward compatibility
__all__ = [
    "GraphService",
    "GraphBackend",
    "GraphData",
    "GraphEdge",
    "GraphNode",
    "sanitize_rel_type",
    "validate_rel_type",
]


# ---------------------------------------------------------------------------
# Singleton backend instance
# ---------------------------------------------------------------------------

_backend: GraphBackend | None = None


async def _get_backend() -> GraphBackend:
    """Lazily instantiate the configured graph backend."""
    global _backend  # noqa: PLW0603
    if _backend is not None:
        return _backend

    settings = get_settings()

    if settings.GRAPH_BACKEND == "neo4j":
        from app.database import get_neo4j_driver
        from app.services.neo4j_backend import Neo4jBackend

        driver = await get_neo4j_driver()
        _backend = Neo4jBackend(driver)
        logger.info("Graph backend: Neo4j (%s)", settings.NEO4J_URI)
    else:
        from app.services.age_backend import AGEBackend

        _backend = AGEBackend()
        logger.info("Graph backend: Apache AGE")

    return _backend


def reset_backend() -> None:
    """Reset the cached backend (useful for testing)."""
    global _backend  # noqa: PLW0603
    _backend = None


# ---------------------------------------------------------------------------
# GraphService — backward-compatible static façade
# ---------------------------------------------------------------------------

class GraphService:
    """Façade that delegates to the active graph backend.

    Maintains the same classmethod interface that existing code expects.
    """

    @staticmethod
    def graph_name(ontology_id: UUID) -> str:
        """Derive a human-readable graph identifier for logging."""
        return f"ontology_{str(ontology_id).replace('-', '_')}"

    @classmethod
    async def create_graph(cls, session: AsyncSession, ontology_id: UUID) -> None:
        backend = await _get_backend()
        await backend.create_graph(session, ontology_id)

    @classmethod
    async def drop_graph(cls, session: AsyncSession, ontology_id: UUID) -> None:
        backend = await _get_backend()
        await backend.drop_graph(session, ontology_id)

    @classmethod
    async def get_graph(cls, session: AsyncSession, ontology_id: UUID) -> GraphData:
        backend = await _get_backend()
        return await backend.get_graph(session, ontology_id)

    @classmethod
    async def get_class_uris(cls, session: AsyncSession, ontology_id: UUID) -> list[str]:
        backend = await _get_backend()
        return await backend.get_class_uris(session, ontology_id)

    @classmethod
    async def add_class(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str,
        description: str = "",
        parent_uri: str | None = None,
    ) -> None:
        backend = await _get_backend()
        await backend.add_class(session, ontology_id, uri, label, description, parent_uri)

    @classmethod
    async def update_class(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        backend = await _get_backend()
        await backend.update_class(session, ontology_id, uri, label, description)

    @classmethod
    async def delete_class(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
    ) -> None:
        backend = await _get_backend()
        await backend.delete_class(session, ontology_id, uri)

    @classmethod
    async def add_property(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str,
        domain_uri: str,
        range_uri: str,
        description: str = "",
    ) -> None:
        backend = await _get_backend()
        await backend.add_property(session, ontology_id, uri, label, domain_uri, range_uri, description)

    @classmethod
    async def add_relationship(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        backend = await _get_backend()
        await backend.add_relationship(session, ontology_id, source_uri, target_uri, rel_type)

    @classmethod
    async def delete_relationship(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        backend = await _get_backend()
        await backend.delete_relationship(session, ontology_id, source_uri, target_uri, rel_type)

    @classmethod
    async def build_from_llm_output(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        assembled: dict,
    ) -> None:
        backend = await _get_backend()
        await backend.build_from_llm_output(session, ontology_id, assembled)
