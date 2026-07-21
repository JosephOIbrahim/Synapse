"""
Synapse — Solaris Graph Builder Tests

Tests the graph validation, topological sort, templates, and build_graph
handler logic. All tests are pure Python — no Houdini required.

Run:
    python -m pytest tests/test_solaris_graph.py -v
"""

import sys
import os

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.server.handlers_solaris_graph import (
    validate_graph,
    topo_sort,
    _find_terminal_nodes,
    detect_order_ambiguities,
)
from synapse.server.solaris_graph_templates import (
    multi_asset_merge,
    sublayer_stack,
    render_pass_split,
    lighting_rig,
    hdri_lighting,
    instanceable_assets,
    variant_selector,
    expand_template,
    TEMPLATES,
)


# =============================================================================
# TestValidation — graph validation (pure Python)
# =============================================================================


class TestValidation:
    """Tests for validate_graph()."""

    def test_valid_merge_graph(self):
        """Two sources feeding a merge node passes validation."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "m", "type": "merge"},
        ]
        connections = [
            {"from": "a", "to": "m", "input": 0},
            {"from": "b", "to": "m", "input": 1},
        ]
        valid, errors, warnings = validate_graph(nodes, connections)
        assert valid
        assert errors == []

    def test_valid_sublayer_stack(self):
        """Three sublayers feeding a merge passes validation."""
        nodes = [
            {"id": "l0", "type": "sublayer"},
            {"id": "l1", "type": "sublayer"},
            {"id": "l2", "type": "sublayer"},
            {"id": "m", "type": "merge"},
        ]
        connections = [
            {"from": "l0", "to": "m", "input": 0},
            {"from": "l1", "to": "m", "input": 1},
            {"from": "l2", "to": "m", "input": 2},
        ]
        valid, errors, warnings = validate_graph(nodes, connections)
        assert valid

    def test_duplicate_ids_rejected(self):
        """Duplicate node IDs are caught."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "a", "type": "merge"},
        ]
        valid, errors, _ = validate_graph(nodes, [])
        assert not valid
        assert any("Duplicate" in e for e in errors)

    def test_bad_connection_source_rejected(self):
        """Connection referencing unknown source ID is caught."""
        nodes = [{"id": "a", "type": "sopcreate"}]
        connections = [{"from": "nonexistent", "to": "a", "input": 0}]
        valid, errors, _ = validate_graph(nodes, connections)
        assert not valid
        assert any("nonexistent" in e for e in errors)

    def test_bad_connection_target_rejected(self):
        """Connection referencing unknown target ID is caught."""
        nodes = [{"id": "a", "type": "sopcreate"}]
        connections = [{"from": "a", "to": "nonexistent", "input": 0}]
        valid, errors, _ = validate_graph(nodes, connections)
        assert not valid
        assert any("nonexistent" in e for e in errors)

    def test_cycle_detected(self):
        """Cycle in graph is detected and rejected."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "c", "type": "sopcreate"},
        ]
        connections = [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "a"},
        ]
        valid, errors, _ = validate_graph(nodes, connections)
        assert not valid
        assert any("cycle" in e.lower() for e in errors)

    def test_empty_graph(self):
        """Empty graph (no nodes) is valid."""
        valid, errors, _ = validate_graph([], [])
        assert valid

    def test_single_node_no_connections(self):
        """Single node with no connections is valid."""
        nodes = [{"id": "solo", "type": "sopcreate"}]
        valid, errors, _ = validate_graph(nodes, [])
        assert valid

    def test_missing_display_node_rejected(self):
        """display_node referencing nonexistent ID is caught."""
        nodes = [{"id": "a", "type": "sopcreate"}]
        valid, errors, _ = validate_graph(nodes, [], display_node="nonexistent")
        assert not valid
        assert any("display_node" in e for e in errors)

    def test_merge_input_gap_warned(self):
        """Input indices 0 and 2 (skipping 1) produce a warning."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "m", "type": "merge"},
        ]
        connections = [
            {"from": "a", "to": "m", "input": 0},
            {"from": "b", "to": "m", "input": 2},
        ]
        valid, errors, warnings = validate_graph(nodes, connections)
        assert valid  # Gaps are warnings, not errors
        assert any("gap" in w.lower() for w in warnings)

    def test_linear_graph_passes(self):
        """Simple linear chain (degenerate DAG) passes."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "materiallibrary"},
            {"id": "c", "type": "null"},
        ]
        connections = [
            {"from": "a", "to": "b", "input": 0},
            {"from": "b", "to": "c", "input": 0},
        ]
        valid, errors, _ = validate_graph(nodes, connections)
        assert valid

    def test_self_loop_rejected(self):
        """Self-loop on a node is caught."""
        nodes = [{"id": "a", "type": "sopcreate"}]
        connections = [{"from": "a", "to": "a", "input": 0}]
        valid, errors, _ = validate_graph(nodes, connections)
        assert not valid
        assert any("Self-loop" in e for e in errors)

    def test_diamond_dag_passes(self):
        """Diamond DAG (A→B, A→C, B→D, C→D) passes."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "c", "type": "sopcreate"},
            {"id": "d", "type": "merge"},
        ]
        connections = [
            {"from": "a", "to": "b", "input": 0},
            {"from": "a", "to": "c", "input": 0},
            {"from": "b", "to": "d", "input": 0},
            {"from": "c", "to": "d", "input": 1},
        ]
        valid, errors, _ = validate_graph(nodes, connections)
        assert valid


