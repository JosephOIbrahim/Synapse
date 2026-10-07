"""tops_monitor_stream registers against the PDG event API that H22 really has.

Defect (2026-10-06): 'start' called
    ctx.addEventHandler(_on_event, EventType.WorkItemStateChange
                                   | EventType.CookProgress | EventType.CookComplete)
``pdg.EventType.CookProgress`` does not exist in Houdini 22.0.400, and the
enum does not support ``|`` at all (TypeError, hython probe). The failure was
swallowed, so the tool answered ``status: monitoring`` for a stream with no
handler attached. The callback also read ``event.workItem``, which H22's
``pdg.Event`` does not carry (it has ``workItemId`` + ``currentState``).

Second defect, found by a live hython 22.0.400 cook (2026-10-07): the graph
context never delivers WorkItemStateChange or NodeProgressUpdate (0 events,
against 130 and 11 on the pdg.Node for the same cooks). Handlers are now
registered on the pdg.Node, and the fakes below deliver those two types only
through the node, the way H22 does.

The fake ``pdg`` exposes only members present in the committed H22 symbol
table, and its EventType members are plain objects so ``|`` raises the same
TypeError the real enum does. The fake work item carries only H22 members
(``cookDuration``, not ``cookTime``; no ``lastError``).
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
_STATES = ("Cooking", "CookedSuccess", "CookedCache", "CookedFail", "CookedCancel")
_MEMBERS_USED = (
    "pdg.Node.addEventHandler", "pdg.Node.removeEventHandler", "pdg.Node.workItems",
    "pdg.Node.name", "pdg.WorkItem.cookDuration", "pdg.WorkItem.frame",
    "pdg.WorkItem.resultData", "pdg.Event.message",
)
_NOT_H22 = ("pdg.EventType.CookProgress", "pdg.WorkItem.cookTime", "pdg.WorkItem.lastError")
_NODE = "/obj/topnet1/proc"


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


class _Registry:
    """addEventHandler/removeEventHandler, shared by the fake node and context."""

    def __init__(self):
        self.added = []      # (callback, event_type, handler)
        self.removed = []
        self.fail_on = None

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

    def fire(self, etype_name, event):
        """Deliver to handlers registered here for that type (what PDG does)."""
        for fn, etype, h in list(self.added):
            if etype.name == etype_name and h not in self.removed:
                fn(event)


class _FakeContext(_Registry):
    def __init__(self):
        super().__init__()
        self.items = {}
        self.graph = types.SimpleNamespace(workItemById=lambda i: self.items.get(i))


class _FakePdgNode(_Registry):
    def __init__(self, ctx, name="proc"):
        super().__init__()
        self.context = ctx
        self.name = name
        self.workItems = []


@pytest.fixture
def env(monkeypatch):
    pdg = _fake_pdg()
    monkeypatch.setitem(sys.modules, "pdg", pdg)
    monkeypatch.setitem(sys.modules, "hdefereval", types.ModuleType("hdefereval"))

    ctx = _FakeContext()
    state = types.SimpleNamespace(ctx=ctx, pdg=pdg, pnode=_FakePdgNode(ctx))
    node = types.SimpleNamespace(parent=lambda: None, getPDGNode=lambda: state.pnode)
    monkeypatch.setattr(diag, "hou", types.SimpleNamespace(node=lambda p: node), raising=False)
    monkeypatch.setattr(diag, "HOU_AVAILABLE", True)
    monkeypatch.setattr(diag, "_run_in_main_thread_pdg", lambda fn: fn())
    monkeypatch.setattr(diag, "_ensure_tops_warm_standby", lambda *_a, **_k: None)
    state.handler = diag.TopsDiagnosticsMixin()
    return state


def _call(env, action, **kw):
    return env.handler._handle_tops_monitor_stream({"node": _NODE, "action": action, **kw})


def _state_change(env, item_id, state, message=""):
    """Fire WorkItemStateChange the way H22 does: on the pdg.Node only."""
    env.pnode.fire("WorkItemStateChange", types.SimpleNamespace(
        type=env.pdg.EventType.WorkItemStateChange, workItemId=item_id,
        currentState=state, node=env.pnode, context=env.ctx, message=message,
    ))


def _item(env, item_id, state, **attrs):
    wi = types.SimpleNamespace(state=state, frame=float(item_id), **attrs)
    env.ctx.items[item_id] = wi
    env.pnode.workItems.append(wi)
    return wi


def test_fake_members_are_real_h22_symbols():
    table = _SYMBOLS.read_text(encoding="utf-8")
    for name in _EVENT_TYPES:
        assert f'"pdg.EventType.{name}"' in table, name
    for name in _STATES:
        assert f'"pdg.workItemState.{name}"' in table, name
    for sym in _MEMBERS_USED:
        assert f'"{sym}"' in table, sym
    for sym in _NOT_H22:
        assert f'"{sym}"' not in table, sym
    json.loads(table)  # still a valid table


def test_start_registers_on_the_pdg_node_not_the_context(env):
    result = _call(env, "start")
    assert result["status"] == "monitoring"
    registered = [etype.name for _fn, etype, _h in env.pnode.added]
    assert sorted(registered) == sorted(
        ["WorkItemStateChange", "NodeProgressUpdate", "CookComplete", "CookError"])
    # The graph context never delivers the item/progress events on H22.
    assert env.ctx.added == []


def test_stop_removes_every_registered_handler(env):
    mid = _call(env, "start")["monitor_id"]
    handlers = [h for _fn, _e, h in env.pnode.added]
    assert len(handlers) == 4  # not vacuous: start must have registered
    stopped = _call(env, "stop", monitor_id=mid)
    assert stopped["status"] == "stopped"
    assert sorted(map(id, env.pnode.removed)) == sorted(map(id, handlers))
    assert mid not in env.handler._tops_monitors


def test_registration_failure_is_an_error_not_a_started_stream(env):
    env.pnode.fail_on = "CookComplete"
    with pytest.raises(RuntimeError, match="registering the PDG event handler failed"):
        _call(env, "start")
    # Handlers added before the failure are rolled back; nothing is stored.
    assert env.pnode.added and len(env.pnode.removed) == len(env.pnode.added)
    assert not getattr(env.handler, "_tops_monitors", {})


def test_completed_item_reads_h22_event_and_work_item(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 42, ws.CookedSuccess, cookDuration=1.5, resultData=["/tmp/out.0042.exr"])
    _state_change(env, 42, ws.Cooking)
    _state_change(env, 42, ws.CookedSuccess)

    events = _call(env, "status", monitor_id=mid)["latest_events"]
    started = [e for e in events if e["type"] == "work_item_started"]
    done = [e for e in events if e["type"] == "work_item_completed"]
    assert started and started[0]["item_id"] == 42
    assert done and done[0]["item_id"] == 42 and done[0]["frame"] == 42.0
    assert done[0]["duration_seconds"] == 1.5
    assert done[0]["output_path"] == "/tmp/out.0042.exr"
    assert "callback_error" not in _call(env, "status", monitor_id=mid)


def test_failed_item_carries_the_event_message_not_a_placeholder(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 7, ws.CookedFail)
    _state_change(env, 7, ws.CookedFail, message="python: division by zero")
    status = _call(env, "status", monitor_id=mid)
    failed = [e for e in status["latest_events"] if e["type"] == "work_item_failed"]
    assert failed[0]["error_message"] == "python: division by zero"
    assert status["summary"]["failed"] == 1


def test_cached_and_cancelled_items_are_counted_and_progress_reaches_100(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedSuccess)
    _item(env, 2, ws.CookedCache)
    _item(env, 3, ws.CookedCancel)
    _state_change(env, 1, ws.CookedSuccess)
    _state_change(env, 2, ws.CookedCache)
    _state_change(env, 3, ws.CookedCancel)
    env.pnode.fire("NodeProgressUpdate", types.SimpleNamespace(
        type=env.pdg.EventType.NodeProgressUpdate, node=env.pnode, context=env.ctx))

    status = _call(env, "status", monitor_id=mid)
    assert status["summary"] == {"completed": 1, "cached": 1, "failed": 0,
                                 "cancelled": 1, "total_processed": 3}
    types_seen = [e["type"] for e in status["latest_events"]]
    assert "work_item_cancelled" in types_seen
    cached = [e for e in status["latest_events"] if e.get("cached")]
    assert cached and cached[0]["item_id"] == 2
    progress = [e for e in status["latest_events"] if e["type"] == "cook_progress"]
    assert progress[-1]["completed"] == 3 and progress[-1]["total"] == 3
    assert progress[-1]["percent"] == 100.0


def test_cook_complete_and_cook_error_are_terminal_states(env):
    mid = _call(env, "start")["monitor_id"]
    env.pnode.fire("CookError", types.SimpleNamespace(
        type=env.pdg.EventType.CookError, node=env.pnode, context=env.ctx,
        message="scheduler: no local scheduler"))
    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "error"
    err = [e for e in status["latest_events"] if e["type"] == "cook_error"]
    assert err and err[0]["message"] == "scheduler: no local scheduler"

    env.pnode.fire("CookComplete", types.SimpleNamespace(
        type=env.pdg.EventType.CookComplete, node=env.pnode, context=env.ctx, message=""))
    assert _call(env, "stop", monitor_id=mid)["cook_state"] == "complete"


def test_second_start_on_the_same_node_attaches_nothing_new(env):
    first = _call(env, "start")
    second = _call(env, "start")
    assert second["status"] == "already_monitoring"
    assert second["monitor_id"] == first["monitor_id"]
    assert len(env.pnode.added) == 4
    _call(env, "stop", monitor_id=first["monitor_id"])
    assert len(env.pnode.removed) == len(env.pnode.added)


def test_stop_that_fails_to_marshal_can_be_retried(env, monkeypatch):
    mid = _call(env, "start")["monitor_id"]

    def _timeout(fn):
        raise TimeoutError("main thread busy cooking")

    monkeypatch.setattr(diag, "_run_in_main_thread_pdg", _timeout)
    with pytest.raises(TimeoutError):
        _call(env, "stop", monitor_id=mid)
    assert env.pnode.removed == []  # nothing detached yet
    assert mid in env.handler._tops_monitors

    monkeypatch.setattr(diag, "_run_in_main_thread_pdg", lambda fn: fn())
    assert _call(env, "stop", monitor_id=mid)["status"] == "stopped"
    assert len(env.pnode.removed) == 4


def test_truncation_is_flagged_in_status_and_counts_survive_it(env, monkeypatch):
    monkeypatch.setattr(diag, "_MAX_MONITOR_EVENTS", 10)
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    for i in range(30):
        _item(env, i, ws.CookedSuccess)
        _state_change(env, i, ws.CookedSuccess)
    status = _call(env, "status", monitor_id=mid)
    assert status["events_truncated"] is True
    assert status["events_collected"] <= 11
    assert status["summary"]["completed"] == 30


def test_unreadable_event_is_reported_not_swallowed(env):
    """A callback failure never raises into the cook thread, but status and
    stop name it, so an empty event list cannot pass for a quiet cook."""
    mid = _call(env, "start")["monitor_id"]
    # The old H21 shape: no workItemId / currentState on the event.
    env.pnode.fire("WorkItemStateChange", types.SimpleNamespace(
        type=env.pdg.EventType.WorkItemStateChange,
        workItem=types.SimpleNamespace(id=1), node=None, context=env.ctx,
    ))
    assert "AttributeError" in _call(env, "status", monitor_id=mid)["callback_error"]
    assert "AttributeError" in _call(env, "stop", monitor_id=mid)["callback_error"]


def test_stop_names_a_handler_that_would_not_detach(env):
    mid = _call(env, "start")["monitor_id"]
    calls = []

    def _flaky_remove(handler):
        calls.append(handler)
        if len(calls) == 1:
            raise RuntimeError("still cooking")
        env.pnode.removed.append(handler)

    env.pnode.removeEventHandler = _flaky_remove
    stopped = _call(env, "stop", monitor_id=mid)
    # One failure is reported, and the remaining handlers were still removed.
    assert len(stopped["handler_removal_errors"]) == 1
    assert "still cooking" in stopped["handler_removal_errors"][0]
    assert len(calls) == 4 and len(env.pnode.removed) == 3
