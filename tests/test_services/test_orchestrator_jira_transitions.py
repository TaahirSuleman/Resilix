from __future__ import annotations

import pytest

from resilix.services.session import get_session_store


def _payload() -> dict:
    return {
        "version": "4",
        "groupKey": "jira-transition-test",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ServiceHealthFlapping",
                    "service": "checkout-api",
                    "severity": "critical",
                },
                "annotations": {"summary": "Transition workflow test"},
                "startsAt": "2026-02-07T10:00:00Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_orchestrator_records_jira_transitions_in_order(test_client):
    response = await test_client.post("/webhook/prometheus", json=_payload())
    assert response.status_code == 200
    incident_id = response.json()["incident_id"]

    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None

    trace = state.get("integration_trace", {})
    transitions = trace.get("jira_transitions", [])
    assert len(transitions) >= 3
    assert [item.get("to_status") for item in transitions[:3]] == [
        "To Do",
        "In Progress",
        "In Review",
    ]
    assert all(item.get("ok") is True for item in transitions[:3])
