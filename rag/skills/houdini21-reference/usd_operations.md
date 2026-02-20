# USD Stage Operations

## Triggers
usd, stage, prim, sdf, xform, transform, visibility, purpose, composition, livrps,
reference, sublayer, payload, inherit, variantset, material binding, attribute,
get_usd_attribute, set_usd_attribute, create_usd_prim, modify_usd_prim, stage info,
usd export, usda, usdc, usdz, houdini python usd, pxr, Usd, UsdGeom, UsdShade, Sdf, Gf

## Context
Houdini 21 Solaris / LOP network. All pxr API available inside Houdini's Python session.
Access the live stage via `hou.node("/stage").stage()`. Never mutate the stage returned by
a LOP node directly in production — author via LOPs or via `execute_python` with a
carefully scoped edit context. Code below uses realistic Houdini Python patterns.

---

## Prim Hierarchy Creation

```python
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf

# --- Get the active Solaris stage from inside Houdini Python ---
import hou
stage = hou.node("/stage").stage()   # read-only view of the composed stage

# --- Inspect what already exists ---
for prim in stage.Traverse():
    print(prim.GetPath(), prim.GetTypeName())
# Typical paths Houdini LOPs produce:
#   /sphere1          <- sphere LOP named "sphere1"
#   /materials/mat1   <- materiallibrary LOP
#   /lights/dome      <- domelight LOP
#   /cameras/camera1  <- camera LOP
#   /Render/          <- karmarenderproperties LOP

# --- Recommended scene hierarchy (enforce via scene_import or manual merge) ---
# /World/
#   /geo/       <- all geometry (meshes, instances)
#   /lights/    <- all lights
#   /cameras/   <- all cameras
#   /materials/ <- all materials
# /Render/      <- render settings

# --- Create prims with pxr in a writable stage (e.g., in execute_python context) ---
# NOTE: In Houdini, prefer LOPs for authoring. Use pxr only in execute_python
#       when you need programmatic batch creation.

# Open a layer for writing (edit context pattern)
edit_layer = stage.GetEditTarget().GetLayer()

# Create an Xform prim as a transform group
xform_prim = UsdGeom.Xform.Define(stage, Sdf.Path("/World/geo"))
# Create a Sphere under it
sphere_prim = UsdGeom.Sphere.Define(stage, Sdf.Path("/World/geo/ball"))
sphere_prim.GetRadiusAttr().Set(0.5)   # radius in scene units

# Create a Scope (no transform — organizational only)
scope_prim = UsdGeom.Scope.Define(stage, Sdf.Path("/World/lights"))

# Create a Cube
cube_prim = UsdGeom.Cube.Define(stage, Sdf.Path("/World/geo/box"))
cube_prim.GetSizeAttr().Set(1.0)       # half-extents cube, 1.0 = 2 units wide

# Verify created prims
for path in ["/World/geo", "/World/geo/ball", "/World/geo/box", "/World/lights"]:
    p = stage.GetPrimAtPath(path)
    print(path, "->", p.GetTypeName(), "valid:", p.IsValid())
```

---

## Transforms (Edit LOP vs pxr)

```python
# --- PREFERRED: Use the 'edit' LOP node for transforms ---
# The edit LOP writes the full xformOp stack correctly.
# edit node parms:
#   primpattern  = "/World/geo/ball"
#   tx, ty, tz   = translation
#   rx, ry, rz   = rotation in degrees
#   sx, sy, sz   = scale
# USD xformOp order Houdini writes: translate, rotateXYZ, scale
# Applied order (USD reads right-to-left): scale -> rotate -> translate

# --- Reading current transform via pxr ---
import hou
from pxr import Usd, UsdGeom, Gf

stage = hou.node("/stage").stage()
prim  = stage.GetPrimAtPath("/World/geo/ball")

xformable = UsdGeom.Xformable(prim)

# Get local-to-parent transform matrix at current frame
time_code  = Usd.TimeCode(hou.frame())
local_xform, reset_stack = xformable.GetLocalTransformation(time_code)
print("Local matrix:", local_xform)

# Get world-space transform (composed through parent chain)
world_xform = UsdGeom.XformCache(time_code).GetLocalToWorldTransform(prim)
print("World matrix:", world_xform)

# Decompose translation from world matrix
translation = world_xform.ExtractTranslation()   # Gf.Vec3d
print("World position:", translation)

# --- Writing transform via pxr (execute_python context only) ---
xform_prim = UsdGeom.Xform.Define(stage, "/World/geo/ball")

# Clear existing ops and set fresh translate + rotateXYZ + scale
xform_prim.ClearXformOpOrder()
translate_op = xform_prim.AddTranslateOp()
rotate_op    = xform_prim.AddRotateXYZOp()
scale_op     = xform_prim.AddScaleOp()

translate_op.Set(Gf.Vec3d(1.0, 2.0, 0.0))
rotate_op.Set(Gf.Vec3f(0.0, 45.0, 0.0))   # Y rotation 45 degrees
scale_op.Set(Gf.Vec3f(1.0, 1.0, 1.0))     # uniform scale 1.0

# Animated transform — set at multiple time samples
for frame in range(1, 241):
    tc = Usd.TimeCode(float(frame))
    translate_op.Set(Gf.Vec3d(frame * 0.1, 0.0, 0.0), tc)
```

