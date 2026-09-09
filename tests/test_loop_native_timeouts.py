"""Actual deferred dispatcher + observer, without HOM or substrate handles."""
import importlib.util
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace

import pytest

from synapse.core.protocol import SynapseResponse
from synapse.host import memory_loop as host
from synapse.loop.ports import PortResult


@pytest.mark.parametrize("kind, expected", [
    ("unstarted", None), ("started", None), ("builtin", None),
    ("explicit_runtime", False), ("explicit_value", False), ("success", True)])
def test_native_timeout_is_unknown_and_genuine_failures_are_false(monkeypatch, kind, expected):
    source = Path(__file__).parents[1] / "python/synapse/server/main_thread.py"
    spec = importlib.util.spec_from_file_location("isolated_loop_main_thread", source)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    monkeypatch.setitem(sys.modules, "synapse.server.main_thread", native)
    callbacks, release = queue.Queue(), threading.Event()
    monkeypatch.setitem(sys.modules, "hdefereval", SimpleNamespace(executeDeferred=callbacks.put))
    monkeypatch.setenv("SYNAPSE_LOOP_ENABLED", "1")
    events, values, errors = [], [], []

    class RecordingLoop:
        def begin(self, *args):
            events.append("forecast")
            return {"synthetic": True}
        def finish(self, record, value, result_digest):
            events.append("terminal")
            values.append(value)
            return PortResult.ok({"recording_double": True})

    monkeypatch.setattr(host, "_on_main", lambda fn: fn())
    monkeypatch.setattr(host, "_snapshot", lambda op: {"storage_dir": "unused", "context": {}, "relation_keys": []})
    monkeypatch.setattr(host, "coordinator", lambda root: RecordingLoop())

    def payload():
        assert threading.current_thread() is threading.main_thread()
        events.append("payload_started")
        if kind == "started":
            assert release.wait(2)
        events.append("payload_success")
        return SynapseResponse(id="synthetic", success=True, data={"success": True})

    def dispatch():
        events.append("dispatch")
        if kind == "builtin":
            raise TimeoutError("synthetic timeout")
        if kind == "explicit_runtime":
            raise RuntimeError("genuine handler failure")
        if kind == "explicit_value":
            raise ValueError("genuine handler failure")
        return native.run_on_main(payload, timeout=.08 if kind != "success" else 1,
            record_stall=False, label="isolated-loop-test")

    def run():
        try:
            host.observe_operation("create_node", {}, dispatch, response=True)
        except BaseException as exc:
            errors.append(exc)
        finally:
            release.set()

    thread = threading.Thread(target=run)
    thread.start()
    try:
        if kind in {"started", "success"}:
            callbacks.get(timeout=2)()
        thread.join(2)
        assert not thread.is_alive()
        if kind == "unstarted":
            callbacks.get(timeout=2)()
        assert values == [expected]
        assert events.index("forecast") < events.index("dispatch")
        if kind in {"unstarted", "started"}:
            assert len(errors) == 1 and isinstance(errors[0], RuntimeError)
            assert isinstance(errors[0], native.MainThreadTimeout)
        if kind == "unstarted":
            assert "payload_started" not in events
        if kind == "started":
            assert events.index("payload_started") < events.index("terminal") < events.index("payload_success")
    finally:
        release.set()
        thread.join(2)
