# DOP Checkpoint and Recovery

## Triggers
dop checkpoint, simulation cache, sim file, resume simulation, checkpoint interval,
cache simulation, simulation recovery, .sim file, restart simulation

## Context
Long simulations should use checkpoints (`.sim` files) to enable resumption after crashes or parameter tweaks. Configure checkpoint intervals on the DOP network. Use File Cache SOP for post-sim geometry caching with `$F` frame padding.

## Code

```python
# Configure checkpoint saving on DOP network
import hou
import os

dop_net = hou.node("/obj/dopnet1")

# Enable checkpointing
dop_net.parm("cacheenabled").set(1)

# Checkpoint directory
cache_dir = hou.text.expandString("$HIP/sim_cache/rbd")
os.makedirs(cache_dir, exist_ok=True)

# Set cache path — use $SF (simulation frame) for padding
# $SF is the DOP simulation frame, not the global $F
dop_net.parm("cachedir").set("$HIP/sim_cache/rbd")

# Checkpoint interval — save every N frames
# Low interval (1-5): frequent saves, more disk space, fast recovery
# High interval (10-50): less disk space, longer re-simulation on crash
dop_net.parm("checkpointinterval").set(10)

# Cache memory limit (MB) — flush old frames to disk
dop_net.parm("cachemaxsize").set(2000)  # 2GB RAM cache

print(f"Checkpoints enabled: {cache_dir}")
print(f"  Interval: every 10 frames")
print(f"  RAM limit: 2000 MB")
```

```python
# Resume simulation from checkpoint
import hou
import glob
import os

dop_net = hou.node("/obj/dopnet1")
cache_dir = hou.text.expandString(dop_net.evalParm("cachedir"))

# Find latest checkpoint file
sim_files = sorted(glob.glob(os.path.join(cache_dir, "*.sim")))
if sim_files:
    latest = sim_files[-1]
    # Extract frame number from filename
    basename = os.path.basename(latest)
    print(f"Latest checkpoint: {basename}")
    print(f"  Resume from this frame by setting Start Frame on DOP net")

    # Set the DOP network to start from checkpoint frame
    # Parse frame from filename pattern like "sim_0050.sim"
    import re
    match = re.search(r'(\d+)\.sim$', basename)
    if match:
        checkpoint_frame = int(match.group(1))
        dop_net.parm("startframe").set(checkpoint_frame)
        print(f"  Start frame set to: {checkpoint_frame}")
else:
    print("No checkpoints found — simulation starts from scratch")
```

```python
# File Cache SOP — cache simulation output to disk
import hou
import os

sim_was_enabled = hou.simulationEnabled()
try:
    hou.setSimulationEnabled(False)

    geo_net = hou.node("/obj/geo1")

    # DOP Import SOP (brings DOP results into SOPs)
    dop_import = geo_net.createNode("dopimport", "sim_import")
    dop_import.parm("doppath").set("/obj/dopnet1")
    dop_import.parm("objpattern").set("*")

    # File Cache SOP — write geometry per frame
    cache = geo_net.createNode("filecache", "sim_cache")
    cache.setInput(0, dop_import)

    # Cache path — $F4 for frame padding
    cache_path = "$HIP/geo_cache/sim.$F4.bgeo.sc"
    cache.parm("file").set(cache_path)
    cache.parm("filemode").set(2)   # 2 = Write Files

    # Verify output directory exists
    cache_dir = os.path.dirname(hou.text.expandString(cache_path))
    os.makedirs(cache_dir, exist_ok=True)

    geo_net.layoutChildren()
    print(f"File Cache configured: {cache_path}")

finally:
    hou.setSimulationEnabled(sim_was_enabled)
```

```python
# Cache pre-flight check — verify disk space and paths
import hou
import shutil
import os

def cache_preflight(cache_path, frame_range, estimated_mb_per_frame=50):
    """Verify cache path is valid and has sufficient disk space."""
    expanded = hou.text.expandString(cache_path)
    cache_dir = os.path.dirname(expanded)

    # Check directory
    if not os.path.isdir(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        print(f"Created cache directory: {cache_dir}")

    # Check disk space
    total_frames = frame_range[1] - frame_range[0] + 1
    estimated_gb = (total_frames * estimated_mb_per_frame) / 1024
    disk_usage = shutil.disk_usage(cache_dir)
    free_gb = disk_usage.free / (1024 ** 3)

    print(f"Cache pre-flight:")
    print(f"  Path: {cache_dir}")
    print(f"  Frames: {total_frames} ({frame_range[0]}-{frame_range[1]})")
    print(f"  Estimated size: {estimated_gb:.1f} GB")
    print(f"  Available disk: {free_gb:.1f} GB")

    if estimated_gb > free_gb * 0.8:
        print(f"  WARNING: Cache may exceed 80% of available disk space!")
        return False
    return True

# Usage
ok = cache_preflight(
    cache_path="$HIP/geo_cache/sim.$F4.bgeo.sc",
    frame_range=(1, 240),
    estimated_mb_per_frame=100
)
```

## Expected Output
```
$HIP/sim_cache/rbd/
  ├─ sim_0010.sim    (checkpoint frame 10)
  ├─ sim_0020.sim    (checkpoint frame 20)
  └─ sim_0030.sim    (checkpoint frame 30)

$HIP/geo_cache/
  ├─ sim.0001.bgeo.sc
  ├─ sim.0002.bgeo.sc
  └─ ...
```

## Common Mistakes
- Using `$F` instead of `$SF` in DOP cache paths — `$F` is global frame, `$SF` is simulation frame
- Setting checkpoint interval too high — crash at frame 99 with interval=100 means re-simulating everything
- Not checking disk space before long sim caches — 240 frames × 500MB = 120GB
- Forgetting to set `filemode` to Write (2) on File Cache SOP — defaults to Read, writes nothing
- Caching to network drive — simulation I/O latency kills performance, use local SSD
