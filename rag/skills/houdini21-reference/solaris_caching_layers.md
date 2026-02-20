# Solaris Caching and Layer Management

## Triggers
layer, cache, value clip, geometry clip sequence, usd stitch, optimize cache, static attribute,
usd configure, layer save path, vdb loop, inspect layer, scene graph layers, cache lop,
usd cache, layer break, layer save, save layer, flatten layer, configure layer, active layer,
edit target, layer stack, sublayer cache, stage cache, usd rop cache, per-frame export,
time sample, static vs dynamic, deformation cache, transform cache, animation cache,
geometry cache solaris, vdb sequence, vdb loop lop, value clip lop, clip set, clip manifest,
usd stitch clips, usd flatten, file cache lop, checkpoint, bgeo to usd, sop cache lop,
scene graph details, blue static, green dynamic, inspect active layer, layer contents,
layer identifier, anonymous layer, named layer, root layer, session layer, payload cache,
lazy loading, deferred load, prune, scene graph tree, layer muting, mute layer, contribution,
layer stack inspection, filecache, per-frame usd, topology file, clip metadata,
usd configure sop, dynamic attribute, geometry clip, clip times, frame range cache,
configure layer lop, flatten lop, prune lop, layer break lop

## Context
USD's layer system separates scene description into stackable files with explicit save paths.
In Solaris, each LOP node authors opinions on the active layer, and the layer stack composes
them via LIVRPS strength ordering. Caching workflows export heavy geometry to disk (per-frame
.usd/.bgeo), while Value Clips and Geometry Clip Sequences enable efficient playback of
animated sequences without loading all frames into memory.

## Code

### Layer Concepts -- Active Layer and Layer Stack

```python
# Every LOP chain has an implicit layer stack.
# Each node writes opinions to the active (edit target) layer.
# Layer Break LOP starts a new anonymous layer in the stack.
import hou

def inspect_layer_stack(lop_path="/stage/output0"):
    """Inspect the full layer stack of a LOP node.
    Each layer has an identifier (file path or anonymous tag)
    and contains opinions authored by one or more LOP nodes."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()
    if not stage:
        print("No stage available on this node")
        return

    # Get the full layer stack (strongest to weakest)
    layer_stack = stage.GetLayerStack()
    print(f"Layer stack has {len(layer_stack)} layers:")
    for i, layer in enumerate(layer_stack):
        ident = layer.identifier
        is_anon = layer.anonymous
        num_prims = len(layer.rootPrims)
        tag = " (anonymous)" if is_anon else ""
        print(f"  [{i}] {ident}{tag} -- {num_prims} root prims")

    # Root layer is always the strongest
    root = stage.GetRootLayer()
    print(f"\nRoot layer: {root.identifier}")

    # Session layer holds transient edits (Houdini viewport overrides)
    session = stage.GetSessionLayer()
    print(f"Session layer: {session.identifier}")

    return layer_stack


def inspect_active_layer(lop_path="/stage/output0"):
    """See what the current edit target layer contains.
    This shows exactly what the current LOP node is authoring."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()
    edit_target = stage.GetEditTarget()
    layer = edit_target.GetLayer()

    print(f"Active layer: {layer.identifier}")
    print(f"Anonymous: {layer.anonymous}")

    # Export layer contents as USDA text for inspection
    usda_text = layer.ExportToString()
    print(f"\n--- Layer Contents ({len(usda_text)} chars) ---")
    print(usda_text[:2000])  # truncate for readability
    if len(usda_text) > 2000:
        print(f"... ({len(usda_text) - 2000} more chars)")

    return layer


# Usage
inspect_layer_stack("/stage/output0")
inspect_active_layer("/stage/output0")
```

### Setting Layer Save Paths

```python
# Layers without save paths are anonymous (in-memory only).
# Anonymous layers lose data on scene close.
# Configure Layer LOP sets the save location for a layer.
import hou

def create_configure_layer(parent="/stage", save_dir="$HIP/usd/",
                           layer_name="geo_cache", flatten=False):
    """Create a Configure Layer LOP to set a save path on the active layer.
    Convention: save heavy geo layers to $HIP/usd/ directory."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    config = stage.createNode("configurelayer", f"config_{layer_name}")

    # Set the save path for this layer
    # $HIP expands to the .hip file directory at render/save time
    save_path = f"{save_dir}{layer_name}.usd"
    config.parm("savepath").set(save_path)

    # Optionally set the default prim
    # config.parm("setdefaultprim").set(True)
    # config.parm("defaultprim").set("/World")

    print(f"Configure Layer: save path = {save_path}")
    return config


def create_layer_break(parent="/stage", name="layer_break"):
    """Create a Layer Break LOP to start a new layer in the stack.
    Essential before heavy sections -- without a Layer Break,
    the entire chain writes to a single layer."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    layer_break = stage.createNode("layerbreak", name)
    print(f"Layer Break created: {layer_break.path()}")
    return layer_break


# Build a layered pipeline: geometry -> break -> lights -> break -> materials
# Each section gets its own layer that can be saved independently
stage = hou.node("/stage")
geo_config = create_configure_layer("/stage", "$HIP/usd/", "geometry")
geo_break = create_layer_break("/stage", "break_after_geo")
light_config = create_configure_layer("/stage", "$HIP/usd/", "lighting")
light_break = create_layer_break("/stage", "break_after_lights")
mat_config = create_configure_layer("/stage", "$HIP/usd/", "materials")
```

