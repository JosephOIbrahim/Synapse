"""tops_monitor_stream registers against the PDG event API that H22 really has.

Defect (2026-10-06): 'start' called
    ctx.addEventHandler(_on_event, EventType.WorkItemStateChange
                                   | EventType.CookProgress | EventType.CookComplete)
``pdg.EventType.CookProgress`` does not exist in Houdini 22.0.400, and the
enum does not support ``|`` at all (TypeError, hython probe). The failure was
swallowed, so the tool answered ``status: monitoring`` for a stream with no
handler attached. The callback also read ``event.workItem``, which H22's
``pdg.Event`` does not carry (it has ``workItemId`` + ``currentState``).

Found by live hython 22.0.400 cooks (2026-10-07):
- the graph context never delivers WorkItemStateChange or NodeProgressUpdate
  (0 events, against 130 and 11 on the pdg.Node for the same cooks);
- a failing item's event.message is empty; the text is in WorkItem.logMessages;
- a failed item raises no CookError, and CookComplete still fires;
- H22 coalesces NodeProgressUpdate when items finish together;
- CookStart and CookComplete fire on each pdg.Node in a cook, and a
  generate-only pass fires both with no item ever cooking.

The fakes deliver item and progress events only through the node, the way H22
does, expose only members present in the committed H22 symbol table, and make
EventType members plain objects so ``|`` raises the same TypeError.
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
    "pdg.Node.name", "pdg.Node.context", "pdg.GraphContext.addEventHandler",
    "pdg.GraphContext.removeEventHandler", "pdg.WorkItem.cookDuration", "pdg.WorkItem.frame",
    "pdg.WorkItem.resultData", "pdg.WorkItem.logMessages", "pdg.Event.message",
    "hou.topNodeTypeCategory", "hou.Node.childTypeCategory", "hou.Node.allSubChildren",
    "hou.Node.path",
    "hou.TopNode.getPDGNode",
)
_NOT_H22 = ("pdg.EventType.CookProgress", "pdg.WorkItem.cookTime", "pdg.WorkItem.lastError")
_NODE = "/obj/topnet1/proc"
_NET = "/obj/topnet1"
_TOP_CATEGORY = object()


class _Member:
    """An enum member that, like H22's _pdg.EventType, has no ``|``."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"EventType.{self.name}"


class _PdgNodeBase:
    """Stands in for pdg.Node, so the monitor can tell a node from a scheduler."""


def _fake_pdg():
    mod = types.ModuleType("pdg")
    mod.EventType = types.SimpleNamespace(**{n: _Member(n) for n in _EVENT_TYPES})
    mod.workItemState = types.SimpleNamespace(**{n: _Member(n) for n in _STATES})
    mod.Node = _PdgNodeBase
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

    def types(self):
        return sorted(e.name for _f, e, _h in self.added)


class _FakeContext(_Registry):
    def __init__(self):
        super().__init__()
        self.items = {}
        self.graph = types.SimpleNamespace(workItemById=lambda i: self.items.get(i))


class _FakePdgNode(_Registry, _PdgNodeBase):
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
    state = types.SimpleNamespace(ctx=ctx, pdg=pdg, pnode=_FakePdgNode(ctx, "proc"),
                                  gen=_FakePdgNode(ctx, "gen"))
    proc = types.SimpleNamespace(parent=lambda: None, getPDGNode=lambda: state.pnode,
                                 childTypeCategory=lambda: None, path=lambda: _NODE)
    gen = types.SimpleNamespace(parent=lambda: None, getPDGNode=lambda: state.gen,
                                childTypeCategory=lambda: None, path=lambda: _NET + "/gen")
    # A topnet's localscheduler child answers getPDGNode() with a scheduler,
    # not a pdg.Node (live probe 2026-10-07); it has no work items.
    state.scheduler = types.SimpleNamespace(context=ctx, name="localscheduler",
                                            addEventHandler=None, removeEventHandler=None)
    sched = types.SimpleNamespace(parent=lambda: None, getPDGNode=lambda: state.scheduler,
                                  childTypeCategory=lambda: None, path=lambda: _NET + "/localscheduler")
    # Extra sub-children a test can add (a TOP subnet's node, a nested topnet's node).
    state.extra = []
    net = types.SimpleNamespace(parent=lambda: None, getPDGNode=lambda: None,
                                childTypeCategory=lambda: _TOP_CATEGORY,
                                allSubChildren=lambda: [sched, gen, proc] + state.extra)
    nodes = {_NODE: proc, _NET: net}
    fake_hou = types.SimpleNamespace(node=lambda p: nodes.get(p),
                                     topNodeTypeCategory=lambda: _TOP_CATEGORY)
    monkeypatch.setattr(diag, "hou", fake_hou, raising=False)
    monkeypatch.setattr(diag, "HOU_AVAILABLE", True)
    monkeypatch.setattr(diag, "_run_in_main_thread_pdg", lambda fn: fn())
    monkeypatch.setattr(diag, "_ensure_tops_warm_standby", lambda *_a, **_k: None)
    state.handler = diag.TopsDiagnosticsMixin()
    return state


