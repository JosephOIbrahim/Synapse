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

import inspect
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
    partial_validation_note,
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


# =============================================================================
# 5. The tracker entry point itself — the defect site, pinned behaviourally
# =============================================================================
#
# `MetricsTracker.compute_cycle_metrics` is the ONLY way a cycle's metrics are
# built, and its `fixes_validated` default is the whole fabrication in one
# character. A `= 0` there re-fabricates a whole-cycle measurement for every
# caller that omits the argument, and does it BELOW the orchestrator, so the
# orchestrator-level tests above cannot see it. These pin the default itself.


def test_compute_cycle_metrics_omitting_validation_yields_the_sentinel(
    tmp_path: Path,
) -> None:
    """THE mutant killer for `metrics.py` `fixes_validated: int | None = 0`.

    A caller that never mentions validation has not measured validation. The
    computed cycle must carry the sentinel, not a zero — a zero here would be
    the engine asserting, on its own authority, that a re-run happened.
    """
    tracker = MetricsTracker(tmp_path / "metrics")

    metrics = tracker.compute_cycle_metrics(cycle_number=1, results=[])

    assert metrics.fixes_validated is None, (
        "compute_cycle_metrics fabricated a validated-count for a caller that "
        "supplied no validation evidence"
    )
    assert metrics.to_dict()["fixes_validated"] is None


def test_compute_cycle_metrics_unvalidated_cycle_never_renders_a_numeral(
    tmp_path: Path,
) -> None:
    """The defect's blast radius: default -> persisted row -> human display.

    Follows the fabricated value all the way to the two surfaces a person
    actually reads. Any of the three assertions dies if the default is `0`.
    """
    tracker = MetricsTracker(tmp_path / "metrics")
    metrics = tracker.compute_cycle_metrics(cycle_number=1, results=[])
    tracker.record_cycle(metrics)

    # (a) persisted as JSON null, not 0
    on_disk = json.loads(
        (tmp_path / "metrics" / "cycles.json").read_text(encoding="utf-8")
    )
    assert on_disk["cycles"][0]["fixes_validated"] is None

    # (b) the aggregate stays unmeasured
    assert tracker.total_fixes_validated is None

    # (c) the human sees the word, with no digit anywhere in the cell
    cell = _validated_row(cycle_report(metrics)).split("Validated:")[1]
    assert UNVALIDATED_LABEL in cell
    assert not re.search(r"\d", cell), f"numeric validated-count rendered: {cell!r}"


def test_compute_cycle_metrics_signature_default_is_the_sentinel() -> None:
    """Structural pin on the exact parameter default the crucible mutated."""
    param = inspect.signature(
        MetricsTracker.compute_cycle_metrics
    ).parameters["fixes_validated"]
    assert param.default is None, (
        f"fixes_validated default is {param.default!r}; only None (unvalidated) "
        "is honest — an int default asserts a measurement no validator produced"
    )


def test_metrics_source_carries_no_fabricated_validated_default() -> None:
    """Source-level pin, so the reversion is loud even outside a call."""
    src = (REPO_ROOT / "forge" / "engine" / "metrics.py").read_text(encoding="utf-8")
    assert "fixes_validated: int | None = 0" not in src
    assert "fixes_validated: int = 0" not in src
    assert "fixes_validated: int | None = None" in src


def test_a_real_validated_count_still_flows_through_the_tracker(
    tmp_path: Path,
) -> None:
    """The sentinel default must not block a genuine measurement."""
    tracker = MetricsTracker(tmp_path / "metrics")
    metrics = tracker.compute_cycle_metrics(
        cycle_number=1, results=[], fixes_applied=2, fixes_validated=2,
        fixes_revalidated=2,
    )
    assert metrics.fixes_validated == 2
    assert re.search(r"Validated:\s+2\b", _validated_row(cycle_report(metrics)))


# =============================================================================
# 6. Partial validation is labelled partial, not rendered as a measurement
# =============================================================================
#
# `fixes_validated` is one number for the whole cycle. Without a denominator a
# single re-run verdict among many applied fixes reads as though the cycle had
# been measured — one outcome carrying a verdict flipping the whole cycle.


