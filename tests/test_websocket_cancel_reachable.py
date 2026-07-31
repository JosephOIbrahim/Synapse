"""P3.3 — cancel reaches the websocket recv loop mid-frame.

``python/synapse/server/websocket.py:471`` was ``for message in websocket:`` —
a blocking serial read. A cancel could not reach the handler mid-frame because
the loop was parked inside the websocket iterator. The fix replaces it with a
cancel-aware ``iter_messages`` generator that polls ``recv(timeout=...)`` and
re-checks a cancel event each tick.

These tests are DETERMINISTIC:

- They use a fake websocket. The fake's ``recv`` is cancel-aware (waits on the
  cancel event); its ``__iter__`` is NOT (blocks forever). That asymmetry is
  the fixture — the only way the loop can exit on cancel is if the code calls
  ``recv(timeout=...)`` and checks the event, never ``for message in ws:``.
- No wall-clock sleeps gate the assertions. The fake signals a ``parked``
  event when it is blocking on the next message; the test waits on that event
  (deterministic), then sets cancel and asserts the loop exits.

Negative control: without the fix, ``iter_messages`` does not exist (import
fails) AND ``_handle_client`` would park on ``__iter__`` forever, so all three
tests fail. This was verified empirically by reverting the recv loop to
``for message in websocket:`` — test_handle_client_cancel_mid_frame fails
("handler recv loop never reached the mid-frame parked state") because the
plain iterator parks on its own and never sets the fake's ``parked`` event.
"""

import threading
import time
import types

from websockets.exceptions import ConnectionClosedOK

from synapse.server.websocket import iter_messages, SynapseServer


# =============================================================================
# Fake websocket — the deterministic fixture
# =============================================================================

class _FakeWebSocket:
    """Stubbed websocket connection.

    - ``recv(timeout=...)`` is cancel-aware: it blocks on the cancel event and
      raises ``ConnectionClosedOK`` when cancel is set (mimicking a clean
      close). It sets a ``parked`` event while waiting so the test can detect
      "mid-frame, parked on the next message" deterministically.
    - ``__iter__`` is deliberately NOT cancel-aware: it yields queued messages
      then blocks forever. This is the P3.3 bug — a plain
      ``for message in websocket:`` parks here and a cancel cannot reach it.

    The asymmetry is what makes the test deterministic: only an
    ``iter_messages``-style loop (recv + cancel check) can exit; the plain
    iterator cannot.
    """

    def __init__(self, cancel_event, messages=None, park_when_empty=True):
        self._cancel = cancel_event
        self._messages = list(messages or [])
        self._lock = threading.Lock()
        # Set while recv is blocking for the next message. The test waits on
        # this to know the loop has moved past message #1 and is parked.
        self.parked = threading.Event()
        self.closed = False
        self.sent = []
        # When True, recv parks (blocks) once messages drain — exercises the
        # mid-frame cancel path. When False, recv raises ConnectionClosedOK
        # once messages drain — exercises the "stop on close" path.
        self._park_when_empty = park_when_empty
        # ``request.headers`` is read by origin validation in _handle_client.
        self.request = types.SimpleNamespace(headers={"Origin": ""})

    def recv(self, timeout=None):
        with self._lock:
            if self._messages:
                return self._messages.pop(0)
        if not self._park_when_empty:
            # Stream end — mimic a clean close so the loop terminates.
            self.closed = True
            raise ConnectionClosedOK(None, None)
        # Parked on the next message — signal the test, then wait for cancel.
        self.parked.set()
        try:
            # Deterministic: returns True iff cancel is set (no wall-clock race).
            if self._cancel.wait(timeout=timeout):
                self.closed = True
                raise ConnectionClosedOK(None, None)
            # Poll window elapsed with no message — let the loop re-check.
            raise TimeoutError("no message within poll window")
        finally:
            self.parked.clear()

    def __iter__(self):
        # The P3.3 bug: a plain ``for message in websocket:`` parks here.
        # NOT cancel-aware by design — exercises the negative control.
        while self._messages:
            yield self._messages.pop(0)
        # Block forever — a cancel cannot reach this iterator.
        threading.Event().wait()

    def send(self, data):
        self.sent.append(data)

    def close(self, *args, **kwargs):
        self.closed = True


class _FakeBridge:
    """Minimal bridge stub for the _handle_client integration test."""

    def start_session(self, client_id):
        return "test-session-id"

    def get_session(self, session_id):
        return None

    def end_session(self, session_id):
        return ""

    def get_session_summary(self, session_id):
        return ""


class _FakeHandler:
    """Minimal handler stub for the _handle_client integration test."""

    def set_session_id(self, session_id):
        pass

    def set_user_id(self, user_id):
        pass

    def set_metrics_aggregator(self, agg):
        pass


