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

TWO REGISTRIES, TWO NAME-SPACES — this is the distinction that was silently
breaking light authoring:

* :data:`PUNYCODE_PARMS` / :func:`encoded` — the **LOP parm interface**. These
  are what ``node.parm()`` / ``set_parm`` expect: the punycode ``xn__`` names
  SideFX generates for the parm UI. They are **build-specific** and DO drift on
  a USD bump, so they MUST be re-probed (above).
* :data:`USD_ATTR_NAMES` / :func:`raw` — the **actual USD prim attribute**.
  These are what ``set_usd_attribute`` writes onto the prim
  (``prim.GetAttribute(name).Set``): the raw schema names — ``inputs:intensity``,
  ``inputs:shaping:cone:angle`` — which are **schema-stable** across
  Houdini/USD builds. Passing a punycode ``xn__`` name to ``set_usd_attribute``
  silently NO-OPS (``prim.GetAttribute("xn__…")`` is invalid, and the handler
  is guarded by ``if attr:``), which is exactly the bug this split prevents.
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
    # Camera attrs do NOT live here — see USD_ATTR_NAMES below. Live-probed
    # off the camera LOP on 21.0.671 (2026-07-01,
    # harness/notes/verified_nodetype_catalog_21.0.671.json): standard
    # UsdGeomCamera attributes are NOT in the ``inputs:`` namespace, so they
    # are NEVER punycode-encoded — the parm names are the plain camelCase
    # attrs (focalLength, fStop, …). The six xn__inputs* camera guesses that
    # used to sit here were phantom.
    # ------------------------------------------------------------------
    # Geometry + cone/focus shaping — LIVE-PROBED on 21.0.671 (2026-06-26),
    # superseding the prior placeholders (``shaping_cone_angle``=``_hgbb``,
    # ``shaping_cone_softness``=``_jlbb``) and the corpus geometry values
    # (``_bobja``/``_brbja``/``_o5a``/``_k5a``/``_e5a``/``_i5a``) — ALL phantom.
    # The suffix is STRUCTURE-based on the full property string: an
    # ``inputs:<5-char>`` leaf -> ``_zta`` (color, width); an ``inputs:<6-char>``
    # leaf -> ``_mva`` (radius, height, length). Probe-generated, never guessed.
    # Ground truth: harness/notes/verified_usdlux_encodings_21.0.671.json.
    # ``radius`` is now probed, so ``encoded("radius")`` resolves (previously a
    # deliberate gap); the sphere-radius rule still defers via the single source.
    "radius": "xn__inputsradius_mva",
    "width": "xn__inputswidth_zta",
    "height": "xn__inputsheight_mva",
    "length": "xn__inputslength_mva",
    "shaping_cone_angle": "xn__inputsshapingconeangle_wcbhe",
    "shaping_cone_softness": "xn__inputsshapingconesoftness_shbhe",
    "shaping_focus": "xn__inputsshapingfocus_e5ah",
}


# Aliases whose encoded value is a parmTuple BASE (color3f), not a scalar parm.
# The set/get-parm handlers try node.parmTuple(encoded) for these.
TUPLE_ALIASES: FrozenSet[str] = frozenset({"color", "light_color", "shadow_color"})


def encoded(alias: str) -> Optional[str]:
    """Return the punycode-encoded parm name for a friendly ``alias``.

    Returns ``None`` if the alias is unknown. Pure function over a static
    dict — no determinism concern.

    USE THIS for the LOP **parm interface** (``node.parm()`` / ``set_parm``).
    For the actual USD prim attribute (``set_usd_attribute``), use :func:`raw`.
    """
    return PUNYCODE_PARMS.get(alias)


# alias -> RAW USD attribute name authored on the prim by set_usd_attribute.
# Live-probed off a real UsdLuxSphereLight prim on 21.0.671 (2026-06-26):
# ``prim.GetAttribute("inputs:radius")`` is VALID, while the punycode form
# ``prim.GetAttribute("xn__inputsradius_mva")`` is INVALID and the handler
# (handlers_usd.py:_handle_set_usd_attribute, guarded ``if attr:``) silently
# NO-OPS. These are the stable UsdLux schema names — unlike the punycode parm
# names above, they do NOT drift between Houdini/USD builds, so they are
# H22-safe.
USD_ATTR_NAMES: Dict[str, str] = {
    # Lights — scalars
    "intensity": "inputs:intensity",
    "exposure": "inputs:exposure",
    "color": "inputs:color",  # color3f tuple
    "color_temperature": "inputs:colorTemperature",
    "enable_temperature": "inputs:enableColorTemperature",
    "diffuse": "inputs:diffuse",
    "specular": "inputs:specular",
    "normalize": "inputs:normalize",
    # Geometry
    "radius": "inputs:radius",
    "width": "inputs:width",
    "height": "inputs:height",
    "length": "inputs:length",
    "angle": "inputs:angle",
    # Cone / focus shaping (nested namespace -> colon-separated leaves)
    "shaping_cone_angle": "inputs:shaping:cone:angle",
    "shaping_cone_softness": "inputs:shaping:cone:softness",
    "shaping_focus": "inputs:shaping:focus",
    # DomeLight — HDRI texture (nested namespace)
    "texture_file": "inputs:texture:file",
    "texture_format": "inputs:texture:format",
    # Camera — UsdGeomCamera. NOT ``inputs:``-namespaced, so the camera LOP
    # never punycode-encodes them: parm name == raw attr name (plain
    # camelCase, each with a ``_control`` companion). Live-probed off the
    # camera LOP on 21.0.671 (2026-07-01) — the prior xn__inputs* entries in
    # PUNYCODE_PARMS were phantom guesses and are gone. Ground truth:
    # harness/notes/verified_nodetype_catalog_21.0.671.json.
    "focal_length": "focalLength",
    "focus_distance": "focusDistance",
    "fstop": "fStop",
    "horizontal_aperture": "horizontalAperture",
    "vertical_aperture": "verticalAperture",
    "clipping_range": "clippingRange",  # float2 tuple (near/far)
}


def raw(alias: str) -> Optional[str]:
    """Return the raw USD prim attribute name for a friendly ``alias``.

    Returns ``None`` if the alias is unknown. Mirror of :func:`encoded`, but for
    the **USD prim attribute** name-space (``set_usd_attribute`` ->
    ``prim.GetAttribute(name).Set``) rather than the LOP parm interface. These
    schema names are build-stable; :func:`encoded`'s punycode names are not.
    """
    return USD_ATTR_NAMES.get(alias)