### Cache LOP -- File Cache for LOPs

```python
# The File Cache LOP (called "filecache" in H21) saves the stage
# state to .usd files on disk. Equivalent to SOP File Cache but
# for the USD stage.
import hou

def create_lop_file_cache(parent="/stage", output_dir="$HIP/usd/cache/",
                          name="filecache_geo", frame_range=None):
    """Create a File Cache LOP for caching USD stage to disk.
    Saves per-frame .usd files for animated content,
    or a single .usd for static content."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    cache = stage.createNode("filecache", name)

    # Output file path -- $F4 for per-frame (0001, 0002, ...)
    output_path = f"{output_dir}{name}.$F4.usd"
    cache.parm("file").set(output_path)

    # Set frame range if provided, otherwise use scene range
    if frame_range:
        start, end = frame_range
        cache.parm("trange").set("normal")  # "off" = current frame only
        cache.parm("f1").set(start)
        cache.parm("f2").set(end)
        cache.parm("f3").set(1)  # frame step
    else:
        cache.parm("trange").set("off")  # single frame (static)

    # File format: "usd" auto-detects binary/ascii from extension
    # Use .usdc for binary (smaller, faster), .usda for human-readable
    # cache.parm("fileformat").set("binary")  # default

    print(f"File Cache LOP: {output_path}")
    print(f"  Frame range: {frame_range or 'static (current frame)'}")
    return cache


def load_cached_usd(parent="/stage", cache_path="$HIP/usd/cache/filecache_geo.0001.usd",
                    method="sublayer"):
    """Load a cached USD file back into the stage.
    Use sublayer for full stage merges, reference for individual assets."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    if method == "sublayer":
        loader = stage.createNode("sublayer", "load_cache")
        loader.parm("filepath1").set(cache_path)
    elif method == "reference":
        loader = stage.createNode("reference", "load_cache")
        loader.parm("filepath1").set(cache_path)
        loader.parm("primpath").set("/cache")

    print(f"Loaded cache via {method}: {cache_path}")
    return loader


# Cache animated geometry
cache_node = create_lop_file_cache("/stage", "$HIP/usd/cache/", "hero_geo", (1001, 1100))

# Cache static environment (single frame)
env_cache = create_lop_file_cache("/stage", "$HIP/usd/cache/", "environment_static")
```

### USD ROP Per-Frame Export

```python
# The usdrender ROP in /out exports per-frame .usd files from a LOP network.
# This is the standard way to write USD to disk from a Solaris pipeline.
import hou

def create_usd_rop(lop_path="/stage/output0", output_dir="$HIP/usd/export/",
                   name="usd_export", frame_range=(1001, 1100)):
    """Create a USD ROP in /out for per-frame USD export.
    Set loppath to point at the LOP network output node."""
    out = hou.node("/out")
    if not out:
        print("Couldn't find /out network")
        return

    rop = out.createNode("usd", name)

    # Point to the LOP network output
    rop.parm("loppath").set(lop_path)

    # Output path with $F4 frame token for per-frame files
    output_path = f"{output_dir}{name}.$F4.usd"
    rop.parm("lopoutput").set(output_path)

    # Frame range
    rop.parm("trange").set("normal")
    rop.parm("f1").set(frame_range[0])
    rop.parm("f2").set(frame_range[1])
    rop.parm("f3").set(1)

    # Strip layers above the specified LOP -- flattens output
    # rop.parm("striplayerbreaks").set(True)

    print(f"USD ROP: {rop.path()}")
    print(f"  LOP path: {lop_path}")
    print(f"  Output: {output_path}")
    print(f"  Frames: {frame_range[0]}-{frame_range[1]}")
    return rop


def render_usd_rop(rop_path="/out/usd_export", frame_range=None):
    """Execute the USD ROP to write files to disk.
    Use frame_range tuple to override the ROP's built-in range."""
    rop = hou.node(rop_path)
    if not rop:
        print(f"Couldn't find ROP at {rop_path}")
        return

    if frame_range:
        rop.render(frame_range=(frame_range[0], frame_range[1], 1))
    else:
        rop.render()

    print(f"USD export complete: {rop_path}")


# Create and execute per-frame USD export
rop = create_usd_rop("/stage/output0", "$HIP/usd/export/", "shot_010", (1001, 1100))
# render_usd_rop("/out/shot_010")  # uncomment to execute
```

### Value Clip LOP -- Animated Sequence Playback