def _call(env, action, node=_NODE, **kw):
    return env.handler._handle_tops_monitor_stream({"node": node, "action": action, **kw})


def _state_change(env, item_id, state, message="", on=None):
    """Fire WorkItemStateChange the way H22 does: on the pdg.Node only."""
    pnode = on or env.pnode
    pnode.fire("WorkItemStateChange", types.SimpleNamespace(
        type=env.pdg.EventType.WorkItemStateChange, workItemId=item_id,
        currentState=state, node=pnode, context=env.ctx, message=message,
    ))


def _cook_event(env, name, emitter, message=""):
    emitter.fire(name, types.SimpleNamespace(
        type=getattr(env.pdg.EventType, name), node=None, context=env.ctx, message=message))


def _progress(env, on=None):
    pnode = on or env.pnode
    pnode.fire("NodeProgressUpdate", types.SimpleNamespace(
        type=env.pdg.EventType.NodeProgressUpdate, node=pnode, context=env.ctx))


def _item(env, item_id, state, on=None, **attrs):
    wi = types.SimpleNamespace(state=state, frame=float(item_id), **attrs)
    env.ctx.items[item_id] = wi
    (on or env.pnode).workItems.append(wi)
    return wi


def _events(env, mid, kind):
    monitor = env.handler._tops_monitors[mid]
    return [e for e in monitor["events"] if e["type"] == kind]


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
    assert env.pnode.types() == sorted(
        ["WorkItemStateChange", "NodeProgressUpdate", "CookStart", "CookComplete", "CookError"])
    # The graph context never delivers the item/progress events on H22, and its
    # CookStart is graph-wide; a single node keeps start and end on itself.
    assert env.ctx.added == []


