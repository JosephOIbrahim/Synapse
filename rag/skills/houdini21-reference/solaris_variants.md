# USD Variants in Solaris

## Triggers
variant, variant set, set variant, variant lop, switchable, option, toggle variant,
variant selection, add variant, variant block, variant begin, variant end, variant graft,
base variant, alternate variant, variant naming, clean variant, variant chain,
variant asset, variant dcc, usdview variant, maya variant, variant precedence,
value clip variant, variant composition, variant vs reference, variant switching,
model variant, look variant, shading variant, lod variant, level of detail,
variant group, variant default, auto variant, variant python, variant opinion,
variant LIVRPS, variant strength, variant override, graft variant, variant block begin,
variant block end, variant configure, display variant, render variant, material variant,
geo variant, proxy variant, component builder variant, variant export, select variant,
variant menu, variant combo, addvariant, setvariant, variant prim, variant layer,
variant workflow, variant solaris, variant houdini, variant usd, variant karmavariant combo

## Context
USD variants let you author multiple alternate representations (LODs, shading looks,
geometry options) inside a single asset, switchable without file I/O. In Houdini 21
Solaris, the Add Variant LOP creates variant sets and the Set Variant LOP selects
them. Clean variant workflows use chained Graft LOPs to avoid redundant geometry
duplication.

## Code

### Basic Variant Set Creation with Add Variant LOP

```python
# Create a variant set with multiple variants using Add Variant Begin/End blocks
import hou

def create_variant_set(parent="/stage", variant_set_name="modelVariant",
                       prim_path="/asset", variant_names=None):
    """Create an Add Variant block with named variants.

    The Add Variant LOP works as a Begin/End pair. Each input between
    them becomes a separate variant. The first input is the base content
    that all variants share.

    Args:
        parent: Parent network path (typically /stage)
        variant_set_name: Name of the USD variant set
        prim_path: Prim path where the variant set is authored
        variant_names: List of variant names (e.g., ["base", "damaged", "destroyed"])
    """
    if variant_names is None:
        variant_names = ["base", "damaged", "destroyed"]

    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None, None

    # Create the Add Variant Begin node
    begin = stage.createNode("addvariant", f"variant_begin_{variant_set_name}")
    begin.parm("variantsetname").set(variant_set_name)
    begin.parm("primpath").set(prim_path)

    # Set the number of variants
    num_variants = len(variant_names)
    begin.parm("numvariants").set(num_variants)

    # Name each variant
    for i, name in enumerate(variant_names):
        begin.parm(f"variantname{i + 1}").set(name)

    # Create the Add Variant End node (collects all variant branches)
    end = stage.createNode("addvariant::2.0", f"variant_end_{variant_set_name}")

    begin.setDisplayFlag(False)
    end.setDisplayFlag(True)

    # Layout for readability
    begin.moveToGoodPosition()
    end.moveToGoodPosition()

    print(f"Created variant set '{variant_set_name}' with variants: {variant_names}")
    return begin, end


# Example: create a 3-variant model set
begin_node, end_node = create_variant_set(
    parent="/stage",
    variant_set_name="modelVariant",
    prim_path="/World/hero_asset",
    variant_names=["base", "damaged", "destroyed"]
)
```

### Set Variant LOP -- Selecting Active Variant

