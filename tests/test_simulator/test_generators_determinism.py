from __future__ import annotations

from datetime import datetime, timezone

from simulator.generators.logs import generate_log_entries
from simulator.generators.payloads import build_alert_payload
from simulator.generators.timeline import build_timeline_events


def test_log_generator_is_seed_deterministic() -> None:
    start = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    first = generate_log_entries(
        profile="flapping_backlog",
        service="dns-resolver",
        start_time=start,
        seed=7,
    )
    second = generate_log_entries(
        profile="flapping_backlog",
        service="dns-resolver",
        start_time=start,
        seed=7,
    )
    third = generate_log_entries(
        profile="flapping_backlog",
        service="dns-resolver",
        start_time=start,
        seed=8,
    )

    assert first == second
    assert first != third


def test_payload_generator_is_seed_deterministic() -> None:
    start = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    first = build_alert_payload(
        alertname="DNSResolverFlapping",
        service="dns-resolver",
        severity="critical",
        summary="summary",
        description="description",
        repository="acme/resilix-demo-config",
        target_file="infra/dns/coredns-config.yaml",
        log_profile="flapping_backlog",
        seed=17,
        start_time=start,
    )
    second = build_alert_payload(
        alertname="DNSResolverFlapping",
        service="dns-resolver",
        severity="critical",
        summary="summary",
        description="description",
        repository="acme/resilix-demo-config",
        target_file="infra/dns/coredns-config.yaml",
        log_profile="flapping_backlog",
        seed=17,
        start_time=start,
    )
    assert first == second


def test_timeline_generator_is_deterministic_with_fixed_start() -> None:
    start = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    first = build_timeline_events(start_time=start)
    second = build_timeline_events(start_time=start)
    assert first == second
