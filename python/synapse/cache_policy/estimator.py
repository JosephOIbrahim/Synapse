"""python/synapse/cache_policy/estimator.py -- Mile 2 (resource-aware-cache Phase 0), R-CACHE-1.

Implements the §2.3 break-even model and the §10.3 feasibility formulas EXACTLY as derived
from the blueprint's own stated formulas. Binding constraint #7 / adjudication e7 (REJECT):
this module NEVER copies a numeric fixture from the blueprint's §7.5/§14.1/§18 worked
examples -- those are independently confirmed arithmetically broken (adjudication e7,
Challenge 13: five separate arithmetic contradictions verified by direct calculation).
Every fixture in tests/test_cache_estimator.py is computed fresh from these formulas.

Pure stdlib. No ``hou``, no Qt, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .models import (
    CachePolicy, CacheVolume, GPUDevice, Interval, MachineProfile, WorkloadSnapshot,
    evidence_value, is_unknown,
)

unwrap = evidence_value  # local alias matching the rest of this module's vocabulary


# --------------------------------------------------------------------------- §10.3 formulas, verbatim

def estimated_sequence_bytes_high(estimated_output_bytes_per_frame_high: float,
                                   expected_frame_count: int) -> float:
    """§10.3: ``estimated_sequence_bytes_high = estimated_output_bytes_per_frame_high *
    expected_frame_count``."""
    return estimated_output_bytes_per_frame_high * expected_frame_count


def required_free_before_bake(estimated_sequence_bytes_high_value: float,
                               cache_size_safety_multiplier: float,
                               minimum_free_disk_after_bytes: float,
                               volume_total_bytes: float,
                               minimum_free_disk_after_fraction: float) -> float:
    """§10.3: ``required_free_before_bake = estimated_sequence_bytes_high *
    cache_size_safety_multiplier + max(minimum_free_disk_after_bytes, volume_total_bytes *
    minimum_free_disk_after_fraction)``."""
    return (
        estimated_sequence_bytes_high_value * cache_size_safety_multiplier
        + max(minimum_free_disk_after_bytes, volume_total_bytes * minimum_free_disk_after_fraction)
    )


def safe_available_ram(ram_available_now: float, ram_total: float,
                        ram_safety_fraction: float) -> float:
    """§10.3: ``safe_available_ram = min(ram_available_now, ram_total *
    ram_safety_fraction)``."""
    return min(ram_available_now, ram_total * ram_safety_fraction)


def safe_available_vram(vram_available_now: float, vram_total: float,
                         vram_safety_fraction: float) -> float:
    """VRAM analog of ``safe_available_ram`` -- §10.3 states only the RAM formula
    explicitly; §10.1's evaluation order treats VRAM symmetrically ("predicted_peak_vram_
    exceeds_safe_available"), so the same min(available, total*fraction) shape applies."""
    return min(vram_available_now, vram_total * vram_safety_fraction)


# --------------------------------------------------------------------------- §2.3 break-even model

def break_even_reads_required(write_seconds: float, compute_seconds: float,
                               read_seconds: float) -> Optional[float]:
    """§2.3: ``R_break-even = Tw / (Tc - Tr)``, defined only when ``Tc > Tr``. Returns None
    (never a fabricated number) when ``Tc <= Tr`` -- that case has no speed break-even and
    must be handled by the non-performance-justification path (``workflow_requires_
    persistence``), per §2.3: "If Tc <= Tr, the cache has no speed benefit ... The decision
    explanation must name that non-performance reason."
    """
    denominator = compute_seconds - read_seconds
    if denominator <= 0:
        return None
    return write_seconds / denominator


