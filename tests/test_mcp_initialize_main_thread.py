"""MCP initialize and DELETE do no Houdini work on their own thread and never wait on main.

History. ``MCPServer._handle_initialize`` used to preload project context by
dispatching ``synapse_project_setup``. First it ran on the hwebserver worker,
where the bridge's undo group and R1 scene hash were off-main ``hou.*`` calls
(R-001, Wave 0). R-001 moved the whole dispatch onto Houdini's main thread with
``run_on_main`` (label ``mcp:initialize:project_setup``). That made it safe but
unbounded: a payload that has started on the main thread cannot be stopped.

On every Connect that preload ran ``ensure_scene_structure`` (seeding
``$JOB/claude/project.md``, ``$HIP/claude/memory.md`` and ``agent.usd`` when
missing), ran ``reload_show_config()``, and cached the loaded context in
``session.project_context``, which nothing read. On 2026-11-22 the panel's
first tools/call (the Doctor button) sent the lazy ``initialize``, the preload
never returned, and Windows closed Houdini about 68 s after it started
(docs/reviews/connect-freeze-forensics-2026-11-23.md, section 1). So the
preload is gone: an agent loads project memory by calling
``synapse_project_setup`` itself, as the system prompt and the initialize
instructions tell it to; each memory and agent.usd writer creates the scene
structure when it writes; and initialize keeps the show-config reload, which
only clears a dict.

These tests pin that ``initialize``:

  * called from a NON-main thread, returns without the main thread doing
    anything (nothing is posted to hdefereval, so it cannot wait on a
    payload), and never reaches the handler or any ``hou.*`` call;
  * called ON the main thread, likewise reaches no handler and no ``hou.*``;
  * never calls ``run_on_main`` at all;
  * still clears the show-config cache, with no hou call and nothing posted;
  * still answers with a session id and the instructions that name
    ``synapse_project_setup``.

Session end (v5.104.2). initialize first sweeps expired sessions, and DELETE
/mcp ends one. Both used to run the session-end cleanup inline on the request
thread: ``hou.hipFile.path()``, ``hou.getenv("JOB")``, ``ensure_scene_structure``
(folders and seed files) and the agent.usd writes, all off Houdini's main
thread. The second half of this file pins that:

  * initialize (sweeping an expired session) and DELETE return with the main
    thread idle, make no ``hou.*`` call and no file write on the request
    thread, and post nothing to hdefereval from it;
  * the recorder thread reads the scene through ``run_on_main`` (label
    ``mcp:session_end:capture``, in the pending-dispatch registry, so the
    emergency halt can cancel it), and once the main thread runs that read the
    record is written on the recorder thread -- never on the main thread --
    into the scene's existing agent.usd (saved, relocated and untitled scenes);
  * a session end creates no ``claude/`` folder, seed file or agent.usd;
  * ends that queue up behind a stalled main thread become ONE record, and a
    task created after the end survives the late record;
  * outside Houdini (no ``hou``, or no ``hdefereval``), or with the records
    switched off, nothing is recorded and nothing is posted -- and a test that
    does not opt in cannot start the process-wide recorder;
  * the recorder thread is a daemon, and ``stop`` joins it. Every recorder a
    test here starts is stopped and joined (``_SessionEndEnv.close``), and
    tests/conftest.py fails any test that leaves one running.

The fakes are the ones R-001 used: a thread-recording ``hou`` patched into the
``shared.bridge`` and ``synapse.mcp.session`` MODULE globals (never
``sys.modules['hou']``, the fake-hou residency trap in tests/conftest.py), and
an ``hdefereval`` installed in ``sys.modules`` only for the duration of each
test so the REAL ``run_on_main`` posts to it. Nothing pumps that fake except
the test, on its own (main) thread.
"""

from __future__ import annotations

import builtins
import contextlib
import importlib
import json
import os
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
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))  # for the test_agent_state harness

import shared.bridge as b  # noqa: E402
from synapse.core.protocol import SynapseResponse
from synapse.mcp import server as server_mod
from synapse.panel import bridge_adapter as ba
from synapse.server import main_thread

# Imported NOW, before any test installs the ``import hou`` seam below, so each
# binds its module-level ``hou`` to the suite's resident and never to a fake.
import synapse.host.memory_lifecycle as memory_lifecycle  # noqa: E402
import synapse.memory.agent_state as agent_state  # noqa: E402
import synapse.memory.scene_memory as scene_memory  # noqa: E402
import synapse.memory.store  # noqa: E402,F401

