"""Pure authorization for curated recipes. No scene API or executable strings.

Approval constructors are for trusted host code, never tool payloads. A binding
describes consent; its strings alone do not authenticate the human who gave it.
The host must obtain it through its existing confirmation path and recheck it
inside the exclusive mutation window immediately before starting the effect.
"""
from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    ActionId, ActionSpec, ApprovalBinding, PermissionCategory, RecipeSpec,
    Refusal, RefusalKind, RunRecipeRequest, SlotSchema, max_permission, RECIPE_ID,
)


RUN_RECIPE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "recipe_id": {"type": "string", "enum": [RECIPE_ID]},
        "action_id": {"type": "string", "enum": [a.value for a in ActionId]},
        "instance_id": {"type": ["string", "null"]},
        "slots": {"type": "object"},
        "expected_revision": {"type": ["integer", "null"], "minimum": 0},
        "request_id": {"type": "string", "minLength": 1},
    },
    "required": ["recipe_id", "action_id", "slots", "request_id"],
    "additionalProperties": False,
}


def _invalid(reason: str) -> Refusal:
    return Refusal(RefusalKind.SLOT_INVALID, reason)


def _finite(value: Any) -> bool:
    if type(value) not in (int, float):  # bool is not an integer slot
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def action_for(req: RunRecipeRequest, spec: RecipeSpec) -> ActionSpec | Refusal:
    if req.recipe_id != spec.recipe_id:
        return Refusal(RefusalKind.UNKNOWN_ACTION, "recipe_id does not match the loaded specification")
    matches = [a for a in spec.actions if a.action_id == req.action_id]
    if len(matches) > 1:
        return Refusal(RefusalKind.AMBIGUOUS, "multiple definitions for the requested action")
    if not matches or req.action_id not in {a.value for a in ActionId}:
        return Refusal(RefusalKind.UNKNOWN_ACTION, f"unsupported action: {req.action_id!r}")
    return matches[0]


def validate_slot(value: Any, slot: SlotSchema) -> Any | Refusal:
    """Validate a value without evaluating, interpolating, or coercing text."""
    if slot.type not in {"float", "int", "color3", "enum", "str"}:
        return _invalid(f"{slot.key}: unsupported schema type {slot.type!r}")
    for bound in (slot.min, slot.max):
        if bound is not None and not _finite(bound):
            return _invalid(f"{slot.key}: schema bound must be finite")
    if slot.min is not None and slot.max is not None and slot.min > slot.max:
        return _invalid(f"{slot.key}: inverted schema bounds")
    if not isinstance(slot.enum, (tuple, list)) or any(type(v) is not str for v in slot.enum):
        return _invalid(f"{slot.key}: invalid schema enum")
    if slot.type == "color3":
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            return _invalid(f"{slot.key}: expected three finite color components")
        values = tuple(value)
    elif slot.type in {"float", "int"}:
        if slot.type == "int" and type(value) is not int:
            return _invalid(f"{slot.key}: expected int (not bool or float)")
        values = (value,)
    else:
        if type(value) is not str:
            return _invalid(f"{slot.key}: expected string")
        if slot.min is not None or slot.max is not None:
            return _invalid(f"{slot.key}: numeric bounds on a string schema")
        if slot.type == "enum" and not slot.enum:
            return _invalid(f"{slot.key}: empty enum")
        if slot.enum and value not in slot.enum:
            return _invalid(f"{slot.key}: {value!r} is outside enum {slot.enum!r}")
        return value
    if slot.enum:
        return _invalid(f"{slot.key}: string enum on a numeric schema")
    for component in values:
        if not _finite(component):
            return _invalid(f"{slot.key}: expected finite numeric value")
        if slot.min is not None and component < slot.min:
            return _invalid(f"{slot.key}: value below minimum {slot.min}")
        if slot.max is not None and component > slot.max:
            return _invalid(f"{slot.key}: value above maximum {slot.max}")
    if slot.type == "color3":
        return tuple(float(v) for v in values)
    return float(value) if slot.type == "float" else value


