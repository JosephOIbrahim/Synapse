"""Cognitive tool factory: legacy WS registry tools -> Dispatcher (G1 port waves).

Port pattern (docs/PORT_WAVE_MANIFEST.md, OD-2 = (a) "wrap"): a ported registry
tool becomes a THIN cognitive Dispatcher tool. The existing WS command handler
inside Houdini stays the execution primitive — this module reimplements nothing.
Each generated tool does exactly what the legacy ``TOOL_DISPATCH`` fallback in
``mcp_server.py::call_tool()`` did for that tool:

    1. Build the payload with the SAME payload builder the canonical registry
       (``synapse.mcp._tool_registry``) declares for the tool.
    2. Hand ``(command_type, payload)`` to an injected transport that performs
       the WS round-trip into the Houdini process.
    3. Return the response data unchanged.

Zero ``hou`` imports — enforced by ``tests/test_cognitive_boundary.py``. The
transport is injected at host-boot time via :func:`configure_transport`
(mirroring ``synapse.inspector.configure_transport``); in production
``mcp_server.py`` supplies a closure that marshals ``send_command`` back onto
the MCP event loop.

Envelope note (the byte-for-byte rule): the Dispatcher contract requires tools
to return a *dict*, but the WS response ``data`` field is ``Any`` (see
``synapse.core.protocol.SynapseResponse``). To keep the legacy success envelope
(``_dumps_str(data)`` for ANY data shape) intact, the tool wraps the raw data
under :data:`DATA_KEY` and the caller unwraps with :func:`unwrap_ws_data`
before serializing. The wrapper never crosses the MCP boundary.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

TransportFn = Callable[[str, Dict[str, Any]], Any]
"""Transport contract: ``(command_type, payload) -> response data``.

Must raise the transport's ORIGINAL exceptions (ConnectionError / RuntimeError /
TimeoutError ...) unwrapped — the Dispatcher records the exception class name in
``AgentToolError.error_type`` and the MCP adapter maps it back onto the legacy
error envelope. Re-wrapping here would silently rewrite that envelope.
"""

DATA_KEY = "__ws_data__"
"""Internal envelope key carrying the raw WS response data through the
Dispatcher's dict-only return contract. Never serialized to MCP callers."""

_transport: Optional[TransportFn] = None


def configure_transport(fn: TransportFn) -> None:
    """Inject the WS transport (host-boot time). Overwrites any prior one."""
    global _transport
    _transport = fn


def reset_transport() -> None:
    """Clear the injected transport (test isolation — see tests/conftest.py)."""
    global _transport
    _transport = None


def unwrap_ws_data(result: Dict[str, Any]) -> Any:
    """Extract the raw WS response data from a passthrough tool's return."""
    return result[DATA_KEY]


def make_passthrough_tool(
    tool_name: str,
    command_type: str,
    build_payload: Callable[[dict], dict],
) -> Callable[..., Dict[str, Any]]:
    """Build a Dispatcher tool that round-trips one registry tool over the WS.

    Args:
        tool_name: Registry tool name (diagnostics only).
        command_type: The WS command type from ``TOOL_DISPATCH[tool_name]``.
        build_payload: The registry's payload builder for this tool — the
            single source of truth for argument -> payload mapping. Its
            exceptions (e.g. ``KeyError`` on a missing required argument)
            propagate unwrapped, exactly as on the legacy path.
    """

    def _tool(**kwargs: Any) -> Dict[str, Any]:
        if _transport is None:
            raise RuntimeError(
                f"ws_passthrough transport is not configured — cannot dispatch "
                f"{tool_name!r}. Call configure_transport(fn) at host boot."
            )
        payload = build_payload(kwargs)
        data = _transport(command_type, payload)
        return {DATA_KEY: data}

    _tool.__name__ = f"ws_passthrough_{tool_name}"
    _tool.__qualname__ = _tool.__name__
    # Pinned for parity tests: the ported tool must carry the registry's own
    # command type + payload builder, not a re-implementation.
    _tool.command_type = command_type          # type: ignore[attr-defined]
    _tool.build_payload = build_payload        # type: ignore[attr-defined]
    _tool.tool_name = tool_name                # type: ignore[attr-defined]
    return _tool
