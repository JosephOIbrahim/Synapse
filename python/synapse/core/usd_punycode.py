"""
Single-source registry of Houdini USD/Karma punycode parameter encodings.

In Houdini 21.0.671, UsdLux/Karma light parameters surface in the parm
interface under punycode-encoded names — e.g. ``inputs:color`` becomes
``xn__inputscolor_zta``. These encodings are *runtime-specific*: SideFX
regenerates them whenever the bundled OpenUSD version moves, so this map MUST
be re-verified on a USD bump (H22).

Every value below was **live-probed** off a real ``domelight::3.0`` on
21.0.671 (2026-06-26) — walk ``node.parmTuples()`` / ``node.parms()`` and read
the names back. The probe is the only trustworthy source: the encodings are
deterministic *per full property-name string* but are **not guessable** and DO
drift between builds. A prior hand-maintained copy of this map had 9 of ~14
entries phantom (``color``=``_kya``, ``diffuse``=``_vya``, ``specular``=``_i0a``,
``normalize``=``_01a``, ``color_temperature`` lowercased, ``texture_*`` wrong) —
that is exactly the failure this single-source module exists to prevent.
Ground truth: ``harness/notes/verified_usdlux_encodings_21.0.671.json``.

This module is the ONE place these literals are allowed to live. ``aliases.py``
and every other caller references :data:`PUNYCODE_PARMS` / :func:`encoded`
instead of pasting the strings, so the encodings can never diverge between
files again. On the next USD bump, **re-probe** (the drop-day probe harness,
task 0.2, auto-produces this map) rather than hand-editing.
"""

from typing import Dict, FrozenSet, Optional


# alias -> H21.0.671 punycode-encoded parm name (all live-probed off domelight::3.0)
PUNYCODE_PARMS: Dict[str, str] = {
    # Lights — scalars
    "intensity": "xn__inputsintensity_i0a",
    "exposure": "xn__inputsexposure_vya",
    "diffuse": "xn__inputsdiffuse_8wa",
    "specular": "xn__inputsspecular_vya",
    "normalize": "xn__inputsnormalize_i0a",
    "angle": "xn__inputsangle_zta",
    "color_temperature": "xn__inputscolorTemperature_wcb",
    "enable_temperature": "xn__inputsenableColorTemperature_omb",
    # Lights — scalar "control" companions (per-attr override toggles)
    "intensity_control": "xn__inputsintensity_control_jeb",
    "exposure_control": "xn__inputsexposure_control_wcb",
    "diffuse_control": "xn__inputsdiffuse_control_99a",
    "specular_control": "xn__inputsspecular_control_wcb",
    "normalize_control": "xn__inputsnormalize_control_jeb",
    "color_control": "xn__inputscolor_control_06a",
    "color_temperature_control": "xn__inputscolorTemperature_control_xpb",
    # Lights — color3f TUPLES. Value is the parmTuple BASE name; callers must
    # resolve via node.parmTuple(base), not node.parm(base) (which returns None
    # for a tuple). See TUPLE_ALIASES and the handler parmTuple fallback.
    "color": "xn__inputscolor_zta",          # components: _ztar/_ztag/_ztab
    "shadow_color": "xn__inputsshadowcolor_r3ag",  # _r3agr/_r3agg/_r3agb
    # DomeLight — HDRI texture
    "texture_file": "xn__inputstexturefile_r3ah",
    "texture_file_control": "xn__inputstexturefile_control_shbh",
    "texture_format": "xn__inputstextureformat_06ah",
    # ------------------------------------------------------------------
    # UNVERIFIED — camera attrs. NOT probe-confirmed (could not instance a
    # camera prim this pass). These are almost certainly WRONG as written:
    # standard UsdGeomCamera attributes (focalLength, fStop, focusDistance,
    # horizontalAperture, verticalAperture, clippingRange) are NOT in the
    # ``inputs:`` namespace, so they are NOT punycode-encoded at all — the
    # real parm names are the plain camelCase attrs. Kept ONLY so callers that
    # reference these alias keys still import; re-probe a real camera prim and
    # correct (or drop these in favour of the plain attr names) on H22.
    "focal_length": "xn__inputsfocallength_e4b",
    "focus_distance": "xn__inputsfocusdistance_f7b",
    "fstop": "xn__inputsfstop_vya",
    "horizontal_aperture": "xn__inputshorizontalaperture_ohb",
    "vertical_aperture": "xn__inputsverticalaperture_gfb",
    "clipping_range": "xn__inputsclippingrange_e4b",
}


# Aliases whose encoded value is a parmTuple BASE (color3f), not a scalar parm.
# The set/get-parm handlers try node.parmTuple(encoded) for these.
TUPLE_ALIASES: FrozenSet[str] = frozenset({"color", "light_color", "shadow_color"})


def encoded(alias: str) -> Optional[str]:
    """Return the punycode-encoded parm name for a friendly ``alias``.

    Returns ``None`` if the alias is unknown. Pure function over a static
    dict — no determinism concern.
    """
    return PUNYCODE_PARMS.get(alias)
