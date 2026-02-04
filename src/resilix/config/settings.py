from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_model_flash: str = "gemini-3-flash"
    gemini_model_pro: str = "gemini-3-pro"

    # Gemini thinking configuration
    sentinel_thinking_level: str = "low"
    sherlock_thinking_level: str = "high"
    mechanic_thinking_level: str = "high"
    include_thoughts: bool = True

    # Infrastructure
    database_url: Optional[str] = None

    # Feature flags
    use_mock_mcp: bool = True
    require_pr_approval: bool = True

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
