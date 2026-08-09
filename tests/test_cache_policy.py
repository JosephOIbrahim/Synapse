"""Mile 2 (resource-aware-cache Phase 0, R-CACHE-1) -- tests for
``synapse.cache_policy`` (models / decision / strategies / policy_loader).

Covers:
  - §17.2 boundary tests (imports without hou/Qt, deterministic serialization, typed
    warnings not fake zero-evidence, policy JSON validation, decisions serialize
    deterministically, LLM cannot alter the structured verdict).
  - §17.1's 12-row pure policy scenario matrix, every row implemented as a test case
    against synthetic MachineProfile/WorkloadSnapshot/CachePolicy/StrategyResolution
    inputs constructed in this file.
  - §10.1's exact evaluation-order short-circuiting (binding: never reorder).
  - The §8.2 mandatory negative control restated at the decision-layer boundary (the
    host-layer negative control lives in tests/test_cache_no_forced_cook.py; this file
    asserts decision.py treats a dirty-not-forced WorkloadSnapshot as measure_first
    without ever needing to call anything geometry-shaped -- decision.py has no such
    call to make, which is itself the point).

Pure stdlib. No ``hou``, no Qt.

Every test states the condition under which it fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYTHON_DIR = _REPO_ROOT / "python"
if str(_PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(_PYTHON_DIR))

from synapse.cache_policy import (  # noqa: E402
    BakeAction,
    BoundaryAction,
    BoundarySignals,
    CachePolicy,
    CacheValidity,
    CacheVerdict,
    Evidence,
    ExistingCacheState,
    FrameRange,
    GPURelevance,
    Interval,
    MachineProfile,
    NodeDescriptor,
    PolicyValidationError,
    StrategyResolution,
    WorkloadSnapshot,
    decide_cache,
    default_policy_dict,
    load_policy,
    resolve_strategy,
)
from synapse.cache_policy.models import Context, StrategySupport
from synapse.cache_policy.decision import decide_boundary_value, validate_existing_cache


# =============================================================================================
# §17.2 boundary tests
# =============================================================================================

def test_cache_policy_imports_without_houdini_or_qt_installed():
    """Fails if any cache_policy module imports hou/Qt at module scope -- run in a
    subprocess with 'hou'/PySide6/PyQt* poisoned to ImportError so a transitively-broken
    import fails loudly instead of silently succeeding because some OTHER test already
    imported the real thing into sys.modules first."""
    import subprocess

    script = (
        "import sys, builtins\n"
        "_real_import = builtins.__import__\n"
        "_forbidden = ('hou', 'hdefereval', 'PySide6', 'PyQt5', 'PyQt6', 'shiboken6')\n"
        "def _guarded_import(name, *a, **kw):\n"
        "    if name in _forbidden or name.split('.')[0] in _forbidden:\n"
        "        raise ImportError(f'test guard: {name} must not be imported by cache_policy')\n"
        "    return _real_import(name, *a, **kw)\n"
        "builtins.__import__ = _guarded_import\n"
        f"sys.path.insert(0, {str(_PYTHON_DIR)!r})\n"
        "import synapse.cache_policy as cp\n"
        "cp.decide_cache(cp.MachineProfile(), cp.WorkloadSnapshot(), "
        "cp.resolve_strategy(cp.NodeDescriptor(context=cp.Context.SOP.value)), cp.CachePolicy())\n"
        "print('OK')\n"
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"
    assert "OK" in result.stdout


def test_decide_cache_handles_real_host_probe_unknown_shaped_machine_profile():
    """Regression test added post-review (crucible showstopper 1). Reviewer fed the ACTUAL
    output of ``host/cache_host_probe.py::detect_machine_profile()`` (with psutil
    unavailable and $HIP unset -- the real shape that module produces when hardware probing
    fails, per its own docstring: "Windows/macOS without psutil: no free stdlib equivalent
    -> unknown, never guessed") straight into decide_cache() and got a TypeError: the
    dataclass default/probe-reported value for an unmeasured field is the literal string
    "unknown" (not None), and several estimator.py sites compared/multiplied it directly
    without normalizing it first (``min("unknown", ram_total * fraction)`` etc.).

    Fixed at the root by normalizing the ``UNKNOWN`` sentinel to ``None`` inside
    ``evidence_value()`` itself (the single required accessor -- see models.py's
    docstring), so every existing ``evidence_value(x) is None`` check downstream became
    correct by construction rather than needing an audit of every call site.

    Fails if any unknown-shaped field anywhere in a real host-probe MachineProfile raises
    instead of producing a graceful (non-exception) verdict.
    """
    _HOST_DIR = _REPO_ROOT / "host"
    if str(_HOST_DIR) not in sys.path:
        sys.path.insert(0, str(_HOST_DIR))
    import cache_host_probe as chp

    original_psutil_available = chp.PSUTIL_AVAILABLE
    original_read_proc_meminfo = chp._read_proc_meminfo
    chp.PSUTIL_AVAILABLE = False  # kill tier 2 (declared-optional psutil)
    # Kill tier 1 too: on Linux CI /proc/meminfo delivers REAL bytes via the stdlib
    # path, so the unknown shape must be FORCED on every platform, never hoped for.
    chp._read_proc_meminfo = lambda warnings: (None, None)
    try:
        import os
        hip_backup = os.environ.pop("HIP", None)
        try:
            profile_dict = chp.detect_machine_profile(cache_root=None)
        finally:
            if hip_backup is not None:
                os.environ["HIP"] = hip_backup
    finally:
        chp.PSUTIL_AVAILABLE = original_psutil_available
        chp._read_proc_meminfo = original_read_proc_meminfo

    assert profile_dict["ram_available_bytes"] == "unknown", (
        "test setup assumption failed: expected the forced-unknown shape from "
        "detect_machine_profile(), got a real measurement instead -- this test would not "
        "have caught the original bug without this shape"
    )

    machine = MachineProfile(**profile_dict)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        peak_working_set_bytes=Evidence.known(
            Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    decision = decide_cache(machine, workload, strategy, CachePolicy())  # must not raise
    assert decision.verdict in (
        CacheVerdict.MEASURE_FIRST.value, CacheVerdict.OPTIMIZE_FIRST.value,
        CacheVerdict.NOT_WORTH_IT.value, CacheVerdict.INSUFFICIENT_DISK.value,
    ), f"expected a graceful degrade verdict on unknown machine evidence, got {decision.verdict!r}"


def test_gpu_device_dict_missing_vram_available_bytes_key_entirely_does_not_crash():
    """Regression test added post-review (crucible showstopper 1, GPU/VRAM half). The real
    ``host/cache_host_probe.py::_detect_gpu_devices`` shape reports ONLY ``name`` and
    ``vram_bytes`` (total, via nvidia-smi) -- it never populates ``vram_available_bytes`` at
    all (the key is simply absent from the dict, not present-and-"unknown"). Fails if a
    dict.get() miss on that key propagates into an arithmetic comparison instead of being
    recognized as unknown."""
    machine = MachineProfile(
        ram_total_bytes=64_000_000_000, ram_available_bytes=40_000_000_000,
        gpu_devices=[{"name": "RTX 4090", "vram_bytes": 24_000_000_000}],  # no vram_available_bytes key
    )
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(3.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(
            Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    decision = decide_cache(machine, workload, strategy, CachePolicy())  # must not raise
    assert decision.verdict == CacheVerdict.MEASURE_FIRST.value


def test_low_confidence_cache_now_degrades_to_insert_boundary_only_by_default_policy():
    """Regression test added post-review (crucible showstopper 2), CORRECTED in a follow-up
    pass after reviewer flagged that the original fix's target verdict (measure_first) made
    CacheVerdict.INSERT_BOUNDARY_ONLY permanently unreachable (a structural bug, not just a
    test problem -- see decision.py step 10's header comment for the full derivation).

    §6.1: a boundary that is architecturally useful (checkpoint_recovery_required) but not
    confident/permitted enough to bake now is exactly "insert_boundary_only" ("Insert under
    undo; do not bake"), not "measure_first" (which implies missing EVIDENCE -- there is
    none missing here; every input is known, the issue is policy permission, not evidence).

    Constructs a workload that is feasible ONLY via non_performance_justification (no
    computable speed-benefit envelope -- Tc<=Tr) with a checkpoint_recovery_required
    boundary signal. With the default policy (allow_low_confidence_bake_recommendation=
    False), this must land on insert_boundary_only, never bake_after_approval.
    """
    machine = _ample_machine_for_confidence_test()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(4.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=50),
        estimated_output_bytes_per_frame=Interval(low=1_000_000.0, high=2_000_000.0),
        peak_working_set_bytes=Evidence.known(
            Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
        expected_future_reads=5,
        compute_seconds_total=Interval(50.0, 60.0),
        write_seconds_total=Interval(10.0, 15.0),
        read_seconds_total=Interval(55.0, 70.0),  # Tr >= Tc: no speed benefit provable
        boundary_signals=BoundarySignals(checkpoint_recovery_required=True),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    decision = decide_cache(machine, workload, strategy, CachePolicy())  # default policy
    assert decision.verdict == CacheVerdict.INSERT_BOUNDARY_ONLY.value, (
        f"expected a low-confidence non-performance-only cache to degrade to "
        f"insert_boundary_only under the default policy, got {decision.verdict!r}"
    )
    assert decision.bake_action == BakeAction.DO_NOT_BAKE.value


def test_low_confidence_cache_now_is_allowed_when_policy_explicitly_permits_it():
    """The other half of the §6.3 rule: an explicit project rule (
    allow_low_confidence_bake_recommendation=True) DOES permit the low-confidence
    cache_now to stand -- the gate must be a real switch, not a hardcoded refusal."""
    machine = _ample_machine_for_confidence_test()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(4.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=50),
        estimated_output_bytes_per_frame=Interval(low=1_000_000.0, high=2_000_000.0),
        peak_working_set_bytes=Evidence.known(
            Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
        expected_future_reads=5,
        compute_seconds_total=Interval(50.0, 60.0),
        write_seconds_total=Interval(10.0, 15.0),
        read_seconds_total=Interval(55.0, 70.0),
        boundary_signals=BoundarySignals(checkpoint_recovery_required=True),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    policy = CachePolicy(allow_low_confidence_bake_recommendation=True)
    decision = decide_cache(machine, workload, strategy, policy)
    assert decision.verdict == CacheVerdict.CACHE_NOW.value
    assert decision.confidence == "low"


def _ample_machine_for_confidence_test() -> MachineProfile:
    from synapse.cache_policy.models import CacheVolume
    return MachineProfile(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes=1_000_000_000_000, total_bytes=2_000_000_000_000),
    )


def test_planner_output_is_deterministic_for_identical_inputs():
    """Fails if decide_cache() is non-deterministic for byte-identical inputs (e.g. via
    an unseeded random, dict-ordering dependency, or wall-clock leakage into the verdict
    itself)."""
    machine = MachineProfile(ram_total_bytes=64_000_000_000, ram_available_bytes=40_000_000_000)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(0.05, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=1),
        estimated_output_bytes_per_frame=Interval(low=2_000_000_000.0, high=2_000_000_000.0),
        expected_future_reads=1,
        write_seconds_total=Interval(1.0, 2.0),
        read_seconds_total=Interval(0.5, 1.0),
        compute_seconds_total=Interval(0.05, 0.05),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    policy = CachePolicy()
    d1 = decide_cache(machine, workload, strategy, policy)
    d2 = decide_cache(machine, workload, strategy, policy)
    assert d1.verdict == d2.verdict
    assert d1.boundary_action == d2.boundary_action
    assert d1.bake_action == d2.bake_action
    assert d1.evidence_digest == d2.evidence_digest


def test_decisions_serialize_deterministically_for_evidence_hashing():
    """Fails if two decisions built from identical substantive inputs produce different
    evidence_digest values -- the digest must be stable across repeated calls even though
    decision_id (an opaque per-call uuid) legitimately differs."""
    machine = MachineProfile(ram_total_bytes=64_000_000_000, ram_available_bytes=40_000_000_000)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    policy = CachePolicy()
    d1 = decide_cache(machine, workload, strategy, policy)
    d2 = decide_cache(machine, workload, strategy, policy)
    assert d1.decision_id != d2.decision_id, "decision_id should be a fresh opaque id per call"
    assert d1.evidence_digest == d2.evidence_digest


def test_llm_generated_explanation_cannot_alter_the_structured_verdict():
    """Fails if there is any code path where mutating `reasons`/`headline` (the
    artist-facing prose an LLM may restate, per §7.5) also changes `verdict`. Simulates an
    LLM 'restating' reasons and confirms the structured fields are untouched -- there is no
    setter that derives verdict from reasons text."""
    machine = MachineProfile(ram_total_bytes=64_000_000_000, ram_available_bytes=40_000_000_000)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
    )
    strategy = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    decision = decide_cache(machine, workload, strategy, CachePolicy())
    original_verdict = decision.verdict
    # "LLM" restates the reasons/headline in artist-friendly language
    decision.reasons = ["Rewritten in friendlier language by an LLM restatement pass"]
    decision.headline = "Totally different friendly headline"
    assert decision.verdict == original_verdict, "restating prose fields must never change verdict"


def test_exceptions_produce_typed_warnings_not_zero_valued_fake_evidence():
    """Restates the §17.2 rule at the cache_policy layer (the host-layer version lives in
    test_cache_host_probe_boundary.py): is_unknown() must report True for evidence with a
    None value, never confusing it with a real, legitimately-zero measurement."""
    from synapse.cache_policy import is_unknown, evidence_value

    zero_but_real = Evidence.known(0.0, unit="seconds", source="hou.OpNode.lastCookTime")
    unmeasured = Evidence.unknown(unit="seconds")
    assert is_unknown(zero_but_real) is False, "a real zero must not be reported as unknown"
    assert evidence_value(zero_but_real) == 0.0
    assert is_unknown(unmeasured) is True
    assert evidence_value(unmeasured) is None


def test_policy_json_rejects_invalid_fraction():
    """Fails if a fraction field outside [0, 1] is silently accepted instead of raising."""
    with pytest.raises(PolicyValidationError):
        load_policy({"ram_safety_fraction": 1.5})
    with pytest.raises(PolicyValidationError):
        load_policy({"vram_safety_fraction": -0.1})


def test_policy_json_rejects_negative_size():
    """Fails if a negative minimum_free_disk_after_bytes is silently accepted."""
    with pytest.raises(PolicyValidationError):
        load_policy({"minimum_free_disk_after_bytes": -1})


def test_policy_json_rejects_non_positive_safety_multiplier():
    """Fails if cache_size_safety_multiplier <= 0 is silently accepted -- a zero or
    negative multiplier would make required_free_before_bake understate real risk."""
    with pytest.raises(PolicyValidationError):
        load_policy({"cache_size_safety_multiplier": 0})


def test_policy_json_rejects_unknown_enum_value():
    """Fails if an invalid network_cache_policy/retention_policy string is silently
    accepted instead of raising."""
    with pytest.raises(PolicyValidationError):
        load_policy({"network_cache_policy": "definitely_not_a_real_policy"})
    with pytest.raises(PolicyValidationError):
        load_policy({"retention_policy": "definitely_not_a_real_policy"})


def test_policy_json_rejects_unknown_field_name():
    """Fails if a typo'd override key (e.g. 'ram_saftey_fraction') is silently dropped
    instead of raising -- a silent drop would mean the artist's override never applied."""
    with pytest.raises(PolicyValidationError):
        load_policy({"ram_saftey_fraction": 0.5})


def test_policy_json_accepts_a_valid_full_override_round_trip():
    """Fails if a fully valid override dict (round-tripped through json.dumps/loads, as a
    real project policy file would be) is rejected."""
    overrides = json.loads(json.dumps({
        "ram_safety_fraction": 0.75, "network_cache_policy": "always_deny",
        "minimum_seconds_saved": 45.0,
    }))
    policy = load_policy(overrides)
    assert policy.ram_safety_fraction == 0.75
    assert policy.network_cache_policy == "always_deny"
    assert policy.minimum_seconds_saved == 45.0


def test_default_policy_dict_round_trips_through_load_policy():
    """Fails if the defaults themselves do not validate -- the built-in defaults must
    always be a legal policy."""
    policy = load_policy(default_policy_dict())
    assert policy.ram_safety_fraction == CachePolicy().ram_safety_fraction


# =============================================================================================
# strategies.py -- §9 resolver discipline
# =============================================================================================

def test_sop_geometry_strategy_supported():
    res = resolve_strategy(NodeDescriptor(context=Context.SOP.value))
    assert res.supported is True
    assert res.strategy_id == "sop_filecache_geometry_v1"


def test_sop_solver_result_strategy_supported_and_distinct():
    res = resolve_strategy(NodeDescriptor(context=Context.SOP.value, is_solver_result=True))
    assert res.supported is True
    assert res.strategy_id == "sop_filecache_solver_result_v1"


def test_sop_vdb_only_strategy_supported_and_distinct():
    """Mile 4 task 1 gap-close: §9 row 2 (SOP VDB-only output -> .vdb candidate) had zero
    test coverage before this mile -- resolve_strategy() implemented it but nothing pinned
    the strategy_id, so a regression collapsing it back to the generic geometry strategy
    would have passed green."""
    res = resolve_strategy(NodeDescriptor(context=Context.SOP.value, data_class="vdb_only"))
    assert res.supported is True
    assert res.strategy_id == "sop_filecache_vdb_v1"


def test_sop_independent_frames_strategy_supported_and_distinct():
    """Mile 4 task 1 gap-close: §9 row 4 (independent frames -> Simulation off, can be
    parallelized) had zero test coverage before this mile."""
    res = resolve_strategy(NodeDescriptor(context=Context.SOP.value, is_independent_frames=True))
    assert res.supported is True
    assert res.strategy_id == "sop_filecache_independent_frames_v1"


def test_sop_solver_result_takes_precedence_over_independent_frames_hint():
    """If a caller (inconsistently) sets both hints, resolve_strategy must not silently
    pick one at random -- pins the documented evaluation order in strategies.py
    (is_solver_result checked before is_independent_frames)."""
    res = resolve_strategy(NodeDescriptor(
        context=Context.SOP.value, is_solver_result=True, is_independent_frames=True,
    ))
    assert res.strategy_id == "sop_filecache_solver_result_v1"


def test_lop_context_returns_unsupported_explicit_per_blueprint():
    """Mile 4 task 1 gap-close: §9 row 6 (Solaris/LOP requires USD-aware path/layer
    policy) had zero test coverage before this mile -- only DOP/COP/unknown were pinned."""
    res = resolve_strategy(NodeDescriptor(context=Context.LOP.value))
    assert res.supported is False
    assert res.support == StrategySupport.UNSUPPORTED.value
    assert res.strategy_id != "sop_filecache_geometry_v1"


def test_cop_context_returns_unsupported_explicit_per_blueprint():
    """§9: 'Return unsupported until a tested resolver exists' -- COP is the row the
    blueprint states this for explicitly."""
    res = resolve_strategy(NodeDescriptor(context=Context.COP.value))
    assert res.supported is False
    assert res.support == StrategySupport.UNSUPPORTED.value


def test_dop_context_returns_unsupported_never_collapsed_to_generic_sop_cache():
    """§9: 'Do not reduce both to one generic SOP cache' -- Phase 0 has no solver-specific
    DOP strategy implemented, so DOP must resolve unsupported, never silently fall through
    to the SOP geometry strategy."""
    res = resolve_strategy(NodeDescriptor(context=Context.DOP.value))
    assert res.supported is False
    assert res.strategy_id != "sop_filecache_geometry_v1"


def test_unknown_context_returns_unsupported_never_guesses():
    res = resolve_strategy(NodeDescriptor(context=Context.UNKNOWN.value))
    assert res.supported is False


# =============================================================================================
# decision.py -- validate_existing_cache (§12.4)
# =============================================================================================

def test_validate_existing_cache_not_present():
    assert validate_existing_cache(None, WorkloadSnapshot()) == CacheValidity.NOT_PRESENT
    assert validate_existing_cache(ExistingCacheState(present=False), WorkloadSnapshot()) == CacheValidity.NOT_PRESENT


def test_validate_existing_cache_unmanifested_is_unverifiable():
    """§12.4: 'unmanifested legacy cache: treat as unverifiable'."""
    existing = ExistingCacheState(present=True, manifested=False)
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.UNVERIFIABLE


def test_validate_existing_cache_complete_matching_signature_is_valid():
    existing = ExistingCacheState(
        present=True, manifested=True, manifest_status="complete",
        upstream_signature="sha256:abc", current_upstream_signature="sha256:abc",
    )
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.VALID


def test_validate_existing_cache_complete_mismatched_signature_is_stale():
    """§12.1: 'files exist' must never equal 'cache valid' when the upstream changed."""
    existing = ExistingCacheState(
        present=True, manifested=True, manifest_status="complete",
        upstream_signature="sha256:abc", current_upstream_signature="sha256:def",
    )
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.STALE


def test_validate_existing_cache_partial_status():
    existing = ExistingCacheState(present=True, manifested=True, manifest_status="partial")
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.PARTIAL


def test_validate_existing_cache_failed_status_is_corrupt():
    existing = ExistingCacheState(present=True, manifested=True, manifest_status="failed")
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.CORRUPT


def test_validate_existing_cache_unknown_signature_is_unverifiable_not_valid():
    """§12.3: 'If a dependency cannot be inspected, validity is unverifiable, not valid.'"""
    existing = ExistingCacheState(
        present=True, manifested=True, manifest_status="complete",
        upstream_signature="sha256:abc", current_upstream_signature="unknown",
    )
    assert validate_existing_cache(existing, WorkloadSnapshot()) == CacheValidity.UNVERIFIABLE


# =============================================================================================
# §17.1 -- the 12-row pure policy scenario matrix
# =============================================================================================

_SOP = lambda: resolve_strategy(NodeDescriptor(context=Context.SOP.value))
_SOP_SOLVER = lambda: resolve_strategy(NodeDescriptor(context=Context.SOP.value, is_solver_result=True))


def _ample_peak_ram() -> Evidence:
    """A peak-working-set evidence value comfortably inside _ample_machine()'s RAM budget
    -- used by scenarios that want to exercise a step AFTER the RAM-feasibility gate (step
    5) without that gate itself firing measure_first/optimize_first first."""
    return Evidence.known(Interval(low=1_000_000_000.0, high=2_000_000_000.0), unit="bytes",
                           source="calibrated_estimate")


def _ample_machine(**overrides) -> MachineProfile:
    from synapse.cache_policy.models import CacheVolume
    base = dict(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes=1_000_000_000_000, total_bytes=2_000_000_000_000),
    )
    base.update(overrides)
    return MachineProfile(**base)


def test_scenario_01_static_cheap_sop_is_not_worth_it():
    """Static 0.05 s SOP, one read, 2 GB output -> not_worth_it. No 'fast machine'
    heuristic overrides economics (§17.1 row 1)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(0.05, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=1),
        estimated_output_bytes_per_frame=Interval(low=2_000_000_000.0, high=2_000_000_000.0),
        expected_future_reads=1,
        compute_seconds_total=Interval(0.05, 0.05),
        write_seconds_total=Interval(3.0, 5.0),   # writing 2GB dwarfs the 0.05s compute
        read_seconds_total=Interval(1.0, 2.0),
        boundary_signals=BoundarySignals(static_or_cheap=True),
        peak_working_set_bytes=_ample_peak_ram(),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.NOT_WORTH_IT.value


def test_scenario_02_valuable_particle_sequence_ample_ssd_is_cache_now():
    """6 s/frame particle sequence, 240 frames, two future reads, ample SSD -> cache_now.
    Break-even and disk headroom are both visible and clearing (§17.1 row 2)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1001, end=1240),  # 240 frames
        estimated_output_bytes_per_frame=Interval(low=800_000_000.0, high=1_000_000_000.0),
        expected_future_reads=2,
        compute_seconds_total=Interval(1400.0, 1440.0),   # ~6s/frame * 240
        write_seconds_total=Interval(200.0, 260.0),
        read_seconds_total=Interval(80.0, 120.0),
        boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
        peak_working_set_bytes=_ample_peak_ram(),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.CACHE_NOW.value
    assert decision.bake_action == BakeAction.BAKE_AFTER_APPROVAL.value


