"""F3 (2026-08-14) — the emergency net EXISTS on the live transport.

Before F3 all five on-disk freeze dumps showed the net inert: "No live
SynapseServer breaker to open (hwebserver transport has no resilience layer)",
"No ACTIVE bridge — emergency halt skipped", and (Aug 13) "Emergency halt
failed (best-effort) / AttributeError: 'SynapseBridge' object has no attribute
'session_report'". These tests pin the three re-scoped (post-crucible) items:

  1. hwebserver/panel transports REGISTER an already-constructed breaker with
     the freeze chain at STARTUP; the chain reads it, never constructs it
     (never-construct invariant intact).
  2. The active-bridge peek VALIDATES the halt-consumable shape — the handler's
     ``_bridge`` is the session tracker ``SynapseBridge`` (no session_report);
     feeding it to ``EmergencyProtocol`` was the Aug-13 AttributeError. The fix
     is in the caller: a shape-mismatched peek yields None and the escalation
     falls through to the WS-path halt instead of crashing on the wrong class.
  3. The WS-path halt (``server/emergency_live.emergency_halt_live``) acts ONLY
     off-main-thread: records F4's in-flight holder as evidence, flips the C4
     abandoned flag on pending unstarted dispatches, sweeps PDG contexts via
     their own API, writes state — and NEVER waits on / marshals onto the
     frozen main thread.

Pure stock-python: zero hou (the PDG sweep is _HOU_AVAILABLE-guarded), zero Qt,
zero hdefereval (all dispatch registry manipulation goes through the pure-Python
cancel_pending_dispatches surface, not an actual run_on_main call).
"""

import json
import os
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from synapse.server import freeze_chain as fc
from synapse.server import websocket as ws
from synapse.server import emergency_live as el
from synapse.server.resilience import CircuitBreaker


def _mt():
    """Resolve the LIVE main_thread module — through sys.modules, at use time.

    ``tests/test_main_thread.py`` replaces ``sys.modules["synapse.server.main_thread"]``
    with a fresh twin at COLLECTION import, so a module-top
    ``from synapse.server import main_thread as mt`` binds the pre-twin object
    in wide runs while production code (``freeze_chain`` / ``emergency_live``)
    resolves the current sys.modules entry at CALL time. Both sides of every
    assertion here must agree on the module object; this is that agreement.
    """
    return sys.modules["synapse.server.main_thread"]


@pytest.fixture(autouse=True)
def _redirect_freeze_dumps(monkeypatch, tmp_path):
    """Keep test escalations and WS-halt state writes out of the real
    ~/.synapse/logs (dev == production seat; test dumps would evict real freeze
    evidence via the newest-5 pruning)."""
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))


@pytest.fixture(autouse=True)
def _clean_registries():
    """No cross-test leakage of: the live-server registry, the registered
    transport breaker, the pending-dispatch registry, F4's in-flight register,
    or the stored halt report."""
    ws._register_live_server(None)
    fc.unregister_transport_breaker(getattr(fc, "_transport_breaker", None))
    held = getattr(_mt(), "_in_flight", None)
    el._reset_live_halt_report()
    yield
    ws._register_live_server(None)
    with fc._transport_breaker_lock:
        fc._transport_breaker = None
    mt = _mt()
    with mt._pending_lock:
        mt._pending_dispatches.clear()
    mt._in_flight = None
    el._reset_live_halt_report()


@pytest.fixture(autouse=True)
def _no_leaked_chains():
    yield
    leaked = getattr(fc, "_chain", None)
    if leaked is not None:
        fc.shutdown_freeze_chain()
        pytest.fail("process-wide FreezeChain left running (R310a zombie shape)")


def _poll(predicate, timeout=2.0, interval=0.005):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _chain():
    """Tiny-threshold chain: detection ~0.06s, escalation deadline 0.2s."""
    return fc.FreezeChain(escalate_after=0.2, heartbeat_interval=0.02,
                          freeze_threshold=0.06)


# ---------------------------------------------------------------------------
# F3.1 — registered transport breaker (constructed at startup, never here)
# ---------------------------------------------------------------------------

def test_registered_breaker_is_opened_on_escalation():
    """FAILS IF: a sustained freeze on the hwebserver stack still finds no
    breaker to open (the "no resilience layer" dump line)."""
    breaker = MagicMock()
    fc.register_transport_breaker(breaker)
    try:
        chain = _chain()
        try:
            chain.heartbeat()
            time.sleep(0.6)
            assert chain.escalated is True
            breaker.force_open.assert_called_once()
        finally:
            chain.stop()
    finally:
        fc.unregister_transport_breaker(breaker)


