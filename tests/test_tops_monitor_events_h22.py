"""tops_monitor_stream registers against the PDG event API that H22 really has.

Defect (2026-10-06): 'start' called
    ctx.addEventHandler(_on_event, EventType.WorkItemStateChange
                                   | EventType.CookProgress | EventType.CookComplete)
``pdg.EventType.CookProgress`` does not exist in Houdini 22.0.400, and the
enum does not support ``|`` at all (TypeError, hython probe). The failure was
swallowed, so the tool answered ``status: monitoring`` for a stream with no
handler attached. The callback also read ``event.workItem``, which H22's
``pdg.Event`` does not carry (it has ``workItemId`` + ``currentState``).

The fake ``pdg`` here exposes only members present in the committed H22
symbol table, and its EventType members are plain objects so ``|`` raises the
same TypeError the real enum does.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from synapse.server.handlers_tops import diagnostics as diag

_SYMBOLS = (
    Path(__file__).resolve().parents[1]
    / "python" / "synapse" / "cognitive" / "tools" / "data" / "h22_symbol_table.json"
)

_EVENT_TYPES = (
    "WorkItemStateChange", "NodeProgressUpdate", "WorkItemCookPercentUpdate",
    "CookComplete", "CookStart", "CookError",
)
_STATES = ("Cooking", "CookedSuccess", "CookedFail", "CookedCancel")


class _Member:
    """An enum member that, like H22's _pdg.EventType, has no ``|``."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"EventType.{self.name}"


def _fake_pdg():
    mod = types.ModuleType("pdg")
    mod.EventType = types.SimpleNamespace(**{n: _Member(n) for n in _EVENT_TYPES})
    mod.workItemState = types.SimpleNamespace(**{n: _Member(n) for n in _STATES})
    return mod


class _FakeContext:
    def __init__(self, fail_on=None):
        self.added = []      # (callback, event_type, handler)
        self.removed = []
        self.fail_on = fail_on
        self.graph = types.SimpleNamespace(workItemById=lambda i: self.items.get(i))
        self.items = {}

    def addEventHandler(self, fn, etype):  # noqa: N802 - mirrors pdg
        if not isinstance(etype, _Member):
            raise TypeError(f"addEventHandler expects one EventType, got {etype!r}")
        if self.fail_on is not None and etype.name == self.fail_on:
            raise RuntimeError("boom")
        handler = object()
        self.added.append((fn, etype, handler))
        return handler

    def removeEventHandler(self, handler):  # noqa: N802 - mirrors pdg
        self.removed.append(handler)


@pytest.fixture
def env(monkeypatch):
    pdg = _fake_pdg()
    monkeypatch.setitem(sys.modules, "pdg", pdg)
    monkeypatch.setitem(sys.modules, "hdefereval", types.ModuleType("hdefereval"))

    state = types.SimpleNamespace(ctx=_FakeContext(), pdg=pdg)
    # getPDGNode reads state.ctx at call time so a test can swap it.
    node = types.SimpleNamespace(
        parent=lambda: None,
        getPDGNode=lambda: types.SimpleNamespace(context=state.ctx),
    )
    fake_hou = types.SimpleNamespace(node=lambda p: node)
    monkeypatch.setattr(diag, "hou", fake_hou, raising=False)
    monkeypatch.setattr(diag, "HOU_AVAILABLE", True)
    monkeypatch.setattr(diag, "_run_in_main_thread_pdg", lambda fn: fn())
    monkeypatch.setattr(diag, "_ensure_tops_warm_standby", lambda *_a, **_k: None)
    state.handler = diag.TopsDiagnosticsMixin()
    return state


def _start(env):
    return env.handler._handle_tops_monitor_stream(
        {"node": "/obj/topnet1/gen", "action": "start"}
    )


def test_fake_members_are_real_h22_symbols():
    table = _SYMBOLS.read_text(encoding="utf-8")
    for name in _EVENT_TYPES:
        assert f"pdg.EventType.{name}" in table, name
    assert "pdg.EventType.CookProgress" not in table
    for name in _STATES:
        assert f"pdg.workItemState.{name}" in table, name
    json.loads(table)  # still a valid table


def test_start_registers_one_handler_per_real_event_type(env):
    result = _start(env)
    assert result["status"] == "monitoring"
    registered = [etype.name for _fn, etype, _h in env.ctx.added]
    assert registered, "start reported monitoring with no PDG handler registered"
    assert set(registered) <= set(_EVENT_TYPES)
    assert "WorkItemStateChange" in registered
    assert "CookComplete" in registered
    assert "NodeProgressUpdate" in registered


def test_stop_removes_every_registered_handler(env):
    mid = _start(env)["monitor_id"]
    handlers = [h for _fn, _e, h in env.ctx.added]
    env.handler._handle_tops_monitor_stream(
        {"node": "/obj/topnet1/gen", "action": "stop", "monitor_id": mid}
    )
    assert sorted(map(id, env.ctx.removed)) == sorted(map(id, handlers))


def test_registration_failure_is_an_error_not_a_started_stream(env):
    env.ctx.fail_on = "CookComplete"
    with pytest.raises(RuntimeError, match="registering the PDG event handler failed"):
        _start(env)
    # Handlers added before the failure are rolled back; nothing is stored.
    assert len(env.ctx.removed) == len(env.ctx.added)
    assert not getattr(env.handler, "_tops_monitors", {})


def test_missing_graph_context_is_an_error(env):
    env.ctx = None
    with pytest.raises(RuntimeError, match="no graph context"):
        _start(env)


def test_callback_reads_h22_event_shape(env):
    mid = _start(env)["monitor_id"]
    pdg = env.pdg
    by_type = {etype.name: fn for fn, etype, _h in env.ctx.added}

    wi = types.SimpleNamespace(state=pdg.workItemState.CookedSuccess, frame=3.0,
                               cookTime=1.5, resultData=["/tmp/out.0003.exr"])
    env.ctx.items[42] = wi
    by_type["WorkItemStateChange"](types.SimpleNamespace(
        type=pdg.EventType.WorkItemStateChange, workItemId=42,
        currentState=pdg.workItemState.CookedSuccess,
        node=types.SimpleNamespace(name="gen"), context=env.ctx,
    ))

    pnode = types.SimpleNamespace(name="gen", workItems=[
        wi, types.SimpleNamespace(state=pdg.workItemState.Cooking),
    ])
    by_type["NodeProgressUpdate"](types.SimpleNamespace(
        type=pdg.EventType.NodeProgressUpdate, node=pnode, context=env.ctx,
    ))

    events = env.handler._tops_monitors[mid]["events"]
    done = [e for e in events if e["type"] == "work_item_completed"]
    assert done and done[0]["item_id"] == 42 and done[0]["frame"] == 3.0
    progress = [e for e in events if e["type"] == "cook_progress"]
    assert progress and progress[0]["completed"] == 1 and progress[0]["total"] == 2