def validate_request(req: RunRecipeRequest, spec: RecipeSpec) -> RunRecipeRequest | Refusal:
    """All declared slots are required: the frozen seam has no slot defaults."""
    if not isinstance(req, RunRecipeRequest) or not isinstance(spec, RecipeSpec):
        return _invalid("expected RunRecipeRequest and RecipeSpec")
    for key in ("recipe_id", "action_id", "request_id"):
        value = getattr(req, key)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            return _invalid(f"{key}: expected nonempty identifier without surrounding whitespace")
    action = action_for(req, spec)
    if isinstance(action, Refusal):
        return action
    if req.instance_id is not None and (
        not isinstance(req.instance_id, str) or not req.instance_id.strip()
        or req.instance_id != req.instance_id.strip()
    ):
        return _invalid("instance_id: expected nonempty string or null")
    if req.expected_revision is not None and (
        type(req.expected_revision) is not int or req.expected_revision < 0
    ):
        return _invalid("expected_revision: expected nonnegative int or null")
    if req.instance_id is None and req.expected_revision is not None:
        return _invalid("expected_revision requires instance_id")
    if req.instance_id is not None and req.expected_revision is None:
        return Refusal(RefusalKind.STALE, "an existing instance requires expected_revision")
    if action.action_id != ActionId.BUILD and req.instance_id is None:
        return _invalid("edit/render requires an instance_id and expected_revision")
    if not isinstance(req.slots, Mapping) or any(type(k) is not str for k in req.slots):
        return _invalid("slots must be a mapping with string keys")
    schemas = {slot.key: slot for slot in action.slots}
    if len(schemas) != len(action.slots):
        return _invalid("duplicate slot schema keys")
    extra, missing = set(req.slots) - set(schemas), set(schemas) - set(req.slots)
    if extra or missing:
        return _invalid(f"slot keys differ: unsupported={sorted(extra)!r}, missing={sorted(missing)!r}")
    slots = {}
    targets = set()
    node_ids = {node.get("id") for node in spec.nodes}
    for key, schema in schemas.items():
        # Targets come exclusively from the curated schema. A binding is a
        # node-id + parameter identifier, not an expression or a node path.
        if not isinstance(schema.binding, str) or "." not in schema.binding:
            return _invalid(f"{key}: binding must be <node_id>.<parm_name>")
        node_id, parm = schema.binding.rsplit(".", 1)
        if node_id not in node_ids or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", parm):
            return _invalid(f"{key}: unresolved or nonliteral binding")
        if schema.binding in targets:
            return _invalid(f"{key}: multiple slots target the same field")
        targets.add(schema.binding)
        value = validate_slot(req.slots[key], schema)
        if isinstance(value, Refusal):
            return value
        slots[key] = value
    return replace(req, slots=MappingProxyType(slots))


@dataclass(frozen=True)
class TypedBinding:
    node_id: str
    parm_name: str
    value: Any


def typed_bindings(req: RunRecipeRequest, spec: RecipeSpec) -> tuple[TypedBinding, ...] | Refusal:
    checked = validate_request(req, spec)
    if isinstance(checked, Refusal):
        return checked
    action = action_for(checked, spec)
    return tuple(TypedBinding(*slot.binding.rsplit(".", 1), checked.slots[slot.key])
                 for slot in action.slots)


def effective_permission(action: ActionSpec, wrapped_gate: PermissionCategory) -> PermissionCategory:
    return max_permission(action.permission, wrapped_gate)


@dataclass(frozen=True)
class ApprovalScope:
    """Trusted host observation, including its resolved output destination."""
    instance_id: str
    graph_revision: int
    engine: str
    resolution: tuple[int, int]
    samples: int
    output_path: str


