"""Mile 2 (resource-aware-cache Phase 0, R-CACHE-1) -- tests for
``synapse.cache_policy.estimator``.

Covers the §2.3 break-even model and the §10.3 feasibility formulas. Binding constraint #7 /
adjudication e7 (REJECT), restated in estimator.py's own header: every numeric fixture here
is computed FRESH from the formulas in this file -- NONE is copied from the blueprint's
§7.5/§14.1/§18 worked examples, which are independently confirmed arithmetically broken
(adjudication e7, Challenge 13: five separate contradictions verified by direct calculation,
e.g. the break-even envelope claimed there as {0.31, 0.55} does not reproduce from its own
stated intervals -- the correct reproduction is {0.273, 0.570}). This file's fixtures use
different numbers throughout and each expected result is derived by the test itself, not
transcribed from any external document.

Pure stdlib. No ``hou``, no Qt.

Every test states the condition under which it fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from synapse.cache_policy import estimator  # noqa: E402
from synapse.cache_policy.models import (  # noqa: E402
    BoundarySignals,
    CachePolicy,
    Evidence,
    FrameRange,
    GPURelevance,
    Interval,
    MachineProfile,
    WorkloadSnapshot,
)


# --------------------------------------------------------------------------- §10.3 formulas, verbatim

def test_estimated_sequence_bytes_high_matches_the_formula():
    """Fails if the formula's multiplication is wrong or its argument order is swapped --
    estimated_sequence_bytes_high = per_frame_high * frame_count."""
    assert estimator.estimated_sequence_bytes_high(2_000_000.0, 500) == 1_000_000_000.0


def test_required_free_before_bake_uses_max_of_the_two_reserve_terms_low():
    """Fails if the max() in required_free_before_bake is inverted or dropped -- when the
    fixed-byte floor exceeds the fractional reserve, the floor must win."""
    seq_high = 100_000_000_000.0  # 100 GB
    multiplier = 1.25
    fixed_floor = 20_000_000_000.0   # 20 GB fixed floor
    volume_total = 200_000_000_000.0  # 200 GB
    fraction = 0.05  # fractional reserve = 10 GB, LESS than the fixed floor
    result = estimator.required_free_before_bake(seq_high, multiplier, fixed_floor,
                                                  volume_total, fraction)
    expected = seq_high * multiplier + fixed_floor  # 20GB floor wins over 10GB fraction
    assert result == expected


def test_required_free_before_bake_uses_max_of_the_two_reserve_terms_high():
    """Fails if the max() in required_free_before_bake ignores the fractional term when IT
    is the larger of the two."""
    seq_high = 100_000_000_000.0
    multiplier = 1.25
    fixed_floor = 5_000_000_000.0    # 5 GB fixed floor, SMALL
    volume_total = 400_000_000_000.0  # 400 GB
    fraction = 0.10  # fractional reserve = 40 GB, LARGER than the fixed floor
    result = estimator.required_free_before_bake(seq_high, multiplier, fixed_floor,
                                                  volume_total, fraction)
    expected = seq_high * multiplier + (volume_total * fraction)
    assert result == expected


def test_safe_available_ram_matches_the_formula():
    """Fails if safe_available_ram does not implement min(available, total*fraction)."""
    assert estimator.safe_available_ram(50_000_000_000.0, 128_000_000_000.0, 0.80) == 50_000_000_000.0
    assert estimator.safe_available_ram(120_000_000_000.0, 128_000_000_000.0, 0.80) == 102_400_000_000.0


def test_safe_available_vram_matches_the_formula():
    """Fails if safe_available_vram diverges from the RAM formula's shape."""
    assert estimator.safe_available_vram(10_000_000_000.0, 24_000_000_000.0, 0.85) == 10_000_000_000.0
    assert estimator.safe_available_vram(23_000_000_000.0, 24_000_000_000.0, 0.85) == 20_400_000_000.0


# --------------------------------------------------------------------------- §2.3 break-even model

def test_break_even_reads_required_matches_the_formula():
    """Fails if break_even_reads_required does not compute Tw / (Tc - Tr) exactly.
    Independently derived fixture: Tw=90, Tc=500, Tr=100 -> 90 / 400 = 0.225.
    """
    assert estimator.break_even_reads_required(90.0, 500.0, 100.0) == 0.225


