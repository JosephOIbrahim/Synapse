"""python/synapse/cache_policy/models.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Typed, versioned, PURE-PYTHON data contracts for blueprint sections 6 (decision model) and
7 (typed contracts). See docs/SYNAPSE_RESOURCE_AWARE_CACHE_BLUEPRINT.md and
docs/intake/adjudication-resource-aware-cache.md for the governing authorities.

BOUNDARY (binding constraint #2 / blueprint 13.2): this module imports stdlib ONLY. Never
``hou``, never Qt, never anything under ``synapse.panel``. This is pinned by
tests/test_cache_policy.py::test_cache_policy_imports_without_houdini_or_qt.

SCHEMA CONVENTION (adjudication b11/E4 -- CORRECT/binding): the blueprint's own §7.2-§7.6
JSON examples use a bare ``"schema_version": "1.0"`` field. The GOVERNING repo convention
(the actual authority, independent of any sibling module) is the namespaced identifier
``docs/SYNAPSE_NEXT_SYSTEM_BLUEPRINT.md`` §4 defines -- ``"schema": "synapse.intent_route/v1"``,
``"synapse.execution_receipt/v2"``, etc. Every contract below therefore carries BOTH a
``schema`` field (namespaced ``"synapse.cache_*/v1"``, primary identifier, per that governing
convention) AND a ``schema_version`` field (bare version string, kept for field-compatibility
with ``host/cache_host_probe.py``'s ``detect_machine_profile()``/``to_workload_snapshot_kwargs()``,
which emit ``schema_version`` as a literal kwarg name).

Corrected post-review (crucible weakness 8): an earlier draft of this note called
``host/cache_host_probe.py``'s side-by-side ``schema``+``schema_version`` keys
"already-committed precedent" this module "follows." That overstated it -- that module is
forge-host's Phase-0 sibling build in this SAME wave, not prior art from an earlier one, and
its own ``"schema": "cache_host_observation/v1"`` is not itself namespaced under
``synapse.`` (only this package's contracts are, per b11's actual requirement). This module
matches its sibling's field SHAPE for interop, not because it predates or governs this one.


UNKNOWN DISCIPLINE (adjudication b6/b4, CLAUDE.md phantom-API doctrine's cousin): a field
that cannot be safely measured is represented as the literal string ``"unknown"`` (scalar
fields, matching ``host/cache_host_probe.py``'s convention) or as an Evidence-shaped
value/dict with ``value=None, source="unknown", confidence="unknown"`` (measured-quantity
fields). NEVER a guessed default, NEVER 0, NEVER False standing in for "not measured".
``evidence_value()`` / ``is_unknown()`` below are the single accessor pair every consumer
(decision.py, estimator.py, strategies.py) must use -- never hand-roll a truthiness check
against these fields.

V0/UNVERIFIED SURFACES (adjudication c1/c2/c4/c5/c6/e8 -- CORRECT/binding): nothing in this
file asserts a Houdini API unit, kwarg, or intrinsic-string name as confirmed fact. Where a
field's provenance ultimately traces to ``hou.OpNode.lastCookTime()`` (unit V0),
``hou.OpNode.isTimeDependent(for_last_cook=True)`` (kwarg V0), or
``hou.Geometry.intrinsicValue("memoryusage")`` (intrinsic-string V0), that lineage is
recorded in the Evidence wrapper's ``source`` field, never smoothed over. See
tests/assay_h22_cache_contract.py (NOT RUN this mile) for where those get verified.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields as dc_fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

# --------------------------------------------------------------------------- sentinels

UNKNOWN = "unknown"
"""The one literal string standing in for "not measured" on scalar (non-evidence-wrapped)
fields. Never a number, never True/False, never an empty collection."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- enums (§6, §7)

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CacheVerdict(str, Enum):
    """§6.1 -- the nine public verdicts."""
    USE_VALID_CACHE = "use_valid_cache"
    CACHE_NOW = "cache_now"
    INSERT_BOUNDARY_ONLY = "insert_boundary_only"
    MEASURE_FIRST = "measure_first"
    OPTIMIZE_FIRST = "optimize_first"
    NOT_WORTH_IT = "not_worth_it"
    INSUFFICIENT_DISK = "insufficient_disk"
    UNSUPPORTED = "unsupported"
    # No producer in decision.py's 15 return paths as of M2b: unsafe-or-missing evidence
    # routes to MEASURE_FIRST (sanctioned by blueprint §2.5), not here. UNKNOWN describes
    # contradictory evidence, which Phase 0 doesn't detect yet. Kept as the defensive
    # dataclass default (see CacheDecision below) -- reviewer-flagged known limitation,
    # not a behavioral risk. Wire a real producer if/when contradiction-detection lands.
    UNKNOWN = "unknown"


