"""Ruling R-D (BP11): a test session must not leave a tracked file changed.

CRUX F7 found two tests that rewrote the vendored NOTICE.md in text mode and
left it with CRLF line endings on Windows after every run. ``tests/conftest.py``
takes a :func:`snapshot` before the first test and asks :func:`touched_since`
after the last; a tracked file a test left changed fails the run by name.

``git diff`` alone cannot see this: under ``core.autocrlf=true`` it compares
line-ending-normalised content, so a CRLF rewrite of an LF file reads as
unchanged. The snapshot therefore records every tracked file's size and
modification time (5,836 files stat in about 0.2 s), plus a hash of the bytes of
every file git already lists as changed. After the session, a file whose stat
moved is compared byte for byte: with its hash from before when it was already
changed, else with what git would check out for it (``git cat-file --filters``).
A test that restores a file's exact bytes therefore passes, and one that leaves
different bytes, or puts back the committed bytes over a developer's edit,
fails. Without git (an sdist or a bare copy) the guard stands aside.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def _git(root: Path, *args):
    try:
        done = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _stat(path: Path):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    except OSError:
        return "unreadable"
    return (st.st_size, st.st_mtime_ns)


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        return "deleted"
    except OSError:
        return "unreadable"


def snapshot(root) -> dict | None:
    """Stat every tracked file, and hash the ones git already lists as changed.

    None when git is unavailable or *root* is not a work tree.
    """
    root = Path(root)
    listed = _git(root, "ls-files", "-z")
    changed = _git(root, "diff", "--name-only", "-z")
    if listed is None or changed is None:
        return None
    files = [raw.decode("utf-8", "replace") for raw in listed.split(b"\0") if raw]
    dirty = [raw.decode("utf-8", "replace") for raw in changed.split(b"\0") if raw]
    return {
        "root": str(root),
        "stats": {path: _stat(root / path) for path in files},
        "dirty": {path: _digest(root / path) for path in dirty},
    }


def touched_since(snap) -> list:
    """Tracked paths whose bytes a test changed since *snap* was taken."""
    if snap is None:
        return []
    root = Path(snap["root"])
    out = []
    for path, before in snap["stats"].items():
        now = _stat(root / path)
        if now == before:
            continue
        if now is None or now == "unreadable":
            if before != now:
                out.append(path)
            continue
        current = (root / path).read_bytes()
        if path in snap["dirty"]:
            if hashlib.sha256(current).hexdigest() != snap["dirty"][path]:
                out.append(path)
            continue
        expected = _git(root, "cat-file", "--filters", f":{path}")
        if expected is None or current != expected:
            out.append(path)
    return sorted(out)
