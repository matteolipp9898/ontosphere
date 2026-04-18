"""Tests for ontology CRUD operations via the ontology service layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ontology import Ontology
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _ensure_user(db: AsyncSession) -> User:
    """Return a test user, creating one if needed."""
    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Test User",
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


async def _create_ontology(
    db: AsyncSession,
    name: str = "Test Ontology",
    description: str = "A test ontology",
    user: User | None = None,
) -> Ontology:
    """Insert an Ontology row and return it."""
    if user is None:
        user = await _ensure_user(db)

    ontology = Ontology(
        id=uuid.uuid4(),
        name=name,
        description=description,
        namespace_uri="http://example.org/test#",
        status="draft",
        user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(ontology)
    await db.commit()
    await db.refresh(ontology)
    return ontology


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_ontology(db_session: AsyncSession):
    """Creating an ontology persists all fields correctly."""
    ontology = await _create_ontology(db_session, name="My Ontology", description="Desc")

    assert ontology.id is not None
    assert ontology.name == "My Ontology"
    assert ontology.description == "Desc"
    assert ontology.status == "draft"
    assert isinstance(ontology.created_at, datetime)


@pytest.mark.asyncio
async def test_list_ontologies(db_session: AsyncSession):
    """Listing ontologies returns all persisted records."""
    user = await _ensure_user(db_session)
    await _create_ontology(db_session, name="Ontology A", user=user)
    await _create_ontology(db_session, name="Ontology B", user=user)

    result = await db_session.execute(select(Ontology))
    ontologies = result.scalars().all()

    assert len(ontologies) == 2
    names = {o.name for o in ontologies}
    assert names == {"Ontology A", "Ontology B"}


@pytest.mark.asyncio
async def test_update_ontology(db_session: AsyncSession):
    """Updating an ontology's name is reflected on subsequent read."""
    ontology = await _create_ontology(db_session, name="Original Name")
    ontology_id = ontology.id

    ontology.name = "Updated Name"
    await db_session.commit()

    result = await db_session.execute(select(Ontology).where(Ontology.id == ontology_id))
    refreshed = result.scalar_one()

    assert refreshed.name == "Updated Name"


@pytest.mark.asyncio
async def test_delete_ontology(db_session: AsyncSession):
    """Deleting an ontology removes it from the database."""
    ontology = await _create_ontology(db_session, name="To Delete")
    ontology_id = ontology.id

    await db_session.delete(ontology)
    await db_session.commit()

    result = await db_session.execute(select(Ontology).where(Ontology.id == ontology_id))
    assert result.scalar_one_or_none() is None
