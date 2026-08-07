"""CI0 — pins the `needs_houdini` marker mechanism.

The marker exists so `.github/workflows/ci.yml` can run
`-m "not needs_houdini"` on stock GitHub runners, which have neither `hou`
(Houdini's Python module) nor `pxr` (OpenUSD).

A filter that removes tests is only honest if it provably removes nothing that
would otherwise have run. That is what this file enforces:

  1. the detector has teeth (positive AND negative synthetic controls),
  2. every module it marks ALREADY refuses to run without its runtime, so the
     filter is redundant with a gate the module carries anyway,
  3. the marker actually covers something (a marker that marks nothing is a
     decoration that will later be cited as evidence),
  4. the marker is registered, so `--strict-markers` stays available.

Constitution Law 1: each of these states the condition under which it fails.
"""

import ast
import re
from pathlib import Path

import pytest

from conftest import (  # the suite's own conftest is importable as a module
    module_runtime_requirement,
    needs_houdini_reason,
)

_ROOT = Path(__file__).resolve().parents[1]
_TESTS = _ROOT / "tests"


def _test_modules():
    return sorted(_TESTS.rglob("test_*.py"))


def _marked_modules():
    marked = {}
    for path in _test_modules():
        source = path.read_text(encoding="utf-8", errors="replace")
        runtime = module_runtime_requirement(source)
        if runtime:
            marked[path] = runtime
    return marked


# ─────────────────────────────────────────────────────────────────
# 1. The detector has teeth
# ─────────────────────────────────────────────────────────────────

_MUST_DETECT = [
    ("bare module-level hou import", "import hou\n", "hou"),
    ("bare module-level pxr import", "from pxr import Usd, Sdf\n", "pxr"),
    ("module-level importorskip", 'import pytest\npytest.importorskip("pxr")\n', "pxr"),
    (
        "module-level pytestmark skipif on a real-hou probe",
        'import pytest\nimport hou\n'
        'pytestmark = pytest.mark.skipif(not _LIVE, reason="needs real hou")\n',
        "hou",
    ),
    (
        "pytestmark skipif naming pxr without importing it",
        'import pytest\n'
        'pytestmark = pytest.mark.skipif(not _HAS_PXR, reason="pxr absent")\n',
        "pxr",
    ),
]

_MUST_NOT_DETECT = [
    ("guarded try/except import", "try:\n    import hou\nexcept ImportError:\n    hou = None\n"),
    ("import inside a function", "def t():\n    import hou\n    return hou\n"),
    (
        "import inside a code string shipped over the wire",
        'CODE = """\nimport hou\nhou.node("/obj")\n"""\n',
    ),
    (
        "importorskip nested in a try (not module level)",
        'try:\n    import pytest\n    pytest.importorskip("hou")\nexcept ImportError:\n    pass\n',
    ),
    (
        "pytestmark gated on something other than the runtime",
        'import pytest\n'
        'pytestmark = pytest.mark.skipif(not _LIVE, reason="set SYNAPSE_H22_LIVE=1")\n',
    ),
    ("relative import that merely looks similar", "from .houdini_helpers import x\n"),
    ("no runtime at all", "import json\n\n\ndef test_x():\n    assert json\n"),
]


@pytest.mark.parametrize("label,source,expected", _MUST_DETECT,
                         ids=[c[0] for c in _MUST_DETECT])
def test_detector_positive_controls(label, source, expected):
    """Fails if the detector stops recognising a real hard requirement —
    i.e. if a module that genuinely needs a runtime silently stops being
    marked and starts erroring the CI run instead."""
    assert module_runtime_requirement(source) == expected


@pytest.mark.parametrize("label,source", _MUST_NOT_DETECT,
                         ids=[c[0] for c in _MUST_NOT_DETECT])
def test_detector_negative_controls(label, source):
    """Fails if the detector starts over-marking — the dangerous direction,
    because an over-mark deselects a test that CAN run on a stock runner."""
    assert module_runtime_requirement(source) is None


