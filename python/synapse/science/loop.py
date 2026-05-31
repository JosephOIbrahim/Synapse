from __future__ import annotations

from .probe import ProbeSpec, ProbeResult
from .registry import Record, Registry


def run_search(
    specs,
    registry,
    probe_fn,
    *,
    require_second_seed: bool = False,
    confirmed=None,
) -> dict:
    """Drive a falsifiability-gated probe search over a list of ProbeSpecs.

    specs:       list[ProbeSpec] — claims to verify.
    registry:    Registry — dedup-aware sink (skip-known prevents re-walks).
    probe_fn:    callable(ProbeSpec) -> ProbeResult — injected probe runner.
    require_second_seed:
                 if True, a champion claim is HELD (not recorded) until it has
                 been confirmed on a second seed (present in `confirmed`).
    confirmed:   optional set of (surface, kind) tuples already confirmed on a
                 2nd seed.

    Returns:
        {
            "recorded": [Record, ...],   # newly recorded this run
            "skipped":  [surface, ...],  # already known, not re-walked
            "held":     [surface, ...],  # champion awaiting 2nd-seed confirmation
            "halted":   [surface, ...],  # record() unexpectedly returned False
        }
    """
    confirmed_set = confirmed if confirmed is not None else set()

    recorded: list[Record] = []
    skipped: list[str] = []
    held: list[str] = []
    halted: list[str] = []

    # 1. iterate specs sorted by rank DESC.
    for spec in sorted(specs, key=lambda s: s.rank, reverse=True):
        # 2. SKIP (no re-walk) anything already known.
        if registry.known(spec.surface, spec.kind) is not None:
            skipped.append(spec.surface)
            continue

        # 3. probe.
        result = probe_fn(spec)

        # 4. classify.
        status = "champion" if result.present else "dead_end"

        # 5. SECOND-SEED GATE.
        if (
            require_second_seed
            and status == "champion"
            and (spec.surface, spec.kind) not in confirmed_set
        ):
            held.append(spec.surface)
            continue

        # 6. record.
        detail = result.signature or (result.error or "")
        rec = Record(
            surface=spec.surface,
            kind=spec.kind,
            status=status,
            detail=detail,
            context=spec.rationale,
        )
        if registry.record(rec):
            recorded.append(rec)
        else:
            # skip-known in step 2 already prevents contradictions; a False
            # here is unexpected — do not overwrite, surface it as halted.
            halted.append(spec.surface)

    # 7. return classified buckets.
    return {
        "recorded": recorded,
        "skipped": skipped,
        "held": held,
        "halted": halted,
    }
