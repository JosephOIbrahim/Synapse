"""pgdrm.py — the PG-DRM kernel: a pure, deterministic, zero-LLM filter.

PG-DRM (Pre-Generation Diagnostic Retrieval Monitoring) is the step-3 filter of
THE LOOP v5.1: it decides, for each recalled memory record, whether that record
may enter the prompt. `docs/THE_LOOP_v5.1.md` §2.4 fixes the mechanism —
"deterministic string tokens, metadata flags, and vector distance thresholds —
never LLM inference": `(Context, Task Context) -> {ALLOW, DROP}`.

WHAT THIS MODULE IS
-------------------
The math, and only the math. It is a set of pure functions over plain values:

  * no I/O of any kind, no filesystem, no network
  * no `hou`, no Houdini, no main-thread marshalling
  * no store handle, no Moneta, no singleton, no module-level mutable state
  * no model call, no embedder call
  * **time is a PARAMETER** (`age_seconds`), measured by the caller and passed
    in. The decision function never reads a clock.

That last rule is load-bearing. In the submitted spec the decay branch was
unreachable because the test built a record from the wall clock and a decay
constant that could not move it off 1.0 within the test's lifetime
(adjudication D5). Age-as-a-parameter makes the whole decay curve reachable
from a table.

WHAT THIS MODULE IS NOT
-----------------------
It is **not** a port and it is not wired into one. `MemoryPort.query_and_filter`
stays contract-surface-only and reports UNAVAILABLE until LOOP rung V0.2, which
is blocked on the Moneta headless seam. Wiring the kernel into the port is that
rung's work, not this one's, so this module never imports `ports` and never
returns a port status: it has no substrate, and a verdict shaped like a port
result would be a capability claim it cannot back.

Nothing here reports a filter verdict it did not compute. An axis that cannot
be evaluated (an unmeasured vector distance while the distance axis is active)
DROPS — an unevaluable axis is not an open axis, matching this repo's own
`mapper.GATE_POLICY`, where an unevaluable predicate BLOCKs.

THE DECAY LAW
-------------
    U_raw(t) = e^(-lambda * t)              lambda >= 0, t >= 0
    U(t)     = max(U_raw(t), protected_floor)

`protected_floor` HAS EXACTLY ONE MEANING HERE — and it is the one the ratified
prose carries (`docs/THE_LOOP_v5.1.md` step 9: a settlement deposit is written
"with protected_floor"; "UUID expired: written as new deposit with protected
floor"):

    protected_floor is a LOWER BOUND on utility. It is the level beneath which
    decay cannot push a record. A record deposited with a floor of 0.5 still
    scores 0.5 after ten half-lives.

It is **not** an eviction threshold. The submitted implementation used it as one
(`utility < protected_floor => drop`), which inverts the meaning: under that
reading a HIGH floor would evict a record faster, so the parameter that is
supposed to protect a deposit would destroy it (adjudication D6). Eviction is
the separate, explicitly named `utility_threshold` argument of `evaluate`.
`tests/test_pgdrm_kernel.py::test_protected_floor_reading_is_protection_not_eviction`
is built so the two readings return opposite verdicts on one record.

THE CONTAMINATION LAW
---------------------
Exact set membership, nothing else:

    foreign = record.tokens - task_context_tokens
    foreign non-empty  =>  DROP

Tokens are compared as exact strings: case-sensitive, whitespace-significant,
no prefix match, no substring match, no stemming, no embedding, no similarity.
A non-string token is a TypeError, not a coerced comparison.

Two edge semantics are deliberate and pinned by tests:

  * A record with an EMPTY token set claims no task scope, therefore carries no
    foreign token, therefore passes this axis. Untagged is not contaminated.
  * An EMPTY task context makes every tagged record foreign. If the caller
    cannot say what the task is, no scoped memory is admitted.

PRECEDENCE
----------
Checks run in a fixed order and the first failure wins, so a verdict's `reason`
is stable and a caller can act on it:

    1. contamination  (cheapest, and the safety-relevant one)
    2. distance       (only when `distance_threshold` is not None)
    3. decay          (utility below `utility_threshold`)

BOUNDARIES
----------
    utility <  utility_threshold      -> DROP   (equal is KEPT)
    distance >  distance_threshold    -> DROP   (equal is KEPT)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Verdict vocabulary. Deliberately NOT the port vocabulary: this kernel has no
# substrate to speak for.
# ---------------------------------------------------------------------------

ALLOW = "ALLOW"
DROP = "DROP"
DECISIONS = frozenset({ALLOW, DROP})

REASON_CLEAN = "CLEAN"
REASON_CONTAMINATED = "CONTAMINATED_TOKENS"
REASON_DISTANCE_UNMEASURED = "DISTANCE_UNMEASURED"
REASON_DISTANCE_EXCEEDED = "DISTANCE_EXCEEDED"
REASON_DECAYED = "DECAYED"
REASONS = frozenset({
    REASON_CLEAN,
    REASON_CONTAMINATED,
    REASON_DISTANCE_UNMEASURED,
    REASON_DISTANCE_EXCEEDED,
    REASON_DECAYED,
})


# ---------------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryRecord:
    """One recalled record, as plain values the caller already measured.

    key
        Caller's identifier. Opaque here; echoed into the verdict.
    tokens
        The exact task-scope tokens this record was deposited under. Empty
        means untagged, which claims no scope (see module docstring).
    age_seconds
        How old the record is AT DECISION TIME, measured by the caller. The
        kernel never reads a clock. The unit is whatever unit `decay_lambda`
        is expressed per; "seconds" is the intended one.
    distance
        Vector distance from the record to the task query, if the caller
        measured one. `None` means UNMEASURED, which is not the same as zero
        and is never treated as zero.
    protected_floor
        Lower bound on this record's utility. A floor, never an eviction
        threshold (see module docstring).
    """

    key: str
    tokens: frozenset
    age_seconds: float
    distance: Optional[float] = None
    protected_floor: float = 0.0


@dataclass(frozen=True)
class Verdict:
    """One record's decision. `utility` is always the computed U, even when the
    record was dropped on an earlier axis, so a caller can log the curve."""

    key: str
    decision: str
    reason: str
    utility: float
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FilterResult:
    """Input-ordered verdicts plus the two key partitions."""

    verdicts: Tuple[Verdict, ...]
    kept: Tuple[str, ...]
    dropped: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Validation. Bad input raises; it is never silently coerced, and it never
# degrades into a permissive default.
# ---------------------------------------------------------------------------


def _number(name: str, value: Any, low: float, high: Optional[float]) -> float:
    # bool is an int subclass; a flag is not a magnitude. ports.py refuses the
    # same trick on `probability`.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, got {value!r}")
    v = float(value)
    if math.isnan(v):
        raise ValueError(f"{name} must be a real number, got NaN")
    if v < low or (high is not None and v > high):
        upper = "inf" if high is None else repr(high)
        raise ValueError(f"{name} must be in [{low}, {upper}], got {v!r}")
    return v


def _token_set(name: str, tokens: Any) -> frozenset:
    if isinstance(tokens, str) or not isinstance(tokens, Iterable):
        raise TypeError(f"{name} must be an iterable of str, got {tokens!r}")
    out = frozenset(tokens)
    bad = [t for t in out if not isinstance(t, str)]
    if bad:
        raise TypeError(
            f"{name} must contain only str tokens; exact membership is the "
            f"whole mechanism. Offending: {bad!r}"
        )
    return out


# ---------------------------------------------------------------------------
# The decay law
# ---------------------------------------------------------------------------


def decay_utility(decay_lambda: float, age_seconds: float,
                  protected_floor: float = 0.0) -> float:
    """U = max(e^(-decay_lambda * age_seconds), protected_floor).

    Pure. `age_seconds` is supplied by the caller; no clock is read here.

    A very old record underflows toward 0.0 rather than raising — decaying out
    is the designed end state, not an error. `decay_lambda = 0` disables decay
    (U = 1 for every age).
    """
    lam = _number("decay_lambda", decay_lambda, 0.0, None)
    age = _number("age_seconds", age_seconds, 0.0, None)
    floor = _number("protected_floor", protected_floor, 0.0, 1.0)
    if math.isinf(lam) or math.isinf(age):
        raw = 0.0 if (lam > 0.0 and age > 0.0) else 1.0
    else:
        raw = math.exp(-lam * age)
    return max(raw, floor)


# ---------------------------------------------------------------------------
# The decision function
# ---------------------------------------------------------------------------


def evaluate(record: MemoryRecord,
             *,
             task_context_tokens: Iterable[str],
             decay_lambda: float,
             utility_threshold: float,
             distance_threshold: Optional[float] = None) -> Verdict:
    """ALLOW or DROP one record. Pure, deterministic, zero-LLM.

    task_context_tokens
        The exact tokens describing the task being served right now.
    decay_lambda
        Decay rate per unit of `record.age_seconds`. 0 disables decay.
    utility_threshold
        Eviction threshold in [0, 1]. `utility < threshold` DROPs; equal keeps.
        This — not `protected_floor` — is what evicts.
    distance_threshold
        `None` turns the distance axis OFF and `record.distance` is ignored.
        A number turns it ON, and then an UNMEASURED distance DROPs (fail
        closed) rather than passing.
    """
    if not isinstance(record, MemoryRecord):
        raise TypeError(f"record must be a MemoryRecord, got {record!r}")

    task_tokens = _token_set("task_context_tokens", task_context_tokens)
    rec_tokens = _token_set("record.tokens", record.tokens)
    lam = _number("decay_lambda", decay_lambda, 0.0, None)
    u_threshold = _number("utility_threshold", utility_threshold, 0.0, 1.0)
    age = _number("record.age_seconds", record.age_seconds, 0.0, None)
    floor = _number("record.protected_floor", record.protected_floor, 0.0, 1.0)
    d_threshold = (None if distance_threshold is None
                   else _number("distance_threshold", distance_threshold, 0.0, None))
    distance = (None if record.distance is None
                else _number("record.distance", record.distance, 0.0, None))

    utility = decay_utility(lam, age, floor)

    # 1 - contamination: exact set difference, no fuzzy match anywhere.
    foreign = rec_tokens - task_tokens
    if foreign:
        return Verdict(
            key=record.key, decision=DROP, reason=REASON_CONTAMINATED,
            utility=utility,
            detail={"foreign_tokens": tuple(sorted(foreign))},
        )

    # 2 - distance, only when the axis is switched on by a threshold.
    if d_threshold is not None:
        if distance is None:
            # Unmeasured renders UNKNOWN, never zero; an unevaluable axis is
            # not an open axis.
            return Verdict(
                key=record.key, decision=DROP,
                reason=REASON_DISTANCE_UNMEASURED, utility=utility,
                detail={"distance": None, "distance_threshold": d_threshold},
            )
        if distance > d_threshold:
            return Verdict(
                key=record.key, decision=DROP,
                reason=REASON_DISTANCE_EXCEEDED, utility=utility,
                detail={"distance": distance, "distance_threshold": d_threshold},
            )

    # 3 - decay.
    if utility < u_threshold:
        return Verdict(
            key=record.key, decision=DROP, reason=REASON_DECAYED,
            utility=utility,
            detail={"utility_threshold": u_threshold, "protected_floor": floor},
        )

    return Verdict(key=record.key, decision=ALLOW, reason=REASON_CLEAN,
                   utility=utility, detail={"protected_floor": floor})


def filter_records(records: Sequence[MemoryRecord],
                   *,
                   task_context_tokens: Iterable[str],
                   decay_lambda: float,
                   utility_threshold: float,
                   distance_threshold: Optional[float] = None) -> FilterResult:
    """Apply `evaluate` to each record, preserving input order.

    Read-only by construction: neither the records nor the token set are
    mutated, and nothing is cached between calls.
    """
    task_tokens = _token_set("task_context_tokens", task_context_tokens)
    verdicts = tuple(
        evaluate(r,
                 task_context_tokens=task_tokens,
                 decay_lambda=decay_lambda,
                 utility_threshold=utility_threshold,
                 distance_threshold=distance_threshold)
        for r in records
    )
    return FilterResult(
        verdicts=verdicts,
        kept=tuple(v.key for v in verdicts if v.decision == ALLOW),
        dropped=tuple(v.key for v in verdicts if v.decision == DROP),
    )


def describe(verdict: Verdict) -> str:
    """One-line human-readable form. Pure string formatting."""
    bits: Mapping[str, Any] = verdict.detail
    extra = " ".join(f"{k}={v!r}" for k, v in sorted(bits.items()))
    return (f"{verdict.key}: {verdict.decision} ({verdict.reason}) "
            f"U={verdict.utility!r}" + (f" {extra}" if extra else ""))
