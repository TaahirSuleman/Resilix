from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import simulator.scripts.run_deployed_demo as run_deployed_demo
import simulator.scripts.run_scenario as run_scenario
import simulator.scripts.trigger_alert as trigger_alert


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


def test_trigger_alert_stamps_simulation_payload(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            if url.endswith("/webhook/prometheus"):
                captured["payload"] = kwargs["json"]
                return _FakeResponse(200, {"incident_id": "INC-1"})
            raise RuntimeError(f"Unexpected URL: {url}")

    monkeypatch.setattr("httpx.Client", _FakeClient)
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setattr(
        "sys.argv",
        [
            "trigger_alert.py",
            "--base-url",
            "https://example.run.app",
            "--scenario",
            "flapping",
        ],
    )

    trigger_alert.main()
    simulation = captured["payload"]["simulation"]
    assert simulation["source"] == "resilix-simulator"
    assert simulation["scenario"] == "flapping"
    assert simulation["seed"] == 42
    assert simulation["generated_at"]


def test_trigger_alert_fixture_mode_stamps_simulation_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "status": "firing",
                "alerts": [
                    {
                        "labels": {
                            "alertname": "DNSResolverFlapping",
                            "service": "dns-resolver",
                            "severity": "critical",
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            if url.endswith("/webhook/prometheus"):
                captured["payload"] = kwargs["json"]
                return _FakeResponse(200, {"incident_id": "INC-1"})
            raise RuntimeError(f"Unexpected URL: {url}")

    monkeypatch.setattr("httpx.Client", _FakeClient)
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setattr(
        "sys.argv",
        [
            "trigger_alert.py",
            "--base-url",
            "https://example.run.app",
            "--scenario",
            "flapping",
            "--fixture",
            str(fixture),
        ],
    )

    trigger_alert.main()
    simulation = captured["payload"]["simulation"]
    assert simulation["source"] == "resilix-simulator"
    assert simulation["scenario"] == "flapping"


def test_run_scenario_stamps_simulation_payload(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {"detail_calls": 0}

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def get(self, url: str, **kwargs: Any) -> _FakeResponse:
            if "/incidents/" in url:
                captured["detail_calls"] += 1
                return _FakeResponse(200, {"incident_id": "INC-1", "status": "resolved"})
            raise RuntimeError(f"Unexpected URL: {url}")

        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            if url.endswith("/webhook/prometheus"):
                captured["payload"] = kwargs["json"]
                return _FakeResponse(200, {"incident_id": "INC-1"})
            raise RuntimeError(f"Unexpected URL: {url}")

    monkeypatch.setattr("httpx.Client", _FakeClient)
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_scenario.py",
            "--base-url",
            "https://example.run.app",
            "--scenario",
            "flapping",
        ],
    )

    run_scenario.main()
    simulation = captured["payload"]["simulation"]
    assert simulation["source"] == "resilix-simulator"
    assert simulation["scenario"] == "flapping"


def test_run_deployed_demo_stamps_simulation_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {"detail_calls": 0}

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_FakeClient":
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
                captured["detail_calls"] += 1
                status = "awaiting_approval" if captured["detail_calls"] == 1 else "resolved"
                return _FakeResponse(200, {"incident_id": "INC-1", "status": status, "timeline": []})
            raise RuntimeError(f"Unexpected URL: {url}")

        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            if url.endswith("/webhook/prometheus"):
                captured["payload"] = kwargs["json"]
                return _FakeResponse(200, {"incident_id": "INC-1"})
            if url.endswith("/incidents/INC-1/approve-merge"):
                return _FakeResponse(200, {"incident_id": "INC-1", "status": "resolved"})
            raise RuntimeError(f"Unexpected URL: {url}")

    monkeypatch.setattr("httpx.Client", _FakeClient)
    monkeypatch.setattr(
        "simulator.scripts.run_deployed_demo.verify_external_side_effects",
        lambda **kwargs: {"ok": True, "incident_id": kwargs["incident_id"]},
    )
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_deployed_demo.py",
            "--base-url",
            "https://example.run.app",
            "--scenario",
            "flapping",
            "--artifacts-dir",
            str(tmp_path),
        ],
    )

    run_deployed_demo.main()
    simulation = captured["payload"]["simulation"]
    assert simulation["source"] == "resilix-simulator"
    assert simulation["scenario"] == "flapping"
