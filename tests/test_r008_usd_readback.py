"""R-008 (HANDS-5): reference_usd and variant 'select' read the truth back.

Predicate:
- a referenced file that lacks the requested prim_path asserts a verification
  error, not a plain success;
- a select on a missing variant set asserts a verification error and records
  one undo group.

Before this repair, ``_handle_reference_usd`` only checked that the file
existed, set filepath1/primpath and returned -- an import that composed
nothing at the requested path still read as success, and the downstream
karma-visibility pythonscript (gated ``if prim:``) silently skipped.
``_handle_manage_variant_set``'s select branch created a pythonscript, never
cooked or read it back, and was the only mutating branch in that handler
outside an undo group.

The Wave 0 readback then inspected the *destination* prim on the cooked stage.
That prim is not evidence: the Reference LOP creates it when absent
(createprims defaults to Create, and the bundled node docs say "If this prim
doesn't exist, the node will create it"), so a file that composes nothing at
prim_path still leaves a valid empty prim. The readback now opens the
referenced file read-only and checks the source layer (prim_path "/" means the
layer's defaultPrim). The variant readback also checks the composed
selection, not just that the variant exists.

The composed-stage read needs Houdini (LIVE); these headless tests fake hou
and pxr, matching the test_m2_cook_verify.py readback idiom.
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from synapse.server.handlers import SynapseHandler
from synapse.server import handlers_usd as husd


class _FakeOperationFailed(Exception):
    pass


class _UndoCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _UndoRecorder:
    """Records every hou.undos.group(label) call -- the predicate counts them."""

    def __init__(self):
        self.groups = []

    def group(self, label=""):
        self.groups.append(label)
        return _UndoCtx()


class _Prim:
    def __init__(self, valid=True, sets=None, selection=""):
        self._valid = valid
        self._sets = dict(sets or {})
        self._selection = selection

    def IsValid(self):
        return self._valid

    def GetVariantSets(self):
        return _VariantSets(self._sets, self._selection)


class _VariantSets:
    def __init__(self, sets, selection=""):
        self._sets = sets
        self._selection = selection

    def GetNames(self):
        return list(self._sets)

    def GetVariantSet(self, name):
        return _VariantSet(self._sets[name], self._selection)


class _VariantSet:
    def __init__(self, variants, selection=""):
        self._variants = variants
        self._selection = selection

    def GetVariantNames(self):
        return list(self._variants)

    def GetVariantSelection(self):
        return self._selection


class _Stage:
    def __init__(self, prim):
        self._prim = prim

    def GetPrimAtPath(self, path):
        return self._prim


class _SourceLayer:
    """Stand-in for the Sdf layer opened from the referenced file.

    ``GetPrimAtPath`` mirrors the real Sdf.Layer contract: a prim spec for a
    path the layer defines, ``None`` otherwise (probed on pxr 0.26.5).
    """

    def __init__(self, prims=(), default_prim=""):
        self._prims = set(prims)
        self.defaultPrim = default_prim

    def GetPrimAtPath(self, path):
        return object() if path in self._prims else None


def _install_fake_pxr(monkeypatch, source_layer=None):
    """Force the readback path even where a real pxr is not installed.

    ``source_layer`` is what ``Sdf.Layer.FindOrOpen`` returns for the
    referenced file -- the reference readback's only evidence.
    """
    fake = ModuleType("pxr")
    fake.Usd = SimpleNamespace()
    layer = source_layer if source_layer is not None else _SourceLayer()
    fake.Sdf = SimpleNamespace(
        Layer=SimpleNamespace(FindOrOpen=lambda path: layer)
    )
    monkeypatch.setitem(sys.modules, "pxr", fake)
    return layer


def _install_inline_main_thread(monkeypatch):
    mt_live = importlib.import_module("synapse.server.main_thread")
    # F4 re-pin: run_on_main gained label=; fakes take **kw.
    monkeypatch.setattr(mt_live, "run_on_main", lambda fn, timeout=None, **kw: fn())


@pytest.fixture()
def ref_wired(monkeypatch):
    """reference_usd: empty /stage net, one reference LOP, undo calls recorded."""
    undo = _UndoRecorder()
    parent = MagicMock(name="parent")
    parent.displayNode.return_value = None
    parent.children.return_value = []
    ref = MagicMock(name="reference_lop")
    ref.path.return_value = "/stage/ref_import"
    parent.createNode.return_value = ref

    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=undo.group),
        OperationFailed=_FakeOperationFailed,
        node=lambda p: parent,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    _install_inline_main_thread(monkeypatch)
    return SynapseHandler(), ref, undo


@pytest.fixture()
def variant_wired(monkeypatch):
    """manage_variant_set: resolve_lop_node -> lop, one pythonscript child."""
    undo = _UndoRecorder()
    lop = MagicMock(name="lop")
    lop.path.return_value = "/stage/render_settings"
    parent = MagicMock(name="parent")
    lop.parent.return_value = parent
    py_lop = MagicMock(name="vsel_lop")
    py_lop.path.return_value = "/stage/vsel_color"
    parent.createNode.return_value = py_lop

    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=undo.group),
        OperationFailed=_FakeOperationFailed,
    )
    monkeypatch.setattr(husd, "hou", fake_hou)
    monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
    _install_inline_main_thread(monkeypatch)

    handler = SynapseHandler()
    monkeypatch.setattr(handler, "_resolve_lop_node", lambda p: lop)
    return handler, py_lop, undo


def _ref_payload(**kw):
    base = {
        "file": "$HIP/asset.usd",
        "mode": "reference",
        "prim_path": "/World/asset",
        "karma_visible": "false",  # keep the fake to one created node
    }
    base.update(kw)
    return base


def _select_payload(**kw):
    base = {
        "prim_path": "/World/car",
        "action": "select",
        "variant_set": "color",
        "variant": "blue",
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# reference_usd -- referenced-file readback
# ---------------------------------------------------------------------------


def test_reference_missing_prim_asserts_verification_error(ref_wired, monkeypatch):
    """PREDICATE: the referenced layer lacks the prim -> verify_error.

    The destination prim is valid on the cooked stage -- the Reference LOP is
    in create mode (createprims defaults to Create) and creates it -- which is
    exactly why it is not the evidence. The readback must consult the source
    layer.
    """
    handler, ref, _ = ref_wired
    ref.stage.return_value = _Stage(_Prim(valid=True))  # created, empty prim
    _install_fake_pxr(monkeypatch, _SourceLayer(prims={"/World/other"}))

    result = handler._handle_reference_usd(_ref_payload())

    assert "verify_error" in result
    assert "readback failed" in result["verify_error"]
    assert "no prim at /World/asset" in result["verify_error"]
    assert result.get("verified") is not True
    ref.cook.assert_called_once_with(force=True)
    ref.stage.assert_not_called()  # never trust the prim the node creates


def test_reference_present_prim_is_verified(ref_wired, monkeypatch):
    """Control: the referenced layer provides the prim -> verified."""
    handler, ref, _ = ref_wired
    _install_fake_pxr(monkeypatch, _SourceLayer(prims={"/World/asset"}))

    result = handler._handle_reference_usd(_ref_payload())

    assert result["verified"] is True
    assert "verify_error" not in result
    ref.cook.assert_called_once_with(force=True)


def test_reference_readback_opens_the_evaluated_filepath(ref_wired, monkeypatch):
    """$HIP-style payload paths are opened through the node's evaluated parm.

    The payload string can be unexpanded ('$HIP/asset.usd'); only the node's
    filepath1 knows the real on-disk path.
    """
    handler, ref, _ = ref_wired
    ref.parm("filepath1").evalAsString.return_value = "C:/resolved/asset.usd"
    opened = []

    def _find_or_open(path):
        opened.append(path)
        return _SourceLayer(prims={"/World/asset"})

    fake = ModuleType("pxr")
    fake.Usd = SimpleNamespace()
    fake.Sdf = SimpleNamespace(Layer=SimpleNamespace(FindOrOpen=_find_or_open))
    monkeypatch.setitem(sys.modules, "pxr", fake)

    result = handler._handle_reference_usd(_ref_payload())

    assert result["verified"] is True
    assert opened == ["C:/resolved/asset.usd"]


def test_reference_cook_failure_is_honest(ref_wired, monkeypatch):
    handler, ref, _ = ref_wired
    _install_fake_pxr(monkeypatch)
    ref.cook.side_effect = _FakeOperationFailed("missing default prim")

    result = handler._handle_reference_usd(_ref_payload())

    assert "hit a snag" in result["cook_error"]
    assert "missing default prim" in result["cook_error"]
    assert result.get("verified") is not True


def test_reference_prim_path_root_uses_layer_default_prim(ref_wired, monkeypatch):
    """prim_path '/' verifies the file's defaultPrim, not a destination prim."""
    handler, ref, _ = ref_wired
    _install_fake_pxr(
        monkeypatch, _SourceLayer(prims={"/World"}, default_prim="World")
    )

    result = handler._handle_reference_usd(_ref_payload(prim_path="/"))

    assert result["verified"] is True
    assert "verify_error" not in result
    ref.cook.assert_called_once_with(force=True)


