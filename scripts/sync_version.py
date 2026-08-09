"""scripts/sync_version.py -- the one version observer, and the one propagator.

Blueprint W0 (SYN-NEXT-001, ratified 619d28a8): root VERSION is canonical.
Every other surface either derives from it or is checked against it here.

House rule (face_token.py): unobtainable renders as UNKNOWN, never zero and
never an estimate. A surface this script cannot read reports UNKNOWN and FAILS
the check -- an unreadable surface is not a conforming surface.

Lineage: harness/verify/version_agreement.py (R107) found five surfaces the
hard way; tests/test_phase0c_doc1_version_conformance.py binds the chain.
This script adds the sixth live surface (README banner -- the v5.42.0 leg of
the three-way split, adjudication SYN-NEXT-001 row 1) and resolves paths from
its own location, so it runs correctly from any CWD.

Declared NON-surfaces (scope-declared per A4): python/synapse/_vendor/*
(upstream packages), forge/ retina/ inspector/ core/determinism.py (component
versions), harness/rope/ + panel manifests/qss (historical UI baseline -- see
the conformance test's own warning), host/version_injector.py (Houdini
version, not SYNAPSE), the install stamp (derived at install time; verified
by doctor at runtime, not writable from the repo).

Encoding (R107): read utf-8-sig -- VERSION once carried a BOM written by
Set-Content during a release. Write utf-8, LF, no BOM.

Usage:
  python scripts/sync_version.py            # --check is the default
  python scripts/sync_version.py --check    # observe, report, exit 0/1
  python scripts/sync_version.py --write    # propagate VERSION -> surfaces
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name -> (pattern or None, relative path). None = the whole file is the value.
SURFACES = {
    'VERSION':     (None, 'VERSION'),
    'pyproject':   (re.compile(r'^version\s*=\s*"([^"]+)"', re.M),
                    'pyproject.toml'),
    '__version__': (re.compile(r'__version__\s*=\s*"([^"]+)"'),
                    'python/synapse/__init__.py'),
    'docstring':   (re.compile(r'Version:\s*([0-9]+\.[0-9]+\.[0-9]+)'),
                    'python/synapse/__init__.py'),
    'claude_md':   (re.compile(r'SYNAPSE v([0-9]+\.[0-9]+\.[0-9]+)'),
                    'CLAUDE.md'),
    'readme':      (re.compile(r'^> v([0-9]+\.[0-9]+\.[0-9]+) \u00b7 Houdini', re.M),
                    'README.md'),
}

UNKNOWN = 'UNKNOWN'


def read_surface(name):
    """One surface's observed value, or UNKNOWN. Never a guess, never 0.0."""
    pat, rel = SURFACES[name]
    path = ROOT / rel
    try:
        txt = path.read_text(encoding='utf-8-sig')
    except OSError:
        return UNKNOWN
    if pat is None:
        v = txt.strip()
        return v if v else UNKNOWN
    m = pat.search(txt)
    return m.group(1) if m else UNKNOWN


def check(verbose=True):
    """Observe all surfaces against canonical VERSION. Report, no writes."""
    vals = {k: read_surface(k) for k in SURFACES}
    canonical = vals['VERSION']
    ok = canonical != UNKNOWN
    for k, v in vals.items():
        conform = (v == canonical) and v != UNKNOWN
        ok = ok and conform
        if verbose:
            state = 'CONFORM' if conform else (
                'UNKNOWN' if v == UNKNOWN else 'DRIFT')
            print(f'{k:12s} {v!s:12s} {state}')
    if verbose:
        print(f'canonical={canonical}  verdict={"PASS" if ok else "FAIL"}')
    return ok, vals


def write_surface(name, value):
    pat, rel = SURFACES[name]
    path = ROOT / rel
    txt = path.read_text(encoding='utf-8-sig')
    new = pat.sub(lambda m: m.group(0).replace(m.group(1), value),
                  txt, count=1)
    with io.open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)


def propagate():
    """VERSION -> every other surface. Two passes: refuse before any write
    if anything is UNKNOWN -- no partial propagation on an unobserved tree."""
    vals = {k: read_surface(k) for k in SURFACES}
    canonical = vals['VERSION']
    if canonical == UNKNOWN:
        print('VERSION      UNKNOWN -- refusing to propagate an unobserved '
              'canonical')
        return False
    unknowns = [k for k, v in vals.items() if v == UNKNOWN]
    if unknowns:
        for k in unknowns:
            print(f'{k:12s} UNKNOWN -- file/pattern missing; refusing to '
                  'write anything')
        return False
    for k, v in vals.items():
        if k != 'VERSION' and v != canonical:
            write_surface(k, canonical)
            print(f'{k:12s} {v} -> {canonical}')
    ok, _ = check()
    return ok


if __name__ == '__main__':
    if '--write' in sys.argv:
        sys.exit(0 if propagate() else 1)
    ok, _ = check()
    sys.exit(0 if ok else 1)
