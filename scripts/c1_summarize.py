#!/usr/bin/env python3
"""C1 - turn the counted ladder into the verdict. Producer path for the
headline figures in ``harness/notes/receipts/C1.json``.

Three things happen here and none of them may be skipped:

1. **The repeatability control.** Every rung ran twice. This computes the
   run-1 vs run-2 delta per arm. A benchmark that has not established its own
   noise floor is a picture, so the control is reported FIRST and every later
   figure is read against it.

2. **The flatness test.** For each arm, the ratio of its largest rung to its
   smallest. "Flat" is a claim about that ratio being ~1. The FLAT_ control
   arm exists so the test can be seen to return "flat" for something — an
   instrument that can only ever say "rises" has not measured anything
   (Constitution Law 1).

3. **Cost paired with outcome.** Coverage — the fraction of the scene's nodes
   a payload actually puts in front of the model — travels beside every token
   figure. A cheap arm that covers less is cheap BECAUSE it covers less, and
   that is reported, never averaged away.

Usage:
    python scripts/c1_summarize.py --counted <count.json> --out <summary.json>
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RUN_RE = re.compile(r"^(?P<rung>L\d+_[A-Za-z0-9_]+?)__r(?P<run>\d+)$")

# The panel worker appends every tool result to a message list that is never
# compacted and re-sends the whole list on each round-trip, up to this many
# iterations in ONE user turn (claude_worker.py _MAX_TOOL_ITERATIONS).
MAX_TOOL_ITERATIONS = 25

# Not every arm is trying to cover the scene, and scoring them as if they were
# would be unfair in a way that flatters the conclusion. inspect_node_detail
# answers "tell me everything about THIS node" - its scene-wide coverage is
# definitionally ~1/N and says nothing about whether it did its job. For those
# arms the honest reading is cost growth alone.
ARM_KIND = {
    "A_inspect_scene_d3": "scene_grounding",
    "B_inspect_scene_deep": "scene_grounding",
    "B_network_explain_d5": "scene_grounding",
    "FLAT_scene_context": "scene_grounding",
    "A_inspect_node_detail": "single_node",
    "B_usd_flatten": "usd_serialization",
}
COVERAGE_MEANINGFUL = {"scene_grounding"}

# Every arm the driver attempts. An arm that is expected but produced no entry
# did not "not apply" - it DIED, and a segfault leaves no error record behind
# to say so. Without this set a crashed arm would render as a blank cell and
# quietly vanish from the failure list (Law 3: status describes what happened).
EXPECTED_ARMS = set(ARM_KIND)
# B_usd_flatten legitimately does not apply to a scene with no Solaris stage;
# that absence is reported through its own arm_error, not as a crash.
OPTIONAL_ARMS = {"B_usd_flatten"}


def _flatness(values: List[int]) -> Optional[float]:
    """max/min across the ladder. Secondary metric only — see _growth."""
    vals = [v for v in values if v is not None]
    if not vals or min(vals) <= 0:
        return None
    return round(max(vals) / min(vals), 2)


def _growth(values: List[Optional[int]]) -> Optional[float]:
    """Tokens at the LARGEST rung over tokens at the SMALLEST rung.

    This, not max/min, is the flatness test. "Flat" is a claim about cost not
    growing WITH SCENE SIZE, and max/min answers a different question: on a
    35-token payload a +-2-token wobble is 6% and would read as "rises" even
    though the payload is provably size-independent. (The flat control does
    wobble by exactly that much, because it embeds the .hip FILENAME, whose
    length differs per scene and not with scene size.)

    Ladder order is scene-size order, so first-to-last is the honest slope.
    """
    vals = [v for v in values if v is not None]
    if len(vals) < 2 or vals[0] <= 0:
        return None
    return round(vals[-1] / vals[0], 2)


def summarize(counted_path: Path, out: Path) -> Dict[str, Any]:
    doc = json.loads(counted_path.read_text(encoding="utf-8"))

    # rung -> run -> arm -> counted entry
    table: Dict[str, Dict[str, Dict[str, Any]]] = {}
    axes: Dict[str, Dict[str, Any]] = {}
    failures: List[Dict[str, Any]] = []

    for r in doc.get("rungs", []):
        label = r.get("label", "")
        m = RUN_RE.match(label)
        if not m:
            continue
        rung, run = m.group("rung"), m.group("run")
        if r.get("status") != "ok":
            failures.append({"rung": rung, "run": run,
                             "status": r.get("status"),
                             "error": r.get("load_error", "")})
            continue
        table.setdefault(rung, {})[run] = r.get("counted", {})
        axes[rung] = r.get("axes", {})
        for arm, err in (r.get("payload_errors") or {}).items():
            failures.append({"rung": rung, "run": run, "arm": arm,
                             "status": "arm_error", "error": err})

    rungs = sorted(table, key=lambda s: int(s.split("_")[0][1:]))
    arms = sorted({a for runs in table.values()
                   for c in runs.values() for a in c})

    # An expected arm with no entry and no recorded error was killed hard.
    for rung in rungs:
        for run, counted in sorted(table[rung].items()):
            for arm in sorted(EXPECTED_ARMS - OPTIONAL_ARMS):
                if arm in counted:
                    continue
                already = any(f.get("rung") == rung and f.get("run") == run
                              and f.get("arm") == arm for f in failures)
                if not already:
                    failures.append({
                        "rung": rung, "run": run, "arm": arm,
                        "status": "arm_produced_no_output",
                        "error": (
                            "Expected arm emitted nothing and recorded no "
                            "exception. Under per-arm crash isolation this "
                            "means the hython process died (segfault) inside "
                            "this arm - see the driver log for the rc."
                        ),
                    })

    # -- 1. the repeatability control ------------------------------------
    control: List[Dict[str, Any]] = []
    for rung in rungs:
        for arm in arms:
            r1 = table[rung].get("1", {}).get(arm)
            r2 = table[rung].get("2", {}).get(arm)
            if not r1 or not r2:
                continue
            a, b = r1["tokens_cl100k"], r2["tokens_cl100k"]
            control.append({
                "rung": rung, "arm": arm,
                "run1_tokens": a, "run2_tokens": b,
                "delta": b - a,
                "delta_pct": round(abs(b - a) / a * 100, 4) if a else None,
            })
    deltas = [c["delta"] for c in control]
    noise = {
        "pairs_compared": len(control),
        "max_abs_delta_tokens": max((abs(d) for d in deltas), default=None),
        "all_identical": all(d == 0 for d in deltas) if deltas else None,
        "verdict": (
            "deterministic - noise floor is 0 tokens; every rung reproduced "
            "its own count exactly"
            if deltas and all(d == 0 for d in deltas)
            else "NOT deterministic - see max_abs_delta_tokens; treat that as "
                 "the noise floor and do not report differences below it"
        ),
    }

    # -- 2 + 3. the curve, with outcome attached -------------------------
    curve: Dict[str, Any] = {}
    for arm in arms:
        points = []
        for rung in rungs:
            c = table[rung].get("1", {}).get(arm)
            if not c:
                points.append({"rung": rung, "tokens": None,
                               "status": "absent (arm failed or n/a)"})
                continue
            cov = c.get("coverage", {}) or {}
            covered = cov.get("covered")
            # THE FIGURE THAT DECIDES WHETHER "CHEAPER" MEANS ANYTHING.
            # An arm looks cheap two ways: by encoding the same scene more
            # tightly, or by sending less of it. Only the first is efficiency.
            # Dividing by nodes actually delivered separates them, and it is
            # the difference between "10x cheaper" and "10x less complete".
            per_node = (
                round(c["tokens_cl100k"] / covered, 1)
                if covered else None
            )
            points.append({
                "rung": rung,
                "node_count": axes[rung].get("node_count"),
                "parm_count": axes[rung].get("parm_count"),
                "tokens": c["tokens_cl100k"],
                "tokens_model_visible": c.get("tokens_cl100k_model_visible"),
                "coverage_fraction": cov.get("fraction"),
                "nodes_covered": covered,
                "nodes_total": cov.get("total"),
                "tokens_per_covered_node": per_node,
            })
        tok = [p["tokens"] for p in points]
        ratio = _flatness(tok)
        growth = _growth(tok)
        kind = ARM_KIND.get(arm, "unknown")
        if kind not in COVERAGE_MEANINGFUL:
            for p in points:
                p["coverage_note"] = (
                    f"coverage denominator is the whole scene, but this arm is "
                    f"'{kind}' - it does not attempt scene-wide grounding. Read "
                    f"its cost growth, not its coverage."
                )
        entry = {
            "arm_kind": kind,
            "coverage_is_meaningful": kind in COVERAGE_MEANINGFUL,
            "points": points,
            "growth_largest_over_smallest_rung": growth,
            "flatness_ratio_max_over_min": ratio,
            "is_flat": (growth is not None and growth <= 1.10),
            "flat_test": (
                "is_flat is True when tokens at the LARGEST rung are <= 1.10x "
                "tokens at the SMALLEST rung. max/min is reported too but is "
                "not the test - it is noise-dominated on tiny payloads."
            ),
        }
        if arm == "B_usd_flatten":
            entry["not_comparable_across_rungs"] = (
                "This arm exports the stage as composed at the LAST child of "
                "/stage in creation order, which is not necessarily the final "
                "composed stage, and it is absent entirely on the four rungs "
                "with no Solaris stage. Its rung-to-rung ratio is therefore "
                "MEANINGLESS - L6 reads smaller than L4 for this reason, not "
                "because the bigger scene serializes smaller. Read each value "
                "as a single cost datapoint, never as a curve."
            )
            entry["is_flat"] = None
        curve[arm] = entry

    # -- the multi-turn consequence --------------------------------------
    # Per-call cost is only half the story: nothing compacts the conversation,
    # so every prior tool result is re-sent on every later round-trip.
    per_turn = {}
    for arm in arms:
        pts = [p for p in curve[arm]["points"] if p.get("tokens")]
        if not pts:
            continue
        top = pts[-1]
        per_turn[arm] = {
            "top_rung": top["rung"],
            "single_call_tokens": top["tokens"],
            "resent_over_25_iterations": top["tokens"] * MAX_TOOL_ITERATIONS
            * (MAX_TOOL_ITERATIONS + 1) // 2,
            "basis": (
                "No compaction exists on the panel path: the message list is "
                "append-only and every prior tool_result is re-sent on each "
                "subsequent API call, up to _MAX_TOOL_ITERATIONS=25 in ONE "
                "user turn. A payload sent at iteration i is charged (26-i) "
                "times, so N identical results cost N(N+1)/2. VERIFIED-DERIVED "
                "from the measured single-call figure; not itself measured."
            ),
        }

    # -- headline: is arm A cheaper because it is tighter, or because it is
    #    smaller? Compared only against B_inspect_scene_deep, which is the SAME
    #    code path one argument apart, so nothing differs but how much scene
    #    is sent.
    efficiency: List[Dict[str, Any]] = []
    a_pts = {p["rung"]: p for p in curve.get("A_inspect_scene_d3", {})
             .get("points", [])}
    b_pts = {p["rung"]: p for p in curve.get("B_inspect_scene_deep", {})
             .get("points", [])}
    for rung in rungs:
        a, b = a_pts.get(rung), b_pts.get(rung)
        if not a or not b or not a.get("tokens") or not b.get("tokens"):
            continue
        apn, bpn = a.get("tokens_per_covered_node"), b.get("tokens_per_covered_node")
        efficiency.append({
            "rung": rung,
            "node_count": a.get("node_count"),
            "raw_cost_advantage_x": round(b["tokens"] / a["tokens"], 2),
            "arm_a_coverage": a.get("coverage_fraction"),
            "arm_a_tokens_per_covered_node": apn,
            "arm_b_tokens_per_covered_node": bpn,
            "true_efficiency_advantage_x": (
                round(bpn / apn, 2) if apn and bpn else None
            ),
        })

    result = {
        "schema": "c1_summary/v1",
        "efficiency_vs_completeness": {
            "_what": (
                "raw_cost_advantage_x is how much cheaper arm A LOOKS. "
                "true_efficiency_advantage_x is how much cheaper it is per "
                "node actually delivered. The gap between the two columns is "
                "the part of the headline that is 'sent less of the scene' "
                "rather than 'encoded it better'."
            ),
            "rows": efficiency,
        },
        "tokenizer": doc.get("tokenizer"),
        "tokenizer_caveat": doc.get("tokenizer_caveat"),
        "arm_a_note": doc.get("arm_a_note"),
        "ladder": [{"rung": r, **axes[r]} for r in rungs],
        "repeatability_control": {"noise": noise, "pairs": control},
        "curve": curve,
        "multi_turn_consequence": per_turn,
        "failures": failures,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True),
                   encoding="utf-8")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--counted", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    res = summarize(Path(args.counted), Path(args.out))

    n = res["repeatability_control"]["noise"]
    print("REPEATABILITY CONTROL")
    print(f"  pairs={n['pairs_compared']}  max|delta|={n['max_abs_delta_tokens']}")
    print(f"  {n['verdict']}\n")

    print(f"{'arm':<26} {'flat?':<7} {'growth':>9}   tokens per rung "
          f"(coverage%)")
    for arm, c in sorted(res["curve"].items()):
        cells = []
        for p in c["points"]:
            if p.get("tokens") is None:
                cells.append("     --")
                continue
            cov = p.get("coverage_fraction")
            cov_s = ("" if cov is None or not c["coverage_is_meaningful"]
                     else f"({cov*100:.0f}%)")
            cells.append(f"{p['tokens']:>8}{cov_s}")
        flat = ("n/a" if c["is_flat"] is None
                else ("FLAT" if c["is_flat"] else "rises"))
        g = c["growth_largest_over_smallest_rung"]
        print(f"{arm:<26} {flat:<7} {str(g):>9}   " + " ".join(cells))

    if res["failures"]:
        print("\nFAILURES (reported separately, never averaged into the curve)")
        for f in res["failures"]:
            print(f"  {f.get('rung')} r{f.get('run')} {f.get('arm','-')}: "
                  f"{f.get('status')} {str(f.get('error'))[:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