class BoundaryAction(str, Enum):
    """§6.2 -- orthogonal to CacheVerdict. Never infer from the verdict string; both are
    always set explicitly by decision.py."""
    NONE = "none"
    INSERT = "insert"
    REUSE_EXISTING = "reuse_existing"


class BakeAction(str, Enum):
    """§6.2 -- orthogonal to CacheVerdict and BoundaryAction.

    ``BAKE_AFTER_APPROVAL`` names an intent, not a guarantee (noted post-review, crucible
    weakness 6): adjudication a7/E3 (CORRECT/highest-severity escalation) found the live
    panel's ``bridge_adapter._panel_consent`` resolves to an unconditional ``return True``
    with ``HumanGate`` disabled, so a real "approval" gate for the disk write this action
    implies does not yet exist on either SYNAPSE transport at HEAD. This Phase-0 policy
    package is transport-agnostic and makes no claim about what enforces the approval --
    it only asserts that this verdict REQUIRES one before any bytes hit disk. Wiring a real
    gate is out of scope for cache_policy and is a Mile 4 (Phase 1 advisor)/E3 concern.
    """
    DO_NOT_BAKE = "do_not_bake"
    BAKE_AFTER_APPROVAL = "bake_after_approval"
    MEASURE_THEN_REASSESS = "measure_then_reassess"
    OPTIMIZE_FIRST = "optimize_first"


class CacheValidity(str, Enum):
    """§6.2 / §12.4. NOTE (adjudication e6, CORRECT): ``stale``/``unverifiable`` live on
    THIS enum, never on CacheVerdict -- §17.1's "Expected verdict" column entries reading
    "stale"/"unverifiable" describe the CacheValidity axis, not a tenth CacheVerdict member.
    """
    NOT_PRESENT = "not_present"
    VALID = "valid"
    STALE = "stale"
    PARTIAL = "partial"
    CORRUPT = "corrupt"
    UNVERIFIABLE = "unverifiable"


