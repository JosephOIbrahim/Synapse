# Karma AOV and Render Pass Setup

## Triggers
aov, render pass, extra image plane, cryptomatte, beauty pass, diffuse pass,
specular pass, denoising, deep output, light group, render variable, aov setup

## Context
AOV (Arbitrary Output Variable) setup for Karma rendering in Houdini 21 Solaris.
Covers adding AOVs via RenderVar prims, configuring Cryptomatte, denoising passes,
light groups, and compositing rebuild formulas.

## Code

```python
# Add AOVs to Karma render via Python
import hou
from pxr import UsdRender, Sdf

def add_aov_to_render(stage_node_path, aov_name, aov_type="color3f", source_name=None):
    """Add a RenderVar (AOV) to the USD stage."""
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'stage'):
        print(f"Node not found or has no stage: {stage_node_path}")
        return

    stage = node.editableStage()
    source = source_name or aov_name

    # Create RenderVar prim under /Render/Vars
    var_path = f"/Render/Vars/{aov_name}"
    var_prim = UsdRender.Var.Define(stage, var_path)
    var_prim.GetSourceNameAttr().Set(source)
    var_prim.GetDataTypeAttr().Set(aov_type)

    print(f"Added AOV: {aov_name} (source={source}, type={aov_type})")
    return var_path

# Common AOV definitions
KARMA_AOVS = {
    "direct_diffuse":    {"type": "color3f", "source": "direct_diffuse"},
    "indirect_diffuse":  {"type": "color3f", "source": "indirect_diffuse"},
    "direct_specular":   {"type": "color3f", "source": "direct_specular"},
    "indirect_specular": {"type": "color3f", "source": "indirect_specular"},
    "direct_emission":   {"type": "color3f", "source": "direct_emission"},
    "sss":               {"type": "color3f", "source": "sss"},
    "albedo":            {"type": "color3f", "source": "albedo"},
    "N":                 {"type": "normal3f", "source": "N"},
    "P":                 {"type": "point3f", "source": "P"},
    "Z":                 {"type": "float",   "source": "depth"},
    "motionvector":      {"type": "float2",  "source": "motionvector"},
    "crypto_material":   {"type": "float",   "source": "crypto_material"},
    "crypto_object":     {"type": "float",   "source": "crypto_object"},
    "crypto_asset":      {"type": "float",   "source": "crypto_asset"},
}
```

```python
# Set up standard AOV suite for production render
import hou

def setup_production_aovs(karma_node_path):
    """Configure standard AOV suite on a Karma render properties node."""
    node = hou.node(karma_node_path)
    if not node:
        print(f"Karma node not found: {karma_node_path}")
        return

    # Karma render properties -- add extra image planes
    # Each plane is a multiparm entry
    production_aovs = [
        ("direct_diffuse", "color3f"),
        ("indirect_diffuse", "color3f"),
        ("direct_specular", "color3f"),
        ("indirect_specular", "color3f"),
        ("direct_emission", "color3f"),
        ("sss", "color3f"),
        ("albedo", "color3f"),
        ("N", "normal3f"),
        ("P", "point3f"),
        ("Z", "float"),
        ("crypto_object", "float"),
        ("crypto_material", "float"),
    ]

    count = len(production_aovs)
    if node.parm("ar_aovs"):
        node.parm("ar_aovs").set(count)
        for i, (name, dtype) in enumerate(production_aovs, 1):
            name_parm = node.parm(f"ar_aov_name{i}")
            if name_parm:
                name_parm.set(name)
            type_parm = node.parm(f"ar_aov_type{i}")
            if type_parm:
                type_parm.set(dtype)
        print(f"Configured {count} AOVs for production")

setup_production_aovs("/stage/karmarenderproperties1")
```

```python
# Configure Cryptomatte for compositing
import hou

def setup_cryptomatte(karma_props_path):
    """Add Cryptomatte AOVs for object and material ID mattes."""
    node = hou.node(karma_props_path)
    if not node:
        return

    # Cryptomatte generates ID mattes for comp selection:
    #   crypto_object  -- select by object name
    #   crypto_material -- select by material name
    #   crypto_asset   -- select by asset name
    #
    # Usage in Nuke: add Cryptomatte node, click on objects to isolate them
    # No manual matte creation needed

    crypto_aovs = ["crypto_object", "crypto_material"]
    for aov_name in crypto_aovs:
        print(f"Cryptomatte AOV: {aov_name}")
        # Added via the multiparm or RenderVar setup above

    print("Cryptomatte ready -- use Cryptomatte node in Nuke to select objects")
```

