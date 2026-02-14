# Render Farm Workflows

## Synapse Render Farm

Synapse includes a local render farm orchestrator that automates sequence
rendering with per-frame validation and self-improving fixes.

### Quick Start

Tell Synapse to render a sequence:
- "render sequence 1001-1100"
- "batch render 1001-1050 on /stage/karma1"
- "render and validate" (single current frame)

### How It Works

1. **Scene Classification** -- Before rendering, Synapse analyzes the USD
   stage to tag the scene: interior/outdoor, many_lights, has_environment,
   has_volumes, high_poly. These tags enable cross-shot learning.

2. **Memory Warmup** -- Queries past render sessions for known-good settings
   matching the current scene tags. If a previous session found that "128
   samples fixes fireflies for interiors," the new session starts with that.

3. **Per-Frame Loop** -- For each frame:
   - Render via Karma XPU (GPU)
   - Validate the output image (OIIO pixel analysis)
   - If validation passes, move to next frame
   - If validation fails, diagnose the issue and apply a fix
   - Re-render up to 3 times

4. **Report** -- Generates a Markdown report with per-frame results, timing,
   issues found, and fixes applied. Sends a Windows toast notification.

### Validation Checks

The validator runs these checks on every rendered frame:

| Check | What It Detects |
|-------|----------------|
| `file_integrity` | Corrupt or incomplete image files |
| `black_frame` | Completely dark frames (missing lights, wrong camera) |
| `nan_check` | NaN/Inf pixels from shader errors |
| `clipping` | Overexposed (burned out) regions |
| `underexposure` | Entire frame too dark |
| `saturation` | Firefly artifacts (isolated extremely bright pixels) |

### Auto-Fix Remedies

When a check fails, the orchestrator applies a targeted fix:

| Issue | Default Fix |
|-------|------------|
| Fireflies (saturation) | Double pixel samples (max 256) |
| Black frame | Increase exposure +2 stops |
| NaN pixels | Enable pixel filter clamp at 100 |
| Clipping | Reduce exposure -1 stop |
| Underexposure | Increase exposure +1 stop |

Memory-assisted fixes take priority over defaults. If a past session
recorded a specific fix for the current scene type, that fix is applied
first.

### Key Render Settings (Karma)

| Parameter | Description | Typical Range |
|-----------|-------------|---------------|
| `karma_samples` | Pixel samples per pixel | 32-256 |
| `karma_maxpathdepth` | Max ray bounce depth | 4-12 |
| `exposure` | Camera exposure in stops | -2 to 10 |
| `karma_pixelfilterclamp` | Clamp extreme pixel values | 10-1000 |

### Lighting Law (Critical)

- **Intensity is ALWAYS 1.0** -- never set intensity above 1
- **Brightness controlled by EXPOSURE** (logarithmic, in stops)
- Key:fill ratio 3:1 = 1.585 stops difference
- Key:fill ratio 4:1 = 2.0 stops difference

### Scene Classification Tags

| Tag | Detected By |
|-----|-------------|
| `interior` | Keywords: room, interior, indoor, cave, tunnel |
| `outdoor` | Keywords: outdoor, exterior, sky, terrain |
| `many_lights` | 5+ light prims in the stage |
| `has_environment` | DomeLight or HDRI prim present |
| `has_volumes` | Volume, VDB, fog, smoke prims |
| `high_poly` | 50,000+ prims |

### PDG / TOPs Render Farms

For studio-scale rendering, Houdini's PDG (Procedural Dependency Graph)
manages distributed rendering across multiple machines:

- **ROP Fetch** -- Wraps a render ROP as a TOP work item
- **Local Scheduler** -- Manages concurrent processes on one machine
- **HQueue Scheduler** -- Distributes to HQueue render farm
- **Deadline/Tractor** -- Third-party scheduler integration

Synapse's render farm complements PDG by adding the validation and
self-improvement loop that PDG lacks (PDG is acyclic -- no loops).

### Troubleshooting

**Render produces no output:**
- Check if `picture` parm is set on the Karma LOP
- Check if `outputimage` is set on the ROP
- Verify the output directory exists
- Use `synapse_render_settings` to inspect current settings

**Fireflies persist after fix:**
- Try increasing samples beyond the auto-fix max (256)
- Lower `karma_maxpathdepth` to 4
- Check for emissive materials with extreme values
- Look for small bright light sources without sufficient samples

**Black frames:**
- Verify camera is assigned in render settings
- Check if lights are active (not deactivated prims)
- Confirm geometry is visible to camera
- Check frame range -- camera or objects may not exist at that frame
