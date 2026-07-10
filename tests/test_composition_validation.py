"""Tests for _verify_composition() in LosslessExecutionBridge.

Validates the Scene Integrity anchor -- USD composition validation
after every stage-touching mutation. In standalone mode (no pxr/hou),
the method gracefully returns True so the pipeline doesn't block.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# Ensure shared package is importable
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from shared.bridge import LosslessExecutionBridge, _HOU_AVAILABLE


# ---------------------------------------------------------------------------
# Standalone mode (no Houdini)
# ---------------------------------------------------------------------------

class TestCompositionStandalone:
    """When hou is not available, composition checks should pass."""

    def test_standalone_returns_true(self):
        """Without Houdini, _verify_composition always returns True."""
        bridge = LosslessExecutionBridge()
        # In standalone mode _HOU_AVAILABLE is False, so method returns True
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/stage/lop1") is True

    def test_standalone_any_path_returns_true(self):
        """Arbitrary paths should not cause errors in standalone mode."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/nonexistent/path") is True
            assert bridge._verify_composition("") is True
            assert bridge._verify_composition("/stage/deeply/nested/node") is True


# ---------------------------------------------------------------------------
# Method existence and callability
# ---------------------------------------------------------------------------

class TestCompositionInterface:
    """Verify the method exists and has the expected signature."""

    def test_method_exists(self):
        bridge = LosslessExecutionBridge()
        assert hasattr(bridge, "_verify_composition")

    def test_method_is_callable(self):
        bridge = LosslessExecutionBridge()
        assert callable(bridge._verify_composition)

    def test_accepts_string_argument(self):
        """Method should accept a single string path argument."""
        bridge = LosslessExecutionBridge()
        # Should not raise TypeError
        result = bridge._verify_composition("/stage/test")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# Mocked Houdini scenarios
# ---------------------------------------------------------------------------

