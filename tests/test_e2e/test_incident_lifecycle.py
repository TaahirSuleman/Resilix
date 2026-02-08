from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_full_incident_lifecycle_with_timeline(test_client):
    payload = {
        "version": "4",
        "groupKey": "lifecycle-group",
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
                "annotations": {"summary": "Lifecycle alert"},
                "startsAt": "2026-02-02T10:30:00Z",
            }
        ],
    }

    create_response = await test_client.post("/webhook/prometheus", json=payload)
    assert create_response.status_code == 200
    incident_id = create_response.json()["incident_id"]

    detail_response = await test_client.get(f"/incidents/{incident_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["integration_trace"]["execution_path"] == "adk"
    assert detail["integration_trace"]["execution_reason"] == "adk_success"

    assert detail["status"] == "awaiting_approval"
    assert detail["pr_status"] == "ci_passed"
    assert detail["approval_status"] == "pending"

    initial_event_types = [event["event_type"] for event in detail["timeline"]]
    assert "incident_created" in initial_event_types
    assert "alert_validated" in initial_event_types
    assert "root_cause_identified" in initial_event_types
    assert "ticket_created" in initial_event_types
    assert "pr_created" in initial_event_types

    approve_response = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approve_response.status_code == 200

    final_detail_response = await test_client.get(f"/incidents/{incident_id}")
    assert final_detail_response.status_code == 200
    final_detail = final_detail_response.json()
    assert final_detail["integration_trace"]["execution_path"] == "adk"
    assert final_detail["integration_trace"]["execution_reason"] == "adk_success"

    assert final_detail["status"] == "resolved"
    assert final_detail["pr_status"] == "merged"
    assert final_detail["approval_status"] == "approved"
    assert final_detail["resolved_at"] is not None
    assert final_detail["mttr_seconds"] is not None

    final_event_types = [event["event_type"] for event in final_detail["timeline"]]
    assert "pr_merged" in final_event_types
    assert "incident_resolved" in final_event_types
