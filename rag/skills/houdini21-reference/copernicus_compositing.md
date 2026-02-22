# Copernicus GPU Compositing (Houdini 21)

## Triggers
copernicus, compositing, gpu comp, cop, grade, tonemap, cryptomatte, denoise,
layer comp, beauty rebuild, aov comp, depth effects, motion blur 2d, glow, blur

## Context
Copernicus is Houdini 21's GPU-accelerated compositing framework, replacing legacy COPs.
Runs on GPU (OpenCL/Metal), OCIO-aware, ACES-ready. All code is Houdini Python.

Note: This file uses `cop2net` + `cop:` prefixed node names (legacy COP2 table syntax
inside /img context). For modern Copernicus workflows at /obj or /stage level, use
`copnet` with bare node names (e.g., `createNode("file")` not `createNode("cop:file")`).
See copernicus_python_api.md for the modern pattern.

## Code

```python
# Copernicus compositing pipeline: load AOVs -> rebuild beauty -> grade -> output
import hou

def create_comp_network(parent="/img"):
    """Create a Copernicus compositing network for production render comp."""
    img = hou.node(parent)
    if not img:
        img = hou.node("/").createNode("img", "comp")

    cop = img.createNode("cop2net", "copernicus_comp")

    # Load beauty render
    beauty = cop.createNode("cop:file", "beauty")
    beauty.parm("filename").set("$HIP/render/beauty.$F4.exr")

    # Load utility passes
    depth = cop.createNode("cop:file", "depth")
    depth.parm("filename").set("$HIP/render/depth.$F4.exr")

    normal = cop.createNode("cop:file", "normal")
    normal.parm("filename").set("$HIP/render/normal.$F4.exr")

    crypto = cop.createNode("cop:file", "crypto")
    crypto.parm("filename").set("$HIP/render/crypto_object.$F4.exr")

    # Grade (lift/gamma/gain -- ASC CDL compatible)
    grade = cop.createNode("cop:grade", "color_correct")
    grade.setInput(0, beauty)
    grade.parm("gain").set(1.1)        # Slight brightness boost
    grade.parm("gamma").set(1.0)
    grade.parm("lift").set(0.0)
    grade.parm("saturation").set(1.05)  # Subtle saturation boost

    # Tonemap (HDR to display range)
    tonemap = cop.createNode("cop:tonemap", "display_transform")
    tonemap.setInput(0, grade)
    # Tonemap methods: Reinhard, ACES, custom curve
    tonemap.parm("method").set("aces")  # ACES output transform

    # Output to disk
    output = cop.createNode("cop:rop_comp", "write_output")
    output.setInput(0, tonemap)
    output.parm("copoutput").set("$HIP/comp/final.$F4.exr")

    cop.layoutChildren()
    print("Copernicus comp network created")
    return cop

create_comp_network()
```

```python
# AOV beauty rebuild: reconstruct beauty from individual light passes
import hou

def setup_beauty_rebuild(cop_path):
    """Rebuild beauty from AOV passes.
    beauty = direct_diffuse + indirect_diffuse
           + direct_specular + indirect_specular
           + direct_emission + sss
    """
    cop = hou.node(cop_path)
    if not cop:
        return

    # Load each AOV pass
    aov_files = {
        "direct_diffuse":    "$HIP/render/direct_diffuse.$F4.exr",
        "indirect_diffuse":  "$HIP/render/indirect_diffuse.$F4.exr",
        "direct_specular":   "$HIP/render/direct_specular.$F4.exr",
        "indirect_specular": "$HIP/render/indirect_specular.$F4.exr",
        "emission":          "$HIP/render/direct_emission.$F4.exr",
        "sss":               "$HIP/render/sss.$F4.exr",
    }

    file_nodes = {}
    for name, path in aov_files.items():
        node = cop.createNode("cop:file", name)
        node.parm("filename").set(path)
        file_nodes[name] = node

    # Layer comp: add all passes together
    layer = cop.createNode("cop:layer_comp", "beauty_rebuild")
    layer.parm("operation").set("add")
    for i, (name, node) in enumerate(file_nodes.items()):
        layer.setInput(i, node)

    cop.layoutChildren()
    print(f"Beauty rebuild from {len(aov_files)} AOV passes")
    return layer

setup_beauty_rebuild("/img/comp/copernicus_comp")
```

```python
# Color correction operations
import hou

def color_correct(cop_path, input_node_name):
    """Apply production color correction chain."""
    cop = hou.node(cop_path)
    if not cop:
        return

    src = cop.node(input_node_name)

    # Exposure adjustment (in stops)
    exposure = cop.createNode("cop:exposure", "exposure_adj")
    exposure.setInput(0, src)
    exposure.parm("exposure").set(0.5)   # +0.5 stops brighter

    # Saturation
    sat = cop.createNode("cop:saturation", "sat_boost")
    sat.setInput(0, exposure)
    sat.parm("saturation").set(1.1)      # 10% more saturated

    # OCIO transform (color space conversion)
    ocio = cop.createNode("cop:ocio_transform", "aces_to_srgb")
    ocio.setInput(0, sat)
    ocio.parm("source_space").set("ACEScg")
    ocio.parm("target_space").set("sRGB")

    # LUT application (1D/3D, .cube, .spi1d/.spi3d)
    # lut = cop.createNode("cop:lut", "show_lut")
    # lut.setInput(0, ocio)
    # lut.parm("lutfile").set("$HIP/luts/show_lut.cube")

    cop.layoutChildren()
    print("Color correction chain applied")
    return ocio
```

