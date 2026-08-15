"""
Main-thread execution utility for Synapse handlers.

Wraps any callable to run on Houdini's main thread with a timeout.
Uses hdefereval.executeDeferred() (non-blocking) + threading.Event
instead of executeInMainThreadWithResult() (blocking, no timeout).

This prevents the soft-deadlock where a hou.* call from the WebSocket
thread blocks indefinitely when Houdini's main thread is busy cooking
or rendering, which in turn blocks all subsequent WebSocket messages
(including pings) behind the stuck handler.
"""

import threading
import time
import logging

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0   # seconds -- scene queries, parm reads/writes
_SLOW_TIMEOUT = 30.0      # seconds -- execute_python, execute_vex, batch

# Thread-local flag to detect reentrant calls (e.g. batch_commands calling
# sub-handlers that each use run_on_main). When already on the main thread
# inside a run_on_main callback, nested calls execute directly.
_tls = threading.local()

# Cache the main thread ID at import time so we can detect main-thread
# callers even when they didn't enter via run_on_main (e.g. Qt slots
# dispatched by AutoConnection from a worker thread).
_MAIN_THREAD_ID = threading.main_thread().ident

# Consecutive timeout counter — used to fast-fail incoming commands when
# the main thread is persistently unresponsive (e.g. frozen UI, heavy cook).
# After 2+ consecutive timeouts, is_main_thread_stalled() returns True and
# new commands fail immediately instead of each blocking for 10-30s.
_stall_lock = threading.Lock()
_consecutive_timeouts = 0
_last_timeout_ts = None   # time.time() of the most recent run_on_main timeout (H3)
_STALL_THRESHOLD = 2

# C6 (Mile 3.1) — dispatch-wait instrumentation. The load-bearing "~2s mutation
# floor" was never attributed: the per-tool histogram times the WHOLE handler, so
# enqueue→callback-start wait (the executeDeferred wake latency — hypothesis T1)
# is indistinguishable from hou work. This histogram measures exactly that gap.
# Buckets straddle the 2000 ms suspect so T1's signature (mass at/near 2000) is
# unmistakable against T2/T3 (small or cook-correlated waits).
_DISPATCH_WAIT_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
_dispatch_lock = threading.Lock()
_dispatch_wait = {
    "count": 0,
    "sum_ms": 0.0,
    "max_ms": 0.0,
    "buckets": {b: 0 for b in _DISPATCH_WAIT_BUCKETS_MS},
}


def _record_dispatch_wait(ms):
    with _dispatch_lock:
        _dispatch_wait["count"] += 1
        _dispatch_wait["sum_ms"] += ms
        if ms > _dispatch_wait["max_ms"]:
            _dispatch_wait["max_ms"] = ms
        for b in _DISPATCH_WAIT_BUCKETS_MS:
            if ms <= b:
                _dispatch_wait["buckets"][b] += 1


def dispatch_wait_stats():
    """Snapshot of the enqueue→start wait histogram (copy — safe to serialize)."""
    with _dispatch_lock:
        return {
            "count": _dispatch_wait["count"],
            "sum_ms": _dispatch_wait["sum_ms"],
            "max_ms": _dispatch_wait["max_ms"],
            "buckets": dict(_dispatch_wait["buckets"]),
        }


def reset_dispatch_wait_stats():
    """Test/diagnostic helper — zero the histogram."""
    with _dispatch_lock:
        _dispatch_wait["count"] = 0
        _dispatch_wait["sum_ms"] = 0.0
        _dispatch_wait["max_ms"] = 0.0
        for b in _DISPATCH_WAIT_BUCKETS_MS:
            _dispatch_wait["buckets"][b] = 0


# C6 (continued) — main-thread DIRECT-path instrumentation. The dominant live
# panel/bridge path runs INLINE on the main thread and short-circuits run_on_main
# at fast path 2 below, returning fn() without ever recording a dispatch-wait
# sample. Result: dispatch_waits.count stays 0 on the path that matters — zero
# attribution. This histogram times fn() on that direct path so the panel/bridge
# path is finally attributed. Distinct sink from _dispatch_wait: that one is the
# enqueue→start WAIT on the worker path; this one is the fn() DURATION on the main
# thread (no queue, so wait is ~0). Same bucket scheme for read parity.
_DIRECT_DURATION_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
_direct_lock = threading.Lock()
_main_thread_direct = {
    "count": 0,
    "sum_ms": 0.0,
    "max_ms": 0.0,
    "buckets": {b: 0 for b in _DIRECT_DURATION_BUCKETS_MS},
}


