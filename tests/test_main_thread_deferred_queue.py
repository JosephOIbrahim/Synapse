"""Worker callers against a manually pumped, one-callback-per-idle FIFO.

No Houdini, timer pump, thread-per-callback, or model request is involved.
The main pytest thread is the only executor of payloads. A test-only source
override lets the evidence runner falsify these checks against isolated copies.
"""
from collections import deque
import gc
import importlib.util
import os
from pathlib import Path
import sys
import threading
import time
import types
import weakref

import pytest


SOURCE = Path(os.environ.get("SYNAPSE_QUEUE_TEST_SOURCE", str(
    Path(__file__).resolve().parents[1] / "python/synapse/server/main_thread.py"
)))


def until(predicate):
    deadline = time.monotonic() + 2
    while not predicate():
        assert time.monotonic() < deadline, "bounded synchronization timed out"
        threading.Event().wait(0.001)


class IdleFIFO(types.ModuleType):
    def __init__(self):
        super().__init__("hdefereval")
        self.callbacks = deque()
        self.lock = threading.Lock()
        self.posts = 0
        self.before_post = None
        self.after_post = None
        self.owner = threading.get_ident()

    def executeDeferred(self, callback):
        if self.before_post is not None:
            self.before_post()
        with self.lock:
            self.callbacks.append(callback)
            self.posts += 1
        if self.after_post is not None:
            self.after_post()

    def depth(self):
        with self.lock:
            return len(self.callbacks)

    def pump_one(self):
        assert threading.get_ident() == self.owner
        with self.lock:
            callback = self.callbacks.popleft()
        callback()


class Caller:
    def __init__(self, mt, fn, **kwargs):
        self.out = {}
        self.done = threading.Event()
        self.waiting = threading.Event()

        def run():
            mt._test_waiter.entered = self.waiting
            try:
                self.out["value"] = mt.run_on_main(fn, **kwargs)
            except BaseException as error:
                self.out["error"] = error
            finally:
                self.done.set()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def join(self):
        assert self.done.wait(2), "worker did not complete"
        self.thread.join(1)
        assert not self.thread.is_alive()
        return self.out


@pytest.fixture
def rig(monkeypatch):
    spec = importlib.util.spec_from_file_location("queue_test_main_thread", SOURCE)
    mt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mt)
    # Observe entry to the real Event.wait without replacing its behavior.
    # Pending-registry insertion precedes actual enqueueing, so it is not a
    # sufficient synchronization point for tests that immediately pump a wake.
    mt._test_waiter = threading.local()

    class ObservedEvent(threading.Event):
        def wait(self, timeout=None):
            mt._test_waiter.entered.set()
            return super().wait(timeout)

    mt.threading = types.SimpleNamespace(**vars(threading))
    mt.threading.Event = ObservedEvent
    vendor = IdleFIFO()
    monkeypatch.setitem(sys.modules, "hdefereval", vendor)
    callers = []

    def start(fn=lambda: "ok", **kwargs):
        call = Caller(mt, fn, timeout=kwargs.pop("timeout", 1.5), **kwargs)
        callers.append(call)
        return call

    yield mt, vendor, start
    # A real vendor owns accepted callbacks until they are pumped; do not silently
    # discard them when a test changes its fake. This also cleans up failed reds.
    vendor.before_post = vendor.after_post = None
    for _ in range(100):
        if not vendor.depth():
            break
        try:
            vendor.pump_one()
        except BaseException:
            pass
    for call in callers:
        call.thread.join(2)


def test_repeated_expiry_retains_one_native_wake_and_no_payloads(rig):
    mt, vendor, start = rig
    ran = []
    refs = []

    class Payload:
        def __call__(self):
            ran.append("zombie")

    for _ in range(12):
        payload = Payload()
        refs.append(weakref.ref(payload))
        call = start(payload, timeout=0.02, record_stall=False)
        assert isinstance(call.join().get("error"), RuntimeError)
        call.out.clear()  # discard the caller's exception traceback too
        del payload
    gc.collect()
    assert mt.pending_dispatch_count() == 0
    assert vendor.depth() == 1, "expired requests flooded the vendor idle FIFO"
    assert all(ref() is None for ref in refs), "expired payload closures retained"
    assert mt.dispatch_wait_stats()["count"] == 12
    assert mt.main_thread_hold_stats()["count"] == 0
    vendor.pump_one()
    assert ran == []
    assert mt.dispatch_wait_stats()["count"] == 12, "double-counted inert wake"