```python
# Value Clips split a time-varying layer into per-frame files.
# Only the current frame's file is loaded into memory at any time.
# Huge memory savings for VDB sequences, deforming geometry, simulations.
import hou

def create_value_clip(parent="/stage", clip_dir="$HIP/usd/cache/",
                      clip_pattern="hero_geo.####.usd",
                      prim_path="/World/geo/hero",
                      frame_range=(1001, 1100),
                      name="valueclip_hero"):
    """Set up Value Clips for per-frame USD playback.
    The clip path pattern uses #### for frame numbers.
    Only the active frame is loaded -- massive memory savings."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    clip = stage.createNode("valueclip", name)

    # Prim path that the clips apply to
    clip.parm("primpath").set(prim_path)

    # Clip asset path pattern (#### expands to frame numbers)
    clip_path = f"{clip_dir}{clip_pattern}"
    clip.parm("clipassetpaths").set(clip_path)

    # Active time range -- when clips are valid
    clip.parm("clipactive1").set(frame_range[0])
    clip.parm("clipactive2").set(frame_range[1])

    # Clip times -- mapping from stage time to clip file time
    # Default: 1:1 mapping (stage frame 1001 -> clip frame 1001)
    clip.parm("cliptimes1").set(frame_range[0])
    clip.parm("cliptimes2").set(frame_range[1])

    # Clip set name (for multiple clip sets on the same prim)
    clip.parm("clipsetname").set("default")

    print(f"Value Clip: {clip_path}")
    print(f"  Prim: {prim_path}")
    print(f"  Active range: {frame_range[0]}-{frame_range[1]}")
    return clip


def create_value_clip_with_offset(parent="/stage", clip_dir="$HIP/usd/cache/",
                                  clip_pattern="explosion.####.usd",
                                  prim_path="/World/fx/explosion",
                                  source_range=(1, 100),
                                  stage_range=(1050, 1149),
                                  name="valueclip_offset"):
    """Value Clip with time offset -- map source clip frames to different stage times.
    Useful for retiming or offsetting cached sequences."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    clip = stage.createNode("valueclip", name)
    clip.parm("primpath").set(prim_path)
    clip.parm("clipassetpaths").set(f"{clip_dir}{clip_pattern}")

    # Stage time range (when the clip is active on the timeline)
    clip.parm("clipactive1").set(stage_range[0])
    clip.parm("clipactive2").set(stage_range[1])

    # Clip times -- maps stage_range[0] -> source_range[0], etc.
    clip.parm("cliptimes1").set(source_range[0])
    clip.parm("cliptimes2").set(source_range[1])

    print(f"Value Clip with offset: stage {stage_range} -> source {source_range}")
    return clip


# Standard value clip setup
clip = create_value_clip("/stage", "$HIP/usd/cache/", "hero_deform.####.usd",
                         "/World/geo/hero", (1001, 1100))

# Offset: source frames 1-100 play at stage frames 1050-1149
clip_offset = create_value_clip_with_offset(
    "/stage", "$HIP/usd/cache/", "explosion.####.usd",
    "/World/fx/explosion", (1, 100), (1050, 1149))
```

### Geometry Clip Sequence LOP (H21)

```python
# New in Houdini 21 -- purpose-built for geometry cache playback.
# Simpler than Value Clips for common cases (sequential frame files).
# Handles topology files and clip manifests automatically.
import hou

def create_geometry_clip_sequence(parent="/stage",
                                  sequence_dir="$HIP/usd/cache/",
                                  file_pattern="sim_geo.####.usd",
                                  prim_path="/World/geo/sim",
                                  frame_range=(1001, 1100),
                                  loop_mode="none",
                                  name="geoclipseq"):
    """Create a Geometry Clip Sequence node for cached playback.
    Simpler than Value Clips -- just point at a sequence of files.
    loop_mode: 'none', 'loop', 'pingpong'."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    geo_clip = stage.createNode("geometryclipsequence", name)

    # File pattern for the sequence
    geo_clip.parm("filepath").set(f"{sequence_dir}{file_pattern}")

    # Prim path to create/apply the clip to
    geo_clip.parm("primpath").set(prim_path)

    # Frame range
    geo_clip.parm("startframe").set(frame_range[0])
    geo_clip.parm("endframe").set(frame_range[1])

    # Loop mode for sequences that should repeat
    loop_modes = {"none": 0, "loop": 1, "pingpong": 2}
    geo_clip.parm("loopmode").set(loop_modes.get(loop_mode, 0))

    print(f"Geometry Clip Sequence: {sequence_dir}{file_pattern}")
    print(f"  Prim: {prim_path}")
    print(f"  Frames: {frame_range[0]}-{frame_range[1]}")
    print(f"  Loop: {loop_mode}")
    return geo_clip


# Deforming character sequence
char_clip = create_geometry_clip_sequence(
    "/stage", "$HIP/usd/cache/", "character_anim.####.usd",
    "/World/geo/character", (1001, 1200), "none")

# Looping pyro simulation
pyro_clip = create_geometry_clip_sequence(
    "/stage", "$HIP/usd/cache/", "pyro_loop.####.usd",
    "/World/fx/pyro", (1, 120), "loop")
```

### VDB Sequence Looping

