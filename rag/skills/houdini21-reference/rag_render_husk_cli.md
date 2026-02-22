# husk Command-Line Rendering

## Triggers
husk, command line render, headless render, batch render husk, husk cli,
standalone render, husk flags, husk output, render without houdini

## Context
husk is Houdini's standalone USD renderer at `$HFS/bin/husk`. It renders USD files without a running Houdini session. Uses `<F4>` frame tokens (not `$F4`). Combine with `iconvert` for EXR-to-JPEG preview conversion.

## Code

```python
# Basic husk render — single frame
import subprocess
import os

hfs = os.environ.get("HFS", r"C:\Program Files\Side Effects Software\Houdini 21.0.596")
husk = os.path.join(hfs, "bin", "husk.exe")

usd_file = r"D:\HOUDINI_PROJECTS_2025\myshot\render\scene.usd"
output = r"D:\HOUDINI_PROJECTS_2025\myshot\render\beauty.<F4>.exr"

# Single frame (frame 1)
result = subprocess.run([
    husk, usd_file,
    "--renderer", "BRAY_HdKarma",    # or BRAY_HdKarmaXPU
    "--frame", "1",
    "--output", output,
    "--res", "1920", "1080",
    "--pixel-samples", "64",
], capture_output=True, text=True)

print(f"Exit code: {result.returncode}")
if result.stderr:
    print(f"Errors: {result.stderr[:500]}")
```

```python
# husk frame range render
import subprocess
import os

hfs = os.environ.get("HFS", r"C:\Program Files\Side Effects Software\Houdini 21.0.596")
husk = os.path.join(hfs, "bin", "husk.exe")

usd_file = r"D:\HOUDINI_PROJECTS_2025\myshot\render\scene.usd"
output = r"D:\HOUDINI_PROJECTS_2025\myshot\render\beauty.<F4>.exr"

# Frame range: frames 1-100, step 1
result = subprocess.run([
    husk, usd_file,
    "--renderer", "BRAY_HdKarma",
    "--frame-range", "1", "100", "1",   # start, end, step
    "--output", output,
    "--res", "1920", "1080",
    "--pixel-samples", "128",
    "--exr-compression", "zips",         # EXR compression
], capture_output=True, text=True, timeout=7200)  # 2hr timeout

print(f"Render complete, exit code: {result.returncode}")
```

```python
# husk with all common flags
import subprocess
import os

hfs = os.environ.get("HFS", r"C:\Program Files\Side Effects Software\Houdini 21.0.596")
husk = os.path.join(hfs, "bin", "husk.exe")

cmd = [
    husk,
    "scene.usd",                        # input USD file

    # Renderer selection
    "--renderer", "BRAY_HdKarma",       # BRAY_HdKarma | BRAY_HdKarmaXPU

    # Frame control
    "--frame", "1",                      # single frame
    # "--frame-range", "1", "100", "1",  # OR: range (start end step)
    # "--frame-list", "1,5,10,20",       # OR: specific frames

    # Output
    "--output", "beauty.<F4>.exr",       # <F4> = husk frame token
    "--res", "1920", "1080",             # override resolution

    # Quality
    "--pixel-samples", "64",             # samples per pixel
    # "--convergence-mode", "path-traced",

    # EXR options
    "--exr-compression", "zips",         # none|rle|zip|zips|piz|pxr24|b44|b44a|dwaa|dwab

    # Camera (if multiple in scene)
    # "--camera", "/cameras/render_cam",

    # Render settings (if multiple in scene)
    # "--render-settings", "/Render/rendersettings1",

    # Verbosity
    "--verbose", "3",                    # 0=errors, 1=warnings, 2=info, 3=debug
]

result = subprocess.run(cmd, capture_output=True, text=True)
```

```python
# EXR to JPEG conversion pipeline using iconvert
import subprocess
import os
import glob

hfs = os.environ.get("HFS", r"C:\Program Files\Side Effects Software\Houdini 21.0.596")
iconvert = os.path.join(hfs, "bin", "iconvert.exe")

render_dir = r"D:\HOUDINI_PROJECTS_2025\myshot\render"

# Convert all EXR files to JPEG for preview
exr_files = sorted(glob.glob(os.path.join(render_dir, "beauty.*.exr")))
for exr_path in exr_files:
    jpg_path = exr_path.replace(".exr", ".jpg")
    result = subprocess.run(
        [iconvert, exr_path, jpg_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        size_kb = os.path.getsize(jpg_path) / 1024
        print(f"Converted: {os.path.basename(jpg_path)} ({size_kb:.0f} KB)")
    else:
        print(f"FAILED: {os.path.basename(exr_path)} - {result.stderr}")
```

```python
# Complete pipeline: render with husk + convert + verify
import subprocess
import os

def render_and_preview(usd_file, output_dir, frame, resolution=(1920, 1080), samples=64):
    """Full pipeline: render frame with husk, convert to JPEG, return paths."""
    hfs = os.environ.get("HFS", r"C:\Program Files\Side Effects Software\Houdini 21.0.596")
    husk = os.path.join(hfs, "bin", "husk.exe")
    iconvert = os.path.join(hfs, "bin", "iconvert.exe")

    os.makedirs(output_dir, exist_ok=True)
    exr_pattern = os.path.join(output_dir, "beauty.<F4>.exr")

    # Step 1: Render
    print(f"Rendering frame {frame}...")
    result = subprocess.run([
        husk, usd_file,
        "--renderer", "BRAY_HdKarma",
        "--frame", str(frame),
        "--output", exr_pattern,
        "--res", str(resolution[0]), str(resolution[1]),
        "--pixel-samples", str(samples),
    ], capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(f"husk failed: {result.stderr[:300]}")

    # Step 2: Verify EXR exists
    exr_path = os.path.join(output_dir, f"beauty.{frame:04d}.exr")
    if not os.path.isfile(exr_path):
        raise FileNotFoundError(f"Expected output not found: {exr_path}")

    exr_size = os.path.getsize(exr_path) / 1024
    print(f"EXR: {exr_path} ({exr_size:.0f} KB)")

    # Step 3: Convert to JPEG
    jpg_path = exr_path.replace(".exr", ".jpg")
    subprocess.run([iconvert, exr_path, jpg_path], check=True)
    print(f"Preview: {jpg_path}")

    return {"exr": exr_path, "jpg": jpg_path, "size_kb": exr_size}


# Usage
result = render_and_preview(
    usd_file=r"D:\HOUDINI_PROJECTS_2025\myshot\scene.usd",
    output_dir=r"D:\HOUDINI_PROJECTS_2025\myshot\render",
    frame=1,
    resolution=(1920, 1080),
    samples=64,
)
```

## Expected Output
```
Rendering frame 1...
EXR: D:\HOUDINI_PROJECTS_2025\myshot\render\beauty.0001.exr (4523 KB)
Preview: D:\HOUDINI_PROJECTS_2025\myshot\render\beauty.0001.jpg
```

## Common Mistakes
- Using `$F4` in husk `--output` — husk uses `<F4>` tokens, not Houdini variables
- Forgetting to set `$HFS` or using wrong Houdini version path for husk binary
- Not setting `--renderer` — husk may default to Storm (GL) which produces viewport-quality output
- Using `--frame-range` with wrong argument order — it's `start end step`, not `start step end`
- Not setting timeout on `subprocess.run` — long renders hang the calling process indefinitely
- Forgetting `iconvert` also lives in `$HFS/bin/` — not a system-wide tool