def break_even_envelope(write_seconds: Interval, compute_seconds: Interval,
                         read_seconds: Interval) -> Optional[Interval]:
    """Interval form of ``break_even_reads_required``. To bound R_break-even = Tw/(Tc-Tr)
    from independent low/high triples, the EASIEST-to-justify extreme pairs the smallest
    numerator with the largest denominator, and the HARDEST-to-justify extreme pairs the
    largest numerator with the smallest denominator:

        low  = Tw.low  / (Tc.high - Tr.low)
        high = Tw.high / (Tc.low  - Tr.high)

    Returns None if the "high" pairing's denominator is <= 0 (Tc.low <= Tr.high somewhere
    in the envelope -- part of the range has no speed benefit at all, so no single interval
    honestly bounds it; callers fall back to the point form per-scenario or to
    ``workflow_requires_persistence``).
    """
    low_denominator = compute_seconds.high - read_seconds.low
    high_denominator = compute_seconds.low - read_seconds.high
    if low_denominator <= 0 or high_denominator <= 0:
        return None
    low = write_seconds.low / low_denominator
    high = write_seconds.high / high_denominator
    if low > high:
        low, high = high, low
    return Interval(low=low, high=high)


def predicted_seconds_saved_conservative(expected_future_reads: float,
                                          compute_seconds: Interval,
                                          read_seconds: Interval) -> float:
    """Conservative (low) estimate of total wall-clock seconds a cache would save:
    ``R * (Tc.low - Tr.high)`` -- the smallest plausible per-replay saving (fastest
    recompute, slowest cache read), summed over R replays. Only called when an envelope
    was computable, which by ``break_even_envelope``'s own guard already guarantees
    ``compute_seconds.low > read_seconds.high``, so this is always non-negative here."""
    return expected_future_reads * (compute_seconds.low - read_seconds.high)


def is_worthwhile(expected_future_reads: float, break_even: Interval,
                   minimum_expected_future_reads: float, *,
                   predicted_seconds_saved: Optional[float] = None,
                   minimum_seconds_saved: float = 0.0) -> bool:
    """Conservative: worthwhile only when R clears the HARDER (higher) end of the
    break-even envelope AND the policy-declared minimum-reads floor AND (fixed post-review,
    crucible weakness 5) the policy-declared minimum-ABSOLUTE-seconds-saved floor
    (``CachePolicy.minimum_seconds_saved``) -- clearing the break-even RATIO alone does not
    imply a meaningful ABSOLUTE saving (e.g. R=1,000,000 clearing the ratio on a workload
    that only saves 0.001s total is still not worth the operational complexity §2.1 names).
    Before this fix, ``minimum_seconds_saved`` was validated by policy_loader and carried in
    the evidence digest but never actually compared against a predicted saving -- present in
    the audit trail, absent from the decision.
    """
    if expected_future_reads < minimum_expected_future_reads:
        return False
    if not (expected_future_reads > break_even.high):
        return False
    if predicted_seconds_saved is not None and predicted_seconds_saved < minimum_seconds_saved:
        return False
    return True


# --------------------------------------------------------------------------- size estimation (§10.3/§11)

@dataclass(frozen=True)
class SizeEstimate:
    low: Optional[float]
    high: Optional[float]
    robust_enough: bool
    method: str


def estimate_sequence_size(workload: WorkloadSnapshot) -> SizeEstimate:
    """§11.1 estimation ladder, Phase-0-reachable rungs only (existing manifest / sample
    write / calibrated-relationship rungs require I/O this pure module never performs --
    a Phase 1 caller resolves those and passes the result via
    ``estimated_output_bytes_per_frame`` before calling decide_cache)."""
    per_frame = workload.estimated_output_bytes_per_frame
    frame_range = workload.frame_range
    if per_frame is None or frame_range is None:
        return SizeEstimate(low=None, high=None, robust_enough=False, method="unknown")
    frame_count = frame_range.frame_count
    if frame_count <= 0:
        return SizeEstimate(low=None, high=None, robust_enough=False, method="unknown")
    low = per_frame.low * frame_count
    high = estimated_sequence_bytes_high(per_frame.high, frame_count)
    return SizeEstimate(low=low, high=high, robust_enough=True, method="per_frame_interval*frame_count")


def disk_headroom(sequence_bytes_high: float, cache_volume: Any, policy: CachePolicy) -> float:
    """Wraps ``required_free_before_bake`` reading ``volume_total_bytes`` off a CacheVolume
    (dataclass or duck-typed dict). Returns ``float("inf")`` (never satisfiable) when the
    volume's total size is unknown -- the caller (decision.py) must treat that as "cannot
    prove headroom", not as "assume it fits"."""
    total = cache_volume_field(cache_volume, "total_bytes")
    total_value = unwrap(total)
    if total_value is None or total_value == "unknown":
        return float("inf")
    return required_free_before_bake(
        sequence_bytes_high,
        policy.cache_size_safety_multiplier,
        policy.minimum_free_disk_after_bytes,
        total_value,
        policy.minimum_free_disk_after_fraction,
    )


