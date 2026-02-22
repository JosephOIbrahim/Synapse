# COPs (Compositing) Node Reference

## Triggers
cops, compositing, cop network, img context, file cop, grade, blur, colorcorrect, over, composite, pixel data, image planes, rop_comp, cop2net, channelcopy, shuffle, premultiply, tonemap, lut, defocus, sharpen, 2d compositing, image processing, comp network

## Context
COPs (Composite Operators) is Houdini's built-in 2D compositing context, located at `/img`. Use it to load rendered images, apply color correction, composite layers, and write output to disk — all scriptable via `hou.node("/img")`.

## Code

### Create a COP network and load an image

```python
import hou

# Get or create the /img context
img = hou.node("/img")

# Create a new cop2net (compositing network container)
cop_net = img.createNode("cop2net", "my_comp")

# Load a rendered EXR from disk
file_cop = cop_net.createNode("file", "beauty_pass")
file_cop.parm("filename1").set("D:/renders/beauty.$F4.exr")

# Enable linearize if loading sRGB source (e.g., JPEG reference)
file_cop.parm("linearize").set(1)

# Override resolution if needed (0 = use file resolution)
file_cop.parm("overridesize").set(0)

# Layout the network cleanly
cop_net.layoutChildren()
```

### Load multiple render passes and composite them

```python
import hou

cop_net = hou.node("/img/my_comp")

# Load diffuse pass
diffuse = cop_net.createNode("file", "diffuse")
diffuse.parm("filename1").set("D:/renders/diffuse.$F4.exr")

# Load specular pass
specular = cop_net.createNode("file", "specular")
specular.parm("filename1").set("D:/renders/specular.$F4.exr")

# Load emission pass
emission = cop_net.createNode("file", "emission")
emission.parm("filename1").set("D:/renders/emission.$F4.exr")

# Add diffuse + specular (additive blend)
add1 = cop_net.createNode("add", "add_diff_spec")
add1.setInput(0, diffuse)
add1.setInput(1, specular)

# Add emission on top
add2 = cop_net.createNode("add", "add_emission")
add2.setInput(0, add1)
add2.setInput(1, emission)

cop_net.layoutChildren()
```

### Alpha composite (A over B)

```python
import hou

cop_net = hou.node("/img/my_comp")

# Load foreground element (must have alpha)
fg = cop_net.createNode("file", "foreground")
fg.parm("filename1").set("D:/renders/fg_element.$F4.exr")

# Load background plate
bg = cop_net.createNode("file", "background")
bg.parm("filename1").set("D:/renders/bg_plate.$F4.exr")

# Over composite: input 0 = A (foreground), input 1 = B (background)
over = cop_net.createNode("over", "composite_over")
over.setInput(0, fg)
over.setInput(1, bg)

cop_net.layoutChildren()
```

### Color grading with colorcorrect and grade

```python
import hou

cop_net = hou.node("/img/my_comp")
beauty = cop_net.createNode("file", "beauty")
beauty.parm("filename1").set("D:/renders/beauty.$F4.exr")

# Color correct: gamma, gain, offset per channel
cc = cop_net.createNode("colorcorrect", "cc_beauty")
cc.setInput(0, beauty)

cc.parm("gamma").set(1.0)          # Overall gamma
cc.parm("gammar").set(1.0)         # Red channel gamma
cc.parm("gammag").set(1.0)         # Green channel gamma
cc.parm("gammab").set(1.0)         # Blue channel gamma
cc.parm("gain").set(1.1)           # Overall gain (slight brighten)
cc.parm("saturation").set(1.15)    # Boost saturation slightly

# Film grade on top: lift/gamma/gain
grade = cop_net.createNode("grade", "film_grade")
grade.setInput(0, cc)

grade.parm("blackpoint").set(0.0)      # Black point (lift origin)
grade.parm("whitepoint").set(1.0)      # White point
grade.parm("lift").set(0.02)           # Lift shadows slightly
grade.parm("gamma").set(1.05)          # Midtone gamma
grade.parm("gain").set(0.95)           # Gain (highlight rolloff)
grade.parm("clampblack").set(1)        # Clamp result at 0

cop_net.layoutChildren()
```

### Blur and sharpen filters

