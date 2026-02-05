from __future__ import annotations

import pytest


def _payload(service: str, starts_at: str) -> dict:
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
                    "service": service,
                    "severity": "critical",
                },
                "annotations": {"summary": f"Alert for {service}"},
                "startsAt": starts_at,
            }
        ],
    }


@pytest.mark.asyncio
async def test_list_incidents_returns_latest_100(test_client):
    for idx in range(3):
        response = await test_client.post(
            "/webhook/prometheus",
            json=_payload(service=f"svc-{idx}", starts_at=f"2026-02-02T10:3{idx}:00Z"),
        )
        assert response.status_code == 200

    response = await test_client.get("/incidents")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert len(body["items"]) == 3
    assert body["items"][0]["created_at"] >= body["items"][1]["created_at"]


@pytest.mark.asyncio
async def test_get_incident_returns_contract_shape(test_client):
    response = await test_client.post(
        "/webhook/prometheus",
        json=_payload(service="dns-resolver", starts_at="2026-02-02T10:30:00Z"),
    )
    incident_id = response.json()["incident_id"]

    detail_response = await test_client.get(f"/incidents/{incident_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()

    assert detail["incident_id"] == incident_id
    assert detail["severity"] == "critical"
    assert detail["service_name"] == "dns-resolver"
    assert "created_at" in detail
    assert "approval_status" in detail
    assert "pr_status" in detail
    assert isinstance(detail["timeline"], list)
