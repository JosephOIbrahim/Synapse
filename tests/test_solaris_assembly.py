"""
Synapse — Solaris Assembly Validation Tests

Tests the Solaris auto-assembly system across three components:
1. Node ordering table (_SOLARIS_NODE_ORDER)
2. Scene pipeline builder (_build_solaris_scene_pipeline)
3. System prompt wiring (_SOLARIS_CONTEXT_GUIDANCE)

All tests are pure Python — no Houdini required.

Run:
    python -m pytest tests/test_solaris_assembly.py -v
"""

import sys
import os

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.server.handlers_solaris_assemble import (
    _SOLARIS_NODE_ORDER,
    _get_sort_key,
    _merge_chain_order,
)
from synapse.routing.planner import _build_solaris_scene_pipeline
from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE


# =============================================================================
# TestSolarisNodeOrder — canonical chain ordering table
# =============================================================================


class TestSolarisNodeOrder:
    """Tests for _SOLARIS_NODE_ORDER and _get_sort_key."""

    def test_geometry_before_materials(self):
        """Geometry nodes (100) sort before material nodes (200)."""
        assert _SOLARIS_NODE_ORDER["sopcreate"] < _SOLARIS_NODE_ORDER["materiallibrary"]
        assert _SOLARIS_NODE_ORDER["sopimport"] < _SOLARIS_NODE_ORDER["materiallibrary"]

    def test_materials_before_cameras(self):
        """Material nodes (200) sort before camera nodes (400)."""
        assert _SOLARIS_NODE_ORDER["materiallibrary"] < _SOLARIS_NODE_ORDER["camera"]

    def test_cameras_before_lights(self):
        """Camera nodes (400) sort before light nodes (500).

        Uses the generic 'light' LOP — the per-shape light types
        (rectlight/spherelight/disklight) are phantom on H21.0.671 (FIX 1).
        """
        assert _SOLARIS_NODE_ORDER["camera"] < _SOLARIS_NODE_ORDER["light"]

    def test_lights_before_render(self):
        """Light nodes (500) sort before render nodes (700)."""
        assert _SOLARIS_NODE_ORDER["light"] < _SOLARIS_NODE_ORDER["karmarenderproperties"]

    def test_render_before_null(self):
        """Render nodes (700) sort before null/output nodes (900)."""
        assert _SOLARIS_NODE_ORDER["karmarenderproperties"] < _SOLARIS_NODE_ORDER["null"]

    def test_full_canonical_order(self):
        """Full canonical chain: geometry < materials < cameras < lights < render < null."""
        order = [
            _SOLARIS_NODE_ORDER["sopcreate"],       # 100
            _SOLARIS_NODE_ORDER["materiallibrary"],  # 200
            _SOLARIS_NODE_ORDER["camera"],           # 400
            _SOLARIS_NODE_ORDER["light"],            # 500
            _SOLARIS_NODE_ORDER["karmarenderproperties"],  # 700
            _SOLARIS_NODE_ORDER["null"],             # 900
        ]
        assert order == sorted(order), "Canonical order values must be strictly ascending"

    def test_domelight_after_generic_light(self):
        """Domelight (600) sorts AFTER the generic area light (500)."""
        assert _SOLARIS_NODE_ORDER["domelight"] > _SOLARIS_NODE_ORDER["light"]

    def test_no_phantom_light_types(self):
        """FIX 1: the order table must name ZERO phantom H21.0.671 light LOPs.

        rectlight/spherelight/disklight/cylinderlight do not exist on
        21.0.671 — createNode fails. Only the generic 'light' plus the
        distinct domelight/distantlight/lightmixer are real.
        """
        phantom = {"rectlight", "spherelight", "disklight", "cylinderlight"}
        assert phantom.isdisjoint(_SOLARIS_NODE_ORDER), (
            "phantom light LOP types leaked into the order table: "
            f"{phantom & set(_SOLARIS_NODE_ORDER)}"
        )
        # The real lighting LOPs are all present.
        for real in ("light", "distantlight", "domelight", "lightmixer"):
            assert real in _SOLARIS_NODE_ORDER, f"missing real light LOP: {real}"

    def test_reference_sorts_in_geometry_tier(self):
        """FIX 4: a 'reference' brings geometry, so it must sort BEFORE
        materials/assign (it was 250, downstream of assignmaterial:220)."""
        assert _SOLARIS_NODE_ORDER["reference"] < _SOLARIS_NODE_ORDER["materiallibrary"]
        assert _SOLARIS_NODE_ORDER["reference"] < _SOLARIS_NODE_ORDER["assignmaterial"]
        # Sits with the geometry-import tier (~100-150).
        assert _SOLARIS_NODE_ORDER["reference"] <= _SOLARIS_NODE_ORDER["sceneimport"]

    def test_unknown_type_gets_default(self):
        """Unknown node types get default sort key 800 via _get_sort_key."""
        # _get_sort_key expects a mock node with type().name()
        class _MockType:
            def name(self):
                return "some_unknown_node"

        class _MockNode:
            def type(self):
                return _MockType()

        assert _get_sort_key(_MockNode()) == 800

    def test_known_type_via_get_sort_key(self):
        """Known node types return their table value via _get_sort_key."""
        class _MockType:
            def name(self):
                return "camera"

        class _MockNode:
            def type(self):
                return _MockType()

        assert _get_sort_key(_MockNode()) == 400

    def test_namespaced_type_stripped(self):
        """Namespaced type (e.g. 'karma::2.0') strips after '::' before lookup."""
        class _MockType:
            def name(self):
                return "domelight::2.0"

        class _MockNode:
            def type(self):
                return _MockType()

        assert _get_sort_key(_MockNode()) == 600


