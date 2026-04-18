"""OntoSphere FastAPI application entry point.

Configures middleware, lifespan events, exception handlers, and mounts
all API routers.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api import api_router
from app.config import get_settings
from app.database import async_session_factory, init_db
from app.models.user import User
from app.schemas.common import StatusResponse

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

settings = get_settings()


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle."""
    logger.info("Starting OntoSphere API v%s ...", _app.version)

    # Ensure the upload directory exists.
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Initialise database (AGE extension, default graph).
    try:
        await init_db()
    except Exception:
        logger.warning(
            "Database initialisation failed – AGE extension may not be available. "
            "The app will continue without graph support.",
            exc_info=True,
        )

    # Seed the default admin user if not present.
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.email == User.DEFAULT_EMAIL)
            )
            if result.scalar_one_or_none() is None:
                default_user = User(
                    email=User.DEFAULT_EMAIL,
                    display_name=User.DEFAULT_DISPLAY_NAME,
                )
                session.add(default_user)
                await session.commit()
                logger.info("Created default admin user (%s).", User.DEFAULT_EMAIL)
            else:
                logger.debug("Default admin user already exists.")
    except Exception:
        logger.warning(
            "Could not seed default user – database tables may not exist yet. "
            "Run Alembic migrations first.",
            exc_info=True,
        )

    yield  # Application is running.

    logger.info("Shutting down OntoSphere API ...")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OntoSphere API",
    version="0.1.0",
    description="Generate ontologies from documents using LLMs.",
    lifespan=lifespan,
)

# -- CORS --
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return a consistent JSON structure for HTTP errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Return 422 for unhandled value errors."""
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unexpected exceptions.  Log and return 500."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix="/api")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health", response_model=StatusResponse, tags=["health"])
async def health_check() -> StatusResponse:
    """Basic liveness probe."""
    return StatusResponse(status="ok", message="OntoSphere API is running.")
