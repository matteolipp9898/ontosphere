"""Graph manipulation routes (classes, relationships) for an ontology."""

from __future__ import annotations

import logging
import uuid
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology
from app.schemas.common import StatusResponse
from app.schemas.graph import (
    ClassCreate,
    ClassUpdate,
    GraphData,
    GraphEdge,
    GraphNode,
    RelationshipCreate,
)
from app.services.graph_service import GraphService
from app.services.graph_service import (
    GraphData as ServiceGraphData,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontologies/{ontology_id}", tags=["graph"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_ontology_or_404(
    ontology_id: uuid.UUID,
    session: AsyncSession,
) -> Ontology:
    result = await session.execute(
        select(Ontology).where(Ontology.id == ontology_id)
    )
    ontology = result.scalars().first()
    if ontology is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ontology {ontology_id} not found.",
        )
    return ontology


def _to_schema_graph(service_data: ServiceGraphData) -> GraphData:
    """Convert service-layer dataclass GraphData to Pydantic schema GraphData."""
    nodes = [
        GraphNode(
            id=n.uri,
            uri=n.uri,
            label=n.label,
            node_type=n.node_type or "class",
            properties=n.properties or {},
            description=n.description or "",
        )
        for n in service_data.nodes
    ]
    edges = [
        GraphEdge(
            id=f"{e.source_uri}-{e.edge_type}-{e.target_uri}",
            source=e.source_uri,
            target=e.target_uri,
            edge_type=e.edge_type,
            properties=e.properties or {},
        )
        for e in service_data.edges
    ]
    return GraphData(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/graph",
    response_model=GraphData,
    summary="Get full graph data",
)
async def get_graph(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> GraphData:
    await _get_ontology_or_404(ontology_id, session)
    try:
        service_data = await GraphService.get_graph(session, ontology_id)
    except Exception:
        logger.exception("Failed to retrieve graph for ontology %s.", ontology_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve graph data.",
        )
    return _to_schema_graph(service_data)


@router.post(
    "/classes",
    response_model=GraphNode,
    status_code=status.HTTP_201_CREATED,
    summary="Add a class to the ontology graph",
)
async def add_class(
    ontology_id: uuid.UUID,
    body: ClassCreate,
    session: AsyncSession = Depends(get_db),
) -> GraphNode:
    await _get_ontology_or_404(ontology_id, session)
    try:
        await GraphService.add_class(
            session,
            ontology_id,
            uri=body.uri,
            label=body.label,
            description=body.description,
            parent_uri=body.parent_uri,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Failed to add class for ontology %s.", ontology_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add class.",
        )
    return GraphNode(
        id=body.uri,
        uri=body.uri,
        label=body.label,
        node_type="class",
        description=body.description,
    )


@router.patch(
    "/classes/{uri:path}",
    response_model=GraphNode,
    summary="Update a class in the ontology graph",
)
async def update_class(
    ontology_id: uuid.UUID,
    uri: str,
    body: ClassUpdate,
    session: AsyncSession = Depends(get_db),
) -> GraphNode:
    await _get_ontology_or_404(ontology_id, session)
    decoded_uri = unquote(uri)
    try:
        await GraphService.update_class(
            session,
            ontology_id,
            uri=decoded_uri,
            label=body.label,
            description=body.description,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class '{decoded_uri}' not found.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception(
            "Failed to update class %s for ontology %s.", decoded_uri, ontology_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update class.",
        )
    return GraphNode(
        id=decoded_uri,
        uri=decoded_uri,
        label=body.label or "",
        node_type="class",
        description=body.description or "",
    )


@router.delete(
    "/classes/{uri:path}",
    response_model=StatusResponse,
    summary="Delete a class from the ontology graph",
)
async def delete_class(
    ontology_id: uuid.UUID,
    uri: str,
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await _get_ontology_or_404(ontology_id, session)
    decoded_uri = unquote(uri)
    try:
        await GraphService.delete_class(session, ontology_id, decoded_uri)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Class '{decoded_uri}' not found.",
        )
    except Exception:
        logger.exception(
            "Failed to delete class %s for ontology %s.", decoded_uri, ontology_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete class.",
        )
    return StatusResponse(status="ok", message=f"Class '{decoded_uri}' deleted.")


@router.post(
    "/relationships",
    response_model=StatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a relationship between two nodes",
)
async def add_relationship(
    ontology_id: uuid.UUID,
    body: RelationshipCreate,
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await _get_ontology_or_404(ontology_id, session)
    try:
        await GraphService.add_relationship(
            session,
            ontology_id,
            source_uri=body.source_uri,
            target_uri=body.target_uri,
            rel_type=body.relationship_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception(
            "Failed to add relationship for ontology %s.", ontology_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add relationship.",
        )
    return StatusResponse(status="ok", message="Relationship created.")


@router.delete(
    "/relationships/{rel_id}",
    response_model=StatusResponse,
    summary="Delete a relationship",
)
async def delete_relationship(
    ontology_id: uuid.UUID,
    rel_id: str,
    source_uri: str = Query(..., description="Source node URI"),
    target_uri: str = Query(..., description="Target node URI"),
    rel_type: str = Query(..., description="Relationship type"),
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await _get_ontology_or_404(ontology_id, session)
    try:
        await GraphService.delete_relationship(
            session,
            ontology_id,
            source_uri=unquote(source_uri),
            target_uri=unquote(target_uri),
            rel_type=rel_type,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )
    except Exception:
        logger.exception(
            "Failed to delete relationship %s for ontology %s.", rel_id, ontology_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete relationship.",
        )
    return StatusResponse(status="ok", message="Relationship deleted.")
