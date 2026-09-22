"""Rope L5-19 — the composition decisions, pinned.

The first axis: what each profile folds away. Folding changes what is SHOWN,
never what the agent can DO — so these tests pin both halves: the per-profile
presentation decisions (Curious folds, ML surfaces economics, Expert is the
untouched dense baseline) and the capability invariant (the widget-id set is
identical across all three profiles; composition may reorder, fold or
re-emphasise, never remove).

Pure-data tests: manifests through ``compositor.resolve()`` only — no Qt.
"""

import pytest

from synapse.panel import compositor
from synapse.panel.manifests import curious, expert, ml

PROFILES = {
    "curious": curious.MANIFEST,
    "expert": expert.MANIFEST,
    "ml": ml.MANIFEST,
}


def _plan(manifest):
    return compositor.resolve(manifest)


def _widgets(plan):
    """Flatten a resolved plan to {widget_id: spec}."""
    out = {}
    for region in plan["regions"]:
        for spec in region["widgets"]:
            out[spec["id"]] = spec
    return out


# ---------------------------------------------------------------- resolve --

# bc-wave BC-2: the rail's token meter, palette hint, connection dot/label,
# Corpus and activity meter are HIDDEN OWNERS - constructed for their writers
# and read through the overflow, in no layout, listed by no manifest (the
# compositor applies visible=True to every listed id). Their ids stay in the
# compositor vocabulary (WIDGET_ATTRS is unchanged), so the drift check below
# is "everything known, minus exactly these".
RAIL_OVERFLOW_OWNERS = frozenset({
    "token_meter", "palette_hint", "connection_dot", "connection_label",
    "corpus", "activity_meter",
})
# Compatibility IDs stay registered, but user-requested 2026-09-22 removal
# excludes both the diagnostic and its redundant single-home switcher.
RETIRED_HOME_SWITCHES = frozenset({"chat_pill", "token_pill"})


class TestResolveCleanly:
    @pytest.mark.parametrize("name", sorted(PROFILES))
    def test_validates_and_resolves(self, name):
        manifest = PROFILES[name]
        assert compositor.validate_manifest(manifest) == []
        plan = _plan(manifest)
        assert plan["profile"] == name

    @pytest.mark.parametrize("name", sorted(PROFILES))
    def test_no_vocabulary_drift(self, name):
        """Every id a manifest names must survive into the plan.

        ``resolve()`` skip-logs unknown ids instead of raising, so a typo'd
        widget would silently vanish — this catches it: the resolved set must
        be exactly the compositor's registry, nothing dropped, nothing extra.
        """
        plan = _plan(PROFILES[name])
        assert set(_widgets(plan)) == (set(compositor.known_widget_ids())
                                      - RAIL_OVERFLOW_OWNERS - RETIRED_HOME_SWITCHES)


# ------------------------------------------------- capability invariant --

class TestCapabilityInvariant:
    def test_widget_id_set_identical_across_profiles(self):
        """L5: identical capability. Composition may reorder, fold or
        re-emphasise — never remove. The id SET available is the same in
        every profile."""
        sets = {
            name: frozenset(_widgets(_plan(m)))
            for name, m in PROFILES.items()
        }
        assert sets["curious"] == sets["expert"] == sets["ml"]

    def test_no_profile_hides_anything(self):
        """Folding is collapse (present at zero height), never visible=False.
        Nothing is withheld in any profile."""
        for name, manifest in PROFILES.items():
            for wid, spec in _widgets(_plan(manifest)).items():
                assert spec["visible"] is True, (name, wid)


# ------------------------------------------------------------- per-profile --

class TestExpertUntouched:
    def test_expert_collapses_none_and_hides_none(self):
        for wid, spec in _widgets(_plan(expert.MANIFEST)).items():
            assert spec["collapsed"] is False, wid
            assert spec["visible"] is True, wid


class TestCuriousFolds:
    def test_curious_folds_nothing_since_the_rail_chrome_left(self):
        """bc-wave BC-2: the readouts curious used to fold (token meter,
        activity meter) left the rail for the overflow in every profile, so
        there is nothing left to fold - and nothing may be smuggled back in
        as a fold. TOKEN navigation was retired on 2026-09-22."""
        collapsed = {
            wid for wid, spec in _widgets(_plan(curious.MANIFEST)).items()
            if spec["collapsed"]
        }
        assert collapsed == set(), collapsed
        assert not RETIRED_HOME_SWITCHES.intersection(_widgets(_plan(curious.MANIFEST)))

    def test_collapsed_readouts_stay_present_and_reachable(self):
        """Collapsed widgets remain in the plan; retired navigation cannot
        return disguised as a hidden or collapsed control."""
        widgets = _widgets(_plan(curious.MANIFEST))
        for wid, spec in widgets.items():
            if spec["collapsed"]:
                assert spec["visible"] is True, wid
        assert not RETIRED_HOME_SWITCHES.intersection(widgets)


class TestMLEconomics:
    def test_ml_leaves_every_widget_expert_shows_visible(self):
        expert_widgets = _widgets(_plan(expert.MANIFEST))
        ml_widgets = _widgets(_plan(ml.MANIFEST))
        for wid, spec in expert_widgets.items():
            if spec["visible"]:
                assert ml_widgets[wid]["visible"] is True, wid
                assert ml_widgets[wid]["collapsed"] is False, wid

    def test_ml_economics_read_without_a_click(self):
        """The rail readout pair carries the numbers on the always-visible
        surface: pinned visible, promoted hero (L5-19)."""
        widgets = _widgets(_plan(ml.MANIFEST))
        # bc-wave BC-2: the token meter left the rail (overflow); the model
        # token (Addendum 2) retains its emphasis after TOKEN's retirement.
        for wid in ("author_token",):
            assert widgets[wid]["visible"] is True, wid
            assert widgets[wid]["collapsed"] is False, wid
            assert widgets[wid]["prominence"] == "hero", wid
