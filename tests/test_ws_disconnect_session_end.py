"""A WebSocket disconnect's session-end record: no Houdini or file work on its thread (L28).

History. When a ``/synapse`` client disconnected, ``SynapseServer._handle_client``
(server/websocket.py) wrote its Living Memory session end inline on the
connection's own thread (websockets.sync gives each connection one):
``hou.hipFile.path()`` and ``hou.getenv("JOB")`` off Houdini's main thread; for
an untitled hip, ``isNewFile`` and ``hou.text.expandString``, the second behind
a run_on_main wait of up to 10 s that counted toward the stall detector;
``ensure_scene_structure``, which creates claude/, project.md, memory.md and
agent.usd when they are missing; then two agent.usd opens and saves and a
memory.md append. The session-end recorder the MCP path already uses
(mcp/session.py, ``schedule_session_end``) now takes the end.

Scope. ``SynapseServer`` is the fallback server: the package starts it only
when the hwebserver adapter cannot load (server/start_hwebserver.py). The GUI's
hwebserver /synapse endpoint (server/hwebserver_adapter.py) writes no
session-end record, before and after this change.

These tests pin that a disconnect:

  * with SYNAPSE_AUTO_MEMORY unset (the default), returns while nothing runs
    Houdini's main thread, having made no hou.* call, posted nothing to
    hdefereval and changed no file;
  * with SYNAPSE_AUTO_MEMORY=1, still waits on the main thread from the
    connection thread for the session tracker's summary row (end_session ->
    the memory store's add, run_on_main label ``memory:add``), while the
    session-end record is still only queued; when that row's write fails, the
    record keeps its agent.usd entry and loses its memory.md summary;
  * once the main thread runs the recorder's one read, has read hou on the
    main thread only (label ``mcp:session_end:capture``) and has written the
    task suspension and the session_history entry "Session ended (client: ...)"
    on the recorder thread, never on the main or the connection thread; the
    record's end time and task cutoff are the disconnect's own time;
  * appends the session summary to memory.md only when the session ran
    commands and memory.md already exists (Mile 1 / C-2), with or without an
    agent.usd beside it; when that append fails, logs a lost summary naming
    the file and whether the agent.usd record was written, while a failure
    before log_session returns is still logged as the record not written;
  * records into the scene's existing claude/ for saved, untitled and
    relocated scenes, and creates nothing for a scene without claude/;
  * shares one agent.usd write with an MCP session end queued beside it;
  * without hou, reads, posts and writes nothing and starts no thread; without
    hdefereval (hython), posts and writes nothing, and makes no hou call on the
    connection thread: hdefereval's import guard (``hou.isUIAvailable``) runs
    on the recorder thread, once.

The fakes follow tests/test_mcp_initialize_main_thread.py: a thread-recording
hou patched into module globals (never ``sys.modules['hou']``) and an
hdefereval in ``sys.modules`` for the test only, which nothing runs but the
test's own (main) thread. They are defined here, not imported, so this file
also runs on the trees before the fix (the red control). The hython test
installs ``_VendorHdefereval``, an import hook whose module body does what the
vendor module's does under hython; the SYNAPSE_AUTO_MEMORY tests give the
session tracker ``_MemoryStore``, whose add goes through the real
``store._on_memory_main`` marshal.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import json
import logging
import os
import queue
import sys
import threading
import time
import types
from unittest.mock import Mock

import pytest

from synapse.core.protocol import SynapseResponse
from synapse.server import main_thread
from synapse.server import websocket as transport
from synapse.session.tracker import SynapseBridge

# Imported before any test patches hou, so each keeps the suite's resident.
import synapse.host.memory_lifecycle as memory_lifecycle  # noqa: E402
import synapse.memory.agent_state as agent_state  # noqa: E402
import synapse.memory.scene_memory as scene_memory  # noqa: E402
import synapse.memory.store as memory_store  # noqa: E402

session_mod = importlib.import_module("synapse.mcp.session")

# Literals, not session_mod attributes, so a tree without them still runs
# these tests to their assertions.
_RECORDS_ENV = "SYNAPSE_MCP_SESSION_END_RECORDS"
_CAPTURE_LABEL = "mcp:session_end:capture"
_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_JOIN_S = 5.0

_COMMAND = json.dumps({"type": "get_scene_info", "id": "cmd-1", "payload": {}})
_HEARTBEAT = json.dumps({"type": "heartbeat", "id": "hb-1"})


class _FakeHdefereval(types.ModuleType):
    """``executeDeferred`` only records; the test's own thread runs what was posted."""

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
        deadline = time.monotonic() + timeout
        with self._posted:
            while len(self.posted_from) < count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._posted.wait(remaining)
        return True

    def pump(self):
        """Houdini's main thread goes idle: run what was posted, on the CALLING thread."""
        ran = 0
        while True:
            try:
                fn = self.pending.get_nowait()
            except queue.Empty:
                return ran
            fn()
            ran += 1


