"""Rope L5-6 — composition-only Curious pin (Law L5).

Curious must be the expert surface exactly, re-paced: same regions, same
widgets, same order, everything visible and collapsed only where
declared — capability identical — with the entire diff confined to
presentation defaults (widget prominence and collapse) and the
system-prompt overlay. The behaviors that have no widget
in the compositor's vocabulary (error translation, decision narration, quick
actions, recipes, /explain, confirm-on-destructive, jargon) must ride the
overlay, because composition-only means no new widgets. Pure data through
``compositor.resolve``; no Qt.
"""

import copy
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from synapse.panel import compositor
from synapse.panel.manifests import get_manifest, validate_manifest

# The complete allowed diff vs expert, besides profile name + overlay:
# (region id, widget id) -> (expert prominence, curious prominence).
# Re-pinned after the L5-15..L5-23 seat pass: connect, corpus and
# palette_hint no longer carry a Curious-only prominence (L5-23 gives them
# the same button treatment in every profile), and activity_meter joins
# token_meter as quiet alongside its L5-19 fold.
EXPECTED_PROMINENCE_DELTAS = {
    ("rail", "token_meter"): ("standard", "quiet"),
    ("rail", "activity_meter"): ("standard", "quiet"),
    ("mode_bar", "token_pill"): ("standard", "quiet"),
}

# The complete allowed collapse diff vs expert (the L5-19 economics and
# telemetry folds). Collapsed means present in the layout at zero height,
# never withheld: `visible` stays strict below. A new fold must be added
# here deliberately, never smuggled.
EXPECTED_COLLAPSE_DELTAS = {
    ("rail", "token_meter"),
    ("rail", "activity_meter"),
}

# L5-18: density is a manifest lever (airy / standard / tight) resolved at
# the top of the plan. Padding is presentation, not capability, so the
# delta is allowed — but declared here, as (expert, curious), so a new one
# cannot arrive silently.
EXPECTED_DENSITY_DELTA = ("standard", "airy")

# One marker per composition-only behavior the task names; each must be
# carried by the overlay because no widget exists for it.
OVERLAY_MARKERS = (
    "breaks",                   # error_translator always-on: the overlay
                                # carries this as "when something breaks",
                                # in the plain prose the behavior asks for
    "plain language",
    "decision",                 # decision_log narration inline
    "inline",
    "quick actions",            # quick_actions expanded
    "recipe",                   # recipe_book promoted
    "/explain",                 # /explain suggested post-build
    "confirm",                  # confirm-on-destructive
    "destructive",
    "jargon",                   # jargon overlay
    "capability is unchanged",  # L5: the overlay never downscales
)


def _resolved(name):
    return compositor.resolve(get_manifest(name))


def test_curious_validates_and_uses_existing_widgets_only():
    manifest = get_manifest("curious")
    assert validate_manifest(manifest) == []
    known = compositor.known_widget_ids()
    manifest_ids = [
        entry if isinstance(entry, str) else entry["id"]
        for region in manifest["regions"] for entry in region["widgets"]
    ]
    unknown = [wid for wid in manifest_ids if wid not in known]
    assert unknown == [], "composition-only broken, new widgets: %r" % unknown
    # And resolve drops nothing — every declared entry survives, in order.
    resolved_ids = [
        w["id"] for r in _resolved("curious")["regions"] for w in r["widgets"]
    ]
    assert resolved_ids == manifest_ids


def test_capability_surface_identical_to_expert():
    curious, expert = _resolved("curious"), _resolved("expert")
    assert [r["id"] for r in curious["regions"]] == [
        r["id"] for r in expert["regions"]]
    assert {r["id"]: [w["id"] for w in r["widgets"]]
            for r in curious["regions"]} == {
        r["id"]: [w["id"] for w in r["widgets"]]
        for r in expert["regions"]}
    assert curious["defaults"] == expert["defaults"]
    collapsed = set()
    for region in curious["regions"]:
        for spec in region["widgets"]:
            assert spec["visible"] is True     # nothing withheld
            if spec["collapsed"]:
                collapsed.add((region["id"], spec["id"]))
    # Folding is pacing, not capability: a collapsed widget is present at
    # zero height, one click away, never removed. Only declared folds may
    # collapse; an undeclared one fails here.
    assert collapsed == EXPECTED_COLLAPSE_DELTAS


def _prominence_stripped(plan):
    """The resolved plan minus everything a profile is ALLOWED to change:
    widget prominence, declared collapse, density, the overlay, and the
    profile name itself. Region prominence and the defaults block stay
    in — they must not drift."""
    plan = copy.deepcopy(plan)
    plan["profile"] = None
    plan["system_prompt_overlay"] = None
    plan["density"] = None
    for region in plan["regions"]:
        for spec in region["widgets"]:
            spec["prominence"] = None
            # Declared folds are an allowed presentation diff. Undeclared
            # ones are caught strictly in the capability test above.
            if (region["id"], spec["id"]) in EXPECTED_COLLAPSE_DELTAS:
                spec["collapsed"] = None
    return plan


def test_diff_vs_expert_touches_only_presentation_defaults():
    curious, expert = _resolved("curious"), _resolved("expert")
    # Recursive equality of everything outside the allowed diff: order,
    # visibility, collapse, stretch, builders, defaults, region prominence.
    assert _prominence_stripped(curious) == _prominence_stripped(expert)
    # Density is stripped above because it is an allowed lever; the value
    # it may take is pinned here so a silent change still fails.
    assert (expert["density"], curious["density"]) == EXPECTED_DENSITY_DELTA
    # And the widget-prominence diff is EXACTLY the declared set — a new
    # delta must be added here deliberately, never smuggled.
    deltas = {}
    for c_region, e_region in zip(curious["regions"], expert["regions"]):
        for c, e in zip(c_region["widgets"], e_region["widgets"]):
            if c["prominence"] != e["prominence"]:
                deltas[(c_region["id"], c["id"])] = (
                    e["prominence"], c["prominence"])
    assert deltas == EXPECTED_PROMINENCE_DELTAS


def test_overlay_carries_the_widgetless_behaviors():
    overlay = get_manifest("curious")["system_prompt_overlay"]
    assert overlay  # curious re-paces; expert's overlay stays empty (L5-5)
    lowered = overlay.lower()
    missing = [m for m in OVERLAY_MARKERS if m not in lowered]
    assert missing == [], "overlay lost behaviors: %r" % missing
