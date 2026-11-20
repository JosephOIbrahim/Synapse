"""Wave 0 / CONDUCTOR-1 + CONDUCTOR-6 — the PDG cook must not park Houdini.

CONDUCTOR-1 predicate
---------------------
tops_cook_node returns within 2s with a task id while the cook runs; Houdini
stays responsive; a completion event reports the final state; cancel stops it;
a fake-graph test asserts no failed result before completion and that cancel
never dirties a finished node.

CONDUCTOR-6 predicate
---------------------
The single-node cancel branch calls the PDG cancel path and reports "cancelled"
only after reading state back, or returns an explicit cannot-cancel; dirty is
never called and the reported readback matches the reply.

These tests drive the real handlers against fakes: the fake ``pdg`` module
mirrors the H22 surface CONDUCTOR-1/6 rely on (pdg.EventType.CookComplete /
CookError, pdg.Node.addEventHandler / removeEventHandler, pdg.Node.cancel,
pdg.WorkItem.cancel). Live behaviour (UI responsiveness, a real local-scheduler
cook) still needs Houdini — see the node receipt.
"""

import sys
import threading
import time
import types
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Stubs are installed per-test (never at import) so this file cannot leak a
# half-populated ``pdg`` module into the rest of the suite.
# ---------------------------------------------------------------------------

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server.handlers_tops import cook as cook_mod  # noqa: E402


class _EventType:
    """The two pdg.EventType members the cook task bridge registers."""
    CookComplete = "CookComplete"
    CookError = "CookError"


class _WorkItemState:
    """The pdg.workItemState members the TOPS handlers read."""
    CookedSuccess = "CookedSuccess"
    CookedFail = "CookedFail"
    Cooking = "Cooking"
    Scheduled = "Scheduled"
    Uncooked = "Uncooked"
    CookedCancel = "CookedCancel"


def _pdg_stub():
    mod = types.ModuleType("pdg")
    mod.EventType = _EventType
    mod.workItemState = _WorkItemState
    return mod


def _hdefereval_stub():
    mod = types.ModuleType("hdefereval")
    mod.executeDeferred = lambda fn, *a, **k: fn()
    mod.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    return mod



# ---------------------------------------------------------------------------
# Fakes — H22-shaped pdg/hou surfaces, nothing more
# ---------------------------------------------------------------------------

class _State:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class _WorkItem:
    def __init__(self, name="wi0", state="Cooking"):
        self.name = name
        self.state = _State(state)
        self.cancel_calls = 0

    def cancel(self):
        # pdg.WorkItem.cancel: "Cancels the work item, if it is cooking"
        self.cancel_calls += 1
        if self.state.name == "Cooking":
            self.state = _State("CookedCancel")


class _PdgNode:
    def __init__(self, items=None):
        self.workItems = list(items or [])
        self.dirty_calls = []
        self.cancel_calls = 0
        self.handlers = []
        self.on_cancel = None

    def dirty(self, upstream):
        self.dirty_calls.append(upstream)

    def cancel(self):
        self.cancel_calls += 1
        if self.on_cancel is not None:
            self.on_cancel()
            return
        for wi in self.workItems:
            if wi.state.name == "Cooking":
                wi.state = _State("CookedCancel")

    def addEventHandler(self, fn, etype):
        wrapper = SimpleNamespace(fn=fn, etype=etype)
        self.handlers.append(wrapper)
        return wrapper

    def removeEventHandler(self, wrapper):
        if wrapper in self.handlers:
            self.handlers.remove(wrapper)

    def fire(self, etype, message=""):
        for wrapper in list(self.handlers):
            if wrapper.etype == etype:
                wrapper.fn(SimpleNamespace(type=etype, message=message))


class _GraphContext:
    """pdg.GraphContext-shaped emitter (the R8 registration scope)."""

    def __init__(self):
        self.handlers = []

    def addEventHandler(self, fn, etype):
        wrapper = SimpleNamespace(fn=fn, etype=etype)
        self.handlers.append(wrapper)
        return wrapper

    def removeEventHandler(self, wrapper):
        if wrapper in self.handlers:
            self.handlers.remove(wrapper)

    def fire(self, etype, message=""):
        for wrapper in list(self.handlers):
            if wrapper.etype == etype:
                wrapper.fn(SimpleNamespace(type=etype, message=message))


