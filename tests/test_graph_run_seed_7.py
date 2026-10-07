"""F02: emitted pythonscript code must raise on a missing prim.

The embedded ``if prim:`` guard used to make a missing prim cook cleanly, so
the handler reported variant sets / modifications as authored when nothing
was. Exec the captured code against a stage whose GetPrimAtPath returns None.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

if "hou" not in sys.modules:  # defer to conftest's canonical hou resident
    sys.modules["hou"] = types.ModuleType("hou")
if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")
_hdefereval = sys.modules["hdefereval"]
if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()
if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
    _hdefereval.executeInMainThreadWithResult = lambda fn: fn()

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"
import pkgbootstrap  # noqa: E402

for _name, _path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
]:
    pkgbootstrap.ensure_package(_name, _path)
for _name, _fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
]:
    pkgbootstrap.load_module(_name, _fpath)

handlers_mod = sys.modules["synapse.server.handlers"]


@pytest.fixture
def handler_and_lop():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    lop_node = MagicMock()
    parent = MagicMock()
    lop_node.parent.return_value = parent
    py_lop = MagicMock()
    parent.createNode.return_value = py_lop
    h._resolve_lop_node = MagicMock(return_value=lop_node)
    return h, py_lop


def _exec_missing_prim(code):
    stage = MagicMock()
    stage.GetPrimAtPath.return_value = None
    fake_hou = MagicMock()
    fake_hou.pwd.return_value.editableStage.return_value = stage
    pxr = types.ModuleType("pxr")
    for sub in ("Usd", "Sdf", "UsdGeom", "Kind", "Vt"):
        setattr(pxr, sub, MagicMock())
    with patch.dict(sys.modules, {"pxr": pxr}):
        exec(code, {"hou": fake_hou})


def test_variant_set_create_raises_on_missing_prim(handler_and_lop):
    h, py_lop = handler_and_lop
    h._handle_manage_variant_set({
        "prim_path": "/World/nope",
        "action": "create",
        "variant_set": "color",
        "variants": ["red", "blue"],
    })
    code = py_lop.parm.return_value.set.call_args[0][0]
    with pytest.raises(ValueError, match="/World/nope"):
        _exec_missing_prim(code)


def test_modify_usd_prim_raises_on_missing_prim(handler_and_lop):
    h, py_lop = handler_and_lop
    h._handle_modify_usd_prim({"prim_path": "/World/nope", "kind": "component"})
    code = py_lop.parm.return_value.set.call_args[0][0]
    with pytest.raises(ValueError, match="/World/nope"):
        _exec_missing_prim(code)
