"""SIM records: problem clusters, attempt records, and the vocabulary around them.

Two rules shape this module.

1. **A cluster is identified by its symptom, not by its story.** ``cluster_id`` is
   a hash of the normalized symptom signature, so the same failure observed twice
   lands in the same file without a human deciding it should.
2. **An attempt is falsifiable or it is not recorded.** Every ``AttemptRecord``
   carries an ``ex_ante_prediction`` committed before evaluation and a
   ``target_artifact`` naming the file or surface it edited. An observation is
   required unless the candidate was rejected at screening, before it ran.

Validation happens on write *and* on read: a ledger that can be corrupted by a
hand edit is not a ledger.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from .setting import SettingFingerprint

SCHEMA_VERSION = "sim/v1"

CLUSTER_ID_RE = re.compile(r"^pc-[0-9a-f]{16}$")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")


class SchemaError(ValueError):
    """A record does not satisfy the schema. Raised on write and on read."""


class EditScope(str, Enum):
    """What kind of harness surface an edit touches. This decides its transfer risk.

    INVARIANT_GATE edits — termination checks, deliverable verification, schema or
    registration audits — carry across models and datasets. MODEL_SPECIFIC_REPAIR
    and DOMAIN_HEURISTIC edits are the ones that invert when the setting changes.
    """

    INVARIANT_GATE = "INVARIANT_GATE"
    CONTEXT_ORCHESTRATION = "CONTEXT_ORCHESTRATION"
    MODEL_SPECIFIC_REPAIR = "MODEL_SPECIFIC_REPAIR"
    DOMAIN_HEURISTIC = "DOMAIN_HEURISTIC"


class ClusterStatus(str, Enum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    REGRESSED = "REGRESSED"
    OBSOLETE_ON_TARGET = "OBSOLETE_ON_TARGET"


class SelectorVerdict(str, Enum):
    RETAIN = "RETAIN"
    REVISE = "REVISE"
    REPLACE = "REPLACE"
    REMOVE = "REMOVE"
    REJECTED_SCREENING = "REJECTED_SCREENING"


def normalize_signature(text: str) -> str:
    """Canonical form of a symptom signature: casefolded, whitespace-collapsed."""
    if not isinstance(text, str):
        raise SchemaError("symptom signature must be a string")
    normalized = " ".join(text.split()).casefold()
    if not normalized:
        raise SchemaError("symptom signature must not be empty")
    return normalized


def cluster_id_for(symptom_signature: str) -> str:
    """Deterministic cluster id from a symptom signature."""
    digest = hashlib.sha256(normalize_signature(symptom_signature).encode("utf-8")).hexdigest()
    return "pc-" + digest[:16]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


# Outcomes that mean "this edit is in force". RETAIN and REPLACE are both
# retained: REPLACE says the new edit supersedes an incumbent, not that it
# failed. Everything else - REVISE, REMOVE, REJECTED_SCREENING - is not retained.
RETAINED_VERDICTS = frozenset({SelectorVerdict.RETAIN, SelectorVerdict.REPLACE})


def _iso(value: str, field_name: str) -> None:
    _require(isinstance(value, str) and bool(value), f"{field_name} must be a non-empty ISO-8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - message path
        raise SchemaError(f"{field_name} is not ISO-8601: {value!r}") from exc


@dataclass(frozen=True)
class ProblemCluster:
    """A failure class, addressable by its symptom."""

    cluster_id: str
    symptom_signature: str
    root_cause_diagnosis: str
    status: ClusterStatus
    created_utc: str

    def __post_init__(self) -> None:
        _require(bool(CLUSTER_ID_RE.match(self.cluster_id)), f"bad cluster_id: {self.cluster_id!r}")
        _require(
            self.cluster_id == cluster_id_for(self.symptom_signature),
            "cluster_id does not match its symptom signature",
        )
        _require(isinstance(self.root_cause_diagnosis, str), "root_cause_diagnosis must be a string")
        _require(isinstance(self.status, ClusterStatus), "status must be a ClusterStatus")
        _iso(self.created_utc, "created_utc")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "symptom_signature": self.symptom_signature,
            "root_cause_diagnosis": self.root_cause_diagnosis,
            "status": self.status.value,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProblemCluster":
        try:
            return cls(
                cluster_id=str(data["cluster_id"]),
                symptom_signature=str(data["symptom_signature"]),
                root_cause_diagnosis=str(data["root_cause_diagnosis"]),
                status=ClusterStatus(str(data["status"])),
                created_utc=str(data["created_utc"]),
            )
        except (KeyError, ValueError) as exc:
            raise SchemaError(f"ProblemCluster: {exc}") from exc


@dataclass(frozen=True)
class Prediction:
    """What the edit promises, committed before it is measured."""

    expected_delta: float
    target_metric: str
    max_regression: float
    target_trace_node: str = ""

    def __post_init__(self) -> None:
        _require(isinstance(self.expected_delta, (int, float)), "expected_delta must be numeric")
        _require(isinstance(self.max_regression, (int, float)), "max_regression must be numeric")
        _require(self.max_regression >= 0, "max_regression must not be negative")
        _require(isinstance(self.target_metric, str) and bool(self.target_metric.strip()), "target_metric must be a non-empty string")

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_delta": float(self.expected_delta),
            "target_metric": self.target_metric,
            "max_regression": float(self.max_regression),
            "target_trace_node": self.target_trace_node,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Prediction":
        try:
            return cls(
                expected_delta=float(data["expected_delta"]),
                target_metric=str(data["target_metric"]),
                max_regression=float(data["max_regression"]),
                target_trace_node=str(data.get("target_trace_node", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaError(f"Prediction: {exc}") from exc


@dataclass(frozen=True)
class Observation:
    """What was measured, after the candidate ran."""

    measured_delta: float
    latency_delta_s: float = 0.0
    token_delta: int = 0
    regressions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require(isinstance(self.measured_delta, (int, float)), "measured_delta must be numeric")
        _require(isinstance(self.latency_delta_s, (int, float)), "latency_delta_s must be numeric")
        _require(isinstance(self.token_delta, int), "token_delta must be an int")
        _require(all(isinstance(r, str) for r in self.regressions), "regressions must be strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "measured_delta": float(self.measured_delta),
            "latency_delta_s": float(self.latency_delta_s),
            "token_delta": int(self.token_delta),
            "regressions": list(self.regressions),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Observation":
        try:
            return cls(
                measured_delta=float(data["measured_delta"]),
                latency_delta_s=float(data.get("latency_delta_s", 0.0)),
                token_delta=int(data.get("token_delta", 0)),
                regressions=tuple(str(r) for r in data.get("regressions", ())),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaError(f"Observation: {exc}") from exc


@dataclass(frozen=True)
class AttemptRecord:
    """One candidate harness edit, its prediction, and what happened.

    ``target_artifact`` is what makes the record address the thing that changed:
    a skill file, a prompt block, a routing table, a tool roster entry. Without it
    an edit can be described but not located, and a later reader cannot tell
    whether the same edit has already been tried.
    """

    attempt_id: str
    cluster_id: str
    round_id: str
    parent_harness_hash: str
    candidate_harness_hash: str
    setting: SettingFingerprint
    edit_scope: EditScope
    target_artifact: str
    diff_patch: str
    edit_rationale: str
    ex_ante_prediction: Prediction
    selector_verdict: SelectorVerdict
    created_utc: str
    ex_post_observation: Observation | None = None

    def __post_init__(self) -> None:
        _require(isinstance(self.attempt_id, str) and bool(self.attempt_id.strip()), "attempt_id required")
        _require(bool(CLUSTER_ID_RE.match(self.cluster_id)), f"bad cluster_id: {self.cluster_id!r}")
        _require(isinstance(self.round_id, str) and bool(self.round_id.strip()), "round_id required")
        _require(bool(HASH_RE.match(self.parent_harness_hash)), "parent_harness_hash must be 64 hex chars")
        _require(bool(HASH_RE.match(self.candidate_harness_hash)), "candidate_harness_hash must be 64 hex chars")
        _require(isinstance(self.setting, SettingFingerprint), "setting must be a SettingFingerprint")
        _require(isinstance(self.edit_scope, EditScope), "edit_scope must be an EditScope")
        _require(
            isinstance(self.target_artifact, str) and bool(self.target_artifact.strip()),
            "target_artifact is required: name the file or surface this edit changes",
        )
        _require(isinstance(self.diff_patch, str) and bool(self.diff_patch.strip()), "diff_patch required")
        _require(isinstance(self.edit_rationale, str) and bool(self.edit_rationale.strip()), "edit_rationale required")
        _require(isinstance(self.ex_ante_prediction, Prediction), "ex_ante_prediction must be a Prediction")
        _require(isinstance(self.selector_verdict, SelectorVerdict), "selector_verdict must be a SelectorVerdict")
        _iso(self.created_utc, "created_utc")
        if self.selector_verdict is not SelectorVerdict.REJECTED_SCREENING:
            _require(
                isinstance(self.ex_post_observation, Observation),
                "ex_post_observation is required unless the candidate was rejected at screening",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "attempt_id": self.attempt_id,
            "cluster_id": self.cluster_id,
            "round_id": self.round_id,
            "parent_harness_hash": self.parent_harness_hash,
            "candidate_harness_hash": self.candidate_harness_hash,
            "setting": self.setting.to_dict(),
            "edit_scope": self.edit_scope.value,
            "target_artifact": self.target_artifact,
            "diff_patch": self.diff_patch,
            "edit_rationale": self.edit_rationale,
            "ex_ante_prediction": self.ex_ante_prediction.to_dict(),
            "ex_post_observation": (
                self.ex_post_observation.to_dict() if self.ex_post_observation is not None else None
            ),
            "selector_verdict": self.selector_verdict.value,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttemptRecord":
        try:
            observation = data.get("ex_post_observation")
            return cls(
                attempt_id=str(data["attempt_id"]),
                cluster_id=str(data["cluster_id"]),
                round_id=str(data["round_id"]),
                parent_harness_hash=str(data["parent_harness_hash"]),
                candidate_harness_hash=str(data["candidate_harness_hash"]),
                setting=SettingFingerprint.from_dict(data["setting"]),
                edit_scope=EditScope(str(data["edit_scope"])),
                target_artifact=str(data.get("target_artifact", "")),
                diff_patch=str(data["diff_patch"]),
                edit_rationale=str(data["edit_rationale"]),
                ex_ante_prediction=Prediction.from_dict(data["ex_ante_prediction"]),
                ex_post_observation=Observation.from_dict(observation) if observation else None,
                selector_verdict=SelectorVerdict(str(data["selector_verdict"])),
                created_utc=str(data["created_utc"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaError(f"AttemptRecord: {exc}") from exc


JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_VERSION + "/attempt-record",
    "type": "object",
    "required": [
        "attempt_id",
        "cluster_id",
        "round_id",
        "parent_harness_hash",
        "candidate_harness_hash",
        "setting",
        "edit_scope",
        "target_artifact",
        "diff_patch",
        "edit_rationale",
        "ex_ante_prediction",
        "selector_verdict",
        "created_utc",
    ],
    "properties": {
        "attempt_id": {"type": "string", "minLength": 1},
        "cluster_id": {"type": "string", "pattern": "^pc-[0-9a-f]{16}$"},
        "round_id": {"type": "string", "minLength": 1},
        "parent_harness_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "candidate_harness_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "setting": {
            "type": "object",
            "required": ["model_id", "eval_split_id", "harness_hash"],
            "properties": {
                "model_id": {"type": "string", "minLength": 1},
                "eval_split_id": {"type": "string", "minLength": 1},
                "harness_hash": {"type": "string", "minLength": 1},
            },
        },
        "edit_scope": {"enum": [scope.value for scope in EditScope]},
        "target_artifact": {"type": "string", "minLength": 1},
        "diff_patch": {"type": "string", "minLength": 1},
        "edit_rationale": {"type": "string", "minLength": 1},
        "ex_ante_prediction": {
            "type": "object",
            "required": ["expected_delta", "target_metric", "max_regression"],
        },
        "ex_post_observation": {"type": ["object", "null"]},
        "selector_verdict": {"enum": [verdict.value for verdict in SelectorVerdict]},
        "created_utc": {"type": "string", "minLength": 1},
    },
}
