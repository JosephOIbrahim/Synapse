"""python/synapse/cache_policy/decision.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Implements ``decide_cache()``, the §10.1 deterministic policy algorithm, in the EXACT
evaluation order the blueprint specifies:

    1. strategy support
    2. existing-cache validity
    3. boundary value
    4. passive-evidence safety
    5. RAM feasibility
    6. GPU/VRAM feasibility (only if gpu_relevance == REQUIRED)
    7. size-estimate robustness
    8. disk headroom
    9. break-even value
    10. verdict from boundary + value

Order matters (§10.1 preamble: "Safety and validity must short-circuit performance
enthusiasm"). Do not reorder. tests/test_cache_policy.py::test_evaluation_order_* pins this.

Two gaps the blueprint's own pseudocode (§10.1) leaves implicit are filled in here,
documented at the point they're filled rather than silently:

  * RAM/VRAM "unknown" branches. §10.1's pseudocode shows an explicit
    ``if vram_is_unknown(machine): return measure_first_or_unknown(...)`` for the VRAM
    branch but has no symmetric statement for RAM, even though §10.3 says outright "If peak
    working set is unknown, do not claim it fits." This module adds the same
    unknown-first-then-exceeds shape to the RAM step, because leaving it out would let an
    unmeasured peak silently pass the RAM gate (`peak_high > safe` with `peak_high=None`
    would raise `TypeError`, or, worse, a naive `bool(None) -> False` reading would treat
    "unmeasured" as "does not exceed" -- optimistic-on-unknown, the exact anti-pattern
    binding constraint #3 and blueprint §4.5/§19 forbid). ``estimator.ram_feasibility``
    reports ``unknown=True`` explicitly for this reason.
  * ``UNSUPPORTED``/``NOT_PRESENT``/other short-circuit branches still populate a full
    ``CacheDecision`` (not a bare enum) so every return path is uniformly typed and
    serializable -- ``_build_decision`` is the single construction point.

Pure stdlib. No ``hou``, no Qt, no I/O (binding constraint #2 / §13.2 import boundaries).
"""
from __future__ import annotations

from typing import Any, List, Optional

from . import estimator
from .models import (
    BakeAction, BoundaryAction, CacheDecision, CachePolicy, CacheValidity, CacheVerdict,
    Confidence, Estimates, ExistingCacheState, GPURelevance, Interval, MachineProfile,
    NEGATIVE_BOUNDARY_SIGNALS, POSITIVE_BOUNDARY_SIGNALS, WorkloadSnapshot,
    evidence_value, is_unknown,
)
from .signatures import compute_evidence_digest
from .strategies import StrategyResolution

unwrap = evidence_value


# --------------------------------------------------------------------------- §12 existing-cache validity

def validate_existing_cache(existing: Optional[ExistingCacheState],
                             workload: WorkloadSnapshot) -> CacheValidity:
    """§12.1/§12.4: "files exist" never equals "cache valid". Unparametrized ``workload``
    is accepted (matching the §10.1 pseudocode's ``validate_existing_cache(workload.
    existing_cache, workload)`` signature) for forward-compatibility with a Phase 1 resolver
    that needs more than ``existing`` alone -- unused in Phase 0's implementation.
    """
    del workload  # unused in Phase 0; kept in the signature to match §10.1's call shape
    if existing is None or not existing.present:
        return CacheValidity.NOT_PRESENT
    if not existing.manifested:
        # §12.4: "unmanifested legacy cache: treat as unverifiable unless an import/
        # adoption workflow creates a manifest."
        return CacheValidity.UNVERIFIABLE
    status = existing.manifest_status
    if status == "partial":
        return CacheValidity.PARTIAL
    if status in ("failed", "cancelled"):
        return CacheValidity.CORRUPT
    if status != "complete":
        return CacheValidity.UNVERIFIABLE
    recorded_sig = existing.upstream_signature
    current_sig = existing.current_upstream_signature
    if is_unknown(recorded_sig) or is_unknown(current_sig):
        # §12.3: "If a dependency cannot be inspected, validity is unverifiable, not valid."
        return CacheValidity.UNVERIFIABLE
    if recorded_sig != current_sig:
        return CacheValidity.STALE
    return CacheValidity.VALID