class _Hou:
    """Records the thread, and the run_on_main label holding main, of every read."""

    def __init__(self, hip_path, is_new_file):
        self.calls = []  # (name, thread ident)
        self.holders = []
        self.ui_checks = []  # the NAME of the thread of every isUIAvailable call
        self._lock = threading.Lock()
        self.hipFile = types.SimpleNamespace(
            path=lambda: self._read("hou.hipFile.path", hip_path),
            isNewFile=lambda: self._read("hou.hipFile.isNewFile", is_new_file),
        )

    def _read(self, name, value):
        self.record(name)
        return value

    def record(self, name):
        holder = main_thread.current_main_thread_holder()
        with self._lock:
            self.calls.append((name, threading.get_ident()))
            self.holders.append(holder[0] if holder else None)

    def getenv(self, name, default=None):
        self.record("hou.getenv")
        return default

    def isUIAvailable(self):
        """hython's answer. Thread NAMES, not idents: an exited thread's ident is reused."""
        self.record("hou.isUIAvailable")
        with self._lock:
            self.ui_checks.append(threading.current_thread().name)
        return False


class _VendorHdefereval(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """``import hdefereval`` as hython runs it: a real module body, every time.

    The vendor module ends with ``if not hou.isUIAvailable(): raise
    ImportError(...)`` (hdefereval.py:240-241 in Houdini 22.0.400). Python does
    not cache a failed import, so each ``import hdefereval`` runs that body --
    a hou call -- again, on the importing thread. ``sys.modules['hdefereval'] =
    None`` fails the import without running any body.
    """

    def __init__(self, hou_fake):
        self._hou = hou_fake
        self.ran_on = []  # the NAME of the thread of every module-body run

    def find_spec(self, name, path=None, target=None):
        if name != "hdefereval":
            return None
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec):
        return None  # the default module object

    def exec_module(self, module):
        self.ran_on.append(threading.current_thread().name)
        module.hou = self._hou
        if not self._hou.isUIAvailable():
            raise ImportError("hdefereval is only available in a graphical Houdini")


def _memory_row_on_main(store, content, **kwargs):
    """The memory store's add body: runs where ``store._on_memory_main`` sends it."""
    holder = main_thread.current_main_thread_holder()
    store.ran.append((content, holder[0] if holder else None, threading.current_thread().name))


# Named "add" so the real marshal labels the dispatch "memory:add", as it does
# SynapseMemory.add (memory/store.py, @_on_memory_main).
_memory_row_on_main.__name__ = "add"
_marshalled_memory_row = memory_store._on_memory_main(_memory_row_on_main)


class _MemoryStore:
    """The session tracker's memory store (``bridge._synapse``) for SYNAPSE_AUTO_MEMORY=1.

    ``add`` records the thread that CALLED it, then goes through the real
    ``_on_memory_main`` marshal, as SynapseMemory.add does: run_on_main from
    the calling thread. ``summary_fails`` makes the session summary row's add
    raise MainThreadTimeout, as run_on_main does when the main thread does not
    answer in time, without the 10 s wait.
    """

    def __init__(self, summary_fails=False):
        self.calls = []  # (content, calling thread name)
        self.ran = []  # (content, run_on_main label holding main, thread name)
        self._summary_fails = summary_fails

    def add(self, content, **kwargs):
        self.calls.append((content, threading.current_thread().name))
        if self._summary_fails and kwargs.get("tags") == ["session", "summary"]:
            raise main_thread.MainThreadTimeout(
                "Houdini's main thread didn't respond in time")
        return _marshalled_memory_row(self, content, **kwargs)


class _Handler:
    """Runs a command and counts it into the session, as the executor's log does."""

    def __init__(self, bridge):
        self._bridge = bridge
        self._session_id = None

    def set_session_id(self, session_id):
        self._session_id = session_id

    def set_user_id(self, user_id):
        pass

    def handle(self, command):
        session = self._bridge.get_session(self._session_id)
        if session is not None:
            session.commands_executed += 1  # bridge.log_action, after the command
        return SynapseResponse(id=command.id, success=True, data={})


def _bridge():
    """The real session tracker with no memory store: no Moneta, no main-thread work."""
    bridge = object.__new__(SynapseBridge)
    bridge._sessions, bridge._lock, bridge._synapse = {}, threading.Lock(), None
    return bridge