# The FakeStage mock-pxr harness, as tests/test_autonomy_task_provenance.py uses it.
import test_agent_state as pxr_harness  # noqa: E402

session_mod = importlib.import_module("synapse.mcp.session")

# Literals, not session_mod attributes, so a red-control tree without them
# still runs these tests to their assertions.
_RECORDS_ENV = "SYNAPSE_MCP_SESSION_END_RECORDS"
_CAPTURE_LABEL = "mcp:session_end:capture"
_RECORDER_THREAD_NAME = "synapse-mcp-session-end"  # tests/conftest.py matches this name
_STAMP = "%Y-%m-%dT%H:%M:%SZ"


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
    """``executeDeferred`` posts; only the test runs what was posted (``pump``)."""

    def __init__(self):
        super().__init__("hdefereval")
        self.pending: queue.Queue = queue.Queue()
        self.posted_from = []  # thread ident of every executeDeferred caller
        self._posted = threading.Condition()

    def executeDeferred(self, fn):
        with self._posted:
            self.posted_from.append(threading.get_ident())
            self.pending.put(fn)
            self._posted.notify_all()

    def wait_for_posts(self, count, timeout):
        """True once *count* payloads have been posted in all; False on timeout."""
        deadline = time.monotonic() + timeout
        with self._posted:
            while len(self.posted_from) < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._posted.wait(remaining)
        return True

    def pump(self):
        """Run every posted payload on the CALLING thread (the test's main)."""
        ran = 0
        while True:
            try:
                fn = self.pending.get_nowait()
            except queue.Empty:
                return ran
            fn()
            ran += 1


# ---------------------------------------------------------------------------
# A fake hou that records the calling thread of every entry point the bridge
# would reach on a dispatch (the R1 hash, the undo group, the undo evidence)
# ---------------------------------------------------------------------------
class _ThreadRecordingHou:
    def __init__(self, hip_path="untitled.hip", is_new_file=True):
        self.calls = []  # list[(call_name, thread_ident)]
        self.holders = []  # the run_on_main label holding the main thread at each call
        self._lock = threading.Lock()
        self.undos = _ThreadRecordingUndos(self)
        self.hipFile = _ThreadRecordingHipFile(self, hip_path, is_new_file)
        self.LopNode = type("LopNode", (), {})

    def record(self, name):
        holder = main_thread.current_main_thread_holder()
        with self._lock:
            self.calls.append((name, threading.current_thread().ident))
            self.holders.append(holder[0] if holder else None)

    def node(self, path):
        self.record("hou.node")
        return None

    def getenv(self, name, default=None):
        self.record("hou.getenv")
        return default


class _ThreadRecordingHipFile:
    def __init__(self, hou_fake, hip_path, is_new_file):
        self._hou = hou_fake
        self._path = hip_path
        self._is_new = is_new_file

    def path(self):
        self._hou.record("hou.hipFile.path")
        return self._path

    def isNewFile(self):
        self._hou.record("hou.hipFile.isNewFile")
        return self._is_new


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
    assert not hasattr(session, "project_context"), (
        "the session carries a project_context slot again; nothing reads one")


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


def test_initialize_clears_the_show_config_cache_without_houdini_work(fakes, monkeypatch):
    """Session start is show config's reload point; the reload is a dict clear only.

    The preload used to reach reload_show_config() through project_setup. It
    stays in initialize, where it touches no hou, no file and no main thread.
    """
    hou_fake, fake_hdefereval = fakes
    show_config = importlib.import_module("synapse.core.show_config")
    monkeypatch.setattr(show_config, "hou", hou_fake, raising=False)
    monkeypatch.setattr(session_mod, "hou", hou_fake, raising=False)
    stale = ("<stale env file>", "<stale hip show.json>", "<stale job show.json>")
    show_config._cache[stale] = object()
    try:
        server = server_mod.MCPServer(handler=_RecordingHandler())
        (resp_body, headers), _ident = _run_on_request_thread(
            lambda: server.handle_request(_initialize_body()), "initialize")

        assert resp_body is not None and "Mcp-Session-Id" in headers
        assert stale not in show_config._cache, (
            "initialize no longer reloads show config: a show.json edited between "
            "sessions is not re-read at session start")
        assert hou_fake.calls == [], hou_fake.calls
        assert fake_hdefereval.posted_from == [] and fake_hdefereval.pending.empty()
    finally:
        show_config._cache.pop(stale, None)


