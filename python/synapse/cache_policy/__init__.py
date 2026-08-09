"""synapse.cache_policy -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Pure-Python decision policy for SYNAPSE's resource-aware cache advisor. Authorized scope:
Ruling R-CACHE-1 (docs/reviews/cache-adjudication-ruling.md, Joe/CTO, 2026-08-09), acting on
docs/intake/adjudication-resource-aware-cache.md against
docs/SYNAPSE_RESOURCE_AWARE_CACHE_BLUEPRINT.md. Phase 0 ONLY.

HARD BOUNDARY: every module in this package imports stdlib only. Never ``hou``, never Qt,
never anything under ``synapse.panel``. Pinned by
tests/test_cache_policy.py::test_cache_policy_imports_without_houdini_or_qt.

No advice card, no tool registration, no Phase 1/2 wiring lives here -- see the mile
dispatch's binding constraints. This package is deliberately NOT imported by any server/
panel module yet; a live caller is a Mile 4 decision (R-CACHE-1 disposition item 4, d6 cure).
"""
from .models import (  # noqa: F401
    BakeAction,
    BoundaryAction,
    BoundarySignals,
    CacheDecision,
    CacheManifest,
    CachePolicy,
    CacheValidity,
    CacheVerdict,
    CacheVolume,
    Confidence,
    Context,
    Estimates,
    Evidence,
    ExistingCacheState,
    FrameRange,
    GPUDevice,
    GPURelevance,
    Interval,
    ManifestStatus,
    MachineProfile,
    PathClass,
    StateModel,
    StrategySupport,
    UNKNOWN,
    WorkloadSnapshot,
    evidence_confidence,
    evidence_value,
    existing_cache_from_manifest,
    is_unknown,
    to_jsonable,
)
from .decision import decide_cache, decide_boundary_value, validate_existing_cache  # noqa: F401
from .strategies import NodeDescriptor, StrategyResolution, resolve_strategy  # noqa: F401
from .policy_loader import (  # noqa: F401
    PolicyValidationError,
    default_policy_dict,
    load_policy,
    load_policy_from_json,
)
from .signatures import (  # noqa: F401
    SIGNATURE_ALGORITHM_VERSION,
    build_upstream_signature,
    canonical_bytes,
    compute_evidence_digest,
    digest_of,
)

__all__ = [
    "BakeAction", "BoundaryAction", "BoundarySignals", "CacheDecision", "CacheManifest",
    "CachePolicy", "CacheValidity", "CacheVerdict", "CacheVolume", "Confidence", "Context",
    "Estimates", "Evidence", "ExistingCacheState", "FrameRange", "GPUDevice", "GPURelevance",
    "Interval", "ManifestStatus", "MachineProfile", "PathClass", "StateModel",
    "StrategySupport", "UNKNOWN", "WorkloadSnapshot", "evidence_confidence", "evidence_value",
    "existing_cache_from_manifest", "is_unknown", "to_jsonable",
    "decide_cache", "decide_boundary_value", "validate_existing_cache",
    "NodeDescriptor", "StrategyResolution", "resolve_strategy",
    "PolicyValidationError", "default_policy_dict", "load_policy", "load_policy_from_json",
    "SIGNATURE_ALGORITHM_VERSION", "build_upstream_signature", "canonical_bytes",
    "compute_evidence_digest", "digest_of",
]
