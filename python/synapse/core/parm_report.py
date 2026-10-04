"""Report parm writes that did not land.

A tool that guards a write with ``if parm:`` turns a renamed or missing parm
into a silent no-op and still reports success. ``note_missing`` is the other
branch of that guard: it records ``<node type>.<name>`` (alternates joined with
``|``) in the list the tool returns as ``parms_missed``. An empty list is a
claim: every guarded write in that call landed.

Pure Python: works on real ``hou`` nodes and on test fakes.
"""
from __future__ import annotations

from typing import List


def _type_name(node) -> str:
    type_fn = getattr(node, "type", None)
    node_type = type_fn() if callable(type_fn) else None
    name_fn = getattr(node_type, "name", None)
    candidate = name_fn() if callable(name_fn) else None
    return candidate if isinstance(candidate, str) and candidate else "?"


def note_missing(missed: List[str], node, *names: str) -> None:
    """Record that none of ``names`` exists as a parm on ``node``."""
    entry = f"{_type_name(node)}.{'|'.join(names)}"
    if entry not in missed:
        missed.append(entry)
