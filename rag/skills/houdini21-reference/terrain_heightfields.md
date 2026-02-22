# Terrain and Heightfields

## Triggers
heightfield, terrain, erosion, heightfield_noise, heightfield_erode, heightfield_scatter,
heightfield_convert, heightfield_mask, heightfield_pattern, heightfield_paint,
terrain mesh, terrain LOD, scatter vegetation, scatter rocks, terrain to solaris,
sopimport terrain, terrain displacement, hydraulic erosion, thermal erosion,
bedrock layer, sediment layer, debris layer, moisture map, terrain caching

## Context
Houdini's heightfield system uses 2D volume grids (one voxel deep) for terrain creation.
Each heightfield is a stack of named layers: height, mask, sediment, bedrock, debris, water.
The canonical pipeline is: heightfield -> noise -> erode -> mask -> scatter -> convert -> cache -> solaris.

---

## Heightfield Creation

```python
import hou

obj = hou.node("/obj")
geo = obj.createNode("geo", "terrain_geo")

# --- Base heightfield grid ---
hf = geo.createNode("heightfield", "hf_base")
# Terrain footprint in world units
hf.parm("sizex").set(1000.0)       # X extent (metres)
hf.parm("sizey").set(1000.0)       # Z extent (metres)
# Grid spacing controls resolution: lower = more voxels, slower ops
# Layout/blocking: 5.0 | Mid preview: 1.0 | Hero: 0.25-0.5 | Close-up: 0.1
# WARNING: 0.1 spacing on 1000x1000 = 100M voxels. Start coarse.
hf.parm("gridspacing").set(1.0)    # metres per voxel
hf.parm("height").set(0.0)         # initial flat elevation
# Orientation: 0=XZ (standard terrain), 1=XY, 2=YZ
hf.parm("orientation").set(0)
hf.parm("center", 0).set(0.0)
hf.parm("center", 1).set(0.0)
hf.parm("center", 2).set(0.0)
```

---

## Noise Layers (Terrain Shaping)

```python
# --- Primary macro-scale noise (mountains/hills) ---
noise1 = geo.createNode("heightfield_noise", "hf_noise_macro")
noise1.setInput(0, hf)
# noisetype: 0=Perlin, 1=Simplex, 2=Worley, 3=fBm, 4=Sparse Convolution
noise1.parm("noisetype").set(0)         # Perlin
noise1.parm("height").set(200.0)        # amplitude in world units
noise1.parm("elementsize").set(500.0)   # feature wavelength (large = broad mountains)
noise1.parm("octaves").set(8)           # detail layers stacked (more = rougher)
noise1.parm("roughness").set(0.5)       # high-freq gain per octave (0=smooth, 1=jagged)
noise1.parm("lacunarity").set(2.0)      # frequency multiplier per octave
noise1.parm("offset", 0).set(0.0)       # X seed offset for variation
noise1.parm("offset", 1).set(0.0)       # Y seed offset
noise1.parm("offset", 2).set(0.0)       # Z seed offset

# --- Secondary detail noise (mid-scale ridges) ---
noise2 = geo.createNode("heightfield_noise", "hf_noise_detail")
noise2.setInput(0, noise1)
noise2.parm("noisetype").set(3)         # fBm for more organic feel
noise2.parm("height").set(30.0)         # smaller amplitude overlaid on macro
noise2.parm("elementsize").set(80.0)    # medium feature size
noise2.parm("octaves").set(6)
noise2.parm("roughness").set(0.65)

# --- Terrain patterning (terraces / ridges / distortion) ---
pattern = geo.createNode("heightfield_pattern", "hf_terraces")
pattern.setInput(0, noise2)
# patterntype: 0=Terraces, 1=Ridges, 2=Radial, 3=Distort
pattern.parm("patterntype").set(0)      # terraces for mesa / stratified rock look
pattern.parm("height").set(50.0)        # terrace height band
pattern.parm("count").set(8)            # number of terrace steps
pattern.parm("sharpness").set(0.7)      # edge crispness (0=rounded, 1=hard)
```

---

## Masking

