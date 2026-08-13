"""Tests for the Karma progressive render presets (W1-KPRE).

Pure-data tests over ``synapse.core.render_presets`` -- no ``hou`` import, so
they run on stock CI runners (the AST detector never marks this module
``needs_houdini``; mirrors ``tests/test_render_constants.py``).

Each test class maps to a W1-KPRE acceptance predicate:
  * TestPresetTable            -> presets set samples/resolution/denoise/engine
                                  per the addendum table                 [test]
  * TestProbeVerifiedNames     -> only probe-verified 22.0.400 parm names ship
                                  (reflectlimit/refractlimit/denoisemode are
                                  phantom and must NOT appear)            [probe]
  * TestBackgroundPolicy       -> quality+ background; layout/lighting fg [test]
  * TestXpuFlushNote           -> XPU flush-delay note travels with surface[check]
  * TestAdditiveAndCrucible    -> no smuggled camera/node path; resolver order
"""

import sys
from pathlib import Path

import pytest

# Ensure the worktree's python/ package dir wins even when run standalone.
# (Under pytest, pyproject's pythonpath=["python"] already covers this.)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.core.render_presets import (  # noqa: E402
    PROBED_BUILD,
    XPU_FLUSH_DELAY_NOTE,
    PARM_NAMES,
    ENGINE_TOKENS,
    DENOISE_TOKENS,
    PROBE_VERIFIED_PARM_NAMES,
    PROGRESSIVE_PRESETS,
    PRESET_ORDER,
    BOUNCE_BASELINE,
    get_preset,
    list_presets,
    preset_parm_overrides,
    resolve_stage_chain,
)


class TestPresetTable:
    """Acceptance #1 -- presets set pathtracedsamples/resolution/denoise/engine
    per the addendum 2.2 progressive-pipeline table (+ 2.1/2.3 policy)."""

    def test_four_named_presets_in_order(self):
        assert PRESET_ORDER == ("layout", "lighting", "quality", "final")
        assert set(PROGRESSIVE_PRESETS) == set(PRESET_ORDER)
        assert list_presets() == list(PRESET_ORDER)

    def test_order_field_ascends(self):
        orders = [PROGRESSIVE_PRESETS[n]["order"] for n in PRESET_ORDER]
        assert orders == [1, 2, 3, 4]

    def test_layout(self):
        p = get_preset("layout")
        assert p["resolution"] == (320, 240)
        assert p["pixel_samples"] == 4
        assert p["denoise"] == "off"
        assert p["engine"] == "xpu"

    def test_lighting(self):
        p = get_preset("lighting")
        assert p["resolution"] == (960, 540)
        assert 16 <= p["pixel_samples"] <= 32          # addendum band
        assert p["pixel_samples_range"] == (16, 32)
        assert p["denoise"] == "oidn"
        assert p["engine"] == "xpu"

    def test_quality(self):
        p = get_preset("quality")
        assert p["resolution"] == (1920, 1080)
        assert p["pixel_samples"] == 64
        assert p["denoise"] == "oidn"
        assert p["engine"] == "xpu"

    def test_final(self):
        p = get_preset("final")
        w, h = p["resolution"]
        assert w >= 1920 and h >= 1080                 # addendum "1920x1080+"
        assert 128 <= p["pixel_samples"] <= 512        # addendum band
        assert p["pixel_samples_range"] == (128, 512)
        assert p["denoise"] == "off"                   # hero finals render clean
        assert p["engine"] == "cpu"                    # reference quality

    def test_every_preset_declares_the_four_axes(self):
        for name in PRESET_ORDER:
            p = get_preset(name)
            assert isinstance(p["pixel_samples"], int) and p["pixel_samples"] > 0
            assert len(p["resolution"]) == 2
            assert p["denoise"] in DENOISE_TOKENS
            assert p["engine"] in ENGINE_TOKENS

    def test_get_preset_unknown_raises(self):
        with pytest.raises(KeyError):
            get_preset("hero")


