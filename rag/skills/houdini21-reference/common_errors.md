# Common Houdini Errors and Solutions

## Triggers
houdini error, cook error, node not found, parameter not found, render black,
fireflies, vex syntax error, read-only attribute, cache missing, create node fails

## Context
Common Houdini errors encountered during Synapse sessions, with diagnostic code for each.
Covers: node/path errors, parameter errors, render errors, VEX errors, simulation errors,
viewport errors, and file/cache errors.

## Code

```python
# Diagnostic 1: MaterialLibrary cook error (createNode returns None)
import hou

matlib = hou.node("/stage/materiallibrary1")
if matlib:
    # CRITICAL: cook before creating children -- internal subnet doesn't exist until first cook
    matlib.cook(force=True)
    subnet = matlib.createNode("subnet", "my_material")
    if subnet is None:
        print("createNode returned None -- matlib may need re-cooking")
    else:
        print(f"Created: {subnet.path()}")
```

```python
# Diagnostic 2: Node path not found
import hou

def find_node_safe(path):
    """Find a node, suggest alternatives if not found."""
    node = hou.node(path)
    if node is not None:
        return node

    # Try parent to list siblings
    parts = path.rsplit("/", 1)
    if len(parts) == 2:
        parent = hou.node(parts[0])
        if parent:
            children = [c.name() for c in parent.children()]
            print(f"Couldn't find '{parts[1]}' in {parts[0]}")
            print(f"  Available: {children[:10]}")
        else:
            print(f"Parent path '{parts[0]}' also not found")
    return None

# Usage
node = find_node_safe("/stage/karmarendersettings1")
```

```python
# Diagnostic 3: Node type not found
import hou

def create_node_safe(parent_path, node_type, name=None):
    """Create a node with type validation and common misspelling correction."""
    COMMON_FIXES = {
        "attributewrangle": "attribwrangle",
        "copy_to_points": "copytopoints",
        "attribute_wrangle": "attribwrangle",
        "material_library": "materiallibrary",
        "usd_render": "usdrender",
    }

    parent = hou.node(parent_path)
    if not parent:
        print(f"Parent not found: {parent_path}")
        return None

    corrected = COMMON_FIXES.get(node_type, node_type)
    if corrected != node_type:
        print(f"Corrected node type: '{node_type}' -> '{corrected}'")

    try:
        node = parent.createNode(corrected, name) if name else parent.createNode(corrected)
        return node
    except hou.OperationFailed as e:
        print(f"Couldn't create '{corrected}': {e}")
        return None

# Usage
wrangle = create_node_safe("/obj/geo1", "attribwrangle", "my_wrangle")
```

```python
# Diagnostic 4: USD parameter encoded name resolution
import hou

def find_usd_parm(node, friendly_name):
    """Find a USD parameter by its friendly name."""
    # Common encoded name mappings
    USD_PARM_MAP = {
        "intensity": "xn__inputsintensity_i0a",
        "exposure": "xn__inputsexposure_vya",
        "exposure_control": "xn__inputsexposure_control_wcb",
        "color": "xn__inputscolor_kya",
        "texture_file": "xn__inputstexturefile_i1a",
        "color_temperature": "xn__inputscolortemperature_u5a",
        "enable_color_temperature": "xn__inputsenablecolortemperature_r5a",
    }

    encoded = USD_PARM_MAP.get(friendly_name, friendly_name)
    parm = node.parm(encoded)
    if parm:
        return parm

    # Substring search through all parms
    matches = [p for p in node.parms() if friendly_name.lower() in p.name().lower()]
    if matches:
        print(f"Couldn't find '{friendly_name}', similar parms:")
        for m in matches[:5]:
            print(f"  {m.name()} = {m.eval()}")
    return None

# Usage
light = hou.node("/stage/domelight1")
if light:
    exp_parm = find_usd_parm(light, "exposure")
```

