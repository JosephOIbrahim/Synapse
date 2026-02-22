# Karma Rendering Guide

## Triggers

karma, karma xpu, karma cpu, render settings, pixel samples, progressive render, resolution override, output path, usdrender rop, soho_foreground, iconvert, exr to jpeg, denoiser, oidn, aov, render pass, light linking, light group, motion blur, depth of field, dof, volume rendering, fireflies, black render, render output

## Context

Karma is Houdini's native path-tracer. Karma XPU (GPU+CPU hybrid) is the default choice for almost all work; Karma CPU is reserved for OSL shaders or complex nested dielectrics. All configuration lives on Karma LOP nodes inside `/stage` and on a `usdrender` ROP in `/out`.

## Code

```python
# ── ENGINE SELECTION ──────────────────────────────────────────────────────────
# Karma XPU: GPU+CPU hybrid, 5-20x faster, no OSL, VRAM-limited
# Karma CPU: CPU-only, full OSL support, larger scenes via system RAM
# Default: always XPU unless you need OSL or nested-glass dielectrics.

import hou

def set_karma_engine(karma_lop_path, use_xpu=True):
    """Switch the engine on an existing Karma render settings LOP."""
    node = hou.node(karma_lop_path)
    if node is None:
        raise ValueError(f"Couldn't find node at {karma_lop_path!r}")
    # "xpu" = Karma XPU (GPU+CPU hybrid); "cpu" = Karma CPU (path-tracer only)
    node.parm("engine").set("xpu" if use_xpu else "cpu")
```

```python
# ── KARMA LOP NODE CONFIGURATION ─────────────────────────────────────────────
# The Karma LOP ("karmasettings") lives in /stage and holds ALL render quality
# knobs. The usdrender ROP in /out only handles output paths and frame range.

import hou

def configure_karma_lop(
    karma_lop_path="/stage/karmasettings",
    pixel_samples=64,           # Primary quality knob — double for each quality tier
    min_samples=1,              # Early-termination floor (adaptive sampling)
    convergence_mode="automatic",  # "automatic" = adaptive; "manual" = fixed samples
    pixel_oracle="variance",    # "variance" = noise-adaptive; "uniform" = fixed grid
    diffuse_bounces=4,
    specular_bounces=6,
    refract_bounces=6,
    volume_bounces=2,
    sss_bounces=2,
    bucket_size=32,             # 32-64 for GPU; 16-32 for CPU
    camera_prim_path="/cameras/render_cam",
    output_picture="$HIP/render/beauty/shot.$F4.exr",
):
    node = hou.node(karma_lop_path)
    if node is None:
        raise ValueError(f"Couldn't find node at {karma_lop_path!r}")

    # ── Sampling ──────────────────────────────────────────────────────────────
    node.parm("karma:global:pathtracedsamples").set(pixel_samples)
    node.parm("karma:global:minpathtracedsamples").set(min_samples)
    node.parm("karma:global:convergencemode").set(convergence_mode)
    node.parm("karma:global:pixeloracle").set(pixel_oracle)

    # ── Bounces ───────────────────────────────────────────────────────────────
    node.parm("karma:global:diffuselimit").set(diffuse_bounces)
    node.parm("karma:global:reflectlimit").set(specular_bounces)
    node.parm("karma:global:refractlimit").set(refract_bounces)
    node.parm("karma:global:volumelimit").set(volume_bounces)
    node.parm("karma:global:ssslimit").set(sss_bounces)

    # ── Performance ───────────────────────────────────────────────────────────
    node.parm("karma:global:bucketsize").set(bucket_size)
    # Russian roulette cutoff: 0.01 default; lower = more accurate but slower
    node.parm("karma:global:russianroulettecutoff").set(0.01)
    # Light sampling multiplier — raise for scenes with many small/bright lights
    node.parm("karma:global:lightsamples").set(1)

    # ── Camera + output ───────────────────────────────────────────────────────
    # camera parm expects USD prim path, NOT Houdini node path
    node.parm("camera").set(camera_prim_path)
    node.parm("picture").set(output_picture)
```

