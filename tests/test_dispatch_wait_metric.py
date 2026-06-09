"""C6 instrumentation (CTO Remediation Mile 3.1) — dispatch_wait_ms histogram.

The "~2s mutation floor" was never attributed: the per-tool histogram times the
whole handler, conflating run_on_main's enqueue→callback-start wake latency with
hou work. This instrument measures exactly that gap. These pins prove: the wait
is recorded (≈ the injected delay, right bucket), abandoned payloads still
sample, and the histogram exports on the Prometheus surface.

Adjudication of T1/T2/T3 needs a LIVE graphical session (transport-blocked this
run — see Ledger); this is the instrument, not the verdict.
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


def _fake_hdefereval(delay):
    fake = types.ModuleType("hdefereval")

    def executeDeferred(cb):
        def runner():
            time.sleep(delay)
            cb()
        threading.Thread(target=runner, daemon=True).start()
    fake.executeDeferred = executeDeferred
    return fake


def _from_worker(mt, fn, timeout):
    out = {}

    def worker():
        try:
            out["value"] = mt.run_on_main(fn, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            out["error"] = e
    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=5)
    return out


def test_dispatch_wait_recorded_with_right_magnitude(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.2))
    mt.reset_dispatch_wait_stats()

    _from_worker(mt, lambda: "ok", timeout=2.0)

    s = mt.dispatch_wait_stats()
    assert s["count"] == 1
    assert 150 <= s["sum_ms"] <= 1500          # ≈200ms injected wake delay (loose ceiling for CI)
    assert s["buckets"][2000] >= 1             # cumulative: lands at/below the 2000 bucket
    assert s["buckets"][100] == 0              # but NOT at/below 100ms — magnitude is real


def test_abandoned_payload_still_samples(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.4))
    mt.reset_dispatch_wait_stats()

    out = _from_worker(mt, lambda: "ok", timeout=0.1)   # times out; payload abandoned
    assert "error" in out
    time.sleep(0.6)                                     # let the abandoned payload wake

    s = mt.dispatch_wait_stats()
    assert s["count"] == 1                              # the queue-sit time is still a datum


def test_histogram_exports_on_prometheus_surface():
    from synapse.server.metrics import render_prometheus
    text = render_prometheus(dispatch_waits={
        "count": 3, "sum_ms": 6100.0, "max_ms": 2050.0,
        "buckets": {1: 0, 5: 0, 10: 0, 50: 0, 100: 1, 250: 1, 500: 1,
                    1000: 1, 2000: 1, 4000: 3},
    })
    assert "# TYPE synapse_dispatch_wait_ms histogram" in text
    assert 'synapse_dispatch_wait_ms_bucket{le="2000"} 1' in text
    assert 'synapse_dispatch_wait_ms_bucket{le="+Inf"} 3' in text
    assert "synapse_dispatch_wait_ms_sum 6100.0" in text
    assert "synapse_dispatch_wait_ms_max 2050.0" in text
    # zero-count histograms stay silent (no noise on idle sessions)
    assert "dispatch_wait" not in render_prometheus(dispatch_waits={"count": 0, "buckets": {}})
