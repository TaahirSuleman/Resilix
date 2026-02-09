from __future__ import annotations

from typing import Any

import pytest

import resilix.config.settings as settings_module
from resilix.services.session import get_session_store


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


@pytest.mark.asyncio
async def test_webhook_rejects_when_provider_not_ready(monkeypatch: pytest.MonkeyPatch, test_client):
    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "api")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "api")
    monkeypatch.setattr(
        "resilix.api.webhooks.get_provider_readiness",
        lambda: {
            "jira": {
                "ready": False,
                "resolved_backend": "unavailable",
                "reason": "missing_or_invalid_config",
                "missing_fields": ["JIRA_API_TOKEN"],
            },
            "github": {
                "ready": True,
                "resolved_backend": "github_api",
                "reason": "ok",
                "missing_fields": [],
            },
        },
    )
    monkeypatch.setattr(
        "resilix.api.webhooks.get_adk_runtime_status",
        lambda: {
            "runner_policy": "adk_only",
            "service_revision": "rev-test",
            "service_service": "resilix",
            "adk_mode": "strict",
            "adk_ready": True,
            "adk_last_error": None,
            "adk_session_backend": "in_memory",
            "mock_fallback_allowed": False,
        },
    )

    store = get_session_store()
    before = await store.list_items()

    payload = {
        "status": "firing",
        "alerts": [{"labels": {"alertname": "HighErrorRate", "service": "checkout-api", "severity": "critical"}}],
    }
    response = await test_client.post("/webhook/prometheus", json=payload)
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "provider_not_ready"
    assert body["detail"]["details"]["provider"] == "jira"
    assert body["detail"]["details"]["reason"] == "missing_or_invalid_config"
    assert "JIRA_API_TOKEN" in body["detail"]["details"]["missing_fields"]

    after = await store.list_items()
    assert len(after) == len(before)


@pytest.mark.asyncio
async def test_webhook_simulation_payload_emits_cascade_logs(
    monkeypatch: pytest.MonkeyPatch,
    test_client,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _CaptureLogger:
        def info(self, *args: Any, **kwargs: Any) -> None:
            message = str(args[0]) if args else ""
            calls.append((message, kwargs))

    monkeypatch.setattr("resilix.api.webhooks.logger", _CaptureLogger())
    payload = {
        "status": "firing",
        "simulation": {"source": "resilix-simulator", "scenario": "flapping", "seed": 42},
        "alerts": [
            {
                "labels": {
                    "alertname": "DNSResolverFlapping",
                    "service": "dns-resolver",
                    "severity": "critical",
                }
            }
        ],
        "log_entries": [
            {
                "event": "TargetHealthFlapping",
                "service": "dns-resolver",
                "component": "HealthCheckSubsystem",
                "message": "Targets alternating due to backlog",
                "metadata": {"queue_depth": 230000},
            },
            {
                "event": "DependencyTimeout",
                "service": "checkout-api",
                "component": "DnsClient",
                "message": "DNS dependency timed out",
                "metadata": {"timeout_ms": 1400},
            },
        ],
    }

    response = await test_client.post("/webhook/prometheus", json=payload)
    assert response.status_code == 200
    messages = [message for message, _ in calls]
    assert "Simulation cascade payload received" in messages
    assert "Simulation cascade log" in messages


@pytest.mark.asyncio
async def test_webhook_non_simulation_payload_skips_cascade_logs(
    monkeypatch: pytest.MonkeyPatch,
    test_client,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class _CaptureLogger:
        def info(self, *args: Any, **kwargs: Any) -> None:
            message = str(args[0]) if args else ""
            calls.append((message, kwargs))

    monkeypatch.setattr("resilix.api.webhooks.logger", _CaptureLogger())
    payload = {
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
        "log_entries": [
            {
                "event": "TargetHealthFlapping",
                "service": "dns-resolver",
                "component": "HealthCheckSubsystem",
                "message": "Targets alternating due to backlog",
                "metadata": {"queue_depth": 230000},
            }
        ],
    }

    response = await test_client.post("/webhook/prometheus", json=payload)
    assert response.status_code == 200
    messages = [message for message, _ in calls]
    assert "Simulation cascade payload received" not in messages
    assert "Simulation cascade log" not in messages


@pytest.mark.asyncio
async def test_webhook_infra_target_forces_config_action(test_client) -> None:
    payload = {
        "status": "firing",
        "repository": "acme/resilix-demo-config",
        "target_file": "infra/dns/coredns-config.yaml",
        "alerts": [
            {
                "labels": {
                    "alertname": "HighErrorRate",
                    "service": "dns-resolver",
                    "severity": "critical",
                }
            }
        ],
    }

    response = await test_client.post("/webhook/prometheus", json=payload)
    assert response.status_code == 200
    incident_id = response.json()["incident_id"]

    detail = await test_client.get(f"/incidents/{incident_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["thought_signature"]["root_cause_category"] == "config_error"
    assert body["remediation_result"]["action_taken"] == "config_change"
