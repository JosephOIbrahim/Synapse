"""RSI loop E — FORGE's build loop must not author its own success.

Pins the honest-signal contract for `forge/engine`:

  * `fixes_applied` counts CONFIRMED applications only — never intent, never
    a classification, never a failed application.
  * `fixes_validated` is `None` ("unvalidated") unless a REAL re-run produced
    a number. A rendered `0` may only ever mean "validation ran and confirmed
    nothing".
  * The reporter renders the sentinel as the word, never as a numeral.
  * Cross-cycle aggregation tolerates the sentinel and does not sum `None`
    into a fabricated zero.

Background: `forge/engine` has NO apply/verify stage. `FORGE.md` Phase 5
("VERIFY (Re-run)") is a procedure a human or Claude Code follows, not a
module. Before this contract, `orchestrator.py` incremented `fixes_applied`
on classification with the comment "Optimistic" and passed a hardcoded
`fixes_validated=0`, which `reporter.py` printed to a human as though it were
a measurement.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from forge.engine.metrics import MetricsTracker  # noqa: E402
from forge.engine.orchestrator import ForgeOrchestrator  # noqa: E402
from forge.engine.reporter import (  # noqa: E402
    UNVALIDATED_LABEL,
    convergence_dashboard,
    cycle_report,
    validated_cell,
)
from forge.engine.schemas import (  # noqa: E402
    AgentRole,
    CycleMetrics,
    FailureCategory,
    FixOutcome,
    ScenarioResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def forge_dir(tmp_path: Path) -> Path:
    """An empty, isolated FORGE tree (never touches the repo's real one)."""
    (tmp_path / "corpus").mkdir()
    (tmp_path / "metrics").mkdir()
    (tmp_path / "scenarios").mkdir()
    (tmp_path / "backlog").mkdir()
    (tmp_path / "scenarios" / "registry.json").write_text(
        json.dumps({"scenarios": []}), encoding="utf-8"
    )
    return tmp_path


def _automated_failure(scenario_id: str = "SC-001") -> ScenarioResult:
    """A failed result whose category routes to the AUTOMATED fix destination."""
    result = ScenarioResult(
        cycle=1,
        agent=AgentRole.ENGINEER,
        scenario_id=scenario_id,
        success=False,
        failure_point="step 2",
        failure_category=FailureCategory.MISSING_CONVENTION,
        error_message="boom",
        corpus_contribution="Convention X is undocumented.",
    )
    assert result.failure_category.fix_destination == "automated"
    return result


# =============================================================================
# 1. The reporter never renders a numeric validated-count without a real one
# =============================================================================


def test_reporter_renders_unvalidated_word_not_zero() -> None:
    """No validation ran => the human sees the word, not a fabricated 0."""
    metrics = CycleMetrics(cycle_number=1, scenarios_run=4, scenarios_passed=2)
    assert metrics.fixes_validated is None  # sentinel is the default

    report = cycle_report(metrics)
    validated_line = next(ln for ln in report.splitlines() if "Validated:" in ln)

    assert UNVALIDATED_LABEL in validated_line
    # The cell must contain no digits at all — a numeral here would read as a
    # measurement to the person looking at the box.
    cell = validated_line.split("Validated:")[1]
    assert not re.search(r"\d", cell), f"numeric validated-count rendered: {cell!r}"


def test_reporter_renders_a_real_zero_when_validation_actually_ran() -> None:
    """A measured zero is a legitimate, distinguishable result."""
    metrics = CycleMetrics(cycle_number=1, fixes_validated=0)
    validated_line = next(
        ln for ln in cycle_report(metrics).splitlines() if "Validated:" in ln
    )
    assert UNVALIDATED_LABEL not in validated_line
    assert re.search(r"Validated:\s+0\b", validated_line)


def test_reporter_renders_the_measured_count() -> None:
    metrics = CycleMetrics(cycle_number=1, fixes_validated=3)
    validated_line = next(
        ln for ln in cycle_report(metrics).splitlines() if "Validated:" in ln
    )
    assert re.search(r"Validated:\s+3\b", validated_line)


def test_validated_cell_sentinel_and_number_share_a_width() -> None:
    """Box alignment must survive the sentinel (it is displayed to a human)."""
    assert len(validated_cell(None)) == len(validated_cell(7))
    assert validated_cell(None).strip() == UNVALIDATED_LABEL


def _validated_row(report: str) -> str:
    return next(ln for ln in report.splitlines() if "Validated:" in ln)


def test_sentinel_does_not_change_the_report_row_width() -> None:
    """The box was already ragged; the sentinel must not make it worse.

    (Row widths across the report differ upstream of this change — the
    invariant that belongs to this fix is that swapping a number for the
    sentinel leaves THIS row the same width.)
    """
    sentinel_row = _validated_row(cycle_report(CycleMetrics(cycle_number=1)))
    numeric_row = _validated_row(cycle_report(CycleMetrics(cycle_number=1, fixes_validated=9)))
    assert len(sentinel_row) == len(numeric_row)


# =============================================================================
# 2. The applied-count does not increment on intent or on failed application
# =============================================================================


def test_applied_count_does_not_increment_on_classification_alone(
    forge_dir: Path,
) -> None:
    """The regression pin for the old `fixes_applied += 1  # Optimistic`.

    A failure routed to the automated destination is a fix CANDIDATE. With no
    outcome evidence, zero fixes were applied and nothing was validated.
    """
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results([_automated_failure()])

    assert summary["metrics"]["fixes_generated"] == 1, "candidate should be routed"
    assert summary["metrics"]["fixes_applied"] == 0
    assert summary["metrics"]["fixes_validated"] is None
    assert summary["validation_evidence"] is False


def test_applied_count_does_not_increment_on_a_failed_application(
    forge_dir: Path,
) -> None:
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure()],
        fix_outcomes=[
            FixOutcome(scenario_id="SC-001", applied=False, detail="write failed")
        ],
    )

    assert summary["metrics"]["fixes_applied"] == 0
    assert summary["metrics"]["fixes_failed"] == 1
    # A fix that never applied cannot have been validated.
    assert summary["metrics"]["fixes_validated"] is None


