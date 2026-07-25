"""
Tests for synapse_solaris_scene_template — RELAY-SOLARIS Phase 3
"""

import pytest

from synapse.mcp.tool_impls.solaris.scene_template import (
    validate, plan, _SOURCE_PATTERN, _TOOL_NAME, _PATH_TEMPLATES,
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

class TestF8ParentPathConvergence:
    """F8/Ruling 15 — `parent_path` is the convergent key and unknown keys are
    loud. Host-free because the defect is parameter resolution, not wiring.
    Live counterpart: `test_f8_scene_template_honours_parent_path_live`.
    """

    def test_parent_path_is_the_convergent_key(self):
        from synapse.mcp.tool_impls.solaris.scene_template import _resolve_parent_path
        assert _resolve_parent_path({"parent_path": "/stage/lopnet1"}) == "/stage/lopnet1"

    def test_parent_remains_an_accepted_alias(self):
        from synapse.mcp.tool_impls.solaris.scene_template import _resolve_parent_path
        assert _resolve_parent_path({"parent": "/stage/lopnet2"}) == "/stage/lopnet2"

    def test_parent_path_wins_over_the_alias(self):
        from synapse.mcp.tool_impls.solaris.scene_template import _resolve_parent_path
        assert _resolve_parent_path({"parent": "/a", "parent_path": "/b"}) == "/b"

    def test_defaults_to_stage_when_absent(self):
        from synapse.mcp.tool_impls.solaris.scene_template import _resolve_parent_path
        assert _resolve_parent_path({}) == "/stage"

    def test_unknown_key_raises_instead_of_defaulting(self):
        with pytest.raises(Exception, match="unknown parameter"):
            validate({"parnet_path": "/stage/lopnet1"})

    def test_known_keys_are_accepted(self):
        validate({
            "scene_name": "shot",
            "parent_path": "/stage",
            "sop_paths": ["/obj/a"],
            "render_engine": "karma_cpu",
            "resolution": [640, 480],
            "output_path": "$HIP/x.png",
        })


# SR1 M3: the mock-`hou` execute tests that stood here are DELETED per
# Constitution Law 1 / Ruling 12 item 3. Host-behaviour assertions for this
# tool now live in `tests/solaris/test_live_wiring.py`, gated on a real
# `import hou` and executed under hython 22.0.368.