# =============================================================================
# TestMergeChainOrder — FIX 3: canonical-position insertion (no blind append)
# =============================================================================


class _FakeType:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _FakeNode:
    """Minimal stand-in exposing .type().name() for _get_sort_key."""

    def __init__(self, type_name):
        self._type = _FakeType(type_name)

    def type(self):
        return self._type

    def __repr__(self):
        return f"<{self._type.name()}>"


class TestMergeChainOrder:
    """Tests for _merge_chain_order — the core of FIX 3."""

    def test_low_order_target_not_placed_after_higher_tail(self):
        """A light (500) merged into a chain ending in usdrender_rop (800)
        must NOT land after the ROP — the original bug."""
        matlib = _FakeNode("materiallibrary")   # 200
        karma = _FakeNode("karmarenderproperties")  # 700
        rop = _FakeNode("usdrender_rop")         # 800
        light = _FakeNode("light")               # 500

        ordered = _merge_chain_order([matlib, karma, rop], [light], _get_sort_key)
        types = [n.type().name() for n in ordered]

        # Light slots between materiallibrary and karma — never after the ROP.
        assert types == [
            "materiallibrary", "light", "karmarenderproperties", "usdrender_rop",
        ], types
        assert types.index("light") < types.index("usdrender_rop")
        # General invariant: no node precedes one with a strictly higher key.
        keys = [_get_sort_key(n) for n in ordered]
        assert keys == sorted(keys)

    def test_in_order_common_case_preserved(self):
        """When every target sorts at/after the tail, result == append
        (behaviour preserved for the common in-order case)."""
        matlib = _FakeNode("materiallibrary")   # 200
        camera = _FakeNode("camera")             # 400
        light = _FakeNode("light")               # 500
        rop = _FakeNode("usdrender_rop")         # 800

        ordered = _merge_chain_order([matlib, camera], [light, rop], _get_sort_key)
        assert [n.type().name() for n in ordered] == [
            "materiallibrary", "camera", "light", "usdrender_rop",
        ]

    def test_empty_existing_chain_is_just_sorted_targets(self):
        rop = _FakeNode("usdrender_rop")
        light = _FakeNode("light")
        camera = _FakeNode("camera")
        ordered = _merge_chain_order([], [rop, light, camera], _get_sort_key)
        assert [n.type().name() for n in ordered] == [
            "camera", "light", "usdrender_rop",
        ]


# =============================================================================
# TestSolarisScenePipeline — execute_python code generation
# =============================================================================


