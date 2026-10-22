#!/usr/bin/env python3
"""calibrate.py - the producer for the JEV guard thresholds.

Every threshold in a question file is a NUMBER. A number with no producer path is a
number nobody can re-derive, and when the model drifts it cannot be defended or
corrected - it can only be nudged. This script is the producer: it measures the
observed score distribution from the ledger and says, for each shipped threshold,
whether that threshold can actually fire.

THE COMPARABLE QUANTITY IS FRACTION-OF-RANGE, NOT THE RAW VALUE.

A Score with N criteria returns a probability-weighted POSITION in 0..N-1. A raw
score of 2.0 means different things on different rubrics:

    3 criteria -> range 0..2 -> 2.0 is 100% of range  (the top row; nothing reaches it)
    4 criteria -> range 0..3 -> 2.0 is  67% of range  (high, but reachable)

So "is 2.0 a good threshold?" has no answer until you know how many criteria the
rubric has. This script always reports the fraction.

CLASSIFICATION of a threshold, against the observed distribution:

    DEAD      the threshold cannot fire at all. It is worse than no gate: it prints
              PASS forever, because no row can ever trip it.
    DORMANT   it fires on fewer than 5% of observed rows. Alive, but it is a
              near-silent gate. Treat with suspicion.
    LIVE      it fires on a meaningful share of observed rows.

Run:

    python harness/harness2/calibrate.py
    python harness/harness2/calibrate.py --check     # fail if questions.json has drifted
    python harness/harness2/calibrate.py --all        # include untracked ledger rows
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LEDGER = HERE.parent / "jev" / "ledger"
QUESTIONS = HERE / "questions.json"

DORMANT_BELOW = 0.05  # a threshold that fires on under 5% of rows is near-silent


# ---------------------------------------------------------------- measurement

def ledger_files(all_rows: bool) -> list[Path]:
    if all_rows:
        return sorted(LEDGER.glob("*.jsonl"))
    try:
        out = subprocess.run(["git", "ls-files", "harness/jev/ledger/"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout
    except Exception:  # noqa: BLE001
        return sorted(LEDGER.glob("*.jsonl"))
    return [REPO / line.strip() for line in out.splitlines() if line.strip().endswith(".jsonl")]


def measure(all_rows: bool = False) -> dict:
    """Every score answer in the ledger, grouped by question id."""
    buckets: dict[str, list[float]] = {}
    ok_rows = 0
    files = ledger_files(all_rows)
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("result") != "ok":
                continue
            ok_rows += 1
            scores = (row.get("answers") or {}).get("scores") or {}
            for qid, ans in scores.items():
                s = (ans or {}).get("score")
                if s is not None:
                    buckets.setdefault(qid, []).append(float(s))
    return {"ok_rows": ok_rows, "files": len(files), "buckets": buckets}


def dist(values: list[float]) -> dict:
    if not values:
        return {}
    v = sorted(values)
    n = len(v)

    def pct(p: float) -> float:
        k = (n - 1) * p
        f = int(k)
        c = min(f + 1, n - 1)
        return v[f] + (v[c] - v[f]) * (k - f)

    return {"n": n, "min": v[0], "p50": pct(0.50), "p75": pct(0.75), "p90": pct(0.90),
            "max": v[-1], "values": v}


# ---------------------------------------------------------------- classification

def classify(threshold: float, criteria_count: int, observed: list[float]) -> dict:
    """Classify a threshold against an observed distribution of the SAME fraction-of-range."""
    max_score = criteria_count - 1
    out = {
        "threshold": threshold,
        "criteria": criteria_count,
        "max_score": max_score,
        "fraction_of_range": (threshold / max_score) if max_score > 0 else None,
        "observed_n": len(observed),
    }
    if max_score <= 0 or threshold > max_score:
        out["verdict"] = "DEAD"
        out["why"] = "threshold %g exceeds max score %g for %d criteria" % (
            threshold, max_score, criteria_count)
        out["reachable_fraction"] = 0.0
        return out
    if not observed:
        out["verdict"] = "UNMEASURED"
        out["why"] = "no observed rows for this rubric - cannot classify"
        out["reachable_fraction"] = None
        return out
    # compare on the fraction-of-range axis, so rubrics of different sizes line up
    reach = sum(1 for s in observed if s / max_score >= threshold / max_score)
    frac = reach / len(observed)
    out["reachable_fraction"] = round(frac, 4)
    if reach == 0:
        out["verdict"] = "DEAD"
        out["why"] = "no observed row reaches this fraction of range"
    elif frac < DORMANT_BELOW:
        out["verdict"] = "DORMANT"
        out["why"] = "fires on %.1f%% of observed rows" % (frac * 100)
    else:
        out["verdict"] = "LIVE"
        out["why"] = "fires on %.1f%% of observed rows" % (frac * 100)
    return out


def rubric_sizes(q: dict) -> dict:
    """How many criteria does each shipped Score rubric have?"""
    out = {}
    for gname, guard in q.get("guards", {}).items():
        for qid, spec in (guard.get("questions") or {}).items():
            if spec.get("type") == "score":
                out["%s.%s" % (gname, qid)] = len(spec.get("criteria") or [])
    return out


def shipped_thresholds(q: dict) -> list[dict]:
    out = []
    for gname, guard in q.get("guards", {}).items():
        policy = guard.get("policy") or {}
        for qid, spec in (guard.get("questions") or {}).items():
            if spec.get("type") != "score":
                continue
            key = "min_strength" if "strength" in qid else "min_value"
            if key not in policy:
                continue
            out.append({
                "guard": gname,
                "question": qid,
                "policy_key": key,
                "threshold": float(policy[key]),
                "criteria": len(spec.get("criteria") or []),
            })
    return out


# ---------------------------------------------------------------- report

def build_report(all_rows: bool = False) -> dict:
    q = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    m = measure(all_rows=all_rows)
    sizes = rubric_sizes(q)

    # The reference rubric: the repo's own shipped `novelty` score, 3 criteria.
    nov = m["buckets"].get("novelty", [])
    nov_dist = dist(nov)

    thresholds = []
    for t in shipped_thresholds(q):
        ref = nov if t["criteria"] != len(sizes.get("harness2.novelty", [])) or True else []
        # compare against the observed novelty rubric, normalised to FRACTION of range
        if nov:
            ref_max = 2  # novelty has 3 criteria -> range 0..2
            normalised = [s / ref_max for s in nov]
            th_max = t["criteria"] - 1
            reach = sum(1 for f in normalised if f >= t["threshold"] / th_max)
            frac = reach / len(normalised)
            verdict = "DEAD" if reach == 0 else ("DORMANT" if frac < DORMANT_BELOW else "LIVE")
            why = ("no observed row reaches this fraction of range" if reach == 0
                   else "fires on %.1f%% of observed rows" % (frac * 100))
        else:
            verdict, frac, why = "UNMEASURED", None, "no observed novelty rows"
        thresholds.append({
            **t,
            "max_score": t["criteria"] - 1,
            "fraction_of_range": round(t["threshold"] / (t["criteria"] - 1), 4)
            if t["criteria"] > 1 else None,
            "verdict": verdict,
            "reachable_fraction": round(frac, 4) if frac is not None else None,
            "why": why,
        })

    return {
        "ledger_files": m["files"],
        "ok_rows": m["ok_rows"],
        "reference_rubric": "novelty",
        "reference_distribution": {k: (round(v, 4) if isinstance(v, float) else v)
                                   for k, v in nov_dist.items() if k != "values"},
        "thresholds": thresholds,
    }


def _fmt(rep: dict) -> str:
    out = []
    out.append("ledger: %d files, %d ok rows" % (rep["ledger_files"], rep["ok_rows"]))
    d = rep["reference_distribution"]
    if d:
        out.append("reference rubric 'novelty' (3 criteria, range 0..2), n=%d" % d["n"])
        out.append("  min %.2f  p50 %.2f  p75 %.2f  p90 %.2f  max %.2f" % (
            d["min"], d["p50"], d["p75"], d["p90"], d["max"]))
    out.append("")
    out.append("%-28s %-9s %-8s %-8s %-8s %s" % ("threshold", "value", "frac", "reaches", "verdict", "why"))
    for t in rep["thresholds"]:
        out.append("%-28s %-9s %-8s %-8s %-8s %s" % (
            "%s.%s" % (t["guard"], t["question"]), t["threshold"], t["fraction_of_range"],
            t["reachable_fraction"], t["verdict"], t["why"]))
    return "\n".join(out)


def check_recorded(rep: dict) -> list[str]:
    """Compare the calibration recorded in questions.json against a fresh measurement."""
    q = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    problems = []
    for gname, guard in q.get("guards", {}).items():
        rec = (guard.get("calibration") or {})
        for key, rec_entry in rec.items():
            tkey = rec_entry.get("policy_key")
            pol = guard.get("policy") or {}
            if tkey and tkey not in pol:
                problems.append("%s.calibration.%s names policy_key %r, which is not in policy"
                                % (gname, key, tkey))
                continue
            if tkey and abs(float(pol[tkey]) - float(rec_entry.get("value", -1))) > 1e-9:
                problems.append("%s.policy.%s is %s but the calibration records %s"
                                % (gname, tkey, pol[tkey], rec_entry.get("value")))
            fresh = next((x for x in rep["thresholds"]
                          if x["guard"] == gname and x["policy_key"] == tkey), None)
            if fresh and rec_entry.get("verdict") and rec_entry["verdict"] != fresh["verdict"]:
                problems.append("%s.calibration.%s records verdict %s but a fresh measurement says %s"
                                % (gname, key, rec_entry["verdict"], fresh["verdict"]))
    return problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="include untracked ledger rows")
    ap.add_argument("--check", action="store_true",
                    help="fail if the calibration recorded in questions.json has drifted")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    a = ap.parse_args(argv)

    rep = build_report(all_rows=a.all)
    if a.json:
        print(json.dumps(rep, indent=1))
    else:
        print(_fmt(rep))

    if a.check:
        problems = check_recorded(rep)
        if problems:
            print("\nCALIBRATION DRIFT:")
            for p in problems:
                print("  " + p)
            return 1
        print("\ncalibration in questions.json matches a fresh measurement.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
