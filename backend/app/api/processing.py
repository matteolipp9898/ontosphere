"""Routes for kicking off and checking ontology processing tasks."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology, OntologyStatus
from app.schemas.common import TaskStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontologies/{ontology_id}", tags=["processing"])


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


@router.post(
    "/process",
    response_model=TaskStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start ontology processing",
)
async def start_processing(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> TaskStatus:
    ontology = await _get_ontology_or_404(ontology_id, session)

    if ontology.status == OntologyStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ontology is already being processed.",
        )

    # Ensure there is at least one document to process
    if not ontology.documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload at least one document before processing.",
        )

    # Mark the ontology as processing
    ontology.status = OntologyStatus.PROCESSING
    await session.flush()

    # Dispatch the Celery task
    from app.tasks.processing import process_ontology_task

    task = process_ontology_task.delay(str(ontology_id))

    logger.info(
        "Dispatched processing task %s for ontology %s.", task.id, ontology_id
    )
    return TaskStatus(
        task_id=task.id,
        status="processing",
        progress=0,
        message="Processing started.",
    )


@router.get(
    "/status",
    response_model=TaskStatus,
    summary="Get ontology processing status",
)
async def get_processing_status(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> TaskStatus:
    ontology = await _get_ontology_or_404(ontology_id, session)

    ont_status = (
        ontology.status.value
        if isinstance(ontology.status, OntologyStatus)
        else ontology.status
    )

    # If the ontology is processing, try to get Celery task info
    if ontology.status == OntologyStatus.PROCESSING:
        from celery.result import AsyncResult
        from app.tasks.processing import process_ontology_task

        # Inspect active tasks for this ontology (convention: task_id stored
        # or we look it up).  For simplicity, return the DB status with a
        # placeholder task_id.  A production implementation would persist the
        # task_id on the ontology model.
        return TaskStatus(
            task_id="",
            status=ont_status,
            progress=50,
            message="Ontology is currently being processed.",
        )

    if ontology.status == OntologyStatus.ERROR:
        return TaskStatus(
            task_id="",
            status=ont_status,
            progress=0,
            message="Processing failed.",
        )

    if ontology.status == OntologyStatus.READY:
        return TaskStatus(
            task_id="",
            status=ont_status,
            progress=100,
            message="Processing complete.",
        )

    # DRAFT or any other status
    return TaskStatus(
        task_id="",
        status=ont_status,
        progress=0,
        message="Ontology has not been processed yet.",
    )
