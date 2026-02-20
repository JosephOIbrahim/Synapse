# Solaris/LOP Node Types Reference

## Triggers
solaris, lop, lops, stage, usd, sopimport, sublayer, reference, merge, edit, camera, light, domelight, rectlight, spherelight, distantlight, disklight, cylinderlight, materiallibrary, assignmaterial, karmarenderproperties, karmarendersettings, usdrender, render settings, render properties, configureprimitive, componentoutput, switch, null, configurestage, sceneimport, sopcreate, instancer, layout, renderproduct, rendersettings, rendergeometrysettings, mtlxstandard_surface, materiallinker, create node lop, lop node python, solaris python, stage node

## Context
Comprehensive Python reference for creating and configuring Solaris (LOP) nodes in Houdini 21 via `hou.node().createNode()` and `parm().set()`. Covers stage management, geometry import, materials, all light types, cameras, render settings, and layout nodes. Lighting Law: intensity is ALWAYS 1.0; brightness is controlled exclusively by exposure (logarithmic, in stops).

## Code

### Stage Management — Merge, Switch, Null, Configure Stage

```python
import hou

stage = hou.node("/stage")

# --- merge: combine multiple LOP input streams ---
# Later inputs are stronger (higher sublayer priority)
merge = stage.createNode("merge", "merge1")
# Connect: merge.setInput(0, geo_branch), merge.setInput(1, light_branch)

# --- switch: pass one of several inputs downstream ---
sw = stage.createNode("switch", "switch1")
sw.parm("input").set(0)  # 0-based index of which input to pass through

# --- null: pass-through marker / output anchor ---
# Convention: name your output null OUTPUT or OUT, set display flag on it
out = stage.createNode("null", "OUTPUT")
out.setDisplayFlag(True)   # blue flag = render/display output

# --- configurestage: global stage metadata ---
cfg = stage.createNode("configurestage", "stage_config")
cfg.parm("upaxis").set("Y")          # "Y" (default) or "Z"
cfg.parm("metersperunit").set(0.01)  # 0.01 = centimetres, 1.0 = metres
cfg.parm("startframe").set(1.0)
cfg.parm("endframe").set(240.0)
cfg.parm("fps").set(24.0)
```

### Geometry — SOP Import

```python
import hou

stage = hou.node("/stage")

# sopimport: bring SOP geometry into the USD stage as a Mesh prim
sop_imp = stage.createNode("sopimport", "geo_import")

# Path to SOP node — use the OUT null of the SOP network
sop_imp.parm("soppath").set("/obj/geo1/OUT")

# Where to place the prim in the USD hierarchy
sop_imp.parm("primpath").set("/World/geo/mesh1")

# Import style: "Flat" or "Hierarchy" (hierarchy preserves SOP groups)
sop_imp.parm("importstyle").set("Flat")

# For animated geometry, set importframe to $F so each frame is re-cooked
sop_imp.parm("importframe").set(hou.frame())  # or expression "$F"
# sop_imp.parm("importframe").setExpression("$F")

# Import SOP primitive groups as USD GeomSubsets (for per-face material assignment)
sop_imp.parm("subsetgroups").set("*")

# GOTCHA: SOP 'Cd' attribute → USD 'displayColor'
#         SOP 'N'  attribute → USD 'normals'
# These mappings happen automatically; no extra parms needed.
```

### Geometry — SOP Create (embedded SOP network inside LOP)

```python
import hou

stage = hou.node("/stage")

# sopcreate: embeds a full SOP network inside a LOP node
sop_create = stage.createNode("sopcreate", "inline_geo")
sop_create.parm("primpath").set("/World/geo/inline_mesh")

# Double-click in UI to enter the embedded SOP network.
# From Python, access the inner network:
inner = sop_create.node("sopnet")
box = inner.createNode("box", "box1")
box.parm("sizex").set(2.0)
box.parm("sizey").set(1.0)
box.parm("sizez").set(2.0)
out = inner.createNode("null", "OUT")
out.setInput(0, box)
out.setDisplayFlag(True)
out.setRenderFlag(True)
```

