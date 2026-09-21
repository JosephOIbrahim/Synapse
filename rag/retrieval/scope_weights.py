"""The ONE scope-ranking table for SYNAPSE retrieval.

Ranks ``h22_prose`` > ``guide`` > ``h21``. h22_prose (what a node is, what a setting does)
is served first; H21 (``rag/skills/houdini21-reference``) is the fallback scope, taken only
on a miss; every ordered hit carries which scope it came from. For how-to phrasing ("set up",
"how do I", "why does") the guide scope outranks prose; for reference phrasing (a bare node or
parameter name) prose outranks guides.

The ``guide`` slot was landed INERT by BP10-CORPUS and is now **ACTIVE as of BP10-GUIDES**,
which shipped ``rag/corpus/guides/`` -- ``is_active('guide')`` is True, so guide chunks now
rank per the how-to rule already encoded and tested here.

The rule lives here, as a table, not as a heuristic buried in code (HARVEST_SPEC
"Retrieval priority"). Editing the ranking is a text diff in this one file.

Two corpora answering the same question is the confused state to avoid, so the retrieval
layer takes h22_prose first and falls to h21 only on a miss, and every answer names which
one it came from. Live wiring of the generated (gitignored) h22_prose corpus into the
serving path is staged for BP10-GUIDES; this module is the ranking authority it consults.
"""
from __future__ import annotations

REFERENCE, HOWTO, FALLBACK = "reference", "howto", "fallback"

# base: a higher number is served first. active=False means inert -- present in the table so
# the ranking is complete and reviewable, but contributing nothing until its corpus lands.
SCOPES = {
    "h22_prose": {"base": 100, "active": True,  "role": REFERENCE},
    "guide":     {"base":  90, "active": True,  "role": HOWTO},      # armed by BP10-GUIDES
    "h21":       {"base":  10, "active": True,  "role": FALLBACK},   # rag/skills/houdini21-reference
}
HOWTO_BONUS = 20   # lifts a how-to-role scope above prose when the query is how-to phrased

HOWTO_MARKERS = ("how do i", "how to", "how can i", "how does", "set up", "setup",
                 "why does", "why is", "put together", "build", "create", "workflow", "pipeline")


def phrasing(query: str) -> str:
    """'howto' when the query asks how to put something together, else 'reference'."""
    q = " " + (query or "").lower().strip() + " "
    return HOWTO if any(m in q for m in HOWTO_MARKERS) else REFERENCE


def is_active(scope: str) -> bool:
    return bool(SCOPES.get(scope, {}).get("active"))


def scope_weight(scope: str, query: str = "") -> int:
    """The table weight for a scope on a query (independent of whether it is active yet)."""
    s = SCOPES.get(scope)
    if not s:
        return -1
    w = s["base"]
    if s["role"] == HOWTO and phrasing(query) == HOWTO:
        w += HOWTO_BONUS                      # guide 90 + 20 = 110 > prose 100 on how-to
    return w


def ranked_scopes(query: str = "", available=None):
    """Active scopes, highest weight first. ``available`` (a set) filters to scopes that
    actually returned a hit, so an absent h22_prose falls through to h21 (fallback on miss)."""
    scopes = [s for s in SCOPES if is_active(s)]
    if available is not None:
        scopes = [s for s in scopes if s in available]
    return sorted(scopes, key=lambda s: scope_weight(s, query), reverse=True)


def carry_scope(hit, scope: str) -> dict:
    """Tag a hit with the scope it came from. Every retrieval answer carries its scope."""
    if isinstance(hit, dict):
        return {**hit, "scope": scope}
    return {"hit": hit, "scope": scope}


def order_hits(hits_by_scope: dict, query: str = "", top_k=None):
    """Merge ``{scope: [hit, ...]}`` into one scope-priority-ordered list, each hit tagged
    with its scope. Within a scope the caller's order is preserved. This realises
    'h22_prose first, H21 on a miss': h21 hits appear only below higher-scope hits, and are
    served alone when the higher scopes returned nothing."""
    available = {s for s, hs in hits_by_scope.items() if hs}
    out = []
    for scope in ranked_scopes(query, available):
        for hit in hits_by_scope.get(scope, []):
            out.append(carry_scope(hit, scope))
    return out[:top_k] if top_k else out


def table() -> dict:
    """The ranking table as plain data (for the shadow note or a PR diff)."""
    return {s: dict(v) for s, v in SCOPES.items()}
