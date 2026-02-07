#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BASE_URL:-}" ]]; then
  echo "BASE_URL is required, e.g. https://resilix-service-xxxx.a.run.app" >&2
  exit 1
fi

echo "[1/5] Checking frontend root"
curl -fsS "$BASE_URL/" >/dev/null

echo "[2/5] Checking health metadata"
HEALTH_JSON="$(curl -fsS "$BASE_URL/health")"
echo "$HEALTH_JSON" | jq -e '.status == "ok" and has("app_version") and has("build_sha") and has("frontend_served")' >/dev/null

echo "[3/5] Triggering incident"
INCIDENT_ID="$(curl -fsS -X POST "$BASE_URL/webhook/prometheus" \
  -H 'Content-Type: application/json' \
  --data-binary '{"status":"firing","alerts":[{"labels":{"alertname":"HighErrorRate","service":"checkout-api","severity":"critical"},"annotations":{"summary":"Synthetic smoke alert"}}]}' \
  | jq -r '.incident_id')"

if [[ -z "$INCIDENT_ID" || "$INCIDENT_ID" == "null" ]]; then
  echo "Failed to create incident" >&2
  exit 1
fi

echo "Incident: $INCIDENT_ID"

echo "[4/5] Checking incident detail"
curl -fsS "$BASE_URL/incidents/$INCIDENT_ID" | jq -e '.incident_id == "'"$INCIDENT_ID"'" and has("status") and has("timeline")' >/dev/null

echo "[5/5] Optional merge-approval check"
set +e
APPROVE_RESP="$(curl -sS -X POST "$BASE_URL/incidents/$INCIDENT_ID/approve-merge" \
  -H 'Content-Length: 0' \
  -H 'Accept: application/json')"
APPROVE_CODE=$?
set -e

if [[ $APPROVE_CODE -eq 0 ]]; then
  echo "$APPROVE_RESP" | jq '.' >/dev/null 2>&1 && echo "approve-merge responded with JSON"
else
  echo "approve-merge check skipped or failed (non-fatal for smoke)"
fi

echo "Smoke check passed"
