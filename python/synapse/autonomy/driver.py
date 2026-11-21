"""
Synapse Autonomy Pipeline — Autonomous Driver

Orchestrates the full render loop: Plan -> Validate -> Execute -> Evaluate -> Report.
Supports checkpoint/resume, decision logging, gate-based approval, and
automatic re-planning on evaluation failure (up to max_iterations).
"""

import asyncio
import copy
import json
import logging
import threading
import time
from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from .models import (
    CheckSeverity,
    Decision,
    GateLevel,
    RenderPlan,
    RenderPrediction,
    RenderReport,
    RenderStep,
    SequenceEvaluation,
    StepStatus,
    VerificationResult,
)
from ..core.timeouts import timeout_for
from .planner import (
    RENDER_HANDLERS,
    RenderPlanner,
    requested_frames,
    retry_targets,
)
from .validator import PreFlightValidator
from .evaluator import RenderEvaluator
from .predictor import RenderPredictor

logger = logging.getLogger("synapse.autonomy.driver")

# M3-E: payload-controlled max_iterations is clamped here (the constructor is
# the chokepoint for every entry: handlers.py, agent capabilities, tests).
# Default is 3 everywhere; 10 = ~3x headroom -- iteration count can't fix what
# 10 replans didn't.
MAX_ITERATIONS_HARD_CAP = 10

# M3-E: process-wide live-driver registry (mirrors websocket.py's D3 idiom).
# Lets the render_farm_cancel kill switch reach the RUNNING driver without
# scanning gc or hard-coding who constructed it. Single-seat: last wins.
_live_driver = None
_live_driver_lock = threading.Lock()


def _register_live_driver(driver, only_if=None):
    """Set (or clear) the live-driver handle. ``only_if`` guards clearing so
    an old instance can't deregister a newer one."""
    global _live_driver
    with _live_driver_lock:
        if only_if is not None and _live_driver is not only_if:
            return
        _live_driver = driver


def get_live_driver():
    """The currently-executing AutonomousDriver instance, or None."""
    with _live_driver_lock:
        return _live_driver


