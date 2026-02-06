from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.alert import ValidatedAlert

SENTINEL_INSTRUCTION = """You are the Sentinel, a fast alert triage specialist.

Responsibilities:
1. VALIDATE if an incident is actionable.
2. CLASSIFY severity using evidence from typed operational signals.
3. ENRICH context for downstream agents.
4. DECIDE whether investigation should continue.

You are optimized for low-latency triage and should output ValidatedAlert only.
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
