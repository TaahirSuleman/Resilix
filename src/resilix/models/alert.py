from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidatedAlert(BaseModel):
    """Validated and enriched alert from Sentinel."""

    alert_id: str = Field(description="Unique alert identifier")
    is_actionable: bool = Field(description="Should trigger investigation")
    severity: Severity = Field(description="Alert severity")
    service_name: str = Field(description="Affected service name")
    error_type: str = Field(description="Type of error detected")
    error_rate: float = Field(description="Current error rate percentage")
    affected_endpoints: List[str] = Field(default_factory=list)
    triggered_at: datetime = Field(description="When alert was triggered")
    enrichment: dict[str, Any] = Field(default_factory=dict)
    triage_reason: str = Field(description="Why this decision was made")
