# TOPs/PDG Wedging Reference

## Triggers
wedge, wedging, tops wedge, pdg wedge, parameter sweep, parameter variation, lookdev sweep,
roughness sweep, exposure sweep, multi-parameter, work item, ropfetch, contact sheet,
scheduler, localscheduler, hqueue, pdg output, wedge attribute, @wedge, combinatorial

## Context
Wedging generates parameter variations automatically via TOPs/PDG. Use it for material lookdev
(roughness/color sweeps), lighting variation (exposure ranges), render quality presets, simulation
parameter exploration, and camera turntable sequences.

---

## Wedge Node Setup

```python
import hou

# --- Create topnet and wedge node ---
obj = hou.node("/obj")
topnet = obj.createNode("topnet", "topnet1")

wedge = topnet.createNode("wedge", "wedge1")

# Set wedge count (number of variations)
wedge.parm("wedgecount").set(10)

# Name the wedge attribute (accessed as @wedge_roughness in channel refs)
wedge.parm("wedgeattribs").set("roughness")

# Wedge type: 0 = Range, 1 = Random, 2 = Specific Values
wedge.parm("type").set(0)  # Range

# Range: 0.0 -> 1.0 linear interpolation across wedgecount steps
wedge.parm("range1").set(0.0)
wedge.parm("range2").set(1.0)
```

```python
# --- Wedge type: Specific Values (for A/B comparison) ---
wedge.parm("type").set(2)  # Specific Values

# Add explicit values via the multiparm
values = [0.1, 0.3, 0.5, 0.7, 0.9]
wedge.parm("numvalues").set(len(values))
for i, v in enumerate(values):
    wedge.parm(f"value{i + 1}").set(v)
```

```python
# --- Wedge type: Random (exploration mode) ---
wedge.parm("type").set(1)  # Random
wedge.parm("range1").set(0.0)
wedge.parm("range2").set(1.0)
wedge.parm("wedgecount").set(20)   # 20 random samples within range
wedge.parm("seed").set(42)         # reproducible random seed
```

---

## ropfetch Configuration

```python
import hou

topnet = hou.node("/obj/topnet1")
wedge  = topnet.node("wedge1")

# Create ropfetch to drive a Karma render for each work item
ropfetch = topnet.createNode("ropfetch", "ropfetch1")

# Point ropfetch at the render ROP
ropfetch.parm("roppath").set("/out/karma1")

# Wire wedge -> ropfetch
ropfetch.setInput(0, wedge)

# ropfetch auto-sets per work item:
#   pdg_workitemindex  -- integer index of the current work item
#   top_outputfilepath -- auto-generated output path per variation

# Override output path to embed wedge value in filename
# Use HScript expression on the karma ROP's "picture" parm:
karma = hou.node("/out/karma1")
karma.parm("picture").setExpression(
    '"$HIP/render/roughness_" + pdg.workItem().attrib("wedge_roughness").value + ".exr"',
    hou.exprLanguage.Python
)
```

---

## Channel References — Using Wedge Values in Scene Parameters

```python
# --- HScript backtick expression (most common) ---
# In any Houdini parameter field, type this string literal:
#   `@wedge_roughness`
# TOPs substitutes the per-work-item attribute value at cook time.

import hou

# Set a roughness parm to reference the wedge attribute via HScript
mat_node = hou.node("/stage/materiallibrary1/principledshader1")
mat_node.parm("rough").setExpression("`@wedge_roughness`", hou.exprLanguage.Hscript)

# Exposure sweep (Lighting Law: intensity stays 1.0, sweep EXPOSURE only)
light = hou.node("/stage/distantlight1")
light.parm("xn__inputsexposure_vya").setExpression("`@wedge_exposure`", hou.exprLanguage.Hscript)
light.parm("xn__inputsintensity_i0a").set(1.0)  # NEVER change intensity

# Camera Y rotation for turntable
cam = hou.node("/stage/camera1")
cam.parm("ry").setExpression("`@wedge_ry`", hou.exprLanguage.Hscript)
```

```vex
// --- VEX wrangle: read wedge attribute from upstream TOPs data ---
// Wire the wrangle to receive TOPs attributes via input 1
float roughness = detail(1, "wedge_roughness", 0.5);  // 0.5 = default fallback
@roughness = roughness;
```