```python
import hou

cop_net = hou.node("/img/my_comp")
src = cop_net.createNode("file", "source")
src.parm("filename1").set("D:/renders/beauty.$F4.exr")

# Gaussian blur (e.g., for glow source extraction)
blur = cop_net.createNode("blur", "glow_blur")
blur.setInput(0, src)
blur.parm("sizex").set(20.0)       # Blur radius X in pixels
blur.parm("sizey").set(20.0)       # Blur radius Y in pixels
# blur type: 0=Gaussian, 1=Box, 2=Sharpen
blur.parm("filtertype").set(0)

# Sharpen the original separately
sharpen = cop_net.createNode("sharpen", "beauty_sharpen")
sharpen.setInput(0, src)
sharpen.parm("sharpenamt").set(0.3)   # Sharpen amount (0-1 typical range)

cop_net.layoutChildren()
```

### Defocus (lens blur / bokeh)

```python
import hou

cop_net = hou.node("/img/my_comp")
beauty = cop_net.createNode("file", "beauty")
beauty.parm("filename1").set("D:/renders/beauty.$F4.exr")

# Load depth pass (Z channel) for depth-of-field
depth = cop_net.createNode("file", "depth_pass")
depth.parm("filename1").set("D:/renders/depth.$F4.exr")

# Apply defocus using depth data
defocus = cop_net.createNode("defocus", "dof_blur")
defocus.setInput(0, beauty)   # input 0 = image to blur
defocus.setInput(1, depth)    # input 1 = depth (Z) channel

defocus.parm("fstop").set(4.0)          # F-stop (larger = shallower DOF)
defocus.parm("focaldist").set(5.0)      # Focal distance in scene units
defocus.parm("maxblur").set(30.0)       # Maximum blur radius in pixels
defocus.parm("quality").set(3)          # Quality level (higher = slower)
```

### Channel operations: copy, shuffle, premultiply

```python
import hou

cop_net = hou.node("/img/my_comp")
src = cop_net.createNode("file", "beauty")
src.parm("filename1").set("D:/renders/beauty.$F4.exr")

# Premultiply alpha (multiply RGB by alpha before compositing)
premult = cop_net.createNode("premultiply", "premult_beauty")
premult.setInput(0, src)
# operation: 0=premultiply, 1=unpremultiply
premult.parm("operation").set(0)

# Channel copy: copy luminance from one plane to another channel
chan_copy = cop_net.createNode("channelcopy", "copy_lum_to_alpha")
chan_copy.setInput(0, src)   # destination
chan_copy.setInput(1, src)   # source
# Set source plane and channel to copy from
chan_copy.parm("srcplane").set("C")    # Source image plane
chan_copy.parm("srcchan").set("r")     # Use red channel as source
chan_copy.parm("dstplane").set("C")    # Destination image plane
chan_copy.parm("dstchan").set("a")     # Write into alpha channel

# Shuffle: rearrange RGBA channels
shuffle = cop_net.createNode("shuffle", "swap_rg")
shuffle.setInput(0, src)
# Map output R from input G, output G from input R (swap red/green)
shuffle.parm("rplane").set("C")
shuffle.parm("rchan").set("g")    # Output R comes from input G
shuffle.parm("gplane").set("C")
shuffle.parm("gchan").set("r")    # Output G comes from input R

cop_net.layoutChildren()
```

### Transform: translate, rotate, scale

```python
import hou

cop_net = hou.node("/img/my_comp")
src = cop_net.createNode("file", "element")
src.parm("filename1").set("D:/renders/element.$F4.exr")

# 2D transform
xform = cop_net.createNode("xform", "position_element")
xform.setInput(0, src)

xform.parm("tx").set(0.25)         # Translate X (fraction of image width)
xform.parm("ty").set(-0.1)         # Translate Y (fraction of image height)
xform.parm("rotate").set(5.0)      # Rotation in degrees
xform.parm("sx").set(0.9)          # Scale X
xform.parm("sy").set(0.9)          # Scale Y
# Filter: 0=Nearest, 1=Bilinear, 2=Bicubic
xform.parm("filter").set(2)

# Crop to specific region
crop = cop_net.createNode("crop", "crop_safe_area")
crop.setInput(0, src)
crop.parm("cropx1").set(0.05)      # Left crop (fraction)
crop.parm("cropx2").set(0.95)      # Right crop (fraction)
crop.parm("cropy1").set(0.05)      # Bottom crop
crop.parm("cropy2").set(0.95)      # Top crop
```

