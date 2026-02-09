from __future__ import annotations

from datetime import datetime, timezone

import pytest

from resilix.models.remediation import JiraTicketResult, RemediationResult, RecommendedAction
from resilix.config.settings import get_settings
from resilix.services.integrations.base import MergeGateStatus
from resilix.services.integrations.mock_providers import MockCodeProvider, MockTicketProvider
from resilix.services.orchestrator import apply_direct_integrations


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeTicketProvider:
    def __init__(self) -> None:
        self.created = []
        self.transitions = []

    async def create_incident_ticket(
        self,
        *,
        incident_id: str,
        summary: str,
        description: str,
        priority: str,
    ) -> JiraTicketResult:
        self.created.append(
            {
                "incident_id": incident_id,
                "summary": summary,
                "description": description,
                "priority": priority,
            }
        )
        return JiraTicketResult(
            ticket_key="SRE-00001",
            ticket_url="https://example.atlassian.net/browse/SRE-00001",
            summary=summary,
            priority=priority,
            status="Open",
            created_at=datetime.now(timezone.utc),
        )

    async def transition_ticket(self, *, ticket_key: str, target_status: str) -> dict[str, object]:
        result = {
            "ok": True,
            "from_status": None,
            "to_status": target_status,
            "applied_transition_id": "test-transition",
            "reason": None,
        }
        self.transitions.append(result)
        return result


class FakeCodeProvider:
    def __init__(self) -> None:
        self.created = []

    async def create_remediation_pr(
        self,
        *,
        incident_id: str,
        repository: str,
        target_file: str,
        action: RecommendedAction,
        summary: str,
        remediation_context: dict[str, object] | None = None,
    ) -> RemediationResult:
        self.created.append(
            {
                "incident_id": incident_id,
                "repository": repository,
                "target_file": target_file,
                "action": action,
                "summary": summary,
                "remediation_context": remediation_context,
            }
        )
        return RemediationResult(
            success=True,
            action_taken=action,
            branch_name=f"fix/{incident_id.lower()}",
            pr_number=123,
            pr_url=f"https://github.com/{repository}/pull/123",
            pr_merged=False,
            execution_time_seconds=0.5,
        )

    async def get_merge_gate_status(self, *, repository: str, pr_number: int) -> MergeGateStatus:
        return MergeGateStatus(
            ci_passed=True,
            codeowner_reviewed=True,
            details={"repository": repository, "pr_number": pr_number},
        )


