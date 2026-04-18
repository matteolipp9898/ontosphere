"""Application configuration via environment variables.

Uses pydantic-settings for validated, typed configuration. LLM-related fields
can be set via ``ONTOSPHERE_``-prefixed environment variables (e.g.
``ONTOSPHERE_LLM_API_KEY``) while all other fields use their exact field names
(no prefix).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import ClassVar

from pydantic import AliasChoices, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Full application settings.

    LLM fields accept both ``ONTOSPHERE_``-prefixed and unprefixed env vars
    (prefixed takes precedence).  All other fields use their plain names.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- LLM (accept ONTOSPHERE_-prefixed env vars) --
    LLM_API_BASE: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("ONTOSPHERE_LLM_API_BASE", "LLM_API_BASE"),
    )
    LLM_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("ONTOSPHERE_LLM_API_KEY", "LLM_API_KEY"),
    )
    LLM_MODEL: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("ONTOSPHERE_LLM_MODEL", "LLM_MODEL"),
    )
    LLM_PROVIDER: str = Field(
        default="openai",
        description="openai | azure | anthropic",
        validation_alias=AliasChoices("ONTOSPHERE_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    LLM_API_VERSION: str = Field(
        default="2024-10-21",
        validation_alias=AliasChoices(
            "ONTOSPHERE_LLM_API_VERSION", "LLM_API_VERSION"
        ),
    )

    # -- Database --
    DATABASE_URL: str = (
        "postgresql+asyncpg://ontosphere:ontosphere@localhost:5432/ontosphere"
    )

    # -- Redis / Celery --
    REDIS_URL: str = "redis://localhost:6379/0"

    # -- Security --
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # -- CORS --
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # -- Uploads --
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Internal constant -- not a settings field.
    _ASYNCPG_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"postgresql\+asyncpg://", re.IGNORECASE
    )

    @computed_field  # type: ignore[misc]
    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Derive a synchronous (psycopg2) URL from the async one."""
        return self._ASYNCPG_RE.sub("postgresql+psycopg2://", self.DATABASE_URL)

    @model_validator(mode="after")
    def _validate_llm_provider(self) -> "Settings":
        allowed = {"openai", "azure", "anthropic"}
        if self.LLM_PROVIDER not in allowed:
            raise ValueError(
                f"LLM_PROVIDER must be one of {allowed}, got {self.LLM_PROVIDER!r}"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton."""
    return Settings()
