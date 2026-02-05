from __future__ import annotations

import pytest


def _payload() -> dict:
    return {
        "version": "4",
        "groupKey": "contract-group",
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
                "annotations": {"summary": "Contract test alert"},
                "startsAt": "2026-02-02T10:30:00Z",
            }
        ],
    }


@pytest.mark.asyncio
async def test_incident_list_schema_snapshot(test_client):
    create_response = await test_client.post("/webhook/prometheus", json=_payload())
    assert create_response.status_code == 200

    response = await test_client.get("/incidents")
    assert response.status_code == 200
    body = response.json()

    assert sorted(body.keys()) == ["items"]
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 1

    item = body["items"][0]
    assert sorted(item.keys()) == [
        "approval_status",
        "created_at",
        "incident_id",
        "mttr_seconds",
        "pr_status",
        "service_name",
        "severity",
        "status",
    ]


@pytest.mark.asyncio
async def test_incident_detail_schema_snapshot(test_client):
    create_response = await test_client.post("/webhook/prometheus", json=_payload())
    assert create_response.status_code == 200
    incident_id = create_response.json()["incident_id"]

    response = await test_client.get(f"/incidents/{incident_id}")
    assert response.status_code == 200
    detail = response.json()

    assert sorted(detail.keys()) == [
        "approval_status",
        "created_at",
        "incident_id",
        "jira_ticket",
        "mttr_seconds",
        "pr_status",
        "remediation_result",
        "resolved_at",
        "service_name",
        "severity",
        "status",
        "thought_signature",
        "timeline",
        "validated_alert",
    ]

    assert isinstance(detail["timeline"], list)
    assert isinstance(detail["validated_alert"], dict)
    assert isinstance(detail["thought_signature"], dict)
    assert isinstance(detail["jira_ticket"], dict)
    assert isinstance(detail["remediation_result"], dict)
