"""BP2-PANELDESIGN — the sec.7 rhythm pass, headless.

Pins the spacing pass end to end without Qt:
  - the SPACE_* scale is the sec.7 4-pt grid (4·8·12·16·24·32·48), existing
    rungs unchanged, three stops added, never renamed;
  - the gap() helper steps a base by the density multiplier (airy ×1.5 /
    standard ×1 / tight ×0.75), integer px;
  - the QSS emits, for each REACHABLE camera region, density-keyed `margin`
    (gap) rules whose value == gap(base, level) — i.e. gap tokens step by the
    density multipliers PER PROFILE (curious→airy, expert→standard, ml→tight);
  - the guardrails hold: no `density="standard"` rule, density blocks are
    margin/padding-only, no new colour, and the Expert manifest pin is intact.

Docs: docs/PANEL_RHYTHM_SPEC.md. Sibling density plumbing: tests/test_rope_density.py.
"""

import re

from synapse.panel import compositor
from synapse.panel.manifests import get_manifest
from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import qss

# The one place profile → density is wired (manifests/*.py defaults).
PROFILE_DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}

# The reachable camera regions this leg lands in QSS, and the sec.7 gap BASE
# each one's group-gap margin scales from. (Region 3 recall card is greenfield
# and Region 4 token-face rows are inline-styled with no objectNames — neither
# is QSS-reachable this leg; see the spec §5 ledger.)
REGION_GAP_BASE = {
    "DsTabRow": t.SPACE_MD,   # Region 1 — profile tab strip, group gap below
    "DsVerb":   t.SPACE_SM,   # Region 2 — verb rail, group vertical breathing
    "DsHeader": t.SPACE_SM,   # Region 5 — .hip ribbon + header, group gap below
}


class TestSpaceGrid:
    def test_grid_is_the_sec7_4pt_ladder(self):
        assert t.SPACE_GRID == (4, 8, 12, 16, 24, 32, 48)

    def test_existing_rungs_unchanged_never_renamed(self):
        # Heavy consumers (SM ×44 / XS ×25 / MD ×23 / LG ×9). Frozen.
        assert (t.SPACE_XS, t.SPACE_SM, t.SPACE_MD, t.SPACE_LG, t.SPACE_XL) == (
            4, 8, 16, 24, 40)

    def test_three_new_stops_added(self):
        assert (t.SPACE_12, t.SPACE_32, t.SPACE_48) == (12, 32, 48)

    def test_sec7_fixed_dims(self):
        assert t.ROW_MIN_H == 44
        assert t.RADIUS_CARD == 10
        assert t.RADIUS_ROUND == 999


class TestGapMultiplier:
    def test_scale_table_is_sec7(self):
        assert t.DENSITY_GAP_SCALE == {"airy": 1.5, "standard": 1.0, "tight": 0.75}

    def test_standard_is_identity(self):
        for base in t.SPACE_GRID:
            assert t.gap(base, "standard") == base

    def test_airy_and_tight_step_every_rung(self):
        # base -> (tight ×0.75, airy ×1.5); every rung is a ×4 multiple so the
        # stepped value is an exact integer.
        expected = {4: (3, 6), 8: (6, 12), 12: (9, 18), 16: (12, 24),
                    24: (18, 36), 32: (24, 48), 48: (36, 72)}
        for base, (tight, airy) in expected.items():
            assert t.gap(base, "tight") == tight, base
            assert t.gap(base, "airy") == airy, base

    def test_returns_integer_px(self):
        for base in t.SPACE_GRID:
            for level in ("airy", "standard", "tight"):
                assert isinstance(t.gap(base, level), int)

    def test_unknown_density_never_inverts_the_rhythm(self):
        # A malformed manifest resolves to ×1, never a negative or an inversion.
        assert t.gap(t.SPACE_LG, "cozy") == t.SPACE_LG


