from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RecommendedAction(str, Enum):
    FIX_CODE = "fix_code"
    ROLLBACK = "rollback"
    SCALE_UP = "scale_up"
    CONFIG_CHANGE = "config_change"


class JiraTicketResult(BaseModel):
    ticket_key: str
    ticket_url: str
    summary: str
    priority: str
    status: str
    created_at: datetime


class RemediationResult(BaseModel):
    success: bool
    action_taken: RecommendedAction

    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_merged: bool = False
    target_file: Optional[str] = None
    diff_old_line: Optional[str] = None
    diff_new_line: Optional[str] = None

    execution_time_seconds: float
    error_message: Optional[str] = None


class JiraTicketPayload(BaseModel):
    """ADK-friendly primitive-only payload for Administrator output."""

    ticket_key: str
    ticket_url: str
    summary: str
    priority: str
    status: str
    created_at: str


class RemediationResultPayload(BaseModel):
    """ADK-friendly primitive-only payload for Mechanic output."""

    success: bool
    action_taken: str
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_merged: bool = False
    target_file: Optional[str] = None
    diff_old_line: Optional[str] = None
    diff_new_line: Optional[str] = None
    execution_time_seconds: float
    error_message: Optional[str] = None
