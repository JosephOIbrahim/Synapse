"""F4 (2026-08-14) — the in-flight register: current_main_thread_holder().

The hold histogram records COMPLETED holds only, so a payload still RUNNING
was invisible to every instrument — the class behind the Aug-13/14 freezes
(a mid-freeze dump named a 651ms doctor while a 179s execute_python was in
flight; seven deferred renders zombie-ran 162-177s unnamed). These pins prove:

- fast path 2 (inline, main-thread caller) registers (label, start_ts) on
  entry, exposes the holder MID-CALL to another thread, and clears on exit —
  including on the exception path;
- the deferred _on_main path does the same, but only AFTER the C4
  abandoned-check passes (a zombie-killed payload never registers);
- labels land (unlabeled callers read as "unlabeled");
- nested fast-path-2 calls save/restore the outer holder rather than erasing it;
- the freeze-dump snapshot names the live holder with held_s elapsed.

Standalone: no hou; the deferred path is driven by a fake hdefereval (same
idiom as test_main_thread_hold_metric.py).
"""

import importlib.util
import sys
import threading
import time
import types
from pathlib import Path

_base = Path(__file__).resolve().parents[1] / "python" / "synapse"


def _load_mt():
    spec = importlib.util.spec_from_file_location(
        "synapse.server.main_thread", _base / "server" / "main_thread.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_hdefereval():
    """Stand-in for hdefereval: runs the deferred callback on its own thread
    (the simulated main thread) immediately."""
    fake = types.ModuleType("hdefereval")

    def executeDeferred(cb):
        threading.Thread(target=cb, daemon=True).start()
    fake.executeDeferred = executeDeferred
    return fake


def _mt_live():
    """Resolve the RESIDENT main_thread module — sys.modules, at call time.

    tests/test_main_thread.py replaces
    ``sys.modules["synapse.server.main_thread"]`` with a fresh twin at
    COLLECTION import (the F3 leg documented this trap), so a module-top
    import here would bind the pre-twin object in wide runs while
    telemetry_dump resolves the current sys.modules entry at call time. Both
    sides of an assertion must agree on the module object; this is that
    agreement (same shape as test_f3_emergency_net.py's _mt()).
    """
    return sys.modules["synapse.server.main_thread"]


def _from_worker(mt, fn, timeout=5.0, label=None):
    """Invoke run_on_main from a worker thread (the deferred path)."""
    out = {}

    def worker():
        try:
            out["value"] = mt.run_on_main(fn, timeout=timeout, label=label)
        except Exception as e:  # noqa: BLE001
            out["error"] = e
    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=8)
    assert not t.is_alive(), "worker never returned"
    return out


# ---------------------------------------------------------------------------
# Fast path 2 (main-thread caller runs inline)
# ---------------------------------------------------------------------------

def test_fast_path2_registers_and_clears_on_success(monkeypatch):
    mt = _load_mt()
    assert mt.current_main_thread_holder() is None
    # This test runs on the pytest main thread => ident matches => fast path 2.
    mt.run_on_main(lambda: "ok", label="probe:fp2")
    assert mt.current_main_thread_holder() is None


def test_fast_path2_holder_visible_mid_call_from_other_thread():
    mt = _load_mt()
    entered = threading.Event()
    release = threading.Event()
    seen = {}

    def fn():
        entered.set()
        release.wait(timeout=5)
        return "done"

    def observer():
        entered.wait(timeout=5)
        seen["holder"] = mt.current_main_thread_holder()
        time.sleep(0.05)  # still in flight
        seen["holder2"] = mt.current_main_thread_holder()
        release.set()

    obs = threading.Thread(target=observer)
    obs.start()
    assert mt.run_on_main(fn, label="cops:long_hold") == "done"  # fast path 2
    obs.join(timeout=5)

    holder = seen["holder"]
    assert holder is not None, "register never showed the in-flight hold"
    label, start_ts = holder
    assert label == "cops:long_hold"
    assert 0 <= time.time() - start_ts < 10
    assert seen["holder2"] == holder, "holder must stay identical mid-call"
    assert mt.current_main_thread_holder() is None, "register not cleared on exit"


def test_fast_path2_clears_on_exception():
    mt = _load_mt()

    def boom():
        raise ValueError("nope")
    try:
        mt.run_on_main(boom, label="x")
        raise AssertionError("should have raised")
    except ValueError:
        pass
    assert mt.current_main_thread_holder() is None


