"""
Tests for synapse_solaris_set_purpose — RELAY-SOLARIS Phase 3
"""

import pytest

from synapse.mcp.tool_impls.solaris.set_purpose import (
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


class TestIdentityStampIsNotSwallowed:
    """SR1 crucible S5 — node identity must not depend on a swallowed write.

    `_stamped_configures` matches on the `synapse:tool` userData, so that write
    IS this tool's node identity. While it was best-effort
    (`except Exception: pass`), a failed stamp silently lost identity: the next
    call found no stamped node, created a SECOND `configureprimitive`, and the
    BLOCKER-1 stacking defect returned while the status still read "set".
    """

    class _Node:
        def __init__(self, raise_on_set=False, stored=None):
            self._raise = raise_on_set
            self._data = {}
            self._stored = stored

        def setUserData(self, key, value):
            if self._raise:
                raise RuntimeError("read-only node")
            self._data[key] = self._stored if self._stored is not None else value

        def userData(self, key):
            return self._data.get(key)

    def test_raises_when_the_write_throws(self):
        from synapse.mcp.tool_impls.solaris.set_purpose import (
            _stamp_identity, IdentityStampError,
        )
        with pytest.raises(IdentityStampError, match="could not stamp identity"):
            _stamp_identity(self._Node(raise_on_set=True))

    def test_raises_when_the_write_silently_does_not_land(self):
        """Law 1: `setUserData` returning without throwing proves nothing."""
        from synapse.mcp.tool_impls.solaris.set_purpose import (
            _stamp_identity, IdentityStampError,
        )
        with pytest.raises(IdentityStampError, match="did not land"):
            _stamp_identity(self._Node(stored=""))

    def test_a_landed_stamp_is_findable_by_the_identity_query(self):
        from synapse.mcp.tool_impls.solaris.set_purpose import (
            _stamp_identity, _TOOL_NAME,
        )
        node = self._Node()
        _stamp_identity(node)
        assert node.userData("synapse:tool") == _TOOL_NAME

    def test_provenance_propagates_the_identity_failure(self):
        """The descriptive fields stay best-effort; identity does not."""
        from synapse.mcp.tool_impls.solaris.set_purpose import (
            _stamp_provenance, IdentityStampError,
        )
        with pytest.raises(IdentityStampError):
            _stamp_provenance(self._Node(raise_on_set=True), {})
