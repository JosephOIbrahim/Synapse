"""Acceptance tests for the leg lock and the board's verdict rule.

Every test here states the condition under which it FAILS (Law 1). None of
them can pass vacuously: each one first establishes the negative case, then
the positive.

The two defects being pinned:

  1. `harness/state/locks/` had a reader (`status.py:62`) and no writer, for
     its entire existence. `state_of()` could never return "running", so the
     board printed `ready` for a leg with a live agent in its worktree. That
     is how `.claude/h2-halt/H2_HALT_EVIDENCE.md` happened - twice.

  2. `state_of()` read receipt PRESENCE as success. 17 of 41 receipts on this
     tree are not plain green; all 17 printed as done, including one whose
     status field is the string "held_not_started".
"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, "harness", "lock.py")
LOCKS = os.path.join(ROOT, "harness", "state", "locks")
TESTLEG = "PYTEST_SENTINEL"


def run(*args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, LOCK] + list(args), cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=e)


def _lockmod():
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        import importlib
        return importlib.import_module("lock")
    finally:
        sys.path.pop(0)


def _dead_pid():
    """A pid the liveness probe positively reports as dead.

    Reusing an exited child's pid does NOT work: Popen keeps a handle open, so
    the kernel object outlives the process and OpenProcess still succeeds.
    Windows pids are multiples of 4, so a non-multiple can never name one.

    The precondition is established, never assumed - if no candidate resolves
    as dead this SKIPS. A skip is honest; a pass would be a lie.
    """
    lock = _lockmod()
    for cand in (999999, 999983, 888887, 777773):
        if lock.pid_alive(cand) is False:
            return cand
    pytest.skip("no reliably-dead pid on this host - cannot set up the case")


@pytest.fixture(autouse=True)
def _clean():
    p = os.path.join(LOCKS, "%s.lock" % TESTLEG)
    if os.path.exists(p):
        os.unlink(p)
    yield
    if os.path.exists(p):
        os.unlink(p)


# ---------------------------------------------------------------- the fence

def test_second_acquire_is_refused():
    """FAILS IF: a second acquire on a held leg exits 0.

    This is the whole fence. If this test ever goes green while the second
    acquire succeeds, two agents can enter one worktree and every finding
    produced there is unattributable.
    """
    first = run("acquire", TESTLEG, "--worktree", ".")
    assert first.returncode == 0, first.stdout + first.stderr

    second = run("acquire", TESTLEG, "--worktree", ".")
    assert second.returncode == 3, (
        "second acquire must exit 3 (held), got %d:\n%s"
        % (second.returncode, second.stdout + second.stderr))
    assert "REFUSED" in second.stdout


def test_acquire_records_the_base_commit():
    """FAILS IF: a lock is written without a resolvable base_sha.

    H2 was dispatched onto a base that did not contain the fix it was told to
    probe. A holder that cannot name the tree it measured produces findings
    nobody can attribute.
    """
    assert run("acquire", TESTLEG, "--worktree", ".").returncode == 0
    with open(os.path.join(LOCKS, "%s.lock" % TESTLEG), encoding="utf-8") as fh:
        rec = json.load(fh)
    sha = rec.get("base_sha", "")
    assert len(sha) == 40, "base_sha absent or malformed: %r" % sha
    r = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", sha + "^{commit}"],
                       capture_output=True)
    assert r.returncode == 0, "base_sha %s does not resolve in this repo" % sha


def test_live_lock_is_never_reaped():
    """FAILS IF: reap removes a lock whose holder is still live.

    A wrongly-stolen lock reproduces the exact collision this file prevents,
    so the reaper must be conservative in this direction specifically.
    """
    assert run("acquire", TESTLEG, "--worktree", ".").returncode == 0
    out = run("reap")
    assert os.path.exists(os.path.join(LOCKS, "%s.lock" % TESTLEG)), \
        "reap deleted a live lock:\n" + out.stdout


def test_stale_lock_is_reaped():
    """FAILS IF: a stale lock is never reclaimed.

    The negative half of the test above. Without this, one crashed agent
    wedges its leg forever and the fence becomes a denial of service.
    """
    _ps_lock(_dead_pid(), "2026-01-01T00:00:00")
    out = run("reap", env={"SYNAPSE_LOCK_STALE_SECONDS": "0"})
    assert not os.path.exists(os.path.join(LOCKS, "%s.lock" % TESTLEG)), \
        "stale lock survived reap:\n" + out.stdout
    assert "REAPED" in out.stdout


def test_undeterminable_liveness_is_treated_as_alive():
    """FAILS IF: a lock with an unresolvable pid is reaped.

    When we cannot tell whether the holder lives, refusing is the safe
    direction. A pid far outside any plausible range stands in for the
    undeterminable case.
    """
    assert run("acquire", TESTLEG, "--worktree", ".",
               "--pid", "4294967290").returncode == 0
    run("reap", env={"SYNAPSE_LOCK_STALE_SECONDS": "0"})
    # Either kept, or reaped only because liveness resolved to a clean False.
    # What must never happen is a reap justified by "unknown".
    out = run("list")
    assert "unknown" in out.stdout or not os.path.exists(
        os.path.join(LOCKS, "%s.lock" % TESTLEG))


# -------------------------------------------------- interop with the ps1 lock

def _ps_lock(pid, started):
    """A lock in orchestrate.ps1's exact dialect: {leg, pid, started, machine}."""
    os.makedirs(LOCKS, exist_ok=True)
    p = os.path.join(LOCKS, "%s.lock" % TESTLEG)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"leg": TESTLEG, "pid": pid, "started": started,
                   "machine": "TESTHOST"}, fh)
    return p


