"""Port wave scene-1 parity tests (G1, docs/PORT_WAVE_MANIFEST.md).

DoD gate 1 ("basic pass"): for every ported tool, same args -> same
command_type + payload built + response envelope as the legacy
``TOOL_DISPATCH`` path. Both paths are exercised through the REAL
``mcp_server.call_tool`` handler with a recording fake ``send_command``:

  - ported path: the name is in ``mcp_server._PORTED_WAVE_TOOLS`` (as shipped)
    and routes through the cognitive Dispatcher + ws_passthrough transport;
  - legacy path: ``_PORTED_WAVE_TOOLS`` is monkeypatched empty so the same
    call falls through to the legacy TOOL_DISPATCH -> send_command branch.

The wave is read-only/file-only (pilot wave) so parity goldens are pure
assertion — no scene mutation, no render, no cook.

Anti-test-theater notes:
  - The recorder pins the (command_type, payload) actually sent over the
    transport, not a mock of the port itself.
  - Envelope comparisons are byte-for-byte on the TextContent text.
  - test_ported_path_actually_uses_dispatcher proves the ported branch fired
    (the Dispatcher singleton is built by the ported path and ONLY by it).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import mcp_server  # noqa: E402
from synapse.cognitive.tools import ws_passthrough  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DISPATCH  # noqa: E402


# ---------------------------------------------------------------------------
# Wave inventory — pinned literally (the frozen manifest contract, not a read
# of the code under test).
# ---------------------------------------------------------------------------

SCENE1_WAVE = {
    "synapse_ping": "ping",
    "synapse_health": "get_health",
    "synapse_doctor": "doctor",
    "houdini_scene_info": "get_scene_info",
    "houdini_get_selection": "get_selection",
    "houdini_get_parm": "get_parm",
    "synapse_inspect_selection": "inspect_selection",
    "synapse_inspect_scene": "inspect_scene",
    "synapse_inspect_node": "inspect_node",
    "houdini_network_explain": "network_explain",
    "synapse_write_report": "write_report",
}

# Representative args per tool + the EXACT payload the registry builder must
# produce (pins payload-builder semantics: passthrough / identity / key filter
# / root_path->node rename).
PARITY_CASES = [
    ("synapse_ping", {}, {}),
    ("synapse_health", {}, {}),
    ("synapse_doctor", {"bundle": True}, {"bundle": True}),
    ("synapse_doctor", {}, {}),
    ("houdini_scene_info", {}, {}),
    ("houdini_get_selection", {}, {}),
    ("houdini_get_parm",
     {"node": "/obj/geo1", "parm": "tx"},
     {"node": "/obj/geo1", "parm": "tx"}),
    # _filter_keys: unknown keys must NOT reach the payload
    ("houdini_get_parm",
     {"node": "/obj/geo1", "parm": "tx", "stray": 1},
     {"node": "/obj/geo1", "parm": "tx"}),
    ("synapse_inspect_selection", {"depth": 2}, {"depth": 2}),
    ("synapse_inspect_scene",
     {"root": "/obj", "max_depth": 2, "context_filter": "Sop"},
     {"root": "/obj", "max_depth": 2, "context_filter": "Sop"}),
    ("synapse_inspect_node",
     {"node": "/obj/geo1", "include_code": False, "include_geometry": True},
     {"node": "/obj/geo1", "include_code": False, "include_geometry": True}),
    # root_path -> node rename
    ("houdini_network_explain",
     {"root_path": "/obj/geo1", "depth": 3, "format": "structured"},
     {"depth": 3, "format": "structured", "node": "/obj/geo1"}),
    ("synapse_write_report",
     {"relative_path": "audit/r.md", "content": "hello", "overwrite": False},
     {"relative_path": "audit/r.md", "content": "hello", "overwrite": False}),
]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_port_state():
    """The ported Dispatcher singleton binds the event loop it was built on;
    every test runs in a fresh asyncio.run loop, so reset it (and the injected
    transport) around each test — same hygiene as the Inspector's
    _inspector_cleanup_transport fixture."""
    mcp_server._ported_dispatcher = None
    ws_passthrough.reset_transport()
    yield
    mcp_server._ported_dispatcher = None
    ws_passthrough.reset_transport()


class _RecordingSend:
    """Fake mcp_server.send_command: records (cmd_type, payload), then returns
    canned data or raises the configured exception — identically for both
    dispatch paths."""

    def __init__(self, data=None, exc=None):
        self.calls = []
        self.data = data
        self.exc = exc

    async def __call__(self, cmd_type, payload=None):
        # Copy: the assertion must see what was SENT, not later mutations.
        self.calls.append((cmd_type, dict(payload) if payload is not None else payload))
        if self.exc is not None:
            raise self.exc
        return self.data


def _run_both_paths(monkeypatch, name, args, *, data=None, exc=None):
    """Invoke the real call_tool via the ported path, then via the legacy
    path, with an identical fake transport. Returns
    (ported_result, ported_calls, legacy_result, legacy_calls)."""
    recorder = _RecordingSend(data=data, exc=exc)
    monkeypatch.setattr(mcp_server, "send_command", recorder)

    # Ported path (fresh singleton for this loop).
    mcp_server._ported_dispatcher = None
    ported = asyncio.run(mcp_server.call_tool(name, dict(args)))
    ported_calls = list(recorder.calls)
    recorder.calls.clear()

    # Legacy path: empty the interception set so the SAME name falls through
    # to the TOOL_DISPATCH -> send_command branch.
    monkeypatch.setattr(mcp_server, "_PORTED_WAVE_TOOLS", frozenset())
    legacy = asyncio.run(mcp_server.call_tool(name, dict(args)))
    legacy_calls = list(recorder.calls)

    return ported, ported_calls, legacy, legacy_calls


def _texts(result):
    """Flatten a call_tool result to comparable (type, text) tuples."""
    return [(c.type, c.text) for c in result]


# ---------------------------------------------------------------------------
# Inventory pins
# ---------------------------------------------------------------------------

def test_wave_inventory_pinned():
    """The shipped interception set is exactly the manifest's scene-1 wave."""
    assert mcp_server._PORTED_WAVE_TOOLS == frozenset(SCENE1_WAVE), (
        "scene-1 interception set drifted from the PORT_WAVE_MANIFEST wave "
        f"(symmetric diff: {sorted(mcp_server._PORTED_WAVE_TOOLS ^ set(SCENE1_WAVE))})"
    )


