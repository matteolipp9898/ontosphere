"""Application configuration via environment variables.

Uses pydantic-settings for validated, typed configuration. LLM-related fields
can be set via ``ONTOSPHERE_``-prefixed environment variables (e.g.
``ONTOSPHERE_LLM_API_KEY``) while all other fields use their exact field names
(no prefix).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import ClassVar

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator
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
    LLM_MAX_TOKENS: int = Field(
        default=16384,
        validation_alias=AliasChoices(
            "ONTOSPHERE_LLM_MAX_TOKENS", "LLM_MAX_TOKENS"
        ),
    )

    # -- Database --
    DATABASE_URL: str = (
        "postgresql+asyncpg://ontosphere:ontosphere@localhost:5432/ontosphere"
    )

    # -- Graph backend --
    GRAPH_BACKEND: str = Field(
        default="age",
        description="Graph storage backend: 'age' (Apache AGE) or 'neo4j'",
        validation_alias=AliasChoices("ONTOSPHERE_GRAPH_BACKEND", "GRAPH_BACKEND"),
    )
    NEO4J_URI: str = Field(
        default="bolt://localhost:7687",
        validation_alias=AliasChoices("ONTOSPHERE_NEO4J_URI", "NEO4J_URI"),
    )
    NEO4J_USER: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("ONTOSPHERE_NEO4J_USER", "NEO4J_USER"),
    )
    NEO4J_PASSWORD: str = Field(
        default="ontosphere",
        validation_alias=AliasChoices("ONTOSPHERE_NEO4J_PASSWORD", "NEO4J_PASSWORD"),
    )
    NEO4J_DATABASE: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("ONTOSPHERE_NEO4J_DATABASE", "NEO4J_DATABASE"),
    )

    # -- Redis / Celery --
    REDIS_URL: str = "redis://localhost:6379/0"

    # -- Security --
    SECRET_KEY: str = "dev-secret-key-change-in-production"

    # -- CORS --
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: object) -> list[str]:
        """Accept both JSON arrays and comma-separated strings."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [item.strip() for item in v.split(",") if item.strip()]
        return [str(v)]

    # -- Auto table creation --
    AUTO_CREATE_TABLES: bool = Field(
        default=True,
        validation_alias=AliasChoices("ONTOSPHERE_AUTO_CREATE_TABLES", "AUTO_CREATE_TABLES"),
    )

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
        allowed_backends = {"age", "neo4j"}
        if self.GRAPH_BACKEND not in allowed_backends:
            raise ValueError(
                f"GRAPH_BACKEND must be one of {allowed_backends}, got {self.GRAPH_BACKEND!r}"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton."""
    return Settings()
