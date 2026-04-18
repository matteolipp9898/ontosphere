"""Ontology, OntologyVersion, Document and ConceptProvenance ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OntologyStatus(str, enum.Enum):
    """Lifecycle status of an ontology."""

    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class DocumentStatus(str, enum.Enum):
    """Processing status of an uploaded document."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Ontology(Base):
    """Core ontology entity owned by a user."""

    __tablename__ = "ontologies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    namespace_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[OntologyStatus] = mapped_column(
        String(20),
        default=OntologyStatus.DRAFT,
        server_default=OntologyStatus.DRAFT.value,
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        onupdate=func.now(),
        server_default=func.now(),
    )

    # -- Relationships --
    user: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="ontologies",
        lazy="selectin",
    )
    versions: Mapped[list["OntologyVersion"]] = relationship(
        "OntologyVersion",
        back_populates="ontology",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OntologyVersion.version_number.desc()",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="ontology",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    provenance_records: Mapped[list["ConceptProvenance"]] = relationship(
        "ConceptProvenance",
        back_populates="ontology",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Ontology id={self.id!r} name={self.name!r}>"


class OntologyVersion(Base):
    """Immutable snapshot of an ontology at a given version number."""

    __tablename__ = "ontology_versions"

    ontology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ontologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_jsonld: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    # -- Relationships --
    ontology: Mapped["Ontology"] = relationship(
        "Ontology",
        back_populates="versions",
    )

    def __repr__(self) -> str:
        return (
            f"<OntologyVersion ontology_id={self.ontology_id!r} "
            f"v={self.version_number}>"
        )


class Document(Base):
    """A document uploaded for ontology extraction."""

    __tablename__ = "documents"

    ontology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ontologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        String(20),
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # `uploaded_at` is the same as `created_at` from Base; alias via property.

    # -- Relationships --
    ontology: Mapped["Ontology"] = relationship(
        "Ontology",
        back_populates="documents",
    )
    provenance_records: Mapped[list["ConceptProvenance"]] = relationship(
        "ConceptProvenance",
        back_populates="document",
        lazy="selectin",
    )

    @property
    def uploaded_at(self) -> datetime:
        """Alias for ``created_at`` to match the domain language."""
        return self.created_at

    def __repr__(self) -> str:
        return f"<Document id={self.id!r} filename={self.filename!r}>"


class ConceptProvenance(Base):
    """Records which LLM interaction produced a given concept."""

    __tablename__ = "concept_provenance"

    ontology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ontologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # -- Relationships --
    ontology: Mapped["Ontology"] = relationship(
        "Ontology",
        back_populates="provenance_records",
    )
    document: Mapped["Document | None"] = relationship(
        "Document",
        back_populates="provenance_records",
    )

    def __repr__(self) -> str:
        return (
            f"<ConceptProvenance id={self.id!r} concept_uri={self.concept_uri!r}>"
        )