def test_wave_tools_still_in_registry():
    """Definitions never move (manifest non-goal): every ported tool stays in
    TOOL_DISPATCH with its frozen command_type."""
    for name, cmd_type in SCENE1_WAVE.items():
        assert name in TOOL_DISPATCH, f"{name} missing from TOOL_DISPATCH"
        assert TOOL_DISPATCH[name][0] == cmd_type, (
            f"{name}: command_type drifted "
            f"({TOOL_DISPATCH[name][0]!r} != {cmd_type!r})"
        )


def test_image_tools_not_in_wave():
    """The ImageContent special-case tools must not be intercepted until the
    render wave ports the image envelope (PORT_WAVE_MANIFEST adapter table)."""
    assert not ({"houdini_capture_viewport", "houdini_render"}
                & mcp_server._PORTED_WAVE_TOOLS)


def test_ported_tools_reuse_registry_builders():
    """OD-2(a) wrap: the passthrough tools must carry the registry's OWN
    payload builders and command types — not re-implementations."""
    async def _build():
        return mcp_server._get_ported_dispatcher()

    dispatcher = asyncio.run(_build())
    for name in SCENE1_WAVE:
        assert dispatcher.is_registered(name), f"{name} not registered"
        tool = dispatcher._tools[name]
        cmd_type, build_payload = TOOL_DISPATCH[name]
        assert tool.command_type == cmd_type
        assert tool.build_payload is build_payload, (
            f"{name}: ported tool does not use the registry payload builder"
        )


# ---------------------------------------------------------------------------
# Parity: command_type + payload + success envelope (per tool)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,args,expected_payload", PARITY_CASES,
                         ids=[f"{c[0]}-{i}" for i, c in enumerate(PARITY_CASES)])
def test_parity_command_payload_and_success_envelope(
        monkeypatch, name, args, expected_payload):
    data = {"ok": True, "tool": name, "value": [1, 2, {"k": "v"}]}
    ported, ported_calls, legacy, legacy_calls = _run_both_paths(
        monkeypatch, name, args, data=data)

    # Same command_type + payload as the legacy path, and both equal the
    # pinned expectation (not merely equal to each other).
    assert ported_calls == legacy_calls == [(SCENE1_WAVE[name], expected_payload)]

    # Same response envelope, byte for byte.
    assert _texts(ported) == _texts(legacy)
    assert ported[0].type == "text"
    assert ported[0].text == mcp_server._dumps_str(data)


def test_success_envelope_non_dict_data(monkeypatch):
    """WS response data is Any-typed (SynapseResponse.data) — a non-dict data
    payload must survive the Dispatcher's dict-only contract via the
    ws_passthrough wrapper and serialize exactly as the legacy path did."""
    data = ["plain", "list", 42]
    ported, _, legacy, _ = _run_both_paths(
        monkeypatch, "synapse_ping", {}, data=data)
    assert _texts(ported) == _texts(legacy)
    assert ported[0].text == mcp_server._dumps_str(data)


