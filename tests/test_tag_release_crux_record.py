"""tag_release.py must refuse a tag unless the crux review is closed.

2026-11-12 red-team finding: the v5.101.0 release was held by an owner ruling
that lived in a document nothing read. The gate held because a human
remembered it. These tests pin the control that replaces the memory -- a
committed CRUX-RECORD.json bound to the version and to the git history the
review covered.

Every test builds a throwaway repo in tmp_path; none touches the real tree.
"""
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "tag_release.py"
VER = "5.101.0"

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is required for the record bindings")


def _load():
    spec = importlib.util.spec_from_file_location("tag_release_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load()


# Fixed commit dates. The record's reviewed_date is a literal, so a fixture
# that commits at wall-clock time goes stale by itself once the clock passes
# that date -- the test would start failing for a reason that has nothing to do
# with the control (red-team finding, 2026-11-12).
_FIXED = {"GIT_AUTHOR_DATE": "2026-11-10T00:00:00+00:00",
          "GIT_COMMITTER_DATE": "2026-11-10T00:00:00+00:00"}

# The variables git itself names as repository-local (`git rev-parse
# --local-env-vars`). Any one of them overrides cwd: with GIT_DIR leaked into
# pytest, this fixture's init, config, add and commit -- and the tag tests --
# would act on whatever repository it names, which on this machine is the
# shared .git behind every worktree (review finding R4, 2026-11-13).
_REPO_LOCATION_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")


def _env():
    env = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATION_VARS}
    env.update(_FIXED)
    return env


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True, env=_env())


def _commit(repo, message):
    added = _git(repo, "add", "-A")
    assert added.returncode == 0, added.stderr
    done = _git(repo, "commit", "-q", "-m", message)
    assert done.returncode == 0, done.stderr
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A clean repo with a VERSION and a reviewed tip two commits deep."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q", "-b", "master").returncode == 0
    _git(repo, "config", "user.email", "crux@test.invalid")
    _git(repo, "config", "user.name", "crux test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "VERSION").write_text(VER + "\n", encoding="utf-8")
    base = _commit(repo, "base")
    (repo / "work.txt").write_text("the reviewed work\n", encoding="utf-8")
    tip = _commit(repo, "the reviewed work")
    return repo, base, tip


def _write_record(repo, *, version=VER, record_dir=None, commit=True,
                  path=None, text=None, omit=(), **overrides):
    """Write the crux record. Returns its path."""
    rec = {
        "version": version,
        "review": "NR-RECOVERY-RECEIPTS",
        "reviewer": "Codex",
        "reviewed_date": "2026-11-14",
        "verdict": "PASS",
        "passed": True,
        "commit_range": "",
    }
    rec.update(overrides)
    for key in omit:
        rec.pop(key, None)
    directory = repo / "harness" / "notes" / f"release-{record_dir or version}"
    directory.mkdir(parents=True, exist_ok=True)
    target = path or directory / "CRUX-RECORD.json"
    target.write_text(text if text is not None else json.dumps(rec, indent=2),
                      encoding="utf-8")
    if commit:
        _commit(repo, "crux record")
    return target


def _off_history_commit(repo, parent):
    """A commit that shares `parent` with HEAD but is on no branch."""
    tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    p = _git(repo, "commit-tree", tree, "-p", parent, "-m", "unreviewed")
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def test_absent_record_refuses(mod, repo):
    repo, base, tip = repo
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "no closure record" in problem
    assert "harness/notes/release-5.101.0/CRUX-RECORD.json" in problem
    assert "next act:" in problem


def test_version_mismatch_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, version="5.102.0", record_dir=VER,
                  commit_range=f"{base}..{tip}")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "5.102.0" in problem and VER in problem


def test_commit_not_in_tagged_history_refuses(mod, repo):
    repo, base, tip = repo
    stray = _off_history_commit(repo, base)
    _write_record(repo, commit_range=f"{base}..{stray}")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "stale" in problem
    assert stray[:7] in problem


def test_unresolvable_commit_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(
        repo,
        commit_range="0123456789abcdef0123456789abcdef01234567" + ".." + tip)
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "does not resolve" in problem


