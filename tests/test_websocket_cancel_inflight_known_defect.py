"""H6 probe (R302 rank 3) — cancel is queued BEHIND an in-flight op. KNOWN DEFECT.

THE GAP THIS FILE PINS. P3.3 (9c9bc8e) fixed the PARKED-IN-RECV half of the
07-27 report's finding: ``iter_messages`` polls ``recv(timeout=...)`` and
re-checks a per-connection cancel event, so a cancel reaches a loop that is
waiting for its NEXT message. tests/test_websocket_cancel_reachable.py proves
exactly that — but it stubs ``_handle_message`` (line 157), which is what hid
the OTHER half: the loop body at websocket.py:546-559 dispatches
``self._handle_message(...)`` INLINE, so while a long-running op is executing
(a render, a heavy cook — 30s+), the loop is not in recv at all. Every later
message on that connection — INCLUDING a cancellation command — sits unread
in the socket until the in-flight op returns. The cancel EVENT half-works
(it is only observed at frame boundaries); the cancel COMMAND is strictly
serialized behind the op it is trying to cancel.

These tests drive the REAL ``_handle_message`` (nothing stubbed at the server
layer; only the handler BELOW it is a recording stub, which is the layer the
existing suite already fakes) and PIN the current behavior with honest names.
They are the runnable reproduction for the R303 reopen decision — NOT a fix.
If someone lands a control-plane/data-plane split (H6 fix half, C4 rank 10),
these tests FAIL and must be rewritten as the positive claims.
"""

import threading
import time
import types

import pytest

from synapse.core.protocol import SynapseCommand, SynapseResponse
from synapse.server.websocket import SynapseServer

from websockets.exceptions import ConnectionClosedOK


# =============================================================================
# Fakes — fake websocket mirrors test_websocket_cancel_reachable's fixture
# =============================================================================

class _FakeWebSocket:
    """Cancel-aware ``recv(timeout=...)`` (the post-P3.3 contract); signals
    ``parked`` while blocking on the next message. Messages queued upfront
    model frames already sitting in the socket buffer."""

    def __init__(self, cancel_event, messages=None):
        self._cancel = cancel_event
        self._messages = list(messages or [])
        self._lock = threading.Lock()
        self.parked = threading.Event()
        self.closed = False
        self.sent = []
        self.request = types.SimpleNamespace(headers={"Origin": ""})

    def queued_messages(self):
        with self._lock:
            return list(self._messages)

    def recv(self, timeout=None):
        with self._lock:
            if self._messages:
                return self._messages.pop(0)
        self.parked.set()
        try:
            if self._cancel.wait(timeout=timeout):
                self.closed = True
                raise ConnectionClosedOK(None, None)
            raise TimeoutError("no message within poll window")
        finally:
            self.parked.clear()

    def send(self, data):
        self.sent.append(data)

    def close(self, *args, **kwargs):
        self.closed = True


class _FakeBridge:
    def start_session(self, client_id):
        return "test-session-id"

    def get_session(self, session_id):
        return None

    def end_session(self, session_id):
        return ""

    def get_session_summary(self, session_id):
        return ""


class _RecordingHandler:
    """The layer BELOW _handle_message (same layer the existing suite fakes).

    ``handle`` records dispatch order; a ``render`` command BLOCKS on
    ``release`` — the in-flight long op. ``render_farm_cancel`` (classified
    read-only at handlers.py:226 precisely so it can't block behind the
    render at the MARSHAL layer) returns immediately — the point pinned
    here is that the CONNECTION loop serializes it anyway."""

    def __init__(self):
        self.seen = []  # (event, command_type) tuples, loop-thread only
        self.entered = threading.Event()
        self.release = threading.Event()

    def set_session_id(self, session_id):
        pass

    def set_user_id(self, user_id):
        pass

    def set_metrics_aggregator(self, agg):
        pass

    def handle(self, command):
        self.seen.append(("enter", command.type))
        if command.type == "render":
            self.entered.set()
            # The in-flight op: parks the CONNECTION loop inside
            # _handle_message. 30s guard so a hang fails loudly, not forever.
            self.release.wait(30)
        self.seen.append(("exit", command.type))
        return SynapseResponse(id=command.id, success=True, data={})


def _make_probe_server(handler):
    """Bare SynapseServer with the REAL _handle_message left in place.

    Mirrors test_websocket_cancel_reachable._make_minimal_server but does NOT
    stub _handle_message — that stub is what hid this defect. The extra
    attributes are the ones the real _handle_message dereferences."""
    server = object.__new__(SynapseServer)
    server._clients_lock = threading.Lock()
    server._clients = set()
    server._client_sessions = {}
    server._client_ids = {}
    server._client_counter = 0
    server._client_cancels = {}
    server._on_client_connect = None
    server._on_client_disconnect = None
    server._deploy_config = None  # local mode -> origin/auth skipped path
    server._handler = handler
    server._session_manager = None
    server._user_directory = {}
    server._rate_limiter = None
    # Real _handle_message dereferences these:
    server._enable_resilience = False
    server._circuit_breaker = None
    server._avg_latency = 0.0
    server._latency_alpha = 0.1
    return server