```python
# Diagnostic 5: Keyframe won't set
import hou

def set_keyframe_safe(parm_path, frame, value):
    """Set a keyframe, handling locked/expressed parameters."""
    parm = hou.parm(parm_path)
    if parm is None:
        print(f"Parameter not found: {parm_path}")
        return False

    if parm.isLocked():
        print(f"Parameter is locked: {parm_path}")
        return False

    # Clear existing expression if any
    try:
        expr = parm.expression()
        if expr:
            print(f"Clearing expression: {expr}")
            parm.deleteAllKeyframes()
    except hou.OperationFailed:
        pass  # No expression set

    key = hou.Keyframe()
    key.setFrame(frame)
    key.setValue(value)
    parm.setKeyframe(key)
    return True

# Usage
set_keyframe_safe("/stage/camera1/focalLength", 1, 50.0)
set_keyframe_safe("/stage/camera1/focalLength", 48, 85.0)
```

```python
# Diagnostic 6: Parm tuple mismatch
import hou

def set_transform_safe(node_path, tx=None, ty=None, tz=None):
    """Set transform values correctly using parmTuple."""
    node = hou.node(node_path)
    if not node:
        print(f"Node not found: {node_path}")
        return

    # WRONG: node.parm("t").set((1, 2, 3))  -- "t" is a tuple, not a single parm
    # RIGHT: use parmTuple
    t = node.parmTuple("t")
    if t:
        current = list(t.eval())
        if tx is not None: current[0] = tx
        if ty is not None: current[1] = ty
        if tz is not None: current[2] = tz
        t.set(current)
        print(f"Set transform: {current}")
    else:
        # Fall back to individual parms
        if tx is not None and node.parm("tx"):
            node.parm("tx").set(tx)

# Usage
set_transform_safe("/stage/camera1", tx=5.0, ty=2.0, tz=-8.0)
```

```python
# Diagnostic 7: Black render output
import hou

def diagnose_black_render(karma_node_path):
    """Diagnose why a Karma render produces black output."""
    issues = []
    node = hou.node(karma_node_path)
    if not node:
        issues.append(f"Karma node not found: {karma_node_path}")
        return issues

    # Check camera assignment
    cam = node.evalParm("camera") if node.parm("camera") else ""
    if not cam:
        issues.append("No camera assigned -- set 'camera' parm to USD prim path like /cameras/cam1")

    # Check if any lights exist on stage
    stage = node.stage() if hasattr(node, 'stage') else None
    if stage:
        from pxr import UsdLux
        lights = [p for p in stage.Traverse() if p.IsA(UsdLux.BoundableLightBase) or p.IsA(UsdLux.NonboundableLightBase)]
        if not lights:
            issues.append("No lights on stage -- add a dome light or area light")
        else:
            print(f"Found {len(lights)} light(s)")

    # Check output path
    picture = node.evalParm("picture") if node.parm("picture") else ""
    if not picture:
        issues.append("No output path set -- set 'picture' parm")

    for issue in issues:
        print(f"  Issue: {issue}")
    return issues

diagnose_black_render("/stage/karma1")
```

```python
# Diagnostic 8: Firefly detection and fix
import hou

def fix_fireflies(karma_node_path):
    """Apply anti-firefly settings to Karma render node."""
    node = hou.node(karma_node_path)
    if not node:
        return

    # Intensity must be 1.0 (Lighting Law) -- check all lights
    stage_node = hou.node("/stage")
    if stage_node:
        display = stage_node.displayNode()
        if display and hasattr(display, 'stage'):
            stage = display.stage()
            from pxr import UsdLux
            for prim in stage.Traverse():
                if prim.IsA(UsdLux.BoundableLightBase):
                    intensity = prim.GetAttribute("inputs:intensity")
                    if intensity and intensity.Get() and intensity.Get() > 1.0:
                        print(f"  WARNING: {prim.GetPath()} intensity={intensity.Get()} > 1.0")

    # Increase pixel samples
    if node.parm("karma_samples"):
        current = node.evalParm("karma_samples")
        new_val = min(current * 2, 256)
        node.parm("karma_samples").set(new_val)
        print(f"Increased pixel samples: {current} -> {new_val}")

    # Clamp indirect contribution
    if node.parm("karma_pixelfilterclamp"):
        node.parm("karma_pixelfilterclamp").set(10.0)
        print("Set pixel filter clamp to 10.0")
```