class TestCompositionWithMockedHou:
    """Test composition validation with mocked Houdini."""

    def test_invalid_node_path_returns_true(self):
        """If the node doesn't exist, gracefully return True."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            # Standalone always returns True
            assert bridge._verify_composition("/invalid/node") is True

    def test_node_without_stage_returns_true(self):
        """Nodes without a .stage() method should pass validation."""
        bridge = LosslessExecutionBridge()
        if not _HOU_AVAILABLE:
            assert bridge._verify_composition("/obj/geo1") is True

    def test_no_houdini_returns_true(self):
        """Without a live Houdini, _verify_composition returns True (nothing to
        validate). The exception PATH is fail-closed — see the patched test below."""
        bridge = LosslessExecutionBridge()
        result = bridge._verify_composition("/stage/broken")
        assert result is True


# ---------------------------------------------------------------------------
# With patched hou module (simulating production)
# ---------------------------------------------------------------------------

class TestCompositionPatched:
    """Test with a patched hou module to simulate Houdini environment."""

    def test_valid_stage_with_no_prims_returns_true(self):
        """An empty stage (no prims to traverse) should pass."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_node.stage.return_value = MagicMock()
        mock_node.stage.return_value.Traverse.return_value = []
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/lop1")
            assert result is True

    def test_node_not_found_returns_true(self):
        """hou.node() returning None should pass gracefully."""
        mock_hou = MagicMock()
        mock_hou.node.return_value = None

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/missing")
            assert result is True

    def test_node_without_stage_attr_returns_true(self):
        """Node without .stage attribute should pass gracefully."""
        mock_hou = MagicMock()
        mock_node = MagicMock(spec=[])  # No attributes at all
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            # hasattr(node, 'stage') will be False, returns True
            result = bridge._verify_composition("/stage/sopnode")
            assert result is True

    def test_stage_traverse_exception_fails_closed(self):
        """INT-3 (v4 §4a fail-closed): an exception during validation must FAIL
        CLOSED (return False). A stage that could not be validated is treated as
        invalid -> rollback, not silently reported composition_valid=True."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_node.stage.side_effect = RuntimeError("Stage error")
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/broken")
            assert result is False

    def test_valid_prims_return_true(self):
        """Stage with valid, active prims should pass."""
        mock_hou = MagicMock()
        mock_node = MagicMock()
        mock_prim = MagicMock()
        mock_prim.IsValid.return_value = True
        mock_prim.IsActive.return_value = True
        mock_prim.HasAuthoredReferences.return_value = False
        mock_stage = MagicMock()
        mock_stage.Traverse.return_value = [mock_prim]
        mock_node.stage.return_value = mock_stage
        mock_hou.node.return_value = mock_node

        with patch("shared.bridge._HOU_AVAILABLE", True), \
             patch("shared.bridge.hou", mock_hou):
            bridge = LosslessExecutionBridge()
            result = bridge._verify_composition("/stage/lop1")
            assert result is True


# ---------------------------------------------------------------------------
# Finding 4 — broadened composition validation (payloads, inherits,
# specializes). Fakes patch MODULE GLOBALS via monkeypatch.setattr on
# shared.bridge — never sys.modules (fake-residency trap; same idiom as
# tests/test_phase0c_int3_fail_closed.py and test_live_integrity_envelope.py).
# ---------------------------------------------------------------------------

import logging
from types import SimpleNamespace

import shared.bridge as b


class _ItemsAPI:
    """Fake Usd.References / Usd.Payloads WITH GetAddedOrExplicitItems."""

    def __init__(self, items):
        self._items = list(items)

    def GetAddedOrExplicitItems(self):
        return self._items


class _NoItemsAPI:
    """Fake Usd.Payloads WITHOUT GetAddedOrExplicitItems — the hasattr
    guard must debug-skip, never hard-fail (optional API is NOT an
    exception path)."""


class _FakePrim:
    def __init__(self, path="/World/A", ref_items=(), payload_items=None,
                 payloads_api=None, has_inherits=False,
                 has_specializes=False):
        self._path = path
        self._ref_items = list(ref_items)
        self._payload_items = payload_items
        self._payloads_api = payloads_api
        self._has_inherits = has_inherits
        self._has_specializes = has_specializes

    def IsValid(self):
        return True

    def IsActive(self):
        return True

    def GetPath(self):
        return self._path

    def HasAuthoredReferences(self):
        return bool(self._ref_items)

    def GetReferences(self):
        return _ItemsAPI(self._ref_items)

    def HasAuthoredPayloads(self):
        return self._payloads_api is not None or self._payload_items is not None

    def GetPayloads(self):
        if self._payloads_api is not None:
            return self._payloads_api
        return _ItemsAPI(self._payload_items or [])

    def HasAuthoredInherits(self):
        return self._has_inherits

    def HasAuthoredSpecializes(self):
        return self._has_specializes


class _FakeSdfUnresolvable:
    class Layer:
        @staticmethod
        def Find(path):
            return None

        @staticmethod
        def FindOrOpen(path):
            return None


class _FakeSdfResolves:
    class Layer:
        @staticmethod
        def Find(path):
            return object()

        @staticmethod
        def FindOrOpen(path):
            return object()


class _FakeQuery:
    def __init__(self, arcs):
        self._arcs = list(arcs)

    def GetCompositionArcs(self):
        return self._arcs


class _FakeArc:
    def __init__(self, target_prim_path):
        self._target = target_prim_path

    def GetTargetPrimPath(self):
        return self._target


def _make_fake_usd(inherit_arcs=(), specialize_arcs=None):
    """Fake pxr.Usd. specialize_arcs None → GetDirectSpecializes ABSENT
    (only GetDirectInherits is a live-verified static on H21.0.671)."""

    class _PCQ:
        @staticmethod
        def GetDirectInherits(prim):
            return _FakeQuery(inherit_arcs)

    if specialize_arcs is not None:
        _PCQ.GetDirectSpecializes = staticmethod(
            lambda prim: _FakeQuery(specialize_arcs))

    class _Usd:
        PrimCompositionQuery = _PCQ

    return _Usd


def _item(prim_path="", asset_path=""):
    return SimpleNamespace(primPath=prim_path, assetPath=asset_path)


def _patch_env(monkeypatch, prims, sdf=_FakeSdfResolves, usd=None):
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
    monkeypatch.setattr(b, "_import_pxr_composition", lambda: (sdf, usd))


class TestPayloadArcs:
    """Finding 4: payload arcs get the same two hard checks as references."""

    def test_payload_self_cycle_fails(self, monkeypatch):
        prim = _FakePrim(path="/World/A",
                         payload_items=[_item(prim_path="/World/A")])
        _patch_env(monkeypatch, [prim])
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is False

    def test_payload_unresolvable_asset_is_advisory_not_failure(
            self, monkeypatch, caplog):
        """F-G: authored payload asset paths are commonly anchored-relative
        ('./payload.usdc') and resolve against the INTRODUCING layer — the
        raw-path registry lookup here resolves against CWD, so a miss is NOT
        evidence of a broken stage. Advisory debug note, never a hard fail
        (a hard fail rolled back legitimate mutations on every valid stage
        using the standard published-asset layout)."""
        prim = _FakePrim(path="/World/A",
                         payload_items=[_item(asset_path="/missing/pl.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfUnresolvable)
        with caplog.at_level(logging.DEBUG, logger="synapse.bridge"):
            assert b.LosslessExecutionBridge()._verify_composition(
                "/stage/l") is True
        assert any("advisory" in r.message for r in caplog.records)

    def test_payload_same_path_external_arc_is_not_a_cycle(self, monkeypatch):
        """F-C: payload = @cache.usda@</World/A> authored ON /World/A (the
        standard export-then-payload-back round-trip) is LEGAL composition —
        a genuine self-cycle requires an INTERNAL arc (empty assetPath)."""
        prim = _FakePrim(path="/World/A",
                         payload_items=[_item(prim_path="/World/A",
                                              asset_path="/caches/shot.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfResolves)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True

    def test_payload_resolvable_no_cycle_passes(self, monkeypatch):
        prim = _FakePrim(path="/World/A",
                         payload_items=[_item(prim_path="/World/B",
                                              asset_path="/ok/pl.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfResolves)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True

    def test_payload_items_api_absent_skips_with_debug(self, monkeypatch, caplog):
        """GetAddedOrExplicitItems is verified only on References; an absent
        payload items API must SKIP (debug), never hard-fail — pin the skip."""
        prim = _FakePrim(path="/World/A", payloads_api=_NoItemsAPI())
        _patch_env(monkeypatch, [prim])
        with caplog.at_level(logging.DEBUG, logger="synapse.bridge"):
            assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True
        assert any("GetAddedOrExplicitItems absent" in r.message
                   for r in caplog.records)


class TestInheritSpecializeArcs:
    """Finding 4: inherit/specialize self-cycles hard-fail; a missing class
    prim is LEGAL USD and never fails."""

    def test_inherit_self_cycle_fails(self, monkeypatch):
        prim = _FakePrim(path="/World/A", has_inherits=True)
        usd = _make_fake_usd(inherit_arcs=[_FakeArc("/World/A")])
        _patch_env(monkeypatch, [prim], usd=usd)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is False

    def test_inherit_to_missing_class_passes(self, monkeypatch):
        # /_class_Missing does not exist anywhere — composes to nothing,
        # which is legal USD, NOT a hard failure.
        prim = _FakePrim(path="/World/A", has_inherits=True)
        usd = _make_fake_usd(inherit_arcs=[_FakeArc("/_class_Missing")])
        _patch_env(monkeypatch, [prim], usd=usd)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True

    def test_specialize_self_cycle_fails_when_static_present(self, monkeypatch):
        prim = _FakePrim(path="/World/A", has_specializes=True)
        usd = _make_fake_usd(specialize_arcs=[_FakeArc("/World/A")])
        _patch_env(monkeypatch, [prim], usd=usd)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is False

    def test_non_usd_prim_skips_class_arc_checks(self, monkeypatch, caplog):
        """PrimCompositionQuery statics only accept genuine Usd.Prim objects
        (Boost.Python ArgumentError otherwise). A non-Usd.Prim traverser is
        API-inapplicability -> debug-skip, NOT fail-closed. This is what
        keeps the pre-existing MagicMock-based tests green when a real pxr
        (e.g. pip usd-core) is installed in the test env."""

        class _RealPrimMarker:  # stands in for pxr.Usd.Prim
            pass

        prim = _FakePrim(path="/World/A", has_inherits=True)
        usd = _make_fake_usd(inherit_arcs=[_FakeArc("/World/A")])
        usd.Prim = _RealPrimMarker  # _FakePrim is NOT an instance -> skip
        _patch_env(monkeypatch, [prim], usd=usd)
        with caplog.at_level(logging.DEBUG, logger="synapse.bridge"):
            # The self-cycle arc is never consulted: the guard skips first.
            assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True
        assert any("not a Usd.Prim" in r.message for r in caplog.records)

    def test_specialize_static_absent_skips_with_debug(self, monkeypatch, caplog):
        """No live-verified GetDirectSpecializes exists on H21.0.671 — its
        absence must debug-skip, never hard-fail (optional API is NOT an
        exception path)."""
        prim = _FakePrim(path="/World/A", has_specializes=True)
        usd = _make_fake_usd()  # GetDirectSpecializes ABSENT
        _patch_env(monkeypatch, [prim], usd=usd)
        with caplog.at_level(logging.DEBUG, logger="synapse.bridge"):
            assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True
        assert any("GetDirectSpecializes" in r.message for r in caplog.records)


class TestReferenceRegression:
    """The extracted helper must keep reference outcomes byte-equivalent.
    (These pin the pxr-available reference path, which was previously
    untestable in CI — pxr absent meant the branch never ran.)"""

    def test_reference_self_cycle_still_fails(self, monkeypatch):
        prim = _FakePrim(path="/World/A",
                         ref_items=[_item(prim_path="/World/A")])
        _patch_env(monkeypatch, [prim])
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is False

    def test_reference_unresolvable_still_fails(self, monkeypatch):
        prim = _FakePrim(path="/World/A",
                         ref_items=[_item(asset_path="/missing/ref.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfUnresolvable)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is False

    def test_reference_valid_still_passes(self, monkeypatch):
        prim = _FakePrim(path="/World/A",
                         ref_items=[_item(prim_path="/World/B",
                                          asset_path="/ok/ref.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfResolves)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True

    def test_reference_same_path_external_arc_is_not_a_cycle(self, monkeypatch):
        """F-C (shared helper): an external reference targeting the prim's
        own path in a DIFFERENT layer is legal — only an internal arc (empty
        assetPath, the pre-existing pinned case above) is a self-cycle."""
        prim = _FakePrim(path="/World/A",
                         ref_items=[_item(prim_path="/World/A",
                                          asset_path="/caches/shot.usda")])
        _patch_env(monkeypatch, [prim], sdf=_FakeSdfResolves)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True

    def test_no_pxr_skips_arc_checks_entirely(self, monkeypatch):
        """_pxr_available False (Sdf=None) → reference/payload/inherit checks
        all skip — the original standalone semantics, unchanged."""
        prim = _FakePrim(path="/World/A",
                         ref_items=[_item(prim_path="/World/A")],
                         payload_items=[_item(prim_path="/World/A")],
                         has_inherits=True, has_specializes=True)
        _patch_env(monkeypatch, [prim], sdf=None, usd=None)
        assert b.LosslessExecutionBridge()._verify_composition("/stage/l") is True
