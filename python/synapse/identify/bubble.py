"""One Identify bubble as data: what the overlay draws for one node.

Pure (no ``hou``, no Qt), so it runs on the worker thread and on system
Python. The overlay paints exactly these fields, and nothing here reaches the
scene. Lines are not cut to the old 56-character comment budget: the overlay
wraps text inside the bubble, so the only bound is :data:`TEXT_MAX`, which
keeps a pathological help page from becoming a wall of text.
"""
from __future__ import annotations

from . import compose

#: Bubbles drawn per click. A starting value to tune at the GUI gate
#: (IDENTIFY_BLUEPRINT rule 5); the chip still reports the full selection.
CAP = 60

#: Upper bound for any one text field. The overlay wraps; it does not cut.
TEXT_MAX = 240

#: Node category name -> the short tag drawn at a bubble's top right.
_TAGS = {
    "Sop": "SOP", "Lop": "LOP", "Object": "OBJ", "Driver": "ROP",
    "Cop": "COP", "Cop2": "COP", "Vop": "VOP", "Dop": "DOP", "Chop": "CHOP",
    "Top": "TOP", "Shop": "SHOP", "Manager": "MGR", "Data": "DATA",
}


def category_tag(category) -> str:
    """The short context tag for a node category: ``Sop`` -> ``SOP``."""
    if not category:
        return ""
    name = str(category).strip()
    return _TAGS.get(name, name.upper()[:4])


def bubble_model(facts: dict) -> dict:
    """The overlay's fields for one node, from facts with the summary resolved.

    ``summary`` is None when the library has no exact row; the overlay then
    says so rather than guessing (IDENTIFY_BLUEPRINT rule 6). A LOP names the
    prims it last wrote in ``writes``. Any other node lists its meaningful
    changed parameters in ``changes``, formatted exactly as ``compose`` does.
    """
    if not isinstance(facts, dict):
        raise TypeError("bubble_model expects a facts dict")
    title = facts.get("type_label") or facts.get("type_name") or "unknown"
    summary = facts.get("summary")
    known = facts.get("summary_source") in ("library", "hda") and bool(summary)
    writes = facts.get("lop_writes")
    if isinstance(writes, dict) and writes.get("first"):
        count = int(writes.get("count", 1) or 1)
        writes_field = {
            "path": compose.truncate(str(writes["first"]), TEXT_MAX),
            "more": max(count - 1, 0),
        }
        changes = None
    else:
        writes_field = None
        changes = compose.here_line(facts, TEXT_MAX)
    return {
        "title": compose.truncate(str(title), TEXT_MAX),
        "tag": category_tag(facts.get("category")),
        "summary": compose.truncate(str(summary), TEXT_MAX) if known else None,
        "writes": writes_field,
        "changes": changes,
        "state": compose.state_line(facts, TEXT_MAX),
    }


def legacy_what_lines(facts: dict) -> frozenset:
    """Every What line an older Identify could have written for this node.

    The comment carrier wrote the What line at ``compose.WIDTH``: the library
    or HDA summary when one existed, else ``<label> - not in library``. The
    library may have gained or lost that row since, so both forms count. The
    legacy cleaner removes a block only when its first line is one of these.
    """
    unknown = dict(facts, summary=None, summary_source="unknown")
    lines = {compose.what_line(unknown)}
    if facts.get("summary_source") in ("library", "hda") and facts.get("summary"):
        lines.add(compose.what_line(facts))
    return frozenset(lines)