```python
# Select which variant is active using Set Variant LOP
import hou

def set_variant_selection(parent="/stage", prim_path="/World/hero_asset",
                          variant_set_name="modelVariant", variant_name="base"):
    """Create a Set Variant node to select the active variant.

    The Set Variant LOP sets the variant selection on a prim. This
    controls which variant is visible in the viewport and at render time.
    Multiple variant sets can be selected on a single node.

    Args:
        parent: Parent network path
        prim_path: Prim path that has the variant set
        variant_set_name: Name of the variant set to select from
        variant_name: Which variant to activate
    """
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    sv = stage.createNode("setvariant", f"set_{variant_set_name}_{variant_name}")

    # Set the prim path pattern -- can use wildcards for bulk selection
    sv.parm("primpath").set(prim_path)

    # First variant set selection (1-indexed parms)
    sv.parm("variantset1").set(variant_set_name)
    sv.parm("variantname1").set(variant_name)

    sv.moveToGoodPosition()
    print(f"Set variant '{variant_set_name}' = '{variant_name}' on {prim_path}")
    return sv


def set_multiple_variant_selections(parent="/stage", prim_path="/World/hero_asset",
                                    selections=None):
    """Set multiple variant sets on a single Set Variant node.

    Args:
        selections: dict of {variant_set_name: variant_name}
                    e.g., {"modelVariant": "damaged", "look": "dirty"}
    """
    if selections is None:
        selections = {"modelVariant": "base", "look": "clean"}

    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    sv = stage.createNode("setvariant", "set_multi_variant")
    sv.parm("primpath").set(prim_path)

    # Set the number of variant set selections
    sv.parm("numvariantsets").set(len(selections))

    for i, (vs_name, v_name) in enumerate(sorted(selections.items()), start=1):
        sv.parm(f"variantset{i}").set(vs_name)
        sv.parm(f"variantname{i}").set(v_name)

    sv.moveToGoodPosition()
    print(f"Set {len(selections)} variant selections on {prim_path}: {selections}")
    return sv


# Example: select the "damaged" model variant
set_variant_selection(
    parent="/stage",
    prim_path="/World/hero_asset",
    variant_set_name="modelVariant",
    variant_name="damaged"
)

# Example: set model + look variants together
set_multiple_variant_selections(
    parent="/stage",
    prim_path="/World/hero_asset",
    selections={"modelVariant": "damaged", "look": "dirty"}
)
```

### Clean Variant Setup via Chained Grafts

```python
# Clean variant workflow using Graft LOPs to avoid geometry duplication
import hou

def create_clean_variant_workflow(parent="/stage", prim_path="/World/hero_asset",
                                  variant_set_name="look"):
    """Build a clean variant set using Graft LOPs for minimal file size.

    Problem: Naive variant setup duplicates ALL geometry for each variant,
    even when only materials differ. A 100MB asset with 3 looks becomes 300MB.

    Solution: Use Graft LOPs to layer only the DELTA (what changes) into
    each variant. Shared geometry is authored once at the base level.
    Only material assignments (or other differences) are stored per variant.

    Network topology:
        base_geo --> addvariant_begin
                         |-- graft_clean (clean materials)
                         |-- graft_dirty (dirty materials)
                         |-- graft_damaged (damaged materials)
                     addvariant_end --> setvariant
    """
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    # Step 1: Create the base geometry (shared across all variants)
    # In production this would be a Reference or SOP Import
    base_geo = stage.createNode("sopimport", "base_geometry")
    base_geo.parm("soppath").set("/obj/hero_geo/OUT")

    # Step 2: Create material libraries for each look
    matlib_clean = stage.createNode("materiallibrary", "matlib_clean")
    matlib_dirty = stage.createNode("materiallibrary", "matlib_dirty")
    matlib_damaged = stage.createNode("materiallibrary", "matlib_damaged")

    # Step 3: Create Graft nodes -- each grafts ONLY the material delta
    # Graft merges a branch into the main stage at a specific prim path
    graft_clean = stage.createNode("graft", "graft_look_clean")
    graft_clean.parm("destpath").set(prim_path)
    graft_clean.setInput(0, base_geo)       # Main stage
    graft_clean.setInput(1, matlib_clean)    # Delta to graft in

    graft_dirty = stage.createNode("graft", "graft_look_dirty")
    graft_dirty.parm("destpath").set(prim_path)
    graft_dirty.setInput(0, base_geo)
    graft_dirty.setInput(1, matlib_dirty)

    graft_damaged = stage.createNode("graft", "graft_look_damaged")
    graft_damaged.parm("destpath").set(prim_path)
    graft_damaged.setInput(0, base_geo)
    graft_damaged.setInput(1, matlib_damaged)

    # Step 4: Wire grafts into Add Variant block
    variant_begin = stage.createNode("addvariant", f"variant_begin_{variant_set_name}")
    variant_begin.parm("variantsetname").set(variant_set_name)
    variant_begin.parm("primpath").set(prim_path)
    variant_begin.parm("numvariants").set(3)
    variant_begin.parm("variantname1").set("clean")
    variant_begin.parm("variantname2").set("dirty")
    variant_begin.parm("variantname3").set("damaged")

    # Each graft feeds one variant input
    variant_begin.setInput(0, graft_clean)
    variant_begin.setInput(1, graft_dirty)
    variant_begin.setInput(2, graft_damaged)

    # Step 5: End block collects all variants
    variant_end = stage.createNode("addvariant::2.0", f"variant_end_{variant_set_name}")
    variant_end.setInput(0, variant_begin)

    # Step 6: Default selection
    set_var = stage.createNode("setvariant", f"set_{variant_set_name}")
    set_var.parm("primpath").set(prim_path)
    set_var.parm("variantset1").set(variant_set_name)
    set_var.parm("variantname1").set("clean")
    set_var.setInput(0, variant_end)

    set_var.setDisplayFlag(True)
    set_var.setRenderFlag(True)

    stage.layoutChildren()
    print(f"Clean variant workflow: '{variant_set_name}' with grafted deltas")
    return set_var


create_clean_variant_workflow(
    parent="/stage",
    prim_path="/World/hero_asset",
    variant_set_name="look"
)
```

