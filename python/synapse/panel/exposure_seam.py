"""Panel seam for the exposure projection (v5 §8) — where the harness meets the panel.

The panel's tool/affordance visibility is a RENDER of the provenance→exposure
projection, never a hand-authored list: a tool drops out when its rung falls
(a conformance violation demotes it) and foregrounds when a V1_output Confirmation
lands. Both recipe families (``routing/recipes`` and ``panel/recipe_book``) read
through :func:`tool_exposure`.

This module is the thin, pure seam (no PySide, no Houdini). The capability→rung
**Ledger reader** (loading the per-record files into the records this takes) is the
deferred plumbing the RFC §4 flags — until it lands, callers pass the records they
have. Exposure stays DERIVED (compute-on-read), never stored (Ledger violation #7).
"""

from __future__ import annotations

from synapse.science.exposure import tier_for, panel_visibility


def tool_exposure(tool_name: str, ledger_records) -> dict:
    """Render spec for one tool: its exposure tier (DERIVED from the Ledger) folded
    with the panel render map. Returns ``{tool, tier, visible, enabled, badge,
    foreground}``. The panel shows the tool iff ``visible``; greys it iff not
    ``enabled``; badges/foregrounds per the tier."""
    tier = tier_for(tool_name, ledger_records)
    return {"tool": tool_name, "tier": tier, **panel_visibility(tier)}


def visible_tools(tool_names, ledger_records) -> list:
    """The tools the panel should SURFACE (visible), each with its render spec —
    a render of the projection over a tool list, not a hand-curated subset."""
    specs = (tool_exposure(name, ledger_records) for name in tool_names)
    return [s for s in specs if s["visible"]]
