from __future__ import annotations

from resilix.agents.adk_shim import ParallelAgent, SequentialAgent
from resilix.agents.administrator import build_administrator_agent
from resilix.agents.mechanic import build_mechanic_agent
from resilix.agents.sentinel import build_sentinel_agent
from resilix.agents.sherlock import build_sherlock_agent


def build_root_agent():
    sentinel_agent = build_sentinel_agent()
    sherlock_agent = build_sherlock_agent()
    administrator_agent = build_administrator_agent()
    mechanic_agent = build_mechanic_agent()

    remediation_swarm = ParallelAgent(
        name="RemediationSwarm",
        description="Executes remediation actions in parallel",
        sub_agents=[administrator_agent, mechanic_agent],
    )

    return SequentialAgent(
        name="ResilixOrchestrator",
        description="Orchestrates the autonomous incident response workflow",
        sub_agents=[sentinel_agent, sherlock_agent, remediation_swarm],
    )
