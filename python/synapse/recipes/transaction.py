"""Terminal build/edit transactions; recovery is a separate measured phase.

No render belongs here. A process-local ownership registry protects each
instance AND its stage/box (including two concurrent first builds). This is
not cross-process exclusion. The injected host backend applies an already
prepared BLOCKS operation set; this module is not another graph reconciler.

Undo evidence follows shared/bridge.py's before/after snapshots, with a
stricter unknown policy: no evidence, no mutation. The live driver is
``HoudiniUndoDriver`` below, bound to ``hou.undos`` — its four members
(``group`` / ``areEnabled`` / ``undoLabels`` / ``performUndo``) are
live-verified on H22.0.400 (CTO B2, 2026-09-05: ``undoLabels()`` returns
most-recent-first, headless ``areEnabled()`` is True, ``performUndo()`` pops
the latest item) and carried by the committed h22 symbol table. Merely
entering a context manager is not rollback evidence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import threading
from typing import Any, Callable, ContextManager, Mapping, Protocol, Sequence
from uuid import uuid4

from .contracts import (ActionId, CheckResult, RecipeInstance, RecoveryVerdict,
                        Refusal, RefusalKind, TerminalVerdict, verdict_from_checks)
from .instance import InstanceLifecycle, on_main


class BuildState(str, Enum):
    PREFLIGHT = "PREFLIGHT"
    OWNED = "OWNED"
    PRESTATE = "PRESTATE"
    MUTATING = "MUTATING"
    OBSERVED = "OBSERVED"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True)
class PreparedOperation:
    """An opaque trusted BLOCKS instruction, never arbitrary model Python.

    ``writes`` identifies exact keys in the backend's full authored snapshot.
    A created node can claim its entire record; field edits claim a leaf only.
    The backend preflight validates these against the captured fixture.
    """
    kind: str
    target: str
    value: Any = None
    field: str | None = None
    writes: tuple[tuple[str, ...], ...] = ()


class TransactionBackend(Protocol):
    """Every method executes on the host thread, including undo.

    snapshot must include relevant artist state outside the owned scope, and
    return detached deterministic authored data. foreign_epoch is a monotonic
    event counter for edits NOT caused by this transaction, or None if tracking
    is incomplete. Missing tracking forbids automatic global undo.
    """
    def preflight(self, operations: Sequence[PreparedOperation]) -> Refusal | None: ...
    def dependencies(self) -> Mapping[str, str]: ...
    def snapshot(self) -> Mapping[str, Any]: ...
    def foreign_epoch(self) -> int | None: ...
    def undo_enabled(self) -> bool | None: ...
    def undo_labels(self) -> tuple[str, ...] | None: ...
    def undo_group(self, label: str) -> ContextManager: ...
    def perform_undo(self) -> None: ...
    def apply(self, operation: PreparedOperation) -> None: ...
    def verify(self, action: ActionId, instance: RecipeInstance) -> Sequence[CheckResult]: ...


def _resolve_hou_undos():
    """The live ``hou.undos`` namespace, or None outside Houdini. Guarded import
    (CLAUDE.md §12): this module stays importable in stock python / CI."""
    try:
        import hou
    except ImportError:
        return None
    return getattr(hou, "undos", None)


class HoudiniUndoDriver:
    """The four ``TransactionBackend`` undo methods, bound to ``hou.undos``.

    A host backend composes this (``undo_enabled = driver.undo_enabled`` ...)
    or subclasses it; the graph methods stay the backend's own. Every method
    must run on the host main thread, like the rest of the backend.

    Evidence policy is unchanged from the docstring above: when ``hou.undos``
    cannot be resolved, ``undo_enabled`` / ``undo_labels`` answer **None**
    (unknown, never a faked True/False) and ``BuildTransaction`` refuses before
    any write ("UNAVAILABLE: verified undo group evidence required");
    ``undo_group`` / ``perform_undo`` raise rather than pretend. ``undos`` is
    injectable for tests; ``resolve`` is the lazy lookup used when it is not.
    """
    def __init__(self, undos: Any = None, resolve: Callable[[], Any] | None = None):
        self._undos = undos
        self._resolve = resolve or _resolve_hou_undos

    def _namespace(self):
        if self._undos is None:
            self._undos = self._resolve()
        return self._undos

    def undo_enabled(self) -> bool | None:
        ns = self._namespace()
        if ns is None:
            return None
        try:
            return bool(ns.areEnabled())
        except Exception:
            return None

    def undo_labels(self) -> tuple[str, ...] | None:
        # hou.undos.undoLabels() is most-recent-first (verified 22.0.400), so
        # labels[0] is the latest undo item -- the contract _execute_on_main and
        # _recover_on_main measure against.
        ns = self._namespace()
        if ns is None:
            return None
        try:
            return tuple(ns.undoLabels())
        except Exception:
            return None

    def undo_group(self, label: str) -> ContextManager:
        # hou.undos.group(label): grouping only -- one artist Ctrl+Z reverses the
        # whole block; it does NOT roll back when the block raises (CLAUDE.md §1).
        # Rollback here is _recover_on_main's single measured perform_undo.
        ns = self._namespace()
        if ns is None:
            raise RuntimeError("UNAVAILABLE: hou.undos is not importable in this process")
        return ns.group(label)

    def perform_undo(self) -> None:
        ns = self._namespace()
        if ns is None:
            raise RuntimeError("UNAVAILABLE: hou.undos is not importable in this process")
        ns.performUndo()


@dataclass
class BuildResult:
    run_id: str
    request_id: str
    outcome: str = "pending"
    verdict: TerminalVerdict = TerminalVerdict.UNKNOWN
    recovery: RecoveryVerdict = RecoveryVerdict.NOT_NEEDED
    reason: str = ""
    refusal: Refusal | None = None
    revision_before: int = 0
    revision_after: int | None = None
    fingerprint_before: str | None = None
    fingerprint_after: str | None = None
    applied_operations: int = 0
    undo_evidence: dict[str, Any] = field(default_factory=dict)
    residual_diff: list[dict[str, Any]] = field(default_factory=list)
    checks: tuple[CheckResult, ...] = ()


def state_diff(before: Mapping, after: Mapping, path=()) -> list[dict[str, Any]]:
    """Exact authored delta; absence and a value of None remain distinct."""
    changes = []
    for key in sorted(set(before) | set(after), key=str):
        current = path + (str(key),)
        if key in before and key in after:
            a, b = before[key], after[key]
            if isinstance(a, Mapping) and isinstance(b, Mapping):
                changes.extend(state_diff(a, b, current))
            elif a != b:
                changes.append({"path": current, "before": deepcopy(a), "after": deepcopy(b)})
        else:
            changes.append({"path": current, "before_present": key in before,
                            "after_present": key in after, "before": deepcopy(before.get(key)),
                            "after": deepcopy(after.get(key))})
    return changes


class Ownership:
    """Process-local; unsafe recovery quarantines keys until host remediation.

    Deliberately no timed lease: a slow main-thread call must not lose ownership.
    Clearing a quarantine requires a separately authorized host reset, not retry.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._owners = {}

    def acquire(self, keys, owner):
        with self._lock:
            if any(k in self._owners for k in keys):
                return False
            self._owners.update({k: owner for k in keys})
            return True

    def release(self, keys, owner):
        with self._lock:
            for key in keys:
                if self._owners.get(key) is owner:
                    del self._owners[key]


