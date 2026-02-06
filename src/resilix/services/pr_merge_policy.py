from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class MergeDecision:
    eligible: bool
    code: str
    message: str


def _has_pr(remediation: Any) -> bool:
    if remediation is None:
        return False
    if isinstance(remediation, dict):
        return bool(remediation.get("pr_number") or remediation.get("pr_url"))
    return bool(getattr(remediation, "pr_number", None) or getattr(remediation, "pr_url", None))


def _is_merged(remediation: Any) -> bool:
    if remediation is None:
        return False
    if isinstance(remediation, dict):
        return bool(remediation.get("pr_merged", False))
    return bool(getattr(remediation, "pr_merged", False))


def evaluate_approval_request(state: dict[str, Any]) -> MergeDecision:
    remediation = state.get("remediation_result")
    if not _has_pr(remediation):
        return MergeDecision(False, "pr_not_created", "PR not created")
    if _is_merged(remediation):
        return MergeDecision(False, "already_merged", "PR already merged")

    if state.get("ci_status") != "ci_passed":
        return MergeDecision(False, "ci_not_passed", "Merge approval requires CI passed")

    approval = state.get("approval", {})
    required = bool(approval.get("required", False))
    if not required:
        return MergeDecision(False, "approval_not_required", "Approval is not required for this incident")
    if bool(approval.get("approved", False)):
        return MergeDecision(False, "already_approved", "PR already approved")

    return MergeDecision(True, "eligible", "PR can be approved and merged")


def evaluate_merge_eligibility(state: dict[str, Any]) -> MergeDecision:
    remediation = state.get("remediation_result")
    if not _has_pr(remediation):
        return MergeDecision(False, "pr_not_created", "PR not created")
    if _is_merged(remediation):
        return MergeDecision(False, "already_merged", "PR already merged")

    if state.get("ci_status") != "ci_passed":
        return MergeDecision(False, "ci_not_passed", "CI checks are not complete")

    approval = state.get("approval", {})
    required = bool(approval.get("required", False))
    approved = bool(approval.get("approved", False))
    if required and not approved:
        return MergeDecision(False, "approval_pending", "Manual approval is pending")

    return MergeDecision(True, "eligible", "PR merge is allowed")


def apply_approval_and_merge(state: dict[str, Any]) -> None:
    approval = state.setdefault("approval", {})
    approval["approved"] = True
    approval["approved_at"] = datetime.now(timezone.utc).isoformat()

    remediation = state.get("remediation_result")
    if not isinstance(remediation, dict):
        remediation = {
            "success": True,
            "action_taken": "fix_code",
            "execution_time_seconds": 0.0,
        }
        state["remediation_result"] = remediation

    remediation["pr_merged"] = True
    state["resolved_at"] = datetime.now(timezone.utc).isoformat()
