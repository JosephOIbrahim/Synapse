"""TurnHandle unit tests (Sprint 3 Spike 2.4).

Pins the Future-shaped contract of ``synapse.host.turn_handle.TurnHandle``
that closes the daemon ↔ main-thread deadlock unmasked by Spike 2.3.
The handle is the only thing shared between the daemon thread (sole
writer via ``_set_result`` / ``_set_exception``) and the caller thread
(reader via ``done``, ``cancelled``, ``result``, ``cancel``, ``event``).

These tests exercise the handle in isolation — no daemon, no agent
loop, no Anthropic mock. The daemon-integration tests live in
``test_host_layer.py``.

Hostile cases mandatory:
  - Timeout 0 / negative — must surface immediately, no silent block.
  - Result set before result() called — pre-completion path.
  - Multiple concurrent waiters — stress the threading.Event broadcast.
  - Cancel after complete — terminal state must win.
  - Set result on cancelled handle — cancelled wins.
  - Idempotency on _set_result and _set_exception.
"""

from __future__ import annotations

import threading
import time
from typing import List
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Imports — keep at module scope so failures surface during collection.
# ---------------------------------------------------------------------------


from synapse.host.turn_handle import (
    TurnCancelled,
    TurnHandle,
    TurnNotComplete,
)


# ---------------------------------------------------------------------------
# Module-level pins
# ---------------------------------------------------------------------------


class TestTurnHandleExceptionHierarchy:
    """The exception types are part of the public contract."""

    def test_turn_not_complete_subclasses_timeout_error(self):
        """Q1 lock: TurnNotComplete IS-A TimeoutError so existing
        ``except TimeoutError`` paths still catch it during migration."""
        assert issubclass(TurnNotComplete, TimeoutError)

    def test_turn_cancelled_subclasses_runtime_error(self):
        """TurnCancelled is NOT a TimeoutError — distinct signal so
        callers can route on type."""
        assert issubclass(TurnCancelled, RuntimeError)
        assert not issubclass(TurnCancelled, TimeoutError)

    def test_exceptions_are_distinct_types(self):
        assert TurnNotComplete is not TurnCancelled


# ---------------------------------------------------------------------------
# Lifecycle: pending → terminal state
# ---------------------------------------------------------------------------


class TestTurnHandlePendingState:
    """Fresh handle is pending; terminal predicates are False."""

    def test_handle_starts_pending(self):
        h = TurnHandle()
        assert h.done() is False
        assert h.cancelled() is False

    def test_event_not_set_when_pending(self):
        """The underlying threading.Event drives done(); both must
        agree."""
        h = TurnHandle()
        assert h.event.is_set() is False
        assert h.event.wait(timeout=0) is False

    def test_event_property_returns_threading_event(self):
        """The asyncio-bridge handoff in Spike 3+ relies on this being
        a real ``threading.Event``, not a wrapper."""
        h = TurnHandle()
        assert isinstance(h.event, threading.Event)


# ---------------------------------------------------------------------------
# _set_result happy path
# ---------------------------------------------------------------------------


class TestTurnHandleSetResult:
    """Daemon-side ``_set_result`` makes the handle complete and
    unblocks waiters."""

    def test_set_result_marks_done(self):
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        assert h.done() is True
        assert h.cancelled() is False
        assert h.event.is_set() is True

    def test_result_returns_set_value(self):
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        assert h.result(timeout=0) is sentinel

    def test_result_no_timeout_returns_immediately_when_complete(self):
        """timeout=None on an already-complete handle must NOT block
        forever — Event.wait(None) on a set Event returns instantly."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        # If this is wrong, the test hangs. Bound it with a watchdog.
        start = time.monotonic()
        got = h.result(timeout=None)
        elapsed = time.monotonic() - start
        assert got is sentinel
        assert elapsed < 0.5

    def test_result_set_before_wait_called(self):
        """Pre-completion path: daemon races ahead of the caller.
        Common when test mock clients return immediately."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)  # daemon "wins" before caller waits
        # Caller arrives later — must still see the result.
        assert h.done() is True
        assert h.result(timeout=0.1) is sentinel


# ---------------------------------------------------------------------------
# Timeout / non-completion paths
# ---------------------------------------------------------------------------


