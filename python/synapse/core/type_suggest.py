"""Nearest real node types for a type name that does not exist (10/1, TYPEHINT).

The 10/1 Pieke baseline: asked for a Karma blocker light filter, the model sent
fifteen houdini_create_node calls guessing type names (lightfilter, karmablocker,
barndoors, gobo, kma_blocker, ...). Each came back "Invalid node type name" with
nothing to steer by, and the real type, karmablockerlightfilter, was never
tried. One ranked list of the closest real types turns a failed guess into one
correct retry.

``suggest`` is pure (a name -> label catalogue in, ranked names out) so it is
testable without Houdini; ``live_catalog`` reads the running build's catalogue
for one node-type category (hidden types excluded).
"""
from __future__ import annotations

import difflib
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(text: str) -> str:
    return _NON_ALNUM.sub("", (text or "").lower())


def _base(type_name: str) -> str:
    """'karma::lightfilter::2.0' -> 'lightfilter'; 'light::2.0' -> 'light'."""
    parts = (type_name or "").lower().split("::")
    if len(parts) > 1 and re.fullmatch(r"[0-9.]+", parts[-1]):
        parts = parts[:-1]
    return parts[-1] if parts else ""


def _score(query: str, name: str, label: str) -> float:
    q, b, d = _norm(_base(query)), _norm(_base(name)), _norm(label)
    if not q or not b:
        return 0.0
    if q == b:
        return 100.0
    score = 0.0
    if q in b:
        score = max(score, 80.0 - 0.2 * (len(b) - len(q)))
    if d and q in d:
        score = max(score, 70.0 - 0.1 * (len(d) - len(q)))
    if len(b) >= 4 and b in q:
        score = max(score, 55.0 - 0.2 * (len(q) - len(b)))
    ratio = difflib.SequenceMatcher(None, q, b).ratio()
    if ratio >= 0.6:
        score = max(score, 60.0 * ratio)
    # A compound guess built from the label's words ("filterblocker",
    # "karmalightfilter" -> Karma Blocker Light Filter): two or more of the
    # label's words (4+ letters) inside the guess.
    words = {w for w in _NON_ALNUM.split((label or "").lower()) if len(w) >= 4}
    hits = sum(1 for w in words if w in q)
    if hits >= 2:
        score = max(score, 60.0 + 7.0 * hits)
    # Labs/third-party namespaced packages rank below core types.
    if (name or "").lower().startswith("labs::"):
        score -= 12.0
    return score


def suggest(query: str, catalog: Dict[str, str], limit: int = 5,
            floor: float = 35.0) -> List[str]:
    """The real type names in ``catalog`` closest to ``query``, best first.

    Substring matches on the type name or its label rank first (shorter names
    ahead), then close spellings. Below ``floor`` a candidate is dropped, so an
    unrelated catalogue returns [] rather than noise."""
    scored = []
    for name, label in catalog.items():
        s = _score(query, name, label or "")
        if s >= floor:
            scored.append((-s, len(name), name))
    scored.sort()
    out: List[str] = []
    seen_bases = set()
    for _, _, name in scored:
        base = _base(name)
        if base in seen_bases:      # one row per type, whatever its versions
            continue
        seen_bases.add(base)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def live_catalog(category) -> Dict[str, str]:
    """``{type name: label}`` for every visible type in a hou.NodeTypeCategory.
    Never raises: an unreadable category gives {} (and no suggestions)."""
    try:
        types = category.nodeTypes()
    except Exception as exc:  # noqa: BLE001
        logger.debug("type_suggest: catalogue unreadable: %s", exc)
        return {}
    out: Dict[str, str] = {}
    for name, node_type in types.items():
        try:
            if node_type.hidden() or node_type.deprecated():
                continue
            out[name] = node_type.description()
        except Exception as exc:  # noqa: BLE001
            logger.debug("type_suggest: %s unreadable: %s", name, exc)
            out[name] = ""
    return out


def hint(query: str, catalog: Dict[str, str], context: str = "",
         limit: int = 5) -> str:
    """One plain sentence for the model: the closest real types, or what to do."""
    names = suggest(query, catalog, limit=limit)
    where = (" in %s" % context) if context else ""
    if names:
        listed = ", ".join("%s (%s)" % (n, catalog.get(n) or n) for n in names)
        return ("'%s' is not a node type%s. Closest real types: %s. Use one of these "
                "exactly; do not guess other spellings." % (query, where, listed))
    return ("'%s' is not a node type%s, and nothing close exists. Look up the "
            "artist's words with synapse_knowledge_lookup instead of guessing "
            "spellings." % (query, where))


def live_hint(query: str, category, limit: int = 5) -> Optional[str]:
    """``hint`` against a live category; None if the catalogue is unreadable."""
    catalog = live_catalog(category)
    if not catalog:
        return None
    try:
        context = category.name()
    except Exception as exc:  # noqa: BLE001
        logger.debug("type_suggest: category name unreadable: %s", exc)
        context = ""
    return hint(query, catalog, context=context, limit=limit)
