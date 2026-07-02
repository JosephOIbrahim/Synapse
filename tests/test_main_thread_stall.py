"""WS2 multi-client hardening — H3 stall-detector state + bounded recovery probe.

Before H3, the stall detector was sticky: it trips at 2 consecutive
run_on_main timeouts, and ONLY a successful worker-path run_on_main resets it
— so recovery depended on incidental read-only traffic. probe_main_thread()
gives the two fast-fail gates a bounded (<=2s) recovery attempt: success
resets the counter (the command proceeds), failure fast-fails as before.
stall_state() surfaces the detector for the doctor and for attribution-aware
gate messages.

Idiom: patch the LIVE sys.modules main_thread entry (test_main_thread.py may
have planted a private instance at collection — same source, shared state) and
swap the hdefereval pump via monkeypatch.setitem(sys.modules, ...) since
run_on_main imports it lazily at call time.
"""

import importlib
import sys
import threading
import time
import types

import pytest


def _mt():
    return importlib.import_module("synapse.server.main_thread")


@pytest.fixture
def clean_stall_state():
    """Zero the stall counters before the test and leave the process healthy
    after it (other suites read this shared module-level state)."""
    mt = _mt()
    with mt._stall_lock:
        mt._consecutive_timeouts = 0
        mt._last_timeout_ts = None
    yield mt
    with mt._stall_lock:
        mt._consecutive_timeouts = 0
        mt._last_timeout_ts = None


def test_stall_state_exposed(clean_stall_state):
    mt = clean_stall_state
    assert mt.stall_state() == {
        "stalled": False,
        "consecutive_timeouts": 0,
        "last_timeout_ts": None,
    }

    t0 = time.time()
    mt._record_timeout(10.0)
    mt._record_timeout(10.0)

    state = mt.stall_state()
    assert state["stalled"] is True
    assert state["consecutive_timeouts"] == 2
    assert state["last_timeout_ts"] is not None
    assert state["last_timeout_ts"] >= t0
    assert mt.is_main_thread_stalled()


def test_probe_resets_stall_and_command_proceeds(clean_stall_state, monkeypatch):
    """Main thread recovered (pump runs the deferred fn): the probe succeeds,
    the counter resets, and the gates let the command proceed."""
    mt = clean_stall_state
    mt._record_timeout(10.0)
    mt._record_timeout(10.0)
    assert mt.is_main_thread_stalled()

    pump = types.ModuleType("hdefereval")
    pump.executeDeferred = lambda fn: threading.Thread(target=fn, daemon=True).start()
    monkeypatch.setitem(sys.modules, "hdefereval", pump)

    outcome = {}

    def _from_worker():
        # Worker thread => run_on_main takes the real dispatch path
        outcome["probe"] = mt.probe_main_thread(timeout=2.0)

    t = threading.Thread(target=_from_worker)
    t.start()
    t.join(timeout=5.0)

    assert outcome["probe"] is True
    assert not mt.is_main_thread_stalled()  # counter reset → command proceeds
    assert mt.stall_state()["consecutive_timeouts"] == 0


def test_probe_from_main_thread_fast_path_resets(clean_stall_state):
    """run_on_main's main-thread fast path returns before _record_success —
    the probe resets the counter explicitly, so a probe that provably ran is
    always a recovery signal regardless of the calling thread."""
    mt = clean_stall_state
    mt._record_timeout(10.0)
    mt._record_timeout(10.0)
    assert mt.is_main_thread_stalled()

    assert mt.probe_main_thread(timeout=0.5) is True
    assert not mt.is_main_thread_stalled()


def test_probe_fails_when_still_stalled(clean_stall_state, monkeypatch):
    """Main thread still saturated (pump swallows the deferred fn): the probe
    returns False within its bound and the stall persists (its own timeout is
    recorded)."""
    mt = clean_stall_state
    mt._record_timeout(10.0)
    mt._record_timeout(10.0)

    swallow = types.ModuleType("hdefereval")
    swallow.executeDeferred = lambda fn: None  # main thread never wakes
    monkeypatch.setitem(sys.modules, "hdefereval", swallow)

    outcome = {}

    def _from_worker():
        outcome["probe"] = mt.probe_main_thread(timeout=0.1)

    t = threading.Thread(target=_from_worker)
    t.start()
    t.join(timeout=5.0)

    assert outcome["probe"] is False
    assert mt.is_main_thread_stalled()
    assert mt.stall_state()["consecutive_timeouts"] == 3