```python
# --- Python processor: read wedge attribute at cook time ---
import pdg

work_item = pdg.workItem()

roughness = work_item.attrib("wedge_roughness").value
exposure  = work_item.attrib("wedge_exposure").value
wedge_idx = work_item.index  # integer index (0-based)

print(f"Work item {wedge_idx}: roughness={roughness:.3f}, exposure={exposure:.3f}")
```

---

## Multi-Parameter Wedge (Combinatorial)

```python
import hou

topnet = hou.node("/obj/topnet1")

# wedge1: 3 color values
wedge_color = topnet.createNode("wedge", "wedge_color")
wedge_color.parm("wedgeattribs").set("base_color")
wedge_color.parm("type").set(2)       # Specific Values
wedge_color.parm("numvalues").set(3)
wedge_color.parm("value1").set(0.8)   # near-white
wedge_color.parm("value2").set(0.4)   # mid-grey
wedge_color.parm("value3").set(0.05)  # near-black

# wedge2: 3 roughness values -- stacked after wedge1 for combinatorial expansion
wedge_rough = topnet.createNode("wedge", "wedge_roughness")
wedge_rough.parm("wedgeattribs").set("roughness")
wedge_rough.parm("type").set(2)
wedge_rough.parm("numvalues").set(3)
wedge_rough.parm("value1").set(0.2)
wedge_rough.parm("value2").set(0.5)
wedge_rough.parm("value3").set(0.8)
wedge_rough.setInput(0, wedge_color)  # chain after color wedge

# Result: 3 colors x 3 roughness = 9 work items total

# ropfetch reads both attributes from each work item
ropfetch = topnet.createNode("ropfetch", "ropfetch1")
ropfetch.parm("roppath").set("/out/karma1")
ropfetch.setInput(0, wedge_rough)
```

---

## Scheduler Setup

```python
import hou

topnet = hou.node("/obj/topnet1")

# --- Local scheduler (default, quick tests) ---
local_sched = topnet.createNode("localscheduler", "localscheduler1")

# Limit parallel processes -- for GPU renders set to 1 (Karma XPU, single GPU)
local_sched.parm("maxproccount").set(1)

# For CPU renders match to physical core count
import multiprocessing
local_sched.parm("maxproccount").set(multiprocessing.cpu_count())

# Temp directory for PDG work item scratch data
local_sched.parm("tempdirlocal").set("$HIP/pdg_temp")

# Set as active scheduler for the topnet
topnet.parm("topscheduler").set(local_sched.path())
```

```python
# --- HQueue scheduler (studio render farm) ---
hq_sched = topnet.createNode("hqueuescheduler", "hqueuescheduler1")
hq_sched.parm("hq_server").set("http://rendermaster:5000")
hq_sched.parm("hq_priority").set(50)
hq_sched.parm("hq_maxslots").set(16)   # max concurrent farm slots
topnet.parm("topscheduler").set(hq_sched.path())
```

---

## Output File Management

```python
import hou, os

topnet  = hou.node("/obj/topnet1")
ropfetch = topnet.node("ropfetch1")

# --- Embed wedge index and value in output filename ---
# Set on the Karma ROP's picture parm using an HScript expression
karma = hou.node("/out/karma1")

# $WEDGENUM  -- per-work-item integer index (HScript variable injected by TOPs)
# @wedge_roughness -- attribute value substituted by TOPs
karma.parm("picture").setExpression(
    '"$HIP/render/roughness_" + sprintf("%04d", $WEDGENUM) + "_" + '
    'sprintf("%.3f", `@wedge_roughness`) + ".exr"',
    hou.exprLanguage.Hscript
)

# Ensure output directory exists before cooking
out_dir = hou.expandString("$HIP/render")
os.makedirs(out_dir, exist_ok=True)
```

```python
# --- Python processor: register expected output so TOPs tracks the file ---
import pdg, os

work_item = pdg.workItem()
roughness = work_item.attrib("wedge_roughness").value
idx       = work_item.index

hip    = os.environ.get("HIP", "/tmp")
outpath = os.path.join(hip, "render", f"roughness_{idx:04d}_{roughness:.3f}.exr")

# Register the file as an expected result (TOPs dependency tracking)
work_item.addExpectedResultData(outpath, "file/image")
```

