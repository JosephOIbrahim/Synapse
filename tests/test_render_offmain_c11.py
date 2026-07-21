"""C11 (CTO Remediation Mile 3.5) — render blocking IO moved off the main thread.

Before C11, _render_on_main ran the up-to-15s output-file poll (time.sleep loop)
and the iconvert subprocess INSIDE the main-thread closure — freezing Houdini's
UI and the whole marshal pipeline for the flush window on every render. Now the
closure ends right after node.render() (+ $HFS resolve); poll + iconvert run on
the calling (WS handler) thread, and the flipbook fallback is a second,
conditional main-thread hop.

The pin: NO time.sleep runs inside the main-thread closure.

RE-ANCHORED (marshal-deadlock migration). The previous version of this guard
instrumented a fake ``hdefereval.executeInMainThreadWithResult``. That primitive
is gone — handlers_render marshals via ``server.main_thread.run_on_main``, which
posts with the NON-blocking ``executeDeferred``. Worse, pytest's caller IS the
main thread, so run_on_main took fast path 2 and never touched the fake at all:
the "inside the closure" flag stayed False forever and the sole assertion passed
trivially. Green while pinning nothing.

This version anchors on the real mechanism:

  * ``_handle_render`` is driven from a GENUINE worker thread, so run_on_main
    skips fast path 2 and actually takes the deferred path.
  * The fake ``executeDeferred`` runs each posted closure on its own
    "fake-houdini-main" thread and publishes that thread's id while it runs, so
    "inside the closure" is decided by real thread identity, not a global flag
    that concurrent off-main work could smear.
  * The ROP no longer writes its output during ``render()`` — the file appears
    only after the poll has genuinely slept. Without this the poll returned on
    its first check and the guard could not have seen a sleep anywhere.

Proved to fail red (see the report for this change) by temporarily moving the
poll loop back inside ``_render_on_main``: on_main == 2, assertion fires.
"""

import contextlib
import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

# Established handler-test convention: fakes before importing handlers.
_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)
_hde = ModuleType("hdefereval")
_hde.executeDeferred = staticmethod(lambda fn, *a, **k: fn(*a, **k))
_hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
sys.modules.setdefault("hou", _mock_hou)
sys.modules.setdefault("hdefereval", _hde)

from synapse.server.handlers import SynapseHandler  # noqa: E402


def test_no_sleep_inside_main_thread_closure(tmp_path, monkeypatch):
    from synapse.server import handlers_render as hr

    out_file = tmp_path / "render_0001.exr"

    class _Parm:
        def __init__(self, v=""):
            self._v = v

        def eval(self):
            return self._v

        def set(self, v):
            self._v = v

    picture = _Parm(str(tmp_path / "render_$F4.exr"))

    rendered = {"called": False}

    class _Rop:
        def type(self):
            return SimpleNamespace(name=lambda: "karma")

        def parm(self, name):
            return picture if name == "picture" else None

        def render(self, frame_range=None, verbose=False):
            # Deliberately does NOT write the output: Karma XPU's delayed flush
            # is the whole reason the poll loop exists. The file lands after the
            # poll has actually slept (see spy_sleep) — otherwise the poll would
            # short-circuit on its first check and this guard would observe no
            # sleep at all, on any thread.
            rendered["called"] = True

        def path(self):
            return "/out/karma1"

    fake_hou = SimpleNamespace(
        node=lambda p: _Rop(),
        frame=lambda: 1,
        text=SimpleNamespace(expandString=lambda s: str(tmp_path)),
        ui=MagicMock(),
        paneTabType=SimpleNamespace(SceneViewer="SceneViewer"),
        setFrame=lambda f: None,
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )

    # Fake Houdini event loop. run_on_main posts here (non-blocking) whenever the
    # caller is off-main; we run the payload on a dedicated thread and publish
    # that thread's id for as long as the closure is executing.
    main_closure_tid = {"tid": None}
    deferred_posts = []
    loop_threads = []

    fake_hde = ModuleType("hdefereval")

    def _execute_deferred(cb):
        deferred_posts.append(cb)

        def _runner():
            main_closure_tid["tid"] = threading.get_ident()
            try:
                cb()
            finally:
                main_closure_tid["tid"] = None

        t = threading.Thread(target=_runner, name="fake-houdini-main")
        loop_threads.append(t)
        t.start()

    def _blocking_primitive(*_a, **_k):
        raise AssertionError(
            "executeInMainThreadWithResult self-deadlocks on a main-thread "
            "caller — the render marshal must not use it"
        )

    fake_hde.executeDeferred = _execute_deferred
    fake_hde.executeInMainThreadWithResult = _blocking_primitive

    # time.sleep spy: attributed by REAL thread identity, so a sleep on the
    # fake-main thread (i.e. inside the marshalled closure) is unmistakable.
    sleeps = {"on_main": 0, "off_main": 0}
    ticks = [0]
    real_sleep = time.sleep

    def spy_sleep(s):
        if threading.get_ident() == main_closure_tid["tid"]:
            sleeps["on_main"] += 1
        else:
            sleeps["off_main"] += 1
        # Simulate the delayed flush landing partway through the poll. Counted
        # regardless of which thread slept so that a REGRESSION (poll moved back
        # inside the closure) still completes the render and fails on the
        # assertion below, rather than dying in the "output wasn't created" path.
        ticks[0] += 1
        if ticks[0] >= 2 and rendered["called"]:
            out_file.write_bytes(b"EXR")
        real_sleep(0)  # don't actually wait in the test

    g = SynapseHandler._handle_render.__globals__   # handlers_render namespace
    monkeypatch.setitem(g, "hou", fake_hou)
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)
    monkeypatch.setattr(hr.time, "sleep", spy_sleep)

    h = SynapseHandler()

    # Drive the handler from a genuine worker thread. On the main thread
    # run_on_main takes fast path 2 (inline, correct — but then nothing is ever
    # deferred and this guard would observe nothing).
    outcome = {}
    caller_tid = {"tid": None}

    def _caller():
        caller_tid["tid"] = threading.get_ident()
        try:
            outcome["result"] = h._handle_render({"node": "/out/karma1", "frame": 1})
        except BaseException as exc:  # noqa: BLE001 - re-surfaced below
            outcome["error"] = exc

    worker = threading.Thread(target=_caller, name="fake-ws-handler")
    worker.start()
    worker.join(timeout=60)
    for t in loop_threads:
        t.join(timeout=10)

    assert not worker.is_alive(), "render handler never returned"
    assert "error" not in outcome, outcome.get("error")
    result = outcome["result"]

    assert result["image_path"]                       # render path resolved

    # Non-vacuity guards: the marshal really happened, on a thread that is NOT
    # the caller's, and the poll really slept. Without these, "on_main == 0" is
    # satisfiable by doing nothing at all.
    assert deferred_posts, "run_on_main never deferred — the marshal path was not exercised"
    assert main_closure_tid["tid"] is None             # closure finished
    assert loop_threads and loop_threads[0].ident != caller_tid["tid"]
    assert sleeps["off_main"] >= 1, "the output-file poll never slept — guard is vacuous"

    # THE C11 invariant.
    assert sleeps["on_main"] == 0, "blocking poll ran inside the main-thread closure"