```python
# --- Mask by slope (identify flat vs steep areas) ---
mask_slope = geo.createNode("heightfield_mask_by_feature", "hf_mask_slope")
mask_slope.setInput(0, pattern)
# feature: 0=Height, 1=Slope, 2=Curvature, 3=Noise, 4=Occlusion
mask_slope.parm("feature").set(1)           # slope-based mask
mask_slope.parm("featurerange", 0).set(0.0) # min slope angle (degrees) for mask=1
mask_slope.parm("featurerange", 1).set(30.0)# max slope angle for mask=1 (flat areas)
mask_slope.parm("invert").set(0)            # 0=flat areas white, 1=steep areas white

# --- Mask by height (for snow line, vegetation zones) ---
mask_height = geo.createNode("heightfield_mask_by_feature", "hf_mask_height")
mask_height.setInput(0, mask_slope)
mask_height.parm("feature").set(0)              # height-based
mask_height.parm("layer").set("mask2")          # write to a separate layer slot
mask_height.parm("featurerange", 0).set(150.0)  # above 150 units = snow zone
mask_height.parm("featurerange", 1).set(300.0)  # full snow coverage above 300
mask_height.parm("invert").set(0)

# --- Mask by object (protect road/building footprint from erosion) ---
mask_obj = geo.createNode("heightfield_mask_by_object", "hf_mask_road")
mask_obj.setInput(0, mask_height)
# Connect a polygon object (road spline, building pad) to input 1
# mask_obj.setInput(1, road_geo_node)
mask_obj.parm("layer").set("mask_protected")
mask_obj.parm("expand").set(5.0)    # grow mask by 5 units around object
mask_obj.parm("invert").set(1)      # invert: protected areas = 0 (no erosion)
```

---

## Erosion Configuration

```python
# --- Hydraulic + Thermal erosion combined ---
erode = geo.createNode("heightfield_erode", "hf_erode")
erode.setInput(0, mask_obj)

# erosionmode: 0=Hydraulic, 1=Thermal, 2=Both (recommended for natural terrain)
erode.parm("erosionmode").set(2)

# Simulation length: more iterations = deeper, more developed drainage channels
# Start at 25-50 for layout, use 100-200 for hero terrain
erode.parm("iterations").set(50)

# --- Hydraulic erosion parameters ---
erode.parm("rainamount").set(1.0)       # water injected per iteration (scale to terrain)
erode.parm("eroderate").set(0.3)        # material removal rate; keep low (0.1-0.4) for realism
erode.parm("depositionrate").set(0.5)   # how much sediment drops when water slows
erode.parm("sedimentcap").set(0.5)      # max sediment a water unit can carry
erode.parm("evaporationrate").set(0.05) # water loss per iteration
erode.parm("wateradhesion").set(0.5)    # tendency of water to follow existing channels

# --- Thermal erosion parameters ---
erode.parm("bankangle").set(30.0)       # max stable slope (degrees); material slides below this
erode.parm("globalerosion").set(0.05)   # uniform surface wearing (small value)
erode.parm("thermalrate").set(0.5)      # speed of thermal collapse

# --- Erosion masking: use "mask_protected" layer to shield roads/buildings ---
erode.parm("masklayer").set("mask")     # main mask drives erosion density

# Workflow: erode at coarse res first (gridspacing=2) for channel patterns,
# then refine to 0.5 and re-erode for surface detail.
```

---

## Scatter (Vegetation and Rocks)

