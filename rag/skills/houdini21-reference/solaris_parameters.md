# Solaris/LOP Parameter Reference

## Triggers
solaris parameter, lop parameter, usd parameter, encoded name, xn__ parameter,
light parameter, camera parameter, material parameter, karma parameter, usd render

## Context
USD/LOP parameters use encoded names (xn__...) that don't match their friendly
display names. This reference provides code for looking up, reading, and setting
these parameters programmatically.

## Code

```python
# Look up encoded parameter names on any LOP node
import hou

def list_usd_parms(node_path):
    """List all parameters on a LOP node with their encoded names."""
    node = hou.node(node_path)
    if not node:
        print(f"Node not found: {node_path}")
        return

    parms = node.parms()
    for p in sorted(parms, key=lambda x: x.name()):
        name = p.name()
        label = p.description()
        val = p.eval()
        # Filter to USD-encoded names
        if name.startswith("xn__") or name in ("focalLength", "fStop", "focusDistance"):
            print(f"  {label:<30} {name:<45} = {val}")

list_usd_parms("/stage/domelight1")
```

```python
# Light parameters -- ALL light types
import hou

# Common encoded parameter names for USD lights
LIGHT_PARMS = {
    "intensity":         "xn__inputsintensity_i0a",       # float, always 1.0
    "color":             "xn__inputscolor_kya",            # vec3 RGB
    "exposure":          "xn__inputsexposure_vya",         # float, stops
    "exposure_control":  "xn__inputsexposure_control_wcb", # string, "set"
    "texture_file":      "xn__inputstexturefile_i1a",      # string, HDRI path
    "enable_colortemp":  "xn__inputsenablecolortemperature_r5a",  # bool
    "color_temperature": "xn__inputscolortemperature_u5a", # float, Kelvin
}

def configure_dome_light(node_path, hdri_path, exposure=0.25):
    """Configure a dome light with HDRI and exposure."""
    node = hou.node(node_path)
    if not node:
        return

    # Intensity ALWAYS 1.0 (Lighting Law)
    node.parm(LIGHT_PARMS["intensity"]).set(1.0)

    # Enable exposure
    node.parm(LIGHT_PARMS["exposure_control"]).set("set")
    node.parm(LIGHT_PARMS["exposure"]).set(exposure)

    # Set HDRI texture
    node.parm(LIGHT_PARMS["texture_file"]).set(hdri_path)

    print(f"Dome light configured: exposure={exposure}, HDRI={hdri_path}")

configure_dome_light(
    "/stage/domelight1",
    "D:/GreyscaleGorillaAssetLibrary/studio_02.exr",
    exposure=0.25
)
```

```python
# Key light with color temperature
import hou

def configure_key_light(node_path, exposure=1.0, color_temp=5500):
    """Configure a key light with color temperature."""
    node = hou.node(node_path)
    if not node:
        return

    LIGHT_PARMS = {
        "intensity":         "xn__inputsintensity_i0a",
        "exposure":          "xn__inputsexposure_vya",
        "exposure_control":  "xn__inputsexposure_control_wcb",
        "enable_colortemp":  "xn__inputsenablecolortemperature_r5a",
        "color_temperature": "xn__inputscolortemperature_u5a",
    }

    node.parm(LIGHT_PARMS["intensity"]).set(1.0)  # Lighting Law
    node.parm(LIGHT_PARMS["exposure_control"]).set("set")
    node.parm(LIGHT_PARMS["exposure"]).set(exposure)
    node.parm(LIGHT_PARMS["enable_colortemp"]).set(True)
    node.parm(LIGHT_PARMS["color_temperature"]).set(color_temp)

    print(f"Key light: exposure={exposure}, temp={color_temp}K")

configure_key_light("/stage/rectlight1", exposure=1.0, color_temp=5500)
```