# --------------------------------------------------------------------------- §10.2 boundary value

class BoundaryDecision:
    __slots__ = ("should_exist", "action", "reasons")

    def __init__(self, should_exist: bool, action: BoundaryAction, reasons: List[str]):
        self.should_exist = should_exist
        self.action = action
        self.reasons = reasons


def decide_boundary_value(workload: WorkloadSnapshot, policy: CachePolicy) -> BoundaryDecision:
    """§10.2: positive signals argue FOR a boundary; negative signals argue against one.
    An unevaluated signal (``None``) is never treated as a vote either way -- only an
    explicit ``True`` counts. A negative signal present with no positive signal present
    wins (no boundary); any positive signal present wins over no signals at all.
    """
    del policy  # no policy-level override in Phase 0
    sig = workload.boundary_signals
    if sig is None:
        return BoundaryDecision(should_exist=False, action=BoundaryAction.NONE,
                                 reasons=["no boundary signal evaluated"])
    positive = [name for name in POSITIVE_BOUNDARY_SIGNALS if getattr(sig, name) is True]
    negative = [name for name in NEGATIVE_BOUNDARY_SIGNALS if getattr(sig, name) is True]
    if positive:
        return BoundaryDecision(should_exist=True, action=BoundaryAction.INSERT, reasons=positive)
    if negative:
        return BoundaryDecision(should_exist=False, action=BoundaryAction.NONE, reasons=negative)
    return BoundaryDecision(should_exist=False, action=BoundaryAction.NONE,
                             reasons=["no boundary signal present"])


# --------------------------------------------------------------------------- §4/§8.2 passive-evidence safety

def passive_evidence_is_unsafe_or_missing(workload: WorkloadSnapshot) -> bool:
    """§4.2/§8.2/§19: never call ``geometry()`` on a dirty node, and never trust a decision
    built on evidence that observation could not safely obtain. Reads only fields
    ``host/cache_host_probe.py`` already populates (``needs_to_cook``, ``last_cook_seconds``,
    ``geometry_memory_bytes``) -- never re-derives dirtiness from ``observation_status``
    alone, since ``to_workload_snapshot_kwargs()`` does not currently forward that field.
    """
    needs = unwrap(workload.needs_to_cook)
    if needs is None:
        # needsToCook() itself failed/unknown -- neither branch is a green light (§8.2).
        return True
    if needs is True:
        # Dirty: safe to proceed only if genuine historical evidence backs the critical
        # fields (host probe's dirty branch never calls geometry() -- see its module
        # docstring -- so geometry_memory_bytes is only non-unknown via the
        # last_observation_store historical fallback).
        if is_unknown(workload.last_cook_seconds) and is_unknown(workload.geometry_memory_bytes):
            return True
        return False
    # needs is False (clean): still require the baseline cook-time evidence.
    return is_unknown(workload.last_cook_seconds)


# --------------------------------------------------------------------------- decision construction

