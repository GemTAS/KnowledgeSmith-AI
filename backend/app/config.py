"""Application configuration via environment variables."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Centralised application settings loaded from environment / .env file."""

    # Ingestion
    ingestion_root: str = Field(
        default=".",
        alias="KNOWLEDGESMITH_INGESTION_ROOT",
        description="Root directory for source ingestion",
    )
    output_dir: str = Field(
        default="./output",
        alias="KNOWLEDGESMITH_OUTPUT_DIR",
        description="Output directory for knowledge artifacts",
    )
    max_file_size: int = Field(
        default=1_048_576,
        alias="KNOWLEDGESMITH_MAX_FILE_SIZE",
        description="Maximum file size in bytes",
    )
    allowed_extensions: str = Field(
        default=".md,.txt,.py,.json,.yaml,.yml",
        alias="KNOWLEDGESMITH_ALLOWED_EXTENSIONS",
        description="Comma-separated list of allowed file extensions",
    )

    # AI / LLM
    google_api_key: str = Field(
        default="",
        alias="GOOGLE_API_KEY",
        description="Google Gemini API key",
    )
    model_name: str = Field(
        default="gemini-2.5-flash",
        alias="KNOWLEDGESMITH_MODEL",
        description="Model name for LLM extraction",
    )
    use_llm: bool = Field(
        default=False,
        alias="KNOWLEDGESMITH_USE_LLM",
        description="Enable LLM-based extraction",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="KNOWLEDGESMITH_LOG_LEVEL",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── Derived helpers ────────────────────────────────────────────

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [e.strip() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def ingestion_root_path(self) -> Path:
        return Path(self.ingestion_root).resolve()

    @property
    def output_dir_path(self) -> Path:
        return Path(self.output_dir).resolve()


def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()


settings = get_settings()
