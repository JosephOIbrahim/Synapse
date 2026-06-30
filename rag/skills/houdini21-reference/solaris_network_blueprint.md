# Solaris Network Blueprint — Canonical LOP Chain

## Triggers
solaris chain, lop chain, network blueprint, node order, wire order, solaris pipeline,
canonical chain, solaris wiring, build lop network, lop network order, solaris network pattern,
sopcreate chain, stage chain, lop wiring, create solaris scene, solaris from scratch,
new solaris scene, setup solaris, setup lop

## Context
Canonical node-wiring order for a Solaris (LOP) network in Houdini 21. This is the
standard chain that every Solaris scene should follow. All LOP nodes live in /stage,
never /obj. Use sopcreate (not sopimport) for new geometry. Wire linearly with
setInput(0, prev). Lighting Law: intensity is ALWAYS 1.0; brightness via exposure only.

## Production Reference Patterns (verified live on H21.0.671)

> The linear chain in the next section is the MINIMAL / quick-scene case. Real shots are
> assembled from the patterns below. Every node type here is confirmed to exist in 21.0.671;
> the strength rule is confirmed by a live merge/sublayer probe.

### 1. Component Builder — the publishable-asset pattern (preferred for assets)

```
componentgeometry ─┐(input 0)
                   ├─→ componentmaterial ─→ componentoutput
materiallibrary ───┘(input 1)
```

- `componentgeometry` holds the geo (default / proxy / sim variants); `materiallibrary` holds the shaders.
- `componentmaterial` binds them: **geometry on input 0, material library on input 1**.
- `componentoutput` writes the asset (default prim, variants, thumbnail). Use this for any geometry you would publish or reference — NOT `sopcreate`.

### 2. Karma render terminal (production)

```
<scene> ─→ rendersettings ─→ renderproduct ─→ usdrender_rop
              (or the modern `karmarendersettings` wrapper, which authors all three)
              + rendergeometrysettings for per-prim render overrides
```

- The production render terminal is `rendersettings` / `renderproduct` / `usdrender_rop` (or `karmarendersettings`). Do **not** terminate on `karmarenderproperties`.
- `usdrender` is NOT a valid node type in 21.0.671 — use `usdrender_rop`.

### 3. Shot assembly — layered, NOT a single linear chain

```
reference / sopimport (per asset) ─→ merge | graftstages ─→ editproperties (overrides)
   ─→ lighting ─→ camera ─→ render terminal
```

- Combine assets with `merge` or `graftstages`, not a flat `setInput(0, prev)` chain.
- Manage the layer stack with `configurelayer` / `layerbreak`; override prims with `editproperties` / `editmaterialproperties` / `xform` / `prune`.
- Organize large scenes into nested `lopnet` subnets per topic (lights, geometry, render).

### 4. Lighting

```
domelight (HDRI) + light (generic; set light type via parm) ─→ lightmixer ─→ into scene
```

- `rectlight`, `spherelight`, `disklight` are **NOT valid node types** in 21.0.671. Create a generic `light` LOP and set its light-type parm, or use `domelight` / `distantlight`. `lightmixer` groups and balances lights.

### 5. Geometry into the stage — decision

| Situation | Node |
|---|---|
| New procedural geo for this scene | `sopcreate` |
| Geometry already in `/obj` | `sopimport` |
| Published USD asset | `reference` |
| Publishable asset (geo + materials + variants) | Component Builder (pattern 1) |

### Composition strength (verified by live probe, 21.0.671)

- **`merge` and `sublayer` LOPs: the HIGHER input index / later input is STRONGER** — it wins on conflicting opinions. This is the OPPOSITE of raw USD `subLayerPaths` (where index 0 is strongest). The `sublayer` LOP's `positiontype` / `positionindex` parms set insertion strength.
- **Downstream overrides upstream**: a later node in the chain wins over an earlier one on the same attribute; the last display-flagged LOP is the stage you see and render.

---

## Chain Order