def test_applied_count_increments_only_on_confirmed_application(
    forge_dir: Path,
) -> None:
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure("SC-001"), _automated_failure("SC-002")],
        fix_outcomes=[
            FixOutcome(scenario_id="SC-001", applied=True, detail="skill file written"),
            FixOutcome(scenario_id="SC-002", applied=False, detail="patch rejected"),
        ],
    )

    assert summary["metrics"]["fixes_applied"] == 1
    assert summary["metrics"]["fixes_failed"] == 1
    # Applied but never re-run => still unvalidated.
    assert summary["metrics"]["fixes_validated"] is None


def test_validated_count_comes_from_real_rerun_verdicts(forge_dir: Path) -> None:
    """A re-run that refutes the fix must be able to drive the count DOWN."""
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure("SC-001"), _automated_failure("SC-002")],
        fix_outcomes=[
            FixOutcome(scenario_id="SC-001", applied=True, validated=True),
            FixOutcome(scenario_id="SC-002", applied=True, validated=False),
        ],
    )

    assert summary["metrics"]["fixes_applied"] == 2
    assert summary["metrics"]["fixes_validated"] == 1
    assert summary["validation_evidence"] is True


def test_all_reruns_failing_yields_a_measured_zero_not_the_sentinel(
    forge_dir: Path,
) -> None:
    """The signal CAN represent total failure — that is the L1 bar."""
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure("SC-001")],
        fix_outcomes=[
            FixOutcome(scenario_id="SC-001", applied=True, validated=False)
        ],
    )

    assert summary["metrics"]["fixes_validated"] == 0
    assert summary["validation_evidence"] is True


# =============================================================================
# 3. Aggregation handles the sentinel
# =============================================================================


def test_aggregation_returns_sentinel_when_no_cycle_was_validated(
    tmp_path: Path,
) -> None:
    tracker = MetricsTracker(tmp_path / "metrics")
    tracker.record_cycle(CycleMetrics(cycle_number=1))
    tracker.record_cycle(CycleMetrics(cycle_number=2))

    assert tracker.total_fixes_validated is None
    assert tracker.get_convergence_report()["total_fixes_validated"] is None


def test_aggregation_sums_only_measured_cycles(tmp_path: Path) -> None:
    tracker = MetricsTracker(tmp_path / "metrics")
    tracker.record_cycle(CycleMetrics(cycle_number=1))  # unvalidated
    tracker.record_cycle(CycleMetrics(cycle_number=2, fixes_validated=2))
    tracker.record_cycle(CycleMetrics(cycle_number=3, fixes_validated=0))

    assert tracker.total_fixes_validated == 2


def test_aggregation_survives_a_persisted_null(tmp_path: Path) -> None:
    """`None` round-trips through cycles.json as JSON null and stays honest."""
    metrics_dir = tmp_path / "metrics"
    tracker = MetricsTracker(metrics_dir)
    tracker.record_cycle(CycleMetrics(cycle_number=1))

    on_disk = json.loads((metrics_dir / "cycles.json").read_text(encoding="utf-8"))
    assert on_disk["cycles"][0]["fixes_validated"] is None

    reloaded = MetricsTracker(metrics_dir)
    assert reloaded.total_fixes_validated is None


def test_convergence_dashboard_renders_the_sentinel(tmp_path: Path) -> None:
    tracker = MetricsTracker(tmp_path / "metrics")
    tracker.record_cycle(CycleMetrics(cycle_number=1))

    dashboard = convergence_dashboard(tracker.get_convergence_report())
    validated_line = next(
        ln for ln in dashboard.splitlines() if "Total Fixes Validated" in ln
    )
    assert UNVALIDATED_LABEL in validated_line
    cell = validated_line.split("Validated:")[1]
    assert not re.search(r"\d", cell), f"numeric total rendered: {cell!r}"

    # Swapping the sentinel for a real number must not change the row width.
    report = tracker.get_convergence_report()
    numeric_line = next(
        ln
        for ln in convergence_dashboard({**report, "total_fixes_validated": 12}).splitlines()
        if "Total Fixes Validated" in ln
    )
    assert len(validated_line) == len(numeric_line)


# =============================================================================
# 4. Source-level pin: the optimism must not come back
# =============================================================================


def test_orchestrator_source_carries_no_optimistic_increment() -> None:
    src = (REPO_ROOT / "forge" / "engine" / "orchestrator.py").read_text(
        encoding="utf-8"
    )
    assert "fixes_applied += 1" not in src, "optimistic applied-increment returned"
    assert "fixes_validated=0" not in src, "hardcoded validated-count returned"