# =============================================================================
# TestTopoSort — topological sorting
# =============================================================================


class TestTopoSort:
    """Tests for topo_sort()."""

    def test_linear_order(self):
        """Linear chain A→B→C sorts correctly."""
        ids = {"a", "b", "c"}
        conns = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
        result = topo_sort(ids, conns)
        assert result.index("a") < result.index("b") < result.index("c")

    def test_fan_in_merge(self):
        """Fan-in: sources appear before merge node."""
        ids = {"x", "y", "m"}
        conns = [
            {"from": "x", "to": "m", "input": 0},
            {"from": "y", "to": "m", "input": 1},
        ]
        result = topo_sort(ids, conns)
        assert result.index("x") < result.index("m")
        assert result.index("y") < result.index("m")

    def test_fan_out_split(self):
        """Fan-out: source appears before all targets."""
        ids = {"src", "t1", "t2"}
        conns = [
            {"from": "src", "to": "t1"},
            {"from": "src", "to": "t2"},
        ]
        result = topo_sort(ids, conns)
        assert result.index("src") < result.index("t1")
        assert result.index("src") < result.index("t2")

    def test_diamond_order(self):
        """Diamond: A before B,C; B,C before D."""
        ids = {"a", "b", "c", "d"}
        conns = [
            {"from": "a", "to": "b"},
            {"from": "a", "to": "c"},
            {"from": "b", "to": "d"},
            {"from": "c", "to": "d"},
        ]
        result = topo_sort(ids, conns)
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_isolated_nodes_included(self):
        """Isolated nodes (no connections) appear in output."""
        ids = {"a", "b", "lone"}
        conns = [{"from": "a", "to": "b"}]
        result = topo_sort(ids, conns)
        assert set(result) == ids

    def test_deterministic(self):
        """Same input produces same output across multiple calls."""
        ids = {"c", "a", "b"}
        conns = [{"from": "a", "to": "c"}, {"from": "b", "to": "c"}]
        results = [topo_sort(ids, conns) for _ in range(10)]
        assert all(r == results[0] for r in results)


# =============================================================================
# TestFindTerminals
# =============================================================================


class TestFindTerminals:
    """Tests for _find_terminal_nodes()."""

    def test_single_terminal(self):
        ids = {"a", "b", "c"}
        conns = [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}]
        assert _find_terminal_nodes(ids, conns) == ["c"]

    def test_multiple_terminals(self):
        ids = {"a", "b", "c"}
        conns = [{"from": "a", "to": "b"}, {"from": "a", "to": "c"}]
        assert _find_terminal_nodes(ids, conns) == ["b", "c"]

    def test_no_connections(self):
        ids = {"a", "b"}
        assert _find_terminal_nodes(ids, []) == ["a", "b"]


# =============================================================================
# TestOrderAmbiguities — FIX 2: detect-and-surface merge/sublayer ordering
# =============================================================================


