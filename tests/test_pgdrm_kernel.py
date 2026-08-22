"""test_pgdrm_kernel.py — pins the PG-DRM kernel (MEMORY board rung M2).

The kernel is a PURE function set: no I/O, no `hou`, no store handle, no
network, no LLM, and **time is a parameter** (`age_seconds`) that the caller
measures. The kernel never reads a clock — that is exactly how the submitted
spec's decay branch became unreachable (adjudication D5).

Every decay expectation below is HAND-COMPUTED from a mathematical identity
and the arithmetic is shown inline. Nothing here is read back from
`synapse.loop.pgdrm`, and nothing is copied from the blueprint
(repo precedent: a control pinned "161"; the truth was 171).

    e^(-k * ln2)  = (e^ln2)^-k  = 2^-k
    e^(-k * ln10) = (e^ln10)^-k = 10^-k
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.loop import pgdrm  # noqa: E402
from synapse.loop import ports  # noqa: E402

# ---------------------------------------------------------------------------
# Hand-computed constants. LN2/LN10 are the standard decimal expansions of
# ln 2 and ln 10 to double precision; they are NOT produced by the module
# under test.
# ---------------------------------------------------------------------------
LN2 = 0.6931471805599453
LN10 = 2.302585092994046

KERNEL_SRC = Path(pgdrm.__file__).read_text(encoding="utf-8")


def _rec(**kw):
    """MemoryRecord with test-neutral defaults; every field overridable."""
    base = dict(key="k", tokens=frozenset({"shot_A"}), age_seconds=0.0,
                distance=None, protected_floor=0.0)
    base.update(kw)
    return pgdrm.MemoryRecord(**base)


def _eval(record, **kw):
    base = dict(task_context_tokens=frozenset({"shot_A"}), decay_lambda=LN2,
                utility_threshold=0.0, distance_threshold=None)
    base.update(kw)
    return pgdrm.evaluate(record, **base)


# ===========================================================================
# 1 - PURITY: the whole point of this rung
# ===========================================================================

def test_kernel_imports_nothing_impure():
    """AST-level: the module may import only pure stdlib typing/math helpers.

    Mutation that turns this red: add `import time` to pgdrm.py.
    """
    tree = ast.parse(KERNEL_SRC)
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
            else:  # relative import - a sibling of the kernel
                roots.add("__relative__")
    assert roots <= {"__future__", "math", "dataclasses", "typing"}, (
        f"impure imports in pgdrm.py: {sorted(roots)}"
    )


@pytest.mark.parametrize("forbidden", [
    "time.time", "datetime", "random", "os.", "open(", "requests",
    "import hou", "anthropic", "sqlite3", "socket", "threading",
])
def test_kernel_source_names_no_impure_surface(forbidden):
    assert forbidden not in KERNEL_SRC, f"pgdrm.py references {forbidden!r}"


def test_kernel_never_returns_success_and_is_not_wired_to_the_port():
    """M2 hard refusal: the kernel is not a port. It has no substrate, so it
    may not speak the port's SUCCESS vocabulary, and it must not be wired into
    MemoryPort.query_and_filter (that is LOOP V0.2, blocked)."""
    assert "SUCCESS" not in KERNEL_SRC
    assert "PortResult" not in KERNEL_SRC
    assert "pgdrm" not in Path(ports.__file__).read_text(encoding="utf-8")
    # the ratified surface is untouched and still honest-UNAVAILABLE
    result = ports.MemoryPort().query_and_filter(["r"], ["t"])
    assert result.status == "UNAVAILABLE"


def test_evaluate_is_deterministic_across_calls():
    """Same inputs -> identical verdict. A clock read inside the decision
    function would make repeated calls drift."""
    r = _rec(age_seconds=3.0)
    first = _eval(r)
    second = _eval(r)
    assert first == second


def test_filter_does_not_mutate_its_inputs():
    records = (_rec(key="a"), _rec(key="b", tokens=frozenset({"other"})))
    tokens = {"shot_A"}
    snapshot = tuple(records)
    pgdrm.filter_records(records, task_context_tokens=tokens,
                         decay_lambda=LN2, utility_threshold=0.0)
    assert records == snapshot
    assert tokens == {"shot_A"}


# ===========================================================================
# 2 - DECAY: U = e^(-lambda * t), hand-computed
# ===========================================================================

@pytest.mark.parametrize("decay_lambda,age,expected,arithmetic", [
    # lambda = 0 -> e^0 = 1 exactly, for any age.
    (0.0, 0.0, 1.0, "e^(-0*0) = e^0 = 1"),
    (0.0, 1_000_000.0, 1.0, "e^(-0*1e6) = e^0 = 1"),
    # lambda = ln2 -> one half-life per unit of t: U = 2^-t
    (LN2, 0.0, 1.0, "e^(-ln2*0) = 2^-0 = 1"),
    (LN2, 1.0, 0.5, "e^(-ln2*1) = 2^-1 = 1/2"),
    (LN2, 2.0, 0.25, "e^(-ln2*2) = 2^-2 = 1/4"),
    (LN2, 3.0, 0.125, "e^(-ln2*3) = 2^-3 = 1/8"),
    (LN2, 10.0, 0.0009765625, "e^(-ln2*10) = 2^-10 = 1/1024"),
    # lambda = ln10 -> one decade per unit of t: U = 10^-t
    (LN10, 1.0, 0.1, "e^(-ln10*1) = 10^-1"),
    (LN10, 2.0, 0.01, "e^(-ln10*2) = 10^-2"),
    (LN10, 3.0, 0.001, "e^(-ln10*3) = 10^-3"),
    # scaled: lambda*t = 1 and 2 -> the standard constants 1/e and 1/e^2
    (0.001, 1000.0, 0.36787944117144233, "e^(-0.001*1000) = e^-1 = 1/e"),
    (0.5, 4.0, 0.1353352832366127, "e^(-0.5*4) = e^-2"),
])
def test_decay_table_hand_computed(decay_lambda, age, expected, arithmetic):
    """Mutation that turns this red: flip the sign in exp(-decay_lambda*age)."""
    got = pgdrm.decay_utility(decay_lambda, age)
    assert got == pytest.approx(expected, rel=1e-12, abs=1e-15), arithmetic


def test_decay_is_monotonically_non_increasing_in_age():
    ages = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 64.0]
    us = [pgdrm.decay_utility(LN2, a) for a in ages]
    assert us == sorted(us, reverse=True)
    assert us[0] == 1.0


def test_decay_underflows_to_zero_not_to_an_exception():
    """A very old record must decay toward 0, never raise."""
    assert pgdrm.decay_utility(LN2, 1e9) == 0.0


# ===========================================================================
# 3 - protected_floor: ONE meaning (D6), and a test that DISTINGUISHES
#     the two readings
# ===========================================================================

def test_protected_floor_is_a_lower_bound_on_utility():
    """floor=0.9 with a raw decay of 2^-1 = 0.5 -> utility is lifted to 0.9.

    Mutation that turns this red: drop the max(raw, floor) clamp."""
    assert pgdrm.decay_utility(LN2, 1.0, protected_floor=0.9) == 0.9


def test_protected_floor_never_caps_a_fresher_record():
    """It is a FLOOR, not a ceiling: raw 2^-1 = 0.5 > floor 0.1 -> stays 0.5.

    Mutation that turns this red: min(raw, floor) instead of max."""
    assert pgdrm.decay_utility(LN2, 1.0, protected_floor=0.1) == 0.5


def test_protected_floor_reading_is_protection_not_eviction():
    """THE D6 DISCRIMINATOR.

    Reading A (RATIFIED HERE; blueprint prose + THE_LOOP_v5.1 step 9):
        protected_floor is a floor beneath which decay cannot push utility.
        U = max(e^(-lambda*t), floor).
    Reading B (the submitted code): floor is an eviction threshold -
        raw utility < floor  =>  DROP.

    The record below is constructed so the two readings DISAGREE:
        raw   = e^(-ln2*10) = 2^-10 = 0.0009765625   (hand-computed)
        floor = 0.5
        utility_threshold = 0.2
      Reading A: U = max(0.0009765625, 0.5) = 0.5;  0.5 >= 0.2  -> ALLOW
      Reading B: 0.0009765625 < 0.5                              -> DROP

    Mutation that turns this red: implement Reading B
    (`if raw < protected_floor: return DROP`).
    """
    settled = _rec(key="settlement_deposit", age_seconds=10.0, protected_floor=0.5)
    verdict = _eval(settled, utility_threshold=0.2)
    assert verdict.decision == pgdrm.ALLOW
    assert verdict.utility == 0.5
    assert verdict.reason == pgdrm.REASON_CLEAN


def test_without_a_floor_the_same_record_is_evicted_by_the_threshold():
    """Same age, floor=0.0: utility 2^-10 = 0.0009765625 < 0.2 -> DROP.
    Proves protected_floor and utility_threshold are two different knobs."""
    unprotected = _rec(key="stale", age_seconds=10.0, protected_floor=0.0)
    verdict = _eval(unprotected, utility_threshold=0.2)
    assert verdict.decision == pgdrm.DROP
    assert verdict.reason == pgdrm.REASON_DECAYED
    assert verdict.utility == pytest.approx(0.0009765625, rel=1e-12)


def test_utility_threshold_boundary_is_inclusive():
    """U == threshold is KEPT (strict <). 2^-1 = 0.5 exactly in binary float.

    Mutation that turns this red: `<=` instead of `<`."""
    r = _rec(age_seconds=1.0)
    assert _eval(r, utility_threshold=0.5).decision == pgdrm.ALLOW
    assert _eval(r, utility_threshold=0.5000001).decision == pgdrm.DROP


# ===========================================================================
# 4 - CONTAMINATION: exact-token set membership, no fuzzy, no embedding
# ===========================================================================

def test_clean_record_is_a_subset_of_the_task_context():
    r = _rec(tokens=frozenset({"shot_A"}))
    v = _eval(r, task_context_tokens=frozenset({"shot_A", "lighting"}))
    assert v.decision == pgdrm.ALLOW


def test_any_foreign_token_contaminates():
    """Mutation that turns this red: intersect instead of difference
    (`record.tokens & task_tokens` non-empty => clean)."""
    r = _rec(tokens=frozenset({"shot_A", "shot_B"}))
    v = _eval(r, task_context_tokens=frozenset({"shot_A"}))
    assert v.decision == pgdrm.DROP
    assert v.reason == pgdrm.REASON_CONTAMINATED
    assert v.detail["foreign_tokens"] == ("shot_B",)


def test_foreign_tokens_are_reported_sorted_and_complete():
    r = _rec(tokens=frozenset({"z_tok", "a_tok", "shot_A"}))
    v = _eval(r, task_context_tokens=frozenset({"shot_A"}))
    assert v.detail["foreign_tokens"] == ("a_tok", "z_tok")


@pytest.mark.parametrize("record_token,task_token", [
    ("shot_a", "shot_A"),     # case differs -> foreign (case-SENSITIVE)
    ("shot", "shot_010"),     # record token is a prefix -> foreign
    ("shot_010", "shot"),     # task token is a prefix -> foreign
    (" shot_A", "shot_A"),    # whitespace is significant
    ("shot_A ", "shot_A"),
])
def test_matching_is_exact_not_fuzzy(record_token, task_token):
    """Mutation that turns this red: casefold/startswith/`in` matching."""
    v = _eval(_rec(tokens=frozenset({record_token})),
              task_context_tokens=frozenset({task_token}))
    assert v.decision == pgdrm.DROP
    assert v.reason == pgdrm.REASON_CONTAMINATED


def test_untagged_record_claims_no_task_scope_and_passes_the_token_axis():
    """An empty token set has no foreign token, so it cannot be cross-task
    contamination. Documented semantics, pinned here."""
    v = _eval(_rec(tokens=frozenset()), task_context_tokens=frozenset({"shot_A"}))
    assert v.decision == pgdrm.ALLOW


def test_empty_task_context_makes_every_tagged_record_foreign():
    v = _eval(_rec(tokens=frozenset({"shot_A"})), task_context_tokens=frozenset())
    assert v.decision == pgdrm.DROP
    assert v.reason == pgdrm.REASON_CONTAMINATED


def test_non_string_token_is_rejected():
    """No numeric/embedding smuggling through the token axis."""
    with pytest.raises(TypeError):
        _eval(_rec(tokens=frozenset({1})))
    with pytest.raises(TypeError):
        _eval(_rec(), task_context_tokens=frozenset({1}))


# ===========================================================================
# 5 - DISTANCE: implemented, or it would not exist (D4)
# ===========================================================================

def test_distance_axis_is_off_when_no_threshold_is_given():
    """threshold=None -> the axis is inactive and distance is ignored."""
    v = _eval(_rec(distance=99.0), distance_threshold=None)
    assert v.decision == pgdrm.ALLOW


def test_distance_beyond_threshold_drops():
    """Mutation that turns this red: `<` instead of `>` in the comparison."""
    v = _eval(_rec(distance=0.31), distance_threshold=0.30)
    assert v.decision == pgdrm.DROP
    assert v.reason == pgdrm.REASON_DISTANCE_EXCEEDED
    assert v.detail["distance"] == 0.31


def test_distance_at_and_below_threshold_is_kept():
    assert _eval(_rec(distance=0.30), distance_threshold=0.30).decision == pgdrm.ALLOW
    assert _eval(_rec(distance=0.29), distance_threshold=0.30).decision == pgdrm.ALLOW


def test_unmeasured_distance_fails_closed():
    """An unevaluable axis is not an open axis (AGENTS.md Law 4 + the repo's
    own mapper: None => BLOCK). Unmeasured renders UNKNOWN, never zero.

    Mutation that turns this red: treat distance=None as passing."""
    v = _eval(_rec(distance=None), distance_threshold=0.30)
    assert v.decision == pgdrm.DROP
    assert v.reason == pgdrm.REASON_DISTANCE_UNMEASURED
    assert v.detail["distance"] is None


# ===========================================================================
# 6 - PRECEDENCE: the composed case, not the isolated one
# ===========================================================================

def test_contamination_outranks_distance_and_decay():
    """Mutation that turns this red: reorder the checks so decay runs first."""
    worst = _rec(key="worst", tokens=frozenset({"other"}), age_seconds=50.0,
                 distance=9.0)
    v = _eval(worst, distance_threshold=0.1, utility_threshold=0.9)
    assert v.reason == pgdrm.REASON_CONTAMINATED


def test_distance_outranks_decay():
    r = _rec(key="far_and_old", age_seconds=50.0, distance=9.0)
    v = _eval(r, distance_threshold=0.1, utility_threshold=0.9)
    assert v.reason == pgdrm.REASON_DISTANCE_EXCEEDED


# ===========================================================================
# 7 - filter_records: order-preserving, deterministic
# ===========================================================================

def test_filter_preserves_input_order_and_partitions_correctly():
    records = (
        _rec(key="clean_fresh", age_seconds=0.0),
        _rec(key="foreign", tokens=frozenset({"shot_B"})),
        _rec(key="protected_old", age_seconds=10.0, protected_floor=0.5),
        _rec(key="stale", age_seconds=10.0),
    )
    res = pgdrm.filter_records(records, task_context_tokens=frozenset({"shot_A"}),
                               decay_lambda=LN2, utility_threshold=0.2)
    assert tuple(v.key for v in res.verdicts) == (
        "clean_fresh", "foreign", "protected_old", "stale")
    assert res.kept == ("clean_fresh", "protected_old")
    assert res.dropped == ("foreign", "stale")


def test_filter_is_deterministic():
    records = (_rec(key="a"), _rec(key="b", tokens=frozenset({"x"})))
    kw = dict(task_context_tokens=frozenset({"shot_A"}), decay_lambda=LN2,
              utility_threshold=0.0)
    assert pgdrm.filter_records(records, **kw) == pgdrm.filter_records(records, **kw)


def test_filter_of_nothing_is_empty_not_an_error():
    res = pgdrm.filter_records((), task_context_tokens=frozenset({"shot_A"}),
                               decay_lambda=LN2, utility_threshold=0.0)
    assert res.kept == () and res.dropped == () and res.verdicts == ()


# ===========================================================================
# 8 - DOMAIN VALIDATION: bad input raises, never silently coerces
# ===========================================================================

@pytest.mark.parametrize("kwargs", [
    dict(decay_lambda=-1.0),
    dict(utility_threshold=-0.1),
    dict(utility_threshold=1.1),
    dict(distance_threshold=-0.5),
])
def test_out_of_domain_parameters_raise_value_error(kwargs):
    with pytest.raises(ValueError):
        _eval(_rec(), **kwargs)


@pytest.mark.parametrize("bad", [
    dict(age_seconds=-1.0),
    dict(protected_floor=-0.1),
    dict(protected_floor=1.1),
    dict(distance=-0.5),
])
def test_out_of_domain_record_fields_raise_value_error(bad):
    with pytest.raises(ValueError):
        _eval(_rec(**bad))


def test_bool_is_not_a_number_here():
    """True is an int subclass; ports.py already refuses that trick."""
    with pytest.raises(TypeError):
        pgdrm.decay_utility(True, 1.0)
    with pytest.raises(TypeError):
        pgdrm.decay_utility(1.0, True)


def test_nan_is_rejected_everywhere_it_could_fake_a_pass():
    """NaN compares False against everything, so an unguarded NaN distance
    would slide past `distance > threshold` and be reported ALLOW — a filter
    verdict computed from a value that is not a number.

    Mutation that turns this red: drop the isnan guard in _number."""
    nan = float("nan")
    with pytest.raises(ValueError):
        _eval(_rec(distance=nan), distance_threshold=0.3)
    with pytest.raises(ValueError):
        pgdrm.decay_utility(nan, 1.0)
    with pytest.raises(ValueError):
        pgdrm.decay_utility(1.0, nan)


def test_describe_is_pure_string_formatting():
    v = _eval(_rec(key="rec1", tokens=frozenset({"shot_B"})))
    line = pgdrm.describe(v)
    assert line.startswith("rec1: DROP (CONTAMINATED_TOKENS)")
    assert "shot_B" in line


def test_decay_utility_rejects_negative_lambda_and_age():
    with pytest.raises(ValueError):
        pgdrm.decay_utility(-0.1, 1.0)
    with pytest.raises(ValueError):
        pgdrm.decay_utility(0.1, -1.0)
