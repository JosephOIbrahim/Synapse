"""C4 (CTO Remediation Mile 2) — run_on_main abandons zombie mutations on timeout.

Before C4: run_on_main timed out and raised (telling the caller to retry), but the
deferred payload still ran fn() whenever the main thread freed — a 'zombie' mutation
applied after the failure report, and a retry double-applied. C4 adds a per-call
abandoned flag: once the caller times out, _on_main returns without running fn().

main_thread.py imports `hdefereval` lazily inside run_on_main, so the test injects a
fake into sys.modules. run_on_main is called from a WORKER thread so it takes the
deferred path (not the main-thread fast path). Loaded via importlib spec to avoid the
package __init__ eager-hou import.
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
    """executeDeferred runs the callback on another thread after `delay` seconds."""
    fake = types.ModuleType("hdefereval")

    def executeDeferred(cb):
        def runner():
            time.sleep(delay)
            cb()
        threading.Thread(target=runner, daemon=True).start()
    fake.executeDeferred = executeDeferred
    return fake


def _call_from_worker(mt, fn, timeout):
    """Run run_on_main on a non-main thread so it takes the deferred path."""
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


def test_timed_out_payload_is_abandoned(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.4))

    ran = []
    out = _call_from_worker(mt, lambda: ran.append("MUTATED") or "ok", timeout=0.1)

    assert isinstance(out.get("error"), RuntimeError)   # caller was told it failed
    time.sleep(0.6)                                     # let the delayed payload fire
    assert ran == [], "zombie mutation executed after the caller gave up"


def test_normal_payload_executes_and_returns(monkeypatch):
    mt = _load_mt()
    monkeypatch.setitem(sys.modules, "hdefereval", _fake_hdefereval(delay=0.0))

    ran = []
    out = _call_from_worker(mt, lambda: ran.append("MUTATED") or "result", timeout=2.0)

    assert out.get("value") == "result"
    assert ran == ["MUTATED"]                           # fast (non-timed-out) op still runs
