"""BP12 items 13 and 14, found 2026-09-28 on Houdini 22.0.400.

13. H22's pxr has no ``GetAddedOrExplicitItems`` on ``Usd.References`` (or
    ``Usd.Payloads``), so the composition anchor raised on every stage with an
    authored reference and failed the op CLOSED as a "USD Composition
    violation". SYNAPSE could not set a parameter on a stock Karma Render
    Settings LOP. The anchor now reads the authored list ops from the prim
    stack, and a LOP target is anchored on itself rather than on an HDA
    internal that channel-references it.
14. A ``hou.Ramp`` in a tool result made ``_dumps_str`` raise
    "Type is not JSON serializable: Ramp".
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shared.bridge as b  # noqa: E402
from shared.bridge import LosslessExecutionBridge, Operation  # noqa: E402
from shared.types import AgentID  # noqa: E402
from synapse.mcp._tool_registry import _dumps_str  # noqa: E402


# ---------------------------------------------------------------- 13a: list ops from the prim stack

class _NoItemsAPI:
    """Usd.References / Usd.Payloads as H22.0.400 ships them: no GetAddedOrExplicitItems."""


class _ListProxy:
    """SdfPrimSpec.referenceList / .payloadList: carries GetAddedOrExplicitItems on H22."""

    def __init__(self, items):
        self._items = list(items)

    def GetAddedOrExplicitItems(self):
        return self._items


class _Layer:
    def __init__(self, base):
        self._base = base

    def ComputeAbsolutePath(self, path):
        return self._base + "/" + path.lstrip("./") if path.startswith("./") else path


class _H22Prim:
    def __init__(self, path="/World/A", ref_items=(), payload_items=(), layer=None):
        self._path = path
        spec = SimpleNamespace(referenceList=_ListProxy(ref_items),
                               payloadList=_ListProxy(payload_items), layer=layer)
        self._stack = [spec]
        self._has_refs = bool(ref_items)
        self._has_payloads = bool(payload_items)

    def IsValid(self):
        return True

    def IsActive(self):
        return True

    def GetPath(self):
        return self._path

    def HasAuthoredReferences(self):
        return self._has_refs

    def GetReferences(self):
        return _NoItemsAPI()

    def HasAuthoredPayloads(self):
        return self._has_payloads

    def GetPayloads(self):
        return _NoItemsAPI()

    def GetPrimStack(self):
        return self._stack

    def HasAuthoredInherits(self):
        return False

    def HasAuthoredSpecializes(self):
        return False


def _item(prim_path="", asset_path=""):
    return SimpleNamespace(primPath=prim_path, assetPath=asset_path)


def _sdf_finding(known):
    class _Sdf:
        class Layer:
            @staticmethod
            def Find(path):
                return object() if path in known else None

            @staticmethod
            def FindOrOpen(path):
                return object() if path in known else None
    return _Sdf


def _patch_env(monkeypatch, prims, sdf):
    class _Stage:
        def Traverse(self):
            return list(prims)

    class _Node:
        def stage(self):
            return _Stage()

    class _Hou:
        def node(self, path):
            return _Node()

    monkeypatch.setattr(b, "_HOU_AVAILABLE", True)
    monkeypatch.setattr(b, "hou", _Hou())
    monkeypatch.setattr(b, "_import_pxr_composition", lambda: (sdf, None))


def test_h22_internal_reference_passes(monkeypatch):
    """The stage that failed live: an ordinary internal reference, no list-op API on Usd.References."""
    prim = _H22Prim(ref_items=[_item(prim_path="/World/B")])
    _patch_env(monkeypatch, [prim], _sdf_finding(set()))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is True


def test_h22_self_reference_still_fails(monkeypatch):
    prim = _H22Prim(ref_items=[_item(prim_path="/World/A")])
    _patch_env(monkeypatch, [prim], _sdf_finding(set()))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is False


def test_h22_unresolvable_reference_still_fails(monkeypatch):
    prim = _H22Prim(ref_items=[_item(asset_path="C:/nowhere/missing.usd")])
    _patch_env(monkeypatch, [prim], _sdf_finding(set()))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is False


def test_relative_reference_resolves_against_its_layer(monkeypatch):
    prim = _H22Prim(ref_items=[_item(asset_path="./tex.usd")], layer=_Layer("C:/proj"))
    _patch_env(monkeypatch, [prim], _sdf_finding({"C:/proj/tex.usd"}))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is True


def test_h22_payload_self_cycle_now_checked(monkeypatch):
    prim = _H22Prim(payload_items=[_item(prim_path="/World/A")])
    _patch_env(monkeypatch, [prim], _sdf_finding(set()))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is False


def test_reference_with_no_list_op_api_fails_closed(monkeypatch):
    """Neither Usd.References nor the prim stack offers the list ops, so the
    reference checks cannot run. References are the strict arc: fail CLOSED."""
    prim = _H22Prim(ref_items=[_item(prim_path="/World/B")])
    prim._stack = [SimpleNamespace(layer=None)]  # specs without a referenceList
    _patch_env(monkeypatch, [prim], _sdf_finding(set()))
    assert LosslessExecutionBridge()._verify_composition("/stage/net/settings") is False


# ---------------------------------------------------------------- 13b: a LOP target anchors on itself

def _op(node_path):
    return Operation(agent_id=AgentID.HANDS, operation_type="set_parameter", summary="t",
                     fn=lambda: None, kwargs={"node_path": node_path})


def test_lop_target_is_its_own_stage_path():
    LopNode = type("LopNode", (), {})
    settings = LopNode()
    settings.path = lambda: "/stage/lookdev/preview_settings"
    internal = LopNode()
    internal.path = lambda: "/stage/lookdev/preview_settings/pythonscript1"
    settings.dependents = lambda: [internal]
    settings.outputs = lambda: []
    mock_hou = MagicMock()
    mock_hou.LopNode = LopNode
    mock_hou.node.return_value = settings
    with patch("shared.bridge._HOU_AVAILABLE", True), patch("shared.bridge.hou", mock_hou):
        op = _op("/stage/lookdev/preview_settings")
        assert LosslessExecutionBridge()._infer_stage_touch(op) is True
        assert op.stage_path == "/stage/lookdev/preview_settings"


def test_sop_trace_skips_hda_internals():
    LopNode = type("LopNode", (), {})
    sop = MagicMock()
    sop.path.return_value = "/obj/asset"
    inner = LopNode()
    inner.path = lambda: "/obj/asset/lopnet1/ref1"
    downstream = LopNode()
    downstream.path = lambda: "/stage/sopimport1"
    sop.dependents.return_value = [inner, downstream]
    sop.outputs.return_value = []
    mock_hou = MagicMock()
    mock_hou.LopNode = LopNode
    mock_hou.node.return_value = sop
    with patch("shared.bridge._HOU_AVAILABLE", True), patch("shared.bridge.hou", mock_hou):
        op = _op("/obj/asset")
        assert LosslessExecutionBridge()._infer_stage_touch(op) is True
        assert op.stage_path == "/stage/sopimport1"


# ---------------------------------------------------------------- 14: Ramp values serialize

class _FakeRamp:
    def basis(self):
        return ("rampBasis.Linear", "rampBasis.Constant")

    def keys(self):
        return (0.0, 1.0)

    def values(self):
        return ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))

    def isColor(self):
        return True


class _Opaque:
    def __str__(self):
        return "<opaque>"


def test_ramp_and_unknown_host_values_serialize():
    out = json.loads(_dumps_str({"ramp": _FakeRamp(), "other": _Opaque(), "n": 1}))
    assert out["ramp"] == {"type": "ramp", "basis": ["Linear", "Constant"], "keys": [0.0, 1.0],
                           "values": [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]], "is_color": True}
    assert out["other"] == "<opaque>" and out["n"] == 1
