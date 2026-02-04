from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.thought_signature import ThoughtSignature
from resilix.tools.log_tools import query_logs

SHERLOCK_INSTRUCTION = """You are Sherlock, a master incident investigator.

Your mission: Determine the ROOT CAUSE of the incident, not just symptoms.

Investigation Process:
1. HYPOTHESIZE: Form 2-3 theories based on the alert context
2. GATHER: Use tools to collect evidence (logs, traces, recent deploys)
3. ANALYZE: Correlate evidence across sources
4. DEDUCE: Identify the most likely root cause
5. DOCUMENT: Create a detailed Thought Signature for remediation
"""


def build_sherlock_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.sherlock_thinking_level, include_thoughts=settings.include_thoughts)
    return build_llm_agent(
        LlmAgent,
        name="SherlockAgent",
        model=settings.gemini_model_pro,
        description="Deep root cause analysis with chain-of-thought reasoning",
        instruction=SHERLOCK_INSTRUCTION,
        tools=[query_logs],
        output_key="thought_signature",
        output_schema=ThoughtSignature,
        **config,
    )
