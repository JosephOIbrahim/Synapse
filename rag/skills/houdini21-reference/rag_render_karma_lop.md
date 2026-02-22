# Karma LOP — Unified Render Configuration

## Triggers
karma lop, karma node, karma settings, karma render node, karma cpu, karma xpu,
render settings lop, karma configuration, set up karma

## Context
The Karma LOP in /stage is the unified render configuration node. It creates RenderSettings + RenderProduct + camera binding in one node. Karma CPU and Karma XPU are separate LOP node types with different capabilities.

## Code

```python
# Creating and configuring a Karma LOP via Python
import hou

stage_net = hou.node("/stage")

# --- Karma CPU (full feature set) ---
karma = stage_net.createNode("karmarendersettings", "karma_cpu")

# Resolution
karma.parm("resolutionx").set(1920)
karma.parm("resolutiony").set(1080)

# Camera — MUST be USD prim path, not Houdini node path
# WRONG: /stage/camera1
# RIGHT: /cameras/camera1
karma.parm("camera").set("/cameras/render_cam")

# Output path — use $F4 for frame padding
karma.parm("picture").set("$HIP/render/beauty.$F4.exr")

# Pixel samples (quality vs speed tradeoff)
# Test renders: 4-8, Production: 64-256
karma.parm("samplesperpixel").set(64)

# Override resolution for test renders
# Values: "" (use above), "scale" (percentage), "specific" (exact)
karma.parm("override_res").set("")  # NOTE: string menu, not int


# --- Karma XPU (GPU-accelerated, MaterialX only) ---
karma_xpu = stage_net.createNode("karmarendersettings", "karma_xpu")
karma_xpu.parm("renderer").set("BRAY_HdKarmaXPU")

# XPU-specific: no VEX shaders, MaterialX only
# XPU-specific: limited AOV support compared to CPU
karma_xpu.parm("resolutionx").set(1920)
karma_xpu.parm("resolutiony").set(1080)
karma_xpu.parm("camera").set("/cameras/render_cam")
karma_xpu.parm("picture").set("$HIP/render/beauty_xpu.$F4.exr")
```

```python
# Reading Karma configuration from an existing node
import hou

karma = hou.node("/stage/karmarendersettings1")
if karma:
    print(f"Resolution: {karma.evalParm('resolutionx')}x{karma.evalParm('resolutiony')}")
    print(f"Camera: {karma.evalParm('camera')}")
    print(f"Output: {karma.evalParm('picture')}")
    print(f"Samples: {karma.evalParm('samplesperpixel')}")
    print(f"Renderer: {karma.evalParm('renderer')}")

    # Check if Karma CPU or XPU
    renderer = karma.evalParm("renderer")
    if "XPU" in renderer:
        print("WARNING: XPU mode — MaterialX shaders only, no VEX")
    else:
        print("CPU mode — full shader support")

    # Get the USD prim paths this node creates
    stage = karma.stage()
    if stage:
        from pxr import UsdRender
        for prim in stage.Traverse():
            if prim.IsA(UsdRender.Settings):
                print(f"  Created RenderSettings: {prim.GetPath()}")
```

```python
# Wiring Karma into a standard Solaris chain
import hou

stage_net = hou.node("/stage")

# Standard chain: merge -> matlib -> camera -> karma
merge = stage_net.node("merge1")          # geometry + lights
camera = stage_net.node("camera1")         # camera LOP
karma = stage_net.createNode("karmarendersettings", "render_settings")

# Wire: merge -> camera -> karma
camera.setInput(0, merge)
karma.setInput(0, camera)

# Set karma as display node for rendering
karma.setDisplayFlag(True)

# Configure
karma.parm("camera").set("/cameras/camera1")
karma.parm("picture").set("$HIP/render/output.$F4.exr")
karma.parm("samplesperpixel").set(8)  # low for test
```

## Expected Scene Graph
```
/Render/
  └─ karmarendersettings1  (UsdRenderSettings)
       ├─ resolution: (1920, 1080)
       ├─ pixelAspectRatio: 1.0
       ├─ camera → /cameras/render_cam
       ├─ renderer: "BRAY_HdKarma" or "BRAY_HdKarmaXPU"
       └─ product1  (UsdRenderProduct)
            ├─ productName: "$HIP/render/beauty.$F4.exr"
            └─ orderedVars → [/Render/.../color, /Render/.../alpha, ...]
```

## Common Mistakes
- Using Houdini node path for camera (`/stage/camera1`) instead of USD prim path (`/cameras/camera1`)
- Forgetting that `override_res` is a string menu (`""`, `"scale"`, `"specific"`), not an integer
- Assuming Karma XPU supports VEX shaders — it only supports MaterialX
- Not setting display flag on Karma node — render won't find the settings
- Setting pixel samples too high for test renders — start at 4-8, scale up
