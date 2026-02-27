"""
Tool Schema Bridge -- Convert MCP tool definitions to Anthropic API format.

Pure data transform. No Houdini dependency, no hou imports, no Qt imports.
Imports only from synapse.mcp._tool_registry and (optionally) the group
knowledge modules at the repo root.
"""

from __future__ import annotations

from synapse.mcp._tool_registry import TOOL_DEFS, TOOL_DISPATCH


# =========================================================================
# Group knowledge tools (6 additional tools from mcp_tools_* modules)
# =========================================================================

_GROUP_TOOLS: list[tuple[str, str]] = []  # (name, description)

_GROUP_MODULE_MAP = {
    "synapse_group_scene": "mcp_tools_scene",
    "synapse_group_render": "mcp_tools_render",
    "synapse_group_usd": "mcp_tools_usd",
    "synapse_group_tops": "mcp_tools_tops",
    "synapse_group_memory": "mcp_tools_memory",
    "synapse_group_cops": "mcp_tools_cops",
}

for _group_name, _module_name in _GROUP_MODULE_MAP.items():
    try:
        import importlib
        _mod = importlib.import_module(_module_name)
        _knowledge: str = getattr(_mod, "GROUP_KNOWLEDGE", "")
        if _knowledge:
            # Match mcp_server.py: "[TOOL GROUP] {first 200 chars}..."
            _desc = f"[TOOL GROUP] {_knowledge[:200]}..."
            _GROUP_TOOLS.append((_group_name, _desc))
    except (ImportError, ModuleNotFoundError):
        pass  # Skip missing group modules gracefully


# =========================================================================
# Build Anthropic tool cache at import time
# =========================================================================

_EMPTY_INPUT_SCHEMA: dict = {"type": "object", "properties": {}, "required": []}


def _build_cache() -> tuple[dict, ...]:
    """Convert TOOL_DEFS + group tools to Anthropic API format. Returns immutable tuple."""
    tools: list[dict] = []

    # Registry tools (102)
    for entry in TOOL_DEFS:
        name, _cmd, _builder, description, input_schema, _ro, _destr, _idemp = entry
        tools.append({
            "name": name,
            "description": description,
            "input_schema": input_schema,  # Anthropic uses input_schema, NOT inputSchema
        })

    # Group knowledge tools (up to 6)
    for group_name, group_desc in _GROUP_TOOLS:
        tools.append({
            "name": group_name,
            "description": group_desc,
            "input_schema": _EMPTY_INPUT_SCHEMA,
        })

    return tuple(tools)


# Module-level cache -- built once, immutable
_TOOLS_CACHE: tuple[dict, ...] = _build_cache()


# =========================================================================
# Public API
# =========================================================================


def get_anthropic_tools() -> list[dict]:
    """Return tool definitions in Anthropic API format.

    Each tool dict has keys: name, description, input_schema.
    Cached at module level since TOOL_DEFS is immutable.
    """
    return list(_TOOLS_CACHE)


def get_tool_dispatch(tool_name: str) -> tuple | None:
    """Return (command_type, payload_builder) for a tool, or None if not found."""
    return TOOL_DISPATCH.get(tool_name)


def get_tool_count() -> int:
    """Return total number of tools (registry + group tools)."""
    return len(_TOOLS_CACHE)
