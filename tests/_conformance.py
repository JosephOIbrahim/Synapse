"""
Reusable conformance assertions for SYNAPSE tests.

After three drift bugs caught manually across passes 3 / 5 / 6 the pattern is
clear: a string value (constant, fingerprint, stage name) lives in N files,
someone renames one, the others silently break. This module provides a small
diagnostic helper that future tests can use to pin those values.

Usage:

    from tests._conformance import assert_value_in_all_files

    def test_charmander_canonical():
        assert_value_in_all_files(
            value="charmander",
            files=[
                "shared/constants.py",
                "python/synapse/memory/scene_memory.py",
                "CLAUDE.md",
            ],
            description="canonical evolution stage 1 name",
        )

The helper produces a single failure message naming every out-of-sync file
rather than the one-at-a-time drip a manual assert would give.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def assert_value_in_all_files(
    value: str,
    files: list[str],
    description: str = "",
    word_boundary: bool = True,
) -> None:
    """Assert *value* appears in every file in *files*.

    Args:
        value: The literal string the files must mention.
        files: Repo-relative paths. Missing files count as failures.
        description: Human-readable label for the diagnostic.
        word_boundary: If True (default), match \\b{value}\\b so partial
                       substring matches don't count. Set False for values
                       that contain non-word characters (e.g. fingerprints
                       with `|` separators).

    Raises:
        AssertionError listing every out-of-sync file in one message.
    """
    if word_boundary:
        pattern = re.compile(rf"\b{re.escape(value)}\b")
    else:
        pattern = re.compile(re.escape(value))

    missing: list[str] = []
    not_found: list[str] = []

    for rel_path in files:
        full = _REPO_ROOT / rel_path
        if not full.exists():
            missing.append(rel_path)
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except Exception as exc:
            missing.append(f"{rel_path} (read error: {exc})")
            continue
        if not pattern.search(text):
            not_found.append(rel_path)

    if missing or not_found:
        label = description or f"value {value!r}"
        lines = [f"Canonical constant drift detected for {label}:"]
        if missing:
            lines.append("  Files not found / unreadable:")
            lines.extend(f"    - {p}" for p in missing)
        if not_found:
            lines.append(f"  Files missing the value {value!r}:")
            lines.extend(f"    - {p}" for p in not_found)
        lines.append(
            "  → Either update the listed files to mention the canonical "
            "value, or update the test if the canonical name has changed."
        )
        raise AssertionError("\n".join(lines))
