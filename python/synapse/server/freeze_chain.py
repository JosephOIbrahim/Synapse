"""
Process-wide freeze-safety chain — D3 wiring (CTO Remediation, operator call: WIRE).

The freeze chain was dead end-to-end on the live stack (C10, V1-confirmed):
the v9 panel never called ``server.heartbeat()``, so the Watchdog never armed;
``_on_freeze`` only logged; ``EmergencyProtocol.trigger_emergency_halt`` had
zero production callers. Worse, the chain only EXISTED on ``SynapseServer`` —
and the live transport is hwebserver, with the fallback ``SynapseServer``
built ``enable_resilience=False``. Wiring the panel to ``server.heartbeat()``
alone would arm nothing: activation theater.

So the live freeze authority moved HERE: one process-wide Watchdog + the
escalation policy, independent of which transport runs. F3 (2026-08-14)
finished the net: the hwebserver transport now constructs its own breaker AT
STARTUP and registers it for the chain to read (the never-construct invariant
below is intact — this module still holds no constructor), the bridge peek
validates the halt-consumable shape (fixing the Aug-13 ``session_report``
AttributeError — the handler's ``_bridge`` is the session tracker, not a
``LosslessExecutionBridge``), and the no-``/mcp``-bridge case gets a WS-path
halt (``server/emergency_live.py``) that acts off-main-thread only and never
waits on the frozen main thread.

    panel QTimer (1 s) ──► beat() ──► Watchdog.heartbeat()
                                          │ no heartbeat > 5 s
                                          ▼
                                   _on_freeze(elapsed)        [warn; arm timer]
                                          │ still frozen at 30 s
                                          ▼
                                   _escalate()                [act]
                                     ├─ registered transport breaker? force_open()
                                     │     (else SynapseServer._circuit_breaker peek)
                                     ├─ haltable ACTIVE bridge?  EmergencyProtocol
                                     │                          .trigger_emergency_halt()
                                     └─ else WS-path halt (emergency_live)
    recovery (next beat) ──► _on_recover()  [cancel timer; reset breaker]

"Active bridge" means an already-constructed one (attribute peek on the live
handlers) — escalation never *creates* a bridge, and never creates a breaker
either (``register_transport_breaker`` receives only startup-constructed
breakers). Every action is best-effort: the chain must never crash its own
timer thread or the UI thread that beats it.

Zero ``hou`` at import. Zero Qt. The only consumers of hou are inside
``trigger_emergency_halt`` itself and the WS-path halt's guarded PDG sweep.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from .resilience import Watchdog

logger = logging.getLogger("synapse.freeze_chain")

# Detection fires at the Watchdog default (no heartbeat > 5 s). Escalation acts
# only if the freeze SUSTAINS to this wall-clock age (ratified D3 number).
ESCALATION_S = 30.0


class FreezeChain:
    """One Watchdog + the acting escalation policy. Construct via get_freeze_chain()."""

    def __init__(
        self,
        escalate_after: float = ESCALATION_S,
        heartbeat_interval: float = 1.0,
        freeze_threshold: float = 5.0,
    ):
        self._escalate_after = escalate_after
        self._timer_lock = threading.Lock()
        self._escalation_timer: Optional[threading.Timer] = None
        self._escalated = False
        self._stopped = False
        self._watchdog = Watchdog(
            heartbeat_interval=heartbeat_interval,
            freeze_threshold=freeze_threshold,
            on_freeze=self._on_freeze,
            on_recover=self._on_recover,
        )
        self._watchdog.start()  # arms lazily; monitoring begins on first heartbeat

    # -- the one call the panel makes ------------------------------------
    def heartbeat(self):
        self._watchdog.heartbeat()

    def stop(self):
        """Shut the WHOLE chain down: watchdog AND any pending escalation.

        Stopping only the watchdog leaves a zombie: an armed escalation Timer
        survives ``Watchdog.stop()``, and the watchdog's ``_is_frozen`` stays
        True after stop — so the orphaned timer fires later, passes its
        is-frozen guard, and acts (dump + breaker force_open) against whatever
        globals are live AT THAT MOMENT. In tests that double-fired
        force_open across test boundaries (the two flaky master-CI reds of
        2026-08-02); in production the same zombie could fire into a
        successor session after a panel teardown. Idempotent.
        """
        self._stopped = True
        with self._timer_lock:
            self._cancel_timer_locked()
        self._watchdog.stop()

    @property
    def is_frozen(self) -> bool:
        return self._watchdog.is_frozen

    @property
    def escalated(self) -> bool:
        """This freeze episode has been CLAIMED — not that its actions landed.

        ``_escalate`` sets this latch FIRST, then acts (telemetry dump, then
        breaker ``force_open``, then the emergency halt — in that order, in
        ``_escalate``'s body; line numbers deliberately not cited, they rotted
        once already inside this very docstring). The latch-before-act order
        is what makes a duplicate timer unable to act twice, and it opens a
        real millisecond-class window in which ``escalated`` is True while the
        breaker is still shut. Measured twice: the R310a lane probe read
        0.5-9.3 ms (flagged by its own author as an overestimate — the probe's
        spin loop steals GIL slices); the attack-F crucible's independent
        re-measure read 0.79-6.50 ms over 5 trials. Do not read this property
        as "the breaker is open"; wait on the outcome you actually care about.

        The dump ``flush_telemetry`` writes from inside that window records
        whatever this latch holds at read time — for a dump taken by
        ``_escalate`` itself that is ``escalated: true`` before the breaker
        provably opened (a claim recorded as an outcome, in SYNAPSE's own
        post-mortem artifact). Honest fix is a separate completion signal
        (R310a followup); deliberately not folded into the zombie fix, which
        was a different defect.
        """
        return self._escalated

    def stats(self) -> dict:
        s = self._watchdog.get_stats()
        s["escalated"] = self._escalated
        s["escalate_after_s"] = self._escalate_after
        return s

    # -- detection callbacks (Watchdog monitor thread) --------------------
    def _on_freeze(self, elapsed: float):
        if self._stopped:
            return  # monitor tick racing a shutdown must not arm a new timer
        logger.warning(
            "Main thread frozen for %.1fs — escalation in %.0fs unless it recovers",
            elapsed, max(0.0, self._escalate_after - elapsed),
        )
        t = threading.Timer(max(0.0, self._escalate_after - elapsed), self._escalate)
        t.daemon = True
        with self._timer_lock:
            self._cancel_timer_locked()
            self._escalation_timer = t
        t.start()

    def _on_recover(self):
        with self._timer_lock:
            self._cancel_timer_locked()
        was_escalated, self._escalated = self._escalated, False
        logger.info("Main thread recovered%s",
                    " (post-escalation: resetting breaker)" if was_escalated else "")
        breaker = _peek_transport_breaker()
        if breaker is not None:
            try:
                breaker.reset()
            except Exception:
                logger.exception("Breaker reset on recovery failed")

    def _cancel_timer_locked(self):
        if self._escalation_timer is not None:
            self._escalation_timer.cancel()
            self._escalation_timer = None

    # -- the acting half (escalation timer thread) ------------------------
    def _escalate(self):
        try:
            if self._stopped:
                return  # chain shut down after this timer was armed
            if self._escalated:
                return  # already acted for this freeze episode — never twice
            if not self._watchdog.is_frozen:
                return  # recovered between detection and the deadline
            self._escalated = True
            logger.error(
                "SUSTAINED FREEZE: main thread unresponsive ≥%.0fs — opening the "
                "circuit breaker and triggering the emergency halt (if a bridge "
                "is active)", self._escalate_after,
            )

            # M3-C: durable evidence FIRST — a sustained freeze is exactly the
            # state the post-mortem needs captured before any action mutates
            # it. Bounded and safe on this timer thread: in-memory peeks +
            # one small local write, zero hou, zero main-thread marshalling.
            # The outer try/except is the second net.
            try:
                from .telemetry_dump import flush_telemetry
                dump_path = flush_telemetry(reason="sustained_freeze")
                if dump_path:
                    logger.error("Freeze evidence dumped: %s", dump_path)
            except Exception:
                logger.exception("Freeze telemetry dump failed (best-effort)")

            breaker = _peek_transport_breaker()
            if breaker is not None:
                try:
                    breaker.force_open()
                    logger.error("Transport circuit breaker forced OPEN (sustained freeze)")
                except Exception:
                    logger.exception("force_open failed")
            else:
                logger.error(
                    "No transport breaker to open — none registered by a "
                    "live transport and no SynapseServer present — proceeding "
                    "to the halt check"
                )

            bridge = _peek_active_bridge()
            if bridge is not None:
                try:
                    from shared.bridge import EmergencyProtocol
                    report = EmergencyProtocol.trigger_emergency_halt(
                        bridge, reason=f"sustained main-thread freeze ≥{self._escalate_after:.0f}s"
                    )
                    logger.error("Emergency halt triggered: %s",
                                 report.get("action", "?"))
                except Exception:
                    logger.exception("Emergency halt failed (best-effort)")
            else:
                # F3 item 3 — the no-/mcp-bridge case: the WS-path halt, which
                # acts ONLY off-main-thread (pending-dispatch abandon via C4,
                # PDG context cancel via its own API, state write) and records
                # F4's in-flight holder as evidence. It NEVER waits on or
                # marshals onto the frozen main thread — anything it queued
                # there would sit behind the very hold it responds to.
                try:
                    from .emergency_live import emergency_halt_live
                    report = emergency_halt_live(
                        reason=f"sustained main-thread freeze ≥{self._escalate_after:.0f}s (no active /mcp bridge)"
                    )
                    logger.error(
                        "WS-path emergency halt fired: pending cancelled=%d holder=%s",
                        report.get("pending_dispatches_cancelled", 0),
                        (report.get("main_thread_holder") or {}).get("label"),
                    )
                except Exception:
                    logger.exception("WS-path emergency halt failed (best-effort)")
        except Exception:
            # The chain must never crash its own timer thread.
            logger.exception("Freeze escalation crashed (suppressed)")


# -- reachability peeks (NEVER construct; attribute reads only) -------------
#
# The NEVER-construct invariant covers the whole net, not just the bridge:
# the freeze handler must not mutate state while observing the freeze. So the
# hwebserver transport's breaker is constructed AT TRANSPORT STARTUP
# (hwebserver_adapter.start_hwebserver) and REGISTERED here for the chain to
# read — this module contains no breaker constructor call, only a slot.

_transport_breaker = None
_transport_breaker_lock = threading.Lock()


def register_transport_breaker(breaker):
    """Register an ALREADY-CONSTRUCTED transport circuit breaker.

    Called once by the transport's startup path (hwebserver_adapter on the
    live stack). The chain never constructs a breaker itself — construction
    inside the freeze handler was the exact shape the never-construct
    invariant bans. Pass None / never call for transports with no breaker.
    """
    global _transport_breaker
    with _transport_breaker_lock:
        _transport_breaker = breaker


def unregister_transport_breaker(breaker):
    """Unhook a registered breaker at transport shutdown. Stale-handle-safe:
    only clears when the live registration IS this breaker (matches the
    websocket registry's only_if discipline)."""
    global _transport_breaker
    with _transport_breaker_lock:
        if _transport_breaker is breaker:
            _transport_breaker = None


def _peek_transport_breaker():
    """The live transport's breaker: the REGISTERED one first (hwebserver
    path), else a SynapseServer's ``_circuit_breaker`` attribute. Never
    constructs; None when neither exists."""
    with _transport_breaker_lock:
        registered = _transport_breaker
    if registered is not None:
        return registered
    srv = _peek_live_server()
    return getattr(srv, "_circuit_breaker", None) if srv is not None else None


def _peek_live_server():
    """The running SynapseServer, if any — via its module registry (preferred)
    or the start_hwebserver fallback handle. None on the pure-hwebserver stack."""
    try:
        from .websocket import get_live_server
        srv = get_live_server()
        if srv is not None:
            return srv
    except Exception:
        pass
    try:
        from .start_hwebserver import get_running_server
        return get_running_server()
    except Exception:
        return None


def _peek_active_bridge():
    """An ALREADY-CONSTRUCTED haltable bridge, or None. Peeks `_bridge`
    attributes on the live handlers (hwebserver module handler, then the live
    server's). Never calls `_get_bridge()` — that would lazily create one.

    F3 item 2 (caller fix): the peek VALIDATES the shape before handing the
    object to ``EmergencyProtocol.trigger_emergency_halt``, whose first action
    is ``bridge.session_report()``. The live hwebserver handler's ``_bridge``
    is the session tracker ``SynapseBridge`` (``session/tracker.py``) — a
    memory/session bridge that has NO ``session_report`` method. That mismatch
    was the Aug-13 freeze-dump defect::

        Emergency halt failed (best-effort)
        AttributeError: 'SynapseBridge' object has no attribute 'session_report'

    The attribute already exists on the right class
    (``LosslessExecutionBridge.session_report``, shared/bridge.py) — nothing
    is implemented here; the fix is that this caller stops feeding the halt
    an object it can't consume. A shape-mismatch peek now yields None, so
    escalation falls through to the WS-path halt
    (``server/emergency_live.emergency_halt_live``) instead of crashing on
    the wrong bridge.
    """
    def _haltable(candidate):
        # EmergencyProtocol's only bridge read is session_report(). Duck-typed,
        # deliberately not isinstance: standalone tests run with no shared
        # import path fixtures and both sides honor the same contract.
        return candidate is not None and callable(
            getattr(candidate, "session_report", None)
        )

    try:
        from . import hwebserver_adapter
        handler = getattr(hwebserver_adapter, "_handler", None)
        bridge = getattr(handler, "_bridge", None)
        if _haltable(bridge):
            return bridge
        if bridge is not None:
            logger.info(
                "Peeked handler._bridge (%s) is not a haltable bridge "
                "(no session_report) — routing to the WS-path halt",
                type(bridge).__name__,
            )
    except Exception:
        pass
    try:
        srv = _peek_live_server()
        handler = getattr(srv, "_handler", None) if srv else None
        return getattr(handler, "_bridge", None) if _haltable(
            getattr(handler, "_bridge", None)
        ) else None
    except Exception:
        return None


# -- process-wide singleton ---------------------------------------------------

_chain: Optional[FreezeChain] = None
_chain_lock = threading.Lock()


def get_freeze_chain() -> FreezeChain:
    """Lazy process-wide chain (created on the first beat)."""
    global _chain
    with _chain_lock:
        if _chain is None:
            _chain = FreezeChain()
        return _chain


def shutdown_freeze_chain() -> bool:
    """Stop the process-wide chain and clear the singleton.

    Returns True if a chain was running, False if there was nothing to stop.
    Idempotent and safe to call when no chain was ever built.

    This is the counterpart ``get_freeze_chain()`` never had, and its absence
    was a live defect. ``get_freeze_chain()`` starts a Watchdog thread plus the
    acting escalation policy at PRODUCTION thresholds; when whatever was
    beating it goes away, ``_last_heartbeat`` simply stops advancing. Nothing
    marks the chain done, so ~``freeze_threshold`` seconds later the orphan
    "detects" a freeze and ~``ESCALATION_S`` seconds after that it ESCALATES —
    ``breaker.force_open()`` on the live server plus a full
    ``EmergencyProtocol.trigger_emergency_halt`` on whatever bridge is active
    AT THAT MOMENT. That is exactly the zombie ``FreezeChain.stop()`` documents,
    one level up at the singleton, where no caller could reach ``stop()``.

    Not hypothetical on either side:

    * **Production** — closing the SYNAPSE panel ends its 1 s beat but left the
      chain running, so a still-live bridge could be halted ~30 s after a panel
      close the artist had already moved on from. ``panel.closeEvent`` now
      calls this.
    * **Tests** — one ``fc.beat()`` in
      ``test_beat_singleton_is_stable_and_cheap`` armed an escalation that
      fired 30.0 s later into an unrelated test's mock breaker, turning
      ``force_open.assert_called_once()`` into "Called 2 times" in whichever
      test happened to be running then. That is the R310a flake in
      ``tests/test_m3_logs_doctor.py`` — a different test each run, in a file
      nobody had touched. Reproduced deterministically by padding the gap
      between the two files to 29.3-29.6 s.
    """
    global _chain
    with _chain_lock:
        chain, _chain = _chain, None
    if chain is None:
        return False
    chain.stop()
    return True


def beat():
    """The panel's one-call entry: heartbeat the process-wide chain.
    Cheap (lock + timestamp); safe on the UI thread at 1 s cadence."""
    get_freeze_chain().heartbeat()
