from __future__ import annotations

import pytest

from resilix.services.session import get_session_store


def _config_error_payload() -> dict:
    return {
        "version": "4",
        "groupKey": "phase4-config-error",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ServiceHealthFlapping",
                    "service": "edge-router",
                    "severity": "critical",
                },
                "annotations": {"summary": "Health checks are unstable with growing backlog"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
        "log_entries": [
            {
                "timestamp": "2026-02-05T12:38:23Z",
                "level": "ERROR",
                "service": "NLB",
                "component": "HealthCheckSubsystem",
                "event": "TargetHealthFlapping",
                "message": "Targets alternating between healthy and unhealthy due to propagation backlog",
                "metadata": {"queue_depth": 230061, "unhealthy_targets_count": 480},
            },
            {
                "timestamp": "2026-02-05T12:38:41Z",
                "level": "ERROR",
                "service": "NLB",
                "component": "HealthCheckSubsystem",
                "event": "TargetHealthFlapping",
                "message": "Targets alternating between healthy and unhealthy due to propagation backlog",
                "metadata": {"queue_depth": 330234, "unhealthy_targets_count": 583},
            },
            {
                "timestamp": "2026-02-05T12:38:49Z",
                "level": "ERROR",
                "service": "coredns",
                "component": "ResolverClient",
                "event": "ResolverDialTimeout",
                "message": "Resolver request timed out under queue pressure",
                "metadata": {"timeout_ms": 980, "resolver": "10.0.0.1:53"},
            },
            {
                "timestamp": "2026-02-05T12:38:57Z",
                "level": "ERROR",
                "service": "checkout-api",
                "component": "DnsClient",
                "event": "DependencyTimeout",
                "message": "DNS dependency timed out while routing checkout traffic",
                "metadata": {"timeout_ms": 1460, "dependency": "dns-resolver"},
            },
            {
                "timestamp": "2026-02-05T12:39:05Z",
                "level": "WARN",
                "service": "edge-router",
                "component": "RetryController",
                "event": "CircuitBreakerOpen",
                "message": "Retry saturation detected after timeout bursts",
                "metadata": {"open_circuits": 4, "error_class": "DependencyTimeout"},
            },
        ],
    }


@pytest.mark.asyncio
async def test_generic_config_error_lifecycle(test_client):
    create = await test_client.post("/webhook/prometheus", json=_config_error_payload())
    assert create.status_code == 200
    incident_id = create.json()["incident_id"]

    detail = await test_client.get(f"/incidents/{incident_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "awaiting_approval"
    assert body["thought_signature"]["root_cause_category"] == "config_error"
    assert body["remediation_result"]["action_taken"] == "config_change"
    pre_transitions = (body.get("integration_trace") or {}).get("jira_transitions") or []
    assert [item.get("to_status") for item in pre_transitions[:3]] == ["To Do", "In Progress", "In Review"]
    event_types = [event["event_type"] for event in body.get("timeline", [])]
    assert "ticket_moved_in_progress" in event_types
    assert "pr_created" in event_types
    assert "ticket_moved_in_review" in event_types
    assert event_types.index("ticket_moved_in_progress") < event_types.index("pr_created")
    assert event_types.index("pr_created") < event_types.index("ticket_moved_in_review")

    approved = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approved.status_code == 200
    final_body = approved.json()
    assert final_body["status"] == "resolved"
    assert final_body["pr_status"] == "merged"
    post_transitions = (final_body.get("integration_trace") or {}).get("jira_transitions") or []
    assert any(item.get("to_status") == "Done" and item.get("ok") is True for item in post_transitions)


@pytest.mark.asyncio
async def test_ambiguous_alert_uses_sentinel_fallback(test_client):
    payload = {
        "version": "4",
        "groupKey": "phase4-ambiguous",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "UnknownSignal",
                    "service": "payments-api",
                    "severity": "low",
                },
                "annotations": {"summary": "Intermittent issue"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    create = await test_client.post("/webhook/prometheus", json=payload)
    incident_id = create.json()["incident_id"]
    detail = await test_client.get(f"/incidents/{incident_id}")
    body = detail.json()
    assert body["validated_alert"]["enrichment"]["used_llm_fallback"] is True
    assert body["validated_alert"]["is_actionable"] is True


@pytest.mark.asyncio
async def test_thought_signature_handoff_integrity(test_client):
    create = await test_client.post("/webhook/prometheus", json=_config_error_payload())
    incident_id = create.json()["incident_id"]
    detail = await test_client.get(f"/incidents/{incident_id}")
    body = detail.json()

    signature = body["thought_signature"]
    ticket = body["jira_ticket"]
    remediation = body["remediation_result"]

    assert signature["incident_id"] == incident_id
    assert signature["target_file"]
    assert signature["root_cause_category"] in ticket["summary"]
    assert remediation["action_taken"] == signature["recommended_action"]


@pytest.mark.asyncio
async def test_merge_policy_enforced_for_pending_ci(test_client):
    create = await test_client.post("/webhook/prometheus", json=_config_error_payload())
    incident_id = create.json()["incident_id"]
    store = get_session_store()
    state = await store.get(incident_id)
    assert state is not None
    state["ci_status"] = "pending"
    await store.save(incident_id, state)

    approval = await test_client.post(f"/incidents/{incident_id}/approve-merge")
    assert approval.status_code == 409
    assert approval.json()["detail"]["code"] == "ci_not_passed"


@pytest.mark.asyncio
async def test_flapping_backlog_fixture_drives_high_quality_rca(test_client):
    create = await test_client.post("/webhook/prometheus", json=_config_error_payload())
    incident_id = create.json()["incident_id"]

    detail = await test_client.get(f"/incidents/{incident_id}")
    body = detail.json()
    signature = body["thought_signature"]

    assert signature["root_cause_category"] == "config_error"
    assert signature["confidence_score"] >= 0.7
    assert len(signature["evidence_chain"]) >= 4
