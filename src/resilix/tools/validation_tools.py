from __future__ import annotations

import ast
from typing import Dict

try:
    from google.adk.tools import tool
except Exception:  # pragma: no cover
    def tool(fn):
        return fn


@tool
def code_validation(source_code: str) -> Dict[str, str | bool]:
    """Validate python syntax for generated code."""
    try:
        ast.parse(source_code)
        return {"valid": True, "error": ""}
    except SyntaxError as exc:  # pragma: no cover - deterministic
        return {"valid": False, "error": str(exc)}