---

## USD Attributes (Reading and Writing)

```python
import hou
from pxr import Usd, Sdf, Gf, Vt

stage = hou.node("/stage").stage()
prim  = stage.GetPrimAtPath("/World/geo/ball")
tc    = Usd.TimeCode(hou.frame())

# --- Reading any attribute ---
attr = prim.GetAttribute("xformOp:translate")
if attr.IsValid():
    value = attr.Get(tc)        # returns Gf.Vec3d or None if no value at time
    print("translate:", value)
    print("type name:", attr.GetTypeName())   # e.g. "double3"
    print("variability:", attr.GetVariability())  # Uniform or Varying

# List all authored attributes on a prim
for attr in prim.GetAuthoredAttributes():
    print(attr.GetName(), "=", attr.Get(tc))

# --- Common attributes and their USD type names ---
# xformOp:translate    -> Gf.Vec3d     (local translation)
# xformOp:rotateXYZ   -> Gf.Vec3f     (rotation degrees XYZ)
# xformOp:scale       -> Gf.Vec3f     (scale)
# xformOp:transform   -> Gf.Matrix4d  (full 4x4 local matrix)
# visibility          -> "inherited" | "invisible"
# purpose             -> "default" | "render" | "proxy" | "guide"
# extent              -> Vt.Vec3fArray([min, max])

# --- Writing an attribute (execute_python or editable stage) ---
attr = prim.GetAttribute("xformOp:translate")
if not attr:
    attr = prim.CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3)
attr.Set(Gf.Vec3d(0.0, 1.0, 0.0))        # default time (no animation)
attr.Set(Gf.Vec3d(0.0, 5.0, 0.0), 48.0)  # at frame 48

# --- Geometry attributes (mesh) ---
mesh_prim = stage.GetPrimAtPath("/World/geo/rubbertoy/geo/shape")
mesh      = UsdGeom.Mesh(mesh_prim)

points = mesh.GetPointsAttr().Get(tc)      # Vt.Vec3fArray
counts = mesh.GetFaceVertexCountsAttr().Get(tc)  # Vt.IntArray
indices = mesh.GetFaceVertexIndicesAttr().Get(tc) # Vt.IntArray
normals = mesh.GetNormalsAttr().Get(tc)    # Vt.Vec3fArray or None

print(f"Mesh: {len(points)} points, {len(counts)} faces")

# --- Custom primvar (arbitrary per-point data) ---
primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
# Read existing primvar
for pv in primvars_api.GetPrimvars():
    print(pv.GetName(), pv.GetInterpolation(), pv.Get(tc))

# Author a new primvar (e.g. per-point float for use in shader)
new_pv = primvars_api.CreatePrimvar(
    "myDensity",
    Sdf.ValueTypeNames.FloatArray,
    UsdGeom.Tokens.vertex          # per-point interpolation
)
new_pv.Set(Vt.FloatArray([0.5, 1.0, 0.2]))  # one value per point
```

---

## Light Encoded Parameter Names

