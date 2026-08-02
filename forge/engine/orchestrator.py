"""
FORGE Orchestrator — Main cycle runner for the self-improvement loop.

This module is the entry point for Claude Code. It coordinates:
1. Loading state (corpus, metrics, scenarios)
2. Routing scenarios to agents via MoE
3. Collecting and classifying results
4. Generating and applying fixes
5. Verifying improvements
6. Updating corpus and metrics
7. Reporting progress

Usage in Claude Code:
  The orchestrator is NOT run as a standalone Python script.
  Claude Code reads FORGE.md and uses this module's logic as a reference
  for how to orchestrate Task sub-agents. The actual execution happens
  through Claude Code's Task tool, with each agent being a sub-agent.

  Think of this as the RECIPE that Claude Code follows, not the chef.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .schemas import (
    AgentRole,
    BacklogItem,
    CorpusEntry,
    CycleMetrics,
    FailureCategory,
    FixOutcome,
    ScenarioComplexity,
    ScenarioDefinition,
    ScenarioDomain,
    ScenarioFocus,
    ScenarioResult,
    load_json,
    save_json,
)
from .classifier import classify_failure, classify_batch, should_escalate_to_human, generate_backlog_item
from .corpus_manager import CorpusManager
from .metrics import MetricsTracker
from .reporter import (
    cycle_report,
    autonomous_progress,
    agent_status,
    backlog_summary,
    convergence_dashboard,
    run_summary,
)
from .router import route_scenario, route_batch


class ForgeOrchestrator:
    """Main orchestrator for FORGE improvement cycles.
    
    This class manages the full cycle lifecycle. Claude Code instantiates
    it and calls methods in sequence to drive the improvement loop.
    """

    def __init__(self, forge_dir: Path):
        self.forge_dir = forge_dir
        self.corpus = CorpusManager(forge_dir / "corpus")
        self.metrics = MetricsTracker(forge_dir / "metrics")
        self.scenarios = self._load_scenarios()
        self.backlog = self._load_backlog()
        self.current_cycle: int = self.metrics.cycle_count + 1

    # =========================================================================
    # Cycle Lifecycle
    # =========================================================================

    def plan_cycle(
        self,
        tier: int = 1,
        domains: list[str] | None = None,
        agents: list[str] | None = None,
        focus: str | None = None,
    ) -> dict[str, Any]:
        """Plan a cycle: select scenarios and route to agents.
        
        Returns a plan dict that Claude Code uses to spawn Task sub-agents.
        """
        # Filter scenarios by tier
        eligible = [s for s in self.scenarios if s.tier <= tier]

        # Filter by domain if specified
        if domains:
            domain_enums = [ScenarioDomain(d) for d in domains]
            eligible = [s for s in eligible if s.domain in domain_enums]

        # Filter by focus if specified
        if focus:
            focus_enum = ScenarioFocus(focus)
            eligible = [s for s in eligible if s.focus == focus_enum]

        # Parse agent filter
        agent_filter = None
        if agents and agents != ["all"]:
            agent_filter = [AgentRole(a.upper()) for a in agents]

        # Route scenarios to agents
        corpus_entries = self.corpus.get_all_entries()
        work = route_batch(eligible, corpus_entries, agent_filter)

        plan = {
            "cycle": self.current_cycle,
            "tier": tier,
            "scenarios_count": len(eligible),
            "agents": {
                agent.value: [
                    {
                        "scenario_id": a.scenario.id,
                        "scenario_title": a.scenario.title,
                        "role": a.role_in_scenario,
                        "corpus_context_count": len(a.corpus_context),
                    }
                    for a in assignments
                ]
                for agent, assignments in work.items()
            },
            "total_assignments": sum(len(v) for v in work.values()),
        }

        return plan

    def process_results(
        self,
        results: list[ScenarioResult],
        tier: int = 1,
        fix_outcomes: list[FixOutcome] | None = None,
    ) -> dict[str, Any]:
        """Process collected results through the improvement engine.

        1. Classify failures
        2. Route fixes (automated destination, or queue for human review)
        3. Update corpus
        4. Compute metrics
        5. Generate report

        ``fix_outcomes`` carries **evidence** that fixes were actually applied
        and/or re-run. There is no apply/verify stage in ``forge/engine`` —
        ``FORGE.md`` Phase 5 is a procedure a human or Claude Code follows — so
        the engine cannot observe application or validation, only be told with
        evidence. With no evidence: ``fixes_applied`` is 0 (nothing confirmed
        applied) and ``fixes_validated`` is ``None`` (*unvalidated*), never a
        fabricated 0.

        Returns a summary dict with the cycle report.
        """
        outcomes = list(fix_outcomes or [])
        # --- CLASSIFY ---
        failed_results = [r for r in results if not r.success]
        friction_results = [
            r for r in results if r.success and (r.friction_notes or r.missing_tools)
        ]

        classified = classify_batch(failed_results + friction_results)

        # --- ROUTE FIXES & UPDATE CORPUS ---
        # NOTE: fixes_applied / fixes_validated are NOT computed here. Nothing
        # in this loop writes a fix, so nothing in this loop may claim one was
        # applied. Both are derived from FixOutcome evidence after the loop.
        fixes_generated = 0
        fixes_queued = 0
        new_corpus_entries = 0
        new_backlog_items = []

        for category, cat_results in classified.items():
            for result in cat_results:
                # Create corpus observation
                entry = self.corpus.add_observation(
                    result=result,
                    category=category,
                    pattern=result.corpus_contribution or f"{category.value}: {result.failure_point}",
                    context=f"Cycle {self.current_cycle}, agent {result.agent.value}",
                )
                new_corpus_entries += 1

                if category.fix_destination == "automated":
                    # Counts a failure ROUTED to the automated-fix destination.
                    # Claude Code writes the actual fix (skill file, CLAUDE.md
                    # rule, test case) outside this module and reports the
                    # result back via fix_outcomes. Routing is not applying:
                    # nothing is incremented here on intent.
                    fixes_generated += 1

                elif category.fix_destination == "human_review":
                    fixes_generated += 1
                    fixes_queued += 1
                    item = generate_backlog_item(result, category, self.current_cycle)
                    new_backlog_items.append(item)

                elif should_escalate_to_human(category, entry.recurrence_count):
                    fixes_queued += 1
                    item = generate_backlog_item(result, category, self.current_cycle)
                    new_backlog_items.append(item)

        # Add successes to corpus as capability confirmations
        for result in results:
            if result.success and result.corpus_contribution:
                self.corpus.add_observation(
                    result=result,
                    pattern=result.corpus_contribution,
                    context=f"Capability confirmed in cycle {self.current_cycle}",
                )
                new_corpus_entries += 1

        # --- EVOLVE CORPUS ---
        promotions = self.corpus.evolve_all()

        # --- SAVE BACKLOG ---
        for item in new_backlog_items:
            self.backlog.append(item)
        self._save_backlog()

        # --- FIX OUTCOMES (evidence-derived, never optimistic) ---
        fixes_applied = sum(1 for o in outcomes if o.applied)
        fixes_failed = sum(1 for o in outcomes if not o.applied)
        # Only outcomes that both applied AND carry a real re-run verdict count
        # as validation evidence. No such evidence => None (unvalidated), which
        # is a different fact from a measured zero.
        revalidated = [o for o in outcomes if o.applied and o.validated is not None]
        fixes_validated = (
            sum(1 for o in revalidated if o.validated) if revalidated else None
        )
        # The denominator. A cycle where 1 of 8 applied fixes was re-run is not
        # a measured cycle — it is a partial measurement, and the report must
        # be able to say so rather than let one verdict speak for all eight.
        fixes_revalidated = len(revalidated)

        # --- COMPUTE METRICS ---
        cycle_metrics = self.metrics.compute_cycle_metrics(
            cycle_number=self.current_cycle,
            results=results,
            fixes_generated=fixes_generated,
            fixes_applied=fixes_applied,
            fixes_validated=fixes_validated,
            fixes_revalidated=fixes_revalidated,
            fixes_failed=fixes_failed,
            fixes_queued_human=fixes_queued,
            corpus_entries_added=new_corpus_entries,
            corpus_promotions=len(promotions),
            total_corpus_entries=self.corpus.stats["total"],
            tier=tier,
        )
        self.metrics.record_cycle(cycle_metrics)

        # --- GENERATE REPORT ---
        report = cycle_report(cycle_metrics)

        self.current_cycle += 1

        return {
            "cycle_number": cycle_metrics.cycle_number,
            "report": report,
            "metrics": cycle_metrics.to_dict(),
            "fixes_validated": fixes_validated,
            "fixes_revalidated": fixes_revalidated,
            "validation_evidence": bool(revalidated),
            "validation_is_partial": cycle_metrics.validation_is_partial,
            "new_backlog_items": len(new_backlog_items),
            "corpus_promotions": len(promotions),
            "should_stop": cycle_metrics.should_stop,
            "should_tier_up": cycle_metrics.should_tier_up,
            "flatlined": self.metrics.is_flatlined,
        }

    def get_status(self) -> str:
        """Get current FORGE status."""
        latest = self.metrics.latest
        corpus_stats = self.corpus.stats
        open_backlog = [i for i in self.backlog if i.status == "open"]

        lines = [
            "",
            "  FORGE STATUS",
            f"  Cycles completed: {self.metrics.cycle_count}",
            f"  Last pass rate: {latest.get('pass_rate', 0) * 100:.0f}%" if latest else "  No cycles run yet",
            f"  Corpus: {corpus_stats['total']} entries",
            f"  Backlog: {len(open_backlog)} items awaiting review",
        ]

        if self.metrics.is_flatlined:
            lines.append("  ⚠ FLATLINE DETECTED — Layer 3 review recommended")

        return "\n".join(lines)

    def get_convergence(self) -> str:
        """Get convergence dashboard for Layer 3 review."""
        report = self.metrics.get_convergence_report()
        return convergence_dashboard(report)

    def get_backlog(self) -> str:
        """Get human review backlog summary."""
        return backlog_summary(self.backlog)

    # =========================================================================
    # Agent Prompt Generation
    # =========================================================================

    def build_agent_prompt(
        self,
        agent: AgentRole,
        scenario: ScenarioDefinition,
        corpus_context: list[CorpusEntry],
    ) -> str:
        """Build the full prompt for a Task sub-agent.
        
        This is what gets passed to Claude Code's Task tool.
        Combines the agent persona, scenario description, corpus context,
        and available MCP tools.
        """
        # Load persona file
        persona_path = self.forge_dir / "agents" / f"{agent.value.lower()}.md"
        if agent == AgentRole.ARCHITECT:
            persona_path = self.forge_dir / "agents" / "pipeline_architect.md"
        persona = persona_path.read_text(encoding="utf-8") if persona_path.exists() else ""

        # Build corpus context string
        corpus_str = ""
        if corpus_context:
            corpus_str = "\n## Relevant Knowledge from Previous Cycles\n\n"
            for entry in corpus_context[:5]:
                corpus_str += f"- [{entry.stage.value}] {entry.pattern}\n"
                corpus_str += f"  Context: {entry.context}\n"
                corpus_str += f"  Confidence: {entry.confidence:.2f}\n\n"

        # Build scenario string
        scenario_str = f"""