def test_initialize_still_points_agents_at_project_setup(fakes):
    """The handshake keeps telling the agent to load memory itself."""
    handler = _RecordingHandler()
    server = server_mod.MCPServer(handler=handler)

    resp_body, _ = server.handle_request(_initialize_body())

    result = json.loads(resp_body)["result"]
    assert "synapse_project_setup" in result["instructions"]
    assert result["capabilities"]["tools"] == {"listChanged": True}


# ===========================================================================
# Session end: initialize's sweep and DELETE /mcp
# ===========================================================================

_TWO_HOURS = 7200.0
_REQUEST_JOIN_S = 5.0
_TEST_CAPTURE_TIMEOUT_S = 5.0


class _SessionEndEnv:
    """One session-end test's fakes, and the thread every call ran on."""

    def __init__(self, hou_fake, hdefereval, recorder, scene):
        self.hou = hou_fake  # None: the test runs outside Houdini
        self.hdefereval = hdefereval  # None: there is no hdefereval
        self.recorder = recorder  # None: a tree without the recorder (red control)
        self.scene = scene
        # (writer, agent_usd, summary dict / task cutoff, thread ident)
        self.writes = []
        self.lookups = []  # thread ident of every agent.usd lookup

    def wait_for_read(self, count=1):
        """Wait until the recorder has posted its main-thread read(s)."""
        assert self.hdefereval.wait_for_posts(count, _REQUEST_JOIN_S), (
            "the session-end recorder posted no main-thread read within 5 s")

    def run_main(self):
        """Houdini's main thread goes idle: run what was posted, on THIS thread."""
        return self.hdefereval.pump()

    def settle(self):
        if self.recorder is not None:
            assert self.recorder.wait_idle(_REQUEST_JOIN_S), (
                "the session-end recorder did not go idle within 5 s"
            )

    def recorder_started(self):
        return getattr(self.recorder, "_thread", None) is not None

    def close(self):
        """Release, stop and join the recorder; leave run_on_main's queue empty."""
        if self.recorder is None:
            return
        if self.hdefereval is not None:
            deadline = time.monotonic() + _REQUEST_JOIN_S
            while not self.recorder.wait_idle(0.05):
                self.hdefereval.pump()  # a read the test never let the main thread run
                assert time.monotonic() < deadline, "the session-end recorder never went idle"
            self.hdefereval.pump()  # the wake a cancelled or timed-out read leaves behind
        stop = getattr(self.recorder, "stop", None)
        if stop is not None:  # a red-control tree has no stop()
            assert stop(_REQUEST_JOIN_S), "the session-end recorder thread did not stop"
            thread = getattr(self.recorder, "_thread", None)
            assert thread is None or not thread.is_alive()
        with main_thread._deferred_lock:
            left = list(main_thread._deferred_calls), main_thread._deferred_wake
        assert left == ([], None), "the test left run_on_main's deferred queue non-empty"


def _scene_layout(tmp_path, layout, monkeypatch):
    """A scene on disk. ``agent_usd`` is where its session-end record belongs."""
    if layout == "saved":
        scene = tmp_path / "shot"
        (scene / "claude").mkdir(parents=True)
        hip = scene / "shot.hip"
        hip.write_text("", encoding="utf-8")
        agent_usd = scene / "claude" / "agent.usd"
        agent_usd.write_text("#usda 1.0\n", encoding="utf-8")
        return {"hip": str(hip), "is_new": False, "agent_usd": str(agent_usd)}
    if layout == "relocated":
        # The hip's folder has no claude/; this process recorded a relocation.
        scene = tmp_path / "locked_shot"
        scene.mkdir()
        hip = scene / "shot.hip"
        hip.write_text("", encoding="utf-8")
        moved = tmp_path / "moved"
        (moved / "claude").mkdir(parents=True)
        agent_usd = moved / "claude" / "agent.usd"
        agent_usd.write_text("#usda 1.0\n", encoding="utf-8")
        monkeypatch.setitem(scene_memory._RELOCATED, os.path.normpath(str(scene)), str(moved))
        return {"hip": str(hip), "is_new": False, "agent_usd": str(agent_usd)}
    if layout == "unsaved":
        base = tmp_path / "untitled" / "sessions" / "launch"
        (base / "claude").mkdir(parents=True)
        agent_usd = base / "claude" / "agent.usd"
        agent_usd.write_text("#usda 1.0\n", encoding="utf-8")
        hip = tmp_path / "bin" / "untitled.hip"  # Houdini's never-saved placeholder
        return {"hip": str(hip), "is_new": True, "agent_usd": str(agent_usd),
                "unsaved_base": base}
    if layout == "no_memory":
        scene = tmp_path / "fresh"
        scene.mkdir()
        hip = scene / "fresh.hip"
        hip.write_text("", encoding="utf-8")
        return {"hip": str(hip), "is_new": False, "agent_usd": None,
                "claude_dir": str(scene / "claude")}
    if layout == "claude_without_agent_usd":
        # The scene has notes (claude/memory.md) but no agent.usd yet.
        scene = tmp_path / "noted"
        (scene / "claude").mkdir(parents=True)
        (scene / "claude" / "memory.md").write_text("# Scene memory\n", encoding="utf-8")
        hip = scene / "noted.hip"
        hip.write_text("", encoding="utf-8")
        return {"hip": str(hip), "is_new": False, "agent_usd": None,
                "claude_dir": str(scene / "claude")}
    raise AssertionError(layout)


