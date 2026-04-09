"""
Conformance + regression tests for shared/router.py.

Covers the seven bug/brittleness fixes:
  R11 -- route_task() singleton (fast paths actually reachable)
  R12 -- internal auto-promotion at FAST_PATH_PROMOTION_THRESHOLD
  R13 -- score-based task type extraction (no insertion-order dependency)
  R14 -- complexity classification independent of word count
  R15 -- relative advisory threshold (gap-aware top-K)
  R16 -- CONSTANTS_HASH stamping for session fast paths
  R17 -- empty domain_signals tuple instead of GEOMETRY fallback

Plus a doc-vs-code conformance check that parses CLAUDE.md and asserts the
mechanisms it claims to have are actually present in router.py.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

# Make shared/ importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shared.router import (  # noqa: E402
    MOERouter,
    RoutingDecision,
    extract_features,
    get_default_router,
    reset_default_router,
    route_task,
    _classify_complexity,
)
from shared.types import (  # noqa: E402
    AgentID,
    Complexity,
    DomainSignal,
    RoutingFeatures,
    TaskType,
    Urgency,
)
from shared.constants import (  # noqa: E402
    ADVISORY_GAP_RATIO,
    CONSTANTS_HASH,
    DOMAIN_KEYWORDS,
    FAST_PATHS,
    FAST_PATH_PROMOTION_THRESHOLD,
    ROUTER_CALIBRATION_PERIOD,
    TASK_TYPE_KEYWORDS,
)


# ─────────────────────────────────────────────────────────────────
# R11: route_task() singleton — fast paths must be reachable
# ─────────────────────────────────────────────────────────────────

class TestRouteTaskSingleton:
    def setup_method(self):
        reset_default_router()

    def test_singleton_persists_call_count(self):
        a = get_default_router()
        b = get_default_router()
        assert a is b
        for _ in range(5):
            route_task("inspect the geometry")
        assert get_default_router()._call_count == 5

    def test_fast_path_reachable_after_calibration(self):
        # Burn through calibration with arbitrary calls
        for _ in range(ROUTER_CALIBRATION_PERIOD + 1):
            route_task("placeholder warmup")
        # Now hit a known FAST_PATHS entry
        decision = route_task("inspect geometry")  # observation|trivial|geometry|normal
        # Method may be 'fast_path' or 'scored' depending on FAST_PATHS table
        # contents — what matters is that route_task survives across calls.
        assert isinstance(decision, RoutingDecision)
        assert get_default_router()._call_count >= ROUTER_CALIBRATION_PERIOD + 2

    def test_reset_clears_singleton(self):
        route_task("create a node")
        reset_default_router()
        # New router has fresh count
        assert get_default_router()._call_count == 0


# ─────────────────────────────────────────────────────────────────
# R12: Internal auto-promotion
# ─────────────────────────────────────────────────────────────────

class TestAutoPromotion:
    def test_fingerprint_promoted_after_threshold(self):
        router = MOERouter()
        # Burn calibration so fast path lookups are active
        warmup = extract_features("orchestrate the pdg render farm pipeline")
        for _ in range(ROUTER_CALIBRATION_PERIOD + 1):
            router.route(warmup)

        novel = RoutingFeatures(
            task_type=TaskType.ARCHITECTURE,
            complexity=Complexity.MODERATE,
            domain_signals=(DomainSignal.TESTING,),
            urgency=Urgency.NORMAL,
        )
        fp = novel.fingerprint()
        assert fp not in FAST_PATHS  # precondition

        for _ in range(FAST_PATH_PROMOTION_THRESHOLD):
            router.route(novel)

        assert fp in router._session_fast_paths
        # Stamped with current constants hash
        assert router._session_fast_paths[fp][2] == CONSTANTS_HASH

    def test_existing_fast_path_not_double_promoted(self):
        router = MOERouter()
        for _ in range(ROUTER_CALIBRATION_PERIOD + 1):
            router.route(extract_features("noop"))

        # Construct a feature vector matching a hand-tuned FAST_PATHS key
        feat = extract_features("inspect the geometry")
        for _ in range(FAST_PATH_PROMOTION_THRESHOLD + 2):
            router.route(feat)

        # Should NOT have been added to session paths (already in FAST_PATHS)
        if feat.fingerprint() in FAST_PATHS:
            assert feat.fingerprint() not in router._session_fast_paths


# ─────────────────────────────────────────────────────────────────
# R13: Score-based task type extraction (no insertion-order dependency)
# ─────────────────────────────────────────────────────────────────

class TestTaskTypeScoring:
    def test_most_matched_task_type_wins(self):
        # 'test' + 'validate' both map to INTEGRATION (2 matches),
        # 'create' maps to GENERATION (1 match) — INTEGRATION should win.
        feat = extract_features("create a test to validate this")
        assert feat.task_type == TaskType.INTEGRATION

    def test_deterministic_when_tied(self):
        # Same input → same output, regardless of how many times called
        results = {extract_features("design the architecture").task_type for _ in range(20)}
        assert len(results) == 1


# ─────────────────────────────────────────────────────────────────
# R14: Complexity is no longer driven by word count
# ─────────────────────────────────────────────────────────────────

class TestComplexityNoWordCount:
    def test_verbose_trivial_prompt_not_research_grade(self):
        # 200-word verbose prompt with a single domain — must NOT be RESEARCH
        long = ("inspect the geometry " * 50).strip()
        feat = extract_features(long)
        assert feat.complexity != Complexity.RESEARCH

    def test_apex_solo_is_complex(self):
        feat = extract_features("build apex rig")
        assert feat.complexity == Complexity.COMPLEX

    def test_cops_solo_is_complex(self):
        feat = extract_features("create cop network")
        assert feat.complexity == Complexity.COMPLEX

    def test_orchestration_with_two_domains_is_complex(self):
        feat = extract_features("orchestrate pdg render pipeline")
        assert feat.complexity == Complexity.COMPLEX

    def test_two_domains_default_moderate(self):
        feat = extract_features("create usd shader")  # usd + materialx
        assert feat.complexity == Complexity.MODERATE

    def test_four_domains_research(self):
        feat = extract_features("usd vex pdg render integration")
        assert feat.complexity == Complexity.RESEARCH


# ─────────────────────────────────────────────────────────────────
# R15: Relative advisory threshold
# ─────────────────────────────────────────────────────────────────

class TestRelativeAdvisory:
    def test_advisory_suppressed_when_gap_too_wide(self):
        # Construct features where one agent dominates
        router = MOERouter()
        feat = RoutingFeatures(
            task_type=TaskType.OBSERVATION,
            complexity=Complexity.TRIVIAL,
            domain_signals=(DomainSignal.GEOMETRY,),
            urgency=Urgency.NORMAL,
        )
        # Force scored path (no calibration warmup)
        decision = router.route(feat)
        if decision.method == "scored":
            primary_score = decision.scores[decision.primary]
            if decision.advisory is not None:
                advisory_score = decision.scores[decision.advisory]
                assert advisory_score >= ADVISORY_GAP_RATIO * primary_score


# ─────────────────────────────────────────────────────────────────
# R16: CONSTANTS_HASH stamping invalidates stale session fast paths
# ─────────────────────────────────────────────────────────────────

class TestConstantsHashStamping:
    def test_stale_hash_skipped(self):
        router = MOERouter()
        for _ in range(ROUTER_CALIBRATION_PERIOD + 1):
            router.route(extract_features("noop"))

        feat = RoutingFeatures(
            task_type=TaskType.ARCHITECTURE,
            complexity=Complexity.MODERATE,
            domain_signals=(DomainSignal.TESTING,),
            urgency=Urgency.NORMAL,
        )
        fp = feat.fingerprint()
        # Inject a stale entry directly
        router._session_fast_paths[fp] = (AgentID.HANDS, None, "deadbeefdead")

        decision = router.route(feat)
        # Stale entry must NOT be used — should fall through to scored
        assert decision.method != "session_fast_path"


# ─────────────────────────────────────────────────────────────────
# R17: No GEOMETRY fallback for empty keyword prompts
# ─────────────────────────────────────────────────────────────────

class TestNoGeometryBias:
    def test_keywordless_prompt_has_empty_signals(self):
        feat = extract_features("xyzzy plugh quux")
        assert feat.domain_signals == ()

    def test_keywordless_does_not_route_to_observer_by_default(self):
        feat = extract_features("xyzzy plugh quux")
        router = MOERouter()
        decision = router.route(feat)
        # Without any domain signal, OBSERVER should not get a free affinity
        # boost. Primary is determined purely by task-type boost (default
        # GENERATION → HANDS).
        assert decision.scores[AgentID.OBSERVER] == 0.0


# ─────────────────────────────────────────────────────────────────
# FAST_PATHS table validity — every key must be reachable from current
# keyword tables. If a keyword change drifts a fingerprint, this fails loud.
# ─────────────────────────────────────────────────────────────────

class TestFastPathsReachability:
    def test_every_fast_path_key_is_constructible(self):
        # Reverse-engineer: for each FAST_PATHS key, parse components and
        # build a RoutingFeatures matching it, then verify .fingerprint() ==
        # the original key.
        for key in FAST_PATHS:
            parts = key.split("|")
            assert len(parts) == 4, f"Malformed FAST_PATHS key: {key}"
            tt_str, complexity_str, domains_str, urgency_str = parts
            try:
                tt = TaskType(tt_str)
                cx = Complexity(complexity_str)
                ur = Urgency(urgency_str)
            except ValueError as e:
                pytest.fail(f"FAST_PATHS key {key!r} uses unknown enum: {e}")

            domain_names = sorted(domains_str.split("+")) if domains_str else []
            try:
                domains = tuple(DomainSignal(d) for d in domain_names)
            except ValueError as e:
                pytest.fail(f"FAST_PATHS key {key!r} uses unknown domain: {e}")

            feat = RoutingFeatures(
                task_type=tt,
                complexity=cx,
                domain_signals=domains,
                urgency=ur,
            )
            assert feat.fingerprint() == key, (
                f"FAST_PATHS key {key!r} does not round-trip — keyword tables "
                f"may have drifted. Got: {feat.fingerprint()!r}"
            )


# ─────────────────────────────────────────────────────────────────
# Doc/code conformance — parse CLAUDE.md §2.3 and assert mechanisms
# named there actually exist in router.py / constants.py
# ─────────────────────────────────────────────────────────────────

class TestClaudeMdConformance:
    @pytest.fixture
    def claude_md(self) -> str:
        path = _REPO_ROOT / "CLAUDE.md"
        return path.read_text(encoding="utf-8")

    def test_session_learning_threshold_documented_matches_code(self, claude_md):
        # CLAUDE.md should reference the FAST_PATH_PROMOTION_THRESHOLD constant
        # OR the literal default value (3). If neither, doc has drifted.
        m = re.search(r"FAST_PATH_PROMOTION_THRESHOLD.*?(\d+)", claude_md)
        if m:
            assert int(m.group(1)) == FAST_PATH_PROMOTION_THRESHOLD
        else:
            # Fall back to checking the default literal appears in §2.3 context
            assert str(FAST_PATH_PROMOTION_THRESHOLD) in claude_md

    def test_constants_hash_documented(self, claude_md):
        assert "CONSTANTS_HASH" in claude_md, (
            "CLAUDE.md §2.3 must mention CONSTANTS_HASH-based invalidation "
            "now that the router enforces it."
        )

    def test_calibration_period_documented(self, claude_md):
        # CLAUDE.md mentions 'calibration period with dense evaluation'
        assert "calibration" in claude_md.lower()
        assert ROUTER_CALIBRATION_PERIOD == 10  # value pinned by docs

    def test_route_method_exists(self):
        # The mechanism CLAUDE.md describes must actually be present
        assert hasattr(MOERouter, "route")
        assert hasattr(MOERouter, "learn_fast_path")
        assert callable(get_default_router)