# ---------------------------------------------------------------------------
# Parity: error envelopes (the legacy except-clause routing)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("exc,expected_text", [
    (ConnectionError("Houdini might not be running"),
     "Couldn't reach Synapse — Houdini might not be running"),
    (ConnectionRefusedError("refused"),
     "Couldn't reach Synapse — refused"),
    (RuntimeError("Node not found: /obj/nope"),
     "Synapse hit a snag: Node not found: /obj/nope"),
    (TimeoutError("The ping command took too long to respond"),
     "Something unexpected happened: The ping command took too long to respond"),
    (ValueError("bad value"),
     "Something unexpected happened: bad value"),
], ids=["connection", "connection-subclass", "runtime", "timeout", "generic"])
def test_parity_error_envelopes(monkeypatch, exc, expected_text):
    ported, _, legacy, _ = _run_both_paths(
        monkeypatch, "synapse_ping", {}, exc=exc)
    assert _texts(ported) == _texts(legacy)
    assert ported[0].text == expected_text


def test_parity_missing_required_arg(monkeypatch):
    """A payload builder KeyError (missing required arg) must produce the
    identical generic envelope on both paths — and never reach the wire."""
    ported, ported_calls, legacy, legacy_calls = _run_both_paths(
        monkeypatch, "houdini_network_explain", {})
    assert ported_calls == legacy_calls == []
    assert _texts(ported) == _texts(legacy)
    assert ported[0].text == "Something unexpected happened: 'root_path'"


# ---------------------------------------------------------------------------
# The ported branch really is the Dispatcher path (not test theater)
# ---------------------------------------------------------------------------

def test_ported_path_actually_uses_dispatcher(monkeypatch):
    """The Dispatcher singleton is built by the ported branch and ONLY by it:
    a ported call constructs it; a legacy fall-through call never does."""
    recorder = _RecordingSend(data={"ok": True})
    monkeypatch.setattr(mcp_server, "send_command", recorder)

    # Legacy fall-through first: singleton stays unbuilt.
    monkeypatch.setattr(mcp_server, "_PORTED_WAVE_TOOLS", frozenset())
    asyncio.run(mcp_server.call_tool("synapse_ping", {}))
    assert mcp_server._ported_dispatcher is None

    # Ported call: singleton is built and the tool is registered on it.
    monkeypatch.setattr(mcp_server, "_PORTED_WAVE_TOOLS",
                        frozenset(SCENE1_WAVE))
    asyncio.run(mcp_server.call_tool("synapse_ping", {}))
    assert mcp_server._ported_dispatcher is not None
    for name in SCENE1_WAVE:
        assert mcp_server._ported_dispatcher.is_registered(name)


def test_unknown_tool_envelope_unchanged(monkeypatch):
    """A name outside both the wave and the registry keeps the legacy
    'unknown tool' envelope."""
    recorder = _RecordingSend(data={})
    monkeypatch.setattr(mcp_server, "send_command", recorder)
    result = asyncio.run(mcp_server.call_tool("synapse_not_a_tool", {}))
    assert _texts(result) == [(
        "text",
        "I don't recognize the tool 'synapse_not_a_tool' — "
        "check the available tools list",
    )]
    assert recorder.calls == []


# ---------------------------------------------------------------------------
# ws_passthrough module unit surface
# ---------------------------------------------------------------------------

def test_ws_passthrough_wrap_unwrap_roundtrip():
    tool = ws_passthrough.make_passthrough_tool(
        "t", "cmd", lambda args: dict(args))
    seen = []
    ws_passthrough.configure_transport(
        lambda cmd, payload: seen.append((cmd, payload)) or {"echo": payload})
    out = tool(a=1)
    assert seen == [("cmd", {"a": 1})]
    assert ws_passthrough.unwrap_ws_data(out) == {"echo": {"a": 1}}


def test_ws_passthrough_unconfigured_transport_raises():
    tool = ws_passthrough.make_passthrough_tool(
        "t", "cmd", lambda args: dict(args))
    ws_passthrough.reset_transport()
    with pytest.raises(RuntimeError, match="transport is not configured"):
        tool()


def test_ws_passthrough_transport_exceptions_unwrapped():
    """The transport contract: original exception classes propagate — the
    envelope mapping depends on the class name surviving intact."""
    tool = ws_passthrough.make_passthrough_tool(
        "t", "cmd", lambda args: dict(args))

    def _boom(cmd, payload):
        raise ConnectionError("down")

    ws_passthrough.configure_transport(_boom)
    with pytest.raises(ConnectionError, match="down"):
        tool()
