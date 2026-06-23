#!/usr/bin/env python3
"""Run a pytest selector under Houdini's hython, which ships PySide.

The PySide-bound panel goalposts (failure-trail, docking-minimums) cannot run
under stock CPython here -- no PySide, so they SKIP, and a skip exits 0, which
the SYNAPSE harness reads as PASSING (a false green). Routing those verifies
through this shim runs them under hython, where PySide exists, so they give a
real pass/fail. The token goalposts stay on stock pytest (they are pure-Python).

hython resolution (first usable wins; "usable" = its python imports pytest +
PySide6, so a build without pytest is skipped instead of failing wrong-reason):
  1. $SYNAPSE_HYTHON                 -- explicit pin (recommended; skips the scan)
  2. `hython` on PATH
  3. newest installed Houdini (Windows / Linux / macOS default layouts)

Usage (from a contract `verify`):
    python .synapse/hytest.py tests/panel/test_docking.py::test_usable_at_min_height

Exits with pytest's own return code (or non-zero if no usable hython is found),
so the harness verify stays honest. Stock-CPython only -- imports no hou/PySide.
"""
import glob
import os
import re
import subprocess
import sys
from shutil import which


def _candidates():
    pinned = os.environ.get("SYNAPSE_HYTHON")
    if pinned:
        yield pinned
    on_path = which("hython")
    if on_path:
        yield on_path
    patterns = [
        r"C:/Program Files/Side Effects Software/Houdini */bin/hython.exe",
        "/opt/hfs*/bin/hython",
        "/Applications/Houdini/Houdini*/Frameworks/Houdini.framework/"
        "Versions/Current/Resources/bin/hython",
    ]
    found = []
    for pat in patterns:
        found += glob.glob(pat)

    def _ver(path):
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", path)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    for path in sorted(found, key=_ver, reverse=True):  # newest first
        yield path


def _usable(hython):
    """True only if this hython's python imports pytest + PySide6 -- otherwise
    `hython -m pytest` would fail for the wrong reason (no module), which would
    re-create the unsatisfiable trap this shim exists to avoid."""
    try:
        proc = subprocess.run(
            [hython, "-c", "import pytest, PySide6"],
            capture_output=True, text=True, timeout=180)
        return proc.returncode == 0
    except Exception:
        return False


def find_hython():
    seen = set()
    for cand in _candidates():
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if os.path.isfile(cand) and _usable(cand):
            return cand
    return None


def main(argv):
    if not argv:
        sys.stderr.write(
            "hytest: usage: python .synapse/hytest.py <pytest-selector> [...]\n")
        return 2
    hython = find_hython()
    if not hython:
        sys.stderr.write(
            "hytest: no hython with pytest+PySide6 found. Set $SYNAPSE_HYTHON to a "
            "Houdini hython (e.g. '.../Houdini 21.0.671/bin/hython.exe'), or add "
            "one to PATH.\n")
        return 3
    sys.stderr.write("hytest: %s\n" % hython)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run([hython, "-m", "pytest", "-q", *argv]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