```python
# Houdini encodes USD light attribute names with Punycode because "inputs:" and "texture:"
# contain colons. Use these EXACT encoded names with get_parm / set_parm on LOP nodes.

import hou

dome = hou.node("/stage/domelight1")   # example domelight LOP node

# --- Read light parms via LOP node ---
intensity = dome.evalParm("xn__inputsintensity_i0a")   # always keep at 1.0
exposure  = dome.evalParm("xn__inputsexposure_vya")    # log2 stops, controls brightness
color_r   = dome.evalParm("xn__inputscolorr_o5a")      # red channel
color_g   = dome.evalParm("xn__inputscolorg_o5a")      # green channel
color_b   = dome.evalParm("xn__inputscolorb_o5a")      # blue channel
hdri_file = dome.evalParm("xn__inputstexturefile_i1a") # dome HDRI texture path

print(f"intensity={intensity}, exposure={exposure}, hdri={hdri_file}")

# --- Set light parms via LOP node (coaching tone: always intensity=1.0) ---
dome.parm("xn__inputsintensity_i0a").set(1.0)    # LIGHTING LAW: never > 1.0
dome.parm("xn__inputsexposure_vya").set(0.25)    # mild fill; studio HDRI provides range
dome.parm("xn__inputstexturefile_i1a").set(
    "D:/GreyscaleGorillaAssetLibrary/hdri/studio_01.hdr"
)

# --- Key light exposure math ---
import math
key_exposure  = 1.0          # key light stops
fill_ratio    = 4.0          # key:fill ratio 4:1
fill_exposure = key_exposure - math.log2(fill_ratio)   # = 1.0 - 2.0 = -1.0 stops
rim_exposure  = key_exposure - math.log2(8.0)           # 8:1 = -2.0 stops
print(f"key={key_exposure:.2f}  fill={fill_exposure:.2f}  rim={rim_exposure:.2f}")

# --- Read via pxr USD attribute (alternative) ---
from pxr import Usd, UsdLux
stage     = hou.node("/stage").stage()
light_prim = stage.GetPrimAtPath("/lights/dome")
if light_prim.IsValid():
    dome_light = UsdLux.DomeLight(light_prim)
    print("intensity attr:", dome_light.GetIntensityAttr().Get())
    print("exposure attr: ", dome_light.GetExposureAttr().Get())
    # Texture file
    print("texture file:  ", dome_light.GetTextureFileAttr().Get())
```

---

## Visibility and Purpose

```python
import hou
from pxr import Usd, UsdGeom

stage = hou.node("/stage").stage()
tc    = Usd.TimeCode(hou.frame())

# --- Visibility: "inherited" (visible) or "invisible" (hidden everywhere) ---
prim = stage.GetPrimAtPath("/World/geo/ball")
imageable = UsdGeom.Imageable(prim)

# Read current computed visibility (resolves through parent chain)
computed_vis = imageable.ComputeVisibility(tc)   # "inherited" or "invisible"
print("computed visibility:", computed_vis)

# Read authored visibility token
vis_attr = imageable.GetVisibilityAttr()
authored = vis_attr.Get(tc)  # UsdGeom.Tokens.inherited or .invisible
print("authored:", authored)

# Set invisible
vis_attr.Set(UsdGeom.Tokens.invisible)
# Restore to inherited (visible if parents are visible)
vis_attr.Set(UsdGeom.Tokens.inherited)

# --- Purpose: controls visibility per-context ---
# "default"  -> visible in viewport AND render    (normal geo)
# "render"   -> render only, NOT in viewport      (displacement geo, high-res hair)
# "proxy"    -> viewport only, NOT in render      (low-res stand-in)
# "guide"    -> optional in viewport, never render (construction helpers)

purpose_attr = imageable.GetPurposeAttr()
purpose_attr.Set(UsdGeom.Tokens.proxy)   # low-res in viewport
purpose_attr.Set(UsdGeom.Tokens.render)  # detail only in Karma
purpose_attr.Set(UsdGeom.Tokens.default) # normal (both contexts)

# Compute effective purpose (inherits from parents when not authored)
effective_purpose = imageable.ComputePurpose()
print("effective purpose:", effective_purpose)

# --- Activate / deactivate (stronger than visibility) ---
# Deactivated prims are completely excluded from the stage traversal
prim.SetActive(False)   # deactivate (prunes from traversal)
prim.SetActive(True)    # reactivate

# --- Batch: hide all proxy prims for final render ---
for p in stage.Traverse():
    if UsdGeom.Imageable(p).ComputePurpose() == UsdGeom.Tokens.proxy:
        UsdGeom.Imageable(p).GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
```

