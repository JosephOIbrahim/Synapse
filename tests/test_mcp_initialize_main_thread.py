"""R-001 — the MCP initialize preload must not touch ``hou.*`` off the main thread.

Finding (Wave 0 repair scaffold, node SUBSTRATE-1): ``MCPServer._handle_initialize``
called ``dispatch_tool(handler, "synapse_project_setup", {})`` on the hwebserver
worker thread. ``dispatch_tool`` routes every tool that is not read-only *to the
bridge* through ``execute_through_bridge`` (``synapse.panel.bridge_adapter``);
``synapse_project_setup`` is not in the bridge's read-only set, so the bridge's
``_execute_houdini`` ran ``hou.undos.group()`` and the R1 topological scene hash
on the CALLING thread. Off Houdini's main thread that is an unsafe ``hou.*``
call, ``_on_main_thread()`` records ``main_thread_executed=False``, fidelity
drops to 0.0, the bridge returns a failure, and ``session.project_context``
never caches.

These tests pin the repair's observable predicate:

  * ``MCPServer.handle_request("initialize")`` called from a NON-main thread
    with the REAL dispatch chain (``dispatch_tool`` -> ``bridge_adapter`` ->
    ``shared.bridge``) records ZERO ``hou.*`` calls on any thread other than
    the process main thread, and the session caches ``project_context``.
  * The same handshake called ON the main thread neither deadlocks nor
    changes behaviour (``run_on_main``'s fast path 2 runs the payload inline;
    the L8 self-deadlock the vendor blocking marshal caused must not return).

The handler object is minimal on purpose: the real ``SynapseHandler``
project_setup body touches the Living-Memory store on disk, which is not what
this node is about. Everything between the server and the handler — the tool
registry entry, ``dispatch_tool``, the bridge adapter and the bridge — is the
real production chain. A handler is a real object whose ``handle()`` is
actually invoked, and it records the thread it ran on so the test can prove
the marshal moved the whole dispatch, not just the bridge envelope.

Idiom: patch ``shared.bridge`` MODULE globals (``_HOU_AVAILABLE`` / ``hou``),
never ``sys.modules['hou']`` — the fake-hou residency trap in tests/conftest.py.
``hdefereval`` is installed in ``sys.modules`` only for the duration of each
test (``monkeypatch.setitem``) so the REAL ``run_on_main`` resolve sees it.
"""

from __future__ import annotations

import contextlib
import json
import queue
import sys
import threading
import time
import types
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import shared.bridge as b  # noqa: E402
from synapse.core.protocol import SynapseResponse
from synapse.mcp import server as server_mod
from synapse.panel import bridge_adapter as ba


# ---------------------------------------------------------------------------
# Isolation: the process-wide bridge singleton (and the panel alias) per test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _fresh_process_bridge():
    b.reset_process_bridge()
    ba._bridge = None
    yield
    b.reset_process_bridge()
    ba._bridge = None


# ---------------------------------------------------------------------------
# A fake hdefereval that delivers ONE deferred callable at a time
# ---------------------------------------------------------------------------
class _FakeHdefereval(types.ModuleType):
    """``executeDeferred`` posts; the test's main thread pumps the queue.

    This models hdefereval's contract on the one axis under test: the
    callable runs on the process main thread, not on the poster's thread.
    """

    def __init__(self):
        super().__init__("hdefereval")
        self.pending: queue.Queue = queue.Queue()

    def executeDeferred(self, fn):
        self.pending.put(fn)


# ---------------------------------------------------------------------------
# A fake hou that records the calling thread of every entry point the bridge
# reaches on this path (the R1 hash + the undo group + the undo evidence)
# ---------------------------------------------------------------------------
class _ThreadRecordingHou:
    def __init__(self):
        self.calls = []  # list[(call_name, thread_ident)]
        self._lock = threading.Lock()
        self.undos = _ThreadRecordingUndos(self)
        self.LopNode = type("LopNode", (), {})

    def record(self, name):
        with self._lock:
            self.calls.append((name, threading.current_thread().ident))

    def node(self, path):
        self.record("hou.node")
        # None -> the R1 hash uses its "invalid_context" sentinel, and
        # before == after so the op's delta is "no_change". The bridge path
        # is still fully exercised (group + hash + evidence).
        return None


