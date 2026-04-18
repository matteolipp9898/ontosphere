"""Version management routes for ontology snapshots."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology, OntologyVersion
from app.schemas.common import StatusResponse
from app.schemas.ontology import OntologyVersionCreate, OntologyVersionRead
from app.services.ontology_service import create_version, list_versions, rollback_version

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ontologies/{ontology_id}/versions",
    tags=["versions"],
)


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=list[OntologyVersionRead],
    summary="List ontology versions",
)
async def list_ontology_versions(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[OntologyVersionRead]:
    await _get_ontology_or_404(ontology_id, session)

    try:
        versions = await list_versions(session, ontology_id)
    except Exception:
        logger.exception("Failed to list versions for ontology %s.", ontology_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list versions.",
        )

    return [OntologyVersionRead.model_validate(v) for v in versions]


@router.post(
    "/",
    response_model=OntologyVersionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a version snapshot",
)
async def create_ontology_version(
    ontology_id: uuid.UUID,
    body: OntologyVersionCreate,
    session: AsyncSession = Depends(get_db),
) -> OntologyVersionRead:
    await _get_ontology_or_404(ontology_id, session)

    try:
        version = await create_version(session, ontology_id, body.description)
    except Exception:
        logger.exception("Failed to create version for ontology %s.", ontology_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create version snapshot.",
        )

    return OntologyVersionRead.model_validate(version)


@router.post(
    "/{version_id}/rollback",
    response_model=StatusResponse,
    summary="Rollback to a specific version",
)
async def rollback_ontology_version(
    ontology_id: uuid.UUID,
    version_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    await _get_ontology_or_404(ontology_id, session)

    # Verify the version exists and belongs to the ontology
    result = await session.execute(
        select(OntologyVersion).where(
            OntologyVersion.id == version_id,
            OntologyVersion.ontology_id == ontology_id,
        )
    )
    version = result.scalars().first()
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found for ontology {ontology_id}.",
        )

    try:
        await rollback_version(session, ontology_id, version_id)
    except Exception:
        logger.exception(
            "Failed to rollback ontology %s to version %s.", ontology_id, version_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rollback to the requested version.",
        )

    return StatusResponse(
        status="ok",
        message=f"Rolled back to version {version.version_number}.",
    )