```python
# --- Scatter points for tree placement on flat, non-eroded areas ---
scatter = geo.createNode("heightfield_scatter", "hf_scatter_trees")
scatter.setInput(0, erode)

scatter.parm("npts").set(5000)              # total scatter point budget
scatter.parm("densitylayer").set("mask")    # layer driving density (flat=white=more points)
scatter.parm("removeoverlap").set(1)        # prevent overlapping instances
scatter.parm("overlapradius").set(3.0)      # minimum spacing between points (world units)

# Scale variation for natural look
scatter.parm("scalemin").set(0.8)
scatter.parm("scalemax").set(1.4)

scatter.parm("orienttonormal").set(1)       # align Y-up to terrain surface normal
scatter.parm("seed").set(12345)             # deterministic seed

# --- Copy tree geometry to scattered points ---
# trees_geo = geo.createNode("file", "trees_file")
# trees_geo.parm("file").set("/assets/trees/oak_packed.bgeo.sc")
# copy_trees = geo.createNode("copytopoints", "copy_trees")
# copy_trees.setInput(0, trees_geo)
# copy_trees.setInput(1, scatter)
# copy_trees.parm("pack").set(1)     # use packed primitives for memory efficiency

# --- Rock scatter (steeper slopes, use inverted slope mask) ---
scatter_rocks = geo.createNode("heightfield_scatter", "hf_scatter_rocks")
scatter_rocks.setInput(0, erode)
scatter_rocks.parm("npts").set(2000)
scatter_rocks.parm("densitylayer").set("mask")
scatter_rocks.parm("invertdensity").set(1)  # rocks on steep areas (inverted flat mask)
scatter_rocks.parm("overlapradius").set(1.5)
scatter_rocks.parm("scalemin").set(0.5)
scatter_rocks.parm("scalemax").set(3.0)
scatter_rocks.parm("seed").set(99999)
```

---

## Convert Heightfield to Polygon Mesh

```python
# --- Convert heightfield volume to renderable polygon mesh ---
convert = geo.createNode("heightfield_convert", "hf_convert_hero")
convert.setInput(0, erode)

# converto: 0=Polygon Mesh, 1=VDB, 2=Points
convert.parm("converto").set(0)         # polygon mesh for Karma rendering

# lod: 1.0=full resolution, 0.5=half, 0.25=quarter
# Hero (close-up) = 1.0 | Mid = 0.25 | Far/bg = 0.05
convert.parm("lod").set(1.0)

convert.parm("triangulate").set(1)      # triangles for displacement-safe mesh

# Transfer heightfield layers as vertex/point attributes for shading
convert.parm("transferheight").set(1)   # height attribute -> drive blend masks
convert.parm("transfermask").set(1)     # mask (slope) -> grass/cliff blending
```

---

## LOD Pipeline

```python
# --- Build three LOD levels from the same eroded heightfield ---
lod_configs = [
    ("hero",   1.0,   "D:/terrain_cache/hero/terrain.$F4.bgeo.sc"),
    ("mid",    0.25,  "D:/terrain_cache/mid/terrain.$F4.bgeo.sc"),
    ("far",    0.05,  "D:/terrain_cache/far/terrain.$F4.bgeo.sc"),
]

lod_nodes = {}
for lod_name, lod_val, cache_path in lod_configs:
    # Convert at this LOD level
    conv = geo.createNode("heightfield_convert", f"hf_convert_{lod_name}")
    conv.setInput(0, erode)
    conv.parm("converto").set(0)
    conv.parm("lod").set(lod_val)
    conv.parm("triangulate").set(1)

    # Cache to disk
    fc = geo.createNode("filecache", f"cache_{lod_name}")
    fc.setInput(0, conv)
    fc.parm("file").set(cache_path)
    fc.parm("loadfromdisk").set(1)      # toggle to 0 to re-cook and write
    lod_nodes[lod_name] = fc

# --- Save node positions for readability ---
hf.setPosition(hou.Vector2(0, 0))
noise1.setPosition(hou.Vector2(0, -2))
noise2.setPosition(hou.Vector2(0, -4))
pattern.setPosition(hou.Vector2(0, -6))
mask_slope.setPosition(hou.Vector2(0, -8))
erode.setPosition(hou.Vector2(0, -12))
scatter.setPosition(hou.Vector2(-4, -14))
convert.setPosition(hou.Vector2(4, -14))
geo.layoutChildren()
```

---

## Caching the Erosion Result

```python
# --- FileCache after erosion: erosion is expensive, cache it ---
cache_erode = geo.createNode("filecache", "cache_eroded_hf")
cache_erode.setInput(0, erode)

cache_path_hf = "D:/terrain_cache/eroded/terrain_hf.$F4.bgeo.sc"
cache_erode.parm("file").set(cache_path_hf)

# To write: set loadfromdisk=0 and cook
cache_erode.parm("loadfromdisk").set(0)
cache_erode.cook(force=True)

# To read from cache in subsequent sessions: set loadfromdisk=1
cache_erode.parm("loadfromdisk").set(1)

# Wire everything downstream from the cache, not from erode directly
# so re-cooks of scatter/convert don't trigger re-erosion.
scatter.setInput(0, cache_erode)
convert.setInput(0, cache_erode)
```

