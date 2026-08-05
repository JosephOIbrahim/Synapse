"""The rope's failure path must not be able to destroy work it never declared.

Regression test for the asymmetry between the runner's two exit paths. The
success path was already scoped, and its own comment said why -- "never `add
-A`: the LIVE Synapse session writes files while we run." The failure path then
called `git reset --hard HEAD`, reverting every tracked file in the repository.

Concretely: a concurrently running MONETA harness holding 545 uncommitted lines
was one failed rope task away from losing all of them, with no stash and no
reflog, because the work had never been committed.

This test FAILS against `git reset --hard HEAD` and passes against revert().
It builds a throwaway git repo in tmp_path; it never touches the real tree.
"""
import importlib.util
import os
import subprocess
import sys

import pytest

RUNNER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "harness", "rope", "runner.py",
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("_rope_runner", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    """A throwaway repo: one file the task declares, one innocent bystander."""
    d = tmp_path / "repo"
    d.mkdir()
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@t.t")
    _git(d, "config", "user.name", "t")
    (d / "declared.txt").write_text("original declared\n", encoding="utf-8")
    (d / "bystander.txt").write_text("original bystander\n", encoding="utf-8")
    _git(d, "add", "-A")
    _git(d, "commit", "-qm", "base")
    return d


def test_revert_restores_the_task_own_tracked_file(repo, monkeypatch):
    r = _load_runner()
    monkeypatch.setattr(r, "ROOT", str(repo))
    (repo / "declared.txt").write_text("agent edit\n", encoding="utf-8")

    r.revert({"files": ["declared.txt"]}, {"declared.txt": True})

    assert (repo / "declared.txt").read_text(encoding="utf-8") == "original declared\n"


def test_revert_leaves_undeclared_work_alone(repo, monkeypatch):
    """THE POINT. `git reset --hard HEAD` fails this; a scoped revert passes.

    bystander.txt stands in for python/synapse/memory/scene_memory.py -- a file
    a concurrent process is actively writing and that this task never named.
    """
    r = _load_runner()
    monkeypatch.setattr(r, "ROOT", str(repo))
    (repo / "declared.txt").write_text("agent edit\n", encoding="utf-8")
    (repo / "bystander.txt").write_text("545 lines of somebody else's work\n",
                                        encoding="utf-8")

    r.revert({"files": ["declared.txt"]}, {"declared.txt": True})

    assert (repo / "declared.txt").read_text(encoding="utf-8") == "original declared\n"
    assert (repo / "bystander.txt").read_text(encoding="utf-8") == (
        "545 lines of somebody else's work\n"
    ), "the failure path destroyed work the task never declared"


def test_revert_removes_only_files_this_attempt_created(repo, monkeypatch):
    r = _load_runner()
    monkeypatch.setattr(r, "ROOT", str(repo))
    (repo / "new_test.py").write_text("created by the attempt\n", encoding="utf-8")
    (repo / "preexisting.txt").write_text("was already here\n", encoding="utf-8")

    r.revert(
        {"files": ["new_test.py", "preexisting.txt"]},
        {"new_test.py": False, "preexisting.txt": True},
    )

    assert not (repo / "new_test.py").exists(), "created file should be removed"
    assert (repo / "preexisting.txt").exists(), (
        "an untracked file that predates the attempt is never ours to delete"
    )


def test_stray_edits_reports_what_scoped_revert_cannot_undo(repo, monkeypatch):
    """L2: it frays visibly. Leaving a stray edit is recoverable; destroying an
    unrelated process's work is not. Prefer the recoverable failure, then say so."""
    r = _load_runner()
    monkeypatch.setattr(r, "ROOT", str(repo))
    (repo / "bystander.txt").write_text("out of scope edit\n", encoding="utf-8")

    stray = r.stray_edits({"files": ["declared.txt"]})

    assert "bystander.txt" in stray
    assert "declared.txt" not in stray


def test_the_old_blunt_revert_really_did_destroy_it(repo):
    """Proof the tests above are a REGRESSION test and not merely a passing one.

    Runs what the failure path used to run -- `git reset --hard HEAD` -- against
    the identical fixture, and asserts it eats the bystander. Kept permanently:
    if anyone ever 'simplifies' revert() back to a whole-tree reset, the tests
    above go red and this one explains, in one place, exactly what was lost.
    """
    (repo / "declared.txt").write_text("agent edit\n", encoding="utf-8")
    (repo / "bystander.txt").write_text("545 lines of somebody else's work\n",
                                        encoding="utf-8")

    _git(repo, "reset", "--hard", "HEAD")          # the old failure path, verbatim

    assert (repo / "declared.txt").read_text(encoding="utf-8") == "original declared\n"
    assert (repo / "bystander.txt").read_text(encoding="utf-8") == "original bystander\n", (
        "if this ever stops holding, reset --hard changed semantics -- but as of "
        "the commit that added this test, the blunt revert destroyed undeclared work"
    )
