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

    execution_time_seconds: float
    error_message: Optional[str] = None
