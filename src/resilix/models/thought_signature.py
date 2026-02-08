from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class RootCauseCategory(str, Enum):
    CODE_BUG = "code_bug"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


from .remediation import RecommendedAction


class Evidence(BaseModel):
    source: str = Field(description="logs|traces|metrics|deployment")
    timestamp: datetime
    content: str = Field(description="The actual evidence")
    relevance: str = Field(description="How this relates to root cause")


class ThoughtSignature(BaseModel):
    incident_id: str
    root_cause: str = Field(description="Clear statement of the root cause")
    root_cause_category: RootCauseCategory
    evidence_chain: List[Evidence] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1, description="Confidence in RCA")

    recommended_action: RecommendedAction
    target_repository: Optional[str] = None
    target_file: Optional[str] = None
    target_line: Optional[int] = None
    related_commits: List[str] = Field(default_factory=list)

    investigation_summary: str
    investigation_duration_seconds: float


class ThoughtSignaturePayload(BaseModel):
    """ADK-friendly output schema with primitive/list types only."""

    incident_id: str
    root_cause: str
    root_cause_category: str
    evidence_chain: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1)
    recommended_action: str
    target_repository: Optional[str] = None
    target_file: Optional[str] = None
    target_line: Optional[int] = None
    related_commits: List[str] = Field(default_factory=list)
    investigation_summary: str
    investigation_duration_seconds: float
