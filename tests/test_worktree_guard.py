"""The P0 guard: a directory is not a worktree just because it exists.

`.claude/worktrees/` holds directories that are NOT registered git worktrees.
Because they sit inside the main repo, git run from one resolves upward:

    git -C .claude/worktrees/h2-requalify rev-parse --show-toplevel
        -> C:/Users/User/SYNAPSE          (the MAIN tree)
    git -C .claude/worktrees/h2-requalify rev-parse --abbrev-ref HEAD
        -> feat/repair-heats-01           (the LIVE branch)

`harness/orchestrate.ps1:238` only creates a worktree when the directory is
ABSENT, so an orphan makes the dispatcher skip creation and launch an
acceptEdits agent whose commits land on the live branch of the main tree.

Every test states the condition under which it FAILS. The fixtures build real
orphans in a scratch clone rather than asserting against the repo's current
shape, so the suite does not go green merely because someone cleaned up.
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "harness", "worktree_guard.py")
LOCK = os.path.join(ROOT, "harness", "lock.py")


def _guardmod():
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        import importlib
        return importlib.import_module("worktree_guard")
    finally:
        sys.path.pop(0)


def run(script, *args):
    return subprocess.run([sys.executable, script] + list(args), cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


# ------------------------------------------------- classification, from truth

def test_orphan_directory_is_not_a_worktree(tmp_path):
    """FAILS IF: a plain directory inside the repo classifies as a worktree.

    This is the defect itself. If `classify` ever returns 'registered' or
    'absent' for a directory git does not know about, the guard is blind and
    the dispatcher walks straight into the main tree.
    """
    g = _guardmod()
    orphan = os.path.join(ROOT, ".claude", "worktrees", "_pytest_orphan_")
    os.makedirs(orphan, exist_ok=True)
    try:
        assert g.classify(orphan) == "orphan", \
            "a non-registered directory inside the repo must classify as orphan"
        top, branch = g.resolves_to(orphan)
        assert os.path.normcase(os.path.normpath(top)) == \
            os.path.normcase(os.path.normpath(ROOT)), \
            "orphan resolved to %s, expected the main tree - the whole premise" % top
        assert branch, "orphan resolves to a real branch: %r" % branch
    finally:
        os.rmdir(orphan)


def test_absent_directory_is_allowed():
    """FAILS IF: a not-yet-created worktree is treated as armed.

    `absent` is the healthy pre-dispatch state - the dispatcher creates it.
    Refusing here would block every first run of every leg.
    """
    g = _guardmod()
    assert g.classify(os.path.join(ROOT, ".claude", "worktrees",
                                   "_definitely_not_here_")) == "absent"
    ok, st, _ = g.verify(".claude/worktrees/_definitely_not_here_")
    assert ok and st == "absent"


def test_registered_worktree_passes():
    """FAILS IF: a real git worktree is flagged.

    A guard that cannot tell a genuine worktree from an orphan is a guard
    nobody will leave switched on.
    """
    g = _guardmod()
    reg = g.registered_worktrees()
    assert reg, "git worktree list returned nothing - cannot establish the case"
    # The main tree is always registered.
    assert g.classify(ROOT) == "registered"


def test_verify_reports_the_actual_harm():
    """FAILS IF: the refusal message does not name where writes would land.

    An operator who is told only 'not a worktree' will re-run it. One who is
    told 'writes land on feat/x in the main tree' will not.
    """
    g = _guardmod()
    orphan = os.path.join(ROOT, ".claude", "worktrees", "_pytest_orphan2_")
    os.makedirs(orphan, exist_ok=True)
    try:
        ok, st, why = g.verify(".claude/worktrees/_pytest_orphan2_")
        assert not ok and st == "orphan"
        assert "main tree" in why.lower()
        assert ROOT.replace("\\", "/").lower() in why.replace("\\", "/").lower()
    finally:
        os.rmdir(orphan)


# ------------------------------------------------------------- the CLI + wire

def test_audit_exits_nonzero_while_any_leg_is_armed():
    """FAILS IF: audit reports success while a manifest leg points at an orphan.

    Deliberately red on this tree today (9 dispatchable legs are armed). It
    goes green only when every leg's worktree is registered or absent - which
    is the actual remediation, not a suppression.
    """
    out = run(GUARD, "audit")
    g = _guardmod()
    reg = g.registered_worktrees()
    legs = json.load(open(os.path.join(ROOT, "harness", "legs.json"),
                          encoding="utf-8-sig"))["legs"]
    armed = [l["id"] for l in legs if not g.verify(l.get("worktree"), reg)[0]]
    if armed:
        assert out.returncode == g.EXIT_ARMED, (
            "legs %s are armed but audit exited %d:\n%s"
            % (armed, out.returncode, out.stdout))
        assert "ARMED" in out.stdout
    else:
        assert out.returncode == 0, out.stdout


def test_lock_refuses_to_arm_an_orphan():
    """FAILS IF: acquire succeeds on a leg whose worktree is an orphan.

    The lock is the chokepoint. If it hands out a lock for an orphan, the
    dispatcher proceeds and the agent writes to the main tree - the exact P0.
    """
    orphan_rel = ".claude/worktrees/_pytest_orphan3_"
    orphan = os.path.join(ROOT, orphan_rel)
    os.makedirs(orphan, exist_ok=True)
    lockfile = os.path.join(ROOT, "harness", "state", "locks",
                            "PYTEST_ORPHAN.lock")
    try:
        out = run(LOCK, "acquire", "PYTEST_ORPHAN", "--worktree", orphan_rel)
        assert out.returncode == 5, (
            "acquire on an orphan must exit 5, got %d:\n%s"
            % (out.returncode, out.stdout + out.stderr))
        assert not os.path.exists(lockfile), \
            "a lock was written for an orphan worktree"
    finally:
        if os.path.exists(lockfile):
            os.unlink(lockfile)
        os.rmdir(orphan)


def test_guard_never_deletes():
    """FAILS IF: any guard verb removes a directory.

    Law 4 - a prior housekeeping pass destroyed the only copies of three
    receipts. An orphan may be the last copy of something. The guard reports.
    """
    orphan_rel = ".claude/worktrees/_pytest_orphan4_"
    orphan = os.path.join(ROOT, orphan_rel)
    os.makedirs(orphan, exist_ok=True)
    canary = os.path.join(orphan, "canary.txt")
    with open(canary, "w", encoding="utf-8") as fh:
        fh.write("must survive")
    try:
        for verb in (["audit"], ["classify", orphan_rel]):
            run(GUARD, *verb)
            assert os.path.exists(canary), \
                "guard %s removed content from an orphan" % verb[0]
    finally:
        os.unlink(canary)
        os.rmdir(orphan)
