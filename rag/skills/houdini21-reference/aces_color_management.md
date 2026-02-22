# ACES Color Management in Houdini 21

## Triggers
aces, color management, ocio, opencolorio, color space, acescg, srgb, raw,
texture color space, display transform, linear rendering, color pipeline

## Context
ACES (Academy Color Encoding System) provides a standardized color pipeline for VFX.
Houdini 21 integrates ACES via OpenColorIO. This reference covers setup, texture handling,
Karma rendering, and compositing with code examples.

## Code

```python
# Configure ACES OCIO environment
import hou
import os

def check_ocio_config():
    """Verify OCIO is configured correctly in Houdini."""
    ocio_path = os.environ.get("OCIO", "")
    if not ocio_path:
        print("OCIO environment variable not set")
        print("Fix: Set OCIO to your ACES config path")
        print('  Windows: setx OCIO "D:\\ACES\\cg-config-v2.0.0_aces-v1.3_ocio-v2.3.ocio"')
        print('  houdini.env: OCIO = "D:/ACES/cg-config-v2.0.0.ocio"')
        return False

    if not os.path.exists(ocio_path):
        print(f"OCIO config not found: {ocio_path}")
        return False

    print(f"OCIO config: {ocio_path}")

    # Check if Houdini picked it up
    try:
        import PyOpenColorIO as ocio
        config = ocio.GetCurrentConfig()
        print(f"Active OCIO config: {config.getDescription()}")
        print(f"Color spaces: {config.getNumColorSpaces()}")

        # List key color spaces
        for cs_name in ["ACEScg", "ACES2065-1", "sRGB", "Raw"]:
            cs = config.getColorSpace(cs_name)
            if cs:
                print(f"  Found: {cs_name}")
            else:
                print(f"  MISSING: {cs_name}")
    except ImportError:
        print("PyOpenColorIO not available -- check Houdini Color Settings UI")

    return True

check_ocio_config()
```

```python
# Color space assignments for textures in MaterialX
import hou

# Color space rules:
COLOR_SPACE_RULES = {
    # Color textures -> srgb_texture (convert to ACEScg for rendering)
    "albedo":     "srgb_texture",
    "diffuse":    "srgb_texture",
    "base_color": "srgb_texture",
    "emission":   "srgb_texture",

    # Data textures -> Raw (NO color transform)
    "normal":       "Raw",
    "roughness":    "Raw",
    "metalness":    "Raw",
    "displacement": "Raw",
    "opacity":      "Raw",
    "height":       "Raw",
    "ao":           "Raw",
    "mask":         "Raw",

    # HDRI -> linear (already in scene-referred space)
    "hdri":    "scene-linear Rec.709-sRGB",
    "env_map": "scene-linear Rec.709-sRGB",
}

def set_texture_colorspace(mtlximage_node_path, texture_type):
    """Set correct color space on a MaterialX image node."""
    node = hou.node(mtlximage_node_path)
    if not node:
        return

    colorspace = COLOR_SPACE_RULES.get(texture_type, "srgb_texture")
    if node.parm("colorspace"):
        node.parm("colorspace").set(colorspace)
        print(f"Set {texture_type} -> {colorspace}")
    else:
        print(f"No colorspace parm on {mtlximage_node_path}")

# Usage: set color spaces on all texture nodes in a material
set_texture_colorspace("/stage/materiallibrary1/hero_mat/base_color_tex", "base_color")
set_texture_colorspace("/stage/materiallibrary1/hero_mat/roughness_tex", "roughness")
set_texture_colorspace("/stage/materiallibrary1/hero_mat/normal_tex", "normal")
```

```python
# Verify texture color spaces across all materials
import hou
from pxr import UsdShade, Sdf

def audit_texture_colorspaces(stage_node_path):
    """Check all texture nodes for correct color space assignment."""
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'stage'):
        return

    stage = node.stage()
    issues = []

    for prim in stage.Traverse():
        if not prim.IsA(UsdShade.Shader):
            continue

        shader = UsdShade.Shader(prim)
        shader_id = prim.GetAttribute("info:id").Get() or ""

        # Check image nodes
        if "image" not in shader_id.lower():
            continue

        file_input = shader.GetInput("file")
        cs_input = shader.GetInput("colorspace")

        if file_input:
            file_val = file_input.Get()
            file_path = str(file_val.path) if isinstance(file_val, Sdf.AssetPath) else str(file_val)
            cs_val = cs_input.Get() if cs_input else "unknown"

            # Check for common issues
            lower_path = file_path.lower()
            if any(kw in lower_path for kw in ("normal", "nrm", "_n.", "_n_")):
                if cs_val != "Raw":
                    issues.append(
                        f"Normal map should be Raw, got '{cs_val}': {prim.GetPath()}"
                    )
            elif any(kw in lower_path for kw in ("rough", "metal", "disp", "height", "ao")):
                if cs_val != "Raw":
                    issues.append(
                        f"Data texture should be Raw, got '{cs_val}': {prim.GetPath()}"
                    )

    if issues:
        print(f"Color space issues ({len(issues)}):")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("All texture color spaces look correct")

    return issues

audit_texture_colorspaces("/stage/karmarendersettings1")
```

