"""
Tests for shared/conductor_advisor.py — the read side of the
self-observability loop.

Validates that the advisor:
  - Stays silent when input is empty (no false alarms)
  - Stays silent below the statistical-meaning threshold
  - Surfaces low-success-rate as a WARN
  - Surfaces anchor violations as CRITICAL regardless of count
  - Clusters evolution drift failures by category and recommends fixes
  - Recommends router promotion for hot fingerprints not in FAST_PATHS
  - Composes correctly via the advise_from_bridge() helper

These tests pin the contract that future passes can build on. The advisor
must NEVER mutate state, NEVER reach across module boundaries, and ALWAYS
return structured Recommendation objects rather than free-form strings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.bridge import LosslessExecutionBridge, Operation  # noqa: E402
from shared.conductor_advisor import (  # noqa: E402
    KIND_AGENT_HEALTH,
    KIND_EVOLUTION_WRITER_FIX,
    KIND_ROUTER_PROMOTE,
    SEVERITY_CRITICAL,
    SEVERITY_INFO,
    SEVERITY_WARN,
    ConductorAdvisor,
    Recommendation,
    advise_from_bridge,
)
from shared.constants import FAST_PATH_PROMOTION_THRESHOLD  # noqa: E402
from shared.evolution import EvolutionIntegrity  # noqa: E402
from shared.types import AgentID  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Silence on empty / under-threshold input
# ─────────────────────────────────────────────────────────────────


class TestSilence:
    def test_empty_input_returns_no_recommendations(self):
        advisor = ConductorAdvisor()
        assert advisor.analyze() == []

    def test_under_threshold_ops_no_health_alarm(self):
        advisor = ConductorAdvisor()
        # 5 ops, all failing — but below MIN_OPS_FOR_VERDICT (10), so silence
        recs = advisor.analyze(bridge_stats={
            "operations_total": 5,
            "operations_verified": 0,
            "anchor_violations": 0,
            "success_rate": 0.0,
        })
        assert recs == []

    def test_single_evolution_failure_no_writer_alarm(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(evolution_failures=[
            EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: foo"]),
        ])
        # Below DRIFT_FIELD_CLUSTER_THRESHOLD (3), so noise — no recommendation
        assert recs == []


# ─────────────────────────────────────────────────────────────────
# Bridge health analysis
# ─────────────────────────────────────────────────────────────────


class TestBridgeHealth:
    def test_low_success_rate_triggers_warn(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 50,
            "operations_verified": 40,
            "anchor_violations": 0,
            "success_rate": 0.80,  # below 0.85 threshold
        })
        health = [r for r in recs if r.kind == KIND_AGENT_HEALTH]
        assert len(health) == 1
        assert health[0].severity == SEVERITY_WARN
        assert "80%" in health[0].rationale
        assert health[0].evidence["operations_total"] == 50

    def test_anchor_violation_is_critical_regardless_of_count(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 1,
            "operations_verified": 0,
            "anchor_violations": 1,
            "success_rate": 0.0,
        })
        critical = [r for r in recs if r.severity == SEVERITY_CRITICAL]
        assert len(critical) == 1
        assert "anchor violation" in critical[0].rationale.lower()

    def test_healthy_bridge_no_recommendations(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(bridge_stats={
            "operations_total": 100,
            "operations_verified": 100,
            "anchor_violations": 0,
            "success_rate": 1.0,
        })
        assert recs == []

    def test_confidence_scales_with_sample_size(self):
        advisor = ConductorAdvisor()
        small = advisor.analyze(bridge_stats={
            "operations_total": 20,
            "operations_verified": 10,
            "anchor_violations": 0,
            "success_rate": 0.5,
        })[0]
        large = advisor.analyze(bridge_stats={
            "operations_total": 200,
            "operations_verified": 100,
            "anchor_violations": 0,
            "success_rate": 0.5,
        })[0]
        assert large.confidence > small.confidence
        assert large.confidence == 1.0  # capped


# ─────────────────────────────────────────────────────────────────
# Evolution drift clustering
# ─────────────────────────────────────────────────────────────────


class TestEvolutionDrift:
    def test_three_drifts_same_category_warn(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(evolution_failures=[
            EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: a"]),
            EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: b"]),
            EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: c"]),
        ])
        fix = [r for r in recs if r.kind == KIND_EVOLUTION_WRITER_FIX]
        assert len(fix) == 1
        assert fix[0].target == "Decision content drift"
        assert fix[0].severity == SEVERITY_WARN
        assert fix[0].evidence["count"] == 3

    def test_five_drifts_escalate_to_critical(self):
        advisor = ConductorAdvisor()
        failures = [
            EvolutionIntegrity(fidelity=0.0, failures=[f"Asset content drift: a{i}"])
            for i in range(5)
        ]
        recs = advisor.analyze(evolution_failures=failures)
        critical = [r for r in recs if r.kind == KIND_EVOLUTION_WRITER_FIX]
        assert len(critical) == 1
        assert critical[0].severity == SEVERITY_CRITICAL

    def test_mixed_categories_get_independent_recommendations(self):
        advisor = ConductorAdvisor()
        failures = [
            EvolutionIntegrity(fidelity=0.0, failures=[
                "Decision content drift: x",
                "Asset lost: y",
            ]),
            EvolutionIntegrity(fidelity=0.0, failures=[
                "Decision content drift: z",
                "Asset lost: w",
            ]),
            EvolutionIntegrity(fidelity=0.0, failures=[
                "Decision content drift: q",
                "Asset lost: r",
            ]),
        ]
        recs = advisor.analyze(evolution_failures=failures)
        targets = {r.target for r in recs if r.kind == KIND_EVOLUTION_WRITER_FIX}
        assert "Decision content drift" in targets
        assert "Asset lost" in targets
        assert len(targets) == 2


# ─────────────────────────────────────────────────────────────────
# Router promotion analysis
# ─────────────────────────────────────────────────────────────────


class TestRouterPromotion:
    def test_hot_unknown_fingerprint_recommended(self):
        advisor = ConductorAdvisor()
        # Use a fingerprint that's clearly not in FAST_PATHS
        recs = advisor.analyze(routing_fingerprints={
            "architecture|moderate|testing|normal": FAST_PATH_PROMOTION_THRESHOLD,
        })
        promotes = [r for r in recs if r.kind == KIND_ROUTER_PROMOTE]
        assert len(promotes) == 1
        assert promotes[0].severity == SEVERITY_INFO
        assert "FAST_PATHS" in promotes[0].rationale

    def test_known_fast_path_not_recommended(self):
        from shared.constants import FAST_PATHS
        advisor = ConductorAdvisor()
        # Pick an existing FAST_PATHS key and pretend it's been hit a lot
        existing_key = next(iter(FAST_PATHS))
        recs = advisor.analyze(routing_fingerprints={
            existing_key: FAST_PATH_PROMOTION_THRESHOLD * 5,
        })
        # Already hand-tuned — no need to recommend
        assert not any(r.kind == KIND_ROUTER_PROMOTE for r in recs)

    def test_under_threshold_fingerprint_not_recommended(self):
        advisor = ConductorAdvisor()
        recs = advisor.analyze(routing_fingerprints={
            "novel|trivial|testing|normal": FAST_PATH_PROMOTION_THRESHOLD - 1,
        })
        assert not any(r.kind == KIND_ROUTER_PROMOTE for r in recs)


# ─────────────────────────────────────────────────────────────────
# Recommendation contract — pinning the schema future passes will rely on
# ─────────────────────────────────────────────────────────────────


class TestRecommendationContract:
    def test_recommendation_is_frozen(self):
        rec = Recommendation(
            kind=KIND_AGENT_HEALTH, target="test", rationale="r",
            confidence=0.5,
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.kind = "mutated"  # type: ignore[misc]

    def test_to_dict_shape(self):
        rec = Recommendation(
            kind=KIND_AGENT_HEALTH, target="bridge", rationale="r",
            confidence=0.8, severity=SEVERITY_WARN,
            evidence={"foo": 1},
        )
        d = rec.to_dict()
        for key in ("kind", "target", "rationale", "confidence", "severity", "evidence"):
            assert key in d
        assert d["confidence"] == 0.8

    def test_severity_is_one_of_three(self):
        for sev in (SEVERITY_INFO, SEVERITY_WARN, SEVERITY_CRITICAL):
            rec = Recommendation(
                kind=KIND_AGENT_HEALTH, target="t", rationale="r",
                confidence=1.0, severity=sev,
            )
            assert rec.severity in (SEVERITY_INFO, SEVERITY_WARN, SEVERITY_CRITICAL)


# ─────────────────────────────────────────────────────────────────
# End-to-end: advise_from_bridge — the convenience helper
# ─────────────────────────────────────────────────────────────────


class TestAdviseFromBridge:
    def test_pulls_stats_from_real_bridge(self):
        bridge = LosslessExecutionBridge()

        def _noop():
            return "ok"

        # Generate enough operations to cross the verdict threshold
        for _ in range(20):
            bridge.execute(Operation(
                agent_id=AgentID.OBSERVER,
                operation_type="read_network",
                summary="t",
                fn=_noop,
            ))

        # Healthy bridge → no recommendations from health analyzer
        recs = advise_from_bridge(bridge)
        health = [r for r in recs if r.kind == KIND_AGENT_HEALTH]
        assert health == []

    def test_composes_all_three_analyzers(self):
        bridge = LosslessExecutionBridge()

        # Inject low success rate via stats fixture (simulated)
        # Use a stub advisor with explicit stats to test composition
        advisor = ConductorAdvisor()
        recs = advisor.analyze(
            bridge_stats={
                "operations_total": 50, "operations_verified": 30,
                "anchor_violations": 1, "success_rate": 0.6,
            },
            evolution_failures=[
                EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: a"]),
                EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: b"]),
                EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: c"]),
            ],
            routing_fingerprints={
                "novel|complex|testing|normal": FAST_PATH_PROMOTION_THRESHOLD * 2,
            },
        )
        kinds = {r.kind for r in recs}
        assert KIND_AGENT_HEALTH in kinds          # success rate + anchor
        assert KIND_EVOLUTION_WRITER_FIX in kinds  # 3 drifts of same category
        assert KIND_ROUTER_PROMOTE in kinds        # hot novel fingerprint
        # And the two health items should both be present
        health = [r for r in recs if r.kind == KIND_AGENT_HEALTH]
        assert len(health) == 2

    def test_advisor_never_mutates_inputs(self):
        """Read-only contract — inputs survive analysis unchanged."""
        bridge_stats = {
            "operations_total": 50, "operations_verified": 30,
            "anchor_violations": 0, "success_rate": 0.6,
        }
        original_stats = dict(bridge_stats)
        failures = [
            EvolutionIntegrity(fidelity=0.0, failures=["Decision content drift: x"]),
        ]
        original_failures_count = len(failures)
        fingerprints = {"a|b|c|d": 5}
        original_fingerprints = dict(fingerprints)

        ConductorAdvisor().analyze(
            bridge_stats=bridge_stats,
            evolution_failures=failures,
            routing_fingerprints=fingerprints,
        )

        assert bridge_stats == original_stats
        assert len(failures) == original_failures_count
        assert fingerprints == original_fingerprints
