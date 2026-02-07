from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TimelineEventType(str, Enum):
    INCIDENT_CREATED = "incident_created"
    ALERT_VALIDATED = "alert_validated"
    INVESTIGATION_STARTED = "investigation_started"
    EVIDENCE_COLLECTED = "evidence_collected"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    TICKET_CREATED = "ticket_created"
    TICKET_MOVED_TODO = "ticket_moved_todo"
    TICKET_MOVED_IN_PROGRESS = "ticket_moved_in_progress"
    TICKET_MOVED_IN_REVIEW = "ticket_moved_in_review"
    TICKET_MOVED_DONE = "ticket_moved_done"
    TICKET_TRANSITION_FAILED = "ticket_transition_failed"
    FIX_GENERATED = "fix_generated"
    PR_CREATED = "pr_created"
    PR_MERGED = "pr_merged"
    INCIDENT_RESOLVED = "incident_resolved"
    ESCALATED_TO_HUMAN = "escalated_to_human"


class TimelineEvent(BaseModel):
    event_type: TimelineEventType
    timestamp: datetime
    agent: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None