```
SOPCreate → MaterialLibrary → AssignMaterial → Camera → Lights → RenderProperties → OUTPUT null
```

Every node in /stage. Every connection: `node.setInput(0, previous_node)`.

## Code

### Minimal Complete Solaris Scene

```python
import hou

stage = hou.node("/stage")

# 1. Geometry via SOPCreate (NOT sopimport for new geo)
# sopcreate embeds a SOP network inside the LOP node
geo = stage.createNode("sopcreate", "geo_create")
# Double-click sopcreate to edit its internal SOP network
# Internal SOP output becomes a USD Mesh prim

# 2. Material Library — contains shader subnets
matlib = stage.createNode("materiallibrary", "materials")
matlib.setInput(0, geo)
# Add MaterialX shaders inside the matlib node
# Assign geo paths directly via matlib's geopath parms

# 3. Assign Material (if not using matlib geopath assignment)
assign = stage.createNode("assignmaterial", "assign_mtl")
assign.setInput(0, matlib)
# assign.parm("primpattern1").set("/geo_create/mesh_0")
# assign.parm("matspecpath1").set("/materials/shader1")

# 4. Camera
cam = stage.createNode("camera", "shot_cam")
cam.setInput(0, assign)
cam.parm("focalLength").set(50.0)     # mm: 25=wide, 50=standard, 85=portrait
cam.parm("horizontalAperture").set(36.0)  # 36mm = full-frame sensor

# 5. Lights — dome + key as minimum
dome = stage.createNode("domelight", "env_dome")
dome.setInput(0, cam)
dome.parm("xn__inputsintensity_i0a").set(1.0)       # Lighting Law: always 1.0
dome.parm("xn__inputsexposure_vya").set(0.25)        # HDRI provides range
# dome.parm("xn__inputstexturefile_r3ah").set("path/to/hdri.exr")

key = stage.createNode("distantlight", "key_light")
key.setInput(0, dome)
key.parm("xn__inputsintensity_i0a").set(1.0)         # Lighting Law
key.parm("xn__inputsexposure_vya").set(1.0)
key.parm("xn__inputsenableColorTemperature_omb").set(True)
key.parm("xn__inputscolorTemperature_wcb").set(5500)  # Daylight

# 6. Render Properties
render_props = stage.createNode("karmarenderproperties", "render_settings")
render_props.setInput(0, key)
# render_props.parm("camera").set("/shot_cam")       # explicit camera path
# render_props.parm("resolutionx").set(1920)
# render_props.parm("resolutiony").set(1080)

# 7. OUTPUT null — display flag goes here
output = stage.createNode("null", "OUTPUT")
output.setInput(0, render_props)
output.setDisplayFlag(True)

# Layout the network for readability
stage.layoutChildren()

print("Solaris chain built: geo → materials → camera → lights → render → OUTPUT")
```

### Production Chain with Merge

```python
import hou

stage = hou.node("/stage")

# --- Geometry branch ---
geo1 = stage.createNode("sopcreate", "hero_geo")
geo2 = stage.createNode("sopcreate", "env_geo")

# --- Material branch ---
matlib = stage.createNode("materiallibrary", "materials")

# --- Merge: geometry first, then materials
merge = stage.createNode("merge", "assembly")
merge.setInput(0, geo1)      # geometry first
merge.setInput(1, geo2)
merge.setInput(2, matlib)    # then materials

# --- Assign after merge ---
assign = stage.createNode("assignmaterial", "assign_mtl")
assign.setInput(0, merge)

# --- Camera ---
cam = stage.createNode("camera", "shot_cam")
cam.setInput(0, assign)
cam.parm("focalLength").set(50.0)

# --- Lighting ---
dome = stage.createNode("domelight", "env_dome")
dome.setInput(0, cam)
dome.parm("xn__inputsintensity_i0a").set(1.0)
dome.parm("xn__inputsexposure_vya").set(0.25)

key = stage.createNode("distantlight", "key_light")
key.setInput(0, dome)
key.parm("xn__inputsintensity_i0a").set(1.0)
key.parm("xn__inputsexposure_vya").set(1.0)

# --- Render settings ---
render_props = stage.createNode("karmarenderproperties", "render_settings")
render_props.setInput(0, key)

# --- Output ---
output = stage.createNode("null", "OUTPUT")
output.setInput(0, render_props)
output.setDisplayFlag(True)

stage.layoutChildren()
```