def test_network_path_watches_each_child_and_the_context_for_cook_end(env):
    result = _call(env, "start", node=_NET)
    assert result["status"] == "monitoring"
    # The scheduler child is skipped: it is not a pdg.Node.
    assert sorted(result["nodes_monitored"]) == ["gen", "proc"]
    for child in (env.gen, env.pnode):
        assert child.types() == ["NodeProgressUpdate", "WorkItemStateChange"]
    assert env.ctx.types() == ["CookComplete", "CookError", "CookStart"]
    mid = result["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedSuccess, on=env.gen)
    _item(env, 2, ws.CookedSuccess)
    _state_change(env, 1, ws.CookedSuccess, on=env.gen)
    _state_change(env, 2, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.ctx)
    stopped = _call(env, "stop", node=_NET, monitor_id=mid)
    assert stopped["summary"]["completed"] == 2
    assert stopped["cook_state"] == "complete"
    assert len(env.ctx.removed) == 3 and len(env.gen.removed) == 2 and len(env.pnode.removed) == 2


def test_stop_removes_every_registered_handler(env):
    mid = _call(env, "start")["monitor_id"]
    handlers = [h for _fn, _e, h in env.pnode.added]
    assert len(handlers) == 5  # not vacuous: start must have registered
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

    started = _events(env, mid, "work_item_started")
    done = _events(env, mid, "work_item_completed")
    assert started and started[0]["item_id"] == 42
    assert done and done[0]["item_id"] == 42 and done[0]["frame"] == 42.0
    assert done[0]["duration_seconds"] == 1.5
    assert done[0]["output_path"] == "/tmp/out.0042.exr"
    status = _call(env, "status", monitor_id=mid)
    assert "callback_error" not in status
    assert status["cook_state"] == "cooking"


def test_failed_item_error_text_comes_from_the_item_log(env):
    """H22.0.400: the failing event's message is '' and lastError does not exist."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 7, ws.CookedFail, logMessages=(
        "[09:12:58.931] ERROR: Failed to run script:\n"
        "RuntimeError: probe failure\n"))
    _state_change(env, 7, ws.CookedFail, message="")
    failed = _events(env, mid, "work_item_failed")
    assert "RuntimeError: probe failure" in failed[0]["error_message"]
    assert _call(env, "status", monitor_id=mid)["summary"]["failed"] == 1


def test_failed_item_prefers_a_non_empty_event_message(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 8, ws.CookedFail, logMessages="noise")
    _state_change(env, 8, ws.CookedFail, message="scheduler lost the item")
    assert _events(env, mid, "work_item_failed")[0]["error_message"] == "scheduler lost the item"


def test_a_cook_with_a_failed_item_ends_complete_with_errors(env):
    """No CookError fires for an item failure on H22; CookComplete still does."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedSuccess)
    _item(env, 2, ws.CookedFail)
    _state_change(env, 1, ws.CookedSuccess)
    _state_change(env, 2, ws.CookedFail)
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "complete_with_errors"


def test_cook_error_is_not_overwritten_by_cook_complete(env):
    mid = _call(env, "start")["monitor_id"]
    _cook_event(env, "CookError", env.pnode, message="scheduler: no local scheduler")
    err = _events(env, mid, "cook_error")
    assert err and err[0]["message"] == "scheduler: no local scheduler"
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "stop", monitor_id=mid)["cook_state"] == "error"


def test_cached_and_cancelled_items_are_counted(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedSuccess)
    _item(env, 2, ws.CookedCache)
    _item(env, 3, ws.CookedCancel)
    _state_change(env, 1, ws.CookedSuccess)
    _state_change(env, 2, ws.CookedCache)
    _state_change(env, 3, ws.CookedCancel)
    _progress(env)

    status = _call(env, "status", monitor_id=mid)
    assert status["summary"] == {"completed": 1, "cached": 1, "failed": 0,
                                 "cancelled": 1, "total_processed": 3}
    assert _events(env, mid, "work_item_cancelled")
    cached = [e for e in _events(env, mid, "work_item_completed") if e.get("cached")]
    assert cached and cached[0]["item_id"] == 2
    row = _events(env, mid, "cook_progress")[-1]
    assert row["processed"] == 3 and row["total"] == 3 and row["percent"] == 100.0