class TestOrderAmbiguities:
    """Tests for detect_order_ambiguities() — the FIX 2 detection."""

    def test_merge_multi_input_flagged(self):
        """A merge with 2+ inputs is surfaced with its input order."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "m", "type": "merge"},
        ]
        conns = [
            {"from": "a", "to": "m", "input": 0},
            {"from": "b", "to": "m", "input": 1},
        ]
        findings = detect_order_ambiguities(nodes, conns)
        assert len(findings) == 1
        f = findings[0]
        assert f["node"] == "m"
        assert f["node_type"] == "merge"
        assert f["input_count"] == 2
        # current_order is sorted by input index
        assert f["current_order"] == ["a", "b"]
        assert "HIGHER input index" in f["suggested_fix"]

    def test_current_order_reflects_input_index_not_conn_order(self):
        """Connections listed out of index order still report by input index."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "m", "type": "merge"},
        ]
        # b is declared first but lands on input 1
        conns = [
            {"from": "b", "to": "m", "input": 1},
            {"from": "a", "to": "m", "input": 0},
        ]
        findings = detect_order_ambiguities(nodes, conns)
        assert findings[0]["current_order"] == ["a", "b"]

    def test_sublayer_gets_sublayer_specific_fix(self):
        nodes = [
            {"id": "l0", "type": "sublayer"},
            {"id": "l1", "type": "sublayer"},
            {"id": "s", "type": "sublayer"},
        ]
        conns = [
            {"from": "l0", "to": "s", "input": 0},
            {"from": "l1", "to": "s", "input": 1},
        ]
        findings = detect_order_ambiguities(nodes, conns)
        assert len(findings) == 1
        assert "sublayer" in findings[0]["suggested_fix"].lower()
        assert "subLayerPaths" in findings[0]["suggested_fix"]

    def test_single_input_merge_not_flagged(self):
        """A merge with one input has no ordering ambiguity."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "m", "type": "merge"},
        ]
        conns = [{"from": "a", "to": "m", "input": 0}]
        assert detect_order_ambiguities(nodes, conns) == []

    def test_switch_multi_input_not_flagged(self):
        """A switch is order-INDEPENDENT (explicit input selection)."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "sw", "type": "switch"},
        ]
        conns = [
            {"from": "a", "to": "sw", "input": 0},
            {"from": "b", "to": "sw", "input": 1},
        ]
        assert detect_order_ambiguities(nodes, conns) == []

    def test_non_order_dependent_multi_input_not_flagged(self):
        """A plain (non merge/sublayer) node with 2 inputs isn't an opinion
        merge — not flagged."""
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "x", "type": "assignmaterial"},
        ]
        conns = [
            {"from": "a", "to": "x", "input": 0},
            {"from": "b", "to": "x", "input": 1},
        ]
        assert detect_order_ambiguities(nodes, conns) == []

    def test_deterministic_sort_by_node_id(self):
        nodes = [
            {"id": "a", "type": "sopcreate"},
            {"id": "b", "type": "sopcreate"},
            {"id": "m2", "type": "merge"},
            {"id": "m1", "type": "merge"},
        ]
        conns = [
            {"from": "a", "to": "m2", "input": 0},
            {"from": "b", "to": "m2", "input": 1},
            {"from": "a", "to": "m1", "input": 0},
            {"from": "b", "to": "m1", "input": 1},
        ]
        findings = detect_order_ambiguities(nodes, conns)
        assert [f["node"] for f in findings] == ["m1", "m2"]


# =============================================================================
# TestTemplates — pre-built topology templates
# =============================================================================


