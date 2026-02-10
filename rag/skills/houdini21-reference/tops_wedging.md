# TOPs/PDG Wedging Reference

## What is Wedging?

Wedging generates parameter variations automatically. Use it for:
- Material lookdev (roughness sweeps, color variations)
- Lighting variations (exposure ranges)
- Render quality presets (sample count sweeps)
- Simulation parameter exploration (viscosity, turbulence)
- Camera angle/focal length tests

## Network Structure

Create a `topnet` at `/obj` level (or in `/stage` for LOP workflows). Inside:

```
wedge -> ropfetch (or other processor)
```

For post-processing (contact sheets, comparison):
```
wedge -> ropfetch -> waitforall -> imagemagick
```

## Wedge Node Key Parameters

| Parameter | Name | Type | Description |
|-----------|------|------|-------------|
| Wedge Count | `wedgecount` | int | Number of variations |
| Wedge Attributes | `wedgeattribs` | string | Attribute name to create |
| Type | `type` | menu | Random, Range, or Specific values |
| Range Start | `range1` | float | Start of range |
| Range End | `range2` | float | End of range |

### Wedge Types
- **Range**: Linear interpolation from start to end. Best for parameter sweeps.
- **Random**: Random values within range. Best for exploration.
- **Specific Values**: Explicit list of values. Best for A/B comparisons.

## MCP Tool: houdini_wedge

```json
{
  "node": "/obj/topnet1/wedge1",
  "parm": "roughness",
  "values": [0.1, 0.3, 0.5, 0.7, 0.9]
}
```

The handler creates work items for each value and cooks the network.

## ropfetch Node

Fetches a ROP and renders for each wedge variation:
- `roppath`: Path to the render ROP (e.g., `/out/karma1`)
- `pdg_workitemindex`: Auto-set per work item
- `top_outputfilepath`: Auto-generated output path per variation

## Channel References

To use wedge values in your scene, use:
```
`@wedge_roughness`
```
in any parameter expression. TOPs injects the attribute at cook time.

### In VEX
```vex
// Access wedge attribute in VEX wrangle
float roughness = detail(1, "wedge_roughness");
```

### In Python
```python
# Access wedge attribute in Python
work_item = pdg.workItem()
roughness = work_item.attrib("wedge_roughness").value
```

## Work Item Processors

| Node | Description | Use Case |
|------|-------------|----------|
| `ropfetch` | Render a ROP | Rendering wedge variations |
| `pythonprocessor` | Run Python per work item | Custom processing |
| `genericgenerator` | Create work items from Python | Custom generation |
| `filepattern` | Generate from file glob | Process existing files |
| `waitforall` | Wait for all upstream items | Collect before montage |
| `imagemagick` | ImageMagick operations | Contact sheets, montages |
| `ffmpegencodevideo` | Encode video | Turntables, playblasts |
| `partitionbyattribute` | Group work items | Organize by wedge param |

## Typical Workflows

### Roughness Sweep
```
wedge(roughness: 0.0 -> 1.0, 10 steps) -> ropfetch -> waitforall -> imagemagick_montage
```
Creates a contact sheet comparing 10 roughness values.

### Exposure Sweep (Lighting Law compliant)
```
wedge(exposure: 2.0 -> 8.0, 5 steps) -> ropfetch
```
**Note**: Wedge exposure, NOT intensity. Intensity stays at 1.0.

### Multi-Parameter Wedge
Stack multiple wedge nodes for combinatorial exploration:
```
wedge1(color: red,green,blue) -> wedge2(roughness: 0.2,0.5,0.8) -> ropfetch
```
Generates 3 x 3 = 9 variations.

### Simulation Parameter Sweep
```
wedge(viscosity: 0.0,0.5,5.0,50.0) -> ropfetch(sim_rop)
```
Useful for dialing in FLIP or Pyro parameters before committing to a long sim.

### Camera Turntable
```
wedge(ry: 0 -> 360, 36 steps) -> ropfetch -> waitforall -> ffmpegencodevideo
```
Renders 36 frames of camera rotation and encodes to video.

## Schedulers

PDG uses schedulers to execute work items:

| Scheduler | Description | Use Case |
|-----------|-------------|----------|
| `localscheduler` | Local machine, parallel processes | Default, quick tests |
| `hqueuescheduler` | HQueue farm submission | Studio render farm |
| `deadline` | Deadline scheduler | Deadline render farm |

### Local Scheduler Tips
- `maxproccount`: Limit parallel processes (default = CPU core count)
- For GPU renders (Karma XPU), set to 1 to avoid GPU contention
- For CPU renders, match to core count
- `tempdirlocal`: Temp directory for work item data

## Output File Management

### Automatic Output Paths
TOPs generates output paths per work item:
```
$HIP/render/wedge_roughness_0.1.exr
$HIP/render/wedge_roughness_0.3.exr
...
```

### Custom Output via Tag
Use `@pdg_output` to control output file naming:
```python
# In python processor
import os
work_item.addExpectedResultData(
    os.path.join("$HIP/render", f"wedge_{wedge_val:.2f}.exr"),
    "file/image"
)
```

## Performance Tips

- Start with low sample counts during wedging -- you're comparing, not delivering
- Use `waitforall` + `imagemagick` montage for quick comparison contact sheets
- For GPU renders, limit parallel work items to 1 (GPU can't share between renders)
- Cache simulation before wedging render parameters -- don't re-sim per wedge
- Use `partitionbyattribute` to group results by parameter for organized review

## Common Wedge Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| All renders look identical | Channel reference not wired | Check `@wedge_name` syntax in scene parm |
| TOPs won't cook | Scheduler not running | Start local scheduler, check process limit |
| Output files overwrite each other | No per-item output path | Use `$WEDGENUM` or `@pdg_index` in output path |
| Combinatorial explosion | Too many stacked wedges | Reduce per-wedge count, use targeted values |
| GPU out of memory | Multiple GPU renders in parallel | Set `maxproccount=1` on local scheduler |