_SCOPE_FIELDS = tuple(ApprovalScope.__dataclass_fields__)


def _scope_values(scope: ApprovalScope | ApprovalBinding | Mapping[str, Any]) -> dict:
    values = {key: scope[key] if isinstance(scope, Mapping) else getattr(scope, key)
              for key in _SCOPE_FIELDS}
    for key in ("instance_id", "engine", "output_path"):
        if type(values[key]) is not str or not values[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    for key, lower in (("graph_revision", 0), ("samples", 1)):
        if type(values[key]) is not int or values[key] < lower:
            raise ValueError(f"{key} must be an integer >= {lower}")
    resolution = values["resolution"]
    if (not isinstance(resolution, (list, tuple)) or len(resolution) != 2
            or any(type(v) is not int or v < 1 for v in resolution)):
        raise ValueError("resolution must contain two positive integers")
    values["resolution"] = tuple(resolution)  # JSON arrays and seam tuples agree
    return values


def validate_approval_scope(scope: ApprovalScope | Mapping[str, Any]) -> ApprovalScope:
    """Validate a proposal without granting it any approval provenance."""
    return ApprovalScope(**_scope_values(scope))


def bind_approval(scope: ApprovalScope | Mapping[str, Any], *, approved_by: str,
                  approved_at: str | None = None) -> ApprovalBinding:
    """Called ONLY after trusted human confirmation, never from model input."""
    if type(approved_by) is not str or not approved_by.strip():
        raise ValueError("trusted approval provenance is required")
    stamp = approved_at or datetime.now(timezone.utc).isoformat()
    parsed = datetime.fromisoformat(stamp)
    if parsed.tzinfo is None:
        raise ValueError("approval timestamp must include a timezone")
    return ApprovalBinding(**_scope_values(scope), approved_by=approved_by, approved_at=stamp)


def recheck_approval(binding: ApprovalBinding, live_scope: ApprovalScope | Mapping[str, Any]) -> bool:
    """Exact scope equality. No rounding, path normalization or revision coercion."""
    if not isinstance(binding, ApprovalBinding):
        return False
    try:
        if not isinstance(binding.approved_by, str) or not binding.approved_by.strip():
            return False
        if datetime.fromisoformat(binding.approved_at).tzinfo is None:
            return False
        return _scope_values(binding) == _scope_values(live_scope)
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
        return False


def require_approval(binding: ApprovalBinding | None,
                     live_scope: ApprovalScope | Mapping[str, Any]) -> Refusal | None:
    """Start-time guard for the injected bounded render job/host executor."""
    if binding is None:
        return Refusal(RefusalKind.APPROVAL_REQUIRED, "render requires trusted approval before start")
    if not recheck_approval(binding, live_scope):
        return Refusal(RefusalKind.APPROVAL_MISMATCH, "approved scope no longer matches live scope")
    return None


def is_terminal(action: ActionSpec | ActionId | str) -> bool:
    """All four baseline actions finish a turn's mutation authority."""
    action_id = action.action_id if isinstance(action, ActionSpec) else action
    return action_id in tuple(ActionId)


class MutationBudget:
    """One host-owned turn; never reset this object on a tool retry.

    Reserve BEFORE dispatch. A failed/uncertain terminal call still ends the
    turn; it cannot justify a follow-on repair. Reads do not spend authority.
    """
    def __init__(self) -> None:
        self._terminal = False
        self._lock = threading.Lock()

    def consume(self, action: ActionSpec | ActionId | str | None = None, *,
                mutating: bool = True) -> Refusal | None:
        with self._lock:
            if not mutating:
                return None
            if self._terminal:
                return Refusal(RefusalKind.CONFLICT, "terminal action ended mutation for this turn; a new turn is required")
            if action is not None and not is_terminal(action):
                return Refusal(RefusalKind.UNKNOWN_ACTION, "unknown action cannot spend mutation authority")
            if action is not None:
                self._terminal = True
            return None
