from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

import pytest


def _payload() -> dict:
    return {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "DNSResolverFlapping",
                    "service": "dns-resolver",
                    "severity": "critical",
                },
                "annotations": {"summary": "Test alert"},
                "startsAt": "2026-02-02T10:30:00Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_approve_merge_success_when_ci_passed_and_pr_exists(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 200
    detail = approve_response.json()
    assert detail["pr_status"] == "merged"
    assert detail["approval_status"] == "approved"
    transitions = (detail.get("integration_trace") or {}).get("jira_transitions") or []
    assert any(item.get("to_status") == "Done" and item.get("ok") is True for item in transitions)


@pytest.mark.asyncio
async def test_approve_merge_returns_409_when_ci_not_passed(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    # Force pending CI state
    from resilix.services.session import get_session_store

    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None
    state["ci_status"] = "pending"
    await store.save(incident_id, state)

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 409
    assert approve_response.json()["detail"]["code"] == "ci_not_passed"


@pytest.mark.asyncio
async def test_approve_merge_returns_409_when_pr_missing(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    from resilix.services.session import get_session_store

    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None
    state["remediation_result"] = {
        "success": True,
        "action_taken": "fix_code",
        "execution_time_seconds": 1.0,
    }
    await store.save(incident_id, state)

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 409
    assert approve_response.json()["detail"]["code"] == "pr_not_created"


@pytest.mark.asyncio
async def test_approve_merge_returns_409_when_codeowner_review_missing(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    from resilix.services.session import get_session_store

    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None
    state["ci_status"] = "ci_passed"
    state["codeowner_review_status"] = "pending"
    state["thought_signature"] = {"target_repository": None}
    await store.save(incident_id, state)

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 409
    assert approve_response.json()["detail"]["code"] == "codeowner_review_required"


@pytest.mark.asyncio
async def test_approve_merge_returns_404_for_missing_incident(test_client):
    approve_response = await test_client.post("/incidents/INC-DOESNOTEXIST/approve-merge")
    assert approve_response.status_code == 404


@pytest.mark.asyncio
async def test_approve_merge_uses_current_runtime_gate_settings_over_stale_policy(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    from resilix.services.session import get_session_store
    import resilix.config.settings as settings_module

    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None
    state["ci_status"] = "pending"
    state["codeowner_review_status"] = "pending"
    state["policy"] = {"require_ci_pass": True, "require_codeowner_review": True}
    if isinstance(state.get("thought_signature"), dict):
        state["thought_signature"]["target_repository"] = None
    await store.save(incident_id, state)

    with patch.dict(
        os.environ,
        {"REQUIRE_CI_PASS": "false", "REQUIRE_CODEOWNER_REVIEW": "false"},
        clear=False,
    ):
        settings_module.get_settings.cache_clear()
        approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")

    assert approve_response.status_code == 200
    detail = approve_response.json()
    assert detail["approval_status"] == "approved"
    assert detail["pr_status"] == "merged"


@pytest.mark.asyncio
async def test_approve_merge_emits_simulation_recovery_log(
    monkeypatch: pytest.MonkeyPatch,
    test_client,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _CaptureLogger:
        def info(self, message: str, **kwargs: Any) -> None:
            calls.append((message, kwargs))

        def warning(self, message: str, **kwargs: Any) -> None:
            calls.append((message, kwargs))

    monkeypatch.setattr("resilix.api.incidents.logger", _CaptureLogger())
    payload = _payload()
    payload["simulation"] = {"source": "resilix-simulator", "scenario": "flapping", "seed": 42}
    response = await test_client.post("/webhook/prometheus", json=payload)
    incident_id = response.json()["incident_id"]

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 200
    messages = [message for message, _ in calls]
    assert "Simulated recovery verified" in messages


@pytest.mark.asyncio
async def test_approve_merge_skips_simulation_recovery_log_for_non_simulation_payload(
    monkeypatch: pytest.MonkeyPatch,
    test_client,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _CaptureLogger:
        def info(self, message: str, **kwargs: Any) -> None:
            calls.append((message, kwargs))

        def warning(self, message: str, **kwargs: Any) -> None:
            calls.append((message, kwargs))

    monkeypatch.setattr("resilix.api.incidents.logger", _CaptureLogger())
    response = await test_client.post("/webhook/prometheus", json=_payload())
    incident_id = response.json()["incident_id"]

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 200
    messages = [message for message, _ in calls]
    assert "Simulated recovery verified" not in messages
