"""Registry offers, observed cards, compiled-spec cache and transport dedup.

No card method certifies a run or grants consent. Host wiring supplies current
scope, a receipt and tracker evidence. A new request must re-observe the scene.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
import threading
from typing import Any, Callable, Mapping

from .contracts import (
    ActionId, ActionSpec, ApprovalBinding, Availability, CheckId, CheckResult,
    CheckStatus, EvidenceFreshness, OperationState, PermissionCategory,
    RecipeInstance, RecipeSpec, RecoveryVerdict, RunReceipt, RunRecipeRequest,
    SlotSchema, TerminalVerdict,
)
from .receipt import _encode, freeze, from_dict, timestamp, to_dict


@dataclass(frozen=True)
class ApprovalScope:
    instance_id: str
    graph_revision: int
    engine: str
    resolution: tuple[int, int]
    samples: int
    output_path: str

    def matches(self, binding: ApprovalBinding | None) -> bool:
        if binding is None or not binding.approved_by.strip():
            return False
        try:
            timestamp(binding.approved_at)
        except (ValueError, AttributeError, TypeError):
            return False
        return all(getattr(self, field.name) == getattr(binding, field.name) for field in fields(self))


@dataclass(frozen=True)
class RecipeCard:
    recipe_id: str
    recipe_version: str
    action_id: ActionId
    scope: str
    availability: Availability
    operation_state: OperationState
    verdict: TerminalVerdict | None
    freshness: EvidenceFreshness
    checks: tuple[CheckResult, ...]
    approval: ApprovalBinding | None
    approval_required: bool
    recovery: RecoveryVerdict
    reason: str
    next_action: str
    run_id: str | None = None

    def __post_init__(self):
        for name in ("reason", "next_action"):
            value = getattr(self, name)
            if not value.strip() or "\n" in value or "\r" in value:
                raise ValueError(f"card {name} must be one nonempty line")


def make_card(spec: RecipeSpec, action_id: ActionId, *, availability: Availability,
              scope: str, instance: RecipeInstance | None = None,
              receipt: RunReceipt | None = None,
              freshness: EvidenceFreshness = EvidenceFreshness.UNKNOWN,
              operation_state: OperationState | None = None,
              approval_scope: ApprovalScope | None = None,
              approval: ApprovalBinding | None = None,
              availability_reason: str = "", next_action: str | None = None) -> RecipeCard:
    """Project one registry offer, including blocked offers, without new checks.

    A receipt is historical evidence. ``approval_required`` describes the NEXT
    action; it never starts or cancels an existing job. The authority adapter
    must repeat the scope comparison immediately before executing.
    """
    action = next((item for item in spec.actions if item.action_id == action_id), None)
    if action is None:
        raise ValueError("action is not a registry offer")
    if availability == Availability.BLOCKED and not availability_reason.strip():
        raise ValueError("blocked offer requires availability_reason")
    if receipt is not None:
        # A card cannot accidentally display another scene/recipe's green receipt.
        if (receipt.recipe_id != spec.recipe_id or receipt.recipe_version != spec.version
                or receipt.action_id != action_id or instance is None
                or receipt.instance_id != instance.instance_id):
            raise ValueError("receipt does not belong to this card")
        receipt = from_dict(to_dict(receipt))
        if receipt.revision_after is not None and receipt.revision_after != instance.graph_revision:
            freshness = EvidenceFreshness.STALE
    else:
        freshness = EvidenceFreshness.UNKNOWN
    state = operation_state or (receipt.operation_state if receipt else OperationState.PENDING)
    binding = approval if approval is not None else (receipt.approval if receipt else None)
    requires_gate = action_id == ActionId.RENDER or action.permission in (
        PermissionCategory.APPROVE, PermissionCategory.CRITICAL)
    scope_is_live = (instance is not None and approval_scope is not None
                     and approval_scope.instance_id == instance.instance_id
                     and approval_scope.graph_revision == instance.graph_revision)
    needs_approval = requires_gate and not (scope_is_live and approval_scope.matches(binding))
    if needs_approval and state != OperationState.RUNNING:
        state = OperationState.AWAITING_APPROVAL
    observed = {item.check: item for item in receipt.checks} if receipt else {}
    checks = tuple(observed.get(cid, CheckResult(cid, CheckStatus.NOT_RUN, "No run evidence"))
                   for cid in CheckId)
    reason, following = "No run evidence", "Run the supported action"
    if receipt:
        reason = receipt.reason or "Required checks passed in this recorded run"
        following = "Review the recorded evidence"
    if freshness == EvidenceFreshness.STALE:
        reason, following = "Scene changed since this receipt", "Re-observe the current scope"
    elif freshness == EvidenceFreshness.UNKNOWN and receipt:
        reason, following = "Current scene evidence is unmeasured or tracking is incomplete", "Re-observe with complete change tracking"
    if needs_approval:
        reason, following = "Approval is required for the current scope", "Review and approve the current scope"
    if receipt and receipt.recovery in (RecoveryVerdict.RESIDUE, RecoveryVerdict.UNKNOWN):
        reason, following = "Recovery left residue or could not be verified", "Inspect recovery before another write"
    if availability == Availability.BLOCKED:
        reason, following = availability_reason, "Resolve the recipe availability reason"
    return RecipeCard(spec.recipe_id, spec.version, action_id, scope, availability,
                      state, receipt.verdict if receipt else None, freshness, checks,
                      binding, needs_approval, receipt.recovery if receipt else RecoveryVerdict.UNKNOWN,
                      reason, next_action or following, receipt.run_id if receipt else None)


_OUTCOME_KEYS = frozenset({"verdict", "terminal_verdict", "operation_state", "freshness",
                          "receipt", "run_receipt", "checks", "render_job"})


def _spec_data(value: Any) -> Any:
    """Whitelist declarative types; deny even nested run results/outcomes."""
    if isinstance(value, Enum):
        if type(value) not in (ActionId, CheckId, PermissionCategory):
            raise ValueError("live verdicts and state do not belong in the spec cache")
        return value.value
    if is_dataclass(value):
        if type(value) not in (RecipeSpec, ActionSpec, SlotSchema):
            raise ValueError("only compiled declarative specs may be cached")
        return {field.name: _spec_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        if any(key in _OUTCOME_KEYS for key in value):
            raise ValueError("outcome field in compiled spec")
        return {key: _spec_data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_spec_data(item) for item in value]
    if isinstance(value, str) and value in {item.value for item in TerminalVerdict}:
        raise ValueError("serialized verdict in compiled spec")
    return _encode(value)


def spec_digest(spec: RecipeSpec) -> str:
    """All compiled specification fields participate, including build and layout."""
    if type(spec) is not RecipeSpec:
        raise TypeError("SpecCache accepts RecipeSpec only")
    return hashlib.sha256(json.dumps(_spec_data(spec), sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class SpecCache:
    """Digest-keyed compiled RecipeSpec snapshots only. No response cache."""

    def __init__(self):
        self._specs: dict[str, RecipeSpec] = {}
        self._lock = threading.RLock()

    def put(self, digest: str, spec: RecipeSpec) -> None:
        if digest != spec_digest(spec):
            raise ValueError("compiled spec digest mismatch")
        # Freeze only data fields; actions/slots are frozen seam dataclasses.
        detached = replace(spec, golden_reference=freeze(spec.golden_reference),
                           nodes=freeze(spec.nodes), connections=freeze(spec.connections),
                           presentation=freeze(spec.presentation))
        with self._lock:
            self._specs[digest] = detached

    def get(self, digest: str) -> RecipeSpec | None:
        with self._lock:
            return self._specs.get(digest)


@dataclass(frozen=True)
class RequestJob:
    request_id: str
    request_digest: str
    operation_state: OperationState
    job_id: str | None = None
    receipt: RunReceipt | None = None


@dataclass(frozen=True)
class DedupDecision:
    should_execute: bool
    job: RequestJob


class RequestDedup:
    """One host-owned request/job registry, retained for the scene session.

    Claim atomically BEFORE any effect. Retry returns the same pending/running/
    terminal job, never a fresh permit. No timeout/eviction grants a new permit.
    This is transport dedup within one host lifetime, not crash recovery: wire a
    durable job journal before promising dedup across host restarts. Do not make
    a new registry per request, panel refresh, undo, or scene reset.
    """

    def __init__(self):
        self._jobs: dict[str, RequestJob] = {}
        self._requests: dict[str, RunRecipeRequest] = {}
        self._lock = threading.RLock()

    def claim(self, request: RunRecipeRequest) -> DedupDecision:
        if not request.request_id.strip():
            raise ValueError("request_id is required")
        payload = {field.name: _encode(getattr(request, field.name)) for field in fields(request)}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        with self._lock:
            job = self._jobs.get(request.request_id)
            if job is not None:
                if job.request_digest != digest:
                    raise ValueError("request_id reused for a different request")
                return DedupDecision(False, job)
            job = RequestJob(request.request_id, digest, OperationState.PENDING)
            self._jobs[request.request_id] = job
            self._requests[request.request_id] = replace(request, slots=freeze(request.slots))
            return DedupDecision(True, job)

    def get(self, request_id: str) -> RequestJob | None:
        with self._lock:
            return self._jobs.get(request_id)

    def transition(self, request_id: str, state: OperationState, *, job_id: str | None = None,
                   receipt: RunReceipt | None = None) -> RequestJob:
        if not isinstance(state, OperationState):
            raise ValueError("state must be an OperationState")
        allowed = {
            OperationState.PENDING: {OperationState.AWAITING_APPROVAL, OperationState.RUNNING, OperationState.TERMINAL},
            OperationState.AWAITING_APPROVAL: {OperationState.RUNNING, OperationState.TERMINAL},
            OperationState.RUNNING: {OperationState.TERMINAL},
            OperationState.TERMINAL: set(),
        }
        with self._lock:
            previous = self._jobs[request_id]
            if state not in allowed[previous.operation_state]:
                raise ValueError("invalid job state transition")
            if previous.job_id is not None and job_id not in (None, previous.job_id):
                raise ValueError("request already belongs to another job")
            if state == OperationState.TERMINAL:
                if receipt is None or receipt.request_id != request_id or receipt.operation_state != state:
                    raise ValueError("terminal job requires its terminal receipt")
                request = self._requests[request_id]
                if (receipt.recipe_id != request.recipe_id or receipt.action_id.value != request.action_id
                        or (request.instance_id is not None and receipt.instance_id != request.instance_id)):
                    raise ValueError("terminal receipt does not describe the claimed request")
                expected_job = job_id or previous.job_id
                recorded_job = receipt.render_job.get("job_id")
                if expected_job is not None and (
                        (recorded_job is not None and recorded_job != expected_job)
                        or (request.action_id == ActionId.RENDER.value and recorded_job is None)):
                    raise ValueError("terminal receipt does not identify the tracked render job")
                receipt = from_dict(to_dict(receipt))
            elif receipt is not None:
                raise ValueError("only terminal jobs accept receipts")
            job = replace(previous, operation_state=state, job_id=job_id or previous.job_id, receipt=receipt)
            self._jobs[request_id] = job
            return job

    def execute_once(self, request: RunRecipeRequest, effect: Callable[[], RunReceipt]) -> RequestJob:
        """Convenience for synchronous effects; async jobs use claim/transition.

        An exception leaves RUNNING: an uncertain task must be reconciled by
        the host, never automatically retried after a UI timeout.
        """
        decision = self.claim(request)
        if not decision.should_execute:
            return decision.job
        self.transition(request.request_id, OperationState.RUNNING)
        receipt = effect()
        return self.transition(request.request_id, OperationState.TERMINAL, receipt=receipt)