def test_reference_prim_path_root_without_default_prim_is_not_success(
    ref_wired, monkeypatch
):
    """A layer with no defaultPrim is an explicit non-success for '/'.

    The Reference LOP's default primpath "/" references the file's default
    prim; with none declared the reference composes nothing.
    """
    handler, ref, _ = ref_wired
    _install_fake_pxr(monkeypatch, _SourceLayer(prims={"/World"}))

    result = handler._handle_reference_usd(_ref_payload(prim_path="/"))

    assert "verify_error" in result
    assert "no default prim" in result["verify_error"]
    assert result.get("verified") is not True
    ref.cook.assert_called_once_with(force=True)


def test_reference_prim_path_root_default_prim_missing_from_layer(
    ref_wired, monkeypatch
):
    """defaultPrim metadata pointing at a prim the layer lacks is a failure."""
    handler, ref, _ = ref_wired
    _install_fake_pxr(
        monkeypatch, _SourceLayer(prims={"/Other"}, default_prim="World")
    )

    result = handler._handle_reference_usd(_ref_payload(prim_path="/"))

    assert "verify_error" in result
    assert "no prim at /World" in result["verify_error"]
    assert result.get("verified") is not True


def test_reference_without_pxr_is_explicitly_unverified(ref_wired, monkeypatch):
    """No pxr means no evidence -- an explicit unverified state, never success."""
    handler, _, _ = ref_wired
    monkeypatch.setitem(sys.modules, "pxr", None)  # simulate an interpreter without pxr

    result = handler._handle_reference_usd(_ref_payload())

    assert "verify_error" in result
    assert "unverified" in result["verify_error"]
    assert result.get("verified") is not True


