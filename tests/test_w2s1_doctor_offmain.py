"""W2-S1 — doctor off-main: the F1 crash class closed by marshalling first.

Context. The install/ops doctor (server/doctor.py::run_doctor) is dispatched
OFF Houdini's main thread on the in-Houdini hwebserver transport (W2-S1's
mcp/server.py branch) so its ~514 ms cold store-construct + embedder init no
longer pins Houdini's main thread. But a bare ``hou.*`` call from a worker
thread faults the process NATIVELY — a crash no ``try/except`` can catch
(W1-MTFIX finding F1). So every ``hou.*`` the doctor reaches off-main must be
marshalled to the main thread FIRST. This module pins that, without a live
Houdini, by:

  * a fake ``hou`` whose every read RECORDS the thread it ran on, and
  * a fake ``hdefereval`` whose ``executeDeferred`` runs the deferred callback
    on the test's MAIN thread — i.e. a stand-in for Houdini's main-thread event
    loop, so ``run_on_main``'s DEFERRED path is genuinely exercised.

Construct off a worker thread and assert every hou touch landed on the MAIN
thread (marshalled). The NEGATIVE CONTROL runs the SAME construct with the
marshal disabled and asserts hou IS touched off-main — so the positive tests
can genuinely fail (Law 1).

Pure logic + stdlib threading. Runs under stock pytest, no Houdini.
"""

import queue
import sys
import threading
import time
import types
from pathlib import Path

import pytest

import synapse.memory.store as store_mod
from synapse.memory.store import SynapseMemory


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------

class _MainThreadPump:
    """Stand-in for Houdini's main-thread event loop.

    ``executeDeferred(fn)`` enqueues fn; ``pump_until(done)`` runs queued fns on
    the CALLING thread (the test's main thread) until *done* is set. This is
    what lets ``run_on_main``'s deferred path resolve: the worker posts fn here
    and blocks on its own Event; this pump runs fn on main and wakes it.
    """

    def __init__(self):
        self.q = queue.Queue()

    def executeDeferred(self, fn):
        self.q.put(fn)

    def pump_until(self, done, timeout=8.0):
        deadline = time.time() + timeout
        while not done.is_set() and time.time() < deadline:
            try:
                fn = self.q.get(timeout=0.02)
            except queue.Empty:
                continue
            fn()
        # drain anything already queued after done flipped
        while True:
            try:
                self.q.get_nowait()()
            except queue.Empty:
                break


def _recording_hou(touches, hip, temp):
    """A fake hou for the resolver that records the thread of every read."""
    def _path():
        touches.append(("path", threading.get_ident()))
        return hip

    def _isnew():
        touches.append(("isNewFile", threading.get_ident()))
        return True

    def _expand(_s):
        touches.append(("expandString", threading.get_ident()))
        return temp

    hip_file = types.SimpleNamespace(path=_path, isNewFile=_isnew)
    text = types.SimpleNamespace(expandString=_expand)
    return types.SimpleNamespace(hipFile=hip_file, text=text)


def _plain_hou(hip, temp, is_new):
    """A fake hou with no thread recording — for semantics assertions."""
    hip_file = types.SimpleNamespace(path=lambda: hip, isNewFile=lambda: is_new)
    text = types.SimpleNamespace(expandString=lambda _s: temp)
    return types.SimpleNamespace(hipFile=hip_file, text=text)


def _run_off_main(fn):
    """Run *fn* on a worker thread while pumping deferred callbacks on main.

    Returns (result_box, touches-ready). result_box carries 'val' or 'err'.
    """
    box = {}
    done = threading.Event()

    def worker():
        try:
            box["val"] = fn()
        except BaseException as e:  # noqa: BLE001 — capture, assert in test
            box["err"] = e
        finally:
            done.set()

    t = threading.Thread(target=worker, name="w2s1-worker")
    return box, done, t


@pytest.fixture(autouse=True)
def _clean_flags():
    store_mod._BACKEND_FALLBACK = None
    announced = store_mod._UNSAVED_RELOCATION_ANNOUNCED
    yield
    store_mod._BACKEND_FALLBACK = None
    store_mod._UNSAVED_RELOCATION_ANNOUNCED = announced


# ---------------------------------------------------------------------------
# predicate 2 — the F1 crash class, tested directly
# ---------------------------------------------------------------------------