def _server(handler, client_ids):
    server = object.__new__(transport.SynapseServer)
    server._handler = handler
    server._clients_lock, server._client_counter = threading.Lock(), 0
    server._clients, server._client_ids = set(), {}
    server._client_cancels, server._client_sessions = {}, {}
    server._on_client_connect, server._on_client_disconnect = client_ids.append, None
    server._deploy_config = server._session_manager = server._user_directory = None
    server._rate_limiter = server._circuit_breaker = None
    server._enable_resilience = False
    server._avg_latency, server._latency_alpha = 0.0, 0.2
    return server


def _tree(root):
    """Every folder and file under *root*, with each file's size and mtime."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            found[os.path.relpath(os.path.join(dirpath, name), root)] = "folder"
        for name in filenames:
            stat = os.stat(os.path.join(dirpath, name))
            found[os.path.relpath(os.path.join(dirpath, name), root)] = (
                stat.st_size, stat.st_mtime_ns)
    return found


def _changes(before, after):
    return sorted(set(before.items()) ^ set(after.items()), key=str)


def _same_path(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def _scene(tmp_path, layout, monkeypatch, memory_md, agent_usd):
    """A scene on disk; ``claude`` is the folder its session-end record belongs in."""
    if layout in ("saved", "no_claude"):
        folder = tmp_path / "shot"
        hip, is_new, home = folder / "shot.hip", False, folder
    elif layout == "relocated":
        # The hip's folder has no claude/; this process recorded a relocation.
        folder = tmp_path / "locked_shot"
        hip, is_new, home = folder / "shot.hip", False, tmp_path / "moved"
        monkeypatch.setitem(scene_memory._RELOCATED, os.path.normpath(str(folder)), str(home))
    elif layout == "untitled":
        folder = tmp_path / "bin"  # Houdini's never-saved placeholder; not on disk
        hip, is_new = folder / "untitled.hip", True
        home = tmp_path / "untitled" / "sessions" / "launch"
    else:
        raise AssertionError(layout)
    if layout != "untitled":
        folder.mkdir(parents=True)
        hip.write_text("", encoding="utf-8")
    scene = {"hip": str(hip), "is_new": is_new, "home": str(home),
             "claude": str(home / "claude"), "agent_usd": str(home / "claude" / "agent.usd"),
             "memory_md": str(home / "claude" / "memory.md")}
    if layout != "no_claude":
        (home / "claude").mkdir(parents=True)
        if agent_usd:
            (home / "claude" / "agent.usd").write_text("#usda 1.0\n", encoding="utf-8")
        if memory_md:
            (home / "claude" / "memory.md").write_text("# Scene memory\n", encoding="utf-8")
    return scene


class _Env:
    """One test's fakes, its connections, and every session-end write with its thread."""

    def __init__(self, root, scene, hou, hdefereval, recorder, server):
        self.root, self.scene = root, scene
        self.hou = hou  # None: outside Houdini
        self.hdefereval = hdefereval  # None: no hdefereval (hython)
        self.recorder = recorder  # None: a tree without the recorder (red control)
        self.server = server
        self.client_ids = []
        self.writes = []  # (writer, path, detail, thread ident)
        self.workers = []

    def connect(self, *messages):
        """One client sends *messages* and closes, on its own thread; returns at once.

        Returns (worker, outcome): outcome gets the thread's ``ident`` and any
        ``error`` it raised.
        """
        socket = Mock()
        socket.request.headers = {}
        socket.messages = list(messages)
        outcome = {}

        def _connection():
            outcome["ident"] = threading.get_ident()
            try:
                self.server._handle_client(socket)
            except BaseException as exc:  # surfaced by the caller
                outcome["error"] = exc

        worker = threading.Thread(target=_connection, name="ws-connection", daemon=True)
        self.workers.append(worker)
        worker.start()
        return worker, outcome

    def disconnect(self, *messages):
        """One client sends *messages* and closes. Nothing runs Houdini's main thread."""
        worker, outcome = self.connect(*messages)
        worker.join(_JOIN_S)
        assert not worker.is_alive(), (
            "the disconnect did not return within 5 s while Houdini's main thread was "
            "idle: the connection thread is waiting on main-thread work")
        if "error" in outcome:
            raise outcome["error"]
        return outcome["ident"]

    def problems(self, connection, before):
        """What the disconnect did before Houdini's main thread ran anything."""
        found = []
        if self.hou is not None and self.hou.calls:
            found.append("hou.* called before the main thread ran anything: {}".format(
                [(name, "connection thread" if ident == connection else "another thread")
                 for name, ident in self.hou.calls]))
        if self.hdefereval is not None and connection in self.hdefereval.posted_from:
            found.append("the connection thread posted to hdefereval")
        if self.writes:
            found.append("session-end writes before the main thread's read: {}".format(
                [(w[0], "connection thread" if w[3] == connection else "another thread")
                 for w in self.writes]))
        changed = _changes(before, _tree(self.root))
        if changed:
            found.append("files changed: {}".format(changed))
        return found

    def drain(self):
        """Houdini's main thread comes back: run what was posted until the recorder is idle.

        Every hou read so far must have run here, on the main thread.
        """
        deadline = time.monotonic() + _JOIN_S
        while True:
            self.hdefereval.pump()
            if self.recorder is None or self.recorder.wait_idle(0.05):
                break
            assert time.monotonic() < deadline, "the session-end recorder never went idle"
        self.hdefereval.pump()  # a wake left behind by a read that was already done
        main = threading.get_ident()
        off_main = [name for name, ident in self.hou.calls if ident != main]
        assert off_main == [], "hou.* ran off Houdini's main thread: {}".format(off_main)
        return main

    def recorder_ident(self):
        thread = getattr(self.recorder, "_thread", None)
        return thread.ident if thread is not None else None

    def recorder_started(self):
        return getattr(self.recorder, "_thread", None) is not None

    def close(self):
        """Finish any connection, release and stop the recorder, leave run_on_main idle."""
        deadline = time.monotonic() + 30.0
        for worker in self.workers:  # a pre-fix tree's connection waits on main
            while worker.is_alive() and time.monotonic() < deadline:
                if self.hdefereval is not None:
                    self.hdefereval.pump()
                worker.join(0.05)
        if self.recorder is None:
            return
        if self.hdefereval is not None:
            while not self.recorder.wait_idle(0.05):
                self.hdefereval.pump()
                assert time.monotonic() < deadline, "the session-end recorder never went idle"
            self.hdefereval.pump()
        stop = getattr(self.recorder, "stop", None)
        if stop is not None:  # a pre-fix tree's recorder has no stop()
            assert stop(_JOIN_S), "the session-end recorder thread did not stop"
        with main_thread._deferred_lock:
            left = list(main_thread._deferred_calls), main_thread._deferred_wake
        assert left == ([], None), "the test left run_on_main's deferred queue non-empty"


