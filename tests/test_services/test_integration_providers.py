from __future__ import annotations

from base64 import b64encode
from typing import Any

import pytest

from resilix.models.remediation import RecommendedAction
from resilix.services.integrations.base import ProviderConfigError
from resilix.services.integrations.github_direct import GithubDirectProvider
from resilix.services.integrations.jira_direct import JiraDirectProvider
from resilix.services.integrations.router import (
    get_code_provider,
    get_provider_readiness,
    get_ticket_provider,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("GET", url, kwargs))
        if "/issue/" in url and url.endswith("/transitions"):
            return _FakeResponse(
                200,
                {
                    "transitions": [
                        {"id": "1", "name": "Start Progress", "to": {"name": "In Progress"}},
                        {"id": "2", "name": "Ready for Review", "to": {"name": "In Review"}},
                        {"id": "3", "name": "Done", "to": {"name": "Done"}},
                    ]
                },
            )
        if "/issue/" in url:
            return _FakeResponse(200, {"fields": {"status": {"name": "To Do"}}})
        if url.endswith("/status"):
            return _FakeResponse(200, {"state": "success"})
        if "/reviews" in url:
            return _FakeResponse(200, [{"state": "APPROVED"}])
        if "/git/ref/heads/" in url:
            return _FakeResponse(200, {"object": {"sha": "abc123"}})
        if "/contents/" in url:
            return _FakeResponse(404, {})
        if "/pulls/" in url:
            return _FakeResponse(200, {"head": {"sha": "abc123"}, "mergeable_state": "clean"})
        return _FakeResponse(200, {"default_branch": "main"})

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/issue"):
            return _FakeResponse(201, {"key": "SRE-101"})
        if url.endswith("/git/refs"):
            return _FakeResponse(201, {"ref": "refs/heads/fix"})
        if url.endswith("/pulls"):
            return _FakeResponse(201, {"number": 42, "html_url": "https://github.com/o/r/pull/42"})
        return _FakeResponse(200, {})

    async def put(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("PUT", url, kwargs))
        if url.endswith("/merge"):
            return _FakeResponse(200, {"merged": True})
        return _FakeResponse(201, {"content": {"sha": "def456"}})


class _FakeAsyncClientWithDnsContent(_FakeAsyncClient):
    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(("GET", url, kwargs))
        if "/git/ref/heads/" in url:
            return _FakeResponse(200, {"object": {"sha": "abc123"}})
        if "/contents/infra/dns/coredns-config.yaml" in url:
            source = """apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-config
data:
  Corefile: |
    .:53 {
        errors
        forward . 10.0.0.1:53
        cache 30
    }
  failover_mode: "DISABLED_MANUAL"
"""
            content_b64 = b64encode(source.encode("utf-8")).decode("utf-8")
            return _FakeResponse(
                200,
                {"sha": "file-sha", "encoding": "base64", "content": content_b64},
            )
        return await super().get(url, **kwargs)


@pytest.mark.asyncio
async def test_jira_direct_provider_normalizes_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    provider = JiraDirectProvider(
        jira_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="token",
        project_key="SRE",
        issue_type="Bug",
    )
    result = await provider.create_incident_ticket(
        incident_id="INC-001",
        summary="[AUTO] test issue",
        description="description",
        priority="High",
    )
    assert result.ticket_key == "SRE-101"
    assert result.ticket_url.endswith("/browse/SRE-101")


@pytest.mark.asyncio
async def test_jira_direct_transition_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    provider = JiraDirectProvider(
        jira_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="token",
        project_key="SRE",
        issue_type="Bug",
    )
    result = await provider.transition_ticket(ticket_key="SRE-101", target_status="In Progress")
    assert result["ok"] is True
    assert result["applied_transition_id"] == "1"


@pytest.mark.asyncio
async def test_jira_direct_transition_alias_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    provider = JiraDirectProvider(
        jira_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="token",
        project_key="SRE",
        issue_type="Bug",
        transition_aliases='{"in review":["ready for review"]}',
    )
    result = await provider.transition_ticket(ticket_key="SRE-101", target_status="In Review")
    assert result["ok"] is True
    assert result["applied_transition_id"] == "2"


@pytest.mark.asyncio
async def test_jira_direct_transition_unavailable_non_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    provider = JiraDirectProvider(
        jira_url="https://example.atlassian.net",
        username="user@example.com",
        api_token="token",
        project_key="SRE",
        issue_type="Bug",
    )
    result = await provider.transition_ticket(ticket_key="SRE-101", target_status="Blocked")
    assert result["ok"] is False
    assert "No transition found" in str(result["reason"])


@pytest.mark.asyncio
async def test_github_direct_provider_normalizes_pr_and_merge_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")

    remediation = await provider.create_remediation_pr(
        incident_id="INC-002",
        repository="owner/resilix-demo-app",
        target_file="README.md",
        action=RecommendedAction.CONFIG_CHANGE,
        summary="fix issue",
    )
    assert remediation.pr_number == 42
    assert remediation.pr_url and remediation.pr_url.endswith("/pull/42")

    gate = await provider.get_merge_gate_status(repository="owner/resilix-demo-app", pr_number=42)
    assert gate.ci_passed is True
    assert gate.codeowner_reviewed is True


@pytest.mark.asyncio
async def test_github_direct_provider_returns_diff_preview_for_dns_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClientWithDnsContent)
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")

    remediation = await provider.create_remediation_pr(
        incident_id="INC-003",
        repository="owner/resilix-demo-config",
        target_file="infra/dns/coredns-config.yaml",
        action=RecommendedAction.CONFIG_CHANGE,
        summary="dns fix",
    )

    assert remediation.target_file == "infra/dns/coredns-config.yaml"
    assert remediation.diff_old_line is not None
    assert remediation.diff_new_line is not None
    assert "forward . 10.0.0.1:53" in remediation.diff_old_line
    assert "forward . 1.1.1.1 8.8.8.8 9.9.9.9" in remediation.diff_new_line


