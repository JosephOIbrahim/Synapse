#!/usr/bin/env python
"""V3 producer — demonstrate that colour is COMPUTED, and that age wins.

    python harness/notes/econ/v3_stale_demo.py [--from V3_probe_live.install.json]

Emits ``harness/notes/econ/V3_stale_demo.json``.

Two things are demonstrated on REAL probe rows, not on fixtures:

1. **Colour is computed at read time.** The same immutable ``ProbeResult``
   objects are read at a sweep of clock offsets. Nothing about a row changes;
   its colour does. If colour were stored, every column of the sweep would be
   identical — so the sweep is a check that can fail.

2. **Staleness degrades to GREY, never to green.** Every row that was GREEN
   is GREY once ``probed_at`` is aged past the TTL, and a row that was RED
   goes GREY too rather than staying RED. UNKNOWN outranks both verdicts,
   because a probe that has not run recently knows nothing.

The negative control is the third block: a row aged past the TTL and then
**re-probed** returns to its live colour. Without it, "everything goes grey
eventually" would be indistinguishable from a function that always says grey.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "python"))

from synapse.panel.providers import probe as P    # noqa: E402


def rows_from_artifact(path: pathlib.Path):
    """Rebuild ProbeResult objects from a recorded live probe."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in payload["rows"]:
        out.append(P.ProbeResult(
            model=r["model"],
            tier_candidates=tuple(r["tier_candidates"]),
            available=r["available"],
            quota_remaining=r["quota_remaining"],
            quota_total=r["quota_total"],
            cost_per_1k_in=r["cost_per_1k_in"],
            cost_per_1k_out=r["cost_per_1k_out"],
            latency_ms=r["latency_ms"],
            probed_at=r["probed_at"],
            provider=r["provider"],
            method=r["method"],
            reason=r["reason"],
            evidence_tier=r["evidence_tier"],
            quota_source=r["quota_source"],
            cost_source=r["cost_source"],
            tier_basis=r["tier_basis"],
            declared=r["declared"],
            live=r["live"],
            capabilities=tuple(r["capabilities"]) if r["capabilities"] else None,
            detail=r["detail"],
        ))
    return out, payload


