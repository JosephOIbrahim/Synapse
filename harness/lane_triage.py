#!/usr/bin/env python3
"""Lane triage — what does each dirty worktree hold, and is it worth committing?

    python harness/lane_triage.py            # every dirty worktree, classified
    python harness/lane_triage.py --lane q2-baseline   # one lane, full file list
    python harness/lane_triage.py --json     # machine-readable

For each dirty worktree, every uncommitted file is classified:

    JUNK      generated/derivative noise (pyc, logs, caches, $HOUDINI_TEMP_DIR
              litter, .tmp) — safe to drop, never worth a commit
    LANDED    content byte-identical to the same path on master — the work
              already arrived by another route; drop
    STALE     modified file whose master copy has ALSO moved since the lane's
              base — the lane's version lost the race; review before drop
    REAL      new or modified content that exists nowhere on master — the only
              class that can justify a commit

The recommendation per lane is mechanical from the counts:
    all JUNK/LANDED            -> DROP THE LANE (nothing survives)
    any REAL                   -> REVIEW: the REAL files are listed; read those
                                  and only those
    only STALE                 -> REVIEW-LIKELY-DROP (master moved past it)

Law 2: every verdict names its producer (the diff/pattern that decided it).
'?' where a check could not run. No caching — always the live tree.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JUNK_PATTERNS = [
    "*.pyc", "__pycache__/*", "*/__pycache__/*", "*.log", "*.tmp",
    "$HOUDINI_TEMP_DIR/*", "*.orig", "*.rej", ".pytest_cache/*",
    "*.egg-info/*", "hip_backup/*", "*.hip.bak*",
    # orchestration/scratch markers observed in parked lanes
    ".claude/.orch_launched", "*.q2msg", ".q2tmp_*", ".q2tmp_*/*",
    ".sh_tmp*", ".sh_tmp*/*",
]


def run(args, cwd=None, timeout=60):
    try:
        p = subprocess.run(args, cwd=cwd or REPO, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 127, ""


def dirty_worktrees():
    rc, out = run(["git", "worktree", "list", "--porcelain"])
    if rc != 0:
        return []
    trees = [l[len("worktree "):] for l in out.splitlines()
             if l.startswith("worktree ")]
    result = []
    for w in trees:
        if os.path.normpath(w) == os.path.normpath(REPO):
            continue
        rc, st = run(["git", "status", "--porcelain"], cwd=w)
        if rc == 0 and st.strip():
            result.append((w, st))
    return result


def is_junk(path):
    p = path.replace("\\", "/")
    return any(fnmatch.fnmatch(p, pat) or fnmatch.fnmatch(os.path.basename(p), pat)
               for pat in JUNK_PATTERNS)


def classify(wt, status_out):
    """Classify every dirty file in one worktree."""
    files = []
    for line in status_out.splitlines():
        if len(line) < 4:
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        entry = {"path": path, "git": code.strip() or "??"}
        if is_junk(path):
            entry["class"] = "JUNK"
            entry["why"] = "matches junk pattern"
            files.append(entry)
            continue

        lane_file = os.path.join(wt, path)
        master_has = run(["git", "cat-file", "-e", "master:" + path])[0] == 0

        if not os.path.exists(lane_file):
            # deleted in lane
            entry["class"] = "REAL" if master_has else "JUNK"
            entry["why"] = "deletion of a tracked file" if master_has else "delete of untracked"
            files.append(entry)
            continue

        if master_has:
            rc, _ = run(["git", "diff", "--quiet", "master", "--", path], cwd=wt)
            # diff --quiet: rc 0 = identical to master
            if run(["git", "diff", "--quiet", "master", "--", path], cwd=wt)[0] == 0:
                entry["class"] = "LANDED"
                entry["why"] = "byte-identical to master:%s" % path
            else:
                # did master also move past the lane's base?
                rc2, base = run(["git", "merge-base", "master", "HEAD"], cwd=wt)
                moved = False
                if rc2 == 0 and base.strip():
                    moved = run(["git", "diff", "--quiet", base.strip(), "master",
                                 "--", path])[0] != 0
                entry["class"] = "STALE" if moved else "REAL"
                entry["why"] = ("master moved past this file since the lane's base"
                                if moved else "differs from master; master unchanged since base")
        else:
            # Absent on master NOW — but was it deliberately deleted? A lane
            # that predates a deletion resurrects the dead if committed.
            rc3, hist = run(["git", "log", "--oneline", "-1", "master", "--", path])
            if rc3 == 0 and hist.strip():
                entry["class"] = "RESURRECTED"
                entry["why"] = "master DELETED this file (%s) - committing revives it" % hist.strip()[:28]
            else:
                entry["class"] = "REAL"
                entry["why"] = "new file, never existed on master"
        files.append(entry)
    return files


def recommend(files):
    counts = {}
    for f in files:
        counts[f["class"]] = counts.get(f["class"], 0) + 1
    if counts.get("REAL"):
        return "REVIEW", counts
    if counts.get("STALE") or counts.get("RESURRECTED"):
        return "REVIEW-LIKELY-DROP", counts
    return "DROP", counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", help="show full file detail for one lane")
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    lanes = []
    for wt, st in dirty_worktrees():
        name = os.path.basename(wt)
        if ns.lane and name != ns.lane:
            continue
        files = classify(wt, st)
        rec, counts = recommend(files)
        lanes.append({"lane": name, "path": wt, "recommendation": rec,
                      "counts": counts, "files": files})

    if ns.json:
        print(json.dumps(lanes, indent=2))
        return

    for L in lanes:
        c = L["counts"]
        summary = " ".join("%s=%d" % (k, v) for k, v in sorted(c.items()))
        print("%-24s %-20s %s" % (L["lane"], L["recommendation"], summary))
        show = L["files"] if (ns.lane or L["recommendation"] != "DROP") else []
        for f in show:
            if f["class"] in ("REAL", "STALE", "RESURRECTED") or ns.lane:
                print("    %-6s %-4s %-60s %s" % (f["class"], f["git"],
                                                  f["path"][:60], f["why"][:50]))
    if not lanes:
        print("no dirty worktrees")


if __name__ == "__main__":
    main()
