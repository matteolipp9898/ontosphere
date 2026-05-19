"""Neo4j graph backend implementation.

Implements :class:`~app.services.graph_backend.GraphBackend` using the
official Neo4j async Python driver with native Cypher queries.

Graph isolation: uses label-based prefixing (``Onto_<id>:Class``) to
support Neo4j Community Edition (single database). Enterprise users can
override with ``NEO4J_DATABASE`` per ontology if needed.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.graph_backend import (
    GraphBackend,
    GraphData,
    GraphEdge,
    GraphNode,
    validate_rel_type,
)

logger = logging.getLogger(__name__)


class Neo4jBackend(GraphBackend):
    """Neo4j graph backend — stores ontologies using label-based isolation."""

    def __init__(self, driver: Any) -> None:
        """Initialize with a neo4j AsyncDriver instance."""
        self._driver = driver

    def _prefix(self, ontology_id: UUID) -> str:
        """Return the ontology-specific label prefix."""
        return f"Onto_{str(ontology_id).replace('-', '_')}"

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    async def create_graph(
        self,
        session: AsyncSession,  # noqa: ARG002 — not used by Neo4j
        ontology_id: UUID,
    ) -> None:
        prefix = self._prefix(ontology_id)
        # Create indexes for faster lookups
        async with self._driver.session() as neo_session:
            await neo_session.run(
                f"CREATE INDEX IF NOT EXISTS FOR (n:`{prefix}`) ON (n.uri)"
            )
        logger.info("Created Neo4j graph namespace '%s'", prefix)

    async def drop_graph(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
    ) -> None:
        prefix = self._prefix(ontology_id)
        async with self._driver.session() as neo_session:
            # Delete all nodes with this prefix label
            await neo_session.run(
                f"MATCH (n:`{prefix}`) DETACH DELETE n"
            )
        logger.info("Dropped Neo4j graph namespace '%s'", prefix)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_graph(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
    ) -> GraphData:
        prefix = self._prefix(ontology_id)
        graph = GraphData()

        async with self._driver.session() as neo_session:
            # Fetch all nodes
            result = await neo_session.run(
                f"MATCH (n:`{prefix}`) RETURN n.uri AS uri, n.label AS label, "
                f"n.description AS description, n.node_type AS node_type"
            )
            records = await result.data()
            for record in records:
                graph.nodes.append(
                    GraphNode(
                        uri=record.get("uri", ""),
                        label=record.get("label", ""),
                        description=record.get("description", "") or "",
                        node_type=record.get("node_type", "class") or "class",
                    )
                )

            # Fetch all edges
            result = await neo_session.run(
                f"MATCH (a:`{prefix}`)-[r]->(b:`{prefix}`) "
                f"RETURN a.uri AS source_uri, b.uri AS target_uri, "
                f"type(r) AS edge_type, r.label AS label"
            )
            records = await result.data()
            for record in records:
                graph.edges.append(
                    GraphEdge(
                        source_uri=record.get("source_uri", ""),
                        target_uri=record.get("target_uri", ""),
                        edge_type=record.get("edge_type", ""),
                        label=record.get("label", "") or "",
                    )
                )

        logger.info(
            "Loaded Neo4j graph '%s': %d nodes, %d edges",
            prefix,
            len(graph.nodes),
            len(graph.edges),
        )
        return graph

    async def get_class_uris(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
    ) -> list[str]:
        prefix = self._prefix(ontology_id)
        async with self._driver.session() as neo_session:
            result = await neo_session.run(
                f"MATCH (n:`{prefix}`:Class) RETURN n.uri AS uri"
            )
            records = await result.data()
        return [r["uri"] for r in records if r.get("uri")]

    # ------------------------------------------------------------------
    # Write operations -- Classes
    # ------------------------------------------------------------------

    async def add_class(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        uri: str,
        label: str,
        description: str = "",
        parent_uri: str | None = None,
    ) -> None:
        prefix = self._prefix(ontology_id)
        async with self._driver.session() as neo_session:
            await neo_session.run(
                f"CREATE (n:`{prefix}`:Class {{uri: $uri, label: $label, "
                f"description: $description, node_type: 'class'}})",
                uri=uri,
                label=label,
                description=description,
            )

            if parent_uri:
                await neo_session.run(
                    f"MATCH (child:`{prefix}`:Class {{uri: $child_uri}}), "
                    f"(parent:`{prefix}`:Class {{uri: $parent_uri}}) "
                    f"CREATE (child)-[:SUBCLASS_OF {{label: 'subClassOf'}}]->(parent)",
                    child_uri=uri,
                    parent_uri=parent_uri,
                )

        logger.debug("Added class '%s' to Neo4j graph '%s'", uri, prefix)

    async def update_class(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        uri: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        prefix = self._prefix(ontology_id)
        set_clauses: list[str] = []
        params: dict[str, Any] = {"uri": uri}

        if label is not None:
            set_clauses.append("n.label = $label")
            params["label"] = label
        if description is not None:
            set_clauses.append("n.description = $description")
            params["description"] = description

        if not set_clauses:
            return

        cypher = (
            f"MATCH (n:`{prefix}`:Class {{uri: $uri}}) SET {', '.join(set_clauses)}"
        )
        async with self._driver.session() as neo_session:
            await neo_session.run(cypher, **params)
        logger.debug("Updated class '%s' in Neo4j graph '%s'", uri, prefix)

    async def delete_class(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        uri: str,
    ) -> None:
        prefix = self._prefix(ontology_id)
        async with self._driver.session() as neo_session:
            await neo_session.run(
                f"MATCH (n:`{prefix}`:Class {{uri: $uri}}) DETACH DELETE n",
                uri=uri,
            )
        logger.debug("Deleted class '%s' from Neo4j graph '%s'", uri, prefix)

    # ------------------------------------------------------------------
    # Write operations -- Properties
    # ------------------------------------------------------------------

    async def add_property(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        uri: str,
        label: str,
        domain_uri: str,
        range_uri: str,
        description: str = "",
    ) -> None:
        prefix = self._prefix(ontology_id)
        async with self._driver.session() as neo_session:
            # Create property node
            await neo_session.run(
                f"CREATE (p:`{prefix}`:Property {{uri: $uri, label: $label, "
                f"description: $description, node_type: 'property'}})",
                uri=uri,
                label=label,
                description=description,
            )

            # DOMAIN edge
            await neo_session.run(
                f"MATCH (p:`{prefix}`:Property {{uri: $prop_uri}}), "
                f"(c:`{prefix}`:Class {{uri: $domain_uri}}) "
                f"CREATE (p)-[:DOMAIN {{label: 'domain'}}]->(c)",
                prop_uri=uri,
                domain_uri=domain_uri,
            )

            # RANGE edge
            if not range_uri.startswith("xsd:"):
                await neo_session.run(
                    f"MATCH (p:`{prefix}`:Property {{uri: $prop_uri}}), "
                    f"(c:`{prefix}`:Class {{uri: $range_uri}}) "
                    f"CREATE (p)-[:RANGE {{label: 'range'}}]->(c)",
                    prop_uri=uri,
                    range_uri=range_uri,
                )
            else:
                await neo_session.run(
                    f"MATCH (p:`{prefix}`:Property {{uri: $prop_uri}}) "
                    f"SET p.range_datatype = $range_uri",
                    prop_uri=uri,
                    range_uri=range_uri,
                )

        logger.debug("Added property '%s' to Neo4j graph '%s'", uri, prefix)

    # ------------------------------------------------------------------
    # Write operations -- Relationships
    # ------------------------------------------------------------------

    async def add_relationship(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        prefix = self._prefix(ontology_id)
        safe_type = validate_rel_type(rel_type)

        async with self._driver.session() as neo_session:
            # Neo4j doesn't support parameterized relationship types,
            # so we interpolate the validated (safe) type directly.
            await neo_session.run(
                f"MATCH (a:`{prefix}` {{uri: $source_uri}}), "
                f"(b:`{prefix}` {{uri: $target_uri}}) "
                f"CREATE (a)-[:{safe_type} {{label: $label}}]->(b)",
                source_uri=source_uri,
                target_uri=target_uri,
                label=safe_type.lower(),
            )
        logger.debug(
            "Added relationship %s -> %s [%s] in Neo4j graph '%s'",
            source_uri,
            target_uri,
            safe_type,
            prefix,
        )

    async def delete_relationship(
        self,
        session: AsyncSession,  # noqa: ARG002
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        prefix = self._prefix(ontology_id)
        safe_type = validate_rel_type(rel_type)

        async with self._driver.session() as neo_session:
            await neo_session.run(
                f"MATCH (a:`{prefix}` {{uri: $source_uri}})"
                f"-[r:{safe_type}]->"
                f"(b:`{prefix}` {{uri: $target_uri}}) DELETE r",
                source_uri=source_uri,
                target_uri=target_uri,
            )
        logger.debug(
            "Deleted relationship %s -> %s [%s] from Neo4j graph '%s'",
            source_uri,
            target_uri,
            safe_type,
            prefix,
        )

    # ------------------------------------------------------------------
    # Bulk build from LLM output
    # ------------------------------------------------------------------

    async def build_from_llm_output(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        assembled: dict,
    ) -> None:
        prefix = self._prefix(ontology_id)
        classes: list[dict] = assembled.get("classes", [])
        properties: list[dict] = assembled.get("properties", [])
        relationships: list[dict] = assembled.get("relationships", [])

        class_uris: set[str] = set()
        errors: int = 0

        # 1. Create all class nodes
        for cls_data in classes:
            uri = cls_data.get("uri", "")
            if not uri:
                continue
            try:
                await self.add_class(
                    session,
                    ontology_id,
                    uri=uri,
                    label=cls_data.get("label", uri),
                    description=cls_data.get("description", ""),
                    parent_uri=cls_data.get("parent"),
                )
                class_uris.add(uri)
            except Exception as exc:
                errors += 1
                logger.error(
                    "Failed to add class %r to Neo4j graph %r: %s",
                    uri,
                    prefix,
                    exc,
                )

        # 2. Create property nodes with DOMAIN/RANGE edges
        for prop_data in properties:
            uri = prop_data.get("uri", "")
            domain_uri = prop_data.get("domain", "")
            range_uri = prop_data.get("range", "")
            if not uri or not domain_uri:
                continue
            if domain_uri in class_uris:
                try:
                    await self.add_property(
                        session,
                        ontology_id,
                        uri=uri,
                        label=prop_data.get("label", uri),
                        domain_uri=domain_uri,
                        range_uri=range_uri,
                        description=prop_data.get("description", ""),
                    )
                except Exception as exc:
                    errors += 1
                    logger.error(
                        "Failed to add property %r (domain=%r) to Neo4j graph %r: %s",
                        uri,
                        domain_uri,
                        prefix,
                        exc,
                    )

        # 3. Create explicit relationships
        for rel_data in relationships:
            source_uri = rel_data.get("source_uri", "")
            target_uri = rel_data.get("target_uri", "")
            rel_type = rel_data.get("type", "")
            if not source_uri or not target_uri or not rel_type:
                continue
            try:
                await self.add_relationship(
                    session,
                    ontology_id,
                    source_uri=source_uri,
                    target_uri=target_uri,
                    rel_type=rel_type,
                )
            except Exception as exc:
                errors += 1
                logger.warning(
                    "Skipping relationship %s -> %s [%s] in Neo4j graph %r: %s",
                    source_uri,
                    target_uri,
                    rel_type,
                    prefix,
                    exc,
                )

        logger.info(
            "Built Neo4j graph from LLM output: %d classes, %d properties, "
            "%d relationships (%d errors)",
            len(classes),
            len(properties),
            len(relationships),
            errors,
        )
