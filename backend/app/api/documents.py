"""Document upload and listing routes for a given ontology."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.ontology import Document, Ontology
from app.schemas.ontology import DocumentRead

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/ontologies/{ontology_id}/documents",
    tags=["documents"],
)

ALLOWED_CONTENT_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

# Some browsers send generic types; map extensions as fallback.
_EXTENSION_TO_CONTENT_TYPE: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
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


def _resolve_content_type(upload: UploadFile) -> str:
    """Determine a valid content type from the upload metadata or filename."""
    ct = upload.content_type or ""
    if ct in ALLOWED_CONTENT_TYPES:
        return ct
    # Fall back to extension-based detection
    if upload.filename:
        suffix = Path(upload.filename).suffix.lower()
        if suffix in _EXTENSION_TO_CONTENT_TYPE:
            return _EXTENSION_TO_CONTENT_TYPE[suffix]
    return ct


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=list[DocumentRead],
    status_code=status.HTTP_201_CREATED,
    summary="Upload one or more documents",
)
async def upload_documents(
    ontology_id: uuid.UUID,
    files: list[UploadFile],
    session: AsyncSession = Depends(get_db),
) -> list[DocumentRead]:
    await _get_ontology_or_404(ontology_id, session)

    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    upload_dir = Path(settings.UPLOAD_DIR) / str(ontology_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    created_docs: list[DocumentRead] = []

    for upload in files:
        # --- content type validation ---
        content_type = _resolve_content_type(upload)
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Unsupported file type '{content_type}' for "
                    f"'{upload.filename}'. Allowed: PDF, DOCX, TXT, MD."
                ),
            )

        # --- read & size validation ---
        data = await upload.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File '{upload.filename}' exceeds the maximum size of "
                    f"{settings.MAX_FILE_SIZE_MB} MB."
                ),
            )

        # --- persist to disk ---
        file_id = uuid.uuid4()
        safe_name = f"{file_id}_{upload.filename or 'unnamed'}"
        file_path = upload_dir / safe_name
        file_path.write_bytes(data)

        # --- create database record ---
        doc = Document(
            ontology_id=ontology_id,
            filename=upload.filename or "unnamed",
            content_type=content_type,
            file_path=str(file_path),
            file_size=len(data),
        )
        session.add(doc)
        await session.flush()
        await session.refresh(doc)

        logger.info(
            "Uploaded document %s (%s, %d bytes) for ontology %s.",
            doc.id,
            doc.filename,
            doc.file_size,
            ontology_id,
        )
        created_docs.append(DocumentRead.model_validate(doc))

    return created_docs


@router.get(
    "/",
    response_model=list[DocumentRead],
    summary="List documents for an ontology",
)
async def list_documents(
    ontology_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[DocumentRead]:
    await _get_ontology_or_404(ontology_id, session)

    result = await session.execute(
        select(Document)
        .where(Document.ontology_id == ontology_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [DocumentRead.model_validate(d) for d in docs]