### Geometry — Scene Import (OBJ-level scene to USD)

```python
import hou

stage = hou.node("/stage")

# sceneimport: import an entire OBJ-level scene into USD in one step
scene_imp = stage.createNode("sceneimport", "scene_import")
scene_imp.parm("objects").set("/obj/*")           # object path pattern
scene_imp.parm("importpathprefix").set("/World")  # USD path prefix
# display menu: "display" (viewport only), "render", "both"
scene_imp.parm("display").set("both")

# GOTCHA: OBJ-level materials are NOT imported — reassign materials in LOPs
```

### Geometry — USD Primitive Shapes

```python
import hou

stage = hou.node("/stage")

# USD built-in shapes (lightweight, not SOP geometry)
sphere  = stage.createNode("sphere",   "sphere1")
cube    = stage.createNode("cube",     "cube1")
cone    = stage.createNode("cone",     "cone1")
cyl     = stage.createNode("cylinder", "cylinder1")
capsule = stage.createNode("capsule",  "capsule1")

# Default prim path = /$OS (node name). Override:
sphere.parm("primpath").set("/World/shapes/ball")

# NOTE: there is NO 'grid' or 'plane' LOP node.
# Simulate a ground plane with a cube scaled flat:
ground = stage.createNode("cube", "ground_plane")
ground.parm("primpath").set("/World/ground")

# Then use an edit node to squash it:
edit_ground = stage.createNode("edit", "edit_ground")
edit_ground.setInput(0, ground)
edit_ground.parm("primpattern").set("/World/ground")
edit_ground.parm("sy").set(0.01)   # nearly flat
edit_ground.parm("tx").set(0.0)
edit_ground.parm("ty").set(-0.5)   # sit at y=0
edit_ground.parm("tz").set(0.0)
```

### Materials — Material Library

```python
import hou

stage = hou.node("/stage")

# materiallibrary: container for USD Material prims and shader networks
matlib = stage.createNode("materiallibrary", "matlib1")
matlib.parm("matpathprefix").set("/materials")
matlib.parm("matname1").set("chrome")

# CRITICAL GOTCHA: cook the matlib BEFORE creating child shader nodes.
# Without cook(), the internal subnet does not exist and createNode() returns None.
matlib.cook(force=True)

# Dive inside the material library to build the shader network
mat_subnet = matlib.node("chrome")   # subnet named after material
if mat_subnet is None:
    mat_subnet = matlib.createNode("subnet", "chrome")

# Create the MaterialX standard surface shader
shader = mat_subnet.createNode("mtlxstandard_surface", "surface_shader")

# Base color (RGB, 0-1)
shader.parm("base_colorr").set(0.8)
shader.parm("base_colorg").set(0.8)
shader.parm("base_colorb").set(0.8)
shader.parm("base").set(1.0)          # base weight

# Metal / specular
shader.parm("metalness").set(1.0)     # 0=dielectric, 1=metal
shader.parm("specular").set(1.0)
shader.parm("specular_roughness").set(0.05)   # 0=mirror, 1=diffuse
shader.parm("specular_IOR").set(1.5)

# Coat (clear coat layer)
shader.parm("coat").set(0.2)
shader.parm("coat_roughness").set(0.1)

# Transmission (glass)
shader.parm("transmission").set(0.0)  # 1.0 = fully transparent

# Subsurface scattering
shader.parm("subsurface").set(0.0)

# Emission
shader.parm("emission").set(0.0)
shader.parm("emission_colorr").set(1.0)
shader.parm("emission_colorg").set(1.0)
shader.parm("emission_colorb").set(1.0)

# Opacity
shader.parm("opacity").set(1.0)
```

### Materials — Assign Material

