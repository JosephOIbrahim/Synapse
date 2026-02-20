# Render Output Path Configuration

## Triggers
render output, output path, render file, picture parm, outputimage, render to file,
save render, render destination, soho_foreground, synchronous render

## Context
For reliable render output, set the path on BOTH the Karma LOP (`picture`) AND the usdrender ROP (`outputimage`). The ROP's `soho_foreground=1` flag enables synchronous rendering but blocks Houdini entirely — only use for quick test renders.

## Code

```python
# Setting render output on both Karma LOP and usdrender ROP
import hou
import os

# --- Step 1: Configure Karma LOP output ---
karma = hou.node("/stage/karmarendersettings1")
output_dir = "$HIP/render"
output_pattern = f"{output_dir}/beauty.$F4.exr"

karma.parm("picture").set(output_pattern)

# Verify output directory exists (expand variables first)
expanded_dir = hou.text.expandString(output_dir)
if not os.path.isdir(expanded_dir):
    os.makedirs(expanded_dir, exist_ok=True)
    print(f"Created output directory: {expanded_dir}")


# --- Step 2: Configure usdrender ROP ---
# Create or find usdrender ROP in /out
out_net = hou.node("/out")
rop = out_net.node("usdrender1")
if not rop:
    rop = out_net.createNode("usdrender", "usdrender1")

# CRITICAL: Set outputimage on the ROP too
# Without this, the ROP may not write to the expected location
rop.parm("outputimage").set(output_pattern)

# Set LOP path — the ROP needs to know which LOP node to render
# Auto-discover: find the display node in /stage
stage_net = hou.node("/stage")
display_node = stage_net.displayNode()
if display_node:
    rop.parm("loppath").set(display_node.path())
    print(f"ROP loppath set to: {display_node.path()}")


# --- Step 3: Foreground vs Background rendering ---

# SYNCHRONOUS (blocks Houdini until done — test renders only)
# WARNING: If render is slow, WebSocket server becomes unresponsive
rop.parm("soho_foreground").set(1)
rop.render()  # blocks here until frame is written

# ASYNCHRONOUS (non-blocking — production renders)
rop.parm("soho_foreground").set(0)
rop.render()  # returns immediately, render runs in background
# Must poll for file existence to confirm completion
```

```python
# Verifying render output was written
import hou
import os
import time

def wait_for_render(output_path, timeout=120):
    """Wait for render output file, with timeout."""
    expanded = hou.text.expandString(output_path)
    # Substitute current frame
    frame = int(hou.frame())
    expanded = expanded.replace("$F4", f"{frame:04d}")

    start = time.time()
    while time.time() - start < timeout:
        if os.path.isfile(expanded) and os.path.getsize(expanded) > 0:
            size_kb = os.path.getsize(expanded) / 1024
            print(f"Render complete: {expanded} ({size_kb:.0f} KB)")
            return expanded
        time.sleep(1.0)

    raise TimeoutError(f"Render output not found after {timeout}s: {expanded}")


# Usage
rop = hou.node("/out/usdrender1")
rop.parm("soho_foreground").set(0)
rop.render()
result = wait_for_render("$HIP/render/beauty.$F4.exr", timeout=60)
```

```python
# Converting EXR to JPEG for preview using iconvert
import hou
import subprocess
import os

exr_path = hou.text.expandString("$HIP/render/beauty.0001.exr")
jpg_path = exr_path.replace(".exr", ".jpg")

# iconvert lives in $HFS/bin/
hfs = hou.text.expandString("$HFS")
iconvert = os.path.join(hfs, "bin", "iconvert.exe")

if os.path.isfile(exr_path):
    subprocess.run([iconvert, exr_path, jpg_path], check=True)
    print(f"Preview: {jpg_path}")
```

## Expected Output
```
$HIP/render/
  ├─ beauty.0001.exr    (full EXR from Karma)
  ├─ beauty.0001.jpg    (preview from iconvert)
  ├─ beauty.0002.exr
  └─ ...
```

## Common Mistakes
- Setting `picture` on Karma LOP but not `outputimage` on the ROP — output may silently go elsewhere
- Using `soho_foreground=1` on heavy scenes — locks Houdini, WebSocket becomes unresponsive, user must force-kill
- Forgetting to set `loppath` on usdrender ROP — ROP has no LOP node to render from
- Not expanding `$HIP` before checking if output directory exists — `os.path.isdir("$HIP/render")` is always False
- Render output_file kwarg doesn't work for usdrender ROPs — must set `outputimage` or `picture` parm directly
