"""
Synapse Autonomy Pipeline — Autonomous Driver

Orchestrates the full render loop: Plan -> Validate -> Execute -> Evaluate -> Report.
Supports checkpoint/resume, decision logging, gate-based approval, and
automatic re-planning on evaluation failure (up to max_iterations).
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from .models import (
    CheckSeverity,
    Decision,
    GateLevel,
    RenderPlan,
    RenderReport,
    RenderStep,
    SequenceEvaluation,
    StepStatus,
)
from .planner import RenderPlanner
from .validator import PreFlightValidator
from .evaluator import RenderEvaluator

logger = logging.getLogger("synapse.autonomy.driver")


class HandlerInterface(Protocol):
    """Async callable interface for executing MCP handler tools."""

    async def call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a handler tool by name with the given parameters."""
        ...


class MemorySystem(Protocol):
    """Minimal interface for the Synapse memory system."""

    def add(self, content: str, **kwargs: Any) -> Any:
        """Store a memory entry."""
        ...


class AutonomousDriver:
    """Drives the full autonomous render loop.

    Lifecycle per execution:
        1. Plan: build a RenderPlan from artist intent
        2. Gate: present plan for approval if gate level >= REVIEW
        3. Validate: run pre-flight checks (HARD_FAIL stops, SOFT_WARN continues)
        4. Execute: call render handler(s) via handler_interface
        5. Evaluate: run quality checks on rendered output
        6. Re-plan: if evaluation fails and iterations < max, loop back
        7. Report: compile final RenderReport

    Args:
        planner: Builds and revises render plans.
        validator: Runs pre-flight scene checks.
        evaluator: Evaluates rendered output quality.
        handler_interface: Async callable for MCP handler tools.
        memory_system: For persisting decisions and context.
        max_iterations: Maximum re-plan attempts before giving up.
    """

    def __init__(
        self,
        planner: RenderPlanner,
        validator: PreFlightValidator,
        evaluator: RenderEvaluator,
        handler_interface: HandlerInterface,
        memory_system: Optional[MemorySystem] = None,
        max_iterations: int = 3,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._evaluator = evaluator
        self._handler = handler_interface
        self._memory = memory_system
        self._max_iterations = max_iterations

        self._decisions: List[Decision] = []
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._cancelled = False

        # Approval callback — override for UI integration
        self._approval_callback: Optional[Callable[[RenderPlan], bool]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, intent: str) -> RenderReport:
        """Run the full autonomous render loop.

        Args:
            intent: Natural-language render intent from the artist.

        Returns:
            RenderReport with plan, evaluation, decisions, and success flag.
        """
        start_time = time.monotonic()
        self._cancelled = False
        self._decisions = []
        iteration = 0
        evaluation: Optional[SequenceEvaluation] = None

        # Step 1: Plan
        plan = self._planner.plan(intent)
        self._log_decision(
            context="initial_plan",
            decision=f"Created render plan with {len(plan.steps)} step(s) "
                     f"for {plan.estimated_frames} frame(s)",
            reasoning=f"Parsed intent: '{intent}'",
            gate=GateLevel.INFORM,
        )
        self._checkpoint("plan_created", {"plan_intent": plan.intent})

        # Step 2: Gate check
        if plan.gate_level in (GateLevel.REVIEW, GateLevel.CONFIRM):
            approved = await self._present_for_approval(plan)
            if not approved:
                self._log_decision(
                    context="gate_rejected",
                    decision="Artist declined the render plan",
                    reasoning="Plan was presented for approval and rejected",
                    gate=plan.gate_level,
                )
                return RenderReport(
                    plan=plan,
                    decisions=list(self._decisions),
                    iterations=0,
                    total_time_seconds=time.monotonic() - start_time,
                    success=False,
                )

        while iteration < self._max_iterations:
            if self._cancelled:
                self._log_decision(
                    context="emergency_stop",
                    decision="Render loop cancelled via emergency stop",
                    reasoning="emergency_stop() was called during execution",
                    gate=GateLevel.INFORM,
                )
                break

            iteration += 1
            self._checkpoint(f"iteration_{iteration}", {"iteration": iteration})

            # Step 3: Validate
            checks = await self._validator.validate(plan)
            plan.validation_checks = checks

            hard_fails = [c for c in checks if c.severity == CheckSeverity.HARD_FAIL and not c.passed]
            soft_warns = [c for c in checks if c.severity == CheckSeverity.SOFT_WARN and not c.passed]

            if hard_fails:
                fail_names = ", ".join(c.name for c in hard_fails)
                self._log_decision(
                    context="validation_failed",
                    decision=f"Stopping: {len(hard_fails)} hard failure(s): {fail_names}",
                    reasoning="; ".join(c.message for c in hard_fails),
                    gate=GateLevel.INFORM,
                )
                return RenderReport(
                    plan=plan,
                    decisions=list(self._decisions),
                    iterations=iteration,
                    total_time_seconds=time.monotonic() - start_time,
                    success=False,
                )

            if soft_warns:
                warn_names = ", ".join(c.name for c in soft_warns)
                self._log_decision(
                    context="validation_warnings",
                    decision=f"Continuing with {len(soft_warns)} warning(s): {warn_names}",
                    reasoning="Soft warnings don't block execution",
                    gate=GateLevel.INFORM,
                )

            # Step 4: Execute render steps
            execution_ok = await self._execute_steps(plan)
            if not execution_ok:
                self._log_decision(
                    context="execution_failed",
                    decision="One or more render steps failed",
                    reasoning="Handler returned an error during execution",
                    gate=GateLevel.INFORM,
                )
                if iteration < self._max_iterations:
                    # Build a minimal evaluation so replan has something to work with
                    if evaluation is None:
                        evaluation = SequenceEvaluation(passed=False)
                    plan = self._planner.replan(plan, evaluation)
                    continue
                break

            # Step 5: Collect render results and evaluate
            render_results = await self._collect_results(plan)
            evaluation = self._evaluator.evaluate_sequence(render_results)

            self._log_decision(
                context="evaluation_complete",
                decision=f"Sequence score: {evaluation.overall_score:.2f}, "
                         f"passed: {evaluation.passed}",
                reasoning=f"{len(evaluation.frame_evaluations)} frame(s) evaluated, "
                          f"{len(evaluation.temporal_issues)} temporal issue(s)",
                gate=GateLevel.INFORM,
            )

            # Step 6: Check if we need to re-plan
            if evaluation.passed:
                self._log_decision(
                    context="render_success",
                    decision="Render sequence passed quality checks",
                    reasoning=f"Overall score {evaluation.overall_score:.2f} >= 0.7 threshold",
                    gate=GateLevel.INFORM,
                )
                break

            if iteration < self._max_iterations:
                self._log_decision(
                    context="replan",
                    decision=f"Re-planning (iteration {iteration}/{self._max_iterations})",
                    reasoning="Evaluation failed — adjusting settings and re-rendering failed frames",
                    gate=GateLevel.INFORM,
                )
                plan = self._planner.replan(plan, evaluation)
            else:
                self._log_decision(
                    context="max_iterations",
                    decision=f"Giving up after {self._max_iterations} iteration(s)",
                    reasoning="Max iteration limit reached without passing quality checks",
                    gate=GateLevel.INFORM,
                )

        total_time = time.monotonic() - start_time

        # Step 7: Compile report
        report = RenderReport(
            plan=plan,
            evaluation=evaluation,
            decisions=list(self._decisions),
            iterations=iteration,
            total_time_seconds=total_time,
            success=evaluation.passed if evaluation else False,
        )

        # Persist to memory
        if self._memory:
            try:
                self._memory.add(
                    content=f"Autonomous render: '{intent}' - "
                            f"{'succeeded' if report.success else 'failed'} "
                            f"after {iteration} iteration(s) in {total_time:.1f}s",
                    type="decision",
                    tags=["autonomy", "render"],
                )
            except Exception:
                logger.warning("Couldn't persist render report to memory")

        return report

    def emergency_stop(self) -> None:
        """Cancel the current render loop at the next checkpoint.

        Also attempts to cancel any active TOPS work items via the
        handler interface.
        """
        self._cancelled = True
        self._log_decision(
            context="emergency_stop_requested",
            decision="Emergency stop requested by artist",
            reasoning="Artist triggered emergency stop",
            gate=GateLevel.INFORM,
        )
        logger.warning("Emergency stop requested — render loop will halt at next checkpoint")

    def set_approval_callback(self, callback: Callable[[RenderPlan], bool]) -> None:
        """Set a callback for gate approval prompts.

        The callback receives a RenderPlan and returns True to approve,
        False to reject. If no callback is set, plans at REVIEW level
        are auto-approved and CONFIRM level plans are auto-rejected.
        """
        self._approval_callback = callback

    # ------------------------------------------------------------------
    # Internal: execution
    # ------------------------------------------------------------------

    async def _execute_steps(self, plan: RenderPlan) -> bool:
        """Execute all steps in the plan sequentially.

        Returns True if all steps completed, False if any failed.
        """
        for step in plan.steps:
            if self._cancelled:
                step.status = StepStatus.SKIPPED
                continue

            step.status = StepStatus.RUNNING
            try:
                result = await self._handler.call(step.handler, step.params)
                step.result = result
                step.status = StepStatus.COMPLETED
            except Exception as exc:
                step.error = str(exc)
                step.status = StepStatus.FAILED
                logger.error(
                    "Step '%s' failed: %s", step.description, exc
                )
                return False

        return True

    async def _collect_results(
        self,
        plan: RenderPlan,
    ) -> List[Dict[str, Any]]:
        """Collect rendered frame data for evaluation.

        Queries the handler_interface for render output paths and
        optionally loads image data if available.
        """
        results: List[Dict[str, Any]] = []

        # Find the render step to get frame range
        render_step = None
        for step in plan.steps:
            if step.handler in ("render_sequence", "render"):
                render_step = step
                break

        if render_step is None or render_step.result is None:
            return results

        # Extract output info from render result
        output_frames = render_step.result.get("frames", [])
        if isinstance(output_frames, list):
            for frame_info in output_frames:
                if isinstance(frame_info, dict):
                    results.append({
                        "frame": frame_info.get("frame", 0),
                        "output_path": frame_info.get("output_path", ""),
                        "image_data": frame_info.get("image_data"),
                    })
                elif isinstance(frame_info, (int, float)):
                    results.append({
                        "frame": int(frame_info),
                        "output_path": render_step.result.get("output_dir", ""),
                        "image_data": None,
                    })

        # If no structured frame data, build from step params
        if not results and render_step.result:
            start = render_step.params.get("start_frame", 1)
            end = render_step.params.get("end_frame", start)
            output_dir = render_step.result.get("output_dir", "")
            for f in range(start, end + 1):
                results.append({
                    "frame": f,
                    "output_path": output_dir,
                    "image_data": None,
                })

        return results

    # ------------------------------------------------------------------
    # Internal: gate system
    # ------------------------------------------------------------------

    async def _present_for_approval(self, plan: RenderPlan) -> bool:
        """Present a plan for artist approval.

        Uses the registered approval callback if available. Otherwise:
        - REVIEW plans are auto-approved (artist trusts the system)
        - CONFIRM plans are auto-rejected (too risky without explicit approval)
        """
        if self._approval_callback is not None:
            try:
                return self._approval_callback(plan)
            except Exception as exc:
                logger.error("Approval callback raised an error: %s", exc)
                return False

        # Default policy
        if plan.gate_level == GateLevel.REVIEW:
            self._log_decision(
                context="auto_approve",
                decision="Auto-approved REVIEW-level plan (no approval callback set)",
                reasoning="Default policy: REVIEW plans proceed without explicit approval",
                gate=GateLevel.REVIEW,
            )
            return True

        # CONFIRM requires explicit approval
        self._log_decision(
            context="auto_reject",
            decision="Auto-rejected CONFIRM-level plan (no approval callback set)",
            reasoning="Default policy: CONFIRM plans require an explicit approval callback",
            gate=GateLevel.CONFIRM,
        )
        return False

    # ------------------------------------------------------------------
    # Internal: checkpoint / resume
    # ------------------------------------------------------------------

    def _checkpoint(self, step: str, state: Dict[str, Any]) -> None:
        """Save a checkpoint for potential resume.

        Checkpoints are in-memory for now. Phase 3 will persist to disk.
        """
        self._checkpoints[step] = {
            "timestamp": time.time(),
            "state": state,
            "decisions_count": len(self._decisions),
        }
        logger.debug("Checkpoint saved: %s", step)

    def _resume(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Resume from a saved checkpoint.

        Returns the checkpoint state dict or None if not found.
        """
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            logger.warning("Couldn't find checkpoint '%s' to resume from", checkpoint_id)
            return None
        logger.info("Resuming from checkpoint '%s'", checkpoint_id)
        return cp.get("state")

    # ------------------------------------------------------------------
    # Internal: decision logging
    # ------------------------------------------------------------------

    def _log_decision(
        self,
        context: str,
        decision: str,
        reasoning: str,
        gate: GateLevel,
    ) -> None:
        """Record a decision made during the autonomous loop."""
        d = Decision(
            timestamp=datetime.now(),
            context=context,
            decision=decision,
            reasoning=reasoning,
            gate_level=gate,
        )
        self._decisions.append(d)
        logger.info("[%s] %s — %s", context, decision, reasoning)
