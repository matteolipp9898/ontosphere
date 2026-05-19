"""Abstract graph backend interface and shared data transfer objects.

All graph backends (Apache AGE, Neo4j, etc.) implement the
:class:`GraphBackend` abstract base class.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Data transfer objects (shared across all backends)
# ---------------------------------------------------------------------------

@dataclass
class GraphNode:
    uri: str
    label: str
    description: str = ""
    node_type: str = "class"  # class | property | individual
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_uri: str
    target_uri: str
    edge_type: str
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphData:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers (shared)
# ---------------------------------------------------------------------------

VALID_RELATIONSHIP_TYPES = {
    "SUBCLASS_OF",
    "HAS_PROPERTY",
    "DOMAIN",
    "RANGE",
    "EQUIVALENT_TO",
    "RELATES_TO",
}


def sanitize_rel_type(rel_type: str) -> str:
    """Sanitize a relationship type for use as a Cypher edge label.

    Uppercases, replaces non-alphanumeric characters with underscores,
    and ensures the result starts with a letter.
    """
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", rel_type).upper()
    if not sanitized or not sanitized[0].isalpha():
        sanitized = "REL_" + sanitized
    return sanitized


def validate_rel_type(rel_type: str) -> str:
    """Sanitize and validate a relationship type. Raises ValueError if invalid."""
    safe_type = sanitize_rel_type(rel_type)
    if safe_type not in VALID_RELATIONSHIP_TYPES:
        raise ValueError(
            f"Invalid relationship type '{rel_type}' (sanitized: '{safe_type}'). "
            f"Must be one of {VALID_RELATIONSHIP_TYPES}"
        )
    return safe_type


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class GraphBackend(ABC):
    """Abstract interface for ontology graph storage backends."""

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        """Create a new graph for the given ontology."""

    @abstractmethod
    async def drop_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        """Drop/clear the graph for an ontology."""

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> GraphData:
        """Retrieve all nodes and edges from the ontology graph."""

    @abstractmethod
    async def get_class_uris(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> list[str]:
        """Return all Class node URIs in the graph."""

    # ------------------------------------------------------------------
    # Write operations -- Classes
    # ------------------------------------------------------------------

    @abstractmethod
    async def add_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str,
        description: str = "",
        parent_uri: str | None = None,
    ) -> None:
        """Create a Class node, optionally linking it via SUBCLASS_OF."""

    @abstractmethod
    async def update_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        """Update properties on an existing Class node."""

    @abstractmethod
    async def delete_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
    ) -> None:
        """Delete a Class node and all edges connected to it."""

    # ------------------------------------------------------------------
    # Write operations -- Properties
    # ------------------------------------------------------------------

    @abstractmethod
    async def add_property(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str,
        domain_uri: str,
        range_uri: str,
        description: str = "",
    ) -> None:
        """Create a Property node with DOMAIN and RANGE edges."""

    # ------------------------------------------------------------------
    # Write operations -- Relationships
    # ------------------------------------------------------------------

    @abstractmethod
    async def add_relationship(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        """Create a typed edge between two nodes."""

    @abstractmethod
    async def delete_relationship(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        """Delete a specific edge between two nodes."""

    # ------------------------------------------------------------------
    # Bulk build from LLM output
    # ------------------------------------------------------------------

    @abstractmethod
    async def build_from_llm_output(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        assembled: dict,
    ) -> None:
        """Populate the graph from LLM assembly output.

        *assembled* is expected to have keys ``classes``, ``properties``,
        and ``relationships`` as produced by ``LLMClient.assemble_ontology``.
        """
