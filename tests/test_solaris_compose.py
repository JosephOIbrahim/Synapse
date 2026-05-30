"""Tests for the Solaris compose LOP-network primitive (solaris_compose.py).

Pure-logic + guarded-behavior tests with a mock ``hou`` (runs in CI without
Houdini). Every entry point was additionally [REAL]-verified on H21.0.671 via
the bridge during Mile 1; this is the standalone safety net.

The module has NO intra-package imports, so we load it directly via importlib
(no package __init__ / hou dependency at import time). Mock-hou rebinds are
monkeypatch-scoped so they auto-restore and never leak across the suite.
"""

import importlib.util
import pathlib
import types
from unittest.mock import MagicMock

import pytest

_MOD_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "python" / "synapse" / "server" / "solaris_compose.py"
)
_spec = importlib.util.spec_from_file_location("solaris_compose_under_test", _MOD_PATH)
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


class _FakeLopNetwork:
    """Stand-in class so isinstance(node, hou.LopNetwork) is exercisable."""


def _make_hou(existing=("sublayer", "usdrender_rop", "null", "pythonscript"),
              node_for_path=None):
    h = types.SimpleNamespace()
    h.LopNetwork = _FakeLopNetwork
    _cat = object()
    h.lopNodeTypeCategory = lambda: _cat
    h.nodeType = lambda cat, name: (object() if name in existing else None)
    h.node = lambda path: node_for_path
    return h


@pytest.fixture
def hou_stub(monkeypatch):
    """Install a mock hou on the module, auto-restored (no cross-test leak)."""
    h = _make_hou()
    monkeypatch.setattr(sc, "hou", h, raising=False)
    monkeypatch.setattr(sc, "HOU_AVAILABLE", True, raising=False)
    return h


# -- canonical_type / phantom map -------------------------------------------

def test_canonical_type_remaps_known_phantom():
    assert sc.canonical_type("usdrender") == "usdrender_rop"


def test_canonical_type_passthrough():
    assert sc.canonical_type("sublayer") == "sublayer"
    assert sc.canonical_type("materiallibrary") == "materiallibrary"


# -- _require_hou guard ------------------------------------------------------

def test_resolve_stage_raises_without_hou(monkeypatch):
    monkeypatch.setattr(sc, "HOU_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        sc.resolve_stage()


# -- lop_type_exists ---------------------------------------------------------

def test_lop_type_exists(hou_stub):
    assert sc.lop_type_exists("sublayer") is True
    assert sc.lop_type_exists("usdrender") is False  # phantom


# -- create_lop --------------------------------------------------------------

def test_create_lop_remaps_phantom_then_creates(hou_stub):
    parent = MagicMock()
    sc.create_lop(parent, "usdrender", "rop")
    parent.createNode.assert_called_once_with("usdrender_rop", "rop")


def test_create_lop_real_type(hou_stub):
    parent = MagicMock()
    sc.create_lop(parent, "sublayer", "sl")
    parent.createNode.assert_called_once_with("sublayer", "sl")


def test_create_lop_no_name(hou_stub):
    parent = MagicMock()
    sc.create_lop(parent, "null")
    parent.createNode.assert_called_once_with("null")


def test_create_lop_raises_on_absent_type(hou_stub):
    parent = MagicMock()
    with pytest.raises(sc.PhantomNodeTypeError):
        sc.create_lop(parent, "definitely_not_a_type", "x")
    parent.createNode.assert_not_called()


# -- resolve_stage -----------------------------------------------------------

def _install_hou(monkeypatch, node):
    h = _make_hou(node_for_path=node)
    monkeypatch.setattr(sc, "hou", h, raising=False)
    monkeypatch.setattr(sc, "HOU_AVAILABLE", True, raising=False)


def test_resolve_stage_returns_lopnetwork(monkeypatch):
    node = _FakeLopNetwork()
    _install_hou(monkeypatch, node)
    assert sc.resolve_stage() is node


def test_resolve_stage_missing_raises(monkeypatch):
    _install_hou(monkeypatch, None)
    with pytest.raises(sc.StageUnavailableError):
        sc.resolve_stage()


def test_resolve_stage_wrong_type_raises(monkeypatch):
    notlop = MagicMock()
    notlop.type.return_value.name.return_value = "geo"
    _install_hou(monkeypatch, notlop)
    with pytest.raises(sc.StageUnavailableError):
        sc.resolve_stage()


# -- wire --------------------------------------------------------------------

def test_wire_calls_setinput(hou_stub):
    node, src = MagicMock(), MagicMock()
    sc.wire(node, src, 2)
    node.setInput.assert_called_once_with(2, src)


# -- read_stage --------------------------------------------------------------

def test_read_stage_returns_stage(hou_stub):
    node = MagicMock()
    fake_stage = object()
    node.stage.return_value = fake_stage
    assert sc.read_stage(node) is fake_stage


def test_read_stage_none_raises(hou_stub):
    node = MagicMock()
    node.stage.return_value = None
    with pytest.raises(sc.StageUnavailableError):
        sc.read_stage(node)


# -- composition_errors / winning_layer -------------------------------------

def test_composition_errors_maps_to_str():
    stage = MagicMock()
    stage.GetCompositionErrors.return_value = ["err1", "err2"]
    assert sc.composition_errors(stage) == ["err1", "err2"]


def test_composition_errors_empty():
    stage = MagicMock()
    stage.GetCompositionErrors.return_value = []
    assert sc.composition_errors(stage) == []


def test_winning_layer_requires_pxr(monkeypatch):
    monkeypatch.setattr(sc, "_PXR_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        sc.winning_layer(MagicMock(), "/probe", "synapse:test")
