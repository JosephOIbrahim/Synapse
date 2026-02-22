# Copernicus Python API — Houdini 21

Python API for creating, configuring, and cooking Copernicus COP networks programmatically.

## Creating COP Networks

```python
import hou

# COP network at /obj level (standalone compositing)
obj = hou.node("/obj")
copnet = obj.createNode("copnet")
copnet.setName("my_textures")

# COP network inside LOP context (for MaterialX op: paths)
stage = hou.node("/stage")
cop_in_lop = stage.createNode("copnet")
cop_in_lop.setName("procedural_textures")

# COP network inside SOP context (texture baking)
geo = hou.node("/obj/geo1")
cop_in_sop = geo.createNode("cop2net")
cop_in_sop.setName("bake_network")
```

## Common COP Node Types (Copernicus H21)

```python
copnet = hou.node("/obj/copnet1")

# Generators
file_node = copnet.createNode("file")
file_node.parm("filename1").set("$HIP/tex/input.exr")

noise = copnet.createNode("fractal_noise")
noise.parm("freq").set(8.0)
noise.parm("octaves").set(4)

color = copnet.createNode("constant")
# color.parm("color1r").set(0.5)

ramp = copnet.createNode("ramp")

# Color correction
grade = copnet.createNode("color_correct")
grade.parm("gain").set(1.2)

# Filters
blur = copnet.createNode("blur")
blur.parm("radius").set(5.0)

sharpen = copnet.createNode("sharpen")

# Compositing
over = copnet.createNode("over")
add = copnet.createNode("add")
multiply = copnet.createNode("multiply")

# Transform
xform = copnet.createNode("xform")
crop = copnet.createNode("crop")

# Custom GPU processing
opencl = copnet.createNode("opencl")

# Output
rop = copnet.createNode("rop_comp")
rop.parm("copoutput").set("$HIP/render/output.$F4.exr")
```

## Wiring and Display Flags

```python
# Connect nodes: dest.setInput(input_index, source_node)
blur.setInput(0, file_node)     # Input 0 = primary
grade.setInput(0, blur)
over.setInput(0, grade)         # Foreground
over.setInput(1, background)    # Background

# Set display and render flags
grade.setDisplayFlag(True)      # Shows in viewer
grade.setRenderFlag(True)       # Used for output

# Query connections
inputs = grade.inputs()         # List of connected input nodes
outputs = grade.outputs()       # List of downstream nodes
```

## OpenCL Node Configuration

```python
opencl = copnet.createNode("opencl")
opencl.setName("custom_effect")

kernel_code = '''
#bind layer src? val=0
#bind layer !dst
#bind parm float brightness val=1.0
#bind parm float contrast val=1.0

@KERNEL
{
    float4 c = @src;
    c.xyz *= @brightness;
    c.xyz = (c.xyz - 0.5f) * @contrast + 0.5f;
    @dst = c;
}
'''

# Set kernel code
opencl.parm("kernelcode").set(kernel_code)

# Access generated parameters (created from #bind parm)
# After setting kernel code, parameters appear on the node:
opencl.parm("brightness").set(1.5)
opencl.parm("contrast").set(1.2)

# Wire input
opencl.setInput(0, source_node)
```

## Solver (Block Begin/End) Creation

```python
copnet = hou.node("/obj/copnet1")

# Source image
source = copnet.createNode("file")
source.parm("filename1").set("$HIP/tex/seed_mask.exr")

# Create Block pair
block_begin = copnet.createNode("block_begin")
block_end = copnet.createNode("block_end")

# Processing node inside the solver
opencl = copnet.createNode("opencl")
opencl.parm("kernelcode").set(growth_kernel_code)

# Wire the solver loop
block_begin.setInput(0, source)       # Primary: initial state
opencl.setInput(0, block_begin)       # Process feedback
block_end.setInput(0, opencl)         # Close the loop

# Configure solver behavior
block_end.parm("method").set("feedback")    # Feedback loop mode
block_end.parm("iterations").set(10)        # Sub-steps per frame
block_end.parm("simulate").set(True)        # Frame-dependent mode

# Set output flags
block_end.setDisplayFlag(True)
block_end.setRenderFlag(True)
```

## Reaction-Diffusion Solver Setup

```python
copnet = hou.node("/obj/copnet1")

# Initial state: uniform A=1, small B seed
init_a = copnet.createNode("constant")
# Set to white (A=1.0 everywhere)

init_b = copnet.createNode("constant")
# Set to black (B=0.0 everywhere)

# Small seed region for B
seed = copnet.createNode("circle")   # or geometry mask

# Merge initial state
# ...

# Create R-D solver
block_begin = copnet.createNode("block_begin")
block_end = copnet.createNode("block_end")

rd_kernel = copnet.createNode("opencl")
rd_kernel.parm("kernelcode").set(gray_scott_kernel)

# Wire
block_begin.setInput(0, init_state)
rd_kernel.setInput(0, block_begin)
block_end.setInput(0, rd_kernel)

# R-D parameters
block_end.parm("iterations").set(20)   # Fast convergence
block_end.parm("simulate").set(True)

# Access R-D control parms on OpenCL node
rd_kernel.parm("feed").set(0.04)
rd_kernel.parm("kill").set(0.06)
rd_kernel.parm("dA").set(1.0)
rd_kernel.parm("dB").set(0.5)
```

## Procedural Texture Network (Full Pipeline)

