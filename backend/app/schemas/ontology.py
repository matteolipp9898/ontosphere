"""Pydantic v2 schemas for ontology-related API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------


class OntologyCreate(BaseModel):
    """Payload to create a new ontology."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    namespace_uri: str = Field(..., min_length=1, max_length=2048)


class OntologyUpdate(BaseModel):
    """Payload for partial ontology updates."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    namespace_uri: str | None = Field(default=None, min_length=1, max_length=2048)


class OntologyRead(BaseModel):
    """Read representation of an ontology."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    namespace_uri: str
    status: str
    created_at: datetime
    updated_at: datetime | None = None
    document_count: int = 0


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class DocumentRead(BaseModel):
    """Read representation of a document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ontology_id: UUID
    filename: str
    content_type: str
    file_size: int
    status: str
    error_message: str | None = None
    uploaded_at: datetime


# ---------------------------------------------------------------------------
# Ontology Version
# ---------------------------------------------------------------------------


class OntologyVersionCreate(BaseModel):
    """Payload to create a new ontology version snapshot."""

    description: str = ""


class OntologyVersionRead(BaseModel):
    """Read representation of an ontology version."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ontology_id: UUID
    version_number: int
    description: str
    created_at: datetime
