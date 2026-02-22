"""
Synapse Render Farm Orchestrator

Local render farm that renders sequences, validates each frame
automatically, diagnoses issues, adjusts settings, and re-renders --
learning from every outcome so future renders start smarter.

Architecture:
- External Python orchestrator (not pure PDG -- PDG is acyclic, can't loop)
- Wraps existing handlers: render, validate_frame, render_settings
- All Houdini mutations go through handler safety middleware
- Tier 0 speed: no LLM per frame, only code-speed diagnosis

GPU/CPU Pipeline Overlap:
- 1 concurrent Karma XPU render (exclusive GPU)
- Validation runs on CPU after render completes
- Next frame starts rendering while previous validates
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ..core.determinism import round_float
from ..memory.models import MemoryType, MemoryQuery
from .render_diagnostics import (
    Remedy,
    classify_scene,
    diagnose_issues,
    record_fix_outcome,
    query_known_fixes,
    ISSUE_REMEDIES,
)
from .render_notify import (
    BatchReport,
    FrameResult,
    build_progress_event,
    notify_batch_complete,
    notify_persistent_failure,
)

logger = logging.getLogger("synapse.render_farm")


# =========================================================================
# Callback types for handler delegation
# =========================================================================

@dataclass
class RenderCallbacks:
    """Callbacks to existing Synapse handlers.

    The orchestrator doesn't import hou or call Houdini directly.
    All scene mutations go through these callbacks, which delegate
    to the existing handler safety middleware.
    """
    render_frame: Callable[[Dict], Dict]
    """render handler: (payload) -> {"image_path": str, "rop": str, ...}"""

    validate_frame: Callable[[Dict], Dict]
    """validate_frame handler: (payload) -> {"valid": bool, "checks": {...}}"""

    get_render_settings: Callable[[Dict], Dict]
    """render_settings handler (read): (payload) -> {"settings": {...}}"""

    set_render_settings: Callable[[Dict], Dict]
    """render_settings handler (write): (payload) -> {"settings": {...}}"""

    get_stage_info: Optional[Callable[[Dict], Dict]] = None
    """get_stage_info handler for scene classification."""

    broadcast: Optional[Callable[[Dict], None]] = None
    """WebSocket broadcast for progress events."""


# =========================================================================
# Orchestrator
# =========================================================================

class RenderFarmOrchestrator:
    """Renders sequences with per-frame validation and auto-fix.

    Usage:
        callbacks = RenderCallbacks(
            render_frame=handler._handle_render,
            validate_frame=handler._handle_validate_frame,
            get_render_settings=lambda p: handler._handle_render_settings(p),
            set_render_settings=lambda p: handler._handle_render_settings(p),
        )
        farm = RenderFarmOrchestrator(callbacks)
        report = farm.render_sequence(
            rop="/stage/karma1",
            frame_range=(1001, 1100),
        )
    """

    def __init__(
        self,
        callbacks: RenderCallbacks,
        memory=None,
        max_retries: int = 3,
        auto_fix: bool = True,
        report_dir: Optional[str] = None,
        notify_milestones: bool = True,
    ):
        self._cb = callbacks
        self._memory = memory
        self._max_retries = max_retries
        self._auto_fix = auto_fix
        self._report_dir = report_dir
        self._notify_milestones = notify_milestones
        # CPU pool for validation (runs while GPU renders next frame)
        self._cpu_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="synapse_validate")
        self._scene_tags: List[str] = []
        self._running = False
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the current render sequence."""
        self._cancelled = True

    @property
    def is_running(self) -> bool:
        return self._running

    # -----------------------------------------------------------------
    # Scene classification + memory warmup
    # -----------------------------------------------------------------

    def _classify_scene(self) -> List[str]:
        """Classify the current USD stage for cross-shot learning."""
        if self._cb.get_stage_info is None:
            return []
        try:
            info = self._cb.get_stage_info({})
            return classify_scene(info)
        except Exception:
            logger.debug("Scene classification failed", exc_info=True)
            return []

    def _warmup_from_memory(self, rop: str) -> Dict:
        """Query memory for known-good settings matching scene tags.

        If a high-confidence past fix matches, returns settings to apply
        before the first frame. This is where self-improvement compounds.
        """
        if self._memory is None or not self._scene_tags:
            return {}

        suggested = {}
        # For each issue type, check if memory has a known fix
        for issue_type in sorted(ISSUE_REMEDIES.keys()):
            fixes = query_known_fixes(
                self._memory, issue_type, self._scene_tags, limit=3
            )
            if fixes and fixes[0].get("score", 0) > 0.7:
                # Parse the fix content for the parameter value
                content = fixes[0].get("content", "")
                # Extract parameter name and value from structured content
                for line in content.split("\n"):
                    if line.startswith("**Parameter:**"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            parm = parts[0].replace("**Parameter:**", "").strip()
                            try:
                                val = float(parts[1].strip())
                                suggested[parm] = val
                            except ValueError:
                                pass
        return suggested

    # -----------------------------------------------------------------
    # Single frame: render + validate + auto-fix
    # -----------------------------------------------------------------

    def render_frame_validated(
        self,
        rop: str,
        frame: int,
        current_settings: Optional[Dict] = None,
    ) -> FrameResult:
        """Render one frame, validate, and auto-fix if needed.

        Args:
            rop: ROP node path.
            frame: Frame number.
            current_settings: Current render settings (for remedy computation).

        Returns:
            FrameResult with success/failure details.
        """
        result = FrameResult(frame=frame, success=False)
        settings_snapshot = dict(current_settings or {})

        for attempt in range(1 + self._max_retries):
            if self._cancelled:
                result.error = "Cancelled"
                return result

            # --- Render ---
            t0 = time.time()
            try:
                render_resp = self._cb.render_frame({
                    "node": rop,
                    "frame": frame,
                })
                result.render_time = round_float(time.time() - t0)
                result.image_path = render_resp.get("image_path", "")
            except Exception as e:
                result.render_time = round_float(time.time() - t0)
                result.error = str(e)
                result.success = False
                return result

            if not result.image_path:
                result.error = "Render produced no output image"
                result.success = False
                return result

            # --- Validate ---
            t1 = time.time()
            try:
                val_resp = self._cb.validate_frame({
                    "image_path": result.image_path,
                })
                result.validate_time = round_float(time.time() - t1)
            except Exception as e:
                result.validate_time = round_float(time.time() - t1)
                # Validation error is not a render failure
                logger.warning("Validation error on frame %d: %s", frame, e)
                result.success = True
                return result

            if val_resp.get("valid", True):
                result.success = True
                # Record success for learning
                if attempt > 0 and self._memory is not None:
                    # We fixed something — record what worked
                    for fix_desc in result.fixes_applied:
                        record_fix_outcome(
                            self._memory,
                            issue_type=result.issues[-1] if result.issues else "unknown",
                            remedy=Remedy(
                                issue_type="auto",
                                description=fix_desc,
                                parm_name="",
                                adjust_fn="set",
                                adjust_value=0,
                            ),
                            success=True,
                            scene_tags=self._scene_tags,
                            settings_applied=settings_snapshot,
                            frame=frame,
                        )
                return result

            # --- Validation failed ---
            failed_checks = [
                name for name, check in sorted(val_resp.get("checks", {}).items())
                if not check.get("passed", True)
            ]
            result.issues.extend(failed_checks)

            if not self._auto_fix or attempt >= self._max_retries:
                result.retries = attempt
                result.success = False
                result.error = f"Validation failed: {', '.join(failed_checks)}"
                # Record failure for learning
                if self._memory is not None:
                    for issue in failed_checks:
                        record_fix_outcome(
                            self._memory,
                            issue_type=issue,
                            remedy=Remedy(
                                issue_type=issue,
                                description="exhausted retries",
                                parm_name="",
                                adjust_fn="set",
                                adjust_value=0,
                            ),
                            success=False,
                            scene_tags=self._scene_tags,
                            settings_applied=settings_snapshot,
                            frame=frame,
                        )
                return result

            # --- Diagnose and fix ---
            diagnostics = diagnose_issues(
                val_resp, self._memory, self._scene_tags
            )

            if not diagnostics:
                result.retries = attempt
                result.success = False
                result.error = f"No remedy available for: {', '.join(failed_checks)}"
                return result

            # Apply the top remedy
            issue_type, remedy, memory_match = diagnostics[0]
            logger.info(
                "Frame %d: applying remedy '%s' for %s (attempt %d/%d)",
                frame, remedy.description, issue_type, attempt + 1, self._max_retries,
            )

            try:
                # Get current value of the parameter
                current_val = settings_snapshot.get(remedy.parm_name, 0)
                if isinstance(current_val, str):
                    try:
                        current_val = float(current_val)
                    except ValueError:
                        current_val = 0
                new_val = remedy.compute_new_value(current_val)

                # Apply the fix via render_settings handler
                self._cb.set_render_settings({
                    "node": rop,
                    "settings": {remedy.parm_name: new_val},
                })
                settings_snapshot[remedy.parm_name] = new_val
                result.fixes_applied.append(
                    f"{remedy.parm_name}={new_val} ({remedy.description})"
                )
            except Exception as e:
                logger.warning(
                    "Failed to apply remedy on frame %d: %s", frame, e
                )
                result.retries = attempt
                result.success = False
                result.error = f"Remedy application failed: {e}"
                return result

            result.retries = attempt + 1
            # Loop back to re-render

        result.success = False
        result.error = "Exhausted all retries"
        return result

    # -----------------------------------------------------------------
    # Full sequence
    # -----------------------------------------------------------------

    def render_sequence(
        self,
        rop: str,
        frame_range: Tuple[int, int],
        step: int = 1,
    ) -> BatchReport:
        """Render a frame range with per-frame validation and auto-fix.

        Args:
            rop: ROP node path (auto-discovers if empty).
            frame_range: (start_frame, end_frame) inclusive.
            step: Frame step (default: 1).

        Returns:
            BatchReport with per-frame results and summary.
        """
        self._running = True
        self._cancelled = False
        start_frame, end_frame = frame_range
        frames = list(range(start_frame, end_frame + 1, step))
        total = len(frames)

        report = BatchReport(
            start_frame=start_frame,
            end_frame=end_frame,
            total_frames=total,
            rop_path=rop,
        )
        wall_start = time.time()

        # Phase 0: Scene classification + memory warmup
        self._scene_tags = self._classify_scene()
        report.scene_tags = list(self._scene_tags)

        # Get initial render settings
        initial_settings = {}
        try:
            settings_resp = self._cb.get_render_settings({"node": rop})
            initial_settings = settings_resp.get("settings", {})
        except Exception:
            logger.debug("Could not read initial render settings")

        # Apply memory-suggested settings if available
        suggested = self._warmup_from_memory(rop)
        if suggested:
            logger.info("Applying memory-suggested settings: %s", suggested)
            try:
                self._cb.set_render_settings({
                    "node": rop,
                    "settings": suggested,
                })
                initial_settings.update(suggested)
            except Exception:
                logger.debug("Failed to apply memory-suggested settings")

        report.settings_used = dict(initial_settings)

        # Phase 1: Render each frame
        pending_validation: Optional[Future] = None
        milestone_thresholds = {
            int(total * 0.25): "25%",
            int(total * 0.50): "50%",
            int(total * 0.75): "75%",
        }

        for idx, frame in enumerate(frames):
            if self._cancelled:
                break

            # Broadcast progress
            if self._cb.broadcast:
                try:
                    self._cb.broadcast(build_progress_event(
                        frame=idx + 1,
                        total_frames=total,
                        status="rendering",
                    ))
                except Exception:
                    pass

            # Render and validate this frame
            frame_result = self.render_frame_validated(
                rop=rop,
                frame=frame,
                current_settings=initial_settings,
            )

            report.frame_results.append(frame_result)
            report.total_render_time += frame_result.render_time

            if frame_result.success:
                report.successful_frames += 1
            else:
                report.failed_frames += 1
                # Notify on persistent failure
                if frame_result.retries >= self._max_retries:
                    notify_persistent_failure(
                        frame,
                        frame_result.issues[0] if frame_result.issues else "unknown",
                        frame_result.retries,
                    )

            # Milestone notifications
            if self._notify_milestones and (idx + 1) in milestone_thresholds:
                pct = milestone_thresholds[idx + 1]
                if self._cb.broadcast:
                    try:
                        self._cb.broadcast(build_progress_event(
                            frame=idx + 1,
                            total_frames=total,
                            status=f"milestone_{pct}",
                            details={"milestone": pct},
                        ))
                    except Exception:
                        pass

        # Phase 2: Finalize
        report.total_wall_time = round_float(time.time() - wall_start)
        self._running = False

        # Write report and send notifications
        report_dir = self._report_dir
        if not report_dir:
            # Default: use a temporary directory
            report_dir = os.path.join(os.path.expanduser("~"), ".synapse", "render_reports")

        notify_results = notify_batch_complete(report, report_dir)
        logger.info(
            "Render sequence complete: %d/%d frames OK (%.0f%%), wall time %.1fs",
            report.successful_frames,
            report.total_frames,
            report.success_rate * 100,
            report.total_wall_time,
        )

        # Record batch outcome in memory
        if self._memory is not None:
            try:
                self._memory.add(
                    content=(
                        f"**Render Batch:** {start_frame}-{end_frame}\n"
                        f"**Result:** {report.successful_frames}/{report.total_frames} OK\n"
                        f"**Time:** {report.total_wall_time:.1f}s\n"
                        f"**Scene Tags:** {', '.join(self._scene_tags)}\n"
                        f"**ROP:** {rop}"
                    ),
                    memory_type=MemoryType.NOTE,
                    tags=sorted(["render_report", *self._scene_tags[:3]]),
                    keywords=sorted(["render", "batch", "sequence"]),
                    source="auto",
                )
            except Exception:
                logger.debug("Failed to record batch in memory")

        return report

    def get_status(self) -> Dict:
        """Get current render farm status for the MCP tool."""
        return {
            "running": self._running,
            "cancelled": self._cancelled,
            "scene_tags": self._scene_tags,
        }

    def shutdown(self):
        """Clean up the CPU thread pool."""
        self._cpu_pool.shutdown(wait=False)