```python
# Import VDB sequences into Solaris and loop them using Value Clips.
# Common for pyro, clouds, fog volumes that need to cycle.
import hou

def setup_vdb_loop(parent="/stage",
                   vdb_dir="$HIP/vdb/",
                   vdb_pattern="smoke.####.vdb",
                   prim_path="/World/fx/smoke",
                   source_frames=(1, 120),
                   stage_range=(1001, 1480),
                   name="vdb_loop"):
    """Set up a looping VDB sequence via SOP Import + Value Clips.
    source_frames: the frame range in the VDB file sequence.
    stage_range: where on the timeline the loop plays.
    The clip times wrap around to create seamless looping."""
    stage_node = hou.node(parent)
    if not stage_node:
        print(f"Couldn't find node at {parent}")
        return

    # Step 1: SOP Import to bring VDB into Solaris
    sop_import = stage_node.createNode("sopimport", f"import_{name}")
    sop_import.parm("soppath").set(f"/obj/geo1/file_vdb")  # point to SOP file node
    sop_import.parm("primpath").set(prim_path)

    # Step 2: Value Clip for looping
    clip = stage_node.createNode("valueclip", f"clip_{name}")
    clip.parm("primpath").set(prim_path)

    # For looping: set clip times to cycle through source range
    # Stage time 1001 -> clip time 1, stage time 1120 -> clip time 120,
    # stage time 1121 -> clip time 1 (loop), etc.
    src_start, src_end = source_frames
    src_duration = src_end - src_start + 1
    stg_start, stg_end = stage_range

    clip.parm("clipactive1").set(stg_start)
    clip.parm("clipactive2").set(stg_end)

    # Map cyclically: use multiple time entries for loop points
    # Each loop restart maps back to source start
    num_loops = (stg_end - stg_start + 1) // src_duration
    print(f"VDB loop: {num_loops} loops of {src_duration} frames")
    print(f"  Source: {source_frames}, Stage: {stage_range}")

    # Wire: import -> clip
    clip.setInput(0, sop_import)

    return clip


def cache_vdb_to_usd(sop_path="/obj/geo1/file_vdb", output_dir="$HIP/usd/vdb/",
                     name="smoke_vol", frame_range=(1, 120)):
    """Cache VDB SOP geometry to per-frame USD for efficient Solaris loading.
    Avoids re-cooking the SOP network every frame."""
    obj = hou.node("/obj/geo1")
    if not obj:
        print("Couldn't find /obj/geo1")
        return

    # Use a ROP Geometry Output to write .usd per frame
    out = hou.node("/out")
    rop = out.createNode("usd", f"cache_{name}")
    rop.parm("loppath").set("/stage/sopimport_vdb")
    rop.parm("lopoutput").set(f"{output_dir}{name}.$F4.usd")
    rop.parm("trange").set("normal")
    rop.parm("f1").set(frame_range[0])
    rop.parm("f2").set(frame_range[1])

    print(f"VDB cache ROP: {rop.path()}")
    print(f"  Output: {output_dir}{name}.$F4.usd")
    return rop


# Set up looping smoke VDB
vdb_loop = setup_vdb_loop("/stage", "$HIP/vdb/", "smoke.####.vdb",
                          "/World/fx/smoke", (1, 120), (1001, 1480))
```

### UsdConfigure SOP -- Static vs Dynamic Optimization

```python
# In SOPs, before importing to Solaris, mark attributes as static or dynamic.
# Static attributes (UVs, topology, materials) are written once.
# Dynamic attributes (P, N, velocity) are written per-frame.
# This can reduce cache sizes dramatically (e.g., 170MB -> 30MB).
import hou

def configure_static_dynamic(sop_path="/obj/geo1/OUT",
                             static_attrs=None,
                             dynamic_attrs=None,
                             name="usdconfigure"):
    """Add a UsdConfigure SOP to optimize which attributes are time-sampled.
    Static attributes: written once (UVs, topology, rest position).
    Dynamic attributes: written per-frame (P, N, v).

    Without this, ALL attributes are written every frame = huge files."""
    geo = hou.node(sop_path)
    if not geo:
        print(f"Couldn't find SOP at {sop_path}")
        return

    parent = geo.parent()
    config = parent.createNode("usdconfigure", name)
    config.setInput(0, geo)

    # Default static attributes (written once, save massive space)
    if static_attrs is None:
        static_attrs = ["uv", "shop_materialpath", "rest", "id",
                        "name", "pscale"]  # topology is always static

    # Default dynamic attributes (time-sampled per frame)
    if dynamic_attrs is None:
        dynamic_attrs = ["P", "N", "v", "Cd"]

    # Set static attributes (space-separated list)
    config.parm("staticattribs").set(" ".join(static_attrs))

    # Set dynamic attributes
    config.parm("dynamicattribs").set(" ".join(dynamic_attrs))

    # Explicitly mark transform as static or dynamic
    # config.parm("transformmode").set("static")  # or "dynamic"

    print(f"UsdConfigure: {config.path()}")
    print(f"  Static: {', '.join(static_attrs)}")
    print(f"  Dynamic: {', '.join(dynamic_attrs)}")
    print("  Expected savings: static attrs written 1x instead of per-frame")
    return config


def verify_time_samples(lop_path="/stage/output0", prim_path="/World/geo/hero"):
    """Check which attributes have time samples (dynamic) vs single value (static).
    In Scene Graph Details: Blue = static, Green = dynamic."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        print(f"Couldn't find prim at {prim_path}")
        return

    print(f"Time sample analysis for {prim_path}:")
    for attr in prim.GetAttributes():
        num_samples = attr.GetNumTimeSamples()
        if num_samples > 0:
            print(f"  [DYNAMIC] {attr.GetName()}: {num_samples} time samples")
        else:
            val = attr.Get()
            print(f"  [STATIC]  {attr.GetName()}: single value")


# Optimize a character mesh: only P and N are dynamic
config = configure_static_dynamic(
    "/obj/geo1/character_OUT",
    static_attrs=["uv", "rest", "id", "shop_materialpath", "pscale"],
    dynamic_attrs=["P", "N", "v"])

# Verify after caching
# verify_time_samples("/stage/output0", "/World/geo/hero")
```

