"""Independent ownership review: test actual worker dispatch and stale queues."""
from dataclasses import replace
from pathlib import Path
import queue
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from synapse.host.memory_lifecycle import MemoryBinding
from synapse.memory import store


class MainPump:
    """Run real run_on_main deferred callbacks on the test's main thread."""
    def __init__(self):
        self.queue = queue.Queue()
        self.posted = threading.Event()

    def executeDeferred(self, callback):
        self.queue.put(callback)
        self.posted.set()

    def worker(self, callback, before_pump=None):
        values, errors = [], []

        def run():
            try:
                values.append(callback())
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        if before_pump is not None:
            assert self.posted.wait(2), "worker did not reach main-thread dispatch"
            before_pump()
        deadline = time.monotonic() + 5
        while thread.is_alive() and time.monotonic() < deadline:
            try:
                self.queue.get(timeout=0.02)()
            except queue.Empty:
                pass
        thread.join(0.1)
        assert not thread.is_alive(), "main-thread dispatch did not complete"
        return values, errors


@pytest.fixture
def host_owner(tmp_path, monkeypatch):
    pump = MainPump()
    calls = []

    def record(name):
        def run(*args, **kwargs):
            calls.append((name, threading.get_ident()))
            return []
        return run

    owner = store.SynapseMemory.__new__(store.SynapseMemory)
    owner.project_path = tmp_path
    owner.storage_dir = tmp_path / ".synapse"
    owner._memory_binding = MemoryBinding(str(tmp_path / "a.hip"), tmp_path, tmp_path, False, "job")
    owner._on_memory_added = []
    owner._on_memory_updated = []
    owner.store = SimpleNamespace(**{name: record(name) for name in
        ("add", "search", "get_by_type", "get_recent")})
    monkeypatch.setattr(store, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store, "hou", SimpleNamespace(
        hipFile=SimpleNamespace(name=lambda: str(tmp_path / "a.hip")),
        frame=lambda: 1,
    ), raising=False)
    monkeypatch.setattr(store, "_global_synapse", owner)
    monkeypatch.setitem(sys.modules, "hdefereval", pump)
    return owner, pump, calls


@pytest.mark.parametrize("method,args,backend_method", [
    ("add", ("Recorded operation",), "add"),
    ("search", ("coral",), "search"),
    ("recall", ("coral",), "get_by_type"),
    ("get_decisions", (), "get_by_type"),
    ("get_recent", (), "get_recent"),
])
def test_worker_memory_api_executes_backend_on_main(host_owner, method, args, backend_method):
    owner, pump, calls = host_owner
    _, errors = pump.worker(lambda: getattr(owner, method)(*args))
    assert not errors
    assert calls == [(backend_method, threading.main_thread().ident)]


@pytest.mark.parametrize("change", ["owner", "scene"])
def test_queued_action_cannot_mutate_previous_owner_after_context_changes(host_owner, monkeypatch, change):
    owner, pump, calls = host_owner

    def change_context():
        if change == "owner":
            monkeypatch.setattr(store, "_global_synapse", object())
        else:
            owner._memory_binding = replace(owner._memory_binding, hip_path=str(owner.project_path / "b.hip"))

    _, errors = pump.worker(lambda: owner.add("Executed before Save As"), change_context)
    assert len(errors) == 1 and "scene changed" in str(errors[0]).lower()
    assert calls == []


def test_negative_control_unwrapped_add_exposes_worker_backend_access(host_owner, monkeypatch):
    owner, pump, calls = host_owner
    # Remove only the new host boundary in memory; no product file is altered.
    # The former metadata-only marshal still runs, exposing the real old seam.
    monkeypatch.setattr(store.SynapseMemory, "add", store.SynapseMemory.add.__wrapped__)
    _, errors = pump.worker(lambda: owner.add("Control operation"))
    assert not errors
    assert len(calls) == 1 and calls[0][0] == "add"
    assert calls[0][1] != threading.main_thread().ident


@pytest.mark.parametrize("replace_owner", [False, True])
def test_automatic_logging_keeps_independent_audit_if_owner_changes(host_owner, monkeypatch, replace_owner):
    from synapse.server import handlers
    owner, pump, _ = host_owner
    pending, memory_calls, audit_calls = [], [], []
    bridge = SimpleNamespace(
        _synapse=owner,
        log_action=lambda *args, **kwargs: memory_calls.append(threading.get_ident()),
    )
    handler = handlers.SynapseHandler.__new__(handlers.SynapseHandler)
    handler._bridge = bridge
    handler._session_id = "fixture-session"
    handler._user_id = "fixture-user"
    monkeypatch.setattr(handlers, "_log_executor", SimpleNamespace(submit=pending.append))
    monkeypatch.setattr(handlers, "audit_log", lambda: SimpleNamespace(log=lambda **kw: audit_calls.append(kw)))
    handler._submit_logs("create_node", {"fixture": True}, {"created": True})
    assert len(pending) == 1
    if replace_owner:
        bridge._synapse = object()
    _, errors = pump.worker(pending[0])
    assert not errors
    assert memory_calls == ([] if replace_owner else [threading.main_thread().ident])
    assert len(audit_calls) == 1 and audit_calls[0]["operation"] == "create_node"


@pytest.mark.parametrize("tool_name,tool_args,expected_backend", [
    ("synapse_recall", {"query": "coral", "scope": "project"}, "get_by_type"),
    ("synapse_search", {"query": "coral", "scope": "project"}, "search"),
    ("synapse_decide", {"decision": "Keep coral", "scope": "project"}, "durable_add"),
])
def test_registered_memory_tool_route_keeps_owner_work_on_main(
        host_owner, monkeypatch, tool_name, tool_args, expected_backend):
    """Exercise payload builder -> registered handler -> real tracker -> API.

    Inert backend/host edges avoid GUI, disk, transport, and knowledge writes.
    """
    from synapse.memory.models import MemoryTier
    from synapse.mcp._tool_registry import TOOL_DISPATCH
    from synapse.server.handlers import SynapseHandler
    from synapse.session import tracker

    owner, pump, calls = host_owner
    phases, requests, augmentation = [], [], []
    bridge = tracker.SynapseBridge.__new__(tracker.SynapseBridge)
    bridge._synapse = owner
    bridge._markdown_sync = None
    bridge._context_cache = None
    bridge.refresh_memory_owner = lambda: phases.append(("refresh", threading.get_ident()))
    monkeypatch.setattr(tracker, "HOU_AVAILABLE", False)

    def get_bridge():
        phases.append(("borrow", threading.get_ident()))
        return bridge

    def search(query):
        calls.append(("search", threading.get_ident()))
        requests.append(query)
        return []

    def durable_add(memory):
        calls.append(("durable_add", threading.get_ident()))
        requests.append(memory)
        return True

    owner.store.search = search
    owner.store.add_durable_if_absent = durable_add
    handler = SynapseHandler()
    handler._get_bridge = get_bridge
    handler._augment_with_knowledge = lambda *args: augmentation.append(True)
    command_name, build_payload = TOOL_DISPATCH[tool_name]
    registered = handler._registry.get(command_name)
    assert registered is not None
    values, errors = pump.worker(lambda: registered(build_payload(tool_args)))
    assert not errors
    assert phases == [("borrow", threading.main_thread().ident),
                      ("refresh", threading.main_thread().ident)]
    assert calls == [(expected_backend, threading.main_thread().ident)]
    assert augmentation == []
    if requests:
        assert requests[0].tier == MemoryTier.SHOW
    if tool_name == "synapse_decide":
        assert values[0]["recorded"] and values[0]["scope"] == "project"
