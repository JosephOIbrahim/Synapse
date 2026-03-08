"""
Tests for synapse_solaris_component_builder — RELAY-SOLARIS Phase 3

Tests validate, plan, and execute (with mock Houdini).
No live Houdini required.
"""

import pytest
import sys
from unittest.mock import MagicMock, patch

# Import the tool module's validate/plan functions (pure Python, no hou)
# We need to handle the relative import by adjusting sys.path or mocking
import sys; cb_mod = sys.modules["synapse.mcp.tools.solaris.component_builder"]
from synapse.mcp.tools.solaris.component_builder import validate, plan, execute, _SOURCE_PATTERN, _TOOL_NAME


class TestComponentBuilderValidation:
    """Parameter validation tests — pure Python."""

    def test_rejects_missing_asset_name(self):
        with pytest.raises(Exception, match="asset_name is required"):
            validate({})

    def test_rejects_empty_asset_name(self):
        with pytest.raises(Exception, match="asset_name is required"):
            validate({"asset_name": ""})

    def test_rejects_invalid_asset_name_chars(self):
        with pytest.raises(Exception, match="invalid characters"):
            validate({"asset_name": "my asset!"})

    def test_rejects_asset_name_with_spaces(self):
        with pytest.raises(Exception, match="invalid characters"):
            validate({"asset_name": "hero chair"})

    def test_rejects_asset_name_starting_with_digit(self):
        with pytest.raises(Exception, match="invalid characters"):
            validate({"asset_name": "123asset"})

    def test_accepts_valid_asset_name(self):
        validate({"asset_name": "hero_chair"})  # Should not raise

    def test_accepts_asset_name_with_underscores(self):
        validate({"asset_name": "my_cool_asset_v2"})

    def test_rejects_proxy_reduction_out_of_range(self):
        with pytest.raises(Exception, match="proxy_reduction"):
            validate({"asset_name": "test", "proxy_reduction": 1.5})

    def test_rejects_negative_proxy_reduction(self):
        with pytest.raises(Exception, match="proxy_reduction"):
            validate({"asset_name": "test", "proxy_reduction": -0.1})

    def test_rejects_invalid_purpose(self):
        with pytest.raises(Exception, match="Unknown purpose"):
            validate({"asset_name": "test", "purposes": ["render", "bogus"]})

    def test_accepts_all_valid_purposes(self):
        validate({"asset_name": "test", "purposes": ["render", "proxy", "simproxy"]})


class TestComponentBuilderPlan:
    """Plan generation tests — pure Python."""

    def test_plan_returns_list(self):
        ops = plan({"asset_name": "chair"})
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_plan_starts_with_create_component(self):
        ops = plan({"asset_name": "chair"})
        assert ops[0]["op"] == "create_component"
        assert ops[0]["name"] == "component_chair"

    def test_plan_contains_correct_node_sequence(self):
        ops = plan({"asset_name": "chair"})
        node_types = [
            o.get("node_type") for o in ops
            if o.get("op") == "create_node"
        ]
        assert "componentgeometry" in node_types
        assert "componentmaterial" in node_types
        assert "componentoutput" in node_types

    def test_plan_wire_chain_matches_canonical_order(self):
        ops = plan({"asset_name": "chair"})
        wire_ops = [o for o in ops if o.get("op") == "wire_chain"]
        assert len(wire_ops) == 1
        sequence = wire_ops[0]["sequence"]
        assert sequence == ["componentgeometry", "componentmaterial", "componentoutput"]

    def test_plan_includes_proxy_by_default(self):
        ops = plan({"asset_name": "chair"})
        proxy_ops = [o for o in ops if o.get("op") == "create_proxy"]
        assert len(proxy_ops) == 1

    def test_plan_no_proxy_when_render_only(self):
        ops = plan({"asset_name": "chair", "purposes": ["render"]})
        proxy_ops = [o for o in ops if o.get("op") == "create_proxy"]
        assert len(proxy_ops) == 0

    def test_plan_includes_materials(self):
        ops = plan({
            "asset_name": "chair",
            "materials": [{"name": "wood"}, {"name": "metal"}],
        })
        mat_ops = [o for o in ops if o.get("op") == "create_material"]
        assert len(mat_ops) == 2
        assert mat_ops[0]["name"] == "wood"
        assert mat_ops[1]["name"] == "metal"

    def test_plan_includes_export_when_path_given(self):
        ops = plan({"asset_name": "chair", "export_path": "/tmp/chair.usd"})
        export_ops = [o for o in ops if o.get("op") == "set_export"]
        assert len(export_ops) == 1
        assert export_ops[0]["path"] == "/tmp/chair.usd"

    def test_plan_includes_provenance(self):
        ops = plan({"asset_name": "chair"})
        prov_ops = [o for o in ops if o.get("op") == "stamp_provenance"]
        assert len(prov_ops) == 1
        assert prov_ops[0]["source_pattern"] == _SOURCE_PATTERN

    def test_plan_geometry_source_adds_op(self):
        ops = plan({"asset_name": "chair", "geometry_source": "/obj/geo1"})
        geo_ops = [o for o in ops if o.get("op") == "set_geometry_source"]
        assert len(geo_ops) == 1
        assert geo_ops[0]["source"] == "/obj/geo1"


class TestComponentBuilderExecute:
    """Execute tests with mock Houdini."""

    def test_idempotent_returns_already_exists(self, mock_stage, mock_hou):
        """Second call with same params returns already_exists."""

        # Pre-create the component so it already exists
        mock_stage.createNode("subnet", "component_test_asset")

        with patch.object(cb_mod, "hou", mock_hou):
            with patch.object(cb_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                result = execute({"asset_name": "test_asset"})

        assert result["status"] == "already_exists"

    def test_creates_subnet_when_native_unavailable(self, mock_stage, mock_hou):
        """When componentbuilder doesn't exist, creates subnet with internal wiring."""

        with patch.object(cb_mod, "hou", mock_hou):
            with patch.object(cb_mod, "HOU_AVAILABLE", True):
                with patch.object(cb_mod, "_has_native_componentbuilder", return_value=False):
                    mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                    mock_hou.undos.group.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
                    result = execute({"asset_name": "chair"})

        assert result["status"] == "created"
        assert result["strategy"] == "subnet"
        assert "componentgeometry" in result["internal_nodes"]
        assert "componentmaterial" in result["internal_nodes"]
        assert "componentoutput" in result["internal_nodes"]

    def test_stamps_provenance(self, mock_stage, mock_hou):
        """Created nodes get provenance user data."""

        with patch.object(cb_mod, "hou", mock_hou):
            with patch.object(cb_mod, "HOU_AVAILABLE", True):
                with patch.object(cb_mod, "_has_native_componentbuilder", return_value=False):
                    mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                    mock_hou.undos.group.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
                    result = execute({"asset_name": "lamp"})

        comp_node = mock_stage._children.get("component_lamp")
        assert comp_node is not None
        assert comp_node.userData("synapse:tool") == _TOOL_NAME
        assert comp_node.userData("synapse:source_pattern") == _SOURCE_PATTERN