def test_scenario_03_stateful_solver_unknown_output_size_is_measure_first_or_boundary_only():
    """Stateful solver, unknown output size, no prior samples -> measure_first or
    insert_boundary_only. No fabricated size (§17.1 row 3)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(4.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=100),
        # estimated_output_bytes_per_frame deliberately left unknown (None)
        boundary_signals=BoundarySignals(stateful_downstream_scrub=True),
    )
    decision = decide_cache(machine, workload, _SOP_SOLVER(), CachePolicy())
    assert decision.verdict in (CacheVerdict.MEASURE_FIRST.value, CacheVerdict.INSERT_BOUNDARY_ONLY.value)


def test_scenario_04_per_frame_ram_above_safe_is_optimize_first():
    """Per-frame working set above safe RAM -> optimize_first. File Cache is not described
    as a memory fix (§17.1 row 4)."""
    machine = _ample_machine(ram_total_bytes=32_000_000_000, ram_available_bytes=20_000_000_000)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(3.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        peak_working_set_bytes=Evidence.known(
            Interval(low=15_000_000_000.0, high=30_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy(ram_safety_fraction=0.80))
    assert decision.verdict == CacheVerdict.OPTIMIZE_FIRST.value
    assert "RAM" in decision.headline


def test_scenario_05_gpu_required_above_safe_vram_is_optimize_first():
    """GPU-required workload above safe VRAM -> optimize_first. GPU evidence used only
    because relevance is proven (§17.1 row 5)."""
    machine = _ample_machine(gpu_devices=[
        {"name": "RTX 4090", "vram_bytes": 24_000_000_000, "vram_available_bytes": 22_000_000_000}
    ])
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(3.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(
            Interval(low=1_000_000_000.0, high=23_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy(vram_safety_fraction=0.85))
    assert decision.verdict == CacheVerdict.OPTIMIZE_FIRST.value


def test_scenario_06_cpu_only_workload_on_rtx4090_same_as_without_gpu_metadata():
    """CPU-only workload on RTX 4090 -> same result as without RTX metadata. GPU name
    cannot sway the verdict (§17.1 row 6)."""
    base_kwargs = dict(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=240),
        estimated_output_bytes_per_frame=Interval(low=800_000_000.0, high=1_000_000_000.0),
        expected_future_reads=2,
        compute_seconds_total=Interval(1400.0, 1440.0),
        write_seconds_total=Interval(200.0, 260.0),
        read_seconds_total=Interval(80.0, 120.0),
        boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
        gpu_relevance=GPURelevance.NOT_USED.value,
        peak_working_set_bytes=_ample_peak_ram(),
    )
    machine_with_gpu = _ample_machine(gpu_devices=[{"name": "RTX 4090", "vram_bytes": 24_000_000_000}])
    machine_without_gpu = _ample_machine(gpu_devices=[])
    d_with = decide_cache(machine_with_gpu, WorkloadSnapshot(**base_kwargs), _SOP(), CachePolicy())
    d_without = decide_cache(machine_without_gpu, WorkloadSnapshot(**base_kwargs), _SOP(), CachePolicy())
    assert d_with.verdict == d_without.verdict == CacheVerdict.CACHE_NOW.value


def test_scenario_07_valuable_cache_insufficient_free_space():
    """Valuable 960 GB cache, 600 GB free -> insufficient_disk. Uses high estimate plus
    reserve (§17.1 row 7)."""
    from synapse.cache_policy.models import CacheVolume
    machine = MachineProfile(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(
            free_bytes=600 * 1024**3,   # 600 GiB free
            total_bytes=2000 * 1024**3,  # 2000 GiB volume
        ),
    )
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=240),
        estimated_output_bytes_per_frame=Interval(low=3.8 * 1024**3, high=4.0 * 1024**3),  # ~960GB high
        expected_future_reads=3,
        compute_seconds_total=Interval(1400.0, 1440.0),
        write_seconds_total=Interval(200.0, 260.0),
        read_seconds_total=Interval(80.0, 120.0),
        boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
        peak_working_set_bytes=_ample_peak_ram(),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.INSUFFICIENT_DISK.value


def test_scenario_08_existing_matching_complete_manifest_is_use_valid_cache():
    """Existing matching complete manifest -> use_valid_cache. No unnecessary rebake
    (§17.1 row 8)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:same", current_upstream_signature="sha256:same",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.USE_VALID_CACHE.value
    assert decision.boundary_action == BoundaryAction.REUSE_EXISTING.value
    assert decision.bake_action == BakeAction.DO_NOT_BAKE.value