class TestTemplates:
    """Tests for graph templates."""

    # -- multi_asset_merge --

    def test_multi_asset_merge_2_streams(self):
        """multi_asset_merge with 2 streams creates correct structure."""
        result = multi_asset_merge(stream_count=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "geo_0" in node_ids
        assert "geo_1" in node_ids
        assert "merge" in node_ids
        assert "output" in node_ids
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"Template validation failed: {errors}"

    def test_multi_asset_merge_3_streams(self):
        """multi_asset_merge with 3 streams creates 3 geo nodes."""
        result = multi_asset_merge(stream_count=3)
        geo_nodes = [n for n in result["nodes"] if n["id"].startswith("geo_")]
        assert len(geo_nodes) == 3

    def test_multi_asset_merge_5_streams(self):
        """multi_asset_merge with 5 streams creates 5 geo nodes."""
        result = multi_asset_merge(stream_count=5)
        geo_nodes = [n for n in result["nodes"] if n["id"].startswith("geo_")]
        assert len(geo_nodes) == 5
        merge_conns = [c for c in result["connections"] if c["to"] == "merge"]
        assert len(merge_conns) == 5
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"Template validation failed: {errors}"

    def test_multi_asset_merge_includes_render_by_default(self):
        """multi_asset_merge includes karma + ROP by default (renderable scene)."""
        result = multi_asset_merge(stream_count=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "karma_settings" in node_ids, "Missing karmarenderproperties"
        assert "rop" in node_ids, "Missing usdrender_rop"

    def test_multi_asset_merge_includes_materials(self):
        """multi_asset_merge always includes materiallibrary."""
        result = multi_asset_merge(stream_count=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "matlib" in node_ids, "Missing materiallibrary"

    def test_multi_asset_merge_canonical_order(self):
        """Render tail follows canonical order: matlib → camera → light → karma → output.

        usdrender_rop branches off karma_settings (terminal node, zero outputs).
        The main chain ends at OUTPUT null for display flag.
        """
        result = multi_asset_merge(stream_count=2)
        # Extract the linear tail after merge by following connections to non-ROP targets
        id_to_type = {n["id"]: n["type"] for n in result["nodes"]}
        # Build conn_map: for each source, find the non-ROP target on input 0
        conn_map = {}
        for c in result["connections"]:
            if c.get("input", 0) == 0 and c["from"] != "geo_0":
                target_type = id_to_type.get(c["to"], "")
                # Skip ROP branch — it's terminal, not part of main chain
                if target_type != "usdrender_rop":
                    conn_map[c["from"]] = c["to"]

        # Walk from merge (main display chain)
        chain = []
        current = "merge"
        while current in conn_map:
            current = conn_map[current]
            chain.append(id_to_type[current])

        # Main chain: matlib → camera → domelight → karma → null
        assert chain == [
            "materiallibrary", "camera", "domelight",
            "karmarenderproperties", "null",
        ], f"Wrong canonical order: {chain}"

        # ROP must branch off karma_settings (not in main chain)
        rop_conns = [c for c in result["connections"]
                     if c["to"] == "rop"]
        assert len(rop_conns) == 1
        assert rop_conns[0]["from"] == "karma_settings"

    # -- sublayer_stack --

    def test_sublayer_stack_3_layers(self):
        """sublayer_stack with 3 layers creates correct structure."""
        result = sublayer_stack(layer_count=3)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "layer_0" in node_ids
        assert "layer_1" in node_ids
        assert "layer_2" in node_ids
        assert "sublayer_merge" in node_ids
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"Template validation failed: {errors}"

    def test_sublayer_stack_includes_render(self):
        """sublayer_stack includes karma + ROP by default."""
        result = sublayer_stack(layer_count=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "karma_settings" in node_ids
        assert "rop" in node_ids

    # -- render_pass_split --

    def test_render_pass_split_2_passes(self):
        """render_pass_split with 2 passes creates parallel render chains."""
        result = render_pass_split(pass_count=2)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "scene_input" in node_ids
        assert "karma_pass_0" in node_ids
        assert "karma_pass_1" in node_ids
        assert "rop_pass_0" in node_ids
        assert "rop_pass_1" in node_ids
        # Display is on karma settings (ROP is terminal, no display flag)
        assert result["display_node"] == "karma_pass_0"
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"Template validation failed: {errors}"

    def test_render_pass_split_source_is_null_input(self):
        """render_pass_split source is a null node (scene input), not sopcreate."""
        result = render_pass_split(pass_count=2)
        source = next(n for n in result["nodes"] if n["id"] == "scene_input")
        assert source["type"] == "null", "Source should be null input, not sopcreate"

    # -- lighting_rig --

    def test_lighting_rig_chains_linearly(self):
        """Lighting rig chains lights linearly — NO merge node."""
        result = lighting_rig()
        node_ids = {n["id"] for n in result["nodes"]}
        # Must NOT have a merge node — lights chain linearly in Solaris
        assert "light_merge" not in node_ids, "Lights should NOT be merged"
        # Must have linear connections
        for conn in result["connections"]:
            assert conn.get("input", 0) == 0, "All connections should be input 0 (linear)"

    def test_lighting_rig_default_lights(self):
        """Default lighting rig creates env/key/fill lights."""
        result = lighting_rig()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "env" in node_ids
        assert "key" in node_ids
        assert "fill" in node_ids

    def test_lighting_rig_includes_render(self):
        """Lighting rig includes karma + ROP by default."""
        result = lighting_rig()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "karma_settings" in node_ids
        assert "rop" in node_ids

    def test_lighting_rig_has_scene_input(self):
        """Lighting rig has a scene input null for connecting upstream."""
        result = lighting_rig()
        scene_input = next(n for n in result["nodes"] if n["id"] == "scene_input")
        assert scene_input["type"] == "null"

    # -- General template tests --

    def test_template_override_merges(self):
        """Overlay nodes override existing template nodes by id."""
        result = expand_template(
            "multi_asset_merge",
            params={"stream_count": 2},
            overlay_nodes=[{"id": "geo_0", "parms": {"soppath": "/obj/hero"}}],
        )
        geo_0 = next(n for n in result["nodes"] if n["id"] == "geo_0")
        assert geo_0["parms"]["soppath"] == "/obj/hero"
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"Template validation failed: {errors}"

    def test_unknown_template_raises(self):
        """Unknown template name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown template"):
            expand_template("nonexistent_template")

    def test_template_output_validates_cleanly(self):
        """All templates produce valid graphs with default params."""
        for name, fn in TEMPLATES.items():
            result = fn()
            valid, errors, _ = validate_graph(
                result["nodes"], result["connections"], result.get("display_node")
            )
            assert valid, f"Template '{name}' validation failed: {errors}"

    def test_render_pass_split_named_passes(self):
        """render_pass_split with custom pass names."""
        result = render_pass_split(pass_count=2, pass_names=["beauty", "depth"])
        node_ids = {n["id"] for n in result["nodes"]}
        assert "karma_beauty" in node_ids
        assert "karma_depth" in node_ids
        assert "rop_beauty" in node_ids
        assert "rop_depth" in node_ids

    def test_all_templates_renderable(self):
        """Scene templates include render settings; utility templates may not."""
        # Utility templates are wired into scenes, not standalone render targets
        _UTILITY_TEMPLATES = {"variant_selector"}
        for name, fn in TEMPLATES.items():
            if name in _UTILITY_TEMPLATES:
                continue
            result = fn()
            node_types = {n["type"] for n in result["nodes"]}
            if name == "render_pass_split":
                # render_pass_split has per-pass render settings
                assert "karmarenderproperties" in node_types
            else:
                assert "karmarenderproperties" in node_types, \
                    f"Template '{name}' missing karmarenderproperties"
                assert "usdrender_rop" in node_types, \
                    f"Template '{name}' missing usdrender_rop"


# =============================================================================
# TestSystemPromptGuidance — updated guidance content
# =============================================================================


class TestSystemPromptGuidance:
    """Tests for updated _SOLARIS_CONTEXT_GUIDANCE with graph assembly info."""

    def test_contains_build_graph(self):
        """Guidance mentions build_graph tool."""
        from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE
        assert "build_graph" in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_assemble_chain(self):
        """Guidance mentions assemble_chain tool."""
        from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE
        assert "assemble_chain" in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_template_names(self):
        """Guidance mentions template names."""
        from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE
        assert "multi_asset_merge" in _SOLARIS_CONTEXT_GUIDANCE
        assert "sublayer_stack" in _SOLARIS_CONTEXT_GUIDANCE

    def test_contains_merge_ordering(self):
        """Guidance explains merge input ordering -- and states the DIRECTION.

        The prior assertion accepted either polarity ("opinion strength" OR
        "input 0" appearing anywhere), so it stayed green while the prompt
        taught the inverted rule. Ground truth is SideFX's own shipped doc,
        houdini/help/nodes.zip -> lop/merge.txt: "Layers in earlier inputs are
        weaker than layers in later inputs" (and lop/sublayer.txt: "weaker to
        stronger, from left to right"). The handlers already encode this
        correctly (handlers_solaris_graph.py:196,233,239); the prompt did not.
        """
        from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE
        g = _SOLARIS_CONTEXT_GUIDANCE
        assert "HIGHER input index = STRONGER" in g, (
            "merge guidance must state the direction explicitly")
        assert "input 0 is the WEAKEST" in g
        # The inverted claim must not reappear, in any casing.
        assert "0 has highest opinion" not in g.lower()
        assert "input 0 is the strongest" not in g.lower()


# =============================================================================
# TestHdriLighting — hdri_lighting template
# =============================================================================


class TestHdriLighting:
    """Tests for hdri_lighting() template."""

    def test_default_includes_sun_and_render(self):
        result = hdri_lighting()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "hdri_dome" in node_ids
        assert "physical_sky" in node_ids
        assert "sun" in node_ids
        assert "karma_settings" in node_ids
        assert "rop" in node_ids
        assert "output" in node_ids

    def test_no_sun(self):
        result = hdri_lighting(include_sun=False)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "sun" not in node_ids
        assert "hdri_dome" in node_ids
        assert "physical_sky" in node_ids

    def test_no_render(self):
        result = hdri_lighting(include_render=False)
        node_ids = {n["id"] for n in result["nodes"]}
        assert "karma_settings" not in node_ids
        assert "rop" not in node_ids
        assert "output" in node_ids

    def test_linear_chain_valid(self):
        result = hdri_lighting()
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"hdri_lighting graph invalid: {errors}"

    def test_display_node_is_output(self):
        result = hdri_lighting()
        assert result["display_node"] == "output"

    def test_connection_flow_top_to_bottom(self):
        """All connections flow scene_input → dome → sky → sun → ... → output."""
        result = hdri_lighting()
        from_ids = [c["from"] for c in result["connections"]]
        assert from_ids[0] == "scene_input"
        assert "hdri_dome" in from_ids
        assert "physical_sky" in from_ids


# =============================================================================
# TestInstanceableAssets — instanceable_assets template
# =============================================================================


class TestInstanceableAssets:
    """Tests for instanceable_assets() template."""

    def test_default_three_assets(self):
        result = instanceable_assets()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "asset_0" in node_ids
        assert "asset_1" in node_ids
        assert "asset_2" in node_ids
        assert "merge" in node_ids
        # W.3 (H22): the scatter node is `paintinstances` — the canonical
        # rename of the removed `layout` LOP (whats-new 22/solaris.txt L137).
        assert "paintinstances" in node_ids

    def test_custom_asset_count(self):
        result = instanceable_assets(asset_count=5)
        node_ids = {n["id"] for n in result["nodes"]}
        for i in range(5):
            assert f"asset_{i}" in node_ids

    def test_merge_inputs_contiguous(self):
        """Each asset connects to merge at contiguous input indices."""
        result = instanceable_assets(asset_count=4)
        merge_inputs = [
            c["input"] for c in result["connections"] if c["to"] == "merge"
        ]
        assert sorted(merge_inputs) == [0, 1, 2, 3]

    def test_asset_count_zero_raises(self):
        with pytest.raises(ValueError, match="asset_count must be >= 1"):
            instanceable_assets(asset_count=0)

    def test_valid_graph(self):
        result = instanceable_assets()
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"instanceable_assets graph invalid: {errors}"

    def test_no_camera_no_lights(self):
        result = instanceable_assets(include_camera=False, include_lights=False)
        node_types = {n["type"] for n in result["nodes"]}
        assert "camera" not in node_types
        assert "domelight" not in node_types


# =============================================================================
# H22 canonical-spelling ratchet — no template may emit a removed LOP name
# =============================================================================


class TestNoRemovedH22Spellings:
    """W.3 (H22.0.368): `Lop/instancer` and `Lop/layout` were renamed
    (copytopoints / paintinstances — whats-new 22/solaris.txt L143/L137).
    hou.nodeType lookup of the old names returns None; only the opalias
    rescues createNode(). SYNAPSE emits canonical spellings — a legacy
    type in ANY template is a regression this ratchet catches."""

    REMOVED = {"instancer", "layout"}

    def test_no_template_emits_removed_spellings(self):
        for name, fn in TEMPLATES.items():
            result = fn()
            legacy = {n["type"] for n in result["nodes"]} & self.REMOVED
            assert not legacy, (
                f"template {name!r} emits removed H21 spellings "
                f"{sorted(legacy)} — use copytopoints/paintinstances"
            )


# =============================================================================
# TestVariantSelector — variant_selector template
# =============================================================================


class TestVariantSelector:
    """Tests for variant_selector() template."""

    def test_default_structure(self):
        result = variant_selector()
        node_ids = {n["id"] for n in result["nodes"]}
        assert "asset_input" in node_ids
        assert "explore" in node_ids
        assert "select" in node_ids
        assert "output" in node_ids

    def test_default_variant_names(self):
        result = variant_selector(variant_count=3)
        assert result["variant_names"] == ["variant_0", "variant_1", "variant_2"]

    def test_custom_variant_names(self):
        result = variant_selector(variant_names=["red", "green", "blue"])
        assert result["variant_names"] == ["red", "green", "blue"]

    def test_linear_chain_order(self):
        """asset_input → explore → select → output."""
        result = variant_selector()
        conn_pairs = [(c["from"], c["to"]) for c in result["connections"]]
        assert ("asset_input", "explore") in conn_pairs
        assert ("explore", "select") in conn_pairs
        assert ("select", "output") in conn_pairs

    def test_valid_graph(self):
        result = variant_selector()
        valid, errors, _ = validate_graph(
            result["nodes"], result["connections"], result["display_node"]
        )
        assert valid, f"variant_selector graph invalid: {errors}"

    def test_display_node_is_output(self):
        result = variant_selector()
        assert result["display_node"] == "output"


# =============================================================================
# B4 / B5 -- idempotency and pre-flight recognition
# =============================================================================

class _B4Type:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


class _B4Node:
    def __init__(self, name, type_name, parent_path="/stage"):
        self._name = name
        self._type = _B4Type(type_name)
        self._path = "%s/%s" % (parent_path, name)

    def type(self):
        return self._type

    def path(self):
        return self._path


class _B4Parent:
    """Records createNode calls so a duplicate is visible in the assertion."""

    def __init__(self, existing=None):
        self._children = dict(existing or {})
        self.created = []

    def node(self, name):
        return self._children.get(name)

    def createNode(self, node_type, node_name):
        self.created.append((node_type, node_name))
        n = _B4Node(node_name, node_type)
        self._children[node_name] = n
        return n


class TestEnsureNodeIdempotency:
    """B4: build_graph used a raw createNode. Houdini auto-uniquifies a
    colliding name, so an identical second build produced a whole second
    network drawn on top of the first (OUTPUT -> OUTPUT1) and moved the display
    flag to it, while reporting status='created' with no warnings."""

    def test_creates_when_absent(self):
        from synapse.server.handlers_solaris_graph import _ensure_node
        parent = _B4Parent()
        node, created = _ensure_node(parent, "materiallibrary", "matlib")
        assert created is True
        assert parent.created == [("materiallibrary", "matlib")]

    def test_reuses_when_name_and_type_match(self):
        from synapse.server.handlers_solaris_graph import _ensure_node
        parent = _B4Parent({"matlib": _B4Node("matlib", "materiallibrary")})
        node, created = _ensure_node(parent, "materiallibrary", "matlib")
        assert created is False
        assert parent.created == [], "must not create a duplicate"

    def test_reuse_tolerates_a_versioned_existing_type(self):
        """Houdini resolves a bare name to the newest version, so a node asked
        for as `domelight` reports `domelight::3.0`. Matching on the full name
        would miss and duplicate."""
        from synapse.server.handlers_solaris_graph import _ensure_node
        parent = _B4Parent({"key": _B4Node("key", "domelight::3.0")})
        node, created = _ensure_node(parent, "domelight", "key")
        assert created is False
        assert parent.created == []

    def test_name_collision_across_types_is_raised_not_papered_over(self):
        """guards.ensure_node matches on NAME alone and would hand back a
        `null` when a `merge` was asked for. That is a real conflict."""
        from synapse.server.handlers_solaris_graph import _ensure_node
        from synapse.core.errors import SynapseUserError
        parent = _B4Parent({"OUTPUT": _B4Node("OUTPUT", "null")})
        with pytest.raises(SynapseUserError) as exc:
            _ensure_node(parent, "merge", "OUTPUT")
        assert "null" in str(exc.value) and "merge" in str(exc.value)
        assert parent.created == []
        assert exc.value.suggestion, "must carry a remediation"