def _install_import_hou_seam(monkeypatch, hou_fake):
    """Route a function-level ``import hou`` to the fake, for this test only.

    The pre-fix cleanup (an older red control's tree) imported hou inside the
    function, which a module-global patch cannot reach. This intercepts the
    import statement instead of planting ``sys.modules['hou']``, so nothing
    becomes resident; the memory modules were imported at the top of this
    file, before any seam existed. ``None`` makes ``import hou`` fail, as it
    does outside Houdini.
    """
    real_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "hou" and level == 0:
            if hou_fake is None:
                raise ImportError("No module named 'hou'")
            return hou_fake
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)


@pytest.fixture
def session_end_env(monkeypatch, tmp_path):
    made = []

    def _make(layout="saved", hou_present=True, hdefereval_present=True,
              real_writers=False, capture_timeout=_TEST_CAPTURE_TIMEOUT_S):
        scene = _scene_layout(tmp_path, layout, monkeypatch)
        hou_fake = _ThreadRecordingHou(scene["hip"], scene["is_new"]) if hou_present else None
        monkeypatch.setattr(session_mod, "hou", hou_fake, raising=False)
        _install_import_hou_seam(monkeypatch, hou_fake)
        # The explicit opt-in: tests/conftest.py turns the records off for the run.
        monkeypatch.setenv(_RECORDS_ENV, "1")
        if hdefereval_present:
            hdefereval = _FakeHdefereval()
            monkeypatch.setitem(sys.modules, "hdefereval", hdefereval)
        else:
            hdefereval = None
            monkeypatch.setitem(sys.modules, "hdefereval", None)  # import fails
        with main_thread._deferred_lock:
            assert main_thread._deferred_wake is None, (
                "an earlier test left a run_on_main wake that nothing ran")
        recorder = None
        if hasattr(session_mod, "_SessionEndRecorder"):
            try:
                recorder = session_mod._SessionEndRecorder(capture_timeout=capture_timeout)
            except TypeError:  # a red-control tree's recorder takes no timeout
                recorder = session_mod._SessionEndRecorder()
            monkeypatch.setattr(session_mod, "_RECORDER", recorder)
        env = _SessionEndEnv(hou_fake, hdefereval, recorder, scene)

        if not real_writers:
            def _suspend(path, created_at_or_before=None):
                env.writes.append(
                    ("suspend_all_tasks", path, created_at_or_before, threading.get_ident()))

            def _log(path, summary):
                env.writes.append(("log_session", path, dict(summary), threading.get_ident()))

            monkeypatch.setattr(agent_state, "suspend_all_tasks", _suspend)
            monkeypatch.setattr(agent_state, "log_session", _log)
        if hasattr(session_mod, "_existing_agent_usd"):
            real_lookup = session_mod._existing_agent_usd

            def _lookup(facts):
                env.lookups.append(threading.get_ident())
                return real_lookup(facts)

            monkeypatch.setattr(session_mod, "_existing_agent_usd", _lookup)
        if layout == "unsaved" and hou_fake is not None:
            # In Houdini this reads hou.text.expandString, so it is a hou read.
            def _existing_unsaved_base():
                hou_fake.record("memory_lifecycle.existing_unsaved_base")
                return scene["unsaved_base"]

            monkeypatch.setattr(memory_lifecycle, "existing_unsaved_base", _existing_unsaved_base)
        made.append(env)
        return env

    yield _make
    # Before monkeypatch undoes the fakes: release, stop and join every recorder.
    for env in made:
        env.close()