def test_scenario_09_existing_files_changed_upstream_signature_is_stale():
    """Existing files with changed upstream signature -> stale. File existence cannot
    equal validity (§17.1 row 9)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:old", current_upstream_signature="sha256:new",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.cache_validity == CacheValidity.STALE.value
    assert decision.verdict != CacheVerdict.USE_VALID_CACHE.value


def test_scenario_10_existing_unmanifested_cache_is_unverifiable():
    """Existing unmanifested cache -> unverifiable. Requires explicit project rule/override
    (§17.1 row 10)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        existing_cache=ExistingCacheState(present=True, manifested=False),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.cache_validity == CacheValidity.UNVERIFIABLE.value
    assert decision.verdict != CacheVerdict.USE_VALID_CACHE.value


def test_scenario_11_unknown_context_is_unsupported():
    """Unknown context -> unsupported. No generic node mutation (§17.1 row 11)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot()
    unknown_strategy = resolve_strategy(NodeDescriptor(context=Context.UNKNOWN.value))
    decision = decide_cache(machine, workload, unknown_strategy, CachePolicy())
    assert decision.verdict == CacheVerdict.UNSUPPORTED.value
    assert decision.bake_action == BakeAction.DO_NOT_BAKE.value


def test_scenario_12_dirty_node_no_prior_observation_is_measure_first():
    """Dirty node with no prior observation -> measure_first. Geometry accessor is never
    invoked -- decision.py has no geometry() call to make at all; this asserts the
    WorkloadSnapshot shape host/cache_host_probe.py's dirty_not_forced branch actually
    produces (unknown last_cook_seconds/geometry_memory_bytes) drives measure_first here
    (§17.1 row 12)."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(True, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.unknown(unit="seconds"),
        geometry_memory_bytes=Evidence.unknown(unit="bytes"),
        observation_status="dirty_not_forced",
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.MEASURE_FIRST.value


