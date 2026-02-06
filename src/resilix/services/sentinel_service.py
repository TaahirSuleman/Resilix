from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from resilix.models.alert import Severity, ValidatedAlert

SignalFallback = Callable[[dict[str, Any]], dict[str, Any]]

SIGNAL_WEIGHTS: dict[str, float] = {
    "error_rate_high": 3.0,
    "health_flapping": 3.0,
    "backlog_growth": 2.0,
    "dependency_timeout": 2.0,
}


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


def _first_alert(payload: dict[str, Any]) -> dict[str, Any]:
    alerts = payload.get("alerts") or []
    if alerts:
        first = alerts[0]
        if isinstance(first, dict):
            return first
    return payload


def _collect_signal_hits(payload: dict[str, Any]) -> Counter[str]:
    hits: Counter[str] = Counter()
    alerts = payload.get("alerts") or []
    raw_signals = payload.get("signals") or []
    log_entries = payload.get("log_entries") or []

    for signal in raw_signals:
        if signal in SIGNAL_WEIGHTS:
            hits[str(signal)] += 1

    for alert in alerts:
        labels = alert.get("labels", {}) if isinstance(alert, dict) else {}
        annotations = alert.get("annotations", {}) if isinstance(alert, dict) else {}
        text = " ".join(
            str(value)
            for value in (
                labels.get("alertname"),
                labels.get("severity"),
                annotations.get("summary"),
                annotations.get("description"),
            )
            if value is not None
        ).lower()
        if "error" in text or "5xx" in text or "higherrorrate" in text:
            hits["error_rate_high"] += 1
        if "flapping" in text or "alternating" in text:
            hits["health_flapping"] += 1
        if "timeout" in text or "timed out" in text:
            hits["dependency_timeout"] += 1

    for entry in log_entries:
        if not isinstance(entry, dict):
            continue
        text = " ".join(
            str(value)
            for value in (entry.get("event"), entry.get("message"), entry.get("component"))
            if value is not None
        ).lower()
        metadata = entry.get("metadata", {})
        queue_depth = metadata.get("queue_depth") if isinstance(metadata, dict) else None

        if "flapping" in text or "alternating" in text:
            hits["health_flapping"] += 1
        if isinstance(queue_depth, (int, float)) and queue_depth > 200000:
            hits["backlog_growth"] += 1
        if "timeout" in text or "timed out" in text:
            hits["dependency_timeout"] += 1

    return hits


def _score_signals(signal_hits: Counter[str]) -> float:
    score = 0.0
    for signal, count in signal_hits.items():
        if signal not in SIGNAL_WEIGHTS:
            continue
        score += SIGNAL_WEIGHTS[signal]
        score += min(max(count - 1, 0), 3) * 0.5
    return score


def _severity_from_score(score: float, fallback: str = "high") -> Severity:
    from_score = Severity.LOW
    if score >= 6:
        from_score = Severity.CRITICAL
    elif score >= 4:
        from_score = Severity.HIGH
    elif score >= 2:
        from_score = Severity.MEDIUM
    try:
        from_label = Severity(fallback.lower())
    except ValueError:
        return from_score

    order = {
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    if order[from_label] > order[from_score]:
        return from_label
    return from_score


def evaluate_alert(
    payload: dict[str, Any],
    incident_id: str,
    llm_fallback: Optional[SignalFallback] = None,
) -> tuple[ValidatedAlert, dict[str, Any]]:
    alert = _first_alert(payload)
    labels = alert.get("labels", {}) if isinstance(alert, dict) else {}
    annotations = alert.get("annotations", {}) if isinstance(alert, dict) else {}
    starts_at = alert.get("startsAt") if isinstance(alert, dict) else None

    signal_hits = _collect_signal_hits(payload)
    score = _score_signals(signal_hits)
    deterministic_confidence = min(0.95, 0.45 + (score * 0.06))
    ambiguous = score < 2.5 or not signal_hits

    severity = _severity_from_score(score, fallback=str(labels.get("severity", "high")))
    is_actionable = score >= 2 or str(payload.get("status", "firing")).lower() == "firing"
    triage_reason = (
        "Signals detected: "
        + ", ".join(f"{name}:{count}" for name, count in sorted(signal_hits.items()))
        if signal_hits
        else "No deterministic incident signals were detected."
    )
    used_llm_fallback = False

    if ambiguous and llm_fallback is not None:
        fallback_result = llm_fallback(
            {
                "incident_id": incident_id,
                "signal_hits": dict(signal_hits),
                "score": score,
                "labels": labels,
                "annotations": annotations,
            }
        )
        if fallback_result:
            used_llm_fallback = True
            severity_raw = str(fallback_result.get("severity", severity.value))
            try:
                severity = Severity(severity_raw)
            except ValueError:
                severity = Severity.HIGH
            is_actionable = bool(fallback_result.get("is_actionable", is_actionable))
            triage_reason = str(fallback_result.get("triage_reason", triage_reason))
            deterministic_confidence = float(
                fallback_result.get("confidence_score", deterministic_confidence)
            )

    created = _parse_dt(starts_at)
    error_type = str(labels.get("alertname", "UnknownAlert"))
    service_name = str(labels.get("service", "unknown-service"))
    endpoint = labels.get("endpoint")
    affected_endpoints = [str(endpoint)] if endpoint else []
    error_rate = 1.0 + score

    validated = ValidatedAlert(
        alert_id=incident_id,
        is_actionable=is_actionable,
        severity=severity,
        service_name=service_name,
        error_type=error_type,
        error_rate=round(error_rate, 3),
        affected_endpoints=affected_endpoints,
        triggered_at=created,
        enrichment={
            "signal_scores": dict(signal_hits),
            "weighted_score": score,
            "used_llm_fallback": used_llm_fallback,
            "deterministic_confidence": round(deterministic_confidence, 3),
        },
        triage_reason=triage_reason,
    )
    trace = {
        "signal_scores": dict(signal_hits),
        "weighted_score": score,
        "ambiguous": ambiguous,
        "used_llm_fallback": used_llm_fallback,
        "deterministic_confidence": round(deterministic_confidence, 3),
    }
    return validated, trace