@pytest.fixture
def ws_env(monkeypatch, tmp_path):
    made = []

    def _make(layout="saved", memory_md=True, agent_usd=True, hou_present=True,
              hdefereval_present=True):
        root = tmp_path / "scene"
        root.mkdir()
        scene = _scene(root, layout, monkeypatch, memory_md, agent_usd)
        hou = _Hou(scene["hip"], scene["is_new"]) if hou_present else None
        monkeypatch.setattr(session_mod, "hou", hou, raising=False)
        # Before the session-end recorder, the disconnect hook read websocket.py's own hou.
        monkeypatch.setattr(transport, "hou", hou, raising=False)
        monkeypatch.setattr(transport, "HOU_AVAILABLE", hou is not None)
        monkeypatch.setenv(_RECORDS_ENV, "1")  # tests/conftest.py turns records off
        monkeypatch.delenv("SYNAPSE_AUTO_MEMORY", raising=False)
        hdefereval = _FakeHdefereval() if hdefereval_present else None
        monkeypatch.setitem(sys.modules, "hdefereval", hdefereval)  # None: import fails
        with main_thread._deferred_lock:
            assert main_thread._deferred_wake is None, (
                "an earlier test left a run_on_main wake that nothing ran")
        recorder = None
        if hasattr(session_mod, "_SessionEndRecorder"):
            try:
                recorder = session_mod._SessionEndRecorder(capture_timeout=_JOIN_S)
            except TypeError:  # an older recorder takes no timeout
                recorder = session_mod._SessionEndRecorder()
            monkeypatch.setattr(session_mod, "_RECORDER", recorder)
        bridge = _bridge()
        monkeypatch.setattr(transport, "get_bridge", lambda: bridge)
        monkeypatch.setattr(transport, "get_auth_key", lambda: None)
        monkeypatch.setattr(transport, "validate_origin", lambda *a, **k: True)
        monkeypatch.setattr(transport, "iter_messages",
                            lambda websocket, cancel_event, *a, **k: iter(websocket.messages))
        env = _Env(str(root), scene, hou, hdefereval, recorder, None)
        env.server = _server(_Handler(bridge), env.client_ids)

        def _suspend(path, created_at_or_before=None):
            env.writes.append(
                ("suspend_all_tasks", path, created_at_or_before, threading.get_ident()))

        def _log(path, summary):
            env.writes.append(("log_session", path, dict(summary), threading.get_ident()))

        real_write_session_end = scene_memory.write_session_end

        def _memory_md(scene_dir, summary):
            env.writes.append(("write_session_end", scene_dir, dict(summary), threading.get_ident()))
            real_write_session_end(scene_dir, summary)

        monkeypatch.setattr(agent_state, "suspend_all_tasks", _suspend)
        monkeypatch.setattr(agent_state, "log_session", _log)
        monkeypatch.setattr(scene_memory, "write_session_end", _memory_md)
        if layout == "untitled" and hou is not None:
            def _existing_unsaved_base():  # in Houdini this reads hou.text.expandString
                hou.record("memory_lifecycle.existing_unsaved_base")
                return scene["home"]

            monkeypatch.setattr(memory_lifecycle, "existing_unsaved_base", _existing_unsaved_base)
        made.append(env)
        return env

    yield _make
    for env in made:  # before monkeypatch undoes the fakes
        env.close()