def test_live_fifo_runs_one_payload_per_wake_on_main(rig):
    mt, vendor, start = rig
    order = []
    calls = []
    for number in range(3):
        calls.append(start(lambda n=number: order.append((n, threading.get_ident())) or n))
        assert calls[-1].waiting.wait(1)
    assert vendor.depth() == 1
    for number in range(3):
        vendor.pump_one()
        assert order == [(n, vendor.owner) for n in range(number + 1)]
        assert calls[number].join() == {"value": number}
        assert vendor.depth() == (1 if number < 2 else 0)
    assert mt.pending_dispatch_count() == 0


def test_expired_middle_does_not_delay_or_reorder_live_payloads(rig):
    mt, vendor, start = rig
    ran = []
    first = start(lambda: ran.append("first"))
    assert first.waiting.wait(1)
    dead = start(lambda: ran.append("dead"), timeout=0.03)
    assert dead.waiting.wait(1)
    last = start(lambda: ran.append("last"))
    assert last.waiting.wait(1)
    assert "error" in dead.join()
    vendor.pump_one()
    first.join()
    vendor.pump_one()
    assert last.join() == {"value": None}
    assert ran == ["first", "last"]
    assert vendor.depth() == 0


def test_empty_expired_queue_keeps_ticket_and_reuses_existing_wake(rig):
    mt, vendor, start = rig
    expired = start(timeout=0.02)
    assert "error" in expired.join()
    fresh = start(lambda: "fresh")
    assert fresh.waiting.wait(1)
    assert vendor.posts == 1, "pruning empty work must not clear an outstanding wake"
    vendor.pump_one()
    assert fresh.join() == {"value": "fresh"}
    assert vendor.depth() == 0


def test_foreign_vendor_callbacks_remain_in_order(rig):
    mt, vendor, start = rig
    order = []
    vendor.executeDeferred(lambda: order.append("foreign-before"))
    first = start(lambda: order.append("one"))
    assert first.waiting.wait(1)
    second = start(lambda: order.append("two"))
    assert second.waiting.wait(1)
    vendor.executeDeferred(lambda: order.append("foreign-after"))
    vendor.pump_one()
    vendor.pump_one()
    first.join()
    assert order == ["foreign-before", "one"]
    vendor.pump_one()
    assert order[-1] == "foreign-after", "SYNAPSE consumed another vendor callback's turn"
    vendor.pump_one()
    second.join()
    assert order == ["foreign-before", "one", "foreign-after", "two"]


def test_emergency_halt_prunes_queued_work_but_preserves_wake(rig):
    mt, vendor, start = rig
    ran = []
    old = [start(lambda: ran.append("cancelled"), timeout=0.12) for _ in range(3)]
    assert all(call.waiting.wait(1) for call in old)
    assert mt.cancel_pending_dispatches("test") == 3
    assert mt.cancel_pending_dispatches("test") == 0
    fresh = start(lambda: ran.append("fresh"))
    assert fresh.waiting.wait(1)
    assert vendor.depth() == 1
    vendor.pump_one()
    assert fresh.join() == {"value": None}
    assert ran == ["fresh"]
    assert all("error" in call.join() for call in old)
    assert mt.dispatch_wait_stats()["count"] == 4


@pytest.mark.parametrize("record_wait", [False, True])
def test_pruned_wait_sample_is_once_and_respects_opt_out(rig, record_wait):
    mt, vendor, start = rig
    call = start(timeout=0.03, record_wait=record_wait, record_stall=False)
    assert "error" in call.join()
    count = int(record_wait)
    assert mt.dispatch_wait_stats()["count"] == count
    assert mt.stall_state()["consecutive_timeouts"] == 0
    vendor.pump_one()
    assert mt.dispatch_wait_stats()["count"] == count
    assert mt.main_thread_hold_stats()["count"] == 0


def test_midflight_timeout_finishes_once_then_serves_next(rig):
    mt, vendor, start = rig
    ran = []
    first = None

    def payload():
        ran.append("started")
        assert first.done.wait(1), "caller did not time out while payload was running"
        ran.append("finished")
        return "late"

    first = start(payload, timeout=0.08, label="slow")
    assert first.waiting.wait(1)
    second = start(lambda: "next", label="next")
    assert second.waiting.wait(1)
    vendor.pump_one()
    assert "error" in first.join()
    assert ran == ["started", "finished"]
    assert mt.main_thread_hold_stats()["abandoned_count"] == 1
    vendor.pump_one()
    assert second.join() == {"value": "next"}
    assert mt.current_main_thread_holder() is None


