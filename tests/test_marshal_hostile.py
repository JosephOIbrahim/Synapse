"""Adversarial suite for the marshal boundary (Definition-of-Done D6).

WHAT THIS PINS
--------------
The sprint migrated nine raw ``hdefereval.executeInMainThreadWithResult`` call
sites onto ``synapse.server.main_thread.run_on_main`` (and rebuilt
``synapse.host.main_thread_executor._exec_gui`` in the same shape). The vendor
primitive has two independent defects, both transcribed faithfully into
``_FakeHdefereval`` below:

1. ``_queueDeferred(..., block=True)`` parks in ``_condition.wait()`` with NO
   timeout and NO thread check (H22.0.368
   ``houdini/python3.13libs/hdefereval.py:93``). The only notifier is
   ``_processDeferred``, which runs on the MAIN thread. A main-thread caller
   therefore waits forever for itself: permanent self-deadlock.
2. It reads its result back out of the MODULE GLOBAL ``_last_result``, so two
   concurrent blocking marshals anywhere in the process can hand each other's
   results to the wrong caller — silent corruption, not a hang.

Every test here has a matching NEGATIVE CONTROL that drives the *old* primitive
through the identical topology and asserts the defect reproduces. A guard that
cannot go red is worse than no guard, and this file refuses to ship one.

The unbounded park was confirmed out-of-band before this file was written: a
scratch transcription of the vendor code called from the main thread never
returned and was killed by an 8 s external timeout (exit 124), while the same
topology through ``run_on_main`` returned in 0.41 ms without ever touching the
deferred queue. ``_FakeHdefereval`` bounds that park at ``block_timeout`` and
raises :class:`_FakeVendorDeadlock` instead, so a REGRESSION surfaces as a
failing assertion rather than a hung suite.

HERMETICITY (the fake-residency trap)
-------------------------------------
~46 test modules plant ``sys.modules['hou']`` fakes at MODULE level and the
alphabetically-first planter wins for the whole run
(``tests/conftest.py`` FAKE_HOU_RESIDENCY_GUARD). This file plants NOTHING at
module level. Everything is installed per-test through ``monkeypatch``:

* ``hou`` — the canonical conftest fake is reused; only ``isUIAvailable`` is
  attached per test (``monkeypatch.setattr(..., raising=False)``), which is the
  tri-state seam ``main_thread_executor.detect_runtime_mode()`` reads.
* ``hdefereval`` — ``run_on_main`` imports it LAZILY inside the function, so it
  must be visible in ``sys.modules``; installed via ``monkeypatch.setitem`` and
  restored automatically (works whether or not another module already planted
  one).
* ``main_thread_executor`` binds ``hdefereval`` as a module GLOBAL at import, so
  that one is patched as a module attribute, never through ``sys.modules``.

Zero real Houdini. Zero Qt. Runs identically isolated and in the full suite.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import pytest

from synapse.host import main_thread_executor as mte
from synapse.server import main_thread as mt
from synapse.server import marshal_guard as mg


# ---------------------------------------------------------------------------
# Vendor-shaped fake
# ---------------------------------------------------------------------------

class _FakeVendorDeadlock(RuntimeError):
    """Stands in for the vendor's UNBOUNDED park.

    The real ``_condition.wait()`` at hdefereval.py:93 has no timeout and never
    returns for a main-thread caller. Modelling that literally would hang the
    suite on a regression, so the fake bounds the park and raises this instead.
    Seeing it means "the caller reached the blocking primitive and nothing could
    ever wake it" — i.e. the deadlock.
    """


class _FakeHdefereval:
    """Transcription of the vendor dispatch surface, defects included.

    ``executeDeferred``                — the NON-blocking post ``run_on_main``
                                         and ``_exec_gui`` use. Safe.
    ``executeInMainThreadWithResult``  — the banned blocking primitive, with
                                         both defects intact (bounded park +
                                         ``last_result`` module global).
    ``pump_once``                      — the vendor's ``_processDeferred``, the
                                         only notifier of the condition.
    """

    def __init__(self, block_timeout: float = 0.5):
        self._cv = threading.Condition()
        self._queue: deque = deque()
        self.block_timeout = block_timeout
        # THE SECOND DEFECT: one shared result cell for the whole process.
        self.last_result = None
        self.deferred_posts = 0
        self.blocking_calls = 0
        self.pump_errors: list = []
        self._stop = threading.Event()
        self._pump_thread = None

    # -- vendor API ---------------------------------------------------------

    # NOTE: neither enqueue path notifies the condition. That is faithful to the
    # vendor — `_queueDeferred` only appends; `_processDeferred` is the SOLE
    # notifier, and it runs on the main thread. Notifying on append would let a
    # parked caller wake before its work ran and read a stale `last_result`,
    # which is a *different* bug from the one under test.

    def executeDeferred(self, cb):
        with self._cv:
            self.deferred_posts += 1
            self._queue.append(cb)

    def executeInMainThreadWithResult(self, cb, *args, **kwargs):
        with self._cv:
            self.blocking_calls += 1
            self._queue.append(lambda: cb(*args, **kwargs))
            if not self._cv.wait(timeout=self.block_timeout):
                raise _FakeVendorDeadlock(
                    "parked in _condition.wait() with no notifier — the vendor "
                    "wait is unbounded; this fake bounds it so the suite can "
                    "observe the deadlock instead of joining it"
                )
        return self.last_result   # <-- reads the shared global, not a per-call cell

    def pump_once(self) -> int:
        """The vendor's _processDeferred: drain the queue, notify waiters."""
        with self._cv:
            items = list(self._queue)
            self._queue.clear()
        for cb in items:
            try:
                self.last_result = cb()
            except BaseException as exc:   # noqa: BLE001 — mirror vendor swallow
                self.pump_errors.append(exc)
        with self._cv:
            self._cv.notify_all()
        return len(items)

    def queued(self) -> int:
        with self._cv:
            return len(self._queue)

    # -- test control -------------------------------------------------------

    def start_pump(self):
        """Run the event loop on a background thread (Houdini's main thread)."""
        def _loop():
            while not self._stop.is_set():
                if self.pump_once() == 0:
                    time.sleep(0.005)
        self._pump_thread = threading.Thread(
            target=_loop, name="fake-houdini-eventloop", daemon=True)
        self._pump_thread.start()
        return self._pump_thread

    def stop_pump(self):
        self._stop.set()
        if self._pump_thread is not None:
            self._pump_thread.join(timeout=2.0)
            self._pump_thread = None
        # Release anything still parked in the bounded wait.
        with self._cv:
            self._cv.notify_all()


