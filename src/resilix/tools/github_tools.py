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


@tool
def get_file_contents(repository: str, path: str, ref: str = "") -> Dict[str, Any]:
    """Fetch file contents from a repository.

    Returns text content when available. Never raises.
    """
    try:
        from base64 import b64decode
        from resilix.config import get_settings

        settings = get_settings()
        token = (settings.github_token or "").strip()
        repo_text = (repository or "").strip()
        file_path = (path or "").strip().lstrip("/")
        if not repo_text or not file_path:
            return {
                "repository": repository,
                "path": path,
                "ref": ref,
                "content": None,
                "sha": None,
                "error": "missing_repository_or_path",
            }
        if "/" in repo_text:
            owner, repo = repo_text.split("/", 1)
        else:
            owner = (settings.github_owner or "").strip()
            repo = repo_text
        if not token or not owner or not repo:
            return {
                "repository": f"{owner}/{repo}".strip("/"),
                "path": file_path,
                "ref": ref,
                "content": None,
                "sha": None,
                "error": "github_not_configured",
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        params: Dict[str, Any] = {}
        if ref.strip():
            params["ref"] = ref.strip()
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
                headers=headers,
                params=params or None,
            )
        if response.status_code == 404:
            if file_path.startswith("infra/dns/") and not file_path.endswith("coredns-config.yaml"):
                fallback_path = "infra/dns/coredns-config.yaml"
                with httpx.Client(timeout=10.0) as client:
                    fallback_response = client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/contents/{fallback_path}",
                        headers=headers,
                        params=params or None,
                    )
                if fallback_response.status_code == 200:
                    fallback_payload = fallback_response.json()
                    fallback_encoded = str(fallback_payload.get("content") or "")
                    fallback_content = ""
                    if str(fallback_payload.get("encoding") or "") == "base64" and fallback_encoded:
                        fallback_content = b64decode(fallback_encoded).decode("utf-8", errors="replace")
                    return {
                        "repository": f"{owner}/{repo}",
                        "path": file_path,
                        "resolved_path": fallback_path,
                        "ref": ref,
                        "content": fallback_content,
                        "sha": fallback_payload.get("sha"),
                        "error": None,
                    }
            return {
                "repository": f"{owner}/{repo}",
                "path": file_path,
                "ref": ref,
                "content": None,
                "sha": None,
                "error": "not_found",
            }
        if response.status_code >= 400:
            return {
                "repository": f"{owner}/{repo}",
                "path": file_path,
                "ref": ref,
                "content": None,
                "sha": None,
                "error": f"github_http_{response.status_code}",
            }
        payload = response.json()
        encoded = str(payload.get("content") or "")
        encoding = str(payload.get("encoding") or "")
        content = ""
        if encoding == "base64" and encoded:
            content = b64decode(encoded).decode("utf-8", errors="replace")
        return {
            "repository": f"{owner}/{repo}",
            "path": file_path,
            "ref": ref,
            "content": content,
            "sha": payload.get("sha"),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "repository": repository,
            "path": path,
            "ref": ref,
            "content": None,
            "sha": None,
            "error": str(exc),
        }


@tool
def search_code(repository: str, query: str, path_prefix: str = "") -> Dict[str, Any]:
    """Search code in a repository.

    Returns bounded matching items and never raises.
    """
    try:
        from resilix.config import get_settings

        settings = get_settings()
        token = (settings.github_token or "").strip()
        repo_text = (repository or "").strip()
        query_text = (query or "").strip()
        if not repo_text or not query_text:
            return {
                "repository": repository,
                "query": query,
                "path_prefix": path_prefix,
                "count": 0,
                "items": [],
                "error": "missing_repository_or_query",
            }

        if "/" in repo_text:
            owner, repo = repo_text.split("/", 1)
        else:
            owner = (settings.github_owner or "").strip()
            repo = repo_text
        if not token or not owner or not repo:
            return {
                "repository": f"{owner}/{repo}".strip("/"),
                "query": query_text,
                "path_prefix": path_prefix,
                "count": 0,
                "items": [],
                "error": "github_not_configured",
            }

        scoped_query = f"{query_text} repo:{owner}/{repo}"
        prefix = path_prefix.strip().strip("/")
        if prefix:
            scoped_query = f"{scoped_query} path:{prefix}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                "https://api.github.com/search/code",
                headers=headers,
                params={"q": scoped_query, "per_page": 10},
            )
        if response.status_code >= 400:
            return {
                "repository": f"{owner}/{repo}",
                "query": query_text,
                "path_prefix": path_prefix,
                "count": 0,
                "items": [],
                "error": f"github_http_{response.status_code}",
            }

        payload = response.json()
        raw_items = payload.get("items")
        items: list[dict[str, str]] = []
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                items.append(
                    {
                        "name": str(item.get("name") or ""),
                        "path": str(item.get("path") or ""),
                        "sha": str(item.get("sha") or ""),
                        "url": str(item.get("html_url") or ""),
                    }
                )

        return {
            "repository": f"{owner}/{repo}",
            "query": query_text,
            "path_prefix": path_prefix,
            "count": len(items),
            "items": items,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "repository": repository,
            "query": query,
            "path_prefix": path_prefix,
            "count": 0,
            "items": [],
            "error": str(exc),
        }
