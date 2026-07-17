"""RETINA host-boundary lint — the zero-cv2 pin (M0).

SYNAPSE_RETINA_BLUEPRINT P5 locks the Houdini host process as
perception-free: **zero ``cv2`` imports host-side, ever**. The RETINA
worker (OpenCV/OIIO/ONNX) lives in its own venv, out of process,
host-ABI-independent by construction; the only in-process code is thin
manifest/sentinel hooks. This mirrors the zero-``hou`` cognitive-boundary
lint (``test_cognitive_boundary.py``) from the opposite direction: that
one keeps the brain host-agnostic, this one keeps the host eye-free.

The pin lands in M0, before any perception code exists (blueprint §8:
"zero-cv2 CRUCIBLE pin lands in M0"), so cv2 creep fails pytest loud at
collection-time from day one — no silent drift, no CI-config-only
enforcement.

If you need OpenCV in host code: you don't. Put the operation in the
RETINA worker and let verdict events cross the perception channel; or,
for GPU-heavy per-pixel work, author it as a COP network (blueprint P6)
and let OpenCV remain the out-of-process oracle.

Scope: every surface that executes inside (or is imported by) the
Houdini host process — the ``python/synapse`` package, the repo-root
``shared/`` bridge layer, ``mcp_server.py``, and the ``houdini/``
package/panel definitions. The future ``retina/`` worker tree is
deliberately OUTSIDE this scope.
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent

# Every host-process code surface. The RETINA worker tree (when it
# exists) must NOT be added here — it is the one place cv2 belongs.
_HOST_SURFACES: tuple[Path, ...] = (
    _REPO_ROOT / "python" / "synapse",
    _REPO_ROOT / "shared",
    _REPO_ROOT / "houdini",
)
_HOST_FILES: tuple[Path, ...] = (
    _REPO_ROOT / "mcp_server.py",
)

# Matches ``import cv2``, ``import cv2.foo``, ``import cv2 as X``,
# ``from cv2 import ...``, ``from cv2.foo import ...``. Leading
# whitespace allowed — conditional/lazy imports inside functions still
# count; the boundary rule is structural, not lexical. Anchored with \b
# so names like ``cv2x`` or ``opencv_utils`` don't false-positive.
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:import\s+cv2\b|from\s+cv2\b)",
    re.MULTILINE,
)


def _scan(py_file: Path) -> list[int]:
    source = py_file.read_text(encoding="utf-8", errors="replace")
    return [
        # 1-indexed line numbers, matching editor display
        source[: m.start()].count("\n") + 1
        for m in _FORBIDDEN_IMPORT.finditer(source)
    ]


def test_host_process_has_no_cv2_imports() -> None:
    """Fail loud if any host-process surface imports cv2 (RETINA P5)."""
    for root in _HOST_SURFACES:
        assert root.is_dir(), (
            f"Expected host surface at {root} — did the tree move? "
            "Update this lint's _HOST_SURFACES."
        )

    violators: list[tuple[str, list[int]]] = []

    for root in _HOST_SURFACES:
        for py_file in sorted(root.rglob("*.py")):
            hits = _scan(py_file)
            if hits:
                violators.append(
                    (str(py_file.relative_to(_REPO_ROOT)), hits)
                )

    for py_file in _HOST_FILES:
        if py_file.is_file():
            hits = _scan(py_file)
            if hits:
                violators.append(
                    (str(py_file.relative_to(_REPO_ROOT)), hits)
                )

    assert not violators, (
        "The Houdini host process must stay perception-free — ZERO cv2 "
        "imports host-side (SYNAPSE_RETINA_BLUEPRINT P5). Move pixel "
        "work to the RETINA worker (own venv) and let verdict events "
        "cross the perception channel; for GPU per-pixel work, author a "
        "COP network instead (P6).\n"
        "Violations:\n"
        + "\n".join(f"  {path}: lines {lines}" for path, lines in violators)
    )


def test_retina_worker_tree_is_not_in_host_scope() -> None:
    """The lint's own scope stays honest: if a retina/ worker tree
    appears at the repo root, it must not be inside any host surface
    (it is the one place cv2 belongs — adding it to _HOST_SURFACES
    would forbid the worker's whole purpose)."""
    retina_root = _REPO_ROOT / "retina"
    if not retina_root.exists():
        return  # M2 lands the worker; nothing to check yet
    for root in _HOST_SURFACES:
        assert not retina_root.resolve().is_relative_to(root.resolve()), (
            f"retina/ worker tree found INSIDE host surface {root} — "
            "the worker must live outside every host-process surface "
            "(blueprint P5)."
        )