### LOD Variant Pattern

```python
# LOD (Level of Detail) variant set with viewport/render switching
import hou

def create_lod_variant_set(parent="/stage", prim_path="/World/hero_asset",
                           sop_paths=None):
    """Create an LOD variant set with high/medium/low/proxy levels.

    Each LOD variant references different SOP geometry at different
    polygon counts. Default is "high" for rendering, "proxy" for viewport.

    Args:
        parent: Parent network path
        prim_path: Prim path for the asset
        sop_paths: Dict mapping LOD name to SOP output path
    """
    if sop_paths is None:
        sop_paths = {
            "high":   "/obj/hero_geo/high_res_OUT",
            "medium": "/obj/hero_geo/medium_res_OUT",
            "low":    "/obj/hero_geo/low_res_OUT",
            "proxy":  "/obj/hero_geo/proxy_OUT",
        }

    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    lod_names = list(sop_paths.keys())

    # Create SOP Import for each LOD level
    sop_imports = {}
    for lod_name, sop_path in sop_paths.items():
        imp = stage.createNode("sopimport", f"import_{lod_name}")
        imp.parm("soppath").set(sop_path)
        imp.parm("pathprefix").set(prim_path)
        sop_imports[lod_name] = imp

    # Add Variant block
    var_begin = stage.createNode("addvariant", "variant_begin_lod")
    var_begin.parm("variantsetname").set("lod")
    var_begin.parm("primpath").set(prim_path)
    var_begin.parm("numvariants").set(len(lod_names))

    for i, name in enumerate(lod_names):
        var_begin.parm(f"variantname{i + 1}").set(name)
        var_begin.setInput(i, sop_imports[name])

    var_end = stage.createNode("addvariant::2.0", "variant_end_lod")
    var_end.setInput(0, var_begin)

    # Set default: "high" for rendering
    set_render = stage.createNode("setvariant", "set_lod_render")
    set_render.parm("primpath").set(prim_path)
    set_render.parm("variantset1").set("lod")
    set_render.parm("variantname1").set("high")
    set_render.setInput(0, var_end)

    set_render.setDisplayFlag(True)
    set_render.setRenderFlag(True)

    stage.layoutChildren()
    print(f"LOD variant set created: {lod_names}")
    print(f"  Default selection: 'high' (for rendering)")
    print(f"  Switch to 'proxy' for fast viewport navigation")
    return set_render


def configure_lod_purpose(parent="/stage", prim_path="/World/hero_asset"):
    """Configure USD purpose for automatic LOD switching.

    USD 'purpose' attribute controls viewport vs render visibility:
      - 'render'  : visible only at render time (high-res)
      - 'proxy'   : visible only in viewport (low-res stand-in)
      - 'guide'   : visible only when guides enabled
      - 'default' : always visible

    Use Configure Primitive LOP to set purpose per LOD variant.
    """
    stage = hou.node(parent)
    if not stage:
        return None

    # Configure high LOD for render purpose
    config_high = stage.createNode("configureprimitive", "config_lod_high")
    config_high.parm("primpath").set(f"{prim_path}/high_res")
    config_high.parm("purpose").set("render")

    # Configure proxy LOD for proxy purpose
    config_proxy = stage.createNode("configureprimitive", "config_lod_proxy")
    config_proxy.parm("primpath").set(f"{prim_path}/proxy")
    config_proxy.parm("purpose").set("proxy")

    stage.layoutChildren()
    print("Configured purpose: high=render, proxy=proxy")
    return config_high, config_proxy


# Example usage
create_lod_variant_set(parent="/stage", prim_path="/World/hero_asset")
```

