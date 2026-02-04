from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.alert import ValidatedAlert

SENTINEL_INSTRUCTION = """You are the Sentinel, a fast alert triage specialist.

Responsibilities:
1. VALIDATE: Check if the alert is actionable (not noise, not duplicate)
2. CLASSIFY: Determine severity (critical, high, medium, low)
3. ENRICH: Add service metadata and context
4. DECIDE: Should this trigger investigation? (yes/no with reason)

Input: Prometheus AlertManager JSON webhook payload
Output: Structured ValidatedAlert object
"""


def build_sentinel_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.sentinel_thinking_level, include_thoughts=False)
    return build_llm_agent(
        LlmAgent,
        name="SentinelAgent",
        model=settings.gemini_model_flash,
        description="Fast alert validation and noise filtering",
        instruction=SENTINEL_INSTRUCTION,
        tools=[],
        output_key="validated_alert",
        output_schema=ValidatedAlert,
        **config,
    )
