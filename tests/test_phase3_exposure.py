"""Track C · Phase 3 — the provenance→exposure projection (v5 §8). Pure, CI tier.

Pins the runbook verify list: each rung → the correct tier; a demotion re-renders
(greyed/disabled); a V1_output Confirmation foregrounds the tool; authoring a tier
FAILS (derived-only, no store API — Ledger violation #7). Plus the capability→rung
join, legacy-rung migration through exposure, and the bridge-drop backgrounding.
"""

from dataclasses import dataclass, field
from typing import Dict

from synapse.science import exposure
from synapse.science.exposure import (
    highest_tier, tier_for, panel_visibility, demote, on_bridge_drop,
    TIER_FOR_RUNG, RUNG_ORDER,
)


# ── each rung → the correct tier ─────────────────────────────────────────────

def test_tier_map_conformance():
    # crucible strengthening: every rung maps to a tier that exists in the strength
    # order (else highest_tier's max() would KeyError on a future rung addition),
    # and every solid rung has a tier.
    from synapse.science.exposure import TIER_FOR_RUNG, TIER_STRENGTH, RUNG_ORDER
    assert set(TIER_FOR_RUNG.values()) <= set(TIER_STRENGTH), \
        "a rung maps to a tier missing from TIER_STRENGTH → highest_tier would KeyError"
    assert set(RUNG_ORDER) <= set(TIER_FOR_RUNG), "a solid rung has no tier mapping"


def test_each_rung_maps_to_its_tier():
    assert highest_tier(["doc_only"]) == "not_surfaced"
    assert highest_tier(["V0_membership"]) == "surfaced_unverified"
    assert highest_tier(["V1_cook"]) == "available"
    assert highest_tier(["V1_output"]) == "foreground"
    assert highest_tier(["V1-degraded"]) == "surfaced_caveat"
    assert highest_tier([]) == "not_surfaced"


def test_highest_solid_rung_wins():
    assert highest_tier(["doc_only", "V0_membership", "V1_cook"]) == "available"
    assert highest_tier(["V1_cook", "V1_output", "V0_membership"]) == "foreground"
    # V1-degraded only surfaces-with-caveat when no solid rung beats it
    assert highest_tier(["V1-degraded", "V1_output"]) == "foreground"
    assert highest_tier(["V1-degraded", "doc_only"]) == "surfaced_caveat"


def test_legacy_rung_migrates_through_exposure():
    # a record still carrying legacy "V1" projects to V1_cook → available
    assert highest_tier(["V1"]) == "available"
    assert highest_tier(["V0 (citation self-check)"]) == "surfaced_unverified"  # annotated


# ── panel render seam ────────────────────────────────────────────────────────

def test_panel_visibility_per_tier():
    assert panel_visibility("not_surfaced")["visible"] is False
    assert panel_visibility("surfaced_unverified") == {
        "visible": True, "enabled": True, "badge": "unverified", "foreground": False}
    assert panel_visibility("available")["enabled"] is True
    fg = panel_visibility("foreground")
    assert fg["foreground"] is True and fg["badge"] == "trusted"
    assert panel_visibility("surfaced_caveat")["badge"] == "degraded"
    # a copy, not the shared dict (the panel must not mutate the projection)
    assert panel_visibility("available") is not exposure.PANEL_RENDER["available"]


def test_v1_output_confirmation_foregrounds_the_tool():
    # the runbook check: a V1_output Confirmation foregrounds the capability
    recs = [_rec("cops_opencl", "V1_output")]
    assert tier_for("cops_opencl", recs) == "foreground"
    assert panel_visibility(tier_for("cops_opencl", recs))["foreground"] is True


def test_demotion_re_renders_greyed():
    # the runbook check: a demotion re-renders the panel (visible but disabled)
    v = panel_visibility(demote("conformance_violation"))
    assert v["visible"] is True and v["enabled"] is False and v["badge"] == "demoted"


def test_bridge_drop_backgrounds_live_tiers():
    assert on_bridge_drop("foreground") == "surfaced_caveat"
    assert on_bridge_drop("available") == "surfaced_caveat"
    assert on_bridge_drop("surfaced_unverified") == "surfaced_unverified"  # unchanged


# ── the capability→rung join ─────────────────────────────────────────────────

@dataclass
class _Rec:
    verified_by: str = ""
    target: str = ""
    extra: Dict[str, str] = field(default_factory=dict)


def _rec(capability, rung, *, via="target"):
    return _Rec(verified_by=rung, target=capability if via == "target" else "",
                extra={} if via == "target" else {"capability": capability})


def test_tier_for_joins_by_target_and_extra_capability():
    recs = [
        _rec("a", "V1_cook", via="target"),
        _rec("b", "V1_output", via="extra"),
        _rec("a", "doc_only", via="target"),
    ]
    assert tier_for("a", recs) == "available"      # highest of {V1_cook, doc_only}
    assert tier_for("b", recs) == "foreground"     # joined via extra.capability
    assert tier_for("c", recs) == "not_surfaced"   # no records → not surfaced


# ── derived, never authored (Ledger violation #7) ────────────────────────────

def test_exposure_is_derived_only_no_store_api():
    # Authoring a tier must be impossible: there is NO setter/store — only compute.
    for forbidden in ("set_tier", "store_tier", "author_tier", "write_exposure", "save"):
        assert not hasattr(exposure, forbidden), f"exposure exposes an authoring path {forbidden!r}"


def test_tier_for_is_pure_idempotent():
    recs = [_rec("x", "V1_cook")]
    assert tier_for("x", recs) == tier_for("x", recs) == "available"  # same in → same out


# ── the panel seam (the harness↔panel meeting point) ─────────────────────────

def test_panel_seam_renders_projection_not_a_list():
    from synapse.panel.exposure_seam import tool_exposure, visible_tools
    recs = [
        _rec("render", "V1_output"),       # foreground
        _rec("cops_pixel_sort", "doc_only"),  # not surfaced
        _rec("inspect_stage", "V1_cook"),  # available
    ]
    fg = tool_exposure("render", recs)
    assert fg["tier"] == "foreground" and fg["foreground"] is True and fg["visible"]
    hidden = tool_exposure("cops_pixel_sort", recs)
    assert hidden["visible"] is False     # a doc_only tool is a promise, not surfaced
    names = ["render", "cops_pixel_sort", "inspect_stage", "unknown_tool"]
    surfaced = {t["tool"] for t in visible_tools(names, recs)}
    assert surfaced == {"render", "inspect_stage"}  # doc_only + unknown not surfaced
