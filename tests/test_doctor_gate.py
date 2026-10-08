"""The Doctor is never held back by the scene preflight (owner ruling, Joe 2026-10-08 06:11).

With undo off in Houdini, the panel's Doctor button was refused "unrecoverable: Undo is off in
Houdini, so a change could not be undone. The change was not sent." The doctor never touches the
scene and runs off Houdini's main thread (mcp/server.py, W2-S1); it counts as a change only
because ``bundle`` writes a zip under ~/.synapse/diagnostics. Three fixes, pinned here:

1. ``preflight_gate.admit`` lets ``synapse_doctor`` through, as it does farm controls, and a real
   change is still refused. Read-only mode's own fence still refuses the doctor.
2. ``scene.undo_off`` needs the artist; it is not unrecoverable. The next change checks again, so
   turning undo back on clears it.
3. The Doctor dialog says SYNAPSE did not run the check when the failure is a refusal.

Every name that is new in this change is imported inside its test, so on the old code the test
fails rather than the file failing to collect.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from synapse.core import outcomes as O  # noqa: E402
from synapse.core import preflight as PF  # noqa: E402
from synapse.mcp import read_only_mode as RO  # noqa: E402
from synapse.mcp import server as S  # noqa: E402
from synapse.server import preflight_gate as G  # noqa: E402

DOCTOR = "synapse_doctor"
CHANGE = "houdini_set_parm"
UNDO_OFF = {"loading": False, "undo_enabled": False, "hip_path": "C:/show/shot/shot.hip"}


@pytest.fixture(autouse=True)
def _fresh():
    PF.reset()
    yield
    PF.reset()


class Hop:
    """A fake hop onto Houdini's main thread: it counts its calls and answers as told."""

    def __init__(self, facts):
        self.facts = dict(facts)
        self.calls = 0

    def __call__(self, timeout_s):
        self.calls += 1
        return dict(self.facts)


def _houdini(monkeypatch, hop):
    """This process has Houdini, and *hop* is its main thread."""
    monkeypatch.setattr(G, "houdini_hop", lambda: hop)
    return hop


# -- 1. The doctor passes the gate; a real change does not ---------------------------------------

def test_the_doctor_passes_with_undo_off_while_a_real_change_is_refused(monkeypatch):
    hop = _houdini(monkeypatch, Hop(UNDO_OFF))
    holder = SimpleNamespace()
    assert RO.is_change(DOCTOR), "the doctor is a change; the exemption is the gate's, not this"
    assert G.admit(holder, DOCTOR) is None
    assert G.admit(holder, DOCTOR, client_version="0.0.0") is None
    assert hop.calls == 0, "the doctor must not wait on Houdini's main thread"
    assert not hasattr(holder, "preflight_due"), "the doctor must not mark the session ready"

    refused = G.admit(holder, CHANGE)
    assert refused is not None and refused["code"] == "scene.undo_off"
    assert refused["dispatched"] == "no"
    assert getattr(holder, "preflight_due", True) is True
    assert hop.calls == 1


def test_mcp_sends_the_doctor_with_undo_off_and_refuses_the_change(monkeypatch):
    """End to end over POST /mcp, the route the panel's Doctor button takes."""
    hop = _houdini(monkeypatch, Hop(UNDO_OFF))
    doctor = Mock(return_value={"content": [{"type": "text", "text": "{}"}]})
    dispatch = Mock(return_value={"content": [{"type": "text", "text": "{}"}]})
    monkeypatch.setattr(S, "_dispatch_doctor_off_main", doctor)
    monkeypatch.setattr(S, "dispatch_tool", dispatch)
    server = S.MCPServer(handler=SimpleNamespace(handle=Mock()))
    server._enable_resilience = False
    sid = server._sessions.create_session({})

    def call(name, arguments, number):
        body = json.dumps({"jsonrpc": "2.0", "id": number, "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}}).encode()
        reply, _headers = server.handle_request(body, session_id=sid)
        return json.loads(reply)["result"]

    assert not call(DOCTOR, {"bundle": False}, 1).get("isError")
    assert doctor.call_count == 1 and hop.calls == 0
    refused = call(CHANGE, {}, 2)
    assert refused.get("isError") and dispatch.call_count == 0
    assert refused["content"][0]["text"].startswith("needs_artist: Undo is off")


def test_read_only_mode_still_refuses_the_doctor(monkeypatch):
    """The gate's exemption leaves read-only mode's own fence as it was (guard)."""
    monkeypatch.setenv("SYNAPSE_MCP_READ_ONLY", "1")
    assert RO.refusal_for_tool(DOCTOR) is not None


# -- 2. Undo off needs the artist, and clears once undo is back on -------------------------------

def test_undo_off_needs_the_artist_keeps_its_fix_and_is_checked_again(monkeypatch):
    outcome, dispatched, next_step = O.CODES["scene.undo_off"]
    assert outcome is O.Outcome.NEEDS_ARTIST and dispatched == "no"
    assert "undoctrl on" in next_step

    hop = _houdini(monkeypatch, Hop(UNDO_OFF))
    holder = SimpleNamespace()
    refused = G.admit(holder, CHANGE)
    assert refused["outcome"] == "needs_artist" and refused["code"] == "scene.undo_off"
    G.note(holder, refused)  # what /mcp does with every tools/call result, refusals included
    assert getattr(holder, "preflight_due", True) is True

    hop.facts["undo_enabled"] = True
    assert G.admit(holder, CHANGE) is None
    assert hop.calls == 2 and holder.preflight_due is False


# -- 3. The dialog's heading names a refusal -----------------------------------------------------

@pytest.mark.parametrize("message", [
    "needs_artist: Undo is off in Houdini, so a change could not be undone. The change was not "
    "sent. Next: Turn undo back on: run undoctrl on in Houdini's Textport, then send it again.",
    "unrecoverable: Undo is off in Houdini, so a change could not be undone. The change was not sent.",
    "refused: SYNAPSE is in read-only mode, so it was not run.",
    "retryable: SYNAPSE is busy. Next: Wait a moment, then send it again.",
], ids=["needs-artist", "unrecoverable", "read-only", "busy"])
def test_a_refusal_says_synapse_did_not_run_the_check(message):
    from synapse.panel.doctor_dialog import failure_heading

    assert failure_heading(message) == "SYNAPSE did not run the check"


@pytest.mark.parametrize("message", [
    "Tool refused",
    "Timed out; check still running",
    "Couldn't reach the SYNAPSE server. Check that Houdini is running.",
    "unknown_outcome: The reply was lost. Next: Check the scene before trying again.",
    "failed: The doctor raised an error.",
    "The check returned no diagnostic report.",
], ids=["tool-text", "timeout", "unreachable", "unknown-outcome", "failed", "bad-report"])
def test_anything_else_keeps_check_unavailable(message):
    from synapse.panel.doctor_dialog import failure_heading

    assert failure_heading(message) == "SYNAPSE check unavailable"
