from __future__ import annotations

from typing import Any, List, Optional


class _BaseAgent:
    def __init__(
        self,
        name: str,
        description: str | None = None,
        instruction: str | None = None,
        tools: Optional[List[Any]] = None,
        output_key: str | None = None,
        output_schema: Any = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.description = description
        self.instruction = instruction
        self.tools = tools or []
        self.output_key = output_key
        self.output_schema = output_schema
        self.model = model
        self.kwargs = kwargs


try:  # pragma: no cover - requires ADK installed
    from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent
except BaseException:  # pragma: no cover
    class LlmAgent(_BaseAgent):
        pass

    class SequentialAgent(_BaseAgent):
        def __init__(self, name: str, description: str, sub_agents: List[Any]) -> None:
            super().__init__(name=name, description=description)
            self.sub_agents = sub_agents

    class ParallelAgent(_BaseAgent):
        def __init__(self, name: str, description: str, sub_agents: List[Any]) -> None:
            super().__init__(name=name, description=description)
            self.sub_agents = sub_agents
