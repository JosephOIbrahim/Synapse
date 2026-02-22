# The /Render Scene Graph Branch Convention

## Triggers
render branch, /Render, render prim location, renderSettingsPrimPath, render scene graph,
where render settings, render prim path, render configuration location

## Context
USD convention places all render configuration under `/Render/` in the scene graph. Karma LOP follows this automatically. The `renderSettingsPrimPath` stage metadata tells renderers which settings to use.

## Code

```python
# Querying all render configurations in a USD stage
import hou
from pxr import UsdRender, Usd

stage = hou.node("/stage/karmarendersettings1").stage()

# --- Find all render settings under /Render/ ---
render_root = stage.GetPrimAtPath("/Render")
if render_root.IsValid():
    print("Render branch contents:")
    for prim in Usd.PrimRange(render_root):
        schema = prim.GetTypeName()
        print(f"  {prim.GetPath()}  ({schema})")
else:
    print("WARNING: No /Render branch found in stage")


# --- Check stage-level renderSettingsPrimPath metadata ---
# This tells the renderer which RenderSettings prim to use
root_layer = stage.GetRootLayer()
render_settings_path = stage.GetMetadata("renderSettingsPrimPath")
print(f"Active render settings: {render_settings_path}")
# Typically: /Render/rendersettings1


# --- List all RenderSettings anywhere in stage (not just /Render/) ---
all_settings = []
for prim in stage.Traverse():
    if prim.IsA(UsdRender.Settings):
        all_settings.append(prim.GetPath())
print(f"All RenderSettings prims: {all_settings}")

# Warn if any are outside /Render/
for path in all_settings:
    if not str(path).startswith("/Render"):
        print(f"WARNING: RenderSettings outside /Render branch: {path}")
```

```python
# Creating render configuration under /Render/ via Karma LOP
import hou

stage_net = hou.node("/stage")

# Karma LOP automatically creates prims under /Render/
karma = stage_net.createNode("karmarendersettings", "my_render")
karma.parm("camera").set("/cameras/render_cam")
karma.parm("picture").set("$HIP/render/beauty.$F4.exr")
karma.parm("resolutionx").set(1920)
karma.parm("resolutiony").set(1080)

# After cooking, the stage will have:
# /Render/my_render          (RenderSettings)
# /Render/my_render/product1 (RenderProduct)
# /Render/my_render/product1/color (RenderVar)
# /Render/my_render/product1/alpha (RenderVar)

# Multiple render configs: create multiple Karma LOPs
karma_preview = stage_net.createNode("karmarendersettings", "preview")
karma_preview.parm("resolutionx").set(640)
karma_preview.parm("resolutiony").set(360)
karma_preview.parm("samplesperpixel").set(4)

# Each creates its own branch:
# /Render/my_render/...
# /Render/preview/...
```

```python
# Switching active render settings via renderSettingsPrimPath
from pxr import Sdf

stage = hou.node("/stage/merge_renders").stage()

# List available render configs
configs = []
for prim in stage.Traverse():
    if prim.IsA(UsdRender.Settings):
        configs.append(str(prim.GetPath()))
        print(f"Available: {prim.GetPath()}")

# Set active render settings (stage metadata)
# The renderer uses this to pick which RenderSettings to render with
if configs:
    stage.SetMetadata("renderSettingsPrimPath", configs[0])
    print(f"Active render config: {configs[0]}")
```

## Expected Scene Graph
```
/Render/                              (Scope or Xform)
  ├─ rendersettings1                  (UsdRenderSettings)
  │    ├─ resolution: (1920, 1080)
  │    ├─ camera → /cameras/render_cam
  │    └─ product1                    (UsdRenderProduct)
  │         ├─ productName: "beauty.$F4.exr"
  │         ├─ color                  (UsdRenderVar)
  │         └─ alpha                  (UsdRenderVar)
  └─ preview                          (UsdRenderSettings)
       ├─ resolution: (640, 360)
       └─ product1                    (UsdRenderProduct)
            └─ ...
```

## Common Mistakes
- Assuming render prims can live anywhere — renderers expect them under `/Render/`
- Not setting `renderSettingsPrimPath` metadata — renderer may pick the wrong config
- Creating RenderSettings at `/rendersettings1` instead of `/Render/rendersettings1`
- Manually creating render prims instead of using Karma LOP — miss auto-configured AOVs
