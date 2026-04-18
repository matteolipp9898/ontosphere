"""User ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    """A registered OntoSphere user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # -- Relationships --
    ontologies: Mapped[list["Ontology"]] = relationship(  # noqa: F821
        "Ontology",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Default seed user constants
    DEFAULT_EMAIL: str = "admin@ontosphere.local"
    DEFAULT_DISPLAY_NAME: str = "Admin"

    def __repr__(self) -> str:
        return f"<User id={self.id!r} email={self.email!r}>"
