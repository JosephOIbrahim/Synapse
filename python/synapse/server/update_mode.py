"""
F1 (freeze-relief, 2026-08-14) — update-mode sandwich.

The measured 179s UI-freeze class is an auto-cook flood: an inline payload
(``execute_python`` / Solaris build-graph) mutates N nodes, and every
mutation kicks an automatic recook while the main thread — and with it the
Qt UI — is held. The sandwich collapses the flood: snapshot the session's
update mode, force ``hou.updateMode.Manual`` for the payload's duration,
restore the pre-sandwich mode unconditionally, THEN ``hou.ui.triggerUpdate()``
(the vendor-documented mechanism — vendor ``hou.py:103374-103383``) so the
deferred changes surface as one update.

Two assumptions are explicitly UNVERIFIED and are NOT relied on here:
"restoring the mode itself triggers one consolidated cook" and
"``cook(force=True)`` works under Manual" — vendor docstrings do not state
either (``hou.py:118487-118500``) and ``h3a_symbols.json:53-55`` marks the
symbols probe-pending. The live gate is ``harness/notes/
probe_update_mode_sandwich.py`` items (a)-(d); this module shipped behind a
dev flag precisely so a failed probe means descope, not fix-forward.

Guards (non-negotiable):
- GUI sessions only: headless (``hou.isUIAvailable()`` False) and
  ``hou``-absent are passthrough no-ops.
- try/finally restore: the PRE-SANDWICH mode from the snapshot is restored
  even if the payload calls ``hou.setUpdateMode`` itself (nested-payload
  safety — the restore is the snapshot, never a constant).
- No UI pumping inside the sandwich. That class is refuted; it stays out.
- Dev-default-OFF flag: ``SYNAPSE_COOK_SANDWICH=1`` (repo convention:
  ``os.environ.get(...).strip().lower() in {truthy}``, mirrors
  ``handlers_cache.advisor_enabled`` and ``core/floor_gate.py``).

Scope invariant (crucible): *sandwich scope ≤ op scope.* The sandwich sits
INSIDE the caller's undo group / per-op hash bracket; it never wraps
``batch_commands`` (a batch's N sub-ops live under one undo group and one
hash bracket — a sandwich around them would span the bracket).

Instrumentation (spec R2 — no live win number exists yet): every ACTIVE
sandwich records hold duration into a module-local histogram (same bucket
scheme as ``main_thread.py``'s direct-path histogram) plus the caller's
collapsed-cook estimate hint, so the instrumented A/B run can measure the
shortened hold. Pass no hint and the record is a hold measurement only.
"""

import contextlib
import logging
import os
import threading
import time

_log = logging.getLogger(__name__)

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:  # standalone / test mode
    hou = None
    HOU_AVAILABLE = False

# Same bucket scheme as main_thread.py's direct-duration histogram so the
# A/B read compares like with like.
_SANDWICH_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
_sandwich_lock = threading.Lock()
_sandwich_stats = {
    "count": 0,                    # active sandwiches (flag on + GUI)
    "sum_ms": 0.0,                 # total hold duration
    "max_ms": 0.0,
    "buckets": {b: 0 for b in _SANDWICH_BUCKETS_MS},
    "est_collapsed_cooks": 0,      # sum of caller note_estimate() hints
    "est_labeled": 0,              # sandwiches that carried a hint
    "skipped_headless": 0,         # flag on, but no GUI session
    "skipped_flag_off": 0,         # flag off (dev default)
    "restore_failures": 0,         # finally-restore raised — bad, count it
}


