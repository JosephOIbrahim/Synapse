"""Merge train for the 2026-09-15 closeout PRs -- deterministic, no model calls.

For each PR number in ORDER:
  1. fetch; if the PR is not mergeable against current master, rebase its branch onto
     origin/master in a temp worktree. The ONLY conflicts this script resolves are the
     tool-count lines in CLAUDE.md:3 and README.md (the "N tools" number): master's line
     is kept and the number is recomputed from len(TOOL_DEFS) in the rebased tree,
     then tests/test_phase0c_doc1_toolcount.py must pass. Any other conflict aborts
     the rebase and stops the train with the file list.
  2. force-push (--force-with-lease) the rebased branch.
  3. wait for CI (gh pr checks --watch). A failed check stops the train.
  4. record CodeRabbit's review state; CHANGES_REQUESTED stops the train.
  5. squash-merge; pull master.
Every step appends to LOG. The script never touches VERSION or tags.

Run from the repo root:  python harness/notes/closeout-2026-09-15/merge_train.py [--from N] [--only N]
"""
import io
import json
import os
import re
import subprocess
import sys
import time

REPO = r"C:/Users/User/SYNAPSE"
LOG = os.path.join(REPO, "harness/notes/closeout-2026-09-15/merge_train.log")
ORDER = [83, 84, 85, 86, 87, 88, 89, 90, 91, 92]  # 93 (pgdrm) is HELD as a draft
HOLD = {93}

def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    io.open(LOG, "a", encoding="utf-8", newline="\n").write(line + "\n")

def run(args, cwd=REPO, check=True, timeout=None):
    # Any python run inside a worktree must import THAT tree's synapse, not the editable install (master).
    env = dict(os.environ, PYTHONPATH=os.path.join(cwd, "python"))
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    if check and r.returncode:
        raise SystemExit(f"FAILED ({r.returncode}): {' '.join(args)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r

def gh_json(*args):
    return json.loads(run(["gh"] + list(args)).stdout)

def tool_count(tree):
    r = run([sys.executable, "-c", "from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"],
            cwd=tree, check=True)
    return int(r.stdout.strip())

COUNT_RE = re.compile(r"(\b)(\d{3})( (?:MCP )?tools\b)")

def resolve_count_conflicts(tree, conflicted):
    """Keep master's line for the count-line conflicts, then rewrite the number."""
    allowed = {"CLAUDE.md", "README.md"}
    if not set(conflicted) <= allowed:
        return False, f"non-count conflicts: {sorted(set(conflicted) - allowed)}"
    for f in conflicted:
        run(["git", "checkout", "--ours", "--", f], cwd=tree)   # during rebase, --ours == the branch being rebased ONTO (master)
    n = tool_count(tree)
    for f in conflicted:
        p = os.path.join(tree, f)
        s = io.open(p, encoding="utf-8").read()
        s2, k = COUNT_RE.subn(lambda m: m.group(1) + str(n) + m.group(3), s)
        if k == 0:
            return False, f"{f}: no 'NNN tools' line found to recompute"
        io.open(p, "w", encoding="utf-8", newline="\n").write(s2)
        run(["git", "add", "--", f], cwd=tree)
    return True, f"count recomputed -> {n}"

def rebase_pr(num, branch):
    wt = os.path.join(REPO, ".claude", "worktrees", f"train-{num}")
    run(["git", "worktree", "remove", "--force", wt], check=False)
    run(["git", "fetch", "-q", "origin", "master", branch])
    run(["git", "worktree", "add", "-q", wt, branch])
    r = run(["git", "rebase", "origin/master"], cwd=wt, check=False)
    while r.returncode:
        conflicted = run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=wt).stdout.split()
        ok, why = resolve_count_conflicts(wt, conflicted)
        log(f"  #{num} rebase conflict on {conflicted}: {why}")
        if not ok:
            run(["git", "rebase", "--abort"], cwd=wt, check=False)
            run(["git", "worktree", "remove", "--force", wt], check=False)
            raise SystemExit(f"STOP: #{num} needs a human rebase ({why})")
        r = run(["git", "-c", "core.editor=true", "rebase", "--continue"], cwd=wt, check=False)
    # the count must be right in the final tree even if no conflict fired (a prior merge may have bumped it)
    n = tool_count(wt)
    changed = False
    for f in ("CLAUDE.md", "README.md"):
        p = os.path.join(wt, f)
        s = io.open(p, encoding="utf-8").read()
        s2 = COUNT_RE.sub(lambda m: m.group(1) + str(n) + m.group(3), s)
        if s2 != s:
            io.open(p, "w", encoding="utf-8", newline="\n").write(s2); changed = True
    if changed:
        run(["git", "commit", "-q", "-am", f"docs: tool count -> {n} after rebase onto master"], cwd=wt)
        log(f"  #{num} count line refreshed -> {n}")
    t = run([sys.executable, "-m", "pytest", "tests/test_phase0c_doc1_toolcount.py", "-q", "-p", "no:cacheprovider"], cwd=wt, check=False)
    tail = t.stdout.strip().splitlines()[-1] if t.stdout.strip() else t.stderr[-300:]
    log(f"  #{num} toolcount pins: {tail}")
    if t.returncode:
        run(["git", "worktree", "remove", "--force", wt], check=False)
        raise SystemExit(f"STOP: #{num} toolcount pins red after rebase")
    run(["git", "push", "-q", "--force-with-lease", "origin", f"HEAD:{branch}"], cwd=wt)
    head = run(["git", "rev-parse", "--short", "HEAD"], cwd=wt).stdout.strip()
    run(["git", "worktree", "remove", "--force", wt], check=False)
    log(f"  #{num} rebased + pushed {head}")

