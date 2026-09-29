"""Ruling R-D (BP11): test hygiene.

A test never clones a remote repository (the BP11-FIXFWD verifier did), never
leaves a tracked file changed, and never persists a regenerated baseline. The
session guard in ``tests/conftest.py`` catches the second and third; the scan
here catches the first. The guard's reads are checked on throwaway git
repositories in a temp folder, so nothing here touches this repository.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from r_d_guard import snapshot, touched_since

ROOT = Path(__file__).resolve().parents[1]
TEST_DIRS = (ROOT / "tests", ROOT / "harness" / "jev" / "tests")
_REMOTE = re.compile(r"(?:https?://|git@|ssh://)")


def test_no_test_clones_a_remote_repository():
    offenders = []
    for folder in TEST_DIRS:
        for path in sorted(folder.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                if "clone" in line and _REMOTE.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.name=r-d", "-c", "user.email=r-d@example.invalid", *args],
                   cwd=str(repo), check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository with this repository's line-ending policy."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    (tmp_path / "notice.md").write_bytes(b"line one\nline two\n")
    (tmp_path / "other.md").write_bytes(b"keep\n")
    _git(tmp_path, "add", ".gitattributes", "notice.md", "other.md")
    _git(tmp_path, "commit", "-q", "-m", "seed")
    return tmp_path


def test_a_clean_session_reports_nothing(repo):
    assert touched_since(snapshot(repo)) == []


def test_a_crlf_rewrite_of_a_tracked_file_is_caught(repo):
    snap = snapshot(repo)
    (repo / "notice.md").write_bytes(b"line one\r\nline two\r\n")
    assert touched_since(snap) == ["notice.md"]


def test_restoring_the_exact_bytes_is_not_reported(repo):
    snap = snapshot(repo)
    original = (repo / "notice.md").read_bytes()
    (repo / "notice.md").write_bytes(b"edited\n")
    (repo / "notice.md").write_bytes(original)
    assert touched_since(snap) == []


def test_putting_committed_bytes_over_a_developer_edit_is_caught(repo):
    (repo / "other.md").write_bytes(b"work in progress\n")
    snap = snapshot(repo)
    (repo / "other.md").write_bytes(b"keep\n")
    assert touched_since(snap) == ["other.md"]


def test_a_regenerated_file_is_caught(repo):
    snap = snapshot(repo)
    (repo / "other.md").write_bytes(b"keep\nregenerated baseline row\n")
    assert touched_since(snap) == ["other.md"]


def test_a_deleted_tracked_file_is_caught(repo):
    snap = snapshot(repo)
    (repo / "notice.md").unlink()
    assert touched_since(snap) == ["notice.md"]


def test_without_git_the_guard_stands_aside(tmp_path):
    bare = tmp_path / "not-a-repo"
    bare.mkdir()
    assert snapshot(bare) is None
    assert touched_since(None) == []
