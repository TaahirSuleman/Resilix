from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
from typing import Iterable


def _isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timestamps(start_time: datetime, count: int, step_seconds: int) -> Iterable[datetime]:
    for idx in range(count):
        yield start_time + timedelta(seconds=step_seconds * idx)


def generate_log_entries(
    *,
    profile: str,
    service: str,
    start_time: datetime | None = None,
    count: int = 2,
    seed: int = 42,
) -> list[dict]:
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    rng = random.Random(seed)
    entries: list[dict] = []

    if profile == "flapping_backlog":
        for idx, ts in enumerate(_timestamps(start_time, count, 9)):
            queue_depth = 220000 + (idx * 60000) + rng.randint(0, 15000)
            unhealthy = 420 + (idx * 70) + rng.randint(0, 40)
            entries.append(
                {
                    "timestamp": _isoformat(ts),
                    "level": "ERROR",
                    "service": service,
                    "component": "HealthCheckSubsystem",
                    "event": "TargetHealthFlapping",
                    "message": "Targets alternating between healthy and unhealthy due to propagation backlog",
                    "metadata": {"queue_depth": queue_depth, "unhealthy_targets_count": unhealthy},
                }
            )
    elif profile == "backlog_growth":
        for idx, ts in enumerate(_timestamps(start_time, count, 11)):
            queue_depth = 210000 + (idx * 50000) + rng.randint(0, 12000)
            entries.append(
                {
                    "timestamp": _isoformat(ts),
                    "level": "WARN",
                    "service": service,
                    "component": "QueueMonitor",
                    "event": "QueueDepthExceeded",
                    "message": "Queue depth backlog rising above safe threshold",
                    "metadata": {"queue_depth": queue_depth, "threshold": 200000},
                }
            )
    elif profile == "dependency_timeout":
        for idx, ts in enumerate(_timestamps(start_time, count, 12)):
            timeout_ms = 1200 + (idx * 200) + rng.randint(0, 100)
            entries.append(
                {
                    "timestamp": _isoformat(ts),
                    "level": "ERROR",
                    "service": service,
                    "component": "UpstreamClient",
                    "event": "DependencyTimeout",
                    "message": "Upstream dependency timed out while processing request",
                    "metadata": {"timeout_ms": timeout_ms, "dependency": "payments-core"},
                }
            )
    elif profile == "error_rate":
        for idx, ts in enumerate(_timestamps(start_time, count, 8)):
            error_rate = 4.2 + (idx * 0.8) + rng.random()
            entries.append(
                {
                    "timestamp": _isoformat(ts),
                    "level": "ERROR",
                    "service": service,
                    "component": "HttpGateway",
                    "event": "HighErrorRate",
                    "message": "5xx error rate spiking above SLO",
                    "metadata": {"error_rate": round(error_rate, 2), "threshold": 1.5},
                }
            )
    else:
        raise ValueError(f"Unknown log profile: {profile}")

    return entries
