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
        chain._watchdog.stop()


def test_recovery_before_deadline_cancels_escalation():
    srv, breaker, _ = _fake_server()
    ws._register_live_server(srv)
    chain = _chain()
    try:
        chain.heartbeat()
        time.sleep(0.1)                         # past detection (0.06), before deadline (0.2)
        assert chain.is_frozen is True
        # Recover AND keep beating past the (cancelled) deadline — stopping again
        # would be a legitimate SECOND freeze and would rightly escalate.
        for _ in range(15):
            chain.heartbeat()
            time.sleep(0.02)
        assert chain.escalated is False
        breaker.force_open.assert_not_called()  # never acted
        breaker.reset.assert_called()           # recovery reset the breaker
    finally:
        chain._watchdog.stop()


def test_no_server_no_bridge_escalates_without_crashing():
    chain = _chain()                            # registry empty; hwebserver handler absent
    try:
        chain.heartbeat()
        time.sleep(0.6)
        assert chain.escalated is True          # acted as far as reality allows, no crash
        assert chain.stats()["escalated"] is True
    finally:
        chain._watchdog.stop()


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
    c1 = fc.get_freeze_chain()
    fc.beat()
    assert fc.get_freeze_chain() is c1          # one process-wide chain
