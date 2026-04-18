"""Shared / generic Pydantic v2 schemas used across the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    """Simple status response for health checks and generic acknowledgements."""

    status: str
    message: str = ""


class TaskStatus(BaseModel):
    """Progress report for a long-running background task (Celery)."""

    task_id: str
    status: str
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    result: dict[str, Any] | None = None


class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper."""

    items: list[Any]
    total: int
    page: int
    page_size: int
