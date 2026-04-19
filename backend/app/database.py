"""Async database engine, session helpers, and Apache AGE utilities.

Provides:
- ``async_engine`` / ``async_session_factory`` for general use.
- ``get_db()`` – FastAPI dependency yielding an ``AsyncSession``.
- ``init_db()`` – one-time DDL bootstrap (AGE extension, graph creation).
- ``execute_age_query()`` / ``create_age_graph()`` – thin wrappers for Cypher
  queries executed through the AGE extension.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    The session is committed on success and rolled back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

_AGE_SEARCH_PATH = "SET search_path = ag_catalog, '$user', public;"


async def init_db() -> None:
    """Create the AGE extension and the default ontosphere graph.

    Safe to call multiple times – uses ``IF NOT EXISTS`` guards.
    """
    async with async_engine.begin() as conn:
        # Enable the AGE extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS age;"))
        await conn.execute(text("LOAD 'age';"))
        await conn.execute(text(_AGE_SEARCH_PATH))

        # Create default graph
        try:
            await conn.execute(
                text("SELECT create_graph('ontosphere');")
            )
            logger.info("Created AGE graph 'ontosphere'.")
        except Exception:
            # Graph already exists – that's fine.
            logger.debug("AGE graph 'ontosphere' already exists.")

    logger.info("Database initialisation complete.")


# ---------------------------------------------------------------------------
# Startup migration: move tables misplaced in ag_catalog back to public
# ---------------------------------------------------------------------------

_MANAGED_TABLES = ("users", "ontologies", "documents", "ontology_versions", "concept_provenance")


async def fix_misplaced_tables() -> None:
    """Move application tables from ag_catalog to public if they were created there by mistake."""
    async with async_engine.begin() as conn:
        for table in _MANAGED_TABLES:
            row = await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'ag_catalog' AND table_name = :tbl"
                ),
                {"tbl": table},
            )
            if row.scalar_one_or_none() is not None:
                logger.warning(
                    "Table %r found in ag_catalog — moving to public.", table
                )
                await conn.execute(
                    text(f'ALTER TABLE ag_catalog."{table}" SET SCHEMA public;')
                )
    logger.info("Misplaced-table migration check complete.")


# ---------------------------------------------------------------------------
# AGE helpers
# ---------------------------------------------------------------------------


async def create_age_graph(session: AsyncSession, graph_name: str) -> None:
    """Create a new AGE graph if it does not already exist.

    Args:
        session: Active async database session.
        graph_name: Name for the new graph (must contain only alphanumerics and underscores).
    """
    # Sanitise the graph name to prevent injection
    safe_name = graph_name.replace("-", "_")
    if not safe_name.replace("_", "").isalnum():
        raise ValueError(f"Invalid graph name: {graph_name!r}")

    await session.execute(text("LOAD 'age';"))
    await session.execute(text(_AGE_SEARCH_PATH))
    try:
        # Use a savepoint so that a "graph already exists" error does not
        # poison the outer transaction.
        async with session.begin_nested():
            await session.execute(text(f"SELECT create_graph('{safe_name}');"))
        logger.info("Created AGE graph %r.", safe_name)
    except Exception:
        logger.debug("AGE graph %r already exists.", safe_name)


def _cypher_literal(value: Any) -> str:
    """Convert a Python value to a Cypher literal string."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    # Everything else → single-quoted Cypher string with escaping.
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _interpolate_cypher(cypher: str, params: dict[str, Any] | None) -> str:
    """Replace ``$param`` placeholders in a Cypher query with literal values.

    AGE does not support native bind parameters inside the ``$$ … $$``
    dollar-quoted Cypher string, so values must be embedded directly.
    Keys are replaced longest-first to avoid ``$uri`` matching inside
    ``$uri_prefix``.
    """
    if not params:
        return cypher
    for key in sorted(params, key=len, reverse=True):
        cypher = cypher.replace(f"${key}", _cypher_literal(params[key]))
    return cypher


async def execute_age_query(
    session: AsyncSession,
    graph_name: str,
    cypher: str,
    params: dict[str, Any] | None = None,
    columns: str = "result agtype",
) -> list[Any]:
    """Execute a Cypher query against an AGE graph.

    Args:
        session: Active async database session.
        graph_name: Target graph name.
        cypher: Cypher query string.  Use ``$param`` placeholders for values
            that will be interpolated via :func:`_interpolate_cypher`.
        params: Optional dict of query parameters.
        columns: Column definition for the AS clause
            (e.g. ``"n agtype"`` or ``"a agtype, r agtype, b agtype"``).

    Returns:
        A list of result rows.
    """
    resolved_cypher = _interpolate_cypher(cypher, params)
    try:
        await session.execute(text("LOAD 'age';"))
        await session.execute(text(_AGE_SEARCH_PATH))

        sql = f"SELECT * FROM cypher('{graph_name}', $$ {resolved_cypher} $$) AS ({columns});"
        # Escape :word patterns (e.g. Cypher [:RANGE]) that SQLAlchemy's
        # text() would misinterpret as SQL bind parameters.  The lookbehind
        # skips word-chars and colons so n:Class and :: casts are untouched.
        sql = re.sub(r"(?<![\w:]):(\w+)", r"\:\1", sql)
        result = await session.execute(text(sql))
        rows = result.fetchall()
        logger.debug(
            "AGE query on graph %r returned %d row(s).", graph_name, len(rows)
        )
        return rows
    except Exception:
        logger.error(
            "AGE query failed on graph %r — cypher: %.300s | params: %r",
            graph_name,
            resolved_cypher,
            params,
            exc_info=True,
        )
        await session.rollback()
        raise
