from __future__ import annotations

import pytest

from resilix.services.orchestrator import MockRunner


@pytest.mark.asyncio
async def test_mechanic_receives_signature_and_produces_strategy_aligned_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    import resilix.config.settings as settings_module

    monkeypatch.setenv("USE_MOCK_PROVIDERS", "true")
    monkeypatch.setenv("JIRA_INTEGRATION_MODE", "mock")
    monkeypatch.setenv("GITHUB_INTEGRATION_MODE", "mock")
    settings_module.get_settings.cache_clear()

    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "DependencyTimeout",
                    "service": "checkout-gateway",
                    "severity": "high",
                },
                "annotations": {"summary": "Upstream calls are timing out"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    state = await MockRunner().run(payload, "INC-HANDOFF-002")

    signature = state["thought_signature"]
    remediation = state["remediation_result"]
    mechanic_trace = state["agent_trace"]["mechanic"]

    assert remediation["pr_number"] is not None
    assert remediation["pr_url"] is not None
    assert remediation["action_taken"] == signature.recommended_action.value
    assert mechanic_trace["strategy"] == signature.root_cause_category.value