def _run_on_request_thread(fn, what):
    """Call *fn* on an hwebserver-like worker while nothing pumps the main thread."""
    outcome = {}

    def _call():
        outcome["ident"] = threading.get_ident()
        try:
            outcome["value"] = fn()
        except BaseException as exc:  # surfaced to the test below
            outcome["error"] = exc

    worker = threading.Thread(target=_call, name="hwebserver-worker", daemon=True)
    worker.start()
    worker.join(timeout=_REQUEST_JOIN_S)
    assert not worker.is_alive(), (
        "{} did not return within 5 s with the main thread idle: it is waiting on "
        "main-thread work".format(what)
    )
    if "error" in outcome:
        raise outcome["error"]
    return outcome["value"], outcome["ident"]


def _expired_session(server):
    sid = server._sessions.create_session({"name": "expired"})
    _age(server, sid)
    return sid


def _age(server, *sids):
    with server._sessions._lock:
        for sid in sids:
            server._sessions._sessions[sid].last_activity = time.time() - _TWO_HOURS


def _assert_request_thread_clean(env, request_ident, what):
    if env.hou is not None:
        on_request = [name for name, ident in env.hou.calls if ident == request_ident]
        assert on_request == [], (
            "{} made hou.* calls on its request thread: {}".format(what, on_request)
        )
    file_work = [w[0] for w in env.writes if w[3] == request_ident]
    file_work += ["agent.usd lookup" for ident in env.lookups if ident == request_ident]
    assert file_work == [], (
        "{} did session-end file work on its request thread: {}".format(what, file_work)
    )
    if env.hdefereval is not None:
        assert request_ident not in env.hdefereval.posted_from, (
            "{} posted to hdefereval itself; the vendor registration can wait on "
            "the HOM lock the main thread holds".format(what)
        )


def _deliver_and_assert_off_main(env, request_ident):
    """Run the one posted read on this (main) thread; the writes must land elsewhere."""
    env.wait_for_read()
    assert env.hou.calls == [], (
        "hou was read before the main thread ran the posted payload: {}".format(env.hou.calls)
    )
    assert env.writes == [], "the record was written before the main thread read the scene"
    main_ident = threading.get_ident()
    ran = env.run_main()
    assert ran == 1, "expected exactly one posted main-thread read, got {}".format(ran)
    env.settle()

    off_main = [name for name, ident in env.hou.calls if ident != main_ident]
    assert off_main == [], "hou.* ran off the main thread: {}".format(off_main)
    assert env.writes, "no session-end record was written after the main thread's read"
    write_threads = {w[3] for w in env.writes} | set(env.lookups)
    assert main_ident not in write_threads, "session-end file work ran on the main thread"
    assert request_ident not in write_threads, "session-end file work ran on the request thread"
    return [name for name, _ident in env.hou.calls]


def _summaries(env):
    return [w[2]["summary_text"] for w in env.writes if w[0] == "log_session"]


def test_initialize_sweeping_an_expired_session_does_no_houdini_work_on_its_thread(
        session_end_env):
    """initialize ends an expired session: its request thread stays free of hou and files."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    expired = _expired_session(server)

    (resp_body, headers), request_ident = _run_on_request_thread(
        lambda: server.handle_request(_initialize_body()), "initialize")

    assert resp_body is not None and "Mcp-Session-Id" in headers
    _assert_request_thread_clean(env, request_ident, "initialize")
    assert server._sessions.get_session(expired) is None
    _deliver_and_assert_off_main(env, request_ident)
    assert _summaries(env) == ["MCP session ended (id: {})".format(expired)]


def test_delete_does_no_houdini_work_on_its_thread(session_end_env):
    """DELETE /mcp (destroy_session) returns with the main thread idle and no hou on its thread."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")

    assert destroyed is True
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    assert server._sessions.get_session(sid) is None
    _deliver_and_assert_off_main(env, request_ident)


@pytest.mark.parametrize("layout", ["saved", "relocated", "unsaved"])
def test_session_end_record_lands_in_the_scenes_existing_agent_usd(session_end_env, layout):
    """Once main runs the read, the record goes to the agent.usd the resolver names."""
    env = session_end_env(layout)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "ending"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")
    assert destroyed is True
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    hou_reads = _deliver_and_assert_off_main(env, request_ident)

    agent_usd = env.scene["agent_usd"]
    assert [(w[0], w[1]) for w in env.writes] == [
        ("suspend_all_tasks", agent_usd), ("log_session", agent_usd)]
    cutoff, summary = env.writes[0][2], env.writes[1][2]
    assert summary["summary_text"] == "MCP session ended (id: {})".format(sid)
    assert isinstance(cutoff, float), (
        "suspend_all_tasks was not limited to tasks created by the end: {!r}".format(cutoff))
    assert summary["end_time"] == time.strftime(_STAMP, time.gmtime(cutoff)), (
        "the task cutoff and the record's end time are not the same moment")
    if layout == "unsaved":
        assert hou_reads == ["hou.hipFile.path", "hou.hipFile.isNewFile",
                             "memory_lifecycle.existing_unsaved_base"]
    else:
        assert hou_reads == ["hou.hipFile.path"]
        resolved = os.path.join(scene_memory.resolve_hip_dir(env.scene["hip"]),
                                "claude", "agent.usd")
        assert os.path.normcase(resolved) == os.path.normcase(agent_usd)


