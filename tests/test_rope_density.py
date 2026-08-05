"""L5-18 — density is a manifest lever (airy / standard / tight): the plumbing.

The second profile axis: each manifest declares ONE panel-wide density in its
defaults, the compositor lifts it out of the fold and stamps it on the panel
root as a Qt dynamic property, and the stylesheet keys airy/tight descendant
rules on that property. Standard is the unstyled baseline ON PURPOSE — expert
== v5.42.0 exactly (L5-5), so NO rule may exist for it.

Headless by design: manifests, ``compositor.resolve`` and ``qss`` import no Qt.
"""

import re

import pytest

from synapse.panel import compositor
from synapse.panel.designsystem import qss
from synapse.panel.manifests import (
    DENSITY_LEVELS,
    MANIFESTS,
    ManifestError,
    get_manifest,
    validate_manifest,
)

EXPECTED_DENSITY = {"curious": "airy", "expert": "standard", "ml": "tight"}


def _density_blocks(sheet, level):
    """Every QSS rule block keyed on the root's density property."""
    return re.findall(
        r'#DsRoot\[density="%s"\][^{}]*\{[^{}]*\}' % level, sheet
    )


class TestManifestDensity:
    def test_levels_are_the_contract(self):
        assert DENSITY_LEVELS == ("airy", "standard", "tight")

    def test_each_manifest_declares_expected_density(self):
        for profile, expected in EXPECTED_DENSITY.items():
            assert MANIFESTS[profile]["defaults"]["density"] == expected, (
                "manifest %r must declare density %r" % (profile, expected)
            )

    def test_declared_manifests_validate_clean(self):
        for profile in EXPECTED_DENSITY:
            assert validate_manifest(MANIFESTS[profile]) == []

    def test_absent_density_defaults_to_standard(self):
        manifest = get_manifest("expert")
        del manifest["defaults"]["density"]
        assert validate_manifest(manifest) == []
        assert compositor.resolve(manifest)["density"] == "standard"

    def test_invalid_density_raises_manifest_error(self):
        manifest = get_manifest("expert")
        manifest["defaults"]["density"] = "cozy"
        with pytest.raises(ManifestError):
            compositor.resolve(manifest)

    def test_non_string_density_raises_manifest_error(self):
        manifest = get_manifest("expert")
        manifest["defaults"]["density"] = True
        with pytest.raises(ManifestError):
            compositor.resolve(manifest)

    def test_density_is_defaults_only_never_a_spec_key(self):
        # Per-widget / per-region density is a schema breach — ONE systemic
        # decision, not per-widget fiddling.
        manifest = get_manifest("expert")
        manifest["regions"][0]["density"] = "airy"
        assert any("density" in p for p in validate_manifest(manifest))

    def test_density_never_folds_into_regions_or_widgets(self):
        for profile in EXPECTED_DENSITY:
            resolved = compositor.resolve(get_manifest(profile))
            assert resolved["density"] == EXPECTED_DENSITY[profile]
            assert "density" not in resolved["defaults"]
            for region in resolved["regions"]:
                assert "density" not in region
                for spec in region["widgets"]:
                    assert "density" not in spec


class TestDensityStylesheet:
    def test_airy_and_tight_rules_exist_and_differ(self):
        sheet = qss.stylesheet()
        airy = _density_blocks(sheet, "airy")
        tight = _density_blocks(sheet, "tight")
        assert airy, "no airy density rules in the stylesheet"
        assert tight, "no tight density rules in the stylesheet"
        assert "\n".join(airy) != "\n".join(tight)

    def test_no_rule_for_standard(self):
        # THE PIN (L5-5): standard IS the unstyled baseline — the sheet may
        # not even mention it, so expert renders v5.42.0 exactly.
        assert 'density="standard"' not in qss.stylesheet()

    def test_density_rules_step_spacing_only(self):
        # The lever moves rhythm and nothing else: every declaration inside a
        # density block is padding/margin — no colour, size, weight, font,
        # radius or border.
        sheet = qss.stylesheet()
        blocks = _density_blocks(sheet, "airy") + _density_blocks(sheet, "tight")
        for block in blocks:
            body = block[block.index("{") + 1:block.rindex("}")]
            for decl in filter(None, (d.strip() for d in body.split(";"))):
                prop = decl.split(":", 1)[0].strip()
                assert prop.startswith(("padding", "margin")), (
                    "density rule carries a non-spacing property: %r" % decl
                )