### Material/Look Variant

```python
# Material/look variant: same geometry, different material assignments
import hou

def create_look_variants(parent="/stage", prim_path="/World/hero_asset",
                         geo_path="/World/hero_asset/geo/shape",
                         looks=None):
    """Create a 'look' variant set with different material assignments.

    Each look variant applies a different material to the same geometry.
    Only material assignments differ -- geometry is NOT duplicated.

    Args:
        parent: Parent network path
        prim_path: Prim where variant set is authored
        geo_path: Full USD path to the geometry shape prim
        looks: Dict mapping look name to material config
    """
    if looks is None:
        looks = {
            "hero":      {"base_color": (0.8, 0.2, 0.1), "roughness": 0.3},
            "weathered": {"base_color": (0.5, 0.4, 0.3), "roughness": 0.7},
            "chrome":    {"base_color": (0.9, 0.9, 0.9), "roughness": 0.05},
        }

    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    look_names = list(looks.keys())

    # Create a Material Library for each look
    matlibs = {}
    for look_name, config in looks.items():
        matlib = stage.createNode("materiallibrary", f"matlib_{look_name}")

        # Cook the matlib to initialize its internal network
        matlib.cook(force=True)

        # Create a MaterialX Standard Surface shader inside
        subnet = matlib.node("material1")
        if subnet is None:
            # If default material doesn't exist, the matlib needs configuration
            matlib.parm("materials").set(1)
            matlib.parm("matpathprefix").set(f"/materials/{look_name}")
            matlib.cook(force=True)
            subnet = matlib.node("material1")

        # Assign to geometry path
        matlib.parm("geopath1").set(geo_path)

        matlibs[look_name] = matlib

    # Create Add Variant block
    var_begin = stage.createNode("addvariant", "variant_begin_look")
    var_begin.parm("variantsetname").set("look")
    var_begin.parm("primpath").set(prim_path)
    var_begin.parm("numvariants").set(len(look_names))

    for i, name in enumerate(look_names):
        var_begin.parm(f"variantname{i + 1}").set(name)
        var_begin.setInput(i, matlibs[name])

    var_end = stage.createNode("addvariant::2.0", "variant_end_look")
    var_end.setInput(0, var_begin)

    # Default to "hero" look
    set_look = stage.createNode("setvariant", "set_look")
    set_look.parm("primpath").set(prim_path)
    set_look.parm("variantset1").set("look")
    set_look.parm("variantname1").set("hero")
    set_look.setInput(0, var_end)

    set_look.setDisplayFlag(True)
    set_look.setRenderFlag(True)

    stage.layoutChildren()
    print(f"Look variant set: {look_names}, default='hero'")
    return set_look


create_look_variants(
    parent="/stage",
    prim_path="/World/hero_asset",
    geo_path="/World/hero_asset/geo/shape",
    looks={
        "hero":      {"base_color": (0.8, 0.2, 0.1), "roughness": 0.3},
        "weathered": {"base_color": (0.5, 0.4, 0.3), "roughness": 0.7},
        "chrome":    {"base_color": (0.9, 0.9, 0.9), "roughness": 0.05},
    }
)
```

### Variant Selection in Python

