"""D3 wiring (CTO Remediation) — the freeze-safety chain ACTS.

Before D3: no heartbeat source on the live stack → Watchdog never armed →
_on_freeze logged only → EmergencyProtocol had zero production callers. These
pins drive the REAL Watchdog (tiny thresholds) through the new FreezeChain and
prove: sustained freeze → breaker force_open + emergency halt via the ACTIVE
bridge (the real EmergencyProtocol code path, fake bridge); recovery before the
deadline cancels escalation and resets the breaker; no-bridge/no-server cases
act partially and never crash; the live-server registry behaves.

Pure stock-python: zero hou (shared.bridge degrades, EmergencyProtocol's PDG
walk is _HOU_AVAILABLE-guarded), zero Qt.
"""

import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from synapse.server import freeze_chain as fc
from synapse.server import websocket as ws


@pytest.fixture(autouse=True)
def _redirect_freeze_dumps(monkeypatch, tmp_path):
    """M3-C's _escalate now dumps telemetry to $SYNAPSE_LOG_DIR — keep test
    escalations out of the real ~/.synapse/logs (dev == production seat;
    test dumps would evict real freeze evidence via the newest-5 pruning)."""
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))


def _poll(predicate, timeout=2.0, interval=0.005):
    """Spin until predicate() is true or timeout elapses; return its final value.

    Polls real state instead of guessing with a fixed sleep, so a contended
    runner can't slide the observation outside the intended timing window.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


# Tiny-threshold chain: detection ~0.06s, escalation deadline 0.2s.
def _chain():
    return fc.FreezeChain(escalate_after=0.2, heartbeat_interval=0.02,
                          freeze_threshold=0.06)


def _fake_server(with_bridge=True):
    bridge = MagicMock()
    bridge.session_report.return_value = {"ops": 0}
    handler = SimpleNamespace(_bridge=bridge if with_bridge else None)
    breaker = MagicMock()
    return SimpleNamespace(_circuit_breaker=breaker, _handler=handler), breaker, bridge


@pytest.fixture(autouse=True)
def _clean_registry():
    ws._register_live_server(None)
    yield
    ws._register_live_server(None)


@pytest.fixture(autouse=True)
def _no_leaked_process_wide_chain():
    """FAILS the test that leaves the PROCESS-WIDE chain running (R310a).

    ``get_freeze_chain()`` builds a chain at PRODUCTION thresholds
    (freeze_threshold 5 s, escalate_after 30 s) whose Watchdog thread and
    escalation Timer outlive the test that built it. Nothing beats it again,
    so 5 s later it "detects" a freeze and at 30.0 s it escalates into
    whatever ``ws._register_live_server`` holds THEN — i.e. into some later,
    unrelated test's mock breaker, plus a stray ``freeze_dump_*.json`` in
    whatever ``$SYNAPSE_LOG_DIR`` that test owns.

    That was the flake: ``tests/test_m3_logs_doctor.py``'s escalation tests
    failing ``force_open ... Called 2 times`` (or ``Called 1 times`` against
    an ``assert_not_called``), a DIFFERENT test each run, in a file the
    failing lane never touched — because which test is running at t+30 s is
    pure machine timing. Reproduced deterministically by padding the gap
    between the two files to 29.3-29.6 s.

    Scope: this file is the only place in the suite that builds the singleton
    today, so a file-local guard is sufficient AND sound. A suite-wide guard
    in tests/conftest.py is the followup if a second builder ever appears.
    """
    yield
    leaked = getattr(fc, "_chain", None)
    if leaked is not None:
        fc.shutdown_freeze_chain()      # never leave it armed for the next test
        pytest.fail(
            "process-wide FreezeChain left running: its escalation timer fires "
            f"~{leaked._escalate_after:.0f}s from now, into whatever live "
            "server/bridge is registered at that moment (another test's mock). "
            "Call fc.shutdown_freeze_chain() before returning."
        )


def test_sustained_freeze_opens_breaker_and_halts_via_active_bridge():
    srv, breaker, bridge = _fake_server(with_bridge=True)
    ws._register_live_server(srv)
    chain = _chain()
    try:
        chain.heartbeat()                       # arm monitoring
        time.sleep(0.6)                         # freeze past detection + deadline
        assert chain.escalated is True
        breaker.force_open.assert_called_once() # the breaker ACTED
        bridge.session_report.assert_called()   # real EmergencyProtocol ran the halt
    finally:
        chain.stop()   # whole chain, not just the watchdog (zombie shape)


def test_recovery_before_deadline_cancels_escalation():
    srv, breaker, _ = _fake_server()
    ws._register_live_server(srv)
    # Generous escalation deadline (1.0s) versus a tiny detection threshold
    # (0.05s): on a contended runner, scheduling jitter in the brief "frozen"
    # window cannot overrun the deadline and fire a spurious escalation. The
    # earlier 0.1s sleep against a 0.2s deadline left no such margin.
    chain = fc.FreezeChain(escalate_after=1.0, heartbeat_interval=0.02,
                           freeze_threshold=0.05)
    try:
        chain.heartbeat()
        # Detect the freeze the moment it registers, rather than assuming a
        # fixed sleep landed inside the [threshold, deadline] window.
        assert _poll(lambda: chain.is_frozen, timeout=2.0)
        # Recover well before the 1.0s deadline and keep beating past it —
        # stopping again would be a legitimate SECOND freeze and rightly escalate.
        for _ in range(15):
            chain.heartbeat()
            time.sleep(0.02)
        assert chain.escalated is False
        breaker.force_open.assert_not_called()  # never acted
        breaker.reset.assert_called()           # recovery reset the breaker
    finally:
        chain.stop()   # whole chain, not just the watchdog (zombie shape)


def test_no_server_no_bridge_escalates_without_crashing():
    chain = _chain()                            # registry empty; hwebserver handler absent
    try:
        chain.heartbeat()
        time.sleep(0.6)
        assert chain.escalated is True          # acted as far as reality allows, no crash
        assert chain.stats()["escalated"] is True
    finally:
        chain.stop()   # whole chain, not just the watchdog (zombie shape)


def test_active_bridge_is_peeked_never_constructed():
    # A live server whose handler has _bridge=None: the peek must yield None and
    # never call a lazy _get_bridge (the fake has none to call — attribute peek only).
    srv, _, _ = _fake_server(with_bridge=False)
    ws._register_live_server(srv)
    assert fc._peek_active_bridge() is None


def test_live_server_registry_set_clear_and_guard():
    a, b = object(), object()
    ws._register_live_server(a)
    assert ws.get_live_server() is a
    ws._register_live_server(None, only_if=b)   # stale stop() must not clobber
    assert ws.get_live_server() is a
    ws._register_live_server(None, only_if=a)   # own-instance stop clears
    assert ws.get_live_server() is None


def test_beat_singleton_is_stable_and_cheap():
    try:
        c1 = fc.get_freeze_chain()
        fc.beat()
        assert fc.get_freeze_chain() is c1      # one process-wide chain
    finally:
        # This ONE beat used to arm a 30 s escalation that outlived the test
        # (R310a). The chain is process-wide; so was the damage.
        fc.shutdown_freeze_chain()


def test_shutdown_freeze_chain_stops_and_clears():
    """FAILS IF: the process-wide chain has no way to be stopped.

    ``get_freeze_chain()`` starts a Watchdog thread + the acting escalation
    policy and had no counterpart, so nothing — not a panel teardown, not a
    test — could end the episode. Pins the whole contract: stops the chain,
    joins the monitor, clears the singleton, reports whether one was running,
    and is idempotent.
    """
    chain = fc.get_freeze_chain()
    fc.beat()                                   # lazy-start the monitor thread
    assert fc._chain is chain
    assert chain._watchdog._thread is not None  # really running

    assert fc.shutdown_freeze_chain() is True   # reports it stopped one
    assert fc._chain is None                    # singleton cleared
    assert chain._stopped is True               # escalation half disarmed
    assert chain._watchdog._thread is None      # monitor joined, not orphaned
    with chain._timer_lock:
        assert chain._escalation_timer is None  # no timer left to fire

    assert fc.shutdown_freeze_chain() is False  # idempotent, nothing to stop


# ---------------------------------------------------------------------------
# attack-F followup 1 — the production half of the R310a fix, pinned
# ---------------------------------------------------------------------------

def test_panel_close_shuts_the_process_wide_chain_sourcepin():
    """The crucible DELETED the entire closeEvent shutdown block and no test
    failed — the production half of the zombie fix was unpinned. The panel's
    Qt tests skip on stock CPython, so this is a SOURCE pin (the house
    pattern: tests/test_panel_fidelity_honesty_sourcepin.py): closeEvent must
    stop the beat timer and shut the process-wide chain down, or a closed
    panel leaves an unbeaten chain that escalates ~30s later against a
    still-live bridge."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent
           / "python" / "synapse" / "panel" / "synapse_panel.py"
           ).read_text(encoding="utf-8", errors="replace")
    start = src.find("def closeEvent")
    assert start != -1, "synapse_panel.closeEvent no longer exists"
    # Bound the scan to closeEvent's body (up to the next def at any indent).
    import re
    m = re.search(r"\n    def \w+", src[start + 10:])
    body = src[start:start + 10 + (m.start() if m else len(src))]
    assert "shutdown_freeze_chain" in body, (
        "closeEvent no longer shuts the process-wide FreezeChain down — "
        "deleting that block revives the R310a zombie: a closed panel leaves "
        "an unbeaten chain whose escalation fires ~30s later (force_open + "
        "emergency halt) against a still-live bridge")