def test_reference_readback_uses_real_sdf_semantics(monkeypatch):
    """Anti-vacuity: drive the readback with a real pxr Sdf layer.

    The fake ``_SourceLayer`` mirrors this contract; this control proves the
    contract is what pxr actually does (prim spec for a defined path, None
    otherwise; defaultPrim is a plain string on the layer).
    """
    pytest.importorskip("pxr")
    from pxr import Sdf

    layer = Sdf.Layer.CreateAnonymous("wave0_ref_layer")
    Sdf.CreatePrimInLayer(layer, "/World/asset")
    layer.defaultPrim = "World"

    fake = ModuleType("pxr")
    fake.Sdf = SimpleNamespace(
        Layer=SimpleNamespace(FindOrOpen=lambda path: layer)
    )
    monkeypatch.setitem(sys.modules, "pxr", fake)

    assert SynapseHandler._verify_reference_cooked(
        None, "/World/asset", "ignored.usda"
    ) is None
    missing = SynapseHandler._verify_reference_cooked(
        None, "/World/other", "ignored.usda"
    )
    assert missing is not None
    assert "no prim at /World/other" in missing
    assert SynapseHandler._verify_reference_cooked(None, "/", "ignored.usda") is None


# ---------------------------------------------------------------------------
# manage_variant_set select -- readback + undo group
# ---------------------------------------------------------------------------


def test_variant_select_missing_set_verify_error_and_one_undo_group(
    variant_wired, monkeypatch
):
    """PREDICATE: select on a missing variant set -> verify_error + 1 undo group."""
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.stage.return_value = _Stage(
        _Prim(valid=True, sets={"size": ["small", "large"]})
    )

    result = handler._handle_manage_variant_set(_select_payload())

    assert "verify_error" in result
    assert "readback failed" in result["verify_error"]
    assert "variant set 'color' wasn't found" in result["verify_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]
    py_lop.cook.assert_called_once_with(force=True)


def test_variant_select_missing_prim_verify_error(variant_wired, monkeypatch):
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.stage.return_value = _Stage(_Prim(valid=False))

    result = handler._handle_manage_variant_set(_select_payload())

    assert "verify_error" in result
    assert "no prim exists at /World/car" in result["verify_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]


def test_variant_select_missing_variant_verify_error(variant_wired, monkeypatch):
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.stage.return_value = _Stage(
        _Prim(valid=True, sets={"color": ["red", "green"]})
    )

    result = handler._handle_manage_variant_set(_select_payload())

    assert "verify_error" in result
    assert "variant 'blue' wasn't found in set 'color'" in result["verify_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]


def test_variant_select_present_set_is_verified_one_undo_group(
    variant_wired, monkeypatch
):
    """Control: an existing set/variant whose selection composed verifies."""
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.stage.return_value = _Stage(
        _Prim(valid=True, sets={"color": ["red", "blue"]}, selection="blue")
    )

    result = handler._handle_manage_variant_set(_select_payload())

    assert result["verified"] is True
    assert "verify_error" not in result
    assert undo.groups == ["SYNAPSE: manage_variant_set"]
    py_lop.cook.assert_called_once_with(force=True)


def test_variant_select_not_applied_verify_error(variant_wired, monkeypatch):
    """PREDICATE (tightened): the set exists but the select did not apply."""
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.stage.return_value = _Stage(
        _Prim(valid=True, sets={"color": ["red", "blue"]}, selection="red")
    )

    result = handler._handle_manage_variant_set(_select_payload())

    assert "verify_error" in result
    assert "didn't apply" in result["verify_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]


def test_variant_select_without_pxr_is_explicitly_unverified(
    variant_wired, monkeypatch
):
    handler, _, undo = variant_wired
    monkeypatch.setitem(sys.modules, "pxr", None)

    result = handler._handle_manage_variant_set(_select_payload())

    assert "verify_error" in result
    assert "unverified" in result["verify_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]


def test_variant_select_cook_failure_is_honest(variant_wired, monkeypatch):
    handler, py_lop, undo = variant_wired
    _install_fake_pxr(monkeypatch)
    py_lop.cook.side_effect = _FakeOperationFailed("bad pythonscript")

    result = handler._handle_manage_variant_set(_select_payload())

    assert "hit a snag" in result["cook_error"]
    assert "bad pythonscript" in result["cook_error"]
    assert result.get("verified") is not True
    assert undo.groups == ["SYNAPSE: manage_variant_set"]