class StrategySupport(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class GPURelevance(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_USED = "not_used"
    UNKNOWN = "unknown"


class StateModel(str, Enum):
    STATIC = "static"
    INDEPENDENT_FRAMES = "independent_frames"
    SEQUENTIAL_STATEFUL = "sequential_stateful"
    UNKNOWN = "unknown"


class PathClass(str, Enum):
    """§7.2. Never inferred from a drive letter alone -- see MachineProfile docstring."""
    LOCAL_SSD = "local_ssd"
    LOCAL_HDD = "local_hdd"
    NETWORK = "network"
    CLOUD_SYNCED = "cloud_synced"
    REMOVABLE = "removable"
    UNKNOWN = "unknown"


class Context(str, Enum):
    """§7.3. V0/unverified for anything beyond "this string was supplied by the caller" --
    cache_policy never introspects a live node itself (no hou import)."""
    SOP = "sop"
    DOP = "dop"
    LOP = "lop"
    COP = "cop"
    TOP = "top"
    UNKNOWN = "unknown"


class ManifestStatus(str, Enum):
    """§7.6 lifecycle states.

    ``CANCELLED`` is a representable STATE (noted post-review, crucible weakness 6), not a
    claim that cancellation is achievable: adjudication e3/E6 (ADAPT->REJECT) established
    that this build exposes no API to cancel, abort, interrupt, or kill an in-flight
    Houdini cook/render (harness/notes/H3a_SIDEFX_ASK.md). A manifest could legitimately
    observe ``cancelled`` if some OTHER mechanism (process kill, artist force-quit) leaves
    that state on disk -- this Phase 0 package models the shape without asserting a live
    cancel path exists. Blueprint §17.4 assay item 10 (manifest cancellation state) is
    explicitly excluded from this mile's assay script (§17.4 items 1-7 only).
    """
    PLANNED = "planned"
    WRITING = "writing"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --------------------------------------------------------------------------- Evidence (§7.1)

@dataclass(frozen=True)
class Evidence:
    """§7.1 evidence wrapper. Every decision-critical measured value should be wrapped in
    one of these (or the field-compatible plain dict shape ``host/cache_host_probe.py``
    already emits -- see ``evidence_value``/``is_unknown`` below, which accept both).
    """
    value: Any
    unit: Optional[str] = None
    source: str = UNKNOWN
    scope: str = ""
    confidence: str = Confidence.UNKNOWN.value
    observed_at: Optional[str] = None

    @classmethod
    def known(cls, value: Any, *, unit: Optional[str] = None, source: str,
              scope: str = "", confidence: str = Confidence.HIGH.value,
              observed_at: Optional[str] = None) -> "Evidence":
        return cls(value=value, unit=unit, source=source, scope=scope,
                    confidence=confidence, observed_at=observed_at or now_iso())

    @classmethod
    def unknown(cls, *, unit: Optional[str] = None, scope: str = "") -> "Evidence":
        return cls(value=None, unit=unit, source=UNKNOWN, scope=scope,
                    confidence=Confidence.UNKNOWN.value, observed_at=None)

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    def to_dict(self) -> dict:
        return {
            "value": self.value, "unit": self.unit, "source": self.source,
            "scope": self.scope, "confidence": self.confidence,
            "observed_at": self.observed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            value=d.get("value"), unit=d.get("unit"), source=d.get("source", UNKNOWN),
            scope=d.get("scope", ""), confidence=d.get("confidence", Confidence.UNKNOWN.value),
            observed_at=d.get("observed_at"),
        )


def evidence_value(x: Any) -> Any:
    """Duck-typed accessor: works on an Evidence instance, a plain evidence-shaped dict
    (the ``host/cache_host_probe.py`` shape), a raw scalar-or-``UNKNOWN`` field (the
    MachineProfile/CacheVolume/GPUDevice convention), or None. This is the ONE accessor
    every consumer must go through -- never ``x["value"]`` or ``x.value`` directly, and
    never a hand-rolled ``x is None`` or ``x == "unknown"`` check at a call site.

    NORMALIZATION (fixed post-review, crucible showstopper 1): the literal string
    ``UNKNOWN`` ("unknown") is normalized to ``None`` here, at the single accessor,
    rather than leaving it to every downstream ``is None`` check to also remember an
    ``or x == "unknown"`` clause. Before this fix, ``estimator.ram_feasibility``/
    ``vram_feasibility``/``disk_headroom`` each unwrapped a field via this function,
    checked ``is None``, and then arithmetic'd the result -- but a genuinely unmeasured
    ``MachineProfile.ram_available_bytes`` (its own dataclass default IS the string
    "unknown", not None) sailed through that check unrecognized and reached
    ``min("unknown", ram_total * fraction)``, raising TypeError on real
    ``host/cache_host_probe.py`` output. Centralizing the normalization here means every
    existing ``evidence_value(x) is None`` call site downstream is now correct by
    construction, without auditing each one individually.
    """
    if x is None:
        return None
    if isinstance(x, Evidence):
        v = x.value
    elif isinstance(x, dict) and "value" in x:
        v = x.get("value")
    else:
        v = x
    return None if v == UNKNOWN else v


def is_unknown(x: Any) -> bool:
    """True when x represents "not measured": None, the literal string "unknown", or an
    evidence wrapper/dict whose value is None or "unknown". Delegates to
    ``evidence_value``'s normalization -- kept as an explicit ``is None`` check here (not
    a second independent implementation) so there is exactly one place that decides what
    "unknown" means.
    """
    return evidence_value(x) is None


def evidence_confidence(x: Any) -> str:
    """§6.3: "Confidence is computed from evidence provenance and completeness, not prose
    sentiment." Fixed post-review (crucible weakness 3): a bare scalar carrying no
    provenance wrapper at all (not an Evidence instance, not an evidence-shaped dict) used
    to report ``high`` confidence merely because its value happened to be present and not
    ``UNKNOWN`` -- that inverts the rule (confidence comes from PROVENANCE, not value
    presence). An un-wrapped value has no recorded provenance, so its confidence is always
    ``unknown`` here, regardless of whether the value itself is known or unknown.
    """
    if isinstance(x, Evidence):
        return x.confidence
    if isinstance(x, dict) and "confidence" in x:
        return x.get("confidence", Confidence.UNKNOWN.value)
    return Confidence.UNKNOWN.value


# --------------------------------------------------------------------------- small value types

@dataclass(frozen=True)
class Interval:
    """A low/high bound. Used wherever the blueprint calls for a range instead of a fake
    point value (§7.2 throughput, §7.5 estimates, §10.3 feasibility math)."""
    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low > self.high:
            raise ValueError(f"Interval.low ({self.low}) must be <= Interval.high ({self.high})")

    @classmethod
    def point(cls, value: float) -> "Interval":
        """A degenerate interval representing a single measured/known value with no
        modeled uncertainty -- NOT the same as unknown (use None/UNKNOWN for that)."""
        return cls(low=value, high=value)

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0

    def to_dict(self) -> dict:
        return {"low": self.low, "high": self.high}

    @classmethod
    def from_dict(cls, d: dict) -> "Interval":
        return cls(low=d["low"], high=d["high"])


@dataclass
class FrameRange:
    start: int
    end: int
    step: int = 1
    fps: Optional[float] = None

    @property
    def frame_count(self) -> int:
        """Noted post-review (crucible weakness 4): a degenerate ``step == 0`` or
        ``end < start`` reports 0, not the ``UNKNOWN`` sentinel. This is a deliberate
        difference from every other "unmeasured" field in this module: unlike
        ``ram_total_bytes`` or ``last_cook_seconds``, a ``FrameRange`` only exists at all
        when a caller has already supplied concrete start/end/step integers -- there is no
        partially-known FrameRange, only a present one (with a real, if degenerate,
        frame_count) or an absent one (``WorkloadSnapshot.frame_range = None``, which IS
        this module's "frame range unknown" sentinel at the whole-object level). Every
        caller of ``.frame_count`` (``estimator.estimate_sequence_size``,
        ``estimator._extrapolate_compute_seconds``) already treats ``<= 0`` as
        "not usable", the same treatment an explicit unknown would receive -- so this is
        contained, not silently wrong, but is documented explicitly here per review.
        """
        if self.step == 0 or self.end < self.start:
            return 0
        return ((self.end - self.start) // self.step) + 1

    def to_dict(self) -> dict:
        return {"start": self.start, "end": self.end, "step": self.step, "fps": self.fps}


# --------------------------------------------------------------------------- MachineProfile (§7.2)

@dataclass
class GPUDevice:
    """§7.2 gpu_devices entry. ``vram_bytes`` is total VRAM, included only when actually
    measured (never inferred from ``name``). ``vram_available_bytes`` is a Phase-0-forward
    extension slot: no shipped probe in this mile populates it (host/cache_host_probe.py's
    ``_detect_gpu_devices`` reports total only via nvidia-smi), so it defaults to UNKNOWN and
    estimator.py's VRAM feasibility check treats that honestly as unknown, never as "0 used
    so everything is free"."""
    name: str = UNKNOWN
    vram_bytes: Any = UNKNOWN
    vram_available_bytes: Any = UNKNOWN

    @classmethod
    def from_dict(cls, d: dict) -> "GPUDevice":
        return cls(
            name=d.get("name", UNKNOWN),
            vram_bytes=d.get("vram_bytes", UNKNOWN),
            vram_available_bytes=d.get("vram_available_bytes", UNKNOWN),
        )


@dataclass
class CacheVolume:
    """§7.2 cache_volume. ``path_class`` is never inferred from a drive letter alone --
    stays UNKNOWN unless a project/user override supplies one (see
    host/cache_host_probe.py's ``_detect_cache_volume``, which already follows this rule).
    """
    path: Any = UNKNOWN
    path_class: str = PathClass.UNKNOWN.value
    free_bytes: Any = UNKNOWN
    total_bytes: Any = UNKNOWN
    read_mib_s: Any = UNKNOWN   # Optional[Interval]-shaped dict or UNKNOWN
    write_mib_s: Any = UNKNOWN  # Optional[Interval]-shaped dict or UNKNOWN


@dataclass
class MachineProfile:
    """§7.2. Field names match ``host/cache_host_probe.py::detect_machine_profile()``'s
    return-dict keys exactly, so ``maybe_construct_machine_profile`` in that (already
    committed, not modified here) module can construct a real typed instance instead of
    falling back to the plain dict.
    """
    schema: str = "synapse.cache_machine_profile/v1"
    schema_version: str = "1.0"
    profile_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    captured_at: str = field(default_factory=now_iso)
    os_family: str = UNKNOWN
    cpu_logical_threads: Any = UNKNOWN
    houdini_thread_cap: Any = UNKNOWN
    ram_total_bytes: Any = UNKNOWN
    ram_available_bytes: Any = UNKNOWN
    process_rss_bytes: Any = UNKNOWN
    gpu_devices: list = field(default_factory=list)
    cache_volume: Any = field(default_factory=CacheVolume)
    houdini_version: str = UNKNOWN
    synapse_version: str = UNKNOWN
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------- WorkloadSnapshot (§7.3)

@dataclass
class BoundarySignals:
    """§10.2 boundary-value signals, as explicit tri-state (True/False/None=unknown)
    booleans a caller sets from observed context. None (not False) means "not evaluated" --
    decide_boundary_value() must never treat an unevaluated signal as a negative one.
    """
    # positive signals
    stateful_downstream_scrub: Optional[bool] = None
    expensive_separable_upstream: Optional[bool] = None
    multiple_downstream_consumers: Optional[bool] = None
    repeated_viewport_reads: Optional[bool] = None
    cross_department_handoff: Optional[bool] = None
    checkpoint_recovery_required: Optional[bool] = None
    nondeterministic_or_externally_expensive_source: Optional[bool] = None
    # negative signals
    static_or_cheap: Optional[bool] = None
    changes_almost_every_edit: Optional[bool] = None
    read_not_faster_than_recompute: Optional[bool] = None
    output_large_relative_to_compute: Optional[bool] = None


POSITIVE_BOUNDARY_SIGNALS = (
    "stateful_downstream_scrub", "expensive_separable_upstream",
    "multiple_downstream_consumers", "repeated_viewport_reads",
    "cross_department_handoff", "checkpoint_recovery_required",
    "nondeterministic_or_externally_expensive_source",
)
NEGATIVE_BOUNDARY_SIGNALS = (
    "static_or_cheap", "changes_almost_every_edit",
    "read_not_faster_than_recompute", "output_large_relative_to_compute",
)


@dataclass
class ExistingCacheState:
    """§7.3 ``existing_cache`` / §12 validity. Deliberately NOT a filesystem reader --
    cache_policy has zero I/O and zero hou; a Phase 1 caller populates this from a real
    manifest read and passes it in.

    NOTED POST-REVIEW (crucible weakness 5b, documented rather than fixed this mile):
    ``CachePolicy.allow_unmanifested_cache_load`` is validated by policy_loader.py and
    carried in every decision's evidence digest, but ``decision.validate_existing_cache``
    does NOT currently read it -- an unmanifested-but-present cache always resolves
    ``UNVERIFIABLE`` regardless of this flag's value (§17.1 scenario 10 pins that as the
    correct DEFAULT-policy behavior). §12.4's own wording ("unmanifested legacy cache:
    treat as unverifiable unless an import/adoption workflow creates a manifest") implies
    the override's effect is "run the adoption workflow", not "silently treat it as valid"
    -- that adoption-workflow shape is a Phase 1 concern this pure module does not build.
    Left unwired deliberately rather than guessing its exact semantics; a future mile must
    either wire a real effect here or remove the field from CachePolicy.
    """
    present: bool = False
    manifested: bool = False
    manifest_status: Optional[str] = None  # ManifestStatus value, or None
    upstream_signature: Any = UNKNOWN
    current_upstream_signature: Any = UNKNOWN
    path: Any = UNKNOWN


@dataclass
class WorkloadSnapshot:
    """§7.3. The Phase-0-populatable subset (node_path, node_type, time_dependent,
    needs_to_cook, last_cook_seconds, geometry_memory_bytes, warnings, schema_version)
    matches ``host/cache_host_probe.py::to_workload_snapshot_kwargs()`` field-for-field so
    ``maybe_construct_workload_snapshot`` there can build a real instance from a live
    passive observation. Every other §7.3 field (strategy resolution, sizing, break-even
    inputs, existing-cache state, ...) is a Phase 1/decision-time concern with an honest
    UNKNOWN/None default here -- decision.py's algorithm treats every one of them as
    unknown-safe, never optimistic, per binding constraint #3.
    """
    schema: str = "synapse.cache_workload_snapshot/v1"
    schema_version: str = "1.0"
    node_path: str = UNKNOWN
    node_type: str = UNKNOWN
    context: str = Context.UNKNOWN.value

    # cache strategy resolution -- populated by strategies.resolve_strategy(), not stored
    # redundantly here; kept for callers who want to snapshot the resolution alongside the
    # workload for audit/serialization purposes.
    cache_strategy_id: str = UNKNOWN
    strategy_support: str = StrategySupport.UNKNOWN.value
    strategy_support_reasons: list = field(default_factory=list)

    frame_range: Optional[FrameRange] = None

    # passive observation evidence (host/cache_host_probe.py shape: Evidence dict or None)
    time_dependent: Any = None
    needs_to_cook: Any = None
    last_cook_seconds: Any = None
    geometry_memory_bytes: Any = None
    observation_status: str = UNKNOWN  # "clean_snapshot" | "dirty_not_forced" | "dirty_unknown" | UNKNOWN

    state_model: str = StateModel.UNKNOWN.value
    substeps: Any = UNKNOWN

    point_count: Any = UNKNOWN
    primitive_count: Any = UNKNOWN
    voxel_summary: Any = UNKNOWN

    peak_working_set_bytes: Any = None  # Evidence-wrapped Interval, or None = unknown
    gpu_relevance: str = GPURelevance.UNKNOWN.value
    gpu_relevance_evidence: Any = None

    estimated_output_bytes_per_frame: Optional[Interval] = None

    # Phase-0 addition (documented, not a blueprint field): lets a caller supply an
    # already-known compute/write/read range directly (e.g. a calibrated historical
    # aggregate) instead of forcing estimator.py to extrapolate from a single
    # last_cook_seconds sample. When absent, estimator.py extrapolates using
    # CachePolicy.single_sample_extrapolation_margin (named, documented, never a silent
    # magic number -- see policy_loader.py).
    compute_seconds_total: Optional[Interval] = None
    write_seconds_total: Optional[Interval] = None
    read_seconds_total: Optional[Interval] = None

    fanout_count: Any = UNKNOWN
    expected_future_reads: Any = UNKNOWN

    boundary_signals: Optional[BoundarySignals] = None
    existing_cache: Optional[ExistingCacheState] = None

    upstream_signature: Any = UNKNOWN
    external_dependencies: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------- CachePolicy (§7.4)

@dataclass
class CachePolicy:
    """§7.4. Conservative starting policy, not a physical law -- every threshold here is
    named, documented, and project-overridable via policy_loader.py. Never scatter a magic
    number through decision.py/estimator.py directly; add a named field here instead.
    """
    schema: str = "synapse.cache_policy/v1"
    schema_version: str = "1.0"
    minimum_seconds_saved: float = 30.0
    minimum_expected_future_reads: float = 1.0
    ram_safety_fraction: float = 0.80
    vram_safety_fraction: float = 0.85
    cache_size_safety_multiplier: float = 1.25
    minimum_free_disk_after_bytes: int = 21474836480  # 20 GiB
    minimum_free_disk_after_fraction: float = 0.10
    allow_low_confidence_bake_recommendation: bool = False
    allow_unmanifested_cache_load: bool = False
    preferred_cache_root: str = "$HIP/cache"
    network_cache_policy: str = "measure_or_override"
    retention_policy: str = "manual_manifest_scoped"
    # Phase-0 addition (documented, named -- see WorkloadSnapshot.compute_seconds_total):
    # fractional uncertainty margin applied ONLY when estimator.py must extrapolate a
    # single last_cook_seconds sample across an entire frame range. 0.15 = +/-15%.
    single_sample_extrapolation_margin: float = 0.15


NETWORK_CACHE_POLICY_VALUES = frozenset({"measure_or_override", "always_allow", "always_deny"})
RETENTION_POLICY_VALUES = frozenset({"manual_manifest_scoped", "auto_prune_lru", "never_delete"})


# --------------------------------------------------------------------------- CacheDecision (§7.5)

@dataclass
class Estimates:
    compute_seconds: Optional[Interval] = None
    write_seconds: Optional[Interval] = None
    read_seconds: Optional[Interval] = None
    cache_bytes: Optional[Interval] = None
    break_even_future_reads: Optional[Interval] = None

    def to_dict(self) -> dict:
        return {
            k: (v.to_dict() if v is not None else None)
            for k, v in (
                ("compute_seconds", self.compute_seconds),
                ("write_seconds", self.write_seconds),
                ("read_seconds", self.read_seconds),
                ("cache_bytes", self.cache_bytes),
                ("break_even_future_reads", self.break_even_future_reads),
            )
        }


@dataclass
class CacheDecision:
    """§7.5. ``reasons`` must be generated from rule IDs / structured facts by decision.py,
    never from free-form LLM prose (§17.2: "an LLM-generated explanation cannot alter the
    structured verdict passed to execution") -- this dataclass has no field an LLM can
    write into that changes ``verdict``/``boundary_action``/``bake_action``.
    """
    schema: str = "synapse.cache_decision/v1"
    schema_version: str = "1.0"
    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    verdict: str = CacheVerdict.UNKNOWN.value
    boundary_action: str = BoundaryAction.NONE.value
    bake_action: str = BakeAction.DO_NOT_BAKE.value
    cache_validity: str = CacheValidity.NOT_PRESENT.value
    strategy_id: str = UNKNOWN
    confidence: str = Confidence.UNKNOWN.value
    headline: str = ""
    reasons: list = field(default_factory=list)
    blockers: list = field(default_factory=list)
    missing_evidence: list = field(default_factory=list)
    estimates: Estimates = field(default_factory=Estimates)
    proposed_path: Any = UNKNOWN
    frame_range: Optional[dict] = None
    policy_version: str = "1.0"
    evidence_digest: str = UNKNOWN


# --------------------------------------------------------------------------- CacheManifest (§7.6)

@dataclass
class CacheManifestFiles:
    expected: Any = UNKNOWN
    written: Any = UNKNOWN
    total_bytes: Any = UNKNOWN
    listing_digest: Any = UNKNOWN


@dataclass
class CacheManifest:
    """§7.6. "Only complete plus matching signatures is automatically loadable" (§7.6) --
    decision.py never reads this dataclass directly; it consumes the (deliberately
    simpler) ExistingCacheState above. ``existing_cache_from_manifest`` bridges the two for
    callers that do have a real manifest.
    """
    schema: str = "synapse.cache_manifest/v1"
    schema_version: str = "1.0"
    cache_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = ManifestStatus.PLANNED.value
    strategy_id: str = UNKNOWN
    created_at: Any = UNKNOWN
    completed_at: Any = UNKNOWN
    houdini_version: str = UNKNOWN
    synapse_version: str = UNKNOWN
    scene_identity: Any = UNKNOWN
    source_node_path: str = UNKNOWN
    upstream_signature: Any = UNKNOWN
    external_dependency_digest: Any = UNKNOWN
    frame_range: Optional[dict] = None
    format: str = UNKNOWN
    files: CacheManifestFiles = field(default_factory=CacheManifestFiles)
    interrupted: bool = False


def existing_cache_from_manifest(manifest: Optional[CacheManifest],
                                  current_upstream_signature: Any) -> ExistingCacheState:
    """Bridges a CacheManifest into the simpler ExistingCacheState decision.py consumes.
    A manifest that does not exist at all is NOT_PRESENT; any manifest that DOES exist is,
    by construction, "manifested" (an unmanifested legacy cache is represented directly as
    ExistingCacheState(present=True, manifested=False), never via this function -- see
    §12.4 "unmanifested legacy cache: treat as unverifiable")."""
    if manifest is None:
        return ExistingCacheState(present=False, manifested=False)
    return ExistingCacheState(
        present=True,
        manifested=True,
        manifest_status=manifest.status,
        upstream_signature=manifest.upstream_signature,
        current_upstream_signature=current_upstream_signature,
    )


# --------------------------------------------------------------------------- generic (de)serialization

def to_jsonable(obj: Any) -> Any:
    """Recursively converts dataclasses/Enums/Interval/FrameRange/etc. into plain
    JSON-serializable primitives, WITHOUT relying on json's implicit (str, Enum) handling
    (kept explicit and testable on purpose -- see signatures.py's determinism tests).
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dc_fields(obj)}
    # last resort: best-effort string form (should not normally be reached by this package's
    # own types; kept so a stray unexpected value fails a determinism test loudly rather than
    # raising deep inside json.dumps).
    return str(obj)