```python
# ── CPU vs XPU COMPARISON (runtime check) ────────────────────────────────────
# Use this to decide engine at scene start.

def karma_engine_for_scene(has_osl_shaders=False, nested_dielectrics=False,
                            vram_gb=24, geo_size_gb=0.0):
    """
    Returns "xpu" or "cpu" based on scene requirements.
    RTX 4090 has 24 GB VRAM — XPU spills to CPU RAM when VRAM is exhausted but
    gets slower; for scenes clearly over budget, CPU is more predictable.
    """
    if has_osl_shaders:
        return "cpu"          # XPU does NOT support OSL — hard requirement
    if nested_dielectrics:
        return "cpu"          # XPU has limited nested-glass accuracy
    if geo_size_gb > vram_gb * 0.8:
        return "cpu"          # Scene won't fit comfortably in VRAM
    return "xpu"              # Default: XPU is 5-20x faster for most shots
```

```python
# ── PROGRESSIVE RENDER PIPELINE ──────────────────────────────────────────────
# Never jump to production settings. Always validate in 4 tiers.
# Each tier catches a class of problems before you spend render time.

import hou, os, subprocess

RENDER_TIERS = {
    # Tier 1: Layout Check — 5 seconds, verifies composition/camera/lighting
    "layout": {
        "res": (320, 240),
        "karma:global:pathtracedsamples": 4,
        "karma:global:diffuselimit": 1,
        "karma:global:reflectlimit": 1,
        "karma:global:refractlimit": 1,
        "karma:global:volumelimit": 0,
        "karma:global:ssslimit": 0,
        # No displacement, no SSS — just enough to see composition
    },
    # Tier 2: Lighting Pass — ~30 seconds, evaluate materials and shadows
    "lighting": {
        "res": (960, 540),
        "karma:global:pathtracedsamples": 32,
        "karma:global:diffuselimit": 2,
        "karma:global:reflectlimit": 4,
        "karma:global:refractlimit": 4,
        "karma:global:volumelimit": 0,
        "karma:global:ssslimit": 0,
    },
    # Tier 3: Quality Preview — 2-5 minutes, near-final check
    "preview": {
        "res": (1920, 1080),
        "karma:global:pathtracedsamples": 64,
        "karma:global:diffuselimit": 4,
        "karma:global:reflectlimit": 6,
        "karma:global:refractlimit": 6,
        "karma:global:volumelimit": 2,
        "karma:global:ssslimit": 2,
    },
    # Tier 4: Final — production time, deliverable frame
    "final": {
        "res": (1920, 1080),
        "karma:global:pathtracedsamples": 256,
        "karma:global:diffuselimit": 6,
        "karma:global:reflectlimit": 8,
        "karma:global:refractlimit": 8,
        "karma:global:volumelimit": 4,
        "karma:global:ssslimit": 4,
        # Denoiser enabled at final tier only
        "karma:global:denoisemode": "oidn",
    },
}

def apply_render_tier(karma_lop_path, rop_path, tier_name):
    """Apply a named render tier to the Karma LOP and usdrender ROP."""
    tier = RENDER_TIERS[tier_name]
    karma = hou.node(karma_lop_path)
    rop   = hou.node(rop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    if rop is None:
        raise ValueError(f"Couldn't find usdrender ROP at {rop_path!r}")

    # Apply resolution to the ROP (override_res must be "specific" to take effect)
    w, h = tier["res"]
    rop.parm("override_res").set("specific")   # "": no override; "specific": use res below
    rop.parm("res_fraction").set("specific")   # required companion parm
    rop.parmTuple("res").set((w, h))

    # Apply all karma:global parms to the Karma LOP
    for parm_name, value in tier.items():
        if parm_name == "res":
            continue
        parm = karma.parm(parm_name)
        if parm is not None:
            parm.set(value)
    print(f"[karma] Applied tier '{tier_name}' — {w}x{h} @ {tier.get('karma:global:pathtracedsamples')} samples")
```

```python
# ── RESOLUTION OVERRIDE ───────────────────────────────────────────────────────
# Resolution lives on the usdrender ROP, not on the Karma LOP.
# override_res is a string menu: "" (no override), "scale", "specific".

def set_render_resolution(rop_path, width, height):
    """Force a specific resolution on the usdrender ROP."""
    rop = hou.node(rop_path)
    if rop is None:
        raise ValueError(f"Couldn't find ROP at {rop_path!r}")
    rop.parm("override_res").set("specific")   # must be "specific" not an int
    rop.parmTuple("res").set((width, height))

def set_render_resolution_scale(rop_path, fraction=0.5):
    """Scale resolution by a fraction (e.g. 0.5 = half-res preview)."""
    rop = hou.node(rop_path)
    if rop is None:
        raise ValueError(f"Couldn't find ROP at {rop_path!r}")
    rop.parm("override_res").set("scale")
    rop.parm("res_fraction").set(str(fraction))  # "0.5", "0.25", "1.0"
```