class TestProbeVerifiedNames:
    """Acceptance #2 -- only names confirmed on the live 22.0.400 build ship.
    The three docs-only names the probe caught are phantom and must be absent."""

    def test_probed_build_is_22_0_400(self):
        assert PROBED_BUILD == "22.0.400"

    def test_canonical_parm_names(self):
        assert PARM_NAMES["pixel_samples"] == "pathtracedsamples"
        assert PARM_NAMES["engine"] == "engine"
        assert PARM_NAMES["denoise"] == "denoiser"
        assert PARM_NAMES["background"] == "soho_foreground"
        assert PARM_NAMES["xform_samples"] == "xformsamples"
        assert PARM_NAMES["geo_samples"] == "geosamples"

    def test_bounce_names_are_the_real_ones_not_the_phantoms(self):
        # The addendum prose said reflectlimit/refractlimit -- both PHANTOM.
        assert PARM_NAMES["reflection_limit"] == "reflectionlimit"
        assert PARM_NAMES["refraction_limit"] == "refractionlimit"
        assert PARM_NAMES["diffuse_limit"] == "diffuselimit"
        assert PARM_NAMES["volume_limit"] == "volumelimit"
        assert PARM_NAMES["sss_limit"] == "ssslimit"

    def test_phantom_names_never_appear_anywhere(self):
        phantoms = {"reflectlimit", "refractlimit", "denoisemode"}
        # not in the name map...
        assert phantoms.isdisjoint(set(PARM_NAMES.values()))
        # ...and not in any emitted override, for any preset.
        for name in PRESET_ORDER:
            assert phantoms.isdisjoint(set(preset_parm_overrides(name)))

    def test_overrides_only_use_probe_verified_names(self):
        for name in PRESET_ORDER:
            keys = set(preset_parm_overrides(name))
            unverified = keys - PROBE_VERIFIED_PARM_NAMES
            assert not unverified, f"{name}: un-probed parm names {unverified}"

    def test_engine_and_denoise_values_are_valid_menu_tokens(self):
        for name in PRESET_ORDER:
            ov = preset_parm_overrides(name)
            assert ov["engine"] in ENGINE_TOKENS
            assert ov["denoiser"] in DENOISE_TOKENS

    def test_overrides_carry_samples_and_bounces(self):
        ov = preset_parm_overrides("quality")
        assert ov["pathtracedsamples"] == 64
        for logical, val in BOUNCE_BASELINE.items():
            assert ov[PARM_NAMES[logical]] == val


class TestBackgroundPolicy:
    """Acceptance #3 -- quality and final render in background; layout and
    lighting stay foreground. soho_foreground polarity: 1=fg, 0=bg."""

    def test_background_flags(self):
        assert get_preset("layout")["background"] is False
        assert get_preset("lighting")["background"] is False
        assert get_preset("quality")["background"] is True
        assert get_preset("final")["background"] is True

    def test_soho_foreground_override_polarity(self):
        # foreground stages set soho_foreground=1, background stages set 0
        assert preset_parm_overrides("layout")["soho_foreground"] == 1
        assert preset_parm_overrides("lighting")["soho_foreground"] == 1
        assert preset_parm_overrides("quality")["soho_foreground"] == 0
        assert preset_parm_overrides("final")["soho_foreground"] == 0

    def test_only_quality_plus_are_background(self):
        bg = [n for n in PRESET_ORDER if get_preset(n)["background"]]
        assert bg == ["quality", "final"]


class TestXpuFlushNote:
    """Acceptance #4 -- the XPU flush-delay note travels with the preset
    surface (10-15s post-render() is not a hang)."""

    def test_note_content(self):
        note = XPU_FLUSH_DELAY_NOTE.lower()
        assert "10-15" in note or "10-15s" in note
        assert "flush" in note
        assert "not a hang" in note


class TestAdditiveAndCrucible:
    """Crucible criteria -- no smuggled camera/node path; resolver ordering."""

    def test_no_camera_key_smuggled(self):
        # Camera on usdrender is a USD prim path the artist owns; presets must
        # never carry one.
        for name in PRESET_ORDER:
            ov = preset_parm_overrides(name)
            assert "camera" not in ov
            assert "override_camera" not in ov

    def test_no_override_value_looks_like_a_node_path(self):
        for name in PRESET_ORDER:
            for val in preset_parm_overrides(name).values():
                if isinstance(val, str):
                    assert not val.startswith("/"), f"{name}: node-path-shaped value {val!r}"

    def test_resolve_stage_chain_default_is_full_ordered(self):
        chain = resolve_stage_chain(None)
        assert [n for n, _ in chain] == list(PRESET_ORDER)

    def test_resolve_stage_chain_reorders_to_canonical(self):
        chain = resolve_stage_chain(["final", "layout"])
        assert [n for n, _ in chain] == ["layout", "final"]

    def test_resolve_stage_chain_accepts_single_string(self):
        chain = resolve_stage_chain("quality")
        assert [n for n, _ in chain] == ["quality"]

    def test_resolve_stage_chain_unknown_raises(self):
        with pytest.raises(KeyError):
            resolve_stage_chain(["layout", "bogus"])