# ---------------------------------------------------------------------------
# 1. The red control: the disconnect itself
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("layout", ["saved", "untitled", "no_claude"])
def test_a_disconnect_returns_with_main_idle_and_no_houdini_or_file_work(ws_env, layout):
    """One command, then close: back with main unpumped, no hou, no post, no file changed.

    SYNAPSE_AUTO_MEMORY is unset here (ws_env removes it), as by default; with
    it on, see test_with_auto_memory_on_a_disconnect_still_waits_on_main_for_the_summary_row.
    """
    env = ws_env(layout)
    before = _tree(env.root)

    connection = env.disconnect(_COMMAND)

    assert env.problems(connection, before) == []


# ---------------------------------------------------------------------------
# 2. The record, once Houdini's main thread runs the read
# ---------------------------------------------------------------------------
def test_the_record_is_read_on_main_and_written_on_the_recorder_thread(ws_env):
    """hou on main only (labelled); suspend, session_history and memory.md on the recorder.

    The end, and so the task cutoff, is the disconnect itself: only an MCP
    session that the sweep removes ends at an earlier moment (its last request).
    """
    env = ws_env("saved")
    before = _tree(env.root)
    called = time.time()
    connection = env.disconnect(_COMMAND)
    returned = time.time()
    assert env.problems(connection, before) == []

    main = env.drain()  # fails if any hou read ran off the main thread

    assert [name for name, _ident in env.hou.calls] == ["hou.hipFile.path"]
    assert set(env.hou.holders) == {_CAPTURE_LABEL}, env.hou.holders
    recorder = env.recorder_ident()
    assert [(w[0], w[3]) for w in env.writes] == [
        ("suspend_all_tasks", recorder), ("log_session", recorder),
        ("write_session_end", recorder)], "the record was not written on the recorder thread"
    assert recorder not in (main, connection)
    cutoff, record = env.writes[0][2], env.writes[1][2]
    assert record["summary_text"] == "Session ended (client: {})".format(env.client_ids[0])
    assert isinstance(cutoff, float) and record["end_time"] == time.strftime(
        _STAMP, time.gmtime(cutoff)), "the task cutoff and the end time differ"
    assert called <= cutoff <= returned, "the disconnect's end is not the time it happened"


# ---------------------------------------------------------------------------
# 3. memory.md: a summary only for a session that ran commands, into a file that exists
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("commands_ran,memory_md", [
    (True, True), (False, True), (True, False)], ids=["ran-exists", "idle-exists", "ran-missing"])
def test_memory_md_gets_the_summary_only_when_commands_ran_and_it_exists(
        ws_env, commands_ran, memory_md):
    env = ws_env("saved", memory_md=memory_md)
    md_path = env.scene["memory_md"]
    before_md = open(md_path, encoding="utf-8").read() if memory_md else None
    before = _tree(env.root)
    connection = env.disconnect(_COMMAND if commands_ran else _HEARTBEAT)
    assert env.problems(connection, before) == []

    env.drain()

    assert [w[0] for w in env.writes if w[0] != "write_session_end"] == [
        "suspend_all_tasks", "log_session"], "the agent.usd record is written either way"
    appended = [w for w in env.writes if w[0] == "write_session_end"]
    if commands_ran and memory_md:
        assert len(appended) == 1 and _same_path(appended[0][1], env.scene["claude"])
        assert appended[0][3] == env.recorder_ident()
        added = open(md_path, encoding="utf-8").read()[len(before_md):]
        assert added.startswith("### Session End\n") and "**Commands:** 1" in added, added
        assert appended[0][2]["stopped_at"] == env.writes[1][2]["end_time"]
    else:
        assert appended == [], "a summary was written for {}".format(
            "an idle session" if memory_md else "a scene without memory.md")
        if memory_md:
            assert open(md_path, encoding="utf-8").read() == before_md
        else:
            assert not os.path.exists(md_path), "the session end created memory.md"