# ─────────────────────────────────────────────────────────────────
# 2. The honesty invariant
# ─────────────────────────────────────────────────────────────────

def test_every_marked_module_already_refuses_without_its_runtime():
    """THE load-bearing test of this file.

    `-m "not needs_houdini"` may only remove tests that would have skipped
    anyway. So every marked module must carry its OWN gate — an importorskip
    or a skipif — independent of the marker. If one does not, the CI filter
    would be hiding a test that could have run, and this fails.

    Fails when: someone marks a module (or writes one the detector marks) that
    has no self-gate, e.g. a module whose only protection is the marker itself.
    """
    ungated = []
    for path, runtime in _marked_modules().items():
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
        has_gate = False
        for node in ast.walk(tree):
            segment = ""
            if isinstance(node, ast.Call):
                segment = ast.get_source_segment(source, node) or ""
            if not segment:
                continue
            if "importorskip" in segment or "skipif" in segment:
                has_gate = True
                break
        if not has_gate:
            ungated.append(f"{path.relative_to(_ROOT)} (needs {runtime})")
    assert not ungated, (
        "these modules are marked needs_houdini but carry no self-gate, so the "
        "CI -m filter would be the ONLY thing stopping them — that is a filter "
        "hiding a runnable test, not describing one:\n  " + "\n  ".join(ungated))


def test_marker_never_covers_a_module_that_only_fakes_its_runtime():
    """The conftest plants a canonical FAKE `hou`, so a module can `import hou`
    and still run fine on a stock interpreter. Such a module must NOT be marked
    on the strength of the import alone — it must also carry a real-hou gate.

    Fails when: a module gets marked whose only hou contact is the fake.
    """
    offenders = []
    for path, runtime in _marked_modules().items():
        if runtime != "hou":
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        # A real-hou gate distinguishes the fake from the genuine article:
        # either it probes for the canonical sentinel, or it skips on a live flag.
        if not re.search(r"__synapse_canonical__|skipif|importorskip", source):
            offenders.append(str(path.relative_to(_ROOT)))
    assert not offenders, (
        "marked as needing `hou` but with nothing that separates real Houdini "
        "from the conftest's canonical fake:\n  " + "\n  ".join(offenders))


# ─────────────────────────────────────────────────────────────────
# 3 + 4. The mechanism has content, and is registered
# ─────────────────────────────────────────────────────────────────

def test_marker_covers_a_nonempty_set():
    """A marker that marks nothing is a decoration that gets cited as evidence
    (Law 1). Fails if every hou/pxr-hard module leaves the tree — at which
    point the marker and the CI filter should be deleted, not kept as scenery.
    """
    marked = _marked_modules()
    assert marked, (
        "needs_houdini marks zero modules. Either the detector broke or the "
        "last hard-requirement module left the tree; if the latter, remove the "
        "marker and the -m filter in .github/workflows/ci.yml rather than "
        "keeping a filter that filters nothing.")


def test_every_reason_names_the_missing_dependency():
    """The brief's requirement: a reader must be able to audit WHY a test did
    not run. Fails if a reason ever stops naming the module it needs."""
    for runtime in ("hou", "pxr"):
        reason = needs_houdini_reason(runtime)
        assert runtime in reason, reason
        assert "needs a Houdini runtime" in reason


def test_marker_is_registered_in_pyproject():
    """Fails if the marker is dropped from pyproject, which would make the CI
    filter silently match nothing under --strict-markers."""
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "needs_houdini:" in pyproject, (
        "needs_houdini is not registered in [tool.pytest.ini_options] markers")


def test_ci_workflow_filters_and_shows_skips():
    """The mechanism is only worth anything if CI actually uses it, and only
    honest if the skipped set is visible. Fails if either half is dropped from
    the workflow.
    """
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert 'not needs_houdini' in ci, "CI no longer filters on needs_houdini"
    assert "-rs" in ci, (
        "CI dropped -rs, so skipped tests and their reasons stop printing in "
        "the run summary — the skipped set would become invisible")
