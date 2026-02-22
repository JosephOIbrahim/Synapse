# Karma Rendering Reference

## Triggers
render, karma, rop, usdrender, xpu, cpu, samples, bounces, denoiser, resolution,
override_res, output format, exr, fireflies, motion blur, volume step rate

## Context
Karma rendering setup in Houdini 21: ROP configuration, engine selection,
quality settings, resolution override, denoising, troubleshooting.
All code is Houdini Python.

## Code

```python
# Create and configure a usdrender ROP in /out
import hou

def setup_karma_rop(
    name="karma_render",
    lop_path="/stage",
    camera="/cameras/render_cam",
    width=1920,
    height=1080,
    output_path="$HIP/render/shot.$F4.exr",
):
    """Full Karma ROP setup checklist.
    IMPORTANT: output_file kwarg in rop.render() does NOT work for usdrender.
    Must set outputimage or picture parm directly."""
    out = hou.node("/out")
    rop = out.createNode("usdrender", name)

    # 1. LOP path -- must point to a LOP node with a valid stage
    lop_display = hou.node(lop_path)
    if lop_display:
        # Find display node in /stage
        display = lop_display.displayNode()
        if display:
            rop.parm("loppath").set(display.path())

    # 2. Renderer
    rop.parm("renderer").set("BRAY_HdKarma")

    # 3. Camera -- must be USD prim path, NOT Houdini node path
    rop.parm("override_camera").set(camera)

    # 4. Resolution -- override_res is a STRING MENU, not int!
    #    "" = None (use USD), "scale" = percentage, "specific" = exact
    rop.parm("override_res").set("specific")
    rop.parm("res_user1").set(width)
    rop.parm("res_user2").set(height)

    # 5. Output -- MUST set parm directly (render kwarg doesn't work)
    rop.parm("outputimage").set(output_path)

    print(f"Karma ROP: {rop.path()}")
    print(f"  Camera: {camera} (USD prim path)")
    print(f"  Resolution: {width}x{height}")
    print(f"  Output: {output_path}")
    return rop

setup_karma_rop()
```

```python
# Karma engine selection: XPU vs CPU
import hou

def select_karma_engine(karma_props_path, engine="xpu"):
    """Select Karma engine.
    XPU (default): GPU-accelerated, fast, production quality.
    CPU: slower but handles edge cases:
      - Nested dielectrics (glass inside liquid)
      - Complex SSS (skin with multiple scatter profiles)
      - Volume rendering with many scattering events
      - When XPU produces unconverging fireflies
    """
    node = hou.node(karma_props_path)
    if not node:
        return

    if node.parm("engine"):
        node.parm("engine").set(engine)
    print(f"Karma engine: {engine}")

select_karma_engine("/stage/karmarenderproperties1", "xpu")
```

```python
# Karma render properties: sample and bounce settings
import hou

# Progressive quality presets
KARMA_QUALITY_PRESETS = {
    "preview": {
        "karma:global:pathtracedsamples": 16,
        "karma:global:minpathtracedsamples": 1,
        "karma:global:pixeloracle": "uniform",
        "karma:global:convergencethreshold": 0.05,
        "karma:global:diffuselimit": 1,
        "karma:global:reflectlimit": 2,
        "karma:global:volumesteprate": 0.1,
    },
    "lighting": {
        "karma:global:pathtracedsamples": 64,
        "karma:global:minpathtracedsamples": 4,
        "karma:global:pixeloracle": "variance",
        "karma:global:convergencethreshold": 0.01,
        "karma:global:diffuselimit": 2,
        "karma:global:reflectlimit": 4,
        "karma:global:volumesteprate": 0.25,
    },
    "production": {
        "karma:global:pathtracedsamples": 256,
        "karma:global:minpathtracedsamples": 16,
        "karma:global:pixeloracle": "variance",
        "karma:global:convergencethreshold": 0.005,
        "karma:global:diffuselimit": 4,
        "karma:global:reflectlimit": 6,
        "karma:global:volumesteprate": 0.5,
    },
}


def apply_karma_preset(karma_props_path, preset_name):
    """Apply a quality preset to Karma render properties."""
    node = hou.node(karma_props_path)
    if not node:
        return

    preset = KARMA_QUALITY_PRESETS.get(preset_name)
    if not preset:
        print(f"Unknown preset: {preset_name}")
        print(f"Available: {list(KARMA_QUALITY_PRESETS.keys())}")
        return

    for parm_name, value in preset.items():
        p = node.parm(parm_name)
        if p:
            p.set(value)
    print(f"Applied '{preset_name}' preset to {karma_props_path}")

apply_karma_preset("/stage/karmarenderproperties1", "lighting")
```

```python
# Denoising configuration
import hou

def configure_denoiser(karma_props_path, enable=True, method="oidn"):
    """Configure Karma denoiser.
    Methods: 'oidn' (Intel CPU), 'optix' (NVIDIA GPU), 'none'
    Requires denoise_albedo and denoise_normal auxiliary AOVs.
    Rule: higher base samples (64-128) + denoise > low samples (16) + heavy denoise
    """
    node = hou.node(karma_props_path)
    if not node:
        return

    if node.parm("karma:global:enabledenoise"):
        node.parm("karma:global:enabledenoise").set(1 if enable else 0)
    if node.parm("karma:global:denoisemode"):
        node.parm("karma:global:denoisemode").set(method)

    print(f"Denoiser: {'enabled' if enable else 'disabled'} ({method})")

configure_denoiser("/stage/karmarenderproperties1", enable=True, method="oidn")
```