### UsdStitch and UsdStitchClips (Command Line)

```python
# usdstitch: merges per-frame USD files into a single time-sampled file.
# usdstitchclips: creates value clip metadata from per-frame files.
# These are command-line tools from the USD toolset ($HFS/bin/).
import hou
import subprocess
import os

def run_usd_stitch(frame_files, output_path, hfs=None):
    """Run usdstitch to merge per-frame USD files into one time-sampled file.
    Useful for creating a single file from a cache sequence.

    WARNING: Output file can be very large for long sequences.
    For large sequences, prefer usdstitchclips (value clips) instead."""
    if hfs is None:
        hfs = os.environ.get("HFS", "C:/Program Files/Side Effects Software/Houdini 21.0.596")

    usdstitch = os.path.join(hfs, "bin", "usdstitch")

    cmd = [usdstitch] + frame_files + ["-o", output_path]
    print(f"Running: {' '.join(cmd[:3])} ... -o {output_path}")
    print(f"  Input files: {len(frame_files)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Stitched {len(frame_files)} frames -> {output_path}")
    else:
        print(f"usdstitch failed: {result.stderr}")

    return result.returncode == 0


def run_usd_stitch_clips(frame_dir, file_pattern, output_path,
                         clip_set_name="default", hfs=None):
    """Run usdstitchclips to create value clip metadata from per-frame files.
    Creates three files:
      - topology.usd (shared topology, written once)
      - manifest.usd (clip manifest listing all frames)
      - output.usd (the main file with clip metadata)

    This is the preferred method for large sequences -- only loads one frame at a time."""
    if hfs is None:
        hfs = os.environ.get("HFS", "C:/Program Files/Side Effects Software/Houdini 21.0.596")

    usdstitchclips = os.path.join(hfs, "bin", "usdstitchclips")

    # Collect frame files matching the pattern
    import glob
    pattern = os.path.join(frame_dir, file_pattern.replace("####", "*"))
    frame_files = sorted(glob.glob(pattern))

    if not frame_files:
        print(f"No files matching {pattern}")
        return False

    cmd = [usdstitchclips,
           "--clipSet", clip_set_name,
           "--out", output_path] + frame_files

    print(f"Running usdstitchclips:")
    print(f"  Input: {len(frame_files)} files from {frame_dir}")
    print(f"  Output: {output_path}")
    print(f"  Clip set: {clip_set_name}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Created clip metadata: {output_path}")
        # Topology and manifest files are created alongside
        topo_path = output_path.replace(".usd", ".topology.usd")
        manifest_path = output_path.replace(".usd", ".manifest.usd")
        print(f"  Topology: {topo_path}")
        print(f"  Manifest: {manifest_path}")
    else:
        print(f"usdstitchclips failed: {result.stderr}")

    return result.returncode == 0


# Stitch 100 frames into one file (small sequences only)
# frame_files = [f"$HIP/usd/cache/geo.{str(f).zfill(4)}.usd" for f in range(1001, 1101)]
# run_usd_stitch(frame_files, "$HIP/usd/geo_combined.usd")

# Create value clips from per-frame cache (preferred for large sequences)
# run_usd_stitch_clips("$HIP/usd/cache/", "hero_deform.####.usd",
#                      "$HIP/usd/hero_clipped.usd")
```

### Layered Cache Strategy -- Static + Animation Separation

