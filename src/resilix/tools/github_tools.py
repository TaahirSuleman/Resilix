from __future__ import annotations

from typing import Any, Dict

import httpx

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
def github_list_repositories(owner: str = "") -> Dict[str, Any]:
    """List repositories for a GitHub owner.

    This tool is intentionally lightweight and safe for LLM discovery/planning.
    It returns a bounded set of repository names and basic metadata.
    """
    try:
        from resilix.config import get_settings

        settings = get_settings()
        token = (settings.github_token or "").strip()
        resolved_owner = (owner or settings.github_owner or "").strip()
        if not token or not resolved_owner:
            return {"owner": resolved_owner, "count": 0, "repositories": [], "error": "github_not_configured"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://api.github.com/users/{resolved_owner}/repos",
                headers=headers,
                params={"per_page": 25, "sort": "updated"},
            )
        if response.status_code >= 400:
            return {
                "owner": resolved_owner,
                "count": 0,
                "repositories": [],
                "error": f"github_http_{response.status_code}",
            }
        payload = response.json()
        repos = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                if not name:
                    continue
                repos.append(
                    {
                        "name": str(name),
                        "full_name": str(item.get("full_name") or ""),
                        "default_branch": str(item.get("default_branch") or ""),
                        "private": bool(item.get("private", False)),
                    }
                )
        return {"owner": resolved_owner, "count": len(repos), "repositories": repos, "error": None}
    except Exception as exc:  # pragma: no cover
        return {"owner": owner, "count": 0, "repositories": [], "error": str(exc)}


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


@tool
def list_commits(repository: str, limit: int = 5) -> Dict[str, Any]:
    """List recent commits for a repository.

    This is a safe compatibility tool for LLM planning in Sherlock.
    It should never raise and returns an empty list if GitHub is unavailable.
    """
    try:
        from resilix.config import get_settings

        settings = get_settings()
        token = (settings.github_token or "").strip()
        repo_text = (repository or "").strip()
        if not repo_text:
            return {"repository": repository, "count": 0, "commits": [], "error": "missing_repository"}

        if "/" in repo_text:
            owner, repo = repo_text.split("/", 1)
        else:
            owner = (settings.github_owner or "").strip()
            repo = repo_text

        if not token or not owner or not repo:
            return {"repository": f"{owner}/{repo}".strip("/"), "count": 0, "commits": [], "error": "github_not_configured"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"per_page": max(1, min(int(limit), 20))},
            )

        if response.status_code >= 400:
            return {
                "repository": f"{owner}/{repo}",
                "count": 0,
                "commits": [],
                "error": f"github_http_{response.status_code}",
            }

        payload = response.json()
        commits: list[dict[str, str]] = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                sha = str(item.get("sha") or "")
                message = str((item.get("commit") or {}).get("message") or "")
                html_url = str(item.get("html_url") or "")
                if not sha:
                    continue
                commits.append(
                    {
                        "sha": sha,
                        "message": message,
                        "url": html_url,
                    }
                )
        return {"repository": f"{owner}/{repo}", "count": len(commits), "commits": commits, "error": None}
    except Exception as exc:  # pragma: no cover
        return {"repository": repository, "count": 0, "commits": [], "error": str(exc)}
