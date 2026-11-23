"""MCP initialize does no Houdini work: no dispatch, nothing on the main thread.

History. ``MCPServer._handle_initialize`` used to preload project context by
dispatching ``synapse_project_setup``. First it ran on the hwebserver worker,
where the bridge's undo group and R1 scene hash were off-main ``hou.*`` calls
(R-001, Wave 0). R-001 moved the whole dispatch onto Houdini's main thread with
``run_on_main`` (label ``mcp:initialize:project_setup``). That made it safe but
unbounded: a payload that has started on the main thread cannot be stopped.

On 2026-11-22 the panel's first tools/call (the Doctor button) sent the lazy
``initialize``, the preload never returned, and Windows closed Houdini about
68 s later. The result it cached, ``session.project_context``, was never read
anywhere. So the preload is gone: an agent loads project memory by calling
``synapse_project_setup`` itself, as the system prompt and the initialize
instructions tell it to.

These tests pin that ``initialize``:

  * called from a NON-main thread, returns without the main thread doing
    anything (nothing is posted to hdefereval, so it cannot wait on a
    payload), and never reaches the handler or any ``hou.*`` call;
  * called ON the main thread, likewise reaches no handler and no ``hou.*``;
  * never calls ``run_on_main`` at all;
  * still answers with a session id and the instructions that name
    ``synapse_project_setup``.

The fakes are the ones R-001 used: a thread-recording ``hou`` patched into the
``shared.bridge`` MODULE globals (never ``sys.modules['hou']``, the fake-hou
residency trap in tests/conftest.py), and an ``hdefereval`` installed in
``sys.modules`` only for the duration of each test so the REAL ``run_on_main``
would see it if anything called it.
"""

from __future__ import annotations

import contextlib
import json
import queue
import sys
import threading
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
# A fake hdefereval that only records what is posted to the main thread
# ---------------------------------------------------------------------------
class _FakeHdefereval(types.ModuleType):
    """``executeDeferred`` posts; nothing in these tests ever pumps it."""

    def __init__(self):
        super().__init__("hdefereval")
        self.pending: queue.Queue = queue.Queue()

    def executeDeferred(self, fn):
        self.pending.put(fn)


# ---------------------------------------------------------------------------
# A fake hou that records the calling thread of every entry point the bridge
# would reach on a dispatch (the R1 hash, the undo group, the undo evidence)
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
# A real handler object; it records every command it is asked to run
# ---------------------------------------------------------------------------
class _RecordingHandler:
    def __init__(self):
        self.calls = []  # list[(command_type, thread_ident)]

    def handle(self, command):
        self.calls.append((command.type, threading.current_thread().ident))
        return SynapseResponse(
            id=command.id,
            success=True,
            data={"project_memory": "should never be read", "scene_memory": ""},
        )


def _initialize_body():
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"clientInfo": {"name": "initialize-no-main-thread-work"}},
    }).encode("utf-8")


@pytest.fixture
def fakes(monkeypatch):
    hou_fake = _ThreadRecordingHou()
    fake_hdefereval = _FakeHdefereval()
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", hou_fake)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hdefereval)
    return hou_fake, fake_hdefereval


def _assert_no_houdini_work(server, headers, handler, hou_fake, fake_hdefereval):
    assert handler.calls == [], (
        "initialize dispatched {!r}; it must not run any tool (the old preload "
        "ran synapse_project_setup on Houdini's main thread)".format(handler.calls)
    )
    assert hou_fake.calls == [], (
        "initialize made hou.* calls {!r}; it must not touch Houdini".format(hou_fake.calls)
    )
    assert fake_hdefereval.pending.empty(), (
        "initialize posted work to Houdini's main thread; a started main-thread "
        "payload cannot be stopped, which is how the 2026-11-22 Connect froze"
    )
    session = server._sessions.get_session(headers["Mcp-Session-Id"])
    assert session is not None
    assert session.initialized is True
    assert session.project_context is None


def test_initialize_off_main_returns_without_the_main_thread(fakes):
    """Off-main initialize finishes while nobody pumps the main thread.

    The old preload posted its payload and waited for it; with nothing pumping
    the fake hdefereval it could not return, so the join below would time out.
    """
    hou_fake, fake_hdefereval = fakes
    handler = _RecordingHandler()
    server = server_mod.MCPServer(handler=handler)
    outcome = {}

    def _call():
        try:
            outcome["response"] = server.handle_request(_initialize_body())
        except BaseException as exc:  # surfaced to the test below
            outcome["error"] = exc

    worker = threading.Thread(target=_call, name="hwebserver-worker", daemon=True)
    worker.start()
    worker.join(timeout=5.0)
    assert not worker.is_alive(), (
        "initialize did not return within 5 s with the main thread idle: it is "
        "waiting on main-thread work"
    )
    if "error" in outcome:
        raise outcome["error"]
    resp_body, headers = outcome["response"]
    assert resp_body is not None
    assert "Mcp-Session-Id" in headers
    _assert_no_houdini_work(server, headers, handler, hou_fake, fake_hdefereval)


def test_initialize_on_the_main_thread_does_no_houdini_work(fakes):
    """On the main thread run_on_main would run inline, so check the calls."""
    hou_fake, fake_hdefereval = fakes
    handler = _RecordingHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, headers = server.handle_request(_initialize_body())

    assert resp_body is not None
    _assert_no_houdini_work(server, headers, handler, hou_fake, fake_hdefereval)


def test_initialize_never_calls_run_on_main(fakes, monkeypatch):
    """Nothing in initialize is marshalled, inline or deferred."""
    from synapse.server import main_thread

    marshalled = []

    def _refuse(fn, *args, **kwargs):
        marshalled.append(kwargs.get("label"))
        raise AssertionError("initialize called run_on_main (label %r)" % kwargs.get("label"))

    monkeypatch.setattr(main_thread, "run_on_main", _refuse)
    handler = _RecordingHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, headers = server.handle_request(_initialize_body())

    assert marshalled == []
    assert resp_body is not None
    assert handler.calls == []


def test_initialize_still_points_agents_at_project_setup(fakes):
    """The handshake keeps telling the agent to load memory itself."""
    handler = _RecordingHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, _ = server.handle_request(_initialize_body())

    result = json.loads(resp_body)["result"]
    assert "synapse_project_setup" in result["instructions"]
    assert result["capabilities"]["tools"] == {"listChanged": True}
