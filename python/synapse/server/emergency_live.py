"""
WS-path emergency halt — F3 (2026-08-14), the no-``/mcp``-bridge case.

``EmergencyProtocol.trigger_emergency_halt`` (``shared/bridge.py``) consumes a
``LosslessExecutionBridge`` and its ``session_report()``. The live ``/synapse``
hwebserver transport has no such bridge — its handler's ``_bridge`` is the
session tracker (``session/tracker.py``), so the pre-F3 freeze-chain halt
either crashed on it (Aug-13 ``AttributeError: SynapseBridge has no attribute
session_report``) or was skipped outright ("No ACTIVE bridge — emergency halt
skipped", all five on-disk freeze dumps). This module is the halt the WS path
actually gets.

Deadlock shape, analyzed (spec F3 item 3): the halt fires WHILE the main
thread is frozen mid-op. Anything the halt marshals onto the main thread
(hdefereval, run_on_main, executeInMainThreadWithResult) queues BEHIND the
very hold it is responding to — the halt would join the pile-up it exists to
interrupt, and on H22 the marshal block has no timeout either (it hangs the
escalation timer thread forever). So this halt performs ONLY what does not
need the main thread, and never waits on it:

    1. RECORD the in-flight holder from F4's ``current_main_thread_holder()``
       register — the label+age of the op holding the main thread RIGHT NOW
       goes into the report and the dump as evidence. Read-only, lock-free.
    2. CANCEL pending unstarted dispatches through the C4 abandoned-flag
       registry (``main_thread.cancel_pending_dispatches``) — queued payloads
       wake into a no-op instead of piling mutations behind the runaway hold.
       Lock+bool only; never touches hdefereval or the main thread.
    3. CANCEL PDG graph contexts through their own API
       (``getPDGGraphContext().cancelCook()``) — the same API the /mcp halt
       uses, called from THIS thread, not marshalled. Cancel of a PDG cook is
       a worker-side operation; it does not marshal onto the frozen main
       thread. Best-effort under the hou import guard, fully try/excepted.
    4. WRITE state: the halt's report persisted as ``emergency_halt_<UTC>.json``
       in the log dir — durable evidence of the actions taken (captured AFTER
       them, so it records their results). Deliberately not a second
       ``freeze_dump_*``: the chain's own escalation already dumped the
       ``sustained_freeze`` telemetry, and a duplicate would churn the bounded
       newest-5 freeze evidence.
    5. NOTIFY the panel: the panel IS the frozen main thread's host process —
       there is no channel it can paint to mid-freeze, so notification is the
       durable error log entry plus the freeze-chain transport breaker (which
       fast-fails the panel's next command with an honest "paused" response
       when the main thread recovers). ``last_live_halt_report()`` exposes the
       most recent halt for health surfaces to surface post-recovery.

Zero hou / hdefereval / Qt at import. Everything in here is callable from the
freeze-chain escalation timer thread with no risk of joining the freeze.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger("synapse.emergency_live")

try:
    import hou  # type: ignore
    _HOU_AVAILABLE = True
except ImportError:  # standalone / testing
    hou = None
    _HOU_AVAILABLE = False

# The most recent halt report, kept for post-recovery health surfaces.
_last_report: Optional[dict] = None
_report_lock = threading.Lock()


def last_live_halt_report() -> Optional[dict]:
    """Copy of the most recent WS-path halt report, or None."""
    with _report_lock:
        return dict(_last_report) if _last_report is not None else None


def _reset_live_halt_report():
    """Test helper — clear the stored report."""
    global _last_report
    with _report_lock:
        _last_report = None


def _holder_evidence(report: dict):
    """Read F4's in-flight register and age the current hold, if any.
    Lock-free single-writer read (main_thread.py documents the discipline)."""
    try:
        from . import main_thread
        holder = main_thread.current_main_thread_holder()
    except Exception:
        holder = None
    if holder is not None:
        label, start_ts = holder[0], holder[1]
        report["main_thread_holder"] = {
            "label": label,
            "start_ts": start_ts,
            "age_s": round(max(0.0, time.time() - float(start_ts)), 3),
        }
    else:
        report["main_thread_holder"] = None


def _cancel_pending_dispatches(report: dict, reason: str):
    """Flip the C4 abandoned flag on queued-but-unstarted dispatches."""
    try:
        from . import main_thread
        report["pending_dispatches_cancelled"] = (
            main_thread.cancel_pending_dispatches(reason)
        )
    except Exception as exc:
        report["pending_dispatches_cancelled"] = 0
        report.setdefault("notes", []).append(
            f"pending-dispatch cancel failed: {exc!r}"
        )


def _cancel_pdg_contexts(report: dict):
    """Suspend PDG cooks via their own API, from THIS thread. Best-effort,
    hou-guarded, and never marshalled onto the frozen main thread."""
    if not _HOU_AVAILABLE:
        report["pdg_contexts_cancelled"] = 0
        return
    cancelled = 0
    try:
        for node in hou.node("/obj").allSubChildren():
            try:
                if hasattr(node, "getPDGGraphContext"):
                    ctx = node.getPDGGraphContext()
                    if ctx:
                        ctx.cancelCook()
                        cancelled += 1
            except Exception:
                continue  # one bad TOP node must not stop the sweep
    except Exception as exc:
        report.setdefault("notes", []).append(f"pdg sweep failed: {exc!r}")
    report["pdg_contexts_cancelled"] = cancelled


_MAX_HALT_REPORTS = 5  # bounded evidence, same discipline as freeze_dump pruning


def _write_state(report: dict):
    """Durable evidence: persist THIS halt's report (what was cancelled, the
    holder evidence, the reason) as ``emergency_halt_<UTC>.json`` in the log
    dir — a NEW bounded artifact, pruned to the newest 5.

    Deliberately NOT a second ``flush_telemetry(reason=...)`` call: every
    non-periodic flush writes a fresh ``freeze_dump_*.json``, and the freeze
    chain's own escalation already dumped ``sustained_freeze`` evidence first.
    A second dump would be a byte-near-duplicate that pollutes the bounded
    newest-5 freeze evidence (evicting real freeze dumps one halt earlier) and
    silently breaks the M3-C pin "one escalation = one sustained_freeze dump".
    The halt's distinct state — its actions — is what needs persisting.
    """
    try:
        import json as _json
        import os as _os
        from ..core.logfile import log_dir
        d = log_dir()
        _os.makedirs(d, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = _os.path.join(d, f"emergency_halt_{stamp}.json")
        blob = _json.dumps(report, sort_keys=True, default=str).encode("utf-8")
        import tempfile as _tf
        fd, tmp = _tf.mkstemp(prefix=".halt-", suffix=".tmp", dir=d)
        try:
            with _os.fdopen(fd, "wb") as f:
                f.write(blob)
                f.flush()
            _os.replace(tmp, target)  # atomic, the bridge_endpoint idiom
        except Exception:
            try:
                _os.remove(tmp)
            except OSError:
                pass
            raise
        # Prune to the newest handful — never raise.
        try:
            dumps = sorted(
                (p for p in _os.listdir(d) if p.startswith("emergency_halt_")),
                reverse=True,
            )
            for old in dumps[_MAX_HALT_REPORTS:]:
                try:
                    _os.remove(_os.path.join(d, old))
                except OSError:
                    pass
        except Exception:
            pass
        report["state_file"] = target
    except Exception as exc:
        report["state_file"] = None
        report.setdefault("notes", []).append(f"state write failed: {exc!r}")


def emergency_halt_live(reason: str) -> dict:
    """The WS-path halt. OFF-MAIN-THREAD ACTIONS ONLY — never waits on,
    marshals onto, or constructs anything on the frozen main thread.

    Callable from the freeze-chain escalation timer thread; total work is
    peeks + lock-held flag flips + a PDG cancel sweep + one bounded local
    file write. Returns the halt report (also stored for
    ``last_live_halt_report()``).
    """
    global _last_report
    report = {
        "action": "LIVE_PATH_HALT",
        "execution_path": "live",
        "emergency_reason": reason,
        "emergency_timestamp": datetime.now().isoformat(),
        "notes": [],
    }
    _holder_evidence(report)
    _cancel_pending_dispatches(report, reason)
    _cancel_pdg_contexts(report)
    _write_state(report)
    with _report_lock:
        _last_report = dict(report)
    logger.error(
        "LIVE-PATH EMERGENCY HALT (%s): pending_dispatches_cancelled=%d "
        "pdg_contexts_cancelled=%d holder=%s state=%s",
        reason,
        report["pending_dispatches_cancelled"],
        report["pdg_contexts_cancelled"],
        (report.get("main_thread_holder") or {}).get("label"),
        report.get("state_file"),
    )
    return report