```python
import hou

stage = hou.node("/stage")
copnet = stage.createNode("copnet")
copnet.setName("proc_textures")

# --- Albedo ---
noise_albedo = copnet.createNode("fractal_noise")
noise_albedo.parm("freq").set(6.0)
noise_albedo.parm("octaves").set(5)

ramp_albedo = copnet.createNode("ramp")
ramp_albedo.setInput(0, noise_albedo)
ramp_albedo.setName("OUT_albedo")
ramp_albedo.setDisplayFlag(True)

# --- Roughness ---
noise_rough = copnet.createNode("fractal_noise")
noise_rough.parm("freq").set(12.0)

thresh_rough = copnet.createNode("threshold")
thresh_rough.setInput(0, noise_rough)

blur_rough = copnet.createNode("blur")
blur_rough.setInput(0, thresh_rough)
blur_rough.parm("radius").set(3.0)
blur_rough.setName("OUT_roughness")

# --- Normal (from height) ---
noise_height = copnet.createNode("fractal_noise")
noise_height.parm("freq").set(8.0)

# Normal from height via OpenCL Sobel
normal_gen = copnet.createNode("opencl")
normal_gen.parm("kernelcode").set(height_to_normal_kernel)
normal_gen.setInput(0, noise_height)
normal_gen.setName("OUT_normal")

# MaterialX references:
#   base_color:         op:/stage/proc_textures/OUT_albedo
#   specular_roughness: op:/stage/proc_textures/OUT_roughness
#   normal:             op:/stage/proc_textures/OUT_normal

# Layout nodes for readability
copnet.layoutChildren()
```

## Height-to-Normal Kernel (for texture pipeline)

```python
height_to_normal_kernel = '''
#bind layer height? val=0.5
#bind layer !dst
#bind parm float strength val=1.0

@KERNEL
{
    int2 pos = (int2)(get_global_id(0), get_global_id(1));

    // Sample height neighbors
    int2 px = clamp(pos + (int2)(1, 0), (int2)(0), (int2)(@xres-1, @yres-1));
    int2 nx = clamp(pos + (int2)(-1, 0), (int2)(0), (int2)(@xres-1, @yres-1));
    int2 py = clamp(pos + (int2)(0, 1), (int2)(0), (int2)(@yres-1, @yres-1));
    int2 ny = clamp(pos + (int2)(0, -1), (int2)(0), (int2)(@xres-1, @yres-1));

    float hpx = @height.x;  // at px
    float hnx = @height.x;  // at nx
    float hpy = @height.x;  // at py
    float hny = @height.x;  // at ny

    // Central difference gradient
    float dx = (hpx - hnx) * @strength;
    float dy = (hpy - hny) * @strength;

    // Normal from gradient (tangent space)
    float3 n = normalize((float3)(-dx, -dy, 1.0f));

    // Encode to 0-1 range for storage
    n = n * 0.5f + 0.5f;

    @dst = (float4)(n.x, n.y, n.z, 1.0f);
}
'''
```

## Cooking and Exporting

```python
# Force cook a COP node
node = hou.node("/obj/copnet1/grade1")
node.cook(force=True)

# Get resolution
width = node.xRes()
height = node.yRes()

# Export via ROP COP Output
rop = copnet.createNode("rop_comp")
rop.parm("copoutput").set("$HIP/render/texture.exr")
rop.parm("trange").set(0)  # Render current frame
rop.render()

# Export frame range
rop.parm("trange").set(1)  # Render frame range
rop.parm("f1").set(1)
rop.parm("f2").set(100)
rop.parm("f3").set(1)      # Frame step
rop.render()
```

## Layer Data Access

```python
# Read pixel data from a COP node
node = hou.node("/obj/copnet1/grade1")

# Get all planes (layers)
planes = node.planes()  # e.g., ['C', 'A'] for color + alpha

# Get plane resolution
xres = node.xRes()
yres = node.yRes()

# Read pixel values (returns tuple of floats)
# allPixels(plane_name) -> flat array of pixel values
pixels = node.allPixels("C")  # Color plane

# Set pixel values
# node.setPixelsOfCookingPlane(plane_name, values, ...)
```

## Network Layout and Organization

```python
# Auto-layout all children
copnet.layoutChildren()

# Set node position manually
node.setPosition(hou.Vector2(2.0, -3.0))

# Set node color (for organization)
node.setColor(hou.Color(0.4, 0.8, 0.4))  # Green for outputs

# Add sticky note
sticky = copnet.createStickyNote()
sticky.setText("Albedo Branch")
sticky.setPosition(hou.Vector2(0, 0))
sticky.setSize(hou.Vector2(4, 2))

# Set node comment
node.setComment("Final output - do not modify")
node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
```

## SYNAPSE Integration Pattern

```python
# Pattern for SYNAPSE MCP tool calling COP operations
# via execute_python handler

def create_procedural_texture(copnet_path, noise_type, freq, channels):
    """Create procedural texture network via SYNAPSE."""
    import hou

    parent = hou.node(copnet_path)
    if parent is None:
        # Create COP network
        context = hou.node(copnet_path.rsplit("/", 1)[0])
        parent = context.createNode("copnet")
        parent.setName(copnet_path.rsplit("/", 1)[1])

    # Build noise generator
    noise = parent.createNode("fractal_noise")
    noise.parm("freq").set(freq)

    outputs = {}
    for channel in channels:
        if channel == "albedo":
            cc = parent.createNode("color_correct")
            cc.setInput(0, noise)
            cc.setName("OUT_albedo")
            outputs["albedo"] = cc.path()
        elif channel == "roughness":
            thresh = parent.createNode("threshold")
            thresh.setInput(0, noise)
            thresh.setName("OUT_roughness")
            outputs["roughness"] = thresh.path()

    parent.layoutChildren()
    return outputs
```
