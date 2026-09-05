"""Recipe proposal handler. Host dependencies are explicit and fail closed.

No lifecycle imports, scene handles, consent flags, or model-supplied code.
The registered tool only proposes approval-level effects. Trusted UI approval
and the bounded job's immediate start-time recheck are separate host paths.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import threading
from typing import Any, Mapping, Protocol

from synapse.recipes.authority import (
    ApprovalScope, MutationBudget, TypedBinding, action_for, effective_permission,
    typed_bindings, validate_request, validate_approval_scope, RUN_RECIPE_INPUT_SCHEMA,
)
from synapse.recipes.contracts import (
    ActionId, ActionSpec, PermissionCategory, RecipeSpec, Refusal, RefusalKind,
    RunRecipeRequest, max_permission,
)


class SpecLoader(Protocol):
    def __call__(self, recipe_id: str) -> RecipeSpec: ...


class ScopeProvider(Protocol):
    """Read-only, trusted host resolution of the exact render proposal scope."""
    def __call__(self, request: RunRecipeRequest, spec: RecipeSpec) -> ApprovalScope: ...


@dataclass(frozen=True)
class PreparedOperation:
    request: RunRecipeRequest
    spec: RecipeSpec
    action: ActionSpec
    permission: PermissionCategory
    bindings: tuple[TypedBinding, ...]


class Executor(Protocol):
    """LIFECYCLE adapter; execute rechecks revisions inside host ownership.

    The returned dictionary is the actual operation outcome/receipt, never a
    placeholder success. APPROVE and CRITICAL actions never reach this method
    through the model's proposal handler.
    """
    def wrapped_permission(self, action: ActionSpec) -> PermissionCategory: ...
    def execute(self, operation: PreparedOperation) -> dict: ...


_CONSENT_KEYS = frozenset({"approval", "approved", "approved_by", "approved_at",
                           "consent", "auto_approve", "binding", "skip_approval"})
_CAPABILITY_KEYS = _CONSENT_KEYS | {"code", "python", "vex", "node_path", "output_path", "output_root"}


def refusal_result(refusal: Refusal) -> dict:
    return {"status": "refused", "kind": refusal.kind.value,
            "reason": refusal.reason, "supported_alternative": refusal.supported_alternative}


def parse_request(payload: Mapping[str, Any]) -> RunRecipeRequest | Refusal:
    if not isinstance(payload, Mapping):
        return Refusal(RefusalKind.SLOT_INVALID, "recipe payload must be an object")
    if _CONSENT_KEYS.intersection(payload):
        return Refusal(RefusalKind.APPROVAL_REQUIRED, "the recipe wrapper cannot supply or self-authorize approval")
    fields = set(RunRecipeRequest.__dataclass_fields__)
    if set(payload) - fields:
        return Refusal(RefusalKind.SLOT_INVALID, "unsupported recipe payload fields")
    required = {"recipe_id", "action_id", "slots", "request_id"}
    if required - set(payload):
        return Refusal(RefusalKind.SLOT_INVALID, f"missing request fields: {sorted(required - set(payload))}")
    if isinstance(payload["slots"], Mapping) and _CAPABILITY_KEYS.intersection(payload["slots"]):
        return Refusal(RefusalKind.SLOT_INVALID, "consent, code, node paths and output destinations are host-selected capabilities")
    return RunRecipeRequest(payload["recipe_id"], payload["action_id"], payload.get("instance_id"),
                            deepcopy(payload["slots"]), payload.get("expected_revision"), payload["request_id"])


def _same_request(left: RunRecipeRequest, right: RunRecipeRequest) -> bool:
    """JSON identity includes types: true must never inherit the outcome of 1."""
    def same(a: Any, b: Any) -> bool:
        if type(a) is not type(b):
            return False
        if isinstance(a, Mapping):
            return set(a) == set(b) and all(same(a[key], b[key]) for key in a)
        if isinstance(a, (tuple, list)):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if type(a) is float and a != a and b != b:
            return True  # identical invalid NaN retries retain their refusal
        return a == b
    return all(same(getattr(left, key), getattr(right, key))
               for key in RunRecipeRequest.__dataclass_fields__)


class RecipeHandlerMixin:
    def configure_recipe_authority(self, *, spec_loader: SpecLoader | None = None,
                                   executor: Executor | None = None,
                                   scope_provider: ScopeProvider | None = None,
                                   mutation_budget: MutationBudget | None = None) -> None:
        """Configure once in the host, never from a tool payload.

        Dedup is session/process-local and deliberately unbounded for that
        session: evicting an old receipt would make an old retry mutate again.
        A host restart requires the lifecycle's durable job identity store.
        """
        if hasattr(self, "_recipe_lock"):
            raise RuntimeError("recipe authority is already configured")
        self._recipe_lock = threading.RLock()
        self._recipe_loader = spec_loader
        self._recipe_executor = executor
        self._recipe_scope_provider = scope_provider
        self._recipe_budget = mutation_budget
        self._recipe_outcomes: dict[str, tuple[RunRecipeRequest, dict]] = {}

    def begin_recipe_turn(self, budget: MutationBudget) -> None:
        """Trusted worker-turn boundary; never call on retries or each tool call."""
        with self._recipe_lock:
            if not isinstance(budget, MutationBudget):
                raise TypeError("the host must supply the turn's MutationBudget")
            self._recipe_budget = budget

    def _handle_run_recipe(self, payload: dict) -> dict:
        request = parse_request(payload)
        if isinstance(request, Refusal):
            return refusal_result(request)
        if not isinstance(request.request_id, str) or not request.request_id.strip():
            return refusal_result(Refusal(RefusalKind.SLOT_INVALID, "request_id must be a nonempty string"))
        if not hasattr(self, "_recipe_lock"):
            return {"status": "UNAVAILABLE", "reason": "recipe authority host dependencies are not configured"}
        with self._recipe_lock:
            previous = self._recipe_outcomes.get(request.request_id)
            if previous is not None:
                prior_request, outcome = previous
                if not _same_request(request, prior_request):
                    return refusal_result(Refusal(RefusalKind.DUPLICATE_REQUEST,
                                                  "request_id was already used for different content"))
                return deepcopy(outcome)
            # Hold the claim across execution so overlapping transport retries
            # cannot both dispatch. Exceptions are terminal UNKNOWN outcomes:
            # an effect may have happened before the exception/timeout.
            self._recipe_outcomes[request.request_id] = (
                request, {"status": "UNKNOWN", "reason": "request is in flight; do not retry its effects"})
            try:
                outcome = self._prepare_recipe(request)
            except Exception as exc:
                outcome = {"status": "UNKNOWN", "reason": f"recipe operation raised {type(exc).__name__}: {exc}; effects are unverified"}
            self._recipe_outcomes[request.request_id] = (request, deepcopy(outcome))
            return deepcopy(outcome)

    def _prepare_recipe(self, request: RunRecipeRequest) -> dict:
        loader = self._recipe_loader
        if loader is None:
            from synapse.blocks import fixtures
            loader = getattr(fixtures, "load_recipe_spec", None)
        if loader is None:
            return {"status": "UNAVAILABLE", "reason": "BLOCKS recipe spec loader is unavailable; inject SpecLoader"}
        try:
            spec = loader(request.recipe_id)
        except (ValueError, OSError) as exc:
            return {"status": "UNAVAILABLE", "reason": f"recipe specification unavailable: {exc}"}
        checked = validate_request(request, spec)
        if isinstance(checked, Refusal):
            return refusal_result(checked)
        if spec.golden_reference.get("status") == "PENDING_HUMAN":
            return {"status": "UNAVAILABLE", "reason": "golden scene qualification is PENDING_HUMAN"}
        action = action_for(checked, spec)
        # Even a mislabeled render wrapper retains the underlying render gate.
        floor = PermissionCategory.APPROVE if action.action_id == ActionId.RENDER else PermissionCategory.INFORM
        wrapped = self._recipe_executor.wrapped_permission(action) if self._recipe_executor else floor
        permission = effective_permission(action, max_permission(floor, wrapped))
        bindings = typed_bindings(checked, spec)
        if isinstance(bindings, Refusal):
            return refusal_result(bindings)
        operation = PreparedOperation(checked, spec, action, permission, bindings)
        if self._recipe_budget is None:
            return {"status": "UNAVAILABLE", "reason": "host turn MutationBudget is unavailable"}
        stop = self._recipe_budget.consume(action)
        if stop:
            return refusal_result(stop)
        if permission in (PermissionCategory.APPROVE, PermissionCategory.CRITICAL):
            binding = None
            reason = "trusted human approval is required; no effect has started"
            if self._recipe_scope_provider is not None:
                scope = self._recipe_scope_provider(checked, spec)
                if not isinstance(scope, ApprovalScope):
                    return {"status": "UNAVAILABLE", "reason": "trusted scope provider did not return ApprovalScope"}
                try:
                    scope = validate_approval_scope(scope)
                except (ValueError, TypeError):
                    return {"status": "UNAVAILABLE", "reason": "trusted scope provider returned an invalid render scope"}
                if scope.instance_id != checked.instance_id or scope.graph_revision != checked.expected_revision:
                    return refusal_result(Refusal(RefusalKind.STALE, "live instance/revision differs from request"))
                # This is a PROPOSED scope, never an ApprovalBinding. In
                # particular there is no invented approved_by/approved_at.
                binding = asdict(scope)
            else:
                reason += "; trusted scope provider is unavailable"
            return {"status": "awaiting_approval", "kind": RefusalKind.APPROVAL_REQUIRED.value,
                    "binding": binding, "permission": permission.value,
                    "request_id": checked.request_id, "reason": reason}
        if self._recipe_executor is None:
            return {"status": "UNAVAILABLE", "reason": "recipe lifecycle Executor is unavailable"}
        outcome = self._recipe_executor.execute(operation)
        if not isinstance(outcome, dict) or not outcome.get("status"):
            return {"status": "UNKNOWN", "reason": "executor returned no operation status; effects are unverified"}
        return outcome
