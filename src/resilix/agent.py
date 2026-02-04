from __future__ import annotations

from resilix.agents.orchestrator import build_root_agent

_root_agent = None


def get_root_agent():
    global _root_agent
    if _root_agent is None:
        _root_agent = build_root_agent()
    return _root_agent