```python
# The most efficient caching strategy: separate static and dynamic data.
# Export static geometry (topology, UVs, materials) once.
# Export dynamic attributes (P, N, velocity) per-frame as value clips.
# Sublayer static, value-clip dynamic. Massive file size savings.
import hou

def build_layered_cache_pipeline(parent="/stage",
                                 geo_lop_path="/stage/sopimport_hero",
                                 output_dir="$HIP/usd/cache/",
                                 asset_name="hero",
                                 prim_path="/World/geo/hero",
                                 frame_range=(1001, 1100)):
    """Build a complete layered caching pipeline:
    1. Static layer: topology, UVs, materials (one file, no time samples)
    2. Dynamic layer: P, N, velocity (per-frame value clips)
    3. Assembly: sublayer static + value-clip dynamic"""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    nodes = {}

    # --- Phase 1: Static cache (single frame, constant attributes) ---
    # Layer Break before static section
    nodes["break_pre_static"] = stage.createNode("layerbreak", "break_pre_static")

    # Configure layer with save path for static data
    nodes["config_static"] = stage.createNode("configurelayer", "config_static")
    nodes["config_static"].parm("savepath").set(
        f"{output_dir}{asset_name}_static.usd")

    # File Cache for static -- single frame, no time samples
    nodes["cache_static"] = stage.createNode("filecache", f"cache_{asset_name}_static")
    nodes["cache_static"].parm("file").set(
        f"{output_dir}{asset_name}_static.usd")
    nodes["cache_static"].parm("trange").set("off")  # single frame

    # --- Phase 2: Dynamic cache (per-frame, time-varying attributes) ---
    nodes["break_pre_dynamic"] = stage.createNode("layerbreak", "break_pre_dynamic")

    nodes["config_dynamic"] = stage.createNode("configurelayer", "config_dynamic")
    nodes["config_dynamic"].parm("savepath").set(
        f"{output_dir}{asset_name}_anim.$F4.usd")

    # File Cache for dynamic -- per-frame with $F4 token
    nodes["cache_dynamic"] = stage.createNode("filecache", f"cache_{asset_name}_anim")
    nodes["cache_dynamic"].parm("file").set(
        f"{output_dir}{asset_name}_anim.$F4.usd")
    nodes["cache_dynamic"].parm("trange").set("normal")
    nodes["cache_dynamic"].parm("f1").set(frame_range[0])
    nodes["cache_dynamic"].parm("f2").set(frame_range[1])

    # --- Phase 3: Assembly -- combine static + dynamic ---
    nodes["break_assembly"] = stage.createNode("layerbreak", "break_assembly")

    # Sublayer the static geometry
    nodes["sub_static"] = stage.createNode("sublayer", f"load_{asset_name}_static")
    nodes["sub_static"].parm("filepath1").set(
        f"{output_dir}{asset_name}_static.usd")

    # Value Clip the dynamic attributes
    nodes["clip_dynamic"] = stage.createNode("valueclip", f"clip_{asset_name}_anim")
    nodes["clip_dynamic"].parm("primpath").set(prim_path)
    nodes["clip_dynamic"].parm("clipassetpaths").set(
        f"{output_dir}{asset_name}_anim.####.usd")
    nodes["clip_dynamic"].parm("clipactive1").set(frame_range[0])
    nodes["clip_dynamic"].parm("clipactive2").set(frame_range[1])
    nodes["clip_dynamic"].parm("cliptimes1").set(frame_range[0])
    nodes["clip_dynamic"].parm("cliptimes2").set(frame_range[1])

    # Wire the assembly chain
    nodes["clip_dynamic"].setInput(0, nodes["sub_static"])

    print(f"Layered cache pipeline for '{asset_name}':")
    print(f"  Static: {output_dir}{asset_name}_static.usd (one file)")
    print(f"  Dynamic: {output_dir}{asset_name}_anim.####.usd (per-frame)")
    print(f"  Assembly: sublayer static + value-clip dynamic")
    print(f"  Prim: {prim_path}")
    print(f"  Frames: {frame_range[0]}-{frame_range[1]}")
    return nodes


# Build the full layered cache pipeline for a hero character
nodes = build_layered_cache_pipeline(
    "/stage", "/stage/sopimport_hero", "$HIP/usd/cache/",
    "hero_character", "/World/geo/hero", (1001, 1200))
```

### Scene Graph Debugging Tools