def test_memory_md_without_agent_usd_gets_the_summary_and_no_agent_usd(ws_env):
    """claude/ holds memory.md but no agent.usd: the summary is kept, nothing is created."""
    env = ws_env("saved", agent_usd=False)
    md_path = env.scene["memory_md"]
    before_md = open(md_path, encoding="utf-8").read()
    before = _tree(env.root)
    connection = env.disconnect(_COMMAND)
    assert env.problems(connection, before) == []

    env.drain()

    assert [(w[0], w[3]) for w in env.writes] == [("write_session_end", env.recorder_ident())]
    assert "**Commands:** 1" in open(md_path, encoding="utf-8").read()[len(before_md):]
    assert not os.path.exists(env.scene["agent_usd"]), "the session end created agent.usd"


class _SessionLog(logging.Handler):
    """Every record ``synapse.mcp.session`` logs, from any thread."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def warnings(self):
        return [r for r in self.records if r.levelno >= logging.WARNING]


@pytest.fixture
def session_log():
    """Caught on the module's own logger, so propagation settings do not matter."""
    logger = logging.getLogger("synapse.mcp.session")
    handler, level = _SessionLog(), logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(level)


@pytest.mark.parametrize("agent_usd", [True, False], ids=["agent-usd", "no-agent-usd"])
def test_a_memory_md_append_that_fails_is_logged_as_a_lost_summary(
        ws_env, monkeypatch, session_log, agent_usd):
    """memory.md refuses the append (read-only, or its lock timed out): only the summary is lost.

    The agent.usd record, when the scene has an agent.usd, is written first.
    The append's failure is logged as a summary not appended to that
    memory.md, saying whether the agent.usd record was written -- never as
    the whole record not written.
    """
    env = ws_env("saved", agent_usd=agent_usd)

    def _read_only(scene_dir, summary):
        env.writes.append(("write_session_end", scene_dir, dict(summary), threading.get_ident()))
        raise PermissionError(13, "Permission denied", os.path.join(scene_dir, "memory.md"))

    monkeypatch.setattr(scene_memory, "write_session_end", _read_only)
    env.disconnect(_COMMAND)
    env.drain()

    record = ["suspend_all_tasks", "log_session"] if agent_usd else []
    assert [w[0] for w in env.writes] == record + ["write_session_end"]
    warned = session_log.warnings()
    assert len(warned) == 1, [r.getMessage() for r in warned]
    message = warned[0].getMessage()
    assert "was not written" not in message, message
    assert os.path.normcase(
        "session summary not appended to " + env.scene["memory_md"]) in os.path.normcase(message)
    assert message.endswith(
        "the agent.usd record was written" if agent_usd
        else "the scene has no agent.usd, so no record was written either"), message
    assert warned[0].exc_info is not None and warned[0].exc_info[0] is PermissionError


def test_a_failure_before_log_session_returns_is_logged_as_an_unwritten_record(
        ws_env, monkeypatch, session_log):
    """log_session raises: the recorder reports the record as not written.

    The boundary of the test above. The memory.md append that would follow
    is not attempted.
    """
    env = ws_env("saved")

    def _save_fails(path, summary):
        env.writes.append(("log_session", path, dict(summary), threading.get_ident()))
        raise OSError("agent.usd could not be saved")

    monkeypatch.setattr(agent_state, "log_session", _save_fails)
    env.disconnect(_COMMAND)
    env.drain()

    assert [w[0] for w in env.writes] == ["suspend_all_tasks", "log_session"]
    warned = [r.getMessage() for r in session_log.warnings()]
    assert len(warned) == 1 and warned[0].startswith("Session-end record for ") and (
        warned[0].endswith(" was not written")), warned


# ---------------------------------------------------------------------------
# 4. Layouts, and no Houdini to read
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("layout", ["saved", "untitled", "relocated"])
def test_the_record_lands_in_the_scenes_existing_claude_folder(ws_env, layout):
    env = ws_env(layout)
    before = _tree(env.root)
    connection = env.disconnect(_COMMAND)
    assert env.problems(connection, before) == []

    env.drain()

    got = [(w[0], w[1]) for w in env.writes]
    want = [("suspend_all_tasks", env.scene["agent_usd"]), ("log_session", env.scene["agent_usd"]),
            ("write_session_end", env.scene["claude"])]
    assert len(got) == len(want) and all(
        g[0] == w[0] and _same_path(g[1], w[1]) for g, w in zip(got, want)), got
    reads = [name for name, _ident in env.hou.calls]
    if layout == "untitled":
        assert reads == ["hou.hipFile.path", "hou.hipFile.isNewFile",
                         "memory_lifecycle.existing_unsaved_base"]
    else:
        assert reads == ["hou.hipFile.path"]
        assert _same_path(scene_memory.resolve_hip_dir(env.scene["hip"]), env.scene["home"])


