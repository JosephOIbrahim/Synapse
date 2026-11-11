"""NR-QC-TIMING: compose timing_receipt.json from a run directory (frozen rule r2).

Inputs: ``run.json`` and ``raw.jsonl`` from run_timing.py and the path-free staging
summary from stage.py. Medians, spreads, the unit values, branches, the
who-decides row and the verdict all come from decide.py, so the numbers in the
receipt are the numbers the predicate recomputes.

No generation timestamp: the same inputs give the same bytes. A leak guard refuses
to write (exit 2) when any drive path, user-profile marker, build-folder or cloud
marker, or a run-time host marker (``--host-marker``) would land in the receipt.
Wall-clock stamps from the raw log stay in the raw log.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("qc_timing_decide", os.path.join(HERE, "decide.py"))
decide = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(decide)

RULE_SHA256 = "7d4c3bfecfe3adefb8db30b4455eca3266d9cbb5089d54986153489578a4e282"
PACKET_SHA256 = "7df176899dd2da66837dd0cf382942108da4ffe517fb54b0b6cba1647685f3a1"
ROLES = {
    "char-8": "deciding", "sib-v016": "deciding", "sib-v017": "deciding",
    "char-9": "cross-check", "char-2": "cross-check",
    "char-3": "supporting", "char-4": "supporting", "char-10": "supporting",
    "char-13": "stand-in", "char-12": "stand-in",
}
SEQUENCES = {"char-2": 24, "char-3": 61, "char-4": 9, "char-13": 24}
SCRIPTS = ["harness/vision/qc_timing/stage.py", "harness/vision/qc_timing/run_timing.py",
           "harness/vision/qc_timing/make_receipt.py"]
COMMANDS = {
    "stage": "<R4_PYTHON> -B harness/vision/qc_timing/stage.py --rule <RULE_R2> --stage-root <STAGE_ROOT> "
             "--manifest <STAGE_MANIFEST> --summary <STAGE_SUMMARY>",
    "run": "<R4_PYTHON> -B harness/vision/qc_timing/run_timing.py --manifest <STAGE_MANIFEST> --out <RUN_DIR> "
           "--passes 3  (PYTHONPATH=<RELEASE_TREE>)",
    "make_receipt": "<R4_PYTHON> -B harness/vision/qc_timing/make_receipt.py --run <RUN_DIR> "
                    "--staging-summary <STAGE_SUMMARY> --harness-commit <HARNESS_COMMIT>",
}
PASS_FIELDS = ("index", "seq", "void", "void_reason", "R", "wall", "W", "S", "S_dense", "S_rest", "lines",
               "other_lines", "types", "overhead_s", "inconclusive", "n_labels", "count", "mask_pixels",
               "nonfinite_pixels", "width", "height", "origin", "firefly_check_pass", "check_disagrees",
               "threads", "before", "after", "check_failed_report_only", "monotonic_ns")
_DRIVE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
_PROFILE = re.compile(r"[\\/]users?[\\/]|appdata", re.I)
_BUILTIN_MARKERS = ("synapse-build", "onedrive", "myth_and_logic")


def find_leaks(text: str, host_markers: Sequence[str] = ()) -> List[str]:
    """Snippets of every drive path, user-profile marker, built-in marker and
    run-time host marker in ``text``. Empty means safe to commit."""
    norm = text.replace("\\\\", "/").replace("\\", "/")
    bad = [norm[m.start(): m.start() + 72] for m in _DRIVE.finditer(norm)]
    bad.extend(text[max(0, m.start() - 24): m.end() + 24] for m in _PROFILE.finditer(text))
    low = text.lower()
    for marker in tuple(_BUILTIN_MARKERS) + tuple(host_markers):
        at = low.find(marker.lower()) if marker else -1
        if at >= 0:
            bad.append(text[max(0, at - 24): at + len(marker) + 24])
    return bad


def _exc(text: Optional[str]) -> Optional[str]:
    """Keep only 'read|scan: ExceptionType' so no path reaches the receipt."""
    if not text:
        return None
    return ":".join(str(text).split(":")[:2]).strip()


def _pass(rec: Dict[str, Any]) -> Dict[str, Any]:
    p = {k: rec[k] for k in PASS_FIELDS if k in rec}
    p["exception"] = _exc(rec.get("exception"))
    return p


def _median_fields(passes: List[Dict[str, Any]]) -> Dict[str, float]:
    return {q: decide.median([p[q] for p in passes]) for q in decide.MEDIAN_FIELDS}


def compose(run: Dict[str, Any], raw: List[Dict[str, Any]], staging: Optional[Dict[str, Any]],
            harness: Dict[str, Any]) -> Dict[str, Any]:
    env = run["environment"]
    dry = sorted((r for r in raw if r["kind"] == "dry"), key=lambda r: r["seq"])
    timed: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in sorted((r for r in raw if r["kind"] == "timed"), key=lambda r: r["seq"]):
        timed.setdefault((r["id"], str(r["frame"])), []).append(r)
    render = {}
    if staging:
        render = {(f["id"], f["frame"]): f.get("render_time_s") for f in staging["files"]}
    frames, dframes = [], []
    for (fid, fr), recs in sorted(timed.items(), key=lambda kv: (list(ROLES).index(kv[0][0]) if kv[0][0] in ROLES else 99, kv[0][1])):
        good = [r for r in recs if not r.get("void")]
        f: Dict[str, Any] = {"id": fid, "frame": fr, "role": ROLES.get(fid, "smoke"),
                             "passes": [_pass(r) for r in recs]}
        if fid in ("char-12", "char-13"):
            f["non_voting"] = True
        if good:
            m = _median_fields(good)
            f["medians"] = m
            f["derived"] = decide.frame_values(m)
            f["spread"] = {q: {"min": min(p[q] for p in good), "max": max(p[q] for p in good)}
                           for q in decide.MEDIAN_FIELDS}
            reaches = all(p.get("inconclusive") is False and not p.get("exception") for p in good)
            f["reaches_result"] = reaches
            f["inconclusive"] = any(p.get("inconclusive") for p in good)
            f["n_labels"] = good[0].get("n_labels")
            f["count"] = good[0].get("count")
            f["mask_pixels"] = good[0].get("mask_pixels")
            f["check_disagrees"] = any(p.get("check_disagrees") for p in good)
            dframes.append({"id": fid, "frame": fr, "reaches": reaches, **f["derived"]})
        frames.append(f)
    by = {(f["id"], f["frame"]): f for f in frames}
    dec = decide.decide([x for x in dframes if x["id"] in decide.TIER + decide.FALLBACK])
    decision = {"row": dec["row"], "voting": dec["voting"], "verdict": dec["verdict"], "units": dec["units"]}

    statements: Dict[str, Any] = {"part0_read": ["char-9", "char-2", "char-3", "char-4"],
                                  "non_voting": ["char-12", "char-13"]}
    try:
        statements["char3_vs_char4"] = {"frames": "0001-0009", "pairs": [
            {"frame": fr, "S_char3": by[("char-3", fr)]["medians"]["S"], "S_char4": by[("char-4", fr)]["medians"]["S"],
             "W_char3": by[("char-3", fr)]["medians"]["W"], "W_char4": by[("char-4", fr)]["medians"]["W"],
             "count_char3": by[("char-3", fr)]["count"], "count_char4": by[("char-4", fr)]["count"]}
            for fr in [f"{n:04d}" for n in range(1, 10)]]}
    except KeyError:
        pass
    try:
        statements["char10_vs_char3"] = {
            "T_char10": by[("char-10", "single")]["derived"]["T"],
            "T_char3_median": decide.median([by[("char-3", f"{n:04d}")]["derived"]["T"] for n in range(1, 62)])}
    except KeyError:
        pass
    per_id: Dict[str, float] = {}
    for fid in sorted({k[0] for k in by}):
        fr_ = [by[k]["derived"]["T"] / render[k] for k in by
               if k[0] == fid and "derived" in by[k] and render.get(k)]
        if fr_:
            per_id[fid] = decide.median(fr_)
    statements["render_time"] = {"context_only": True, "basis": "header renderTime, T / renderTime", "per_id": per_id}
    seqs = {}
    for sid, n in SEQUENCES.items():
        ts = {k[1]: by[k]["derived"]["T"] for k in by if k[0] == sid and "derived" in by[k]}
        if len(ts) == n:
            slow = max(ts, key=ts.get)
            seqs[sid] = {"slowest_frame": slow, "slowest_T": ts[slow], "frames_per_s": len(ts) / sum(ts.values())}
    statements["sequences"] = seqs

    drec = [{"id": r["id"], "seq": r["seq"], "inconclusive": r.get("inconclusive"), "n_labels": r.get("n_labels"),
             "count": r.get("count"), "mask_pixels": r.get("mask_pixels"), "threads": r.get("threads"),
             "exception": _exc(r.get("exception"))} for r in dry]
    receipt: Dict[str, Any] = {
        "schema": "nr-qc-timing-receipt/1",
        "mode": run["mode"],
        "rule": {"revision": 2, "sha256": RULE_SHA256, "packet_sha256": PACKET_SHA256, "B": 2.0, "threshold": 0.5},
        "method": {"W": "inner time of the cv2.imwrite call at firefly_scan.py line 458 (a wrapper, no product edit)",
                   "S": "fireflies() wall time minus W", "S_dense": "inner times of the calls at lines 292, 313, 314, 352, 542, 549",
                   "S_rest": "S minus S_dense; a call from any other line is listed in other_lines and lands here",
                   "R": "read_frame(path, subimage=0)", "median_of": "non-void timed passes after one untimed pass"},
        "product": env["product"],
        "environment": {k: env[k] for k in ("python", "numpy", "cv2", "openimageio", "logical_cores", "threads",
                                            "pythonpath", "cpu_model", "scratch_drive_model") if k in env},
        "harness": harness,
        "staging": ({"distinct_files": staging["distinct_files"], "files": staging["files"]} if staging else None),
        "dry_pass": {"exception": next((d["exception"] for d in drec if d["exception"]), None), "records": drec},
        "frames": frames,
        "decision": decision,
        "statements": statements,
        "producer": {
            "commands": COMMANDS, "scripts": SCRIPTS,
            "identities": {"R4_PYTHON": {"version": env.get("python")},
                           "RULE_R2": {"sha256": RULE_SHA256},
                           "RELEASE_TREE": env["product"],
                           "STAGE_MANIFEST": {"produced_by": "stage.py"},
                           "RUN_DIR": {"produced_by": "run_timing.py"}},
        },
    }
    return receipt


def harness_binding(root: str, commit: str) -> Dict[str, Any]:
    """Harness commit and the sha256 of each harness file as git has it at that commit."""
    def git(*a: str) -> bytes:
        r = subprocess.run(["git", "-C", root, *a], capture_output=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace"))
        return r.stdout
    full = git("rev-parse", commit).decode().strip()
    names = git("ls-tree", "-r", "--name-only", full, "--", "harness/vision/qc_timing").decode().split()
    files = {n: hashlib.sha256(git("show", f"{full}:{n}")).hexdigest()
             for n in names if not n.endswith("timing_receipt.json")}
    return {"commit": full, "files": files}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run", required=True, help="run directory from run_timing.py")
    p.add_argument("--staging-summary", help="stage.py's path-free summary")
    p.add_argument("--harness-commit", default="HEAD")
    p.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
    p.add_argument("--out", help="receipt to write (default: <repo>/harness/vision/qc_timing/timing_receipt.json)")
    p.add_argument("--host-marker", action="append", default=[], help="a run-time marker that must not appear")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    with open(os.path.join(a.run, "run.json"), encoding="utf-8") as fh:
        run = json.load(fh)
    with open(os.path.join(a.run, "raw.jsonl"), encoding="utf-8") as fh:
        raw = [json.loads(x) for x in fh if x.strip()]
    staging = None
    if a.staging_summary:
        with open(a.staging_summary, encoding="utf-8") as fh:
            staging = json.load(fh)
    receipt = compose(run, raw, staging, harness_binding(a.repo, a.harness_commit))
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    leaks = find_leaks(text, a.host_marker)
    if leaks:
        print("REFUSED: the receipt would carry host details:", file=sys.stderr)
        for x in leaks[:10]:
            print("  " + x, file=sys.stderr)
        return 2
    out = a.out or os.path.join(a.repo, "harness", "vision", "qc_timing", "timing_receipt.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote receipt, mode={receipt['mode']}, verdict={receipt['decision']['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
