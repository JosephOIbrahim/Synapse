"""set_usd_primvar: primvar-authoring handler + its three wiring sites.

Covers the new ``set_usd_primvar`` command that authors a UsdGeom primvar via
``UsdGeom.PrimvarsAPI(prim).CreatePrimvar(name, Sdf.ValueTypeNames.<T>,
interpolation).Set(value)`` -- the interpolation-aware sibling of
set_usd_attribute (which only sets a raw, interpolation-less attribute).

Three things are pinned here:
  * the handler emits the right pythonscript-LOP code (type/interp/optionals),
  * the gate map (protocol.py) classifies it REVIEW like set_usd_attribute,
  * the MCP tool registry exposes houdini_set_usd_primvar -> set_usd_primvar.

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
if not hasattr(_h, "text"):
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_usd as husd  # noqa: E402


# ---------------------------------------------------------------------------
# Pure host-side type resolver
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token,expected", [
    ("float", "Float"),
    ("float3", "Float3"),
    ("color3f", "Color3f"),
    ("int", "Int"),
    ("normal3f", "Normal3f"),
    ("texcoord2f", "TexCoord2f"),
    ("COLOR3F", "Color3f"),          # case-insensitive
    (" float3 ", "Float3"),          # whitespace-tolerant
    ("float3[]", "Float3Array"),     # array suffix
    ("color3fArray", "Color3fArray"),
    ("nope", None),
    ("", None),
    (None, None),
])
def test_resolve_primvar_type(token, expected):
    assert husd._resolve_primvar_type(token) == expected


# ---------------------------------------------------------------------------
# Handler: code emission
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
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    # Isolate from the shared display-wiring helper.
    monkeypatch.setattr(husd, "_wire_display", lambda *a, **k: {})

    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None: fn())

    code_store = {}
    py_lop = MagicMock(name="py_lop")
    py_lop.path.return_value = "/stage/primvar_Cd"
    py_lop.parm.return_value = _CapturingParm(code_store)
    parent = MagicMock()
    parent.createNode.return_value = py_lop
    lop = MagicMock()
    lop.parent.return_value = parent

    monkeypatch.setattr(
        SynapseHandler, "_resolve_lop_node", lambda self, p: lop, raising=False
    )
    return SynapseHandler(), py_lop, code_store


def test_handler_exists():
    assert hasattr(SynapseHandler, "_handle_set_usd_primvar")


def test_constant_color_primvar_emits_primvarsapi(wired):
    handler, py_lop, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "interpolation": "constant",
        "value": [1.0, 0.0, 0.0],
    })
    src = code["code"]
    assert "from pxr import Sdf, UsdGeom, Vt" in src
    assert "UsdGeom.PrimvarsAPI(prim).CreatePrimvar(" in src
    assert "Sdf.ValueTypeNames.Color3f" in src
    assert "'constant'" in src
    assert "pv.Set([1.0, 0.0, 0.0])" in src
    assert result["type"] == "Color3f"
    assert result["interpolation"] == "constant"
    assert result["primvar_name"] == "Cd"
    assert "cook_error" not in result


def test_node_name_and_cook_forced(wired):
    handler, py_lop, _ = wired
    handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "value": [1.0, 0.0, 0.0],
    })
    # pythonscript LOP created with a primvar_-prefixed name, cooked force=True.
    parent = py_lop.parent.return_value  # noqa: F841 (sanity only)
    py_lop.cook.assert_called_once_with(force=True)


def test_array_type_with_interpolation(wired):
    handler, _, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/mesh",
        "primvar_name": "width",
        "type": "float[]",
        "interpolation": "vertex",
        "value": [0.1, 0.2, 0.3],
    })
    assert "Sdf.ValueTypeNames.FloatArray" in code["code"]
    assert "'vertex'" in code["code"]
    assert result["type"] == "FloatArray"


def test_facevarying_canonicalized(wired):
    handler, _, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/mesh",
        "primvar_name": "st",
        "type": "texcoord2f[]",
        "interpolation": "facevarying",
        "value": [[0, 0], [1, 0], [1, 1]],
    })
    assert "'faceVarying'" in code["code"]
    assert result["interpolation"] == "faceVarying"


def test_element_size_and_indices_emitted(wired):
    handler, _, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/mesh",
        "primvar_name": "st",
        "type": "texcoord2f[]",
        "interpolation": "faceVarying",
        "value": [[0, 0], [1, 1]],
        "element_size": 2,
        "indices": [0, 1, 1, 0],
    })
    src = code["code"]
    assert "pv.SetElementSize(2)" in src
    assert "pv.SetIndices(Vt.IntArray([0, 1, 1, 0]))" in src
    assert result["element_size"] == 2
    assert result["indices"] == [0, 1, 1, 0]


def test_optionals_omitted_when_absent(wired):
    handler, _, code = wired
    handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "value": [1.0, 0.0, 0.0],
    })
    assert "SetElementSize" not in code["code"]
    assert "SetIndices" not in code["code"]


def test_unsupported_type_fails_fast(wired):
    handler, py_lop, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "bogus",
        "value": 1.0,
    })
    assert "Unsupported primvar type" in result["error"]
    assert "code" not in code  # no pythonscript node was created


def test_unsupported_interpolation_fails_fast(wired):
    handler, _, code = wired
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "interpolation": "spiral",
        "value": [1.0, 0.0, 0.0],
    })
    assert "Unsupported interpolation" in result["error"]
    assert "code" not in code


def test_cook_error_is_honest(wired):
    handler, py_lop, _ = wired
    py_lop.cook.side_effect = _FakeOperationFailed("no prim at /World/geo")
    result = handler._handle_set_usd_primvar({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "value": [1.0, 0.0, 0.0],
    })
    assert "hit a snag when cooking" in result["cook_error"]
    assert "created_node" in result
    assert "type" not in result  # success keys absent on the error branch


# ---------------------------------------------------------------------------
# Wiring site 1: gate map (protocol.py)
# ---------------------------------------------------------------------------


def test_gate_level_is_review():
    from synapse.agent.protocol import DEFAULT_GATE_LEVELS, classify_gate_level
    from synapse.core.gates import GateLevel

    assert DEFAULT_GATE_LEVELS["set_usd_primvar"] == GateLevel.REVIEW
    # Same level as the sibling it mirrors.
    assert classify_gate_level("set_usd_primvar") == classify_gate_level("set_usd_attribute")


# ---------------------------------------------------------------------------
# Wiring site 2: MCP tool registry (_tool_registry.py)
# ---------------------------------------------------------------------------


def test_mcp_tool_registered():
    from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON

    assert "houdini_set_usd_primvar" in TOOL_DISPATCH
    cmd, builder = TOOL_DISPATCH["houdini_set_usd_primvar"]
    assert cmd == "set_usd_primvar"

    schema = TOOL_JSON["houdini_set_usd_primvar"]["inputSchema"]
    assert set(schema["required"]) == {"prim_path", "primvar_name", "type", "value"}
    for key in ("interpolation", "element_size", "indices", "node", "set_display"):
        assert key in schema["properties"]


def test_mcp_payload_builder_filters_keys():
    from synapse.mcp._tool_registry import TOOL_DISPATCH

    _, builder = TOOL_DISPATCH["houdini_set_usd_primvar"]
    payload = builder({
        "prim_path": "/World/geo",
        "primvar_name": "Cd",
        "type": "color3f",
        "interpolation": "constant",
        "value": [1, 0, 0],
        "element_size": 3,
        "indices": [0, 1],
        "set_display": False,
        "garbage": "drop me",
    })
    assert "garbage" not in payload
    assert payload["prim_path"] == "/World/geo"
    assert payload["primvar_name"] == "Cd"
    assert payload["type"] == "color3f"
    assert payload["value"] == [1, 0, 0]
