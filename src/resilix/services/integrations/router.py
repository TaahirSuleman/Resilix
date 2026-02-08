from __future__ import annotations

from resilix.config import get_settings
from resilix.services.integrations.base import CodeProvider, ProviderConfigError, TicketProvider
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


def _normalize_mode(provider: str, mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized in {"api", "mock"}:
        return normalized
    raise ProviderConfigError(
        provider=provider,
        mode=mode,
        reason_code="invalid_mode",
        missing_or_invalid_fields=[f"{provider.upper()}_INTEGRATION_MODE"],
    )


def _missing_jira_fields(settings: object) -> list[str]:
    missing: list[str] = []
    if not _usable(getattr(settings, "jira_url", None)):
        missing.append("JIRA_URL")
    if not _usable(getattr(settings, "jira_username", None)):
        missing.append("JIRA_USERNAME")
    if not _usable(getattr(settings, "jira_api_token", None)):
        missing.append("JIRA_API_TOKEN")
    if not _usable(getattr(settings, "jira_project_key", None)):
        missing.append("JIRA_PROJECT_KEY")
    return missing


def _missing_github_fields(settings: object) -> list[str]:
    missing: list[str] = []
    if not _usable(getattr(settings, "github_token", None)):
        missing.append("GITHUB_TOKEN")
    if not _usable(getattr(settings, "github_owner", None)):
        missing.append("GITHUB_OWNER")
    return missing


def get_ticket_provider() -> tuple[TicketProvider, str]:
    settings = get_settings()
    mode = _normalize_mode("jira", settings.jira_integration_mode)
    if mode == "mock":
        return MockTicketProvider(), "jira_mock"
    missing = _missing_jira_fields(settings)
    if missing:
        raise ProviderConfigError(
            provider="jira",
            mode=mode,
            reason_code="missing_or_invalid_config",
            missing_or_invalid_fields=missing,
        )
    provider = JiraDirectProvider(
        jira_url=settings.jira_url or "",
        username=settings.jira_username or "",
        api_token=settings.jira_api_token or "",
        project_key=settings.jira_project_key,
        issue_type=settings.jira_issue_type,
        transition_strict=settings.jira_transition_strict,
        transition_aliases=settings.jira_transition_aliases,
    )
    return provider, "jira_api"


def get_code_provider() -> tuple[CodeProvider, str]:
    settings = get_settings()
    mode = _normalize_mode("github", settings.github_integration_mode)
    if mode == "mock":
        return MockCodeProvider(), "github_mock"
    missing = _missing_github_fields(settings)
    if missing:
        raise ProviderConfigError(
            provider="github",
            mode=mode,
            reason_code="missing_or_invalid_config",
            missing_or_invalid_fields=missing,
        )
    provider = GithubDirectProvider(
        token=settings.github_token or "",
        owner=settings.github_owner,
        default_base_branch=settings.github_default_base_branch,
    )
    return provider, "github_api"


def get_provider_readiness() -> dict[str, dict[str, object]]:
    settings = get_settings()
    readiness: dict[str, dict[str, object]] = {}

    for provider_name, mode_value, missing_fn in (
        ("jira", settings.jira_integration_mode, _missing_jira_fields),
        ("github", settings.github_integration_mode, _missing_github_fields),
    ):
        try:
            mode = _normalize_mode(provider_name, mode_value)
        except ProviderConfigError as exc:
            readiness[provider_name] = {
                "ready": False,
                "resolved_backend": "unavailable",
                "reason": exc.reason_code,
                "missing_fields": exc.missing_or_invalid_fields,
            }
            continue

        if mode == "mock":
            readiness[provider_name] = {
                "ready": True,
                "resolved_backend": f"{provider_name}_mock",
                "reason": "mock_mode",
                "missing_fields": [],
            }
            continue

        missing_fields = missing_fn(settings)
        if missing_fields:
            readiness[provider_name] = {
                "ready": False,
                "resolved_backend": "unavailable",
                "reason": "missing_or_invalid_config",
                "missing_fields": missing_fields,
            }
            continue

        readiness[provider_name] = {
            "ready": True,
            "resolved_backend": f"{provider_name}_api",
            "reason": "ok",
            "missing_fields": [],
        }

    return readiness
