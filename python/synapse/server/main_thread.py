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
_STALL_THRESHOLD = 2


def is_main_thread_stalled():
    """Return True if recent run_on_main calls have been timing out.

    Used by the WebSocket handler to fast-fail incoming commands instead
    of queueing them behind a blocked main thread (which causes the
    connection accumulation cascade).
    """
    with _stall_lock:
        return _consecutive_timeouts >= _STALL_THRESHOLD


def _record_timeout(timeout):
    global _consecutive_timeouts
    with _stall_lock:
        _consecutive_timeouts += 1
        count = _consecutive_timeouts
    logger.warning("Main thread timeout (%d consecutive, %.0fs limit)", count, timeout)


def _record_success():
    global _consecutive_timeouts
    with _stall_lock:
        _consecutive_timeouts = 0


def run_on_main(fn, timeout=_DEFAULT_TIMEOUT):
    """Run *fn* on Houdini's main thread with a timeout.

    Returns the result of fn(). Raises RuntimeError if the timeout
    expires (Houdini main thread is busy). Re-raises any exception
    that fn() raised.

    Reentrant-safe: if called from within a run_on_main callback
    (already on the main thread), fn() is invoked directly.
    Also detects when the caller is already on the main thread
    (e.g. via a Qt slot) and calls fn() directly to avoid deadlock.
    """
    # Fast path 1: reentrant call from within a run_on_main callback
    if getattr(_tls, "on_main", False):
        return fn()

    # Fast path 2: caller is already on the main thread (e.g. Qt slot
    # delivered via AutoConnection). Deferring would deadlock because
    # the main thread is blocked in this function waiting for the
    # deferred callback, which can't fire until this function returns.
    if threading.current_thread().ident == _MAIN_THREAD_ID:
        return fn()

    import hdefereval

    result_holder = [None]
    error_holder = [None]
    done = threading.Event()

    def _on_main():
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
