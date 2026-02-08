from datetime import UTC, datetime

from resilix.models.alert import AlertEnrichment, Severity, SignalScores, ValidatedAlert


def test_validated_alert_schema():
    alert = ValidatedAlert(
        alert_id="INC-1234",
        is_actionable=True,
        severity=Severity.CRITICAL,
        service_name="checkout-service",
        error_type="HighErrorRate",
        error_rate=5.2,
        affected_endpoints=["/api/checkout"],
        triggered_at=datetime.now(UTC),
        enrichment=AlertEnrichment(
            signal_scores=SignalScores(error_rate_high=1, health_flapping=2),
            weighted_score=5.0,
            used_llm_fallback=False,
            deterministic_confidence=0.8,
        ),
        triage_reason="Error rate exceeded",
    )

    assert alert.severity == Severity.CRITICAL
    assert alert.is_actionable is True
