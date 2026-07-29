"""Is this leg's worktree a real worktree, or a directory pretending to be one?

    python harness/worktree_guard.py audit        # every leg; exits 5 if any is armed
    python harness/worktree_guard.py check H5     # one leg
    python harness/worktree_guard.py classify .claude/worktrees/h5-compat

WHY THIS EXISTS
---------------
`.claude/worktrees/` holds 26 directories. Twelve are registered git worktrees.
The other fourteen are ORPHANS - plain directories that still sit inside the
main repository. Because they are inside it, every git command run from one
walks up and resolves to the main repo:

    git -C .claude/worktrees/h2-requalify rev-parse --show-toplevel
        -> C:/Users/User/SYNAPSE
    git -C .claude/worktrees/h2-requalify rev-parse --abbrev-ref HEAD
        -> feat/repair-heats-01

`orchestrate.ps1:238` creates a worktree only when the directory is ABSENT:

    if (-not (Test-Path $wt)) { git worktree add -b $leg.branch $wt HEAD }

So an orphan makes the dispatcher skip creation and launch a headless agent -
with acceptEdits - whose commits land on the live branch of the main tree.
Fourteen legs point at orphans and nine of those are `state: ready`.

Constitution Article V requires one worktree per parallel agent. This is the
failure mode where the isolation mechanism silently routes back into the thing
it is isolating from, which is worse than having no isolation at all, because
the board reports the leg as isolated.

WHAT IT WILL NOT DO
-------------------
It never deletes, moves, prunes, or repairs anything. Law 4: census output is a
hypothesis, and classification precedes deletion by a human. A prior
housekeeping pass on this repo pruned three worktrees whose receipts had never
been committed and destroyed the only copies (`orchestrate.ps1:142-150`). An
orphan may be the last copy of something. It is reported, never reclaimed.

THE TWO CHECKS
--------------
Registry   - is the path in `git worktree list --porcelain`? Authoritative for
             what git believes.
Resolution - does `rev-parse --show-toplevel` from that path equal the main
             repo root? This is the one that names the actual harm, and it is
             observed rather than inferred.

A path fails if EITHER check says it is not its own worktree.

Law 1 - the condition under which this fails: `audit` exits 5 while any leg's
worktree directory exists but is not its own git worktree. Against this tree
today that is nine ready legs, so the check is red on arrival - which is the
point. Pinned by `tests/test_worktree_guard.py`.
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "harness", "legs.json")

OK_STATES = ("registered", "absent")

EXIT_ARMED = 5


def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def _git(cwd, *a):
    r = subprocess.run(["git", "-C", cwd] + list(a), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else None


def registered_worktrees():
    """Normalized paths git considers worktrees, main tree included."""
    out = _git(ROOT, "worktree", "list", "--porcelain") or ""
    return {_norm(ln[len("worktree "):]) for ln in out.splitlines()
            if ln.startswith("worktree ")}


def classify(path, registry=None):
    """'registered' | 'orphan' | 'absent' | 'foreign'

    orphan  - the directory exists but is not its own worktree. The dangerous
              case: a dispatcher will skip creation and run an agent there.
    foreign - exists, is not registered, and does NOT resolve into this repo.
              Not our problem, but not a worktree either.
    """
    abs_p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.isdir(abs_p):
        return "absent"
    reg = registry if registry is not None else registered_worktrees()
    if _norm(abs_p) in reg:
        return "registered"
    top = _git(abs_p, "rev-parse", "--show-toplevel")
    if top is None:
        return "foreign"
    return "orphan" if _norm(top) == _norm(ROOT) else "foreign"


def resolves_to(path):
    """What a git command run from here would actually target. For the report."""
    abs_p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.isdir(abs_p):
        return (None, None)
    return (_git(abs_p, "rev-parse", "--show-toplevel"),
            _git(abs_p, "rev-parse", "--abbrev-ref", "HEAD"))


def verify(worktree, registry=None):
    """(ok, state, reason). `absent` is OK - the dispatcher creates it."""
    if not worktree:
        return (True, "none", "leg declares no worktree")
    st = classify(worktree, registry)
    if st in OK_STATES:
        return (True, st, "")
    if st == "orphan":
        top, br = resolves_to(worktree)
        return (False, st,
                "directory exists but is NOT a git worktree; git from here "
                "resolves to %s on %s - an agent dispatched here would write "
                "to the main tree" % (top, br))
    return (False, st, "directory exists and is not a worktree of this repo")


def _legs():
    with open(MANIFEST, encoding="utf-8-sig") as fh:
        return json.load(fh)["legs"]


def cmd_audit(a):
    reg = registered_worktrees()
    armed, clean = [], 0
    for leg in _legs():
        ok, st, why = verify(leg.get("worktree"), reg)
        if ok:
            clean += 1
            if a.verbose:
                print("  ok      %-8s %-10s %s" % (leg["id"], st, leg.get("worktree") or ""))
            continue
        armed.append((leg, st, why))

    for leg, st, why in armed:
        top, br = resolves_to(leg.get("worktree"))
        print("  ARMED   %-8s state=%-8s %s" % (leg["id"], leg.get("state"), leg.get("worktree")))
        print("          %s -> %s @ %s" % (st, top, br))

    print()
    print("  %d clean, %d ARMED" % (clean, len(armed)))
    if armed:
        ready = [l["id"] for l, _, _ in armed if l.get("state") == "ready"]
        print("  dispatchable right now: %s" % (" ".join(ready) or "(none)"))
        print()
        print("  These directories are NOT deleted by this tool and must not be")
        print("  deleted without classifying their contents first (Law 4). To")
        print("  re-register one that holds nothing you need:")
        print("      git worktree add -b <branch> <path> HEAD   # after moving it aside")
        return EXIT_ARMED
    return 0


def cmd_check(a):
    leg = next((l for l in _legs() if l["id"] == a.leg), None)
    if leg is None:
        print("no such leg: %s" % a.leg)
        return 1
    ok, st, why = verify(leg.get("worktree"))
    if ok:
        print("ok %s (%s)" % (a.leg, st))
        return 0
    print("ARMED %s (%s): %s" % (a.leg, st, why))
    return EXIT_ARMED


def cmd_classify(a):
    st = classify(a.path)
    top, br = resolves_to(a.path)
    print("%s: %s" % (a.path, st))
    if top:
        print("  git here resolves to %s @ %s" % (top, br))
    return 0 if st in OK_STATES else EXIT_ARMED


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    au = sub.add_parser("audit")
    au.add_argument("-v", "--verbose", action="store_true")
    ck = sub.add_parser("check")
    ck.add_argument("leg")
    cl = sub.add_parser("classify")
    cl.add_argument("path")
    ns = p.parse_args(argv)
    return {"audit": cmd_audit, "check": cmd_check, "classify": cmd_classify}[ns.cmd](ns)


if __name__ == "__main__":
    sys.exit(main())
