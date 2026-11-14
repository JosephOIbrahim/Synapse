"""Stamp every pytest run with the identity of what it measured.

Two full-suite artefacts from 2026-11-12 carried a platform line, a Python version
and a rootdir, and nothing else: no commit sha, no interpreter path, no record of
which dependency set was present. One of them was produced from a worktree other
than the one it was cited for, and neither could prove which commit it measured.

This file exists because a script people must remember to call is exactly what
failed. A hook runs whether or not anyone remembers.

It is deliberately cheap and deliberately fail-soft: an identity that cannot be
computed reports UNKNOWN and never fails a test run. A harness that refuses to run
because it cannot describe itself would be worse than one that runs unlabelled.
"""
from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

# The modules whose absence or presence changed this project's suite results.
# find_spec, not import: probing presence must not pay an import cost or a side
# effect, and a package that is installed-but-broken must still read as present.
_PROBE = ("numpy", "cv2", "mcp", "pxr", "PySide6", "anthropic", "pydantic")

# The checkout this conftest belongs to. git runs here, not in the process cwd:
# pytest started from a temp folder stamped UNKNOWN, and started from inside
# another repository it stamped that repository's sha (review finding R5).
_ROOT = Path(__file__).resolve().parent


def _git(*args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=str(_ROOT), capture_output=True, text=True,
                           timeout=15)
    except Exception:  # noqa: BLE001 - a missing git is not a test failure
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def _deps() -> dict:
    present = {}
    for name in _PROBE:
        try:
            present[name] = importlib.util.find_spec(name) is not None
        except Exception:  # noqa: BLE001
            present[name] = None
    return present


def _exe_tag() -> str:
    """Distinguish installs without publishing a home directory.

    The version alone cannot tell two 3.14 installs apart; the full path would put a
    username into every log. The basename plus a short hash of the path answers the
    question the log needs without carrying the path.
    """
    exe = sys.executable or ""
    digest = hashlib.sha256(exe.encode("utf-8", "replace")).hexdigest()[:8]
    return f"{(exe.rsplit(chr(92), 1)[-1]).rsplit('/', 1)[-1]}@{digest}"


def identity() -> dict:
    """The identity of this run. Never raises."""
    return {
        "commit": _git("rev-parse", "HEAD") or "UNKNOWN",
        "dirty": bool(_git("status", "--porcelain")),
        "interpreter": f"{sys.implementation.name} {sys.version.split()[0]}",
        "executable": _exe_tag(),
        "deps": _deps(),
    }


def _line(ident: dict) -> str:
    deps = " ".join(f"{k}={'y' if v else 'n'}" for k, v in ident["deps"].items())
    commit = ident["commit"][:12] + (" (dirty)" if ident["dirty"] else "")
    return (f"synapse identity: commit {commit} | {ident['interpreter']} "
            f"at {ident['executable']} | {deps}")


def pytest_configure(config):
    config._synapse_identity = identity()


def pytest_report_header(config):
    ident = getattr(config, "_synapse_identity", None) or identity()
    return [_line(ident)]


def pytest_terminal_summary(terminalreporter):
    """One closing line, so a log ends with the verdict rather than the last test."""
    ident = getattr(terminalreporter.config, "_synapse_identity", None) or identity()
    terminalreporter.write_line(_line(ident))