```python
# Motion blur settings
import hou

def configure_motion_blur(karma_props_path, enable=True, shutter_open=-0.25, shutter_close=0.25):
    """Configure motion blur on Karma.
    Default shutter: (-0.25, 0.25) centered.
    VFX standard: (-0.5, 0.5) centered for full-frame blur.
    xform_motionsamples=2 enables transform blur.
    geo_motionsamples=2 enables deformation blur (cloth, muscle)."""
    node = hou.node(karma_props_path)
    if not node:
        return

    if enable:
        if node.parm("karma:object:xform_motionsamples"):
            node.parm("karma:object:xform_motionsamples").set(2)
        if node.parm("karma:global:shutteropen"):
            node.parm("karma:global:shutteropen").set(shutter_open)
        if node.parm("karma:global:shutterclose"):
            node.parm("karma:global:shutterclose").set(shutter_close)
        # Deformation blur (set to 2 for cloth/muscle/waves)
        if node.parm("karma:object:geo_motionsamples"):
            node.parm("karma:object:geo_motionsamples").set(2)
    else:
        if node.parm("karma:object:xform_motionsamples"):
            node.parm("karma:object:xform_motionsamples").set(1)  # 1=off

    print(f"Motion blur: {'on' if enable else 'off'}, shutter=[{shutter_open}, {shutter_close}]")

configure_motion_blur("/stage/karmarenderproperties1")
```

```python
# Troubleshooting: diagnose common render issues
import hou

def diagnose_black_render(rop_path):
    """Check common causes of black render output."""
    rop = hou.node(rop_path)
    if not rop:
        print(f"ROP not found: {rop_path}")
        return

    issues = []

    # 1. Camera assigned?
    camera = rop.evalParm("override_camera")
    if not camera or camera == "":
        issues.append("No camera assigned (override_camera is empty)")

    # 2. LOP path valid?
    loppath = rop.evalParm("loppath")
    lop_node = hou.node(loppath) if loppath else None
    if not lop_node:
        issues.append(f"Invalid loppath: '{loppath}'")

    # 3. Output path set?
    output = rop.evalParm("outputimage")
    if not output or output == "":
        issues.append("No output path (outputimage is empty)")

    # 4. Resolution override correct type?
    override_res = rop.evalParm("override_res")
    if override_res == "":
        issues.append("override_res is empty string (no resolution set)")

    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("ROP configuration looks correct")
        print("If still black: check lights exist with exposure > 0")
        print("Check objects aren't set to invisible")
    return issues


def diagnose_fireflies(karma_props_path):
    """Check common causes of fireflies (bright pixels)."""
    node = hou.node(karma_props_path)
    if not node:
        return

    suggestions = []
    samples = node.evalParm("karma:global:pathtracedsamples") if node.parm("karma:global:pathtracedsamples") else 0
    if samples < 128:
        suggestions.append(f"Increase samples from {samples} to 256+")

    oracle = node.evalParm("karma:global:pixeloracle") if node.parm("karma:global:pixeloracle") else ""
    if oracle != "variance":
        suggestions.append("Switch pixel oracle to 'variance' mode")

    threshold = node.evalParm("karma:global:convergencethreshold") if node.parm("karma:global:convergencethreshold") else 0
    if threshold > 0.005:
        suggestions.append(f"Lower convergence threshold from {threshold} to 0.005")

    print("Firefly diagnosis:")
    for s in suggestions:
        print(f"  - {s}")
    print("Also check: light intensity <= 1.0 (Lighting Law), roughness >= 0.001")
    return suggestions


# Output format reference
OUTPUT_FORMATS = {
    ".exr":  "Production (16-bit float, AOV support, deep compositing)",
    ".jpg":  "Quick preview only (8-bit, lossy, no AOVs)",
    ".png":  "Web preview (8-bit, lossless, no AOVs)",
    ".tif":  "Print / high-bit-depth (16-bit integer)",
}

for ext, desc in OUTPUT_FORMATS.items():
    print(f"  {ext}: {desc}")
```

```python
# Render with soho_foreground for synchronous output
import hou

def render_synchronous(rop_path, start_frame=None, end_frame=None):
    """Render with soho_foreground=1 for synchronous file write.
    WARNING: blocks Houdini entirely -- do NOT use for heavy scenes.
    Default soho_foreground=0 returns before render is done."""
    rop = hou.node(rop_path)
    if not rop:
        return

    # soho_foreground=1 required for reliable file existence after render()
    rop.parm("soho_foreground").set(1)

    if start_frame and end_frame:
        rop.parm("trange").set(1)  # Render Frame Range
        rop.parm("f1").set(start_frame)
        rop.parm("f2").set(end_frame)

    rop.render()
    output = rop.evalParm("outputimage")
    print(f"Render complete: {output}")

# Karma XPU file flush: 10-15s delay between render() and file on disk
# Poll with 0.25s interval for up to 15s after render returns
```

## Common Mistakes
- Using `rop.render(output_file=...)` -- does NOT work for usdrender ROPs; set `outputimage` parm directly
- Setting `override_res` as int instead of string -- it's a string menu: `""`, `"scale"`, `"specific"`
- Camera as Houdini node path instead of USD prim path -- use `/cameras/render_cam` not `/stage/render_cam`
- Light intensity > 1.0 -- violates Lighting Law; use exposure for brightness
- Roughness exactly 0.0 -- causes fireflies; use 0.001 minimum
- Low samples (16) with heavy denoiser -- produces smearing; use 64-128 base samples
- soho_foreground=1 on heavy scenes -- blocks Houdini; WebSocket server becomes unresponsive
- Denoising utility AOVs (depth, normal, crypto) -- only denoise beauty pass