### Scale / resize resolution

```python
import hou

cop_net = hou.node("/img/my_comp")
src = cop_net.createNode("file", "hires")
src.parm("filename1").set("D:/renders/beauty_4k.$F4.exr")

# Scale node resizes the image
scale = cop_net.createNode("scale", "downres_to_hd")
scale.setInput(0, src)
# scalemethod: 0=Fit, 1=Specific Size, 2=Scale by Factor
scale.parm("scalemethod").set(1)
scale.parm("sizex").set(1920)
scale.parm("sizey").set(1080)
# Filter: 0=Nearest, 1=Bilinear, 2=Area average (best for downscaling)
scale.parm("filter").set(2)
```

### Build a complete comp pipeline programmatically

```python
import hou

def build_comp_pipeline(render_dir, output_path, frame_range=(1001, 1100)):
    """Build a full beauty comp pipeline: load passes -> grade -> output."""
    img = hou.node("/img")
    cop_net = img.createNode("cop2net", "auto_comp")

    # -- Load passes --
    beauty = cop_net.createNode("file", "beauty")
    beauty.parm("filename1").set(f"{render_dir}/beauty.$F4.exr")

    specular = cop_net.createNode("file", "specular")
    specular.parm("filename1").set(f"{render_dir}/specular.$F4.exr")

    sss = cop_net.createNode("file", "sss")
    sss.parm("filename1").set(f"{render_dir}/sss.$F4.exr")

    # -- Combine passes (additive) --
    add_spec = cop_net.createNode("add", "add_specular")
    add_spec.setInput(0, beauty)
    add_spec.setInput(1, specular)

    add_sss = cop_net.createNode("add", "add_sss")
    add_sss.setInput(0, add_spec)
    add_sss.setInput(1, sss)

    # -- Color grade --
    cc = cop_net.createNode("colorcorrect", "color_grade")
    cc.setInput(0, add_sss)
    cc.parm("gamma").set(1.0)
    cc.parm("gain").set(1.05)
    cc.parm("saturation").set(1.1)

    grade = cop_net.createNode("grade", "film_grade")
    grade.setInput(0, cc)
    grade.parm("lift").set(0.01)
    grade.parm("gamma").set(1.02)
    grade.parm("gain").set(0.98)

    # -- Output null (mark final result) --
    out = cop_net.createNode("null", "OUT")
    out.setInput(0, grade)
    out.setDisplayFlag(True)

    # -- ROP for writing to disk --
    rop = cop_net.createNode("rop_comp", "write_comp")
    rop.setInput(0, out)
    rop.parm("coppath").set(out.path())
    rop.parm("copoutput").set(output_path)
    rop.parm("trange").set(1)                        # 1 = frame range
    rop.parm("f1").set(frame_range[0])
    rop.parm("f2").set(frame_range[1])
    rop.parm("f3").set(1)                            # step

    cop_net.layoutChildren()
    return rop

# Usage
rop = build_comp_pipeline(
    render_dir="D:/renders/shot_010",
    output_path="D:/comp/shot_010/comp.$F4.exr"
)
```

### Export composited image to disk (rop_comp)

```python
import hou

cop_net = hou.node("/img/my_comp")
out_null = hou.node("/img/my_comp/OUT")   # final node in the chain

# Create ROP inside the cop network
rop = cop_net.createNode("rop_comp", "write_output")
rop.setInput(0, out_null)

# Point the rop at the final cop node
rop.parm("coppath").set(out_null.path())

# Output file path (use $F4 for 4-digit frame padding)
rop.parm("copoutput").set("D:/comp/output/comp.$F4.exr")

# Frame range
rop.parm("trange").set(1)        # 0=current frame only, 1=range
rop.parm("f1").set(1001)
rop.parm("f2").set(1100)
rop.parm("f3").set(1)            # frame step

# Output format options (for non-EXR formats)
# rop.parm("filetype").set("jpeg")
# rop.parm("quality").set(95)

# Render (blocking)
rop.render()
print(f"Comp written to: {rop.parm('copoutput').eval()}")
```