class _Cat:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _NType:
    def __init__(self, cat):
        self._cat = _Cat(cat)

    def category(self):
        return self._cat


class _TopNode:
    def __init__(self, path, pdg_node, category="Top", cook_state="Cooking"):
        self._path = path
        self._pdg = pdg_node
        self._category = category
        self.cook_state = cook_state
        self.kick_blocks = []
        self.generate_calls = 0
        self.on_kick = None
        self.ctx = None

    def path(self):
        return self._path

    def name(self):
        return self._path.rsplit("/", 1)[-1]

    def type(self):
        return _NType(self._category)

    def getPDGNode(self):
        return self._pdg

    def getCookState(self):
        return _State(self.cook_state)

    def getPDGGraphContext(self):
        return self.ctx

    def generateStaticItems(self):
        self.generate_calls += 1

    def cookWorkItems(self, block=False, **kwargs):
        self.kick_blocks.append(block)
        if self.on_kick is not None:
            self.on_kick(self)


class _Hou:
    def __init__(self, nodes):
        self.nodes = nodes

    def node(self, path):
        return self.nodes.get(path)


@pytest.fixture
def install(monkeypatch):
    """Point the real handlers at fake hou/pdg/hdefereval, per test."""
    def _install(nodes):
        fake_hou = _Hou(nodes)
        g = SynapseHandler._handle_tops_cook_node.__globals__
        monkeypatch.setitem(g, "hou", fake_hou)
        monkeypatch.setitem(g, "HOU_AVAILABLE", True)
        monkeypatch.setitem(sys.modules, "pdg", _pdg_stub())
        monkeypatch.setitem(sys.modules, "hdefereval", _hdefereval_stub())
        return fake_hou
    return _install


def _cook(h, path, **extra):
    return h._handle_tops_cook_node({"node": path, **extra})


# ---------------------------------------------------------------------------
# CONDUCTOR-1 — non-blocking task model
# ---------------------------------------------------------------------------

def test_cook_returns_task_id_immediately_while_cook_runs(install):
    """Predicate: tops_cook_node returns within 2s with a task id while the
    cook runs. Nothing fires a completion event — the cook is still going."""
    pdg = _PdgNode([_WorkItem()])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    t0 = time.monotonic()
    res = _cook(h, "/obj/topnet1/gen1")
    elapsed = time.monotonic() - t0

    assert elapsed < 2.0, f"tops_cook_node took {elapsed:.2f}s while the cook runs"
    assert res["status"] == "cooking"
    assert res["task_id"].startswith("cook-")
    assert res["event_bridge"] is True
    assert res["error"] is None
    assert node.kick_blocks == [False], "the cook must be kicked non-blocking"


def test_no_failed_result_before_completion_then_event_reports_final_state(install):
    """Predicate: no failed result before completion; the completion event
    reports the final state on the task."""
    wi = _WorkItem()
    pdg = _PdgNode([wi])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")

    # Not finished yet: a "failed" here would be the old 60s false failure.
    assert started["status"] == "cooking"
    assert started.get("error") is None

    # A cook-level CookComplete while THIS node still has a cooking item is a
    # sibling's event — it must not finish our task.
    pdg.fire(_EventType.CookComplete)
    still = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert still["status"] == "cooking"

    wi.state = _State("CookedSuccess")
    node.cook_state = "Cooked"
    pdg.fire(_EventType.CookComplete)          # PDG worker thread in production

    polled = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert polled["status"] == "cooked"
    assert polled["event"] == "CookComplete"
    assert polled["error"] is None
    # Handlers detach once the task is terminal (no leaked PDG callbacks).
    assert pdg.handlers == []


def test_cook_error_event_reports_failed_with_its_message(install):
    wi = _WorkItem()
    pdg = _PdgNode([wi])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")
    wi.state = _State("CookedFail")            # an errored item is terminal
    node.cook_state = "Failed"
    pdg.fire(_EventType.CookError, "work item 0 exploded")

    polled = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert polled["status"] == "failed"
    assert polled["event"] == "CookError"
    assert "exploded" in polled["error"]