class HandlerInterface(Protocol):
    """Async callable interface for executing MCP handler tools.

    The R-035 synchronous fallback (``AutonomousDriver.execute_sync``) also
    needs a ``call_sync(tool_name, params)`` method. It is looked up at call
    time, so an async-only interface still satisfies the normal ``execute``
    path.
    """

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
        predictor: Optional[RenderPredictor] = None,
        max_iterations: int = 3,
        max_wall_clock_seconds: Optional[float] = None,
    ) -> None:
        self._planner = planner
        self._validator = validator
        self._evaluator = evaluator
        self._handler = handler_interface
        self._memory = memory_system
        self._predictor = predictor
        # M3-E: clamp the payload-controlled iteration count; bound the run's
        # wall clock at the canonical client budget unless explicitly raised.
        self._max_iterations = max(1, min(int(max_iterations), MAX_ITERATIONS_HARD_CAP))
        self._max_wall_clock = (
            float(max_wall_clock_seconds) if max_wall_clock_seconds
            else timeout_for("autonomous_render")
        )

        self._decisions: List[Decision] = []
        self._checkpoints: Dict[str, Dict[str, Any]] = {}
        self._cancelled = False
        # R-035: the run's absolute deadline, set by _execute_inner. The
        # step loop consults it so a run stops at a STEP boundary (never
        # starting work the caller's budget cannot cover), not only at the
        # next iteration boundary.
        self._deadline: Optional[float] = None
        self._wall_clock_stopped = False

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
        # M3-E: self-register so the render_farm_cancel kill switch can reach
        # this run; deregister on every exit (only_if guards a newer run).
        _register_live_driver(self)
        try:
            return await self._execute_inner(intent)
        finally:
            _register_live_driver(None, only_if=self)

    async def _execute_inner(self, intent: str) -> RenderReport:
        start_time = time.monotonic()
        deadline = start_time + self._max_wall_clock
        # R-035: the step loop reads the same deadline. Reset the trip flag so
        # a reused driver cannot report a previous run's stop.
        self._deadline = deadline
        self._wall_clock_stopped = False
        stop_reason = ""
        self._cancelled = False
        self._decisions = []
        iteration = 0
        evaluation: Optional[SequenceEvaluation] = None
        prediction: Optional[RenderPrediction] = None
        verification: Optional[VerificationResult] = None

        # Step 1: Plan
        #
        # ``original_plan`` is the artist's request and is never rebound or
        # written to. The plan is mutated in three places below (validation
        # checks, step status/result, the retry rebind); if execution ran
        # against it directly, by iteration 2 the "original" handed to replan
        # would already be the previous retry.
        original_plan = self._planner.plan(intent)
        plan = self._execution_copy(original_plan)

        # The execution copy the report describes. It is reassigned below,
        # immediately before dispatch, and never rebound by a replan: a
        # replan leaves a fresh, unrun copy in ``plan``, and a cancel or
        # wall-clock stop at the top of the next iteration would otherwise
        # report that unrun copy as the attempt -- saying nothing ran while a
        # render was dispatched and failed.
        last_executed = plan

        # A plan with more than one render step has no single product set.
        # Refuse it before dispatch rather than silently grading the first
        # render and ignoring the rest.
        render_steps = [
            step for step in original_plan.steps
            if step.handler in RENDER_HANDLERS
        ]
        if len(render_steps) > 1:
            self._log_decision(
                context="unsupported_plan_shape",
                decision=f"Refusing a plan with {len(render_steps)} render steps",
                reasoning="The driver grades a single render product set; "
                          "a plan with more than one render step would "
                          "silently grade only the first",
                gate=GateLevel.INFORM,
            )
            return RenderReport(
                plan=original_plan,
                executed=plan,
                decisions=list(self._decisions),
                iterations=0,
                total_time_seconds=time.monotonic() - start_time,
                success=False,
                stop_reason="unsupported_plan_shape",
                execution_mode="async",
            )

        # The frames the artist asked for, captured from the original plan and
        # never recomputed. A replan narrows to the failed frames; grading
        # against that would compare a full render to a subset and call every
        # good frame unplanned.
        planned_frames = self._planned_frames(original_plan)
        # Results accumulate across attempts, keyed by frame. A replan retries
        # only the failed frames; grading the retry on its own would lose the
        # frames that already succeeded and report them as missing from the
        # plan. Each retry replaces its frame's entry, and its failure state.
        accumulated: Dict[int, Dict[str, Any]] = {}
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
                    plan=original_plan,
                    executed=plan,
                    decisions=list(self._decisions),
                    iterations=0,
                    total_time_seconds=time.monotonic() - start_time,
                    success=False,
                    stop_reason="gate_rejected",
                    execution_mode="async",
                )

        while iteration < self._max_iterations:
            if self._cancelled:
                self._log_decision(
                    context="emergency_stop",
                    decision="Render loop cancelled via emergency stop",
                    reasoning="emergency_stop() was called during execution",
                    gate=GateLevel.INFORM,
                )
                stop_reason = "cancelled"
                break

            if time.monotonic() >= deadline:
                self._log_decision(
                    context="wall_clock_exceeded",
                    decision=f"Stopping: wall-clock budget ({self._max_wall_clock:.0f}s) "
                             f"exceeded after {iteration} iteration(s)",
                    reasoning="Per-run wall-clock bound -- partial progress is "
                              "reported honestly, not erased",
                    gate=GateLevel.INFORM,
                )
                stop_reason = "wall_clock_exceeded"
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
                    plan=original_plan,
                    executed=plan,
                    decisions=list(self._decisions),
                    iterations=iteration,
                    total_time_seconds=time.monotonic() - start_time,
                    success=False,
                    stop_reason="validation_failed",
                    execution_mode="async",
                )

            if soft_warns:
                warn_names = ", ".join(c.name for c in soft_warns)
                self._log_decision(
                    context="validation_warnings",
                    decision=f"Continuing with {len(soft_warns)} warning(s): {warn_names}",
                    reasoning="Soft warnings don't block execution",
                    gate=GateLevel.INFORM,
                )

            # Step 3.5: Predict render outcome (if predictor available)
            prediction: Optional[RenderPrediction] = None
            if self._predictor is not None:
                try:
                    prediction = await self._predictor.predict(plan, checks)
                    self._log_decision(
                        context="prediction",
                        decision=f"Pre-render prediction: {prediction.geo_prim_count} geo, "
                                 f"{prediction.light_count} lights, {prediction.material_count} materials",
                        reasoning=f"{len(prediction.pre_render_issues)} pre-render issue(s)"
                                  if prediction.pre_render_issues
                                  else "Scene structure looks good",
                        gate=GateLevel.INFORM,
                    )
                    self._checkpoint("prediction", {
                        "camera": prediction.camera_prim,
                        "geo_count": prediction.geo_prim_count,
                        "issues": len(prediction.pre_render_issues),
                    })
                except Exception as exc:
                    logger.warning("Prediction failed (non-blocking): %s", exc)

            # Step 4: Execute render steps
            # From here this copy is the attempt that ran. If a later
            # iteration rebinds ``plan`` to a fresh replan copy and stops
            # before dispatching it, ``last_executed`` keeps this attempt.
            last_executed = plan
            execution_ok = await self._execute_steps(plan)
            # A cancel during execution must not be reported as a pass: the
            # steps that never ran leave no frames, and a partial sequence is
            # not a finished render.
            if self._cancelled:
                self._log_decision(
                    context="cancelled_during_execution",
                    decision="Render sequence cancelled while steps were running",
                    reasoning="emergency_stop() was called during execution; "
                              "frames after the cancel never rendered",
                    gate=GateLevel.INFORM,
                )
                stop_reason = "cancelled"
                break
            # R-035: the wall clock expired at a step boundary while steps were
            # being dispatched. The steps that were already running finished;
            # the rest were SKIPPED and never started. Stop here -- collecting
            # and grading a partial sequence would present an unfinished run.
            if self._wall_clock_stopped:
                self._log_decision(
                    context="wall_clock_exceeded",
                    decision=f"Stopping at a step boundary: wall-clock budget "
                             f"({self._max_wall_clock:.0f}s) exceeded",
                    reasoning="Per-run wall-clock bound -- steps that had not "
                              "started were skipped and are reported as such",
                    gate=GateLevel.INFORM,
                )
                stop_reason = "wall_clock_exceeded"
                break
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
                    # Reconcile against the artist's plan, never against the
                    # previous retry.
                    plan = self._execution_copy(
                        self._planner.replan(original_plan, evaluation)
                    )
                    continue
                stop_reason = "max_iterations"
                break

            # Step 5: Collect render results and evaluate
            render_results = await self._collect_results(plan)
            self._accumulate(accumulated, render_results)
            evaluation = self._evaluator.evaluate_sequence(
                [accumulated[k] for k in sorted(accumulated)],
                planned_frames=planned_frames,
                farm_failed_frames=self._farm_failed_frames(plan),
            )

            self._log_decision(
                context="evaluation_complete",
                decision=f"Sequence score: {evaluation.overall_score:.2f}, "
                         f"passed: {evaluation.passed}",
                reasoning=f"{len(evaluation.frame_evaluations)} frame(s) evaluated, "
                          f"{len(evaluation.temporal_issues)} temporal issue(s)"
                          f", {len(evaluation.hard_failures)} hard failure(s)"
                          f", {evaluation.unverified_count} unverified",
                gate=GateLevel.INFORM,
            )

            # Step 5.5: Verify prediction against actual results
            verification: Optional[VerificationResult] = None
            if self._predictor is not None and prediction is not None:
                try:
                    prediction.render_succeeded = execution_ok
                    verification = await self._predictor.verify(prediction, evaluation)
                    self._log_decision(
                        context="verification",
                        decision=f"Verification score: {verification.score:.2f}, "
                                 f"rerender recommended: {verification.should_rerender}",
                        reasoning=verification.reasoning,
                        gate=GateLevel.INFORM,
                    )
                except Exception as exc:
                    logger.warning("Verification failed (non-blocking): %s", exc)

            # Step 6: Check if we need to re-plan
            if evaluation.passed:
                self._log_decision(
                    context="render_success",
                    decision="Render sequence passed quality checks",
                    reasoning=f"Overall score {evaluation.overall_score:.2f} "
                              f">= {evaluation.pass_threshold:.2f} threshold",
                    gate=GateLevel.INFORM,
                )
                break

            if iteration < self._max_iterations:
                # Check if rerendering would actually help
                replan_reasoning = "Evaluation failed -- adjusting settings and re-rendering failed frames"
                if self._predictor is not None and verification is not None:
                    if not verification.should_rerender:
                        replan_reasoning = (
                            "Evaluation failed but verification suggests rerender may not help "
                            f"(score: {verification.score:.2f}). Attempting anyway."
                        )
                # Name the retry reason codes in the readable trail: a
                # missing product and an unreadable one are different
                # problems and should not both read as "evaluation failed".
                target_reasons = retry_targets(original_plan, evaluation)
                if target_reasons:
                    codes = ", ".join(
                        f"frame {frame}: {code}"
                        for frame, code in sorted(target_reasons.items())
                    )
                    replan_reasoning += f" Retry targets -- {codes}"
                self._log_decision(
                    context="replan",
                    decision=f"Re-planning (iteration {iteration}/{self._max_iterations})",
                    reasoning=replan_reasoning,
                    gate=GateLevel.INFORM,
                )
                plan = self._execution_copy(
                    self._planner.replan(original_plan, evaluation)
                )
            else:
                self._log_decision(
                    context="max_iterations",
                    decision=f"Giving up after {self._max_iterations} iteration(s)",
                    reasoning="Max iteration limit reached without passing quality checks",
                    gate=GateLevel.INFORM,
                )
                stop_reason = "max_iterations"

        total_time = time.monotonic() - start_time

        # Step 7: Compile report
        # The report carries the artist's plan. A retry plan is an execution
        # detail: a consumer recomputing the product set from report.plan
        # must not see the last retry's subset. What actually ran -- the last
        # dispatched attempt's validation results and each step's
        # status/result -- rides on ``executed`` instead, so neither half is
        # discarded. A stop that lands between attempts (cancel, wall clock)
        # reports the attempt that ran, not the fresh copy the replan left.
        report = RenderReport(
            plan=original_plan,
            executed=last_executed,
            evaluation=evaluation,
            prediction=prediction if self._predictor is not None else None,
            verification=verification if self._predictor is not None else None,
            decisions=list(self._decisions),
            iterations=iteration,
            total_time_seconds=total_time,
            # A run that stopped for a reason (cancel, wall clock, iteration
            # cap, execution failure) did not succeed, whatever the mean of
            # the frames that did come back says.
            success=bool(evaluation and evaluation.passed and not stop_reason),
            stop_reason=stop_reason,
            execution_mode="async",
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

    def execute_sync(self, intent: str, reason: str = "") -> RenderReport:
        """Run the plan's steps on THIS thread, with no asyncio at all (R-035).

        The fallback for a worker thread where no event loop can be created.
        Houdini 22 ships a patched asyncio ("haio") whose event loop refuses
        ``create_task`` off the main thread, which kills ``asyncio.run`` before
        its first task; a future build could refuse the plain loop class too.
        This path plans, applies the gate policy, and dispatches each step
        through ``handler_interface.call_sync`` -- the same handlers the async
        path calls, which marshal themselves onto Houdini's main thread.

        What does NOT run here, and is never claimed in the report: the
        pre-flight validator (its eight checks are one ``asyncio.gather``),
        the predictor, verification, and quality grading. ``validation_checks``
        is empty ("no check ran", per ``RenderReport``), and the report leaves
        ``evaluation``/``prediction``/``verification`` as None. A run whose
        steps all completed stops with ``stop_reason='sync_steps_ungraded'``
        and ``success=False`` -- frames may be on disk, but nothing graded
        them. ``execution_mode='sync_steps'`` is set on every report.

        The fallback is selected BEFORE any coroutine is created by the caller,
        so no step can be dispatched twice. A guard raised mid-run is a real
        failure to report through the async path, never a reason to replay the
        plan here.
        """
        # M3-E parity: the kill switch reaches this run too.
        _register_live_driver(self)
        try:
            return self._execute_sync_inner(intent, reason)
        finally:
            _register_live_driver(None, only_if=self)

    def _execute_sync_inner(self, intent: str, reason: str) -> RenderReport:
        start_time = time.monotonic()
        deadline = start_time + self._max_wall_clock
        self._deadline = deadline
        self._wall_clock_stopped = False
        self._cancelled = False
        self._decisions = []

        original_plan = self._planner.plan(intent)
        plan = self._execution_copy(original_plan)

        self._log_decision(
            context="sync_fallback",
            decision="Running the plan with the synchronous step loop",
            reasoning=(
                "No asyncio event loop could be created on the render worker "
                "thread (%s), so the plan's steps run without one; validation, "
                "prediction and quality grading need a loop and did not run."
                % (reason or "event-loop construction was refused")
            ),
            gate=GateLevel.INFORM,
        )

        def _report(stop_reason: str, iterations: int) -> RenderReport:
            return RenderReport(
                plan=original_plan,
                executed=plan,
                decisions=list(self._decisions),
                iterations=iterations,
                total_time_seconds=time.monotonic() - start_time,
                # Nothing was graded, so nothing may read as a pass.
                success=False,
                stop_reason=stop_reason,
                execution_mode="sync_steps",
            )

        render_steps = [
            step for step in original_plan.steps
            if step.handler in RENDER_HANDLERS
        ]
        if len(render_steps) > 1:
            self._log_decision(
                context="unsupported_plan_shape",
                decision=f"Refusing a plan with {len(render_steps)} render steps",
                reasoning="The driver grades a single render product set; "
                          "a plan with more than one render step would "
                          "silently grade only the first",
                gate=GateLevel.INFORM,
            )
            return _report("unsupported_plan_shape", 0)

        if plan.gate_level in (GateLevel.REVIEW, GateLevel.CONFIRM):
            if not self._decide_approval(plan):
                self._log_decision(
                    context="gate_rejected",
                    decision="Artist declined the render plan",
                    reasoning="Plan was presented for approval and rejected",
                    gate=plan.gate_level,
                )
                return _report("gate_rejected", 0)

        if self._cancelled:
            self._log_decision(
                context="emergency_stop",
                decision="Render loop cancelled via emergency stop",
                reasoning="emergency_stop() was called before the sync loop ran",
                gate=GateLevel.INFORM,
            )
            return _report("cancelled", 0)

        if time.monotonic() >= deadline:
            self._log_decision(
                context="wall_clock_exceeded",
                decision=f"Stopping: wall-clock budget ({self._max_wall_clock:.0f}s) "
                         f"exceeded before the first step",
                reasoning="Per-run wall-clock bound -- no step was started",
                gate=GateLevel.INFORM,
            )
            return _report("wall_clock_exceeded", 0)

        self._log_decision(
            context="validation_skipped",
            decision="Pre-flight validation did not run",
            reasoning="The eight pre-flight checks run through asyncio.gather; "
                      "this thread has no event loop, so an empty "
                      "validation_checks list means no check ran",
            gate=GateLevel.INFORM,
        )

        call_sync = getattr(self._handler, "call_sync", None)
        if call_sync is None:
            raise RuntimeError(
                "The synchronous autonomy fallback needs "
                "handler_interface.call_sync(); %s provides only call()."
                % (type(self._handler).__name__,)
            )

        execution_ok = True
        for step in plan.steps:
            if self._step_blocked(step):
                continue
            step.status = StepStatus.RUNNING
            try:
                step.result = call_sync(step.handler, step.params)
                step.status = StepStatus.COMPLETED
            except Exception as exc:
                step.error = str(exc)
                step.status = StepStatus.FAILED
                logger.error("Step '%s' failed: %s", step.description, exc)
                execution_ok = False
                break

        if self._cancelled:
            self._log_decision(
                context="cancelled_during_execution",
                decision="Render sequence cancelled while steps were running",
                reasoning="emergency_stop() was called during execution; "
                          "frames after the cancel never rendered",
                gate=GateLevel.INFORM,
            )
            return _report("cancelled", 1)
        if self._wall_clock_stopped:
            self._log_decision(
                context="wall_clock_exceeded",
                decision=f"Stopping at a step boundary: wall-clock budget "
                         f"({self._max_wall_clock:.0f}s) exceeded",
                reasoning="Per-run wall-clock bound -- steps that had not "
                          "started were skipped and are reported as such",
                gate=GateLevel.INFORM,
            )
            return _report("wall_clock_exceeded", 1)
        if not execution_ok:
            self._log_decision(
                context="execution_failed",
                decision="One or more render steps failed",
                reasoning="Handler returned an error during execution; the "
                          "synchronous fallback does not retry",
                gate=GateLevel.INFORM,
            )
            return _report("execution_failed", 1)

        self._log_decision(
            context="sync_steps_ungraded",
            decision="Every planned step ran; nothing graded the output",
            reasoning="Quality grading needs the event loop this thread cannot "
                      "create, so the step results are reported as they came "
                      "back, never as a pass",
            gate=GateLevel.INFORM,
        )
        return _report("sync_steps_ungraded", 1)

    def emergency_stop(self) -> None:
        """Cancel the current render loop at the next iteration boundary.

        Sets the cancel flag only -- the in-flight step finishes before the
        loop stops (no TOPS work-item cancellation is attempted here).
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

        R-035: the wall clock is checked at every STEP boundary as well as at
        each iteration boundary. An in-flight step is never aborted (a render
        cannot be safely torn mid-call), but once the deadline has passed no
        further step starts; the remaining steps are marked SKIPPED and
        ``_wall_clock_stopped`` tells the caller why the report is partial.
        """
        for step in plan.steps:
            if self._step_blocked(step):
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

    def _step_blocked(self, step: RenderStep) -> bool:
        """Mark ``step`` SKIPPED when the run is cancelled or out of time.

        Shared by the async step loop and the synchronous fallback so both
        paths agree on what "never started" means: an in-flight step always
        finishes (a render is not torn mid-call), and the wall clock is
        consulted at every step boundary.
        """
        if self._cancelled:
            step.status = StepStatus.SKIPPED
            return True

        if self._deadline is not None and time.monotonic() >= self._deadline:
            step.status = StepStatus.SKIPPED
            self._wall_clock_stopped = True
            return True

        return False

    @staticmethod
    def _execution_copy(plan: RenderPlan) -> RenderPlan:
        """A mutable copy to execute against.

        Execution writes step status/result and fills in the plan's validation
        checks. Doing that on the artist's plan would make the "original"
        handed to replan a rewritten plan by iteration 2. Copying the step
        objects is not enough on its own: ``replace(step)`` leaves ``params``
        pointing at the plan's own dict, so a handler that writes into the
        params it was handed would rewrite the artist's request. The params
        are deep-copied for exactly that reason.

        The copy starts with no validation checks. The planner's declared
        checks are a to-do list, not results. Every path that runs validation
        replaces the empty list with the validator's verdicts; every path that
        stops before dispatch (gate rejected, unsupported shape, or a cancel
        or wall-clock stop before the first validate) reports the absence
        honestly instead of presenting declared ``passed=False`` checks as
        hard failures that never happened (ruling R4b).
        """
        return replace(
            plan,
            steps=[
                replace(step, params=copy.deepcopy(step.params))
                for step in plan.steps
            ],
            validation_checks=[],
        )

    def _render_step(self, plan: RenderPlan):
        """The single step that renders, or None when there isn't exactly one.

        Ambiguity returns None rather than picking the first: a caller that
        cannot identify the render step has no product set, and guessing one
        is how the second render gets silently ignored.
        """
        renders = [
            step for step in plan.steps if step.handler in RENDER_HANDLERS
        ]
        if len(renders) != 1:
            return None
        return renders[0]

    def _planned_frames(self, plan: RenderPlan) -> Optional[List[int]]:
        """The frames the plan asked for, or None when the plan does not say.

        This is what the sequence is graded against. Without it a render that
        lost frames is scored on the frames that happened to come back. The
        product set is derived by the planner, so a sparse request stays
        sparse instead of being re-expanded into a range here.
        """
        frames = requested_frames(plan)
        return list(frames) if frames is not None else None

    def _accumulate(
        self,
        accumulated: Dict[int, Dict[str, Any]],
        render_results: List[Dict[str, Any]],
    ) -> None:
        """Fold a batch of frame results into the cross-attempt accumulator.

        A full-plan re-run (an execution-failure retry, or a replan that
        returns the original plan) can come back with a failed row for a
        frame whose product was already accepted. That row must not replace
        the known-good selection; the retry is reported, not the regression.
        """
        for row in render_results:
            try:
                frame_no = int(row.get("frame", 0))
            except (TypeError, ValueError):
                frame_no = 0

            incoming_failed = self._row_failed(row)
            existing = accumulated.get(frame_no)
            if (
                existing is not None
                and incoming_failed
                and not self._row_failed(existing)
            ):
                self._log_decision(
                    context="accumulated_product_preserved",
                    decision=f"Kept the accepted product for frame {frame_no}",
                    reasoning="A retry returned a failed row for a frame that "
                              "already has a known-good output; the "
                              "known-good product is kept",
                    gate=GateLevel.INFORM,
                )
                continue

            accumulated[frame_no] = row

    @staticmethod
    def _row_failed(row: Dict[str, Any]) -> bool:
        """A rendered-frame row that carries no usable product."""
        return bool(row.get("error")) or not row.get("output_path")

    def _farm_failed_frames(self, plan: RenderPlan) -> int:
        """The farm's own failed-frame count for this render, 0 when unknown."""
        step = self._render_step(plan)
        if step is None or not isinstance(step.result, dict):
            return 0
        try:
            return int(step.result.get("failed_frames", 0) or 0)
        except (TypeError, ValueError):
            return 0

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
        render_step = self._render_step(plan)

        if render_step is None or render_step.result is None:
            return results

        # Extract output info from the published BatchReport.to_dict() shape
        # (render_farm.py): frame_results entries carry frame + image_path,
        # and the farm's per-frame error when the frame failed.
        for fr in render_step.result.get("frame_results", []):
            if isinstance(fr, dict):
                results.append({
                    "frame": fr.get("frame", 0),
                    "output_path": fr.get("image_path", ""),
                    "image_data": None,
                    "error": fr.get("error", ""),
                })

        # Single-frame handlers return a bare image_path instead
        if not results and render_step.result.get("image_path"):
            frame = render_step.params.get(
                "frame", render_step.params.get("start_frame", 1)
            )
            results.append({
                "frame": int(frame),
                "output_path": render_step.result["image_path"],
                "image_data": None,
            })

        # Unparseable result -> [] -> evaluate_sequence([]) -> honest failure.
        # Never fabricate frame entries from step params.
        return results

    # ------------------------------------------------------------------
    # Internal: gate system
    # ------------------------------------------------------------------

    async def _present_for_approval(self, plan: RenderPlan) -> bool:
        """Present a plan for artist approval (async entry point).

        The policy itself contains no await; it is shared with the synchronous
        fallback through ``_decide_approval``.
        """
        return self._decide_approval(plan)

    def _decide_approval(self, plan: RenderPlan) -> bool:
        """The gate policy, with no I/O in it.

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