def test_a_scene_without_claude_gets_no_record_and_no_folder(ws_env):
    env = ws_env("no_claude")
    before = _tree(env.root)
    connection = env.disconnect(_COMMAND)
    assert env.problems(connection, before) == []

    env.drain()

    assert env.writes == []
    assert not os.path.exists(env.scene["claude"]), "the session end created claude/"
    assert _changes(before, _tree(env.root)) == []


@pytest.mark.parametrize("missing", ["hou", "hdefereval"])
def test_without_hou_or_hdefereval_a_disconnect_posts_and_writes_nothing(ws_env, missing):
    """Outside Houdini, or with no hdefereval (no main thread to post to): no record at all.

    Without hou nothing starts. Without hdefereval the recorder thread (not the
    connection thread) finds that once, drops the end and exits; a later
    disconnect queues nothing and starts no thread.
    """
    env = ws_env("saved", hou_present=missing != "hou",
                 hdefereval_present=missing != "hdefereval")
    before = _tree(env.root)

    connection = env.disconnect(_COMMAND)

    assert env.problems(connection, before) == []
    if env.recorder is not None:
        assert env.recorder.wait_idle(_JOIN_S)
    if missing == "hou":
        assert not env.recorder_started(), "the session-end recorder started"
    else:
        checker = env.recorder._thread
        assert checker is not None and checker.name == "synapse-mcp-session-end"
        checker.join(_JOIN_S)
        assert not checker.is_alive(), "the recorder thread kept running without hdefereval"
        env.disconnect(_COMMAND)
        assert env.recorder.wait_idle(_JOIN_S)
        assert env.recorder._thread is checker, "a later disconnect started another recorder"
    assert env.writes == [] and _changes(before, _tree(env.root)) == []
    if env.hou is not None:
        assert env.hou.calls == []
    if env.hdefereval is not None:
        assert env.hdefereval.posted_from == []


def test_in_hython_a_disconnect_makes_no_hou_call_on_its_thread(ws_env, monkeypatch):
    """hdefereval's import guard calls hou.isUIAvailable(): never on the connection thread.

    Under hython ``hou`` imports and ``import hdefereval`` runs the vendor body
    and fails, on every attempt. The check belongs to the recorder thread:
    once per process, and nothing is recorded.
    """
    env = ws_env("saved", hdefereval_present=False)
    vendor = _VendorHdefereval(env.hou)
    monkeypatch.delitem(sys.modules, "hdefereval")  # absent, so the import finds the hook
    monkeypatch.setattr(sys, "meta_path", [vendor] + sys.meta_path)
    before = _tree(env.root)

    for _ in range(2):
        env.disconnect(_COMMAND)
        if env.recorder is not None:
            assert env.recorder.wait_idle(_JOIN_S)

    on_connection = [name for name in env.hou.ui_checks if name != "synapse-mcp-session-end"]
    assert on_connection == [], (
        "a disconnect ran hdefereval's import guard (hou.isUIAvailable) on its own "
        "thread: {}".format(on_connection))
    assert env.hou.ui_checks == ["synapse-mcp-session-end"], (
        "the recorder thread should run the import guard exactly once: {}".format(
            env.hou.ui_checks))
    assert vendor.ran_on == ["synapse-mcp-session-end"]
    assert [name for name, _ident in env.hou.calls] == ["hou.isUIAvailable"]
    assert env.writes == [] and _changes(before, _tree(env.root)) == []


# ---------------------------------------------------------------------------
# One agent.usd write for ends from both callers
# ---------------------------------------------------------------------------
def test_disconnects_queued_beside_an_mcp_session_end_share_one_record(ws_env):
    """log_session names its prim by the second, so ends queued together must be one write."""
    env = ws_env("saved")
    manager = session_mod.MCPSessionManager()
    mcp_id = manager.create_session({"name": "mcp"})
    assert manager.destroy_session(mcp_id) is True
    if env.recorder is not None and hasattr(session_mod, "schedule_session_end"):
        # The recorder's read for the MCP end now waits on a main thread that is busy.
        assert env.hdefereval.wait_for_posts(1, _JOIN_S)
    before = _tree(env.root)
    first = env.disconnect(_COMMAND)
    second = env.disconnect(_COMMAND)
    assert env.problems(first, before) == [] and env.problems(second, before) == []

    env.drain()

    records = [w[2] for w in env.writes if w[0] == "log_session"]
    assert [r["summary_text"] for r in records] == [
        "MCP session ended (id: {}); Sessions ended (clients: {})".format(
            mcp_id, ", ".join(env.client_ids))], records
    cutoffs = [w[2] for w in env.writes if w[0] == "suspend_all_tasks"]
    assert len(cutoffs) == 1 and records[0]["end_time"] == time.strftime(
        _STAMP, time.gmtime(cutoffs[0]))
    assert len([w for w in env.writes if w[0] == "write_session_end"]) == 2, (
        "each disconnect's summary goes to memory.md; the MCP end has none")


