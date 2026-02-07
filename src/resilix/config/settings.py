from __future__ import annotations

import os
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
    use_mock_providers: bool = True
    # Deprecated alias kept for one migration cycle.
    use_mock_mcp: Optional[bool] = None
    require_pr_approval: bool = True
    require_ci_pass: bool = True
    require_codeowner_review: bool = True
    merge_method: str = "squash"

    # Integration modes
    jira_integration_mode: str = "api"
    github_integration_mode: str = "api"

    # GitHub integration
    github_token: Optional[str] = None
    github_owner: str = "PLACEHOLDER_OWNER"
    github_default_base_branch: str = "main"

    # Jira integration
    jira_url: Optional[str] = None
    jira_username: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_project_key: str = "PLACEHOLDER_JIRA_PROJECT_KEY"
    jira_issue_type: str = "Bug"
    jira_status_todo: str = "To Do"
    jira_status_in_progress: str = "In Progress"
    jira_status_in_review: str = "In Review"
    jira_status_done: str = "Done"
    jira_transition_strict: bool = False
    jira_transition_aliases: str = ""

    # Logging
    log_level: str = "INFO"
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    app_version: Optional[str] = None
    build_sha: Optional[str] = None
    build_time: Optional[str] = None
    frontend_dist_dir: Optional[str] = None

    def effective_use_mock_providers(self) -> bool:
        if os.getenv("USE_MOCK_PROVIDERS") is not None:
            return self.use_mock_providers
        if os.getenv("USE_MOCK_MCP") is not None and self.use_mock_mcp is not None:
            return self.use_mock_mcp
        return self.use_mock_providers

    def is_legacy_mock_flag_used(self) -> bool:
        return os.getenv("USE_MOCK_MCP") is not None and os.getenv("USE_MOCK_PROVIDERS") is None


@lru_cache
def get_settings() -> Settings:
    return Settings()