---

## Contact Sheet Pipeline

```python
import hou

topnet = hou.node("/obj/topnet1")
wedge    = topnet.node("wedge1")
ropfetch = topnet.node("ropfetch1")

# waitforall: barrier -- collect all rendered frames before montage
waitforall = topnet.createNode("waitforall", "waitforall1")
waitforall.setInput(0, ropfetch)

# imagemagick montage: assemble EXRs into a contact sheet
montage = topnet.createNode("imagemagick", "montage1")
montage.setInput(0, waitforall)

# montage command: arrange in a grid, label each tile with the wedge index
montage.parm("imagemagickop").set(0)  # 0 = montage mode
montage.parm("montagegeometry").set("320x240")   # thumbnail size per tile
montage.parm("montagetile").set("5x2")           # grid: 5 cols x 2 rows = 10 tiles
montage.parm("montageoutput").set("$HIP/render/contact_sheet.jpg")

# Layout: wedge -> ropfetch -> waitforall -> montage
print("Network: wedge -> ropfetch -> waitforall -> montage")
print(f"Tiles:   {wedge.parm('wedgecount').eval()} variations")
```

```python
# --- Camera turntable: 36 frames -> ffmpeg video ---
import hou

topnet = hou.node("/obj/topnet1")

# wedge Y rotation 0 -> 360 in 36 steps (10-degree increments)
wedge_ry = topnet.createNode("wedge", "wedge_ry")
wedge_ry.parm("wedgeattribs").set("ry")
wedge_ry.parm("type").set(0)          # Range
wedge_ry.parm("range1").set(0.0)
wedge_ry.parm("range2").set(350.0)    # stop before 360 (same as 0)
wedge_ry.parm("wedgecount").set(36)

ropfetch_tt = topnet.createNode("ropfetch", "ropfetch_turntable")
ropfetch_tt.parm("roppath").set("/out/karma1")
ropfetch_tt.setInput(0, wedge_ry)

waitforall_tt = topnet.createNode("waitforall", "waitforall_tt")
waitforall_tt.setInput(0, ropfetch_tt)

ffmpeg = topnet.createNode("ffmpegencodevideo", "ffmpeg1")
ffmpeg.setInput(0, waitforall_tt)
ffmpeg.parm("outputfile").set("$HIP/render/turntable.mp4")
ffmpeg.parm("framerate").set(12)      # 36 frames / 12 fps = 3-second loop
```

---

## Cooking the Network via Python

```python
import hou

topnet  = hou.node("/obj/topnet1")
ropfetch = topnet.node("ropfetch1")

# Dirty all work items to force a full recook
topnet.dirtyAllTasks(True)

# Cook synchronously (blocks until complete)
ropfetch.cookWorkItems(block=True)

# Check work item results
for work_item in ropfetch.workItems():
    print(f"  [{work_item.index}] state={work_item.state} "
          f"outputs={[r.localized_path for r in work_item.resultData]}")
```

---

## Common Wedge Issues

- **All renders look identical**: The channel reference `@wedge_name` is missing or misspelled in the scene parameter. Verify the attribute name matches exactly (case-sensitive). Check the wedge node's `wedgeattribs` parm.
- **TOPs won't cook**: The local scheduler is not started or its process limit is 0. Open the localscheduler node, check `maxproccount`, and ensure it is set as the active scheduler on the topnet.
- **Output files overwrite each other**: The ROP output path has no per-item token. Use `$WEDGENUM`, `@pdg_index`, or embed `@wedge_<attr>` in the filename expression.
- **Combinatorial explosion**: Stacking multiple wedge nodes multiplies work items. Three wedges of 10 each = 1,000 items. Reduce per-wedge count or use Specific Values with fewer entries.
- **GPU out of memory with parallel items**: Set `maxproccount=1` on the local scheduler. Karma XPU uses the full GPU; concurrent renders will OOM.
- **Wedge attribute not visible downstream**: The attribute must be created by the wedge node upstream in the same PDG graph. Check the network wiring — a broken input chain silently drops attributes.