```python
import hou

stage = hou.node("/stage")

# assignmaterial: bind a material to geometry prims by USD path pattern
assign = stage.createNode("assignmaterial", "assign1")

# First assignment pair
assign.parm("nummaterials").set(1)   # number of pattern/material pairs
assign.parm("primpattern1").set("/World/geo/mesh1")          # exact USD prim path
assign.parm("matspecpath1").set("/materials/chrome")          # material USD path

# Add a second assignment pair
assign.parm("nummaterials").set(2)
assign.parm("primpattern2").set("/World/geo/ground")
assign.parm("matspecpath2").set("/materials/concrete")

# Wildcard pattern: assign to all children of a prim
assign.parm("primpattern1").set("/World/geo/*")

# GOTCHA: pattern must match actual USD prim paths, NOT Houdini node paths.
# Verify paths with: stage.node("stage_info_node").cook()
# or hou.node("/stage").stage().Traverse()
```

### Lights — Dome Light (HDRI environment)

```python
import hou

stage = hou.node("/stage")

dome = stage.createNode("domelight", "dome_light")

# LIGHTING LAW: intensity is ALWAYS 1.0. Brightness via exposure ONLY.
dome.parm("xn__inputsintensity_i0a").set(1.0)

# Enable exposure control and set value (in stops)
dome.parm("xn__inputsexposure_control_wcb").set("set")
dome.parm("xn__inputsexposure_vya").set(0.25)   # 0.25 stops for HDRI ambient fill

# HDRI texture (Greyscale Gorilla HDRIs or similar)
dome.parm("xn__inputstexturefile_i1a").set(
    "D:/GreyscaleGorillaAssetLibrary/HDRIs/studio_01.exr"
)
# Format: "automatic" (let Houdini detect), "latlong", "mirroredBall"
dome.parm("xn__inputstextureformat_i7a").set("automatic")

# Rotate the HDRI environment (azimuth)
dome.parm("ry").set(45.0)

# Without an HDRI texture the dome emits uniform white light — always set the texture.
```

### Lights — Distant Light (sun / directional)

```python
import hou

stage = hou.node("/stage")

sun = stage.createNode("distantlight", "key_sun")

# Lighting Law: intensity always 1.0
sun.parm("xn__inputsintensity_i0a").set(1.0)
sun.parm("xn__inputsexposure_control_wcb").set("set")
sun.parm("xn__inputsexposure_vya").set(1.0)   # key light: 1 stop

# Enable color temperature for natural warmth (daylight = ~5600K, tungsten = 3200K)
sun.parm("xn__inputsenablecolortemperature_r5a").set(True)
sun.parm("xn__inputscolortemperature_u5a").set(5600.0)

# Angular diameter: 0.53 = sun, larger = softer shadows (overcast)
sun.parm("xn__inputsangle_06a").set(0.53)

# Rotation controls direction. Position (tx/ty/tz) has NO effect on distant lights.
sun.parm("rx").set(-45.0)   # elevation: negative = light coming from above
sun.parm("ry").set(30.0)    # azimuth

# Key:fill ratio 3:1 = 1.585 stops difference, 4:1 = 2.0 stops
# Fill light at 0 stops, key at 1.585 → ratio 3:1
```

### Lights — Rect Light (area light)

