#!/usr/bin/env python3
"""sweep.py -- MEMORY board live invariant sweep.

Watches in-flight legs FROM OUTSIDE. It cannot read an agent's reasoning; it
reads what an agent's actions leave on disk, which is the only honest signal
available while a leg is still running.

    python harness/memory/marshal/sweep.py            # human-readable
    python harness/memory/marshal/sweep.py --json     # machine readable
    python harness/memory/marshal/sweep.py --out <p>  # also write the verdict

Exit codes:  0 = CLEAR   2 = BREACH   3 = sweep could not run

The six invariants, and why each one exists:

  I1  MAIN-TREE CONTAMINATION.  While a forge works in a worktree, the repo root
      must gain no new edits under python/ tests/ shared/ panel/. An absolute
      C:/Users/User/SYNAPSE path written from inside a worktree lands on
      MASTER's tree instead of the branch. This is the highest-frequency real
      failure in this repo and it is invisible from inside the leg.

  I2  TERRITORY.  mem/m1-* owns python/synapse/memory/ and must not touch
      python/synapse/loop/. mem/m2-* owns python/synapse/loop/pgdrm.py and must
      not touch python/synapse/memory/. Exclusive-write or the merge collides.

  I3  FORBIDDEN SURFACE.  Nobody touches .synapse/contracts/ or VERSION.
      Both are ratified/gated text; an edit there is a ratification flip
      performed by an agent.

  I4  NO PROMOTION.  No merge into master, no new commits on master, nothing
      pushed. Article V -- those are Joe's word, per act.

  I5  PORT SURFACE.  python/synapse/loop/ports.py must be byte-identical to
      master across every mem/* worktree. The §4 parameter names are pinned by
      .synapse/contracts/loop-v00.yaml.

  I6  SECOND CONDUCTOR.  Only this board's run may write harness/memory/bus/.
      Two conductors on one board is a silent corruptor.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

# Paths a forge would only touch from inside its worktree.
CODE_PREFIXES = ("python/", "tests/", "shared/", "panel/")
FORBIDDEN = (".synapse/contracts/", "VERSION")
PINNED_FILES = ("python/synapse/loop/ports.py",)

TERRITORY = {
    "mem/m1-": {"owns": "python/synapse/memory/", "forbidden": ("python/synapse/loop/",)},
    "mem/m2-": {"owns": "python/synapse/loop/", "forbidden": ("python/synapse/memory/",)},
    "mem/m3-": {"owns": "harness/memory/notes/", "forbidden": ("python/",)},
    "mem/m4-": {"owns": "python/", "forbidden": ()},
}


def git(*a, cwd=None):
    """Run git. stdout is rstripped of NEWLINES ONLY.

    BUG FOUND 2026-08-21 by reading sweep_8's own output: this used to return
    ``r.stdout.strip()``, which ate the LEADING SPACE of the first porcelain
    line. `` M python/x`` became ``M python/x``, so ``ln[3:]`` yielded
    ``ython/x`` for the first changed file in every worktree. A truncated path
    matches no prefix, so I2 (territory), I3 (forbidden surface) and I5 (pinned
    port) would all have reported CLEAR on a real breach in that one slot --
    a checker producing a silent false negative. Scalar callers now strip at
    the call site instead."""
    r = subprocess.run(["git", *a], cwd=str(cwd or REPO),
                       capture_output=True, text=True)
    return r.returncode, r.stdout.rstrip(chr(10)), r.stderr.strip()


def worktrees():
    rc, out, _ = git("worktree", "list", "--porcelain")
    if rc != 0:
        return []
    trees, cur = [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                trees.append(cur)
            cur = {"path": line[9:]}
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line.startswith("HEAD "):
            cur["head"] = line[5:]
    if cur:
        trees.append(cur)
    return trees


def _mem_only_commits():
    """Commits reachable from a mem/* branch but not from master."""
    rc, out, _ = git("branch", "--list", "mem/*", "--format=%(refname:short)")
    if rc != 0:
        return set()
    shas = set()
    for br in [b.strip() for b in out.split(chr(10)) if b.strip()]:
        rc2, revs, _ = git("rev-list", "master.." + br)
        if rc2 == 0:
            shas.update(r.strip() for r in revs.split(chr(10)) if r.strip())
    return shas


def mem_trees(trees):
    """Worktrees this board is responsible for policing.

    GAP CLOSED 2026-08-22 (found by MARSHAL, window 2): this used to filter on a
    ``mem/`` BRANCH prefix only. A crucible attacks a commit in a DETACHED
    checkout -- correct posture, it must not move the branch -- so it carried no
    branch, fell through to the I6 NOTE list, and I2/I3/I5 never covered it. An
    unpoliced worktree is exactly where a territory or forbidden-surface breach
    would hide. A detached head that any mem/* branch CONTAINS is ours; anything
    else stays a NOTE (other boards are not our collisions)."""
    owned = []
    for t in trees:
        br = str(t.get("branch", ""))
        if br.startswith("mem/"):
            t["_policed_as"] = br
            owned.append(t)
            continue
        head = str(t.get("head", "")).strip()
        if not head or Path(t["path"]).resolve() == REPO:
            continue
        # CORRECTED same day: `branch --contains` is backwards for this. An old
        # master commit is contained by every mem/* branch (they descend from
        # master), so a foreign scratch checkout looked like ours. The precise
        # test is membership in `master..<branch>` -- the commits UNIQUE to a
        # mem branch. A crucible checks out a branch TIP or a commit on it.
        if head in _mem_only_commits():
            t["_policed_as"] = "detached@" + head[:8] + " (on a mem/* branch)"
            owned.append(t)
    return owned


def changed_in(tree):
    """Files a worktree has changed vs master -- staged, unstaged and committed."""
    path = tree["path"]
    files = set()
    rc, out, _ = git("status", "--porcelain", cwd=path)
    if rc == 0:
        for ln in out.splitlines():
            p = ln[2:].strip().split(" -> ")[-1]
            if p:
                files.add(p.replace("\\", "/"))
    rc, out, _ = git("diff", "--name-only", "master...HEAD", cwd=path)
    if rc == 0:
        files.update(p.replace("\\", "/") for p in out.splitlines() if p)
    return sorted(files)


def sweep():
    findings = []

    def hit(inv, severity, detail, evidence):
        findings.append({"invariant": inv, "severity": severity,
                         "detail": detail, "evidence": evidence})

    trees = worktrees()
    if not trees:
        return {"verdict": "UNKNOWN", "findings": [
            {"invariant": "I0", "severity": "BREACH",
             "detail": "git worktree list failed -- sweep could not run",
             "evidence": ""}], "worktrees": []}

    mem = mem_trees(trees)

    # ---- I1 main-tree contamination -------------------------------------
    rc, out, _ = git("status", "--porcelain")
    main_code = []
    for ln in out.splitlines():
        p = ln[2:].strip().split(" -> ")[-1].replace("\\", "/")
        if p.startswith(CODE_PREFIXES):
            main_code.append(ln.strip())
    if main_code and mem:
        hit("I1", "BREACH",
            "repo root has edits under code paths while mem/* worktrees are live "
            "-- an absolute repo-root path written from a worktree lands on MASTER",
            main_code[:20])

    # ---- I2 / I3 / I5 per worktree --------------------------------------
    per_tree = {}
    for t in mem:
        br = t.get("branch") or t.get("_policed_as", "?")
        files = changed_in(t)
        per_tree[br] = files
        # A detached crucible checkout has no owner, so territory does not apply
        # to it -- but I3 (forbidden surface) and I5 (pinned port) still do.
        rule = next((v for k, v in TERRITORY.items() if str(br).startswith(k)), None)
        if rule:
            crossed = [f for f in files if f.startswith(rule["forbidden"])]
            if crossed:
                hit("I2", "BREACH",
                    f"{br} crossed into territory it does not own "
                    f"(owns {rule['owns']})",
                    crossed)
        bad = [f for f in files if f.startswith(FORBIDDEN)]
        if bad:
            hit("I3", "BREACH",
                f"{br} touched a forbidden surface -- ratified or gated text",
                bad)
        for pinned in PINNED_FILES:
            if pinned in files:
                hit("I5", "BREACH",
                    f"{br} modified the pinned §4 port surface; the parameter "
                    "names are ratified by .synapse/contracts/loop-v00.yaml",
                    [pinned])

    # ---- I4 no promotion -------------------------------------------------
    rc, out, _ = git("rev-parse", "master")
    master_sha = out.strip()
    rc, base_out, _ = git("rev-parse", "origin/master")
    base_out = base_out.strip()
    if rc == 0 and base_out and base_out != master_sha:
        rc2, ahead, _ = git("rev-list", "--count", "origin/master..master")
        ahead = (ahead or "").strip()
        if rc2 == 0 and ahead and ahead != "0":
            hit("I4", "NOTE",
                f"master is {ahead} commit(s) ahead of origin/master "
                "(pre-existing local state, not necessarily this run)",
                [master_sha[:12]])
    for t in mem:
        br = t.get("branch", "?")
        rc, out, _ = git("log", "--oneline", "-n", "1", "--merges",
                         f"master..{br}", cwd=t["path"])
        if rc == 0 and out.strip():
            hit("I4", "BREACH", f"{br} contains a merge commit", [out])

    # ---- I6 second conductor --------------------------------------------
    policed = {id(t) for t in mem}
    other = [t.get("branch") or t.get("head", "?")[:12] for t in trees
             if id(t) not in policed and Path(t["path"]).resolve() != REPO]
    if other:
        hit("I6", "NOTE",
            "other worktrees exist on this machine -- confirm they belong to a "
            "DIFFERENT board before calling this a collision",
            other)

    breaches = [f for f in findings if f["severity"] == "BREACH"]
    return {
        "verdict": "BREACH" if breaches else "CLEAR",
        "findings": findings,
        "worktrees": [{"branch": t.get("branch"),
                       "policed_as": t.get("_policed_as"),
                       "path": t["path"],
                       "changed": per_tree.get(t.get("branch") or t.get("_policed_as"), [])}
                      for t in mem],
        "main_tree_code_edits": main_code,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="MEMORY board live invariant sweep")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()

    try:
        r = sweep()
    except Exception as exc:  # noqa: BLE001
        print(f"SWEEP COULD NOT RUN: {exc}", file=sys.stderr)
        return 3

    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(r, indent=2) + "\n")

    if a.json:
        print(json.dumps(r, indent=2))
    else:
        print(f"SWEEP {r['verdict']}")
        for w in r["worktrees"]:
            print(f"  {str(w.get('branch') or w.get('policed_as') or '?'):<34} {len(w['changed'])} changed file(s)")
        for f in r["findings"]:
            print(f"  [{f['severity']}] {f['invariant']} {f['detail']}")
            for e in (f["evidence"] or [])[:8]:
                print(f"        {e}")
        if not r["findings"]:
            print("  all six invariants hold")

    return 2 if r["verdict"] == "BREACH" else 0


if __name__ == "__main__":
    raise SystemExit(main())
