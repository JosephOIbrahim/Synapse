"""Phase 0c / DOC-1: SYNAPSE version is single-sourced and the docs conform.

v4 §4a.4: a version string is a claim ABOUT the system -- it must bind to code, not
drift. Canonical source = pyproject.toml [project].version. This test asserts the
chain pyproject == __init__.__version__ == __init__ docstring == CLAUDE.md banner.
If any drifts (the v5.8.0-vs-5.10.0 banner the CTO review flagged) it fails loud.

Reads files by path -> stock-CI-safe (no package import). This is the version slice
of DOC-1; the tool-count slice (108/110/117 ambiguity) is a separate follow-up.
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (_ROOT / rel).read_text(encoding="utf-8")


def _canonical_version():
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert m, "pyproject.toml has no [project] version"
    return m.group(1)


def test_version_single_sourced_and_docs_conform():
    canonical = _canonical_version()  # e.g. 5.10.0

    init = _read("python/synapse/__init__.py")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', init)
    assert m, "__init__.py has no __version__"
    assert m.group(1) == canonical, (
        f"__version__ ({m.group(1)}) != pyproject version ({canonical})"
    )

    # The package front-matter docstring must not contradict __version__.
    assert f"Version: {canonical}" in init, (
        f"__init__.py docstring does not state 'Version: {canonical}'"
    )

    # CLAUDE.md must state the canonical version, not a stale banner.
    claude = _read("CLAUDE.md")
    assert f"v{canonical}" in claude, (
        f"CLAUDE.md does not state the canonical SYNAPSE version v{canonical} "
        "(DOC-1: update the banner -- or this test if the version changed)."
    )
