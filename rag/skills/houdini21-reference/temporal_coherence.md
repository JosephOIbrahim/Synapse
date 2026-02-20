# Temporal Coherence in Animation Rendering

## Triggers
temporal coherence, flickering, noise flicker, texture swimming, geometry popping, shadow flicker, firefly, denoiser smearing, LOD pop, volume flickering, motion blur, xformsamples, geosamples, step rate, pixel samples, animation render, frame consistency, OIDN, OptiX, rest position, adaptive subdivision, deformation blur, velocity blur, shutter range, Karma animation settings, frame comparison

## Context
Temporal coherence means visual consistency between consecutive frames. Flickering noise, swimming textures, popping geometry, and inconsistent shadows all break the illusion of continuous motion in the Houdini/Karma pipeline.

## Code

### Artifact Diagnostic — Identify Temporal Instability by Type

```python
# Run in Houdini Python shell to audit a node for common temporal instability causes.
# Returns a dict of detected risk factors.

import hou

def diagnose_temporal_artifacts(node_path):
    """
    Inspect a geometry or LOP node for properties that cause frame-to-frame instability.
    Checks adaptivity, rest attribute, velocity attribute, and subdivision settings.
    """
    node = hou.node(node_path)
    if node is None:
        raise ValueError(f"Couldn't find node at {node_path!r}")

    risks = {}

    # --- Geometry node checks ---
    geo = node.geometry() if hasattr(node, "geometry") else None
    if geo:
        # Texture swimming: procedural noise driven by @P on deforming geo
        attribs = [a.name() for a in geo.pointAttribs()]
        has_rest = "rest" in attribs
        has_v    = "v" in attribs       # velocity — needed for velocity motion blur
        risks["missing_rest_attribute"] = not has_rest
        risks["missing_velocity_attribute"] = not has_v

        # Geometry popping: adaptive meshing changes topology per frame
        prim_count = geo.intrinsicValue("pointcount")
        risks["zero_primitives"] = (prim_count == 0)

    # --- Render/LOP node checks ---
    try:
        # Adaptive subdivision — must be 0 for animation
        adaptivity = node.evalParm("vm_rendersubd") or node.evalParm("vm_shadingquality")
        if adaptivity and float(adaptivity) > 0:
            risks["adaptive_subdivision_nonzero"] = True
    except Exception:
        pass

    return risks


def print_artifact_report(node_path):
    risks = diagnose_temporal_artifacts(node_path)
    print(f"\n=== Temporal Coherence Audit: {node_path} ===")
    if not any(risks.values()):
        print("  No risks detected.")
        return
    for risk, flagged in risks.items():
        if flagged:
            label = risk.replace("_", " ").capitalize()
            print(f"  [RISK] {label}")


# Usage:
# print_artifact_report("/obj/pyro_sim/fluid_surface")
```

### Artifact Reference — VEX Diagnostic Snippet

```vex
// Attach to a Wrangle SOP (run over Points) to flag geometry using world-space
// position (@P) for noise instead of rest position -- a common cause of texture swimming.
// Outputs a "temporal_risk" integer attribute: 1 = at risk, 0 = safe.

@temporal_risk = 0;

// If this geo has a rest attribute, noise driven by it is temporally stable.
// If it only has @P and the geometry deforms, the noise will swim.
int has_rest = haspointattrib(0, "rest");
if (!has_rest) {
    @temporal_risk = 1;  // flag: no rest position, noise may swim
}

// Velocity attribute check -- required for velocity-based motion blur.
int has_vel = haspointattrib(0, "v");
if (!has_vel) {
    @temporal_risk = max(@temporal_risk, 1);  // flag: no velocity for motion blur
}
```

### Denoiser Setup — Configure Intel OIDN and OptiX on Karma LOP

