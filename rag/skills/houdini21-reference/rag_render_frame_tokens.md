# Render Output: Frame Token Formats

## Triggers
frame token, $F4, F4, frame padding, render sequence, output path sequence,
frame number format, husk output, timeSamples render, frame variable

## Context
CRITICAL: Houdini has THREE different frame token systems that are NOT interchangeable. Using the wrong format causes silent failures — renders complete but output files are missing or incorrectly named.

## CRITICAL: Three Different Frame Token Systems

| Context | Format | Example |
|---------|--------|---------|
| Houdini parameter expressions | `$F4` or `${F4}` | `$HIP/render/shot.$F4.exr` |
| husk command-line --output | `<F4>` | `output.<F4>.exr` |
| USD RenderProduct timeSamples | Explicit per-frame | `{1: "shot.0001.exr", 2: "shot.0002.exr"}` |

## Code

```python
# --- System 1: Houdini Parameter Expressions ($F4) ---
# Used in: Karma LOP picture parm, usdrender ROP outputimage parm
# $F = frame number (no padding)
# $F4 = frame number zero-padded to 4 digits
# $F6 = frame number zero-padded to 6 digits
import hou

karma = hou.node("/stage/karmarendersettings1")

# Correct — Houdini parameter expression
karma.parm("picture").set("$HIP/render/beauty.$F4.exr")

# Verify expansion at current frame
expanded = karma.evalParm("picture")
print(f"Frame {hou.frame()}: {expanded}")
# Output at frame 42: C:/projects/myshot/render/beauty.0042.exr

# Common variants
# $HIP/render/shot.$F4.exr          → shot.0001.exr
# $HIP/render/$HIPNAME.$F4.exr      → scene_v01.0001.exr
# $HIP/render/${HIPNAME}_beauty.$F4.exr → scene_v01_beauty.0001.exr


# --- System 2: husk CLI Tokens (<F4>) ---
# Used ONLY with husk command-line --output flag
# <F> = frame number (no padding)
# <F4> = zero-padded to 4 digits
# WRONG: $F4 in husk command — will be literal string "$F4"
import subprocess
import os

hfs = hou.text.expandString("$HFS")
husk = os.path.join(hfs, "bin", "husk.exe")

usd_file = hou.text.expandString("$HIP/render/scene.usd")
output = "C:/render/beauty.<F4>.exr"  # husk-style token

# Single frame
subprocess.run([
    husk, usd_file,
    "--renderer", "BRAY_HdKarma",
    "--frame", "1",
    "--output", output,
], check=True)

# Frame range
subprocess.run([
    husk, usd_file,
    "--renderer", "BRAY_HdKarma",
    "--frame-range", "1", "100", "1",  # start end step
    "--output", output,
], check=True)


# --- System 3: USD RenderProduct timeSamples ---
# Used when setting per-frame output paths directly on USD prims
# No token substitution — explicit path per frame
from pxr import UsdRender, Sdf

stage = hou.node("/stage/karmarendersettings1").stage()
product_prim = stage.GetPrimAtPath("/Render/rendersettings1/product1")
product = UsdRender.Product(product_prim)

# Check if using timeSamples (animation) or static path (token)
product_name_attr = product.GetProductNameAttr()
time_samples = product_name_attr.GetTimeSamples()

if time_samples:
    # Per-frame explicit paths
    for t in time_samples:
        path = product_name_attr.Get(t)
        print(f"Frame {int(t)}: {path}")
else:
    # Static path with token (will be $F4 style from Karma LOP)
    path = product_name_attr.Get()
    print(f"Static output pattern: {path}")
```

```python
# Detecting which token system is in use
def detect_frame_token(path_string):
    """Identify which frame token system a path uses."""
    if "$F" in path_string or "${F" in path_string:
        return "houdini_expression"  # $F4, ${F4}
    elif "<F" in path_string:
        return "husk_cli"            # <F4>
    else:
        return "static_or_timesample" # no token, check USD timeSamples

# Converting between systems
def houdini_to_husk(path):
    """Convert $F4 → <F4> for husk command-line use."""
    import re
    return re.sub(r'\$\{?F(\d+)\}?', r'<F\1>', path)

def husk_to_houdini(path):
    """Convert <F4> → $F4 for Houdini parameter use."""
    import re
    return re.sub(r'<F(\d+)>', r'$F\1', path)

# Examples
print(houdini_to_husk("$HIP/render/beauty.$F4.exr"))
# → $HIP/render/beauty.<F4>.exr
# NOTE: $HIP still needs expansion separately for husk!

print(husk_to_houdini("output.<F4>.exr"))
# → output.$F4.exr
```

```python
# Expanding frame tokens manually for file existence checks
def expand_frame_path(pattern, frame):
    """Expand a Houdini-style frame token to actual path."""
    import re
    def replace_token(match):
        padding = int(match.group(1)) if match.group(1) else 1
        return str(frame).zfill(padding)
    # Handle ${F4} and $F4
    result = re.sub(r'\$\{?F(\d*)\}?', replace_token, pattern)
    return result

# Usage
pattern = "$HIP/render/beauty.$F4.exr"
expanded_hip = hou.text.expandString("$HIP")
pattern_abs = pattern.replace("$HIP", expanded_hip)
for frame in range(1, 11):
    path = expand_frame_path(pattern_abs, frame)
    print(f"Frame {frame}: {path}")
```

## Common Mistakes
- Using `$F4` in husk `--output` flag — husk doesn't expand Houdini variables, use `<F4>`
- Using `<F4>` in Karma LOP `picture` parm — Houdini doesn't understand husk tokens
- Forgetting to expand `$HIP` when using husk — husk doesn't know Houdini env vars
- Not checking timeSamples on RenderProduct — animated outputs use per-frame paths, not tokens
- Using `$F` (no padding) — output files won't sort correctly: `shot.1.exr`, `shot.10.exr`, `shot.2.exr`
- Mixing token systems in a pipeline — pick one system per context and stick with it