```python
import hou

stage = hou.node("/stage")

key = stage.createNode("rectlight", "key_rect")

# Lighting Law: intensity = 1.0, brightness via exposure
key.parm("xn__inputsintensity_i0a").set(1.0)
key.parm("xn__inputsexposure_control_wcb").set("set")
key.parm("xn__inputsexposure_vya").set(1.0)   # key light brightness

# Size (larger = softer shadows)
key.parm("xn__inputswidth_e5a").set(1.5)
key.parm("xn__inputsheight_k5a").set(1.0)

# Normalize: keep brightness constant as size changes (True = normalize)
key.parm("xn__inputsnormalize_ida").set(True)

# Position and aim
key.parm("tx").set(3.0)
key.parm("ty").set(2.0)
key.parm("tz").set(2.0)
key.parm("rx").set(-20.0)
key.parm("ry").set(-60.0)

# Fill light (lower exposure for 3:1 ratio = key 1.0, fill = 1.0 - 1.585 ≈ -0.585)
fill = stage.createNode("rectlight", "fill_rect")
fill.parm("xn__inputsintensity_i0a").set(1.0)
fill.parm("xn__inputsexposure_control_wcb").set("set")
fill.parm("xn__inputsexposure_vya").set(-0.585)  # 1.585 stops below key = 3:1 ratio
fill.parm("xn__inputswidth_e5a").set(2.0)
fill.parm("xn__inputsheight_k5a").set(1.5)
fill.parm("tx").set(-3.0)
fill.parm("ty").set(1.5)
fill.parm("tz").set(1.5)
```

### Lights — Sphere Light

```python
import hou

stage = hou.node("/stage")

# spherelight: point or sphere area light (practical light source, bulb, candle)
sph = stage.createNode("spherelight", "bulb_light")

sph.parm("xn__inputsintensity_i0a").set(1.0)
sph.parm("xn__inputsexposure_control_wcb").set("set")
sph.parm("xn__inputsexposure_vya").set(0.5)

# Radius > 0 = soft shadows. Radius = 0 = hard point-light shadows.
sph.parm("xn__inputsradius_o5a").set(0.1)

# Position (spherelight position DOES matter, unlike distantlight)
sph.parm("tx").set(0.0)
sph.parm("ty").set(2.0)
sph.parm("tz").set(0.0)

# Color (warm tungsten)
sph.parm("xn__inputsenablecolortemperature_r5a").set(True)
sph.parm("xn__inputscolortemperature_u5a").set(3200.0)
```

### Lights — Disk Light and Cylinder Light

```python
import hou

stage = hou.node("/stage")

# disklight: circular area light — spotlight-like soft source
disk = stage.createNode("disklight", "disk_light")
disk.parm("xn__inputsintensity_i0a").set(1.0)
disk.parm("xn__inputsexposure_control_wcb").set("set")
disk.parm("xn__inputsexposure_vya").set(0.8)
disk.parm("xn__inputsradius_o5a").set(0.5)   # disk radius
disk.parm("tx").set(0.0)
disk.parm("ty").set(3.0)
disk.parm("tz").set(0.0)
disk.parm("rx").set(-90.0)   # aim downward

# cylinderlight: tube/neon/fluorescent strip
cyl = stage.createNode("cylinderlight", "strip_light")
cyl.parm("xn__inputsintensity_i0a").set(1.0)
cyl.parm("xn__inputsexposure_control_wcb").set("set")
cyl.parm("xn__inputsexposure_vya").set(0.5)
cyl.parm("xn__inputslength_i5a").set(2.0)    # tube length
cyl.parm("xn__inputsradius_o5a").set(0.05)   # tube radius
cyl.parm("tx").set(0.0)
cyl.parm("ty").set(2.5)
cyl.parm("tz").set(-1.0)
```

### Camera

```python
import hou

stage = hou.node("/stage")

cam = stage.createNode("camera", "render_cam")
cam.parm("primpath").set("/cameras/render_cam")

# Focal length in mm (lower = wider FOV)
# 25mm = wide angle, 50mm = standard, 85mm = portrait
cam.parm("focalLength").set(50.0)

# Sensor size (film back) in mm
cam.parm("horizontalAperture").set(36.0)   # full-frame 35mm = 36mm wide
cam.parm("verticalAperture").set(24.0)

# Depth of field (f-stop=0 disables DOF entirely)
cam.parm("fStop").set(0.0)          # 0 = no DOF; 2.8 = shallow; 8.0 = deep
cam.parm("focusDistance").set(5.0)  # focus distance in scene units

# Clip planes
cam.parm("clippingRange").set((0.1, 10000.0))   # (near, far)

# Position and orient
cam.parm("tx").set(0.0)
cam.parm("ty").set(1.5)
cam.parm("tz").set(5.0)
cam.parm("rx").set(-10.0)
cam.parm("ry").set(0.0)
cam.parm("rz").set(0.0)

# GOTCHA: Karma needs the USD PRIM path (/cameras/render_cam),
# NOT the Houdini node path (/stage/render_cam).
# Always use cam.parm("primpath").eval() when wiring render settings.
cam_prim_path = cam.parm("primpath").eval()   # "/cameras/render_cam"
```

