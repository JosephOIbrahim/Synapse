"""Opt-in read-only mode for MCP clients (BP12 item 12).

MCP clients reach Houdini through two transports: ``POST /mcp`` (MCP
Streamable HTTP) and the ``/synapse``
WebSocket that ``mcp_server.py`` bridges stdio clients such as Claude Code
onto. Setting ``SYNAPSE_MCP_READ_ONLY=1`` in Houdini's environment fences both
to the tools that are read-only under both of SYNAPSE's gating sets: the MCP
transport's ``readOnlyHint`` annotation and the bridge's own read-only set
(``server.is_transport_fast_path``). Any other tool is refused with a message
that names it and this variable.

The fence sits in the transports and applies to every caller of them. That
includes the SYNAPSE panel's own agent, which sends its tool calls to
``POST /mcp`` (``panel/tool_executor.py``), so while the variable is set the
panel can only read as well. Stopping is never fenced, for any caller: the
tools in ``STOPS_ALWAYS_PASS`` always run, because a mode meant to prevent
changes must never keep anyone from stopping work. A WebSocket command that
is not a tool
(``authenticate``, ``heartbeat``, ``ping`` and the like) is protocol and always
passes. The variable is read on every call, so it can be switched without a
restart. It is off by default.
"""
from __future__ import annotations

import os

ENV = "SYNAPSE_MCP_READ_ONLY"

_ON = frozenset({"1", "true", "yes", "on"})

#: Stop controls pass the fence for every caller. Stopping work is not a change the
#: fence exists to prevent, and refusing it would turn a safety mode into a hazard:
#: the panel's Cancel cook and Emergency halt are among these.
STOPS_ALWAYS_PASS = frozenset({
    "tops_cancel_cook",
    "synapse_emergency_halt",
    "synapse_farm_cancel",
    "synapse_render_farm_cancel",
    "synapse_render_stop",
})

#: Command type -> tool name, built from the tool registry on first use.
_TOOL_BY_COMMAND: dict | None = None


def enabled() -> bool:
    """True when ``SYNAPSE_MCP_READ_ONLY`` asks for read-only mode."""
    return os.environ.get(ENV, "").strip().lower() in _ON


def is_change(tool_name: str) -> bool:
    """True for a tool this mode refuses: not read-only under both gating sets, and not a stop.

    The Level 1 preflight gate checks exactly these calls before they are sent
    (server/preflight_gate.py), so the two rules never disagree about what a change is.
    """
    if tool_name in STOPS_ALWAYS_PASS:
        return False
    from synapse.mcp.server import is_transport_fast_path

    return not is_transport_fast_path(tool_name)


def refusal_for_tool(tool_name: str) -> str | None:
    """The refusal message for *tool_name*, or None when the call may run."""
    if not enabled():
        return None
    if tool_name in STOPS_ALWAYS_PASS:
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
