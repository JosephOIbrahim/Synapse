"""Approval-bound render jobs around the existing foreground/bounded path.

A render has no access to build rollback. Overrides have their own terminal,
bounded restoration operation. External files are evidence, never undo data.
Transport timeouts preserve ownership and request identity until the actual
main-thread callback completes. Process restart dedup requires a durable host
registry; this registry deliberately does not claim cross-process guarantees.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import threading
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from .contracts import (ApprovalBinding, OperationState, RecipeInstance, RecoveryVerdict,
                        Refusal, RefusalKind, TerminalVerdict)
from .instance import on_main
from .transaction import state_diff


@dataclass(frozen=True)
class RenderPlan:
    run_id: str
    node_path: str
    engine: str
    resolution: tuple[int, int]
    samples: int
    output_path: str
    frame: int

    @classmethod
    def prepare(cls, *, output_root: str, node_path: str, engine: str,
                resolution: tuple[int, int], samples: int, frame: int = 1):
        """Trusted host prepares the exact destination BEFORE asking approval."""
        run_id = uuid4().hex
        output = Path(output_root).resolve() / run_id / "image.exr"
        return cls(run_id, node_path, engine, resolution, samples, str(output), frame)


class ApprovalRechecker(Protocol):
    def __call__(self, binding: ApprovalBinding, instance: RecipeInstance,
                 plan: RenderPlan) -> Refusal | None: ...


class RenderBackend(Protocol):
    """Host methods run on main; cancel is a thread-safe request, not a HOM call.

    start returns only when the actual render has terminated, not when a wait
    budget expires. BoundedRenderAdapter enforces the existing inline branch.
    The enclosing job's dispatcher may time out independently. Capturing and
    restoring overrides must cover ALL fields the existing renderer can touch.
    """
    def capture_overrides(self, plan: RenderPlan) -> Mapping[str, Any]: ...
    def apply_overrides(self, plan: RenderPlan) -> None: ...
    def effective_scope(self, plan: RenderPlan) -> Mapping[str, Any]: ...
    def start(self, plan: RenderPlan) -> Mapping[str, Any]: ...
    def render_terminated(self, plan: RenderPlan) -> bool | None: ...
    def foreign_epoch(self) -> int | None: ...
    def restore_overrides(self, plan: RenderPlan, before: Mapping[str, Any]) -> None: ...
    def cancel(self) -> bool: ...


class BoundedRenderAdapter:
    """Wrap a live RenderHandlerMixin and a qualified override driver.

    We deliberately invoke _handle_render_bounded on the main thread: its
    inline path calls the existing renderer, including all WP4 restoration and
    foreground guards. An off-main session's 'error' can be only a marshal
    timeout, so it cannot establish actual render termination for this job.
    Existing renderer output/engine/sample parms are set via the injected
    driver because the public payload has no exact output/sample binding.
    """
    def __init__(self, handler, overrides):
        self.handler, self.overrides = handler, overrides

    def capture_overrides(self, plan):
        from synapse.server.render_session import active_session
        if active_session() is not None:
            raise RuntimeError("UNAVAILABLE: another legacy render session is active")
        return self.overrides.capture_overrides(plan)

    def apply_overrides(self, plan):
        self.overrides.apply_overrides(plan)

    def effective_scope(self, plan):
        return self.overrides.effective_scope(plan)

    def restore_overrides(self, plan, before):
        self.overrides.restore_overrides(plan, before)

    def start(self, plan):
        from synapse.server.main_thread import _MAIN_THREAD_ID
        if threading.get_ident() != _MAIN_THREAD_ID:
            raise RuntimeError("bounded render adapter must execute on Houdini's main thread")
        return self.handler._handle_render_bounded({
            "node": plan.node_path, "width": plan.resolution[0], "height": plan.resolution[1],
            "frame": plan.frame, "wait_budget_s": 0,
            "force_new": False, "force_foreground": False,
        })

    def cancel(self):
        # No qualified interrupt driver is installed. Never call global undo.
        return False

    def foreign_epoch(self):
        return self.overrides.foreign_epoch()

    def render_terminated(self, plan):
        # RopNode.render() may have launched a background native process.
        # A qualified driver must establish its termination independently of
        # the Python return/exception; absent evidence remains UNKNOWN.
        confirm = getattr(self.overrides, "render_terminated", None)
        return confirm(plan) if confirm is not None else None


@dataclass
class RenderResult:
    request_id: str
    run_id: str
    state: OperationState = OperationState.PENDING
    outcome: str = "pending"
    verdict: TerminalVerdict = TerminalVerdict.UNKNOWN
    recovery: RecoveryVerdict = RecoveryVerdict.NOT_NEEDED
    refusal: Refusal | None = None
    reason: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    render_terminated: bool = False
    cancellation_requested: bool = False
    cancellation_supported: bool | None = None
    logs: list[Any] = field(default_factory=list)
    output_identity: dict[str, Any] = field(default_factory=dict)
    residual_diff: list[dict[str, Any]] = field(default_factory=list)
    backend_result: dict[str, Any] = field(default_factory=dict)


def file_identity(path: str) -> dict[str, Any]:
    """Hash the file actually written; detect replacement/change while hashing."""
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise RuntimeError("fresh regular render output is absent")
    digest = hashlib.sha256()
    with p.open("rb") as stream:
        import os
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
    current = p.stat()
    keys = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if keys(before) != keys(after) or keys(after) != keys(current) or not after.st_size:
        raise RuntimeError("render output is empty or changed during identity capture")
    return {"path": str(p.resolve()), "size": after.st_size, "mtime_ns": after.st_mtime_ns,
            "device": after.st_dev, "inode": after.st_ino, "sha256": digest.hexdigest()}


def _now():
    return datetime.now(timezone.utc).isoformat()


class RenderJob:
    def __init__(self, *, request_id: str, plan: RenderPlan,
                 approval: ApprovalBinding | None, current_instance: Callable[[], RecipeInstance],
                 recheck_approval: ApprovalRechecker, backend: RenderBackend,
                 dispatch: Callable = on_main, guard: Callable | None = None):
        if not request_id:
            raise ValueError("request_id required")
        self.plan, self.approval = plan, approval
        self.current_instance, self.recheck_approval = current_instance, recheck_approval
        self.backend, self.dispatch = backend, dispatch
        if guard is None:
            from synapse.server.foreground_guard import assess_foreground_render
            guard = assess_foreground_render
        self.guard = guard
        self.result = RenderResult(request_id, plan.run_id)
        self._lock = threading.Lock()
        self._render_terminal, self._finished = threading.Event(), threading.Event()
        self._host_returned = threading.Event()
        self._started = self._entered = self._abandoned = False
        self._restore_started = self._override_attempted = False
        self._cancel = threading.Event()
        self._before = None
        self._after = None
        self._foreign = None
        self._pending_outcome = None

    def _check(self):
        binding, plan = self.approval, self.plan
        if binding is None:
            return Refusal(RefusalKind.APPROVAL_REQUIRED, "explicit render approval required")
        current = self.current_instance()
        if current is None or (binding.instance_id, binding.graph_revision) != (
                current.instance_id, current.graph_revision):
            return Refusal(RefusalKind.STALE, "render approval instance revision changed")
        if ((binding.engine, binding.resolution, binding.samples, binding.output_path) !=
                (plan.engine, plan.resolution, plan.samples, plan.output_path) or
                not binding.approved_by or not binding.approved_at):
            return Refusal(RefusalKind.APPROVAL_MISMATCH, "render approval scope mismatch")
        return self.recheck_approval(binding, current, plan)

    def _validate_plan(self):
        plan = self.plan
        p = Path(plan.output_path)
        if (not re.fullmatch(r"[a-f0-9]{32}", plan.run_id) or not p.is_absolute() or
                p.parent.name != plan.run_id or str(p.resolve()) != str(p) or
                len(plan.resolution) != 2 or
                any(type(v) is not int or v <= 0 for v in (*plan.resolution, plan.samples)) or
                type(plan.frame) is not int or not plan.node_path.startswith("/")):
            raise ValueError("invalid bounded run-specific render plan")
        if p.exists() or p.is_symlink():
            raise ValueError("output already exists; stale file cannot count as this run")

    def start(self):
        with self._lock:
            if self._started:
                return self.result
            self._started = True
            self.result.state = OperationState.RUNNING
        try:
            self.dispatch(self._run_on_main)
        except Exception as exc:
            with self._lock:
                if not self._entered:
                    self._abandoned = True
                    self.result.outcome = "failed"
                    self.result.reason = "dispatch unavailable: " + str(exc)
                    self._render_terminal.set()
                else:
                    self.result.logs.append("caller timeout; render termination unconfirmed: " + str(exc))
        if self._render_terminal.is_set():
            self.restore()
        return self.result

    def _run_on_main(self):
        with self._lock:
            if self._abandoned or self._entered:
                return
            self._entered = True
        terminal_confirmed = True
        try:
            self._validate_plan()
            refusal = self._check()
            if refusal:
                self._refuse(refusal)
                return
            assessment = self.guard(self.plan.engine, width=self.plan.resolution[0],
                                    height=self.plan.resolution[1], samples=self.plan.samples,
                                    force=False)
            self.result.logs.append({"foreground_guard": assessment})
            if assessment.get("allow") is not True:
                self._refuse(Refusal(RefusalKind.PROFILE_CONFLICT,
                                    "foreground render refused: " + str(assessment.get("reason", "unknown"))))
                return
            if self._cancel.is_set():
                self.result.outcome = "cancelled"
                self.result.verdict = TerminalVerdict.CANCELLED
                return
            self._before = deepcopy(dict(self.backend.capture_overrides(self.plan)))
            self._foreign = self.backend.foreign_epoch()
            self._override_attempted = True
            self.backend.apply_overrides(self.plan)
            effective = self.backend.effective_scope(self.plan)
            expected = {"engine": self.plan.engine, "resolution": self.plan.resolution,
                        "samples": self.plan.samples, "output_path": self.plan.output_path}
            if dict(effective) != expected:
                self._refuse(Refusal(RefusalKind.APPROVAL_MISMATCH, "live render settings differ from approval"))
                return
            Path(self.plan.output_path).parent.mkdir(parents=True, exist_ok=True)
            # Recheck at the final start boundary, AFTER preparation/overrides.
            refusal = self._check()
            if refusal:
                self._refuse(refusal)
                return
            if self._cancel.is_set():
                self.result.outcome = "cancelled"
                self.result.verdict = TerminalVerdict.CANCELLED
                return
            if Path(self.plan.output_path).exists():
                raise RuntimeError("output appeared before render start; refusing stale overwrite")
            self.result.started_at = _now()
            response = self.backend.start(self.plan)
            if response.get("status") == "render_in_progress":
                # This may name an unrelated active legacy session. Never adopt
                # its token or mark its completion as evidence for our request.
                terminal_confirmed = False
                self.result.reason = "render termination UNKNOWN: bounded renderer returned an active session"
                self.result.backend_result = deepcopy(dict(response))
                self.result.recovery = RecoveryVerdict.UNKNOWN
                return
            self.result.backend_result = deepcopy(dict(response))
            self.result.logs.extend(deepcopy(response.get("logs", [])))
            if response.get("status") in ("cancelled", "canceled"):
                self.result.outcome = "cancelled"
                self.result.verdict = TerminalVerdict.CANCELLED
            elif response.get("error") or response.get("success") is False or response.get("status") in ("error", "failed"):
                raise RuntimeError("render failed: " + str(response))
            else:
                # Classify the file only after independent native termination;
                # a background renderer may not have written its first bytes yet.
                self.result.outcome = "succeeded"
                self.result.reason = "terminal output recorded; P5 image verification remains required"
                # Fresh bytes are NOT a verified image/scene.
                self.result.verdict = TerminalVerdict.UNKNOWN
        except Exception as exc:
            self.result.outcome = "failed"
            self.result.verdict = TerminalVerdict.BROKEN
            self.result.reason = str(exc)
        finally:
            if self.result.started_at and terminal_confirmed:
                try:
                    terminal_confirmed = self.backend.render_terminated(self.plan) is True
                except Exception:
                    terminal_confirmed = False
            if terminal_confirmed:
                self._capture_terminal()
            else:
                self._pending_outcome = (self.result.outcome, self.result.verdict, self.result.reason)
                self.result.outcome = "running"
                self.result.verdict = TerminalVerdict.UNKNOWN
                self.result.recovery = RecoveryVerdict.UNKNOWN
                self.result.output_identity = {}
                self.result.logs.append("native render termination UNKNOWN; overrides remain reserved")
            self._host_returned.set()

    def _capture_terminal(self):
        if self._pending_outcome is not None:
            self.result.outcome, self.result.verdict, self.result.reason = self._pending_outcome
            self._pending_outcome = None
        if self._override_attempted:
            try:
                self._after = deepcopy(dict(self.backend.capture_overrides(self.plan)))
            except Exception as exc:
                self.result.logs.append("post-render overrides unobservable: " + str(exc))
        # Failed/cancelled renders can leave external files too.
        if self.result.started_at:
            try:
                self.result.output_identity = file_identity(self.plan.output_path)
            except Exception:
                self.result.output_identity = {}
                if self.result.outcome == "succeeded":
                    self.result.outcome = "failed"
                    self.result.verdict = TerminalVerdict.BROKEN
                    self.result.reason = "fresh output absent at confirmed native termination"
        self.result.render_terminated = True
        self._render_terminal.set()

    def poll(self):
        """Re-observe native termination without starting or retrying a render."""
        if self._host_returned.is_set() and not self._render_terminal.is_set():
            def probe():
                if self.backend.render_terminated(self.plan) is True:
                    self._capture_terminal()
            try:
                self.dispatch(probe)
            except Exception as exc:
                self.result.logs.append("termination probe unavailable: " + str(exc))
        if self._render_terminal.is_set():
            self.restore()
        return self.result

    def _refuse(self, refusal):
        self.result.refusal = refusal
        self.result.reason = refusal.reason
        self.result.outcome = "refused"
        self.result.verdict = TerminalVerdict.REFUSED

    def cancel(self):
        self._cancel.set()
        self.result.cancellation_requested = True
        with self._lock:
            if self.result.cancellation_supported is not None:
                return self.result.cancellation_supported
            # A request never changes terminal state before host acknowledgement.
            self.result.cancellation_supported = bool(self.backend.cancel())
        return self.result.cancellation_supported

    def restore(self):
        """One separate bounded restoration; never race a running render."""
        if not self._render_terminal.is_set():
            raise RuntimeError("restore refused: actual render terminal state required")
        with self._lock:
            if self._restore_started:
                return self.result.recovery
            self._restore_started = True
        if not self._override_attempted:
            self._finish()
            return self.result.recovery
        self.result.recovery = RecoveryVerdict.UNKNOWN
        try:
            self.dispatch(self._restore_on_main)
        except Exception as exc:
            self.result.logs.append("override restore wait ended; no retry: " + str(exc))
            # Callback may still be restoring. No terminal or second write.
        return self.result.recovery

    def _restore_on_main(self):
        try:
            current = deepcopy(dict(self.backend.capture_overrides(self.plan)))
            self.result.residual_diff = state_diff(self._before, current)
            if current != self._before:
                if (self._after is None or current != self._after or self._foreign is None or
                        self.backend.foreign_epoch() != self._foreign):
                    self.result.recovery = RecoveryVerdict.RESIDUE
                    return
                self.backend.restore_overrides(self.plan, deepcopy(self._before))
            after = deepcopy(dict(self.backend.capture_overrides(self.plan)))
            self.result.residual_diff = state_diff(self._before, after)
            self.result.recovery = (RecoveryVerdict.RESIDUE if self.result.residual_diff
                                    else RecoveryVerdict.RESTORED)
        except Exception as exc:
            self.result.recovery = RecoveryVerdict.UNKNOWN
            self.result.logs.append("override restore failed: " + str(exc))
            try:
                after = deepcopy(dict(self.backend.capture_overrides(self.plan)))
                self.result.residual_diff = state_diff(self._before, after)
                if self.result.residual_diff:
                    self.result.recovery = RecoveryVerdict.RESIDUE
            except Exception:
                pass
        finally:
            self._finish()

    def _finish(self):
        self.result.state = OperationState.TERMINAL
        self.result.completed_at = _now()
        self._finished.set()

    def await_terminal(self, timeout: float | None = None):
        if not self._render_terminal.wait(timeout):
            return None
        self.restore()
        return self.result if self._finished.wait(timeout) else None


class RenderJobRegistry:
    """Register BEFORE start; a lost response always returns the same job.

    Completed entries are retained; no age-based eviction can restart a request.
    Identity is the original action payload (before generating a run/output).
    Host scene reset does not clear transport deduplication.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._jobs = {}

    def get_or_create(self, request_id: str, identity: Any, factory: Callable):
        with self._lock:
            if request_id in self._jobs:
                old_identity, job = self._jobs[request_id]
                if old_identity != identity:
                    return Refusal(RefusalKind.DUPLICATE_REQUEST, "request_id reused for another render")
                return job
            # Refuse a second job while actual termination/restoration is unknown.
            if any(job.result.state != OperationState.TERMINAL or
                   job.result.recovery in (RecoveryVerdict.UNKNOWN, RecoveryVerdict.RESIDUE)
                   for _, job in self._jobs.values()):
                return Refusal(RefusalKind.CONFLICT, "render or override recovery still active")
            job = factory()
            self._jobs[request_id] = (deepcopy(identity), job)
            return job