def test_store_cold_resolve_off_main_marshals_every_hou_read(monkeypatch):
    """A cold store resolve on a worker thread must touch hou ONLY on main."""
    main_ident = threading.main_thread().ident
    touches = []
    fake = _recording_hou(
        touches, "C:/Program Files/Side Effects/Houdini/bin/untitled.hip", "C:/tmp"
    )
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store_mod, "hou", fake, raising=False)
    pump = _MainThreadPump()
    fake_hde = types.ModuleType("hdefereval")
    fake_hde.executeDeferred = pump.executeDeferred
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)

    sm = SynapseMemory.__new__(SynapseMemory)  # no __init__ => no disk writes
    box, done, t = _run_off_main(lambda: sm._resolve_project_path(None))
    t.start()
    pump.pump_until(done)
    t.join(timeout=8)

    assert "err" not in box, box.get("err")
    assert touches, "HOU_AVAILABLE branch never fired — the resolver read no hou"
    off_main = [(n, i) for (n, i) in touches if i != main_ident]
    assert not off_main, (
        "hou touched OFF Houdini's main thread — the W1-MTFIX F1 crash class is "
        f"present: {off_main}"
    )
    # all three reads (path, isNewFile via hip_is_unsaved, expandString) hopped
    assert {n for (n, _i) in touches} == {"path", "isNewFile", "expandString"}


def test_negative_control_marshal_disabled_touches_off_main(monkeypatch):
    """With the marshal disabled the SAME construct touches hou off-main.

    Proves the recorder catches the failure and the positive test is not
    vacuous (Law 1): the marshalling wrap is exactly what moves the reads.
    """
    main_ident = threading.main_thread().ident
    touches = []
    fake = _recording_hou(
        touches, "C:/Program Files/Side Effects/Houdini/bin/untitled.hip", "C:/tmp"
    )
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store_mod, "hou", fake, raising=False)
    # Marshal OFF: _read_on_main becomes a direct passthrough (pre-fix behaviour).
    monkeypatch.setattr(store_mod, "_read_on_main", lambda fn, label=None: fn())

    sm = SynapseMemory.__new__(SynapseMemory)
    box, done, t = _run_off_main(lambda: sm._resolve_project_path(None))
    t.start()
    t.join(timeout=8)

    assert "err" not in box, box.get("err")
    off_main = [(n, i) for (n, i) in touches if i != main_ident]
    assert off_main, (
        "expected off-main hou touches with the marshal disabled — the recorder "
        "is blind and the positive test would be vacuous"
    )


def test_doctor_resolve_store_base_dir_off_main_marshals(monkeypatch):
    """The doctor's own resolver mirror (its FIRST off-main hou, check #4)."""
    from synapse.server import doctor as doctor_mod

    main_ident = threading.main_thread().ident
    touches = []
    fake = _recording_hou(
        touches, "C:/Program Files/Side Effects/Houdini/bin/untitled.hip", "C:/tmp"
    )
    # doctor.py does a LOCAL `import hou`, so inject via sys.modules.
    monkeypatch.setitem(sys.modules, "hou", fake)
    pump = _MainThreadPump()
    fake_hde = types.ModuleType("hdefereval")
    fake_hde.executeDeferred = pump.executeDeferred
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)

    box, done, t = _run_off_main(doctor_mod._resolve_store_base_dir)
    t.start()
    pump.pump_until(done)
    t.join(timeout=8)

    assert "err" not in box, box.get("err")
    assert touches, "doctor resolver read no hou"
    off_main = [(n, i) for (n, i) in touches if i != main_ident]
    assert not off_main, f"doctor hou touched off-main (F1 crash class): {off_main}"


def test_doctor_symbol_table_version_read_off_main_marshals(monkeypatch):
    """_check_symbol_table's hou.applicationVersionString() (check #9)."""
    from synapse.server import doctor as doctor_mod

    main_ident = threading.main_thread().ident
    touches = []

    def _ver():
        touches.append(("applicationVersionString", threading.get_ident()))
        return "22.0.400"

    fake = types.SimpleNamespace(applicationVersionString=_ver)
    monkeypatch.setitem(sys.modules, "hou", fake)
    pump = _MainThreadPump()
    fake_hde = types.ModuleType("hdefereval")
    fake_hde.executeDeferred = pump.executeDeferred
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)

    box, done, t = _run_off_main(doctor_mod._check_symbol_table)
    t.start()
    pump.pump_until(done)
    t.join(timeout=8)

    assert "err" not in box, box.get("err")
    off_main = [(n, i) for (n, i) in touches if i != main_ident]
    assert not off_main, f"doctor version read touched off-main (F1): {off_main}"