def _cmd(cmd_type, cmd_id):
    return SynapseCommand(type=cmd_type, id=cmd_id).to_json()


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setattr(
        "synapse.server.websocket.get_bridge", lambda: _FakeBridge()
    )
    monkeypatch.delenv("SYNAPSE_DEPLOY_MODE", raising=False)  # RBAC off
    handler = _RecordingHandler()
    server = _make_probe_server(handler)
    return server, handler


def _start_client(server, messages):
    cancel_event = threading.Event()
    ws = _FakeWebSocket(cancel_event, messages=messages)

    t = threading.Thread(
        target=lambda: server._handle_client(ws), daemon=True)
    t.start()
    return ws, t


# =============================================================================
# KNOWN DEFECT 1 — a cancel COMMAND on the same connection is strictly
# serialized behind the in-flight op it is trying to cancel.
# =============================================================================

def test_cancel_is_queued_behind_inflight_op_KNOWN_DEFECT(probe):
    """CURRENT BEHAVIOR, pinned honestly: websocket.py's recv loop dispatches
    _handle_message INLINE (:546-559), so a cancellation command sent while
    an op is in flight is not even READ off the socket until the op returns.
    The artist's cancel waits for the very work it is cancelling
    (docs/reviews/synapse-latency-report-2026-07-27.md:41, H6). A fix
    (control-plane lane / data-plane worker) makes this test FAIL — rewrite
    it as the positive claim then."""
    server, handler = probe
    slow_frame = _cmd("render", "op-1")
    cancel_frame = _cmd("render_farm_cancel", "cancel-1")
    ws, t = _start_client(server, [slow_frame, cancel_frame])

    # Deterministic: the slow op is IN FLIGHT (loop thread parked in our
    # handler, release not set).
    assert handler.entered.wait(timeout=5.0), (
        "slow op never reached the handler")

    # THE DEFECT: the cancel frame has not even been read off the socket —
    # the loop thread is provably inside handler.handle (entered set,
    # release unset), so it cannot be in recv.
    assert handler.seen == [("enter", "render")]
    assert ws.queued_messages() == [cancel_frame], (
        "cancel frame should still be sitting unread in the socket queue "
        "while the op it cancels is in flight — if this changed, the "
        "serialization defect may have been fixed; rewrite this test")

    # Let the in-flight op finish; ONLY THEN is the cancel dispatched.
    handler.release.set()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if ("exit", "render_farm_cancel") in handler.seen:
            break
        time.sleep(0.005)

    assert handler.seen == [
        ("enter", "render"),
        ("exit", "render"),
        ("enter", "render_farm_cancel"),
        ("exit", "render_farm_cancel"),
    ], (
        "pinned serialization order changed — the cancel was dispatched "
        "concurrently with (or before) the in-flight op; if that is a real "
        "fix, rewrite this KNOWN_DEFECT test as the positive claim"
    )

    # Cleanly end the connection loop.
    server.request_cancel(ws)
    t.join(timeout=5.0)
    assert not t.is_alive()


# =============================================================================
# KNOWN DEFECT 2 — the P3.3 cancel EVENT is observed only at frame
# boundaries: set mid-op, it takes effect after the op returns.
# =============================================================================

def test_request_cancel_midop_takes_effect_only_after_op_returns_KNOWN_DEFECT(
        probe):
    """CURRENT BEHAVIOR, pinned honestly: request_cancel() (the P3.3 fix)
    interrupts a loop PARKED IN RECV, but a loop blocked inside
    _handle_message observes the event only when the in-flight op returns.
    The half-fixed state: event reachable between frames, unreachable
    mid-op. (What the event CAN do mid-op is already covered by
    test_websocket_cancel_reachable; this pins what it CANNOT do.)"""
    server, handler = probe
    slow_frame = _cmd("render", "op-1")
    after_frame = _cmd("ping", "after-1")  # must NEVER run after the cancel
    ws, t = _start_client(server, [slow_frame, after_frame])

    assert handler.entered.wait(timeout=5.0)

    # Cancel MID-OP via the public P3.3 API.
    server.request_cancel(ws)

    # The loop cannot exit: its thread is blocked inside handler.handle
    # (structural — release is not set). The bounded join documents it.
    t.join(timeout=0.2)
    assert t.is_alive(), (
        "loop exited while the op was still in flight — mid-op cancel "
        "became reachable; rewrite this KNOWN_DEFECT test as the positive "
        "claim")
    assert handler.seen == [("enter", "render")]

    # Op returns -> the event is finally observed at the frame boundary:
    # the loop exits WITHOUT processing the already-queued next frame.
    handler.release.set()
    t.join(timeout=5.0)
    assert not t.is_alive(), "loop did not exit after the op returned"
    assert handler.seen == [("enter", "render"), ("exit", "render")]
    assert ws.queued_messages() == [after_frame], (
        "the queued post-cancel frame must remain unprocessed")
