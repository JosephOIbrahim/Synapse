"""The Parm Gate (W5-PARMGATE, target 1).

``gated_set(node, parm_values)`` validates every parameter NAME against the
node's catalog signature **before touching the node**, so a hallucinated parm
name (the LLM's #1 failure class on weak domains) becomes a caught error with a
nearest-match suggestion instead of a silent no-op or a mid-mutation crash.

Two hard invariants, both load-bearing for the wave:

1. **Never a new undo path.** This module does not import ``hou`` and never
   opens ``hou.undos.group(...)``. It performs the ``parm.set`` writes directly
   on the node the caller passed in, so those writes land inside whatever undo
   group the *caller* already opened. A gated set therefore stays inside the
   caller's single undo group -- it cannot split, nest, or bypass the Ctrl+Z
   discipline the undo waves shipped. (Crucible criterion 1.)

2. **Reject only known-bad; never a false reject.** The gate is exactly as
   strong as the catalog it has. When a catalog signature exists for the
   (category, node_type), an unknown name is *rejected before any mutation*
   with suggestions. When no signature exists (uncatalogued type, or the
   catalog data is not in the tree yet), the gate degrades to a permissive
   safe-set: it writes the names whose live parm exists and records the rest in
   ``skipped`` -- observable, never a silent success on a bad name, but never a
   false rejection either. (This is what lets weak-domain handlers route every
   write through the gate without regressing flows for not-yet-cataloged types.)

The rejection is **catchable and self-correcting** (crucible criterion 3):
``ParmGateError`` subclasses ``ValueError`` (so existing ``except`` paths still
catch it), carries structured ``.unknown`` with per-name suggestions, exposes
``.to_result()`` for the agent loop, and renders the suggestion inline in its
message so even a generic error surface hands the agent the fix.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import catalog as _catalog


# Runs of digits collapse to '#' so a multiparm instance name ("input3_name")
# matches its catalog template ("input#_name") instead of false-rejecting.
_DIGITS = re.compile(r"\d+")


def _normalize_multiparm(name: str) -> str:
    return _DIGITS.sub("#", name)


def _name_is_known(name: str, valid: Iterable[str], valid_norm: frozenset) -> bool:
    if name in valid:
        return True
    norm = _normalize_multiparm(name)
    return norm in valid_norm or norm in valid


def nearest_matches(name: str, candidates: Sequence[str], k: int = 3) -> List[str]:
    """Rank ``candidates`` by closeness to ``name``; return the best ``k``.

    Score = difflib ratio + a substring boost (either string containing the
    other). The substring boost is what makes ``'code' -> 'kernelcode'`` the top
    hint even though the raw edit distance is large. Ties break alphabetically
    for determinism. Only genuinely-close names survive (ratio >= 0.4 or a
    substring hit), so a wildly-wrong name yields an honest empty list rather
    than a misleading one.
    """
    if not name or not candidates:
        return []
    needle = name.lower()
    scored = []
    for cand in candidates:
        hay = cand.lower()
        ratio = SequenceMatcher(None, needle, hay).ratio()
        substring = needle in hay or hay in needle
        if ratio < 0.4 and not substring:
            continue
        score = ratio + (0.5 if substring else 0.0)
        scored.append((-score, cand))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _s, c in scored[:k]]


class ParmGateError(ValueError):
    """A gated set was rejected: one or more parm names are not on the type.

    Subclasses ``ValueError`` so callers that already catch ValueError keep
    working, while callers that want the structured detail catch this type.
    ``unknown`` is ``[{"name": str, "suggestions": [str, ...]}, ...]``.
    """

    def __init__(self, unknown: List[Dict[str, Any]], *,
                 node_type: Optional[str] = None,
                 category: Optional[str] = None):
        self.unknown = unknown
        self.node_type = node_type
        self.category = category
        super().__init__(self._render())

    def _render(self) -> str:
        where = "/".join(x for x in (self.category, self.node_type) if x) or "node"
        parts = []
        for item in self.unknown:
            sug = item.get("suggestions") or []
            hint = f" (did you mean: {', '.join(sug)}?)" if sug else ""
            parts.append(f"'{item['name']}'{hint}")
        return (f"Unknown parameter(s) on {where}: " + "; ".join(parts)
                + " -- rejected before any mutation by the Parm Gate.")

    def to_result(self) -> Dict[str, Any]:
        """Structured payload for the agent loop to self-correct from."""
        return {
            "ok": False,
            "error": "parm_gate_rejected",
            "category": self.category,
            "node_type": self.node_type,
            "unknown": self.unknown,
            "message": str(self),
        }


def _node_identity(node: Any,
                   category: Optional[str],
                   node_type: Optional[str]) -> tuple:
    """Resolve (category, node_type) from explicit args, else from the node.

    Best-effort: any failure to introspect the node leaves the value ``None``,
    which routes the gate to permissive mode rather than crashing.
    """
    if category and node_type:
        return category, node_type
    try:
        ntype = node.type()
        if node_type is None:
            node_type = ntype.name()
        if category is None:
            category = ntype.category().name()
    except Exception:  # noqa: BLE001 -- introspection is best-effort
        pass
    return category, node_type


def _apply(node: Any, name: str, value: Any) -> bool:
    """Write one value to ``name`` on ``node``; True iff the parm existed.

    Tuple/list values go through ``parmTuple``; scalars through ``parm``. A
    missing parm returns False (recorded as skipped) rather than raising -- the
    same resilience the pre-gate handlers had via ``if parm is not None``.
    """
    try:
        if isinstance(value, (list, tuple)):
            pt = node.parmTuple(name)
            if pt is not None:
                pt.set(value)
                return True
            # Fall through: some scalar-ish tuples still set via parm().
        p = node.parm(name)
        if p is not None:
            p.set(value)
            return True
    except Exception:  # noqa: BLE001 -- a set failure is surfaced by caller state
        raise
    return False


def gated_set(node: Any,
              parm_values: Dict[str, Any],
              *,
              category: Optional[str] = None,
              node_type: Optional[str] = None,
              catalog: Optional[_catalog.Catalog] = None) -> Dict[str, Any]:
    """Validate parm NAMES against the catalog, then set the valid ones.

    Args:
        node: the ``hou`` node to write (any object exposing ``parm``/
            ``parmTuple`` and, for auto-identity, ``type()``).
        parm_values: ``{parm_name: value}`` to write.
        category, node_type: override the node's catalog identity (tests, or a
            caller that knows the type it just created).
        catalog: a ``Catalog`` to gate against; defaults to the process catalog.

    Returns a dict:
        ``{"gated": bool, "authority": "catalog"|"none",
           "set": [names written], "skipped": [names whose parm was absent],
           "category": ..., "node_type": ...}``

    Raises:
        ParmGateError: when a catalog signature exists AND one or more names are
            absent from it -- raised BEFORE any mutation, so a rejected call
            never partially writes.
    """
    result = {"gated": False, "authority": "none", "set": [], "skipped": [],
              "category": category, "node_type": node_type}
    if not parm_values:
        return result

    category, node_type = _node_identity(node, category, node_type)
    result["category"], result["node_type"] = category, node_type

    cat = catalog if catalog is not None else _catalog.default_catalog()
    valid = cat.parms(category, node_type) if (category and node_type) else None

    if valid is not None:
        # AUTHORITATIVE: the catalog knows this type. Reject unknown names up
        # front, before any write, with nearest-match suggestions.
        valid_norm = frozenset(_normalize_multiparm(v) for v in valid)
        unknown = [name for name in parm_values
                   if not _name_is_known(name, valid, valid_norm)]
        if unknown:
            ordered = sorted(valid)
            details = [{"name": n, "suggestions": nearest_matches(n, ordered)}
                       for n in unknown]
            raise ParmGateError(details, node_type=node_type, category=category)
        result["authority"] = "catalog"
        result["gated"] = True
        for name, value in parm_values.items():
            (result["set"] if _apply(node, name, value)
             else result["skipped"]).append(name)
        return result

    # PERMISSIVE: no catalog authority for this type -> safe-set. Write the
    # names whose live parm exists; record the rest in `skipped` (observable,
    # never a silent success on a name the live node lacks).
    for name, value in parm_values.items():
        (result["set"] if _apply(node, name, value)
         else result["skipped"]).append(name)
    return result
