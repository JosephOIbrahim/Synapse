"""
Tests for pass-7 work:
  - Per-agent success/failure tracking in LosslessExecutionBridge
  - Per-agent recommendations in ConductorAdvisor
  - tests/_conformance.py canonical-constant pinning helper
  - Real canonical pin: charmander/charmeleon/charizard across all consumers
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from shared.bridge import LosslessExecutionBridge, Operation  # noqa: E402
from shared.conductor_advisor import (  # noqa: E402
    KIND_AGENT_HEALTH,
    SEVERITY_WARN,
    ConductorAdvisor,
)
from shared.types import AgentID  # noqa: E402

import _conformance  # noqa: E402
from _conformance import assert_value_in_all_files  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Per-agent success tracking
# ─────────────────────────────────────────────────────────────────


class TestPerAgentTracking:
    def _ok_op(self, agent: AgentID) -> Operation:
        def _noop():
            return "ok"
        return Operation(
            agent_id=agent,
            operation_type="read_network",
            summary="ok",
            fn=_noop,
        )

    def _fail_op(self, agent: AgentID) -> Operation:
        def _boom():
            raise RuntimeError("expected")
        return Operation(
            agent_id=agent,
            operation_type="read_network",
            summary="boom",
            fn=_boom,
        )

    def test_per_agent_total_increments(self):
        bridge = LosslessExecutionBridge()
        for _ in range(3):
            bridge.execute(self._ok_op(AgentID.HANDS))
        for _ in range(2):
            bridge.execute(self._ok_op(AgentID.OBSERVER))

        stats = bridge.operation_stats()
        assert stats["per_agent"][AgentID.HANDS.value] == 3
        assert stats["per_agent"][AgentID.OBSERVER.value] == 2

    def test_per_agent_verified_only_counts_successes(self):
        bridge = LosslessExecutionBridge()
        for _ in range(4):
            bridge.execute(self._ok_op(AgentID.BRAINSTEM))
        for _ in range(2):
            bridge.execute(self._fail_op(AgentID.BRAINSTEM))

        stats = bridge.operation_stats()
        assert stats["per_agent"][AgentID.BRAINSTEM.value] == 6
        assert stats["per_agent_verified"][AgentID.BRAINSTEM.value] == 4
        rate = stats["per_agent_success_rate"][AgentID.BRAINSTEM.value]
        assert abs(rate - (4 / 6)) < 1e-9

    def test_per_agent_independent(self):
        """One agent's failures should not pollute another's success rate."""
        bridge = LosslessExecutionBridge()
        for _ in range(5):
            bridge.execute(self._ok_op(AgentID.HANDS))
        for _ in range(5):
            bridge.execute(self._fail_op(AgentID.BRAINSTEM))

        stats = bridge.operation_stats()
        assert stats["per_agent_success_rate"][AgentID.HANDS.value] == 1.0
        assert stats["per_agent_success_rate"][AgentID.BRAINSTEM.value] == 0.0

    def test_per_agent_survives_log_eviction(self):
        """Per-agent counters are lifetime totals — bounded log eviction
        must not reset them."""
        bridge = LosslessExecutionBridge(log_max_size=3)
        for _ in range(10):
            bridge.execute(self._ok_op(AgentID.HANDS))

        stats = bridge.operation_stats()
        assert stats["per_agent"][AgentID.HANDS.value] == 10
        assert stats["per_agent_verified"][AgentID.HANDS.value] == 10
        # Log itself was evicted to capacity
        assert stats["log_size"] == 3


# ─────────────────────────────────────────────────────────────────
# ConductorAdvisor: per-agent recommendations
# ─────────────────────────────────────────────────────────────────


class TestPerAgentAdvisor:
    def test_low_per_agent_rate_recommends_specific_agent(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 100,
            "operations_verified": 95,
            "anchor_violations": 0,
            "success_rate": 0.95,  # bridge healthy overall
            "per_agent": {"HANDS": 50, "BRAINSTEM": 50},
            "per_agent_success_rate": {"HANDS": 1.0, "BRAINSTEM": 0.7},
        })
        # Bridge overall is healthy → no bridge-level recommendation
        # But BRAINSTEM specifically should be flagged
        targets = {(r.kind, r.target) for r in recs}
        assert (KIND_AGENT_HEALTH, "BRAINSTEM") in targets
        assert (KIND_AGENT_HEALTH, "HANDS") not in targets
        assert (KIND_AGENT_HEALTH, "bridge") not in targets

    def test_per_agent_below_min_ops_silent(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 100,
            "operations_verified": 95,
            "anchor_violations": 0,
            "success_rate": 0.95,
            "per_agent": {"HANDS": 50, "BRAINSTEM": 5},  # 5 < MIN_OPS
            "per_agent_success_rate": {"HANDS": 1.0, "BRAINSTEM": 0.0},
        })
        targets = {(r.kind, r.target) for r in recs}
        # BRAINSTEM has 0% success but only 5 ops — statistical noise
        assert (KIND_AGENT_HEALTH, "BRAINSTEM") not in targets

    def test_per_agent_recommendation_evidence_includes_agent(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 100,
            "operations_verified": 95,
            "anchor_violations": 0,
            "success_rate": 0.95,
            "per_agent": {"OBSERVER": 30},
            "per_agent_success_rate": {"OBSERVER": 0.5},
        })
        observer_recs = [r for r in recs if r.target == "OBSERVER"]
        assert len(observer_recs) == 1
        assert observer_recs[0].evidence["agent"] == "OBSERVER"
        assert observer_recs[0].evidence["operations_total"] == 30
        assert observer_recs[0].evidence["success_rate"] == 0.5
        assert observer_recs[0].severity == SEVERITY_WARN

    def test_advisor_handles_missing_per_agent_keys_gracefully(self):
        """Old bridge_stats dicts (without per-agent fields) must not crash."""
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 100,
            "operations_verified": 100,
            "anchor_violations": 0,
            "success_rate": 1.0,
            # No per_agent or per_agent_success_rate keys
        })
        # Just shouldn't raise; healthy bridge → no recommendations
        assert recs == []


# ─────────────────────────────────────────────────────────────────
# Canonical-constant pinning helper
# ─────────────────────────────────────────────────────────────────


class TestConformanceHelper:
    def test_passes_when_value_present_in_all(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("hello world")
        b.write_text("the world is wide")
        # Use a temporary helper invocation by patching the repo root
        import _conformance
        original_root = _conformance._REPO_ROOT
        _conformance._REPO_ROOT = tmp_path
        try:
            _conformance.assert_value_in_all_files(
                value="world",
                files=["a.txt", "b.txt"],
                description="test value",
            )
        finally:
            _conformance._REPO_ROOT = original_root

    def test_fails_with_clear_diagnostic_when_missing(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("hello world")
        b.write_text("nothing here")
        import _conformance
        original_root = _conformance._REPO_ROOT
        _conformance._REPO_ROOT = tmp_path
        try:
            with pytest.raises(AssertionError) as excinfo:
                _conformance.assert_value_in_all_files(
                    value="world",
                    files=["a.txt", "b.txt"],
                    description="test value",
                )
            msg = str(excinfo.value)
            assert "test value" in msg
            assert "b.txt" in msg
            assert "a.txt" not in msg or "Files missing" in msg
        finally:
            _conformance._REPO_ROOT = original_root

    def test_word_boundary_avoids_substring_false_positive(self, tmp_path):
        a = tmp_path / "a.txt"
        a.write_text("worldwide")  # contains 'world' as substring but not as word
        import _conformance
        original_root = _conformance._REPO_ROOT
        _conformance._REPO_ROOT = tmp_path
        try:
            with pytest.raises(AssertionError):
                _conformance.assert_value_in_all_files(
                    value="world",
                    files=["a.txt"],
                    word_boundary=True,
                )
            # With word_boundary=False the substring counts
            _conformance.assert_value_in_all_files(
                value="world",
                files=["a.txt"],
                word_boundary=False,
            )
        finally:
            _conformance._REPO_ROOT = original_root

    def test_missing_file_is_a_failure(self, tmp_path):
        import _conformance
        original_root = _conformance._REPO_ROOT
        _conformance._REPO_ROOT = tmp_path
        try:
            with pytest.raises(AssertionError) as excinfo:
                _conformance.assert_value_in_all_files(
                    value="anything",
                    files=["does_not_exist.txt"],
                )
            assert "not found" in str(excinfo.value).lower()
        finally:
            _conformance._REPO_ROOT = original_root


# ─────────────────────────────────────────────────────────────────
# Real-world canonical pin: Pokémon evolution stage names
# This is what would have caught F1 from pass 5 automatically.
# ─────────────────────────────────────────────────────────────────


class TestPokemonStageCanonicalPin:
    def test_charmander_referenced_in_all_consumers(self):
        assert_value_in_all_files(
            value="charmander",
            files=[
                "shared/constants.py",
                "python/synapse/memory/scene_memory.py",
                "python/synapse/memory/evolution.py",
                "tests/test_scene_memory.py",
                "CLAUDE.md",
            ],
            description="canonical evolution stage 1 name",
        )

    def test_charmeleon_referenced_in_all_consumers(self):
        assert_value_in_all_files(
            value="charmeleon",
            files=[
                "shared/constants.py",
                "python/synapse/memory/scene_memory.py",
                "tests/test_scene_memory.py",
                "CLAUDE.md",
            ],
            description="canonical evolution stage 2 name",
        )

    def test_charizard_referenced_in_all_consumers(self):
        assert_value_in_all_files(
            value="charizard",
            files=[
                "shared/constants.py",
                "python/synapse/memory/scene_memory.py",
                "tests/test_scene_memory.py",
                "CLAUDE.md",
            ],
            description="canonical evolution stage 3 name",
        )


# ─────────────────────────────────────────────────────────────────
# CLAUDE.md §16 conformance — pin the recursive observability loop
# documentation against the actual API surface so doc drift fails loud
# ─────────────────────────────────────────────────────────────────


class TestClaudeMd16RecursiveLoopConformance:
    """Pin every public API the §16 documentation claims exists.

    The previous review found CLAUDE.md drifting three fires behind code.
    These tests ensure §16 stays in sync: each identifier must appear in
    both the doc and the implementing module.
    """

    def test_operation_stats_documented_and_implemented(self):
        assert_value_in_all_files(
            value="operation_stats",
            files=["CLAUDE.md", "shared/bridge.py"],
            description="bridge operation_stats public API",
        )

    def test_recent_operations_documented_and_implemented(self):
        assert_value_in_all_files(
            value="recent_operations",
            files=["CLAUDE.md", "shared/bridge.py"],
            description="bridge recent_operations public API",
        )

    def test_fingerprint_counts_documented_and_implemented(self):
        assert_value_in_all_files(
            value="fingerprint_counts",
            files=["CLAUDE.md", "shared/router.py"],
            description="router fingerprint_counts public accessor",
        )

    def test_conductor_advisor_documented_and_implemented(self):
        assert_value_in_all_files(
            value="ConductorAdvisor",
            files=["CLAUDE.md", "shared/conductor_advisor.py"],
            description="ConductorAdvisor module",
        )

    def test_recommendation_history_documented_and_implemented(self):
        assert_value_in_all_files(
            value="RecommendationHistory",
            files=["CLAUDE.md", "shared/conductor_advisor.py"],
            description="RecommendationHistory module",
        )

    def test_advise_from_bridge_documented_and_implemented(self):
        assert_value_in_all_files(
            value="advise_from_bridge",
            files=["CLAUDE.md", "shared/conductor_advisor.py"],
            description="advise_from_bridge convenience helper",
            word_boundary=False,  # underscored identifier — keep loose
        )

    def test_analyze_history_documented_and_implemented(self):
        assert_value_in_all_files(
            value="analyze_history",
            files=["CLAUDE.md", "shared/conductor_advisor.py"],
            description="ConductorAdvisor.analyze_history meta-recursion",
            word_boundary=False,
        )

    def test_per_agent_success_rate_documented_and_implemented(self):
        assert_value_in_all_files(
            value="per_agent_success_rate",
            files=["CLAUDE.md", "shared/bridge.py"],
            description="per-agent success rate stat",
            word_boundary=False,
        )

    def test_kind_constants_documented(self):
        # The Recommendation kinds described in §16.3
        for kind in ("agent_health", "evolution_writer_fix", "router_promote",
                     "repeated_recommendation"):
            assert_value_in_all_files(
                value=kind,
                files=["CLAUDE.md", "shared/conductor_advisor.py"],
                description=f"Recommendation kind {kind!r}",
                word_boundary=False,
            )

    def test_thresholds_documented_and_implemented(self):
        # Thresholds named in §16.4 — values pinned by the test surface
        for name in ("MIN_OPS_FOR_VERDICT", "DRIFT_FIELD_CLUSTER_THRESHOLD",
                     "REPEATED_RECOMMENDATION_THRESHOLD"):
            assert_value_in_all_files(
                value=name,
                files=["CLAUDE.md", "shared/conductor_advisor.py"],
                description=f"advisor threshold {name}",
            )

    def test_section_16_anchor_present(self):
        """The whole §16 must exist with its title — single sanity check."""
        assert_value_in_all_files(
            value="Recursive Observability Loop",
            files=["CLAUDE.md"],
            description="CLAUDE.md §16 section title",
        )