def cache_volume_field(cache_volume: Any, name: str) -> Any:
    """Duck-typed accessor: CacheVolume dataclass or the raw dict shape
    ``host/cache_host_probe.py``'s ``_detect_cache_volume`` emits."""
    if isinstance(cache_volume, dict):
        return cache_volume.get(name)
    return getattr(cache_volume, name, None)


def cache_volume_free_bytes(machine: MachineProfile) -> Any:
    return unwrap(cache_volume_field(machine.cache_volume, "free_bytes"))


# --------------------------------------------------------------------------- RAM / VRAM feasibility

@dataclass(frozen=True)
class FeasibilityCheck:
    unknown: bool
    exceeds: bool
    predicted_peak: Optional[float] = None
    safe_available: Optional[float] = None


def ram_feasibility(machine: MachineProfile, workload: WorkloadSnapshot,
                     policy: CachePolicy) -> FeasibilityCheck:
    """§10.1/§10.3. "If peak working set is unknown, do not claim it fits" (§10.3) -- an
    unknown peak, or unknown machine RAM evidence, reports ``unknown=True`` rather than
    silently passing the check. This is the completion referenced in decision.py's
    docstring for the pseudocode's implicit RAM-unknown gap.
    """
    peak_raw = unwrap(workload.peak_working_set_bytes)
    peak_high = peak_raw.high if isinstance(peak_raw, Interval) else peak_raw
    ram_available = unwrap(machine.ram_available_bytes)
    ram_total = unwrap(machine.ram_total_bytes)
    if peak_high is None or ram_available is None or ram_total is None:
        return FeasibilityCheck(unknown=True, exceeds=False)
    safe = safe_available_ram(ram_available, ram_total, policy.ram_safety_fraction)
    return FeasibilityCheck(unknown=False, exceeds=peak_high > safe,
                             predicted_peak=peak_high, safe_available=safe)


def vram_feasibility(machine: MachineProfile, workload: WorkloadSnapshot,
                      policy: CachePolicy) -> FeasibilityCheck:
    """Same shape as ``ram_feasibility`` for the ``gpu_relevance == REQUIRED`` branch only
    (decision.py gates the call on that). §7.2: "include VRAM only if measured" -- an
    absent/`unknown`-valued device entry, or a missing ``vram_available_bytes`` (which no
    shipped Phase-0 probe currently populates -- see models.GPUDevice's docstring), reports
    ``unknown=True``.
    """
    peak_raw = unwrap(workload.peak_working_set_bytes)  # Phase 0 has no separate VRAM
    # working-set field distinct from the general peak estimate; a Phase 1 strategy may add
    # one. Using the same peak estimate here is a documented simplification, not a silent
    # substitution -- decision.py only reaches this branch when gpu_relevance == REQUIRED,
    # meaning the workload's peak working set IS the GPU-resident one by construction.
    peak_high = peak_raw.high if isinstance(peak_raw, Interval) else peak_raw
    devices = machine.gpu_devices or []
    if not devices or peak_high is None:
        return FeasibilityCheck(unknown=True, exceeds=False)
    device = devices[0]
    vram_total = unwrap(_gpu_field(device, "vram_bytes"))
    vram_available = unwrap(_gpu_field(device, "vram_available_bytes"))
    if vram_total is None or vram_available is None:
        return FeasibilityCheck(unknown=True, exceeds=False)
    safe = safe_available_vram(vram_available, vram_total, policy.vram_safety_fraction)
    return FeasibilityCheck(unknown=False, exceeds=peak_high > safe,
                             predicted_peak=peak_high, safe_available=safe)


def _gpu_field(device: Any, name: str) -> Any:
    if isinstance(device, dict):
        return device.get(name)
    return getattr(device, name, None)


# --------------------------------------------------------------------------- break-even evaluation

