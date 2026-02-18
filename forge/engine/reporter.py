"""
FORGE Reporter — Status display and progress reporting.

Generates render-farm-style progress displays, cycle reports,
and convergence dashboards. Designed to feel like watching
a Deadline render farm monitor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import CycleMetrics, BacklogItem, CorpusStage


# =============================================================================
# Progress Bar Rendering
# =============================================================================


def progress_bar(current: int, total: int, width: int = 40, label: str = "") -> str:
    """Render a text progress bar."""
    if total == 0:
        pct = 0.0
    else:
        pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    pct_str = f"{pct * 100:.1f}%"
    if label:
        return f"  {bar}  {pct_str}  {label}"
    return f"  {bar}  {pct_str}"


def delta_indicator(value: float | None) -> str:
    """Format a delta value with arrow indicator."""
    if value is None:
        return "—"
    if value > 0.01:
        return f"▲ +{value * 100:.1f}%"
    if value < -0.01:
        return f"▼ {value * 100:.1f}%"
    return f"● {value * 100:.1f}%"


# =============================================================================
# Report Generators
# =============================================================================


def cycle_report(metrics: CycleMetrics) -> str:
    """Generate the post-cycle report display."""
    pass_pct = f"{metrics.pass_rate * 100:.0f}%"
    delta = delta_indicator(metrics.improvement_delta)

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        f"║  FORGE CYCLE {metrics.cycle_number:>3}  COMPLETE                                ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Scenarios: {metrics.scenarios_run:>3} run  │  Pass Rate: {pass_pct:>4} ({delta:>10})   ║",
        f"║  Passed:    {metrics.scenarios_passed:>3}     │  Failed:    {metrics.scenarios_failed:>3}                  ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Fixes Generated:  {metrics.fixes_generated:>3}  │  Validated: {metrics.fixes_validated:>3}              ║",
        f"║  Fixes Applied:    {metrics.fixes_applied:>3}  │  Failed:    {metrics.fixes_failed:>3}              ║",
        f"║  Queued (Human):   {metrics.fixes_queued_human:>3}  │                              ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Corpus: +{metrics.corpus_entries_added:>3} entries  │  Promotions: {metrics.corpus_promotions:>3}           ║",
        f"║  Total:   {metrics.total_corpus_entries:>4}       │  Friction:  {metrics.avg_friction_ratio:>5.2f}         ║",
        "╠══════════════════════════════════════════════════════════════╣",
    ]

    # Top failures
    if metrics.failure_categories:
        lines.append("║  Top Failures:                                               ║")
        sorted_cats = sorted(
            metrics.failure_categories.items(), key=lambda x: x[1], reverse=True
        )
        for cat, count in sorted_cats[:3]:
            lines.append(f"║    {cat:<35} ×{count:>3}           ║")
    else:
        lines.append("║  No failures this cycle! 🎉                                  ║")

    # Tool gaps
    if metrics.new_tool_gaps:
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║  New Tool Gaps:                                              ║")
        for gap in metrics.new_tool_gaps[:3]:
            lines.append(f"║    → {gap:<53} ║")

    # Convergence signal
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    if metrics.improvement_delta is not None and abs(metrics.improvement_delta) < 0.005:
        flatline_warn = "  ⚠ FLATLINE: Consider Layer 3 review"
    else:
        flatline_warn = ""
    lines.append(f"║  improvement_delta: {delta:>10}{flatline_warn:<28} ║")

    # Stop condition warnings
    if metrics.should_stop:
        lines.append("║                                                              ║")
        lines.append("║  ⛔ STOP CONDITION MET — Review regressions before continuing ║")

    lines.append("╚══════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def autonomous_progress(
    current_cycle: int,
    total_cycles: int,
    pass_rate: float,
    delta: float | None,
    last_action: str = "",
) -> str:
    """Compact progress display for autonomous mode."""
    bar = progress_bar(current_cycle, total_cycles, width=30)
    delta_str = delta_indicator(delta)
    lines = [
        "",
        f"  FORGE AUTONOMOUS RUN",
        f"{bar}  Cycle {current_cycle}/{total_cycles}",
        f"  Pass: {pass_rate * 100:.0f}%  │  Δ: {delta_str}",
    ]
    if last_action:
        lines.append(f"  Last: {last_action}")
    return "\n".join(lines)


def agent_status(
    agent: str,
    scenario: str,
    status: str,
    elapsed_s: float = 0,
) -> str:
    """Single agent status line (like a render farm task)."""
    status_icons = {
        "queued": "⏳",
        "running": "🔄",
        "passed": "✅",
        "failed": "❌",
        "timeout": "⏰",
    }
    icon = status_icons.get(status, "?")
    elapsed = f"{elapsed_s:.1f}s" if elapsed_s > 0 else ""
    return f"  {icon} {agent:<12} {scenario:<30} {status:<8} {elapsed}"


def backlog_summary(items: list[BacklogItem]) -> str:
    """Summary of items awaiting human review."""
    if not items:
        return "  No items in backlog."

    open_items = [i for i in items if i.status == "open"]
    lines = [
        f"  Backlog: {len(open_items)} items awaiting review",
        "",
    ]

    by_priority = {"critical": [], "high": [], "medium": [], "low": []}
    for item in open_items:
        by_priority.get(item.priority, by_priority["medium"]).append(item)

    priority_icons = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }

    for priority in ["critical", "high", "medium", "low"]:
        items_at_priority = by_priority[priority]
        if items_at_priority:
            icon = priority_icons[priority]
            lines.append(f"  {icon} {priority.upper()} ({len(items_at_priority)}):")
            for item in items_at_priority[:3]:
                lines.append(f"     {item.id}: {item.title}")
            if len(items_at_priority) > 3:
                lines.append(f"     ... and {len(items_at_priority) - 3} more")

    return "\n".join(lines)


def convergence_dashboard(report: dict[str, Any]) -> str:
    """Full convergence dashboard for Layer 3 review."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║              FORGE CONVERGENCE DASHBOARD                     ║",
        "╠══════════════════════════════════════════════════════════════╣",
    ]

    lines.append(f"║  Total Cycles:     {report.get('total_cycles', 0):>4}                                  ║")
    lines.append(f"║  Current Pass Rate: {report.get('current_pass_rate', 0) * 100:>5.1f}%                               ║")
    lines.append(f"║  Current Tier:     {report.get('current_tier', 1):>4}                                  ║")
    lines.append(f"║  Flatlined:        {'YES ⚠' if report.get('is_flatlined') else 'No':>6}                                ║")

    lines.append("╠══════════════════════════════════════════════════════════════╣")
    lines.append(f"║  Total Fixes Applied:    {report.get('total_fixes_applied', 0):>4}                           ║")
    lines.append(f"║  Total Fixes Validated:  {report.get('total_fixes_validated', 0):>4}                           ║")

    # Persistent failures
    persistent = report.get("persistent_failures", [])
    if persistent:
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║  PERSISTENT FAILURES (v25.0 refactor targets):              ║")
        for pf in persistent:
            lines.append(
                f"║    {pf['category']:<30} ({pf['cycles_present']} cycles)      ║"
            )

    # Tool gaps
    gaps = report.get("tool_gap_accumulation", [])
    if gaps:
        lines.append("╠══════════════════════════════════════════════════════════════╣")
        lines.append("║  TOOL GAPS (feature backlog):                                ║")
        for g in gaps[:5]:
            lines.append(
                f"║    {g['tool']:<35} (×{g['requested_in_cycles']})          ║"
            )

    # Recommendation
    lines.append("╠══════════════════════════════════════════════════════════════╣")
    rec = report.get("recommendation", "")
    # Word-wrap recommendation to fit box
    import textwrap

    wrapped = textwrap.wrap(rec, width=56)
    for line in wrapped:
        lines.append(f"║  {line:<58} ║")

    lines.append("╚══════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def run_summary(
    cycles_completed: int,
    final_pass_rate: float,
    starting_pass_rate: float,
    total_fixes: int,
    total_corpus: int,
    backlog_count: int,
    stop_reason: str,
) -> str:
    """Generate end-of-run summary for autonomous mode."""
    improvement = final_pass_rate - starting_pass_rate
    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════╗",
        "║              FORGE RUN COMPLETE                              ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Cycles Completed:  {cycles_completed:>4}                                  ║",
        f"║  Pass Rate:  {starting_pass_rate * 100:.0f}% → {final_pass_rate * 100:.0f}%  ({delta_indicator(improvement):>10})           ║",
        f"║  Total Fixes:       {total_fixes:>4}                                  ║",
        f"║  Corpus Entries:    {total_corpus:>4}                                  ║",
        f"║  Backlog Items:     {backlog_count:>4}                                  ║",
        "╠══════════════════════════════════════════════════════════════╣",
        f"║  Stop Reason: {stop_reason:<44} ║",
        "╚══════════════════════════════════════════════════════════════╝",
    ]
    return "\n".join(lines)
