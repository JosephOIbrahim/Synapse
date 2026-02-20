# Karma XPU Material Constraints

## Triggers
karma xpu, xpu material, xpu limitation, materialx only, xpu shader,
xpu compatibility, gpu render, xpu vs cpu, xpu unsupported

## Context
Karma XPU (GPU-accelerated) supports MaterialX shaders ONLY — no VEX shaders, no RSL, no custom shader types. Some MaterialX features are limited on XPU compared to CPU. Always verify material compatibility before switching to XPU.

## Code

```python
# Check if current materials are XPU-compatible
import hou
from pxr import UsdShade

stage = hou.node("/stage/karmarendersettings1").stage()

xpu_issues = []
xpu_warnings = []

for prim in stage.Traverse():
    if prim.IsA(UsdShade.Material):
        mat = UsdShade.Material(prim)
        mat_path = str(prim.GetPath())

        # Check surface shader
        surface = mat.GetSurfaceOutput()
        if not surface:
            continue

        sources = surface.GetConnectedSources()
        if not sources:
            continue

        shader_prim = sources[0][0].GetPrim()
        shader_id = str(shader_prim.GetAttribute("info:id").Get() or "")

        # XPU requires MaterialX shaders (ND_ prefix)
        if not shader_id.startswith("ND_"):
            xpu_issues.append(
                f"INCOMPATIBLE: {mat_path} uses non-MaterialX shader: {shader_id}"
            )
            continue

        # Check for XPU-limited MaterialX features
        shader = UsdShade.Shader(shader_prim)

        # SSS: XPU only supports random_walk, not burley or brute_force
        sss_input = shader.GetInput("subsurface")
        if sss_input and sss_input.Get() and float(sss_input.Get()) > 0:
            xpu_warnings.append(
                f"WARNING: {mat_path} uses SSS — XPU only supports random_walk mode"
            )

        # Transmission with thin-walled: limited on XPU
        transmission = shader.GetInput("transmission")
        thin_walled = shader.GetInput("thin_walled")
        if (transmission and transmission.Get() and float(transmission.Get()) > 0 and
            thin_walled and thin_walled.Get()):
            xpu_warnings.append(
                f"WARNING: {mat_path} uses thin-walled transmission — may differ on XPU"
            )

# Report
if xpu_issues:
    print("XPU INCOMPATIBLE materials (will render as default grey):")
    for issue in xpu_issues:
        print(f"  {issue}")
else:
    print("All materials are XPU-compatible (MaterialX)")

if xpu_warnings:
    print("\nXPU limitations (will render but may differ from CPU):")
    for w in xpu_warnings:
        print(f"  {w}")
```

```python
# Switching between Karma CPU and XPU with validation
import hou

def set_karma_renderer(karma_node_path, use_xpu=False):
    """Switch Karma renderer with material compatibility check."""
    karma = hou.node(karma_node_path)
    if not karma:
        raise RuntimeError(f"Karma node not found: {karma_node_path}")

    target = "BRAY_HdKarmaXPU" if use_xpu else "BRAY_HdKarma"
    current = karma.evalParm("renderer")

    if current == target:
        print(f"Already using {target}")
        return

    if use_xpu:
        # Validate materials before switching to XPU
        stage = karma.stage()
        from pxr import UsdShade
        non_mtlx = []
        for prim in stage.Traverse():
            if prim.IsA(UsdShade.Shader):
                sid = str(prim.GetAttribute("info:id").Get() or "")
                if sid and not sid.startswith("ND_") and not sid.startswith("mtlx"):
                    non_mtlx.append(str(prim.GetPath()))

        if non_mtlx:
            print(f"WARNING: {len(non_mtlx)} non-MaterialX shaders found:")
            for path in non_mtlx[:5]:
                print(f"  {path}")
            print("These will render as default material on XPU")

    karma.parm("renderer").set(target)
    print(f"Renderer set to: {target}")

# Usage
set_karma_renderer("/stage/karmarendersettings1", use_xpu=True)
set_karma_renderer("/stage/karmarendersettings1", use_xpu=False)
```

```python
# XPU feature support reference
XPU_SUPPORT = {
    # Feature                    CPU    XPU    Notes
    "MaterialX Standard Surface": (True, True,  "Full support"),
    "VEX Shaders":                (True, False, "NOT supported on XPU"),
    "Custom AOVs (LPE)":         (True, False, "Limited on XPU"),
    "Standard AOVs (N, P, Z)":   (True, True,  "Basic set supported"),
    "SSS (random_walk)":         (True, True,  "Supported"),
    "SSS (burley)":              (True, False, "CPU only"),
    "Volumes":                   (True, True,  "Basic volume support"),
    "Volume SSS":                (True, False, "CPU only"),
    "Deep Output":               (True, False, "CPU only"),
    "Cryptomatte":               (True, True,  "Supported since H20.5"),
    "Motion Blur":               (True, True,  "Supported"),
    "Displacement":              (True, True,  "Supported"),
    "Hair/Curves":               (True, True,  "Supported"),
    "Nested Dielectrics":        (True, True,  "Limited on XPU"),
    "Texture Streaming":         (True, True,  "GPU VRAM limited"),
}

# Print compatibility table
print(f"{'Feature':<35} {'CPU':>5} {'XPU':>5}")
print("-" * 50)
for feature, (cpu, xpu, notes) in XPU_SUPPORT.items():
    cpu_str = "Yes" if cpu else "No"
    xpu_str = "Yes" if xpu else "NO"
    print(f"{feature:<35} {cpu_str:>5} {xpu_str:>5}  {notes}")
```

## Expected Output
```
All materials are XPU-compatible (MaterialX)

XPU limitations (will render but may differ from CPU):
  WARNING: /materials/skin uses SSS — XPU only supports random_walk mode

Renderer set to: BRAY_HdKarmaXPU
```

## Common Mistakes
- Switching to XPU without checking materials — VEX shaders silently render as default grey
- Assuming all MaterialX features work identically on XPU — SSS and transmission may differ
- Expecting custom LPE AOVs on XPU — only standard AOVs (color, alpha, depth, N, P) work
- Not checking GPU VRAM for texture-heavy scenes — XPU textures must fit in GPU memory
- Assuming XPU is always faster — for simple scenes with few bounces, CPU can be comparable
