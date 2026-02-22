# Render Delegate Detection and Compatibility

## Triggers
render delegate, hydra delegate, available renderers, renderer compatibility,
render delegate detection, which renderer, BRAY_HdKarma, render plugin, AOV support

## Context
Houdini uses Hydra render delegates. Available delegates depend on installed plugins. Use the Hydra registry or Houdini's `usdrenderers.py` to query what's available and check AOV/feature compatibility per delegate.

## Code

```python
# Query available render delegates in Houdini
import hou

# Method 1: Via hou.lop module (Houdini 21+)
try:
    delegates = hou.lop.renderDelegates()
    for d in delegates:
        print(f"Delegate: {d.name()}")
        print(f"  Display name: {d.displayName()}")
        print(f"  Plugin: {d.pluginId()}")
except AttributeError:
    print("hou.lop.renderDelegates() not available in this version")


# Method 2: Via USD Hydra registry (pxr API)
from pxr import UsdImagingGL

# Get all registered render delegates
delegate_ids = UsdImagingGL.Engine.GetRendererPlugins()
for plugin_id in delegate_ids:
    display_name = UsdImagingGL.Engine.GetRendererDisplayName(plugin_id)
    print(f"  {plugin_id} -> {display_name}")

# Common delegates:
# BRAY_HdKarma     -> Karma CPU
# BRAY_HdKarmaXPU  -> Karma XPU
# HdStormRendererPlugin -> Storm (GL viewport)
# HdArnoldRendererPlugin -> Arnold (if installed)
# HdPrmanLoaderRendererPlugin -> RenderMan (if installed)
```

```python
# Check which render delegate a Karma LOP is using
import hou

karma = hou.node("/stage/karmarendersettings1")
renderer = karma.evalParm("renderer")
print(f"Current delegate: {renderer}")

# Map delegate IDs to capabilities
DELEGATE_CAPABILITIES = {
    "BRAY_HdKarma": {
        "name": "Karma CPU",
        "vex_shaders": True,
        "materialx": True,
        "custom_aovs": True,
        "deep_output": True,
        "sss_modes": ["random_walk", "burley", "brute_force"],
        "volumes": True,
    },
    "BRAY_HdKarmaXPU": {
        "name": "Karma XPU",
        "vex_shaders": False,       # MaterialX ONLY
        "materialx": True,
        "custom_aovs": False,       # Limited AOV support
        "deep_output": False,
        "sss_modes": ["random_walk"],
        "volumes": True,            # Limited volume support
    },
    "HdStormRendererPlugin": {
        "name": "Storm (GL)",
        "vex_shaders": False,
        "materialx": True,
        "custom_aovs": False,
        "deep_output": False,
        "sss_modes": [],
        "volumes": False,
    },
}

caps = DELEGATE_CAPABILITIES.get(renderer, {})
if caps:
    print(f"Delegate: {caps['name']}")
    print(f"  VEX shaders: {'Yes' if caps['vex_shaders'] else 'NO'}")
    print(f"  MaterialX: {'Yes' if caps['materialx'] else 'NO'}")
    print(f"  Custom AOVs: {'Yes' if caps['custom_aovs'] else 'NO'}")
    print(f"  SSS modes: {caps['sss_modes']}")
```

```python
# Checking AOV support per render delegate
import hou
from pxr import UsdRender

stage = hou.node("/stage/karmarendersettings1").stage()

# Find all RenderVar (AOV) prims
aovs = []
for prim in stage.Traverse():
    if prim.IsA(UsdRender.Var):
        source = prim.GetAttribute("sourceName").Get()
        dtype = prim.GetAttribute("dataType").Get()
        aovs.append((str(prim.GetPath()), source, dtype))
        print(f"AOV: {source} ({dtype}) at {prim.GetPath()}")

# Common Karma AOVs that work on both CPU and XPU:
# "color" (color3f) — beauty pass
# "alpha" (float) — alpha channel
# "depth" (float) — camera depth (Z)
# "N" (normal3f) — world-space normals
# "P" (point3f) — world-space position

# CPU-only AOVs:
# "diffuse" (color3f) — diffuse light contribution
# "specular" (color3f) — specular contribution
# "emission" (color3f) — emission contribution
# "sss" (color3f) — subsurface scattering
# "indirect_diffuse" (color3f) — GI diffuse
# "indirect_specular" (color3f) — GI specular
# Custom LPE expressions (e.g., "lpe:C<RD>.*<L>")
```

```python
# Validating materials against render delegate
import hou
from pxr import UsdShade

stage = hou.node("/stage/karmarendersettings1").stage()
renderer = hou.node("/stage/karmarendersettings1").evalParm("renderer")

issues = []
for prim in stage.Traverse():
    if prim.IsA(UsdShade.Material):
        mat = UsdShade.Material(prim)

        # Check surface shader
        surface = mat.GetSurfaceOutput()
        if surface:
            sources = surface.GetConnectedSources()
            if sources:
                shader_prim = sources[0][0].GetPrim()
                shader_id = shader_prim.GetAttribute("info:id").Get()

                # XPU doesn't support VEX shaders
                if "XPU" in renderer and shader_id and "vex" in str(shader_id).lower():
                    issues.append(
                        f"VEX shader {shader_prim.GetPath()} incompatible "
                        f"with Karma XPU — use MaterialX instead"
                    )

if issues:
    print("COMPATIBILITY ISSUES:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("All materials compatible with current render delegate")
```

## Expected Output
```
Available delegates:
  BRAY_HdKarma -> Karma CPU
  BRAY_HdKarmaXPU -> Karma XPU
  HdStormRendererPlugin -> Storm

Current delegate: BRAY_HdKarma
  VEX shaders: Yes
  MaterialX: Yes
  Custom AOVs: Yes
```

## Common Mistakes
- Assuming all AOVs work on Karma XPU — custom LPE and many standard AOVs are CPU-only
- Using VEX shaders with Karma XPU — silently renders with default material (no error)
- Not checking delegate availability before setting it — plugin may not be installed
- Confusing `HdStormRendererPlugin` (GL preview) with production render delegates
