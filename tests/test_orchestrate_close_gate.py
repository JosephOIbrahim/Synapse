"""Acceptance: orchestrate.ps1's close gate (W6-GATE) refuses to call a leg
'done' on receipt-file existence alone. A worktree receipt reaches 'done' ONLY
when it is committed as the branch HEAD (its own closing commit - the W5H rule,
HARDENING-SPEC S4) AND an explicit RELEASE line for the leg's claim is on the bus
(S5). Otherwise the leg holds at 'closing'.

The defect (HARDENING-SPEC Part A, S4/CRX0 + S5): `Get-LegState` returned 'done'
the instant `Get-ReceiptPath` found a receipt file - no commit check, no HEAD
check, no bus RELEASE check (orchestrate.ps1:151). Four waves of receipts
asserted a done-state that did not exist, and legs posted `claim` but never the
matching `status {release}` so `bus.py open_claims()` had no gate consumer.

R135 reconciliation (CTO_RULINGS_01.md:3895-3907). R135's standing answer, when
a leg cannot safely preserve its own work, is that the operator harvests the
receipt from OUTSIDE the contended tree - a third party commits it from the main
tree. The gate must not refuse that. It doesn't: the gate binds ONLY receipts
that live in the leg's own worktree; a main-tree (operator-harvested) receipt
greens as legacy, and a manifest-pinned state:done bypasses the gate entirely.
Both are pinned below so a future edit that breaks the reconciliation fails loud.

Get-LegState is exercised the way test_orchestrate_liveness.py exercises
Get-LastProgress: dot-source orchestrate.ps1 in library mode (SYNAPSE_ORCH_LIB=1
-> functions defined, board loop skipped) with -Repo isolated to a temp dir and
-DryRun set (so the dry run runs the identical checks a real run does), then call
the real function. Skips (never a false pass) where no PowerShell exists.

1h (harness-review 2026-09-15, FENCE-4 - the loud post-cycle check). The gate
now also runs `git diff --name-only <cycle base>..HEAD` through the one matcher
(harness/protected_paths.py over harness/protected_paths.txt) and refuses to
close green - reason prefixed PROTECTED-PATH - when the branch changed VERSION,
harness/state/** or harness/verify/*_baseline.json. `_build_repo` therefore
records a cycle base the way Start-Leg does (.claude/.cycle_base) and carries
the matcher into the scratch repo exactly as it carries bus.py.
"""
import json
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORCH = os.path.join(ROOT, "harness", "orchestrate.ps1")
BUSPY_SRC = os.path.join(ROOT, "harness", "autorevise", "bus.py")
PP_PY_SRC = os.path.join(ROOT, "harness", "protected_paths.py")
PP_TXT_SRC = os.path.join(ROOT, "harness", "protected_paths.txt")


def _powershell():
    return shutil.which("powershell") or shutil.which("pwsh")


pytestmark = pytest.mark.skipif(
    _powershell() is None,
    reason="no powershell/pwsh on this host - Get-LegState is ps1-only",
)


def _fwd(p):
    return str(p).replace("\\", "/")


