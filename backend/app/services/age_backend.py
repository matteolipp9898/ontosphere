"""Apache AGE graph backend implementation.

Implements :class:`~app.services.graph_backend.GraphBackend` using the
Apache AGE PostgreSQL extension with Cypher queries.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import create_age_graph, execute_age_query
from app.services.graph_backend import (
    GraphBackend,
    GraphData,
    GraphEdge,
    GraphNode,
    validate_rel_type,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AGE agtype parsing helpers
# ---------------------------------------------------------------------------

def _parse_agtype(value: Any) -> Any:
    """Parse an AGE agtype value into a Python object.

    AGE returns vertices as ``{...}::vertex``, edges as ``{...}::edge``,
    and scalars as bare JSON values.
    """
    if value is None:
        return None
    s = str(value)
    # Strip the ::vertex / ::edge type suffix
    s = re.sub(r"::(vertex|edge)$", "", s)
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s


def _vertex_props(value: Any) -> dict[str, Any]:
    """Extract the properties dict from an AGE vertex agtype."""
    parsed = _parse_agtype(value)
    if isinstance(parsed, dict):
        props = dict(parsed.get("properties", {}))
        props["_label"] = parsed.get("label", "")
        return props
    return {}


def _edge_info(value: Any) -> dict[str, Any]:
    """Extract label and properties from an AGE edge agtype."""
    parsed = _parse_agtype(value)
    if isinstance(parsed, dict):
        props = dict(parsed.get("properties", {}))
        props["_type"] = parsed.get("label", "")
        return props
    return {}


# ---------------------------------------------------------------------------
# AGE Backend
# ---------------------------------------------------------------------------

class AGEBackend(GraphBackend):
    """Apache AGE graph backend — stores ontologies as per-ontology AGE graphs."""

    @staticmethod
    def graph_name(ontology_id: UUID) -> str:
        """Derive the AGE graph name from the ontology UUID."""
        return f"ontology_{str(ontology_id).replace('-', '_')}"

    # ------------------------------------------------------------------
    # Graph lifecycle
    # ------------------------------------------------------------------

    async def create_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        name = self.graph_name(ontology_id)
        await create_age_graph(session, name)
        logger.info("Created AGE graph '%s'", name)

    async def drop_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> None:
        name = self.graph_name(ontology_id)
        try:
            await execute_age_query(
                session,
                name,
                "MATCH (n) DETACH DELETE n",
            )
        except Exception:
            logger.debug("Graph '%s' may not exist; ignoring drop error", name)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_graph(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> GraphData:
        name = self.graph_name(ontology_id)
        graph = GraphData()

        node_rows = await execute_age_query(
            session,
            name,
            "MATCH (n) RETURN n",
            columns="n agtype",
        )
        for row in node_rows:
            props = _vertex_props(row[0])
            node_type = props.get("node_type", "")
            if not node_type:
                node_type = props.get("_label", "class").lower()
            graph.nodes.append(
                GraphNode(
                    uri=props.get("uri", ""),
                    label=props.get("label", ""),
                    description=props.get("description", ""),
                    node_type=node_type or "class",
                )
            )

        edge_rows = await execute_age_query(
            session,
            name,
            "MATCH (a)-[r]->(b) RETURN a, r, b",
            columns="a agtype, r agtype, b agtype",
        )
        for row in edge_rows:
            a_props = _vertex_props(row[0])
            r_info = _edge_info(row[1])
            b_props = _vertex_props(row[2])
            graph.edges.append(
                GraphEdge(
                    source_uri=a_props.get("uri", ""),
                    target_uri=b_props.get("uri", ""),
                    edge_type=r_info.get("_type", ""),
                    label=r_info.get("label", ""),
                )
            )

        logger.info(
            "Loaded graph '%s': %d nodes, %d edges",
            name,
            len(graph.nodes),
            len(graph.edges),
        )
        return graph

    async def get_class_uris(
        self,
        session: AsyncSession,
        ontology_id: UUID,
    ) -> list[str]:
        name = self.graph_name(ontology_id)
        rows = await execute_age_query(
            session,
            name,
            "MATCH (n:Class) RETURN n",
            columns="n agtype",
        )
        uris = []
        for row in rows:
            uri = _vertex_props(row[0]).get("uri", "")
            if uri:
                uris.append(uri)
        return uris

    # ------------------------------------------------------------------
    # Write operations -- Classes
    # ------------------------------------------------------------------

    async def add_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str,
        description: str = "",
        parent_uri: str | None = None,
    ) -> None:
        name = self.graph_name(ontology_id)

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
                "CREATE (child)-[r:SUBCLASS_OF {label: 'subClassOf'}]->(parent)",
                params={"child_uri": uri, "parent_uri": parent_uri},
            )

        logger.debug("Added class '%s' to graph '%s'", uri, name)

    async def update_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
        label: str | None = None,
        description: str | None = None,
    ) -> None:
        name = self.graph_name(ontology_id)
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

    async def delete_class(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        uri: str,
    ) -> None:
        name = self.graph_name(ontology_id)
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
        name = self.graph_name(ontology_id)

        await execute_age_query(
            session,
            name,
            "CREATE (p:Property {uri: $uri, label: $label, description: $description, "
            "node_type: 'property'})",
            params={"uri": uri, "label": label, "description": description},
        )

        await execute_age_query(
            session,
            name,
            "MATCH (p:Property {uri: $prop_uri}), (c:Class {uri: $domain_uri}) "
            "CREATE (p)-[r:DOMAIN {label: 'domain'}]->(c)",
            params={"prop_uri": uri, "domain_uri": domain_uri},
        )

        if not range_uri.startswith("xsd:"):
            await execute_age_query(
                session,
                name,
                "MATCH (p:Property {uri: $prop_uri}), (c:Class {uri: $range_uri}) "
                "CREATE (p)-[r:RANGE {label: 'range'}]->(c)",
                params={"prop_uri": uri, "range_uri": range_uri},
            )
        else:
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

    async def add_relationship(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        name = self.graph_name(ontology_id)
        safe_type = validate_rel_type(rel_type)

        cypher = (
            f"MATCH (a {{uri: $source_uri}}), (b {{uri: $target_uri}}) "
            f"CREATE (a)-[r:{safe_type} {{label: $label}}]->(b)"
        )
        await execute_age_query(
            session,
            name,
            cypher,
            params={
                "source_uri": source_uri,
                "target_uri": target_uri,
                "label": safe_type.lower(),
            },
        )
        logger.debug(
            "Added relationship %s -> %s [%s] in graph '%s'",
            source_uri,
            target_uri,
            safe_type,
            name,
        )

    async def delete_relationship(
        self,
        session: AsyncSession,
        ontology_id: UUID,
        source_uri: str,
        target_uri: str,
        rel_type: str,
    ) -> None:
        name = self.graph_name(ontology_id)
        safe_type = validate_rel_type(rel_type)

        cypher = (
            f"MATCH (a {{uri: $source_uri}})-[r:{safe_type}]->(b {{uri: $target_uri}}) "
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
            safe_type,
            name,
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
        name = self.graph_name(ontology_id)
        classes: list[dict] = assembled.get("classes", [])
        properties: list[dict] = assembled.get("properties", [])
        relationships: list[dict] = assembled.get("relationships", [])

        # 1. Create all class nodes
        class_uris: set[str] = set()
        errors: int = 0
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
                    "Failed to add class %r to graph %r: %s",
                    uri,
                    name,
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
                        "Failed to add property %r (domain=%r) to graph %r: %s",
                        uri,
                        domain_uri,
                        name,
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
                    "Skipping relationship %s -> %s [%s] in graph %r: %s",
                    source_uri,
                    target_uri,
                    rel_type,
                    name,
                    exc,
                )

        logger.info(
            "Built graph from LLM output: %d classes, %d properties, %d relationships (%d errors)",
            len(classes),
            len(properties),
            len(relationships),
            errors,
        )
