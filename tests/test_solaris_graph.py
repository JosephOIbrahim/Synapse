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
)
from synapse.server.solaris_graph_templates import (
    multi_asset_merge,
    sublayer_stack,
    render_pass_split,
    lighting_rig,
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
        """Guidance explains merge input ordering."""
        from synapse.panel.system_prompt import _SOLARIS_CONTEXT_GUIDANCE
        assert "opinion strength" in _SOLARIS_CONTEXT_GUIDANCE or "input 0" in _SOLARIS_CONTEXT_GUIDANCE
