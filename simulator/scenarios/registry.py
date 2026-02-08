from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from simulator.generators.payloads import build_alert_payload


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
    ),
}


def list_scenarios() -> list[str]:
    return sorted(_SCENARIOS.keys())


def build_payload_for_scenario(
    *,
    name: str,
    repository: str,
    target_file: str | None = None,
    seed: int = 42,
    start_time: datetime | None = None,
) -> dict:
    scenario = _SCENARIOS.get(name)
    if scenario is None:
        raise KeyError(f"Unknown scenario: {name}")

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