### Render — Karma Render Properties (quality settings LOP)

```python
import hou

stage = hou.node("/stage")

# karmarenderproperties: sets Karma-specific quality on the USD stage
krp = stage.createNode("karmarenderproperties", "karma_settings")

# --- Sample counts ---
# Preview: 16-32 samples. Production: 128-256.
krp.parm("karma:global:pathtracedsamples").set(128)    # max samples
krp.parm("karma:global:minpathtracedsamples").set(16)  # min samples

# Pixel oracle: "uniform" = fixed samples, "variance" = adaptive (cleaner, slower)
krp.parm("karma:global:pixeloracle").set("variance")
krp.parm("karma:global:convergencethreshold").set(0.01)   # lower = cleaner (0.001 for hero)

# --- Ray bounce limits ---
krp.parm("karma:global:diffuselimit").set(4)    # diffuse bounces (production: 4-6)
krp.parm("karma:global:reflectlimit").set(6)    # specular/reflect bounces
krp.parm("karma:global:refractionlimit").set(6) # refraction bounces

# --- Volumes ---
krp.parm("karma:global:volumesteprate").set(0.5)   # 0.25=fast, 0.5-1.0=production

# --- Denoiser ---
krp.parm("karma:global:enabledenoise").set(1)   # 0=off, 1=OIDN (Intel Open Image Denoise)

# --- Motion blur ---
krp.parm("karma:global:shutteropen").set(-0.25)
krp.parm("karma:global:shutterclose").set(0.25)

# --- Engine: XPU (GPU) vs CPU ---
# XPU is GPU-accelerated; use CPU for complex nested dielectrics, volumes with many events
krp.parm("engine").set("xpu")   # "xpu" or "cpu"

# Preview (fast iteration) settings
def set_preview_quality(krp_node):
    krp_node.parm("karma:global:pathtracedsamples").set(16)
    krp_node.parm("karma:global:minpathtracedsamples").set(1)
    krp_node.parm("karma:global:pixeloracle").set("uniform")
    krp_node.parm("karma:global:diffuselimit").set(1)
    krp_node.parm("karma:global:reflectlimit").set(2)
    krp_node.parm("karma:global:enabledenoise").set(0)
    krp_node.parm("engine").set("xpu")

set_preview_quality(krp)
```

### Render — Render Geometry Settings (per-object subdivision, displacement)

```python
import hou

stage = hou.node("/stage")

# rendergeometrysettings: apply render-time geometry properties per-prim
rgs = stage.createNode("rendergeometrysettings", "geo_settings")

# Target prim (path or pattern)
rgs.parm("primpattern").set("/World/geo/mesh1")

# Subdivision (Catmull-Clark smoothing at render time)
rgs.parm("karma:object:subdivscheme").set("catmullClark")   # "catmullClark", "loop", "none"
rgs.parm("karma:object:dicingquality").set(1.0)   # 1.0 = standard, 2.0 = finer

# Displacement
# GOTCHA: displacementbound must be >= max displacement value or geometry clips
rgs.parm("karma:object:displacementbound").set(0.5)   # set to max expected displacement

# Motion blur samples
rgs.parm("karma:object:xform_motionsamples").set(2)   # transform motion blur
rgs.parm("karma:object:geo_motionsamples").set(2)     # deformation (point) motion blur
```

### Render — USD Render ROP (in /out)