def _evidence_digest_payload(machine: MachineProfile, workload: WorkloadSnapshot,
                              strategy: StrategyResolution, policy: CachePolicy,
                              estimates: Estimates) -> dict:
    """Excludes opaque/non-deterministic fields (profile_id, captured_at, decision_id,
    observed_at timestamps) so identical substantive inputs always produce an identical
    ``evidence_digest`` -- see signatures.py's determinism contract."""
    return {
        "machine": {
            "os_family": machine.os_family,
            "ram_total_bytes": machine.ram_total_bytes,
            "ram_available_bytes": machine.ram_available_bytes,
            "cache_volume_free_bytes": estimator.cache_volume_field(machine.cache_volume, "free_bytes"),
            "cache_volume_total_bytes": estimator.cache_volume_field(machine.cache_volume, "total_bytes"),
            "houdini_version": machine.houdini_version,
        },
        "workload": {
            "node_path": workload.node_path,
            "node_type": workload.node_type,
            "context": workload.context,
            "last_cook_seconds": unwrap(workload.last_cook_seconds),
            "expected_future_reads": unwrap(workload.expected_future_reads),
        },
        "strategy_id": strategy.strategy_id,
        "policy": {
            "ram_safety_fraction": policy.ram_safety_fraction,
            "vram_safety_fraction": policy.vram_safety_fraction,
            "cache_size_safety_multiplier": policy.cache_size_safety_multiplier,
            "minimum_seconds_saved": policy.minimum_seconds_saved,
            "minimum_expected_future_reads": policy.minimum_expected_future_reads,
        },
        "estimates": estimates.to_dict(),
    }


def _build_decision(*, verdict: CacheVerdict, boundary_action: BoundaryAction,
                     bake_action: BakeAction, cache_validity: CacheValidity,
                     strategy: StrategyResolution, confidence: Confidence, headline: str,
                     reasons: List[str], blockers: List[str], missing_evidence: List[str],
                     machine: MachineProfile, workload: WorkloadSnapshot, policy: CachePolicy,
                     estimates: Optional[Estimates] = None,
                     proposed_path: Any = None) -> CacheDecision:
    est = estimates or Estimates()
    frame_range = workload.frame_range.to_dict() if workload.frame_range is not None else None
    digest = compute_evidence_digest(
        _evidence_digest_payload(machine, workload, strategy, policy, est)
    )
    return CacheDecision(
        verdict=verdict.value,
        boundary_action=boundary_action.value,
        bake_action=bake_action.value,
        cache_validity=cache_validity.value,
        strategy_id=strategy.strategy_id,
        confidence=confidence.value,
        headline=headline,
        reasons=list(reasons),
        blockers=list(blockers),
        missing_evidence=list(missing_evidence),
        estimates=est,
        proposed_path=proposed_path if proposed_path is not None else "unknown",
        frame_range=frame_range,
        policy_version=policy.schema_version,
        evidence_digest=digest,
    )


# --------------------------------------------------------------------------- the algorithm (§10.1)

