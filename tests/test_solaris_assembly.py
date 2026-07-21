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
    _UNRANKED_RANK,
    _UNBOUNDED_INPUT_TYPES,
    _get_sort_key,
    _is_unranked,
    _merge_chain_order,
    _next_free_input,
    _reconstruct_chain,
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

    def test_unknown_type_sorts_upstream_of_the_render_tier(self):
        """B1: an unranked type must never tie with, or follow, the render ROP.

        This test previously asserted the default WAS 800 -- byte-identical to
        usdrender_rop's own rank. Because _merge_chain_order only inserts before
        a node whose key is strictly greater, that tie meant every unranked type
        was appended AFTER the render output: wired, reported, laid out, and
        contributing nothing to the render. 184 of the build's 218 LOP types
        took that path, `plane` and `shadowcatcher` among them.

        The invariant is asserted as a relationship rather than a literal, so
        re-tuning the tiers cannot silently reintroduce the tie.
        """
        class _MockType:
            def name(self):
                return "some_unknown_node"

        class _MockNode:
            def type(self):
                return _MockType()

        default = _get_sort_key(_MockNode())
        assert default == _UNRANKED_RANK
        assert default < _SOLARIS_NODE_ORDER["usdrender_rop"], (
            "an unranked type must sort strictly upstream of the render ROP")
        assert default < _SOLARIS_NODE_ORDER["karmarendersettings"], (
            "an unranked type must sort upstream of the whole render tier")
        assert default > _SOLARIS_NODE_ORDER["materiallibrary"], (
            "but downstream of scene content, so it does not jump the spine")

    def test_ground_plane_and_shadow_catcher_are_ranked(self):
        """B1 regression: the two types the recon predicted would land after
        the ROP. Both verified present on 22.0.368; both were unranked."""
        for type_name in ("plane", "shadowcatcher", "backgroundplate"):
            assert type_name in _SOLARIS_NODE_ORDER, f"{type_name} unranked"
            assert (_SOLARIS_NODE_ORDER[type_name]
                    < _SOLARIS_NODE_ORDER["usdrender_rop"])

    def test_payload_phantom_is_not_in_the_rank_table(self):
        """`payload` is absent from the 22.0.368 LOP catalog -- it carried rank
        155 since H21 and could never have matched a real node."""
        assert "payload" not in _SOLARIS_NODE_ORDER

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


# =============================================================================
# B3 -- merge-DAG awareness and non-destructive wiring
# =============================================================================

class _B3FakeType:
    def __init__(self, name, max_inputs=1):
        self._name = name
        self._max = max_inputs

    def name(self):
        return self._name

    def maxNumInputs(self):
        return self._max


class _B3FakeNode:
    """Minimal hou.Node stand-in: inputs() returns the connected list, with
    None for unoccupied slots, exactly as Houdini does."""

    def __init__(self, name, type_name="null", max_inputs=1, path=None):
        self.name = name
        self._type = _B3FakeType(type_name, max_inputs)
        self._inputs = []
        self._path = path or "/stage/%s" % name

    def type(self):
        return self._type

    def inputs(self):
        return tuple(self._inputs)

    def outputs(self):
        return ()

    def path(self):
        return self._path

    def connect(self, index, upstream):
        while len(self._inputs) <= index:
            self._inputs.append(None)
        self._inputs[index] = upstream
        return self


class TestReconstructChainSeesBranches:
    """_reconstruct_chain followed input 0 only, so a merge DAG was flattened
    into a line and every other branch became invisible -- eligible to be wired
    over, and absent from the response. Merge input index IS USD opinion
    strength, so a lost branch changes which opinion wins."""

    def test_linear_chain_has_no_branches(self):
        root = _B3FakeNode("root")
        mid = _B3FakeNode("mid").connect(0, root)
        tail = _B3FakeNode("tail").connect(0, mid)
        spine, branches = _reconstruct_chain(tail)
        assert [n.name for n in spine] == ["root", "mid", "tail"]
        assert branches == []

    def test_merge_branches_are_reported_not_swallowed(self):
        geo_a = _B3FakeNode("geo_a")
        geo_b = _B3FakeNode("geo_b")
        geo_c = _B3FakeNode("geo_c")
        merge = _B3FakeNode("merge1", "merge", max_inputs=9999)
        merge.connect(0, geo_a).connect(1, geo_b).connect(2, geo_c)
        rop = _B3FakeNode("rop", "usdrender_rop").connect(0, merge)

        spine, branches = _reconstruct_chain(rop)
        # The spine still walks input 0 -- linear ordering of a DAG is not
        # meaningful -- but the other two assets are no longer invisible.
        assert [n.name for n in spine] == ["geo_a", "merge1", "rop"]
        assert sorted(n.name for n in branches) == ["geo_b", "geo_c"]


class TestUnboundedInputsPreserveStrength:
    def test_the_frozen_set_matches_the_live_catalog(self):
        """Every name in _UNBOUNDED_INPUT_TYPES must be variadic on the build
        the committed catalog was harvested from."""
        import json
        import pathlib
        fp = (pathlib.Path(__file__).resolve().parents[1]
              / "harness" / "notes" / "h22_lop_catalog_live_22.0.368.json")
        if not fp.exists():          # catalog is build-stamped; skip elsewhere
            pytest.skip("no 22.0.368 catalog in this tree")
        types = json.loads(fp.read_text(encoding="utf-8"))["types"]
        for name in _UNBOUNDED_INPUT_TYPES:
            assert name in types, f"{name} absent from the live catalog"
            assert types[name]["max_inputs"] >= 9999, (
                f"{name} is not variadic on 22.0.368")

    def test_next_free_input_skips_occupied_slots(self):
        merge = _B3FakeNode("merge1", "merge", max_inputs=9999)
        merge.connect(0, _B3FakeNode("a")).connect(1, _B3FakeNode("b"))
        assert _next_free_input(merge) == 2

    def test_next_free_input_reuses_a_hole(self):
        merge = _B3FakeNode("merge1", "merge", max_inputs=9999)
        merge.connect(0, _B3FakeNode("a")).connect(2, _B3FakeNode("c"))
        assert _next_free_input(merge) == 1

    def test_empty_node_takes_input_zero(self):
        assert _next_free_input(_B3FakeNode("fresh")) == 0


class TestUnrankedDetection:
    def test_known_type_is_not_unranked(self):
        assert not _is_unranked(_B3FakeNode("m", "materiallibrary"))

    def test_unknown_type_is_unranked(self):
        assert _is_unranked(_B3FakeNode("x", "some_unknown_node"))

    def test_versioned_name_resolves_to_its_base_rank(self):
        """Houdini resolves a bare name to the newest version, so a node asked
        for as `domelight` reports `domelight::3.0`. A lookup that does not
        strip the version silently misses and the node lands unranked."""
        versioned = _B3FakeNode("d", "domelight::3.0")
        assert not _is_unranked(versioned)
        assert _get_sort_key(versioned) == _SOLARIS_NODE_ORDER["domelight"]