def test_review_predating_the_reviewed_code_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}",
                  reviewed_date="2001-01-01")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "predates" in problem


def test_range_written_backwards_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{tip}..{base}")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "does not run base -> tip" in problem


def test_valid_record_passes(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}")
    assert mod.crux_record_problem(VER, root=repo) is None


def test_non_passing_verdict_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}",
                  verdict="BROKEN", passed=False)
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "BROKEN" in problem


def test_uncommitted_record_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}", commit=False)
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "not in the commit being tagged" in problem


def test_malformed_json_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, text="{not json")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "is not JSON" in problem


def test_missing_field_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}", omit=("reviewer",))
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "reviewer" in problem


def test_bad_date_refuses(mod, repo):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}",
                  reviewed_date="14 Nov 2026")
    problem = mod.crux_record_problem(VER, root=repo)
    assert problem is not None
    assert "ISO date" in problem


def test_preflight_refuses_without_the_record(mod, repo, monkeypatch, capsys):
    repo, base, tip = repo
    monkeypatch.setattr(mod, "ROOT", repo)

    ok, tag = mod.preflight()

    out = capsys.readouterr().out
    assert ok is False
    assert tag == f"v{VER}"
    assert "crux_record" in out and "REFUSE" in out
    assert "harness/notes/release-5.101.0/CRUX-RECORD.json" in out
    assert "next act:" in out


def test_preflight_reads_a_valid_record_without_suppressing_other_checks(
        mod, repo, monkeypatch, capsys):
    repo, base, tip = repo
    _write_record(repo, commit_range=f"{base}..{tip}")
    monkeypatch.setattr(mod, "ROOT", repo)

    ok, _tag = mod.preflight()

    out = capsys.readouterr().out
    crux_line = [ln for ln in out.splitlines()
                 if ln.startswith("crux_record")]
    assert crux_line and "OK" in crux_line[0]
    assert "REFUSE" not in crux_line[0]
    # The record opens only its own check. sync_version.py is absent from
    # this throwaway repo, so the gate still refuses on that check alone.
    assert ok is False
    assert "sync_check" in out and "REFUSE" in out


def test_the_tag_is_refused_when_head_is_not_the_checked_commit(mod, repo):
    """The gate runs pytest before tagging; a commit landing in that window must
    refuse the tag, or it names a commit nobody tested."""
    r, base, tip = repo
    assert mod._tag_target_refusal(str(r), tip) is False, "same commit must tag"
    assert mod._tag_target_refusal(str(r), base) is True, "an older commit means HEAD moved"
    assert mod._tag_target_refusal(str(r), "") is True, "no sha must refuse"


# ---- the wiring, not just the helper -------------------------------------
# The first version of these tests pinned _tag_target_refusal's truth table and
# nothing else. Two mutants left the suite green: restoring `git tag -a <tag>`
# without the sha, and deleting the refusal call. Both are exercised below.

def test_the_tag_command_carries_the_checked_sha(mod, repo):
    """`git tag -a <tag>` with no commit re-resolves HEAD at tag time. The argv
    must name the sha explicitly, or the race the gate exists to stop is back."""
    r, base, tip = repo
    argv = mod._tag_argv(str(r), "v9.9.9", tip)
    assert tip in argv, f"the tag argv does not name the checked commit: {argv}"
    assert "-a" in argv and "v9.9.9" in argv, argv


def test_the_tag_names_the_checked_commit(mod, repo):
    r, base, tip = repo
    assert mod._create_tag(str(r), "v9.9.9", tip) is True
    out = _git(r, "rev-parse", "v9.9.9^{commit}").stdout.strip()
    assert out == tip, f"the tag names {out}, expected the checked {tip}"


def test_a_moved_head_refuses_and_creates_no_tag(mod, repo):
    """HEAD is at tip; the gate checked base. The tag must not be created."""
    r, base, tip = repo
    assert mod._create_tag(str(r), "v9.9.9", base) is False
    listed = _git(r, "tag", "--list").stdout.strip()
    assert listed == "", f"a tag was created anyway: {listed!r}"