class TestSolarisScenePipeline:
    """Tests for _build_solaris_scene_pipeline from synapse.routing.planner."""

    def test_returns_list_with_execute_python(self):
        """Pipeline builder returns a list of commands with execute_python action."""
        result = _build_solaris_scene_pipeline({}, set())
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0].type == "execute_python"

    def test_code_contains_setInput(self):
        """Generated code wires nodes via setInput(0, prev)."""
        result = _build_solaris_scene_pipeline({}, {"add_camera"})
        code = result[0].payload["code"]
        assert "setInput(0, prev)" in code

    def test_code_contains_layoutChildren(self):
        """Generated code calls layoutChildren() for tidy network."""
        result = _build_solaris_scene_pipeline({}, set())
        code = result[0].payload["code"]
        assert "layoutChildren()" in code

    def test_code_contains_setDisplayFlag(self):
        """Generated code sets display flag on OUTPUT null."""
        result = _build_solaris_scene_pipeline({}, set())
        code = result[0].payload["code"]
        assert "setDisplayFlag(True)" in code

    def test_camera_modifier_adds_camera_section(self):
        """add_camera modifier produces camera creation code."""
        result = _build_solaris_scene_pipeline({}, {"add_camera"})
        code = result[0].payload["code"]
        assert "# --- Camera ---" in code
        assert "cam" in code

    def test_lighting_modifier_adds_lighting_section(self):
        """add_lighting modifier produces lighting creation code."""
        result = _build_solaris_scene_pipeline({}, {"add_lighting"})
        code = result[0].payload["code"]
        assert "# --- Lighting ---" in code
        assert "light" in code

    def test_camera_and_lighting_only(self):
        """Only requested modifiers appear in the generated code."""
        modifiers = {"add_camera", "add_lighting"}
        result = _build_solaris_scene_pipeline({}, modifiers)
        code = result[0].payload["code"]
        # Camera and lighting sections present
        assert "# --- Camera ---" in code
        assert "# --- Lighting ---" in code
        # Material and render sections absent
        assert "# --- Material ---" not in code
        assert "# --- Render Settings ---" not in code

    def test_no_modifiers_minimal_chain(self):
        """No modifiers produces geometry + OUTPUT null only."""
        result = _build_solaris_scene_pipeline({}, set())
        code = result[0].payload["code"]
        assert "# --- Geometry ---" in code
        assert "# --- OUTPUT ---" in code
        # No optional sections
        assert "# --- Material ---" not in code
        assert "# --- Camera ---" not in code
        assert "# --- Lighting ---" not in code
        assert "# --- Render Settings ---" not in code

    def test_render_modifier_adds_karma(self):
        """add_render modifier produces Karma render settings."""
        result = _build_solaris_scene_pipeline({}, {"add_render"})
        code = result[0].payload["code"]
        assert "# --- Render Settings ---" in code
        assert "karmarenderproperties" in code
        assert "karma" in code

    def test_all_modifiers_full_chain(self):
        """All modifiers produce the full canonical chain."""
        modifiers = {"add_geometry", "add_material", "add_camera", "add_lighting", "add_render"}
        result = _build_solaris_scene_pipeline({}, modifiers)
        code = result[0].payload["code"]
        assert "# --- Geometry ---" in code
        assert "# --- Material ---" in code
        assert "# --- Camera ---" in code
        assert "# --- Lighting ---" in code
        assert "# --- Render Settings ---" in code
        assert "# --- OUTPUT ---" in code


# =============================================================================
# TestSystemPromptWiring — Solaris context guidance content
# =============================================================================


class TestSystemPromptWiring:
    """Tests for _SOLARIS_CONTEXT_GUIDANCE from synapse.panel.system_prompt."""

    def test_contains_execute_python(self):
        """Guidance mentions execute_python for atomic scene building."""
        assert "execute_python" in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_setInput(self):
        """Guidance mentions setInput(0, wiring pattern."""
        assert "setInput(0," in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_canonical_chain_order(self):
        """Guidance contains canonical chain order reference."""
        lower = _SOLARIS_CONTEXT_GUIDANCE.lower()
        assert "canonical" in lower or "chain order" in lower

    def test_contains_layoutChildren(self):
        """Guidance mentions layoutChildren() for tidy networks."""
        assert "layoutChildren" in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_display_flag(self):
        """Guidance mentions display flag setting."""
        assert "setDisplayFlag" in _SOLARIS_CONTEXT_GUIDANCE or "display flag" in _SOLARIS_CONTEXT_GUIDANCE.lower()

    def test_contains_wiring_rules(self):
        """Guidance includes wiring rules section."""
        assert "Wiring Rules" in _SOLARIS_CONTEXT_GUIDANCE

    def test_is_string(self):
        """Guidance is a non-empty string."""
        assert isinstance(_SOLARIS_CONTEXT_GUIDANCE, str)
        assert len(_SOLARIS_CONTEXT_GUIDANCE) > 100
