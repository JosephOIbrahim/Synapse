"""
Tests for sparse_router.py (v8-DSA)

Covers: indexer top-k, keyword matching, domain detection,
calibration accuracy, recency boost, build_signatures.
"""

import sys
import os
import importlib.util

# ---------------------------------------------------------------------------
# Bootstrap: import synapse modules without hou
# ---------------------------------------------------------------------------
_SYNAPSE_ROOT = os.path.join(os.path.dirname(__file__), "..", "python")
if _SYNAPSE_ROOT not in sys.path:
    sys.path.insert(0, _SYNAPSE_ROOT)

import pytest

from synapse.agent.sparse_router import (
    CostTier,
    Domain,
    RouteCandidate,
    SparseRouterConfig,
    SparseToolIndexer,
    ToolSignature,
    build_signatures_from_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_signatures():
    """Create a set of test tool signatures."""
    return [
        ToolSignature(
            name="create_node",
            domain=Domain.SCENE,
            keywords=frozenset({"create", "node"}),
            param_patterns=frozenset({"parent", "type", "name"}),
            cost_tier=CostTier.CHEAP,
        ),
        ToolSignature(
            name="set_parm",
            domain=Domain.SCENE,
            keywords=frozenset({"set", "parm", "parameter"}),
            param_patterns=frozenset({"node", "parm", "value"}),
            cost_tier=CostTier.CHEAP,
        ),
        ToolSignature(
            name="render",
            domain=Domain.RENDER,
            keywords=frozenset({"render", "karma", "image"}),
            param_patterns=frozenset({"node", "frame", "width", "height"}),
            cost_tier=CostTier.EXPENSIVE,
        ),
        ToolSignature(
            name="create_material",
            domain=Domain.MATERIAL,
            keywords=frozenset({"create", "material", "shader"}),
            param_patterns=frozenset({"name", "base_color", "roughness"}),
            cost_tier=CostTier.CHEAP,
        ),
        ToolSignature(
            name="get_scene_info",
            domain=Domain.GENERAL,
            keywords=frozenset({"get", "scene", "info"}),
            param_patterns=frozenset(),
            cost_tier=CostTier.FREE,
            read_only=True,
        ),
        ToolSignature(
            name="tops_cook_node",
            domain=Domain.TOPS,
            keywords=frozenset({"tops", "cook", "node", "pdg"}),
            param_patterns=frozenset({"node", "blocking"}),
            cost_tier=CostTier.EXPENSIVE,
        ),
    ]


@pytest.fixture
def indexer():
    config = SparseRouterConfig(top_k=3, calibration_calls=5)
    idx = SparseToolIndexer(config)
    idx.register_tools(_make_signatures())
    return idx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestToolSignature:
    def test_frozen(self):
        sig = _make_signatures()[0]
        with pytest.raises(AttributeError):
            sig.name = "modified"  # type: ignore[misc]

    def test_to_dict_sorted(self):
        sig = _make_signatures()[0]
        d = sig.to_dict()
        assert d["name"] == "create_node"
        assert d["keywords"] == sorted(sig.keywords)
        assert d["param_patterns"] == sorted(sig.param_patterns)

    def test_read_only_flag(self):
        sigs = _make_signatures()
        scene_info = [s for s in sigs if s.name == "get_scene_info"][0]
        assert scene_info.read_only is True


class TestSparseToolIndexer:
    def test_register_and_count(self, indexer):
        assert indexer.tool_count == 6

    def test_index_returns_all_in_dense_mode(self, indexer):
        results = indexer.index(query_keywords=["create", "node"])
        # Dense mode (under calibration_calls), returns all tools
        assert len(results) == 6

    def test_index_top_k_in_sparse_mode(self):
        config = SparseRouterConfig(top_k=2, mode="sparse")
        idx = SparseToolIndexer(config)
        idx.register_tools(_make_signatures())

        results = idx.index(query_keywords=["render"])
        assert len(results) == 2

    def test_keyword_matching_scores(self, indexer):
        results = indexer.index(query_keywords=["render", "karma"])
        # The "render" tool has both keywords — should score highest
        top = results[0]
        assert top.tool_name == "render"
        assert top.match_signals["keyword"] > 0

    def test_domain_matching(self, indexer):
        results = indexer.index(
            query_keywords=["something"],
            query_domain=Domain.RENDER,
        )
        # render tool should get domain boost
        render_result = [r for r in results if r.tool_name == "render"][0]
        assert render_result.match_signals["domain"] == 1.0

    def test_param_matching(self, indexer):
        results = indexer.index(
            query_keywords=[],
            query_params=["node", "parm", "value"],
        )
        # set_parm has all three params
        set_parm = [r for r in results if r.tool_name == "set_parm"][0]
        assert set_parm.match_signals["param"] > 0

    def test_recency_boost(self, indexer):
        # Record a selection
        indexer.record_selection("get_scene_info")

        results = indexer.index(query_keywords=["anything"])
        scene_info = [r for r in results if r.tool_name == "get_scene_info"][0]
        assert scene_info.match_signals["recency"] == 1.0

    def test_deterministic_ordering(self, indexer):
        """Same input produces same output ordering."""
        r1 = indexer.index(query_keywords=["create"])
        r2 = indexer.index(query_keywords=["create"])
        assert [r.tool_name for r in r1] == [r.tool_name for r in r2]

    def test_auto_switch_to_sparse(self):
        config = SparseRouterConfig(top_k=2, calibration_calls=3, mode="dense")
        idx = SparseToolIndexer(config)
        idx.register_tools(_make_signatures())

        # First 3 calls: dense (all 6 tools)
        for _ in range(3):
            r = idx.index(query_keywords=["test"])
            assert len(r) == 6

        # 4th call: auto-switched to sparse (top 2)
        r = idx.index(query_keywords=["test"])
        assert len(r) == 2

    def test_calibration_accuracy_none_initially(self, indexer):
        assert indexer.calibration_accuracy() is None

    def test_calibration_accuracy_tracking(self, indexer):
        indexer.record_selection("render", was_correct=True)
        indexer.record_selection("render", was_correct=True)
        indexer.record_selection("render", was_correct=False)
        acc = indexer.calibration_accuracy()
        assert acc is not None
        assert abs(acc - 0.6667) < 0.01

    def test_to_dict(self, indexer):
        d = indexer.to_dict()
        assert d["tool_count"] == 6
        assert d["call_count"] == 0
        assert "mode" in d

    def test_empty_query(self, indexer):
        results = indexer.index(query_keywords=[])
        assert len(results) == 6
        # All keyword scores should be 0
        for r in results:
            assert r.match_signals["keyword"] == 0.0


class TestRouteCandidate:
    def test_to_dict_rounds_scores(self):
        rc = RouteCandidate(
            tool_name="test",
            score=0.123456789,
            match_signals={"keyword": 0.333333333},
        )
        d = rc.to_dict()
        assert d["score"] == 0.1235
        assert d["match_signals"]["keyword"] == 0.3333


class TestBuildSignatures:
    def test_basic_build(self):
        tool_defs = [
            {
                "name": "render",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node": {"type": "string"},
                        "frame": {"type": "number"},
                    },
                },
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": True,
                },
            },
            {
                "name": "get_scene_info",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": True},
            },
        ]
        sigs = build_signatures_from_registry(tool_defs)
        assert len(sigs) == 2

        render_sig = [s for s in sigs if s.name == "render"][0]
        assert render_sig.domain == Domain.RENDER
        assert render_sig.cost_tier == CostTier.EXPENSIVE
        assert "node" in render_sig.param_patterns

        info_sig = [s for s in sigs if s.name == "get_scene_info"][0]
        assert info_sig.read_only is True
        assert info_sig.cost_tier == CostTier.FREE

    def test_tops_domain_detection(self):
        sigs = build_signatures_from_registry([
            {"name": "tops_cook_node", "inputSchema": {"type": "object", "properties": {}}},
        ])
        assert sigs[0].domain == Domain.TOPS

    def test_material_domain_detection(self):
        sigs = build_signatures_from_registry([
            {"name": "create_material", "inputSchema": {"type": "object", "properties": {}}},
        ])
        assert sigs[0].domain == Domain.MATERIAL

    def test_usd_domain_detection(self):
        sigs = build_signatures_from_registry([
            {"name": "set_usd_attribute", "inputSchema": {"type": "object", "properties": {}}},
        ])
        assert sigs[0].domain == Domain.USD

    def test_memory_domain_detection(self):
        sigs = build_signatures_from_registry([
            {"name": "add_memory", "inputSchema": {"type": "object", "properties": {}}},
        ])
        assert sigs[0].domain == Domain.MEMORY

    def test_missing_annotations(self):
        """Tools without annotations should still build."""
        sigs = build_signatures_from_registry([
            {"name": "custom_tool", "inputSchema": {"type": "object", "properties": {}}},
        ])
        assert len(sigs) == 1
        assert sigs[0].read_only is False
