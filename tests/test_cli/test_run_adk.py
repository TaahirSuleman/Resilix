from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import resilix.run_adk as run_adk


class _FakeRunner:
    def __init__(self, _root_agent):
        pass

    async def run(self, payload: dict, incident_id: str) -> dict:
        return {"payload": payload, "incident_id": incident_id, "status": "ok"}


def test_validate_env_rejects_mock_mode() -> None:
    settings = SimpleNamespace(
        gemini_api_key="abc",
        effective_use_mock_providers=lambda: True,
    )
    with pytest.raises(RuntimeError, match="USE_MOCK_PROVIDERS"):
        run_adk._validate_env(settings)


def test_validate_env_requires_api_key() -> None:
    settings = SimpleNamespace(
        gemini_api_key=None,
        effective_use_mock_providers=lambda: False,
    )
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        run_adk._validate_env(settings)


def test_validate_env_rejects_placeholder_api_key() -> None:
    settings = SimpleNamespace(
        gemini_api_key="your_key",
        effective_use_mock_providers=lambda: False,
    )
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        run_adk._validate_env(settings)


def test_load_payload_from_json_arg() -> None:
    args = SimpleNamespace(alert_json='{"status":"firing"}', alert_file=None)
    payload = run_adk._load_payload(args)
    assert payload["status"] == "firing"


def test_main_runs_and_prints_result(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    payload = {"status": "firing", "alerts": []}

    monkeypatch.setattr(run_adk, "AdkRunner", _FakeRunner)
    monkeypatch.setattr(run_adk, "get_root_agent", lambda: object())
    monkeypatch.setattr(
        run_adk,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-key",
            effective_use_mock_providers=lambda: False,
        ),
    )

    args = ["run_adk", "--alert-json", json.dumps(payload), "--incident-id", "INC-CLI-001"]
    monkeypatch.setattr("sys.argv", args)

    run_adk.main()
    out = capsys.readouterr().out
    result = json.loads(out)

    assert result["incident_id"] == "INC-CLI-001"
    assert result["status"] == "ok"
    assert result["payload"]["status"] == "firing"
