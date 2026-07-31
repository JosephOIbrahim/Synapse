"""F6 (CLEAR P3.1): SessionStart must ping the bridge before reporting connected.

The SessionStart hook used to unconditionally print "Synapse bridge connected."
regardless of whether the Synapse server inside Houdini was actually running --
a lying "connected" signal (the defect class v5.40.1 routed around but did not
fix). The fix gates the "connected" report on a real ping: only report
connected if the ping succeeds, else report disconnected/honest.

The hook is loaded DIRECTLY by path (it is not a package module) and the ping
is mocked, so this runs headless -- no Houdini, no live bridge, no network.

Negative control: the test for the bridge-down case asserts the honest
"not reachable" message is printed AND that the lying "connected." claim is
NOT. Against the unfixed hook (which always prints "Synapse bridge
connected.") that assertion fails -- proving the test exercises the fix.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys

import pytest

_HOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude", "hooks", "synapse_hooks_bridge.py",
)


def _load_hook():
    """Load the hook module fresh by path (no side effects at import time)."""
    spec = importlib.util.spec_from_file_location(
        "synapse_hooks_bridge_under_test", _HOOK_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_session_start(mod, monkeypatch, ping_return):
    """Run the hook's main() with a SessionStart event and a mocked ping.

    Returns (captured_stdout, ping_call_count).
    """
    calls = {"n": 0}

    def fake_ping(*args, **kwargs):
        calls["n"] += 1
        return ping_return

    monkeypatch.setattr(mod, "ping_bridge", fake_ping)

    # Feed a SessionStart hook event on stdin. io.StringIO.isatty() returns
    # False, so read_hook_input() reads it.
    hook_input = {"hook_event_name": "SessionStart"}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(hook_input)))

    # Capture stdout. print() resolves sys.stdout at call time.
    fake_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", fake_stdout)

    mod.main()
    return fake_stdout.getvalue(), calls["n"]


# ---------------------------------------------------------------------------
# Positive: bridge up -> "connected"
# ---------------------------------------------------------------------------
def test_sessionstart_reports_connected_when_ping_succeeds(monkeypatch):
    mod = _load_hook()
    out, n = _run_session_start(mod, monkeypatch, ping_return=True)
    assert n == 1, "ping_bridge must be called before reporting connected"
    assert "Synapse bridge connected." in out


# ---------------------------------------------------------------------------
# Negative control: bridge down -> honest message, NOT "connected."
# Against the unfixed hook this FAILS because the old code always prints
# "Synapse bridge connected." regardless of bridge state.
# ---------------------------------------------------------------------------
def test_sessionstart_reports_disconnected_when_ping_fails(monkeypatch):
    mod = _load_hook()
    out, n = _run_session_start(mod, monkeypatch, ping_return=False)
    assert n == 1, "ping_bridge must be called even when the bridge is down"
    # The honest signal must appear.
    assert "not reachable" in out, (
        f"expected an honest 'not reachable' message, got: {out!r}"
    )
    # The lying "connected" claim must NOT appear.
    assert "Synapse bridge connected." not in out, (
        f"ping failed but hook still reported connected: {out!r}"
    )


# ---------------------------------------------------------------------------
# The ping must actually be invoked. A hook that skips the ping and just
# prints "connected" fails here (call count stays 0).
# ---------------------------------------------------------------------------
def test_ping_is_not_skipped(monkeypatch):
    mod = _load_hook()
    out, n = _run_session_start(mod, monkeypatch, ping_return=True)
    assert n >= 1, (
        "ping_bridge was never called -- the connected report is unguarded"
    )