```python
# Houdini 21 provides three key panels for USD debugging:
# - Scene Graph Tree: browse USD hierarchy
# - Scene Graph Layers: see all layers and their strengths
# - Scene Graph Details: inspect prim properties
#   Blue = static (no time samples), Green = dynamic (time-sampled)
import hou

def debug_scene_graph(lop_path="/stage/output0"):
    """Print a comprehensive scene graph debug report.
    Replicates what the Scene Graph panels show."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()
    if not stage:
        print("No stage available")
        return

    # --- Scene Graph Tree (prim hierarchy) ---
    print("=" * 60)
    print("SCENE GRAPH TREE")
    print("=" * 60)
    for prim in stage.Traverse():
        depth = len(str(prim.GetPath()).split("/")) - 1
        indent = "  " * depth
        type_name = prim.GetTypeName() or "Scope"
        active = "" if prim.IsActive() else " [INACTIVE]"
        print(f"{indent}{prim.GetName()} ({type_name}){active}")

    # --- Scene Graph Layers ---
    print("\n" + "=" * 60)
    print("SCENE GRAPH LAYERS")
    print("=" * 60)
    layer_stack = stage.GetLayerStack()
    for i, layer in enumerate(layer_stack):
        strength = "ROOT" if i == 0 else f"sublayer [{i}]"
        anon_tag = " [anonymous]" if layer.anonymous else ""
        save_path = ""
        if not layer.anonymous:
            save_path = f" -> {layer.realPath}"
        print(f"  [{i}] {strength}: {layer.identifier}{anon_tag}{save_path}")

        # Show what prims this layer defines
        for root_prim in layer.rootPrims:
            print(f"       defines: /{root_prim.name}")

    # --- Muted layers ---
    muted = stage.GetMutedLayers()
    if muted:
        print(f"\n  MUTED LAYERS ({len(muted)}):")
        for m in muted:
            print(f"    - {m}")

    return stage


def debug_prim_details(lop_path="/stage/output0", prim_path="/World/geo/hero"):
    """Inspect a single prim's properties in detail.
    Shows which attributes are static vs dynamic (time-sampled).
    In Scene Graph Details panel: Blue = static, Green = dynamic."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        print(f"Couldn't find prim at {prim_path}")
        return

    print(f"PRIM DETAILS: {prim_path}")
    print(f"  Type: {prim.GetTypeName()}")
    print(f"  Active: {prim.IsActive()}")
    print(f"  Defined: {prim.IsDefined()}")
    print(f"  Has payload: {prim.HasPayload()}")

    # Composition arcs
    prim_index = prim.GetPrimIndex()
    print(f"\n  COMPOSITION:")
    for node_ref in prim_index.rootNode.children:
        print(f"    Arc: {node_ref.arcType}, Layer: {node_ref.layerStack.identifier}")

    # Attributes with time sample info
    print(f"\n  ATTRIBUTES:")
    attrs = prim.GetAttributes()
    static_count = 0
    dynamic_count = 0

    for attr in sorted(attrs, key=lambda a: a.GetName()):
        num_samples = attr.GetNumTimeSamples()
        if num_samples > 0:
            dynamic_count += 1
            tag = f"[GREEN/DYNAMIC] {num_samples} time samples"
        else:
            static_count += 1
            tag = "[BLUE/STATIC] no time samples"

        val = attr.Get()
        val_str = str(val)[:60] if val is not None else "None"
        print(f"    {attr.GetName()}: {tag} = {val_str}")

    print(f"\n  Summary: {static_count} static, {dynamic_count} dynamic attributes")
    if dynamic_count > 0:
        print("  TIP: Accidentally-dynamic attrs waste disk space. Use UsdConfigure SOP")
        print("       to mark constant attrs as static before caching.")

    return prim


def mute_layer(lop_path="/stage/output0", layer_identifier=None):
    """Mute a layer -- temporarily disables its opinions without removing it.
    Non-destructive: muted layers can be unmuted at any time.
    Useful for debugging which layer contributes which opinions."""
    node = hou.node(lop_path)
    if not node:
        print(f"Couldn't find node at {lop_path}")
        return

    stage = node.stage()

    if layer_identifier:
        stage.MuteLayer(layer_identifier)
        print(f"Muted layer: {layer_identifier}")
    else:
        # Show all layers so user can pick one
        print("Available layers to mute:")
        for i, layer in enumerate(stage.GetLayerStack()):
            muted = " [MUTED]" if layer.identifier in stage.GetMutedLayers() else ""
            print(f"  [{i}] {layer.identifier}{muted}")


# Debug the full scene graph
debug_scene_graph("/stage/output0")

# Inspect a specific prim
debug_prim_details("/stage/output0", "/World/geo/hero")
```

### Flatten and Prune