def _record_main_thread_direct(ms):
    with _direct_lock:
        _main_thread_direct["count"] += 1
        _main_thread_direct["sum_ms"] += ms
        if ms > _main_thread_direct["max_ms"]:
            _main_thread_direct["max_ms"] = ms
        for b in _DIRECT_DURATION_BUCKETS_MS:
            if ms <= b:
                _main_thread_direct["buckets"][b] += 1


def main_thread_direct_stats():
    """Snapshot of the main-thread direct-path fn() duration histogram
    (copy — safe to serialize). Records the panel/bridge inline path that the
    dispatch-wait histogram never sees."""
    with _direct_lock:
        return {
            "count": _main_thread_direct["count"],
            "sum_ms": _main_thread_direct["sum_ms"],
            "max_ms": _main_thread_direct["max_ms"],
            "buckets": dict(_main_thread_direct["buckets"]),
        }


def reset_main_thread_direct_stats():
    """Test/diagnostic helper — zero the direct-path histogram."""
    with _direct_lock:
        _main_thread_direct["count"] = 0
        _main_thread_direct["sum_ms"] = 0.0
        _main_thread_direct["max_ms"] = 0.0
        for b in _DIRECT_DURATION_BUCKETS_MS:
            _main_thread_direct["buckets"][b] = 0


# OCC — deferred-path main-thread HOLD instrumentation. The two C6 sinks above
# cover the queue wait (worker path, enqueue→callback-start) and the inline
# fn() duration (fast path 2). The DEFERRED payload itself — fn() running on
# the main thread inside _on_main, which is how EVERY off-main tool payload
# reaches Houdini — was timed by NOTHING: main-thread occupancy had to be
# inferred from wall clocks and timeout constants, and the 2026-07-31 freeze
# investigation got both wrong (10,005ms was _DEFAULT_TIMEOUT + overhead; the
# "46.7s stall" contained three recoveries). This histogram times fn() ON the
# main thread, between the C4 abandoned-flag check and the result store.
# Distinct sink from _dispatch_wait (queue time, same call) and from
# _main_thread_direct (inline path, which never reaches _on_main). Same bucket
# scheme as both for read parity. ``abandoned_count`` counts payloads that
# finished AFTER their caller had already timed out (the C4 residual race) —
# exactly the holds a freeze investigation is looking for. ``slowest_label``
# names the payload that set ``max_ms`` (labels arrive via run_on_main's
# optional ``label=``; unlabeled callers record as "unlabeled").
_HOLD_BUCKETS_MS = (1, 5, 10, 50, 100, 250, 500, 1000, 2000, 4000)
_hold_lock = threading.Lock()
_main_thread_hold = {
    "count": 0,
    "sum_ms": 0.0,
    "max_ms": 0.0,
    "buckets": {b: 0 for b in _HOLD_BUCKETS_MS},
    "slowest_label": None,
    "abandoned_count": 0,
}


def _record_main_thread_hold(ms, label=None, abandoned=False):
    label = label or "unlabeled"
    with _hold_lock:
        _main_thread_hold["count"] += 1
        _main_thread_hold["sum_ms"] += ms
        if ms > _main_thread_hold["max_ms"]:
            _main_thread_hold["max_ms"] = ms
            _main_thread_hold["slowest_label"] = label
        for b in _HOLD_BUCKETS_MS:
            if ms <= b:
                _main_thread_hold["buckets"][b] += 1
        if abandoned:
            _main_thread_hold["abandoned_count"] += 1


# F4 (2026-08-14) — in-flight register. The hold histogram above records
# COMPLETED holds only: a payload still RUNNING is invisible mid-flight, which
# is exactly the class behind the 2026-08-13/14 freezes — a mid-freeze dump
# named a 651ms doctor as slowest while a 179s execute_python was in flight.
# One register covers BOTH dispatch paths: fast path 2 (inline, caller already
# on the main thread) and the deferred _on_main payload (set once the C4
# abandoned-check passes, so deferred zombie renders are named MID-FLIGHT, not
# only after they complete).
# Single-writer-safe by construction: both write sites execute only on the
# main thread, so at most one writer exists at any moment and the writes are
# bare reference assignments (atomic under the GIL). Readers (freeze chain /
# telemetry dump on the watchdog thread, panel retry gate) read with no lock.
# Entry is (label, start_ts); nested payloads save/restore the previous entry
# so an inner hold never erases the outer one's attribution.
_in_flight = None  # (label, start_ts) of the payload currently on the main thread, else None


