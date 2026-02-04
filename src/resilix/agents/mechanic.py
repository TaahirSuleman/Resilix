from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.remediation import RemediationResult
from resilix.tools.github_tools import github_create_pr, github_merge_pr
from resilix.tools.validation_tools import code_validation

MECHANIC_INSTRUCTION = """You are the Mechanic, an expert code remediation specialist.

Your mission: Generate and deploy a FIX for the root cause identified by Sherlock.

Process:
1. UNDERSTAND the Thought Signature
2. LOCATE the faulty code
3. GENERATE a minimal fix
4. VALIDATE syntax
5. DEPLOY via PR
"""


def build_mechanic_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.mechanic_thinking_level, include_thoughts=settings.include_thoughts)
    return build_llm_agent(
        LlmAgent,
        name="MechanicAgent",
        model=settings.gemini_model_pro,
        description="Code generation and deployment via GitHub",
        instruction=MECHANIC_INSTRUCTION,
        tools=[github_create_pr, github_merge_pr, code_validation],
        output_key="remediation_result",
        output_schema=RemediationResult,
        **config,
    )