## Your Assignment

**Scenario:** {scenario.title} ({scenario.id})
**Description:** {scenario.description}
**Tier:** {scenario.tier}
**Domain:** {scenario.domain.value}
**Focus:** {scenario.focus.value}

### Steps:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(scenario.steps))}

### Expected Outcome:
{scenario.expected_outcome}

### Tools Available:
{', '.join(scenario.tools_needed)}

### Estimated Optimal Tool Calls: {scenario.estimated_tool_calls}
"""

        # Build output format instruction
        output_str = """
## Output Format

After executing the scenario, produce a JSON ScenarioResult with these fields:
- success: true/false
- tool_calls: array of {tool, params, result, elapsed_ms, error_message, notes}
- failure_point: which step failed (null if success)
- failure_category: your best guess at classification (null if success)
- error_message: raw error text (null if success)
- workaround_found: did you find a way around the failure?
- workaround_description: how (null if no workaround)
- friction_notes: array of strings noting things that worked but were awkward
- missing_tools: array of strings noting tools you wished existed
- total_elapsed_ms: total time
- tool_calls_count: total number of MCP calls made
- estimated_optimal_calls: minimum calls a perfect workflow would need
- corpus_contribution: one-sentence knowledge nugget for future cycles
- agent_report: your role-specific structured report (see your persona)

