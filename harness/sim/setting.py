"""The setting fingerprint sigma = (model, evaluation split, harness hash).

Every attempt record is stamped with the setting it was measured under. Without
it a negative result cannot be invalidated when the policy model or the task
domain changes, and a model-specific repair silently becomes a handicap on the
next model — the failure this plane exists to prevent.

The model id is supplied by the caller. Today nothing in the product persists
which model ran a turn; when that changes, this is the type it feeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

UNKNOWN = "unknown"


@dataclass(frozen=True)
class SettingFingerprint:
    """Identity of the (policy model, evaluation split) pair an attempt ran under."""

    model_id: str
    eval_split_id: str
    harness_hash: str

    def __post_init__(self) -> None:
        for field_name in ("model_id", "eval_split_id", "harness_hash"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")

    @property
    def is_complete(self) -> bool:
        """False when any component is the explicit unknown sentinel."""
        return UNKNOWN not in (self.model_id, self.eval_split_id)

    def differs_from(self, other: "SettingFingerprint") -> dict[str, bool]:
        """Which components changed between two settings.

        A changed model invalidates MODEL_SPECIFIC_REPAIR edits; a changed split
        invalidates DOMAIN_HEURISTIC edits; a changed harness hash invalidates the
        comparison itself. Phase 4's transfer controller consumes this.
        """
        return {
            "model_changed": self.model_id != other.model_id,
            "split_changed": self.eval_split_id != other.eval_split_id,
            "harness_changed": self.harness_hash != other.harness_hash,
        }

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "eval_split_id": self.eval_split_id,
            "harness_hash": self.harness_hash,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SettingFingerprint":
        return cls(
            model_id=str(data["model_id"]),
            eval_split_id=str(data["eval_split_id"]),
            harness_hash=str(data["harness_hash"]),
        )
