from __future__ import annotations

from resilix.agents.adk_shim import LlmAgent
from resilix.agents.utils import build_agent_config, build_llm_agent
from resilix.config import get_settings
from resilix.models.remediation import JiraTicketResult
from resilix.tools.jira_tools import jira_create_issue

ADMIN_INSTRUCTION = """You are the Administrator, responsible for governance and audit trails.

Your responsibilities:
1. CREATE a Jira ticket documenting the incident
2. SET appropriate priority based on severity
3. ASSIGN to "Resilix Bot" user

Use the Thought Signature from Sherlock to populate all fields accurately.
"""


def build_administrator_agent() -> LlmAgent:
    settings = get_settings()
    config = build_agent_config(settings.sentinel_thinking_level, include_thoughts=False)
    return build_llm_agent(
        LlmAgent,
        name="AdministratorAgent",
        model=settings.gemini_model_flash,
        description="Creates audit trail via Jira ticket management",
        instruction=ADMIN_INSTRUCTION,
        tools=[jira_create_issue],
        output_key="jira_ticket",
        output_schema=JiraTicketResult,
        **config,
    )