```python
# Query and set variant selections programmatically via hou and USD API
import hou

def get_available_variants(stage_node_path, prim_path):
    """Query all variant sets and their options from a USD prim.

    Args:
        stage_node_path: Path to a LOP node to read the stage from
        prim_path: USD prim path to inspect

    Returns:
        Dict of {variant_set_name: [variant_names]}
    """
    node = hou.node(stage_node_path)
    if not node:
        print(f"Couldn't find node: {stage_node_path}")
        return {}

    # Get the USD stage from the LOP node
    stage = node.stage()
    if not stage:
        print("Couldn't get USD stage from node")
        return {}

    prim = stage.GetPrimAtPath(prim_path)
    if not prim or not prim.IsValid():
        print(f"Couldn't find prim: {prim_path}")
        return {}

    # Get all variant sets on this prim
    variant_sets = prim.GetVariantSets()
    result = {}

    for vs_name in variant_sets.GetNames():
        vs = variant_sets.GetVariantSet(vs_name)
        variant_names = vs.GetVariantNames()
        current = vs.GetVariantSelection()
        result[vs_name] = {
            "options": list(variant_names),
            "current": current,
        }
        print(f"  Variant set '{vs_name}': {list(variant_names)} (current: '{current}')")

    return result


def set_variant_via_parm(node_path, variant_set, variant_name):
    """Set a variant selection by modifying the Set Variant node's parameters.

    This is the preferred method -- it updates the Houdini node graph
    and triggers proper cook propagation.
    """
    node = hou.node(node_path)
    if not node:
        print(f"Couldn't find node: {node_path}")
        return

    # Find which parm index has this variant set
    num_sets = node.parm("numvariantsets")
    if num_sets:
        count = num_sets.eval()
    else:
        count = 1

    for i in range(1, count + 1):
        vs_parm = node.parm(f"variantset{i}")
        if vs_parm and vs_parm.eval() == variant_set:
            node.parm(f"variantname{i}").set(variant_name)
            print(f"Set {node_path}: '{variant_set}' = '{variant_name}'")
            return

    print(f"Variant set '{variant_set}' not found on {node_path}")


def query_variant_from_stage(lop_node_path, prim_path):
    """Read the current variant selection directly from the composed USD stage."""
    node = hou.node(lop_node_path)
    if not node:
        return None

    stage = node.stage()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        return None

    vsets = prim.GetVariantSets()
    selections = {}
    for name in vsets.GetNames():
        selections[name] = vsets.GetVariantSet(name).GetVariantSelection()

    return selections


# Example: query and switch variants
print("Available variants:")
variants = get_available_variants("/stage/set_look", "/World/hero_asset")

# Switch to "weathered" look
set_variant_via_parm("/stage/set_look", "look", "weathered")

# Read back from composed stage
current = query_variant_from_stage("/stage/set_look", "/World/hero_asset")
print(f"Current selections: {current}")
```

### Variant Precedence and Composition

