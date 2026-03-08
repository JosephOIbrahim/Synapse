"""
MCP Tool Registry

Maps all existing SYNAPSE command handlers to MCP tool definitions with
JSON Schema input schemas and MCP annotations. Provides dispatch_tool()
to bridge MCP tools/call requests to SynapseHandler.handle().

This module runs INSIDE Houdini (via hwebserver), so dispatch goes
directly through the handler -- no WebSocket hop.

Tool definitions are maintained in _tool_registry.py (single source of truth).
This module re-exports the public API that server.py and mcp_server.py consume.
"""

import time

from ..core.protocol import SynapseCommand

# =========================================================================
# Import everything from the canonical tool registry
# =========================================================================

# Payload builders -- canonical source is _tool_registry.py
from ._tool_registry import (
    _passthrough,
    _identity,
    _execute_python_payload,
    _stage_info_payload,
    _decide_payload,
    _add_memory_payload,
    _filter_keys,
    _network_explain_payload,
    _next_call_id,
    _EMPTY_SCHEMA,
    _dumps_str,
)

# Tool data -- single source of truth
from ._tool_registry import (
    TOOL_DEFS,
    TOOL_DISPATCH as _TOOL_DISPATCH,
    TOOL_JSON as _TOOL_JSON,
    TOOLS_LIST_CACHE as _TOOLS_LIST_CACHE,
    TOOL_NAMES as _TOOL_NAMES,
)


# =========================================================================
# Public API
# =========================================================================

def get_tools() -> list[dict]:
    """Return all MCP tool definitions for tools/list response.

    Returns a cached, pre-sorted list (He2025 determinism).
    Built once at import time -- tool definitions are static.
    """
    return _TOOLS_LIST_CACHE


def get_tool_names() -> list[str]:
    """Return sorted list of all registered tool names."""
    return list(_TOOL_NAMES)


def has_tool(name: str) -> bool:
    """Check if a tool name is registered."""
    return name in _TOOL_DISPATCH


def _truncate_args(args, max_keys=5, max_val_len=100):
    """Truncate tool arguments for journal logging."""
    if not args or not isinstance(args, dict):
        return args or {}
    result = {}
    for i, (k, v) in enumerate(sorted(args.items())):
        if i >= max_keys:
            result["..."] = "{} more keys".format(len(args) - max_keys)
            break
        sv = str(v)
        result[k] = sv[:max_val_len] if len(sv) > max_val_len else sv
    return result


def dispatch_tool(handler, tool_name: str, arguments: dict) -> dict:
    """Dispatch an MCP tools/call request to SynapseHandler.

    Args:
        handler: SynapseHandler instance.
        tool_name: MCP tool name (e.g. 'houdini_create_node').
        arguments: MCP tool arguments dict.

    Returns:
        MCP result dict with 'content' list and optional 'isError'.
    """
    t0 = time.monotonic()
    error_text = None

    try:
        entry = _TOOL_DISPATCH.get(tool_name)
        if entry is None:
            error_text = f"Unknown tool: {tool_name}"
            return {
                "content": [{"type": "text", "text": error_text}],
                "isError": True,
            }

        cmd_type, payload_fn = entry
        payload = payload_fn(arguments)

        # Create a SynapseCommand and dispatch through the handler
        command = SynapseCommand(
            type=cmd_type,
            id=_next_call_id(tool_name),
            payload=payload,
        )

        # Try bridge dispatch for undo/integrity wrapping
        try:
            from synapse.panel.bridge_adapter import (
                execute_through_bridge, is_read_only,
            )
            if not is_read_only(tool_name):
                response = execute_through_bridge(tool_name, handler, command)
            else:
                response = handler.handle(command)
        except ImportError:
            response = handler.handle(command)

        if response.success:
            data = response.data
            text = _dumps_str(data) if isinstance(data, dict) else str(data or "")
            return {"content": [{"type": "text", "text": text}]}
        else:
            error_text = response.error or "Unknown error"
            return {
                "content": [{"type": "text", "text": error_text}],
                "isError": True,
            }
    except Exception as e:
        error_text = str(e)
        raise
    finally:
        # Log to session journal (best-effort, never breaks dispatch)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        try:
            from synapse.panel.session_journal import get_journal
            get_journal().log_tool(
                tool_name,
                _truncate_args(arguments),
                None,
                error=error_text,
                duration_ms=elapsed_ms,
            )
        except Exception:
            pass  # Journal unavailable -- don't break tool dispatch


# =========================================================================
# Public aliases (mcp_server.py imports these names)
# =========================================================================

passthrough = _passthrough
identity = _identity
execute_python_payload = _execute_python_payload
stage_info_payload = _stage_info_payload
decide_payload = _decide_payload
add_memory_payload = _add_memory_payload
filter_keys = _filter_keys
