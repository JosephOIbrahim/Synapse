"""Stage 2 of the selector: turn a prediction and a measurement into a verdict.

The policy is plain code and its thresholds are visible. The rules, in order:

1. No observation means the candidate never ran — ``REJECTED_SCREENING``.
2. A measurement worse than the prediction's own regression bound is ``REMOVE``.
3. No improvement at all is ``REMOVE`` — an edit that costs nothing is still not
   free, and an unimproved harness should not carry it.
4. Any named regression when the prediction allowed none is ``REMOVE``.
5. An improvement that reaches a fraction of what was predicted is ``RETAIN`` —
   or ``REPLACE`` when an incumbent is supplied and beaten by a margin.
6. Anything else is ``REVISE``: the direction was right, the size was not.

The verdict is recorded either way. A losing candidate is not noise; it is the
record that stops the same edit being proposed again.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .schema import AttemptRecord, Observation, Prediction, SelectorVerdict
from .store import SIMStore


@dataclass(frozen=True)
class SelectorPolicy:
    """Thresholds for stage 2. All visible, none inferred by a model."""

    min_prediction_fraction: float = 0.5
    replace_margin: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 < self.min_prediction_fraction <= 1.0:
            raise ValueError("min_prediction_fraction must be in (0, 1]")
        if self.replace_margin < 0:
            raise ValueError("replace_margin must not be negative")


DEFAULT_POLICY = SelectorPolicy()


def verdict_for(
    prediction: Prediction,
    observation: Observation | None,
    *,
    incumbent_delta: float | None = None,
    policy: SelectorPolicy = DEFAULT_POLICY,
) -> SelectorVerdict:
    """Apply the policy to one attempt."""
    if observation is None:
        return SelectorVerdict.REJECTED_SCREENING

    measured = float(observation.measured_delta)

    if measured < -float(prediction.max_regression):
        return SelectorVerdict.REMOVE
    if measured <= 0:
        return SelectorVerdict.REMOVE
    if observation.regressions and prediction.max_regression == 0:
        return SelectorVerdict.REMOVE

    target = float(prediction.expected_delta) * policy.min_prediction_fraction
    if measured >= target:
        if incumbent_delta is not None and measured > float(incumbent_delta) + policy.replace_margin:
            return SelectorVerdict.REPLACE
        return SelectorVerdict.RETAIN
    return SelectorVerdict.REVISE


def finalize(
    record: AttemptRecord,
    observation: Observation | None,
    *,
    incumbent_delta: float | None = None,
    policy: SelectorPolicy = DEFAULT_POLICY,
) -> AttemptRecord:
    """A new record with the observation and the verdict filled in.

    Records are immutable, so this returns a replacement rather than mutating.
    """
    verdict = verdict_for(
        record.ex_ante_prediction, observation, incumbent_delta=incumbent_delta, policy=policy
    )
    return replace(record, ex_post_observation=observation, selector_verdict=verdict)


def record_outcome(store: SIMStore, record: AttemptRecord) -> AttemptRecord:
    """Append the finalized record. The cluster must already be declared."""
    store.append(record)
    return record


def summarize(records: list[AttemptRecord]) -> dict[str, Any]:
    """Counts by verdict, for a health view or a test."""
    counts = {verdict.value: 0 for verdict in SelectorVerdict}
    for record in records:
        counts[record.selector_verdict.value] += 1
    return {"total": len(records), "by_verdict": counts}
