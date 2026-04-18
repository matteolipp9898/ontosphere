"""Graph service for managing Apache AGE ontology graphs.

All methods interact with a per-ontology Apache AGE graph via Cypher queries
executed through the ``execute_age_query`` database helper.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import create_age_graph, execute_age_query

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
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
# GraphService
# ---------------------------------------------------------------------------

class GraphService:
    """Operations on a per-ontology Apache AGE property graph."""

    @staticmethod
    def graph_name(ontology_id: UUID) -> str:
        """Derive the AGE graph name from the ontology UUID."""
        return f"ontology_{str(ontology_id).replace('-', '_')}"

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def create_graph(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        """Create a new AGE graph for the given ontology."""
        name = cls.graph_name(ontology_id)
        await create_age_graph(session, name)
        logger.info("Created AGE graph '%s'", name)

    @classmethod
    async def drop_graph(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        """Drop the AGE graph for an ontology (if it exists)."""
        name = cls.graph_name(ontology_id)
        try:
            await execute_age_query(
                session,
                name,
                "MATCH (n) DETACH DELETE n",
            )
        except Exception:
            # Graph may not exist; that is fine
            logger.debug("Graph '%s' may not exist; ignoring drop error", name)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @classmethod
    async def get_graph(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> GraphData:
        """Retrieve all nodes and edges from the ontology graph."""
        name = cls.graph_name(ontology_id)
        graph = GraphData()

        # Fetch all nodes
        node_rows = await execute_age_query(
            session,
            name,
            "MATCH (n) RETURN n.uri AS uri, n.label AS label, "
            "n.description AS description, n.node_type AS node_type, "
            "labels(n) AS labels",
        )
        for row in node_rows:
            node_type = row.get("node_type", "class")
            # Derive from AGE label if node_type property is absent
            labels = row.get("labels", [])
            if not node_type and labels:
                node_type = str(labels[0]).lower()
            graph.nodes.append(
                GraphNode(
                    uri=row.get("uri", ""),
                    label=row.get("label", ""),
                    description=row.get("description", ""),
                    node_type=node_type or "class",
                )
            )

        # Fetch all edges
        edge_rows = await execute_age_query(
            session,
            name,
            "MATCH (a)-[r]->(b) RETURN a.uri AS source_uri, b.uri AS target_uri, "
            "type(r) AS edge_type, r.label AS label",
        )
        for row in edge_rows:
            graph.edges.append(
                GraphEdge(
                    source_uri=row.get("source_uri", ""),
                    target_uri=row.get("target_uri", ""),
                    edge_type=row.get("edge_type", ""),
                    label=row.get("label", ""),
                )
            )

        logger.info(
            "Loaded graph '%s': %d nodes, %d edges",
            name,
            len(graph.nodes),
            len(graph.edges),
        )
        return graph

    @classmethod
    async def get_class_uris(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> list[str]:
        """Return all :Class node URIs in the graph."""
        name = cls.graph_name(ontology_id)
        rows = await execute_age_query(
            session,
            name,
            "MATCH (n:Class) RETURN n.uri AS uri",
        )
        return [row["uri"] for row in rows if row.get("uri")]

    # ------------------------------------------------------------------
    # Write operations -- Classes
    # ------------------------------------------------------------------

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
        """Create a :Class node, optionally linking it via SUBCLASS_OF."""
        name = cls.graph_name(ontology_id)

        await execute_age_query(
            session,
            name,
            "CREATE (n:Class {uri: $uri, label: $label, description: $description, "
            "node_type: 'class'})",
            params={"uri": uri, "label": label, "description": description},
        )

        if parent_uri:
            await execute_age_query(
                session,
                name,
                "MATCH (child:Class {uri: $child_uri}), (parent:Class {uri: $parent_uri}) "
                "CREATE (child)-[:SUBCLASS_OF {label: 'subClassOf'}]->(parent)",
                params={"child_uri": uri, "parent_uri": parent_uri},
            )

        logger.debug("Added class '%s' to graph '%s'", uri, name)

    @classmethod
    async def update_class(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        """Update properties on an existing :Class node."""
        name = cls.graph_name(ontology_id)
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
            f"MATCH (n:Class {{uri: $uri}}) SET {', '.join(set_clauses)}"
        )
        await execute_age_query(session, name, cypher, params=params)
        logger.debug("Updated class '%s' in graph '%s'", uri, name)

    @classmethod
    async def delete_class(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
    ) -> None:
        """Delete a :Class node and all edges connected to it."""
        name = cls.graph_name(ontology_id)
        await execute_age_query(
            session,
            name,
            "MATCH (n:Class {uri: $uri}) DETACH DELETE n",
            params={"uri": uri},
        )
        logger.debug("Deleted class '%s' from graph '%s'", uri, name)

    # ------------------------------------------------------------------
    # Write operations -- Properties
    # ------------------------------------------------------------------

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
        """Create a :Property node with DOMAIN and RANGE edges."""
        name = cls.graph_name(ontology_id)

        # Create the property node
        await execute_age_query(
            session,
            name,
            "CREATE (p:Property {uri: $uri, label: $label, description: $description, "
            "node_type: 'property'})",
            params={"uri": uri, "label": label, "description": description},
        )

        # DOMAIN edge: Property -> domain class
        await execute_age_query(
            session,
            name,
            "MATCH (p:Property {uri: $prop_uri}), (c:Class {uri: $domain_uri}) "
            "CREATE (p)-[:DOMAIN {label: 'domain'}]->(c)",
            params={"prop_uri": uri, "domain_uri": domain_uri},
        )

        # RANGE edge: Property -> range class (only if range is not an XSD datatype)
        if not range_uri.startswith("xsd:"):
            await execute_age_query(
                session,
                name,
                "MATCH (p:Property {uri: $prop_uri}), (c:Class {uri: $range_uri}) "
                "CREATE (p)-[:RANGE {label: 'range'}]->(c)",
                params={"prop_uri": uri, "range_uri": range_uri},
            )
        else:
            # Store datatype range as a node property
            await execute_age_query(
                session,
                name,
                "MATCH (p:Property {uri: $prop_uri}) "
                "SET p.range_datatype = $range_uri",
                params={"prop_uri": uri, "range_uri": range_uri},
            )

        logger.debug("Added property '%s' to graph '%s'", uri, name)

    # ------------------------------------------------------------------
    # Write operations -- Relationships
    # ------------------------------------------------------------------

    @classmethod
    async def add_relationship(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        """Create a typed edge between two nodes.

        The *rel_type* must be one of the known AGE edge labels:
        SUBCLASS_OF, HAS_PROPERTY, DOMAIN, RANGE, EQUIVALENT_TO, RELATES_TO.
        """
        name = cls.graph_name(ontology_id)

        valid_types = {
            "SUBCLASS_OF",
            "HAS_PROPERTY",
            "DOMAIN",
            "RANGE",
            "EQUIVALENT_TO",
            "RELATES_TO",
        }
        if rel_type not in valid_types:
            raise ValueError(
                f"Invalid relationship type '{rel_type}'. Must be one of {valid_types}"
            )

        # AGE doesn't support parameterised relationship types, so we
        # validate above and interpolate safely.
        cypher = (
            f"MATCH (a {{uri: $source_uri}}), (b {{uri: $target_uri}}) "
            f"CREATE (a)-[:{rel_type} {{label: $label}}]->(b)"
        )
        await execute_age_query(
            session,
            name,
            cypher,
            params={
                "source_uri": source_uri,
                "target_uri": target_uri,
                "label": rel_type.lower(),
            },
        )
        logger.debug(
            "Added relationship %s -> %s [%s] in graph '%s'",
            source_uri,
            target_uri,
            rel_type,
            name,
        )

    @classmethod
    async def delete_relationship(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        """Delete a specific edge between two nodes."""
        name = cls.graph_name(ontology_id)

        valid_types = {
            "SUBCLASS_OF",
            "HAS_PROPERTY",
            "DOMAIN",
            "RANGE",
            "EQUIVALENT_TO",
            "RELATES_TO",
        }
        if rel_type not in valid_types:
            raise ValueError(
                f"Invalid relationship type '{rel_type}'. Must be one of {valid_types}"
            )

        cypher = (
            f"MATCH (a {{uri: $source_uri}})-[r:{rel_type}]->(b {{uri: $target_uri}}) "
            "DELETE r"
        )
        await execute_age_query(
            session,
            name,
            cypher,
            params={"source_uri": source_uri, "target_uri": target_uri},
        )
        logger.debug(
            "Deleted relationship %s -> %s [%s] from graph '%s'",
            source_uri,
            target_uri,
            rel_type,
            name,
        )

    # ------------------------------------------------------------------
    # Bulk build from LLM output
    # ------------------------------------------------------------------

    @classmethod
    async def build_from_llm_output(
        cls,
        session: AsyncSession,
        ontology_id: UUID,
        assembled: dict,
    ) -> None:
        """Populate the graph from the LLM assembly output.

        *assembled* is expected to have keys ``classes``, ``properties``,
        and ``relationships`` as produced by ``LLMClient.assemble_ontology``.
        """
        classes: list[dict] = assembled.get("classes", [])
        properties: list[dict] = assembled.get("properties", [])
        relationships: list[dict] = assembled.get("relationships", [])

        # 1. Create all class nodes
        class_uris: set[str] = set()
        for cls_data in classes:
            uri = cls_data.get("uri", "")
            if not uri:
                continue
            class_uris.add(uri)
            await cls.add_class(
                session,
                ontology_id,
                uri=uri,
                label=cls_data.get("label", uri),
                description=cls_data.get("description", ""),
                parent_uri=cls_data.get("parent"),
            )

        # 2. Create property nodes with DOMAIN/RANGE edges
        for prop_data in properties:
            uri = prop_data.get("uri", "")
            domain_uri = prop_data.get("domain", "")
            range_uri = prop_data.get("range", "")
            if not uri or not domain_uri:
                continue
            # Only create if domain exists in the graph
            if domain_uri in class_uris:
                await cls.add_property(
                    session,
                    ontology_id,
                    uri=uri,
                    label=prop_data.get("label", uri),
                    domain_uri=domain_uri,
                    range_uri=range_uri,
                    description=prop_data.get("description", ""),
                )

        # 3. Create explicit relationships
        for rel_data in relationships:
            source_uri = rel_data.get("source_uri", "")
            target_uri = rel_data.get("target_uri", "")
            rel_type = rel_data.get("type", "")
            if not source_uri or not target_uri or not rel_type:
                continue
            try:
                await cls.add_relationship(
                    session,
                    ontology_id,
                    source_uri=source_uri,
                    target_uri=target_uri,
                    rel_type=rel_type,
                )
            except ValueError as exc:
                logger.warning("Skipping invalid relationship: %s", exc)

        logger.info(
            "Built graph from LLM output: %d classes, %d properties, %d relationships",
            len(classes),
            len(properties),
            len(relationships),
        )