### Render single current frame from cop network

```python
import hou

# Render just the current frame from an existing rop_comp node
rop = hou.node("/img/my_comp/write_output")

# Override to current frame only
rop.parm("trange").set(0)   # 0 = current frame
rop.render()

# Or render a specific frame range without changing the node
rop.render(frame_range=(1001, 1010, 1))   # (start, end, step)
```

### Read pixel data from a COP node in Python

```python
import hou
import numpy as np   # optional — for array manipulation

cop_net = hou.node("/img/my_comp")
beauty = cop_net.createNode("file", "beauty")
beauty.parm("filename1").set("D:/renders/beauty.1001.exr")

# Get image at specific frame
frame = 1001
pixels = beauty.allPixels(frame)      # returns flat list: [R,G,B,A, R,G,B,A, ...]

# Image dimensions
xres, yres = beauty.xRes(), beauty.yRes()
print(f"Resolution: {xres}x{yres}, pixel count: {xres*yres}, data len: {len(pixels)}")

# Convert to numpy array (requires numpy)
arr = np.array(pixels, dtype=np.float32).reshape(yres, xres, 4)
# arr[:,:,0] = R, arr[:,:,1] = G, arr[:,:,2] = B, arr[:,:,3] = A

# Sample a single pixel (row=y, col=x from bottom-left origin)
# Houdini COPs use bottom-left origin (Y=0 is bottom)
pixel_x, pixel_y = 960, 540   # center of 1920x1080
flat_idx = (pixel_y * xres + pixel_x) * 4
r = pixels[flat_idx]
g = pixels[flat_idx + 1]
b = pixels[flat_idx + 2]
a = pixels[flat_idx + 3]
print(f"Pixel ({pixel_x},{pixel_y}): R={r:.4f} G={g:.4f} B={b:.4f} A={a:.4f}")
```

### Write pixel data back into a COP node

```python
import hou

cop_net = hou.node("/img/my_comp")

# Create a constant node to paint into programmatically
const = cop_net.createNode("color", "programmatic_fill")
const.parm("colorr").set(0.5)
const.parm("colorg").set(0.2)
const.parm("colorb").set(0.8)
const.parm("colora").set(1.0)

# For writing arbitrary pixel arrays to a node use setPixels():
# node.setPixels(pixel_list, frame)
# pixel_list must be flat RGBA float list of length xres*yres*4
xres, yres = 256, 256
flat_pixels = []
for y in range(yres):
    for x in range(xres):
        # Gradient: red increases left-right, green increases bottom-top
        r = x / (xres - 1)
        g = y / (yres - 1)
        b = 0.5
        a = 1.0
        flat_pixels.extend([r, g, b, a])

const.setPixels(flat_pixels, frame=1001)
```

### Introspect a COP network: list nodes and their types

```python
import hou

cop_net = hou.node("/img/my_comp")

# List all nodes in the comp network
for node in cop_net.children():
    node_type = node.type().name()
    inputs = [i.name() if i else "None" for i in node.inputs()]
    print(f"  {node.name():<25} type={node_type:<20} inputs={inputs}")

# Find all file COPs (useful for batch-updating paths)
file_nodes = [n for n in cop_net.children() if n.type().name() == "file"]
for fn in file_nodes:
    path = fn.parm("filename1").eval()
    print(f"  File COP '{fn.name()}': {path}")

# Find the display flag node (the final output)
display_node = cop_net.displayNode()
print(f"Display node: {display_node.name() if display_node else 'None'}")
```

### Replace render pass paths in bulk (batch re-path)

```python
import hou

def repath_comp(cop_net_path, old_dir, new_dir):
    """Replace render directory in all file COPs in a comp network."""
    cop_net = hou.node(cop_net_path)
    if cop_net is None:
        raise ValueError(f"COP network not found: {cop_net_path}")

    updated = []
    for node in cop_net.children():
        if node.type().name() != "file":
            continue
        parm = node.parm("filename1")
        current = parm.rawValue()   # rawValue preserves $F4 expressions
        if old_dir in current:
            new_path = current.replace(old_dir, new_dir)
            parm.set(new_path)
            updated.append((node.name(), current, new_path))

    for name, old, new in updated:
        print(f"  {name}: {old} -> {new}")
    print(f"Updated {len(updated)} file COP(s).")

# Usage
repath_comp(
    cop_net_path="/img/my_comp",
    old_dir="D:/renders/v001",
    new_dir="D:/renders/v002"
)
```