def current_main_thread_holder():
    """(label, start_ts) of the payload currently holding the main thread,
    or None when the main thread is idle between payloads.

    Lock-free read-over-only: the register is written solely on the main
    thread (single writer), so a concurrent read sees either the old or the
    new tuple — never a torn value. ``start_ts`` is a time.time() stamp so
    callers can age the current hold (``time.time() - start_ts``); the F2
    retry circuit-breaker and the FreezeChain dump consume exactly that.
    """
    return _in_flight


def main_thread_hold_stats():
    """Snapshot of the deferred-path main-thread hold histogram (copy — safe
    to serialize). This is real occupancy: fn()'s duration measured on the
    main thread itself, not inferred from wall clocks or timeout constants."""
    with _hold_lock:
        return {
            "count": _main_thread_hold["count"],
            "sum_ms": _main_thread_hold["sum_ms"],
            "max_ms": _main_thread_hold["max_ms"],
            "buckets": dict(_main_thread_hold["buckets"]),
            "slowest_label": _main_thread_hold["slowest_label"],
            "abandoned_count": _main_thread_hold["abandoned_count"],
        }


def reset_main_thread_hold_stats():
    """Test/diagnostic helper — zero the hold histogram."""
    with _hold_lock:
        _main_thread_hold["count"] = 0
        _main_thread_hold["sum_ms"] = 0.0
        _main_thread_hold["max_ms"] = 0.0
        for b in _HOLD_BUCKETS_MS:
            _main_thread_hold["buckets"][b] = 0
        _main_thread_hold["slowest_label"] = None
        _main_thread_hold["abandoned_count"] = 0


# F3 (2026-08-14) — pending-dispatch registry. The C4 abandoned flag lives in
# a per-call closure, so nothing OUTSIDE the timed-out caller could cancel a
# dispatch still sitting in the hdefereval queue. During a sustained main-
# thread freeze that is exactly the pile-up pattern: every queued payload
# wakes AFTER the runaway hold clears and mutates the scene anyway. The
# freeze-chain WS-path halt (server/emergency_live.py) flips the SAME C4 flag
# through this registry instead — a cancelled payload wakes into
# `if abandoned[0]: return` inside _on_main, no-oping the mutation. Only
# entries whose payloads have NOT started are flipped safely: an in-flight
# payload reads the flag only before fn() runs (the C4 check), so setting it
# mid-flight changes telemetry attribution, not the running payload. The halt
# never waits on the frozen main thread — flipping is pure lock+bool work.
# Entries deregister when their caller's wait ends (finally-block below), so
# the registry holds only live dispatches.
_pending_lock = threading.Lock()
_pending_dispatches = {}  # token -> (state_lock, abandoned_list, label, enqueue_ts)


def cancel_pending_dispatches(reason: str = "emergency_halt") -> int:
    """Flip the C4 abandoned flag on every pending (unstarted) dispatch.

    Safe to call from ANY thread, notably the freeze-chain escalation timer
    thread while the main thread is frozen — it acquires only per-dispatch
    state locks and the registry lock, never the main thread and never
    hdefereval. Returns the number of dispatches abandoned. A dispatch whose
    caller already timed out is gone from the registry (its own finally
    deregistered it), so this only reaches dispatches a caller still awaits.
    """
    with _pending_lock:
        entries = list(_pending_dispatches.values())
    flipped = 0
    for state_lock, abandoned, label, enqueue_ts in entries:
        try:
            with state_lock:
                if not abandoned[0]:
                    abandoned[0] = True
                    flipped += 1
        except Exception:
            pass  # a payload that raced out must not break the halt
    if flipped:
        logger.warning(
            "Abandoned %d pending main-thread dispatch(es) (%s)", flipped, reason
        )
    return flipped


def pending_dispatch_count() -> int:
    """Live count of main-thread dispatches waiting on hdefereval to wake."""
    with _pending_lock:
        return len(_pending_dispatches)


def is_main_thread_stalled():
    """Return True if recent run_on_main calls have been timing out.

    Used by the WebSocket handler to fast-fail incoming commands instead
    of queueing them behind a blocked main thread (which causes the
    connection accumulation cascade).
    """
    with _stall_lock:
        return _consecutive_timeouts >= _STALL_THRESHOLD


def stall_state():
    """Snapshot of the stall detector (H3) — copy, safe to serialize.

    Surfaced by the doctor (_check_main_thread) and used by the fast-fail
    gates for attribution-aware error messages. ``last_timeout_ts`` is the
    time.time() of the most recent timeout and survives a counter reset
    (it answers "when did this last happen", not "are we stalled now").
    """
    with _stall_lock:
        return {
            "stalled": _consecutive_timeouts >= _STALL_THRESHOLD,
            "consecutive_timeouts": _consecutive_timeouts,
            "last_timeout_ts": _last_timeout_ts,
        }