```python
# Cryptomatte extraction for selective grading
import hou

def extract_cryptomatte(cop_path, crypto_file, selection_name):
    """Extract a matte from Cryptomatte AOV for selective color correction.
    crypto_file: path to crypto_material or crypto_object EXR
    selection_name: material/object name to isolate (e.g., 'hero_mat')
    """
    cop = hou.node(cop_path)
    if not cop:
        return

    # Load Cryptomatte EXR
    crypto = cop.createNode("cop:file", "crypto_input")
    crypto.parm("filename").set(crypto_file)

    # Extract selection as alpha matte
    extract = cop.createNode("cop:crypto_extract", "matte_extract")
    extract.setInput(0, crypto)
    extract.parm("selection").set(selection_name)  # Object or material name

    # Use matte for selective grading
    # Output: per-selection alpha mask
    # Multiply with grade adjustment for isolated color correction
    cop.layoutChildren()
    print(f"Cryptomatte matte: '{selection_name}'")
    return extract

extract_cryptomatte(
    "/img/comp/copernicus_comp",
    "$HIP/render/crypto_object.$F4.exr",
    "hero_character"
)
```

```python
# Depth-based effects and 2D motion blur
import hou

def add_depth_effects(cop_path, beauty_node, depth_node):
    """Add depth-based fog and atmospheric perspective."""
    cop = hou.node(cop_path)
    if not cop:
        return

    beauty = cop.node(beauty_node)
    depth = cop.node(depth_node)

    # Depth-based effects: fog, DOF, atmospheric
    depth_fx = cop.createNode("cop:depth_effects", "depth_fog")
    depth_fx.setInput(0, beauty)
    depth_fx.setInput(1, depth)
    depth_fx.parm("fog_color_r").set(0.6)
    depth_fx.parm("fog_color_g").set(0.7)
    depth_fx.parm("fog_color_b").set(0.85)
    depth_fx.parm("fog_start").set(10.0)     # Distance where fog begins
    depth_fx.parm("fog_end").set(100.0)      # Distance where fog is fully opaque

    cop.layoutChildren()
    return depth_fx


def add_motion_blur_2d(cop_path, beauty_node, motion_vec_file):
    """Apply 2D motion blur from motion vector pass."""
    cop = hou.node(cop_path)
    if not cop:
        return

    beauty = cop.node(beauty_node)

    mv = cop.createNode("cop:file", "motion_vectors")
    mv.parm("filename").set(motion_vec_file)

    mblur = cop.createNode("cop:motion_blur", "mblur_2d")
    mblur.setInput(0, beauty)
    mblur.setInput(1, mv)
    mblur.parm("shutter").set(0.5)       # Shutter angle

    cop.layoutChildren()
    return mblur


def add_glow(cop_path, input_node):
    """Add bloom/glow effect to bright areas."""
    cop = hou.node(cop_path)
    if not cop:
        return

    src = cop.node(input_node)

    glow = cop.createNode("cop:glow", "bloom")
    glow.setInput(0, src)
    glow.parm("threshold").set(1.0)      # Only glow pixels > 1.0 (HDR)
    glow.parm("intensity").set(0.3)
    glow.parm("radius").set(20.0)

    cop.layoutChildren()
    return glow
```

```python
# Denoise in Copernicus
import hou

def denoise_comp(cop_path, beauty_node, albedo_file=None, normal_file=None, method="oidn"):
    """Apply denoising to beauty pass.
    method: 'oidn' (Intel CPU) or 'optix' (NVIDIA GPU)
    Auxiliary AOVs (albedo, normal) improve edge preservation."""
    cop = hou.node(cop_path)
    if not cop:
        return

    beauty = cop.node(beauty_node)

    denoise = cop.createNode("cop:denoise", "denoise_beauty")
    denoise.setInput(0, beauty)
    denoise.parm("method").set(method)

    if albedo_file:
        albedo = cop.createNode("cop:file", "denoise_albedo")
        albedo.parm("filename").set(albedo_file)
        denoise.setInput(1, albedo)

    if normal_file:
        normal = cop.createNode("cop:file", "denoise_normal")
        normal.parm("filename").set(normal_file)
        denoise.setInput(2, normal)

    # CRITICAL: denoise beauty only, NOT utility AOVs (depth, normal, crypto)
    cop.layoutChildren()
    print(f"Denoising with {method}, aux AOVs: albedo={albedo_file is not None}, normal={normal_file is not None}")
    return denoise

denoise_comp(
    "/img/comp/copernicus_comp",
    "beauty",
    albedo_file="$HIP/render/denoise_albedo.$F4.exr",
    normal_file="$HIP/render/denoise_normal.$F4.exr",
)
```

```python
# GPU memory budget reference
GPU_MEMORY_BUDGET = {
    # 4K EXR with N AOVs -> approximate VRAM usage
    "4k_beauty_only":    "~0.5 GB",
    "4k_10_aovs":        "~2 GB",
    "4k_20_aovs":        "~3-5 GB",
    "8k_20_aovs":        "~12-20 GB",
    # GPU cards
    "RTX_4090_24GB":     "Comfortable for most production 4K comps",
    "RTX_3080_10GB":     "4K with limited AOVs, reduce for interactive",
    # If VRAM exceeded: falls back to CPU (slower but functional)
}

for key, val in sorted(GPU_MEMORY_BUDGET.items()):
    print(f"  {key}: {val}")
```

## Common Mistakes
- Applying display transform (ACES/sRGB) before comp operations -- work in linear, transform at output only
- Denoising utility AOVs (depth, normal, cryptomatte) -- only denoise beauty pass
- Not setting $OCIO environment variable -- Copernicus nodes need it for color space awareness
- Using JPEG/PNG for intermediate files -- always use EXR (half-float minimum) for comp work
- Manual add chains instead of `layer_comp` node -- layer_comp is faster and handles edge cases
- Exceeding VRAM with too many AOVs loaded simultaneously -- reduce AOV count or resolution for interactive preview
