from __future__ import annotations

from resilix.services.sentinel_service import evaluate_alert


def test_signal_weighting_marks_alert_critical_and_actionable() -> None:
    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {"alertname": "ServiceHealthFlapping", "service": "edge-router"},
                "annotations": {"summary": "Error rate spike with flapping state"},
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

    validated, trace = evaluate_alert(payload, "INC-SENT-001")

    assert validated.is_actionable is True
    assert validated.severity.value == "critical"
    assert trace["signal_scores"]["health_flapping"] >= 1
    assert trace["signal_scores"]["backlog_growth"] >= 1
    assert trace["used_llm_fallback"] is False


def test_ambiguous_alert_triggers_fallback() -> None:
    payload = {
        "status": "firing",
        "alerts": [
            {
                "labels": {"alertname": "UnknownAnomaly", "service": "payments-api", "severity": "low"},
                "annotations": {"summary": "Intermittent issue"},
                "startsAt": "2026-02-05T12:38:23Z",
            }
        ],
    }
    called = {"count": 0}

    def _fallback(_context: dict[str, object]) -> dict[str, object]:
        called["count"] += 1
        return {
            "severity": "high",
            "is_actionable": True,
            "triage_reason": "Fallback model confirmed escalation.",
            "confidence_score": 0.7,
        }

    validated, trace = evaluate_alert(payload, "INC-SENT-002", llm_fallback=_fallback)

    assert called["count"] == 1
    assert trace["used_llm_fallback"] is True
    assert validated.severity.value == "high"
    assert "Fallback model" in validated.triage_reason