def _poll(predicate, timeout=3.0, interval=0.005):
    """Spin until predicate() is true or timeout elapses; return its final value.

    Anchors on real state instead of a fixed sleep, so a contended runner
    cannot slide the observation outside the intended window (same idiom as
    tests/test_freeze_chain.py:_poll).
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def _call_off_main(fn, join=8.0, name="synapse-ws-worker"):
    """Run fn() on a worker thread (the live WS topology) and report outcome.

    Returns ``{"value": ...}`` or ``{"error": exc}`` plus ``{"thread": t}``.
    Never re-raises — hostile tests assert ON the exception object.
    """
    box: dict = {}

    def _run():
        try:
            box["value"] = fn()
        except BaseException as exc:   # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=_run, name=name, daemon=True)
    t.start()
    t.join(timeout=join)
    box["thread"] = t
    return box


def _assert_marshal_timeout(box, what="caller"):
    """The caller must fail with run_on_main's OWN bounded timeout.

    Deliberately narrower than ``isinstance(err, RuntimeError)``: a caller that
    reached the vendor's park would also raise a RuntimeError subclass
    (``_FakeVendorDeadlock``), and accepting that would let the exact regression
    this file exists to catch slip through as green.
    """
    err = box.get("error")
    assert err is not None, f"{what} should have failed, got {box!r}"
    assert not isinstance(err, _FakeVendorDeadlock), (
        f"{what} reached the BANNED blocking primitive instead of run_on_main's "
        f"bounded wait: {err!r}")
    assert isinstance(err, RuntimeError), f"{what} raised {err!r}"
    assert "main thread didn't respond" in str(err), (
        f"{what} must fail with the marshal timeout, not {err!r}")
    return err


# ---------------------------------------------------------------------------
# Fixtures — everything per-test, nothing at module level
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_marshal_state(monkeypatch, tmp_path):
    """Reset every module-global the marshal boundary owns, before and after.

    ``main_thread`` keeps a stall counter and two histograms; ``marshal_guard``
    keeps a ledger, counters and a dump throttle. Both are process-global by
    design, so a hostile test that trips them would otherwise leak into its
    neighbours (and into the doctor's readings) in a full-suite run.

    ``SYNAPSE_LOG_DIR`` is redirected so stack dumps land in tmp_path and never
    evict real freeze evidence from ~/.synapse/logs (same reason as
    tests/test_freeze_chain.py::_redirect_freeze_dumps).
    """
    monkeypatch.setenv("SYNAPSE_LOG_DIR", str(tmp_path))
    monkeypatch.setenv(mg.GUARD_ENV_VAR, mg.MODE_WARN)
    mt._record_success()
    mt.reset_dispatch_wait_stats()
    mt.reset_main_thread_direct_stats()
    mg.reset_guard_state()
    yield
    mt._record_success()
    mt.reset_dispatch_wait_stats()
    mt.reset_main_thread_direct_stats()
    mg.reset_guard_state()


@pytest.fixture
def vendor(monkeypatch):
    """Install the vendor-shaped fake at BOTH marshal sites, then tear down.

    ``run_on_main`` does ``import hdefereval`` lazily inside the function →
    sys.modules (monkeypatch.setitem restores the previous resident, including
    a fake planted at module level by another test file).
    ``main_thread_executor`` bound it as a module global at import → setattr.
    """
    fake = _FakeHdefereval()
    monkeypatch.setitem(__import__("sys").modules, "hdefereval", fake)
    monkeypatch.setattr(mte, "hdefereval", fake, raising=False)
    monkeypatch.setattr(mte, "_HDEFEREVAL_AVAILABLE", True, raising=False)
    yield fake
    fake.stop_pump()


@pytest.fixture
def gui_mode(monkeypatch, vendor):
    """Drive the tri-state seam into GUI mode without a real Houdini.

    ``detect_runtime_mode()`` imports ``hou`` and calls ``hou.isUIAvailable()``.
    The conftest canonical fake has no such attribute, so it is attached here
    per test (raising=False; monkeypatch deletes it again afterwards). The
    canonical resident object is never replaced — the residency guard stays
    satisfied.
    """
    import hou  # the conftest canonical fake in stock python
    monkeypatch.setattr(hou, "isUIAvailable", lambda: True, raising=False)
    return vendor


# ===========================================================================
# 1. MAIN-THREAD CALLER DOES NOT DEADLOCK
# ===========================================================================

class TestMainThreadCallerDoesNotDeadlock:
    """The core fix: a marshal issued FROM the main thread must complete.

    pytest's thread IS the process main thread, which is exactly the topology
    that kills the vendor primitive (a Qt slot, a panel inline call, a
    /mcp bridge op). ``run_on_main`` fast path 2 (main_thread.py:240)
    short-circuits to a direct ``fn()`` and never reaches the queue.
    """

    def test_negative_control_old_primitive_self_deadlocks(self, vendor):
        """PROOF THE TEST CAN FAIL: the banned primitive, same topology.

        No pump is running — and none CAN run, because the pump is the main
        thread and the main thread is the caller. That is the whole defect.
        The fake bounds the park; the real one never returns (verified
        out-of-band: killed at 8 s, exit 124).
        """
        assert threading.current_thread() is threading.main_thread()
        with pytest.raises(_FakeVendorDeadlock):
            vendor.executeInMainThreadWithResult(lambda: "payload-ran")
        assert vendor.blocking_calls == 1
        assert vendor.queued() == 1, "work was enqueued for a thread that is parked"

    def test_run_on_main_from_main_thread_completes_inline(self, vendor):
        """The fix. Completes, returns the real value, never enqueues."""
        assert threading.current_thread() is threading.main_thread()
        t0 = time.perf_counter()
        result = mt.run_on_main(lambda: "payload-ran", timeout=5.0)
        elapsed = time.perf_counter() - t0

        assert result == "payload-ran"
        assert elapsed < 1.0, "fast path 2 must be a direct call, not a wait"
        assert vendor.blocking_calls == 0, "the banned primitive was reached"
        assert vendor.deferred_posts == 0, "main-thread caller must not enqueue"
        assert vendor.queued() == 0

    def test_run_on_main_from_main_thread_propagates_exceptions(self, vendor):
        """Inline execution must not swallow or wrap the payload's exception."""
        def _boom():
            raise ValueError("node not found at /obj/missing")

        with pytest.raises(ValueError, match="/obj/missing"):
            mt.run_on_main(_boom, timeout=5.0)
        assert vendor.deferred_posts == 0

    def test_executor_gui_mode_main_thread_caller_runs_inline(self, gui_mode):
        """Same invariant at the SECOND marshal site (the tri-state seam).

        GUI mode + main-thread caller → _exec_gui's fast path
        (main_thread_executor.py:215) calls fn(**kwargs) directly.
        """
        assert mte.detect_runtime_mode() == mte.RUNTIME_GUI
        out = mte.main_thread_exec(lambda **kw: {"ok": True, **kw},
                                   {"node": "/obj/geo1"}, timeout=5.0)
        assert out == {"ok": True, "node": "/obj/geo1"}
        assert gui_mode.blocking_calls == 0
        assert gui_mode.deferred_posts == 0

    def test_executor_headless_mode_runs_direct(self, monkeypatch, vendor):
        """Headless hython has no event loop — the seam must NOT marshal."""
        import hou
        monkeypatch.setattr(hou, "isUIAvailable", lambda: False, raising=False)
        assert mte.detect_runtime_mode() == mte.RUNTIME_HEADLESS
        assert mte.main_thread_exec(lambda **kw: {"n": kw["n"]}, {"n": 7}) == {"n": 7}
        assert vendor.deferred_posts == 0
        assert vendor.blocking_calls == 0

    def test_executor_stock_python_refuses_rather_than_guessing(self, monkeypatch, vendor):
        """No hou at all → typed refusal pointing at Dispatcher(is_testing=True).

        Deletes the conftest canonical resident for the duration of ONE test;
        monkeypatch restores it, so the residency guard (which runs at
        collection_finish) never sees the gap.
        """
        import sys
        monkeypatch.delitem(sys.modules, "hou", raising=False)
        assert mte.detect_runtime_mode() == mte.RUNTIME_STOCK
        with pytest.raises(RuntimeError, match="is_testing=True"):
            mte.main_thread_exec(lambda **kw: {}, {})


# ===========================================================================
# 2. CONCURRENT TURNS — results must not be swapped between callers
# ===========================================================================

class TestConcurrentTurnsDoNotSwapResults:
    """The reason the migration matters beyond hangs.

    The vendor reads its result from ``_last_result`` — one cell for the whole
    process. Two concurrent blocking marshals therefore race, and the loser
    silently receives the other caller's data. ``run_on_main`` gives every call
    its own ``result_holder`` closure cell (main_thread.py:277).
    """

    def test_negative_control_old_primitive_swaps_results(self, vendor):
        """PROOF THE TEST CAN FAIL: two blocking marshals, one result cell."""
        results: dict = {}

        def _caller(tag):
            try:
                results[tag] = vendor.executeInMainThreadWithResult(lambda: tag)
            except _FakeVendorDeadlock as exc:
                results[tag] = exc

        threads = [threading.Thread(target=_caller, args=(t,), daemon=True)
                   for t in ("turn-A", "turn-B")]
        for t in threads:
            t.start()
        # Both must be parked before the event loop drains, which is exactly
        # the interleaving that happens under real concurrent WS traffic.
        assert _poll(lambda: vendor.queued() == 2), "both marshals must enqueue"
        vendor.pump_once()
        for t in threads:
            t.join(timeout=5.0)

        assert set(results) == {"turn-A", "turn-B"}
        got = list(results.values())
        assert got[0] == got[1], (
            "expected the module-global defect to hand both callers the SAME "
            f"result; got {results!r}"
        )
        assert sum(1 for tag, val in results.items() if val != tag) == 1, (
            f"exactly one caller must have received the wrong turn's data: {results!r}"
        )

    def test_run_on_main_keeps_each_caller_its_own_result(self, vendor):
        """The fix, under the same concurrency: N callers, N correct results."""
        vendor.start_pump()
        n = 12
        results: dict = {}
        errors: list = []
        ready = threading.Barrier(n)

        def _caller(i):
            try:
                ready.wait(timeout=5.0)
                results[i] = mt.run_on_main(lambda: f"turn-{i}", timeout=8.0)
            except BaseException as exc:   # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=_caller, args=(i,), name=f"ws-{i}",
                                    daemon=True) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        assert not errors, f"no caller may fail: {errors!r}"
        assert results == {i: f"turn-{i}" for i in range(n)}, (
            f"result swapped between concurrent callers: {results!r}")
        assert vendor.blocking_calls == 0, "the banned primitive was reached"
        assert vendor.deferred_posts == n

    def test_concurrent_exceptions_route_to_their_own_caller(self, vendor):
        """Error holders are per-call too — a raising turn must not poison a
        sibling turn that succeeded."""
        vendor.start_pump()
        outcomes: dict = {}

        def _caller(i):
            def _payload():
                if i % 2:
                    raise ValueError(f"boom-{i}")
                return f"ok-{i}"
            try:
                outcomes[i] = mt.run_on_main(_payload, timeout=8.0)
            except ValueError as exc:
                outcomes[i] = f"raised:{exc}"

        threads = [threading.Thread(target=_caller, args=(i,), daemon=True)
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        expected = {i: (f"raised:boom-{i}" if i % 2 else f"ok-{i}") for i in range(8)}
        assert outcomes == expected


# ===========================================================================
# 3. COOK HOLDS MAIN — inline-overrun telemetry, no spurious failure
# ===========================================================================

class TestCookHoldsMain:
    """A long payload on the main thread is the RESIDUAL of the fix, not a bug.

    Migrating a marshal makes a main-thread caller RUN the payload inline
    instead of deadlocking — strictly better, but a 90 s inline render still
    freezes the GUI for 90 s. ``note_main_thread_inline_overrun`` is the only
    place that residual is observable (main_thread.py:258-273), so these pins
    hold it to: it fires, it is honest about the numbers, and it does NOT
    convert legitimately slow work into a failure.
    """

    def test_long_inline_payload_reports_overrun_and_still_succeeds(
            self, monkeypatch, vendor):
        monkeypatch.setenv(mg.INLINE_BUDGET_ENV_VAR, "0.05")
        mg.reset_guard_state()

        result = mt.run_on_main(lambda: (time.sleep(0.2), "cook-done")[1], timeout=5.0)

        assert result == "cook-done", "slow work must still return its value"
        stats = mg.guard_stats()
        assert stats["inline_overruns"] == 1
        assert stats["violations"] == 0, (
            "a slow-but-completing cook is NOT a starvation violation")
        assert stats["stack_dumps"] == 0, "telemetry must not dump on mere slowness"

        entry = [e for e in mg.guard_events() if e["kind"] == "inline_overruns"][-1]
        assert entry["where"] == "main_thread.run_on_main:fast_path_2"
        assert entry["elapsed_s"] >= 0.2
        assert entry["budget_s"] == pytest.approx(0.05)

    def test_fast_inline_payload_records_no_overrun(self, monkeypatch, vendor):
        """The red half: the sink must be SILENT under budget, or the test above
        proves nothing."""
        monkeypatch.setenv(mg.INLINE_BUDGET_ENV_VAR, "5.0")
        mg.reset_guard_state()

        assert mt.run_on_main(lambda: "quick", timeout=5.0) == "quick"
        assert mg.guard_stats()["inline_overruns"] == 0

    def test_overrun_telemetry_never_breaks_the_payload(self, monkeypatch, vendor):
        """Telemetry is wrapped in try/except by contract (main_thread.py:270).

        A broken guard import must not convert a working marshal into a failure —
        nor must it swallow the payload's own exception.
        """
        def _explode(*a, **k):
            raise RuntimeError("telemetry sink is down")
        monkeypatch.setattr(mg, "note_main_thread_inline_overrun", _explode)
        monkeypatch.setenv(mg.INLINE_BUDGET_ENV_VAR, "0.01")

        assert mt.run_on_main(lambda: (time.sleep(0.05), "survived")[1]) == "survived"

        with pytest.raises(ValueError, match="payload-error"):
            mt.run_on_main(lambda: (_ for _ in ()).throw(ValueError("payload-error")))

    def test_inline_duration_is_attributed_to_the_direct_histogram(self, vendor):
        """C6: the panel/bridge inline path must not stay at count 0.

        The dispatch-wait histogram only sees the worker path; without this
        second sink the dominant live path has zero attribution.
        """
        mt.reset_main_thread_direct_stats()
        mt.reset_dispatch_wait_stats()
        mt.run_on_main(lambda: (time.sleep(0.02), "x")[1])

        direct = mt.main_thread_direct_stats()
        assert direct["count"] == 1
        assert direct["max_ms"] >= 20.0
        assert mt.dispatch_wait_stats()["count"] == 0, (
            "an inline call never queued, so it is not a dispatch-wait sample")


# ===========================================================================
# 4. CANCEL MID-MARSHAL — C4 zombie-kill, and its DOCUMENTED residual
# ===========================================================================

class TestCancelMidMarshal:
    """C4 (main_thread.py:280-287) promises exactly one thing, and this class
    pins exactly that thing — not an idealised version of it.

    THE PROMISE: once the caller has timed out, a payload that has NOT YET
    STARTED becomes a no-op. The ``abandoned`` flag is checked under a lock
    immediately before ``fn()`` runs.

    THE DOCUMENTED RESIDUAL, verbatim from the source comment: "A payload
    already inside fn() when the timeout fires is the accepted residual race —
    the lock only serializes the check-vs-set, not fn() itself." Python cannot
    interrupt a running payload. ``test_payload_already_running_is_NOT_killed``
    pins that honestly. If someone later claims cancellation is total, that
    test is the contradiction.
    """

    def test_not_yet_started_payload_is_abandoned(self, vendor):
        """The promise. Caller gives up before the loop drains → no mutation."""
        mutations: list = []
        out = _call_off_main(
            lambda: mt.run_on_main(lambda: mutations.append("MUTATED"), timeout=0.1))

        _assert_marshal_timeout(out, "caller")
        assert vendor.queued() == 1, "the callback is still sitting in the queue"

        # Now let the main thread free up. The zombie must NOT fire.
        vendor.pump_once()
        assert not _poll(lambda: mutations != [], timeout=0.5)
        assert mutations == [], "zombie mutation executed after the caller gave up"
        assert vendor.pump_errors == [], "an abandoned callback must exit cleanly"

    def test_payload_already_running_is_NOT_killed(self, vendor):
        """The DOCUMENTED RESIDUAL — pinned deliberately, not aspirationally.

        A payload already inside fn() when the timeout fires keeps running and
        its mutation lands. The caller was told the op failed, so a retry can
        double-apply. That is the accepted, written-down limit of C4; the fix
        for it is cooperative cancellation inside tool bodies, not this lock.
        """
        vendor.start_pump()
        started = threading.Event()
        mutations: list = []

        def _slow_payload():
            started.set()
            time.sleep(0.45)
            mutations.append("MUTATED")
            return "late"

        out = _call_off_main(lambda: mt.run_on_main(_slow_payload, timeout=0.12))

        assert started.is_set(), "payload must have entered fn() before the timeout"
        _assert_marshal_timeout(out, "caller")   # the caller WAS told it failed
        assert _poll(lambda: mutations == ["MUTATED"], timeout=3.0), (
            "the residual race is real: an already-running payload is NOT stopped. "
            "If this now passes trivially, C4's contract changed — update the "
            "source comment at main_thread.py:283-285 too."
        )

    def test_abandoned_wake_is_still_a_dispatch_wait_sample(self, vendor):
        """C6 semantics: the queue-sit time is the datum regardless of whether
        fn() ran (main_thread.py:291-296). Abandonment must not blind the
        attribution instrument."""
        mt.reset_dispatch_wait_stats()
        _call_off_main(lambda: mt.run_on_main(lambda: "x", timeout=0.1))
        assert vendor.queued() == 1
        vendor.pump_once()
        assert _poll(lambda: mt.dispatch_wait_stats()["count"] == 1)

    def test_executor_gui_path_abandons_zombies_too(self, gui_mode):
        """The SECOND marshal site carries the same C4 flag
        (main_thread_executor.py:230-236) and the same typed timeout."""
        mutations: list = []
        out = _call_off_main(lambda: mte.main_thread_exec(
            lambda **kw: mutations.append("MUTATED"), {}, timeout=0.1))

        assert isinstance(out.get("error"), mte.MainThreadTimeoutError)
        assert isinstance(out["error"], TimeoutError), "typed as stdlib TimeoutError"
        gui_mode.pump_once()
        assert not _poll(lambda: mutations != [], timeout=0.5)
        assert mutations == []


# ===========================================================================
# 5. CALLER DISCONNECTS MID-TURN — cleanup, no leaked waiter
# ===========================================================================

class TestCallerDisconnectsMidTurn:
    """A WS client vanishing mid-turn must cost the process nothing.

    The old ``_exec_gui`` spawned a worker thread to keep the blocking primitive
    off MAIN, and that worker "leaks forever on caller timeout" (marshal audit
    ``docs/sprint_freeze/marshal_map.md`` row 26). The migrated shape spawns no
    thread at all: the caller waits on its own Event, and on timeout it just
    returns. These pins hold that.
    """

    def test_caller_thread_terminates_and_leaks_no_waiter(self, vendor):
        """The disconnect: the caller thread dies while the payload is queued."""
        baseline = {t.ident for t in threading.enumerate()}
        mutations: list = []

        out = _call_off_main(
            lambda: mt.run_on_main(lambda: mutations.append("MUTATED"), timeout=0.1),
            name="disconnecting-client")

        caller = out["thread"]
        _assert_marshal_timeout(out, "disconnecting caller")
        assert _poll(lambda: not caller.is_alive()), "caller thread must terminate"

        # Nothing new and alive is attributable to the marshal.
        leaked = {t.ident for t in threading.enumerate() if t.is_alive()} - baseline
        leaked.discard(caller.ident)
        assert leaked == set(), (
            f"marshal leaked thread(s) after caller disconnect: {leaked!r}")

        # The abandoned callback drains cleanly with nobody left to receive it.
        vendor.pump_once()
        assert vendor.pump_errors == [], (
            "an orphaned callback must not raise into the event loop")
        assert mutations == []

    def test_many_disconnects_leave_no_thread_residue(self, vendor):
        """Repeat the disconnect — a per-call leak would compound visibly."""
        baseline = threading.active_count()
        for _i in range(10):
            out = _call_off_main(
                lambda: mt.run_on_main(lambda: "never", timeout=0.05))
            _assert_marshal_timeout(out, "disconnect #%d" % _i)
            assert _poll(lambda: not out["thread"].is_alive())
        vendor.pump_once()
        assert _poll(lambda: threading.active_count() <= baseline, timeout=3.0), (
            f"thread count grew {baseline} -> {threading.active_count()} across "
            "10 disconnects")

    def test_disconnect_does_not_corrupt_the_next_caller(self, vendor):
        """A turn abandoned mid-flight must not hand its stale result to the
        NEXT turn — the failure mode the vendor's module global has by design."""
        abandoned = _call_off_main(
            lambda: mt.run_on_main(lambda: "STALE", timeout=0.05))
        _assert_marshal_timeout(abandoned, "abandoned turn")

        vendor.start_pump()
        fresh = _call_off_main(lambda: mt.run_on_main(lambda: "FRESH", timeout=5.0))
        assert fresh.get("value") == "FRESH", (
            f"next caller received a foreign result: {fresh!r}")


# ===========================================================================
# 6. WATCHDOG DEGRADATION — report and recover; it CANNOT un-wedge MAIN
# ===========================================================================

class TestWatchdogDegradation:
    """A wedged main thread must produce a TYPED error plus thread-stack
    evidence, and the server must keep serving.

    HONEST LIMIT (marshal_guard docstring, "WHAT THIS CANNOT DO"): once MAIN is
    parked inside ``hdefereval._condition.wait()`` or a native modal loop,
    nothing in Python can un-wedge it — there is no interrupt, and the only
    notifier of that condition is the main thread's own event-loop callback.
    The watchdog reports, captures frames, and keeps the SERVER threads alive.
    No test here asserts unfreeze, and
    ``test_dump_states_it_cannot_unfreeze_main`` pins that the artifact says so
    out loud, so a future reader cannot mistake diagnosis for recovery.
    """

    def test_wedged_main_thread_fast_fails_after_two_timeouts(self, vendor):
        """Degradation ladder: each blocked marshal raises, and after
        _STALL_THRESHOLD consecutive timeouts the stall detector flips so new
        commands fail immediately instead of queueing behind a dead main thread.
        """
        assert mt.is_main_thread_stalled() is False
        for _ in range(mt._STALL_THRESHOLD):
            out = _call_off_main(lambda: mt.run_on_main(lambda: "x", timeout=0.05))
            _assert_marshal_timeout(out, "wedged marshal")

        assert mt.is_main_thread_stalled() is True
        state = mt.stall_state()
        assert state["stalled"] is True
        assert state["consecutive_timeouts"] >= mt._STALL_THRESHOLD
        assert state["last_timeout_ts"] is not None

    def test_starvation_guard_raises_typed_error_and_dumps_stacks(
            self, monkeypatch, tmp_path, vendor):
        """The typed error + the evidence file, in raise mode."""
        monkeypatch.setenv(mg.GUARD_ENV_VAR, mg.MODE_RAISE)
        mg.reset_guard_state()

        with pytest.raises(mg.MainThreadStarvationError, match="self-deadlock"):
            mg.forbid_main_thread_block("test_marshal_hostile:wedged_main")

        assert issubclass(mg.MainThreadStarvationError, RuntimeError)
        stats = mg.guard_stats()
        assert stats["violations"] == 1
        assert stats["stack_dumps"] == 1

        dumps = list(tmp_path.glob(f"{mg.FREEZE_STACK_PREFIX}*.txt"))
        assert len(dumps) == 1, f"expected one stack dump in {tmp_path}: {dumps!r}"
        text = dumps[0].read_text(encoding="utf-8")
        assert "test_marshal_hostile:wedged_main" in text
        assert "<<< MAIN" in text, "the dump must identify the main thread's frames"
        assert "sys._current_frames()" in text and "faulthandler" in text

    def test_dump_states_it_cannot_unfreeze_main(self, tmp_path, vendor):
        """The honesty pin. The artifact must say it diagnoses, not recovers."""
        mg.reset_guard_state()
        path = mg.dump_thread_stacks(reason="wedged", where="hostile",
                                     dir_path=str(tmp_path))
        assert path is not None
        text = open(path, encoding="utf-8").read()
        assert "cannot" in text.lower()
        assert "un-wedge" in text
        assert "hdefereval._condition.wait()" in text

    def test_guard_stays_silent_off_main(self, monkeypatch, vendor):
        """The red half of the guard: an OFF-MAIN thread waiting on MAIN is the
        CORRECT pattern and must never be flagged. A guard that fires here is
        noise, and noise gets the guard switched off (marshal_guard scoping rule).
        """
        monkeypatch.setenv(mg.GUARD_ENV_VAR, mg.MODE_RAISE)
        mg.reset_guard_state()

        out = _call_off_main(
            lambda: mg.forbid_main_thread_block("off_main_wait_is_legal"))
        assert "error" not in out, f"guard fired off-main: {out!r}"
        assert mg.guard_stats()["violations"] == 0

    def test_process_still_serves_the_next_call_after_the_wedge(self, vendor):
        """Recovery of the SERVER, which is the only recovery on offer.

        The wedge is not un-wedged by anything in Python; the fake event loop
        simply resumes (the real analogue is a cook finishing). What is pinned
        is that the marshal boundary carries no poisoned state across it: the
        next call succeeds and the stall detector clears.
        """
        for _ in range(mt._STALL_THRESHOLD):
            out = _call_off_main(lambda: mt.run_on_main(lambda: "x", timeout=0.05))
            _assert_marshal_timeout(out, "wedged marshal")
        assert mt.is_main_thread_stalled() is True

        vendor.start_pump()   # the main thread becomes responsive again
        served = _call_off_main(lambda: mt.run_on_main(lambda: "served", timeout=5.0))

        assert served.get("value") == "served", f"server did not recover: {served!r}"
        assert mt.is_main_thread_stalled() is False, "stall counter must reset"
        assert mt.stall_state()["last_timeout_ts"] is not None, (
            "the incident timestamp must SURVIVE recovery — it answers 'when did "
            "this last happen', not 'are we stalled now'")

    def test_recovery_probe_bounded_and_reports_honestly(self, vendor):
        """H3's probe_main_thread: bounded, never raises, and its boolean is the
        truth about the main thread — False while wedged, True once served."""
        out = _call_off_main(lambda: mt.probe_main_thread(timeout=0.05))
        assert out.get("value") is False, "a wedged main thread must probe False"

        vendor.start_pump()
        out = _call_off_main(lambda: mt.probe_main_thread(timeout=5.0))
        assert out.get("value") is True
        assert mt.is_main_thread_stalled() is False
