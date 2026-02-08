from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from simulator.generators.payloads import build_alert_payload


RepositoryKind = Literal["app", "config"]


@dataclass(frozen=True)
class ScenarioContract:
    lifecycle_path: tuple[str, str, str]
    root_cause_categories: tuple[str, ...]
    action_types: tuple[str, ...]
    target_repository_kind: RepositoryKind
    target_file_pattern: str
    max_to_awaiting_approval_seconds: int
    max_to_resolved_seconds: int


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    alertname: str
    service: str
    severity: str
    summary: str
    details: str
    log_profile: str
    default_target_file: str
    repository_kind: RepositoryKind
    contract: ScenarioContract


_SCENARIOS: dict[str, Scenario] = {
    "baseline": Scenario(
        name="baseline",
        description="Baseline error-rate incident with 5xx spike",
        alertname="HighErrorRate",
        service="checkout-api",
        severity="high",
        summary="High 5xx error rate detected",
        details="Error rate exceeded SLO threshold for sustained period",
        log_profile="error_rate",
        default_target_file="src/app/handlers.py",
        repository_kind="app",
        contract=ScenarioContract(
            lifecycle_path=("processing", "awaiting_approval", "resolved"),
            root_cause_categories=("code_bug",),
            action_types=("fix_code",),
            target_repository_kind="app",
            target_file_pattern="src/app/",
            max_to_awaiting_approval_seconds=120,
            max_to_resolved_seconds=300,
        ),
    ),
    "flapping": Scenario(
        name="flapping",
        description="DNS resolver flapping with backlog growth",
        alertname="DNSResolverFlapping",
        service="dns-resolver",
        severity="critical",
        summary="DNS resolver targets are flapping",
        details="Targets alternating between healthy and unhealthy",
        log_profile="flapping_backlog",
        default_target_file="infra/dns/coredns-config.yaml",
        repository_kind="config",
        contract=ScenarioContract(
            lifecycle_path=("processing", "awaiting_approval", "resolved"),
            root_cause_categories=("config_error",),
            action_types=("config_change",),
            target_repository_kind="config",
            target_file_pattern="infra/dns/",
            max_to_awaiting_approval_seconds=120,
            max_to_resolved_seconds=300,
        ),
    ),
    "dependency_timeout": Scenario(
        name="dependency_timeout",
        description="Upstream dependency timeouts",
        alertname="DependencyTimeout",
        service="payments-api",
        severity="high",
        summary="Dependency timeouts detected",
        details="Upstream dependency timed out under load",
        log_profile="dependency_timeout",
        default_target_file="infra/dependencies.yaml",
        repository_kind="config",
        contract=ScenarioContract(
            lifecycle_path=("processing", "awaiting_approval", "resolved"),
            root_cause_categories=("dependency_failure", "config_error"),
            action_types=("config_change", "fix_code"),
            target_repository_kind="config",
            target_file_pattern="infra/",
            max_to_awaiting_approval_seconds=120,
            max_to_resolved_seconds=300,
        ),
    ),
}


def list_scenarios() -> list[str]:
    return sorted(_SCENARIOS.keys())


def get_scenario(name: str) -> Scenario:
    scenario = _SCENARIOS.get(name)
    if scenario is None:
        raise KeyError(f"Unknown scenario: {name}")
    return scenario


def get_scenario_contract(name: str) -> dict[str, object]:
    scenario = get_scenario(name)
    return {
        "name": scenario.name,
        "lifecycle_path": list(scenario.contract.lifecycle_path),
        "root_cause_categories": list(scenario.contract.root_cause_categories),
        "action_types": list(scenario.contract.action_types),
        "target_repository_kind": scenario.contract.target_repository_kind,
        "target_file_pattern": scenario.contract.target_file_pattern,
        "max_to_awaiting_approval_seconds": scenario.contract.max_to_awaiting_approval_seconds,
        "max_to_resolved_seconds": scenario.contract.max_to_resolved_seconds,
    }


def build_payload_for_scenario(
    *,
    name: str,
    repository: str,
    target_file: str | None = None,
    seed: int = 42,
    start_time: datetime | None = None,
) -> dict:
    scenario = get_scenario(name)

    if start_time is None:
        start_time = datetime.now(timezone.utc)

    return build_alert_payload(
        alertname=scenario.alertname,
        service=scenario.service,
        severity=scenario.severity,
        summary=scenario.summary,
        description=scenario.details,
        repository=repository,
        target_file=target_file or scenario.default_target_file,
        log_profile=scenario.log_profile,
        seed=seed,
        start_time=start_time,
        group_key=f"scenario-{scenario.name}",
    )
