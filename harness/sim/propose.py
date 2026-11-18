"""Candidate validation — the proposer contract, enforced before anything runs.

A candidate harness edit is admissible only if it can answer three questions
*before* it is evaluated:

1. **Which failure is this for?** A ``cluster_id`` that already exists in the SIM
   ledger, or a new cluster declared with its symptom signature and diagnosis.
2. **What will change, and by how much?** An ex-ante prediction naming the metric,
   the expected delta and the largest regression that would still be acceptable.
3. **What is being edited?** A ``target_artifact`` and an ``edit_scope`` from the
   closed vocabulary, plus the diff itself.

Two further rules follow from the ledger. A candidate that repeats an attempt
already recorded as a non-retained outcome, on the same artifact under the same
setting, is refused — that is the cyclic dead-end the plane exists to prevent.
And validation is **pure**: it reads the ledger, never writes it.

Everything is opt-in. With no store supplied this module still enforces the
structural contract, but the duplicate rule needs a ledger to consult.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .schema import ClusterStatus, EditScope, Prediction, ProblemCluster, SchemaError, cluster_id_for
from .setting import SettingFingerprint
from .store import SIMStore, StoreError


@dataclass(frozen=True)
class CandidateValidation:
    """The verdict on one candidate, with the fields a record will need."""

    candidate_id: str
    ok: bool
    reasons: tuple[str, ...] = ()
    cluster_id: str | None = None
    edit_scope: EditScope | None = None
    target_artifact: str | None = None
    prediction: Prediction | None = None
    new_cluster: ProblemCluster | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "ok": self.ok,
            "reasons": list(self.reasons),
            "cluster_id": self.cluster_id,
            "edit_scope": self.edit_scope.value if self.edit_scope else None,
            "target_artifact": self.target_artifact,
        }


def _first(candidate: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in candidate and candidate[key] not in (None, ""):
            return candidate[key]
    return None


def _parse_scope(value: Any) -> EditScope:
    if isinstance(value, EditScope):
        return value
    return EditScope(str(value))


def _parse_prediction(value: Any) -> Prediction:
    if isinstance(value, Prediction):
        return value
    if isinstance(value, Mapping):
        return Prediction.from_dict(value)
    raise SchemaError("prediction must be a Prediction or a mapping with its fields")


def validate_candidate(
    candidate: Mapping[str, Any],
    *,
    store: SIMStore | None = None,
    setting: SettingFingerprint | None = None,
    allow_new_cluster: bool = True,
    now_utc: str = "",
) -> CandidateValidation:
    """Check one candidate against the proposer contract. Never writes."""
    if not isinstance(candidate, Mapping):
        raise TypeError("candidate must be a mapping")
    candidate_id = str(_first(candidate, "id", "candidate_id") or "")
    reasons: list[str] = []
    if not candidate_id:
        reasons.append("candidate has no id")

    # 1. Which failure is this for?
    cluster_id_raw = _first(candidate, "cluster_id", "cluster")
    declared = _first(candidate, "new_cluster", "cluster_declaration")
    new_cluster: ProblemCluster | None = None
    cluster_id: str | None = str(cluster_id_raw) if cluster_id_raw else None

    if declared is not None:
        if not allow_new_cluster:
            reasons.append("new cluster declarations are not accepted here")
        else:
            try:
                signature = str(declared["symptom_signature"])
                new_cluster = ProblemCluster(
                    cluster_id=cluster_id_for(signature),
                    symptom_signature=signature,
                    root_cause_diagnosis=str(declared.get("root_cause_diagnosis", "")),
                    status=ClusterStatus(str(declared.get("status", "OPEN"))),
                    created_utc=str(declared.get("created_utc") or now_utc or "1970-01-01T00:00:00+00:00"),
                )
                cluster_id = new_cluster.cluster_id
            except (KeyError, SchemaError, ValueError) as exc:
                reasons.append(f"new cluster declaration is not valid: {exc}")
    if not cluster_id:
        reasons.append("candidate cites no problem cluster")

    # 2. What will change, and by how much?
    prediction: Prediction | None = None
    raw_prediction = _first(candidate, "ex_ante_prediction", "prediction")
    if raw_prediction is None:
        reasons.append("candidate carries no ex-ante prediction")
    else:
        try:
            prediction = _parse_prediction(raw_prediction)
        except (SchemaError, ValueError) as exc:
            reasons.append(f"ex-ante prediction is not valid: {exc}")

    # 3. What is being edited?
    scope: EditScope | None = None
    raw_scope = _first(candidate, "edit_scope", "scope")
    if raw_scope is None:
        reasons.append("candidate classifies no edit scope")
    else:
        try:
            scope = _parse_scope(raw_scope)
        except ValueError as exc:
            reasons.append(f"edit scope is not in the vocabulary: {exc}")

    target = _first(candidate, "target_artifact", "target", "artifact")
    if not target:
        reasons.append("candidate names no target artifact")

    if not _first(candidate, "diff_patch", "diff"):
        reasons.append("candidate carries no diff")

    # 4. Not already a known negative under this setting.
    if store is not None and setting is not None and target and cluster_id:
        try:
            negatives = store.known_negatives(str(target), setting)
        except StoreError as exc:
            reasons.append(f"ledger unreadable: {exc}")
            negatives = []
        if negatives:
            prior = ", ".join(sorted({record.attempt_id for record in negatives}))
            reasons.append(
                f"known negative: {target} was already tried and not retained under this setting ({prior})"
            )

    return CandidateValidation(
        candidate_id=candidate_id,
        ok=not reasons,
        reasons=tuple(reasons),
        cluster_id=cluster_id,
        edit_scope=scope,
        target_artifact=str(target) if target else None,
        prediction=prediction,
        new_cluster=new_cluster,
    )


def validate_candidates(
    candidates: Iterable[Mapping[str, Any]],
    *,
    store: SIMStore | None = None,
    setting: SettingFingerprint | None = None,
    allow_new_cluster: bool = True,
) -> dict[str, CandidateValidation]:
    """Validate a batch, keyed by candidate id. Ids are not required to be unique."""
    results: dict[str, CandidateValidation] = {}
    for candidate in candidates:
        result = validate_candidate(
            candidate, store=store, setting=setting, allow_new_cluster=allow_new_cluster
        )
        results[result.candidate_id] = result
    return results


def rejected_ids(results: Mapping[str, CandidateValidation]) -> dict[str, list[str]]:
    """The subset a caller should exclude, with reasons — the shape both hooks use."""
    return {
        candidate_id: list(result.reasons)
        for candidate_id, result in results.items()
        if not result.ok
    }
