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
# AGE helpers
# ---------------------------------------------------------------------------


async def create_age_graph(session: AsyncSession, graph_name: str) -> None:
    """Create a new AGE graph if it does not already exist.

    Args:
        session: Active async database session.
        graph_name: Name for the new graph.
    """
    await session.execute(text(_AGE_SEARCH_PATH))
    try:
        await session.execute(text(f"SELECT create_graph('{graph_name}');"))
        logger.info("Created AGE graph %r.", graph_name)
    except Exception:
        logger.debug("AGE graph %r already exists.", graph_name)


async def execute_age_query(
    session: AsyncSession,
    graph_name: str,
    cypher: str,
    params: dict[str, Any] | None = None,
) -> list[Any]:
    """Execute a Cypher query against an AGE graph.

    Args:
        session: Active async database session.
        graph_name: Target graph name.
        cypher: Cypher query string.  Use ``$param`` placeholders.
        params: Optional dict of query parameters.

    Returns:
        A list of result rows.
    """
    await session.execute(text(_AGE_SEARCH_PATH))

    # AGE uses the ``cypher()`` SQL function.  Parameters are interpolated
    # by the caller because AGE does not support native bind parameters.
    sql = f"SELECT * FROM cypher('{graph_name}', $$ {cypher} $$) AS (result agtype);"
    result = await session.execute(text(sql), params or {})
    rows = result.fetchall()
    logger.debug(
        "AGE query on graph %r returned %d row(s).", graph_name, len(rows)
    )
    return rows
