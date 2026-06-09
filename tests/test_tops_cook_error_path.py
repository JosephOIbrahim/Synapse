"""C9 (CTO Remediation Mile 2) — tops_cook_node error path returns a structured
error instead of crashing on an undefined `logger`.

cook.py referenced `logger` at the cook-failure branch but never imported it, so a
real PDG cook failure raised `NameError: name 'logger' is not defined` and masked
the actual error (the structured {status:'error', ...} dict at the end was never
returned). C9 imports `logger` from `._common`. This pins the failure path.
"""

import importlib
import logging
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

# Minimal fakes so `import synapse.server.handlers` succeeds standalone.
sys.modules.setdefault("hou", ModuleType("hou"))
_hde = sys.modules.setdefault("hdefereval", ModuleType("hdefereval"))
if not hasattr(_hde, "executeInMainThreadWithResult"):
    _hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))


def test_cook_module_defines_logger():
    cook = importlib.import_module("synapse.server.handlers_tops.cook")
    assert isinstance(getattr(cook, "logger", None), logging.Logger)  # NameError now impossible


def test_cook_failure_returns_structured_error_not_nameerror(monkeypatch):
    fake_hde = ModuleType("hdefereval")
    fake_hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)

    from synapse.server.handlers import SynapseHandler

    class _Node:
        def getPDGNode(self):
            return SimpleNamespace(workItems=[1, 2])
        def cook(self, block=False):
            raise RuntimeError("cook boom")

    # Patch the handler's ACTUAL execution namespace (__globals__ of the function,
    # which the nested _run closure reads) — identity-proof against any global `hou`
    # a prior suite test left bound, or a re-imported cook module in sys.modules.
    g = SynapseHandler._handle_tops_cook_node.__globals__
    monkeypatch.setitem(g, "hou", SimpleNamespace(node=lambda _p: _Node()))
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)

    h = SynapseHandler()
    res = h._handle_tops_cook_node({"node": "/obj/topnet1/cook", "blocking": True})

    assert res["status"] == "error"          # structured error, not a NameError crash
    assert "cook boom" in res["error"]       # the REAL cook error survives
    assert res["work_items"] == 2
