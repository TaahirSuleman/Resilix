from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from simulator.scenarios.registry import get_scenario

RepositoryKind = Literal["app", "config"]

DEFAULT_DEMO_APP_REPO = "PLACEHOLDER_OWNER/resilix-demo-app"
DEFAULT_DEMO_CONFIG_REPO = "PLACEHOLDER_OWNER/resilix-demo-config"
DEFAULT_CONFIG_TARGET_FILE = "infra/dns/coredns-config.yaml"


def resolve_base_url(value: str | None) -> str:
    base_url = value or os.getenv("RESILIX_BASE_URL") or os.getenv("BASE_URL")
    if not base_url:
        raise SystemExit("Base URL is required via --base-url, RESILIX_BASE_URL, or BASE_URL")
    return base_url.rstrip("/")


def _owner_repo(owner: str, kind: RepositoryKind) -> str:
    suffix = "resilix-demo-app" if kind == "app" else "resilix-demo-config"
    return f"{owner}/{suffix}"


def default_demo_repository(kind: RepositoryKind) -> str:
    owner = (os.getenv("GITHUB_OWNER") or "").strip()
    if owner:
        return _owner_repo(owner, kind)
    if kind == "app":
        return os.getenv("RESILIX_DEMO_APP_REPO", DEFAULT_DEMO_APP_REPO)
    return os.getenv("RESILIX_DEMO_CONFIG_REPO", DEFAULT_DEMO_CONFIG_REPO)


def resolve_repository(
    *,
    explicit_repository: str | None,
    kind: RepositoryKind,
) -> str:
    if explicit_repository:
        return explicit_repository
    target_repository = os.getenv("RESILIX_TARGET_REPOSITORY")
    if target_repository:
        return target_repository
    if kind == "app":
        return os.getenv("RESILIX_DEMO_APP_REPO", default_demo_repository("app"))
    return os.getenv("RESILIX_DEMO_CONFIG_REPO", default_demo_repository("config"))


def resolve_repository_for_scenario(
    *,
    scenario_name: str,
    explicit_repository: str | None,
) -> str:
    scenario = get_scenario(scenario_name)
    return resolve_repository(
        explicit_repository=explicit_repository,
        kind=scenario.repository_kind,
    )


def ensure_non_placeholder_repository(repository: str) -> None:
    lowered = repository.strip().lower()
    if lowered.startswith("placeholder_owner/"):
        raise SystemExit(
            "Repository is unresolved placeholder. Set RESILIX_DEMO_APP_REPO/RESILIX_DEMO_CONFIG_REPO "
            "or pass --repository."
        )


def resolve_target_file(value: str | None, default: str = DEFAULT_CONFIG_TARGET_FILE) -> str:
    return value or os.getenv("RESILIX_TARGET_FILE") or default


def ensure_fixture_exists(path_value: str) -> Path:
    path = Path(path_value)
    if not path.exists():
        raise SystemExit(f"Fixture not found: {path}")
    return path