def test_session_end_creates_no_memory_folder(session_end_env):
    """A scene with no claude/ gets none: a session end seeds nothing."""
    env = session_end_env("no_memory")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "ending"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")

    assert destroyed is True
    assert not os.path.exists(env.scene["claude_dir"]), (
        "the session end created claude/ on the request thread")
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    env.wait_for_read()
    assert env.run_main() == 1
    env.settle()
    assert env.writes == []
    assert not os.path.exists(env.scene["claude_dir"])


def test_a_claude_folder_without_agent_usd_gets_no_record_and_no_new_file(session_end_env):
    """claude/ exists but agent.usd does not: the end writes nothing and creates nothing.

    The recorder does look (the lookup runs on its thread); agent_state's
    writers would create the file, so the lookup's isfile guard is what keeps
    a session end from seeding agent.usd.
    """
    env = session_end_env("claude_without_agent_usd")
    claude_dir = env.scene["claude_dir"]
    before = sorted(os.listdir(claude_dir))
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "ending"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")

    assert destroyed is True
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    env.wait_for_read()
    assert env.run_main() == 1
    env.settle()
    assert env.lookups, "the recorder never looked for the scene's agent.usd"
    assert env.writes == [], "a session end wrote into a scene with no agent.usd: {}".format(
        [w[:2] for w in env.writes])
    assert sorted(os.listdir(claude_dir)) == before == ["memory.md"]


def test_outside_houdini_a_session_end_records_and_posts_nothing(session_end_env):
    """No hou: initialize's sweep and DELETE still work and nothing is recorded."""
    env = session_end_env("saved", hou_present=False)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    leaving = server._sessions.create_session({"name": "leaving"})
    expired = _expired_session(server)

    (resp_body, _), _ident = _run_on_request_thread(
        lambda: server.handle_request(_initialize_body()), "initialize")
    destroyed, _ident = _run_on_request_thread(
        lambda: server.destroy_session(leaving), "DELETE /mcp")

    assert resp_body is not None and destroyed is True
    assert server._sessions.get_session(expired) is None
    env.settle()
    assert env.hdefereval.pending.empty() and env.hdefereval.posted_from == []
    assert env.writes == [] and env.lookups == []
    assert not env.recorder_started()


def test_without_hdefereval_a_session_end_reads_no_hou_and_records_nothing(session_end_env):
    """hou but no hdefereval (hython: no main thread to post to): skip, never read hou inline."""
    env = session_end_env("saved", hdefereval_present=False)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")

    assert destroyed is True
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    env.settle()
    assert env.hou.calls == []
    assert env.writes == [] and env.lookups == []
    assert not env.recorder_started()


def test_with_the_records_switched_off_a_session_end_posts_and_writes_nothing(
        session_end_env, monkeypatch):
    """SYNAPSE_MCP_SESSION_END_RECORDS=off: nothing queued, posted, read or written."""
    env = session_end_env("saved")
    monkeypatch.setenv(_RECORDS_ENV, "off")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    destroyed, request_ident = _run_on_request_thread(
        lambda: server.destroy_session(sid), "DELETE /mcp")

    assert destroyed is True
    _assert_request_thread_clean(env, request_ident, "DELETE /mcp")
    env.settle()
    assert env.hdefereval.posted_from == [] and env.hou.calls == []
    assert env.writes == [] and env.lookups == []
    assert not env.recorder_started()