```python
# Flatten LOP: collapse the entire layer stack into a single layer.
# Prune LOP: remove prims from the stage (destructive).
# Both are useful for export cleanup but lose composition structure.
import hou

def create_flatten_stage(parent="/stage", name="flatten_for_export"):
    """Create a Flatten LOP to collapse the layer stack into one layer.
    Use before final export when you want a single self-contained file.

    WARNING: Flattening bakes all opinions and removes composition structure.
    You lose the ability to override via stronger layers.
    Only flatten for final delivery, not during active development."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    flatten = stage.createNode("flatten", name)

    # Flatten mode options:
    # "flatten_all" - collapse everything into one layer
    # "flatten_stage" - flatten composed stage (default)
    flatten.parm("flattenmode").set("flatten_stage")

    print(f"Flatten LOP: {flatten.path()}")
    print("  WARNING: Loses composition structure. Use for final export only.")
    return flatten


def create_prune(parent="/stage", prim_patterns=None, name="prune_cleanup"):
    """Create a Prune LOP to remove prims from the stage.
    Use for cleanup before export -- remove construction geometry,
    debug visualizers, or helper prims.

    WARNING: Prune is destructive. Pruned prims cannot be recovered
    without re-composing from source layers."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    prune = stage.createNode("prune", name)

    if prim_patterns is None:
        prim_patterns = ["/World/debug/*", "/World/construction/*"]

    # Set the prim pattern to prune (space-separated for multiple)
    prune.parm("primpattern").set(" ".join(prim_patterns))

    # Prune method: "deactivate" (reversible) or "remove" (permanent)
    # Deactivate is safer -- prims are hidden but still in the layer
    prune.parm("method").set("deactivate")

    print(f"Prune LOP: {prune.path()}")
    print(f"  Patterns: {prim_patterns}")
    print(f"  Method: deactivate (reversible)")
    return prune


def export_flattened_usd(parent="/stage", output_path="$HIP/usd/final/shot_010.usd",
                         prune_patterns=None):
    """Full export pipeline: prune -> flatten -> configure layer -> file cache.
    Produces a clean, self-contained USD file for delivery."""
    stage = hou.node(parent)
    if not stage:
        print(f"Couldn't find node at {parent}")
        return

    nodes = []

    # Step 1: Prune unwanted prims
    if prune_patterns:
        prune = create_prune(parent, prune_patterns, "prune_export")
        nodes.append(prune)

    # Step 2: Flatten the layer stack
    flatten = create_flatten_stage(parent, "flatten_export")
    nodes.append(flatten)

    # Step 3: Configure the output layer path
    config = stage.createNode("configurelayer", "config_export")
    config.parm("savepath").set(output_path)
    nodes.append(config)

    # Step 4: File Cache to write the final file
    cache = stage.createNode("filecache", "export_final")
    cache.parm("file").set(output_path)
    cache.parm("trange").set("off")  # single frame for static export
    nodes.append(cache)

    # Wire the chain
    for i in range(1, len(nodes)):
        nodes[i].setInput(0, nodes[i - 1])

    print(f"Export pipeline: prune -> flatten -> configure -> cache")
    print(f"  Output: {output_path}")
    return nodes


# Flatten for delivery
flatten = create_flatten_stage("/stage")

# Prune debug geometry
prune = create_prune("/stage", ["/World/debug/*", "/World/helpers/*"])

# Full export pipeline
export_flattened_usd("/stage", "$HIP/usd/delivery/shot_010_final.usd",
                     ["/World/debug/*", "/World/construction/*"])
```

### Gotchas

```python
# Common pitfalls with Solaris caching and layer management.
# Reference this when debugging cache issues.
import hou

# GOTCHA 1: Anonymous layers lose data on scene close
# Always set save paths for important layers
def check_anonymous_layers(lop_path="/stage/output0"):
    """Warn about anonymous layers that will lose data on save/close."""
    node = hou.node(lop_path)
    if not node:
        return

    stage = node.stage()
    warnings = []
    for layer in stage.GetLayerStack():
        if layer.anonymous and len(layer.rootPrims) > 0:
            warnings.append(
                f"Anonymous layer has {len(layer.rootPrims)} prims: "
                f"{layer.identifier} -- will be LOST on close!")

    if warnings:
        print("WARNING: Anonymous layers with data:")
        for w in warnings:
            print(f"  {w}")
        print("FIX: Add Configure Layer LOP with a save path")
    else:
        print("All layers with data have save paths (OK)")


# GOTCHA 2: Value Clips require consistent topology
# All frames must have the same prim paths and attribute set.
# If frame 50 adds an attribute that frame 1 doesn't have, clips break.

# GOTCHA 3: File Cache path must include $F4 for per-frame output
# Without $F4, all frames overwrite the same file.
# Correct:   $HIP/usd/cache/geo.$F4.usd
# Wrong:     $HIP/usd/cache/geo.usd (single file, frames overwrite)

# GOTCHA 4: Layer Break is essential before heavy sections
# Without Layer Breaks, the entire LOP chain writes to one layer.
# This means you can't save sections independently or debug per-layer.

# GOTCHA 5: Muting vs deleting layers
# Muting: non-destructive, temporarily hides opinions (safe for debugging)
# Deleting/pruning: permanent, cannot recover without re-composing
# Always try muting first when debugging layer issues.

# GOTCHA 6: bgeo via SOP Import cooks every frame
# If you SOP Import heavy geometry, it re-cooks each frame even if static.
# FIX: Cache to USD on disk first, then reference/sublayer the .usd file.
def check_sop_import_performance(parent="/stage"):
    """Find SOP Import nodes that may be cooking every frame unnecessarily."""
    stage = hou.node(parent)
    if not stage:
        return

    for child in stage.allSubChildren():
        if child.type().name() == "sopimport":
            sop_path = child.parm("soppath").eval()
            print(f"SOP Import: {child.path()} -> {sop_path}")
            print(f"  TIP: If static geo, cache to USD first for better performance")


# GOTCHA 7: Scene Graph Details color coding
# Blue = static (no time samples) = GOOD for constant data
# Green = dynamic (has time samples) = expected for animated attrs
# If you see Green on UVs or topology -> accidentally time-sampled -> wasteful
# FIX: Use UsdConfigure SOP to mark those attrs as static

# GOTCHA 8: Flatten destroys composition
# After flattening, you cannot override with stronger layers.
# Only flatten for final delivery, never in the middle of a pipeline.

check_anonymous_layers("/stage/output0")
check_sop_import_performance("/stage")
```
