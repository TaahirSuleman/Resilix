from datetime import datetime

from resilix.models.alert import Severity, ValidatedAlert


def test_validated_alert_schema():
    alert = ValidatedAlert(
        alert_id="INC-1234",
        is_actionable=True,
        severity=Severity.CRITICAL,
        service_name="checkout-service",
        error_type="HighErrorRate",
        error_rate=5.2,
        affected_endpoints=["/api/checkout"],
        triggered_at=datetime.utcnow(),
        enrichment={"foo": "bar"},
        triage_reason="Error rate exceeded",
    )

    assert alert.severity == Severity.CRITICAL
    assert alert.is_actionable is True
