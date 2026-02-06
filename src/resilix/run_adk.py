from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict

from resilix.config import get_settings
from resilix.services.orchestrator import AdkRunner
from resilix.agent import get_root_agent


def _load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.alert_json:
        return json.loads(args.alert_json)
    if args.alert_file:
        with open(args.alert_file, "r", encoding="utf-8") as handle:
            return json.load(handle)
    raise ValueError("Either --alert-file or --alert-json must be provided")


def _validate_env(settings) -> None:
    if settings.use_mock_mcp:
        raise RuntimeError("USE_MOCK_MCP must be false to run ADK directly")
    key = (settings.gemini_api_key or "").strip().lower()
    if not key or key in {"your_key", "your_api_key", "changeme", "replace_me", "replace-with-real-key"}:
        raise RuntimeError("GEMINI_API_KEY must be set for ADK runs")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Resilix ADK runner locally")
    parser.add_argument("--alert-file", help="Path to alert JSON payload")
    parser.add_argument("--alert-json", help="Inline alert JSON string")
    parser.add_argument("--incident-id", help="Optional incident id override")
    args = parser.parse_args()

    settings = get_settings()
    _validate_env(settings)

    payload = _load_payload(args)
    incident_id = args.incident_id or "INC-local"

    runner = AdkRunner(get_root_agent())
    state = _run_async(runner.run(payload, incident_id))
    print(json.dumps(state, indent=2, default=str))


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    main()
