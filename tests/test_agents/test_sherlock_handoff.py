from __future__ import annotations

import pytest

from resilix.services.orchestrator import MockRunner


@pytest.mark.asyncio
async def test_sherlock_thought_signature_handoff_contains_required_fields() -> None:
    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {
                    "alertname": "ServiceHealthFlapping",
                    "service": "edge-router",
                    "severity": "critical",
                },
                "annotations": {"summary": "Unstable target health"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
        "log_entries": [
            {
                "timestamp": "2026-02-05T12:38:23Z",
                "event": "TargetHealthFlapping",
                "message": "Targets alternating between healthy and unhealthy",
                "metadata": {"queue_depth": 230061},
            }
        ],
    }
    state = await MockRunner().run(payload, "INC-HANDOFF-001")
    signature = state["thought_signature"]

    assert signature.incident_id == "INC-HANDOFF-001"
    assert signature.root_cause_category.value == "config_error"
    assert signature.target_file is not None
    assert len(signature.evidence_chain) >= 1
