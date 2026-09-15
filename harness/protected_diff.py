#!/usr/bin/env python
"""harness/protected_diff.py - "what did this cycle actually change, and is any of
it protected?", asked of git rather than of a file the agent can edit.

1h repair round (harness-review 2026-09-15, FENCE-4). The first cut of 1h asked
`git diff --name-only <base>..HEAD` in each consumer, with `<base>` read from
`<wt>/.claude/.cycle_base` - an untracked, gitignored file inside the agent's own
writable worktree. Four holes followed, all of them a clean bypass:

  1. `echo $(git rev-parse HEAD) > .claude/.cycle_base` makes the diff empty, so
     any protected change is invisible.                       [base tampering]
  2. `git mv VERSION VERSION.bak` - `--name-only` reports the rename DESTINATION
     only, so moving a protected file out of the way read clean. [rename]
  3. `Copy-Item x VERSION` without a commit - the check saw committed history
     only, and REPORT.md row 1h says "a run whose worktree TOUCHES VERSION".
                                                               [uncommitted]
  4. the same, staged but not committed.                       [staged]

This module is the ONE answer to all four, and the ONE thing both consumers
(harness/run.ts, harness/orchestrate.ps1) shell out to, so their notion of "what
changed" cannot drift. It uses harness/protected_paths.py as the matcher, which
in turn reads harness/protected_paths.txt - still the single protected set.

BASE RESOLUTION (hole 1). The recorded .cycle_base is a HINT, never the
authority. It is used only if it is a real commit AND an ancestor of HEAD AND
at-or-before merge-base(<dispatch ref>, HEAD). An agent that moves the marker
FORWARD (the only useful direction for hiding work) fails that last test, and
the merge-base wins - so the tampered run is judged from the true fork point and
the change it tried to hide is reported. Moving the marker BACKWARD only widens
the diff, which cannot hide anything. If neither source resolves, that is exit 2:
"cannot prove untouched" is not "untouched".

CHANGE SET (holes 2-4). The union of four questions, all with `--no-renames` so a
move is reported as delete+add:
    git diff --no-renames --name-only <base>..HEAD   committed on the branch
    git diff --no-renames --name-only HEAD           unstaged, tracked
    git diff --no-renames --name-only --cached HEAD  staged
    git ls-files --others --exclude-standard         untracked, not ignored

SCOPE - what this does NOT fence (stated plainly rather than implied away).
Files that .gitignore excludes are invisible to every question above, so the
gitignored members of harness/state/** (drop.json, posture.json,
release_readiness_verdict.json, studio_readiness_verdict.json, suite_stamp.json,
DECISIONS.md) are OUT OF SCOPE here, as is anything written to the MAIN checkout
rather than to the worktree - run.ts writes harness/state/done.json to the main
tree by design (run.ts:64), so a check that flagged it would refuse every honest
run. What this fences is the committed, staged, unstaged and untracked-tracked-
able surface of the leg's own worktree. The gitignored main-tree runtime state is
the pre-commit hook's ground (1b) and a human's, not this gate's.

CLI (stdlib only, no repo imports):
    python harness/protected_diff.py --worktree <wt> [--ref <dispatch ref>]
                                     [--base-file <path>] [--set-file <path>]
                                     [--explain]
Exit 0 = nothing protected changed; 1 = hits, one repo-relative path per line on
STDOUT; 2 = the check could not be made (one reason line on STDERR). With
--explain the resolved base and its provenance also go to STDERR (never STDOUT,
so a consumer can always read STDOUT as the hit list).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import protected_paths  # noqa: E402  (sibling module, stdlib-only)

EXIT_CLEAN = 0
EXIT_HIT = 1
EXIT_ERROR = 2

# Refs tried, in order, for the fork point when the caller names none. A cycle
# worktree is cut from the main checkout's HEAD, which is normally master.
DEFAULT_REFS = ("master", "main")


def _git(wt: str, *args: str):
    return subprocess.run(["git", "-C", wt, *args],
                          capture_output=True, text=True)


def _lines(out: str) -> list[str]:
    return [s.strip() for s in (out or "").splitlines() if s.strip()]


def _is_commit(wt: str, rev: str) -> bool:
    return _git(wt, "rev-parse", "--verify", "--quiet", rev + "^{commit}").returncode == 0


def _is_ancestor(wt: str, a: str, b: str) -> bool:
    return _git(wt, "merge-base", "--is-ancestor", a, b).returncode == 0


def read_base_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def resolve_base(wt: str, base_file: str, ref: str = "") -> tuple[str, str, str]:
    """(base_sha, provenance, error). The recorded marker is a hint that must
    survive two tests; the merge-base is the authority when they disagree."""
    recorded = read_base_file(base_file)
    if recorded and not (_is_commit(wt, recorded) and _is_ancestor(wt, recorded, "HEAD")):
        # a marker naming a foreign or non-ancestor commit proves nothing
        recorded = ""

    mb = ""
    mb_ref = ""
    refs = [r for r in ([ref] if ref else []) + list(DEFAULT_REFS) if r]
    for candidate in refs:
        if not _is_commit(wt, candidate):
            continue
        r = _git(wt, "merge-base", candidate, "HEAD")
        if r.returncode == 0 and r.stdout.strip():
            mb, mb_ref = r.stdout.strip(), candidate
            break

    if recorded and mb:
        if _is_ancestor(wt, recorded, mb):
            return recorded, "recorded .cycle_base (agrees with merge-base/%s)" % mb_ref, ""
        # the marker sits AHEAD of the fork point - the one direction that hides work
        return mb, ("merge-base/%s - the recorded .cycle_base %s is AHEAD of the fork "
                    "point and was discarded" % (mb_ref, recorded[:8])), ""
    if recorded:
        return recorded, "recorded .cycle_base (no fork ref resolvable to cross-check)", ""
    if mb:
        return mb, "merge-base/%s (no usable .cycle_base)" % mb_ref, ""
    return "", "", ("no cycle base at %s and no fork point resolvable from %s; cannot "
                    "prove VERSION/harness untouched" % (base_file, "/".join(refs) or "any ref"))


def changed_paths(wt: str, base: str) -> tuple[list[str], str]:
    """Every path this worktree changed: committed since `base`, unstaged, staged,
    and untracked-but-not-ignored. `--no-renames` so a move is delete + add."""
    out: list[str] = []
    probes = [
        ["diff", "--no-renames", "--name-only", "%s..HEAD" % base],
        ["diff", "--no-renames", "--name-only", "HEAD"],
        ["diff", "--no-renames", "--name-only", "--cached", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ]
    for argv in probes:
        r = _git(wt, *argv)
        if r.returncode != 0:
            return [], "git %s failed in %s: %s" % (
                " ".join(argv[:3]), wt, (r.stderr or "").strip()[:200])
        out.extend(_lines(r.stdout))
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq, ""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--worktree", required=True, help="the leg's worktree (a git checkout)")
    ap.add_argument("--ref", default="", help="dispatch ref to take the fork point from")
    ap.add_argument("--base-file", default="",
                    help="marker file (default: <worktree>/.claude/.cycle_base)")
    ap.add_argument("--set-file", default=protected_paths.DEFAULT_FILE,
                    help="protected set (default: harness/protected_paths.txt)")
    ap.add_argument("--explain", action="store_true",
                    help="write the resolved base and its provenance to stderr")
    a = ap.parse_args(argv)

    wt = a.worktree
    if not os.path.isdir(wt):
        sys.stderr.write("protected_diff: no such worktree: %s\n" % wt)
        return EXIT_ERROR
    if _git(wt, "rev-parse", "--git-dir").returncode != 0:
        sys.stderr.write("protected_diff: not a git checkout: %s\n" % wt)
        return EXIT_ERROR

    try:
        globs = protected_paths.load(a.set_file)
    except OSError as e:
        sys.stderr.write("protected_diff: cannot read %s: %s\n" % (a.set_file, e))
        return EXIT_ERROR
    if not globs:
        sys.stderr.write("protected_diff: %s declares no globs - refusing to vouch for an "
                         "empty set\n" % a.set_file)
        return EXIT_ERROR

    base_file = a.base_file or os.path.join(wt, ".claude", ".cycle_base")
    base, provenance, err = resolve_base(wt, base_file, a.ref)
    if err:
        sys.stderr.write("protected_diff: %s\n" % err)
        return EXIT_ERROR
    if a.explain:
        sys.stderr.write("protected_diff: base %s via %s\n" % (base[:8], provenance))

    paths, err = changed_paths(wt, base)
    if err:
        sys.stderr.write("protected_diff: %s\n" % err)
        return EXIT_ERROR

    hits = protected_paths.protected_hits(paths, globs)
    for h in hits:
        sys.stdout.write(h + "\n")
    return EXIT_HIT if hits else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