```python
# ── OUTPUT PATHS: KARMA LOP + USDRENDER ROP ───────────────────────────────────
# Both must agree on the output path. If they differ, the ROP outputimage wins.
# Best practice: set both to the same value to avoid confusion.

def set_output_paths(karma_lop_path, rop_path, output_path):
    """
    Set output EXR path on both the Karma LOP and the usdrender ROP.
    output_path example: "$HIP/render/beauty/shot.$F4.exr"
    """
    karma = hou.node(karma_lop_path)
    rop   = hou.node(rop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    if rop is None:
        raise ValueError(f"Couldn't find usdrender ROP at {rop_path!r}")

    karma.parm("picture").set(output_path)    # Karma LOP: "picture" parm
    rop.parm("outputimage").set(output_path)  # usdrender ROP: "outputimage" parm

    # Ensure output directory exists before rendering
    resolved = hou.expandString(output_path.replace("$F4", "0001"))
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    print(f"[karma] Output path set: {output_path}")
```

```python
# ── USDRENDER ROP SETUP ───────────────────────────────────────────────────────
# The usdrender ROP in /out connects the Karma LOP to the render pipeline.
# loppath must point to the last Karma/render-settings LOP in /stage.

def configure_usdrender_rop(
    rop_path="/out/karma_render",
    karma_lop_path="/stage/karmasettings",  # last displayed LOP in /stage
    output_path="$HIP/render/beauty/shot.$F4.exr",
    frame_start=None,
    frame_end=None,
    soho_foreground=1,   # 1 = synchronous (blocks until done); 0 = async (returns immediately)
):
    """
    Configure a usdrender ROP for Karma rendering.
    soho_foreground=1 is REQUIRED for reliable file output from MCP/scripted renders.
    With soho_foreground=0 the ROP returns before the EXR is written.
    """
    # Create the ROP if it doesn't exist
    out_net = hou.node("/out")
    rop = hou.node(rop_path)
    if rop is None:
        rop = out_net.createNode("usdrender", rop_path.split("/")[-1])

    # Point the ROP at the Karma LOP (LOP network path, not prim path)
    rop.parm("loppath").set(karma_lop_path)

    # Output image — must match Karma LOP's "picture" parm
    rop.parm("outputimage").set(output_path)

    # soho_foreground: 1 = blocks Houdini until render completes (safe for scripting)
    # WARNING: with soho_foreground=1 the Houdini UI becomes unresponsive during render
    # For interactive work use 0; for MCP/scripted use 1.
    rop.parm("soho_foreground").set(soho_foreground)

    # Frame range
    if frame_start is not None and frame_end is not None:
        rop.parm("trange").set(1)  # 0 = current frame only; 1 = frame range
        rop.parm("f1").set(frame_start)
        rop.parm("f2").set(frame_end)
    else:
        rop.parm("trange").set(0)  # render only current frame

    print(f"[karma] usdrender ROP configured: {rop_path} -> {karma_lop_path}")
    return rop
```

```python
# ── SOHO_FOREGROUND PARAMETER ─────────────────────────────────────────────────
# soho_foreground controls whether usdrender blocks the Python thread until done.
# This is the single most common cause of "render started but no file appeared".

def render_frame_synchronous(rop_path, frame=None):
    """
    Render a single frame synchronously. Guarantees the EXR is on disk before
    this function returns. Required when the next step reads the render output.
    """
    rop = hou.node(rop_path)
    if rop is None:
        raise ValueError(f"Couldn't find ROP at {rop_path!r}")

    # Force synchronous mode for this render
    rop.parm("soho_foreground").set(1)   # blocks until render complete
    rop.parm("trange").set(0)            # current frame only

    if frame is not None:
        hou.setFrame(frame)

    rop.render()  # returns only after EXR is written to disk
    print(f"[karma] Frame {hou.frame()} render complete")

def render_frame_async(rop_path):
    """
    Fire-and-forget render. Returns immediately. Use for interactive previews.
    Do NOT use when downstream code reads the render output.
    """
    rop = hou.node(rop_path)
    if rop is None:
        raise ValueError(f"Couldn't find ROP at {rop_path!r}")
    rop.parm("soho_foreground").set(0)   # returns before EXR is written
    rop.parm("trange").set(0)
    rop.render()
```

