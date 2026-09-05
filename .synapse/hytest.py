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
  3. the installed Houdini whose version equals the committed symbol-table
     stamp for its major (python/synapse/cognitive/tools/data/
     h<major>_symbol_table.json -> "houdini_version"; 22.0.400 today)
  4. newest installed Houdini (Windows / Linux / macOS default layouts)

Rule 3 exists because "newest" is folklore on a host with several 22.0.x
builds: a newer build imports pytest + PySide6 just fine, so it passes the
usability gate and then runs probes against a runtime no symbol table
describes (B10, 2026-09-05). The stamp is the build SYNAPSE is verified on.

Usage (from a contract `verify`):
    python .synapse/hytest.py tests/panel/test_docking.py::test_usable_at_min_height
    python .synapse/hytest.py --which     # print the hython that would run, and why

Exits with pytest's own return code (or non-zero if no usable hython is found),
so the harness verify stays honest. Stock-CPython only -- imports no hou/PySide.
"""
import glob
import json
import os
import re
import subprocess
import sys
from shutil import which

# <repo>/python/synapse/cognitive/tools/data -- where introspect_runtime.py
# writes h<major>_symbol_table.json. Module-level so a test can point it at a
# fixture directory.
SYMBOL_TABLE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "python", "synapse", "cognitive", "tools", "data")

_INSTALL_PATTERNS = [
    r"C:/Program Files/Side Effects Software/Houdini */bin/hython.exe",
    "/opt/hfs*/bin/hython",
    "/Applications/Houdini/Houdini*/Frameworks/Houdini.framework/"
    "Versions/Current/Resources/bin/hython",
]


def _ver(path):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", path)
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def _stamped_versions():
    """{major: (maj, min, build)} from every committed h<major>_symbol_table.json.

    A table that is missing, unreadable, or carries no ``houdini_version`` is
    simply absent from the map -- rule 3 then has nothing to match and the
    scan falls through to newest-first. Never raises."""
    stamps = {}
    for path in glob.glob(os.path.join(SYMBOL_TABLE_DIR, "h*_symbol_table.json")):
        m = re.search(r"h(\d+)_symbol_table\.json$", path.replace("\\", "/"))
        if not m:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                version = json.load(fh).get("houdini_version")
        except Exception:
            continue
        if isinstance(version, str) and re.fullmatch(r"\d+\.\d+\.\d+", version):
            stamps[int(m.group(1))] = _ver(version)
    return stamps


def _installed():
    found = []
    for pat in _INSTALL_PATTERNS:
        found += [p.replace("\\", "/") for p in glob.glob(pat)]
    return sorted(found, key=_ver, reverse=True)  # newest first


def _candidates():
    """Yield bare hython paths in resolution order (see module docstring).

    Consumer contract: scripts/solaris_v3_accept.py:hython_candidates iterates
    this and hands each item to subprocess.run as the executable -- so this
    must yield plain path strings, never tuples. The reasoned view lives in
    _candidates_with_reason()."""
    for path, _reason in _candidates_with_reason():
        yield path


def _candidates_with_reason():
    """Yield (path, reason) in resolution order (see module docstring)."""
    pinned = os.environ.get("SYNAPSE_HYTHON")
    if pinned:
        yield pinned, "SYNAPSE_HYTHON pin"
    on_path = which("hython")
    if on_path:
        yield on_path, "hython on PATH"
    installed = _installed()
    stamps = _stamped_versions()
    stamped = [p for p in installed if stamps.get(_ver(p)[0]) == _ver(p)]
    for path in stamped:
        yield path, "symbol-table stamp h%d = %s" % (
            _ver(path)[0], ".".join(str(x) for x in _ver(path)))
    for path in installed:
        if path in stamped:
            continue
        yield path, ("newest installed (no committed symbol-table stamp matches"
                     " an installed build)" if not stamped
                     else "newer install, NOT the symbol-table build")


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


def find_hython_with_reason():
    seen = set()
    for cand, reason in _candidates_with_reason():
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if os.path.isfile(cand) and _usable(cand):
            return cand, reason
    return None, None


def find_hython():
    return find_hython_with_reason()[0]


def main(argv):
    if not argv:
        sys.stderr.write(
            "hytest: usage: python .synapse/hytest.py <pytest-selector> [...]\n"
            "        python .synapse/hytest.py --which\n")
        return 2
    hython, reason = find_hython_with_reason()
    if not hython:
        sys.stderr.write(
            "hytest: no hython with pytest+PySide6 found. Set $SYNAPSE_HYTHON to a "
            "Houdini hython (e.g. '.../Houdini 22.0.400/bin/hython.exe'), or add "
            "one to PATH.\n")
        return 3
    sys.stderr.write("hytest: %s (%s)\n" % (hython, reason))
    if argv == ["--which"]:
        sys.stdout.write(hython + "\n")
        return 0
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return subprocess.run([hython, "-m", "pytest", "-q", *argv]).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
