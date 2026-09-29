"""Identify's only scene writer: it removes old ``~ identify ~`` comment blocks.

Older versions of Identify appended their bubble text to a node's comment,
below an ASCII sentinel line, and switched the comment display on. Bubbles are
now drawn by the overlay (``overlay.py``), which writes nothing to the scene.
One write is still worth doing: when the artist identifies a node that carries
a block an older version left behind (an autosave or a crash-recovery file can
hold one), the block is removed and the artist's own text above it stays
byte-identical.

A block is removed only when it has the exact shape Identify wrote (CRUX F4).
Its sentinel is the last standalone sentinel line in the comment, one to three
lines follow it, none longer than ``compose.WIDTH``, and the first of them is a
What line Identify would have written for that node
(``bubble.legacy_what_lines``). An artist's own standalone ``~ identify ~`` line
followed by their own text is therefore left alone. One undo group wraps a
cleanup, so one Ctrl+Z puts the blocks back, and nothing is written when no
node carries a block.

``hou`` is import-guarded; tests inject a fake with ``undos.group`` and
``nodeFlag.DisplayComment``.
"""
from __future__ import annotations

from contextlib import nullcontext
import logging

from . import compose

_log = logging.getLogger(__name__)

try:  # pragma: no cover - exercised live under hython
    import hou
except ImportError:  # pragma: no cover
    hou = None


#: The ASCII line older versions wrote above their bubble text.
SENTINEL = "~ identify ~"

#: One undo group per cleanup.
UNDO_LABEL = "SYNAPSE Identify cleanup"

#: The most lines an older block carried below its sentinel: What, Here, State.
_MAX_LINES = 3


def legacy_block_start(comment: str, what_lines) -> int:
    """Index of the line where an old Identify block starts, or -1.

    *what_lines* holds the What lines Identify could have written for this
    node. Anything that does not match the exact block shape is artist text.
    """
    lines = (comment or "").split("\n")
    start = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == SENTINEL:
            start = i
            break
    if start == -1:
        return -1
    tail = lines[start + 1:]
    if not 1 <= len(tail) <= _MAX_LINES:
        return -1
    if any(len(line) > compose.WIDTH for line in tail):
        return -1
    if tail[0] not in what_lines:
        return -1
    return start


def has_legacy_block(comment: str, what_lines) -> bool:
    return legacy_block_start(comment, what_lines) != -1


def strip_legacy(comment: str, what_lines) -> str:
    """*comment* without its old Identify block; unchanged when it has none."""
    start = legacy_block_start(comment, what_lines)
    if start == -1:
        return comment or ""
    return "\n".join((comment or "").split("\n")[:start])


def clean_legacy(items) -> int:
    """Remove old Identify blocks from ``[(node, what_lines), ...]``.

    Returns how many nodes were cleaned. The comment display flag follows what
    the old clear did for a block with no record of its prior value: on when
    artist text remains, off when the comment is now empty.
    """
    targets = []
    for node, what_lines in items:
        comment = node.comment() or ""
        if has_legacy_block(comment, what_lines):
            targets.append((node, comment, what_lines))
    if not targets:
        return 0
    group = hou.undos.group(UNDO_LABEL) if hou is not None else nullcontext()
    with group:
        for node, comment, what_lines in targets:
            artist = strip_legacy(comment, what_lines)
            node.setComment(artist)
            node.setGenericFlag(hou.nodeFlag.DisplayComment, bool(artist))
    _log.info("Identify removed %d old comment block(s)", len(targets))
    return len(targets)