```python
import hou

# The usdrender ROP lives in /out, NOT /stage
out_net = hou.node("/out")

rop = out_net.createNode("usdrender", "karma_rop")

# loppath: path to the LOP display/output node
rop.parm("loppath").set("/stage/OUTPUT")

# Renderer
rop.parm("renderer").set("BRAY_HdKarma")

# Camera (USD prim path, not node path)
rop.parm("override_camera").set("/cameras/render_cam")

# Resolution override
# override_res is a STRING menu: "" (use stage), "scale", "specific"
rop.parm("override_res").set("specific")
rop.parm("res_user1").set(1920)    # width
rop.parm("res_user2").set(1080)    # height

# Output image path
rop.parm("outputimage").set("$HIP/render/beauty.$F4.exr")

# GOTCHA: rop.render(output_file="...") does NOT work for usdrender ROPs.
# Set outputimage parm directly (as above), then call render with no output_file arg.
rop.render()

# GOTCHA: soho_foreground=1 blocks Houdini's WebSocket — never use for heavy scenes.
# For synchronous file write (needed in scripts), use:
rop.parm("soho_foreground").set(1)
rop.render()
rop.parm("soho_foreground").set(0)   # reset after
```

### Edit — Transform and Attribute Editing

```python
import hou

stage = hou.node("/stage")

# edit: transform, modify attributes on existing USD prims
# CORRECT way to move/rotate/scale prims in Solaris
edit = stage.createNode("edit", "xform_edit")
edit.parm("primpattern").set("/World/geo/mesh1")

# Translate
edit.parm("tx").set(2.0)
edit.parm("ty").set(0.0)
edit.parm("tz").set(-1.5)

# Rotate (degrees, XYZ order)
edit.parm("rx").set(0.0)
edit.parm("ry").set(45.0)
edit.parm("rz").set(0.0)

# Scale
edit.parm("sx").set(1.0)
edit.parm("sy").set(1.0)
edit.parm("sz").set(1.0)

# GOTCHA: Do NOT set xformOp:translate directly via set_usd_attribute.
# Use edit node — it manages xformOpOrder correctly.

# editproperties: set arbitrary USD attributes (visibility, custom metadata)
edit_props = stage.createNode("editproperties", "attr_edit")
edit_props.parm("primpattern").set("/World/geo/mesh1")

# configureprimitive: set prim kind, purpose, active state, instanceable
cfg_prim = stage.createNode("configureprimitive", "configure_asset")
cfg_prim.parm("primpattern").set("/World/asset")
cfg_prim.parm("kind").set("component")       # "component", "group", "assembly", "subcomponent"
cfg_prim.parm("purpose").set("default")      # "default", "render", "proxy", "guide"
cfg_prim.parm("active").set(True)            # False = invisible to traversal
cfg_prim.parm("instanceable").set(False)     # True = enable GPU instancing
```

### Reference and Sublayer (USD file composition)

```python
import hou

stage = hou.node("/stage")

# reference: import an external USD file as a reference under a target prim
ref = stage.createNode("reference", "asset_ref")
ref.parm("filepath1").set("D:/HOUDINI_PROJECTS_2025/assets/rubbertoy.usdc")
ref.parm("primpath").set("/World/rubbertoy")
# reftype: "Reference" (always loaded) or "Payload" (deferred / loadable on demand)
ref.parm("reftype").set("Reference")

# sublayer: merge an entire USD layer into the current stage (like a comp layer)
# Best for: lighting rigs, animation caches, department overrides
# Use sublayer for Karma — assetreference is invisible to Karma.
sub = stage.createNode("sublayer", "lighting_rig")
sub.parm("filepath1").set("D:/HOUDINI_PROJECTS_2025/lighting/three_point_rig.usda")
# Layer position: "strongest" (later / wins conflicts) or "weakest" (base layer)
sub.parm("position").set("strongest")

# For $HFS test assets (rubbertoy, pig, etc.):
import os
hfs = hou.expandString("$HFS")
pig_path = os.path.join(hfs, "houdini", "usd", "assets", "pig", "pig.usd")
sub2 = stage.createNode("sublayer", "pig_asset")
sub2.parm("filepath1").set(pig_path)
```

