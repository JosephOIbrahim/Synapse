"""TurnHandle — Future-shaped return for ``SynapseDaemon.submit_turn``.

Sprint 3 Spike 2.4 closes the daemon ↔ main-thread deadlock by moving
the caller's wait off the synchronous ``queue.get()`` path. The daemon
posts the result onto the handle when the agent loop completes; the
caller chooses their own waiting strategy (poll ``done()``, wait on the
underlying ``threading.Event``, or block in ``result(timeout=...)`` from
a non-main thread).

Why this lives in ``synapse.host.*``
------------------------------------
The handle's lifecycle is bound to the daemon thread (the only writer)
and the caller's thread (the only reader). Both are host-layer
concerns. ``synapse.cognitive.*`` stays host-agnostic and never sees
this type — the cognitive boundary lint (no ``import hou`` under
``synapse/cognitive/**``) is preserved by construction.

Why ``threading.Event`` and not ``asyncio.Future``
--------------------------------------------------
No new dependencies and no asyncio leak into the cognitive layer. The
``event`` property exposes a plain ``threading.Event``; asyncio
bridging at Spike 3+ uses
``asyncio.get_running_loop().run_in_executor(None, handle.event.wait)``
or similar — that's the caller's problem, not the daemon's.

Cancellation semantics
----------------------
``daemon.cancel()`` and ``handle.cancel()`` are intentionally distinct.
``daemon.cancel()`` stops the daemon thread (all in-flight handles
cascade to ``STATUS_CANCELLED`` via the agent loop's cooperative cancel
checks). ``handle.cancel()`` is local to one waiter — it surfaces
``TurnCancelled`` to anyone calling ``result()`` on that handle but
does NOT signal the daemon to stop processing the request. The daemon
finishes the request and quietly drops the result on the cancelled
handle (logged at debug, no error).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.cognitive.agent_loop import AgentTurnResult

logger = logging.getLogger(__name__)


class TurnNotComplete(TimeoutError):
    """Raised by ``TurnHandle.result(timeout=…)`` when the timeout
    elapses without the daemon posting a result.

    The turn may still be running on the daemon thread; the handle
    remains valid and a subsequent ``result()`` call may complete
    normally.

    Subclasses :class:`TimeoutError` so existing
    ``except TimeoutError`` paths still catch it — the migration to
    the new shape is opt-in stricter typing, not a hard break.
    """


class TurnCancelled(RuntimeError):
    """Raised by ``TurnHandle.result(...)`` when the handle was
    cancelled before the daemon posted a result.

    Two cancellation paths converge here:

    - The caller invoked ``handle.cancel()`` directly.
    - ``daemon.stop()`` drained the request queue and the request
      had not yet been picked up by the daemon thread (see
      ``SynapseDaemon._drain_request_queue``).
    """


class TurnHandle:
    """Future-shaped result envelope for one ``submit_turn`` call.

    Thread-safe: multiple threads can call ``done()`` / ``result()`` /
    ``cancel()`` concurrently. The daemon thread is the sole writer
    (via the private ``_set_result`` / ``_set_exception`` methods);
    callers are readers.

    Lifecycle:
        pending    — created by submit_turn, daemon hasn't touched yet
        complete   — _set_result called, .result() returns the value
        failed     — _set_exception called, .result() re-raises the exc
        cancelled  — .cancel() called or daemon drained the request
    """

    __slots__ = (
        "_event",
        "_lock",
        "_result",
        "_exception",
        "_cancelled",
        "_completed",
    )

    def __init__(self) -> None:
        self._event = threading.Event()
        # _lock guards the transition from pending → terminal state.
        # The terminal-state fields below are written exactly once
        # (subsequent writes are logged + dropped) and are only read
        # after _event.is_set(), which acts as the happens-before
        # boundary for the writes.
        self._lock = threading.Lock()
        self._result: Optional["AgentTurnResult"] = None
        self._exception: Optional[BaseException] = None
        self._cancelled: bool = False
        self._completed: bool = False

    # -- Public read surface --------------------------------------------

    def done(self) -> bool:
        """True if the turn has completed, failed, or been cancelled.

        Cheap to call in a tight poll loop — reads a single
        ``threading.Event`` flag, no lock acquisition.
        """
        return self._event.is_set()

    def cancelled(self) -> bool:
        """True if the handle was cancelled before completion.

        Distinct from ``done()`` — a handle that completed normally
        returns ``done() == True`` and ``cancelled() == False``.
        """
        return self._cancelled

    def result(
        self,
        timeout: Optional[float] = None,
    ) -> "AgentTurnResult":
        """Block until the turn completes or ``timeout`` elapses.

        ``timeout=None`` waits indefinitely. **Never call with
        ``timeout=None`` from the Houdini main thread in GUI mode** —
        that re-introduces the Spike 2.4 deadlock. Use ``done()``
        polling or daemon-side completion callback instead.

        Args:
            timeout: Maximum seconds to wait. ``None`` means wait
                forever. Pass a finite value from tests so stuck
                tests surface loudly.

        Returns:
            The ``AgentTurnResult`` posted by the daemon.

        Raises:
            TurnNotComplete: ``timeout`` elapsed without a result. The
                handle remains valid; the daemon may still post later.
            TurnCancelled: handle was cancelled before completion (via
                ``handle.cancel()`` or daemon queue drain).
            BaseException: whatever the daemon thread captured via
                ``_set_exception`` (rare; ``_process_request`` wraps
                most failures into an ``AgentTurnResult`` with status
                ``STATUS_API_ERROR`` and posts via ``_set_result``).
        """
        signaled = self._event.wait(timeout=timeout)
        if not signaled:
            raise TurnNotComplete(
                f"TurnHandle.result did not complete within {timeout}s"
            )
        if self._cancelled:
            raise TurnCancelled(
                "TurnHandle was cancelled before the daemon posted a result"
            )
        if self._exception is not None:
            raise self._exception
        # _completed implies _result is not None (set together under lock).
        assert self._result is not None
        return self._result

    def cancel(self) -> bool:
        """Cancel the handle. Returns True if cancellation took effect,
        False if the turn already completed or was already cancelled.

        Does NOT cancel the agent loop itself — for that, call
        ``daemon.cancel()``. This only affects waiters on this one
        handle: any thread parked in ``result(...)`` unblocks with
        ``TurnCancelled``. The daemon thread continues processing the
        request to completion (if it had picked it up); when it tries
        to post the result on this handle, the post is dropped with a
        debug log.
        """
        with self._lock:
            if self._completed or self._cancelled:
                return False
            self._cancelled = True
            self._event.set()
        return True

    @property
    def event(self) -> threading.Event:
        """The underlying completion ``threading.Event``.

        Exposed for callers that want to wait on multiple handles via
        composition (or asyncio bridging in Spike 3+ when perception
        events arrive). The Event is set when the handle transitions
        to any terminal state (complete, failed, cancelled) — callers
        still need to inspect ``cancelled()`` / call ``result()`` to
        determine which.
        """
        return self._event

    # -- Daemon-side (private) ------------------------------------------

    def _set_result(self, result: "AgentTurnResult") -> None:
        """Daemon posts the agent-turn result.

        Idempotent: a second call is logged at debug and dropped.
        Posting a result on a cancelled handle is also a debug log +
        drop — the cancelled state wins.

        Public on the type but underscore-prefixed: callers must not
        invoke. The daemon's ``_process_request`` is the sole writer.
        """
        with self._lock:
            if self._completed:
                logger.debug(
                    "TurnHandle._set_result called twice — dropping second result"
                )
                return
            if self._cancelled:
                logger.debug(
                    "TurnHandle._set_result called on cancelled handle — "
                    "dropping result"
                )
                return
            self._result = result
            self._completed = True
            self._event.set()

    def _set_exception(self, exc: BaseException) -> None:
        """Daemon posts an unexpected exception that escaped run_turn.

        Rare — the agent loop catches API errors itself and surfaces
        them as ``AgentTurnResult(status=STATUS_API_ERROR)``. This
        path is reserved for daemon-internal failures that don't fit
        the ``AgentTurnResult`` shape.

        Same idempotency rules as ``_set_result``.
        """
        with self._lock:
            if self._completed:
                logger.debug(
                    "TurnHandle._set_exception called after completion — "
                    "dropping second post"
                )
                return
            if self._cancelled:
                logger.debug(
                    "TurnHandle._set_exception called on cancelled handle — "
                    "dropping exception"
                )
                return
            self._exception = exc
            self._completed = True
            self._event.set()
