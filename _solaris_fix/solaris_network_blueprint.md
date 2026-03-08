# Solaris Network Blueprint — Canonical LOP Chain Patterns

## Triggers
solaris setup, create scene, build scene, scene setup, render setup, full scene,
create solaris, lop network, solaris network, set up render, build render scene,
create render scene, sopcreate material camera light render, lighting setup solaris,
karma scene, scene assembly solaris, lop chain, node chain solaris

## Context
Canonical node wiring patterns for Solaris (LOP) networks in Houdini 21.
CRITICAL: All Solaris work happens in `/stage` context, NEVER in `/obj`.
When an artist says "set up a scene" or "create a render" while in Solaris,
build LINEAR chains in `/stage` using `.setInput(0, previous_node)`.

## ABSOLUTE RULES

1. **Parent is ALWAYS `/stage`** — Never create LOP nodes under `/obj`.
2. **Use `sopcreate` not `sopimport`** — SOPCreate embeds geometry inside the
   LOP network. SOPImport references `/obj` geometry, which breaks self-contained
   Solaris workflows and introduces cross-context dependencies.
3. **Wire LINEARLY** — Each node feeds into the next via `.setInput(0, prev)`.
   Do NOT use merge nodes for a standard scene chain. Merge is for combining
   independent branches (e.g., multiple asset references).
4. **Set display flag on the LAST node** — `last_node.setDisplayFlag(True)`.
5. **Inspect before setting encoded parameters** — USD parm names are encoded
   (e.g., `xn__inputsintensity_i0a`). Always use `synapse_inspect_node` first.

## Canonical Linear Chain

```
SOPCreate → MaterialLibrary → AssignMaterial → Camera → Key Light → Dome Light → Render Properties → [OUTPUT null]
```

Each node's output feeds into the next node's first input. The chain is
strictly sequential — no parallel branches, no merge nodes.

## Code — Minimal Complete Scene (SOPCreate Path)

```python
import hou

stage = hou.node("/stage")

# ─── 1. GEOMETRY (SOPCreate — self-contained in /stage) ───────────
sop_create = stage.createNode("sopcreate", "geo")
sop_create.parm("primpath").set("/World/geo/mesh")

# Enter the embedded SOP network and build geometry
inner = sop_create.node("sopnet")
# Create geometry inside (example: sphere)
sphere = inner.createNode("sphere", "sphere1")
sphere.parm("rows").set(24)
sphere.parm("cols").set(24)
out = inner.createNode("null", "OUT")
out.setInput(0, sphere)
out.setDisplayFlag(True)
out.setRenderFlag(True)

prev = sop_create  # Track chain position

# ─── 2. MATERIAL LIBRARY ──────────────────────────────────────────
matlib = stage.createNode("materiallibrary", "materials")
matlib.parm("matpathprefix").set("/materials")
matlib.parm("matname1").set("surface_mat")
matlib.setInput(0, prev)

# CRITICAL: Cook before creating shader children
matlib.cook(force=True)

# Create MaterialX standard surface shader
mat_subnet = matlib.node("surface_mat")
if mat_subnet:
    shader = mat_subnet.createNode("mtlxstandard_surface", "mtlx_surface")
    shader.parm("base_colorr").set(0.8)
    shader.parm("base_colorg").set(0.2)
    shader.parm("base_colorb").set(0.2)
    shader.parm("specular_roughness").set(0.35)

prev = matlib

# ─── 3. ASSIGN MATERIAL ──────────────────────────────────────────
assign = stage.createNode("assignmaterial", "assign_mat")
assign.parm("primpattern1").set("/World/geo/*")
assign.parm("matspecpath1").set("/materials/surface_mat")
assign.setInput(0, prev)
prev = assign

# ─── 4. CAMERA ────────────────────────────────────────────────────
cam = stage.createNode("camera", "render_cam")
cam.parm("primpath").set("/cameras/render_cam")
cam.parm("focalLength").set(50.0)
cam.parm("tx").set(0.0)
cam.parm("ty").set(1.0)
cam.parm("tz").set(5.0)
cam.parm("rx").set(-10.0)
cam.setInput(0, prev)
prev = cam

# ─── 5. KEY LIGHT ─────────────────────────────────────────────────
# Lighting Law: intensity ALWAYS 1.0, control brightness via exposure
key = stage.createNode("rectlight", "key_light")
key.parm("primpath").set("/lights/key")
key.parm("xn__inputsintensity_i0a").set(1.0)
key.parm("xn__inputsexposure_control_wcb").set("set")
key.parm("xn__inputsexposure_vya").set(4.0)
key.parm("xn__inputswidth_e5a").set(2.0)
key.parm("xn__inputsheight_k5a").set(1.5)
key.parm("tx").set(3.0)
key.parm("ty").set(4.0)
key.parm("tz").set(2.0)
key.parm("rx").set(-45.0)
key.parm("ry").set(45.0)
key.setInput(0, prev)
prev = key

# ─── 6. DOME LIGHT (environment / fill) ──────────────────────────
dome = stage.createNode("domelight", "dome_light")
dome.parm("primpath").set("/lights/dome")
dome.parm("xn__inputsintensity_i0a").set(1.0)
dome.parm("xn__inputsexposure_control_wcb").set("set")
dome.parm("xn__inputsexposure_vya").set(0.0)
# For HDRI: dome.parm("xn__inputstexturefile_i1a").set("/path/to/env.exr")
dome.setInput(0, prev)
prev = dome

# ─── 7. KARMA RENDER PROPERTIES ──────────────────────────────────
krp = stage.createNode("karmarenderproperties", "karma_settings")
krp.parm("karma:global:pathtracedsamples").set(64)
krp.parm("karma:global:pixeloracle").set("uniform")
krp.parm("karma:global:diffuselimit").set(3)
krp.parm("engine").set("xpu")
krp.setInput(0, prev)
prev = krp

# ─── 8. OUTPUT NULL (display flag target) ─────────────────────────
output = stage.createNode("null", "OUTPUT")
output.setInput(0, prev)
output.setDisplayFlag(True)

# ─── Layout for clarity ──────────────────────────────────────────
stage.layoutChildren()

print("Solaris scene ready:")
print("  SOPCreate → Material → Assign → Camera → Key Light → Dome → Karma → OUTPUT")
print(f"  Camera prim: /cameras/render_cam")
```