# ---------------------------------------------------------------------------
# predicate 4 — headless / on-main behaviour unchanged
# ---------------------------------------------------------------------------

def test_resolve_semantics_unchanged_on_main_thread(monkeypatch, tmp_path):
    """On the main thread _read_on_main is a passthrough; results must be
    byte-identical to the pre-marshalling resolver for every branch."""
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", True)
    sm = SynapseMemory.__new__(SynapseMemory)

    # unsaved (full path ending untitled.hip) -> $HOUDINI_TEMP_DIR/untitled
    monkeypatch.setattr(
        store_mod, "hou",
        _plain_hou("C:/Program Files/SideFX/bin/untitled.hip", str(tmp_path), True),
        raising=False,
    )
    assert sm._resolve_project_path(None) == Path(str(tmp_path)) / "untitled"

    # saved scene -> the project path itself
    hip = str(tmp_path / "shots" / "seq010_v002.hip")
    monkeypatch.setattr(
        store_mod, "hou", _plain_hou(hip, str(tmp_path / "TEMP"), False), raising=False
    )
    assert sm._resolve_project_path(None) == Path(hip)

    # explicit path always wins, untouched
    assert sm._resolve_project_path("D:/proj") == Path("D:/proj")


def test_resolve_no_hou_fallback_unchanged(monkeypatch):
    """No Houdini -> cwd/untitled.hip fallback, the hou block never entered."""
    monkeypatch.setattr(store_mod, "HOU_AVAILABLE", False)
    sm = SynapseMemory.__new__(SynapseMemory)
    assert sm._resolve_project_path(None) == Path.cwd() / "untitled.hip"


def test_read_on_main_falls_back_to_direct_when_marshal_absent(monkeypatch):
    """If server.main_thread is unimportable, _read_on_main calls fn() directly
    (the historical behaviour, correct on the main thread / no-hou contexts)."""
    monkeypatch.setitem(sys.modules, "synapse.server.main_thread", None)
    box = []
    out = store_mod._read_on_main(lambda: (box.append(1), "ok")[1])
    assert out == "ok"
    assert box == [1]


# ---------------------------------------------------------------------------
# predicate 4 — C5 lock / provenance preserved (bridge-bypass structural proof)
# ---------------------------------------------------------------------------

def test_doctor_offmain_dispatch_uses_handler_handle_not_bridge():
    """_dispatch_doctor_off_main routes through handler.handle() — where the C5
    mutation lock + FloorGate Tier-0 provenance live — and NOT through the
    bridge (whose _execute_houdini would run hou off-main = the F1 crash). It
    builds the canonical 'doctor' command and shapes the MCP result."""
    from synapse.mcp.server import _dispatch_doctor_off_main
    from synapse.core.protocol import SynapseResponse

    seen = {}

    class _FakeHandler:
        def handle(self, command):
            seen["type"] = command.type
            seen["payload"] = command.payload
            return SynapseResponse(
                id=command.id, success=True,
                data={"checks": [], "summary": {"ok": 0, "fail": 0, "skipped": 0}},
            )

    result = _dispatch_doctor_off_main(_FakeHandler(), "synapse_doctor", {"bundle": False})

    assert seen["type"] == "doctor", "must dispatch the canonical 'doctor' command"
    assert isinstance(seen["payload"], dict)
    assert not result.get("isError")
    assert result["content"][0]["type"] == "text"


def test_doctor_offmain_dispatch_propagates_handler_failure():
    """A handler failure surfaces as an isError result (parity with dispatch_tool)."""
    from synapse.mcp.server import _dispatch_doctor_off_main
    from synapse.core.protocol import SynapseResponse

    class _FailHandler:
        def handle(self, command):
            return SynapseResponse(id=command.id, success=False, error="boom")

    result = _dispatch_doctor_off_main(_FailHandler(), "synapse_doctor", {})
    assert result.get("isError") is True
    assert "boom" in result["content"][0]["text"]