def test_graph_context_is_a_registration_backstop(install):
    """The R8 graph-level emitter is registered too; either scope resolves the
    task and both detach on completion."""
    wi = _WorkItem()
    pdg = _PdgNode([wi])
    ctx = _GraphContext()
    node = _TopNode("/obj/topnet1/gen1", pdg)
    node.ctx = ctx
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")

    assert started["event_bridge"] is True
    assert len(pdg.handlers) == 2      # node-scoped (precise)
    assert len(ctx.handlers) == 2      # graph-scoped (R8 backstop)

    wi.state = _State("CookedSuccess")
    node.cook_state = "Cooked"
    ctx.fire(_EventType.CookComplete)  # the R8 path

    polled = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert polled["status"] == "cooked"
    assert pdg.handlers == [] and ctx.handlers == []


def test_blocking_waits_off_main_thread_and_completes(install, monkeypatch):
    """blocking=True waits OUTSIDE the main thread; the completion event wakes
    the waiter and the final state is reported."""
    monkeypatch.setattr(cook_mod, "_on_main_thread", lambda: False)

    pdg = _PdgNode([_WorkItem()])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    def _fire_soon():
        pdg.workItems[0].state = _State("CookedSuccess")
        node.cook_state = "Cooked"
        pdg.fire(_EventType.CookComplete)

    node.on_kick = lambda _n: threading.Timer(0.05, _fire_soon).start()

    h = SynapseHandler()
    res = h._handle_tops_cook_node(
        {"node": "/obj/topnet1/gen1", "blocking": True, "blocking_timeout": 2.0})

    assert res["status"] == "cooked"
    assert res["wait_timed_out"] is False


def test_blocking_timeout_is_a_still_cooking_receipt_not_a_failure(install, monkeypatch):
    """Predicate: bound the wait without reporting a false failure."""
    monkeypatch.setattr(cook_mod, "_on_main_thread", lambda: False)

    pdg = _PdgNode([_WorkItem()])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = h._handle_tops_cook_node(
        {"node": "/obj/topnet1/gen1", "blocking": True, "blocking_timeout": 0.05})

    assert started["status"] == "cooking"
    assert started["wait_timed_out"] is True
    assert started["task_id"].startswith("cook-")
    assert "not a failure" in started["note"]
    assert started.get("error") is None


def test_blocking_from_main_thread_never_waits(install, monkeypatch):
    """A blocking request that arrives ON the main thread must not park the UI."""
    monkeypatch.setattr(cook_mod, "_on_main_thread", lambda: True)

    pdg = _PdgNode([_WorkItem()])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    res = h._handle_tops_cook_node(
        {"node": "/obj/topnet1/gen1", "blocking": True, "blocking_timeout": 30.0})

    assert res["status"] == "cooking"
    assert res["wait_skipped"] == "main_thread"
    assert node.kick_blocks == [False]


def test_immediate_readback_reports_cooked_when_cook_already_finished(install):
    """A tiny/all-cached graph finishes on the kick: the immediate readback is
    reported truthfully instead of a stale 'cooking'."""
    pdg = _PdgNode([_WorkItem(state="CookedSuccess")])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})
    node.on_kick = lambda n: setattr(n, "cook_state", "Cooked")

    h = SynapseHandler()
    res = _cook(h, "/obj/topnet1/gen1")

    assert res["status"] == "cooked"
    assert res["event"] == "state_readback"
    assert res["error"] is None


def test_poll_readback_finishes_when_events_miss(install):
    """A missed event still resolves: polling reads hou.TopNode.getCookState()."""
    pdg = _PdgNode([_WorkItem(state="CookedSuccess")])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")
    assert started["status"] == "cooking"

    node.cook_state = "Cooked"                 # no event ever fired
    polled = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert polled["status"] == "cooked"
    assert polled["event"] == "state_readback"


def test_poll_unknown_task_is_an_explicit_error(install):
    install({})
    h = SynapseHandler()
    with pytest.raises(ValueError, match="No cook task"):
        h._handle_tops_cook_node({"task_id": "cook-doesnotexist"})


def test_tops_cook_node_is_in_known_slow_tools():
    """CONDUCTOR-1: the panel preflight flags the PDG graph-context touch."""
    from synapse.panel.bridge_adapter import _KNOWN_SLOW_TOOLS
    assert "tops_cook_node" in _KNOWN_SLOW_TOOLS