def _git(wt, *args):
    r = subprocess.run(["git", "-C", str(wt), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, "git %s failed:\n%s\n%s" % (args, r.stdout, r.stderr)
    return r.stdout.strip()


def _leg_state(repo, leg):
    """Call the REAL Get-LegState with -Repo isolated to `repo` and -DryRun set.
    Returns (state, reason) where reason is the CloseGateReason the gate recorded
    (empty string when none)."""
    ps = _powershell()
    leg_json = json.dumps(leg)  # double-quoted keys only -> safe inside PS single quotes
    script = "\n".join([
        "$env:SYNAPSE_ORCH_LIB='1'",
        ". '%s' -Repo '%s' -DryRun -Quiet *> $null" % (_fwd(ORCH), _fwd(repo)),
        "$leg = '%s' | ConvertFrom-Json" % leg_json,
        "$state = Get-LegState $leg",
        "$reason = $script:CloseGateReason[$leg.id]",
        "Write-Output ('STATE=' + $state)",
        "Write-Output ('REASON=' + $reason)",
    ])
    out = subprocess.run(
        [ps, "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    assert out.returncode == 0, "powershell failed:\n%s\n%s" % (out.stdout, out.stderr)
    state, reason = None, ""
    for line in out.stdout.splitlines():
        if line.startswith("STATE="):
            state = line[len("STATE="):].strip()
        elif line.startswith("REASON="):
            reason = line[len("REASON="):].strip()
    return state, reason


def _build_repo(tmp_path):
    """A scratch repo root with bus.py in place and a `wt` worktree that is a real
    git repo carrying one product commit on branch wave99/close."""
    repo = tmp_path / "repo"
    (repo / "harness" / "autorevise").mkdir(parents=True)
    shutil.copy(BUSPY_SRC, repo / "harness" / "autorevise" / "bus.py")
    # 1h: Test-CloseGate shells out to the one matcher; carry it like bus.py.
    shutil.copy(PP_PY_SRC, repo / "harness" / "protected_paths.py")
    shutil.copy(PP_TXT_SRC, repo / "harness" / "protected_paths.txt")
    wt = repo / "wt"
    wt.mkdir()
    _git(wt, "init", "-q")
    _git(wt, "config", "user.email", "probe@synapse.local")
    _git(wt, "config", "user.name", "close gate test")
    _git(wt, "checkout", "-q", "-b", "wave99/close")
    # The fork point Start-Leg records at dispatch (.claude/.cycle_base): everything
    # after it is what the leg changed. product.txt lands AFTER the base on purpose, so
    # every clean-close test below also proves an unprotected diff does not refuse.
    _git(wt, "commit", "-q", "--allow-empty", "-m", "cycle base (what Start-Leg cut the worktree from)")
    (wt / ".claude").mkdir()
    (wt / ".claude" / ".cycle_base").write_text(_git(wt, "rev-parse", "HEAD") + "\n", encoding="utf-8")
    (wt / "product.txt").write_text("product work", encoding="utf-8")
    _git(wt, "add", "product.txt")
    _git(wt, "commit", "-q", "-m", "product work")
    (wt / "harness" / "notes" / "receipts").mkdir(parents=True)
    return repo, wt


LEG = {
    "id": "W99-CLOSEGATE", "name": "scratch close-gate leg",
    "receipt": "W99-CLOSEGATE.json", "branch": "wave99/close",
    "worktree": "wt", "deps": [],
}
RCPT_REL = "harness/notes/receipts/W99-CLOSEGATE.json"


def test_receipt_uncommitted_holds_at_closing(tmp_path):
    """V1: a receipt written into the worktree but not committed is 'closing',
    not 'done'. FAILS IF the state machine still greens on file existence."""
    repo, wt = _build_repo(tmp_path)
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green"}',
                               encoding="utf-8")
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "uncommitted receipt read as %r" % state
    assert "is not committed on" in reason, reason


def test_receipt_not_head_holds_at_closing(tmp_path):
    """V2: the receipt is committed but a later commit follows it, so it is not
    the branch HEAD. Must hold at 'closing' - the receipt is not the closing
    commit (W5H)."""
    repo, wt = _build_repo(tmp_path)
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green"}',
                               encoding="utf-8")
    _git(wt, "add", RCPT_REL)
    _git(wt, "commit", "-q", "-m", "receipt (not the closing commit yet)")
    (wt / "product2.txt").write_text("later work", encoding="utf-8")
    _git(wt, "add", "product2.txt")
    _git(wt, "commit", "-q", "-m", "later work after the receipt")
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "non-HEAD receipt read as %r" % state
    assert "is not the branch HEAD" in reason, reason


def test_receipt_head_but_no_release_holds_at_closing(tmp_path):
    """V3: the receipt IS the branch HEAD but no RELEASE line is on the bus.
    Must hold at 'closing' - S5 requires an explicit release at close."""
    repo, wt = _build_repo(tmp_path)
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green"}',
                               encoding="utf-8")
    _git(wt, "add", RCPT_REL)
    _git(wt, "commit", "-q", "-m", "receipt is the closing commit")
    assert _git(wt, "log", "-1", "--format=%H", "--", RCPT_REL) == _git(wt, "rev-parse", "HEAD")
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "no-release receipt read as %r" % state
    assert "no RELEASE line for W99-CLOSEGATE" in reason, reason


def test_clean_leg_passes_end_to_end_in_dry_run(tmp_path):
    """ACCEPTANCE 2: a clean leg - receipt committed as the branch HEAD AND an
    explicit RELEASE posted on the bus - passes the new gates end to end in
    -DryRun, reading 'done'."""
    repo, wt = _build_repo(tmp_path)
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green"}',
                               encoding="utf-8")
    _git(wt, "add", RCPT_REL)
    _git(wt, "commit", "-q", "-m", "receipt is the closing commit")
    # explicit RELEASE via the real bus.py (Python argv -> no shell quoting issue)
    buspy = str(repo / "harness" / "autorevise" / "bus.py")
    rel = subprocess.run(
        ["python", buspy, "post", "wave99", "W99-CLOSEGATE", "status",
         json.dumps({"release": ["harness/orchestrate.ps1"]})],
        capture_output=True, text=True)
    assert rel.returncode == 0, rel.stderr
    # bus.py must now agree the leg has released (exit 0)
    chk = subprocess.run(["python", buspy, "released", "wave99", "W99-CLOSEGATE"],
                         capture_output=True, text=True)
    assert chk.returncode == 0, "bus.py released did not see the release: %s" % chk.stdout
    state, reason = _leg_state(repo, LEG)
    assert state == "done", "clean leg read as %r (reason=%r)" % (state, reason)


def test_operator_harvested_main_tree_receipt_is_done(tmp_path):
    """R135 reconciliation: a receipt harvested by the operator into the MAIN
    tree (no receipt in the leg's worktree) must still green as legacy 'done' -
    the gate binds worktree receipts only and must NOT refuse R135's standing
    third-party-harvest answer. FAILS IF the gate over-reaches into main-tree
    receipts and holds a rescued leg at 'closing' forever."""
    repo, wt = _build_repo(tmp_path)
    # receipt lives ONLY in the main tree's receipts dir, not in wt/
    main_rcpt = repo / "harness" / "notes" / "receipts"
    main_rcpt.mkdir(parents=True, exist_ok=True)
    (main_rcpt / "W99-CLOSEGATE.json").write_text(
        '{"leg":"W99-CLOSEGATE","status":"green"}', encoding="utf-8")
    state, _ = _leg_state(repo, LEG)
    assert state == "done", "operator-harvested main-tree receipt read as %r" % state


def test_manifest_pinned_done_bypasses_gate(tmp_path):
    """The human escape valve: a leg pinned state:done in the manifest stays
    'done' regardless of commit/HEAD/RELEASE. FAILS IF the gate overrides a
    human word."""
    repo, wt = _build_repo(tmp_path)
    # a worktree receipt that would otherwise fail every gate condition - including
    # 1h's protected-path diff (VERSION committed on the branch)
    _commit_protected_touch(wt, "VERSION")
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE"}', encoding="utf-8")
    pinned = dict(LEG, state="done")
    state, _ = _leg_state(repo, pinned)
    assert state == "done", "manifest-pinned done was overridden to %r" % state


# ---- 1h: post-cycle protected-path diff (harness-review 2026-09-15, FENCE-4) ----

def _commit_protected_touch(wt, rel):
    """Commit a change to `rel` on the leg's branch, the way an agent that wrote
    around a form-matched deny rule would (Copy-Item, git commit -a, python -c)."""
    p = wt / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("9.9.9\n", encoding="utf-8")
    _git(wt, "add", rel)
    _git(wt, "commit", "-q", "-m", "agent wrote around the deny rule: %s" % rel)


def _close_cleanly(repo, wt):
    """Receipt committed as the branch HEAD AND an explicit RELEASE on the bus -
    every pre-1h close condition met. Whatever the gate says after this is 1h."""
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green"}',
                               encoding="utf-8")
    _git(wt, "add", RCPT_REL)
    _git(wt, "commit", "-q", "-m", "receipt is the closing commit")
    buspy = str(repo / "harness" / "autorevise" / "bus.py")
    rel = subprocess.run(
        ["python", buspy, "post", "wave99", "W99-CLOSEGATE", "status",
         json.dumps({"release": ["harness/orchestrate.ps1"]})],
        capture_output=True, text=True)
    assert rel.returncode == 0, rel.stderr


@pytest.mark.parametrize("rel", [
    "VERSION", "harness/state/done.json", "harness/verify/suite_baseline.json"])
def test_protected_path_touched_refuses_close(tmp_path, rel):
    """1h ACCEPTANCE (REPORT.md: 'A run whose worktree touches VERSION prints a
    loud PROTECTED-PATH line ... and refuses to close green'). Receipt is HEAD,
    RELEASE is posted, but `rel` changed between the recorded cycle base and
    HEAD -> the leg holds at 'closing' with a PROTECTED-PATH reason naming the
    path. FAILS IF the gate greens on receipt + release alone, i.e. the
    form-matched deny rule is still the only fence."""
    repo, wt = _build_repo(tmp_path)
    _commit_protected_touch(wt, rel)
    _close_cleanly(repo, wt)
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "protected touch of %s read as %r (reason=%r)" % (rel, state, reason)
    assert reason.startswith("PROTECTED-PATH"), reason
    assert rel in reason, reason


def test_unprotected_diff_still_closes(tmp_path):
    """Over-reach guard: a branch that changed ordinary files (python/, the
    receipt, product.txt) closes 'done'. The diff RUNS (the base is the empty
    commit, so all of those are in it) and finds nothing protected."""
    repo, wt = _build_repo(tmp_path)
    (wt / "python").mkdir()
    (wt / "python" / "x.py").write_text("print('ok')\n", encoding="utf-8")
    _git(wt, "add", "python/x.py")
    _git(wt, "commit", "-q", "-m", "ordinary product work")
    _close_cleanly(repo, wt)
    state, reason = _leg_state(repo, LEG)
    assert state == "done", "unprotected diff refused: %r (reason=%r)" % (state, reason)


def test_no_cycle_base_and_no_fork_point_refuses_close(tmp_path):
    """'Cannot prove untouched' is not 'untouched'. No recorded base, no
    resolvable fork point (the scratch repo has no master and the leg declares
    no base) -> the gate refuses with 'check impossible' rather than greening
    blind."""
    repo, wt = _build_repo(tmp_path)
    (wt / ".claude" / ".cycle_base").unlink()
    _close_cleanly(repo, wt)
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "baseless leg read as %r" % state
    assert "PROTECTED-PATH check impossible" in reason, reason


def test_legacy_worktree_falls_back_to_leg_base_fork_point(tmp_path):
    """A worktree cut before 1h has no .cycle_base. When the leg declares a base
    ref the gate diffs from merge-base(base, HEAD), so legacy in-flight legs are
    judged on their own commits, not refused wholesale. Both directions pinned:
    clean -> done, then VERSION on the branch -> closing."""
    repo, wt = _build_repo(tmp_path)
    (wt / ".claude" / ".cycle_base").unlink()
    _git(wt, "branch", "trunk", _git(wt, "rev-parse", "HEAD"))
    leg = dict(LEG, base="trunk")
    _close_cleanly(repo, wt)
    state, reason = _leg_state(repo, leg)
    assert state == "done", "legacy clean leg read as %r (reason=%r)" % (state, reason)
    _commit_protected_touch(wt, "VERSION")
    (wt / RCPT_REL).write_text('{"leg":"W99-CLOSEGATE","status":"green","n":2}',
                               encoding="utf-8")
    _git(wt, "add", RCPT_REL)
    _git(wt, "commit", "-q", "-m", "receipt is the closing commit again")
    state, reason = _leg_state(repo, leg)
    assert state == "closing" and "VERSION" in reason, (state, reason)


def test_operator_harvested_receipt_does_not_launder_protected_touch(tmp_path):
    """R135 greens the RECEIPT question for a main-tree harvest; it must not
    green a VERSION bump on the leg's branch. Worktree exists (with the touch),
    receipt lives only in the main tree -> 'closing' with PROTECTED-PATH."""
    repo, wt = _build_repo(tmp_path)
    _commit_protected_touch(wt, "VERSION")
    main_rcpt = repo / "harness" / "notes" / "receipts"
    main_rcpt.mkdir(parents=True, exist_ok=True)
    (main_rcpt / "W99-CLOSEGATE.json").write_text(
        '{"leg":"W99-CLOSEGATE","status":"green"}', encoding="utf-8")
    state, reason = _leg_state(repo, LEG)
    assert state == "closing", "harvested receipt laundered a VERSION touch: %r" % state
    assert reason.startswith("PROTECTED-PATH") and "VERSION" in reason, reason