def test_partial_validation_is_flagged_on_the_metrics(forge_dir: Path) -> None:
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure("SC-001"), _automated_failure("SC-002")],
        fix_outcomes=[
            # one re-run verdict …
            FixOutcome(scenario_id="SC-001", applied=True, validated=True),
            # … and one applied fix that was never re-run
            FixOutcome(scenario_id="SC-002", applied=True, validated=None),
        ],
    )

    assert summary["metrics"]["fixes_applied"] == 2
    assert summary["metrics"]["fixes_validated"] == 1
    assert summary["fixes_revalidated"] == 1
    assert summary["validation_is_partial"] is True, (
        "1 verdict across 2 applied fixes reported as a whole-cycle measurement"
    )


def test_full_validation_is_not_flagged_partial(forge_dir: Path) -> None:
    orch = ForgeOrchestrator(forge_dir)
    summary = orch.process_results(
        [_automated_failure("SC-001"), _automated_failure("SC-002")],
        fix_outcomes=[
            FixOutcome(scenario_id="SC-001", applied=True, validated=True),
            FixOutcome(scenario_id="SC-002", applied=True, validated=False),
        ],
    )
    assert summary["metrics"]["fixes_validated"] == 1
    assert summary["fixes_revalidated"] == 2
    assert summary["validation_is_partial"] is False


def test_an_unvalidated_cycle_is_not_called_partial() -> None:
    """The sentinel already says 'nothing measured' — don't double-label it."""
    metrics = CycleMetrics(cycle_number=1, fixes_applied=3)
    assert metrics.fixes_validated is None
    assert metrics.validation_is_partial is False
    assert partial_validation_note(metrics) is None


def test_reporter_surfaces_the_partial_coverage_caveat() -> None:
    metrics = CycleMetrics(
        cycle_number=1, fixes_applied=8, fixes_validated=1, fixes_revalidated=1
    )
    assert metrics.validation_is_partial is True

    report = cycle_report(metrics)
    note = next(ln for ln in report.splitlines() if "PARTIAL" in ln)
    assert "1 of 8" in note
    assert "7 unvalidated" in note
    # It has to fit the box. (Other rows are hand-padded and already ragged —
    # see test_sentinel_does_not_change_the_report_row_width — so the border
    # is the only trustworthy width reference.)
    border = next(ln for ln in report.splitlines() if ln.startswith("╔"))
    assert len(note) == len(border)
    assert note.startswith("║") and note.endswith("║")


def test_reporter_omits_the_caveat_when_coverage_is_complete() -> None:
    metrics = CycleMetrics(
        cycle_number=1, fixes_applied=2, fixes_validated=2, fixes_revalidated=2
    )
    assert "PARTIAL" not in cycle_report(metrics)


# =============================================================================
# 7. The repo's own committed metrics must not claim a validation that never ran
# =============================================================================


def test_committed_cycles_json_claims_no_validation_that_never_happened() -> None:
    """`forge/metrics/cycles.json` is the repo's real FORGE record.

    Its three cycles were hand-authored (they carry `friction_scenarios` /
    `scenario_results`, which `CycleMetrics` has no fields for) with
    `fixes_validated: 0`. Under this contract a rendered 0 means "a re-run ran
    and confirmed nothing" — but FORGE has no validator, and all three cycles
    also record `fixes_applied: 0`, so no fix ever existed to re-run. Those
    zeroes are the same fabrication as the code defect, frozen in data: they
    made `total_fixes_validated` report a measured 0 for the whole project.
    """
    cycles = json.loads(
        (REPO_ROOT / "forge" / "metrics" / "cycles.json").read_text(encoding="utf-8")
    )["cycles"]
    assert cycles, "the repo's FORGE record should not be empty"

    for cycle in cycles:
        if cycle.get("fixes_validated") is not None:
            # A number is only legitimate alongside fixes that were applied.
            assert cycle.get("fixes_applied", 0) > 0, (
                f"cycle {cycle.get('cycle_number')} claims a measured "
                f"fixes_validated={cycle['fixes_validated']} with "
                f"fixes_applied={cycle.get('fixes_applied', 0)} — nothing was "
                "applied, so nothing could have been re-run"
            )

    tracker = MetricsTracker(REPO_ROOT / "forge" / "metrics")
    assert tracker.total_fixes_validated is None, (
        "the repo aggregate reports a measured validated-count; no validator "
        "has ever run in forge/engine"
    )
