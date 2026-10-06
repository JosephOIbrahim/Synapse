"""F03: a failed PDG cook whose rollback raised must not claim 'pdg_rolled_back'.

On 22.0.400 ``dirtyAllTasks(remove_files=...)`` raises TypeError (the live
signature is ``dirtyAllTasks(self, remove_outputs)``), so ``dirtied`` stays
False. The IntegrityBlock must then record 'rollback_incomplete', matching the
'TASKS NOT DIRTIED' message in the same branch. Fakes mirror
tests/test_pdg_cook_timeout.py.
"""
import sys
import types
from types import SimpleNamespace

import pytest

import shared.bridge as b
from shared.bridge import LosslessExecutionBridge, Operation
from shared.types import AgentID


class _FakeGraphContext:
    def __init__(self):
        self._handlers = []

    def addEventHandler(self, fn, etype):
        self._handlers.append((fn, etype))
        return SimpleNamespace(fn=fn, etype=etype)

    def removeEventHandler(self, wrapper):
        pass

    def cancelCook(self):
        pass


class _FakeTopNode:
    def __init__(self, path):
        self._path = path
        self.ctx = _FakeGraphContext()
        self.dirty_called = False

    def executeGraph(self):
        for fn, etype in self.ctx._handlers:
            if etype == "CookError":
                fn(SimpleNamespace(type="CookError", message="work item failed"))

    def dirtyAllTasks(self, remove_outputs):  # live 22.0.400 signature
        self.dirty_called = True

    def getPDGGraphContext(self):
        return self.ctx


class _FakeHou:
    def __init__(self, top):
        self._top = top

    def node(self, path):
        return self._top if path == self._top._path else None


class _FakeHdefereval:
    def executeInMainThreadWithResult(self, fn):
        return fn()


def _fake_pdg_module():
    mod = types.ModuleType("pdg")
    mod.EventType = SimpleNamespace(CookComplete="CookComplete", CookError="CookError")
    return mod


@pytest.mark.asyncio
async def test_failed_rollback_records_rollback_incomplete(monkeypatch):
    top = _FakeTopNode("/obj/topnet1")
    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _FakeHou(top))
    monkeypatch.setattr(b, "hdefereval", _FakeHdefereval())
    monkeypatch.setattr(b, "_GATES_AVAILABLE", False)
    monkeypatch.setitem(sys.modules, "pdg", _fake_pdg_module())

    op = Operation(
        agent_id=AgentID.CONDUCTOR,
        operation_type="cook_pdg_chain",
        summary="test cook",
        fn=lambda **k: None,
        kwargs={"node_path": "/obj/topnet1", "cook_timeout": 5.0},
    )
    result = await LosslessExecutionBridge().execute_async(op)

    assert result.success is False
    assert top.dirty_called is False  # the call raised TypeError before entry
    assert result.integrity.delta_hash == "rollback_incomplete"
