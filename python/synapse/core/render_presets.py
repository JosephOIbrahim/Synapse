"""Karma progressive render presets (W1-KPRE).

Four named presets that encode the production progressive-render pipeline from
``docs/SYNAPSE_latency_and_karma_rendersettings_2026.md`` (Parts 2-4):

    layout  ->  lighting  ->  quality  ->  final

render low + fast, check, then raise. Part 3 of the addendum makes this the
*operational mitigation* for panel latency: anything above the lighting pass
renders in background (``soho_foreground = 0``) so the render never fights the
panel for Houdini's main thread.

Law (autoresearch pattern)
--------------------------
Parameter **NAMES are probe-verified** against the live Houdini build; parameter
**VALUES are design choices** from the addendum's settings tables. A name
asserted from docs alone is a BLOCK (the ``karmarenderproperties`` precedent) --
so every concrete parm name below was confirmed ``exists=True`` via live
``node.parm(...)`` introspection, not copied from prose.

Probe provenance
----------------
* Build          : Houdini ``22.0.400`` (``hou.applicationVersionString()``)
* Date           : 2026-08-12
* Method         : created ``karmarendersettings`` (LOP), ``usdrender_rop`` and
  ``karma`` (ROP) on the live bridge, enumerated ``node.parm(...)`` /
  ``node.parmTuple(...)`` and the parm menu tokens, then destroyed the temp
  nodes. Full receipts: ``harness/notes/receipts/W1-KPRE.json``.

Corrections the probe forced vs the addendum's prose (all three docs-only names
are PHANTOM on 22.0.400 -- shipping them would silently no-op):

    reflectlimit  ->  reflectionlimit    (Float, karmarendersettings + karma ROP)
    refractlimit  ->  refractionlimit    (Float, "                          ")
    denoisemode   ->  denoiser           (String menu: off | optix | oidn)

Purity
------
No ``hou`` import: this is pure data + a resolver so the preset definitions are
testable in stock CI (mirrors ``synapse.core.show_config``). The live
apply-to-node work stays in the server handlers, which consume this module.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# Build these parm names were probe-verified against.
PROBED_BUILD = "22.0.400"
PROBE_DATE = "2026-08-12"

# XPU flush-delay note -- travels with the preset surface (acceptance #4).
# The quality/final presets default to XPU (quality) / are XPU-capable, and
# Karma XPU flushes image tiles to disk 10-15s AFTER render() returns. A slow
# return is the flush, not a hang.
XPU_FLUSH_DELAY_NOTE = (
    "Karma XPU flushes image tiles to disk ~10-15s AFTER render() returns. "
    "A slow return on an XPU render is the file flush completing, NOT a hang -- "
    "wait for the flush before treating the render as stalled or killing it."
)

# ---------------------------------------------------------------------------
# Probe-verified parm names (live Houdini 22.0.400). Logical setting -> the
# CONCRETE parm name confirmed to exist on the render-settings surface.
# ---------------------------------------------------------------------------
PARM_NAMES: Dict[str, str] = {
    "pixel_samples": "pathtracedsamples",   # Int  (karmarendersettings + karma ROP)
    "engine": "engine",                     # String menu: cpu | xpu
    "denoise": "denoiser",                  # String menu: off | optix | oidn
    "diffuse_limit": "diffuselimit",        # Float
    "reflection_limit": "reflectionlimit",  # Float  (NOT reflectlimit -- phantom)
    "refraction_limit": "refractionlimit",  # Float  (NOT refractlimit -- phantom)
    "volume_limit": "volumelimit",          # Float
    "sss_limit": "ssslimit",                # Float
    "xform_samples": "xformsamples",        # Int  (motion blur, transform)
    "geo_samples": "geosamples",            # Int  (motion blur, geometry)
    "background": "soho_foreground",        # Toggle: 1 = foreground, 0 = background
}

# Menu tokens confirmed on the build -- design-choice VALUES must be one of these.
ENGINE_TOKENS: Tuple[str, ...] = ("cpu", "xpu")
DENOISE_TOKENS: Tuple[str, ...] = ("off", "optix", "oidn")

# Resolution component parm names differ by node type (both probe-verified).
# Presets carry only (width, height); resolution is applied by the existing
# _handle_render path, which already fans across exactly these candidates.
RESOLUTION_PARMS: Dict[str, Tuple[str, str]] = {
    "karma": ("resolutionx", "resolutiony"),   # karmarendersettings + karma ROP
    "usdrender": ("res_user1", "res_user2"),   # usdrender ROP (+ override_res=specific)
}

# Every concrete parm name this module is allowed to emit. The test asserts
# preset overrides never step outside this probe-verified set.
PROBE_VERIFIED_PARM_NAMES = frozenset(
    list(PARM_NAMES.values())
    + list(RESOLUTION_PARMS["karma"])
    + list(RESOLUTION_PARMS["usdrender"])
    + ["override_res"]
)

# ---------------------------------------------------------------------------
# Shared production baselines (Part 4 cheat-sheet). Applied by every preset so
# a single named call lands a complete, sane bounce + motion configuration.
# ---------------------------------------------------------------------------
BOUNCE_BASELINE: Dict[str, int] = {
    "diffuse_limit": 2,
    "reflection_limit": 4,
    "refraction_limit": 4,
    "volume_limit": 2,
    "sss_limit": 2,
}
MOTION_BASELINE: Dict[str, int] = {
    "xform_samples": 2,
    "geo_samples": 2,
}

# ---------------------------------------------------------------------------
# The four progressive presets. VALUES are design choices from the addendum
# (Parts 2.2 / 2.3 / 3 / 4); NAMES route through PARM_NAMES above.
#
#   - resolution / pixel_samples : addendum 2.2 progressive-pipeline table
#   - denoise                    : addendum 2.3 (OIDN for previews/most shots,
#                                  off for hero finals)
#   - engine                     : addendum 2.1 (XPU default; CPU for hero finals
#                                  needing reference quality / OSL / nested glass)
#   - background                 : addendum Part 3 (quality+ -> background so the
#                                  render doesn't fight the panel main thread)
#
# Camera is DELIBERATELY absent: on usdrender the camera is a USD prim path the
# artist owns (override_camera). A preset must never smuggle a node path in, so
# presets carry no camera key at all.
# ---------------------------------------------------------------------------
PROGRESSIVE_PRESETS: Dict[str, dict] = {
    "layout": {
        "order": 1,
        "resolution": (320, 240),
        "pixel_samples": 4,
        "denoise": "off",     # blocking pass -- no denoise step
        "engine": "xpu",
        "background": False,  # foreground: fast, low-stakes, minimal main-thread cost
        "purpose": "Blocking / framing",
    },
    "lighting": {
        "order": 2,
        "resolution": (960, 540),
        "pixel_samples": 24,               # addendum 16-32; 24 = midpoint design choice
        "pixel_samples_range": (16, 32),
        "denoise": "oidn",                 # iteration loop -- OIDN lets samples stay low
        "engine": "xpu",
        "background": False,               # foreground: the light-look iteration loop
        "purpose": "Light look / exposure",
    },
    "quality": {
        "order": 3,
        "resolution": (1920, 1080),
        "pixel_samples": 64,
        "denoise": "oidn",
        "engine": "xpu",
        "background": True,                # quality+ -> background (Part 3)
        "purpose": "Lookdev / most shots",
    },
    "final": {
        "order": 4,
        "resolution": (1920, 1080),        # 1080p+ (addendum "1920x1080+")
        "pixel_samples": 256,              # addendum 128-512; 256 = midpoint design choice
        "pixel_samples_range": (128, 512),
        "denoise": "off",                  # hero finals render clean; denoise as separate pass
        "engine": "cpu",                   # hero finals -> reference quality / OSL / nested glass
        "background": True,                # background (Part 3)
        "purpose": "Hero finals",
    },
}

# Canonical progressive order (low -> high). resolve_stage_chain always emits in
# this order regardless of how the caller lists the stages.
PRESET_ORDER: Tuple[str, ...] = ("layout", "lighting", "quality", "final")


def list_presets() -> List[str]:
    """Preset names in canonical low->high order."""
    return list(PRESET_ORDER)


def get_preset(name: str) -> dict:
    """Return a copy of a named preset. Raises KeyError with the valid set."""
    key = str(name).strip().lower()
    if key not in PROGRESSIVE_PRESETS:
        raise KeyError(
            f"Unknown render preset {name!r}. "
            f"Valid presets: {', '.join(PRESET_ORDER)}"
        )
    return dict(PROGRESSIVE_PRESETS[key])


def preset_parm_overrides(name: str) -> Dict[str, object]:
    """Concrete ``parm-name -> value`` dict for a preset.

    Ready to hand to ``_handle_render_settings`` (whose generic loop does
    ``node.parm(k).set(v)``). Every key is a probe-verified parm name.

    Intentionally EXCLUDED:
      * resolution -- applied by the existing ``_handle_render`` path, which
        already fans across the per-node-type resolution candidates.
      * camera     -- scene-owned USD prim path; a preset must never smuggle one.
    """
    p = get_preset(name)
    ov: Dict[str, object] = {
        PARM_NAMES["pixel_samples"]: int(p["pixel_samples"]),
        PARM_NAMES["engine"]: p["engine"],
        PARM_NAMES["denoise"]: p["denoise"],
        # soho_foreground polarity: 1 = foreground, 0 = background (probe-verified,
        # matches the existing progressive-render fg/bg convention).
        PARM_NAMES["background"]: 0 if p["background"] else 1,
    }
    for logical, val in BOUNCE_BASELINE.items():
        ov[PARM_NAMES[logical]] = val
    for logical, val in MOTION_BASELINE.items():
        ov[PARM_NAMES[logical]] = val
    return ov


def resolve_stage_chain(stages=None) -> List[Tuple[str, dict]]:
    """Resolve a requested stage chain to ``[(name, preset), ...]``.

    ``stages=None`` -> the full 4-stage chain. A list of names -> only those
    stages, always emitted in canonical ``PRESET_ORDER`` (a caller listing
    ``["final", "layout"]`` still runs layout before final). Unknown names raise
    KeyError.
    """
    if stages is None:
        chosen = list(PRESET_ORDER)
    else:
        if isinstance(stages, str):
            stages = [stages]
        requested = {str(s).strip().lower() for s in stages}
        unknown = requested - set(PROGRESSIVE_PRESETS)
        if unknown:
            raise KeyError(
                f"Unknown render preset(s): {', '.join(sorted(unknown))}. "
                f"Valid presets: {', '.join(PRESET_ORDER)}"
            )
        chosen = [n for n in PRESET_ORDER if n in requested]
    return [(n, get_preset(n)) for n in chosen]


__all__ = [
    "PROBED_BUILD",
    "PROBE_DATE",
    "XPU_FLUSH_DELAY_NOTE",
    "PARM_NAMES",
    "ENGINE_TOKENS",
    "DENOISE_TOKENS",
    "RESOLUTION_PARMS",
    "PROBE_VERIFIED_PARM_NAMES",
    "BOUNCE_BASELINE",
    "MOTION_BASELINE",
    "PROGRESSIVE_PRESETS",
    "PRESET_ORDER",
    "list_presets",
    "get_preset",
    "preset_parm_overrides",
    "resolve_stage_chain",
]