### ROP Wiring (for actual rendering)

```python
import hou

# After building the Solaris chain in /stage:
# Karma LOP feeds usdrender ROP in /out

# Karma LOP (inside /stage, before OUTPUT null)
stage = hou.node("/stage")
karma = stage.createNode("karma", "karma_render")
karma.parm("camera").set("/shot_cam")
karma.parm("picture").set("$HIP/render/$HIPNAME.$OS.$F4.exr")
# Wire karma before output
# karma.setInput(0, render_props)
# output.setInput(0, karma)

# ROP (in /out)
out_net = hou.node("/out")
rop = out_net.createNode("usdrender", "render_rop")
rop.parm("loppath").set("/stage/karma_render")
rop.parm("outputimage").set("$HIP/render/$HIPNAME.$OS.$F4.exr")
rop.parm("soho_foreground").set(1)  # Wait for render to finish before returning
```

## Rules

1. **All LOP nodes in /stage** — never create LOP node types in /obj
2. **sopcreate for new geometry** — sopimport is for referencing existing SOP networks
3. **Wire linearly**: `node.setInput(0, previous_node)` — one chain, no floating nodes
4. **Merge order**: geometry first, then lights, then referenced assets
5. **Material library with subnets** preferred over separate matlib + assign nodes
6. **Assign geo paths directly in matlib** when possible — fewer nodes, cleaner chain
7. **Lighting Law**: intensity ALWAYS 1.0, brightness via exposure only
8. **HDRI on dome light** for environment lighting — dome exposure ~0.25 for studio HDRI
9. **Camera focalLength in mm**: 25=wide, 50=standard, 85=portrait
10. **OUTPUT null with display flag** at chain end — convention for render/display output
11. **soho_foreground=1** on usdrender ROP for synchronous file write
12. **Set picture on Karma LOP AND outputimage on ROP** for reliable output paths

## Auto-Assembly Tool

Use `synapse_solaris_assemble_chain` to automatically wire unwired LOP nodes into
the canonical chain order. This is a safety net — if nodes were created but not
wired (e.g. after multiple `houdini_create_node` calls), this tool detects them
and connects them in the correct Solaris order.

### Modes

| Mode | Use Case | Required Params |
|------|----------|-----------------|
| `all` | Scan /stage for all unwired nodes, sort by canonical order, wire linearly | none (auto-discovers) |
| `nodes` | Wire specific node paths in canonical or given order | `nodes` list |
| `after` | Append nodes after a specific chain tail | `after` + `nodes` |

### Canonical Sort Order

```
sopcreate/sopimport  100   (geometry)
materiallibrary      200   (materials)
assignmaterial       220   (assignment)
camera               400   (camera)
rectlight            500   (area light)
distantlight         500   (distant light)
domelight            600   (environment)
karmarenderproperties 700  (render settings)
null                 900   (OUTPUT)
```

### Examples

```python
# Auto-wire everything unwired in /stage
synapse_solaris_assemble_chain()

# Preview what would be wired (no mutations)
synapse_solaris_assemble_chain(dry_run=True)

# Wire specific nodes
synapse_solaris_assemble_chain(mode="nodes", nodes=["/stage/cam1", "/stage/dome1"])

# Append after an existing chain tail
synapse_solaris_assemble_chain(mode="after", after="/stage/materials", nodes=["/stage/cam1"])
```

### When to Use

- After creating multiple LOP nodes that aren't wired yet
- When floating nodes are detected in /stage
- As a cleanup pass before rendering
- To restore a broken chain after manual edits