def test_without_opting_in_a_test_cannot_start_the_process_wide_recorder(monkeypatch):
    """The suite's fake hou and a planted hdefereval are not enough to start it.

    tests/conftest.py turns the records off for the run; a test that ends MCP
    sessions without opting in (as tests/test_mcp_protocol.py does) starts no
    recorder thread and posts no read.
    """
    hou_fake = _ThreadRecordingHou("shot.hip", False)
    fake_hdefereval = _FakeHdefereval()
    monkeypatch.setattr(session_mod, "hou", hou_fake, raising=False)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hdefereval)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    leaving = server._sessions.create_session({"name": "leaving"})
    _expired_session(server)

    server.handle_request(_initialize_body())  # sweeps the expired session
    assert server.destroy_session(leaving) is True

    assert fake_hdefereval.posted_from == [], (
        "the process-wide session-end recorder started and posted a read without "
        "the test opting in")
    assert [t.name for t in threading.enumerate()
            if t.name == _RECORDER_THREAD_NAME and t.is_alive()] == []
    assert hou_fake.calls == []
    assert os.environ.get(_RECORDS_ENV) == "0", (
        "tests/conftest.py no longer turns MCP session-end records off for the run")


def test_the_recorder_thread_is_a_daemon(session_end_env):
    """A recorder waiting on a stalled main thread never holds the process open at exit."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    _run_on_request_thread(lambda: server.destroy_session(sid), "DELETE /mcp")
    env.wait_for_read()

    thread = env.recorder._thread
    assert thread is not None and thread.is_alive()
    assert thread.daemon is True, "the session-end recorder thread is not a daemon"
    assert thread.name == _RECORDER_THREAD_NAME  # tests/conftest.py finds leaks by name
    env.run_main()
    env.settle()


def test_stop_joins_the_recorder_thread_and_later_ends_start_nothing(session_end_env):
    """``stop`` ends and joins the thread; an end after it queues nothing."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    first = server._sessions.create_session({"name": "first"})
    _run_on_request_thread(lambda: server.destroy_session(first), "DELETE /mcp")
    env.wait_for_read()
    env.run_main()
    env.settle()
    thread = env.recorder._thread

    assert env.recorder.stop(_REQUEST_JOIN_S) is True
    assert not thread.is_alive()

    second = server._sessions.create_session({"name": "second"})
    _run_on_request_thread(lambda: server.destroy_session(second), "DELETE /mcp")
    assert env.recorder._thread is thread and not thread.is_alive()
    assert env.recorder.wait_idle(0.1)
    assert _summaries(env) == ["MCP session ended (id: {})".format(first)]


def test_a_sweep_that_ends_several_sessions_writes_one_record_naming_them_all(
        session_end_env):
    """Two sessions expire together: one record, both ids, in the order they ended."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    first = server._sessions.create_session({"name": "first"})
    second = server._sessions.create_session({"name": "second"})
    _age(server, first, second)

    (resp_body, _), request_ident = _run_on_request_thread(
        lambda: server.handle_request(_initialize_body()), "initialize")

    assert resp_body is not None
    _assert_request_thread_clean(env, request_ident, "initialize")
    _deliver_and_assert_off_main(env, request_ident)
    assert _summaries(env) == ["MCP sessions ended (ids: {}, {})".format(first, second)]
    assert [w[0] for w in env.writes] == ["suspend_all_tasks", "log_session"]


def test_ends_queued_behind_a_stalled_main_thread_become_one_record(session_end_env):
    """Three DELETEs while the main thread is busy: one read, one record, the last end's time.

    log_session names its prim by the second it writes, so three records
    written together after the stall would overwrite each other.
    """
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sids = [server._sessions.create_session({"name": n}) for n in ("a", "b", "c")]

    _run_on_request_thread(lambda: server.destroy_session(sids[0]), "DELETE /mcp")
    env.wait_for_read()  # the recorder's read waits on a main thread that is not running
    for sid in sids[1:]:
        before_last = time.time()
        destroyed, ident = _run_on_request_thread(
            lambda sid=sid: server.destroy_session(sid), "DELETE /mcp")
        assert destroyed is True
        _assert_request_thread_clean(env, ident, "DELETE /mcp")
    assert env.writes == []

    env.run_main()  # the main thread comes back
    env.settle()

    assert _summaries(env) == ["MCP sessions ended (ids: {})".format(", ".join(sids))], (
        "ends queued behind the stalled main thread were written as separate records")
    suspends = [w for w in env.writes if w[0] == "suspend_all_tasks"]
    assert len(suspends) == 1
    cutoff = suspends[0][2]
    assert isinstance(cutoff, float) and cutoff >= before_last, (
        "the task cutoff is not the last end's time")
    log = [w for w in env.writes if w[0] == "log_session"][0]
    assert log[2]["end_time"] == time.strftime(_STAMP, time.gmtime(cutoff))


def _use_fake_pxr(monkeypatch):
    """agent_state on the FakeStage harness, with a stage registry of this test's own."""
    monkeypatch.setattr(pxr_harness, "_fake_stages", {})
    fake_usd = types.SimpleNamespace(Stage=types.SimpleNamespace(
        CreateNew=pxr_harness._fake_create_new, Open=pxr_harness._fake_open))
    monkeypatch.setattr(agent_state, "PXR_AVAILABLE", True)
    monkeypatch.setattr(agent_state, "Usd", fake_usd)
    monkeypatch.setattr(agent_state, "Sdf", pxr_harness.FakeSdf)
    monkeypatch.setattr(agent_state, "Vt", pxr_harness.FakeVt)


