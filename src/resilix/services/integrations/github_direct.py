from __future__ import annotations

from base64 import b64encode
from typing import Any

import httpx

from resilix.models.remediation import RecommendedAction, RemediationResult
from resilix.services.integrations.base import MergeGateStatus


class GithubDirectProvider:
    def __init__(
        self,
        *,
        token: str,
        owner: str,
        default_base_branch: str = "main",
        timeout_seconds: float = 20.0,
    ) -> None:
        self._token = token
        self._owner = owner
        self._default_base_branch = default_base_branch
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _repo_name(self, repository: str) -> str:
        if "/" in repository:
            return repository.split("/", 1)[1]
        return repository

    async def _get_default_branch(self, client: httpx.AsyncClient, repo_name: str) -> str:
        endpoint = f"https://api.github.com/repos/{self._owner}/{repo_name}"
        resp = await client.get(endpoint, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("default_branch") or self._default_base_branch)

    async def create_remediation_pr(
        self,
        *,
        incident_id: str,
        repository: str,
        target_file: str,
        action: RecommendedAction,
        summary: str,
    ) -> RemediationResult:
        repo_name = self._repo_name(repository)
        branch_name = f"fix/resilix-{incident_id.lower()}"
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            base_branch = await self._get_default_branch(client, repo_name)

            base_ref_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/git/ref/heads/{base_branch}",
                headers=self._headers(),
            )
            base_ref_resp.raise_for_status()
            base_sha = base_ref_resp.json()["object"]["sha"]

            branch_resp = await client.post(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/git/refs",
                headers=self._headers(),
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )
            if branch_resp.status_code not in (201, 422):
                branch_resp.raise_for_status()

            existing_file_sha = None
            get_file_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/{target_file}",
                headers=self._headers(),
                params={"ref": branch_name},
            )
            if get_file_resp.status_code == 200:
                existing_file_sha = get_file_resp.json().get("sha")
            elif get_file_resp.status_code not in (404,):
                get_file_resp.raise_for_status()

            file_content = (
                f"# Resilix automated remediation\n"
                f"# Incident: {incident_id}\n"
                f"# Action: {action.value}\n"
                f"# Summary: {summary}\n"
            )
            content_b64 = b64encode(file_content.encode("utf-8")).decode("utf-8")
            put_payload: dict[str, Any] = {
                "message": f"fix: {summary[:72]}",
                "content": content_b64,
                "branch": branch_name,
            }
            if existing_file_sha:
                put_payload["sha"] = existing_file_sha

            put_resp = await client.put(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/{target_file}",
                headers=self._headers(),
                json=put_payload,
            )
            put_resp.raise_for_status()

            pr_resp = await client.post(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/pulls",
                headers=self._headers(),
                json={
                    "title": f"[Resilix] {summary[:120]}",
                    "head": branch_name,
                    "base": base_branch,
                    "body": f"Automated remediation for incident `{incident_id}`.",
                },
            )
            if pr_resp.status_code == 422:
                list_resp = await client.get(
                    f"https://api.github.com/repos/{self._owner}/{repo_name}/pulls",
                    headers=self._headers(),
                    params={"head": f"{self._owner}:{branch_name}", "state": "open"},
                )
                list_resp.raise_for_status()
                prs = list_resp.json()
                if not prs:
                    pr_resp.raise_for_status()
                pr_data = prs[0]
            else:
                pr_resp.raise_for_status()
                pr_data = pr_resp.json()

        pr_number = int(pr_data["number"])
        pr_url = str(pr_data["html_url"])
        return RemediationResult(
            success=True,
            action_taken=action,
            branch_name=branch_name,
            pr_number=pr_number,
            pr_url=pr_url,
            pr_merged=False,
            execution_time_seconds=1.0,
        )

    async def get_merge_gate_status(self, *, repository: str, pr_number: int) -> MergeGateStatus:
        repo_name = self._repo_name(repository)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            pr_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/pulls/{pr_number}",
                headers=self._headers(),
            )
            pr_resp.raise_for_status()
            pr_data = pr_resp.json()
            head_sha = pr_data["head"]["sha"]
            mergeable_state = str(pr_data.get("mergeable_state") or "")

            status_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/commits/{head_sha}/status",
                headers=self._headers(),
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()
            ci_state = str(status_data.get("state") or "pending")

            reviews_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/pulls/{pr_number}/reviews",
                headers=self._headers(),
            )
            reviews_resp.raise_for_status()
            reviews = reviews_resp.json()
            has_approved_review = any(str(review.get("state")) == "APPROVED" for review in reviews)

        ci_passed = ci_state == "success"
        codeowner_reviewed = has_approved_review or mergeable_state in {"clean", "has_hooks"}
        return MergeGateStatus(
            ci_passed=ci_passed,
            codeowner_reviewed=codeowner_reviewed,
            details={"ci_state": ci_state, "mergeable_state": mergeable_state},
        )

    async def merge_pr(self, *, repository: str, pr_number: int, method: str) -> bool:
        repo_name = self._repo_name(repository)
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            resp = await client.put(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/pulls/{pr_number}/merge",
                headers=self._headers(),
                json={"merge_method": method},
            )
        if resp.status_code in (200, 201):
            return True
        if resp.status_code in (405, 409, 422):
            return False
        resp.raise_for_status()
        return False
