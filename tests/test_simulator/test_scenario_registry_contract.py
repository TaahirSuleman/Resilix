from __future__ import annotations

from simulator.scenarios.registry import (
    get_scenario,
    get_scenario_contract,
    list_scenarios,
)
from simulator.scripts.common import resolve_repository_for_scenario


def test_scenarios_expose_contract_metadata() -> None:
    names = list_scenarios()
    assert names == ["baseline", "dependency_timeout", "flapping"]

    baseline = get_scenario("baseline")
    flapping = get_scenario("flapping")

    assert baseline.repository_kind == "app"
    assert flapping.repository_kind == "config"

    contract = get_scenario_contract("flapping")
    assert contract["lifecycle_path"] == ["processing", "awaiting_approval", "resolved"]
    assert contract["target_repository_kind"] == "config"
    assert contract["target_file_pattern"] == "infra/dns/"


def test_repository_resolution_uses_demo_repos(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_OWNER", "acme")
    monkeypatch.delenv("RESILIX_TARGET_REPOSITORY", raising=False)
    monkeypatch.delenv("RESILIX_DEMO_APP_REPO", raising=False)
    monkeypatch.delenv("RESILIX_DEMO_CONFIG_REPO", raising=False)

    baseline_repo = resolve_repository_for_scenario(
        scenario_name="baseline",
        explicit_repository=None,
    )
    flapping_repo = resolve_repository_for_scenario(
        scenario_name="flapping",
        explicit_repository=None,
    )

    assert baseline_repo == "acme/resilix-demo-app"
    assert flapping_repo == "acme/resilix-demo-config"


def test_repository_resolution_no_longer_falls_back_to_monorepo(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("RESILIX_TARGET_REPOSITORY", raising=False)
    monkeypatch.delenv("RESILIX_DEMO_APP_REPO", raising=False)
    monkeypatch.delenv("RESILIX_DEMO_CONFIG_REPO", raising=False)

    baseline_repo = resolve_repository_for_scenario(
        scenario_name="baseline",
        explicit_repository=None,
    )
    flapping_repo = resolve_repository_for_scenario(
        scenario_name="flapping",
        explicit_repository=None,
    )

    assert baseline_repo.endswith("/resilix-demo-app")
    assert flapping_repo.endswith("/resilix-demo-config")
    assert baseline_repo != "PLACEHOLDER_OWNER/resilix"
    assert flapping_repo != "PLACEHOLDER_OWNER/resilix"