```python
# Configure the Karma LOP denoiser for animation production.
# Intel OIDN = frame-by-frame, no temporal smearing, safe default.
# OptiX = GPU-accelerated, also frame-by-frame in Karma.
# Rule: pick ONE denoiser and keep it consistent across the full sequence.

import hou

def configure_karma_denoiser(karma_node_path, denoiser="oidn", base_samples=64):
    """
    Set up denoising on a Karma LOP node for animation.

    Args:
        karma_node_path: Path to the Karma LOP node (e.g. "/stage/karma1")
        denoiser:        "oidn" (Intel, CPU) or "optix" (NVIDIA, GPU)
        base_samples:    Pixel samples fed to the denoiser — minimum 64 for animation
    """
    node = hou.node(karma_node_path)
    if node is None:
        raise ValueError(f"Couldn't find Karma node at {karma_node_path!r}")

    # --- Base sample count ---
    # 64+ samples before denoising for frame-to-frame consistency.
    # Fewer samples + heavy denoising causes temporal smearing.
    node.parm("vm_samples").set(base_samples)

    # --- Enable denoiser ---
    # vm_denoiser: 0=off, 1=OIDN, 2=OptiX
    denoiser_map = {"oidn": 1, "optix": 2, "off": 0}
    node.parm("vm_denoiser").set(denoiser_map.get(denoiser, 1))

    # --- Auxiliary AOVs improve edge preservation ---
    # Albedo and normal passes help the denoiser reconstruct sharp edges.
    # DO NOT denoise depth, normal, or cryptomatte AOVs directly.
    node.parm("vm_denoise_albedo").set(1)   # provide albedo aux pass
    node.parm("vm_denoise_normal").set(1)   # provide normal aux pass

    print(f"Karma denoiser configured: {denoiser.upper()} | {base_samples} samples")
    print(f"  Node: {karma_node_path}")
    print(f"  Denoise beauty only — utility AOVs (depth, normal, cryptomatte) left raw.")


# Usage:
# configure_karma_denoiser("/stage/karma1", denoiser="oidn", base_samples=64)
# configure_karma_denoiser("/stage/karma1", denoiser="optix", base_samples=128)
```

### Motion Blur — Set xformsamples and geosamples on Karma LOP

```python
# Motion blur is essential for temporal coherence at 24fps.
# Without it, fast-moving objects appear to teleport between frames.
# Transform blur covers rigid motion; deformation blur covers mesh deformation.

import hou

def configure_motion_blur(
    karma_node_path,
    xformsamples=2,
    geosamples=2,
    shutter_open=-0.5,
    shutter_close=0.5,
    velocity_blur=False
):
    """
    Configure motion blur settings on a Karma LOP node.

    Args:
        karma_node_path: Path to the Karma LOP node
        xformsamples:    Transform motion blur time samples (2 = linear, 3 = curved)
        geosamples:      Deformation motion blur time samples (2-3 for deforming geo)
        shutter_open:    Shutter open time relative to frame (centered: -0.5)
        shutter_close:   Shutter close time relative to frame (centered: 0.5)
        velocity_blur:   Use velocity attribute (@v) for motion blur (faster, less accurate)
    """
    node = hou.node(karma_node_path)
    if node is None:
        raise ValueError(f"Couldn't find Karma node at {karma_node_path!r}")

    # --- Transform samples: covers rigid body / camera / light motion ---
    # 2 = minimum for linear motion. 3 for curved arcs (camera sweeps, etc.)
    node.parm("vm_xformsamples").set(xformsamples)

    # --- Deformation samples: covers skinned meshes, cloth, fluid surfaces ---
    # 2 = adequate for slow deformation. 3 for fast cloth or muscle sim.
    node.parm("vm_geosamples").set(geosamples)

    # --- Shutter range ---
    # Centered (-0.5, 0.5): natural balanced blur, most common for VFX.
    # Trailing (0.0, 1.0): motion smears forward, can look like film exposure.
    # Pick ONE convention per project and never change it mid-sequence.
    node.parm("vm_shutter").set(shutter_open)
    node.parm("vm_shutteroffset").set(shutter_close)

    # --- Velocity-based blur ---
    # Uses @v attribute instead of evaluating geo at multiple time samples.
    # Faster to compute; accurate only for linear motion (no rotation artifacts).
    node.parm("vm_velblur").set(1 if velocity_blur else 0)

    print(f"Motion blur configured on {karma_node_path}")
    print(f"  xformsamples={xformsamples}  geosamples={geosamples}")
    print(f"  shutter=({shutter_open}, {shutter_close})  velocity_blur={velocity_blur}")


# Usage (standard animation setup):
# configure_motion_blur("/stage/karma1", xformsamples=2, geosamples=2)

# Usage (fast deforming cloth, curved camera move):
# configure_motion_blur("/stage/karma1", xformsamples=3, geosamples=3,
#                       shutter_open=-0.5, shutter_close=0.5)

# Usage (velocity-based, pyro or fluid with @v on particles):
# configure_motion_blur("/stage/karma1", velocity_blur=True)
```

