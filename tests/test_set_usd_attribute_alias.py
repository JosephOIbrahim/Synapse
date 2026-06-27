"""set_usd_attribute: the ``attribute_name`` payload-key alias.

FINDING 4 (HIGH) -- the v5.17.0 set_usd_attribute name-space fix was inert
because the MCP schema (houdini_get/set_usd_attribute), render_recipes.py, and
routing/planner.py all send the key ``attribute_name``, which was NOT in
``PARAM_ALIASES["usd_attribute"]``. ``resolve_param`` therefore RAISED before
any hou code ran, so the corrected ``inputs:*`` names never reached
``prim.GetAttribute().Set()``.

Fix: ``attribute_name`` added to ``PARAM_ALIASES["usd_attribute"]``
(core/aliases.py). This file pins that:

  * unit -- ``resolve_param`` resolves both the new ``attribute_name`` key and
    the back-compat ``usd_attribute`` key to the same value, and the reverse
    alias map has no collision (``attribute_name`` -> ``usd_attribute`` only);
  * end-to-end -- driving the ``_handle_set_usd_attribute`` dispatch with
    ``{"prim_path": ..., "attribute_name": "inputs:exposure", "value": 5.0}``
    reaches the handler body (the pythonscript-LOP code carries
    ``attr_name == "inputs:exposure"``) and does NOT raise the missing-param
    error -- and the old ``usd_attribute`` key still works.

Headless. Handler-module globals are patched directly -- sys.modules residency
is order-fragile (sibling convention, docs/HARDENING_RUN_2026-06-10.md Mile 3).
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.core.aliases import (  # noqa: E402
    PARAM_ALIASES,
    _REVERSE_ALIASES,
    resolve_param,
)
from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402


# ---------------------------------------------------------------------------
# Unit: alias resolution + collision-freedom
# ---------------------------------------------------------------------------


def test_attribute_name_is_registered_alias():
    assert "attribute_name" in PARAM_ALIASES["usd_attribute"]


def test_resolve_param_new_key():
    # The bug: this key used to RAISE because it wasn't an alias.
    assert (
        resolve_param({"attribute_name": "inputs:exposure"}, "usd_attribute")
        == "inputs:exposure"
    )


def test_resolve_param_old_key_back_compat():
    assert (
        resolve_param({"usd_attribute": "inputs:exposure"}, "usd_attribute")
        == "inputs:exposure"
    )


def test_reverse_map_has_no_collision():
    # attribute_name must map to usd_attribute and nothing else.
    assert _REVERSE_ALIASES["attribute_name"] == "usd_attribute"


# ---------------------------------------------------------------------------
# End-to-end: the dispatch reaches the handler body without the missing-param
# raise, carrying attr_name == "inputs:exposure".
# ---------------------------------------------------------------------------


class _FakeOperationFailed(Exception):
    pass


class _UndoGroup:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _CapturingParm:
    def __init__(self, store):
        self._store = store

    def set(self, v):
        self._store["code"] = v


@pytest.fixture()
def wired(monkeypatch):
    """Fake hou on the USD handler module + inline run_on_main.

    Returns (handler, py_lop, code_store).
    """
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: _UndoGroup()),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True, raising=False)
    # Isolate from the shared display-wiring helper.
    monkeypatch.setattr(husd, "_wire_display", lambda *a, **k: {})

    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())

    code_store = {}
    py_lop = MagicMock(name="py_lop")
    py_lop.path.return_value = "/stage/set_attr"
    py_lop.parm.return_value = _CapturingParm(code_store)
    parent = MagicMock()
    parent.createNode.return_value = py_lop
    lop = MagicMock()
    lop.parent.return_value = parent

    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), py_lop, code_store


def test_dispatch_with_attribute_name_reaches_handler(wired):
    handler, py_lop, code = wired
    # The exact payload the MCP schema / planner emit -- key is attribute_name.
    result = handler._handle_set_usd_attribute({
        "prim_path": "/lights/x",
        "attribute_name": "inputs:exposure",
        "value": 5.0,
    })
    # No missing-param raise -- we got a real result and a cooked node.
    py_lop.cook.assert_called_once_with(force=True)
    assert result["attribute"] == "inputs:exposure"
    assert result["value"] == 5.0
    # attr_name flowed into the emitted pythonscript-LOP code unchanged.
    assert "'inputs:exposure'" in code["code"]


def test_dispatch_with_old_usd_attribute_key_still_works(wired):
    handler, _, code = wired
    result = handler._handle_set_usd_attribute({
        "prim_path": "/lights/x",
        "usd_attribute": "inputs:exposure",
        "value": 5.0,
    })
    assert result["attribute"] == "inputs:exposure"
    assert "'inputs:exposure'" in code["code"]


def test_missing_attribute_key_still_raises(wired):
    handler, _, _ = wired
    # No attribute key at all -> the helpful missing-param ValueError.
    with pytest.raises(ValueError, match="usd_attribute"):
        handler._handle_set_usd_attribute({
            "prim_path": "/lights/x",
            "value": 5.0,
        })
