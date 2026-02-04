from __future__ import annotations

from typing import Dict


class MockGithubClient:
    def create_pull_request(self, repo: str, branch: str, title: str, body: str) -> Dict[str, str | int]:
        return {
            "pr_number": 456,
            "pr_url": f"https://github.com/{repo}/pull/456",
            "branch": branch,
            "title": title,
            "body": body,
        }

    def merge_pull_request(self, repo: str, pr_number: int) -> Dict[str, bool]:
        return {"merged": True}