def test_break_even_reads_required_returns_none_when_tc_equals_tr():
    """Fails if Tc == Tr does not produce None -- §2.3: 'the cache has no speed benefit' in
    this case, and the formula's denominator is zero."""
    assert estimator.break_even_reads_required(90.0, 300.0, 300.0) is None


def test_break_even_reads_required_returns_none_when_tc_less_than_tr():
    """Fails if a negative denominator (Tc < Tr, reading is SLOWER than recomputing --
    e.g. a badly-throttled network cache volume) silently returns a negative or fabricated
    break-even instead of None."""
    assert estimator.break_even_reads_required(90.0, 100.0, 300.0) is None


def test_break_even_envelope_matches_hand_derivation():
    """Independently derived fixture (NOT from the blueprint's worked example -- see this
    file's header): Tw=(300,450), Tc=(1200,1400), Tr=(100,160).
        low  = Tw.low  / (Tc.high - Tr.low)  = 300 / (1400-100)  = 300/1300  ~= 0.230769
        high = Tw.high / (Tc.low  - Tr.high) = 450 / (1200-160)  = 450/1040  ~= 0.432692
    Fails if either bound diverges from this hand-derived value, or if low/high are swapped.
    """
    envelope = estimator.break_even_envelope(
        write_seconds=Interval(300.0, 450.0),
        compute_seconds=Interval(1200.0, 1400.0),
        read_seconds=Interval(100.0, 160.0),
    )
    assert envelope is not None
    assert abs(envelope.low - (300.0 / 1300.0)) < 1e-9
    assert abs(envelope.high - (450.0 / 1040.0)) < 1e-9
    assert envelope.low < envelope.high


def test_break_even_envelope_returns_none_when_worst_case_denominator_nonpositive():
    """Fails if the envelope silently produces a bogus (e.g. negative or infinite) bound
    instead of None when part of the input range has no speed benefit at all
    (Tc.low <= Tr.high)."""
    envelope = estimator.break_even_envelope(
        write_seconds=Interval(100.0, 200.0),
        compute_seconds=Interval(50.0, 500.0),   # Tc.low = 50
        read_seconds=Interval(60.0, 400.0),      # Tr.high = 400 > Tc.low
    )
    assert envelope is None


def test_is_worthwhile_requires_clearing_the_high_break_even_and_the_policy_minimum():
    """Fails if is_worthwhile clears on the optimistic (low) bound alone -- safety must
    short-circuit performance enthusiasm (blueprint §10.1 preamble): worthwhile requires R
    to exceed the HARDER (high) end of the envelope."""
    envelope = Interval(low=0.5, high=2.0)
    assert estimator.is_worthwhile(1.0, envelope, minimum_expected_future_reads=1.0) is False, (
        "R=1.0 clears the optimistic bound (0.5) but not the conservative one (2.0) -- must not be worthwhile"
    )
    assert estimator.is_worthwhile(3.0, envelope, minimum_expected_future_reads=1.0) is True


def test_is_worthwhile_respects_policy_minimum_even_above_break_even():
    """Fails if a policy-declared minimum_expected_future_reads floor is ignored when R
    technically clears the break-even envelope."""
    envelope = Interval(low=0.1, high=0.2)
    assert estimator.is_worthwhile(0.5, envelope, minimum_expected_future_reads=2.0) is False


# --------------------------------------------------------------------------- evaluate_break_even integration

def _policy(**overrides) -> CachePolicy:
    base = CachePolicy()
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def test_evaluate_break_even_is_unknown_when_write_or_read_seconds_absent():
    """Fails if missing write/read totals are silently treated as zero instead of unknown --
    the exact 'never a zero-valued fake evidence' defect class (§17.2)."""
    workload = WorkloadSnapshot(
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=100),
        expected_future_reads=3,
        # write_seconds_total / read_seconds_total left at default None
    )
    result = estimator.evaluate_break_even(workload, _policy())
    assert result.is_unknown is True