### Volume Stability — Configure Step Rate for Consistent Volume Rendering

```python
# Volume rendering flickers when step rate is too coarse or changes per frame.
# The fix: consistent step rate at 0.25 or finer for production animation.
# Shadow step can be coarser (0.5) but must also stay consistent.

import hou

def configure_volume_stability(karma_node_path, step_rate=0.25, shadow_step_rate=0.5):
    """
    Set volume step rates on a Karma LOP node for stable animation rendering.

    Args:
        karma_node_path:  Path to Karma LOP node
        step_rate:        Volume step rate — 0.25 minimum for production (smaller = more accurate)
        shadow_step_rate: Shadow volume step rate — can be 2x coarser than beauty
    """
    node = hou.node(karma_node_path)
    if node is None:
        raise ValueError(f"Couldn't find Karma node at {karma_node_path!r}")

    # vm_volumesteprate: controls how finely volumes are marched.
    # 0.1 = fine (expensive); 0.25 = production minimum; 1.0 = debug only.
    # MUST be identical across every frame in the sequence — changing this
    # mid-sequence causes visible brightness and density shifts.
    node.parm("vm_volumesteprate").set(step_rate)

    # Shadow step can be 2x coarser than beauty for speed, but keep it fixed.
    node.parm("vm_volumeshadowsteprate").set(shadow_step_rate)

    print(f"Volume stability configured on {karma_node_path}")
    print(f"  step_rate={step_rate}  shadow_step_rate={shadow_step_rate}")
    print(f"  Ensure VDB caches use consistent grid bounds across the frame range.")


# Usage (production animation):
# configure_volume_stability("/stage/karma1", step_rate=0.25, shadow_step_rate=0.5)

# Usage (hero shot, full quality):
# configure_volume_stability("/stage/karma1", step_rate=0.1, shadow_step_rate=0.25)
```

### Render Settings Comparison — Single Frame vs Animation

```python
# Compare current Karma render settings against recommended animation values.
# Prints a delta report flagging settings that need adjustment.

import hou

# Recommended settings for each mode
SINGLE_FRAME_SETTINGS = {
    "vm_samples":          32,    # pixel samples (32-64 for stills)
    "vm_volumesteprate":   0.1,   # volume step rate (can be finer for stills)
    "vm_diffuselimit":     2,     # diffuse bounces
    "vm_denoiser":         0,     # denoiser optional for stills
    "vm_xformsamples":     1,     # no motion blur needed for stills
    "vm_geosamples":       1,
}

ANIMATION_SETTINGS = {
    "vm_samples":          64,    # minimum 64 for denoiser input
    "vm_volumesteprate":   0.25,  # production minimum for stable volumes
    "vm_diffuselimit":     4,     # consistent bounces — never adaptive across seq
    "vm_denoiser":         1,     # denoiser recommended (OIDN=1)
    "vm_xformsamples":     2,     # transform motion blur (linear)
    "vm_geosamples":       2,     # deformation motion blur
}

def compare_render_settings(karma_node_path, mode="animation"):
    """
    Compare actual Karma LOP settings against recommended single-frame or animation values.
    Prints deltas where current values fall short of recommendations.

    Args:
        karma_node_path: Path to the Karma LOP node
        mode:            "animation" or "single_frame"
    """
    node = hou.node(karma_node_path)
    if node is None:
        raise ValueError(f"Couldn't find Karma node at {karma_node_path!r}")

    recommended = ANIMATION_SETTINGS if mode == "animation" else SINGLE_FRAME_SETTINGS

    print(f"\n=== Render Settings Audit [{mode}]: {karma_node_path} ===")
    all_ok = True
    for parm_name, target in recommended.items():
        try:
            current = node.evalParm(parm_name)
        except Exception:
            print(f"  [SKIP] {parm_name} — parm not found on this node type")
            continue

        if current < target:
            print(f"  [LOW]  {parm_name}: current={current}  recommended>={target}")
            all_ok = False
        else:
            print(f"  [OK]   {parm_name}: {current}")

    if all_ok:
        print("  All settings meet recommendations.")


# Usage:
# compare_render_settings("/stage/karma1", mode="animation")
# compare_render_settings("/stage/karma1", mode="single_frame")
```