# ---------------------------------------------------------------------------
# CONDUCTOR-6 — cancel through the PDG path, read back, never dirty
# ---------------------------------------------------------------------------

def test_cancel_calls_pdg_cancel_and_reports_only_after_readback(install):
    wi = _WorkItem(state="Cooking")
    pdg = _PdgNode([wi])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")

    res = h._handle_tops_cancel_cook({"node": "/obj/topnet1/gen1"})

    assert res["status"] == "cancelled"
    assert res["cancel_api"] == "pdg.Node.cancel"
    assert res["readback"] == {"CookedCancel": 1}
    assert res["cooking_remaining"] == 0
    assert pdg.cancel_calls == 1
    assert pdg.dirty_calls == [], "cancel must never dirty the node"

    # The task record carries the same outcome: a late event cannot relabel it.
    pdg.fire(_EventType.CookComplete)
    polled = h._handle_tops_cook_node({"task_id": started["task_id"]})
    assert polled["status"] == "cancelled"
    assert polled["cancel_api"] == "pdg.Node.cancel"
    assert pdg.dirty_calls == []


def test_cancel_reports_requested_when_readback_still_cooking(install):
    """The PDG cancel is asynchronous: without a state change the reply says
    cancel_requested, never a false 'cancelled'."""
    pdg = _PdgNode([_WorkItem(state="Cooking")])
    pdg.on_cancel = lambda: None  # cancel accepted; items still cooking at readback
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    res = h._handle_tops_cancel_cook({"node": "/obj/topnet1/gen1"})

    assert res["status"] == "cancel_requested"
    assert res["readback"] == {"Cooking": 1}
    assert res["cooking_remaining"] == 1
    assert pdg.dirty_calls == []


def test_cancel_never_dirties_a_finished_node(install):
    """Predicate: cancel never dirties a finished node."""
    items = [_WorkItem(state="CookedSuccess"), _WorkItem(state="CookedFail")]
    pdg = _PdgNode(items)
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    res = h._handle_tops_cancel_cook({"node": "/obj/topnet1/gen1"})

    assert res["status"] == "not_cooking"
    assert res["readback"] == {"CookedFail": 1, "CookedSuccess": 1}
    assert pdg.dirty_calls == []
    assert pdg.cancel_calls == 0
    assert all(wi.cancel_calls == 0 for wi in items)


def test_cancel_returns_cannot_cancel_when_no_pdg_api_reaches_the_node(install):
    """Predicate: where no cancel API can reach the node, the reply is an
    explicit cannot-cancel — never dirty()."""
    wi = _WorkItem(state="Cooking")
    pdg = _PdgNode([wi])
    pdg.cancel = None      # no pdg.Node.cancel
    wi.cancel = None       # no pdg.WorkItem.cancel
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    res = h._handle_tops_cancel_cook({"node": "/obj/topnet1/gen1"})

    assert res["status"] == "cannot_cancel"
    assert res["readback"] == {"Cooking": 1}
    assert pdg.dirty_calls == []


def test_cancel_falls_back_to_the_pdg_handle_when_the_marshal_times_out(install, monkeypatch):
    """A blocking cook can hold the main thread; cancel must still reach the
    node through the pdg-only handle captured at cook start."""
    pdg = _PdgNode([_WorkItem(state="Cooking")])
    node = _TopNode("/obj/topnet1/gen1", pdg)
    install({"/obj/topnet1/gen1": node})

    h = SynapseHandler()
    started = _cook(h, "/obj/topnet1/gen1")  # records the pdg handle on the task

    from synapse.server.main_thread import MainThreadTimeout

    def _timed_out(fn, timeout=None):
        raise MainThreadTimeout("Houdini's main thread didn't respond in time")

    monkeypatch.setattr(cook_mod, "_run_in_main_thread_pdg", _timed_out)

    res = h._handle_tops_cancel_cook({"task_id": started["task_id"]})

    assert res["marshal_timed_out"] is True
    assert res["status"] == "cancelled"
    assert res["cancel_api"] == "pdg.Node.cancel"
    assert res["readback"] == {"CookedCancel": 1}
    assert pdg.dirty_calls == []


def test_cancel_needs_node_or_task_id(install):
    install({})
    h = SynapseHandler()
    with pytest.raises(ValueError, match="needs 'node' or a known 'task_id'"):
        h._handle_tops_cancel_cook({})
