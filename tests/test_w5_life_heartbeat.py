"""W5-LIFE (R.2) — process-lifetime heartbeat owner + deliberate detach.

These pins are headless (no Qt, no hou). They cover the acceptance predicates
that are simulatable without a live Houdini GUI:

* the process-lifetime beat OWNER exists under ``python/synapse/server/`` and
  carries the machine-gate authority markers (target 1 / gate leg 2);
* panel close is a DELIBERATE DETACH, not a chain shutdown — a healthy runtime
  that keeps being beaten never false-positive-escalates (target 2, GREEN leg);
* a genuinely stalled main thread (beat stops) still escalates (target 4, RED
  leg) — the very failure the old panel-owned timer left the runtime exposed to.

The GUI-only parts — a real parentless QTimer firing on the Houdini main-thread
event loop, and Joe's live close→reopen — are recorded UNKNOWN in the receipt,
never simulated into a pass.
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path

import pytest

from synapse.server import runtime_beat as rb


@pytest.fixture(autouse=True)
def _hermetic_beat(monkeypatch):
    """Zero the owner's module state around every test, and PIN the headless
    path deterministically. Another test in the full suite can leave a Qt stub
    in sys.modules whose QApplication.instance() is non-None; without this pin
    ensure_beat_started() would arm a stub timer and 'headless behaviour' would
    depend on ambient suite state instead of the code under test. Forcing
    _qapp_instance -> None makes every assertion here order-independent."""
    monkeypatch.setattr(rb, "_qapp_instance", lambda: None)
    rb.reset_for_test()
    yield
    rb.reset_for_test()


# ---------------------------------------------------------------------------
# Target 1 / gate leg 2 — the owner exists with its authority markers
# ---------------------------------------------------------------------------

def test_owner_carries_the_machine_gate_markers():
    src = Path(rb.__file__).read_text(encoding="utf-8")
    # These are exactly what harness/verify/checks.py::check_runtime_owns_heartbeat
    # scans server/*.py for (leg 2). Both present here.
    assert "# RUNTIME_BEAT_SOURCE" in src
    assert "def ensure_beat_started" in src


def test_owner_lives_under_server():
    assert Path(rb.__file__).parent.name == "server"


# ---------------------------------------------------------------------------
# Owner behaviour headless (no Qt event loop on CI)
# ---------------------------------------------------------------------------

def test_ensure_beat_started_is_safe_and_idempotent_headless():
    # No QApplication in CI -> no real timer armed, but it must never raise and
    # must mark the panel attached. Second call is a no-op that returns the same.
    # _qapp_instance is pinned to None by the autouse fixture, so this is the
    # deterministic "no event loop" path regardless of whether a sibling test
    # left a Qt stub importable (which would flip the import-time _QT_AVAILABLE
    # flag — an environment fact this behaviour test must not depend on).
    first = rb.ensure_beat_started()
    second = rb.ensure_beat_started()
    assert first is False   # no event loop -> no real timer armed
    assert second is False  # idempotent
    st = rb.beat_status()
    assert st["timer_armed"] is False
    assert st["panel_attached"] is True


def test_detach_is_deliberate_and_reported():
    rb.ensure_beat_started()
    status = rb.detach_panel()
    assert status["panel_attached"] is False
    assert status["beat_running"] is False        # headless: no live timer
    assert status["detach_count"] == 1
    assert rb.beat_status()["panel_attached"] is False


def test_detach_never_shuts_the_chain_down(monkeypatch):
    # The old closeEvent called shutdown_freeze_chain() — that removed all
    # protection after close. The deliberate detach must NEVER do that.
    from synapse.server import freeze_chain as fc
    calls = {"shutdown": 0}
    monkeypatch.setattr(
        fc, "shutdown_freeze_chain",
        lambda: calls.__setitem__("shutdown", calls["shutdown"] + 1),
    )
    rb.ensure_beat_started()
    rb.detach_panel()
    assert calls["shutdown"] == 0


# ---------------------------------------------------------------------------
# RED/GREEN pair — the freeze_chain + resilience.Watchdog semantics
# (predicate 2). Short thresholds; poll on real state, never widen sleeps.
# ---------------------------------------------------------------------------

def _short_chain():
    from synapse.server import freeze_chain as fc
    return fc.FreezeChain(
        escalate_after=0.5,     # act 0.5s into a sustained freeze
        heartbeat_interval=0.03,
        freeze_threshold=0.25,  # "frozen" after 0.25s with no beat
    )


def test_GREEN_deliberate_detach_keeps_a_healthy_runtime_unescalated():
    """Panel closes -> deliberate detach -> the PROCESS-LIFETIME beat CONTINUES.
    A continuously-beaten (healthy) runtime must NEVER escalate, even well past
    the escalation deadline."""
    chain = _short_chain()
    try:
        end = time.time() + 1.2  # > escalate_after (0.5s) by a wide margin
        while time.time() < end:
            chain.heartbeat()
            assert not chain.escalated, "a beaten (healthy) runtime must not escalate"
            time.sleep(0.03)
        assert not chain.is_frozen
        assert not chain.escalated
    finally:
        chain.stop()


def test_RED_stalled_main_thread_still_escalates(monkeypatch):
    """Beat stops (main thread genuinely stalls) -> the Watchdog detects the
    freeze and the chain escalates. This is the exact exposure the old
    panel-owned timer created on close; the fix keeps the beat alive so this
    only fires on a REAL freeze."""
    from synapse.server import freeze_chain as fc
    # Hermetic: escalation's external reaches return None so this test flips the
    # latch and PROVES it reached the acting half, with no cross-test breaker/halt.
    breaker_peeked = {"n": 0}
    monkeypatch.setattr(fc, "_peek_transport_breaker",
                        lambda: breaker_peeked.__setitem__("n", breaker_peeked["n"] + 1) or None)
    monkeypatch.setattr(fc, "_peek_active_bridge", lambda: None)

    chain = fc.FreezeChain(escalate_after=0.5, heartbeat_interval=0.03, freeze_threshold=0.25)
    try:
        chain.heartbeat()  # arm the watchdog with one beat, then stop beating
        # The `escalated` latch flips (freeze_chain.py:183) BEFORE the acting
        # half (breaker peek, :203) runs on the escalation Timer thread. Poll
        # for the acting half so the assertion can't race the latch.
        deadline = time.time() + 6.0
        while time.time() < deadline and breaker_peeked["n"] < 1:
            time.sleep(0.02)
        assert chain.escalated, "a sustained unbeaten (frozen) main thread must escalate"
        assert chain.is_frozen
        assert breaker_peeked["n"] >= 1, "escalation must reach the acting half (breaker peek)"
    finally:
        chain.stop()


def test_owner_beat_after_detach_drives_the_chain_and_stays_healthy(monkeypatch):
    """Tie the OWNER to the chain: route module beat() to a short-threshold
    chain, detach the panel (must not shut down), then keep driving the
    process-lifetime beat via the owner — the runtime stays healthy."""
    from synapse.server import freeze_chain as fc
    chain = _short_chain()
    # runtime_beat._emit_beat does `from .freeze_chain import beat` each call, so
    # patching the module attribute routes the owner's beat into our short chain.
    monkeypatch.setattr(fc, "beat", chain.heartbeat)
    try:
        rb.ensure_beat_started()          # headless: marks attached, no real timer
        status = rb.detach_panel()        # deliberate detach
        assert status["panel_attached"] is False
        end = time.time() + 1.0           # > escalate_after
        while time.time() < end:
            rb.beat_once()                # the process-lifetime beat keeps going
            assert not chain.escalated
            time.sleep(0.03)
        assert not chain.escalated
    finally:
        chain.stop()