# ---------------------------------------------------------------------------
# SYNAPSE_AUTO_MEMORY=1: end_session's memory-store row did not move
# ---------------------------------------------------------------------------
def _until(condition, what):
    deadline = time.monotonic() + _JOIN_S
    while not condition():
        assert time.monotonic() < deadline, what
        time.sleep(0.01)


def _run_one_wake(env):
    """Houdini's main thread runs ONE posted wake (one payload), on this thread."""
    env.hdefereval.pending.get(timeout=_JOIN_S)()


def test_with_auto_memory_on_a_disconnect_still_waits_on_main_for_the_summary_row(
        ws_env, monkeypatch):
    """SYNAPSE_AUTO_MEMORY=1: the summary row waits on main from the connection thread.

    The session tracker's end_session writes the session summary row to the
    memory store, whose add is @_on_memory_main: run_on_main from the calling
    thread (label memory:add, 10 s once posted, a timeout counted by the stall
    detector). Only the session-end record moved to the recorder, so with
    auto-memory on a disconnect still waits for Houdini's main thread; the
    record itself is still only queued. Today's behaviour, pinned so that
    changing it is a decision (docs/studio/DEPLOYMENT.md, SYNAPSE_AUTO_MEMORY).
    """
    env = ws_env("saved")
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", "1")
    monkeypatch.setattr(memory_store, "HOU_AVAILABLE", True)
    store = _MemoryStore()
    transport.get_bridge()._synapse = store
    md_path = env.scene["memory_md"]
    before_md = open(md_path, encoding="utf-8").read()
    main_name = threading.current_thread().name

    worker, outcome = env.connect(_COMMAND)
    # The first command's session-start row waits on main too (not this test's subject).
    _run_one_wake(env)
    # The disconnect: end_session's summary row is queued for the main thread.
    _until(lambda: len(store.calls) == 2 and env.hdefereval.pending.qsize() == 1,
           "the disconnect never asked the main thread for its summary row")
    with main_thread._pending_lock:
        queued = [entry[2] for entry in main_thread._pending_dispatches.values()]
    assert queued == ["memory:add"], queued
    worker.join(0.2)
    assert worker.is_alive(), "the disconnect returned before main ran its summary row"
    assert env.writes == [] and not env.recorder_started(), (
        "the session-end record was queued before the summary row was written")

    _run_one_wake(env)  # main writes the summary row; the disconnect goes on
    worker.join(_JOIN_S)
    assert not worker.is_alive(), "the disconnect did not return once main ran its row"
    if "error" in outcome:
        raise outcome["error"]

    assert [thread for _content, thread in store.calls] == ["ws-connection"] * 2, (
        "the memory-store rows were not called from the connection thread")
    assert store.calls[0][0].startswith("AI session started")
    assert [(label, thread) for _content, label, thread in store.ran] == [
        ("memory:add", main_name)] * 2
    env.drain()
    recorder = env.recorder_ident()
    assert [(w[0], w[3]) for w in env.writes] == [
        ("suspend_all_tasks", recorder), ("log_session", recorder),
        ("write_session_end", recorder)], "the session-end record did not go to the recorder"
    assert "**Commands:** 1" in open(md_path, encoding="utf-8").read()[len(before_md):]


def test_with_auto_memory_on_a_failed_summary_row_loses_only_the_memory_md_summary(
        ws_env, monkeypatch):
    """SYNAPSE_AUTO_MEMORY=1 and the summary row times out: memory.md gets nothing.

    end_session raises (run_on_main's MainThreadTimeout), so the disconnect
    has no summary text. The session-end record is still queued and still
    writes its agent.usd entry; the memory.md summary is lost.
    """
    env = ws_env("saved")
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", "1")
    monkeypatch.setattr(memory_store, "HOU_AVAILABLE", False)  # the start row runs inline
    store = _MemoryStore(summary_fails=True)
    transport.get_bridge()._synapse = store
    md_path = env.scene["memory_md"]
    before_md = open(md_path, encoding="utf-8").read()
    before = _tree(env.root)

    connection = env.disconnect(_COMMAND)

    assert env.problems(connection, before) == []
    assert [content.startswith("AI session started") for content, _t in store.calls] == [
        True, False], store.calls
    env.drain()
    assert [w[0] for w in env.writes] == ["suspend_all_tasks", "log_session"], (
        "the agent.usd record should still be written, and memory.md nothing")
    assert open(md_path, encoding="utf-8").read() == before_md