def decide_cache(machine: MachineProfile, workload: WorkloadSnapshot,
                  strategy: StrategyResolution, policy: CachePolicy) -> CacheDecision:
    """§10.1's ``decide_cache(machine, workload, strategy, policy)`` -- see this module's
    header for the exact evaluation order (never reorder) and for the two documented gap
    completions (RAM-unknown check, decision construction uniformity)."""

    # 1. strategy support
    if not strategy.supported:
        return _build_decision(
            verdict=CacheVerdict.UNSUPPORTED, boundary_action=BoundaryAction.NONE,
            bake_action=BakeAction.DO_NOT_BAKE, cache_validity=CacheValidity.NOT_PRESENT,
            strategy=strategy, confidence=Confidence.HIGH,
            headline=f"No validated cache strategy for context '{strategy.context}'",
            reasons=list(strategy.reasons), blockers=["no validated strategy"],
            missing_evidence=[], machine=machine, workload=workload, policy=policy,
        )

    # 2. existing-cache validity
    validity = validate_existing_cache(workload.existing_cache, workload)
    validity_notes: List[str] = []
    if validity == CacheValidity.VALID:
        return _build_decision(
            verdict=CacheVerdict.USE_VALID_CACHE, boundary_action=BoundaryAction.REUSE_EXISTING,
            bake_action=BakeAction.DO_NOT_BAKE, cache_validity=validity, strategy=strategy,
            confidence=Confidence.HIGH,
            headline="Existing cache matches current source and policy",
            reasons=["Existing manifest is complete and upstream signature matches"],
            blockers=[], missing_evidence=[], machine=machine, workload=workload, policy=policy,
        )
    if validity in (CacheValidity.STALE, CacheValidity.PARTIAL, CacheValidity.CORRUPT,
                    CacheValidity.UNVERIFIABLE):
        validity_notes.append(f"Existing cache validity is '{validity.value}' -- not usable as-is")

    # 3. boundary value
    boundary = decide_boundary_value(workload, policy)

    # 4. passive-evidence safety
    if passive_evidence_is_unsafe_or_missing(workload):
        return _build_decision(
            verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW,
            headline="Passive observation evidence is missing or unsafe to trust",
            reasons=["No forced cook was performed; dirty/unknown state has no valid historical fallback"] + validity_notes,
            blockers=[], missing_evidence=["cook-time or geometry-memory evidence"],
            machine=machine, workload=workload, policy=policy,
        )

    # 5. RAM feasibility (unknown-first, per this module's header)
    ram = estimator.ram_feasibility(machine, workload, policy)
    if ram.unknown:
        return _build_decision(
            verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW, headline="Peak working-set RAM evidence is unknown",
            reasons=["Cannot claim RAM feasibility without a measured peak working set"] + validity_notes,
            blockers=[], missing_evidence=["peak_working_set_bytes or machine RAM evidence"],
            machine=machine, workload=workload, policy=policy,
        )
    if ram.exceeds:
        return _build_decision(
            verdict=CacheVerdict.OPTIMIZE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.OPTIMIZE_FIRST, cache_validity=validity, strategy=strategy,
            confidence=Confidence.HIGH, headline="Predicted peak RAM exceeds safe available RAM",
            reasons=[
                f"Predicted peak {ram.predicted_peak:.0f} bytes exceeds safe available "
                f"{ram.safe_available:.0f} bytes",
                "A File Cache stores output after a frame computes; it cannot make an "
                "impossible frame fit into RAM (§2.4 memory law)",
            ] + validity_notes,
            blockers=["per-frame RAM"], missing_evidence=[],
            machine=machine, workload=workload, policy=policy,
        )

    # 6. GPU/VRAM feasibility, only if relevance is proven REQUIRED
    if workload.gpu_relevance == GPURelevance.REQUIRED.value:
        vram = estimator.vram_feasibility(machine, workload, policy)
        if vram.unknown:
            return _build_decision(
                verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
                bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
                confidence=Confidence.LOW, headline="VRAM evidence is unknown for a GPU-required workload",
                reasons=["gpu_relevance is REQUIRED but VRAM availability was not measured"] + validity_notes,
                blockers=[], missing_evidence=["VRAM availability"],
                machine=machine, workload=workload, policy=policy,
            )
        if vram.exceeds:
            return _build_decision(
                verdict=CacheVerdict.OPTIMIZE_FIRST, boundary_action=boundary.action,
                bake_action=BakeAction.OPTIMIZE_FIRST, cache_validity=validity, strategy=strategy,
                confidence=Confidence.HIGH, headline="Predicted peak VRAM exceeds safe available VRAM",
                reasons=[
                    f"Predicted peak {vram.predicted_peak:.0f} bytes exceeds safe available "
                    f"{vram.safe_available:.0f} bytes",
                    "GPU evidence is used only because relevance was proven REQUIRED, never "
                    "inferred from GPU name/model (§19)",
                ] + validity_notes,
                blockers=["per-frame VRAM"], missing_evidence=[],
                machine=machine, workload=workload, policy=policy,
            )

    # 7. size-estimate robustness
    size = estimator.estimate_sequence_size(workload)
    if not size.robust_enough:
        return _build_decision(
            verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW, headline="Output size estimate is not robust enough",
            reasons=["No fabricated size: estimated_output_bytes_per_frame or frame_range is unknown"] + validity_notes,
            blockers=[], missing_evidence=["estimated_output_bytes_per_frame", "frame_range"],
            machine=machine, workload=workload, policy=policy,
        )

    # 8. disk headroom
    required_headroom = estimator.disk_headroom(size.high, machine.cache_volume, policy)
    free_bytes = estimator.cache_volume_free_bytes(machine)
    cache_bytes_interval = Interval(low=size.low, high=size.high)
    if free_bytes is None:
        return _build_decision(
            verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW, headline="Cache volume free space is unknown",
            reasons=["Cannot verify disk headroom without a measured free_bytes value"] + validity_notes,
            blockers=[], missing_evidence=["cache_volume.free_bytes"],
            machine=machine, workload=workload, policy=policy,
            estimates=Estimates(cache_bytes=cache_bytes_interval),
        )
    if free_bytes < required_headroom:
        return _build_decision(
            verdict=CacheVerdict.INSUFFICIENT_DISK, boundary_action=boundary.action,
            bake_action=BakeAction.DO_NOT_BAKE, cache_validity=validity, strategy=strategy,
            confidence=Confidence.HIGH, headline="Target volume lacks required headroom",
            reasons=[
                f"Required headroom {required_headroom:.0f} bytes (high estimate + policy "
                f"reserve) exceeds free space {free_bytes:.0f} bytes",
            ] + validity_notes,
            blockers=["insufficient disk"], missing_evidence=[],
            machine=machine, workload=workload, policy=policy,
            estimates=Estimates(cache_bytes=cache_bytes_interval),
        )

    # 9. break-even value
    value = estimator.evaluate_break_even(workload, policy)
    estimates_so_far = Estimates(
        compute_seconds=value.compute_seconds, write_seconds=value.write_seconds,
        read_seconds=value.read_seconds, cache_bytes=cache_bytes_interval,
        break_even_future_reads=value.break_even_future_reads,
    )
    if value.is_unknown:
        return _build_decision(
            verdict=CacheVerdict.MEASURE_FIRST, boundary_action=boundary.action,
            bake_action=BakeAction.MEASURE_THEN_REASSESS, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW, headline="Break-even evidence is insufficient",
            reasons=["compute/write/read seconds or expected_future_reads are unknown"] + validity_notes,
            blockers=[], missing_evidence=["compute_seconds_total/write_seconds_total/read_seconds_total or expected_future_reads"],
            machine=machine, workload=workload, policy=policy, estimates=estimates_so_far,
        )
    if not value.is_worthwhile and not value.non_performance_justification:
        return _build_decision(
            verdict=CacheVerdict.NOT_WORTH_IT, boundary_action=boundary.action,
            bake_action=BakeAction.DO_NOT_BAKE, cache_validity=validity, strategy=strategy,
            confidence=Confidence.MEDIUM, headline="Expected savings do not exceed cost or policy threshold",
            reasons=["Break-even future-reads requirement is not cleared by expected_future_reads"] + validity_notes,
            blockers=[], missing_evidence=[],
            machine=machine, workload=workload, policy=policy, estimates=estimates_so_far,
        )

    # 10. verdict from boundary + value
    #
    # STRUCTURAL FIX (post-CLEAR follow-up, reviewer-flagged): the blueprint's own §10.1
    # pseudocode distinguishes `value.is_worthwhile` (used at step 9's not_worth_it gate)
    # from a SEPARATE `value.feasible` (used here: "if boundary.should_exist and
    # value.feasible: cache_now(...)"). An earlier version of this function defined
    # `feasible = value.is_worthwhile or value.non_performance_justification` -- BUT
    # step 9 already returns NOT_WORTH_IT precisely when that same expression is False
    # (De Morgan's: `not A and not B` failing to fire means `A or B` is already True by
    # the time step 10 runs). Reusing the identical expression made `feasible` always
    # True here, which collapsed `if boundary.should_exist and feasible` to
    # `if boundary.should_exist`, and then the `if boundary.should_exist:
    # INSERT_BOUNDARY_ONLY` branch below it could never be reached -- CacheVerdict.
    # INSERT_BOUNDARY_ONLY, one of the nine documented §6.1 public verdicts, was DEAD
    # CODE start to finish, both before and after the showstopper-2 confidence-gate fix.
    #
    # Fixed by making `feasible` a genuinely NARROWER condition than the step-9 gate:
    # "confident enough, right now, to justify an actual bake" -- true when the
    # break-even math itself proves out (`is_worthwhile`), OR when only a non-performance
    # justification applies AND policy explicitly permits acting on that at low
    # confidence (§6.3's escape hatch, the same policy.allow_low_confidence_bake_
    # recommendation switch showstopper 2 wired). This reopens a real gap between the
    # step-9 gate (has ANY justification) and this one (confident enough to bake NOW),
    # which is exactly where INSERT_BOUNDARY_ONLY belongs: boundary.should_exist is True,
    # some justification exists (guaranteed by step 9), but not one confident/permitted
    # enough to write to disk without another look.
    feasible = value.is_worthwhile or (
        value.non_performance_justification and policy.allow_low_confidence_bake_recommendation
    )
    cache_now_confidence = Confidence.MEDIUM if value.is_worthwhile else Confidence.LOW

    if boundary.should_exist and feasible:
        return _build_decision(
            verdict=CacheVerdict.CACHE_NOW, boundary_action=boundary.action,
            bake_action=BakeAction.BAKE_AFTER_APPROVAL, cache_validity=validity, strategy=strategy,
            confidence=cache_now_confidence,
            headline="Cache recommended", reasons=list(boundary.reasons) + validity_notes,
            blockers=[], missing_evidence=[],
            machine=machine, workload=workload, policy=policy, estimates=estimates_so_far,
        )
    if boundary.should_exist:
        # Reached only when: boundary.should_exist is True, and step 9 already proved
        # (is_worthwhile or non_performance_justification), but `feasible` above is
        # False -- which by construction only happens when is_worthwhile is False AND
        # non_performance_justification is True AND policy.allow_low_confidence_bake_
        # recommendation is False. §6.1: "A boundary is architecturally useful, but
        # baking now is not justified or not yet feasible. -> Insert under undo; do not
        # bake." -- exactly this state, not "go measure something" (nothing further to
        # measure here; every input is already known, per steps 4-9's unknown-checks all
        # having passed).
        return _build_decision(
            verdict=CacheVerdict.INSERT_BOUNDARY_ONLY, boundary_action=boundary.action,
            bake_action=BakeAction.DO_NOT_BAKE, cache_validity=validity, strategy=strategy,
            confidence=Confidence.LOW,
            headline="Boundary is architecturally useful; baking now is not yet justified",
            reasons=(
                list(boundary.reasons)
                + ["Feasible only via non-performance justification at low confidence; "
                   "policy.allow_low_confidence_bake_recommendation is False"]
                + validity_notes
            ),
            blockers=[], missing_evidence=[],
            machine=machine, workload=workload, policy=policy, estimates=estimates_so_far,
        )
    # boundary.should_exist is False: matches the blueprint's own §10.1 pseudocode
    # fallback verbatim -- no qualitative boundary signal was ever recognized, so no
    # cache is recommended regardless of how the economics alone would read.
    return _build_decision(
        verdict=CacheVerdict.NOT_WORTH_IT, boundary_action=BoundaryAction.NONE,
        bake_action=BakeAction.DO_NOT_BAKE, cache_validity=validity, strategy=strategy,
        confidence=Confidence.MEDIUM, headline="No boundary signal justifies a cache here",
        reasons=list(boundary.reasons) + validity_notes, blockers=[], missing_evidence=[],
        machine=machine, workload=workload, policy=policy, estimates=estimates_so_far,
    )
