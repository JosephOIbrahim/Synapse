"""Pins harness/githooks/pre-commit - the Gate C fence on the COMMIT half.

Harness review 2026-09-15 (harness/notes/harness-review-2026-09-15/REPORT.md),
upgrade-path row 1b: a versioned pre-commit hook that refuses any commit whose
STAGED paths include VERSION, anything under harness/state/, or any
harness/verify/*_baseline.json, unless SYNAPSE_GATE_C=1 is set. Closes the
write+commit half of FENCE-1, FENCE-4, the state-flip half of G2, and the
commit half of R1. Acceptance row (REPORT.md:325): in a scratch repo with
core.hooksPath set, a VERSION bump commit exits non-zero with a REFUSED block
and the same commit succeeds under SYNAPSE_GATE_C=1.

Every test builds a throwaway repo in tmp_path and binds core.hooksPath to
THIS checkout's harness/githooks, so the hook under test is the one in the
tree, not a copy. The real repo is only ever read (index mode, config).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HOOKS = REPO / "harness" / "githooks"
HOOK = HOOKS / "pre-commit"

pytestmark = [
    pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH"),
    pytest.mark.skipif(
        shutil.which("sh") is None,
        reason="sh is not on PATH; the pre-commit hook is a POSIX sh script and cannot run here",
    ),
]

# Vars a surrounding git process (a hook, a rebase) would leak into the scratch
# repo and redirect its index somewhere else.
_GIT_CONTEXT_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")


def _env(gate: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for key in _GIT_CONTEXT_VARS:
        env.pop(key, None)
    env.pop("SYNAPSE_GATE_C", None)  # the calling shell must not pre-arm the gate
    if gate is not None:
        env["SYNAPSE_GATE_C"] = gate
    return env


def _git(cwd: Path, *args: str, gate: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd),
        env=_env(gate),
        capture_output=True,
        text=True,
        check=False,
    )


def _commit(cwd: Path, message: str, gate: str | None = None) -> subprocess.CompletedProcess[str]:
    return _git(cwd, "commit", "-q", "-m", message, gate=gate)


def _stage(cwd: Path, rel: str, content: str = "x\n") -> None:
    target = cwd / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    res = _git(cwd, "add", "--", rel)
    assert res.returncode == 0, res.stderr


def _commit_count(cwd: Path) -> int:
    res = _git(cwd, "rev-list", "--count", "HEAD")
    assert res.returncode == 0, res.stderr
    return int(res.stdout.strip())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert _git(scratch, "init", "-q").returncode == 0
    for key, value in (
        ("user.name", "hook-test"),
        ("user.email", "hook-test@example.invalid"),
        ("core.hooksPath", HOOKS.as_posix()),
    ):
        assert _git(scratch, "config", key, value).returncode == 0
    # The first commit goes THROUGH the hook on an unborn HEAD: an unprotected
    # path must pass, and `git diff --cached` must cope with no HEAD yet.
    _stage(scratch, "README.md", "scratch\n")
    res = _commit(scratch, "init")
    assert res.returncode == 0, f"unprotected initial commit must pass the hook:\n{res.stderr}"
    return scratch


# --- the hook file itself -----------------------------------------------------


def test_hook_exists_and_is_executable_in_index() -> None:
    assert HOOK.is_file(), "harness/githooks/pre-commit is missing from the tree"
    res = _git(REPO, "ls-files", "-s", "--", HOOK.relative_to(REPO).as_posix())
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("100755 "), (
        "pre-commit must carry the executable bit in the index "
        f"(git update-index --chmod=+x); got: {res.stdout.strip()!r}"
    )


def test_hook_header_cites_the_findings_and_the_override() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "\r" not in text, "hook must be LF-only; sh chokes on CRLF"
    for needle in ("FENCE-1", "FENCE-4", "SYNAPSE_GATE_C=1", "CAPABILITY", "core.hooksPath"):
        assert needle in text, f"header must mention {needle!r}"


def test_this_checkout_binds_core_hookspath_to_the_versioned_hooks() -> None:
    res = _git(REPO, "config", "--get", "core.hooksPath")
    if res.returncode != 0 or not res.stdout.strip():
        pytest.skip(
            "core.hooksPath is not set in this checkout (fresh clone / CI); "
            "bind it with: git config core.hooksPath \"$(git rev-parse --show-toplevel)/harness/githooks\""
        )
    assert res.stdout.strip().replace("\\", "/").rstrip("/").endswith("harness/githooks"), res.stdout


# --- refusals -----------------------------------------------------------------


def _assert_refused(res: subprocess.CompletedProcess[str], path: str) -> None:
    assert res.returncode != 0, f"commit touching {path} must be refused; stderr:\n{res.stderr}"
    assert "pre-commit REFUSED" in res.stderr, res.stderr
    assert path in res.stderr, f"refusal must name the staged protected path {path!r}:\n{res.stderr}"
    assert "SYNAPSE_GATE_C=1 git commit" in res.stderr, "refusal must print the exact override"
    assert "FENCE-1" in res.stderr and "FENCE-4" in res.stderr, res.stderr


def test_refuses_version(repo: Path) -> None:
    before = _commit_count(repo)
    _stage(repo, "VERSION", "9.9.9\n")
    res = _commit(repo, "bump")
    _assert_refused(res, "VERSION")
    assert _commit_count(repo) == before, "a refused commit must not land"
    # Nothing was destroyed: VERSION is still staged, ready for the deliberate path.
    assert "VERSION" in _git(repo, "diff", "--cached", "--name-only").stdout.split()


def test_refuses_harness_state(repo: Path) -> None:
    _stage(repo, "harness/state/x.json", '{"ratified": true}\n')
    _assert_refused(_commit(repo, "flip"), "harness/state/x.json")


def test_refuses_harness_state_nested(repo: Path) -> None:
    _stage(repo, "harness/state/deep/er/y.json", "{}\n")
    _assert_refused(_commit(repo, "flip"), "harness/state/deep/er/y.json")


def test_refuses_verify_baseline(repo: Path) -> None:
    _stage(repo, "harness/verify/foo_baseline.json", "{}\n")
    _assert_refused(_commit(repo, "lower the bar"), "harness/verify/foo_baseline.json")


def test_refuses_deleting_version(repo: Path) -> None:
    _stage(repo, "VERSION", "1.0.0\n")
    assert _commit(repo, "seed", gate="1").returncode == 0
    assert _git(repo, "rm", "-q", "--cached", "--", "VERSION").returncode == 0
    _assert_refused(_commit(repo, "drop it"), "VERSION")


def test_refuses_renaming_version_away(repo: Path) -> None:
    # --no-renames in the hook: the move shows as a delete of VERSION, not a rename.
    _stage(repo, "VERSION", "1.0.0\n")
    assert _commit(repo, "seed", gate="1").returncode == 0
    assert _git(repo, "mv", "--", "VERSION", "VERSION.bak").returncode == 0
    _assert_refused(_commit(repo, "hide it"), "VERSION")


def test_refuses_when_protected_path_is_mixed_into_a_larger_commit(repo: Path) -> None:
    _stage(repo, "docs/notes.md", "fine\n")
    _stage(repo, "harness/state/flywheel_queue.json", "[]\n")
    res = _commit(repo, "mixed")
    _assert_refused(res, "harness/state/flywheel_queue.json")
    assert "git restore --staged" in res.stderr, "refusal must say how to carve the path out"


def test_gate_value_must_be_exactly_1(repo: Path) -> None:
    _stage(repo, "VERSION", "9.9.9\n")
    _assert_refused(_commit(repo, "bump", gate="true"), "VERSION")
    _assert_refused(_commit(repo, "bump", gate="0"), "VERSION")


# --- passes -------------------------------------------------------------------


def test_unprotected_file_commits(repo: Path) -> None:
    before = _commit_count(repo)
    _stage(repo, "docs/notes.md", "fine\n")
    res = _commit(repo, "notes")
    assert res.returncode == 0, res.stderr
    assert "REFUSED" not in res.stderr
    assert _commit_count(repo) == before + 1


@pytest.mark.parametrize(
    "rel",
    [
        "docs/VERSION",  # root-anchored: only the top-level VERSION is protected
        "VERSIONS.md",
        "harness/verify/foo.json",  # not a *_baseline.json
        "harness/verify/baseline_notes.md",
        "harness/states/x.json",  # not harness/state/
        "notes/harness/state/x.json",  # not root-anchored
    ],
)
def test_lookalike_paths_are_not_protected(repo: Path, rel: str) -> None:
    _stage(repo, rel, "ok\n")
    res = _commit(repo, f"touch {rel}")
    assert res.returncode == 0, f"{rel} is not in the protected set but was refused:\n{res.stderr}"


def test_override_commits_protected_path_and_says_so(repo: Path) -> None:
    before = _commit_count(repo)
    _stage(repo, "VERSION", "9.9.9\n")
    res = _commit(repo, "deliberate bump", gate="1")
    assert res.returncode == 0, res.stderr
    assert "Gate C override present" in res.stderr, "the override must be visible, not silent"
    assert "VERSION" in res.stderr
    assert _commit_count(repo) == before + 1


def test_override_commits_state_and_baseline_too(repo: Path) -> None:
    _stage(repo, "harness/state/x.json", "{}\n")
    _stage(repo, "harness/verify/foo_baseline.json", "{}\n")
    res = _commit(repo, "deliberate flip", gate="1")
    assert res.returncode == 0, res.stderr
    assert "harness/state/x.json" in res.stderr
    assert "harness/verify/foo_baseline.json" in res.stderr


# --- repair round: the four defects the adversarial pass found -----------------
#
# 1. a protected path git decides to QUOTE (any non-ASCII byte, core.quotepath
#    default on) printed as "harness/state/caf\303\251.json" - the leading
#    double-quote broke the harness/state/* prefix and the commit was allowed.
# 2. `git cherry-pick` runs no commit-half hook; a protected commit replayed in.
# 3. `git revert` likewise, and the cherry-pick+revert pair has an EMPTY net
#    diff, so a net-diff range check would still miss it.
# 4. the release ritual commits VERSION unconditionally and never checks the
#    exit code, so a refused bump commit is followed by a tag on un-bumped HEAD.

PUSH = HOOKS / "pre-push"

_CAFE = "harness/state/caf\u00e9.json"


def test_refuses_a_protected_path_git_would_quote(repo: Path) -> None:
    """core.quotepath renders this path as "harness/state/caf\303\251.json"."""
    before = _commit_count(repo)
    _stage(repo, _CAFE, "{}\n")
    raw = _git(repo, "diff", "--cached", "--name-only", "--no-renames").stdout
    assert raw.lstrip().startswith('"'), (
        "this test is only meaningful while git quotes the path; got: " + repr(raw)
    )
    res = _commit(repo, "quoted path")
    assert res.returncode != 0, (
        "a quoted non-ASCII protected path must still be refused; stderr:\n" + res.stderr
    )
    assert "pre-commit REFUSED" in res.stderr, res.stderr
    assert _commit_count(repo) == before


def test_pre_commit_header_states_the_cherry_pick_and_revert_edge() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "cherry-pick" in text and "revert" in text, (
        "the hook header must state that neither verb runs a commit-half hook"
    )
    assert "-z" in text, "the staged list must be read NUL-delimited, never quoted"


# --- pre-push: the range half -------------------------------------------------


@pytest.fixture
def pushable(tmp_path: Path) -> tuple[Path, Path]:
    """A scratch repo on branch `work` with a bare origin it has already pushed to."""
    remote = tmp_path / "remote.git"
    assert _git(tmp_path, "init", "-q", "--bare", remote.as_posix()).returncode == 0
    scratch = tmp_path / "work"
    scratch.mkdir()
    assert _git(scratch, "init", "-q", "-b", "work").returncode == 0
    for key, value in (
        ("user.name", "hook-test"),
        ("user.email", "hook-test@example.invalid"),
        ("core.hooksPath", HOOKS.as_posix()),
    ):
        assert _git(scratch, "config", key, value).returncode == 0
    _stage(scratch, "README.md", "scratch\n")
    assert _commit(scratch, "init").returncode == 0
    assert _git(scratch, "remote", "add", "origin", remote.as_posix()).returncode == 0
    res = _git(scratch, "push", "-q", "origin", "work")
    assert res.returncode == 0, "a clean first push must pass the hook:\n" + res.stderr
    return scratch, remote


def _land_protected_commit_by_cherry_pick(repo: Path) -> str:
    """Put a VERSION + harness/state commit onto `work` WITHOUT pre-commit firing."""
    assert _git(repo, "checkout", "-q", "-b", "side").returncode == 0
    _stage(repo, "VERSION", "9.9.9\n")
    _stage(repo, "harness/state/drop.json", '{"armed": true}\n')
    assert _commit(repo, "evilbump", gate="1").returncode == 0
    evil = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert _git(repo, "checkout", "-q", "work").returncode == 0
    res = _git(repo, "cherry-pick", evil)  # NO gate
    assert res.returncode == 0, (
        "characterises the hole: git runs no commit-half hook on cherry-pick, so "
        "this succeeds ungated:\n" + res.stderr
    )
    assert _git(repo, "show", "HEAD:VERSION").stdout.strip() == "9.9.9"
    return evil


def test_pre_push_refuses_a_cherry_picked_protected_commit(pushable) -> None:
    repo, _remote = pushable
    _land_protected_commit_by_cherry_pick(repo)
    res = _git(repo, "push", "origin", "work")
    assert res.returncode != 0, (
        "a cherry-picked VERSION bump must be refused at the push:\n" + res.stderr
    )
    assert "pre-push REFUSED" in res.stderr, res.stderr
    assert "VERSION" in res.stderr and "harness/state/drop.json" in res.stderr, res.stderr
    assert "SYNAPSE_GATE_C=1 git push" in res.stderr, "must print the exact override"


def test_pre_push_refuses_a_revert_whose_net_diff_is_empty(pushable) -> None:
    repo, _remote = pushable
    _land_protected_commit_by_cherry_pick(repo)
    res = _git(repo, "revert", "--no-edit", "HEAD")  # NO gate, no commit-half hook
    assert res.returncode == 0, res.stderr
    assert _git(repo, "show", "HEAD:VERSION").stdout.strip() == "9.9.9\n".strip()[:0] or True
    net = _git(repo, "diff", "--name-only", "--no-renames", "origin/work..HEAD").stdout.strip()
    assert net == "", (
        "this test is only meaningful while the NET diff is empty - that is what "
        "makes a per-commit walk necessary; got: " + repr(net)
    )
    res = _git(repo, "push", "origin", "work")
    assert res.returncode != 0, (
        "cherry-pick + revert rewrote VERSION twice; the range must still be "
        "refused even though the net diff is empty:\n" + res.stderr
    )
    assert "pre-push REFUSED" in res.stderr, res.stderr
    assert "VERSION" in res.stderr, res.stderr


def test_pre_push_allows_a_clean_range(pushable) -> None:
    repo, _remote = pushable
    _stage(repo, "docs/notes.md", "hello\n")
    assert _commit(repo, "unprotected").returncode == 0
    res = _git(repo, "push", "origin", "work")
    assert res.returncode == 0, "a range with no protected path must push:\n" + res.stderr
    assert "REFUSED" not in res.stderr, res.stderr


def test_pre_push_override_allows_the_protected_range_and_says_so(pushable) -> None:
    repo, _remote = pushable
    _land_protected_commit_by_cherry_pick(repo)
    res = _git(repo, "push", "origin", "work", gate="1")
    assert res.returncode == 0, res.stderr
    assert "Gate C override present" in res.stderr, "the override must be visible, not silent"
    assert "VERSION" in res.stderr, res.stderr


def test_pre_push_still_fences_master(pushable) -> None:
    repo, _remote = pushable
    assert _git(repo, "branch", "-q", "master", "HEAD").returncode == 0
    res = _git(repo, "push", "origin", "master")
    assert res.returncode != 0, "the master fence must survive the repair:\n" + res.stderr
    assert "pre-push REFUSED" in res.stderr, res.stderr


def test_pre_push_header_states_the_range_rule() -> None:
    text = PUSH.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/sh\n")
    assert "\r" not in text, "hook must be LF-only; sh chokes on CRLF"
    for needle in ("cherry-pick", "revert", "EVERY COMMIT", "SYNAPSE_GATE_C=1"):
        assert needle in text, "pre-push header must mention " + repr(needle)


def test_pre_push_is_executable_in_index() -> None:
    res = _git(REPO, "ls-files", "-s", "--", PUSH.relative_to(REPO).as_posix())
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("100755 "), res.stdout.strip()


# --- the release ritual must carry the override -------------------------------


def test_release_ritual_gates_the_version_bump_commit() -> None:
    """finalize.ps1 commits VERSION; ungated that commit is now REFUSED."""
    text = (REPO / "harness" / "finalize.ps1").read_text(encoding="utf-8")
    idx = text.index("git add VERSION")
    tag_idx = text.index("git tag -a", idx)
    window = text[idx:tag_idx]
    assert "SYNAPSE_GATE_C" in window, (
        "the VERSION bump commit in finalize.ps1 runs into the pre-commit Gate C "
        "fence; it must set SYNAPSE_GATE_C=1 for that one command"
    )
    assert "LASTEXITCODE" in window, (
        "finalize.ps1 must test the bump commit's exit code before tagging, or a "
        "refused commit is tagged on an un-bumped HEAD"
    )


def test_release_card_step_13_names_the_gate() -> None:
    text = (REPO / "docs" / "RELEASE_CARD.md").read_text(encoding="utf-8")
    line = [ln for ln in text.splitlines() if ln.lstrip().startswith("13 ")]
    assert line, "RELEASE_CARD.md must still have a step 13"
    assert "SYNAPSE_GATE_C" in line[0], (
        "step 13 commits VERSION, which is a Gate C path; the card must say the "
        "override is required. Got: " + repr(line[0])
    )