### Validation Workflow — Frame Comparison for Temporal Stability

```python
# Automate the 3-frame and 10-frame validation workflow.
# Renders a short test range and computes per-pixel luminance delta between frames
# to quantitatively measure flicker without needing manual MPlay review.

import hou
import os
import subprocess
import tempfile

def render_validation_range(
    karma_node_path,
    rop_node_path,
    start_frame=48,
    end_frame=50,
    output_dir=None,
    resolution=(320, 240)
):
    """
    Render a short validation range at low resolution to check for temporal instability.
    Low-res (320x240) is fast and sufficient to detect flicker patterns.

    Args:
        karma_node_path: Path to Karma LOP (for settings)
        rop_node_path:   Path to usdrender ROP in /out
        start_frame:     First frame of validation range
        end_frame:       Last frame of validation range
        output_dir:      Directory for output EXRs (defaults to system temp)
        resolution:      Render resolution tuple — keep small for fast iteration
    """
    node = hou.node(karma_node_path)
    rop  = hou.node(rop_node_path)
    if node is None:
        raise ValueError(f"Couldn't find Karma node at {karma_node_path!r}")
    if rop is None:
        raise ValueError(f"Couldn't find ROP node at {rop_node_path!r}")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="synapse_temporal_")

    output_path = os.path.join(output_dir, "validation.$F4.exr")

    # Override resolution for fast validation render
    node.parm("res_overridex").set(resolution[0])
    node.parm("res_overridey").set(resolution[1])

    # Set output path on ROP
    rop.parm("outputimage").set(output_path)
    rop.parm("picture").set(output_path)

    print(f"Rendering frames {start_frame}-{end_frame} at {resolution[0]}x{resolution[1]}")
    print(f"Output: {output_dir}")

    # Render the validation range
    rop.render(frame_range=(start_frame, end_frame, 1))

    print("Validation render complete.")
    print(f"Review in MPlay: flip rapidly between frames to spot flicker.")
    print(f"Or run: compare_frame_luminance('{output_dir}', {start_frame}, {end_frame})")
    return output_dir


def compare_frame_luminance(output_dir, start_frame, end_frame, threshold=0.02):
    """
    Compare consecutive EXR frames by converting to JPEG via iconvert and computing
    average pixel delta. Flags frames where the mean luminance change exceeds threshold.

    Args:
        output_dir:   Directory containing validation.$F4.exr files
        start_frame:  First frame
        end_frame:    Last frame
        threshold:    Mean luminance delta fraction above which a frame is flagged (default 2%)
    """
    hfs = hou.getenv("HFS")
    iconvert = os.path.join(hfs, "bin", "iconvert.exe")

    jpeg_paths = []
    for frame in range(start_frame, end_frame + 1):
        exr_path  = os.path.join(output_dir, f"validation.{frame:04d}.exr")
        jpeg_path = os.path.join(output_dir, f"validation.{frame:04d}.jpg")
        if not os.path.exists(exr_path):
            print(f"  [MISSING] {exr_path}")
            continue
        subprocess.run(
            [iconvert, exr_path, jpeg_path],
            creationflags=0x08000000,  # CREATE_NO_WINDOW on Windows
            check=True
        )
        jpeg_paths.append((frame, jpeg_path))

    if len(jpeg_paths) < 2:
        print("Not enough frames to compare.")
        return

    # Use Python Imaging Library if available for pixel-level delta
    try:
        from PIL import Image, ImageChops
        import statistics

        print(f"\n=== Frame Luminance Delta Report (threshold={threshold*100:.1f}%) ===")
        for i in range(len(jpeg_paths) - 1):
            frame_a, path_a = jpeg_paths[i]
            frame_b, path_b = jpeg_paths[i + 1]
            img_a = Image.open(path_a).convert("L")  # grayscale for luminance
            img_b = Image.open(path_b).convert("L")
            diff  = ImageChops.difference(img_a, img_b)
            pixels = list(diff.getdata())
            mean_delta = statistics.mean(pixels) / 255.0
            flag = "[FLICKER]" if mean_delta > threshold else "[OK]     "
            print(f"  {flag} frame {frame_a}->{frame_b}: mean_delta={mean_delta*100:.2f}%")

    except ImportError:
        # PIL not available — just report file sizes as a proxy for content change
        print("\n=== Frame File Size Delta (PIL not available) ===")
        for i in range(len(jpeg_paths) - 1):
            frame_a, path_a = jpeg_paths[i]
            frame_b, path_b = jpeg_paths[i + 1]
            size_a = os.path.getsize(path_a)
            size_b = os.path.getsize(path_b)
            delta  = abs(size_b - size_a) / max(size_a, 1)
            flag   = "[LARGE DELTA]" if delta > 0.05 else "[OK]         "
            print(f"  {flag} frame {frame_a}->{frame_b}: size_delta={delta*100:.1f}%")


# Full validation workflow:
# 1. Render 3 consecutive frames at low res
# out_dir = render_validation_range("/stage/karma1", "/out/usdrender1",
#                                   start_frame=48, end_frame=50)
# 2. Compare luminance between consecutive frames
# compare_frame_luminance(out_dir, 48, 50, threshold=0.02)
# 3. If clean, expand to 10-frame range before committing to full sequence
# render_validation_range("/stage/karma1", "/out/usdrender1",
#                         start_frame=41, end_frame=50)
```