def test_fast_path2_nested_calls_restore_outer_holder():
    mt = _load_mt()
    seen_by_observer = {}

    def inner():
        return mt.run_on_main(lambda: "inner-value", label="inner")

    def outer():
        inner_result = mt.run_on_main(inner, label="outer")
        # After the inner call completes, the OUTER holder must be visible
        # again to other threads while the outer payload still runs.
        entered.set()
        release.wait(timeout=5)
        return inner_result

    entered = threading.Event()
    release = threading.Event()

    def observer():
        entered.wait(timeout=5)
        seen_by_observer["holder"] = mt.current_main_thread_holder()
        release.set()

    obs = threading.Thread(target=observer)
    obs.start()
    assert mt.run_on_main(outer, label="outermost") == "inner-value"
    obs.join(timeout=5)
    holder = seen_by_observer["holder"]
    assert holder is not None and holder[0] == "outermost", (
        "nested call must restore the outer holder, got %r" % (holder,))


# ---------------------------------------------------------------------------
# Deferred path (_on_main via hdefereval.executeDeferred)
# ---------------------------------------------------------------------------

def test_deferred_registers_after_abandoned_check_and_clears(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval())
    assert mt.current_main_thread_holder() is None
    out = _from_worker(mt, lambda: "v", label="cops:deferred")
    assert out["value"] == "v"
    assert mt.current_main_thread_holder() is None


def test_deferred_holder_visible_mid_call(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval())
    entered = threading.Event()
    release = threading.Event()

    def fn():
        entered.set()
        release.wait(timeout=5)
        return "fin"

    # Watch the register from this (test-main) thread while the deferred
    # payload runs on the simulated main thread.
    t = threading.Thread(
        target=lambda: mt.run_on_main(fn, timeout=5.0, label="render:zombie"))
    t.start()
    assert entered.wait(timeout=5), "deferred payload never started"
    holder = mt.current_main_thread_holder()
    assert holder is not None, "deferred in-flight hold invisible mid-call"
    assert holder[0] == "render:zombie"
    start_ts = holder[1]
    assert time.time() - start_ts < 5
    release.set()
    t.join(timeout=8)
    assert mt.current_main_thread_holder() is None


def test_deferred_unlabeled_reads_unlabeled(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval())
    entered = threading.Event()
    release = threading.Event()

    def fn():
        entered.set()
        release.wait(timeout=5)

    t = threading.Thread(target=lambda: mt.run_on_main(fn, timeout=5.0))
    t.start()
    assert entered.wait(timeout=5)
    holder = mt.current_main_thread_holder()
    assert holder is not None and holder[0] == "unlabeled"
    release.set()
    t.join(timeout=8)


def test_deferred_abandoned_before_start_never_registers(monkeypatch):
    """A payload killed by the C4 zombie gate (caller timed out before the
    deferred callback started) must NEVER touch the register."""
    mt = _load_mt()
    # hdefereval that sits on the callback far past the caller's timeout.
    fake = types.ModuleType("hdefereval")
    fired = {"cb": None}

    def executeDeferred(cb):
        def runner():
            time.sleep(0.8)
            fired["cb"] = cb
            cb()
        threading.Thread(target=runner, daemon=True).start()
    fake.executeDeferred = executeDeferred
    monkeypatch.setitem(sys.modules, "hdefereval", fake)

    out = _from_worker(mt, lambda: "mutated", timeout=0.15)
    assert isinstance(out["error"], RuntimeError)
    # The deferred callback has not fired yet (0.8s sit > 0.15s timeout).
    # When it DOES fire, the abandoned flag must gate it out entirely.
    deadline = time.monotonic() + 3
    while fired["cb"] is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert mt.current_main_thread_holder() is None


# ---------------------------------------------------------------------------
# Freeze-dump wiring — collect_telemetry names the live holder
# ---------------------------------------------------------------------------

def test_freeze_dump_names_current_holder(monkeypatch):
    from synapse.server import telemetry_dump as td

    holder = ("cops:long_hold", time.time() - 7.25)
    monkeypatch.setattr(
        "synapse.server.main_thread._in_flight", holder)
    snap = td.collect_telemetry()
    entry = snap["main_thread_holder"]
    assert entry is not None, "dump lost the in-flight holder"
    assert entry["label"] == "cops:long_hold"
    assert entry["start_ts"] == holder[1]
    assert 6.0 < entry["held_s"] < 30.0


def test_freeze_dump_holder_none_when_idle(monkeypatch):
    # Isolate the register first: in a full-suite run some earlier test may
    # legitimately leave the RESIDENT module's _in_flight non-None (in-flight
    # payloads on un-joined daemon threads, twin-module swaps at collection).
    # What this pin asserts is untouched: dump-time mapping of an idle holder
    # must be real data (None), never an absence marker or a fabricated entry.
    mt = _mt_live()
    monkeypatch.setattr(mt, "_in_flight", None)
    from synapse.server import telemetry_dump as td
    snap = td.collect_telemetry()
    assert snap["main_thread_holder"] is None
    assert "main_thread_holder_absent" not in snap
