"""The root conftest must stamp every run with what it measured.

Why this file exists: two full-suite logs from 2026-11-12 could not prove which
commit or which interpreter produced them, and one was cited for a worktree it was
not produced from. The header is now the proof; these tests keep it honest.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("pytest")

_spec = importlib.util.spec_from_file_location("synapse_root_conftest", ROOT / "conftest.py")
conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conftest)


def test_identity_records_a_commit_or_says_unknown():
    ident = conftest.identity()
    assert isinstance(ident["commit"], str)
    assert ident["commit"] == "UNKNOWN" or len(ident["commit"]) == 40, ident["commit"]


def test_identity_records_the_running_interpreter():
    ident = conftest.identity()
    assert ident["interpreter"] == f"{sys.implementation.name} {sys.version.split()[0]}"


def test_identity_records_the_dependency_set_that_changed_results():
    deps = conftest.identity()["deps"]
    for name in ("numpy", "cv2", "mcp", "pxr"):
        assert name in deps, f"{name} is not probed; that absence is what made today's numbers incomparable"
        assert deps[name] in (True, False, None)


def test_the_header_line_carries_commit_interpreter_and_deps():
    line = conftest._line(conftest.identity())
    assert "commit" in line and "at" in line
    for name in ("numpy", "cv2"):
        assert name + "=" in line, f"the header does not report {name}: {line}"


def test_the_header_never_publishes_a_home_directory(monkeypatch):
    """A log may be attached to a release; the machine's identity must not ride along."""
    ident = conftest.identity()
    line = conftest._line(ident)
    assert str(Path.home()) not in line
    assert "\\Users\\" not in line and "/Users/" not in line


def test_identity_never_raises_when_git_is_unavailable(monkeypatch):
    monkeypatch.setattr(conftest, "_git", lambda *a: "")
    ident = conftest.identity()
    assert ident["commit"] == "UNKNOWN"
    assert ident["dirty"] is False


def test_the_hook_is_reachable_by_pytest():
    """The hooks must exist where pytest looks for them: the root conftest."""
    for hook in ("pytest_configure", "pytest_report_header", "pytest_terminal_summary"):
        assert callable(getattr(conftest, hook, None)), hook
    assert (ROOT / "conftest.py").exists()


def test_the_report_header_hook_emits_the_line(monkeypatch):
    """_line working is not the same as the hook running. Pin the wiring."""
    class _Cfg:
        pass
    cfg = _Cfg()
    conftest.pytest_configure(cfg)
    lines = conftest.pytest_report_header(cfg)
    assert lines, "the report header hook returned nothing"
    assert "commit" in lines[0] and "numpy=" in lines[0], lines[0]


# git's repository-local variables (`git rev-parse --local-env-vars`): the throwaway
# repository below must not be created inside whatever repository a leaked GIT_DIR names.
_REPO_LOCATION_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
    "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")


def test_identity_stamps_this_repository_whatever_the_working_directory(monkeypatch, tmp_path):
    """Review finding R5 (2026-11-13): the stamp ran git in the process cwd. Run from a
    temp folder it said UNKNOWN; run from inside another repository it stamped THAT
    repository's sha -- the mis-citation this hook exists to prevent. The other
    repository here has its own HEAD, so a cwd-relative stamp is a wrong answer, not
    merely an unknown one."""
    if shutil.which("git") is None:
        pytest.skip("git is not on PATH")
    here = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    if here.returncode != 0:
        pytest.skip("this checkout is not a git repository")
    dirty_here = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                                capture_output=True, text=True)

    other = tmp_path / "other"
    other.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in _REPO_LOCATION_VARS}
    for args in (["init", "-q"], ["config", "user.email", "other@test.invalid"],
                 ["config", "user.name", "other"], ["config", "commit.gpgsign", "false"],
                 ["commit", "-q", "--allow-empty", "-m", "another repository"]):
        p = subprocess.run(["git", *args], cwd=str(other), env=env, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
    monkeypatch.chdir(other)

    ident = conftest.identity()
    assert ident["commit"] == here.stdout.strip(), (
        "the stamp named the repository the process happened to be in")
    assert ident["dirty"] is bool(dirty_here.stdout.strip())
