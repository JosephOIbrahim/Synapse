"""
Synapse — Solaris Context Inference Tests

Tests _infer_parent() for correct parent network inference and
_solaris_context_block() for context-aware system prompt guidance.
These tests prevent regression of the Solaris context fix that
eliminates the hardcoded /obj default bias.

Run:
    python -m pytest tests/test_solaris_context.py -v
"""

import sys
import os

import pytest

# Add package to path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.routing.planner import _infer_parent
from synapse.panel.system_prompt import _solaris_context_block


# =============================================================================
# TestInferParent — context-aware parent inference
# =============================================================================


class TestInferParent:
    """Tests for _infer_parent() from synapse.routing.planner."""

    # -- Explicit parent always wins --

    def test_explicit_parent_always_wins(self):
        """Explicit 'parent' key takes priority over all signals."""
        assert _infer_parent({"parent": "/custom/path"}) == "/custom/path"

    def test_explicit_parent_overrides_solaris_signals(self):
        """Explicit parent wins even when Solaris signals are present."""
        assert _infer_parent({"parent": "/obj", "type": "domelight"}) == "/obj"

    def test_explicit_parent_overrides_sop_signals(self):
        """Explicit parent wins even when SOP signals are present."""
        assert _infer_parent({"parent": "/stage", "type": "box"}) == "/stage"

    # -- current_network context --

    def test_current_network_stage(self):
        """current_network='/stage' contains 'stage' signal -> /stage."""
        assert _infer_parent({"current_network": "/stage"}) == "/stage"

    # -- LOP node types -> /stage --

    def test_lop_domelight(self):
        """domelight contains 'light' Solaris signal."""
        assert _infer_parent({"type": "domelight"}) == "/stage"

    def test_lop_rectlight(self):
        """rectlight contains 'light' Solaris signal."""
        assert _infer_parent({"type": "rectlight"}) == "/stage"

    def test_lop_materiallibrary(self):
        """materiallibrary contains 'material' Solaris signal."""
        assert _infer_parent({"type": "materiallibrary"}) == "/stage"

    def test_lop_karmarenderproperties(self):
        """karmarenderproperties contains 'render' Solaris signal."""
        assert _infer_parent({"type": "karmarenderproperties"}) == "/stage"

    def test_lop_sopcreate_with_context(self):
        """sopcreate is a Solaris LOP but contains 'sop' SOP signal.

        In realistic usage, additional Solaris context (network path,
        intent) disambiguates. 'sop' in 'sopcreate' ties with a single
        Solaris signal, so we need enough context to break the tie.
        """
        # Realistic: sopcreate used in a Solaris/USD stage context
        assert _infer_parent({"type": "sopcreate", "context": "solaris usd stage"}) == "/stage"

    def test_lop_assignmaterial(self):
        """assignmaterial contains 'material' Solaris signal."""
        assert _infer_parent({"type": "assignmaterial"}) == "/stage"

    def test_lop_camera_with_context(self):
        """camera has no inherent Solaris signal.

        In realistic usage, Solaris context disambiguates.
        With light/render context, correctly infers /stage.
        """
        assert _infer_parent({"type": "camera", "intent": "set up camera and light"}) == "/stage"

    # -- SOP node types -> /obj --

    def test_sop_box(self):
        """box has no signals, defaults to /obj."""
        assert _infer_parent({"type": "box"}) == "/obj"

    def test_sop_scatter(self):
        """scatter has no signals, defaults to /obj."""
        assert _infer_parent({"type": "scatter"}) == "/obj"

    def test_sop_attribwrangle(self):
        """attribwrangle has no signals, defaults to /obj."""
        assert _infer_parent({"type": "attribwrangle"}) == "/obj"

    def test_sop_filecache(self):
        """filecache has no signals, defaults to /obj."""
        assert _infer_parent({"type": "filecache"}) == "/obj"

    # -- Intent-based inference --

    def test_intent_camera_and_light(self):
        """'camera and light' contains 'light' Solaris signal."""
        assert _infer_parent({"intent": "camera and light setup"}) == "/stage"

    def test_intent_karma_render(self):
        """'karma render' contains both 'karma' and 'render' Solaris signals."""
        assert _infer_parent({"intent": "karma render settings"}) == "/stage"

    def test_intent_scatter_points(self):
        """'scatter points' has no signals, defaults to /obj."""
        assert _infer_parent({"intent": "scatter points on surface"}) == "/obj"

    def test_intent_vex_wrangle(self):
        """'vex wrangle' has no signals, defaults to /obj."""
        assert _infer_parent({"intent": "vex wrangle for attributes"}) == "/obj"

    # -- Edge cases --

    def test_empty_params_default_obj(self):
        """Empty params dict defaults to /obj."""
        assert _infer_parent({}) == "/obj"

    # -- Canonical Solaris chain regression guard --

    @pytest.mark.parametrize("node_type", [
        "domelight",
        "rectlight",
        "materiallibrary",
        "karmarenderproperties",
        "assignmaterial",
        "sublayer",
        "reference",
    ])
    def test_canonical_solaris_chain_nodes(self, node_type):
        """Every node with inherent Solaris signals must infer /stage.

        These node type names contain substrings that match SOLARIS_SIGNALS
        ('light', 'material', 'render', 'sublayer', 'reference'), ensuring
        they always route to /stage without additional context.
        """
        assert _infer_parent({"type": node_type}) == "/stage"


# =============================================================================
# TestSystemPromptContext — context-aware system prompt guidance
# =============================================================================


class TestSystemPromptContext:
    """Tests for _solaris_context_block() from synapse.panel.system_prompt."""

    def test_stage_network_produces_solaris_guidance(self):
        """network='/stage' produces Solaris/LOP guidance with key rules."""
        result = _solaris_context_block({"network": "/stage"})
        assert result is not None
        assert "Solaris" in result
        # Guidance includes sublayer as the way to bring geo into stage
        assert "sublayer" in result.lower()

    def test_obj_network_produces_sop_guidance(self):
        """network='/obj' produces SOP guidance."""
        result = _solaris_context_block({"network": "/obj"})
        assert result is not None
        assert "SOP" in result

    def test_empty_context_no_crash(self):
        """Empty context dict does not crash."""
        # Should not raise — defaults to network='/obj'
        result = _solaris_context_block({})
        assert result is None or isinstance(result, str)
