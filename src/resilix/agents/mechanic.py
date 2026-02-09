from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.remediation import RemediationResultPayload
from resilix.tools.github_tools import (
    get_file_contents,
    github_create_pr,
    github_list_repositories,
    github_merge_pr,
    search_code,
)
from resilix.tools.validation_tools import code_validation

MECHANIC_INSTRUCTION = """You are the Mechanic, an expert remediation specialist.

Your mission is to propose and validate a minimal patch from the ThoughtSignature.
Select strategy by root-cause category and artifact type, validate syntax, and execute PR flow.
Manual approval and merge policies are enforced outside of your reasoning path.
Before proposing remediation, inspect the target file and nearby patterns in the repository.

You may only call these tools:
- github_list_repositories
- get_file_contents
- search_code
- github_create_pr
- github_merge_pr
- code_validation
Do not call any other tool names.
"""


def build_mechanic_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.mechanic_thinking_level, include_thoughts=settings.include_thoughts)
    return build_llm_agent(
        LlmAgent,
        name="MechanicAgent",
        model=settings.resolved_gemini_model_flash(),
        description="Code generation and deployment via GitHub",
        instruction=MECHANIC_INSTRUCTION,
        tools=[
            github_list_repositories,
            get_file_contents,
            search_code,
            github_create_pr,
            github_merge_pr,
            code_validation,
        ],
        output_key="remediation_result",
        output_schema=RemediationResultPayload,
        **config,
    )
