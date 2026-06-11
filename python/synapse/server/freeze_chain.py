"""
Process-wide freeze-safety chain — D3 wiring (CTO Remediation, operator call: WIRE).

The freeze chain was dead end-to-end on the live stack (C10, V1-confirmed):
the v9 panel never called ``server.heartbeat()``, so the Watchdog never armed;
``_on_freeze`` only logged; ``EmergencyProtocol.trigger_emergency_halt`` had
zero production callers. Worse, the chain only EXISTED on ``SynapseServer`` —
and the live transport is hwebserver (no resilience layer), with the fallback
``SynapseServer`` built ``enable_resilience=False``. Wiring the panel to
``server.heartbeat()`` alone would arm nothing: activation theater.

So the live freeze authority moves HERE: one process-wide Watchdog + the
escalation policy, independent of which transport runs.

    panel QTimer (1 s) ──► beat() ──► Watchdog.heartbeat()
                                          │ no heartbeat > 5 s
                                          ▼
                                   _on_freeze(elapsed)        [warn; arm timer]
                                          │ still frozen at 30 s
                                          ▼
                                   _escalate()                [act]
                                     ├─ live SynapseServer?  breaker.force_open()
                                     └─ ACTIVE bridge?       EmergencyProtocol
                                                              .trigger_emergency_halt()
    recovery (next beat) ──► _on_recover()  [cancel timer; reset breaker]

"Active bridge" means an already-constructed one (attribute peek on the live
handlers) — escalation never *creates* a bridge. Every action is best-effort:
the chain must never crash its own timer thread or the UI thread that beats it.

Zero ``hou`` at import. Zero Qt. The only consumers of hou are inside
``trigger_emergency_halt`` itself (already guarded there).
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

    @property
    def is_frozen(self) -> bool:
        return self._watchdog.is_frozen

    @property
    def escalated(self) -> bool:
        return self._escalated

    def stats(self) -> dict:
        s = self._watchdog.get_stats()
        s["escalated"] = self._escalated
        s["escalate_after_s"] = self._escalate_after
        return s

    # -- detection callbacks (Watchdog monitor thread) --------------------
    def _on_freeze(self, elapsed: float):
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
        srv = _peek_live_server()
        breaker = getattr(srv, "_circuit_breaker", None) if srv else None
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

            srv = _peek_live_server()
            breaker = getattr(srv, "_circuit_breaker", None) if srv else None
            if breaker is not None:
                try:
                    breaker.force_open()
                    logger.error("Circuit breaker forced OPEN (sustained freeze)")
                except Exception:
                    logger.exception("force_open failed")
            else:
                logger.error(
                    "No live SynapseServer breaker to open (hwebserver transport "
                    "has no resilience layer) — proceeding to the halt check"
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
                logger.error("No ACTIVE bridge — emergency halt skipped "
                             "(escalation never constructs one)")
        except Exception:
            # The chain must never crash its own timer thread.
            logger.exception("Freeze escalation crashed (suppressed)")


# -- reachability peeks (NEVER construct; attribute reads only) -------------

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
    """An ALREADY-CONSTRUCTED bridge, or None. Peeks `_bridge` attributes on the
    live handlers (hwebserver module handler, then the live server's). Never
    calls `_get_bridge()` — that would lazily create one."""
    try:
        from . import hwebserver_adapter
        handler = getattr(hwebserver_adapter, "_handler", None)
        bridge = getattr(handler, "_bridge", None)
        if bridge is not None:
            return bridge
    except Exception:
        pass
    try:
        srv = _peek_live_server()
        handler = getattr(srv, "_handler", None) if srv else None
        return getattr(handler, "_bridge", None)
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


def beat():
    """The panel's one-call entry: heartbeat the process-wide chain.
    Cheap (lock + timestamp); safe on the UI thread at 1 s cadence."""
    get_freeze_chain().heartbeat()
