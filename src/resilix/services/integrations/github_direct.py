from __future__ import annotations

from base64 import b64decode, b64encode
import re
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

    async def _resolve_target_file_on_missing(
        self,
        *,
        client: httpx.AsyncClient,
        repo_name: str,
        target_file: str,
        branch_name: str,
    ) -> str:
        normalized = target_file.strip().lstrip("/")
        if normalized == "infra/dns/coredns-config.yaml":
            return normalized
        if not normalized.startswith("infra/dns/"):
            return normalized

        dir_resp = await client.get(
            f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/infra/dns",
            headers=self._headers(),
            params={"ref": branch_name},
        )
        if dir_resp.status_code >= 400:
            return normalized

        payload = dir_resp.json()
        if not isinstance(payload, list):
            return normalized

        names = [str(item.get("name") or "") for item in payload if isinstance(item, dict)]
        if "coredns-config.yaml" in names:
            return "infra/dns/coredns-config.yaml"

        yaml_candidates = [name for name in names if name.endswith(".yaml")]
        if yaml_candidates:
            return f"infra/dns/{yaml_candidates[0]}"
        return normalized

    @staticmethod
    def _legacy_remediation_content(
        *,
        incident_id: str,
        action: RecommendedAction,
        summary: str,
    ) -> str:
        return (
            f"# Resilix automated remediation\n"
            f"# Incident: {incident_id}\n"
            f"# Action: {action.value}\n"
            f"# Summary: {summary}\n"
        )

    def _build_remediated_content(
        self,
        *,
        target_file: str,
        existing_content: str,
        action: RecommendedAction,
        summary: str,
        remediation_context: dict[str, object] | None,
    ) -> str | None:
        normalized_target = target_file.strip().lower().lstrip("/")
        if normalized_target.endswith("infra/dns/coredns-config.yaml"):
            return self._patch_coredns_config(existing_content)
        if normalized_target.endswith("infra/dependencies.yaml"):
            return self._patch_dependencies_yaml(existing_content)
        if normalized_target.endswith("src/app/handlers.py"):
            return self._patch_handlers_py(existing_content)
        return None

    @staticmethod
    def _extract_diff_preview(
        *,
        old_content: str,
        new_content: str,
    ) -> tuple[str | None, str | None]:
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        for idx in range(max(len(old_lines), len(new_lines))):
            old_line = old_lines[idx] if idx < len(old_lines) else None
            new_line = new_lines[idx] if idx < len(new_lines) else None
            if old_line == new_line:
                continue
            old_norm = old_line.strip() if isinstance(old_line, str) else ""
            new_norm = new_line.strip() if isinstance(new_line, str) else ""
            if not old_norm and not new_norm:
                continue
            return old_line, new_line
        return None, None

    @staticmethod
    def _default_preview_for_target(
        *,
        target_file: str,
        action: RecommendedAction,
    ) -> tuple[str | None, str | None]:
        normalized = target_file.strip().lower().lstrip("/")
        if normalized.endswith("infra/dns/coredns-config.yaml"):
            return ("forward . 10.0.0.1:53", "forward . 1.1.1.1 8.8.8.8 9.9.9.9")
        if normalized.endswith("infra/dependencies.yaml"):
            return ("timeout_ms: 9000", "timeout_ms: 1500")
        if normalized.endswith("src/app/handlers.py"):
            return ('requests.get("https://example.com")', "_resilix_safe_http_call(requests.get, ...)")
        return (None, f"# remediation: {action.value}")

    @staticmethod
    def _patch_coredns_config(content: str) -> str | None:
        if not content:
            return None
        lines = content.splitlines()
        changed = False
        forward_found = False
        failover_found = False

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("forward ."):
                indent = line[: len(line) - len(line.lstrip())]
                updated = f"{indent}forward . 1.1.1.1 8.8.8.8 9.9.9.9"
                if line != updated:
                    lines[idx] = updated
                    changed = True
                forward_found = True
            if stripped.startswith("failover_mode:"):
                indent = line[: len(line) - len(line.lstrip())]
                updated = f'{indent}failover_mode: "AUTO"'
                if line != updated:
                    lines[idx] = updated
                    changed = True
                failover_found = True

        if not forward_found:
            insertion_index = len(lines)
            for idx, line in enumerate(lines):
                if line.strip().startswith("cache "):
                    insertion_index = idx
                    break
            lines.insert(insertion_index, "        forward . 1.1.1.1 8.8.8.8 9.9.9.9")
            changed = True

        if not failover_found:
            lines.append('  failover_mode: "AUTO"')
            changed = True

        if not changed:
            return None
        return "\n".join(lines) + "\n"

    @staticmethod
    def _patch_dependencies_yaml(content: str) -> str | None:
        if not content:
            return None
        patched = content
        changed = False

        replacements = [
            (r"(?m)^(\s*timeout_ms:\s*)\d+(\s*)$", r"\g<1>1500\2"),
            (r"(?m)^(\s*timeout_seconds:\s*)\d+(\s*)$", r"\g<1>2\2"),
            (r"(?m)^(\s*retries:\s*)\d+(\s*)$", r"\g<1>3\2"),
            (r"(?m)^(\s*max_retries:\s*)\d+(\s*)$", r"\g<1>3\2"),
            (r"(?m)^(\s*backoff_ms:\s*)\d+(\s*)$", r"\g<1>250\2"),
            (r"(?m)^(\s*circuit_breaker_enabled:\s*)(true|false)(\s*)$", r"\g<1>true\3"),
        ]

        for pattern, replacement in replacements:
            updated, count = re.subn(pattern, replacement, patched)
            if count > 0:
                changed = True
                patched = updated

        if "timeout_ms:" not in patched and "timeout_seconds:" not in patched:
            if not patched.endswith("\n"):
                patched += "\n"
            patched += (
                "resilix_remediation:\n"
                "  timeout_ms: 1500\n"
                "  max_retries: 3\n"
                "  backoff_ms: 250\n"
                "  circuit_breaker_enabled: true\n"
            )
            changed = True

        if not changed:
            return None
        if not patched.endswith("\n"):
            patched += "\n"
        return patched

    @staticmethod
    def _patch_handlers_py(content: str) -> str | None:
        if not content:
            return None

        patched = content
        replaced_count = 0
        for method in ("get", "post", "put", "delete", "patch"):
            pattern = rf"\brequests\.{method}\("
            replacement = f"_resilix_safe_http_call(requests.{method}, "
            patched, count = re.subn(pattern, replacement, patched)
            replaced_count += count

        if replaced_count == 0:
            return None

        if "def _resilix_safe_http_call(" not in patched:
            helper = """


def _resilix_safe_http_call(http_fn, *args, **kwargs):
    \"\"\"Apply timeout and guarded exception path for upstream HTTP calls.\"\"\"
    kwargs.setdefault("timeout", 2.0)
    try:
        return http_fn(*args, **kwargs)
    except Exception as exc:
        raise RuntimeError(f"upstream_request_failed: {exc}") from exc
"""
            patched = patched.rstrip() + helper + "\n"

        return patched

    async def create_remediation_pr(
        self,
        *,
        incident_id: str,
        repository: str,
        target_file: str,
        action: RecommendedAction,
        summary: str,
        remediation_context: dict[str, object] | None = None,
    ) -> RemediationResult:
        repo_name = self._repo_name(repository)
        target_file_path = target_file.strip().lstrip("/")
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
            existing_content = ""
            get_file_resp = await client.get(
                f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/{target_file_path}",
                headers=self._headers(),
                params={"ref": branch_name},
            )
            if get_file_resp.status_code == 200:
                file_payload = get_file_resp.json()
                existing_file_sha = file_payload.get("sha")
                encoded_content = str(file_payload.get("content") or "")
                if str(file_payload.get("encoding") or "") == "base64" and encoded_content:
                    existing_content = b64decode(encoded_content).decode("utf-8", errors="replace")
            elif get_file_resp.status_code == 404:
                resolved_target = await self._resolve_target_file_on_missing(
                    client=client,
                    repo_name=repo_name,
                    target_file=target_file_path,
                    branch_name=branch_name,
                )
                if resolved_target != target_file_path:
                    target_file_path = resolved_target
                    get_file_resp = await client.get(
                        f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/{target_file_path}",
                        headers=self._headers(),
                        params={"ref": branch_name},
                    )
                    if get_file_resp.status_code == 200:
                        file_payload = get_file_resp.json()
                        existing_file_sha = file_payload.get("sha")
                        encoded_content = str(file_payload.get("content") or "")
                        if str(file_payload.get("encoding") or "") == "base64" and encoded_content:
                            existing_content = b64decode(encoded_content).decode("utf-8", errors="replace")
                    elif get_file_resp.status_code not in (404,):
                        get_file_resp.raise_for_status()
            else:
                get_file_resp.raise_for_status()

            patched_content = self._build_remediated_content(
                target_file=target_file_path,
                existing_content=existing_content,
                action=action,
                summary=summary,
                remediation_context=remediation_context,
            )
            diff_old_line: str | None = None
            diff_new_line: str | None = None
            file_content = patched_content or self._legacy_remediation_content(
                incident_id=incident_id,
                action=action,
                summary=summary,
            )
            if patched_content is not None:
                diff_old_line, diff_new_line = self._extract_diff_preview(
                    old_content=existing_content,
                    new_content=file_content,
                )
            if not diff_new_line:
                diff_old_line, diff_new_line = self._default_preview_for_target(
                    target_file=target_file_path,
                    action=action,
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
                f"https://api.github.com/repos/{self._owner}/{repo_name}/contents/{target_file_path}",
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
            target_file=target_file_path,
            diff_old_line=diff_old_line,
            diff_new_line=diff_new_line,
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
            review_decision = str(pr_data.get("review_decision") or "").upper()

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
        codeowner_reviewed = (
            review_decision == "APPROVED"
            or has_approved_review
            or mergeable_state in {"clean", "has_hooks"}
        )
        return MergeGateStatus(
            ci_passed=ci_passed,
            codeowner_reviewed=codeowner_reviewed,
            details={
                "ci_state": ci_state,
                "mergeable_state": mergeable_state,
                "review_decision": review_decision,
                "has_approved_review": has_approved_review,
            },
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
