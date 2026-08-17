"""W5-WXA — crucible shard A adversarial matrix over the cook-verify contracts.

FIRST-HAND probe (crucible criterion 1: evidence from my own run, never inherited).
Feeds each of the five output-kind contracts in ``synapse.validation.measures`` a
MALFORMED / None / wrong-TYPE observation the W5-MEASURES builder did NOT fixture
(the builder covered ABSENT and present-but-HOLLOW/EMPTY inputs; this probe covers
present-but-WRONG-TYPE inputs) and records the ACTUAL outcome.

Crucible law under audit: "unobtainable renders UNKNOWN, never zero, never estimate."
Every case is classified by what the contract actually did:

  UNKNOWN   honest — the guard rendered UNKNOWN with a reason               (PASS)
  FAIL      graceful — the guard rendered a measured-bad verdict            (PASS-ish)
  MEASURED  the guard accepted the garbage as a real measurement           (SOFT-PASS?)
  CRASH     the guard raised — neither a verdict nor UNKNOWN; it aborted    (HOLE)

A CRASH is the finding-of-interest: a malformed observation is "unobtainable as
judged" and the crucible criterion wants UNKNOWN, but an unhandled exception is
worse than a zero — the honesty guard did not run to a verdict at all.

Run against a wave5/measures checkout (the module is not on master):
    python harness/probes/wxa/adversarial_matrix.py <path-to/python>   # e.g. _m/python
Default: env WXA_MEASURES_PYROOT, else <repo>/_m/python beside this script's tree.

Pure Python, zero hou. Read-only: imports and calls the contracts, mutates nothing.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def _resolve_pyroot() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).resolve()
    env = os.environ.get("WXA_MEASURES_PYROOT")
    if env:
        return Path(env).resolve()
    # default: the side tree _m/python at the worktree root (two levels up from
    # harness/probes/wxa/). Ephemeral — created by `git worktree add --detach _m`.
    here = Path(__file__).resolve()
    return here.parents[3] / "_m" / "python"


PYROOT = _resolve_pyroot()
sys.path.insert(0, str(PYROOT))

from synapse.validation.measures import (  # noqa: E402
    measure, measure_image, measure_sim, measure_geometry,
    measure_channels, measure_graph,
    MEASURED, UNKNOWN, FAIL, EXPLODING,
)

_CONTRACT = {
    "image": measure_image,
    "sim": measure_sim,
    "geometry": measure_geometry,
    "channels": measure_channels,
    "graph": measure_graph,
}

# (case_id, kind, obs, builder_fixtured_this?, why_adversarial)
# kind "dispatch" routes through measure(kind, obs) rather than a direct contract.
MATRIX = [
    # ── image ── builder fixtured absent + empty stats ({}, [], {"R":{}}); NOT scalar/typed-garbage
    ("img/stats-scalar",     "image",    {"resolution": [8, 8], "stats": 0.5},
     "a bare scalar as stats (not per-channel dict/list)"),
    ("img/res-noniter",      "image",    {"resolution": 1080, "stats": {"R": 0.5}},
     "resolution a bare int, not an (w,h) pair"),
    ("img/res-string-elems", "image",    {"resolution": ["a", "b"], "stats": {"R": 0.5}},
     "resolution elements non-numeric strings"),
    # ── sim ── builder fixtured absent frames + string strain inside a dict frame; NOT malformed frames CONTAINER
    ("sim/frames-string",    "sim",      {"frames": "boom"},
     "frames a truthy string, not a list of frame dicts"),
    ("sim/frames-list-nondict", "sim",   {"frames": [42, 43]},
     "frames a list of non-dict scalars"),
    ("sim/frames-int",       "sim",      {"frames": 7},
     "frames a truthy int"),
    # ── geometry ── builder fixtured None counts + numeric bbox + numeric weight_sum; NOT typed-garbage bbox/weight
    ("geo/bbox-noniter",     "geometry", {"point_count": 10, "prim_count": 4, "bbox": 5},
     "bbox a non-iterable scalar"),
    ("geo/bbox-string",      "geometry", {"point_count": 10, "prim_count": 4, "bbox": "box"},
     "bbox a string (iterable of chars)"),
    ("geo/weightsum-string", "geometry", {"point_count": 10, "prim_count": 4, "weight_sum": "1.0"},
     "weight_sum a numeric-looking string"),
    ("geo/counts-zero",      "geometry", {"point_count": 0, "prim_count": 0},
     "BOUNDARY: present-zero counts (cooked-empty vs not-cooked) — the 'never zero' line"),
    # ── channels ── builder fixtured samples=0 + valid range + inverted range; NOT typed-garbage range/samples
    ("chan/range-noniter",   "channels", {"samples": 10, "range": 5},
     "range a non-iterable scalar"),
    ("chan/range-short",     "channels", {"samples": 10, "range": [1]},
     "range a single-element list (rng[1] missing)"),
    ("chan/samples-float",   "channels", {"samples": 3.5},
     "samples a float (neither int nor sized)"),
    ("chan/variance-string", "channels", {"samples": 10, "variance": "bad"},
     "variance a non-numeric string"),
    # ── graph ── builder fixtured absent compiles + list errors; NOT string errors
    ("graph/errors-string",  "graph",    {"compiles": True, "errors": "boom"},
     "errors a string, not a list"),
    # ── dispatcher ── builder fixtured unknown-kind; NOT None obs
    ("disp/obs-none",        "dispatch:image", None,
     "obs is None routed through measure()"),
    ("disp/kind-none",       "dispatch:None",  {},
     "kind is None routed through measure()"),
]


def _classify(verdict: str) -> str:
    if verdict == UNKNOWN:
        return "UNKNOWN(honest)"
    if verdict == FAIL:
        return "FAIL(graceful)"
    if verdict in (MEASURED, EXPLODING):
        return f"{verdict}(soft-pass?)"
    return f"{verdict}(?)"


def run() -> dict:
    rows = []
    for case_id, kind, obs, why in MATRIX:
        rec = {"case": case_id, "kind": kind, "obs": repr(obs), "why_adversarial": why}
        try:
            if kind.startswith("dispatch:"):
                real_kind = kind.split(":", 1)[1]
                real_kind = None if real_kind == "None" else real_kind
                res = measure(real_kind, obs)
            else:
                res = _CONTRACT[kind](obs)
            rec["outcome"] = _classify(res.verdict)
            rec["verdict"] = res.verdict
            rec["reason"] = res.unknown_reason or res.detail or ""
            rec["signals"] = {k: repr(v) for k, v in (res.signals or {}).items()}
            rec["crashed"] = False
        except Exception as exc:  # noqa: BLE001 — capturing the crash IS the finding
            rec["outcome"] = "CRASH(hole)"
            rec["verdict"] = None
            rec["exception"] = f"{type(exc).__name__}: {exc}"
            rec["trace_tail"] = traceback.format_exc().strip().splitlines()[-1]
            rec["crashed"] = True
        rows.append(rec)

    tally = {}
    for r in rows:
        head = r["outcome"].split("(")[0]
        tally[head] = tally.get(head, 0) + 1
    return {"pyroot": str(PYROOT), "cases": len(rows), "tally": tally, "rows": rows}


if __name__ == "__main__":
    out = run()
    w = max(len(r["case"]) for r in out["rows"])
    print(f"# adversarial matrix — measures contracts @ {out['pyroot']}")
    print(f"# {out['cases']} cases  tally={out['tally']}\n")
    for r in out["rows"]:
        line = f"{r['case']:<{w}}  {r['outcome']:<18}"
        if r["crashed"]:
            line += f"  {r['exception']}"
        else:
            tail = r.get("reason", "")
            line += f"  {r['verdict']:<9}  {tail[:70]}"
        print(line)
    print("\n---JSON---")
    print(json.dumps(out, indent=2))