def probe_main_thread(timeout=2.0):
    """H3: bounded recovery probe for the two fast-fail gates.

    Only a successful worker-path run_on_main resets the stall counter, so a
    stall could stick until incidental read-only traffic happened to reset it.
    While stalled, the gates attempt this <=`timeout`s probe once per rejected
    command: success resets the counter (and the command proceeds); failure
    fast-fails as before. Returns True when the main thread responded.
    """
    try:
        run_on_main(lambda: True, timeout=timeout, label="main_thread:probe_main_thread")
    except Exception:
        return False
    # run_on_main's worker path already reset the counter; the main-thread
    # fast paths return early without doing so — reset explicitly (idempotent)
    # so a probe that provably ran is always a recovery signal.
    _record_success()
    return True


def _record_timeout(timeout):
    global _consecutive_timeouts, _last_timeout_ts
    with _stall_lock:
        _consecutive_timeouts += 1
        _last_timeout_ts = time.time()
        count = _consecutive_timeouts
    logger.warning("Main thread timeout (%d consecutive, %.0fs limit)", count, timeout)


def _record_success():
    global _consecutive_timeouts
    with _stall_lock:
        _consecutive_timeouts = 0


def run_on_main(fn, timeout=_DEFAULT_TIMEOUT, record_stall=True, record_wait=True,
                label=None):
    """Run *fn* on Houdini's main thread with a timeout.

    Returns the result of fn(). Raises RuntimeError if the timeout
    expires (Houdini main thread is busy). Re-raises any exception
    that fn() raised.

    Reentrant-safe: if called from within a run_on_main callback
    (already on the main thread), fn() is invoked directly.
    Also detects when the caller is already on the main thread
    (e.g. via a Qt slot) and calls fn() directly to avoid deadlock.

    ``record_stall=False`` opts a timeout OUT of the stall detector
    (_record_timeout / is_main_thread_stalled). For observe-only callers with
    short timeouts (the live integrity envelope's scene-hash captures): two
    such timeouts back-to-back would otherwise trip the 2-strike threshold
    and flip the WS resilience layer into fast-failing REAL commands.
    The RuntimeError is raised either way; success still resets the counter.

    ``record_wait=False`` additionally opts the wake OUT of the C6
    dispatch-wait histogram (_record_dispatch_wait). The live envelope's
    captures pass it: ~2 envelope wakes per mutating op would otherwise
    dominate the C6/T1 attribution instrument — that histogram must stay
    a measure of REAL command waits only.

    ``label`` (optional) attributes the payload in BOTH the OCC
    main-thread hold histogram (main_thread_hold_stats, completed holds) and
    the F4 in-flight register (current_main_thread_holder, the live hold).
    ``None`` records as "unlabeled". Attribution only — it changes no dispatch
    behaviour.
    """
    # Fast path 1: reentrant call from within a run_on_main callback
    if getattr(_tls, "on_main", False):
        return fn()

    # Fast path 2: caller is already on the main thread (e.g. Qt slot
    # delivered via AutoConnection). Deferring would deadlock because
    # the main thread is blocked in this function waiting for the
    # deferred callback, which can't fire until this function returns.
    # C6: this is the dominant panel/bridge inline path — time fn() so it is
    # attributed (the dispatch-wait histogram only sees the worker path). Cheap:
    # one perf_counter pair; record on the way out even if fn() raises.
    if threading.current_thread().ident == _MAIN_THREAD_ID:
        _t_direct = time.perf_counter()
        # F4: register the inline hold BEFORE fn() runs. Fast path 2 never
        # reaches _record_main_thread_hold, so without this the in-flight
        # class that froze the UI twice this week was invisible to every
        # instrument. Save/restore so a nested fast-path-2 call (main-thread
        # caller inside a main-thread payload) restores the outer holder.
        global _in_flight
        _prev_in_flight = _in_flight
        _in_flight = (label or "unlabeled", time.time())
        try:
            return fn()
        finally:
            _in_flight = _prev_in_flight
            _elapsed_ms = (time.perf_counter() - _t_direct) * 1000.0
            # C6 first and unconditionally — the histogram's semantics are
            # unchanged and must not depend on the guard being importable.
            _record_main_thread_direct(_elapsed_ms)
            # Starvation telemetry (L8). Fast path 2 is where a migrated
            # marshal now RUNS inline instead of deadlocking — strictly better,
            # but a long inline payload still freezes the GUI for its duration.
            # This is the only place that residual is observable, so record it.
            # NO bounding is applied here: the caller is the main thread, and
            # there is no mechanism by which Python can interrupt it. Any
            # "timeout" on this path would be a lie. Pure observation.
            # Off-main behaviour below is untouched (C4 zombie-kill and the C6
            # dispatch-wait sample keep their exact prior semantics).
            try:
                from .marshal_guard import (
                    note_main_thread_inline_overrun,
                    inline_budget_s,
                )
                _budget_s = inline_budget_s()
                if _elapsed_ms / 1000.0 > _budget_s:
                    note_main_thread_inline_overrun(
                        "main_thread.run_on_main:fast_path_2",
                        _elapsed_ms / 1000.0,
                        _budget_s,
                    )
            except Exception:
                # Telemetry must never break the payload's return or its
                # exception propagation. Swallow deliberately.
                pass

    import hdefereval

    result_holder = [None]
    error_holder = [None]
    done = threading.Event()
    # C4 — zombie kill. On timeout the caller is told the op failed and to retry; if
    # the deferred payload later runs fn() anyway, that mutation is a "zombie" applied
    # after the failure report (and a retry then double-applies). The abandoned flag,
    # checked under a lock before fn() runs, makes _on_main a no-op once the caller has
    # given up. (A payload already inside fn() when the timeout fires is the accepted
    # residual race — the lock only serializes the check-vs-set, not fn() itself.)
    state_lock = threading.Lock()
    abandoned = [False]
    t_enqueue = time.perf_counter()

    def _on_main():
        # C6: every wake is a dispatch-wait sample — including abandoned ones
        # (the queue-sit time is the datum, regardless of whether fn() runs) —
        # unless the caller opted out (record_wait=False: observe-only
        # envelope captures must not pollute the attribution instrument).
        if record_wait:
            _record_dispatch_wait((time.perf_counter() - t_enqueue) * 1000.0)
        with state_lock:
            if abandoned[0]:
                return  # caller already timed out — do not mutate the scene
        _tls.on_main = True
        # F4: register the hold NOW — after the C4 abandoned-check passes and
        # before the payload starts. This is what names a deferred zombie
        # render (the Aug-13 162-177s class) MID-FLIGHT; the hold histogram
        # below only fires once fn() returns, which for a zombie is "never in
        # time". Save/restore for the nested-main-thread case, as in fast
        # path 2. Single-writer-safe: this closure only runs on the main
        # thread via hdefereval.executeDeferred.
        global _in_flight
        _prev_in_flight = _in_flight
        _in_flight = (label or "unlabeled", time.time())
        # OCC — time the payload itself, ON the main thread. This is the hold
        # the freeze investigations previously inferred from proxies.
        # Measurement only: control flow, C4 semantics, and the result path
        # are untouched.
        _t_hold = time.perf_counter()
        try:
            result_holder[0] = fn()
        except Exception as e:
            error_holder[0] = e
        finally:
            # F4: clear the register on exit (restore the previous holder for
            # the nested case) BEFORE recording the completed hold.
            _in_flight = _prev_in_flight
            _hold_ms = (time.perf_counter() - _t_hold) * 1000.0
            _tls.on_main = False
            try:
                # A payload that ran past its caller's timeout (the C4
                # residual race — abandoned flipped while fn() was running)
                # is the most interesting sample: record it marked.
                with state_lock:
                    _was_abandoned = abandoned[0]
                _record_main_thread_hold(_hold_ms, label, _was_abandoned)
            except Exception:
                pass  # telemetry must never break the result path
            done.set()

    # F3: register in the pending-dispatch registry BEFORE enqueueing so the
    # WS-path emergency halt (server/emergency_live.py) can flip this call's
    # C4 abandoned flag from off-main-thread during a sustained freeze.
    token = id(abandoned)
    with _pending_lock:
        _pending_dispatches[token] = (
            state_lock, abandoned, label or "unlabeled", time.time()
        )

    hdefereval.executeDeferred(_on_main)

    try:
        if not done.wait(timeout=timeout):
            with state_lock:
                abandoned[0] = True
            if record_stall:
                _record_timeout(timeout)
            raise RuntimeError(
                "Houdini's main thread didn't respond in time -- "
                "it may be busy cooking or rendering. "
                "Try again in a moment."
            )

        # Success — reset the stall counter
        _record_success()

        if error_holder[0] is not None:
            raise error_holder[0]

        return result_holder[0]
    finally:
        with _pending_lock:
            _pending_dispatches.pop(token, None)