```python
# ── DENOISER CONFIGURATION ────────────────────────────────────────────────────
# Karma supports Intel OIDN and NVIDIA OptiX denoising as a post-process.
# Karma auto-generates the auxiliary albedo + normal AOVs when denoising is on.

def configure_denoiser(karma_lop_path, mode="oidn"):
    """
    Enable denoising on the Karma LOP.
    mode: "oidn" (Intel Open Image Denoise, CPU-based, cross-vendor)
          "optix" (NVIDIA OptiX, GPU-based, NVIDIA only)
          "none" (disabled)
    """
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    karma.parm("karma:global:denoisemode").set(mode)
    # Karma automatically adds albedo and normal auxiliary AOVs when mode != "none"
    # Do NOT denoise Cryptomatte, ID, or integer passes — denoiser corrupts them
    print(f"[karma] Denoiser set to '{mode}'")
```

```python
# ── AOV / RENDER PASS SETUP ───────────────────────────────────────────────────
# Standard AOVs for a compositable beauty package.
# Beauty rebuild: C = direct_diffuse + indirect_diffuse + direct_specular
#                   + indirect_specular + direct_emission + sss
#                   + direct_volume + indirect_volume

BEAUTY_AOVS = [
    "C",                  # combined beauty (always included automatically)
    "direct_diffuse",
    "indirect_diffuse",
    "direct_specular",
    "indirect_specular",
    "direct_emission",
    "sss",
    "direct_volume",
    "indirect_volume",
]

UTILITY_AOVS = [
    "N",                  # world-space normals (vector3)
    "P",                  # world-space position (point3)
    "depth",              # camera-space Z (float)
    "Albedo",             # surface base color unlit (color3)
    "motionvector",       # per-pixel motion (vector3)
    "crypto_material",    # Cryptomatte by material
    "crypto_object",      # Cryptomatte by object
    "crypto_asset",       # Cryptomatte by asset
]

def add_aovs(karma_lop_path, aov_names):
    """
    Add AOV entries to the Karma LOP via multiparm.
    Each AOV is a row in the 'aov' multiparm block.
    """
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")

    existing = karma.parm("aov").eval()  # number of existing AOV entries
    for i, aov_name in enumerate(aov_names):
        idx = existing + i + 1
        karma.parm("aov").set(idx)           # extend multiparm
        karma.parm(f"aov_name{idx}").set(aov_name)
        # aov_filename: leave empty to use the main picture path with suffix
    print(f"[karma] Added {len(aov_names)} AOVs to {karma_lop_path}")

def add_light_group_aov(karma_lop_path, group_name, light_prim_paths):
    """
    Create a light-group AOV so compositors can control per-light contributions.
    Each group produces an AOV named light_group_<group_name>.
    """
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    count = karma.parm("lightgroups").eval()
    karma.parm("lightgroups").set(count + 1)
    karma.parm(f"lightgroup_name{count+1}").set(group_name)
    karma.parm(f"lightgroup_lights{count+1}").set(" ".join(light_prim_paths))
    # AOV name produced: light_group_<group_name>
    # e.g. group_name="key" -> AOV "light_group_key"
```

```python
# ── CAMERA CONFIGURATION ──────────────────────────────────────────────────────
# Camera parm on Karma LOP takes a USD prim path, not a Houdini node path.
# DOF is per-camera: fStop > 0 enables it, fStop == 0 disables it.

def set_karma_camera(karma_lop_path, camera_usd_path="/cameras/render_cam"):
    """Assign a USD camera prim to the Karma LOP."""
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    karma.parm("camera").set(camera_usd_path)  # must be USD prim path

def configure_camera_dof(stage, camera_prim_path, fstop=2.8, focus_distance=5.0):
    """
    Enable depth of field on a USD camera prim.
    fstop=0 disables DOF entirely; fstop > 0 enables it.
    focus_distance is in scene units.
    """
    from pxr import Usd
    cam_prim = stage.GetPrimAtPath(camera_prim_path)
    if not cam_prim.IsValid():
        raise ValueError(f"Couldn't find camera prim at {camera_prim_path!r}")
    cam_prim.GetAttribute("fStop").Set(fstop)
    cam_prim.GetAttribute("focusDistance").Set(focus_distance)
    # focalLength in mm: 25=wide, 35=standard, 50=portrait, 85=close-up
    # horizontalAperture: 36.0 for full-frame equivalent

def configure_motion_blur(karma_lop_path, enable=True, xform_samples=2, geo_samples=2):
    """
    Enable transform and deformation motion blur.
    xform_samples: number of transform time samples (2 is sufficient for most shots)
    geo_samples: number of deformation time samples (raise to 3-4 for fast flex)
    """
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")
    karma.parm("karma:object:geovelblur").set(1 if enable else 0)
    karma.parm("karma:object:xformsamples").set(xform_samples)
    karma.parm("karma:object:geosamples").set(geo_samples)
    # Shutter: open=0.0, close=1.0 (trailing); centered: open=-0.5, close=0.5
```