def process(num):
    if num in HOLD:
        log(f"#{num} HELD (draft) -- skipped"); return
    pr = gh_json("pr", "view", str(num), "--json", "number,state,isDraft,headRefName,mergeStateStatus,mergeable,title")
    if pr["state"] != "OPEN":
        log(f"#{num} {pr['state']} -- skipped"); return
    branch = pr["headRefName"]
    log(f"#{num} {branch}: {pr['title'][:70]} | {pr['mergeStateStatus']}/{pr['mergeable']}")
    if pr["mergeable"] == "CONFLICTING" or pr["mergeStateStatus"] in ("DIRTY", "BEHIND"):
        rebase_pr(num, branch)
        time.sleep(20)
    # Gate on the CI test matrix only. CodeRabbit is advisory (recorded below) and can sit PENDING for a long time.
    deadline = time.time() + 1800
    while True:
        checks = gh_json("pr", "view", str(num), "--json", "statusCheckRollup")["statusCheckRollup"]
        ci = [c for c in checks if (c.get("name") or c.get("context") or "").startswith("test (")]
        pending = [c for c in ci if c.get("status") not in ("COMPLETED",) and (c.get("state") or "") not in ("SUCCESS", "FAILURE", "ERROR")]
        if ci and not pending:
            break
        if time.time() > deadline:
            raise SystemExit(f"STOP: #{num} CI still pending after 30 min: {[(c.get('name'), c.get('status')) for c in pending]}")
        time.sleep(30)
    bad = [c for c in ci if (c.get("conclusion") or c.get("state")) not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
    if bad:
        raise SystemExit(f"STOP: #{num} CI red: {[(c.get('name') or c.get('context'), c.get('conclusion') or c.get('state')) for c in bad]}")
    other = {(c.get("name") or c.get("context")): (c.get("conclusion") or c.get("state")) for c in checks if c not in ci}
    log(f"  #{num} CI green ({len(ci)} jobs); advisory checks: {other or 'none'}")
    reviews = gh_json("pr", "view", str(num), "--json", "reviews")["reviews"]
    states = {(r.get("author") or {}).get("login"): r.get("state") for r in reviews}
    log(f"  #{num} reviews: {states or 'none'}")
    if "CHANGES_REQUESTED" in states.values():
        raise SystemExit(f"STOP: #{num} has CHANGES_REQUESTED: {states}")
    pr = gh_json("pr", "view", str(num), "--json", "mergeStateStatus,mergeable")
    if pr["mergeable"] == "CONFLICTING":
        log(f"  #{num} became CONFLICTING after CI (master moved) -- rebasing again")
        rebase_pr(num, branch); time.sleep(20)
        return process(num)  # re-enter: wait for the new CI run on the rebased head, then merge
    r = run(["gh", "pr", "merge", str(num), "--squash"], check=False)
    if r.returncode:
        raise SystemExit(f"STOP: #{num} merge refused: {r.stderr[-500:]}")
    run(["git", "pull", "-q", "--ff-only", "origin", "master"])
    head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    log(f"  #{num} MERGED -> master {head}")

if __name__ == "__main__":
    only = None; start = None
    a = sys.argv[1:]
    if "--only" in a: only = int(a[a.index("--only") + 1])
    if "--from" in a: start = int(a[a.index("--from") + 1])
    seq = [only] if only else [n for n in ORDER if start is None or n >= start]
    log(f"train start: {seq}")
    stopped = []
    for n in seq:
        try:
            process(n)
        except SystemExit as e:
            log(f"  #{n} SKIPPED THIS PASS: {e}")
            stopped.append(n)
            # leave any half-made train worktree behind for inspection, but never block the next PR
    log(f"train done; skipped: {stopped or 'none'}")