def test_a_task_created_after_the_end_survives_the_late_record(session_end_env, monkeypatch):
    """The record lands after the next session dispatched work; that work stays pending.

    The inline write this replaced finished before DELETE returned, so it could
    never see a later task. The deferred one can, and must leave it alone.
    """
    env = session_end_env("saved", real_writers=True)
    _use_fake_pxr(monkeypatch)
    agent_usd = env.scene["agent_usd"]
    agent_state.initialize_agent_usd(agent_usd)
    real_now = agent_state._now
    monkeypatch.setattr(agent_state, "_now",
                        lambda: time.strftime(_STAMP, time.gmtime(time.time() - 60)))
    agent_state.create_task(agent_usd, "left_running", "dispatched before the session ended")
    monkeypatch.setattr(agent_state, "_now", real_now)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    _run_on_request_thread(lambda: server.destroy_session(sid), "DELETE /mcp")
    env.wait_for_read()  # Houdini's main thread is busy; the record is not written yet
    agent_state.create_task(agent_usd, "next_session", "dispatched after the session ended")
    env.run_main()
    env.settle()

    stage = pxr_harness._fake_stages[os.path.normpath(agent_usd)]

    def _status(task_id):
        return stage.GetPrimAtPath(
            "/SYNAPSE/agent/tasks/" + task_id).GetAttribute("synapse:status").Get()

    assert _status("next_session") == "pending", (
        "the late session-end record suspended a task created after the session ended")
    assert _status("left_running") == "suspended"
    history = stage.GetPrimAtPath("/SYNAPSE/agent/session_history").GetChildren()
    assert [p.GetAttribute("synapse:summary").Get() for p in history] == [
        "MCP session ended (id: {})".format(sid)]


def test_the_scene_read_is_a_labelled_registered_main_thread_dispatch(session_end_env):
    """The read goes through run_on_main: labelled while it holds main, cancellable while queued."""
    env = session_end_env("saved")
    server = server_mod.MCPServer(handler=_RecordingHandler())
    sid = server._sessions.create_session({"name": "leaving"})

    _run_on_request_thread(lambda: server.destroy_session(sid), "DELETE /mcp")
    env.wait_for_read()
    with main_thread._pending_lock:
        queued = [entry[2] for entry in main_thread._pending_dispatches.values()]
    assert queued == [_CAPTURE_LABEL], (
        "the session-end read is not in run_on_main's pending-dispatch registry, so "
        "the emergency halt cannot cancel it: {}".format(queued))

    env.run_main()
    env.settle()

    assert env.hou.holders and set(env.hou.holders) == {_CAPTURE_LABEL}, (
        "the main-thread read ran unlabelled: {}".format(env.hou.holders))
    assert main_thread.pending_dispatch_count() == 0
    assert _summaries(env) == ["MCP session ended (id: {})".format(sid)]


def test_the_emergency_halt_cancels_a_queued_scene_read(session_end_env):
    """cancel_pending_dispatches stops the read; the recorder gives up and keeps working."""
    env = session_end_env("saved", capture_timeout=2.0)
    server = server_mod.MCPServer(handler=_RecordingHandler())
    halted = server._sessions.create_session({"name": "halted"})

    _run_on_request_thread(lambda: server.destroy_session(halted), "DELETE /mcp")
    env.wait_for_read()
    assert main_thread.cancel_pending_dispatches("test: emergency halt") == 1

    env.run_main()  # Houdini wakes: the cancelled read does not run
    env.settle()  # the recorder stops waiting after its 2 s
    assert env.hou.calls == [] and env.writes == [] and env.lookups == []

    later = server._sessions.create_session({"name": "later"})
    _run_on_request_thread(lambda: server.destroy_session(later), "DELETE /mcp")
    env.wait_for_read(count=2)
    env.run_main()
    env.settle()
    assert _summaries(env) == ["MCP session ended (id: {})".format(later)]
