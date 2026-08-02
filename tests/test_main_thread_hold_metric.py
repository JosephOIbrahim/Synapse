"""OCC instrumentation — deferred-path main-thread HOLD histogram.

The deferred path (_on_main via hdefereval.executeDeferred) is how EVERY
off-main tool payload reaches Houdini's main thread, and it timed NOTHING
around fn(): main-thread occupancy had to be inferred from wall clocks and
timeout constants, and the 2026-07-31 freeze investigation got both wrong
(10,005ms was _DEFAULT_TIMEOUT + overhead; the "46.7s stall" contained three
recoveries). These pins prove: a deferred payload records a hold sample of
the PAYLOAD's duration (not the queue wait) with real thread identity, the
label threads through, a payload abandoned mid-flight (C4 residual race)
still records — marked — while a payload killed BEFORE it starts records
nothing (C4 zombie kill untouched), the fast paths never double-record into
the new sink, snapshots are copies, and the histogram exports on the
Prometheus + doctor surfaces.

Measurement only — no dispatch behaviour is asserted changed, because none is.
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


def _fake_hdefereval(delay=0.0, ident_box=None):
    """Stand-in for hdefereval: runs the deferred callback on its own thread
    (the simulated main thread) after an optional queue-sit delay."""
    fake = types.ModuleType("hdefereval")

    def executeDeferred(cb):
        def runner():
            if ident_box is not None:
                ident_box.append(threading.get_ident())
            if delay:
                time.sleep(delay)
            cb()
        threading.Thread(target=runner, daemon=True).start()
    fake.executeDeferred = executeDeferred
    return fake


def _from_worker(mt, fn, timeout, label=None):
    out = {}

    def worker():
        try:
            out["value"] = mt.run_on_main(fn, timeout=timeout, label=label)
        except Exception as e:  # noqa: BLE001
            out["error"] = e
    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)
    return out


def test_deferred_hold_records_payload_not_queue_wait(monkeypatch):
    """The hold sample is fn()'s duration ON the deferred thread — the 300ms
    queue-sit must land in dispatch_wait, never in the hold histogram."""
    mt = _load_mt()
    deferred_idents = []
    monkeypatch.setitem(
        sys.modules, "hdefereval",
        _fake_hdefereval(delay=0.3, ident_box=deferred_idents))
    mt.reset_main_thread_hold_stats()
    mt.reset_dispatch_wait_stats()

    seen = {}

    def payload():
        seen["thread"] = threading.get_ident()
        time.sleep(0.05)
        return "ok"

    out = _from_worker(mt, payload, timeout=2.0)
    assert out.get("value") == "ok"

    s = mt.main_thread_hold_stats()
    assert s["count"] == 1
    # ≈50ms payload, loose CI ceiling — but the 300ms wake delay must NOT
    # have leaked in (that is dispatch_wait's datum, not the hold's).
    assert 30 <= s["sum_ms"] < 290
    assert s["slowest_label"] == "unlabeled"      # default label
    assert s["abandoned_count"] == 0
    # Real thread identity: the payload (and its timing) ran on the deferred
    # ("main") thread the fake hdefereval spawned — not the worker caller.
    assert seen["thread"] == deferred_idents[0]

    w = mt.dispatch_wait_stats()
    assert w["count"] == 1
    assert w["sum_ms"] > s["sum_ms"]              # queue wait ≈300ms > hold ≈50ms


def test_label_threads_through(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval())
    mt.reset_main_thread_hold_stats()

    _from_worker(mt, lambda: "ok", timeout=2.0, label="houdini_create_node")

    s = mt.main_thread_hold_stats()
    assert s["count"] == 1
    assert s["slowest_label"] == "houdini_create_node"


def test_abandoned_mid_payload_still_records_marked(monkeypatch):
    """A payload the caller abandoned WHILE it was running (C4 residual race)
    is precisely the interesting hold — it must record, marked abandoned."""
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.02))
    mt.reset_main_thread_hold_stats()

    out = _from_worker(mt, lambda: time.sleep(0.5), timeout=0.1, label="slow_op")
    assert "error" in out                     # caller timed out mid-payload
    time.sleep(0.9)                           # let the zombie payload finish

    s = mt.main_thread_hold_stats()
    assert s["count"] == 1
    assert s["abandoned_count"] == 1
    assert s["slowest_label"] == "slow_op"
    assert s["sum_ms"] >= 300                 # the full ≈500ms hold, recorded


def test_abandoned_before_start_records_no_hold(monkeypatch):
    """C4 zombie kill untouched: a payload abandoned BEFORE fn() starts never
    runs, so there is no hold to record — only the dispatch-wait datum."""
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.4))
    mt.reset_main_thread_hold_stats()
    mt.reset_dispatch_wait_stats()

    ran = []
    out = _from_worker(mt, lambda: ran.append(1), timeout=0.05)
    assert "error" in out
    time.sleep(0.8)                           # let the abandoned wake fire

    assert ran == []                          # fn() never executed (C4 intact)
    assert mt.main_thread_hold_stats()["count"] == 0
    assert mt.dispatch_wait_stats()["count"] == 1


def test_fast_paths_do_not_record_hold():
    """Fast path 2 (inline main-thread) records main_thread_direct only;
    fast path 1 (reentrant) records nothing. Neither touches the hold sink."""
    mt = _load_mt()
    mt.reset_main_thread_hold_stats()
    mt.reset_main_thread_direct_stats()

    # Fast path 2: this test runs on the process main thread, which is the
    # freshly loaded module's captured _MAIN_THREAD_ID.
    assert threading.current_thread().ident == mt._MAIN_THREAD_ID
    assert mt.run_on_main(lambda: 42, label="inline_probe") == 42
    assert mt.main_thread_hold_stats()["count"] == 0
    assert mt.main_thread_direct_stats()["count"] == 1

    # Fast path 1: reentrant call from within a run_on_main callback.
    mt._tls.on_main = True
    try:
        assert mt.run_on_main(lambda: 7) == 7
    finally:
        mt._tls.on_main = False
    assert mt.main_thread_hold_stats()["count"] == 0
    assert mt.main_thread_direct_stats()["count"] == 1   # unchanged too


def test_hold_stats_snapshot_is_copy(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval())
    mt.reset_main_thread_hold_stats()

    _from_worker(mt, lambda: "ok", timeout=2.0)

    s = mt.main_thread_hold_stats()
    s["count"] = 999
    s["buckets"][4000] = 999
    s["slowest_label"] = "tampered"

    s2 = mt.main_thread_hold_stats()
    assert s2["count"] == 1
    assert s2["buckets"][4000] != 999
    assert s2["slowest_label"] == "unlabeled"


def test_hold_exports_on_prometheus_surface():
    from synapse.server.metrics import render_prometheus
    text = render_prometheus(main_thread_holds={
        "count": 2, "sum_ms": 5100.0, "max_ms": 5000.0,
        "buckets": {1: 0, 5: 0, 10: 0, 50: 0, 100: 1, 250: 1, 500: 1,
                    1000: 1, 2000: 1, 4000: 1},
        "slowest_label": "houdini_render", "abandoned_count": 1,
    })
    assert "# TYPE synapse_main_thread_hold_ms histogram" in text
    assert 'synapse_main_thread_hold_ms_bucket{le="+Inf"} 2' in text
    assert "synapse_main_thread_hold_ms_sum 5100.0" in text
    assert "synapse_main_thread_hold_ms_max 5000.0" in text
    assert "synapse_main_thread_hold_abandoned_total 1" in text
    assert ('synapse_main_thread_hold_slowest_ms{label="houdini_render"} 5000.0'
            in text)
    # zero-count histograms stay silent (no noise on idle sessions)
    assert "main_thread_hold" not in render_prometheus(
        main_thread_holds={"count": 0, "buckets": {}})


def test_doctor_main_thread_check_surfaces_holds():
    from synapse.server.doctor import _check_main_thread
    r = _check_main_thread()
    assert r["status"] in ("ok", "fail")
    holds = r["result"]["main_thread_holds"]
    for key in ("count", "sum_ms", "max_ms", "buckets",
                "slowest_label", "abandoned_count"):
        assert key in holds
