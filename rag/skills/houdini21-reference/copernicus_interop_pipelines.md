# Copernicus Interop Pipelines — Houdini 21

Cross-context workflows: SOP<->COP, COP->MaterialX, Karma AOV compositing, slap comp, PDG batch.

## SOP -> COP: Geometry Rasterization

### SOP Import COP

```
SOP Import COP:
  Input: SOP geometry path (e.g., /obj/geo1/OUT)
  Output: Layers from geometry attributes

Attribute -> Layer Mapping:
  P       -> Position map (RGB, world space)
  N       -> Normal map (RGB)
  Cd      -> Color (RGB/RGBA)
  uv      -> UV coordinates (UV type)
  density -> Density (Mono)
  Custom  -> Custom layers (any type)

Resolution: Set on the COP Import node
Projection: Camera-based or UV-based
```

### Prepare + Rasterize (Clean Bake Pipeline)

```
Two-step pattern for production mesh baking:

  1. Prepare Geometry COP -> processes mesh for rasterization
  2. Rasterize Geometry COP -> renders geometry attributes to layers

This produces cleaner results than direct SOP Import for baking.
```

### Volume / VDB Import

```
Geometry to Layer COP (v2.0 in H21):
  - Converts 2D and 3D volumes into Copernicus layers
  - VDB fields become layers (density, temperature, vel, custom)
  - Use case: bring pyro sim data into COPs for post-processing

Python example:
```

```python
import hou

copnet = hou.node("/obj/copnet1")
geo_to_layer = copnet.createNode("geometrytolayer")
geo_to_layer.parm("soppath").set("/obj/pyro_sim/OUT")
# Fields auto-detected from VDB names
```

### Invoke SOP Block (SOP Algorithms on Image Data)

```
Invoke Geometry COP / Invoke SOP COP:
  Bridge: apply SOP algorithms to image data

Workflow:
  1. COP generates image data (e.g., brightness map)
  2. Invoke SOP scatters points based on brightness
  3. SOP runs point relaxation / voronoi / etc.
  4. Rasterize result back to COP layer

Enables: SOP procedural algorithms on pixel data
without leaving the COP context.
```

## COP -> MaterialX: op: Path System

### Live Texture Connection

```
MaterialX texture inputs accept op: paths:

  file: op:/stage/copnet1/OUT_albedo

This creates a LIVE connection:
  - COP network cooks -> texture updates in real-time
  - No disk I/O, no texture file management
  - Animated textures work automatically per-frame
  - Changes propagate through Karma render

Setup in Solaris:
  1. Create COP Network node inside /stage (LOP context)
  2. Build texture generation network inside it
  3. In MaterialX shader, set texture file path to:
     op:/stage/copnet1/output_node_name
```

### Full Procedural Texture Pipeline

```python
import hou

stage = hou.node("/stage")

# Create COP network inside LOP context
copnet = stage.createNode("copnet")
copnet.setName("procedural_textures")

# Build texture network
noise = copnet.createNode("fractal_noise")
noise.parm("freq").set(8)

# Albedo branch
albedo_cc = copnet.createNode("color_correct")
albedo_cc.setInput(0, noise)
albedo_cc.setName("OUT_albedo")
albedo_cc.setDisplayFlag(True)

# Roughness branch (threshold noise)
thresh = copnet.createNode("threshold")
thresh.setInput(0, noise)
thresh.setName("OUT_roughness")

# In MaterialX Standard Surface:
#   base_color:         op:/stage/procedural_textures/OUT_albedo
#   specular_roughness: op:/stage/procedural_textures/OUT_roughness
```

### Animated Texture Patterns

```
Time-dependent COPs (solver with Simulate ON, noise with $T):
  Each frame generates new texture automatically
  Material updates per-frame via op: path — no disk writes

Production use cases:
  - Flowing lava:      R-D solver -> displacement map
  - Corroding metal:   growth propagation -> roughness map
  - Water caustics:    flow solver -> emission map
  - Organic patterns:  reaction-diffusion -> color map
  - Living surfaces:   growth + dissolve cycle -> all channels
```

## Wetmap Workflow (Simulation-Driven)

```
SOP Context:
  1. Simulate fluid/particles hitting surface
  2. Generate VDB of wet regions
  3. Export VDB path

COP Context:
  4. Import VDB via Geometry to Layer COP
  5. OpenCL: sample position map against VDB density
  6. Generate wetness mask (Mono layer)
  7. Blur + feather edges for soft transitions
  8. Output as OUT_wetness

MaterialX Integration:
  9. Mix dry_material <-> wet_material using wetness
  10. op:/stage/copnet1/OUT_wetness -> mix factor

Result: Dynamic wetmaps driven by simulation, live in shader
```

### Wetmap OpenCL Kernel

```c
#bind layer position? val=0     // World position from rasterize
#bind layer vdb_density? val=0  // VDB density imported to layer
#bind layer !dst
#bind parm float falloff val=2.0

@KERNEL
{
    float density = @vdb_density.x;

    // Soft falloff from wet to dry
    float wetness = smoothstep(0.0f, @falloff, density);

    @dst = (float4)(wetness, wetness, wetness, 1.0f);
}
```

