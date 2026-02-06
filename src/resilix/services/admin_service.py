from __future__ import annotations

import zlib
from datetime import datetime, timezone

from resilix.models.alert import Severity
from resilix.models.remediation import JiraTicketResult
from resilix.models.thought_signature import ThoughtSignature

PRIORITY_BY_SEVERITY = {
    Severity.CRITICAL: "P1",
    Severity.HIGH: "P2",
    Severity.MEDIUM: "P3",
    Severity.LOW: "P4",
}


def build_ticket_from_signature(
    incident_id: str,
    signature: ThoughtSignature,
    severity: Severity,
    service_name: str,
) -> JiraTicketResult:
    ticket_number = zlib.crc32(f"{incident_id}:{service_name}".encode("utf-8")) % 100000
    ticket_key = f"SRE-{ticket_number:05d}"
    summary = f"[AUTO] {signature.root_cause_category.value}: {signature.root_cause}"
    now = datetime.now(timezone.utc)
    return JiraTicketResult(
        ticket_key=ticket_key,
        ticket_url=f"https://example.atlassian.net/browse/{ticket_key}",
        summary=summary,
        priority=PRIORITY_BY_SEVERITY[severity],
        status="Open",
        created_at=now,
    )