def counts(rows, now):
    c = {k: 0 for k in P.COLOURS}
    for r in rows:
        c[P.colour_for(r, now=now)] += 1
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="V3_probe_live.install.json")
    args = ap.parse_args()

    src = HERE.parent / args.src
    rows, payload = rows_from_artifact(src)
    base = max((r.probed_at for r in rows if r.probed_at), default=time.time())

    # -- 1 · the sweep: same objects, advancing clock ----------------------
    offsets = [0.0, 30.0, 59.9, 60.0, 179.9, P.PROBE_TTL_S, P.PROBE_TTL_S + 0.001,
               300.0, 3600.0]
    sweep = []
    for off in offsets:
        now = base + off
        sweep.append({
            "offset_s": off,
            "counts": counts(rows, now),
            "would_refresh": P.should_refresh(rows[0], now=now),
        })

    # -- 2 · per-row transition, one row at a time -------------------------
    sample = []
    for r in rows[:6] + [r for r in rows if not r.available][:2]:
        fresh = P.colour_for(r, now=base)
        aged = P.colour_for(r, now=base + P.PROBE_TTL_S + 1)
        sample.append({
            "provider": r.provider, "model": r.model,
            "available": r.available, "reason": r.reason,
            "colour_at_probe_time": fresh,
            "colour_after_ttl": aged,
            "row_bytes_changed": False,
        })

    # -- 3 · artificial ageing of the FIELD, not the clock -----------------
    # dataclasses.replace produces a new row whose probed_at is old. This is
    # the brief's "probed_at aged artificially" case explicitly.
    green_rows = [r for r in rows if P.colour_for(r, now=base) == P.COLOUR_GREEN]
    aged_rows = [dataclasses.replace(r, probed_at=base - (P.PROBE_TTL_S + 1))
                 for r in green_rows]
    aged_counts = counts(aged_rows, base)

    # -- negative control: re-probing restores the live colour -------------
    reprobed = [dataclasses.replace(r, probed_at=base) for r in aged_rows]
    reprobed_counts = counts(reprobed, base)

    # -- staleness outranks availability, in both directions ---------------
    red_rows = [r for r in rows if P.colour_for(r, now=base) == P.COLOUR_RED]
    red_aged = [P.colour_for(dataclasses.replace(
        r, probed_at=base - (P.PROBE_TTL_S + 1)), now=base) for r in red_rows]

    checks = {
        "C1_colour_varies_with_clock_alone": {
            "condition_under_which_this_fails":
                "colour_for ignores probed_at, or colour is a stored field — "
                "then every offset in the sweep reports identical counts",
            "distinct_count_vectors": len({json.dumps(s["counts"], sort_keys=True)
                                           for s in sweep}),
            "pass": len({json.dumps(s["counts"], sort_keys=True)
                         for s in sweep}) > 1,
        },
        "C2_aged_green_becomes_grey_never_stays_green": {
            "condition_under_which_this_fails":
                "colour_for checks `available` before it checks age",
            "green_before": len(green_rows),
            "green_after_ageing": aged_counts[P.COLOUR_GREEN],
            "grey_after_ageing": aged_counts[P.COLOUR_GREY],
            "pass": aged_counts[P.COLOUR_GREEN] == 0
                    and aged_counts[P.COLOUR_GREY] == len(green_rows),
        },
        "C3_aged_red_becomes_grey_too": {
            "condition_under_which_this_fails":
                "RED is treated as a terminal verdict that survives staleness — "
                "it must not, because an old 'no' is also UNKNOWN",
            "red_before": len(red_rows),
            "still_red_after_ageing": sum(1 for c in red_aged if c == P.COLOUR_RED),
            "pass": all(c == P.COLOUR_GREY for c in red_aged),
        },
        "C4_negative_control_reprobe_restores_colour": {
            "condition_under_which_this_fails":
                "colour_for always returns grey — the ageing demonstration "
                "would then prove nothing at all",
            "green_after_reprobe": reprobed_counts[P.COLOUR_GREEN],
            "pass": reprobed_counts[P.COLOUR_GREEN] == len(green_rows),
        },
        "C5_future_stamp_is_grey_not_green": {
            "condition_under_which_this_fails":
                "is_stale drops its age<0 clause — a skewed clock would then "
                "hold a rail green indefinitely",
            "skewed_green": counts(
                [dataclasses.replace(r, probed_at=base + 3600) for r in green_rows],
                base)[P.COLOUR_GREEN],
            "pass": counts(
                [dataclasses.replace(r, probed_at=base + 3600) for r in green_rows],
                base)[P.COLOUR_GREEN] == 0,
        },
        "C6_colour_is_absent_from_the_structure": {
            "condition_under_which_this_fails":
                "a colour/status field is added to ProbeResult",
            "fields": list(P.result_field_names()),
            "pass": not ({"colour", "color", "status", "state"}
                         & set(P.result_field_names())),
        },
    }

    out = {
        "schema": "v3_stale_demo/v1",
        "producer": "harness/notes/econ/v3_stale_demo.py",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_artifact": str(src.name),
        "source_generated": payload.get("generated"),
        "rows": len(rows),
        "ttl_s": P.PROBE_TTL_S,
        "refresh_interval_s": P.REFRESH_INTERVAL_S,
        "sweep": sweep,
        "sample_transitions": sample,
        "checks": checks,
        "all_checks_pass": all(c["pass"] for c in checks.values()),
    }
    dest = HERE.parent / "V3_stale_demo.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print("wrote %s" % dest)
    print("\noffset_s   green  red  grey   refresh?")
    for s in sweep:
        c = s["counts"]
        print("  %8.3f  %5d %4d %5d   %s"
              % (s["offset_s"], c["green"], c["red"], c["grey"], s["would_refresh"]))
    print("\nartificial ageing of probed_at (clock held still):")
    print("  %d GREEN rows -> green=%d grey=%d"
          % (len(green_rows), aged_counts["green"], aged_counts["grey"]))
    print("  negative control, re-probed -> green=%d" % reprobed_counts["green"])
    for name, c in checks.items():
        print("  %-46s %s" % (name, "PASS" if c["pass"] else "FAIL"))
    return 0 if out["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
