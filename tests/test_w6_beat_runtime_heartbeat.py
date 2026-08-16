"""W6-BEAT (hardening 3/5 · S3, closes W5-LCRUX F5) — the runtime heartbeat proven
by BEHAVIOUR, not by a marker string.

W5-LIFE relocated the 1 s freeze beat from a panel-parented ``QTimer`` to a
process-lifetime owner (``server/runtime_beat.py``, ``# RUNTIME_BEAT_SOURCE``) and
made panel close a DELIBERATE detach. The machine gate that guarded it
(``harness/verify/checks.py::check_runtime_owns_heartbeat``) was grep-only: a
hollow ``# RUNTIME_BEAT_SOURCE`` comment with no real beat would green it (F5).

These pins exercise the **P0.3 contract itself**, headless (no Qt, no hou):

* **attach then destroy a panel-proxy → the beat CONTINUES.** The process-lifetime
  owner keeps a real ``FreezeChain`` fed past the escalation deadline, so a healthy
  session the artist merely closed the panel on never false-positive-escalates.
* **the session store SURVIVES** the panel-proxy's death AND the reopen module
  flush — because it is on disk, outside the ``synapse.*`` namespace.
* **regression simulation** — a HOLLOW / panel-parented beat (the original defect)
  makes the exact "beat continues" scenario ESCALATE. This proves the healthy-path
  assertions above are falsifiable, not vacuous: the pin catches the defect.

The lazy-``Watchdog`` subtlety is load-bearing: ``resilience.Watchdog`` does not
start monitoring until the first ``heartbeat()``. Every test that must observe an
escalation arms the chain with one real beat first — a never-beaten chain never
escalates, so a hollow owner would read "healthy" vacuously without the arm.
"""

from __future__ import annotations

import importlib
import sys
import time

import pytest

from synapse.server import freeze_chain as fc
from synapse.server import runtime_beat as rb
from synapse.server import session_store


@pytest.fixture(autouse=True)
def _hermetic(monkeypatch):
    """Headless + side-effect-free. No Qt event loop (so ``ensure_beat_started``
    takes the no-real-timer path deterministically, regardless of a sibling test's
    Qt stub). Reset the owner's module state around every test. Neutralise the
    escalation acting-half so a deliberately-frozen chain flips its latch with zero
    external side effects (breaker peek, WS-path halt, telemetry dump)."""
    monkeypatch.setattr(rb, "_qapp_instance", lambda: None)
    monkeypatch.setattr(fc, "_peek_transport_breaker", lambda: None)
    monkeypatch.setattr(fc, "_peek_active_bridge", lambda: None)
    try:
        import synapse.server.emergency_live as _el
        monkeypatch.setattr(
            _el, "emergency_halt_live",
            lambda **k: {"pending_dispatches_cancelled": 0, "main_thread_holder": None},
            raising=False,
        )
    except Exception:
        pass
    try:
        import synapse.server.telemetry_dump as _td
        monkeypatch.setattr(_td, "flush_telemetry", lambda **k: None, raising=False)
    except Exception:
        pass
    rb.reset_for_test()
    yield
    rb.reset_for_test()


def _short_chain():
    # Short thresholds so escalation is observable in ~0.5 s; wide poll margins so
    # CI timing jitter never flips the verdict (mirrors tests/test_w5_life_heartbeat).
    return fc.FreezeChain(escalate_after=0.5, heartbeat_interval=0.03, freeze_threshold=0.25)


class PanelProxy:
    """A Qt-free stand-in for the SynapsePanel widget's lifecycle. On ATTACH it asks
    the process-lifetime owner to ensure the beat (as the panel constructor does) and
    persists its conversation to the disk store; on CLOSE it performs the DELIBERATE
    detach (as ``closeEvent`` does). Destroying the object (``del``) drops it exactly
    as closing the Houdini panel drops the widget — and, critically, the beat is NOT
    the proxy's to own, so it lives on."""

    def __init__(self, store_path, messages):
        self._store_path = store_path
        rb.ensure_beat_started()                          # attach (headless: no real timer armed)
        session_store.save_conversation(messages, path=store_path)

    def close(self):
        return rb.detach_panel()                          # deliberate detach — beat survives


# ---------------------------------------------------------------------------
# Target 2a — attach, destroy the panel-proxy, the beat CONTINUES
# ---------------------------------------------------------------------------

def test_panel_death_leaves_the_process_lifetime_beat_running(tmp_path, monkeypatch):
    chain = _short_chain()
    # runtime_beat._emit_beat does `from .freeze_chain import beat` each call, so
    # patching the module attribute routes the OWNER's beat into our short chain.
    monkeypatch.setattr(fc, "beat", chain.heartbeat)
    try:
        chain.heartbeat()                                 # arm the lazy watchdog with one real beat
        proxy = PanelProxy(str(tmp_path / "conversation.json"),
                           [{"role": "user", "content": "hi"}])
        assert rb.beat_status()["panel_attached"] is True
        for _ in range(5):                                # beat while the panel is attached
            rb.beat_once()
            time.sleep(0.03)

        status = proxy.close()                            # deliberate detach
        assert status["panel_attached"] is False
        assert status["detach_count"] == 1
        del proxy                                         # the panel widget is destroyed on close

        # THE CONTRACT: the process-lifetime beat keeps the runtime healthy well past
        # the escalation deadline. The old panel-parented timer died here; this owner
        # does not.
        end = time.time() + 1.0                           # > escalate_after (0.5 s) by a wide margin
        while time.time() < end:
            rb.beat_once()                                # the PROCESS-LIFETIME beat, not the panel's
            assert not chain.escalated, \
                "a beaten (healthy) runtime must not escalate after panel close"
            time.sleep(0.03)
        assert not chain.escalated
        assert not chain.is_frozen
        assert rb.beat_status()["panel_attached"] is False   # still detached; beat still ran
    finally:
        chain.stop()