### Rest Position — Lock Procedural Noise to Object Space

```vex
// Add to a Point Wrangle SOP to bake rest position for stable procedural textures.
// Connect: [input_geo] -> [Wrangle (this code)] -> [downstream shading/displacement]
// The rest attribute freezes the noise seed to the mesh's un-deformed state,
// so the texture doesn't swim as the geometry deforms over time.

// Only compute rest once (frame 1 or when attribute doesn't exist yet).
// In production: run this in a separate SOP before the deformation network.

if (!haspointattrib(0, "rest")) {
    // Write current (un-deformed) position as rest.
    // This must run BEFORE any deformation nodes in the network.
    v@rest = @P;
}

// In your shader or downstream Wrangle, drive noise by @rest instead of @P:
// float noise_val = noise(v@rest * frequency + offset);
// This gives identical noise values per surface point regardless of deformation.
```

## Common Mistakes

- **Using @P for procedural noise on deforming geometry** — noise seeds change every frame as @P changes, causing texture swimming. Fix: add a rest SOP before the deformation chain and use `@rest` in the shader.

- **Adaptive subdivision enabled for animation** — topology changes per frame cause geometry popping. Fix: set `vm_rendersubd` adaptivity to 0 on the Karma node or Subdivision SOP.

- **Switching denoisers mid-sequence** — OIDN and OptiX produce different noise patterns; switching creates a visible cut. Fix: lock to one denoiser at the start of a shot and never change it.

- **Denoising utility AOVs** — denoising depth, normal, or cryptomatte passes introduces artifacts. Fix: denoise only the beauty pass; utility AOVs must remain raw.

- **Volume step rate set to 0.1 for one frame, 0.25 for another** — causes brightness and density shifts between frames. Fix: set one value in `configure_volume_stability()` and apply it to every frame uniformly.

- **Velocity blur on rotating objects** — `@v` linear velocity doesn't account for rotational motion, causing smear artifacts. Fix: use `xformsamples` / `geosamples` multi-sample blur for objects with significant rotation.

- **Committing to full sequence before 10-frame validation** — skips the cheapest catch for flicker. Fix: always run `render_validation_range()` on a 10-frame window and pass `compare_frame_luminance()` before dispatching to the farm.

- **Missing `@v` attribute when velocity_blur=True** — Karma silently skips velocity blur if the attribute is absent, producing no blur. Fix: verify the attribute exists with the VEX diagnostic snippet above before enabling velocity blur.
