from __future__ import annotations

from typing import Any

import pytest

from simulator.scripts.verify_external_side_effects import (
    verify_github_side_effects,
    verify_jira_side_effects,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeJiraClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeJiraClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if "/rest/api/3/issue/" in url:
            return _FakeResponse(
                200,
                {
                    "fields": {"status": {"name": "Done"}},
                    "changelog": {
                        "histories": [
                            {"items": [{"field": "status", "toString": "In Progress"}]},
                            {"items": [{"field": "status", "toString": "In Review"}]},
                            {"items": [{"field": "status", "toString": "Done"}]},
                        ]
                    },
                },
            )
        raise RuntimeError(f"Unexpected URL: {url}")


class _FakeJiraClientReverse:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeJiraClientReverse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if "/rest/api/3/issue/" in url:
            return _FakeResponse(
                200,
                {
                    "fields": {"status": {"name": "Done"}},
                    "changelog": {
                        "histories": [
                            {"created": "2026-02-08T12:03:00+00:00", "items": [{"field": "status", "toString": "Done"}]},
                            {"created": "2026-02-08T12:02:00+00:00", "items": [{"field": "status", "toString": "In Review"}]},
                            {"created": "2026-02-08T12:01:00+00:00", "items": [{"field": "status", "toString": "In Progress"}]},
                            {"created": "2026-02-08T12:00:00+00:00", "items": [{"field": "status", "toString": "To Do"}]},
                        ]
                    },
                },
            )
        raise RuntimeError(f"Unexpected URL: {url}")


class _FakeGithubClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_FakeGithubClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/pulls/123"):
            return _FakeResponse(200, {"merge_commit_sha": "abc123"})
        if url.endswith("/pulls/123/merge"):
            return _FakeResponse(204, {})
        if url.endswith("/commits/abc123"):
            return _FakeResponse(200, {"parents": [{"sha": "p1"}]})
        raise RuntimeError(f"Unexpected URL: {url}")


def test_verify_jira_side_effects_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.Client", _FakeJiraClient)
    monkeypatch.setenv("JIRA_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.setenv("JIRA_STATUS_IN_PROGRESS", "In Progress")
    monkeypatch.setenv("JIRA_STATUS_IN_REVIEW", "In Review")
    monkeypatch.setenv("JIRA_STATUS_DONE", "Done")

    result = verify_jira_side_effects(ticket_key="SRE-100", timeout_seconds=5.0)
    assert result["ok"] is True
    assert result["done_ok"] is True
    assert result["sequence_ok"] is True


def test_verify_jira_side_effects_handles_newest_first_changelog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("httpx.Client", _FakeJiraClientReverse)
    monkeypatch.setenv("JIRA_URL", "https://example.atlassian.net")
    monkeypatch.setenv("JIRA_USERNAME", "user@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "token")
    monkeypatch.setenv("JIRA_STATUS_IN_PROGRESS", "In Progress")
    monkeypatch.setenv("JIRA_STATUS_IN_REVIEW", "In Review")
    monkeypatch.setenv("JIRA_STATUS_DONE", "Done")

    result = verify_jira_side_effects(ticket_key="SRE-100", timeout_seconds=5.0)
    assert result["ok"] is True
    assert result["done_ok"] is True
    assert result["sequence_ok"] is True


def test_verify_github_side_effects_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.Client", _FakeGithubClient)
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    result = verify_github_side_effects(
        repository="acme/resilix-demo-app",
        pr_number=123,
        expected_merge_method="squash",
        timeout_seconds=5.0,
    )
    assert result["ok"] is True
    assert result["merged"] is True
    assert result["merge_method_check"]["ok"] is True