---

## Composition Arcs (LIVRPS)

```python
# LIVRPS strength order (strongest -> weakest):
# Local > Inherits > VariantSets > References > Payloads > Sublayers
# Stronger arcs override weaker arcs on the same prim+attribute.
# "Local" opinions (edit LOP, set_usd_attribute) always win — this is how
# lighting overrides work on referenced assets.

import hou
from pxr import Usd, Sdf, UsdGeom

stage = hou.node("/stage").stage()

# --- Sublayers: merge full department layers (weakest arc) ---
# Later sublayers (higher index) are STRONGER. Last wins on conflict.
# In Houdini, use the 'sublayer' LOP node. Via pxr:
root_layer = stage.GetRootLayer()
root_layer.subLayerPaths = [
    "layout.usd",    # weakest  — base positions
    "anim.usd",      # medium   — animated transforms override layout
    "lighting.usd",  # stronger — lighting overrides
    "fx.usd",        # strongest sublayer — FX on top
]
# Practical stack: anim.usd sublayer layout.usd sublayer ... -> final.usd

# --- References: import asset under a prim path ---
prim_path = Sdf.Path("/World/geo/rubbertoy")
ref_prim  = stage.DefinePrim(prim_path)
ref_prim.GetReferences().AddReference(
    assetPath="$HFS/houdini/usd/assets/rubbertoy/rubbertoy.usd",
    primPath=Sdf.Path("/rubbertoy")   # prim inside the referenced file
)
# Now /World/geo/rubbertoy inherits the rubbertoy asset's contents.
# Local edits (edit LOP) on /World/geo/rubbertoy override the reference.

# --- Payloads: lazy-loaded heavy assets ---
heavy_prim = stage.DefinePrim(Sdf.Path("/World/geo/hero"))
heavy_prim.GetPayloads().AddPayload(
    assetPath="D:/HOUDINI_PROJECTS_2025/assets/hero_char.usd",
    primPath=Sdf.Path("/hero")
)
# Load/unload payload at runtime for memory management
stage.LoadAndUnload(
    loadSet=Usd.StageLoadRules.AllRule,    # load all payloads
    unloadSet=Sdf.PathSet()
)
# Or selectively:
stage.Load(Sdf.Path("/World/geo/hero"))    # load just this prim's payload
stage.Unload(Sdf.Path("/World/geo/hero"))  # unload (prim remains, data not in memory)

# --- Inherits: shared class prims for defaults ---
# Create a class prim (abstract, not rendered)
class_prim = stage.CreateClassPrim("/_class_prop")
UsdGeom.Xform(class_prim)  # give it a type
class_prim.GetAttribute("visibility").Set(UsdGeom.Tokens.inherited)
# Make a prop inherit from the class
prop_prim = stage.GetPrimAtPath("/World/geo/chair")
prop_prim.GetInherits().AddInherit(Sdf.Path("/_class_prop"))
# Now editing /_class_prop affects all props that inherit from it.

# --- VariantSets: switchable LOD / material variants ---
asset_prim = stage.GetPrimAtPath("/World/geo/rubbertoy")
vset = asset_prim.GetVariantSets().AddVariantSet("lod")
for variant_name in ["high", "mid", "low"]:
    vset.AddVariant(variant_name)

# Author geometry under each variant
vset.SetVariantSelection("high")
with vset.GetVariantEditContext():
    hi_sphere = UsdGeom.Sphere.Define(stage, "/World/geo/rubbertoy/geo")
    hi_sphere.GetRadiusAttr().Set(1.0)

vset.SetVariantSelection("low")
with vset.GetVariantEditContext():
    lo_sphere = UsdGeom.Sphere.Define(stage, "/World/geo/rubbertoy/geo")
    lo_sphere.GetRadiusAttr().Set(0.95)  # slightly simplified

# Switch active variant
vset.SetVariantSelection("mid")

# Query all variants available
print("variants:", vset.GetVariantNames())       # ["high", "mid", "low"]
print("selected:", vset.GetVariantSelection())   # "mid"

# --- Check composition arcs on a prim ---
prim = stage.GetPrimAtPath("/World/geo/rubbertoy")
query = Usd.PrimCompositionQuery(prim)
for arc in query.GetCompositionArcs():
    print(arc.GetArcType(), "->", arc.GetIntroducingLayer())
```

