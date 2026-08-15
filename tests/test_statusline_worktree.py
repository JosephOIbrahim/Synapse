"""The bar reads .git as a directory. In a linked worktree it is a FILE
('gitdir: <path>'), whose HEAD is per-worktree and whose refs/packed-refs live
in a shared commondir. tests/test_statusline.py already covers this - but only
when it happens to be run from INSIDE a worktree; run from a normal checkout
(the CI case) those tests exercise the .git-directory path only and the
worktree regression can return unnoticed.

This file removes that dependency on where pytest is invoked. Each test builds
its own throwaway main repo AND a linked worktree off it, then drives the real
statusline functions against BOTH roots. It is the run-location-independent
proof of predicate #1: 'resolve ROOT/.git when it is a file so branch()/
head_sha()/packed-refs/worktrees enumeration work from inside a linked worktree.'

Every test states the condition under which it FAILS.
"""
import importlib
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name):
    sys.path.insert(0, os.path.join(ROOT, "harness"))
    try:
        return importlib.import_module(name)
    finally:
        sys.path.pop(0)


def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def _out(cwd, *a):
    r = _git(cwd, *a)
    assert r.returncode == 0, "git %s failed: %s" % (a, r.stderr.strip())
    return r.stdout.strip()


@pytest.fixture
def main_and_worktree(tmp_path):
    """A real main checkout (.git is a dir) + a real linked worktree (.git is a
    file). No skip path: git is a hard dependency of the suite this pins."""
    main = tmp_path / "main"
    main.mkdir()
    for a in (("init", "-q"),
              ("config", "user.email", "statwt@example.com"),
              ("config", "user.name", "statwt"),
              ("config", "commit.gpgsign", "false")):
        r = _git(main, *a)
        assert r.returncode == 0, "git %s failed: %s" % (a, r.stderr.strip())
    (main / "f.txt").write_text("x", encoding="utf-8")
    assert _git(main, "add", "f.txt").returncode == 0
    assert _git(main, "commit", "-q", "-m", "init").returncode == 0
    wt = tmp_path / "wt"
    r = _git(main, "worktree", "add", "-q", str(wt), "-b", "feature")
    assert r.returncode == 0, "worktree add failed: %s" % r.stderr.strip()
    return main, wt


def test_fixture_reproduces_the_precondition(main_and_worktree):
    """FAILS IF: the fixture is not actually reproducing the bug's precondition -
    a main .git directory and a worktree .git *file* holding 'gitdir:'."""
    main, wt = main_and_worktree
    assert (main / ".git").is_dir(), "main .git should be a directory"
    assert (wt / ".git").is_file(), "worktree .git should be a file"
    assert (wt / ".git").read_text(encoding="utf-8").startswith("gitdir:")


def test_gitdirs_splits_gitdir_from_commondir(main_and_worktree, monkeypatch):
    """FAILS IF: the resolver does not split per-worktree gitdir from the shared
    commondir. In a normal checkout the two are equal; in a linked worktree the
    gitdir holds HEAD and the commondir holds refs - conflating them reintroduces
    the bug for either branch() or the registry."""
    main, wt = main_and_worktree
    s = _mod("statusline")

    monkeypatch.setattr(s, "ROOT", str(main))
    g, c = s._gitdirs()
    assert s._norm(g) == s._norm(c) == s._norm(main / ".git")

    monkeypatch.setattr(s, "ROOT", str(wt))
    g, c = s._gitdirs()
    assert s._norm(g) != s._norm(c), "gitdir and commondir must differ in a worktree"
    assert s._norm(c) == s._norm(main / ".git"), "commondir must be the shared .git"
    assert os.path.isfile(os.path.join(g, "HEAD")), "gitdir must hold this worktree's HEAD"


def test_branch_resolves_from_either_root(main_and_worktree, monkeypatch):
    """FAILS IF: branch() cannot read a per-worktree HEAD behind a .git file."""
    main, wt = main_and_worktree
    s = _mod("statusline")
    main_branch = _out(main, "rev-parse", "--abbrev-ref", "HEAD")

    monkeypatch.setattr(s, "ROOT", str(main))
    assert s.branch() == main_branch, "main branch misread"

    monkeypatch.setattr(s, "ROOT", str(wt))
    assert s.branch() == "feature", "worktree branch misread behind a .git file"


def test_head_sha_resolves_from_either_root(main_and_worktree, monkeypatch):
    """FAILS IF: head_sha() cannot follow HEAD->refs/heads across the split.

    HEAD lives in the per-worktree gitdir; refs/heads lives in the shared
    commondir. Reading both from one directory returns '' for the worktree."""
    main, wt = main_and_worktree
    s = _mod("statusline")

    monkeypatch.setattr(s, "ROOT", str(main))
    assert s.head_sha() == _out(main, "rev-parse", "HEAD"), "main HEAD misread"

    monkeypatch.setattr(s, "ROOT", str(wt))
    assert s.head_sha() == _out(wt, "rev-parse", "HEAD"), "worktree HEAD misread"


def test_head_sha_reads_packed_refs_from_commondir(main_and_worktree, monkeypatch):
    """FAILS IF: after packing refs, the worktree cannot resolve HEAD.

    The loose ref goes away on `git pack-refs`; the sha then lives only in the
    shared commondir's packed-refs. A worktree read that looks in the gitdir -
    or fails to fall through to packed-refs - returns '' here."""
    main, wt = main_and_worktree
    assert _git(main, "pack-refs", "--all").returncode == 0
    s = _mod("statusline")

    monkeypatch.setattr(s, "ROOT", str(wt))
    assert s.head_sha() == _out(wt, "rev-parse", "HEAD"), \
        "worktree HEAD misread from packed-refs in commondir"


def test_registry_enumerates_all_worktrees_from_either_root(main_and_worktree, monkeypatch):
    """FAILS IF: the worktree enumeration misses the main tree or a sibling.

    git's porcelain lists {main, worktree}. Seeding the set from ROOT drops the
    main tree when this runs from inside the worktree; seeding from the wrong
    directory drops the linked worktrees. Both roots must agree with git."""
    main, wt = main_and_worktree
    s = _mod("statusline")
    expected = {s._norm(ln[len("worktree "):])
                for ln in _out(main, "worktree", "list", "--porcelain").splitlines()
                if ln.startswith("worktree ")}
    assert len(expected) == 2, "fixture should have exactly main + one worktree"

    monkeypatch.setattr(s, "ROOT", str(main))
    assert s.registered_paths() == expected, "registry wrong from the main checkout"

    monkeypatch.setattr(s, "ROOT", str(wt))
    assert s.registered_paths() == expected, "registry wrong from the linked worktree"