# =============================================================================================
# §10.1 evaluation-order short-circuiting -- binding: never reorder
# =============================================================================================

def test_unsupported_strategy_short_circuits_before_anything_else_is_evaluated():
    """Fails if an unsupported strategy does not immediately return UNSUPPORTED even when
    every other input (existing valid cache, ample resources) looks favorable -- strategy
    support is evaluation-order step 1."""
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:x", current_upstream_signature="sha256:x",
        ),
    )
    unsupported = resolve_strategy(NodeDescriptor(context=Context.COP.value))
    decision = decide_cache(machine, workload, unsupported, CachePolicy())
    assert decision.verdict == CacheVerdict.UNSUPPORTED.value


def test_valid_existing_cache_short_circuits_before_ram_check_even_if_ram_would_fail():
    """Fails if a VALID existing cache does not win even when RAM would otherwise fail --
    existing-cache validity is evaluation-order step 2, strictly before RAM feasibility
    (step 5)."""
    machine = MachineProfile(ram_total_bytes=1_000_000, ram_available_bytes=1_000)  # tiny, would fail RAM
    workload = WorkloadSnapshot(
        existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:x", current_upstream_signature="sha256:x",
        ),
        peak_working_set_bytes=Evidence.known(Interval(1e15, 2e15), unit="bytes", source="calibrated_estimate"),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.USE_VALID_CACHE.value