### Use cop2net SOP inline for texture baking

```python
import hou

# cop2net can be embedded inside a SOP network for procedural texture baking
geo = hou.node("/obj/geo1")
if geo is None:
    obj = hou.node("/obj")
    geo = obj.createNode("geo", "tex_bake_geo")

# Create a cop2net SOP inside the geometry network
cop2net_sop = geo.createNode("cop2net", "inline_comp")

# Inside the cop2net SOP, create COP nodes normally
noise_cop = cop2net_sop.createNode("noise", "proc_noise")
noise_cop.parm("frequencyx").set(8.0)
noise_cop.parm("frequencyy").set(8.0)
noise_cop.parm("amplitude").set(1.0)
# type: 0=Perlin, 1=Sparse, 2=Flow, 3=Alligator
noise_cop.parm("type").set(0)

cc_cop = cop2net_sop.createNode("colorcorrect", "cc_noise")
cc_cop.setInput(0, noise_cop)
cc_cop.parm("gamma").set(0.7)

out_cop = cop2net_sop.createNode("null", "OUT")
out_cop.setInput(0, cc_cop)
out_cop.setDisplayFlag(True)

# Reference in a material: use cop:/ path scheme
# e.g., parm("basecolor_texture").set("op:/img/inline_comp/OUT")
cop2net_sop.layoutChildren()
print(f"Inline comp output path: op:{out_cop.path()}")
```

## Common Mistakes

```python
# WRONG: using setDisplayFlag on cop_net itself instead of a child node
cop_net.setDisplayFlag(True)   # error — networks don't have display flags

# CORRECT: set display flag on the terminal COP node
out_null = cop_net.node("OUT")
out_null.setDisplayFlag(True)

# WRONG: allPixels() on a node that hasn't been cooked yet — returns empty
beauty = cop_net.createNode("file", "test")
beauty.parm("filename1").set("D:/renders/beauty.1001.exr")
pixels = beauty.allPixels()    # returns [] if not at the right frame context

# CORRECT: pass explicit frame number
pixels = beauty.allPixels(1001)

# WRONG: rop_comp coppath pointing to the ROP itself (infinite loop)
rop.parm("coppath").set(rop.path())

# CORRECT: point coppath at the upstream null or final grade node
rop.parm("coppath").set(out_null.path())

# WRONG: using absolute pixel coordinates without checking image bounds
xres, yres = node.xRes(), node.yRes()
pixel_x, pixel_y = 2000, 1200   # may exceed actual resolution
# CORRECT: clamp or validate first
pixel_x = min(pixel_x, xres - 1)
pixel_y = min(pixel_y, yres - 1)

# WRONG: forgetting that COP Y-origin is bottom-left (not top-left like most image libs)
# A pixel at the "top" of a 1080-tall image is y=1079, not y=0

# WRONG: setting trange=1 but forgetting to set f1/f2 (renders at defaults)
rop.parm("trange").set(1)
rop.render()   # uses whatever f1/f2 are currently set — check them first

# CORRECT: always explicitly set frame range before rendering
rop.parm("f1").set(1001)
rop.parm("f2").set(1100)
rop.parm("f3").set(1)
rop.render()

# WRONG: rawValue() vs eval() confusion for file paths with $F4
parm = file_cop.parm("filename1")
evaluated = parm.eval()    # expands $F4 to current frame number — good for preview
raw = parm.rawValue()      # returns literal string with $F4 — use this for repath

# WRONG: creating nodes inside /img directly (not inside a cop2net)
hou.node("/img").createNode("file", "beauty")   # fails — /img is a manager, not a cop2net

# CORRECT: always create nodes inside a cop2net
cop_net = hou.node("/img").createNode("cop2net", "comp")
file_node = cop_net.createNode("file", "beauty")
```