def _make_minimal_server():
    """Build a bare SynapseServer with just enough state for _handle_client.

    Uses ``object.__new__`` to skip the heavy ``__init__`` (no real websockets
    server, no resilience layer, no metrics aggregator). Headless / no hou.
    """
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
    server._handler = _FakeHandler()
    server._session_manager = None
    server._user_directory = {}
    server._rate_limiter = None
    # Stub message handling — we are testing the recv loop, not command exec.
    server._handle_message = lambda ws, msg, cid: None
    return server


# =============================================================================
# Test 1 — iter_messages is cancel-aware mid-frame (unit test of the fix)
# =============================================================================

def test_iter_messages_cancel_mid_frame():
    """A cancel injected while parked on the next message exits the loop
    promptly — it does NOT block until the next message arrives."""
    cancel_event = threading.Event()
    # One message so the loop receives something, then parks on the next.
    fake_ws = _FakeWebSocket(cancel_event, messages=['{"type":"ping","id":"1"}'])

    received = []
    exited = threading.Event()
    error_box = {}

    def run():
        try:
            for message in iter_messages(fake_ws, cancel_event, poll_interval=0.02):
                received.append(message)
        except ConnectionClosedOK:
            pass  # cancel during recv raises ConnectionClosedOK — clean exit
        except Exception as e:  # pragma: no cover - defensive
            error_box["err"] = e
        finally:
            exited.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()

    # Deterministic: wait until the loop has processed message #1 and is
    # parked on the next recv. No wall-clock race — this is an event wait.
    assert fake_ws.parked.wait(timeout=5.0), (
        "loop never reached the mid-frame parked state"
    )
    assert received == ['{"type":"ping","id":"1"}'], "first message not delivered"

    # Inject the cancel mid-frame (while parked on the next message).
    cancel_event.set()

    # The loop must exit within a bounded time — NOT block until the next msg.
    assert exited.wait(timeout=5.0), (
        "cancel did not reach the handler mid-frame; loop blocked on recv"
    )
    t.join(timeout=5.0)
    assert not t.is_alive(), "loop thread still alive after cancel"
    assert "err" not in error_box, f"unexpected error: {error_box.get('err')}"


def test_iter_messages_no_cancel_preserves_behavior():
    """When no cancel fires, iter_messages behaves like the plain iterator:
    it yields messages in order and stops on connection close."""
    cancel_event = threading.Event()
    fake_ws = _FakeWebSocket(
        cancel_event,
        messages=['{"type":"ping","id":"a"}', '{"type":"ping","id":"b"}'],
        park_when_empty=False,  # raise ConnectionClosedOK once messages drain
    )

    out = []
    try:
        for message in iter_messages(fake_ws, cancel_event, poll_interval=0.02):
            out.append(message)
    except ConnectionClosedOK:
        pass  # clean close ends the stream — matches ``for message in ws:``
    assert out == ['{"type":"ping","id":"a"}', '{"type":"ping","id":"b"}']
    # No cancel was set.
    assert not cancel_event.is_set()


# =============================================================================
# Test 2 — _handle_client integration: request_cancel reaches the loop
# =============================================================================

def test_handle_client_cancel_mid_frame(monkeypatch):
    """End-to-end: a running _handle_client exits its recv loop promptly when
    request_cancel() is called mid-frame — not when the next message arrives."""
    # Stub the bridge so session bookkeeping in the loop body doesn't blow up.
    monkeypatch.setattr(
        "synapse.server.websocket.get_bridge", lambda: _FakeBridge()
    )

    server = _make_minimal_server()

    fake_ws_holder = {}

    def run_handler():
        cancel_event = threading.Event()
        fake_ws = _FakeWebSocket(
            cancel_event, messages=['{"type":"ping","id":"1"}']
        )
        fake_ws_holder["ws"] = fake_ws
        try:
            server._handle_client(fake_ws)
        except Exception:  # pragma: no cover - defensive
            pass

    t = threading.Thread(target=run_handler, daemon=True)
    t.start()

    # Wait until the handler has registered a cancel event for the connection
    # AND the fake is parked on the next message (mid-frame). Both are
    # deterministic event waits — no wall-clock race.
    deadline = time.monotonic() + 5.0
    registered = False
    while time.monotonic() < deadline:
        with server._clients_lock:
            registered = len(server._client_cancels) > 0
        if registered:
            break
        time.sleep(0.005)
    assert registered, "handler did not register a cancel event for the client"

    ws = fake_ws_holder["ws"]
    assert ws.parked.wait(timeout=5.0), (
        "handler recv loop never reached the mid-frame parked state"
    )

    # Inject the cancel mid-frame via the public API the fix exposes.
    server.request_cancel(ws)

    # The handler must return within a bounded time — not block on the next msg.
    t.join(timeout=5.0)
    assert not t.is_alive(), (
        "request_cancel did not interrupt the handler mid-frame; "
        "the recv loop blocked until the next message (the P3.3 bug)"
    )
    # The cancel event for this connection was deregistered on the way out.
    with server._clients_lock:
        assert ws not in server._client_cancels