```python
# Configure denoising AOVs
import hou

def setup_denoising(karma_props_path, denoiser="oidn"):
    """Configure denoising for Karma with auxiliary AOVs."""
    node = hou.node(karma_props_path)
    if not node:
        return

    # Denoiser options:
    #   "oidn"   -- Intel Open Image Denoise (CPU, frame-by-frame)
    #   "optix"  -- NVIDIA OptiX (GPU, frame-by-frame)
    #
    # Both are frame-by-frame in Karma (no temporal denoising)
    # For animation: use SAME denoiser across entire sequence

    # Auxiliary AOVs improve denoiser quality:
    denoise_aovs = [
        "denoise_albedo",   # Albedo guide for edge preservation
        "denoise_normal",   # Normal guide for surface detail
    ]

    # Best practices:
    #   - Denoise beauty pass ONLY, not utility AOVs (depth, normal, crypto)
    #   - Higher base samples (64-128) + denoise > low samples (16) + heavy denoise
    #   - Consistent denoiser across entire sequence

    print(f"Denoiser: {denoiser}")
    print(f"Auxiliary AOVs: {denoise_aovs}")
    print("Rule: denoise beauty only, NOT utility AOVs")

setup_denoising("/stage/karmarenderproperties1", denoiser="oidn")
```

```python
# Light group AOVs
import hou
from pxr import UsdLux

def setup_light_groups(stage_node_path):
    """Tag lights with groups for per-light AOV output."""
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'stage'):
        return

    stage = node.stage()

    # Tag lights with lightGroup attribute
    # AOVs auto-generated as {aov}_{lightgroup}
    # Example: direct_diffuse_key, direct_diffuse_fill

    groups = {}
    for prim in stage.Traverse():
        if prim.IsA(UsdLux.BoundableLightBase) or prim.IsA(UsdLux.NonboundableLightBase):
            path = str(prim.GetPath())
            name = prim.GetName()
            # Auto-assign group based on light name
            if "key" in name.lower():
                groups[path] = "key"
            elif "fill" in name.lower():
                groups[path] = "fill"
            elif "rim" in name.lower() or "back" in name.lower():
                groups[path] = "rim"
            elif "dome" in name.lower() or "env" in name.lower():
                groups[path] = "env"
            else:
                groups[path] = "other"

    for path, group in groups.items():
        print(f"Light group: {path} -> {group}")

    return groups

setup_light_groups("/stage/merge1")
```

```python
# Compositing: rebuild beauty from AOVs
# In Nuke, connect AOV layers to rebuild:
BEAUTY_REBUILD = """
# Nuke node graph (pseudocode):
# beauty = direct_diffuse + indirect_diffuse
#        + direct_specular + indirect_specular
#        + direct_emission + sss

# With light groups:
# beauty = (direct_diffuse_key + direct_diffuse_fill + direct_diffuse_rim)
#        + (indirect_diffuse)
#        + (direct_specular_key + direct_specular_fill)
#        + (indirect_specular)
#        + (direct_emission)
#        + (sss)

# Per-light adjustment in comp:
# Multiply each light group by a grade node
# Example: reduce fill by 50%:
#   direct_diffuse_fill * 0.5
"""
print(BEAUTY_REBUILD)
```

```python
# Deep output configuration
import hou

def configure_deep_output(karma_props_path, output_path="$HIP/render/deep/shot.$F4.exr"):
    """Enable deep compositing output for depth-correct comp."""
    node = hou.node(karma_props_path)
    if not node:
        return

    # Deep compositing preserves per-sample depth information
    # Enables depth-correct compositing in Nuke
    # Requirements:
    #   - Output format must be .exr
    #   - Enable "Deep Output" in render properties
    #   - File size is significantly larger than regular EXR

    if node.parm("vm_deepresolver"):
        node.parm("vm_deepresolver").set("camera")  # camera-space deep
    if node.parm("vm_deepimage"):
        node.parm("vm_deepimage").set(output_path)

    print(f"Deep output: {output_path}")

configure_deep_output("/stage/karmarenderproperties1")
```

```python
# Query existing AOVs from USD stage
import hou
from pxr import UsdRender

def list_render_vars(stage_node_path):
    """List all RenderVar (AOV) prims on the stage."""
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'stage'):
        return

    stage = node.stage()
    vars_found = []
    for prim in stage.Traverse():
        if prim.IsA(UsdRender.Var):
            source = prim.GetAttribute("sourceName")
            dtype = prim.GetAttribute("dataType")
            vars_found.append({
                "path": str(prim.GetPath()),
                "source": source.Get() if source else "",
                "type": dtype.Get() if dtype else "",
            })

    print(f"Found {len(vars_found)} RenderVar(s):")
    for v in vars_found:
        print(f"  {v['path']}: source={v['source']}, type={v['type']}")

    return vars_found

list_render_vars("/stage/karmarendersettings1")
```

## Expected Scene Graph
```
/Render/
  RenderSettings/
    camera -> /cameras/render_cam
    resolution = (1920, 1080)
  Products/
    renderproduct1/
      productName = "$HIP/render/shot.$F4.exr"
  Vars/
    beauty         (source=C, type=color3f)
    direct_diffuse (source=direct_diffuse, type=color3f)
    N              (source=N, type=normal3f)
    crypto_object  (source=crypto_object, type=float)
```

## Common Mistakes
- Denoising utility AOVs (depth, normal, cryptomatte) -- only denoise beauty
- Switching denoiser mid-sequence (OIDN vs OptiX produce different noise patterns)
- Not providing denoise_albedo and denoise_normal auxiliary AOVs
- Forgetting that Cryptomatte AOVs need special handling in comp (use Cryptomatte node)
- Deep output without .exr format -- deep data requires EXR container
- Low base samples (16-32) with heavy denoiser -- produces smearing in animation
