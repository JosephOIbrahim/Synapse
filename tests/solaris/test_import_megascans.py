"""
Tests for synapse_solaris_import_megascans — RELAY-SOLARIS Phase 3
"""

import pytest

from synapse.mcp.tool_impls.solaris.import_megascans import validate, plan, _SOURCE_PATTERN, _TOOL_NAME


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

class TestParentKeyConvergence:
    """SR1 crucible S2 / F8 / Ruling 15 — `parent_path` is the convergent key."""

    def test_parent_path_is_the_convergent_key(self):
        from synapse.mcp.tool_impls.solaris.import_megascans import _resolve_parent_path
        assert _resolve_parent_path({"parent_path": "/stage/lopnet1"}) == "/stage/lopnet1"

    def test_parent_remains_an_accepted_alias(self):
        from synapse.mcp.tool_impls.solaris.import_megascans import _resolve_parent_path
        assert _resolve_parent_path({"parent": "/stage/lopnet2"}) == "/stage/lopnet2"

    def test_parent_path_wins_over_the_alias(self):
        from synapse.mcp.tool_impls.solaris.import_megascans import _resolve_parent_path
        assert _resolve_parent_path({"parent": "/a", "parent_path": "/b"}) == "/b"

    def test_defaults_to_stage_when_absent(self):
        from synapse.mcp.tool_impls.solaris.import_megascans import _resolve_parent_path
        assert _resolve_parent_path({}) == "/stage"

    def test_unknown_key_raises_instead_of_defaulting(self):
        with pytest.raises(Exception, match="unknown parameter"):
            validate({"usdc_path": "/tmp/r.usdc", "asset_name": "rock",
                      "parnet_path": "/stage/lopnet1"})

    def test_known_keys_are_accepted(self):
        validate({
            "usdc_path": "/tmp/r.usdc", "asset_name": "rock",
            "parent_path": "/stage", "parent": "/stage", "scale_factor": 0.01,
            "ground_asset": True, "rotation_correction": [0, 0, 0],
            "proxy_reduction": 0.05, "import_materials": True,
            "export_path": "/tmp/x.usd",
        })


# SR1 M3: the mock-`hou` execute tests that stood here are DELETED per
# Constitution Law 1 / Ruling 12 item 3. Host-behaviour assertions for this
# tool now live in `tests/solaris/test_live_wiring.py`, gated on a real
# `import hou` and executed under hython 22.0.368.