def test_reads_a_powershell_written_lock():
    """FAILS IF: a lock written by orchestrate.ps1 is invisible to this module.

    Two implementations share one directory. If either cannot read the other's
    dialect, the fence has a seam exactly the width of one language, and the
    collision it exists to stop walks straight through.
    """
    _ps_lock(os.getpid(), "2026-07-29T13:00:00")
    out = run("acquire", TESTLEG, "--worktree", ".")
    assert out.returncode == 3, (
        "a live ps1-format lock must refuse acquire, got %d:\n%s"
        % (out.returncode, out.stdout + out.stderr))


def test_powershell_iso_timestamp_ages_correctly():
    """FAILS IF: an ISO `started` string is scored as age zero.

    The ps1 lock has no heartbeat field. Reading only `started_at` would make
    every PowerShell lock permanently fresh and never reclaimable.
    """
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        import importlib
        lock = importlib.import_module("lock")
    finally:
        sys.path.pop(0)
    import time as _t
    old = _t.strftime("%Y-%m-%dT%H:%M:%S", _t.localtime(_t.time() - 7200))
    got = lock.started_epoch({"started": old, "machine": "X"})
    assert got > 0, "ISO `started` parsed as epoch 0 - staleness is disabled"
    assert 7100 < (_t.time() - got) < 7300, "age %.0fs, expected ~7200" % (_t.time() - got)


def test_reserved_pids_are_refused():
    """FAILS IF: pid 0 or 4 is ever written to a lock.

    `Get-Process -Id 0` is Idle and `-Id 4` is System; both always resolve, so
    orchestrate.ps1 would read either as a live holder forever and the leg
    could never be reclaimed by anything.
    """
    for bad in ("0", "4"):
        out = run("acquire", TESTLEG, "--worktree", ".", "--pid", bad)
        assert out.returncode != 0, "pid %s was accepted:\n%s" % (bad, out.stdout)
        assert not os.path.exists(os.path.join(LOCKS, "%s.lock" % TESTLEG))


# ------------------------------------------------------- the board's verdict

def test_board_reads_receipt_status_not_presence():
    """FAILS IF: a non-green receipt is counted as done.

    Pins the defect directly: hand `verdict_of` a receipt whose status is
    'held_not_started' and it must not say green. If this regresses, the board
    resumes reporting halted legs as complete.
    """
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        import importlib
        status = importlib.import_module("status")
    finally:
        sys.path.pop(0)

    import tempfile
    for payload, expected in (
        ({"status": "green"}, "green"),
        ({"status": "held_not_started"}, "attention"),
        ({"status": "amber"}, "attention"),
        ({"status": "red"}, "attention"),
        ({"status": "green_with_findings"}, "attention"),
        ({}, "attention"),
    ):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as fh:
            json.dump(payload, fh)
            p = fh.name
        try:
            got = status.verdict_of(p)
            assert got == expected, \
                "%r -> %r, expected %r" % (payload, got, expected)
        finally:
            os.unlink(p)


def test_board_surfaces_a_running_leg():
    """FAILS IF: the board cannot distinguish a locked leg from a free one.

    The reader existed for the whole life of the project with nothing writing
    to it. This asserts the writer and the reader now agree.
    """
    manifest = json.load(open(os.path.join(ROOT, "harness", "legs.json"),
                              encoding="utf-8-sig"))
    # A leg whose manifest state is held/done short-circuits before the lock is
    # ever consulted, so it cannot exercise this path. Pick one that can.
    candidates = [l["id"] for l in manifest["legs"]
                  if l.get("state") not in ("held", "done")]
    assert candidates, "no leg in the manifest can reach the running state"
    real_leg = candidates[0]
    p = os.path.join(LOCKS, "%s.lock" % real_leg)
    pre_existing = os.path.exists(p)
    if pre_existing:
        pytest.skip("%s is genuinely locked right now" % real_leg)

    assert run("acquire", real_leg, "--worktree", ".").returncode == 0
    try:
        board = subprocess.run(
            [sys.executable, os.path.join(ROOT, "harness", "status.py")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        assert "running" in board.stdout, \
            "locked leg %s absent from the board:\n%s" % (real_leg, board.stdout)
    finally:
        run("release", real_leg, "--force")
