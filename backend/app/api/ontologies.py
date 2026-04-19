"""CRUD routes for ontology resources."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology, OntologyStatus
from app.models.user import User
from app.schemas.ontology import OntologyCreate, OntologyRead, OntologyUpdate
from app.schemas.common import StatusResponse
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontologies", tags=["ontologies"])


async def _get_default_user_id(session: AsyncSession) -> uuid.UUID:
    """Return the ID of the default MVP admin user.

    Queries the User table for the well-known seed email.  Raises 500 if the
    seed user has not been created yet.
    """
    result = await session.execute(
        select(User).where(User.email == User.DEFAULT_EMAIL)
    )
    user = result.scalars().first()
    if user is None:
        logger.error("Default admin user (%s) not found in database.", User.DEFAULT_EMAIL)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default admin user not found. Run the database seed first.",
        )
    return user.id


async def _get_ontology_or_404(
    ontology_id: uuid.UUID,
    session: AsyncSession,
) -> Ontology:
    """Fetch an ontology by primary key or raise 404."""
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


def _ontology_to_read(ontology: Ontology) -> OntologyRead:
    """Convert an ORM Ontology to its read schema, including document_count."""
    return OntologyRead(
        id=ontology.id,
        name=ontology.name,
        description=ontology.description,
        namespace_uri=ontology.namespace_uri,
        status=ontology.status.value if isinstance(ontology.status, OntologyStatus) else ontology.status,
        created_at=ontology.created_at,
        updated_at=ontology.updated_at,
        document_count=len(ontology.documents) if ontology.documents else 0,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=OntologyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ontology",
)
@router.post("/", response_model=OntologyRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_ontology(
    body: OntologyCreate,
    session: AsyncSession = Depends(get_db),
) -> OntologyRead:
    user_id = await _get_default_user_id(session)
    ontology = Ontology(
        user_id=user_id,
        name=body.name,
        description=body.description,
        namespace_uri=body.namespace_uri,
    )
    session.add(ontology)
    await session.flush()

    # Create the backing AGE graph for this ontology.
    try:
        await GraphService.create_graph(session, ontology.id)
        logger.info(
            "Created AGE graph '%s' for ontology %s.",
            GraphService.graph_name(ontology.id),
            ontology.id,
        )
    except Exception as exc:
        logger.error(
            "Failed to create AGE graph for ontology %s: %s", ontology.id, exc
        )

    await session.refresh(ontology)
    logger.info("Created ontology %s (%s).", ontology.id, ontology.name)
    return _ontology_to_read(ontology)


@router.get(
    "",
    response_model=list[OntologyRead],
    summary="List all ontologies",
)
@router.get("/", response_model=list[OntologyRead], include_in_schema=False)
async def list_ontologies(
    session: AsyncSession = Depends(get_db),
) -> list[OntologyRead]:
    user_id = await _get_default_user_id(session)
    result = await session.execute(
        select(Ontology)
        .where(Ontology.user_id == user_id)
        .order_by(Ontology.created_at.desc())
    )
    ontologies = result.scalars().all()
    return [_ontology_to_read(o) for o in ontologies]


@router.get(
    "/{ontology_id}",
    response_model=OntologyRead,
    summary="Get a single ontology",
)
async def get_ontology(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> OntologyRead:
    ontology = await _get_ontology_or_404(ontology_id, session)
    return _ontology_to_read(ontology)


@router.patch(
    "/{ontology_id}",
    response_model=OntologyRead,
    summary="Update an ontology",
)
async def update_ontology(
    ontology_id: uuid.UUID,
    body: OntologyUpdate,
    session: AsyncSession = Depends(get_db),
) -> OntologyRead:
    ontology = await _get_ontology_or_404(ontology_id, session)
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update.",
        )
    for field, value in update_data.items():
        setattr(ontology, field, value)
    await session.flush()
    await session.refresh(ontology)
    logger.info("Updated ontology %s.", ontology.id)
    return _ontology_to_read(ontology)


@router.delete(
    "/{ontology_id}",
    response_model=StatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an ontology",
)
async def delete_ontology(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> StatusResponse:
    ontology = await _get_ontology_or_404(ontology_id, session)
    await session.delete(ontology)
    await session.flush()
    logger.info("Deleted ontology %s.", ontology_id)
    return StatusResponse(status="ok", message=f"Ontology {ontology_id} deleted.")
