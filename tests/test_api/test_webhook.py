from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_webhook_accepts_prometheus_alert(test_client):
    webhook_payload = {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "TestAlert",
                    "service": "test-service",
                    "severity": "critical",
                },
                "annotations": {"summary": "Test alert"},
                "startsAt": "2026-02-02T10:30:00Z",
            }
        ],
    }

    response = await test_client.post("/webhook/prometheus", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "incident_id" in data

    detail_response = await test_client.get(f"/incidents/{data['incident_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["incident_id"] == data["incident_id"]
    assert "status" in detail
    assert "approval_status" in detail
    assert "pr_status" in detail
    assert isinstance(detail["timeline"], list)
    trace = detail.get("integration_trace") or {}
    assert isinstance(trace.get("execution_path"), str)
    assert bool(trace.get("execution_path"))
    assert isinstance(trace.get("execution_reason"), str)
    assert bool(trace.get("execution_reason"))
    assert trace.get("runner_policy") == "adk_only"
