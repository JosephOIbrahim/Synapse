"""Main-thread executor for Houdini (Sprint 3 Spike 1).

Implements the ``main_thread_executor`` callable contract consumed by
``synapse.cognitive.dispatcher.Dispatcher``. Wraps
``hdefereval.executeInMainThreadWithResult`` with a hard timeout so a
stuck tool can't wedge the agent loop indefinitely.

Spike 2 lock: the timeout default is 30 seconds. Change in lockstep
with the Crucible's deadlock-prevention budget — not in isolation.

Design notes
------------
- ``hdefereval.executeInMainThreadWithResult`` is blocking. To impose a
  timeout from the caller, we dispatch from a worker thread and wait on
  an Event. On timeout, the caller regains control; the main-thread
  payload keeps executing (Python can't safely kill a thread
  mid-operation). Spike 2 pairs this with ``threading.Event('cancel_
  requested')`` inside tool bodies so cooperative cancellation actually
  lands.
- Testing path: use ``synapse.cognitive.dispatcher.Dispatcher(
  is_testing=True)``. This module has no test-mode — it exists to
  touch ``hou`` and ``hdefereval``.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

try:
    import hdefereval  # type: ignore[import-not-found]
    _HDEFEREVAL_AVAILABLE = True
except ImportError:
    hdefereval = None  # type: ignore[assignment]
    _HDEFEREVAL_AVAILABLE = False


DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS: float = 30.0
"""Spike 2 lock. Change in coordination with Crucible deadlock budget."""


class MainThreadTimeoutError(TimeoutError):
    """Main-thread dispatch exceeded the timeout budget.

    Subclass of the stdlib ``TimeoutError`` so callers can catch either
    the specific class or the broader category. Raised from
    ``main_thread_exec``; caught at the Dispatcher's exception boundary
    and wrapped as ``AgentToolError(error_type="MainThreadTimeoutError")``
    so the LLM sees timeouts as structured tool data.
    """


def main_thread_exec(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Marshal ``fn(**kwargs)`` onto Houdini's main thread with a timeout.

    Args:
        fn: Callable returning a JSON-serializable dict.
        kwargs: Keyword arguments passed to ``fn``.
        timeout: Hard timeout in seconds. ``None`` uses
            ``DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS``.

    Returns:
        Whatever ``fn`` returned (expected ``Dict[str, Any]``, but this
        module does not type-check the return — the Dispatcher does).

    Raises:
        MainThreadTimeoutError: main-thread dispatch took longer than
            ``timeout`` seconds.
        RuntimeError: running outside Houdini (``hdefereval`` unavailable).
            Use ``Dispatcher(is_testing=True)`` for tests / CI.
        BaseException: any exception raised by ``fn`` propagates through
            unchanged. The Dispatcher catches it at its own exception
            boundary.
    """
    if not _HDEFEREVAL_AVAILABLE:
        raise RuntimeError(
            "main_thread_exec requires hdefereval, which is only available "
            "inside a Houdini process. For tests and CI, construct the "
            "Dispatcher with is_testing=True."
        )

    effective_timeout: float = (
        timeout if timeout is not None else DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS
    )

    # Thread-local result handoff. list is used as a mutable cell;
    # populated by exactly one of the two slots below.
    result_holder: list[Any] = []
    error_holder: list[BaseException] = []
    done = threading.Event()

    def _dispatch_on_main() -> None:
        """Run on the worker thread — blocks on hdefereval until main runs fn."""
        try:
            result = hdefereval.executeInMainThreadWithResult(
                lambda: fn(**kwargs)
            )
            result_holder.append(result)
        except BaseException as exc:  # noqa: BLE001 - propagate faithfully
            error_holder.append(exc)
        finally:
            done.set()

    worker = threading.Thread(
        target=_dispatch_on_main,
        name="synapse.host.main_thread_exec",
        daemon=True,
    )
    worker.start()

    if not done.wait(timeout=effective_timeout):
        # Work is still queued / executing on main thread. We cannot
        # safely kill it — Python threads don't support forced
        # termination. Control returns to the caller; the payload will
        # still complete (or hang Houdini) on its own timeline.
        raise MainThreadTimeoutError(
            f"Main-thread dispatch of {getattr(fn, '__name__', repr(fn))!r} "
            f"exceeded {effective_timeout:g}s timeout. The dispatched "
            f"callable may still be running on Houdini's main thread."
        )

    if error_holder:
        raise error_holder[0]
    # Exactly one of result/error is populated if done is set.
    return result_holder[0]
