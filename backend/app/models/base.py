"""Declarative base with common columns for all OntoSphere models.

Every model that inherits from :class:`Base` automatically receives:

- ``id`` – UUID primary key with a database-side default of ``gen_random_uuid()``.
- ``created_at`` – Timestamp with timezone defaulting to ``now()``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    """Shared declarative base for all OntoSphere ORM models."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )
