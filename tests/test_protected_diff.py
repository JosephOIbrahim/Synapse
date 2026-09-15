"""Acceptance: harness/protected_diff.py answers "what did this cycle change?"
with git, not with a file the agent can edit - and answers it for the whole
worktree surface, not just committed history.

Each test below is one of the four bypasses the 1h repair round closed. Every one
of them was GREEN (exit 0, gate passes) against the first cut's pipeline,
    git diff --name-only $(cat .claude/.cycle_base)..HEAD | protected_paths.py --check -
which is replayed here as `_old_pipeline` beside the real check, so the test
fails loud if a future edit quietly regresses to it.

  1. base tampering  - `git rev-parse HEAD > .claude/.cycle_base` empties the diff
  2. rename          - `--name-only` reports only a rename's destination
  3. uncommitted     - `Copy-Item x VERSION` never reaches committed history
  4. staged          - the same, `git add`ed but not committed

Plus the two honest boundaries: an unresolvable base is a refusal (exit 2, never
exit 0), and a gitignored path is out of scope by construction - stated in the
module docstring rather than implied away.
"""
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PP_PY = os.path.join(ROOT, "harness", "protected_paths.py")
PD_PY = os.path.join(ROOT, "harness", "protected_diff.py")


def _git(wt, *args, check=True):
    r = subprocess.run(["git", "-C", str(wt), *args], capture_output=True, text=True)
    if check:
        assert r.returncode == 0, "git %s failed:\n%s\n%s" % (args, r.stdout, r.stderr)
    return r.stdout.strip()


def _check(wt, ref="master"):
    """The real check. Returns (exit code, hit paths)."""
    r = subprocess.run(
        ["python", PD_PY, "--worktree", str(wt), "--ref", ref],
        capture_output=True, text=True)
    return r.returncode, [s.strip() for s in r.stdout.splitlines() if s.strip()]


def _old_pipeline(wt):
    """The first cut of 1h, replayed verbatim: committed-only diff from whatever
    the marker file currently says. Kept so a regression to it fails here."""
    base = (wt / ".claude" / ".cycle_base").read_text(encoding="utf-8").strip()
    d = subprocess.run(["git", "-C", str(wt), "diff", "--name-only", "%s..HEAD" % base],
                       capture_output=True, text=True)
    r = subprocess.run(["python", PP_PY, "--check", "-"],
                       input=d.stdout, capture_output=True, text=True)
    return r.returncode


@pytest.fixture()
def wt(tmp_path):
    """A worktree-shaped scratch repo: `master` is the fork point, `leg` is the
    cycle's branch, and .claude/.cycle_base records the fork the way Start-Leg
    and ensureWorktree do."""
    w = tmp_path / "wt"
    w.mkdir()
    _git(w, "init", "-q", "-b", "master", ".")
    _git(w, "config", "user.email", "probe@synapse.local")
    _git(w, "config", "user.name", "protected diff test")
    (w / "VERSION").write_text("5.70.1\n", encoding="utf-8")
    (w / "harness" / "state").mkdir(parents=True)
    (w / "harness" / "state" / "leg0_baselines.json").write_text("{}\n", encoding="utf-8")
    _git(w, "add", "-A")
    _git(w, "commit", "-q", "-m", "fork point")
    (w / ".claude").mkdir()
    (w / ".claude" / ".cycle_base").write_text(_git(w, "rev-parse", "HEAD") + "\n",
                                               encoding="utf-8")
    _git(w, "checkout", "-q", "-b", "leg")
    return w


def test_clean_cycle_passes(wt):
    """Over-reach guard: ordinary product work, committed and uncommitted, is
    not a hit. A fence that refuses everything fences nothing."""
    (wt / "product.txt").write_text("work\n", encoding="utf-8")
    _git(wt, "add", "product.txt")
    _git(wt, "commit", "-q", "-m", "ordinary work")
    (wt / "scratch.txt").write_text("uncommitted ordinary work\n", encoding="utf-8")
    assert _check(wt) == (0, [])


def test_rewritten_cycle_base_cannot_hide_a_bump(wt):
    """BYPASS 1. The agent bumps VERSION, then points .claude/.cycle_base at its
    own HEAD - an untracked, gitignored file inside its own writable worktree.
    The old pipeline reads that as an empty diff (exit 0). The check must fall
    back to merge-base(master, HEAD) and still report VERSION."""
    (wt / "VERSION").write_text("5.99.0\n", encoding="utf-8")
    _git(wt, "add", "VERSION")
    _git(wt, "commit", "-q", "-m", "bump")
    (wt / ".claude" / ".cycle_base").write_text(_git(wt, "rev-parse", "HEAD") + "\n",
                                                encoding="utf-8")
    assert _old_pipeline(wt) == 0, "the replayed old pipeline should show the bypass"
    assert _check(wt) == (1, ["VERSION"])


def test_backdated_cycle_base_is_still_honoured(wt):
    """The other direction is NOT tampering: a marker pointing further back only
    widens the diff, so it is used as-is and a clean cycle stays clean."""
    root = _git(wt, "rev-list", "--max-parents=0", "HEAD")
    (wt / ".claude" / ".cycle_base").write_text(root + "\n", encoding="utf-8")
    (wt / "product.txt").write_text("work\n", encoding="utf-8")
    _git(wt, "add", "product.txt")
    _git(wt, "commit", "-q", "-m", "ordinary work")
    assert _check(wt) == (0, [])


def test_renaming_a_protected_file_away_is_a_hit(wt):
    """BYPASS 2. `git mv VERSION VERSION.bak` - `--name-only` reports only the
    destination, so the old pipeline read the move as clean. `--no-renames`
    reports it as a delete of VERSION plus an add of VERSION.bak."""
    _git(wt, "mv", "VERSION", "VERSION.bak")
    _git(wt, "commit", "-q", "-m", "moved it out of the way")
    assert _old_pipeline(wt) == 0, "the replayed old pipeline should show the bypass"
    assert _check(wt) == (1, ["VERSION"])


def test_uncommitted_touch_is_a_hit(wt):
    """BYPASS 3. REPORT.md row 1h says "a run whose worktree TOUCHES VERSION".
    `Copy-Item x VERSION` writes the file and commits nothing."""
    (wt / "VERSION").write_text("5.99.0\n", encoding="utf-8")
    assert _old_pipeline(wt) == 0, "the replayed old pipeline should show the bypass"
    assert _check(wt) == (1, ["VERSION"])


def test_staged_touch_is_a_hit(wt):
    """BYPASS 4. Staged but not committed - still a touch."""
    (wt / "harness" / "verify").mkdir(parents=True, exist_ok=True)
    (wt / "harness" / "verify" / "suite_baseline.json").write_text(
        '{"passed": 1}\n', encoding="utf-8")
    _git(wt, "add", "harness/verify/suite_baseline.json")
    assert _old_pipeline(wt) == 0, "the replayed old pipeline should show the bypass"
    assert _check(wt) == (1, ["harness/verify/suite_baseline.json"])


def test_untracked_state_file_is_a_hit(wt):
    """A brand-new, never-added harness/state/** file is the "grade my own
    homework" move; untracked-but-not-ignored is inside the fence."""
    (wt / "harness" / "state" / "pwn.json").write_text('{"owned": true}\n',
                                                       encoding="utf-8")
    assert _check(wt) == (1, ["harness/state/pwn.json"])


def test_gitignored_path_is_out_of_scope_and_says_so(wt):
    """SCOPE, pinned rather than implied. A .gitignore'd path is invisible to
    every git question this module asks, so the gitignored members of
    harness/state/** (drop.json, posture.json, the readiness verdicts) are NOT
    fenced here. That boundary is written into the module docstring; this test
    fails if the docstring stops saying so, so the gap can never go quiet."""
    (wt / ".gitignore").write_text("harness/state/drop.json\n", encoding="utf-8")
    _git(wt, "add", ".gitignore")
    _git(wt, "commit", "-q", "-m", "ignore runtime state")
    (wt / "harness" / "state" / "drop.json").write_text('{"drop": true}\n',
                                                        encoding="utf-8")
    assert _check(wt) == (0, []), "an ignored path is invisible to git by construction"
    doc = open(PD_PY, encoding="utf-8").read()
    assert "OUT OF SCOPE" in doc and "gitignore" in doc.lower()


def test_no_base_and_no_fork_ref_refuses(wt):
    """"Cannot prove untouched" is not "untouched": no marker, no resolvable
    fork ref -> exit 2 (error), never exit 0."""
    (wt / ".claude" / ".cycle_base").unlink()
    _git(wt, "branch", "-D", "master")
    code, _ = _check(wt, ref="no-such-ref")
    assert code == 2, "a baseless check must refuse, not pass"


def test_hits_go_to_stdout_and_reasons_to_stderr(wt):
    """The consumers read STDOUT as the hit list. --explain must not pollute it."""
    (wt / "VERSION").write_text("5.99.0\n", encoding="utf-8")
    r = subprocess.run(["python", PD_PY, "--worktree", str(wt), "--ref", "master",
                        "--explain"], capture_output=True, text=True)
    assert r.returncode == 1
    assert [s.strip() for s in r.stdout.splitlines() if s.strip()] == ["VERSION"]
    assert "base" in r.stderr