@dataclass(frozen=True)
class BreakEvenResult:
    is_unknown: bool
    is_worthwhile: bool
    compute_seconds: Optional[Interval] = None
    write_seconds: Optional[Interval] = None
    read_seconds: Optional[Interval] = None
    break_even_future_reads: Optional[Interval] = None
    non_performance_justification: bool = False


def _extrapolate_compute_seconds(workload: WorkloadSnapshot,
                                  policy: CachePolicy) -> Optional[Interval]:
    """Falls back to (last_cook_seconds * frame_count) with the named
    ``single_sample_extrapolation_margin`` when no explicit ``compute_seconds_total`` was
    supplied -- see WorkloadSnapshot.compute_seconds_total's docstring."""
    if workload.compute_seconds_total is not None:
        return workload.compute_seconds_total
    per_frame = unwrap(workload.last_cook_seconds)
    if per_frame is None or workload.frame_range is None:
        return None
    frame_count = workload.frame_range.frame_count
    if frame_count <= 0:
        return None
    point = per_frame * frame_count
    margin = policy.single_sample_extrapolation_margin
    return Interval(low=point * (1.0 - margin), high=point * (1.0 + margin))


def evaluate_break_even(workload: WorkloadSnapshot, policy: CachePolicy) -> BreakEvenResult:
    """§2.3 break-even model, applied at the whole-sequence level (consistent with §18
    Example A, which sums over the full 240-frame range rather than per-frame). NEVER
    reuses a §7.5/§14.1/§18 numeric fixture -- see this module's header and binding
    constraint #7.
    """
    compute = _extrapolate_compute_seconds(workload, policy)
    write = workload.write_seconds_total
    read = workload.read_seconds_total
    if compute is None or write is None or read is None:
        return BreakEvenResult(is_unknown=True, is_worthwhile=False)

    # Fixed post-review (crucible weakness 7): non_performance_justification is a real
    # justification axis independent of whether a speed-benefit envelope happens to be
    # computable (§2.3 names it explicitly for the Tc<=Tr case, but a checkpoint/handoff/
    # nondeterministic-source need does not evaporate just because Tc>Tr elsewhere in the
    # workload -- e.g. R is simply too small to clear the ratio). Computed once, used on
    # every return path below, not only the envelope-is-None branch.
    non_perf = workflow_requires_persistence(workload)

    envelope = break_even_envelope(write, compute, read)
    r = unwrap(workload.expected_future_reads)
    if envelope is None:
        # Tc <= Tr somewhere in the envelope: no speed benefit provable. Only a documented
        # non-performance reason can justify persistence (§2.3).
        return BreakEvenResult(
            is_unknown=False, is_worthwhile=False,
            compute_seconds=compute, write_seconds=write, read_seconds=read,
            break_even_future_reads=None, non_performance_justification=non_perf,
        )
    if r is None or r == "unknown":
        return BreakEvenResult(is_unknown=True, is_worthwhile=False,
                                compute_seconds=compute, write_seconds=write, read_seconds=read,
                                break_even_future_reads=envelope,
                                non_performance_justification=non_perf)
    predicted_saved = predicted_seconds_saved_conservative(r, compute, read)
    worthwhile = is_worthwhile(
        r, envelope, policy.minimum_expected_future_reads,
        predicted_seconds_saved=predicted_saved,
        minimum_seconds_saved=policy.minimum_seconds_saved,
    )
    return BreakEvenResult(
        is_unknown=False, is_worthwhile=worthwhile,
        compute_seconds=compute, write_seconds=write, read_seconds=read,
        break_even_future_reads=envelope, non_performance_justification=non_perf,
    )


def workflow_requires_persistence(workload: WorkloadSnapshot) -> bool:
    """§2.3: handoff / reproducibility / checkpointing / fault-recovery reasons that
    justify a boundary even with no speed benefit. Reuses the boundary-signal vocabulary
    (§10.2) rather than inventing a parallel flag."""
    sig = workload.boundary_signals
    if sig is None:
        return False
    return bool(
        sig.cross_department_handoff
        or sig.checkpoint_recovery_required
        or sig.nondeterministic_or_externally_expensive_source
    )
