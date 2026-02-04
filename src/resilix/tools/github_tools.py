from __future__ import annotations

from typing import Dict

try:
    from google.adk.tools import tool
except Exception:  # pragma: no cover
    def tool(fn):
        return fn


@tool
def github_create_pr(repo: str, branch: str, title: str, body: str) -> Dict[str, str | int]:
    """Create a GitHub PR (mocked)."""
    return {
        "pr_number": 456,
        "pr_url": f"https://github.com/{repo}/pull/456",
        "branch": branch,
        "title": title,
        "body": body,
    }


@tool
def github_merge_pr(repo: str, pr_number: int) -> Dict[str, bool]:
    """Merge a GitHub PR (mocked)."""
    try:
        from resilix.config import get_settings

        settings = get_settings()
        if settings.require_pr_approval:
            return {"merged": False}
    except Exception:  # pragma: no cover
        pass
    return {"merged": True}
