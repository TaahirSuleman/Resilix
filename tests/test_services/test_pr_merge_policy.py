from __future__ import annotations

from resilix.services.pr_merge_policy import (
    apply_approval_and_merge,
    evaluate_approval_request,
    evaluate_merge_eligibility,
)


def _state(
    *,
    ci_status: str = "ci_passed",
    approval_required: bool = True,
    approved: bool = False,
    codeowner_review_status: str = "approved",
):
    return {
        "ci_status": ci_status,
        "codeowner_review_status": codeowner_review_status,
        "policy": {"require_ci_pass": True, "require_codeowner_review": True, "merge_method": "squash"},
        "approval": {"required": approval_required, "approved": approved, "approved_at": None},
        "remediation_result": {
            "success": True,
            "action_taken": "config_change",
            "pr_number": 123,
            "pr_url": "https://example.com/pr/123",
            "pr_merged": False,
            "execution_time_seconds": 1.0,
        },
    }


def test_evaluate_approval_request_blocks_pending_ci() -> None:
    decision = evaluate_approval_request(_state(ci_status="pending"))
    assert decision.eligible is False
    assert decision.code == "ci_not_passed"


def test_evaluate_merge_eligibility_requires_approval_when_configured() -> None:
    decision = evaluate_merge_eligibility(_state(approval_required=True, approved=False))
    assert decision.eligible is False
    assert decision.code == "approval_pending"


def test_evaluate_approval_request_blocks_without_codeowner_review() -> None:
    decision = evaluate_approval_request(_state(codeowner_review_status="pending"))
    assert decision.eligible is False
    assert decision.code == "codeowner_review_required"


def test_apply_approval_and_merge_updates_state() -> None:
    state = _state()
    apply_approval_and_merge(state)
    assert state["approval"]["approved"] is True
    assert state["remediation_result"]["pr_merged"] is True
    assert state["resolved_at"] is not None