### Instancer (USD PointInstancer for scatter)

```python
import hou

stage = hou.node("/stage")

# instancer: scatter thousands of instances from a SOP point cloud
inst = stage.createNode("instancer", "tree_scatter")

# Point source: SOP or LOP providing instance points
inst.parm("pointsource").set("/obj/scatter_geo/OUT")

# Prototype: which USD prim to instance at each point
inst.parm("protosource").set("lop")       # "lop" = from LOP stage
inst.parm("protopath1").set("/World/tree_asset")

# SOP point attributes control per-instance transforms automatically:
#   'orient'     → rotation quaternion
#   'scale'/'pscale' → uniform scale
#   'instanceId' → which prototype to use (for multiple prototypes)
```

### Full Scene Setup (Minimal Karma Scene, End-to-End)

```python
import hou

stage = hou.node("/stage")

# 1. Geometry from SOPs
geo = stage.createNode("sopimport", "geo")
geo.parm("soppath").set("/obj/geo1/OUT")
geo.parm("primpath").set("/World/geo/mesh")

# 2. Material
matlib = stage.createNode("materiallibrary", "mats")
matlib.parm("matpathprefix").set("/materials")
matlib.parm("matname1").set("plastic")
matlib.cook(force=True)
shader = matlib.node("plastic").createNode("mtlxstandard_surface", "surface")
shader.parm("base_colorr").set(0.2)
shader.parm("base_colorg").set(0.6)
shader.parm("base_colorb").set(0.9)
shader.parm("specular_roughness").set(0.3)

# 3. Assign material
assign = stage.createNode("assignmaterial", "assign")
assign.parm("primpattern1").set("/World/geo/mesh")
assign.parm("matspecpath1").set("/materials/plastic")

# 4. HDRI dome light
dome = stage.createNode("domelight", "dome")
dome.parm("xn__inputsintensity_i0a").set(1.0)
dome.parm("xn__inputsexposure_control_wcb").set("set")
dome.parm("xn__inputsexposure_vya").set(0.25)
dome.parm("xn__inputstexturefile_i1a").set("D:/HDRIs/studio.exr")

# 5. Key light (rect)
key = stage.createNode("rectlight", "key")
key.parm("xn__inputsintensity_i0a").set(1.0)
key.parm("xn__inputsexposure_control_wcb").set("set")
key.parm("xn__inputsexposure_vya").set(1.0)
key.parm("xn__inputswidth_e5a").set(1.5)
key.parm("xn__inputsheight_k5a").set(1.0)
key.parm("tx").set(3.0); key.parm("ty").set(3.0); key.parm("tz").set(3.0)
key.parm("rx").set(-35.0); key.parm("ry").set(-45.0)

# 6. Camera
cam = stage.createNode("camera", "render_cam")
cam.parm("primpath").set("/cameras/render_cam")
cam.parm("focalLength").set(50.0)
cam.parm("tx").set(0.0); cam.parm("ty").set(1.5); cam.parm("tz").set(6.0)
cam.parm("rx").set(-10.0)
cam_path = cam.parm("primpath").eval()

# 7. Karma render settings (preview quality)
krp = stage.createNode("karmarenderproperties", "karma")
krp.parm("karma:global:pathtracedsamples").set(32)
krp.parm("karma:global:pixeloracle").set("uniform")
krp.parm("karma:global:diffuselimit").set(2)
krp.parm("engine").set("xpu")

# 8. Merge all branches
merge = stage.createNode("merge", "merge_all")
merge.setInput(0, geo)
merge.setInput(1, matlib)
merge.setInput(2, assign)
merge.setInput(3, dome)
merge.setInput(4, key)
merge.setInput(5, cam)
merge.setInput(6, krp)

# 9. Output null
out_null = stage.createNode("null", "OUTPUT")
out_null.setInput(0, merge)
out_null.setDisplayFlag(True)

# 10. USD Render ROP in /out
rop = hou.node("/out").createNode("usdrender", "karma_rop")
rop.parm("loppath").set("/stage/OUTPUT")
rop.parm("renderer").set("BRAY_HdKarma")
rop.parm("override_camera").set(cam_path)
rop.parm("override_res").set("specific")
rop.parm("res_user1").set(1280)
rop.parm("res_user2").set(720)
rop.parm("outputimage").set("$HIP/render/beauty.$F4.exr")

# Layout nodes for clarity
stage.layoutChildren()

print("Scene ready. Render at:", rop.parm("outputimage").eval())
```