```python
# Diagnostic 9: VEX syntax and type errors
def diagnose_vex_errors(vex_code):
    """Check VEX code for common syntax issues."""
    issues = []

    # Missing semicolons (common for Python users)
    lines = vex_code.strip().split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped and not stripped.endswith(';') and not stripped.endswith('{') \
           and not stripped.endswith('}') and not stripped.startswith('//') \
           and not stripped.startswith('#') and not stripped.startswith('if') \
           and not stripped.startswith('for') and not stripped.startswith('while') \
           and not stripped.startswith('else'):
            issues.append(f"Line {i}: possibly missing semicolon: {stripped}")

    # Read-only attribute writes
    READ_ONLY = ['@ptnum', '@numpt', '@numprim', '@Frame', '@Time', '@TimeInc']
    for ro in READ_ONLY:
        if f'{ro} =' in vex_code or f'{ro}=' in vex_code:
            issues.append(f"Writing to read-only attribute {ro} -- create new attribute instead")

    # Type prefix check
    import re
    untyped = re.findall(r'@(?!ptnum|numpt|numprim|Frame|Time|P|N|Cd|v|up|orient|pscale|id|age)\w+\s*=', vex_code)
    if untyped:
        issues.append(f"Attributes without type prefix: {untyped[:5]} -- use f@, v@, i@, s@ prefix")

    for issue in issues:
        print(f"  VEX issue: {issue}")
    return issues

# Test
diagnose_vex_errors('@ptnum = 5')
diagnose_vex_errors('f@ratio = @ptnum / float(@numpt)')
```

```python
# Diagnostic 10: Simulation explodes
import hou

def diagnose_sim_explosion(dop_path):
    """Check simulation setup for common explosion causes."""
    dop = hou.node(dop_path)
    if not dop:
        print(f"DOP network not found: {dop_path}")
        return

    issues = []

    # Check substeps
    for child in dop.children():
        if child.type().name() == "rbdsolver":
            substeps = child.evalParm("substeps") if child.parm("substeps") else 1
            if substeps < 2:
                issues.append(f"RBD solver substeps={substeps} -- increase to 2-4 for stability")

        if child.type().name() == "groundplane":
            break
    else:
        issues.append("No ground plane found -- add a static object or ground plane")

    for issue in issues:
        print(f"  SIM: {issue}")
    return issues
```

```python
# Diagnostic 11: Cache and file errors
import hou
import os

def diagnose_cache(filecache_path):
    """Check file cache for missing frames or path issues."""
    node = hou.node(filecache_path)
    if not node:
        print(f"File cache not found: {filecache_path}")
        return

    # Check output path
    sopoutput = node.evalParm("sopoutput") if node.parm("sopoutput") else ""
    if not sopoutput:
        print("No output path set on file cache")
        return

    # Expand variables
    expanded = hou.text.expandString(sopoutput)
    output_dir = os.path.dirname(expanded)

    if not os.path.exists(output_dir):
        print(f"Output directory doesn't exist: {output_dir}")
        print(f"  Create it: os.makedirs('{output_dir}', exist_ok=True)")
        return

    # Check frame padding consistency
    if "$F" in sopoutput:
        padding = sopoutput.count("F") if "$FF" not in sopoutput else 1
        # $F4 = 4-digit padding, $F = no padding
        if "$F4" not in sopoutput and "$F3" not in sopoutput:
            print("  WARNING: No frame padding (use $F4 for 4-digit: 0001, 0002, ...)")

    # Count cached files
    import glob
    pattern = expanded.replace("$F4", "????").replace("$F", "*")
    cached = glob.glob(pattern)
    print(f"Found {len(cached)} cached file(s) in {output_dir}")

diagnose_cache("/obj/geo1/filecache1")
```

## Common Mistakes
- Not cooking MaterialLibrary before createNode -- returns None silently
- Using Houdini node path for Karma camera instead of USD prim path
- Setting intensity > 1.0 (violates Lighting Law) -- use exposure instead
- Writing to read-only VEX attributes (@ptnum, @numpt, @Frame)
- Missing type prefix on VEX attributes (use f@, v@, i@, s@)
- Cache path without $F4 padding -- overwrites same file every frame
- Mismatched parm name (friendly vs encoded) on USD/LOP nodes
