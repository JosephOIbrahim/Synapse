# USD Scene Assembly

## Triggers
scene assembly, reference, sublayer, payload, composition, USD file, usdc, usda,
asset reference, layer stack, prim path, production structure, deferred loading

## Context
USD scene assembly in Houdini 21 Solaris: references, sublayers, payloads,
composition arcs, and production hierarchy. Includes Python code for all
assembly operations.

## Code

```python
# Reference vs Sublayer: when to use each
import hou

def reference_usd_asset(stage_path, usd_file, prim_path, parent="/stage"):
    """Import a USD asset as a reference under a target prim path.
    Use for: individual assets, characters, props, vehicles.
    References are overridable by stronger layers."""
    stage = hou.node(parent)
    if not stage:
        return

    ref = stage.createNode("reference", f"ref_{prim_path.split('/')[-1]}")
    ref.parm("filepath1").set(usd_file)
    ref.parm("primpath").set(prim_path)
    # Reference type: "Reference" (always loaded) or "Payload" (deferred)
    ref.parm("reftype").set("Reference")

    print(f"Referenced {usd_file} at {prim_path}")
    return ref


def sublayer_usd(stage_path, usd_file, position="strongest", parent="/stage"):
    """Merge a full USD layer into the current stage.
    Use for: environment layouts, lighting rigs, base layers.
    Sublayers are the strongest composition arc (direct edits)."""
    stage = hou.node(parent)
    if not stage:
        return

    sub = stage.createNode("sublayer", f"sub_{usd_file.split('/')[-1].split('.')[0]}")
    sub.parm("filepath1").set(usd_file)
    # Position: 0=strongest (on top), 1=weakest (at bottom)
    sub.parm("position").set(0 if position == "strongest" else 1)

    print(f"Sublayered {usd_file} as {position}")
    return sub


# CRITICAL: For Karma rendering, use sublayer (not assetreference)
# assetreference nodes are invisible to Karma
reference_usd_asset("/stage", "D:/assets/hero_character.usd", "/World/characters/hero")
sublayer_usd("/stage", "D:/assets/lighting_rig.usd", "strongest")
```

```python
# Payload setup for deferred loading (heavy assets)
import hou

def setup_payload(stage_path, usd_file, prim_path, parent="/stage"):
    """Import USD as payload -- loads on demand, not immediately.
    Use for: hero assets, heavy FX caches, crowd agents.
    Unloaded payloads show as empty prims (fast scene open)."""
    stage = hou.node(parent)
    if not stage:
        return

    ref = stage.createNode("reference", f"payload_{prim_path.split('/')[-1]}")
    ref.parm("filepath1").set(usd_file)
    ref.parm("primpath").set(prim_path)
    ref.parm("reftype").set("Payload")  # Deferred loading

    print(f"Payload: {usd_file} at {prim_path} (deferred)")
    return ref


def load_payload(stage_path, prim_path):
    """Force-load a payload prim via usdprimload LOP."""
    stage = hou.node(stage_path)
    if not stage:
        return

    loader = stage.createNode("usdprimload", "load_payload")
    loader.parm("primpath").set(prim_path)
    loader.parm("loadpayload").set(1)  # 1 = Load
    print(f"Loaded payload at {prim_path}")
    return loader


# When to use Reference vs Payload:
#   Reference: always loaded -- env, lights, cameras (things always visible)
#   Payload: deferred -- hero assets, heavy FX caches, crowd members (>50MB)
setup_payload("/stage", "D:/assets/hero_vehicle.usd", "/World/props/vehicle")
```

```python
# Full production scene assembly
import hou

def assemble_production_scene(parent="/stage"):
    """Build a standard production USD scene hierarchy.

    /World
      /environment     <- sublayered (terrain, sky)
      /characters      <- referenced per-character USDs
      /props           <- referenced prop USDs
      /lights          <- sublayered lighting rig
      /cameras         <- per-shot camera
    """
    stage = hou.node(parent)
    if not stage:
        return

    nodes = []

    # 1. Environment (sublayer -- base layer everything builds on)
    env = stage.createNode("sublayer", "environment")
    env.parm("filepath1").set("$HIP/usd/environment.usd")
    env.parm("position").set(1)  # Weakest (base)
    nodes.append(env)

    # 2. Characters (reference -- per-instance transforms, overridable)
    hero = stage.createNode("reference", "hero_character")
    hero.parm("filepath1").set("$HIP/usd/hero.usd")
    hero.parm("primpath").set("/World/characters/hero")
    hero.setInput(0, env)
    nodes.append(hero)

    # 3. Props (reference or payload for heavy assets)
    props = stage.createNode("reference", "props")
    props.parm("filepath1").set("$HIP/usd/props.usd")
    props.parm("primpath").set("/World/props")
    props.setInput(0, hero)
    nodes.append(props)

    # 4. Lighting rig (sublayer -- strongest, overrides all)
    lights = stage.createNode("sublayer", "lighting_rig")
    lights.parm("filepath1").set("$HIP/usd/lighting.usd")
    lights.parm("position").set(0)  # Strongest
    lights.setInput(0, props)
    nodes.append(lights)

    # 5. Camera (inline LOP, not referenced)
    cam = stage.createNode("camera", "shot_camera")
    cam.parm("focalLength").set(50)  # Standard lens
    cam.setInput(0, lights)
    nodes.append(cam)

    stage.layoutChildren()
    print("Production scene assembled:")
    print("  environment (sublayer) -> hero (ref) -> props (ref) -> lights (sublayer) -> camera")
    return nodes


assemble_production_scene()
```