def test_detach_keeps_freeze_protection_armed_for_headless_work():
    # The old closeEvent worked around the false-freeze by calling
    # shutdown_freeze_chain() — trading a false positive for ZERO protection on any
    # headless op still running after close. The deliberate detach must never do that.
    from synapse.server import freeze_chain as _fc
    calls = {"shutdown": 0}
    import unittest.mock as _mock
    with _mock.patch.object(_fc, "shutdown_freeze_chain",
                            side_effect=lambda: calls.__setitem__("shutdown", calls["shutdown"] + 1)):
        rb.ensure_beat_started()
        rb.detach_panel()
    assert calls["shutdown"] == 0


# ---------------------------------------------------------------------------
# Target 2b — the session store SURVIVES panel death + the reopen module flush
# ---------------------------------------------------------------------------

def test_session_store_survives_panel_death_and_the_reopen_module_flush(tmp_path):
    store = str(tmp_path / "conversation.json")
    messages = [{"role": "user", "content": "build me a torus"},
                {"role": "assistant", "content": "on it — one torus coming up"}]

    proxy = PanelProxy(store, messages)
    proxy.close()
    del proxy                                             # widget death: self._messages would die here

    # (1) survives WIDGET death — the disk store outlives the object.
    assert session_store.has_conversation(store)
    assert session_store.load_conversation(store) == messages

    # (2) survives the REOPEN MODULE FLUSH. The pypanel loader deletes every
    # synapse.* module from sys.modules on each panel create; a store that lived in a
    # synapse.* module global would reset. This one is on disk, so a genuinely FRESH
    # module instance restores it. Pop just the leaf and restore it after (no suite
    # pollution).
    saved = sys.modules.pop("synapse.server.session_store", None)
    try:
        fresh = importlib.import_module("synapse.server.session_store")
        assert fresh is not saved, "expected a fresh module object after the flush"
        assert fresh.load_conversation(store) == messages
    finally:
        if saved is not None:
            sys.modules["synapse.server.session_store"] = saved


def test_fresh_scene_store_is_empty_not_a_crash(tmp_path):
    # A reopen on a scene with no prior conversation restores [] (fresh session),
    # never raises — the panel must open clean on a first run.
    store = str(tmp_path / "never_written.json")
    assert session_store.load_conversation(store) == []
    assert session_store.has_conversation(store) is False


# ---------------------------------------------------------------------------
# Crucible criterion 1 — the pin FAILS when the old panel-parented wiring is
# simulated. Prove the healthy-path assertions above can catch the original defect.
# ---------------------------------------------------------------------------

def test_regression_sim_hollow_beat_escalates_after_panel_close(monkeypatch):
    """Simulate the ORIGINAL defect: the beat does not actually feed the freeze chain
    after the panel closes (the panel-parented timer died with the widget; a hollow
    ``# RUNTIME_BEAT_SOURCE`` owner is the same shape). Under that defect the exact
    'beat continues after panel death' scenario ESCALATES — so the healthy-path pin
    is falsifiable, not vacuous."""
    chain = _short_chain()
    monkeypatch.setattr(fc, "beat", chain.heartbeat)
    # HOLLOW the owner: beat_once() no longer drives the chain.
    monkeypatch.setattr(rb, "_emit_beat", lambda: None)
    try:
        chain.heartbeat()                                 # a real beat existed once (arms the watchdog)
        rb.detach_panel()                                 # panel closes
        deadline = time.time() + 6.0
        while time.time() < deadline and not chain.escalated:
            rb.beat_once()                                # hollow -> no-op; nothing feeds the chain
            time.sleep(0.03)
        assert chain.escalated, \
            "a hollow / panel-parented beat MUST escalate after close — this is the defect the pin catches"
        assert chain.is_frozen
    finally:
        chain.stop()


def test_regression_sim_healthy_owner_does_not_escalate_same_scenario(monkeypatch):
    """The mirror of the sim: with the GENUINE owner (beat_once feeds the chain), the
    identical post-close scenario stays healthy. Together with the hollow sim this
    proves the assertion discriminates real-from-hollow, not that it always passes."""
    chain = _short_chain()
    monkeypatch.setattr(fc, "beat", chain.heartbeat)
    try:
        chain.heartbeat()
        rb.detach_panel()
        end = time.time() + 1.0
        while time.time() < end:
            rb.beat_once()                                # genuine -> feeds the chain
            assert not chain.escalated
            time.sleep(0.03)
        assert not chain.escalated
    finally:
        chain.stop()