---

## Material Binding

```python
import hou
from pxr import Usd, UsdShade, Sdf

stage = hou.node("/stage").stage()
tc    = Usd.TimeCode(hou.frame())

# --- Read material binding on a prim ---
prim = stage.GetPrimAtPath("/World/geo/rubbertoy/geo/shape")
binding_api = UsdShade.MaterialBindingAPI(prim)
mat, rel     = binding_api.ComputeBoundMaterial()    # resolves inherited bindings
if mat:
    print("Bound material path:", mat.GetPath())
else:
    print("No material bound")

# --- Direct binding: assign material to a single prim ---
geo_prim  = stage.GetPrimAtPath("/World/geo/ball")
mat_prim  = stage.GetPrimAtPath("/materials/chrome")
material  = UsdShade.Material(mat_prim)

UsdShade.MaterialBindingAPI(geo_prim).Bind(
    material,
    bindingStrength=UsdShade.Tokens.strongerThanDescendants  # override children
)

# --- Unbind (remove material assignment) ---
UsdShade.MaterialBindingAPI(geo_prim).UnbindAllBindings()

# --- Collection-based binding: one rule, many prims ---
from pxr import Usd
col_api = Usd.CollectionAPI.Apply(stage.GetPrimAtPath("/World"), "metalParts")
col_api.GetIncludesRel().AddTarget(Sdf.Path("/World/geo/bolt1"))
col_api.GetIncludesRel().AddTarget(Sdf.Path("/World/geo/bolt2"))
col_api.GetIncludesRel().AddTarget(Sdf.Path("/World/geo/frame"))

mat_binding = UsdShade.MaterialBindingAPI(stage.GetPrimAtPath("/World"))
mat_binding.Bind(
    UsdShade.Collection(col_api),
    UsdShade.Material(stage.GetPrimAtPath("/materials/steel")),
    "metalParts",
    UsdShade.Tokens.strongerThanDescendants
)

# --- Inspect material network (find surface shader) ---
mat_prim  = stage.GetPrimAtPath("/materials/chrome")
material  = UsdShade.Material(mat_prim)
surface_out = material.GetSurfaceOutput()
shader_prim, out_name, src_type = surface_out.GetConnectedSource()
if shader_prim:
    shader = UsdShade.Shader(shader_prim)
    print("Surface shader:", shader.GetPath())
    print("Shader id:", shader.GetShaderId())   # e.g. "UsdPreviewSurface"
    # Read shader inputs
    for inp in shader.GetInputs():
        print(" ", inp.GetBaseName(), "=", inp.Get(tc))
```

---

## Stage Info Query

```python
import hou
from pxr import Usd, UsdGeom, UsdLux

stage = hou.node("/stage").stage()
tc    = Usd.TimeCode(hou.frame())

# --- Basic stage metadata ---
print("Start frame:  ", stage.GetStartTimeCode())   # float
print("End frame:    ", stage.GetEndTimeCode())
print("FPS:          ", stage.GetFramesPerSecond())
print("Up axis:      ", UsdGeom.GetStageUpAxis(stage))       # "Y" or "Z"
print("Meters/unit:  ", UsdGeom.GetStageMetersPerUnit(stage))# 0.01 = cm

# --- Root layer info ---
root = stage.GetRootLayer()
print("Root layer:   ", root.realPath)
print("Sublayers:    ", root.subLayerPaths)

# --- Count prims by type ---
from collections import Counter
type_counts = Counter(p.GetTypeName() for p in stage.Traverse())
for type_name, count in sorted(type_counts.items()):
    print(f"  {type_name:30s} {count}")

# --- Find all lights ---
light_paths = []
for prim in stage.Traverse():
    if prim.IsA(UsdLux.BoundableLightBase) or prim.IsA(UsdLux.NonboundableLightBase):
        light = UsdLux.LightAPI(prim)
        print(
            prim.GetPath(),
            "exposure:", light.GetExposureAttr().Get(tc),
            "intensity:", light.GetIntensityAttr().Get(tc)
        )
        light_paths.append(prim.GetPath())

# --- Find all cameras ---
for prim in stage.Traverse():
    if prim.GetTypeName() == "Camera":
        cam = UsdGeom.Camera(prim)
        print(prim.GetPath(), "focal:", cam.GetFocalLengthAttr().Get(tc), "mm")

# --- Bounding box of entire scene ---
bbox_cache = UsdGeom.BBoxCache(tc, [UsdGeom.Tokens.default_])
world_prim = stage.GetPrimAtPath("/World")
if world_prim.IsValid():
    bbox = bbox_cache.ComputeWorldBound(world_prim)
    print("Scene bbox:", bbox.GetBox())   # Gf.Range3d
```

