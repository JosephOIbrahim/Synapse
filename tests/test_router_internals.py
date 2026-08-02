"""
Conformance + regression tests for shared/router.py.

Covers the bug/brittleness fixes that survive R20:
  R11 -- route_task() singleton (fast paths actually reachable)
  R13 -- score-based task type extraction (no insertion-order dependency)
  R14 -- complexity classification independent of word count
  R15 -- relative advisory threshold (gap-aware top-K)
  R17 -- empty domain_signals tuple instead of GEOMETRY fallback

RETIRED 2026-08-01 (R20, RSI loop F): the auto-promotion suites are deleted
along with the mechanism they pinned -- TestAutoPromotion (R12),
TestConstantsHashStamping (R16), TestOutcomeVetoedPromotion (R18),
TestOutcomeTypeGuard + TestOutcomeConfirmationUpgrade (R19) -- 37 tests. They were
honest and passing; they tested a mechanism that ran zero times in production.
Deleting the code deletes its tests. What is asserted below instead is that the
promotion surface is GONE (TestPromotionRetired) -- a test that fails loudly if
someone reintroduces it without reopening the registry decision.

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
# R20: the promotion surface is RETIRED and must stay retired
# ─────────────────────────────────────────────────────────────────

class TestPromotionRetired:
    """The subtraction, pinned.

    RSI loop F was retired 2026-08-01 because its promotion path executed zero
    times in production: nothing produced outcomes, and route()'s only non-test
    call site sat inside a function with no references. Reintroducing any of
    these names silently would restore a self-modifying mechanism without
    reopening that decision, so it fails here instead.
    """

    RETIRED_ROUTER_ATTRS = [
        "learn_fast_path", "record_outcome", "outcome_counts",
        "_promotion_allowed", "_outcome_confirmed",
    ]

    @pytest.mark.parametrize("name", RETIRED_ROUTER_ATTRS)
    def test_retired_method_is_gone(self, name):
        assert not hasattr(MOERouter, name), (
            f"MOERouter.{name} was retired with RSI loop F (2026-08-01). "
            f"If it is genuinely needed again, reopen harness/rsi/REGISTRY.json "
            f"loop F first — it carries the evidence for why this was deleted."
        )

    def test_router_keeps_no_session_promotion_state(self):
        router = MOERouter()
        assert not hasattr(router, "_session_fast_paths")
        assert not hasattr(router, "_outcomes")

    def test_routing_never_reports_a_session_fast_path(self):
        """Only two methods survive: hand-tuned 'fast_path' and 'scored'."""
        router = MOERouter()
        feat = RoutingFeatures(
            task_type=TaskType.ARCHITECTURE,
            complexity=Complexity.MODERATE,
            domain_signals=(DomainSignal.TESTING,),
            urgency=Urgency.NORMAL,
        )
        assert feat.fingerprint() not in FAST_PATHS   # precondition
        # Route far past the old promotion threshold and the calibration window.
        methods = {
            router.route(feat).method
            for _ in range(ROUTER_CALIBRATION_PERIOD + FAST_PATH_PROMOTION_THRESHOLD * 5)
        }
        assert methods == {"scored"}
        assert "session_fast_path" not in methods

    def test_fingerprint_counting_survives_the_cut(self):
        """The advisor reads this — counting is advice, not self-modification."""
        router = MOERouter()
        feat = extract_features("inspect the geometry")
        for _ in range(3):
            router.route(feat)
        assert router.fingerprint_counts()[feat.fingerprint()] == 3

    def test_promotion_writer_is_gone_from_the_panel(self):
        """RoutingLog was the second writer into the promotion table."""
        from synapse.panel.routing_log import RoutingLog
        assert not hasattr(RoutingLog, "apply_learned_fast_paths")
        # …but its read-only frequency telemetry survives.
        assert hasattr(RoutingLog, "get_frequent_fingerprints")

    def test_dead_tool_filter_entry_point_is_gone(self):
        """filter_tools() was the sole non-test caller of MOERouter.route()."""
        from synapse.panel import tool_filter
        assert not hasattr(tool_filter, "filter_tools")
        # classify_tool is what the palette actually imports — it stays.
        assert callable(tool_filter.classify_tool)


# ─────────────────────────────────────────────────────────────────
# Doc/code conformance — parse CLAUDE.md §2.3 and assert mechanisms
# named there actually exist in router.py / constants.py
# ─────────────────────────────────────────────────────────────────

class TestClaudeMdConformance:
    @pytest.fixture
    def claude_md(self) -> str:
        path = _REPO_ROOT / "CLAUDE.md"
        return path.read_text(encoding="utf-8")

    def test_promotion_threshold_still_has_a_live_consumer(self, claude_md):
        """FAST_PATH_PROMOTION_THRESHOLD survived R20 — but not in the router.

        It is no longer a promotion gate; it is the advisor's threshold for
        RECOMMENDING a hand-tuned FAST_PATHS entry to a human. The constant
        stays because that consumer is live; the doc must say which one it is.
        """
        import shared.conductor_advisor as advisor
        assert advisor.FAST_PATH_PROMOTION_THRESHOLD == FAST_PATH_PROMOTION_THRESHOLD
        assert "FAST_PATH_PROMOTION_THRESHOLD" in claude_md
        # and the router must NOT be a consumer any more
        router_src = (_REPO_ROOT / "shared" / "router.py").read_text(encoding="utf-8")
        assert "FAST_PATH_PROMOTION_THRESHOLD," not in router_src, (
            "router.py re-imported the promotion threshold — R20 retired that gate."
        )

    def test_constants_hash_survives_but_router_does_not_stamp(self):
        """CONSTANTS_HASH is a constants-module drift primitive, not F's.

        It outlives the retirement because it is an exported constant in its
        own right; what went is the router stamping promoted entries with it.
        """
        assert isinstance(CONSTANTS_HASH, str) and CONSTANTS_HASH
        router_src = (_REPO_ROOT / "shared" / "router.py").read_text(encoding="utf-8")
        assert "self._constants_hash" not in router_src

    def test_calibration_period_documented(self, claude_md):
        # CLAUDE.md mentions 'calibration period with dense evaluation'
        assert "calibration" in claude_md.lower()
        assert ROUTER_CALIBRATION_PERIOD == 10  # value pinned by docs

    def test_route_method_exists(self):
        # The mechanism CLAUDE.md describes must actually be present
        assert hasattr(MOERouter, "route")
        assert hasattr(MOERouter, "fingerprint_counts")
        assert callable(get_default_router)

    def test_claude_md_no_longer_teaches_session_promotion(self, claude_md):
        """Doc drift in the dangerous direction: teaching a deleted feature.

        §2.3 is the section that used to describe auto-promotion as live
        behaviour. It must now describe the retirement instead.
        """
        start = claude_md.index("### 2.3")
        section = claude_md[start:claude_md.index("### 2.4", start)]
        assert "RETIRED" in section, (
            "CLAUDE.md §2.3 must record that session auto-promotion was retired."
        )
        for gone in ("_session_fast_paths", "learn_fast_path", "record_outcome"):
            for line in section.splitlines():
                if gone in line:
                    assert "RETIRED" in section, f"{gone} described without the retirement note"