class TestTurnHandleTimeout:
    """``result(timeout=...)`` raises ``TurnNotComplete`` on expiry."""

    def test_result_timeout_raises_turn_not_complete(self):
        h = TurnHandle()
        with pytest.raises(TurnNotComplete):
            h.result(timeout=0.1)

    def test_timeout_message_includes_timeout_value(self):
        """Operators rely on the timeout figure in log scraping."""
        h = TurnHandle()
        with pytest.raises(TurnNotComplete, match="0.05"):
            h.result(timeout=0.05)

    def test_handle_remains_valid_after_timeout(self):
        """A timeout does not poison the handle — daemon may still
        post the result later. This is the ergonomic shape that lets
        callers do bounded poll loops on top of result()."""
        h = TurnHandle()
        with pytest.raises(TurnNotComplete):
            h.result(timeout=0.05)
        # Handle still accepts a late result.
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        assert h.done() is True
        assert h.result(timeout=0.1) is sentinel

    def test_zero_timeout_resolves_immediately_when_pending(self):
        """timeout=0 on a pending handle: Event.wait(0) returns False
        instantly, so we should raise immediately — not block."""
        h = TurnHandle()
        start = time.monotonic()
        with pytest.raises(TurnNotComplete):
            h.result(timeout=0)
        elapsed = time.monotonic() - start
        assert elapsed < 0.2  # should be near-instant

    def test_zero_timeout_resolves_immediately_when_complete(self):
        """timeout=0 on a complete handle: must return the value, not
        raise. Event.wait(0) on a set Event returns True."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        assert h.result(timeout=0) is sentinel


# ---------------------------------------------------------------------------
# Cancellation paths
# ---------------------------------------------------------------------------


class TestTurnHandleCancel:
    """``cancel()`` and the ``TurnCancelled`` raise path."""

    def test_cancel_pending_handle_succeeds(self):
        h = TurnHandle()
        assert h.cancel() is True
        assert h.cancelled() is True
        assert h.done() is True  # cancelled IS a terminal state
        assert h.event.is_set() is True

    def test_cancel_then_result_raises_turn_cancelled(self):
        h = TurnHandle()
        h.cancel()
        with pytest.raises(TurnCancelled):
            h.result(timeout=1)

    def test_cancel_after_complete_returns_false(self):
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        assert h.cancel() is False
        # Original result still returned.
        assert h.cancelled() is False
        assert h.result(timeout=0) is sentinel

    def test_cancel_twice_second_returns_false(self):
        """Cancellation is idempotent on the predicate; second
        cancel() returns False because no transition occurred."""
        h = TurnHandle()
        assert h.cancel() is True
        assert h.cancel() is False
        assert h.cancelled() is True

    def test_set_result_on_cancelled_handle_dropped(self):
        """Cancelled state wins. The daemon's late post is logged
        and dropped — no exception, no state corruption."""
        h = TurnHandle()
        h.cancel()
        late = MagicMock(name="LateAgentTurnResult")
        h._set_result(late)  # must not raise
        # Cancelled state preserved.
        assert h.cancelled() is True
        with pytest.raises(TurnCancelled):
            h.result(timeout=0.1)

    def test_set_exception_on_cancelled_handle_dropped(self):
        """Same drop-and-log behavior for the exception path."""
        h = TurnHandle()
        h.cancel()
        h._set_exception(RuntimeError("daemon-internal failure"))
        # Cancelled wins; raising the exception would surface stale
        # daemon-internal state to a caller who already cancelled.
        assert h.cancelled() is True
        with pytest.raises(TurnCancelled):
            h.result(timeout=0.1)


# ---------------------------------------------------------------------------
# Idempotency under multi-write
# ---------------------------------------------------------------------------


class TestTurnHandleIdempotency:
    """Single-writer guarantee: second daemon writes are dropped."""

    def test_set_result_idempotent(self):
        h = TurnHandle()
        first = MagicMock(name="first")
        second = MagicMock(name="second")
        h._set_result(first)
        h._set_result(second)  # must not raise; second dropped
        assert h.result(timeout=0) is first

    def test_set_exception_after_set_result_dropped(self):
        """Late ``_set_exception`` on a completed handle: dropped, not
        raised. The daemon should never reach this in practice (we
        only post one or the other), but the contract is robust to
        the bug if it ever happens."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        h._set_result(sentinel)
        h._set_exception(RuntimeError("late exception"))
        # Original result wins; no exception raised.
        assert h.result(timeout=0) is sentinel

    def test_set_result_after_set_exception_dropped(self):
        """Symmetry: exception-then-result also drops the second post."""
        h = TurnHandle()
        original_exc = RuntimeError("daemon-internal failure")
        h._set_exception(original_exc)
        late = MagicMock(name="LateAgentTurnResult")
        h._set_result(late)  # dropped
        with pytest.raises(RuntimeError, match="daemon-internal"):
            h.result(timeout=0.1)


# ---------------------------------------------------------------------------
# Exception propagation through the handle
# ---------------------------------------------------------------------------