---

## USD File Export

```python
import hou, os
from pxr import Usd, UsdGeom

# --- Export full composed stage to USDA (ASCII, human-readable) ---
stage = hou.node("/stage").stage()
output_dir = os.path.join(hou.getenv("HIP"), "export")
os.makedirs(output_dir, exist_ok=True)

# Flatten all composition arcs into a single layer (baked stage)
stage.Export(
    os.path.join(output_dir, "scene_baked.usda"),
    addSourceFileComment=False
)

# --- Export root layer only (preserves composition arcs / references) ---
stage.GetRootLayer().Export(
    os.path.join(output_dir, "scene_root.usda")
)

# --- Export as binary Crate (.usdc) for production speed ---
stage.GetRootLayer().Export(
    os.path.join(output_dir, "scene.usdc")
)

# --- File format reference ---
# .usd   auto-detect (binary or ASCII depending on content)      general purpose
# .usda  ASCII, human-readable, slow to parse                    debug / version control
# .usdc  binary Crate format, fast, compact                      production
# .usdz  zipped package (usdc + textures inline)                 AR / distribution / web

# --- Export via ROP (preferred for production — handles AOVs, multi-frame) ---
rop_node = hou.node("/out/usdoutput1")
if rop_node is None:
    rop_node = hou.node("/out").createNode("rop_usdoutput", "usdoutput1")
rop_node.parm("loppath").set("/stage")                        # source LOP network
rop_node.parm("outputfile").set("$HIP/export/scene.$F4.usd")  # per-frame files
rop_node.parm("fileperframe").set(1)                          # one file per frame
rop_node.parm("trange").set(1)                                # frame range cook
rop_node.parm("f1").set(hou.playbar.playbackRange()[0])
rop_node.parm("f2").set(hou.playbar.playbackRange()[1])
rop_node.render()   # cook and write to disk

# --- Validate exported file ---
import subprocess
hfs = hou.getenv("HFS")
usdcat = os.path.join(hfs, "bin", "usdcat.exe")
result = subprocess.run(
    [usdcat, "--validate", os.path.join(output_dir, "scene_baked.usda")],
    capture_output=True, text=True, encoding="utf-8"
)
print(result.stdout or "Validation passed")
print(result.stderr or "")
```

---

## Common Mistakes

**Do not set xformOp:translate directly via USD attribute** when a Houdini `edit` LOP is available — the edit LOP manages the full xformOp stack (translate + rotateXYZ + scale in the correct order). Writing only `xformOp:translate` without the matching `xformOps:` order attribute produces a no-op transform.

**matlib.cook(force=True) before createNode on shader children** — the materiallibrary LOP must be cooked before `createNode()` on its internal subnet succeeds. Without the cook, the internal subnet does not exist and `createNode` returns None silently.

**Sublayer strength is reversed from intuition** — the last entry in `subLayerPaths` is the STRONGEST. Department overrides go last, not first.

**References vs Sublayers** — Reference imports an asset under a specific prim path (the asset's prims become children of the reference prim). Sublayer merges an entire layer into the current stage at the root level. Use references for assets; use sublayers for department overlays (anim.usd over layout.usd).

**Payload load state** — Payloads default to loaded when opened in Houdini. In batch/headless mode, call `stage.Load()` explicitly or pass `load=Usd.Stage.LoadAll` to `Open()`.

**purpose vs visibility** — `purpose="render"` means the prim appears in Karma but NOT in the viewport. `visibility="invisible"` means hidden from both. Use purpose for LOD switching; use visibility for toggling objects.

**UsdShade.MaterialBindingAPI.ComputeBoundMaterial** returns the material resolved through the full inheritance chain. Checking only the authored binding relationship will miss materials bound on parent prims.

**USD prim paths are case-sensitive** — `/materials/Chrome` and `/materials/chrome` are different prims. Houdini LOP node names become prim names verbatim. Name nodes consistently to avoid duplicate material prims.
