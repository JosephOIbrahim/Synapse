"""Port-wave passthrough hygiene — scene-1 crucible follow-ups W.7 + W.8.

W.7 (BW-1, sev-3): the port-wave sync transport's outer watchdog under-budgeted
``send_command``'s two-attempt retry. Above ~72 s per-command (render 120,
tops_batch_cook 300, render_sequence 600) the old ``cmd_timeout + 60`` cap sat
BELOW send_command's worst case (~2x per-command), so the watchdog would fire
first: cancel a legitimately-reconnecting command mid-flight, misreport the
connection failure as a generic timeout, and — because the injected
CancelledError bypasses send_command's except-branch cleanup — leak the in-flight
``_pending`` entry. Fix: single-source the budget (``transport_outer_budget`` =
``2 * cmd_timeout + 75``) and pop ``_pending`` in a ``finally``.

W.8 (BW-2, sev-2): ``_ported_error_text`` resolves the exception class by NAME
against ``builtins`` (not ``isinstance`` on a live object). That is faithful ONLY
because send_command's entire raise surface is builtin exceptions — a conformance
this file pins so a future non-builtin raise fails loud instead of silently
degrading the ported error envelope to generic.

Pure-Python: no ``hou``, no live bridge, no wall-clock waits (the watchdog test
shrinks the budget rather than sleeping through it).
"""

from __future__ import annotations

import ast
import asyncio
import builtins
import inspect
import sys
import textwrap
from pathlib import Path

import pytest

# mcp_server lives at the repo ROOT (not under python/), so ensure it is
# importable exactly as tests/test_port_wave_scene1.py does.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import mcp_server  # noqa: E402
from synapse.cognitive.tools import ws_passthrough  # noqa: E402
from synapse.core.timeouts import (  # noqa: E402
    SEND_COMMAND_MAX_ATTEMPTS,
    SLOW_COMMANDS,
    timeout_for,
    transport_outer_budget,
)


# ---------------------------------------------------------------------------
# W.7 — outer-watchdog budget covers send_command's 2-attempt worst case
# ---------------------------------------------------------------------------

# The slice where the OLD budget (cmd_timeout + 60) actually breached: any
# command slower than 60 s, where cmd_timeout + 60 < 2 * cmd_timeout. The
# verdict names 72 s as the breach threshold (render/tops/sequence live here).
_SLOW_OVER_72 = sorted(c for c, t in SLOW_COMMANDS.items() if t > 72.0)


def test_breach_slice_is_non_empty():
    """Guards the parametrization below: the >72 s commands the fix targets
    (render 120, tops_batch_cook 300, render_sequence 600) must exist."""
    assert {"render", "tops_batch_cook", "render_sequence"} <= set(_SLOW_OVER_72)


@pytest.mark.parametrize("cmd", _SLOW_OVER_72)
def test_outer_budget_exceeds_send_command_worst_case(cmd):
    per = timeout_for(cmd)
    outer = transport_outer_budget(cmd)
    # send_command retries once, so its worst case is ~SEND_COMMAND_MAX_ATTEMPTS
    # * per; the watchdog must exceed that or it pre-empts the retry.
    assert outer >= SEND_COMMAND_MAX_ATTEMPTS * per
    # ...and the OLD budget was demonstrably too small for this slice.
    assert per + 60.0 < SEND_COMMAND_MAX_ATTEMPTS * per


@pytest.mark.parametrize("cmd,per,expected_outer", [
    ("render", 120.0, 315.0),          # 2*120 + 75
    ("tops_batch_cook", 300.0, 675.0),  # 2*300 + 75
    ("render_sequence", 600.0, 1275.0), # 2*600 + 75
])
def test_outer_budget_named_commands(cmd, per, expected_outer):
    assert timeout_for(cmd) == per
    assert transport_outer_budget(cmd) == expected_outer


def test_outer_budget_keys_like_timeout_for():
    """The watchdog budget must key on MCP tool names too (prefix-stripping),
    not just raw command types — the transport is called with command types but
    the budget helper should stay drop-in with timeout_for()."""
    assert transport_outer_budget("houdini_render") == transport_outer_budget("render")
    # Unknown name -> default per-command -> 2*default + reconnect.
    assert transport_outer_budget("totally_unknown_cmd") == transport_outer_budget(
        "any_other_unknown")


# ---------------------------------------------------------------------------
# W.7 — the not-done/cancel branch of _sync_transport (previously zero coverage)
# ---------------------------------------------------------------------------

def test_sync_transport_outer_watchdog_cancels_and_reports_friendly(monkeypatch):
    """When the outer watchdog trips while send_command is still running (fut
    not done), _sync_transport cancels the coroutine and raises the friendly
    timeout message — not send_command's own passthrough. Exercises the branch
    the >72 s under-budget used to hit for real."""
    async def _hang(cmd_type, payload=None):
        await asyncio.sleep(3600)  # block until the watchdog cancels us

    monkeypatch.setattr(mcp_server, "send_command", _hang)
    # Shrink the watchdog so the branch fires immediately; real budget for
    # 'render' is 315 s. We assert the BRANCH, not the wall-clock value.
    monkeypatch.setattr(mcp_server, "_transport_outer_budget", lambda name: 0.15)

    async def _drive():
        mcp_server._ported_dispatcher = None
        mcp_server._get_ported_dispatcher()  # builds + wires the _sync_transport closure
        transport = ws_passthrough._transport
        assert transport is not None, "port-wave transport was not configured"
        # _sync_transport marshals back onto THIS loop, so it must run off-loop.
        return await asyncio.to_thread(transport, "render", {})

    with pytest.raises(TimeoutError, match="took too long to respond"):
        asyncio.run(_drive())


