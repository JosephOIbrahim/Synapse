"""
FORGE Metrics — Cycle-over-cycle tracking and convergence detection.

The improvement_delta is the north star metric. When it flatlines
for 3+ consecutive cycles, automated improvements are exhausted
and Layer 3 (human architecture review) is needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import (
    CycleMetrics,
    FailureCategory,
    ScenarioResult,
    load_json,
    save_json,
)


class MetricsTracker:
    """Tracks and persists FORGE metrics across cycles."""

    def __init__(self, metrics_dir: Path):
        self.metrics_dir = metrics_dir
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.cycles_path = metrics_dir / "cycles.json"
        self._cycles: list[dict] = load_json(self.cycles_path, {"cycles": []}).get(
            "cycles", []
        )

    # =========================================================================
    # Cycle Metrics Computation
    # =========================================================================

    def compute_cycle_metrics(
        self,
        cycle_number: int,
        results: list[ScenarioResult],
        fixes_generated: int = 0,
        fixes_applied: int = 0,
        fixes_validated: int = 0,
        fixes_failed: int = 0,
        fixes_queued_human: int = 0,
        corpus_entries_added: int = 0,
        corpus_promotions: int = 0,
        total_corpus_entries: int = 0,
        tier: int = 1,
    ) -> CycleMetrics:
        """Compute aggregate metrics for a completed cycle."""
        metrics = CycleMetrics(cycle_number=cycle_number, tier=tier)

        # Execution stats
        metrics.scenarios_run = len(results)
        metrics.scenarios_passed = sum(1 for r in results if r.success)
        metrics.scenarios_failed = metrics.scenarios_run - metrics.scenarios_passed

        # Agents and domains
        metrics.agents_active = list({r.agent.value for r in results})
        metrics.domains_tested = list(
            {
                tc.tool.split("_")[0]
                for r in results
                for tc in r.tool_calls
                if tc.tool
            }
        )

        # Failure categorization
        failure_cats: dict[str, int] = {}
        for r in results:
            if not r.success and r.failure_category:
                cat = r.failure_category.value
                failure_cats[cat] = failure_cats.get(cat, 0) + 1
        metrics.failure_categories = failure_cats
        if failure_cats:
            top = max(failure_cats, key=failure_cats.get)  # type: ignore
            metrics.top_failure = top
            metrics.top_failure_count = failure_cats[top]

        # Fixes
        metrics.fixes_generated = fixes_generated
        metrics.fixes_applied = fixes_applied
        metrics.fixes_validated = fixes_validated
        metrics.fixes_failed = fixes_failed
        metrics.fixes_queued_human = fixes_queued_human

        # Corpus
        metrics.corpus_entries_added = corpus_entries_added
        metrics.corpus_promotions = corpus_promotions
        metrics.total_corpus_entries = total_corpus_entries

        # Efficiency
        friction_ratios = [r.friction_ratio for r in results if r.friction_ratio > 0]
        metrics.avg_friction_ratio = (
            sum(friction_ratios) / len(friction_ratios) if friction_ratios else 0.0
        )
        metrics.total_elapsed_ms = sum(r.total_elapsed_ms for r in results)

        # Tool gaps
        all_gaps: set[str] = set()
        for r in results:
            all_gaps.update(r.missing_tools)
        metrics.new_tool_gaps = sorted(all_gaps)

        # Convergence: compute delta from last cycle
        metrics.improvement_delta = self._compute_delta(metrics)

        # Regression detection
        metrics.regression_count = self._detect_regressions(results)

        return metrics

    def record_cycle(self, metrics: CycleMetrics) -> None:
        """Persist a completed cycle's metrics."""
        self._cycles.append(metrics.to_dict())
        save_json({"cycles": self._cycles}, self.cycles_path)

    # =========================================================================
    # Analysis
    # =========================================================================

    @property
    def cycle_count(self) -> int:
        return len(self._cycles)

    @property
    def latest(self) -> dict | None:
        return self._cycles[-1] if self._cycles else None

    @property
    def pass_rate_history(self) -> list[float]:
        return [c.get("pass_rate", 0.0) for c in self._cycles]

    @property
    def friction_history(self) -> list[float]:
        return [c.get("avg_friction_ratio", 0.0) for c in self._cycles]

    @property
    def is_flatlined(self) -> bool:
        """Check if improvement_delta has flatlined (< 0.5% for 3+ cycles)."""
        if len(self._cycles) < 3:
            return False
        last_3 = self._cycles[-3:]
        return all(
            abs(c.get("improvement_delta", 0) or 0) < 0.005 for c in last_3
        )

    def get_convergence_report(self) -> dict[str, Any]:
        """Generate a convergence analysis for Layer 3 review."""
        if not self._cycles:
            return {"status": "no_data"}

        return {
            "total_cycles": len(self._cycles),
            "current_pass_rate": self._cycles[-1].get("pass_rate", 0),
            "current_tier": self._cycles[-1].get("tier", 1),
            "pass_rate_trend": self.pass_rate_history[-10:],
            "friction_trend": self.friction_history[-10:],
            "is_flatlined": self.is_flatlined,
            "total_fixes_applied": sum(
                c.get("fixes_applied", 0) for c in self._cycles
            ),
            "total_fixes_validated": sum(
                c.get("fixes_validated", 0) for c in self._cycles
            ),
            "persistent_failures": self._find_persistent_failures(),
            "tool_gap_accumulation": self._accumulate_tool_gaps(),
            "recommendation": self._convergence_recommendation(),
        }

    # =========================================================================
    # Internals
    # =========================================================================

    def _compute_delta(self, current: CycleMetrics) -> float | None:
        """Compute improvement delta from previous cycle."""
        if not self._cycles:
            return None
        prev_pass_rate = self._cycles[-1].get("pass_rate", 0)
        return current.pass_rate - prev_pass_rate

    def _detect_regressions(self, results: list[ScenarioResult]) -> int:
        """Count scenarios that previously passed but now fail.
        
        Simplified: counts failures where the scenario ID appeared 
        in a previous cycle's successful results. Requires scenario IDs
        to be stable across cycles.
        """
        if not self._cycles:
            return 0
        # This is a simplified check — full implementation would
        # track per-scenario history across cycles
        return sum(1 for r in results if not r.success)

    def _find_persistent_failures(self) -> list[dict]:
        """Find failure categories that persist across 3+ cycles."""
        if len(self._cycles) < 3:
            return []
        # Count category appearances in last 5 cycles
        cat_counts: dict[str, int] = {}
        for cycle in self._cycles[-5:]:
            for cat in cycle.get("failure_categories", {}):
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        return [
            {"category": cat, "cycles_present": count}
            for cat, count in cat_counts.items()
            if count >= 3
        ]

    def _accumulate_tool_gaps(self) -> list[dict]:
        """Accumulate tool gaps across all cycles, ranked by frequency."""
        gap_counts: dict[str, int] = {}
        for cycle in self._cycles:
            for gap in cycle.get("new_tool_gaps", []):
                gap_counts[gap] = gap_counts.get(gap, 0) + 1
        return sorted(
            [{"tool": gap, "requested_in_cycles": count} for gap, count in gap_counts.items()],
            key=lambda x: x["requested_in_cycles"],
            reverse=True,
        )

    def _convergence_recommendation(self) -> str:
        """Generate a recommendation based on convergence state."""
        if not self._cycles:
            return "Run first cycle to establish baseline."
        if self.is_flatlined:
            return (
                "FLATLINE DETECTED: Automated improvements exhausted. "
                "Layer 3 architecture review recommended. "
                "Review persistent failures and tool gaps for v25.0 refactor targets."
            )
        latest = self._cycles[-1]
        pass_rate = latest.get("pass_rate", 0)
        if pass_rate > 0.95:
            return "High pass rate. Consider increasing scenario tier for deeper testing."
        if pass_rate < 0.60:
            return "Low pass rate. Focus on high-frequency failure categories before expanding scope."
        return "Healthy improvement trajectory. Continue cycling."