def test_registered_breaker_reset_on_recovery():
    breaker = MagicMock()
    fc.register_transport_breaker(breaker)
    try:
        chain = fc.FreezeChain(escalate_after=1.0, heartbeat_interval=0.02,
                               freeze_threshold=0.05)
        try:
            chain.heartbeat()
            assert _poll(lambda: chain.is_frozen, timeout=2.0)
            for _ in range(15):
                chain.heartbeat()
                time.sleep(0.02)
            assert chain.escalated is False
            breaker.force_open.assert_not_called()
            breaker.reset.assert_called()
        finally:
            chain.stop()
    finally:
        fc.unregister_transport_breaker(breaker)


def test_registered_breaker_takes_precedence_over_server_peek():
    registered, server_breaker = MagicMock(), MagicMock()
    srv = SimpleNamespace(_circuit_breaker=server_breaker,
                          _handler=SimpleNamespace(_bridge=None))
    ws._register_live_server(srv)
    fc.register_transport_breaker(registered)
    assert fc._peek_transport_breaker() is registered


def test_peek_falls_back_to_server_breaker_when_nothing_registered():
    srv = SimpleNamespace(_circuit_breaker=MagicMock(),
                          _handler=SimpleNamespace(_bridge=None))
    ws._register_live_server(srv)
    assert fc._peek_transport_breaker() is srv._circuit_breaker


def test_unregister_is_stale_handle_safe():
    a, b = MagicMock(), MagicMock()
    fc.register_transport_breaker(a)
    fc.unregister_transport_breaker(b)       # stale stop must not clobber
    assert fc._peek_transport_breaker() is a
    fc.unregister_transport_breaker(a)       # own-instance stop clears
    assert fc._peek_transport_breaker() is None


def test_never_construct_invariant_in_source():
    """Source pin: freeze_chain contains NO CircuitBreaker construction — it
    reads a breaker registered by transport STARTUP. Construction inside the
    freeze handler is the exact shape the invariant bans."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "python" / "synapse" / "server" / "freeze_chain.py"
           ).read_text(encoding="utf-8", errors="replace")
    assert "CircuitBreaker(" not in src, (
        "freeze_chain constructs a circuit breaker — the invariant is "
        "never-construct; breakers are built at transport startup and "
        "registered for the chain to READ")


def test_adapter_registers_breaker_at_startup_sourcepin():
    """Source pin: the hwebserver transport's startup path must build a real
    CircuitBreaker and register it with the freeze chain — deleting that wiring
    silently returns the net to the pre-F3 "no resilience layer" state while
    every test on this file stays green."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "python" / "synapse" / "server" / "hwebserver_adapter.py"
           ).read_text(encoding="utf-8", errors="replace")
    assert "_circuit_breaker = CircuitBreaker(" in src, (
        "hwebserver_adapter no longer constructs the transport breaker at "
        "startup — the freeze-chain escalation has nothing to open again")
    assert "register_transport_breaker(" in src, (
        "hwebserver_adapter no longer registers its breaker with the freeze "
        "chain — construction without registration is activation theater")
    assert "can_execute(" in src, (
        "the receive loop lost its breaker gate — an open breaker that never "
        "fast-fails a command opens nothing")


# ---------------------------------------------------------------------------
# F3.2 — session_report caller fix (the peek validates the haltable shape)
# ---------------------------------------------------------------------------

def test_peek_active_bridge_rejects_session_tracker_shape():
    """The live hwebserver handler's ``_bridge`` is the session tracker
    ``SynapseBridge`` — no session_report. Feeding it to EmergencyProtocol was
    the Aug-13 AttributeError. The peek must yield None, not the wrong object."""
    srv = SimpleNamespace(
        _circuit_breaker=None,
        _handler=SimpleNamespace(_bridge=SimpleNamespace()),  # no session_report
    )
    ws._register_live_server(srv)
    assert fc._peek_active_bridge() is None


def test_peek_active_bridge_accepts_haltable_shape():
    bridge = SimpleNamespace(session_report=lambda: {"ops": 0})
    srv = SimpleNamespace(_circuit_breaker=None,
                          _handler=SimpleNamespace(_bridge=bridge))
    ws._register_live_server(srv)
    assert fc._peek_active_bridge() is bridge


def test_escalation_routes_ws_halt_when_no_haltable_bridge(monkeypatch):
    """FAILS IF: with no haltable /mcp bridge the halt is SKIPPED (the pre-F3
    "No ACTIVE bridge" no-op) — the WS path must get its own halt."""
    fired = MagicMock(return_value={
        "action": "LIVE_PATH_HALT",
        "pending_dispatches_cancelled": 0,
        "main_thread_holder": None,
    })
    monkeypatch.setattr(el, "emergency_halt_live", fired)
    chain = _chain()
    try:
        chain.heartbeat()
        # Anchor to the real state, not a fixed sleep: under a loaded host
        # (full suite + hython probes in parallel) the watchdog thread can
        # need more than 0.6 s to fire; a wall-clock guess flaked 2026-09-05.
        deadline = time.monotonic() + 5.0
        while not chain.escalated and time.monotonic() < deadline:
            time.sleep(0.05)
        assert chain.escalated is True
        fired.assert_called_once()
        assert "no active /mcp bridge" in fired.call_args.kwargs["reason"]
    finally:
        chain.stop()


