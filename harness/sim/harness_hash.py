"""H_t — the harness, as a hash you can diff.

A commit id is a poor identity for a harness edit: it covers files the harness
does not care about, and it cannot express an edit smaller than a commit. This
module hashes a **declared** list of editable surfaces instead, so

* changing a declared file moves the hash, and
* changing anything undeclared does not.

The declaration is the point. Adding a surface is a deliberate act with a diff,
not an accident of whatever happened to be on disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Sequence

# Directories and files whose contents constitute "the harness" for the purposes of
# an edit record. Globs are relative to the repository root.
DECLARED_SURFACES: tuple[str, ...] = (
    "harness/bench/recipes/**/*",
    "harness/bench/corpus/**/*",
    "harness/bench/prompts/**/*",
    "harness/bench/routing.json",
    ".claude/skills/**/*.md",
    "python/synapse/panel/system_prompt.py",
    "python/synapse/panel/worker_policy.py",
    "python/synapse/mcp/_tool_registry.py",
)

ABSENT = b"\x00ABSENT"


def surface_files(repo_root: Path, surfaces: Sequence[str] | None = None) -> list[Path]:
    """Every declared file that exists, sorted, de-duplicated."""
    root = Path(repo_root)
    found: dict[str, Path] = {}
    for pattern in surfaces or DECLARED_SURFACES:
        for path in root.glob(pattern):
            if path.is_file():
                found.setdefault(path.relative_to(root).as_posix(), path)
    return [found[key] for key in sorted(found)]


def _digest(path: Path) -> bytes:
    return hashlib.sha256(path.read_bytes()).digest()


def surface_tree_hash(repo_root: Path, surfaces: Sequence[str] | None = None) -> str:
    """SHA-256 over the declared surfaces: path, then content hash, in path order.

    A declared pattern that matches nothing contributes an ABSENT marker, so a
    surface appearing or disappearing changes the hash just as an edit does.
    """
    root = Path(repo_root)
    patterns = list(surfaces or DECLARED_SURFACES)

    per_pattern: dict[str, list[str]] = {}
    for pattern in patterns:
        matches = sorted(
            path.relative_to(root).as_posix()
            for path in root.glob(pattern)
            if path.is_file()
        )
        per_pattern[pattern] = matches

    tree = hashlib.sha256()
    for pattern in patterns:
        tree.update(pattern.encode("utf-8") + b"\x00")
        matches = per_pattern[pattern]
        if not matches:
            tree.update(b"\x00" + ABSENT + b"\n")
            continue
        for relative in matches:
            tree.update(relative.encode("utf-8") + b"\x00" + _digest(root / relative) + b"\n")
    return tree.hexdigest()


def changed_surfaces(repo_root: Path, before: str, after: str) -> list[str]:
    """Which declared files differ between two checkouts of the same tree layout.

    Only useful when both hashes were taken over the same declaration; it exists
    so Phase 3 can say *what* changed, not only that something did.
    """
    if before == after:
        return []
    root = Path(repo_root)
    changed: list[str] = []
    for pattern in DECLARED_SURFACES:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                changed.append(path.relative_to(root).as_posix())
    return sorted(set(changed))