---

## Solaris Import

```python
# --- Import converted terrain polygon mesh into Solaris ---
stage = hou.node("/stage")

# Method 1: SOP Import LOP (polygon mesh from filecache)
sop_import = stage.createNode("sopimport", "terrain_import")
sop_import.parm("soppath").set(convert.path())   # point at heightfield_convert output
sop_import.parm("primpath").set("/world/terrain")
sop_import.parm("applydefaultmaterial").set(0)

# Method 2: Import cached bgeo directly via File LOP
# file_lop = stage.createNode("file", "terrain_file")
# file_lop.parm("filepath1").set("D:/terrain_cache/hero/terrain.0001.bgeo.sc")

# --- Assign terrain material ---
mat_assign = stage.createNode("assignmaterial", "terrain_mat")
mat_assign.setInput(0, sop_import)
mat_assign.parm("primpattern1").set("/world/terrain")
mat_assign.parm("matspecpath1").set("/materials/terrain_surface")

# --- Merge with scene root ---
# merge = stage.createNode("merge", "scene_merge")
# merge.setInput(0, existing_scene)
# merge.setInput(1, mat_assign)

# Transfer heightfield erosion layers to USD primvars for MaterialX shading:
# In the SOP network, before sopimport, promote volume layers to point attributes:
attrib_vop = geo.createNode("heightfield_layer_property", "hf_attribs")
# heightfield_layer_property extracts named layers as float attributes on the mesh
# Connect after heightfield_convert, before filecache:
#   convert -> attrib_vop -> cache_hero -> sopimport
```

---

## Erosion Layers as Shading Masks (Python extraction)

```python
# After sopimport, erosion layer values are available as primvars.
# Example: read layer values back via hou for debugging or attribute transfer.

hf_node = geo.node("hf_erode")
if hf_node:
    geo_data = hf_node.geometry()
    # Heightfield layers are stored as volume primitives
    for vol in geo_data.prims():
        if hasattr(vol, "name"):
            print(f"Layer: {vol.name()}, Res: {vol.resolution()}")
    # Typical output:
    # Layer: height,   Res: (1000, 1, 1000)
    # Layer: mask,     Res: (1000, 1, 1000)
    # Layer: bedrock,  Res: (1000, 1, 1000)
    # Layer: debris,   Res: (1000, 1, 1000)
    # Layer: sediment, Res: (1000, 1, 1000)
    # Layer: water,    Res: (1000, 1, 1000)
```

---

## Full Terrain Pipeline (Consolidated)