@pytest.mark.asyncio
async def test_apply_direct_integrations_overrides_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket_provider = FakeTicketProvider()
    code_provider = FakeCodeProvider()

    monkeypatch.setattr(
        "resilix.services.orchestrator.get_ticket_provider",
        lambda: (ticket_provider, "jira_api"),
    )
    monkeypatch.setattr(
        "resilix.services.orchestrator.get_code_provider",
        lambda: (code_provider, "github_api"),
    )
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "api")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "api")

    payload = {
        "version": "4",
        "groupKey": "dns-config-error",
        "status": "firing",
        "receiver": "resilix",
        "repository": "acme/resilix-demo-config",
        "target_file": "infra/dns/coredns-config.yaml",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "DNSResolverFlapping",
                    "service": "dns-resolver",
                    "severity": "critical",
                },
                "annotations": {"summary": "DNS flapping"},
                "startsAt": "2026-02-05T10:30:00Z",
            }
        ],
        "log_entries": [
            {
                "timestamp": "2026-02-05T10:30:01Z",
                "level": "ERROR",
                "service": "dns-resolver",
                "component": "HealthCheckSubsystem",
                "event": "TargetHealthFlapping",
                "message": "Targets alternating between healthy and unhealthy due to backlog",
                "metadata": {"queue_depth": 230061, "unhealthy_targets_count": 480},
            }
        ],
    }

    state: dict[str, object] = {}
    result_state = await apply_direct_integrations(
        state=state,
        raw_alert=payload,
        incident_id="INC-TEST001",
    )

    signature = result_state["thought_signature"]
    assert signature["target_repository"] == "acme/resilix-demo-config"
    assert signature["target_file"] == "infra/dns/coredns-config.yaml"
    created = code_provider.created[0]
    context = created["remediation_context"]
    assert isinstance(context, dict)
    assert context["incident_id"] == "INC-TEST001"
    assert context["service_name"] == "dns-resolver"
    assert context["target_file"] == "infra/dns/coredns-config.yaml"
    assert context["root_cause_category"] in {"config_error", "code_bug", "dependency_failure", "resource_exhaustion"}
    assert context["recommended_action"] in {"config_change", "fix_code", "rollback", "scale_up"}

    assert result_state["jira_ticket"]["ticket_key"] == "SRE-00001"
    assert result_state["remediation_result"]["pr_number"] == 123
    assert result_state["ci_status"] == "ci_passed"
    assert result_state["codeowner_review_status"] == "approved"

    timeline_types = [event["event_type"] for event in result_state.get("timeline", [])]
    assert "ticket_created" in timeline_types
    assert "ticket_moved_todo" in timeline_types
    assert "ticket_moved_in_progress" in timeline_types
    assert "ticket_moved_in_review" in timeline_types
    assert "pr_created" in timeline_types
    in_progress_index = timeline_types.index("ticket_moved_in_progress")
    pr_created_index = timeline_types.index("pr_created")
    in_review_index = timeline_types.index("ticket_moved_in_review")
    assert in_progress_index < pr_created_index
    assert pr_created_index < in_review_index

    trace = result_state.get("integration_trace")
    assert trace is not None
    assert trace.get("post_processor") == "direct_integrations"
    guardrail = trace.get("action_guardrail")
    assert isinstance(guardrail, dict)
    assert guardrail.get("target_file") == "infra/dns/coredns-config.yaml"
    assert guardrail.get("root_cause_category") == "config_error"
    assert guardrail.get("recommended_action") == "config_change"


@pytest.mark.asyncio
async def test_apply_direct_integrations_does_not_noop_with_mock_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "resilix.services.orchestrator.get_ticket_provider",
        lambda: (MockTicketProvider(), "jira_mock"),
    )
    monkeypatch.setattr(
        "resilix.services.orchestrator.get_code_provider",
        lambda: (MockCodeProvider(), "github_mock"),
    )
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "HighErrorRate",
                    "service": "checkout-api",
                    "severity": "critical",
                },
                "annotations": {"summary": "Checkout API error rate spike"},
                "startsAt": "2026-02-08T12:00:00Z",
            }
        ],
    }
    result_state = await apply_direct_integrations(state={}, raw_alert=payload, incident_id="INC-MOCK-001")

    assert result_state.get("validated_alert") is not None
    assert result_state.get("thought_signature") is not None
    assert result_state.get("jira_ticket") is not None
    assert result_state.get("remediation_result") is not None
    assert result_state.get("ci_status") == "ci_passed"
    assert result_state.get("codeowner_review_status") == "approved"
    trace = result_state.get("integration_trace") or {}
    assert trace.get("ticket_provider") == "jira_mock"
    assert trace.get("code_provider") == "github_mock"
    assert trace.get("fallback_used") is True


@pytest.mark.asyncio
async def test_apply_direct_integrations_raises_when_api_mode_resolves_mock_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "resilix.services.orchestrator.get_ticket_provider",
        lambda: (MockTicketProvider(), "jira_mock"),
    )
    monkeypatch.setattr(
        "resilix.services.orchestrator.get_code_provider",
        lambda: (MockCodeProvider(), "github_mock"),
    )
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "api")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "api")

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "HighErrorRate",
                    "service": "checkout-api",
                    "severity": "critical",
                },
                "annotations": {"summary": "Checkout API error rate spike"},
                "startsAt": "2026-02-08T12:00:00Z",
            }
        ],
    }
    with pytest.raises(RuntimeError, match="jira_api_requested_but_mock_provider_resolved"):
        await apply_direct_integrations(state={}, raw_alert=payload, incident_id="INC-MOCK-STRICT-001")