## Code — SOPCreate with Custom Geometry

```python
import hou

stage = hou.node("/stage")

# SOPCreate with more complex internal geometry
sop_create = stage.createNode("sopcreate", "particle_geo")
sop_create.parm("primpath").set("/World/geo/particles")

inner = sop_create.node("sopnet")

# Build a scattered point cloud on a grid
grid = inner.createNode("grid", "base_grid")
grid.parm("sizex").set(10.0)
grid.parm("sizey").set(10.0)
grid.parm("rows").set(100)
grid.parm("cols").set(100)

scatter = inner.createNode("scatter", "scatter1")
scatter.parm("npts").set(5000)
scatter.setInput(0, grid)

# Add noise displacement via wrangle
wrangle = inner.createNode("attribwrangle", "displace")
wrangle.parm("snippet").set(
    'float n = noise(@P * 2.0);\n'
    '@P.y += n * 0.5;\n'
    '@Cd = set(n, 1.0 - n, 0.5);\n'
    '@pscale = fit01(rand(@ptnum), 0.01, 0.05);\n'
)
wrangle.setInput(0, scatter)

out = inner.createNode("null", "OUT")
out.setInput(0, wrangle)
out.setDisplayFlag(True)
out.setRenderFlag(True)
```

## Code — Variant: SOPImport (When OBJ Geometry Already Exists)

```python
import hou

# ONLY use sopimport when geometry ALREADY exists in /obj
# and you cannot move it into a SOPCreate.
# This creates a cross-context dependency.

stage = hou.node("/stage")

sop_imp = stage.createNode("sopimport", "import_existing_geo")
sop_imp.parm("soppath").set("/obj/geo1/OUT")  # Must exist in /obj
sop_imp.parm("primpath").set("/World/geo/imported_mesh")

# WARNING: This creates a dependency on /obj/geo1.
# Prefer sopcreate for self-contained Solaris scenes.
```

## Code — Black Background Environment Setup

```python
import hou

stage = hou.node("/stage")

# For black/studio backgrounds: dome light with zero intensity
# acts as pure black environment (no HDRI, no ambient)
dome = stage.createNode("domelight", "black_env")
dome.parm("primpath").set("/lights/environment")
dome.parm("xn__inputsintensity_i0a").set(1.0)
dome.parm("xn__inputsexposure_control_wcb").set("set")
dome.parm("xn__inputsexposure_vya").set(-10.0)  # Effectively zero light
# No texture file = solid color environment
# Result: pure black background with no ambient contribution
```

## Code — Three-Point Lighting Chain

