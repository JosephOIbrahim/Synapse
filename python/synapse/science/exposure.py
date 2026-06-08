"""The provenance→exposure projection (v5 §8) — the panel bridge.

A capability's HIGHEST current rung → a co-pilot exposure tier. **Derived, never
stored** (Ledger violation #7): there is no authored exposure list, only this pure
function of the Ledger — so exposure can't drift from provenance. The panel renders
the projection; it never has to *know* about provenance. The harness and the panel
v5/v9 meet at the rung.

Pure: stdlib only, zero ``hou``/``pxr``. Rung scale single-sourced from
:mod:`synapse.science.rungs`.
"""

from __future__ import annotations

from typing import Iterable, List

from synapse.science.rungs import migrate_verified_by

# Solid rungs, weakest → strongest (V1-degraded is orthogonal — see TIER_STRENGTH).
RUNG_ORDER = {"doc_only": 0, "V0_membership": 1, "V1_cook": 2, "V1_output": 3}

# Exposure-tier strength (weakest → strongest). V1-degraded's tier (surfaced_caveat)
# sits ABOVE not_surfaced (a live attempt beats mere prose) but BELOW
# surfaced_unverified (a confirmed V0 existence beats "couldn't reach the runtime").
TIER_STRENGTH = {
    "not_surfaced": 0,
    "surfaced_caveat": 1,
    "surfaced_unverified": 2,
    "available": 3,
    "foreground": 4,
}

# rung → exposure tier (v5 §8).
TIER_FOR_RUNG = {
    "doc_only": "not_surfaced",          # a promise, not work — the co-pilot won't offer it
    "V0_membership": "surfaced_unverified",  # offered, rung shown ("exists; not cook-verified")
    "V1_cook": "available",              # offered normally; it executes clean
    "V1_output": "foreground",           # trusted; the eval signal WAS the intended output
    "V1-degraded": "surfaced_caveat",    # live verification unavailable; caveat travels with it
}

# tier → how the panel renders it (the seam the panel reads — NOT a hand-authored
# tool list). visible/enabled/badge/foreground; demotion greys-out (visible, disabled).
PANEL_RENDER = {
    "not_surfaced":        {"visible": False, "enabled": False, "badge": None,        "foreground": False},
    "surfaced_unverified": {"visible": True,  "enabled": True,  "badge": "unverified","foreground": False},
    "available":           {"visible": True,  "enabled": True,  "badge": None,        "foreground": False},
    "foreground":          {"visible": True,  "enabled": True,  "badge": "trusted",   "foreground": True},
    "surfaced_caveat":     {"visible": True,  "enabled": True,  "badge": "degraded",  "foreground": False},
    "demoted":             {"visible": True,  "enabled": False, "badge": "demoted",   "foreground": False},
}


def highest_tier(rungs: Iterable[str]) -> str:
    """The exposure tier for a capability given the rungs observed for it. The
    highest SOLID rung wins; ``V1-degraded`` surfaces-with-caveat only when it is
    the best available. Empty / all-unmappable → not surfaced (doc_only-equivalent)."""
    migrated = [m for m in (migrate_verified_by(r) for r in rungs) if m]
    if not migrated:
        return "not_surfaced"
    # Map each rung to its tier, then take the STRONGEST tier — this handles
    # V1-degraded's orthogonality correctly (its tier out-ranks not_surfaced but
    # not a confirmed solid rung).
    tiers = [TIER_FOR_RUNG[r] for r in migrated if r in TIER_FOR_RUNG]
    if not tiers:
        return "not_surfaced"
    return max(tiers, key=lambda t: TIER_STRENGTH[t])


def _records_for(capability: str, ledger_records) -> List:
    """Join Ledger records to a capability (the net-new plumbing the RFC §4 flags:
    KnowledgeLookupResult has no provenance_status today). A record pertains to a
    capability via its ``target`` (Allocations) or ``extra['capability']``."""
    out = []
    for r in (ledger_records or []):
        target = getattr(r, "target", "") or ""
        cap = (getattr(r, "extra", {}) or {}).get("capability", "")
        if target == capability or cap == capability:
            out.append(r)
    return out


def tier_for(capability: str, ledger_records) -> str:
    """Exposure tier for ``capability``, DERIVED from the Ledger (compute-on-read,
    never stored). Joins records to the capability, then projects the highest rung."""
    rungs = [getattr(r, "verified_by", "") for r in _records_for(capability, ledger_records)]
    return highest_tier(rungs)


def panel_visibility(tier: str) -> dict:
    """Render spec for the panel seam: a copy of the PANEL_RENDER row for ``tier``.
    The panel's tool/affordance visibility is a render of THIS — not a hand list."""
    return dict(PANEL_RENDER.get(tier, PANEL_RENDER["not_surfaced"]))


def demote(reason: str = "conformance_violation") -> str:
    """A conformance violation that demotes a capability's rung greys the tool out
    UNTIL SESSION END (honest, not jarring — v5 §7 demotion semantics). Returns the
    'demoted' tier; the panel renders it visible-but-disabled with a 'demoted' badge."""
    return "demoted"


def on_bridge_drop(tier: str) -> str:
    """Mid-session bridge drop: a live-verified capability backgrounds to the
    caveat tier (V1-degraded semantics) rather than vanishing — the caveat travels
    with the offer. A foreground/available tool degrades; lower tiers are unchanged."""
    if tier in ("foreground", "available"):
        return "surfaced_caveat"
    return tier
