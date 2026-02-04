from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

from resilix.config import get_settings


def build_generation_config(thinking_level: str, include_thoughts: bool) -> Optional[Any]:
    try:  # pragma: no cover - depends on google-genai
        from google.genai import types

        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
            include_thoughts=include_thoughts,
        )
    except Exception:
        return None


def build_llm_agent(agent_cls: Any, **kwargs: Any) -> Any:
    """Build LlmAgent with only supported kwargs (safe across SDK versions)."""
    signature = inspect.signature(agent_cls)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return agent_cls(**kwargs)
    supported = set(signature.parameters.keys())
    filtered: Dict[str, Any] = {key: value for key, value in kwargs.items() if key in supported}
    return agent_cls(**filtered)


def build_agent_config(thinking_level: str, include_thoughts: bool) -> Dict[str, Any]:
    settings = get_settings()
    generation_config = build_generation_config(thinking_level, include_thoughts)

    config: Dict[str, Any] = {}
    if generation_config is not None:
        # Some SDKs call this generate_content_config, others use generation_config
        config["generate_content_config"] = generation_config
        config["generation_config"] = generation_config
    config["api_key"] = settings.gemini_api_key
    return config
