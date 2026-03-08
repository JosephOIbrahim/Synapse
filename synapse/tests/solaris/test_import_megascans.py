"""
Tests for synapse_solaris_import_megascans — RELAY-SOLARIS Phase 3
"""

import pytest
from unittest.mock import MagicMock, patch

import sys; ms_mod = sys.modules["synapse.mcp.tools.solaris.import_megascans"]
from synapse.mcp.tools.solaris.import_megascans import validate, plan, execute, _SOURCE_PATTERN, _TOOL_NAME


class TestImportMegascansValidation:

    def test_rejects_missing_usdc_path(self):
        with pytest.raises(Exception, match="usdc_path is required"):
            validate({"asset_name": "rock"})

    def test_rejects_missing_asset_name(self):
        with pytest.raises(Exception, match="asset_name is required"):
            validate({"usdc_path": "/tmp/rock.usdc"})

    def test_rejects_invalid_asset_name(self):
        with pytest.raises(Exception, match="invalid characters"):
            validate({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock 01"})

    def test_rejects_negative_scale(self):
        with pytest.raises(Exception, match="scale_factor"):
            validate({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock", "scale_factor": -1})

    def test_rejects_proxy_out_of_range(self):
        with pytest.raises(Exception, match="proxy_reduction"):
            validate({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock", "proxy_reduction": 2.0})

    def test_accepts_valid_params(self):
        validate({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock_large"})


class TestImportMegascansPlan:

    def test_plan_returns_list(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        assert isinstance(ops, list)

    def test_plan_has_sop_chain(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        sop_types = [o["node_type"] for o in ops if o.get("op") == "sop_create"]
        assert "usdimport" in sop_types
        assert "xform" in sop_types
        assert "matchsize" in sop_types
        assert "polyreduce" in sop_types
        assert "output" in sop_types

    def test_plan_sop_order_matches_pattern(self):
        """SOP chain must follow: usdimport → xform → matchsize → polyreduce → output."""
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        sop_types = [o["node_type"] for o in ops if o.get("op") == "sop_create"]
        expected = ["usdimport", "xform", "matchsize", "polyreduce", "output"]
        assert sop_types == expected

    def test_plan_skips_matchsize_when_no_ground(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock", "ground_asset": False})
        sop_types = [o["node_type"] for o in ops if o.get("op") == "sop_create"]
        assert "matchsize" not in sop_types

    def test_plan_includes_rotation_when_provided(self):
        ops = plan({
            "usdc_path": "/tmp/rock.usdc",
            "asset_name": "rock",
            "rotation_correction": [0, 90, 0],
        })
        sop_types = [o["node_type"] for o in ops if o.get("op") == "sop_create"]
        # Should have 2 xforms: scale + rotation
        assert sop_types.count("xform") == 2

    def test_plan_has_material_reference(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        ref_ops = [o for o in ops if o.get("op") == "create_reference_lop"]
        assert len(ref_ops) == 1
        assert ref_ops[0]["primpath"] == "/materials/*"
        assert ref_ops[0]["destpath"] == "asset/mtl/"

    def test_plan_skips_material_reference_when_disabled(self):
        ops = plan({
            "usdc_path": "/tmp/rock.usdc",
            "asset_name": "rock",
            "import_materials": False,
        })
        ref_ops = [o for o in ops if o.get("op") == "create_reference_lop"]
        assert len(ref_ops) == 0

    def test_plan_unpack_to_polygons_is_true(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        import_ops = [o for o in ops if o.get("op") == "sop_create" and o.get("node_type") == "usdimport"]
        assert import_ops[0]["params"]["unpack_to_polygons"] is True

    def test_plan_default_scale_is_001(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        xform_ops = [o for o in ops if o.get("op") == "sop_create" and o.get("node_type") == "xform"]
        assert xform_ops[0]["params"]["uniform_scale"] == 0.01

    def test_plan_includes_provenance(self):
        ops = plan({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})
        prov = [o for o in ops if o.get("op") == "stamp_provenance"]
        assert len(prov) == 1
        assert prov[0]["source_pattern"] == _SOURCE_PATTERN


class TestImportMegascansExecute:

    def test_idempotent(self, mock_stage, mock_hou):

        mock_stage.createNode("subnet", "component_rock")

        with patch.object(ms_mod, "hou", mock_hou):
            with patch.object(ms_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                result = execute({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})

        assert result["status"] == "already_exists"

    def test_creates_sop_chain(self, mock_stage, mock_hou):

        with patch.object(ms_mod, "hou", mock_hou):
            with patch.object(ms_mod, "HOU_AVAILABLE", True):
                mock_hou.node.side_effect = lambda p: mock_stage if p == "/stage" else None
                mock_hou.undos.group.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock(return_value=False))
                result = execute({"usdc_path": "/tmp/rock.usdc", "asset_name": "rock"})

        assert result["status"] == "created"
        assert len(result["geometry_nodes"]) >= 3  # import, xform, matchsize, polyreduce
        assert result["material_reference"] is not None