```python
# Camera parameters
import hou

def configure_camera(node_path, focal_length=50, fstop=5.6, focus_dist=5.0,
                     pos=(0, 1.5, 5), rot=(-10, 0, 0)):
    """Configure a USD camera LOP."""
    node = hou.node(node_path)
    if not node:
        return

    # Camera-specific parms (not encoded)
    node.parm("focalLength").set(focal_length)       # mm
    node.parm("fStop").set(fstop)                    # f-number
    node.parm("focusDistance").set(focus_dist)        # scene units
    node.parm("horizontalAperture").set(36.0)        # 35mm full frame

    # Transform (standard Houdini parms)
    node.parmTuple("t").set(pos)
    node.parmTuple("r").set(rot)

    print(f"Camera: focal={focal_length}mm, f/{fstop}, pos={pos}")

configure_camera("/stage/camera1", focal_length=35, pos=(3, 2, 6), rot=(-15, 25, 0))
```

```python
# MaterialX Standard Surface parameters
import hou

def configure_mtlx_surface(subnet_path, base_color=(0.8, 0.2, 0.1),
                            metalness=0.0, roughness=0.3, coat=0.0):
    """Configure a MaterialX standard surface shader."""
    node = hou.node(subnet_path)
    if not node:
        return

    # Find the mtlxstandard_surface node inside the subnet
    surface = None
    for child in node.children():
        if child.type().name() == "mtlxstandard_surface":
            surface = child
            break

    if not surface:
        print(f"No mtlxstandard_surface found in {subnet_path}")
        return

    # Parameter names are NOT encoded (MaterialX uses direct names)
    surface.parm("base_colorr").set(base_color[0])
    surface.parm("base_colorg").set(base_color[1])
    surface.parm("base_colorb").set(base_color[2])
    surface.parm("metalness").set(metalness)
    surface.parm("specular_roughness").set(roughness)
    surface.parm("coat").set(coat)

    print(f"Material: color={base_color}, metal={metalness}, rough={roughness}")
```

```python
# USD Render ROP parameters (in /out)
import hou

def configure_usdrender_rop(rop_path, lop_path="/stage", camera="/cameras/cam1",
                             width=1920, height=1080, output_path="$HIP/render/shot.$F4.exr"):
    """Configure a usdrender ROP for Karma rendering."""
    rop = hou.node(rop_path)
    if not rop:
        # Create it
        out = hou.node("/out")
        rop = out.createNode("usdrender", "karma_rop")

    # LOP path -- points to the display node in /stage
    rop.parm("loppath").set(lop_path)

    # Renderer
    rop.parm("renderer").set("BRAY_HdKarma")  # or BRAY_HdKarmaXPU

    # Camera (USD prim path, NOT Houdini node path)
    rop.parm("override_camera").set(camera)

    # Resolution override
    rop.parm("override_res").set("specific")  # "", "scale", or "specific"
    rop.parm("res_user1").set(width)
    rop.parm("res_user2").set(height)

    # Output image
    rop.parm("outputimage").set(output_path)

    print(f"ROP configured: {width}x{height}, camera={camera}")

configure_usdrender_rop("/out/karma_rop1")
```

```python
# Assign Material parameters
import hou

def assign_material(stage_path="/stage", geo_prim="/geo/hero/shape",
                    material_prim="/materials/hero_mtlx"):
    """Create an assign material node in the stage network."""
    stage = hou.node(stage_path)
    if not stage:
        return

    assign = stage.createNode("assignmaterial", "mat_assign")

    # Prim Pattern -- EXACT USD prim path (not wildcard)
    assign.parm("primpattern1").set(geo_prim)

    # Material Path -- exact USD material prim path
    assign.parm("matspecpath1").set(material_prim)

    print(f"Assigned: {geo_prim} -> {material_prim}")
    return assign

assign_material(geo_prim="/rubbertoy/geo/shape", material_prim="/materials/rubber")
```

## Expected Output
```
Dome light configured: exposure=0.25, HDRI=D:/GreyscaleGorillaAssetLibrary/studio_02.exr
Key light: exposure=1.0, temp=5500K
Camera: focal=35mm, f/5.6, pos=(3, 2, 6)
```

## Common Mistakes
- Using friendly name "intensity" instead of encoded "xn__inputsintensity_i0a"
- Setting intensity > 1.0 instead of using exposure (Lighting Law violation)
- Using Houdini node path for camera instead of USD prim path
- override_res is a string menu ("", "scale", "specific") not an int
- MaterialX parms use direct names (base_colorr) while light parms use xn__ encoding
- Forgetting to set exposure_control to "set" before exposure has any effect
