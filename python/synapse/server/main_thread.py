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
        run_on_main(lambda: True, timeout=timeout)
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


def run_on_main(fn, timeout=_DEFAULT_TIMEOUT, record_stall=True, record_wait=True):
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
        try:
            return fn()
        finally:
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
        try:
            result_holder[0] = fn()
        except Exception as e:
            error_holder[0] = e
        finally:
            _tls.on_main = False
            done.set()

    hdefereval.executeDeferred(_on_main)

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