def test_passive_evidence_unsafe_short_circuits_before_ram_check():
    """Fails if unsafe passive evidence (dirty, no history) does not short-circuit BEFORE
    the RAM check runs -- step 4 precedes step 5. Constructed so RAM would also fail if
    reached, to prove which branch actually fired."""
    machine = MachineProfile(ram_total_bytes=1_000_000, ram_available_bytes=1_000)
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(True, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.unknown(unit="seconds"),
        geometry_memory_bytes=Evidence.unknown(unit="bytes"),
        peak_working_set_bytes=Evidence.known(Interval(1e15, 2e15), unit="bytes", source="calibrated_estimate"),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.MEASURE_FIRST.value
    assert "RAM" not in decision.headline


def test_ram_check_short_circuits_before_gpu_check_even_when_gpu_required():
    """Fails if a RAM failure does not fire before the GPU/VRAM branch is even reached --
    step 5 precedes step 6, even when gpu_relevance == REQUIRED."""
    machine = MachineProfile(
        ram_total_bytes=32_000_000_000, ram_available_bytes=20_000_000_000,
        gpu_devices=[],  # would ALSO fail/unknown at the VRAM step if reached
    )
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(3.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        gpu_relevance=GPURelevance.REQUIRED.value,
        peak_working_set_bytes=Evidence.known(
            Interval(low=15_000_000_000.0, high=30_000_000_000.0), unit="bytes",
            source="calibrated_estimate",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy(ram_safety_fraction=0.80))
    assert decision.verdict == CacheVerdict.OPTIMIZE_FIRST.value
    assert "RAM" in decision.headline


def test_gpu_check_is_skipped_entirely_when_relevance_is_not_required():
    """Fails if the VRAM branch is evaluated (and potentially trips measure_first/
    optimize_first) even though gpu_relevance is OPTIONAL/NOT_USED/UNKNOWN -- step 6 is
    gated strictly on REQUIRED."""
    machine = _ample_machine(gpu_devices=[])  # would report VRAM-unknown if the branch ran
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=240),
        estimated_output_bytes_per_frame=Interval(low=800_000_000.0, high=1_000_000_000.0),
        expected_future_reads=2,
        compute_seconds_total=Interval(1400.0, 1440.0),
        write_seconds_total=Interval(200.0, 260.0),
        read_seconds_total=Interval(80.0, 120.0),
        boundary_signals=BoundarySignals(multiple_downstream_consumers=True),
        gpu_relevance=GPURelevance.NOT_USED.value,
        peak_working_set_bytes=_ample_peak_ram(),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.CACHE_NOW.value


def test_size_robustness_short_circuits_before_disk_headroom_check():
    """Fails if disk headroom is checked (and would raise/mis-evaluate) before size
    robustness is confirmed -- step 7 precedes step 8."""
    from synapse.cache_policy.models import CacheVolume
    machine = MachineProfile(
        ram_total_bytes=128_000_000_000, ram_available_bytes=100_000_000_000,
        cache_volume=CacheVolume(free_bytes="unknown", total_bytes="unknown"),
    )
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(6.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        peak_working_set_bytes=_ample_peak_ram(),
        # estimated_output_bytes_per_frame left unknown -> size not robust
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.MEASURE_FIRST.value
    assert "size" in decision.headline.lower()


# =============================================================================================
# §6.2 -- verdict / boundary_action / bake_action / cache_validity are orthogonal
# =============================================================================================

def test_insert_boundary_only_does_not_imply_bake():
    """§6.2: 'a useful boundary [is not confused] with immediate feasibility'.

    CORRECTED post-CLEAR (reviewer-flagged): this test previously guarded its assertion
    behind ``if decision.verdict == INSERT_BOUNDARY_ONLY.value:``, which passed green while
    asserting nothing -- the fixture never set ``peak_working_set_bytes``, so it was already
    caught at the RAM-unknown gate (step 5, MEASURE_FIRST) long before reaching the
    boundary/value branch this test claims to cover, and CacheVerdict.INSERT_BOUNDARY_ONLY
    was separately unreachable from decision.py's own step-10 logic at the time (see the
    structural fix documented in decision.py's step-10 header comment). Both defects are
    fixed now: an ample peak_working_set_bytes lets this fixture clear every earlier gate,
    and decision.py's step 10 makes INSERT_BOUNDARY_ONLY reachable again. The assertion
    below is now unconditional and will fail loudly if either regresses.
    """
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        needs_to_cook=Evidence.known(False, source="hou.OpNode.needsToCook"),
        last_cook_seconds=Evidence.known(4.0, unit="seconds", source="hou.OpNode.lastCookTime"),
        frame_range=FrameRange(start=1, end=100),
        estimated_output_bytes_per_frame=Interval(low=1_000_000.0, high=2_000_000.0),
        peak_working_set_bytes=_ample_peak_ram(),
        expected_future_reads=0.5,  # below policy minimum -> not worthwhile on value alone
        compute_seconds_total=Interval(400.0, 440.0),
        write_seconds_total=Interval(300.0, 350.0),
        read_seconds_total=Interval(10.0, 20.0),
        boundary_signals=BoundarySignals(checkpoint_recovery_required=True),
    )
    decision = decide_cache(machine, workload, _SOP_SOLVER(), CachePolicy(minimum_expected_future_reads=1.0))
    assert decision.verdict == CacheVerdict.INSERT_BOUNDARY_ONLY.value, (
        f"expected insert_boundary_only (checkpoint signal present, no proven speed benefit, "
        f"low confidence, default policy disallows low-confidence bake), got {decision.verdict!r}"
    )
    assert decision.bake_action == BakeAction.DO_NOT_BAKE.value


def test_use_valid_cache_never_pairs_with_bake_after_approval():
    machine = _ample_machine()
    workload = WorkloadSnapshot(
        existing_cache=ExistingCacheState(
            present=True, manifested=True, manifest_status="complete",
            upstream_signature="sha256:same", current_upstream_signature="sha256:same",
        ),
    )
    decision = decide_cache(machine, workload, _SOP(), CachePolicy())
    assert decision.verdict == CacheVerdict.USE_VALID_CACHE.value
    assert decision.bake_action != BakeAction.BAKE_AFTER_APPROVAL.value


# =============================================================================================
# decide_boundary_value -- §10.2
# =============================================================================================

def test_boundary_value_no_signals_evaluated_defaults_to_no_boundary():
    decision = decide_boundary_value(WorkloadSnapshot(), CachePolicy())
    assert decision.should_exist is False
    assert decision.action == BoundaryAction.NONE


def test_boundary_value_positive_signal_wins():
    workload = WorkloadSnapshot(boundary_signals=BoundarySignals(repeated_viewport_reads=True))
    decision = decide_boundary_value(workload, CachePolicy())
    assert decision.should_exist is True
    assert decision.action == BoundaryAction.INSERT


def test_boundary_value_negative_signal_alone_means_no_boundary():
    workload = WorkloadSnapshot(boundary_signals=BoundarySignals(static_or_cheap=True))
    decision = decide_boundary_value(workload, CachePolicy())
    assert decision.should_exist is False


def test_boundary_value_unevaluated_signal_is_not_treated_as_negative():
    """Fails if a None (not-evaluated) signal is treated as if it were an explicit False
    negative vote -- only explicit True counts either way."""
    workload = WorkloadSnapshot(boundary_signals=BoundarySignals(
        static_or_cheap=None, cross_department_handoff=True,
    ))
    decision = decide_boundary_value(workload, CachePolicy())
    assert decision.should_exist is True
