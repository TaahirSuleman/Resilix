from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalScores(BaseModel):
    """Known signal counters used by deterministic Sentinel scoring."""

    error_rate_high: int = 0
    health_flapping: int = 0
    backlog_growth: int = 0
    dependency_timeout: int = 0


class AlertEnrichment(BaseModel):
    """Structured enrichment payload compatible with Gemini response schema constraints."""

    signal_scores: SignalScores = Field(default_factory=SignalScores)
    weighted_score: float = 0.0
    used_llm_fallback: bool = False
    deterministic_confidence: float = Field(ge=0, le=1, default=0.0)


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
    enrichment: AlertEnrichment = Field(default_factory=AlertEnrichment)
    triage_reason: str = Field(description="Why this decision was made")
