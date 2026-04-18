"""SHACL validation route for an ontology."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ontology import Ontology
from app.schemas.graph import ValidationResult, ValidationViolation
from app.services.validation_service import validate_ontology
from app.services.validation_service import (
    ValidationResult as ServiceValidationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ontologies/{ontology_id}", tags=["validation"])


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


def _to_schema_result(svc: ServiceValidationResult) -> ValidationResult:
    """Convert service-layer validation dataclass to Pydantic schema."""
    all_violations = []
    for v in svc.violations:
        all_violations.append(
            ValidationViolation(
                severity=v.severity,
                focus_node=v.focus_node,
                message=v.message,
                path=v.path,
            )
        )
    for w in svc.warnings:
        all_violations.append(
            ValidationViolation(
                severity=w.severity or "Warning",
                focus_node=w.focus_node,
                message=w.message,
                path=w.path,
            )
        )
    return ValidationResult(
        conforms=svc.conforms,
        violations=all_violations,
        results_text=svc.raw_report,
    )


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Run SHACL validation on the ontology",
)
async def validate_ontology_route(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ValidationResult:
    ontology = await _get_ontology_or_404(ontology_id, session)

    try:
        svc_result = await validate_ontology(
            session, ontology_id, namespace_uri=ontology.namespace_uri,
        )
    except Exception:
        logger.exception("Validation failed for ontology %s.", ontology_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Validation failed due to an internal error.",
        )

    return _to_schema_result(svc_result)