class _ThreadRecordingUndos:
    def __init__(self, hou_fake):
        self._hou = hou_fake

    def areEnabled(self):
        self._hou.record("hou.undos.areEnabled")
        return True

    def undoLabels(self):
        self._hou.record("hou.undos.undoLabels")
        return []

    def group(self, label):
        self._hou.record("hou.undos.group")
        return contextlib.nullcontext()


# ---------------------------------------------------------------------------
# The dispatch target: a real object invoked through the real chain
# ---------------------------------------------------------------------------
class _ProjectSetupHandler:
    def __init__(self):
        self.calls = []  # list[(command_type, thread_ident)]

    def handle(self, command):
        self.calls.append((command.type, threading.current_thread().ident))
        return SynapseResponse(
            id=command.id,
            success=True,
            data={"project_memory": "R-001 preload", "scene_memory": ""},
        )


def _initialize_body():
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"clientInfo": {"name": "r001-main-thread"}},
    }).encode("utf-8")


def _pump_until(worker, fake_hdefereval, timeout=15.0):
    """Run deferred callbacks on THIS (main) thread until the worker returns."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not worker.is_alive() and fake_hdefereval.pending.empty():
            break
        try:
            callback = fake_hdefereval.pending.get(timeout=0.02)
        except queue.Empty:
            continue
        callback()
    worker.join(timeout=5.0)
    assert not worker.is_alive(), (
        "initialize never returned: the preload's deferred payload was never "
        "delivered to the main thread"
    )


def _run_initialize_off_main(server, fake_hdefereval):
    outcome = {}

    def _call():
        try:
            outcome["response"] = server.handle_request(_initialize_body())
        except BaseException as exc:  # surfaced to the test below
            outcome["error"] = exc

    worker = threading.Thread(target=_call, name="hwebserver-worker", daemon=True)
    worker.start()
    _pump_until(worker, fake_hdefereval)
    if "error" in outcome:
        raise outcome["error"]
    return outcome["response"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_initialize_preload_runs_hou_on_the_main_thread(monkeypatch):
    """The R-001 predicate: off-main initialize -> no off-main hou.* + cached context.

    On 4aab502a this fails twice over: the bridge's undo group and R1 hash run
    on the hwebserver worker (recorded as off-main hou calls), and the fidelity
    failure means ``session.project_context`` stays None.
    """
    hou_fake = _ThreadRecordingHou()
    fake_hdefereval = _FakeHdefereval()
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", hou_fake)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hdefereval)

    handler = _ProjectSetupHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, headers = _run_initialize_off_main(server, fake_hdefereval)

    assert resp_body is not None
    assert "Mcp-Session-Id" in headers

    main_ident = threading.main_thread().ident
    off_main = [(name, tid) for name, tid in hou_fake.calls
                if tid != main_ident]
    assert off_main == [], (
        "hou.* ran off Houdini's main thread during initialize: {!r}. The "
        "preload must dispatch through run_on_main.".format(off_main)
    )

    session = server._sessions.get_session(headers["Mcp-Session-Id"])
    assert session is not None
    assert session.project_context is not None, (
        "the bridge failed the preload (main_thread_executed=False), so the "
        "session never cached project_context"
    )

    # The dispatch went through exactly once (never replayed) and the handler
    # itself ran on the main thread — the whole dispatch was marshalled.
    assert [ctype for ctype, _ in handler.calls] == ["project_setup"]
    assert handler.calls[0][1] == main_ident


def test_initialize_on_the_main_thread_stays_inline_and_caches(monkeypatch):
    """A main-thread caller must not self-deadlock and must still cache.

    This is the L8 property: run_on_main's fast path 2 calls the payload
    directly from the main thread, unlike the vendor's blocking marshal that
    parked forever when its own thread was the one that had to release it.
    """
    hou_fake = _ThreadRecordingHou()
    fake_hdefereval = _FakeHdefereval()
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", hou_fake)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hdefereval)

    handler = _ProjectSetupHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, headers = server.handle_request(_initialize_body())

    assert resp_body is not None
    assert fake_hdefereval.pending.empty(), (
        "a main-thread initialize deferred its payload — it must run inline "
        "(deferring from the main thread is the deadlock L8 removed)"
    )
    session = server._sessions.get_session(headers["Mcp-Session-Id"])
    assert session.project_context is not None
    assert [ctype for ctype, _ in handler.calls] == ["project_setup"]
