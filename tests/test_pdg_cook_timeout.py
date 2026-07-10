"""R8-bounded: _execute_pdg_deferred must bound a stuck PDG cook.

A PDG cook that fires neither CookComplete nor CookError (stuck work item,
scheduler stall, a graph already cooking from another trigger) used to poll
``while not cook_complete.is_set(): await asyncio.sleep(0.25)`` FOREVER -- no
IntegrityBlock finalized, the operation never returned. The general
execute_async path has a 120s guard; the PDG path -- the longest op type --
did not.

These tests force the production path via monkeypatch (no real Houdini) and
assert: (1) a stuck cook times out via the ``cook_timeout`` kwarg, calls
graph_context.cancelCook(), dirties tasks with cache PRESERVED by default, and
returns a fail IntegrityBlock with delta_hash == 'pdg_timeout'; (2) a cook that
DOES fire CookComplete still succeeds (the new bound did not break the happy
path); (3) the default timeout constant is the 1800s backstop (pins it loud
against a silent tightening).
"""
import sys
import types
from types import SimpleNamespace

import pytest

import shared.bridge as b
from shared.bridge import (
    LosslessExecutionBridge,
    Operation,
    DEFAULT_COOK_TIMEOUT_S,
)
from shared.types import AgentID


class _FakeGraphContext:
    def __init__(self):
        self.cancel_called = False
        self.removed = []
        self._handlers = []  # (fn, etype) pairs the test can fire manually

    def addEventHandler(self, fn, etype):
        self._handlers.append((fn, etype))
        return SimpleNamespace(fn=fn, etype=etype)

    def removeEventHandler(self, wrapper):
        self.removed.append(wrapper)

    def cancelCook(self):
        self.cancel_called = True


class _FakeTopNode:
    def __init__(self, path):
        self._path = path
        self.ctx = _FakeGraphContext()
        self.executeGraph_called = False
        self.dirty_called = False
        self.dirty_remove = None

    def executeGraph(self):
        # Default: NO event fires -- simulates a stuck cook.
        self.executeGraph_called = True

    def dirtyAllTasks(self, remove_files=False):
        self.dirty_called = True
        self.dirty_remove = remove_files

    def getPDGGraphContext(self):
        return self.ctx


class _FakeHou:
    def __init__(self, top):
        self._top = top

    def node(self, path):
        return self._top if path == self._top._path else None


class _FakeHdefereval:
    def executeInMainThread(self, fn):
        fn()  # run synchronously so effects are observable

    def executeInMainThreadWithResult(self, fn):
        return fn()


def _fake_pdg_module():
    mod = types.ModuleType("pdg")

    class _EventType:
        CookComplete = "CookComplete"
        CookError = "CookError"

    mod.EventType = _EventType()
    return mod


def _patch_bridge(monkeypatch, top):
    """Force the production PDG path without a real Houdini."""
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _FakeHou(top))
    monkeypatch.setattr(b, "hdefereval", _FakeHdefereval())
    # Block the HumanGate consent path so an APPROVE-level cook_pdg_chain op
    # auto-approves instead of polling a real gate for GATE_TIMEOUT_APPROVE.
    monkeypatch.setattr(b, "_GATES_AVAILABLE", False)
    monkeypatch.setitem(sys.modules, "pdg", _fake_pdg_module())


def _cook_op(**extra_kwargs):
    return Operation(
        agent_id=AgentID.CONDUCTOR,
        operation_type="cook_pdg_chain",
        summary="test cook",
        fn=lambda **k: None,  # unused on the deferred path
        kwargs={"node_path": "/obj/topnet1", **extra_kwargs},
    )


@pytest.mark.asyncio
async def test_pdg_cook_timeout_bounds_poll_and_cancels(monkeypatch):
    top = _FakeTopNode("/obj/topnet1")
    _patch_bridge(monkeypatch, top)

    bridge = LosslessExecutionBridge()
    op = _cook_op(cook_timeout=0.5)

    result = await bridge.execute_async(op)

    assert result.success is False
    assert result.integrity is not None
    assert result.integrity.delta_hash == "pdg_timeout"
    assert result.integrity.operation_type == "cook_pdg_chain"
    # We actually exercised the deferred path (sanity).
    assert top.executeGraph_called is True
    # The stuck cook was cancelled on the main thread.
    assert top.ctx.cancel_called is True
    # Tasks dirtied so they recook, cache PRESERVED by default.
    assert top.dirty_called is True
    assert top.dirty_remove is False
    # Both event handlers were cleaned up (no leak).
    assert len(top.ctx.removed) == 2


@pytest.mark.asyncio
async def test_pdg_cook_completes_normally_not_bounded(monkeypatch):
    """Regression guard: a cook that DOES fire CookComplete succeeds and is not
    cut off by the new timeout bound."""
    top = _FakeTopNode("/obj/topnet1")

    def _fire_complete():
        # Called on the main thread (via hdefereval) -- fire the registered
        # CookComplete handler synchronously, exactly as PDG would.
        for fn, etype in top.ctx._handlers:
            if etype == "CookComplete":
                fn(SimpleNamespace(type="CookComplete", message=None))

    top.executeGraph = _fire_complete
    _patch_bridge(monkeypatch, top)

    bridge = LosslessExecutionBridge()
    op = _cook_op(cook_timeout=0.5)

    result = await bridge.execute_async(op)

    assert result.success is True
    assert result.integrity is not None
    assert result.integrity.delta_hash != "pdg_timeout"
    # A successful cook is not cancelled and tasks are not dirtied.
    assert top.ctx.cancel_called is False
    assert top.dirty_called is False


def test_pdg_cook_timeout_default_is_backstop():
    """The default is the 1800s backstop, not a performance target. Pin it so a
    silent tightening (e.g. dropping to the 120s general guard) fails loud."""
    assert DEFAULT_COOK_TIMEOUT_S == 1800.0