"""SIM — the Self-Improvement Memory plane.

A problem-indexed causal ledger that lives beside the runtime and is never
imported by it. Nothing in this package records scene state, executes tools, or
influences a turn; it records what was attempted against the harness, what was
predicted, what was measured, and what was kept.

Phase 2 is the schema and the store. Nothing is wired to it yet.
"""

from .schema import (
    SCHEMA_VERSION,
    AttemptRecord,
    ClusterStatus,
    EditScope,
    Observation,
    Prediction,
    ProblemCluster,
    SchemaError,
    SelectorVerdict,
    cluster_id_for,
    normalize_signature,
)
from .propose import CandidateValidation, rejected_ids, validate_candidate, validate_candidates
from .select import DEFAULT_POLICY, SelectorPolicy, finalize, record_outcome, verdict_for
from .setting import SettingFingerprint
from .store import SIMStore, StoreError
from .transfer import (
    Disposition,
    TransferBoundaryController,
    TransferPlan,
    TransferPolicy,
    revalidation_list,
)

__all__ = [
    "SCHEMA_VERSION",
    "AttemptRecord",
    "ClusterStatus",
    "EditScope",
    "Observation",
    "Prediction",
    "ProblemCluster",
    "SchemaError",
    "SelectorVerdict",
    "CandidateValidation",
    "DEFAULT_POLICY",
    "Disposition",
    "SelectorPolicy",
    "TransferBoundaryController",
    "TransferPlan",
    "TransferPolicy",
    "revalidation_list",
    "SettingFingerprint",
    "SIMStore",
    "StoreError",
    "finalize",
    "record_outcome",
    "rejected_ids",
    "validate_candidate",
    "validate_candidates",
    "verdict_for",
    "cluster_id_for",
    "normalize_signature",
]