```python
# Karma render output configuration for ACES
import hou

def configure_aces_render_output(karma_node_path, output_path="$HIP/render/shot.$F4.exr"):
    """Configure Karma output for ACES-compliant pipeline."""
    node = hou.node(karma_node_path)
    if not node:
        return

    # Karma renders in ACEScg (linear) when OCIO is configured
    # Output EXR should be in ACEScg -- NO display transform baked in
    if node.parm("picture"):
        node.parm("picture").set(output_path)

    # CRITICAL: Do NOT bake display transform into EXR
    # Apply view transform at display/delivery only
    # Beauty EXR: ACEScg (linear)
    # Utility AOVs (depth, normal, motion): Raw

    print(f"Render output: {output_path}")
    print("Color space: ACEScg (linear, no display transform)")
    print("Apply ACES Output Transform at display/delivery only")

configure_aces_render_output("/stage/karma1")
```

```python
# Convert EXR to sRGB JPEG for preview using iconvert
import hou
import subprocess
import os

def exr_to_jpeg_aces(exr_path, jpeg_path=None):
    """Convert ACEScg EXR to sRGB JPEG for preview."""
    if jpeg_path is None:
        jpeg_path = exr_path.rsplit(".", 1)[0] + ".jpg"

    hfs = os.environ.get("HFS", "")
    iconvert = os.path.join(hfs, "bin", "iconvert.exe")

    if not os.path.exists(iconvert):
        print(f"iconvert not found at {iconvert}")
        return

    # iconvert applies OCIO display transform automatically
    # when OCIO env var is set
    expanded_exr = hou.text.expandString(exr_path)
    expanded_jpg = hou.text.expandString(jpeg_path)

    cmd = [iconvert, expanded_exr, expanded_jpg]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"Converted: {expanded_exr} -> {expanded_jpg}")
    else:
        print(f"Conversion failed: {result.stderr}")

exr_to_jpeg_aces("$HIP/render/shot.0001.exr")
```

```python
# OCIO color space conversion in Python
import hou

def convert_color(rgb, from_space, to_space):
    """Convert a color value between ACES color spaces."""
    try:
        import PyOpenColorIO as ocio
        config = ocio.GetCurrentConfig()
        processor = config.getProcessor(from_space, to_space)
        cpu = processor.getDefaultCPUProcessor()

        # Convert single RGB value
        result = list(rgb)
        cpu.applyRGB(result)
        return tuple(result)
    except ImportError:
        print("PyOpenColorIO not available")
        return rgb

# Example: convert sRGB color to ACEScg for use in shaders
srgb_red = (0.8, 0.1, 0.05)
acescg_red = convert_color(srgb_red, "sRGB", "ACEScg")
print(f"sRGB {srgb_red} -> ACEScg {acescg_red}")
```

## Expected Output
```
OCIO config: D:\ACES\cg-config-v2.0.0_aces-v1.3_ocio-v2.3.ocio
Active OCIO config: ACES CG Config v2.0.0
  Found: ACEScg
  Found: ACES2065-1
  Found: sRGB
  Found: Raw
Set base_color -> srgb_texture
Set roughness -> Raw
Set normal -> Raw
All texture color spaces look correct
```

## Common Mistakes
- Applying ACES transform to data textures (normal, roughness) -- set to Raw
- Baking display transform into EXR render output -- keep as ACEScg linear
- Double-converting sRGB textures (washed out or oversaturated colors)
- Using different OCIO configs across tools -- standardize on one version
- Viewing linear EXR without display transform -- looks flat/dark, not broken
- Setting HDRI to sRGB instead of scene-linear -- massively changes exposure