```python
import hou

def build_terrain_pipeline(
    parent_path="/obj/terrain_geo",
    size=1000.0,
    grid_spacing=1.0,
    noise_height=200.0,
    erode_iterations=50,
    cache_dir="D:/terrain_cache"
):
    """
    Build a complete production terrain pipeline:
    base -> noise -> erosion -> mask -> scatter -> LOD convert -> cache -> solaris import
    """
    geo = hou.node(parent_path)
    if not geo:
        obj = hou.node("/obj")
        geo = obj.createNode("geo", parent_path.split("/")[-1])

    # 1. Base grid
    hf = geo.createNode("heightfield", "hf_base")
    hf.parm("sizex").set(size)
    hf.parm("sizey").set(size)
    hf.parm("gridspacing").set(grid_spacing)

    # 2. Macro noise
    n1 = geo.createNode("heightfield_noise", "hf_noise_macro")
    n1.setInput(0, hf)
    n1.parm("height").set(noise_height)
    n1.parm("elementsize").set(size * 0.5)
    n1.parm("octaves").set(8)
    n1.parm("roughness").set(0.5)

    # 3. Detail noise
    n2 = geo.createNode("heightfield_noise", "hf_noise_detail")
    n2.setInput(0, n1)
    n2.parm("height").set(noise_height * 0.15)
    n2.parm("elementsize").set(80.0)
    n2.parm("noisetype").set(3)     # fBm
    n2.parm("octaves").set(6)
    n2.parm("roughness").set(0.65)

    # 4. Slope mask (flat areas = white = vegetation-ready)
    msk = geo.createNode("heightfield_mask_by_feature", "hf_mask_slope")
    msk.setInput(0, n2)
    msk.parm("feature").set(1)              # slope
    msk.parm("featurerange", 0).set(0.0)
    msk.parm("featurerange", 1).set(30.0)

    # 5. Erosion
    erode = geo.createNode("heightfield_erode", "hf_erode")
    erode.setInput(0, msk)
    erode.parm("erosionmode").set(2)        # hydraulic + thermal
    erode.parm("iterations").set(erode_iterations)
    erode.parm("eroderate").set(0.3)
    erode.parm("bankangle").set(30.0)
    erode.parm("rainamount").set(1.0)

    # 6. Cache erosion result
    fc_erode = geo.createNode("filecache", "cache_erode")
    fc_erode.setInput(0, erode)
    fc_erode.parm("file").set(f"{cache_dir}/eroded/terrain.$F4.bgeo.sc")
    fc_erode.parm("loadfromdisk").set(1)

    # 7. LOD conversions
    for lod_name, lod_val in [("hero", 1.0), ("mid", 0.25), ("far", 0.05)]:
        conv = geo.createNode("heightfield_convert", f"hf_convert_{lod_name}")
        conv.setInput(0, fc_erode)
        conv.parm("lod").set(lod_val)
        conv.parm("triangulate").set(1)
        fc = geo.createNode("filecache", f"cache_{lod_name}")
        fc.setInput(0, conv)
        fc.parm("file").set(f"{cache_dir}/{lod_name}/terrain.$F4.bgeo.sc")
        fc.parm("loadfromdisk").set(1)

    # 8. Scatter on eroded terrain (flat mask)
    scat = geo.createNode("heightfield_scatter", "hf_scatter")
    scat.setInput(0, fc_erode)
    scat.parm("npts").set(5000)
    scat.parm("densitylayer").set("mask")
    scat.parm("orienttonormal").set(1)

    # 9. Solaris sopimport (hero mesh)
    hero_conv = geo.node("hf_convert_hero")
    stage = hou.node("/stage")
    if stage and hero_conv:
        sop_imp = stage.createNode("sopimport", "terrain")
        sop_imp.parm("soppath").set(hero_conv.path())
        sop_imp.parm("primpath").set("/world/terrain")

    geo.layoutChildren()
    print(f"Terrain pipeline built: {geo.path()}")
    return geo


# Run it:
# build_terrain_pipeline(
#     parent_path="/obj/hero_terrain",
#     size=1000.0,
#     grid_spacing=1.0,
#     noise_height=200.0,
#     erode_iterations=50,
#     cache_dir="D:/terrain_cache"
# )
```

---

## Common Mistakes

**Terrain looks artificial**: Missing erosion. Run hydraulic + thermal erosion with at least 50 iterations. Noise alone produces obvious procedural patterns.

**Erosion too aggressive**: `eroderate` too high (>0.5). Lower it to 0.1-0.3 and increase `iterations` instead — more iterations at lower rate produces realistic channel development without unrealistic deep cuts.

**Flat terrain, no features**: Noise amplitude too low relative to terrain size. `height` on heightfield_noise should be 10-30% of terrain size for mountains, 2-10% for gentle hills.

**Scatter points on cliffs**: Slope mask missing or inverted. Use heightfield_mask_by_feature with feature=slope and range 0-30 degrees; scatter with densitylayer="mask" places points only on flat ground.

**Memory exhaustion**: Grid spacing too fine. `gridspacing=0.1` on a 1000-unit terrain = 100M voxels. Start at 2.0 for layout, refine to 0.5 for hero areas only.

**Slow rendering**: Rendering the heightfield as a volume. Always convert to polygon mesh with heightfield_convert before sopimport for Karma. Volume rendering of terrain is 10-50x slower than mesh.

**Banding / stairstepping**: Grid spacing too coarse for the view distance. Decrease gridspacing or add micro-displacement in the Karma material to recover surface detail without re-cooking the full heightfield.

**Re-erosion on every cook**: Not caching after erode. Place a filecache node immediately after heightfield_erode with loadfromdisk=1. This is the single most important performance optimization in a terrain pipeline.
