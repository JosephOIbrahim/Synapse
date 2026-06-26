"""
Single-source registry of Houdini USD/Karma punycode parameter encodings.

In Houdini 21.0.671, UsdLux/Karma light and camera parameters surface in the
parm interface under punycode-encoded names — e.g. ``inputs:color`` becomes
``xn__inputscolor_kya``. These encodings are *runtime-specific*: SideFX
regenerates them whenever the bundled OpenUSD version moves, so this map MUST
be re-verified on a USD bump (H22). Ideally it is **probe-generated** from a
live light's parm names (create a domelight, walk ``node.parms()``) rather than
hand-maintained — the literals below were transcribed by hand and drift.

This module is the ONE place these literals are allowed to live. ``aliases.py``
and every other caller references :data:`PUNYCODE_PARMS` / :func:`encoded`
instead of pasting the strings, so the encodings can never diverge between
files again.
"""

from typing import Dict, Optional


# alias -> H21.0.671 punycode-encoded parm name
PUNYCODE_PARMS: Dict[str, str] = {
    # Lights — intensity / exposure
    "intensity": "xn__inputsintensity_i0a",
    "exposure": "xn__inputsexposure_vya",
    "exposure_control": "xn__inputsexposure_control_wcb",
    # Lights — color
    # VERIFY-LIVE: color / color_control encodings diverged across files —
    # specialist_modes.py and mcp/server.py taught 'xn__inputscolor_vya', a
    # copy-paste from exposure ('exposure_vya'). The divergence was resolved
    # toward aliases.py's 'kya' / 'r0b' (canonical). Re-confirm both against a
    # live domelight parm name on the next USD bump (H22).
    "color": "xn__inputscolor_kya",
    "color_control": "xn__inputscolor_control_r0b",
    # Lights — temperature
    "color_temperature": "xn__inputscolortemperature_job",
    "enable_temperature": "xn__inputsenablecolortemperature_yxb",
    # Lights — shape / response
    "normalize": "xn__inputsnormalize_01a",
    "diffuse": "xn__inputsdiffuse_vya",
    "specular": "xn__inputsspecular_i0a",
    # DomeLight
    "texture_file": "xn__inputstexturefile_c5b",
    "texture_format": "xn__inputstextureformat_d8b",
    # Camera
    "focal_length": "xn__inputsfocallength_e4b",
    "focus_distance": "xn__inputsfocusdistance_f7b",
    "fstop": "xn__inputsfstop_vya",
    "horizontal_aperture": "xn__inputshorizontalaperture_ohb",
    "vertical_aperture": "xn__inputsverticalaperture_gfb",
    "clipping_range": "xn__inputsclippingrange_e4b",
}


def encoded(alias: str) -> Optional[str]:
    """Return the punycode-encoded parm name for a friendly ``alias``.

    Returns ``None`` if the alias is unknown. Pure function over a static
    dict — no determinism concern.
    """
    return PUNYCODE_PARMS.get(alias)
