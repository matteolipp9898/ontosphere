"""Ontology export route supporting multiple RDF serialisation formats."""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology
from app.services.export_service import export_ontology

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontologies/{ontology_id}", tags=["export"])

_FORMAT_MEDIA_TYPES: dict[str, str] = {
    "owl": "application/rdf+xml",
    "ttl": "text/turtle",
    "jsonld": "application/ld+json",
    "json": "application/json",
}


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


@router.get(
    "/export",
    summary="Export ontology in a specified format",
    responses={
        200: {
            "description": "Serialised ontology",
            "content": {
                "application/rdf+xml": {},
                "text/turtle": {},
                "application/ld+json": {},
                "application/json": {},
            },
        }
    },
)
async def export_ontology_route(
    ontology_id: uuid.UUID,
    format: Literal["owl", "ttl", "jsonld", "json"] = Query(
        "jsonld", description="Export format"
    ),
    session: AsyncSession = Depends(get_db),
) -> Response:
    ontology = await _get_ontology_or_404(ontology_id, session)

    try:
        content = await export_ontology(
            session, ontology_id, fmt=format, namespace_uri=ontology.namespace_uri,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception:
        logger.exception("Failed to export ontology %s as %s.", ontology_id, format)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export ontology.",
        )

    media_type = _FORMAT_MEDIA_TYPES.get(format, "application/octet-stream")
    extension = "rdf" if format == "owl" else format
    filename = f"ontology_{ontology_id}.{extension}"

    return Response(
        content=content if isinstance(content, bytes) else content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