def test_router_raises_in_api_mode_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    import resilix.config.settings as settings_module

    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "api")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "api")
    monkeypatch.setenv("JIRA_URL", "PLACEHOLDER_JIRA_URL")
    monkeypatch.setenv("JIRA_USERNAME", "PLACEHOLDER_JIRA_USERNAME")
    monkeypatch.setenv("JIRA_API_TOKEN", "PLACEHOLDER_JIRA_API_TOKEN")
    monkeypatch.setenv("GITHUB_TOKEN", "PLACEHOLDER_GITHUB_TOKEN")
    monkeypatch.setenv("GITHUB_OWNER", "PLACEHOLDER_OWNER")
    settings_module.get_settings.cache_clear()

    with pytest.raises(ProviderConfigError, match="jira_missing_or_invalid_config"):
        get_ticket_provider()
    with pytest.raises(ProviderConfigError, match="github_missing_or_invalid_config"):
        get_code_provider()


def test_router_returns_mock_in_explicit_mock_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    import resilix.config.settings as settings_module

    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")
    settings_module.get_settings.cache_clear()

    _, ticket_name = get_ticket_provider()
    _, code_name = get_code_provider()

    assert ticket_name == "jira_mock"
    assert code_name == "github_mock"


def test_provider_readiness_reports_unready_api_config(monkeypatch: pytest.MonkeyPatch) -> None:
    import resilix.config.settings as settings_module

    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "api")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "api")
    monkeypatch.setenv("JIRA_URL", "PLACEHOLDER_JIRA_URL")
    monkeypatch.setenv("JIRA_USERNAME", "PLACEHOLDER_JIRA_USERNAME")
    monkeypatch.setenv("JIRA_API_TOKEN", "PLACEHOLDER_JIRA_API_TOKEN")
    monkeypatch.setenv("JIRA_PROJECT_KEY", "PLACEHOLDER_JIRA_PROJECT_KEY")
    monkeypatch.setenv("GITHUB_TOKEN", "PLACEHOLDER_GITHUB_TOKEN")
    monkeypatch.setenv("GITHUB_OWNER", "PLACEHOLDER_OWNER")
    settings_module.get_settings.cache_clear()

    readiness = get_provider_readiness()
    assert readiness["jira"]["ready"] is False
    assert readiness["jira"]["resolved_backend"] == "unavailable"
    assert readiness["jira"]["reason"] == "missing_or_invalid_config"
    assert "JIRA_URL" in readiness["jira"]["missing_fields"]
    assert readiness["github"]["ready"] is False
    assert readiness["github"]["resolved_backend"] == "unavailable"
    assert readiness["github"]["reason"] == "missing_or_invalid_config"
    assert "GITHUB_TOKEN" in readiness["github"]["missing_fields"]


def test_github_direct_patches_coredns_config_content() -> None:
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")
    source = """apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-config
data:
  Corefile: |
    .:53 {
        errors
        forward . 10.0.0.1:53
        cache 30
    }
  failover_mode: "DISABLED_MANUAL"
"""
    patched = provider._build_remediated_content(
        target_file="infra/dns/coredns-config.yaml",
        existing_content=source,
        action=RecommendedAction.CONFIG_CHANGE,
        summary="dns fix",
        remediation_context={},
    )
    assert patched is not None
    assert "forward . 1.1.1.1 8.8.8.8 9.9.9.9" in patched
    assert 'failover_mode: "AUTO"' in patched


def test_github_direct_patches_dependencies_yaml_content() -> None:
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")
    source = """upstream:
  timeout_ms: 9000
  max_retries: 10
  backoff_ms: 5000
  circuit_breaker_enabled: false
"""
    patched = provider._build_remediated_content(
        target_file="infra/dependencies.yaml",
        existing_content=source,
        action=RecommendedAction.CONFIG_CHANGE,
        summary="dependency fix",
        remediation_context={},
    )
    assert patched is not None
    assert "timeout_ms: 1500" in patched
    assert "max_retries: 3" in patched
    assert "backoff_ms: 250" in patched
    assert "circuit_breaker_enabled: true" in patched


def test_github_direct_patches_handlers_py_content() -> None:
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")
    source = """import requests

def handler():
    return requests.get("https://example.com")
"""
    patched = provider._build_remediated_content(
        target_file="src/app/handlers.py",
        existing_content=source,
        action=RecommendedAction.FIX_CODE,
        summary="handler fix",
        remediation_context={},
    )
    assert patched is not None
    assert "_resilix_safe_http_call(requests.get, " in patched
    assert "def _resilix_safe_http_call" in patched


def test_github_direct_unknown_target_falls_back() -> None:
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")
    patched = provider._build_remediated_content(
        target_file="README.md",
        existing_content="# docs\n",
        action=RecommendedAction.FIX_CODE,
        summary="fallback",
        remediation_context={},
    )
    assert patched is None


def test_github_direct_default_preview_for_dns_target() -> None:
    provider = GithubDirectProvider(token="token", owner="owner", default_base_branch="main")
    old_line, new_line = provider._default_preview_for_target(
        target_file="infra/dns/coredns-config.yaml",
        action=RecommendedAction.CONFIG_CHANGE,
    )
    assert old_line == "forward . 10.0.0.1:53"
    assert new_line == "forward . 1.1.1.1 8.8.8.8 9.9.9.9"