## Karma AOV Compositing

### Beauty Rebuild from Light Passes

```python
import hou

copnet = hou.node("/obj/copnet1")

# Load individual AOVs from Karma EXR output
diffuse_d = copnet.createNode("file")
diffuse_d.parm("filename1").set("$HIP/render/diffuse_direct.exr")
diffuse_d.setName("diffuse_direct")

diffuse_i = copnet.createNode("file")
diffuse_i.parm("filename1").set("$HIP/render/diffuse_indirect.exr")
diffuse_i.setName("diffuse_indirect")

spec_d = copnet.createNode("file")
spec_d.parm("filename1").set("$HIP/render/specular_direct.exr")
spec_d.setName("spec_direct")

spec_i = copnet.createNode("file")
spec_i.parm("filename1").set("$HIP/render/specular_indirect.exr")
spec_i.setName("spec_indirect")

emission = copnet.createNode("file")
emission.parm("filename1").set("$HIP/render/emission.exr")
emission.setName("emission")

# Combine: diffuse = direct + indirect
diff_add = copnet.createNode("add")
diff_add.setInput(0, diffuse_d)
diff_add.setInput(1, diffuse_i)
diff_add.setName("diffuse_combined")

# Combine: specular = direct + indirect
spec_add = copnet.createNode("add")
spec_add.setInput(0, spec_d)
spec_add.setInput(1, spec_i)
spec_add.setName("spec_combined")

# Beauty rebuild: diffuse + specular + emission
beauty1 = copnet.createNode("add")
beauty1.setInput(0, diff_add)
beauty1.setInput(1, spec_add)

beauty_final = copnet.createNode("add")
beauty_final.setInput(0, beauty1)
beauty_final.setInput(1, emission)
beauty_final.setName("beauty_recomp")
beauty_final.setDisplayFlag(True)
```

### AOV Compositing Network Pattern

```
File (diffuse_direct.exr)  --+
File (diffuse_indirect.exr) -+-> Add -> diffuse_combined
File (spec_direct.exr)    ---+
File (spec_indirect.exr)  ---+-> Add -> spec_combined
File (emission.exr) ---------+
                              |
diffuse + spec + emission  ---+-> Add -> beauty_recomp

Compare beauty_recomp vs original beauty.exr for verification.
Differences indicate missing AOVs or LPE tag issues.
```

## Slap Comp (Live Viewport Compositing)

```
H21: Slap comp supported in Render Gallery + LOP Vulkan Viewport

Setup:
  1. In LOP context, set up Karma render
  2. Create COP network for comp operations
  3. COP reads from viewport render (live input)
  4. Apply grading, bloom, vignette, LUT
  5. Output feeds back to viewport display

Artist workflow:
  - Render in viewport -> see composited result LIVE
  - Adjust lighting -> comp updates immediately
  - Iterate look dev without full render cycle
  - Export comp settings to production pipeline

Key advantage: creative decisions with instant feedback
```

## UDIM Support (H21)

```
COP Network UDIM parameter:
  - Set default UDIM tile in network toolbar
  - Replaces <UDIM> token in filenames
  - Per-tile texture generation

Workflow for multi-UDIM procedural textures:
  1. Set UDIM range on COP network
  2. COPs process per tile (UV-aware)
  3. MaterialX references with <UDIM> pattern
  4. Karma resolves correct tile per polygon

Enables: fully procedural multi-tile textures
without pre-baked UDIM texture files.
```

## PDG -> COP: Batch Processing

### ROP COP Output in TOPs

```
TOP Network:
  file_pattern1 (find input images)
      |
  rop_cop1 (cook COP network per image)
      |
  wait_all1

The ROP COP Output TOP:
  - Points to a COP network path
  - Cooks the network per work item
  - Supports frame range iteration
  - Outputs to @pdg_output attribute
```

### Wedged Texture Generation via PDG

```
TOP Network:
  wedge1 (vary noise params: freq, octaves, seed)
      |
  rop_cop1 (cook procedural texture COP per wedge)
      |
  partition1 (group by variant name)
      |
  python1 (generate contact sheet / comparison)

Result: N texture variations generated in parallel via PDG
Each work item produces a unique texture from same COP network.
```

```python
# PDG work item attribute access in COP Python Snippet
import pdg
item = pdg.workItem()
freq = item.floatAttribValue("freq")
seed = item.intAttribValue("seed")
```

## Cross-Context Data Flow Summary

```
                    +--------------+
                    |   SOP        |
                    |  (geometry)  |
                    +------+-------+
                           | rasterize / import
                           v
+-----------+    +----------------------+    +-----------+
|  DOP      |--->|    COPERNICUS        |<---|  LOP      |
| (sim VDB) |    |  (GPU processing)   |    | (USD)     |
+-----------+    +--------+-------------+    +-----------+
  volumes/VDB      |         | op: path     ^    |
                   |         v              |    | slap comp
                   |    +-----------+  +----+--------+
                   |    | MaterialX |  |   Karma     |
                   |    | (shader)  |  |  (render)   |
                   |    +-----------+  +-------------+
                   v
              +-----------+
              |   PDG     |
              | (batch)   |
              +-----------+
```