def test_evaluate_break_even_is_worthwhile_true_for_a_clearly_valuable_sequence():
    """Independently derived: compute=(1000,1100), write=(80,120), read=(10,20), R=5.
    high bound = 120/(1000-20) = 120/980 ~= 0.1224 -- R=5 clears it easily."""
    workload = WorkloadSnapshot(
        compute_seconds_total=Interval(1000.0, 1100.0),
        write_seconds_total=Interval(80.0, 120.0),
        read_seconds_total=Interval(10.0, 20.0),
        expected_future_reads=5,
    )
    result = estimator.evaluate_break_even(workload, _policy())
    assert result.is_unknown is False
    assert result.is_worthwhile is True


def test_evaluate_break_even_not_worthwhile_for_a_marginal_sequence():
    """Independently derived: compute=(100,110), write=(80,120), read=(10,20), R=1.
    high bound = 120/(100-20) = 1.5 -- R=1 does not clear it."""
    workload = WorkloadSnapshot(
        compute_seconds_total=Interval(100.0, 110.0),
        write_seconds_total=Interval(80.0, 120.0),
        read_seconds_total=Interval(10.0, 20.0),
        expected_future_reads=1,
    )
    result = estimator.evaluate_break_even(workload, _policy())
    assert result.is_unknown is False
    assert result.is_worthwhile is False


def test_evaluate_break_even_extrapolates_from_last_cook_seconds_when_no_explicit_total():
    """Fails if a single last_cook_seconds sample cannot drive a compute_seconds_total
    extrapolation via the named single_sample_extrapolation_margin -- this is the fallback
    path host-probe-only callers rely on."""
    workload = WorkloadSnapshot(
        last_cook_seconds=Evidence.known(2.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=100),  # 100 frames
        write_seconds_total=Interval(5.0, 10.0),
        read_seconds_total=Interval(1.0, 2.0),
        expected_future_reads=10,
    )
    policy = _policy(single_sample_extrapolation_margin=0.10)
    result = estimator.evaluate_break_even(workload, policy)
    assert result.is_unknown is False
    point = 2.0 * 100  # 200
    assert result.compute_seconds.low == point * 0.90
    assert result.compute_seconds.high == point * 1.10


def test_evaluate_break_even_non_performance_justification_when_no_speed_benefit():
    """Fails if a Tc<=Tr scenario with a checkpoint/handoff boundary signal does not report
    non_performance_justification=True per §2.3's explicit non-performance carve-out."""
    workload = WorkloadSnapshot(
        compute_seconds_total=Interval(50.0, 60.0),
        write_seconds_total=Interval(10.0, 15.0),
        read_seconds_total=Interval(55.0, 70.0),  # Tr >= Tc: no speed benefit
        expected_future_reads=5,
        boundary_signals=BoundarySignals(checkpoint_recovery_required=True),
    )
    result = estimator.evaluate_break_even(workload, _policy())
    assert result.is_unknown is False
    assert result.is_worthwhile is False
    assert result.non_performance_justification is True


def test_workflow_requires_persistence_false_with_no_signals():
    assert estimator.workflow_requires_persistence(WorkloadSnapshot()) is False


def test_workflow_requires_persistence_true_for_cross_department_handoff():
    workload = WorkloadSnapshot(boundary_signals=BoundarySignals(cross_department_handoff=True))
    assert estimator.workflow_requires_persistence(workload) is True


# --------------------------------------------------------------------------- size + RAM/VRAM feasibility

def test_estimate_sequence_size_not_robust_when_per_frame_output_unknown():
    """Fails if a missing estimated_output_bytes_per_frame is treated as zero-size instead
    of not-robust-enough -- §19: 'no fabricated size'."""
    workload = WorkloadSnapshot(frame_range=FrameRange(start=1, end=10))
    size = estimator.estimate_sequence_size(workload)
    assert size.robust_enough is False
    assert size.low is None and size.high is None


def test_estimate_sequence_size_robust_and_correct_when_inputs_present():
    workload = WorkloadSnapshot(
        frame_range=FrameRange(start=1001, end=1050),  # 50 frames
        estimated_output_bytes_per_frame=Interval(low=1_000_000.0, high=1_500_000.0),
    )
    size = estimator.estimate_sequence_size(workload)
    assert size.robust_enough is True
    assert size.low == 50_000_000.0
    assert size.high == 75_000_000.0


