from __future__ import annotations

from resilix.config import get_settings
from resilix.services.integrations.base import CodeProvider, TicketProvider
from resilix.services.integrations.github_direct import GithubDirectProvider
from resilix.services.integrations.jira_direct import JiraDirectProvider
from resilix.services.integrations.mock_providers import MockCodeProvider, MockTicketProvider

_PLACEHOLDERS = {
    "",
    "placeholder",
    "placeholder_github_token",
    "placeholder_jira_api_token",
    "placeholder_jira_url",
    "placeholder_jira_username",
    "placeholder_jira_project_key",
    "placeholder_owner",
}


def _usable(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in _PLACEHOLDERS


def get_ticket_provider() -> tuple[TicketProvider, str]:
    settings = get_settings()
    mode = settings.jira_integration_mode.lower()
    if mode == "api" and _usable(settings.jira_url) and _usable(settings.jira_username) and _usable(settings.jira_api_token):
        provider = JiraDirectProvider(
            jira_url=settings.jira_url or "",
            username=settings.jira_username or "",
            api_token=settings.jira_api_token or "",
            project_key=settings.jira_project_key,
            issue_type=settings.jira_issue_type,
        )
        return provider, "jira_api"
    return MockTicketProvider(), "jira_mock"


def get_code_provider() -> tuple[CodeProvider, str]:
    settings = get_settings()
    mode = settings.github_integration_mode.lower()
    if mode == "api" and _usable(settings.github_token) and _usable(settings.github_owner):
        provider = GithubDirectProvider(
            token=settings.github_token or "",
            owner=settings.github_owner,
            default_base_branch=settings.github_default_base_branch,
        )
        return provider, "github_api"
    return MockCodeProvider(), "github_mock"