def test_cook_end_always_gets_a_final_progress_row(env):
    """H22 coalesces NodeProgressUpdate when items finish together."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    for i in range(5):
        _item(env, i, ws.CookedSuccess)
    _progress(env)  # the only update H22 sent, before anything finished
    for i in range(5):
        _state_change(env, i, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    rows = _events(env, mid, "cook_progress")
    assert rows[0]["percent"] == 0.0
    assert rows[-1]["processed"] == 5 and rows[-1]["percent"] == 100.0


def test_a_second_cook_starts_its_progress_and_state_over(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    for i in range(3):
        _item(env, i, ws.CookedSuccess)
        _state_change(env, i, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "complete"

    # Second cook of the same 3 items, opened by the context's CookStart.
    _cook_event(env, "CookStart", env.pnode)
    status = _call(env, "status", monitor_id=mid)
    # Started, nothing cooked yet: the previous cook's result still shows.
    assert status["cook_state"] == "starting"
    assert status["last_cook"]["completed"] == 3
    _progress(env)
    first = _events(env, mid, "cook_progress")[-1]
    assert first["processed"] == 0 and first["percent"] == 0.0
    _state_change(env, 0, ws.CookedSuccess)
    _progress(env)
    row = _events(env, mid, "cook_progress")[-1]
    assert row["processed"] == 1 and row["total"] == 3
    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "cooking"
    assert status["last_cook"]["completed"] == 1
    assert status["summary"]["completed"] == 4  # the summary spans both cooks
    _cook_event(env, "CookComplete", env.pnode)
    ends = _events(env, mid, "cook_complete")
    assert len(ends) == 2 and ends[-1]["processed"] == 1 and ends[-1]["cook_state"] == "complete"


def test_events_trailing_a_finished_cook_do_not_reopen_it(env):
    """A late progress tick or a Dirty/Waiting change is not a new cook."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 0, ws.CookedSuccess)
    _state_change(env, 0, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    _progress(env)                      # trailing tick
    _state_change(env, 0, _Member("Dirty"))   # a dirty with no cook behind it
    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "complete"
    assert status["last_cook"]["completed"] == 1


def test_a_cooking_item_after_a_finished_cook_opens_a_new_one(env):
    """Fallback boundary when no CookStart was seen."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 0, ws.CookedSuccess)
    _state_change(env, 0, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    _state_change(env, 0, ws.Cooking)
    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "cooking" and status["last_cook"]["completed"] == 0


def test_cook_error_sticks_through_cancelled_items(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedCancel)
    _cook_event(env, "CookError", env.pnode, message="scheduler died")
    _state_change(env, 1, ws.CookedCancel)
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "error"


def test_a_cook_with_only_cancelled_items_is_not_complete(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 1, ws.CookedCancel)
    _state_change(env, 1, ws.CookedCancel)
    _cook_event(env, "CookComplete", env.pnode)
    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "complete_with_errors"
    done = _events(env, mid, "cook_complete")[-1]
    assert done["processed"] == 1 and done["total"] == 1


def test_one_cook_ends_once_even_if_cook_complete_repeats(env):
    mid = _call(env, "start")["monitor_id"]
    _cook_event(env, "CookComplete", env.pnode)
    _cook_event(env, "CookComplete", env.pnode)
    assert len(_events(env, mid, "cook_complete")) == 1


def test_force_stop_drops_a_monitor_whose_handler_will_not_detach(env):
    mid = _call(env, "start")["monitor_id"]

    def _stuck(handler):
        raise RuntimeError("node deleted")

    env.pnode.removeEventHandler = _stuck
    assert _call(env, "stop", monitor_id=mid)["status"] == "stop_incomplete"
    forced = _call(env, "stop", monitor_id=mid, force=True)
    assert forced["status"] == "dropped_with_handlers_attached"
    assert forced["handlers_still_attached"] == 5
    assert mid not in env.handler._tops_monitors
    # The path can be monitored again.
    assert _call(env, "start")["status"] == "monitoring"


def test_second_start_on_the_same_node_attaches_nothing_new(env):
    first = _call(env, "start")
    second = _call(env, "start")
    assert second["status"] == "already_monitoring"
    assert second["monitor_id"] == first["monitor_id"]
    assert len(env.pnode.added) == 5
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
    assert len(env.pnode.removed) == 5


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


def test_a_handler_that_will_not_detach_keeps_the_monitor_for_a_retry(env):
    mid = _call(env, "start")["monitor_id"]
    calls = []
    real_remove = env.pnode.removeEventHandler

    def _flaky_remove(handler):
        calls.append(handler)
        if len(calls) == 1:
            raise RuntimeError("still cooking")
        real_remove(handler)

    env.pnode.removeEventHandler = _flaky_remove
    stopped = _call(env, "stop", monitor_id=mid)
    # One failure is reported, the rest were still removed, and the monitor
    # stays so the same id can finish the job.
    assert stopped["status"] == "stop_incomplete"
    assert len(stopped["handler_removal_errors"]) == 1
    assert "still cooking" in stopped["handler_removal_errors"][0]
    assert len(calls) == 5 and len(env.pnode.removed) == 4
    assert mid in env.handler._tops_monitors

    retried = _call(env, "stop", monitor_id=mid)
    assert retried["status"] == "stopped"
    assert len(env.pnode.removed) == 5
    assert mid not in env.handler._tops_monitors


def test_a_generate_only_pass_keeps_the_last_real_cook(env):
    """H22 fires CookStart/CookComplete for generateStaticWorkItems with only
    Undefined->Uncooked transitions; that is not a cook of this node."""
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _cook_event(env, "CookStart", env.pnode)
    for i in range(5):
        _item(env, i, ws.CookedSuccess)
        _state_change(env, i, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)

    _cook_event(env, "CookStart", env.pnode)
    for i in range(5):
        _state_change(env, i, _Member("Uncooked"))
    _cook_event(env, "CookComplete", env.pnode)

    status = _call(env, "status", monitor_id=mid)
    assert status["cook_state"] == "complete"
    assert status["last_cook"]["completed"] == 5
    ends = _events(env, mid, "cook_complete")
    assert [e["cook_state"] for e in ends] == ["complete", "nothing_cooked"]


def test_nothing_cooked_before_any_real_cook_says_so(env):
    mid = _call(env, "start")["monitor_id"]
    _cook_event(env, "CookStart", env.pnode)
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "nothing_cooked"


def test_a_new_cook_clears_a_previous_error(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _cook_event(env, "CookError", env.pnode, message="scheduler died")
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "error"
    _cook_event(env, "CookStart", env.pnode)
    _item(env, 1, ws.CookedSuccess)
    _state_change(env, 1, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    assert _call(env, "status", monitor_id=mid)["cook_state"] == "complete"


def test_network_includes_subnet_nodes_and_names_a_nested_graph(env):
    inner = _FakePdgNode(env.ctx, "inside_subnet")
    other_ctx = _FakeContext()
    nested = _FakePdgNode(other_ctx, "nested_topnet_node")
    env.extra[:] = [
        # H22: the subnet node itself answers getPDGNode() with the pdg.Node of
        # the inner node feeding its output (live probe 2026-10-07).
        types.SimpleNamespace(getPDGNode=lambda: inner, path=lambda: _NET + "/subnet1"),
        types.SimpleNamespace(getPDGNode=lambda: inner, path=lambda: _NET + "/subnet1/inside_subnet"),
        types.SimpleNamespace(getPDGNode=lambda: nested, path=lambda: _NET + "/topnet2/nested_topnet_node"),
    ]
    result = _call(env, "start", node=_NET)
    assert sorted(result["nodes_monitored"]) == ["gen", "inside_subnet", "proc"]  # once each
    assert len(inner.added) == 2
    assert result["nodes_unmonitored"] == [_NET + "/topnet2/nested_topnet_node"]
    assert nested.added == []
    mid = result["monitor_id"]
    ws = env.pdg.workItemState
    _item(env, 9, ws.CookedFail, on=inner, logMessages="ERROR: inside the subnet")
    _state_change(env, 9, ws.CookedFail, on=inner)
    _cook_event(env, "CookComplete", env.ctx)
    status = _call(env, "status", node=_NET, monitor_id=mid)
    assert status["cook_state"] == "complete_with_errors"
    assert status["last_cook"]["failed"] == 1  # counted once
    assert len(_events(env, mid, "work_item_failed")) == 1


def test_a_generate_only_pass_shows_starting_not_an_empty_cook(env):
    mid = _call(env, "start")["monitor_id"]
    ws = env.pdg.workItemState
    _cook_event(env, "CookStart", env.pnode)
    _item(env, 0, ws.CookedSuccess)
    _state_change(env, 0, ws.CookedSuccess)
    _cook_event(env, "CookComplete", env.pnode)
    _cook_event(env, "CookStart", env.pnode)          # a generate begins
    _state_change(env, 0, _Member("Uncooked"))
    mid_pass = _call(env, "status", monitor_id=mid)
    assert mid_pass["cook_state"] == "starting"
    assert mid_pass["last_cook"]["completed"] == 1    # not zeroed mid-pass
