"""Opt-in read-only mode for external MCP clients (BP12 item 12).

External clients reach Houdini through two transports that skip the panel's
worker policy: ``POST /mcp`` (MCP Streamable HTTP) and the ``/synapse``
WebSocket that ``mcp_server.py`` bridges stdio clients such as Claude Code
onto. Setting ``SYNAPSE_MCP_READ_ONLY=1`` in Houdini's environment fences both
to the tools that are read-only under both of SYNAPSE's gating sets: the MCP
transport's ``readOnlyHint`` annotation and the bridge's own read-only set
(``server.is_transport_fast_path``). Any other tool is refused with a message
that names it and this variable.

The fence sits in the transports, not in ``SynapseHandler.handle``, so the
panel's own agent is never affected. A WebSocket command that is not a tool
(``authenticate``, ``heartbeat``, ``ping`` and the like) is protocol and always
passes. The variable is read on every call, so it can be switched without a
restart. It is off by default.
"""
from __future__ import annotations

import os

ENV = "SYNAPSE_MCP_READ_ONLY"

_ON = frozenset({"1", "true", "yes", "on"})

#: Command type -> tool name, built from the tool registry on first use.
_TOOL_BY_COMMAND: dict | None = None


def enabled() -> bool:
    """True when ``SYNAPSE_MCP_READ_ONLY`` asks for read-only mode."""
    return os.environ.get(ENV, "").strip().lower() in _ON


def refusal_for_tool(tool_name: str) -> str | None:
    """The refusal message for *tool_name*, or None when the call may run."""
    if not enabled():
        return None
    from synapse.mcp.server import is_transport_fast_path

    if is_transport_fast_path(tool_name):
        return None
    return (f"SYNAPSE is in read-only mode for MCP clients ({ENV} is set), and "
            f"{tool_name} is not on its read-only list, so it was not run. Read-only "
            f"tools still work. Unset {ENV} in Houdini's environment to allow changes.")


def tool_for_command(command_type: str) -> str | None:
    """The tool a WebSocket command type belongs to, or None for a protocol command."""
    global _TOOL_BY_COMMAND
    if _TOOL_BY_COMMAND is None:
        from synapse.mcp._tool_registry import TOOL_DEFS

        _TOOL_BY_COMMAND = {entry[1]: entry[0] for entry in TOOL_DEFS}
    return _TOOL_BY_COMMAND.get(command_type)


def refusal_for_command(command_type: str) -> str | None:
    """The refusal for a WebSocket command, or None when it may run."""
    if not enabled():
        return None
    tool = tool_for_command(command_type)
    return None if tool is None else refusal_for_tool(tool)
