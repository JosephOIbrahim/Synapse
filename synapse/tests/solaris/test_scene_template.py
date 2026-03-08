"""
Tests for synapse_solaris_scene_template — RELAY-SOLARIS Phase 3
"""

import pytest
from unittest.mock import MagicMock, patch

import sys; st_mod = sys.modules["synapse.mcp.tools.solaris.scene_template"]
from synapse.mcp.tools.solaris.scene_template import (
    validate, plan, execute, _SOURCE_PATTERN, _TOOL_NAME, _PATH_TEMPLATES,
)


class TestSceneTemplateValidation:

    def test_accepts_defaults(self):
        validate({})  # All params have defaults

    def test_rejects_invalid_scene_name(self):
        with pytest.raises(Exception, match="invalid characters"):
            validate({"scene_name": "my scene!"})

    def test_rejects_bad_resolution(self):
        with pytest.raises(Exception, match="resolution"):
            validate({"resolution": [0, 1080]})

    def test_rejects_invalid_engine(self):
        with pytest.raises(Exception, match="render_engine"):
            validate({"render_engine": "arnold"})

    def test_accepts_karma_cpu(self):
        validate({"render_engine": "karma_cpu"})

    def test_accepts_karma_xpu(self):
        validate({"render_engine": "karma_xpu"})


class TestSceneTemplatePlan:

    def test_plan_returns_list(self):
        ops = plan({})
        assert isinstance(ops, list)

    def test_plan_starts_with_primitive(self):
        ops = plan({})
        assert ops[0]["node_type"] == "primitive"

    def test_plan_primitive_has_group_kind(self):
        ops = plan({})
        assert ops[0]["params"]["primkind"] == "Group"
        assert ops[0]["params"]["primtype"] == "Xform"

    def test_plan_default_scene_name_is_shot(self):
        ops = plan({})
        assert ops[0]["params"]["primpath"] == "/shot"

    def test_plan_custom_scene_name(self):
        ops = plan({"scene_name": "env_forest"})
        assert ops[0]["params"]["primpath"] == "/env_forest"

    def test_plan_sop_imports_chain_sequentially(self):
        """SOP imports must be chained, never merged — Pattern 1 constraint."""
        ops = plan({"sop_paths": ["/obj/geo1", "/obj/geo2", "/obj/geo3"]})
        sop_ops = [o for o in ops if o.get("node_type") == "sopimport"]
        assert len(sop_ops) == 3
        # All must have chain=True flag
        for op in sop_ops:
            assert op.get("chain") is True

    def test_plan_canonical_node_order(self):
        """Full chain must follow Pattern 1 canonical order."""
        ops = plan({"sop_paths": ["/obj/geo1"]})
        node_types = [o.get("node_type") for o in ops if o.get("node_type")]
        # primitive → sopimport → camera → materiallibrary → karmaphysicalsky → karmarendersettings → usdrender_rop
        expected_order = [
            "primitive", "sopimport", "camera", "materiallibrary",
            "karmaphysicalsky", "karmarendersettings", "usdrender_rop",
        ]
        assert node_types == expected_order

    def test_plan_no_sop_imports_when_empty(self):
        ops = plan({})
        sop_ops = [o for o in ops if o.get("node_type") == "sopimport"]
        assert len(sop_ops) == 0

    def test_plan_primpath_conventions(self):
        """All primitive paths follow /shot/{category}/$OS convention."""
        ops = plan({"sop_paths": ["/obj/geo1"]})
        sop_ops = [o for o in ops if o.get("node_type") == "sopimport"]
        assert sop_ops[0]["params"]["primpath"] == "/shot/geo/$OS"

        cam_ops = [o for o in ops if o.get("node_type") == "camera"]
        assert cam_ops[0]["params"]["primpath"] == "/shot/cam/$OS"

        mat_ops = [o for o in ops if o.get("node_type") == "materiallibrary"]
        assert mat_ops[0]["params"]["primpath"] == "/shot/MTL/$OS"

        sky_ops = [o for o in ops if o.get("node_type") == "karmaphysicalsky"]
        assert sky_ops[0]["params"]["primpath"] == "/shot/LGT/$OS"

    def test_plan_includes_provenance(self):
        ops = plan({})
        prov = [o for o in ops if o.get("op") == "stamp_provenance"]
        assert len(prov) == 1
        assert prov[0]["source_pattern"] == _SOURCE_PATTERN

    def test_plan_wire_chain_correct(self):
        ops = plan({})
        wire = [o for o in ops if o.get("op") == "wire_chain"]
        assert len(wire) == 1
        assert "primitive" in wire[0]["sequence"]
        assert "usdrender_rop" in wire[0]["sequence"]


class TestSceneTemplateExecute:

    def test_idempotent(self, mock_stage, mock_hou):

        mock_stage.createNode("primitive", "primitive_shot")

        with patch.object(st_mod, "hou", mock_hou):
            with patch.object(st_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                result = execute({})

        assert result["status"] == "already_exists"

    def test_creates_full_chain(self, mock_stage, mock_hou):

        with patch.object(st_mod, "hou", mock_hou):
            with patch.object(st_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                mock_hou.undos.group.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
                result = execute({})

        assert result["status"] == "created"
        assert result["hierarchy_root"] == "/shot"
        assert len(result["chain"]) >= 5  # primitive, cam, matlib, sky, rs, rop
        assert result["render_rop"] is not None

    def test_sop_imports_wired_sequentially(self, mock_stage, mock_hou):
        """Verify SOP imports are chained, not merged."""

        with patch.object(st_mod, "hou", mock_hou):
            with patch.object(st_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                mock_hou.undos.group.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
                result = execute({"sop_paths": ["/obj/geo1", "/obj/geo2"]})

        # Find geo nodes in the chain
        geo_nodes = [p for p in result["chain"] if "geo_" in p]
        assert len(geo_nodes) == 2

        # Verify sequential wiring: geo_1's input should be geo_0
        geo_0 = mock_stage._children.get("geo_0")
        geo_1 = mock_stage._children.get("geo_1")
        assert geo_0 is not None
        assert geo_1 is not None
        assert geo_1.inputs()[0] == geo_0  # geo_1 wired AFTER geo_0