def test_send_command_pops_pending_on_cancellation(monkeypatch):
    """W.7(b): an outside cancellation (what the watchdog's fut.cancel() injects)
    raises CancelledError inside send_command — a BaseException none of its
    except branches catch. The finally must still pop the _pending entry so it
    can't leak. Without the fix this leaves a dangling _pending[command_id]."""
    class _FakeWS:
        async def send(self, _msg):
            return None

        async def close(self):
            return None

    async def _fake_get_conn():
        return _FakeWS()

    monkeypatch.setattr(mcp_server, "_get_connection", _fake_get_conn)

    async def _drive():
        mcp_server._pending.clear()
        # 'render' -> cmd_timeout 120 s, so send_command parks on
        # asyncio.wait(...) long enough for us to cancel it mid-flight.
        task = asyncio.ensure_future(mcp_server.send_command("render", {}))
        # Let it register its _pending future and reach the inner wait.
        for _ in range(100):
            await asyncio.sleep(0)
            if mcp_server._pending:
                break
        assert len(mcp_server._pending) == 1, "send_command never registered its future"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return dict(mcp_server._pending)

    remaining = asyncio.run(_drive())
    assert remaining == {}, "send_command leaked a _pending entry on cancellation"


# ---------------------------------------------------------------------------
# W.8(a) — _ported_error_text NAME-resolution vs send_command's raise surface
# ---------------------------------------------------------------------------

def _mk_err(error_type: str, message: str = "boom") -> "mcp_server._AgentToolError":
    return mcp_server._AgentToolError(
        tool_name="synapse_ping", error_type=error_type,
        error_message=message, traceback_str="",
    )


def test_ported_error_text_routes_send_command_builtin_surface():
    """send_command's entire raise surface is builtins (ConnectionError /
    RuntimeError / TimeoutError). _ported_error_text resolves the recorded class
    NAME against builtins, so each routes to its legacy envelope — proving the
    NAME approach reproduces the legacy isinstance routing for the real surface."""
    assert (mcp_server._ported_error_text(_mk_err("ConnectionError", "down"))
            == "Couldn't reach Synapse — down")
    # A builtin ConnectionError SUBCLASS still resolves + routes (isinstance parity).
    assert (mcp_server._ported_error_text(_mk_err("ConnectionRefusedError", "no"))
            == "Couldn't reach Synapse — no")
    assert (mcp_server._ported_error_text(_mk_err("RuntimeError", "snag"))
            == "Synapse hit a snag: snag")
    # TimeoutError is an OSError sibling (not ConnectionError/RuntimeError), so it
    # falls to generic on BOTH the ported and legacy paths — parity, not a bug.
    assert (mcp_server._ported_error_text(_mk_err("TimeoutError", "slow"))
            == "Something unexpected happened: slow")


def test_ported_error_text_custom_subclass_diverges_to_generic():
    """The BW-2 divergence, pinned: _ported_error_text resolves by NAME, not
    isinstance on a live object, so a CUSTOM RuntimeError/ConnectionError subclass
    (name absent from builtins) falls through to the generic envelope where the
    legacy isinstance path would have matched the base. This is safe ONLY because
    send_command never raises such a subclass (see the raise-surface pin below);
    if that ever changes, the ported envelope silently degrades."""
    assert (mcp_server._ported_error_text(_mk_err("StudioConnError", "x"))
            == "Something unexpected happened: x")
    assert (mcp_server._ported_error_text(_mk_err("MyCustomRuntimeError", "y"))
            == "Something unexpected happened: y")


def test_send_command_raise_surface_is_builtin():
    """Conformance pin (W.8a): every exception send_command RAISES is a builtin
    exception whose class NAME resolves via getattr(builtins, name). That is the
    invariant _ported_error_text's NAME-based routing depends on — a non-builtin
    raise here would make the ported error envelope silently degrade to generic.
    Static AST scan so it fails loud on a future edit, with no runtime needed."""
    src = textwrap.dedent(inspect.getsource(mcp_server.send_command))
    tree = ast.parse(src)
    raised: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc
            if isinstance(exc, ast.Call):  # raise X(...) -> unwrap to the callable
                exc = exc.func
            if isinstance(exc, ast.Name):
                raised.add(exc.id)
            elif isinstance(exc, ast.Attribute):  # e.g. asyncio.TimeoutError
                raised.add(exc.attr)
    assert raised, "no raises found in send_command — the AST scan is broken"
    for name in sorted(raised):
        obj = getattr(builtins, name, None)
        assert isinstance(obj, type) and issubclass(obj, BaseException), (
            f"send_command raises {name!r}, which is NOT a builtin exception. "
            "_ported_error_text() resolves the class by name against builtins, so "
            "a non-builtin raise silently degrades the ported error envelope to "
            "generic. Keep send_command's raise surface builtin, or update "
            "_ported_error_text to route the new type."
        )