class TestTurnHandleExceptionPropagation:
    """``_set_exception`` re-raises the exception from ``result()``."""

    def test_set_exception_then_result_raises(self):
        h = TurnHandle()
        h._set_exception(ValueError("daemon went sideways"))
        with pytest.raises(ValueError, match="daemon went sideways"):
            h.result(timeout=0.1)

    def test_set_exception_marks_done_but_not_cancelled(self):
        h = TurnHandle()
        h._set_exception(RuntimeError("x"))
        assert h.done() is True
        assert h.cancelled() is False

    def test_set_exception_unblocks_waiters(self):
        """Same Event-set side effect as _set_result."""
        h = TurnHandle()
        h._set_exception(RuntimeError("x"))
        assert h.event.is_set() is True

    def test_base_exception_propagates_too(self):
        """SystemExit, KeyboardInterrupt — anything ``_set_exception``
        accepts must come back out of ``result()``."""
        h = TurnHandle()
        h._set_exception(KeyboardInterrupt())
        with pytest.raises(KeyboardInterrupt):
            h.result(timeout=0.1)


# ---------------------------------------------------------------------------
# Concurrency stress
# ---------------------------------------------------------------------------


class TestTurnHandleConcurrency:
    """The handle is shared between the daemon thread and one or more
    callers. These tests stress the happy path with multiple readers
    and a single writer."""

    def test_concurrent_waiters_all_unblock(self):
        """5 threads call result(); 1 thread calls _set_result. All
        5 waiters return the same value with no deadlock."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        results: List[object] = []
        results_lock = threading.Lock()
        ready = threading.Event()
        all_started = threading.Barrier(5)

        def _waiter():
            all_started.wait(timeout=2)
            ready.wait(timeout=0.05)  # gentle stagger
            try:
                got = h.result(timeout=3)
                with results_lock:
                    results.append(got)
            except BaseException as exc:  # noqa: BLE001
                with results_lock:
                    results.append(exc)

        threads = [
            threading.Thread(target=_waiter, name=f"waiter-{i}", daemon=True)
            for i in range(5)
        ]
        for t in threads:
            t.start()
        # Ensure all waiters have entered the barrier before the writer fires.
        ready.set()
        time.sleep(0.05)
        h._set_result(sentinel)
        for t in threads:
            t.join(timeout=3)
            assert not t.is_alive(), f"{t.name} did not unblock"

        assert len(results) == 5
        for got in results:
            assert got is sentinel, f"unexpected result: {got!r}"

    def test_concurrent_waiters_all_observe_cancel(self):
        """5 threads call result(); 1 thread calls cancel(). All
        5 waiters raise TurnCancelled."""
        h = TurnHandle()
        seen: List[BaseException] = []
        seen_lock = threading.Lock()
        all_started = threading.Barrier(5)

        def _waiter():
            all_started.wait(timeout=2)
            try:
                h.result(timeout=3)
            except BaseException as exc:  # noqa: BLE001
                with seen_lock:
                    seen.append(exc)

        threads = [
            threading.Thread(target=_waiter, name=f"cancel-waiter-{i}", daemon=True)
            for i in range(5)
        ]
        for t in threads:
            t.start()
        time.sleep(0.05)
        h.cancel()
        for t in threads:
            t.join(timeout=3)
            assert not t.is_alive()

        assert len(seen) == 5
        assert all(isinstance(exc, TurnCancelled) for exc in seen)

    def test_done_polling_under_concurrency(self):
        """Caller polls ``done()`` from a tight loop while a writer
        thread fires ``_set_result`` once. No race on the underlying
        Event; the poller exits cleanly when it observes done=True
        and its final recorded value is True."""
        h = TurnHandle()
        sentinel = MagicMock(name="AgentTurnResult")
        observed: List[bool] = []

        def _poller():
            # Spin until done() flips to True. Bounded by the writer's
            # 2s join timeout via test timeout — if the writer doesn't
            # fire, the poller spins until the test runner kills it.
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                value = h.done()
                observed.append(value)
                if value:
                    return

        def _writer():
            time.sleep(0.02)  # let the poller spin first
            h._set_result(sentinel)

        t_poll = threading.Thread(target=_poller, daemon=True)
        t_write = threading.Thread(target=_writer, daemon=True)
        t_poll.start()
        t_write.start()
        t_write.join(timeout=2)
        t_poll.join(timeout=2)

        assert not t_poll.is_alive(), "poller did not exit after _set_result"
        assert observed, "poller never recorded a value"
        # The poller exits only when it observes True; the final
        # recorded value MUST be True.
        assert observed[-1] is True
        # Sanity: there should be at least a handful of False values
        # before the True (the 0.02s sleep gives the poller time to
        # spin). This pins that done() really is being polled, not
        # just read once.
        assert any(v is False for v in observed[:-1])

    def test_event_property_unblocks_after_set_result(self):
        """Direct ``event.wait()`` is the asyncio-bridge entry point
        for Spike 3+. Confirm it fires on _set_result."""
        h = TurnHandle()
        # Pre-completion: wait(0) is False.
        assert h.event.wait(timeout=0) is False

        def _writer():
            time.sleep(0.05)
            h._set_result(MagicMock(name="AgentTurnResult"))

        threading.Thread(target=_writer, daemon=True).start()
        # event.wait blocks; on _set_result it returns True.
        assert h.event.wait(timeout=2) is True
        assert h.done() is True
