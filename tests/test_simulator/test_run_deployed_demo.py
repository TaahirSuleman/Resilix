from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

import simulator.scripts.run_deployed_demo as run_deployed_demo


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _FakeDemoClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.detail_count = 0

    def __enter__(self) -> "_FakeDemoClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/health"):
            return _FakeResponse(
                200,
                {
                    "status": "ok",
                    "adk_mode": "strict",
                    "effective_use_mock_providers": False,
                    "integration_backends": {"jira": "jira_api", "github": "github_api"},
                },
            )
        if "/incidents/" in url:
            self.detail_count += 1
            if self.detail_count == 1:
                return _FakeResponse(
                    200,
                    {
                        "incident_id": "INC-1",
                        "status": "awaiting_approval",
                        "timeline": [],
                    },
                )
            return _FakeResponse(
                200,
                {
                    "incident_id": "INC-1",
                    "status": "resolved",
                    "timeline": [],
                },
            )
        raise RuntimeError(f"Unexpected URL: {url}")

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/webhook/prometheus"):
            return _FakeResponse(200, {"incident_id": "INC-1"})
        if url.endswith("/incidents/INC-1/approve-merge"):
            return _FakeResponse(200, {"incident_id": "INC-1", "status": "resolved"})
        raise RuntimeError(f"Unexpected URL: {url}")


class _FakeDemoClientTriggerTimeout:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.detail_count = 0
        self.trigger_attempts = 0

    def __enter__(self) -> "_FakeDemoClientTriggerTimeout":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/health"):
            return _FakeResponse(
                200,
                {
                    "status": "ok",
                    "adk_mode": "strict",
                    "effective_use_mock_providers": False,
                    "integration_backends": {"jira": "jira_api", "github": "github_api"},
                },
            )
        if url.endswith("/incidents"):
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return _FakeResponse(
                200,
                {
                    "items": [
                        {
                            "incident_id": "INC-timeout-1",
                            "service_name": "dns-resolver",
                            "severity": "critical",
                            "created_at": now,
                        }
                    ]
                },
            )
        if "/incidents/" in url:
            self.detail_count += 1
            if self.detail_count == 1:
                return _FakeResponse(
                    200,
                    {
                        "incident_id": "INC-timeout-1",
                        "status": "awaiting_approval",
                        "timeline": [],
                    },
                )
            return _FakeResponse(
                200,
                {
                    "incident_id": "INC-timeout-1",
                    "status": "resolved",
                    "timeline": [],
                },
            )
        raise RuntimeError(f"Unexpected URL: {url}")

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/webhook/prometheus"):
            self.trigger_attempts += 1
            raise run_deployed_demo.httpx.ReadTimeout("trigger timeout")
        if url.endswith("/incidents/INC-timeout-1/approve-merge"):
            return _FakeResponse(200, {"incident_id": "INC-timeout-1", "status": "resolved"})
        raise RuntimeError(f"Unexpected URL: {url}")


def test_validate_health_preflight_rejects_mock() -> None:
    with pytest.raises(RuntimeError, match="Mock providers are enabled"):
        run_deployed_demo._validate_health_preflight(
            {
                "status": "ok",
                "adk_mode": "strict",
                "effective_use_mock_providers": True,
                "integration_backends": {"jira": "jira_api", "github": "github_api"},
            }
        )


def test_run_deployed_demo_writes_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("httpx.Client", _FakeDemoClient)
    monkeypatch.setattr(
        "simulator.scripts.run_deployed_demo.verify_external_side_effects",
        lambda **kwargs: {"ok": True, "incident_id": kwargs["incident_id"]},
    )
    monkeypatch.setenv("GITHUB_OWNER", "acme")

    argv = [
        "run_deployed_demo.py",
        "--base-url",
        "https://example.run.app",
        "--scenario",
        "baseline",
        "--artifacts-dir",
        str(tmp_path),
    ]
    monkeypatch.setattr("sys.argv", argv)

    run_deployed_demo.main()

    dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())
    assert dirs, "Expected one artifacts directory"
    artifact_dir = dirs[0]
    assert (artifact_dir / "health.json").exists()
    assert (artifact_dir / "incident.json").exists()
    assert (artifact_dir / "external_checks.json").exists()
    assert (artifact_dir / "summary.md").exists()


def test_run_deployed_demo_recovers_incident_id_after_trigger_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("httpx.Client", _FakeDemoClientTriggerTimeout)
    monkeypatch.setattr(
        "simulator.scripts.run_deployed_demo.verify_external_side_effects",
        lambda **kwargs: {"ok": True, "incident_id": kwargs["incident_id"]},
    )
    monkeypatch.setenv("GITHUB_OWNER", "acme")

    argv = [
        "run_deployed_demo.py",
        "--base-url",
        "https://example.run.app",
        "--scenario",
        "flapping",
        "--artifacts-dir",
        str(tmp_path),
        "--trigger-retries",
        "1",
    ]
    monkeypatch.setattr("sys.argv", argv)

    run_deployed_demo.main()

    dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())
    assert dirs, "Expected one artifacts directory"
    artifact_dir = dirs[0]
    accepted = json.loads((artifact_dir / "accepted.json").read_text(encoding="utf-8"))
    assert accepted["incident_id"] == "INC-timeout-1"
    assert accepted["recovered_via"] in {
        "incident_list_lookup_after_trigger_timeout",
        "final_incident_list_lookup_after_trigger_timeouts",
    }
