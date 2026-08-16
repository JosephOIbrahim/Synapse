"""
Process-lifetime runtime beat source — the freeze-chain heartbeat owner.

# RUNTIME_BEAT_SOURCE

Why this module exists (R.2 / g5 lifecycle, 2026-08-16)
------------------------------------------------------
The 1 s main-thread liveness beat used to be a ``QTimer`` PARENTED TO THE
PANEL widget (``synapse_panel.py``: ``self._freeze_timer = QTimer(self)``).
Closing the panel destroyed the widget and with it the only heartbeat source.
The process-wide Watchdog (``server/freeze_chain.py``) survived, read the dead
beat as a freeze ~5 s later, and ~30 s after that ESCALATED against a
perfectly healthy session the artist had merely closed the panel on:
``breaker.force_open()`` plus a full emergency halt. The panel worked around
that by SHUTTING THE WHOLE CHAIN DOWN on close (``shutdown_freeze_chain``) —
which threw out freeze protection for any headless operation still running
after the panel closed, and left the runtime with no heartbeat owner at all.

This module relocates the beat to a PROCESS-LIFETIME owner. The ``QTimer``
here is PARENTLESS (owned by this module, not by any widget), so it survives
panel close and keeps beating the main-thread liveness signal for as long as
the Houdini process — and its Qt event loop — lives. The panel no longer
constructs the beat timer; it only asks this module to ensure the beat is
running (:func:`ensure_beat_started`) and, on close, performs a DELIBERATE
detach (:func:`detach_panel`) that LEAVES the process-lifetime beat running
rather than killing it.

Consequences, by R.2 target
---------------------------
* **Target 1** — the panel-parented beat source is gone; a single
  process-lifetime owner under ``python/synapse/server/`` (this file) emits
  the beat. Deleting the timer without this replacement would be no freeze
  protection at all, so the machine gate has a second leg that demands this
  owner exist.
* **Target 2** — panel close is a deliberate detach, not a shutdown: the beat
  continues, so the Watchdog keeps getting a live main-thread signal and never
  false-positives a freeze on the healthy runtime the artist just closed.
* **Target 4** — real freeze protection stays live. If the main thread
  genuinely stalls, the Qt event loop is blocked, THIS timer cannot fire, the
  beat stops, and the Watchdog escalates exactly as before. Idle is not
  frozen: an idle main thread still services the event loop, so the timer
  still fires.
* **Target 3 (heartbeat half)** — the runtime keeps its heartbeat across panel
  open/close cycles; reopen finds a live beat, not a fresh one.

Threading / headless
--------------------
:func:`ensure_beat_started` MUST be called on the main thread (where the Qt
event loop lives) — a parentless ``QTimer`` only fires there. Qt is imported
guardedly. Headless (no Qt, or no running ``QApplication`` — pytest / CI) this
module degrades to a no-op: :func:`ensure_beat_started` records that it could
not arm a real timer and returns ``False``; :func:`beat_once` can still drive
``freeze_chain`` manually for headless freeze simulation. Zero ``hou`` at
import; the only Houdini reach is inside ``freeze_chain`` itself.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger("synapse.runtime_beat")

# -- Qt import guard: mirror the panel's PySide6 -> PySide2 fallback ----------
_QT_AVAILABLE = False
QTimer = None  # type: ignore[assignment]
try:  # pragma: no cover - import shape varies by host
    from PySide6.QtCore import QTimer  # type: ignore
    _QT_AVAILABLE = True
except Exception:
    try:  # pragma: no cover
        from PySide2.QtCore import QTimer  # type: ignore
        _QT_AVAILABLE = True
    except Exception:
        QTimer = None  # type: ignore[assignment]
        _QT_AVAILABLE = False

# 1 s cadence — unchanged from the panel-owned timer it replaces. The Watchdog
# freeze threshold (freeze_chain -> resilience.Watchdog, 5 s) is tuned to this.
BEAT_INTERVAL_MS = 1000

# Module state is the whole point: it lives for the PROCESS, not any widget.
_lock = threading.RLock()
_timer = None            # the process-lifetime QTimer (parentless) or None headless
_panel_attached = False  # is a panel currently the UI consumer of this runtime?
_beat_count = 0          # beats emitted (timer + manual)
_detach_count = 0        # deliberate panel detaches observed


def _qapp_instance():
    """The running ``QApplication`` instance, or ``None``. A ``QTimer`` needs a
    live event loop to fire; with no QApplication we must not pretend to arm
    one. Guarded across PySide6 / PySide2 and a total Qt absence."""
    try:  # pragma: no cover - host dependent
        from PySide6.QtWidgets import QApplication  # type: ignore
        return QApplication.instance()
    except Exception:
        pass
    try:  # pragma: no cover
        from PySide2.QtWidgets import QApplication  # type: ignore
        return QApplication.instance()
    except Exception:
        return None


def _emit_beat() -> None:
    """Beat the process-wide freeze chain once, then count it.

    Best-effort: a missing/old server package must never break the timer
    thread or the UI thread. ``freeze_chain.beat()`` is cheap (lock +
    timestamp) and thread-safe.
    """
    global _beat_count
    try:
        from .freeze_chain import beat
        beat()
    except Exception:
        logger.debug("runtime beat: freeze_chain.beat() unavailable", exc_info=True)
    with _lock:
        _beat_count += 1


def ensure_beat_started() -> bool:
    """Ensure the process-lifetime beat is running. Idempotent. MAIN THREAD.

    Call from the panel constructor (main thread) on every open. The first
    call arms a single PARENTLESS ``QTimer`` that beats the freeze chain for
    the process lifetime; every later call — including the reopen path — is a
    no-op that simply re-marks the panel attached and confirms the beat is
    still live.

    Returns ``True`` when a live process-lifetime timer is beating the freeze
    chain, ``False`` in headless / no-event-loop contexts (no real timer
    armed — drive :func:`beat_once` manually there).
    """
    global _timer, _panel_attached
    with _lock:
        _panel_attached = True
        if _timer is not None:
            # Already armed for the process lifetime — the reopen path lands
            # here and must NOT create a second timer.
            return True
        if not _QT_AVAILABLE or _qapp_instance() is None:
            logger.info(
                "runtime beat: no Qt event loop — process-lifetime timer not "
                "armed (headless); drive freeze_chain via beat_once()"
            )
            return False
        try:
            # PARENTLESS on purpose: owned by this module, NOT by any widget,
            # so it survives panel close. This is the whole R.2 fix.
            t = QTimer()
            t.setInterval(BEAT_INTERVAL_MS)
            t.timeout.connect(_emit_beat)
            t.start()
            _timer = t
        except Exception:
            logger.exception("runtime beat: failed to arm process-lifetime timer")
            return False
    # First beat immediately (outside the arm branch's early returns) so the
    # chain arms at once rather than one interval late.
    _emit_beat()
    logger.info("runtime beat: process-lifetime timer armed (%d ms)", BEAT_INTERVAL_MS)
    return True


def detach_panel() -> dict:
    """DELIBERATE beat-source detach on panel close (target 2).

    The panel is closing but the runtime lives on. Unlike the old
    ``closeEvent`` — which stopped the beat and shut the whole freeze chain
    down — this LEAVES the process-lifetime beat running: the Watchdog keeps
    getting a live main-thread signal, so it never false-positives a freeze on
    the healthy runtime the artist just closed the panel on, and freeze
    protection stays armed for any headless operation still in flight.

    Emits one freshening beat when a live timer exists so the chain's
    ``_last_heartbeat`` is current at the exact moment of detach (the explicit
    "watchdog informed" step) — never a stale window during teardown. In
    headless (no timer) it does NOT synthesise a beat, so it can't lazily spin
    up a Watchdog thread nobody asked for.

    Returns a small status dict — the deliberate, non-silent record R.2 asks
    for. NEVER stops the beat; NEVER calls ``shutdown_freeze_chain``.
    """
    global _panel_attached, _detach_count
    with _lock:
        _panel_attached = False
        _detach_count += 1
        beating = _timer is not None
        detaches = _detach_count
    if beating:
        _emit_beat()  # freshen _last_heartbeat right at detach — "informed"
    with _lock:
        beats = _beat_count
    logger.info(
        "runtime beat: panel detached deliberately; process-lifetime beat "
        "still running=%s (detach #%d)", beating, detaches,
    )
    return {
        "beat_running": beating,
        "panel_attached": False,
        "detach_count": detaches,
        "beat_count": beats,
    }


def beat_once() -> None:
    """Emit a single beat immediately.

    The manual drive for headless freeze simulation (no Qt timer) and any
    main-thread caller that wants to freshen the liveness signal.
    """
    _emit_beat()


def is_beating() -> bool:
    """True when a live process-lifetime timer is armed (GUI); False headless."""
    with _lock:
        return _timer is not None


def beat_status() -> dict:
    """Introspection snapshot — observability for the panel / doctor / tests."""
    with _lock:
        return {
            "qt_available": _QT_AVAILABLE,
            "timer_armed": _timer is not None,
            "panel_attached": _panel_attached,
            "beat_count": _beat_count,
            "detach_count": _detach_count,
        }


def stop_beat() -> bool:
    """Stop and clear the process-lifetime timer.

    NOT part of panel close — ``closeEvent`` uses :func:`detach_panel`, which
    leaves the beat running. This exists for genuine process shutdown and for
    test teardown. Returns ``True`` if a timer was stopped.
    """
    global _timer
    with _lock:
        t, _timer = _timer, None
    if t is None:
        return False
    try:
        t.stop()
    except Exception:
        logger.debug("runtime beat: timer stop failed (best-effort)", exc_info=True)
    return True


def reset_for_test() -> None:
    """Reset module state — for hermetic tests only. Stops any timer and zeroes
    the counters/flags so one test's beats can't bleed into the next."""
    global _panel_attached, _beat_count, _detach_count
    stop_beat()
    with _lock:
        _panel_attached = False
        _beat_count = 0
        _detach_count = 0