```python
import hou

# Assumes prev_node is the last node in your chain before lighting
stage = hou.node("/stage")
# prev = <your last non-light node>

# Key light — primary illumination (camera-left, high)
key = stage.createNode("rectlight", "key_light")
key.parm("primpath").set("/lights/key")
key.parm("xn__inputsintensity_i0a").set(1.0)
key.parm("xn__inputsexposure_control_wcb").set("set")
key.parm("xn__inputsexposure_vya").set(4.0)
key.parm("xn__inputswidth_e5a").set(2.0)
key.parm("xn__inputsheight_k5a").set(1.5)
key.parm("tx").set(-3.0); key.parm("ty").set(4.0); key.parm("tz").set(3.0)
key.parm("rx").set(-45.0); key.parm("ry").set(-30.0)
# key.setInput(0, prev)
prev = key

# Fill light — softer, opposite side (camera-right, lower)
fill = stage.createNode("rectlight", "fill_light")
fill.parm("primpath").set("/lights/fill")
fill.parm("xn__inputsintensity_i0a").set(1.0)
fill.parm("xn__inputsexposure_control_wcb").set("set")
fill.parm("xn__inputsexposure_vya").set(2.0)  # 2 stops below key
fill.parm("xn__inputswidth_e5a").set(3.0)
fill.parm("xn__inputsheight_k5a").set(2.0)
fill.parm("tx").set(4.0); fill.parm("ty").set(2.0); fill.parm("tz").set(2.0)
fill.parm("rx").set(-25.0); fill.parm("ry").set(45.0)
fill.setInput(0, prev)
prev = fill

# Rim/back light — edge definition (behind subject)
rim = stage.createNode("rectlight", "rim_light")
rim.parm("primpath").set("/lights/rim")
rim.parm("xn__inputsintensity_i0a").set(1.0)
rim.parm("xn__inputsexposure_control_wcb").set("set")
rim.parm("xn__inputsexposure_vya").set(5.0)  # 1 stop above key
rim.parm("xn__inputswidth_e5a").set(1.0)
rim.parm("xn__inputsheight_k5a").set(3.0)
rim.parm("tx").set(0.0); rim.parm("ty").set(3.0); rim.parm("tz").set(-4.0)
rim.parm("rx").set(-30.0); rim.parm("ry").set(180.0)
rim.setInput(0, prev)
prev = rim
```

## Node Wiring Rules

### Linear Chain (Standard Scene)
```
A.setInput(0, B)  # A receives B's output on input 0
```
Every node connects to the previous via input 0. This is the DEFAULT pattern.

### Merge (Multi-Branch Assembly ONLY)
```
merge.setInput(0, branch_a)
merge.setInput(1, branch_b)  # Later inputs are STRONGER
```
Use merge ONLY when combining independent asset branches (e.g., multiple
USD references from different files). NEVER use merge for a standard
geo → mat → light → camera → render chain.

### AssignMaterial Wiring
AssignMaterial needs the STAGE (geometry + materials) on input 0.
It does NOT need a separate material input — the material path is set
via `matspecpath1` parameter referencing a prim path already on the stage.

## SOPCreate vs SOPImport Decision Tree

```
Need geometry in Solaris?
├── Geometry exists in /obj already? → sopimport (cross-context ref)
├── Building new geometry for this scene? → sopcreate (self-contained) ✓ PREFERRED
├── Referencing external USD file? → reference or sublayer node
└── Instancing points from SOP? → instancer (pointsource parm)
```

**Rule: When in doubt, use sopcreate.** It keeps the Solaris network
self-contained with no dependencies on /obj.

## Common Mistakes

- **Creating LOP nodes under `/obj`** — ALL Solaris nodes go in `/stage`.
  If `/stage` doesn't exist, create it: `hou.node("/").createNode("lopnet", "stage")`
- **Using merge for linear chains** — Merge changes composition strength
  ordering. For a standard scene, wire linearly: each node feeds the next.
- **SOPImport when SOPCreate would work** — SOPImport creates cross-context
  dependencies. SOPCreate is self-contained and portable.
- **Forgetting `matlib.cook(force=True)`** — MaterialLibrary's internal subnet
  doesn't exist until cooked. Always cook before `createNode()` on children.
- **Not setting display flag** — The OUTPUT null must have display flag set
  or the viewport won't show the composed stage.
- **Parallel branches without merge** — If you DO need separate branches
  (e.g., geometry branch + lighting branch), you MUST merge them. But for
  standard scenes, avoid this pattern entirely — wire linearly.
- **Setting intensity > 1.0** — Lighting Law: intensity is ALWAYS 1.0.
  Control brightness via exposure (logarithmic stops). Enable exposure
  control with `xn__inputsexposure_control_wcb` = "set" first.
- **Wrong camera path for rendering** — Karma needs the USD prim path
  (`/cameras/render_cam`), not the Houdini node path (`/stage/render_cam`).
  Use `cam.parm("primpath").eval()`.
