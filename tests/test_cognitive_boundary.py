"""Cognitive-layer boundary lint.

The Sprint 3 constitution locks ``synapse.cognitive.*`` as host-agnostic:
zero ``hou`` imports, composes across DCCs (Houdini, Moneta, Octavius).
Host-specific code lives in ``synapse.host.*``.

This test ships the rule as an artifact of the test suite so it runs on
every CI invocation. Adding an ``import hou`` anywhere under the
cognitive tree fails pytest loud at collection-time — no silent drift,
no CI-config-only enforcement that could be skipped locally.

If you need Houdini in cognitive code: you don't. Move the Houdini bit
to ``synapse.host.*`` and inject it across the dispatcher boundary as a
callable (see ``Dispatcher(main_thread_executor=...)``).
"""

from __future__ import annotations

import re
from pathlib import Path


_COGNITIVE_ROOT = (
    Path(__file__).resolve().parent.parent
    / "python"
    / "synapse"
    / "cognitive"
)

# Matches ``import hou``, ``import hou.foo``, ``import hou as X``,
# ``from hou import ...``, ``from hou.foo import ...``. Leading whitespace
# allowed (conditional imports inside functions still count — the
# boundary rule is structural, not lexical). Anchored with \b so names
# like ``houdini``, ``house_keeping``, ``house`` don't false-positive.
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:import\s+hou\b|from\s+hou\b)",
    re.MULTILINE,
)


def test_cognitive_layer_has_no_hou_imports() -> None:
    """Fail loud if any file under synapse.cognitive.* imports hou."""
    assert _COGNITIVE_ROOT.is_dir(), (
        f"Expected cognitive root at {_COGNITIVE_ROOT} — did the package "
        "get moved or deleted? Update this lint's _COGNITIVE_ROOT."
    )

    violators: list[tuple[str, list[int]]] = []
    for py_file in sorted(_COGNITIVE_ROOT.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        hits = [
            # Report 1-indexed line numbers (matching editor display)
            source[:m.start()].count("\n") + 1
            for m in _FORBIDDEN_IMPORT.finditer(source)
        ]
        if hits:
            rel = py_file.relative_to(_COGNITIVE_ROOT.parent.parent.parent)
            violators.append((str(rel), hits))

    assert not violators, (
        "synapse.cognitive.* must be host-agnostic — ZERO hou imports. "
        "Move host-specific code to synapse.host.* and inject via a "
        "callable across the Dispatcher boundary.\n"
        "Violations:\n"
        + "\n".join(f"  {path}: lines {lines}" for path, lines in violators)
    )