def test_disk_headroom_is_infinite_when_volume_total_unknown():
    """Fails if an unknown volume total silently reports a finite (satisfiable) headroom
    requirement -- must never be treated as 'assume it fits'."""
    from synapse.cache_policy.models import CacheVolume
    volume = CacheVolume(total_bytes="unknown")
    result = estimator.disk_headroom(1_000_000.0, volume, _policy())
    assert result == float("inf")


def test_ram_feasibility_unknown_when_peak_working_set_unmeasured():
    """Fails if an unmeasured peak_working_set_bytes silently passes the RAM gate (treated
    as 'fits') instead of reporting unknown -- §10.3: 'do not claim it fits'."""
    machine = MachineProfile(ram_total_bytes=64_000_000_000, ram_available_bytes=40_000_000_000)
    workload = WorkloadSnapshot()  # peak_working_set_bytes left at default None
    check = estimator.ram_feasibility(machine, workload, _policy())
    assert check.unknown is True
    assert check.exceeds is False


def test_ram_feasibility_exceeds_when_peak_over_safe_available():
    machine = MachineProfile(ram_total_bytes=64_000_000_000, ram_available_bytes=50_000_000_000)
    workload = WorkloadSnapshot(
        peak_working_set_bytes=Evidence.known(
            Interval(low=10_000_000_000.0, high=60_000_000_000.0),
            unit="bytes", source="calibrated_estimate",
        )
    )
    check = estimator.ram_feasibility(machine, workload, _policy(ram_safety_fraction=0.80))
    # safe = min(50e9, 64e9*0.8=51.2e9) = 50e9; peak_high=60e9 > 50e9
    assert check.unknown is False
    assert check.exceeds is True


def test_ram_feasibility_does_not_exceed_when_peak_within_safe_available():
    machine = MachineProfile(ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000)
    workload = WorkloadSnapshot(
        peak_working_set_bytes=Evidence.known(
            Interval(low=5_000_000_000.0, high=20_000_000_000.0),
            unit="bytes", source="calibrated_estimate",
        )
    )
    check = estimator.ram_feasibility(machine, workload, _policy(ram_safety_fraction=0.80))
    assert check.unknown is False
    assert check.exceeds is False


def test_vram_feasibility_unknown_when_no_gpu_devices():
    """GPU-required with zero reported devices must be unknown, never 'passes because
    there is nothing to exceed'."""
    machine = MachineProfile(gpu_devices=[])
    workload = WorkloadSnapshot(
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(Interval(1e9, 2e9), unit="bytes", source="calibrated_estimate"),
    )
    check = estimator.vram_feasibility(machine, workload, _policy())
    assert check.unknown is True


def test_vram_feasibility_unknown_when_vram_available_not_measured():
    """Fails if a device dict with only 'vram_bytes' (total) -- exactly what
    host/cache_host_probe.py's nvidia-smi probe actually reports today -- is treated as
    'available == total' instead of unknown. See models.GPUDevice's docstring."""
    machine = MachineProfile(gpu_devices=[{"name": "RTX 4090", "vram_bytes": 24_000_000_000}])
    workload = WorkloadSnapshot(
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(Interval(1e9, 2e9), unit="bytes", source="calibrated_estimate"),
    )
    check = estimator.vram_feasibility(machine, workload, _policy())
    assert check.unknown is True


def test_vram_feasibility_exceeds_when_measured_available_is_insufficient():
    machine = MachineProfile(gpu_devices=[
        {"name": "RTX 4090", "vram_bytes": 24_000_000_000, "vram_available_bytes": 20_000_000_000}
    ])
    workload = WorkloadSnapshot(
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(Interval(1e9, 23_000_000_000.0), unit="bytes",
                                               source="calibrated_estimate"),
    )
    check = estimator.vram_feasibility(machine, workload, _policy(vram_safety_fraction=0.85))
    # safe = min(20e9, 24e9*0.85=20.4e9) = 20e9; peak_high=23e9 > 20e9
    assert check.unknown is False
    assert check.exceeds is True