```python
# Query composition arcs on a USD stage
import hou
from pxr import Usd, Sdf, UsdGeom

def inspect_composition(stage_node_path):
    """List all references, sublayers, and payloads in a USD stage."""
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'stage'):
        return

    stage = node.stage()
    root_layer = stage.GetRootLayer()

    # Sublayers
    print("Sublayers:")
    for sub in root_layer.subLayerPaths:
        print(f"  {sub}")

    # References and payloads on prims
    print("\nReferences & Payloads:")
    for prim in stage.Traverse():
        prim_spec = root_layer.GetPrimAtPath(prim.GetPath())
        if prim_spec:
            # Check references
            refs = prim_spec.referenceList
            for ref in refs.prependedItems:
                print(f"  {prim.GetPath()} -> ref: {ref.assetPath}")
            # Check payloads
            payloads = prim_spec.payloadList
            for pl in payloads.prependedItems:
                print(f"  {prim.GetPath()} -> payload: {pl.assetPath}")

    # File format summary
    print("\nUSD file formats:")
    print("  .usdc = Binary (Crate) -- fastest read/write")
    print("  .usda = ASCII text -- human-readable, slow")
    print("  .usd  = Auto-detect -- extension is ambiguous")
    print("  .usdz = Zipped package -- AR/web delivery")

inspect_composition("/stage/karma1")
```

```python
# Houdini ships test assets at $HFS/houdini/usd/assets/
import hou
import os

def list_houdini_test_assets():
    """List built-in USD test assets shipped with Houdini."""
    hfs = os.environ.get("HFS", "")
    asset_dir = os.path.join(hfs, "houdini", "usd", "assets")

    if not os.path.isdir(asset_dir):
        print(f"Asset dir not found: {asset_dir}")
        return []

    assets = []
    for f in sorted(os.listdir(asset_dir)):
        if f.endswith((".usd", ".usdc", ".usda")):
            assets.append(os.path.join(asset_dir, f))
            print(f"  {f}")
    return assets

# Usage: reference a test asset
def reference_test_asset(asset_name, prim_path, parent="/stage"):
    """Reference a built-in Houdini test asset (rubbertoy, pig, etc.)."""
    hfs = os.environ.get("HFS", "")
    asset_path = os.path.join(hfs, "houdini", "usd", "assets", asset_name)

    stage = hou.node(parent)
    if not stage:
        return
    ref = stage.createNode("reference", asset_name.split(".")[0])
    ref.parm("filepath1").set(asset_path)
    ref.parm("primpath").set(prim_path)
    print(f"Referenced test asset: {asset_name} at {prim_path}")
    return ref

list_houdini_test_assets()
reference_test_asset("rubbertoy.usd", "/World/props/rubbertoy")
```

## Expected Scene Graph
```
/World/
  /environment/      <- sublayered (terrain, sky, distant geometry)
  /characters/
    /hero            <- referenced USD
    /crowd/          <- payloads (deferred, per-agent)
  /props/            <- referenced props
  /lights/           <- sublayered lighting rig
  /cameras/
    /render_cam      <- per-shot camera
```

## Common Mistakes
- Using assetreference instead of sublayer for Karma -- assetreference is invisible to Karma renderer
- Not using payloads for heavy assets (>50MB) -- slows scene open time
- Referencing with wrong prim path -- must match source USD hierarchy exactly
- Mixing sublayer position (strongest vs weakest) -- environment should be weakest, lighting strongest
- Using .usda for production -- .usdc (binary Crate) is 5-10x faster to load
- Forgetting to cook the stage after adding references -- downstream nodes may not see new prims