### Component Output (Asset Publishing)

```python
import hou

stage = hou.node("/stage")

# Upstream: geo + matlib + assign + configureprimitive (kind=component)
cfg = stage.createNode("configureprimitive", "set_kind")
cfg.parm("primpattern").set("/World/asset")
cfg.parm("kind").set("component")   # required for USD pipeline asset recognition
cfg.parm("instanceable").set(False)

# componentoutput: package into a self-contained USD asset file
comp_out = stage.createNode("componentoutput", "publish_asset")
comp_out.parm("lopoutput").set("D:/HOUDINI_PROJECTS_2025/assets/my_asset/my_asset.usdc")
comp_out.parm("componentname").set("my_asset")
comp_out.parm("thumbnail").set(True)   # generate thumbnail image on export
# Automatically sets kind=component on root prim, embeds materials
```

## Common Mistakes

- **`materiallibrary` child `createNode()` returns None** — Call `matlib.cook(force=True)` before creating any child shader nodes. The internal subnet does not exist until the node is cooked.

- **Intensity > 1.0 on any light** — Always keep `xn__inputsintensity_i0a` at 1.0. Control brightness only via `xn__inputsexposure_vya` (in stops). Enable it with `xn__inputsexposure_control_wcb = "set"`.

- **Wrong camera path format** — Karma requires the USD prim path (`/cameras/render_cam`), not the Houdini node path (`/stage/render_cam`). Use `cam.parm("primpath").eval()` to get the correct value.

- **`rop.render(output_file=...)` does nothing for usdrender** — Set the `outputimage` parm directly, then call `rop.render()` with no arguments.

- **`override_res` type mismatch** — `override_res` is a string menu: `""`, `"scale"`, `"specific"`. Do not pass an integer.

- **No grid or plane LOP node** — Use a `cube` node with `sy=0.01` via an `edit` node to create a flat ground plane.

- **Transforms not applying** — Use an `edit` node to move/rotate/scale prims. Do not write `xformOp:translate` directly as a USD attribute — the `edit` node manages `xformOpOrder` correctly.

- **Material pattern not matching** — Prim patterns in `assignmaterial` must match the actual USD stage paths, not the SOP object names or Houdini node names. Inspect with `hou.node("/stage").stage()` or `synapse_stage_info` before assigning.

- **`soho_foreground=1` hangs Houdini** — Foreground render mode blocks the entire Houdini event loop (including the WebSocket server). Only use it in batch scripts where blocking is acceptable.

- **`sopimport` importing a static frame when animation is needed** — Set `importframe` to `$F` via `sop_imp.parm("importframe").setExpression("$F")` for per-frame geometry.

- **Karma XPU file missing immediately after `rop.render()`** — XPU has a 10-15 second delay between `render()` returning and the file being fully flushed to disk. Add a `time.sleep(15)` or poll for file existence before reading.

- **`sublayer` vs `reference` for Karma** — Use `sublayer` to bring geometry visible to Karma. The `assetreference` LOP node is for viewport work and is NOT visible to Karma renders.

- **Displacement geometry clipping** — `karma:object:displacementbound` must be set to at least the maximum displacement distance. Setting it too small causes geometry to clip at render boundaries.