def sandwich_enabled() -> bool:
    """SYNAPSE_COOK_SANDWICH, OFF by default (dev flag)."""
    return os.environ.get("SYNAPSE_COOK_SANDWICH", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _record(hold_ms, est_collapsed=None):
    with _sandwich_lock:
        _sandwich_stats["count"] += 1
        _sandwich_stats["sum_ms"] += hold_ms
        if hold_ms > _sandwich_stats["max_ms"]:
            _sandwich_stats["max_ms"] = hold_ms
        for b in _SANDWICH_BUCKETS_MS:
            if hold_ms <= b:
                _sandwich_stats["buckets"][b] += 1
        if est_collapsed is not None:
            _sandwich_stats["est_collapsed_cooks"] += est_collapsed
            _sandwich_stats["est_labeled"] += 1


def _mark(key):
    with _sandwich_lock:
        _sandwich_stats[key] += 1


def sandwich_stats():
    """Snapshot of the sandwich histogram (copy — safe to serialize)."""
    with _sandwich_lock:
        return {
            "count": _sandwich_stats["count"],
            "sum_ms": _sandwich_stats["sum_ms"],
            "max_ms": _sandwich_stats["max_ms"],
            "buckets": dict(_sandwich_stats["buckets"]),
            "est_collapsed_cooks": _sandwich_stats["est_collapsed_cooks"],
            "est_labeled": _sandwich_stats["est_labeled"],
            "skipped_headless": _sandwich_stats["skipped_headless"],
            "skipped_flag_off": _sandwich_stats["skipped_flag_off"],
            "restore_failures": _sandwich_stats["restore_failures"],
            "enabled": sandwich_enabled(),
        }


def reset_sandwich_stats():
    """Test/diagnostic helper — zero the histogram (not the flag state)."""
    with _sandwich_lock:
        for k in _sandwich_stats:
            if k == "buckets":
                _sandwich_stats["buckets"] = {
                    b: 0 for b in _SANDWICH_BUCKETS_MS}
            elif isinstance(_sandwich_stats[k], float):
                _sandwich_stats[k] = 0.0
            else:
                _sandwich_stats[k] = 0


class SandwichProbe:
    """Yielded handle. Call sites that KNOW how many auto-cooks the payload
    would have fired (e.g. build_graph: one per node op + display flag)
    report it via ``note_estimate(n)``; arbitrary-code payloads
    (execute_python) pass nothing and contribute a hold sample only."""

    __slots__ = ("label", "active", "est_collapsed")

    def __init__(self, label, active):
        self.label = label
        self.active = active
        self.est_collapsed = None

    def note_estimate(self, n):
        if self.active:
            self.est_collapsed = int(n)


@contextlib.contextmanager
def cook_sandwich(label="cook_sandwich"):
    """Manual-update sandwich: collapse auto-cook floods into one update.

    Passthrough when the flag is off, hou is absent, or the session is
    headless — in every skip case the payload runs identically to today.
    """
    if not sandwich_enabled():
        _mark("skipped_flag_off")
        yield SandwichProbe(label, active=False)
        return
    if not (HOU_AVAILABLE and hou.isUIAvailable()):
        _mark("skipped_headless")
        yield SandwichProbe(label, active=False)
        return

    probe = SandwichProbe(label, active=True)
    # Snapshot FIRST — the restore target is always the pre-sandwich mode,
    # never a constant, so a payload that calls setUpdateMode itself still
    # gets the artist's mode back.
    prior = hou.updateModeSetting()
    t0 = time.perf_counter()
    try:
        hou.setUpdateMode(hou.updateMode.Manual)
    except Exception as e:
        # Couldn't enter Manual — run the payload exactly as today rather
        # than fail a working op on an instrumented experiment.
        _log.warning("cook_sandwich(%s): could not enter Manual (%s); "
                     "payload runs unsandwiched", label, e)
        _mark("skipped_headless")
        yield probe
        return

    try:
        yield probe
    finally:
        # Restore is non-negotiable and must survive whatever the payload
        # raised. A restore failure leaves the session stuck in Manual — the
        # worst failure mode of this mechanism — so it is logged LOUD and
        # counted, and triggerUpdate is still attempted.
        try:
            hou.setUpdateMode(prior)
        except Exception as e:
            _mark("restore_failures")
            _log.error("cook_sandwich(%s): FAILED to restore update mode %r "
                       "— session may be stuck in Manual (%s)",
                       label, prior, e)
        # triggerUpdate is the vendor-documented update mechanism — the
        # claim that restore itself re-cooks is UNVERIFIED, so we never
        # rely on it. Failures here are bad but never mask the payload's
        # own exception.
        try:
            hou.ui.triggerUpdate()
        except Exception as e:
            _log.error("cook_sandwich(%s): hou.ui.triggerUpdate() failed "
                       "(%s)", label, e)
        hold_ms = (time.perf_counter() - t0) * 1000.0
        _record(hold_ms, probe.est_collapsed)
        _log.debug("cook_sandwich(%s): held %.1fms, est_collapsed=%s",
                   label, hold_ms, probe.est_collapsed)
