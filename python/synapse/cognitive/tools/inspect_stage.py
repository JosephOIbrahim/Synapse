"""Cognitive tool: ``synapse_inspect_stage`` (Sprint 3 Spike 1 port).

Thin adapter around ``synapse.inspector.synapse_inspect_stage`` that
matches the Dispatcher's tool contract:

    inspect_stage(**kwargs) -> Dict[str, Any]

The Inspector's own implementation was already host-agnostic — it
composes a Python script, hands it to a pluggable transport, parses the
response. All this module does is:

  1. Accept only JSON-serializable kwargs (``target_path``, ``timeout``).
  2. Call the Inspector.
  3. Serialize the resulting ``StageAST`` into a plain dict via
     ``.to_payload()`` so the Dispatcher can return it directly.

No ``hou`` imports. The transport that reaches Houdini is injected at
daemon-boot time via ``synapse.inspector.configure_transport(fn)`` —
supplied from ``synapse.host.*`` in production, from a test fixture
under pytest.

Strangler Fig role
------------------
This is the FIRST tool ported out of the Sprint-2 WebSocket handler
path and into the inside-out Dispatcher path. The Sprint-2 handler in
``mcp_server.py`` is rewired to call the Dispatcher instead of invoking
``synapse_inspect_stage`` directly. All other tools continue through
the existing handler path — one tool ported, ~43 still direct.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


INSPECT_STAGE_SCHEMA: Dict[str, Any] = {
    "description": (
        "Extracts the AST of the Houdini Solaris /stage context. Returns "
        "USD prim paths, topology, error states, and flags for every "
        "node. Enables scene-aware responses across sessions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_path": {
                "type": "string",
                "description": (
                    "Houdini context path to inspect. Defaults to "
                    "'/stage'. Must be absolute and match "
                    "/[a-zA-Z0-9_/]+."
                ),
            },
            "timeout": {
                "type": "number",
                "description": (
                    "Per-call transport timeout in seconds (default 30)."
                ),
            },
        },
        "required": [],
    },
}
"""Anthropic tool-use schema for ``synapse_inspect_stage``.

Keep in sync with ``inspect_stage``'s signature. The MCP server
(``mcp_server.py``) and the in-process daemon both register the same
schema so the agent sees a consistent tool interface across transports.
"""


def inspect_stage(
    target_path: str = "/stage",
    *,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Extract the flat AST of a Houdini context.

    Args:
        target_path: Houdini context path to inspect. Defaults to
            ``/stage`` (Solaris). Must be absolute and match
            ``/[a-zA-Z0-9_/]+``.
        timeout: Per-call transport timeout in seconds. ``None`` →
            Inspector default (``DEFAULT_TIMEOUT_SECONDS`` = 30).

    Returns:
        The StageAST payload as a plain dict with the schema:

            {
                "schema_version": "1.0.0",
                "target_path": "/stage",
                "nodes": [ {node}, {node}, ... ],
            }

        Each node dict carries ``node_name``, ``node_type``, ``hou_path``,
        ``usd_prim_paths``, ``display_flag``, ``bypass_flag``,
        ``error_state``, ``error_message``, ``inputs``, ``outputs``,
        ``children``, ``key_parms``, ``provenance``.

    Raises:
        Inspector exceptions propagate unchanged. The Dispatcher catches
        them at its exception boundary and wraps them as
        ``AgentToolError`` values — this tool does not try to handle them.
    """
    # Import at call time so module-import of the cognitive.tools package
    # doesn't pay the Inspector's import cost unless a tool is actually
    # invoked. Zero hou at any point in this import graph.
    from synapse.inspector import synapse_inspect_stage

    ast = synapse_inspect_stage(target_path, timeout=timeout)
    return ast.to_payload()