```python
# Variant composition strength and LIVRPS ordering
import hou

# USD Composition Arc Strength Order (strongest to weakest):
#   L - Local (direct opinions on the prim)
#   I - Inherits (class-based sharing)
#   V - Variants (switchable alternates)  <-- VARIANTS ARE HERE
#   R - References (asset composition)
#   P - Payloads (deferred references)
#   S - Specializes (non-destructive extension)
#
# Key implications:
# 1. A variant opinion is WEAKER than a direct sublayer/local opinion
# 2. A variant opinion is STRONGER than a reference opinion
# 3. Multiple variant sets on the same prim are INDEPENDENT
# 4. Variant selections compose through the layer stack

def demonstrate_variant_strength(parent="/stage"):
    """Show how variant opinions interact with other composition arcs.

    If you sublayer a file that sets a variant selection, and then
    set a different selection locally, the LOCAL selection wins
    (Local > Variant in LIVRPS).
    """
    stage = hou.node(parent)
    if not stage:
        return

    # Sublayer brings in a USD file with variant selections baked in
    sub = stage.createNode("sublayer", "base_asset_layer")
    sub.parm("filepath1").set("D:/assets/hero.usd")
    # hero.usd has: variantSet "look" = "clean" authored inside

    # Local override via Set Variant -- this WINS over the sublayered selection
    # because local opinions are stronger than variant opinions in the
    # sublayered file
    override = stage.createNode("setvariant", "override_look")
    override.parm("primpath").set("/World/hero_asset")
    override.parm("variantset1").set("look")
    override.parm("variantname1").set("dirty")
    override.setInput(0, sub)

    override.setDisplayFlag(True)
    stage.layoutChildren()

    print("Variant strength demo:")
    print("  Sublayered file has look='clean'")
    print("  Local Set Variant overrides to look='dirty'")
    print("  Result: look='dirty' (local wins in LIVRPS)")
    return override


def variant_with_value_clips(parent="/stage", prim_path="/World/hero_asset"):
    """Value clips can override variant selections per frame.

    This is an advanced technique for animation where the variant
    selection changes over time (e.g., progressive damage states).
    Value clips are stronger than variant selections authored in
    the same layer.
    """
    stage = hou.node(parent)
    if not stage:
        return

    # Value clips are typically set up via USD API or dedicated LOPs
    # Here we show the concept with Python on the stage
    print("Value clip variant override pattern:")
    print("  Frame 1-24:  modelVariant = 'base'")
    print("  Frame 25-48: modelVariant = 'damaged'")
    print("  Frame 49+:   modelVariant = 'destroyed'")
    print("  Implemented via clipSets metadata on the prim")
    print("  Value clips override the static variant selection per-frame")


demonstrate_variant_strength(parent="/stage")
```

### Exporting Assets with Variants

```python
# Export USD assets preserving variant sets
import hou

def export_asset_with_variants(parent="/stage", output_path="D:/assets/hero_export.usd",
                               prim_path="/World/hero_asset"):
    """Export a USD asset with all variant sets intact.

    Two approaches:
    1. USD ROP -- exports the composed stage to a single .usd file
    2. Component Output LOP -- structured export with variant support

    Variant sets are preserved automatically in the exported file.
    """
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find parent node: {parent}")
        return None

    # Approach 1: USD ROP export (simple, single file)
    rop_net = hou.node("/out")
    if not rop_net:
        rop_net = hou.node("/").createNode("ropnet", "out")

    usd_rop = rop_net.createNode("usd", "export_with_variants")
    usd_rop.parm("loppath").set(f"{parent}/set_look")  # Last LOP in chain
    usd_rop.parm("savestyle").set("flattenstage")       # Or "separatelayers"
    usd_rop.parm("lopoutput").set(output_path)

    # Flatten keeps variants. "separatelayers" exports each layer separately.
    print(f"USD ROP configured to export: {output_path}")
    print(f"  Source LOP: {parent}/set_look")
    print(f"  Save style: flattenstage (variants preserved)")
    return usd_rop


def export_component_with_variants(parent="/stage", prim_path="/World/hero_asset",
                                   output_dir="D:/assets/hero/"):
    """Export using Component Output LOP for production asset structure.

    Component Output creates a properly structured USD asset with:
    - Payload file (geometry)
    - Root file (composition arcs + variant sets)
    - Optional: separate files per variant
    """
    stage = hou.node(parent)
    if not stage:
        return None

    comp_out = stage.createNode("componentoutput", "export_hero")
    comp_out.parm("rootprim").set(prim_path)
    comp_out.parm("lopoutput").set(f"{output_dir}hero.usd")
    comp_out.parm("payloadlopoutput").set(f"{output_dir}hero_payload.usd")

    # Enable variant export
    comp_out.parm("variantlayers").set(1)  # Separate layer per variant

    comp_out.moveToGoodPosition()
    print(f"Component Output configured:")
    print(f"  Root: {output_dir}hero.usd")
    print(f"  Payload: {output_dir}hero_payload.usd")
    print(f"  Variant layers: enabled (separate files per variant)")
    return comp_out


# Configure export
export_asset_with_variants(
    parent="/stage",
    output_path="D:/assets/hero_export.usd",
    prim_path="/World/hero_asset"
)
```

### Gotchas