```python
# ── VOLUME RENDERING SETTINGS ─────────────────────────────────────────────────
# Volumes are expensive. Always start with coarse settings and refine.

def configure_volume_rendering(karma_lop_path, quality="preview"):
    """
    Apply volume rendering settings for a given quality preset.
    Step rate: lower = more accurate but slower; 0.1 preview, 0.25-0.5 production.
    """
    karma = hou.node(karma_lop_path)
    if karma is None:
        raise ValueError(f"Couldn't find Karma LOP at {karma_lop_path!r}")

    presets = {
        "preview":    {"step_rate": 0.1,  "shadow_step": 0.2, "bounces": 0},
        "production": {"step_rate": 0.25, "shadow_step": 0.5, "bounces": 2},
        "high":       {"step_rate": 0.5,  "shadow_step": 1.0, "bounces": 4},
    }
    cfg = presets.get(quality, presets["preview"])

    # Volume step rate controls the primary march step through the volume
    karma.parm("karma:global:volumesteprate").set(cfg["step_rate"])
    # Shadow step can be coarser than primary — saves significant render time
    karma.parm("karma:global:volumeshadowsteprate").set(cfg["shadow_step"])
    # Volume bounces: 0 for preview, 2-4 for production
    karma.parm("karma:global:volumelimit").set(cfg["bounces"])
    # Max volume depth: number of overlapping volume boundaries to track
    karma.parm("karma:global:maxvolumedepth").set(4)
    print(f"[karma] Volume settings applied: {quality} preset")
```

```python
# ── ICONVERT: EXR TO JPEG ─────────────────────────────────────────────────────
# iconvert is Houdini's built-in image converter, located at $HFS/bin/.
# Use it to produce JPEG previews from EXR renders without external dependencies.

import subprocess, os

def exr_to_jpeg(exr_path, jpeg_path=None, quality=90):
    """
    Convert an EXR render to JPEG using Houdini's iconvert.
    iconvert handles half-float EXR, tone-maps to 8-bit JPEG automatically.
    """
    hfs = os.environ.get("HFS", "")
    if not hfs:
        raise EnvironmentError("HFS environment variable not set — is Houdini running?")

    iconvert = os.path.join(hfs, "bin", "iconvert.exe")  # Windows
    if not os.path.exists(iconvert):
        iconvert = os.path.join(hfs, "bin", "iconvert")   # Linux/macOS

    exr_path  = hou.expandString(exr_path)
    if jpeg_path is None:
        jpeg_path = exr_path.replace(".exr", ".jpg")
    jpeg_path = hou.expandString(jpeg_path)

    # iconvert CLI: iconvert [options] input output
    # -q sets JPEG quality (1-100); -g applies gamma correction
    result = subprocess.run(
        [iconvert, "-q", str(quality), exr_path, jpeg_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"iconvert failed: {result.stderr.strip()}")
    print(f"[karma] EXR -> JPEG: {jpeg_path}")
    return jpeg_path

def batch_exr_to_jpeg(exr_dir, frame_range, frame_padding=4):
    """
    Convert a sequence of EXRs to JPEGs.
    exr_dir: directory containing shot.0001.exr, shot.0002.exr, etc.
    """
    converted = []
    for f in frame_range:
        exr = os.path.join(exr_dir, f"shot.{f:0{frame_padding}d}.exr")
        jpg = exr.replace(".exr", ".jpg")
        if os.path.exists(exr):
            converted.append(exr_to_jpeg(exr, jpg))
    print(f"[karma] Converted {len(converted)} frames to JPEG")
    return converted
```