def test_head_sha_is_empty_not_a_traceback_when_git_cannot_answer(mod, tmp_path):
    """The gate must refuse on UNKNOWN; it used to raise AttributeError."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert mod._head_sha(str(plain)) == ""


# ---- the entrypoint's result handling -------------------------------------
# _finish_tag drives the real _create_tag against the fixture's throwaway
# repository. No test invokes the script against SYNAPSE or creates a real tag.

def test_failed_tag_creation_refuses_without_post_tag_conformance(
        mod, repo, monkeypatch, capsys):
    r, base, tip = repo
    conformance = []
    monkeypatch.setattr(mod, "run_conformance",
                        lambda label: conformance.append(label) or True)

    # HEAD is tip, so asking to tag base makes the real _create_tag refuse.
    rc = mod._finish_tag(r, "v9.9.9", base)

    out = capsys.readouterr().out
    assert rc != 0
    assert conformance == [], "post-tag conformance ran although no tag was created"
    assert "REFUSE" in out
    assert "created      OK" not in out
    assert _git(r, "tag", "--list").stdout.strip() == ""


def test_successful_tag_creation_runs_post_tag_conformance_once(
        mod, repo, monkeypatch, capsys):
    r, _base, tip = repo
    conformance = []
    monkeypatch.setattr(mod, "run_conformance",
                        lambda label: conformance.append(label) or True)

    rc = mod._finish_tag(r, "v9.9.9", tip)

    out = capsys.readouterr().out
    assert rc == 0
    assert conformance == ["post"]
    assert "created      OK" in out
    assert "UNKNOWN/FAILED" not in out
    created = _git(r, "rev-parse", "v9.9.9^{commit}")
    assert created.returncode == 0, created.stderr
    assert created.stdout.strip() == tip


# ---- a leaked repository variable cannot redirect the gate -----------------
# Review finding R4 (2026-11-13). _run passed the whole environment to git, and
# git obeys GIT_DIR over `-C`. A hook or a test runner that leaked GIT_DIR would
# point every check -- and the tag itself -- at the repository it names. The
# decoy below is a second throwaway repo, never the real tree.

def _decoy(tmp_path):
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    assert _git(decoy, "init", "-q", "-b", "master").returncode == 0
    _git(decoy, "config", "user.email", "decoy@test.invalid")
    _git(decoy, "config", "user.name", "decoy")
    _git(decoy, "config", "commit.gpgsign", "false")
    (decoy / "decoy.txt").write_text("not the repository being tagged\n",
                                     encoding="utf-8")
    _commit(decoy, "decoy")
    return decoy


def test_a_leaked_git_dir_cannot_redirect_the_tag(mod, repo, tmp_path,
                                                  monkeypatch):
    r, _base, tip = repo
    decoy = _decoy(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))

    assert mod._head_sha(str(r)) == tip, "the gate read the decoy's HEAD"
    assert mod._create_tag(str(r), "v9.9.9", tip) is True

    created = _git(r, "rev-parse", "v9.9.9^{commit}")
    assert created.returncode == 0, "the tag did not land in the tagged repo"
    assert created.stdout.strip() == tip
    assert _git(decoy, "tag", "--list").stdout.strip() == "", (
        "the tag landed in the repository GIT_DIR named")


def test_a_leaked_git_dir_cannot_open_the_crux_gate_from_another_repo(
        mod, repo, tmp_path, monkeypatch):
    r, base, tip = repo
    _write_record(r, commit_range=f"{base}..{tip}")
    decoy = _decoy(tmp_path)
    monkeypatch.setenv("GIT_DIR", str(decoy / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(decoy))
    assert mod.crux_record_problem(VER, root=r) is None, (
        "the record was judged against the decoy's history")


def test_the_scrub_list_covers_what_this_git_calls_repository_local(
        mod, tmp_path):
    named = _git(tmp_path, "rev-parse", "--local-env-vars")
    assert named.returncode == 0, named.stderr
    missing = set(named.stdout.split()) - set(mod._GIT_LOCAL_ENV)
    assert not missing, (
        f"this git names repository-local variables the gate does not scrub: "
        f"{sorted(missing)}")