def _region_density_margins(sheet, level, object_name):
    """Every `margin*` value declared in the density block(s) for a widget whose
    selector contains ``object_name``. Filters out non-margin declarations so
    the prior-wave PADDING density rules (fixed, out of scope) do not pollute."""
    blocks = re.findall(
        r'#DsRoot\[density="%s"\][^{}]*%s[^{}]*\{[^{}]*\}'
        % (level, re.escape(object_name)), sheet)
    margins = {}
    for b in blocks:
        body = b[b.index("{") + 1:b.rindex("}")]
        for decl in filter(None, (d.strip() for d in body.split(";"))):
            key, _, val = decl.partition(":")
            key = key.strip()
            if key.startswith("margin"):
                margins[key] = val.strip()
    return margins


class TestRegionRhythmStepsByDensity:
    def test_each_reachable_region_gap_steps_by_the_multiplier(self):
        sheet = qss.stylesheet()
        for object_name, base in REGION_GAP_BASE.items():
            airy = _region_density_margins(sheet, "airy", object_name)
            tight = _region_density_margins(sheet, "tight", object_name)
            assert airy, "no airy margin rule for #%s" % object_name
            assert tight, "no tight margin rule for #%s" % object_name
            for key, val in airy.items():
                assert val == "%dpx" % t.gap(base, "airy"), (object_name, key, val)
            for key, val in tight.items():
                assert val == "%dpx" % t.gap(base, "tight"), (object_name, key, val)

    def test_per_profile_density_selects_the_multiplier(self):
        # curious→airy(×1.5), expert→standard(×1), ml→tight(×0.75) — the density
        # each profile resolves to is the multiplier its gaps step by.
        for profile, density in PROFILE_DENSITY.items():
            resolved = compositor.resolve(get_manifest(profile))
            assert resolved["density"] == density, profile
            # the tab-strip gap the panel would render for this profile:
            base = REGION_GAP_BASE["DsTabRow"]
            assert t.gap(base, density) == round(
                base * t.DENSITY_GAP_SCALE[density])

    def test_airy_is_looser_than_tight_for_every_region(self):
        sheet = qss.stylesheet()
        for object_name, base in REGION_GAP_BASE.items():
            assert t.gap(base, "airy") > t.gap(base, "tight")
            airy = set(_region_density_margins(sheet, "airy", object_name).values())
            tight = set(_region_density_margins(sheet, "tight", object_name).values())
            assert airy and tight and airy != tight, object_name


class TestGuardrails:
    def test_no_standard_density_rule_in_the_sheet(self):
        # The pin (L5-5): standard is the unstyled baseline — the sheet, comments
        # included, may not carry a standard density block.
        assert 'density="standard"' not in qss.stylesheet()

    def test_density_blocks_are_spacing_only(self):
        # Reinforces test_rope_density across the whole sheet after this pass.
        sheet = qss.stylesheet()
        blocks = re.findall(
            r'#DsRoot\[density="(?:airy|tight)"\][^{}]*\{[^{}]*\}', sheet)
        for b in blocks:
            body = b[b.index("{") + 1:b.rindex("}")]
            for decl in filter(None, (d.strip() for d in body.split(";"))):
                prop = decl.split(":", 1)[0].strip()
                assert prop.startswith(("padding", "margin")), decl

    def test_region_rhythm_introduces_no_hex(self):
        # sec.7 adds rhythm, not colour. The whole rhythm block (base + density
        # margin rules) carries no raw hex — every value is a px integer.
        sheet = qss.stylesheet()
        block = sheet[sheet.index("sec.7 five-camera-region"):
                      sheet.index("---- progress")]
        assert re.search(r'#[0-9a-fA-F]{6}', block) is None

    def test_expert_manifest_pin_intact(self):
        # The rhythm pass touches NO manifest. Expert still resolves to the
        # v5.42.0 structure at standard density (the real pin is
        # test_rope_expert_pin; this is a fast local guard).
        resolved = compositor.resolve(get_manifest("expert"))
        assert resolved["density"] == "standard"
        assert [r["id"] for r in resolved["regions"]] == [
            "rail", "context_ribbon", "mode_bar", "faces"]