PROCESS_OWNERSHIP = Ownership()


class BuildTransaction:
    def __init__(self, *, request_id: str, instance: RecipeInstance,
                 lifecycle: InstanceLifecycle, backend: TransactionBackend,
                 operations: Sequence[PreparedOperation], expected_revision: int,
                 dependencies: Mapping[str, str], action: ActionId = ActionId.BUILD,
                 slots: Mapping[str, Any] | None = None, approved: bool = False,
                 dispatch: Callable = on_main, ownership: Ownership = PROCESS_OWNERSHIP):
        if not request_id:
            raise ValueError("request_id required")
        if action not in (ActionId.BUILD, ActionId.LIGHT, ActionId.MATERIAL):
            raise ValueError("a render is a job, never a build transaction")
        self.instance = deepcopy(instance)
        self.lifecycle, self.backend = lifecycle, backend
        self.operations = tuple(deepcopy(tuple(operations)))
        self.expected_revision = expected_revision
        self.dependencies = deepcopy(dict(dependencies))
        self.action, self.slots, self.approved = action, deepcopy(dict(slots or {})), approved
        self.dispatch, self.ownership = dispatch, ownership
        self.state = BuildState.PREFLIGHT
        self.history = [self.state]
        self.result = BuildResult(uuid4().hex, request_id, revision_before=expected_revision)
        self.label = "SYNAPSE recipe " + self.result.run_id
        self._keys = ("instance:" + instance.instance_id,
                      "scope:" + lifecycle.stage_path + ":" + lifecycle.box_name)
        self._guard = threading.Lock()
        self._terminal = threading.Event()
        self._cancel = threading.Event()
        self._started = self._entered = self._abandoned = False
        self._mutated = self._recovery_attempted = False
        self._owned = False
        self._before = self._after = None
        self._foreign = None
        self._instance_before = deepcopy(instance)
        self._metadata_saved = False

    def _state(self, value):
        self.state = value
        self.history.append(value)

    def _release(self):
        if self._owned:
            self.ownership.release(self._keys, self)
            self._owned = False

    def _refuse(self, refusal):
        self.result.refusal = refusal
        self.result.reason = refusal.reason
        self.result.outcome = "refused"
        self.result.verdict = TerminalVerdict.REFUSED

    def cancel(self):
        """Cooperative request only; never pretend an in-flight apply stopped."""
        self._cancel.set()

    def await_terminal(self, timeout: float | None = None) -> BuildResult | None:
        return self.result if self._terminal.wait(timeout) else None

    def execute(self) -> BuildResult:
        """A dispatcher timeout leaves the callback authoritative and reserved."""
        with self._guard:
            if self._started:
                return self.result
            self._started = True
        try:
            self.dispatch(self._execute_on_main)
        except Exception as exc:
            with self._guard:
                if not self._entered:
                    # Fence a callback that was queued but never actually entered.
                    self._abandoned = True
                    self.result.outcome = "failed"
                    self.result.reason = "dispatch unavailable: " + str(exc)
                    self._state(BuildState.TERMINAL)
                    self._terminal.set()
                else:
                    # It may STILL be mutating; do not set terminal or recover.
                    self.result.reason = "caller wait ended; await terminal: " + str(exc)
        return self.result

    def _validate_fields(self):
        if self.action == ActionId.BUILD:
            return
        if not self.approved:
            raise ValueError("approved LIGHT/MATERIAL action required")
        spec_action = next(a for a in self.lifecycle.spec.actions if a.action_id == self.action)
        bindings = {s.key: s.binding for s in spec_action.slots}
        if set(self.slots) - set(bindings) or len(self.operations) != len(self.slots):
            raise ValueError("prepared edits do not exactly cover declared slots")
        expected = []
        for key, value in self.slots.items():
            node_id, parm = bindings[key].rsplit(".", 1)
            expected.append((self.instance.owned_node_ids[node_id], parm, value))
        for op in self.operations:
            match = (op.target, op.field, op.value)
            if (op.kind != "set_parm" or match not in expected or op.writes != (
                    ("nodes", op.target, "parms", op.field),)):
                raise ValueError("prepared edit escapes the action field binding")
            expected.remove(match)

    def _execute_on_main(self):
        with self._guard:
            if self._abandoned or self._entered:
                return
            self._entered = True
        try:
            self._validate_fields()
            refusal = self.backend.preflight(self.operations)
            if refusal:
                self._refuse(refusal)
                return
            if not self.ownership.acquire(self._keys, self):
                self._refuse(Refusal(RefusalKind.CONFLICT, "instance busy or recovery unresolved"))
                return
            self._owned = True
            self._state(BuildState.OWNED)
            # Re-read under ownership, not from the preflight plan's cache.
            refusal = self.lifecycle.check_revision(self.instance, self.expected_revision)
            if refusal:
                self._refuse(refusal)
                return
            if dict(self.backend.dependencies()) != self.dependencies:
                self._refuse(Refusal(RefusalKind.STALE, "required dependencies changed"))
                return
            refusal = self.lifecycle.check_conflict(self.instance)
            if refusal:
                self._refuse(refusal)
                return
            self._before = deepcopy(dict(self.backend.snapshot()))
            self._foreign = self.backend.foreign_epoch()
            self._state(BuildState.PRESTATE)
            if self.instance.graph_revision:
                self.result.fingerprint_before = self.lifecycle.fingerprint(self.instance)
            if self._cancel.is_set():
                raise _Cancelled("cancelled before mutation")
            if self.action == ActionId.BUILD and self.instance.graph_revision:
                # Observe twice. Never replay operations/defaults on existing BUILD.
                self.result.fingerprint_after = self.lifecycle.fingerprint(self.instance)
                self._after = deepcopy(dict(self.backend.snapshot()))
                if (self.result.fingerprint_before != self.result.fingerprint_after or
                        state_diff(self._before, self._after)):
                    self._refuse(Refusal(RefusalKind.CONFLICT, "state changed during no-op observation"))
                    return
                self._state(BuildState.OBSERVED)
                self._verify()
                if self._cancel.is_set():
                    raise _Cancelled("cancelled during verification")
                if self._foreign is None or self.backend.foreign_epoch() != self._foreign:
                    raise RuntimeError("unrelated edit tracking unavailable or changed")
                self.result.outcome = "noop"
                self.result.revision_after = self.instance.graph_revision
                return
            enabled, labels = self.backend.undo_enabled(), self.backend.undo_labels()
            self.result.undo_evidence.update(enabled=enabled, labels_before=labels)
            if enabled is not True or labels is None:
                raise RuntimeError("UNAVAILABLE: verified undo group evidence required")
            if self._foreign is None:
                raise RuntimeError("UNAVAILABLE: unrelated edit tracking required before mutation")
            with self.backend.undo_group(self.label):
                self._state(BuildState.MUTATING)
                for operation in self.operations:
                    if self._cancel.is_set():
                        raise _Cancelled("cancelled during mutation")
                    self._mutated = True  # apply may partially mutate and then raise
                    self.backend.apply(deepcopy(operation))
                    self.result.applied_operations += 1
                if self._cancel.is_set():
                    raise _Cancelled("cancelled after mutation")
                self._after = deepcopy(dict(self.backend.snapshot()))
                allowed = tuple(p for op in self.operations for p in op.writes)
                delta = state_diff(self._before, self._after)
                if any(not any(tuple(d["path"][:len(p)]) == p for p in allowed) for d in delta):
                    raise RuntimeError("mutation escaped prepared operation scope")
                self.result.fingerprint_after = self.lifecycle.fingerprint(self.instance)
                self._state(BuildState.OBSERVED)
                self._verify()
                if self._cancel.is_set():
                    raise _Cancelled("cancelled during verification")
                if self._foreign is None or self.backend.foreign_epoch() != self._foreign:
                    raise RuntimeError("unrelated edit tracking unavailable or changed")
                # Metadata is part of the SAME undo item for persistent stores.
                committed = self.lifecycle.commit(self.instance, action=self.action, slots=self.slots,
                                                   approved=self.approved,
                                                   expected_revision=self.expected_revision)
                self._metadata_saved = True
            labels_after = self.backend.undo_labels()
            self.result.undo_evidence["labels_after"] = labels_after
            if not labels_after or labels_after[0] != self.label:
                raise RuntimeError("transaction is not the measured latest undo item")
            if self._foreign is None or self.backend.foreign_epoch() != self._foreign:
                raise RuntimeError("unrelated edit tracking unavailable or changed")
            self.result.revision_after = committed.graph_revision
            self.result.outcome = "committed"
        except Exception as exc:
            self.result.outcome = "cancelled" if isinstance(exc, _Cancelled) else "failed"
            if isinstance(exc, _Cancelled):
                self.result.verdict = TerminalVerdict.CANCELLED
            elif not self.result.checks or self.result.verdict != TerminalVerdict.UNKNOWN:
                self.result.verdict = TerminalVerdict.BROKEN
            self.result.reason = str(exc)
            if self._mutated:
                self.result.recovery = RecoveryVerdict.UNKNOWN
                try:
                    self._after = deepcopy(dict(self.backend.snapshot()))
                    self.result.residual_diff = state_diff(self._before, self._after)
                except Exception as observation_error:
                    self._after = None
                    self.result.reason += "; residual unobservable: " + str(observation_error)
        finally:
            self._state(BuildState.TERMINAL)
            if not self._mutated or self.result.outcome == "committed":
                self._release()
            # Last action: the undo group and all mutation callbacks have exited.
            self._terminal.set()

    def _verify(self):
        self.result.checks = tuple(self.backend.verify(self.action, self.instance))
        verdict = verdict_from_checks(self.action, self.result.checks)
        self.result.verdict = verdict
        if verdict != TerminalVerdict.VERIFIED:
            raise RuntimeError("required graph/USD/locality checks did not all pass: " + verdict.value)

    def recover(self) -> RecoveryVerdict:
        if not self._terminal.is_set() or self.state != BuildState.TERMINAL:
            raise RuntimeError("recovery refused: await_terminal before rollback")
        if not self._mutated or self.result.outcome == "committed":
            return self.result.recovery
        with self._guard:
            if self._recovery_attempted:
                return self.result.recovery
            self._recovery_attempted = True  # dispatch timeout never permits a retry
        try:
            self.dispatch(self._recover_on_main)
        except Exception as exc:
            self.result.reason += "; recovery wait ended: " + str(exc)
        return self.result.recovery

    def _recover_on_main(self):
        try:
            current = deepcopy(dict(self.backend.snapshot()))
            self.result.residual_diff = state_diff(self._before, current)
            if not self.result.residual_diff:
                if self._metadata_saved:
                    self.lifecycle.restore_metadata_after_undo(self._instance_before)
                    self.instance = deepcopy(self._instance_before)
                self.result.recovery = RecoveryVerdict.RESTORED
                self._release()
                return
            labels = self.backend.undo_labels()
            epoch = self.backend.foreign_epoch()
            safe = (self._after is not None and current == self._after and
                    self._foreign is not None and epoch == self._foreign and
                    bool(labels) and labels[0] == self.label and
                    self.backend.undo_enabled() is True)
            if not safe:
                self.result.recovery = RecoveryVerdict.RESIDUE
                return  # no writes, retain quarantine
            self.backend.perform_undo()  # exactly once; only our proven latest item
            if self._metadata_saved:
                self.lifecycle.restore_metadata_after_undo(self._instance_before)
                self.instance = deepcopy(self._instance_before)
            restored = deepcopy(dict(self.backend.snapshot()))
            self.result.residual_diff = state_diff(self._before, restored)
            self.result.recovery = (RecoveryVerdict.RESIDUE if self.result.residual_diff
                                    else RecoveryVerdict.RESTORED)
            if self.result.recovery == RecoveryVerdict.RESTORED:
                self._release()
        except Exception as exc:
            self.result.recovery = RecoveryVerdict.UNKNOWN
            self.result.reason += "; recovery evidence unavailable: " + str(exc)


class _Cancelled(RuntimeError):
    pass


class TransactionRegistry:
    """Transport idempotency retained through scene resets, for this process.

    A reset + NEW request creates a new transaction. The SAME request always
    returns its existing run, even after reset; changing its payload refuses.
    Persist this registry externally for retries across host process restarts.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._runs = {}

    def get_or_create(self, request_id: str, identity: Any, factory: Callable):
        with self._lock:
            if request_id in self._runs:
                prior, transaction = self._runs[request_id]
                if prior != identity:
                    return Refusal(RefusalKind.DUPLICATE_REQUEST, "request_id reused for another payload")
                return transaction
            transaction = factory()
            self._runs[request_id] = (deepcopy(identity), transaction)
            return transaction
