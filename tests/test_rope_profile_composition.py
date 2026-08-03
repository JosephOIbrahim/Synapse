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
        assert set(_widgets(plan)) == set(compositor.known_widget_ids())


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
    def test_curious_collapses_at_least_one_widget(self):
        collapsed = {
            wid for wid, spec in _widgets(_plan(curious.MANIFEST)).items()
            if spec["collapsed"]
        }
        assert collapsed, "curious must fold at least one readout"

    def test_collapsed_readouts_stay_present_and_reachable(self):
        """Collapsed widgets remain in the plan (visible=True, height-folded)
        and the TOKEN pill — the one-click path to the full numbers — is
        itself neither collapsed nor hidden."""
        widgets = _widgets(_plan(curious.MANIFEST))
        for wid, spec in widgets.items():
            if spec["collapsed"]:
                assert spec["visible"] is True, wid
        token_pill = widgets["token_pill"]
        assert token_pill["visible"] is True
        assert token_pill["collapsed"] is False


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
        for wid in ("author_token", "token_meter", "token_pill"):
            assert widgets[wid]["visible"] is True, wid
            assert widgets[wid]["collapsed"] is False, wid
            assert widgets[wid]["prominence"] == "hero", wid
