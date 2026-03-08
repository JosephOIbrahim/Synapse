"""
Tests for synapse_solaris_set_purpose — RELAY-SOLARIS Phase 3
"""

import pytest
from unittest.mock import MagicMock, patch

from synapse.mcp.tools.solaris.set_purpose import (
    validate, plan, PURPOSE_OUTPUT_MAP, _SOURCE_PATTERN,
)


class TestSetPurposeValidation:

    def test_rejects_missing_component_path(self):
        with pytest.raises(Exception, match="component_path is required"):
            validate({"purpose": "render"})

    def test_rejects_invalid_purpose(self):
        with pytest.raises(Exception, match="purpose must be"):
            validate({"component_path": "/stage/comp", "purpose": "display"})

    def test_accepts_render(self):
        validate({"component_path": "/stage/comp", "purpose": "render"})

    def test_accepts_proxy(self):
        validate({"component_path": "/stage/comp", "purpose": "proxy"})

    def test_accepts_simproxy(self):
        validate({"component_path": "/stage/comp", "purpose": "simproxy"})


class TestSetPurposePlan:

    def test_plan_maps_purpose_to_output(self):
        ops = plan({"component_path": "/stage/comp", "purpose": "render"})
        assert ops[0]["output_name"] == "default"

    def test_plan_proxy_maps_to_proxy_output(self):
        ops = plan({"component_path": "/stage/comp", "purpose": "proxy"})
        assert ops[0]["output_name"] == "proxy"

    def test_plan_simproxy_maps_to_sim_proxy_output(self):
        ops = plan({"component_path": "/stage/comp", "purpose": "simproxy"})
        assert ops[0]["output_name"] == "sim proxy"

    def test_plan_includes_provenance(self):
        ops = plan({"component_path": "/stage/comp", "purpose": "render"})
        prov = [o for o in ops if o.get("op") == "stamp_provenance"]
        assert len(prov) == 1


class TestPurposeOutputMap:
    """Verify PURPOSE_OUTPUT_MAP matches Pattern 3 source material."""

    def test_render_maps_to_default(self):
        assert PURPOSE_OUTPUT_MAP["render"] == "default"

    def test_proxy_maps_to_proxy(self):
        assert PURPOSE_OUTPUT_MAP["proxy"] == "proxy"

    def test_simproxy_maps_to_sim_proxy(self):
        assert PURPOSE_OUTPUT_MAP["simproxy"] == "sim proxy"

    def test_all_purposes_have_mappings(self):
        assert set(PURPOSE_OUTPUT_MAP.keys()) == {"render", "proxy", "simproxy"}
