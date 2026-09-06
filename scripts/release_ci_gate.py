"""scripts/release_ci_gate.py — a tag is a claim; CI is how it is checked.

Crank 3 (2026-09-06) found that v5.64.0 and v5.65.0 point at commits whose CI
concluded **failure**, and that v5.65.2 was tagged while its run was still
in_progress. It also found why nobody noticed: B1's closure predicate read

    gh run list --branch master --limit 1

which is the BRANCH HEAD, not the tagged commit. Master had moved on and was
green, so the predicate printed green over two red releases.

The ritual cannot check CI before tagging — CI only runs after the push. So the
gate belongs between pushing master and publishing the release:

    scripts/tag_release.py            # refuses a dirty tree, creates the tag
    git push origin master
    python scripts/release_ci_gate.py v5.65.3     # <- waits here
    git push origin v5.65.3
    gh release create v5.65.3 ...

Usage:
  python scripts/release_ci_gate.py <tag> [--wait-minutes 20] [--check-only]

Exit 0 = the tagged commit's CI concluded success.
Exit 1 = it concluded failure, or the wait ran out with the run unfinished.
Exit 2 = the state could not be observed (no gh, no run, no such tag). UNKNOWN
         refuses, the same house rule tag_release.py uses.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(args, timeout=60):
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return p


def commit_for(tag: str):
    p = _run(["git", "rev-list", "-n", "1", tag])
    if p is None or p.returncode != 0:
        return None
    return p.stdout.strip()


def run_for(sha: str, limit: int = 80):
    """The newest workflow run whose head commit IS this commit."""
    p = _run(["gh", "run", "list", "--limit", str(limit), "--json",
              "headSha,status,conclusion,databaseId,name"], timeout=120)
    if p is None or p.returncode != 0:
        return None
    try:
        runs = json.loads(p.stdout)
    except Exception:
        return None
    for r in runs:
        if r.get("headSha", "").startswith(sha[:8]):
            return r
    return False  # observed the list, this commit is not in it


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("--wait-minutes", type=float, default=20.0)
    ap.add_argument("--check-only", action="store_true",
                    help="report the current state and exit; never wait")
    a = ap.parse_args(argv)

    sha = commit_for(a.tag)
    if not sha:
        print("tag          %-18s UNKNOWN — no such tag locally" % a.tag)
        return 2
    print("tag          %-18s %s" % (a.tag, sha[:8]))

    deadline = time.monotonic() + a.wait_minutes * 60
    while True:
        run = run_for(sha)
        if run is None:
            print("ci           could not be observed  REFUSE (no gh, or the API failed)")
            return 2
        if run is False:
            state = "no run for this commit yet"
        else:
            state = "%s %s" % (run.get("status"), run.get("conclusion") or "-")
            if run.get("status") == "completed":
                ok = run.get("conclusion") == "success"
                print("ci           %-18s %s" % (state, "OK" if ok else "REFUSE"))
                if not ok:
                    print("             run %s — a red commit must not become a release" % run.get("databaseId"))
                return 0 if ok else 1
        if a.check_only:
            print("ci           %-18s UNKNOWN (check-only)" % state)
            return 2
        if time.monotonic() >= deadline:
            print("ci           %-18s REFUSE — waited %g min, still not decided"
                  % (state, a.wait_minutes))
            return 1
        print("             %s — waiting…" % state)
        time.sleep(20)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
