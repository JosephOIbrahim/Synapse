"""The transfer boundary: what survives a change of model or of task domain.

Continual self-improvement carries edits across settings, and not all edits
travel. An edit written around one model's failure mode can handicap the next
model; a heuristic fitted to one task domain can invert on another. The edits
that survive are the structural ones — termination checks, deliverable
verification, registration audits — because they encode a property of the task,
not a quirk of the setting.

This module plans the crossing. It does not perform it: it reads the ledger,
classifies every retained edit, and returns a work list. Re-validation runs
against the target setting are a separate, approved act.

Default policy, from the architecture:

* ``MODEL_SPECIFIC_REPAIR`` is provisional when the model changes.
* ``DOMAIN_HEURISTIC`` is provisional when the evaluation split changes.
* ``INVARIANT_GATE`` is an anchor: kept, with its evaluator binding re-verified.
* ``CONTEXT_ORCHESTRATION`` is carried. It is tuned to the setting in principle,
  so ``TransferPolicy.flag_context_on`` can widen the rule; the default leaves it
  alone rather than flagging everything and meaning nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .schema import RETAINED_VERDICTS, AttemptRecord, EditScope
from .setting import SettingFingerprint
from .store import SIMStore


class Disposition(str, Enum):
    """What happens to one inherited edit at the boundary."""

    ANCHOR = "ANCHOR"
    CARRIED = "CARRIED"
    PROVISIONAL_REVALIDATE = "PROVISIONAL_REVALIDATE"


@dataclass(frozen=True)
class TransferPolicy:
    """Which scopes are provisional under which change.

    Defaults are the architecture's: repairs follow the model, heuristics follow
    the split. Set ``flag_context_on`` to ``{"model", "split"}`` to widen it.
    """

    flag_context_on: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        unknown = set(self.flag_context_on) - {"model", "split"}
        if unknown:
            raise ValueError(f"flag_context_on accepts model/split, not {sorted(unknown)}")


DEFAULT_POLICY = TransferPolicy()


@dataclass(frozen=True)
class TransferItem:
    attempt_id: str
    target_artifact: str
    edit_scope: EditScope
    disposition: Disposition
    reason: str
    binding_review: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "target_artifact": self.target_artifact,
            "edit_scope": self.edit_scope.value,
            "disposition": self.disposition.value,
            "reason": self.reason,
            "binding_review": self.binding_review,
        }


@dataclass(frozen=True)
class TransferPlan:
    """The work list for one setting change."""

    from_setting: SettingFingerprint
    to_setting: SettingFingerprint
    transition: dict[str, bool]
    items: tuple[TransferItem, ...]
    superseded: tuple[str, ...] = ()

    @property
    def is_transition(self) -> bool:
        return any(self.transition.values())

    @property
    def requires_revalidation(self) -> bool:
        return any(item.disposition is Disposition.PROVISIONAL_REVALIDATE for item in self.items)

    def counts(self) -> dict[str, int]:
        counts = {disposition.value: 0 for disposition in Disposition}
        for item in self.items:
            counts[item.disposition.value] += 1
        return counts

    def as_dict(self) -> dict[str, Any]:
        return {
            "from": self.from_setting.to_dict(),
            "to": self.to_setting.to_dict(),
            "transition": dict(self.transition),
            "is_transition": self.is_transition,
            "requires_revalidation": self.requires_revalidation,
            "counts": self.counts(),
            "superseded": list(self.superseded),
            "items": [item.as_dict() for item in self.items],
        }


class TransferBoundaryController:
    """Classify retained edits when the setting changes. Reads the ledger only."""

    def __init__(self, store: SIMStore, policy: TransferPolicy = DEFAULT_POLICY) -> None:
        self.store = store
        self.policy = policy

    def retained_edits(self) -> list[AttemptRecord]:
        """The active edits: retained or replacing, newest per target artifact.

        Two retained edits on one artifact mean the later one is the state of the
        world; the earlier is returned separately as superseded rather than
        silently dropped.
        """
        latest: dict[str, AttemptRecord] = {}
        for record in self.store.iter_attempts():
            if record.selector_verdict not in RETAINED_VERDICTS:
                continue
            current = latest.get(record.target_artifact)
            if current is None or record.created_utc >= current.created_utc:
                latest[record.target_artifact] = record
        return sorted(latest.values(), key=lambda r: r.target_artifact)

    def _superseded(self) -> list[str]:
        seen: dict[str, AttemptRecord] = {}
        superseded: list[str] = []
        for record in self.store.iter_attempts():
            if record.selector_verdict not in RETAINED_VERDICTS:
                continue
            current = seen.get(record.target_artifact)
            if current is not None and record.created_utc < current.created_utc:
                superseded.append(record.attempt_id)
            else:
                if current is not None:
                    superseded.append(current.attempt_id)
                seen[record.target_artifact] = record
        return sorted(set(superseded))

    def _disposition(self, scope: EditScope, transition: Mapping[str, bool]) -> tuple[Disposition, str, bool]:
        model_changed = transition["model_changed"]
        split_changed = transition["split_changed"]

        if scope is EditScope.INVARIANT_GATE:
            return (
                Disposition.ANCHOR,
                "structural invariant: kept as an anchor; its evaluator binding is re-verified",
                True,
            )
        if scope is EditScope.MODEL_SPECIFIC_REPAIR:
            if model_changed:
                return (
                    Disposition.PROVISIONAL_REVALIDATE,
                    "model-specific repair: the model that shaped it is gone",
                    False,
                )
            return (Disposition.CARRIED, "model-specific repair under the same model", False)
        if scope is EditScope.DOMAIN_HEURISTIC:
            if split_changed:
                return (
                    Disposition.PROVISIONAL_REVALIDATE,
                    "domain heuristic: the task split it was fitted to is gone",
                    False,
                )
            return (Disposition.CARRIED, "domain heuristic under the same split", False)
        if scope is EditScope.CONTEXT_ORCHESTRATION:
            if ("model" in self.policy.flag_context_on and model_changed) or (
                "split" in self.policy.flag_context_on and split_changed
            ):
                return (
                    Disposition.PROVISIONAL_REVALIDATE,
                    "context orchestration: policy flags it as setting-tuned",
                    False,
                )
            return (Disposition.CARRIED, "context orchestration carried", False)
        return (Disposition.CARRIED, "unclassified scope carried", False)  # pragma: no cover

    def plan(self, from_setting: SettingFingerprint, to_setting: SettingFingerprint) -> TransferPlan:
        """Build the work list for a crossing. Does not run anything."""
        transition = from_setting.differs_from(to_setting)
        items: list[TransferItem] = []
        for record in self.retained_edits():
            disposition, reason, binding_review = self._disposition(record.edit_scope, transition)
            items.append(
                TransferItem(
                    attempt_id=record.attempt_id,
                    target_artifact=record.target_artifact,
                    edit_scope=record.edit_scope,
                    disposition=disposition,
                    reason=reason,
                    binding_review=binding_review,
                )
            )
        return TransferPlan(
            from_setting=from_setting,
            to_setting=to_setting,
            transition=transition,
            items=tuple(items),
            superseded=tuple(self._superseded()),
        )


def revalidation_list(plan: TransferPlan) -> list[TransferItem]:
    """Only the edits the plan says must be re-tested before the target rounds start."""
    return [item for item in plan.items if item.disposition is Disposition.PROVISIONAL_REVALIDATE]
