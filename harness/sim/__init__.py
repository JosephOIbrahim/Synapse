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
from .setting import SettingFingerprint
from .store import SIMStore, StoreError

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
    "SettingFingerprint",
    "SIMStore",
    "StoreError",
    "cluster_id_for",
    "normalize_signature",
]
