"""PlayStealth tool manifest helpers.

This is the machine-readable mirror of the CLI tool registry.
"""

from __future__ import annotations

import json

from playstealth_actions.tool_registry import list_tools


def build_manifest() -> dict[str, object]:
    """Build a JSON-friendly manifest for the CLI tools."""
    tools = [
        {
            "name": tool.name,
            "module": tool.module,
            "purpose": tool.purpose,
            "status": tool.status,
        }
        for tool in list_tools()
    ]
    return {
        "name": "playstealth",
        "description": "Modular Playwright+Stealth survey CLI",
        "tool_count": len(tools),
        "tools": tools,
    }


def format_manifest(indent: int = 2) -> str:
    """Render the manifest as pretty JSON."""
    return json.dumps(build_manifest(), indent=indent, ensure_ascii=False)
