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


def run_on_main(fn, timeout=_DEFAULT_TIMEOUT):
    """Run *fn* on Houdini's main thread with a timeout.

    Returns the result of fn(). Raises RuntimeError if the timeout
    expires (Houdini main thread is busy). Re-raises any exception
    that fn() raised.

    Reentrant-safe: if called from within a run_on_main callback
    (already on the main thread), fn() is invoked directly.
    """
    # Fast path: already on the main thread (nested call from batch, etc.)
    if getattr(_tls, "on_main", False):
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
        raise RuntimeError(
            "Houdini's main thread didn't respond in time -- "
            "it may be busy cooking or rendering. "
            "Try again in a moment."
        )

    if error_holder[0] is not None:
        raise error_holder[0]

    return result_holder[0]