# ---------------------------------------------------------------------------
# F3.3 — the WS-path halt itself (off-main-thread actions only)
# ---------------------------------------------------------------------------

def test_cancel_pending_dispatches_flips_c4_flags():
    """The C4 abandoned flag is now reachable from OUTSIDE the timed-out
    caller: a queued-but-unstarted payload wakes into a no-op."""
    lock = threading.Lock()
    abandoned = [False]
    mt = _mt()
    with mt._pending_lock:
        mt._pending_dispatches[id(abandoned)] = (
            lock, abandoned, "render:karma", time.time()
        )
    assert mt.pending_dispatch_count() == 1
    flipped = mt.cancel_pending_dispatches("test")
    assert flipped == 1
    with lock:
        assert abandoned[0] is True
    # Idempotent — the same entry is not double-counted on a second pass.
    assert mt.cancel_pending_dispatches("test") == 0


def test_cancel_pending_dispatches_with_nothing_pending_is_zero():
    assert _mt().cancel_pending_dispatches("test") == 0
    assert _mt().pending_dispatch_count() == 0


def test_halt_live_standalone_report_shape_and_storage():
    report = el.emergency_halt_live(reason="test freeze")
    assert report["action"] == "LIVE_PATH_HALT"
    assert report["execution_path"] == "live"
    assert report["emergency_reason"] == "test freeze"
    assert report["main_thread_holder"] is None      # nothing in flight standalone
    assert report["pending_dispatches_cancelled"] == 0
    assert report["pdg_contexts_cancelled"] == 0     # _HOU_AVAILABLE-guarded sweep
    state = report["state_file"]
    assert isinstance(state, str) and os.path.isfile(state)
    assert os.path.basename(state).startswith("emergency_halt_")
    # The persisted artifact carries THIS halt's actions, readable from disk.
    on_disk = json.loads(open(state, encoding="utf-8").read())
    assert on_disk["action"] == "LIVE_PATH_HALT"
    assert on_disk["emergency_reason"] == "test freeze"
    # Stored for post-recovery health surfaces.
    assert el.last_live_halt_report()["emergency_reason"] == "test freeze"


def test_halt_live_records_in_flight_holder_age():
    """FAILS IF: the halt report can't name the op holding the main thread
    mid-freeze — the evidence half the spec demands over waiting on it."""
    mt = _mt()
    mt._in_flight = ("handlers_render:execute_python", time.time() - 179.0)
    report = el.emergency_halt_live(reason="named-holder test")
    holder = report["main_thread_holder"]
    assert holder["label"] == "handlers_render:execute_python"
    assert holder["age_s"] >= 179.0


def test_halt_live_abandons_pending_dispatches():
    lock = threading.Lock()
    abandoned = [False]
    mt = _mt()
    with mt._pending_lock:
        mt._pending_dispatches[id(abandoned)] = (lock, abandoned, "cops", time.time())
    report = el.emergency_halt_live(reason="pile-up test")
    assert report["pending_dispatches_cancelled"] == 1
    with lock:
        assert abandoned[0] is True


def test_halt_live_never_touches_main_thread():
    """The deadlock shape: anything marshalled onto the frozen main thread
    queues behind the hold it responds to. The halt runs fully on the calling
    thread with no hdefereval involvement — standalone this is proven by
    construction (hdefereval is unimportable here), and this test asserts the
    module's import surface stays clean of it."""
    import synapse.server.emergency_live as mod
    import sys
    assert "hdefereval" not in [name for name in dir(mod)], (
        "emergency_live must not import hdefereval — marshalling onto the "
        "frozen main thread is exactly the deadlock the WS halt avoids")


# ---------------------------------------------------------------------------
# Cross-cutting: a real CircuitBreaker honors the freeze-chain contract
# ---------------------------------------------------------------------------

def test_real_breaker_force_open_gates_commands():
    """The breaker's honest effect: force_open makes can_execute refuse."""
    cb = CircuitBreaker(name="test-transport")
    allowed, _ = cb.can_execute()
    assert allowed is True
    cb.force_open()
    allowed, info = cb.can_execute()
    assert allowed is False
    assert info["reason"] == "circuit_open"
    cb.reset()
    allowed, _ = cb.can_execute()
    assert allowed is True