@pytest.mark.parametrize("error_type", [ValueError, SystemExit, KeyboardInterrupt])
def test_payload_error_reaches_its_caller_and_future_work_runs(rig, error_type):
    mt, vendor, start = rig
    error = error_type("payload failed")

    def fail():
        raise error

    first = start(fail)
    assert first.waiting.wait(1)
    second = start(lambda: "survived")
    assert second.waiting.wait(1)
    escaped = None
    try:
        vendor.pump_one()
    except BaseException as caught:
        escaped = caught
    assert escaped is None, "payload error escaped into the native idle callback"
    assert first.join().get("error") is error
    vendor.pump_one()
    assert second.join() == {"value": "survived"}
    assert mt.current_main_thread_holder() is None
    assert not getattr(mt._tls, "on_main", False)


def test_enqueue_failure_cleans_registry_and_next_call_recovers(rig):
    mt, vendor, start = rig
    error = RuntimeError("idle callback registration failed")

    def fail():
        raise error

    vendor.before_post = fail
    first = start()
    assert first.join().get("error") is error
    assert mt.pending_dispatch_count() == 0
    vendor.before_post = None
    fresh = start(lambda: "recovered")
    until(lambda: vendor.depth() == 1)
    vendor.pump_one()
    assert fresh.join() == {"value": "recovered"}


def test_failed_registration_releases_all_callers_waiting_on_that_wake(rig):
    mt, vendor, start = rig
    entered, release = threading.Event(), threading.Event()
    error = RuntimeError("registration failed after a concurrent enqueue")

    def fail():
        entered.set()
        assert release.wait(1)
        raise error

    vendor.before_post = fail
    first = start()
    assert entered.wait(1)
    second = start()
    assert second.waiting.wait(1), "second caller did not join the reserved wake"
    release.set()
    assert first.join().get("error") is error
    assert second.join().get("error") is error
    assert mt.pending_dispatch_count() == 0
    assert vendor.depth() == 0


def test_late_accepted_then_failed_wake_cannot_consume_new_ticket(rig):
    mt, vendor, start = rig
    error = RuntimeError("registered then reported failure")

    def fail():
        raise error

    vendor.after_post = fail
    first = start(lambda: "must not run")
    assert first.join().get("error") is error
    vendor.after_post = None
    ran = []
    fresh = start(lambda: ran.append("fresh") or "fresh")
    until(lambda: vendor.depth() == 2)
    vendor.pump_one()  # stale, already accepted native callback
    assert ran == [], "stale ticket stole the fresh request"
    assert not fresh.done.is_set()
    vendor.pump_one()
    assert fresh.join() == {"value": "fresh"}
    assert ran == ["fresh"]
    assert mt.pending_dispatch_count() == 0


def test_next_wake_schedule_failure_does_not_poison_completed_result(rig):
    mt, vendor, start = rig
    first = start(lambda: "completed")
    assert first.waiting.wait(1)
    second = start(lambda: "never")
    assert second.waiting.wait(1)
    error = RuntimeError("next wake failed")

    def fail():
        raise error

    vendor.before_post = fail
    vendor.pump_one()
    assert first.join() == {"value": "completed"}
    assert second.join().get("error") is error
    assert mt.pending_dispatch_count() == 0


def test_enqueue_during_payload_needs_no_extra_native_wake(rig):
    mt, vendor, start = rig
    added = []

    def first_payload():
        added.append(start(lambda: "second"))
        assert added[0].waiting.wait(1)
        assert vendor.depth() == 0, "producer double-scheduled while drain owned ticket"
        return "first"

    first = start(first_payload)
    until(lambda: vendor.depth() == 1)
    vendor.pump_one()
    assert first.join() == {"value": "first"}
    assert vendor.depth() == 1
    vendor.pump_one()
    assert added[0].join() == {"value": "second"}


def test_new_call_after_empty_drain_schedules_again(rig):
    mt, vendor, start = rig
    for value in range(5):
        call = start(lambda n=value: n)
        until(lambda: vendor.depth() == 1)
        vendor.pump_one()
        assert call.join() == {"value": value}
        assert vendor.depth() == 0
    assert vendor.posts == 5


def test_failed_scheduler_does_not_report_main_thread_recovery(rig):
    mt, vendor, start = rig
    for _ in range(2):
        assert "error" in start(timeout=0.02).join()
    vendor.pump_one()  # only the abandoned wake, no live payload ran
    assert mt.is_main_thread_stalled()

    def fail():
        raise RuntimeError("registration failed")

    vendor.before_post = fail
    assert "error" in start().join()
    assert mt.stall_state()["consecutive_timeouts"] == 2