CRITICAL: Use SYNAPSE MCP tools to execute against live Houdini.
Do NOT simulate or mock tool calls. Call the real tools.
Report partial results if you hit errors partway through.
"""

        return f"{persona}\n{corpus_str}\n{scenario_str}\n{output_str}"

    # =========================================================================
    # Internals
    # =========================================================================

    def _load_scenarios(self) -> list[ScenarioDefinition]:
        """Load scenario registry."""
        registry_path = self.forge_dir / "scenarios" / "registry.json"
        data = load_json(registry_path, {"scenarios": []})
        scenarios = []
        for s in data.get("scenarios", []):
            scenarios.append(
                ScenarioDefinition(
                    id=s["id"],
                    title=s["title"],
                    description=s["description"],
                    tier=s["tier"],
                    domain=ScenarioDomain(s["domain"]),
                    complexity=ScenarioComplexity(s["complexity"]),
                    focus=ScenarioFocus(s["focus"]),
                    tools_needed=s.get("tools_needed", []),
                    steps=s.get("steps", []),
                    expected_outcome=s.get("expected_outcome", ""),
                    estimated_tool_calls=s.get("estimated_tool_calls", 5),
                    tags=s.get("tags", []),
                    generated_by=s.get("generated_by", "human"),
                )
            )
        return scenarios

    def _load_backlog(self) -> list[BacklogItem]:
        """Load human review backlog."""
        backlog_path = self.forge_dir / "backlog" / "human_review.json"
        data = load_json(backlog_path, {"items": []})
        return [BacklogItem(**item) for item in data.get("items", [])]

    def _save_backlog(self) -> None:
        """Persist backlog to disk."""
        backlog_path = self.forge_dir / "backlog" / "human_review.json"
        save_json(
            {"version": "1.0.0", "items": [i.to_dict() for i in self.backlog]},
            backlog_path,
        )