```python
# ── LIGHT LINKING ─────────────────────────────────────────────────────────────
# In Solaris, light linking uses USD Collections on the light prim.
# Houdini's Light Linker LOP is easier for artists; use Python for scripted setups.

from pxr import UsdLux, Usd, Sdf

def link_light_to_geometry(stage, light_prim_path, geo_prim_paths):
    """
    Configure a USD light to illuminate only specified geometry prims.
    All other geometry is excluded from this light's contribution.
    """
    light_prim = stage.GetPrimAtPath(light_prim_path)
    if not light_prim.IsValid():
        raise ValueError(f"Couldn't find light prim at {light_prim_path!r}")

    # Apply lightLink collection to the light prim
    collection = Usd.CollectionAPI.Apply(light_prim, "lightLink")
    collection.CreateIncludesRel().SetTargets(
        [Sdf.Path(p) for p in geo_prim_paths]
    )
    # expansionRule: "expandPrims" traverses the subtree; "explicitOnly" for exact paths
    collection.CreateExpansionRuleAttr().Set("expandPrims")
    print(f"[karma] Light {light_prim_path} linked to {geo_prim_paths}")
```

```python
# ── COMPLETE RENDER SETUP: END-TO-END EXAMPLE ────────────────────────────────
# Full workflow: layout check -> lighting pass -> quality preview -> final.

def setup_karma_render_pipeline(
    karma_lop_path="/stage/karmasettings",
    rop_path="/out/karma",
    output_dir="$HIP/render/beauty",
    camera_prim_path="/cameras/render_cam",
):
    """Full Karma pipeline setup with progressive tier validation."""
    output_path = f"{output_dir}/shot.$F4.exr"

    # 1. Configure the Karma LOP with production defaults
    configure_karma_lop(
        karma_lop_path=karma_lop_path,
        pixel_samples=64,
        camera_prim_path=camera_prim_path,
        output_picture=output_path,
    )

    # 2. Set engine to XPU (default) — switch to "cpu" only if OSL is needed
    set_karma_engine(karma_lop_path, use_xpu=True)

    # 3. Configure the usdrender ROP
    rop = configure_usdrender_rop(
        rop_path=rop_path,
        karma_lop_path=karma_lop_path,
        output_path=output_path,
        soho_foreground=1,   # synchronous = safe for scripted renders
    )

    # 4. Validate with layout tier first (fast, catches gross errors)
    apply_render_tier(karma_lop_path, rop_path, "layout")
    render_frame_synchronous(rop_path)

    # 5. Confirm EXR was written
    frame_path = hou.expandString(output_path.replace("$F4", f"{int(hou.frame()):04d}"))
    if not os.path.exists(frame_path):
        raise RuntimeError(f"Layout render failed — no file at {frame_path!r}")

    print("[karma] Layout check passed — promote to 'lighting' or 'final' tier when ready")
    return rop
```

## Common Mistakes

- **Camera parm is a USD prim path, not a Houdini node path.** `/cameras/render_cam` is correct; `/stage/camera1` (a Houdini node path) will produce a black render with no error.

- **soho_foreground=0 (default) returns before the EXR is written.** Any script that reads the render output immediately after `rop.render()` will find no file. Always set `soho_foreground=1` for scripted/MCP renders.

- **Resolution override_res is a string menu, not an int.** Use `rop.parm("override_res").set("specific")` not `.set(1)`. Setting the wrong type silently fails on some Houdini builds.

- **Both picture (Karma LOP) and outputimage (ROP) must be set.** If only one is set, output may be missing or sent to the wrong path. When they differ, the ROP's outputimage wins.

- **Fireflies (bright specks) are caused by intensity > 1.0 or roughness = 0.0.** Always set light intensity to 1.0 and control brightness via exposure. Set minimum roughness to 0.001.

- **Black render with no error usually means one of:** no camera assigned, no lights in the stage, all geometry is on the wrong USD purpose (must be `"default"`), or the material binding path pattern does not match any prims.

- **Denoiser corrupts integer/Cryptomatte passes.** Only apply denoising to the beauty composite. Never denoise `crypto_material`, `crypto_object`, `crypto_asset`, or ID passes.

- **Volume renders with step_rate too low are prohibitively slow.** Start with 0.1 for preview. Shadow step rate can always be 2x coarser than the primary step rate without visible quality loss.

- **soho_foreground=1 blocks the Houdini UI for the entire render duration.** For long renders triggered from the Houdini UI (not MCP), use soho_foreground=0 and check file existence separately.

- **iconvert.exe path requires HFS to be set.** It is always set when running inside Houdini Python. If calling from an external subprocess without Houdini's env, source `houdini_setup` first or hardcode the `$HFS/bin/` path.
