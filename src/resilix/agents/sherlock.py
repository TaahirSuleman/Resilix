from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.thought_signature import ThoughtSignaturePayload
from resilix.tools.log_tools import query_logs
from resilix.tools.github_tools import list_commits

SHERLOCK_INSTRUCTION = """You are Sherlock, a root-cause investigator.

Use high-reasoning mode to:
1. Form competing hypotheses.
2. Gather evidence through tools.
3. Correlate signals into one likely root cause.
4. Emit a complete ThoughtSignature for downstream remediation.

The ThoughtSignature must be internally consistent and include actionable artifact targets.

You may only call these tools:
- query_logs
- list_commits
Do not call any other tool names.
"""


def build_sherlock_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.sherlock_thinking_level, include_thoughts=settings.include_thoughts)
    return build_llm_agent(
        LlmAgent,
        name="SherlockAgent",
        model=settings.resolved_gemini_model_flash(),
        description="Deep root cause analysis with chain-of-thought reasoning",
        instruction=SHERLOCK_INSTRUCTION,
        tools=[query_logs, list_commits],
        output_key="thought_signature",
        output_schema=ThoughtSignaturePayload,
        **config,
    )