```python
# Common variant pitfalls and solutions
import hou

# GOTCHA 1: Variant names must be valid USD identifiers
# Valid:   "high_res", "lookA", "version2", "damaged01"
# Invalid: "high res" (space), "look-A" (hyphen), "2fast" (starts with digit)
# Fix: use underscores and start with a letter
VALID_VARIANT_NAMES = ["base", "damaged_light", "destroyed_v2", "proxy_lo"]
INVALID_VARIANT_NAMES = ["my look", "hi-res", "3rd-option", "look#1"]


# GOTCHA 2: Default variant is the FIRST one authored unless explicitly set
# If you author variants ["destroyed", "base", "high"], default = "destroyed"
# Always author the desired default FIRST, or set it explicitly:
def set_default_variant(parent="/stage", prim_path="/World/hero_asset",
                        variant_set="modelVariant", default_name="base"):
    """Explicitly set the default variant selection.
    Use a Set Variant node AFTER the Add Variant block."""
    stage = hou.node(parent)
    if not stage:
        return
    sv = stage.createNode("setvariant", f"default_{variant_set}")
    sv.parm("primpath").set(prim_path)
    sv.parm("variantset1").set(variant_set)
    sv.parm("variantname1").set(default_name)
    sv.moveToGoodPosition()
    print(f"Default variant set: {variant_set}={default_name}")
    return sv


# GOTCHA 3: Changing variant selection doesn't auto-cook downstream
# After switching variants programmatically, force cook if needed:
def switch_and_cook(setvariant_path, variant_set, variant_name, downstream_path=None):
    """Switch variant and force-cook downstream nodes."""
    node = hou.node(setvariant_path)
    if not node:
        print(f"Couldn't find node: {setvariant_path}")
        return

    # Switch the variant
    node.parm("variantset1").set(variant_set)
    node.parm("variantname1").set(variant_name)

    # Force cook the Set Variant node itself
    node.cook(force=True)

    # If there's a specific downstream node that needs updating
    if downstream_path:
        downstream = hou.node(downstream_path)
        if downstream:
            downstream.cook(force=True)
            print(f"Force-cooked {downstream_path}")

    print(f"Switched {variant_set}={variant_name} and cooked")


# GOTCHA 4: Nested variant sets work but are hard to manage
# Prefer flat, independent variant sets over nesting:
#   GOOD:  variantSet "model" + variantSet "look" (independent, flat)
#   AVOID: variantSet "model" containing variantSet "submodel" (nested)
# Nested sets create combinatorial explosion and confuse downstream tools.


# GOTCHA 5: Graft prim paths must match EXACTLY between base and variant
# If base geometry is at /World/hero_asset/geo/shape
# the graft delta must target the SAME path, not /World/hero_asset/geo
# Mismatched paths create duplicate prims instead of overriding.
def verify_graft_paths(graft_node_path):
    """Check that a Graft node's dest path matches the base prim structure."""
    node = hou.node(graft_node_path)
    if not node:
        print(f"Couldn't find node: {graft_node_path}")
        return

    dest = node.parm("destpath").eval()
    print(f"Graft destination: {dest}")
    print(f"Verify this matches the base geometry prim path exactly.")
    print(f"Mismatch creates duplicate prims instead of clean overrides.")
    return dest


# GOTCHA 6: Variant opinions through references
# When referencing an asset that has variants, the variant selection
# travels WITH the reference. To override it, add a Set Variant node
# AFTER the reference node in your stage.
def override_referenced_variant(parent="/stage", ref_node_path=None,
                                prim_path="/World/hero_asset",
                                variant_set="look", variant_name="dirty"):
    """Override a variant selection on a referenced asset."""
    stage = hou.node(parent)
    if not stage:
        return None

    override = stage.createNode("setvariant", f"override_{variant_set}")
    override.parm("primpath").set(prim_path)
    override.parm("variantset1").set(variant_set)
    override.parm("variantname1").set(variant_name)

    if ref_node_path:
        ref_node = hou.node(ref_node_path)
        if ref_node:
            override.setInput(0, ref_node)

    override.moveToGoodPosition()
    print(f"Override referenced variant: {variant_set}={variant_name}")
    return override
```
