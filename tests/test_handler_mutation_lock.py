"""C5 (CTO Remediation Mile 2) — cross-client mutation serialization in handle().

Two clients can drive one Houdini concurrently; nothing serialized their command
sequences, so two agents' mutations interleaved on the shared scene/undo stack.
C5 holds one process-wide lock around a MUTATING command's invoke(), skipped on
the main thread (already serialized there; locking would deadlock run_on_main).

Mirrors the established handler-test idiom: fake hou/hdefereval before import.
"""

import sys
import threading
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)
_mock_hdefereval = ModuleType("hdefereval")
_mock_hdefereval.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
sys.modules.setdefault("hou", _mock_hou)
sys.modules.setdefault("hdefereval", _mock_hdefereval)

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.core.protocol import SynapseCommand  # noqa: E402


def _cmd(t):
    return SynapseCommand(type=t, id=f"id-{t}", payload={})


def test_mutating_commands_serialize_across_threads():
    h = SynapseHandler()
    events, obs = [], threading.Lock()

    def slow(payload):
        with obs:
            events.append("enter")
        time.sleep(0.25)
        with obs:
            events.append("exit")
        return {"ok": True}

    h._registry.register("c5_mutate", slow)   # not in _READ_ONLY_COMMANDS → mutating

    threads = [threading.Thread(target=lambda: h.handle(_cmd("c5_mutate"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    # The lock forbids overlap: the two enter/exit intervals must not interleave.
    assert events == ["enter", "exit", "enter", "exit"]


def test_main_thread_mutation_skips_lock_no_deadlock():
    h = SynapseHandler()
    started, release = threading.Event(), threading.Event()

    def holder(payload):
        started.set()
        release.wait(timeout=5)        # hold the mutation lock from a worker thread
        return {}

    ran = []

    def quick(payload):
        ran.append("ran")
        return {}

    h._registry.register("c5_hold", holder)
    h._registry.register("c5_quick", quick)

    worker = threading.Thread(target=lambda: h.handle(_cmd("c5_hold")))
    worker.start()
    assert started.wait(timeout=2)     # worker now holds _MUTATION_LOCK

    # This call is on the MAIN thread → must skip the lock and proceed despite the hold.
    h.handle(_cmd("c5_quick"))
    assert ran == ["ran"]              # did not block on the held lock (no deadlock)

    release.set()
    worker.join(timeout=5)


def test_read_only_commands_do_not_serialize():
    h = SynapseHandler()
    # 'search' is read-only; register a slow body and confirm two threads overlap.
    overlap = {"max_concurrent": 0, "cur": 0}
    lk = threading.Lock()

    def slow_read(payload):
        with lk:
            overlap["cur"] += 1
            overlap["max_concurrent"] = max(overlap["max_concurrent"], overlap["cur"])
        time.sleep(0.2)
        with lk:
            overlap["cur"] -= 1
        return {"results": []}

    h._registry.register("search", slow_read)   # 'search' ∈ _READ_ONLY_COMMANDS
    threads = [threading.Thread(target=lambda: h.handle(_cmd("search"))) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert overlap["max_concurrent"] == 2        # read-only ran concurrently (not serialized)
