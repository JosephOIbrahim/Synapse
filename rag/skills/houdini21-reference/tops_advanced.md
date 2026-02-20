# TOPS/PDG Advanced Patterns

## Triggers
tops advanced, pdg advanced, work items dynamic, feedback loop, partitioner, scheduler tuning,
error handling tops, checkpoint resume, production pipeline tops, pdg monitoring, pdg attributes,
waitforall, partitionbyattribute, pythonprocessor advanced, tops performance, farm scheduler,
hqueue scheduler, deadline scheduler, tops iterative, tops feedback, pdg dependency graph

## Context
Beyond basic wedging, TOPS/PDG is a full dependency-graph computation framework. This file
covers advanced patterns for production pipelines. For wedging basics see `tops_wedging.md`.
All code runs inside Houdini's Python environment (hou module available). PDG callbacks run
inside `pythonprocessor`, `pythonpartitioner`, or feedback node parameter expressions.

---

## Dynamic Work Items

```python
# ── Static vs Dynamic Generation ──────────────────────────────────────────────
# Static: count known at generate time (wedge, filepattern, genericgenerator)
# Dynamic: count depends on upstream results — created during cook, not generate
# Set pythonprocessor → "Generate When" = "Each Upstream Item" for dynamic mode.

# pythonprocessor: dynamic item generation from upstream JSON result
import json
import pdg

def generateTasks(item_holder, upstream_items, generation_type):
    for upstream in upstream_items:
        # upstream_items[0].resultData gives list of pdg.File objects
        result_file = upstream.resultData[0].path
        with open(result_file, encoding="utf-8") as fh:
            data = json.load(fh)

        for i, asset in enumerate(data["assets"]):
            # addWorkItem(index=i) creates a child work item
            new_item = item_holder.addWorkItem(
                index=i,
                cloneResultData=False,   # don't inherit parent outputs
                preserveType=True,
            )
            new_item.setStringAttrib("asset_path", asset["path"])
            new_item.setStringAttrib("asset_name", asset["name"])
            new_item.setIntAttrib("lod_count", asset.get("lod_count", 3))
            # Tag output so downstream nodes can find it
            new_item.addExpectedResultData(
                f"/cache/assets/{asset['name']}/result.json", "file/json"
            )
```

```python
# ── Shot list from database (count unknown until query runs) ──────────────────
import pdg
import sqlite3

def generateTasks(item_holder, upstream_items, generation_type):
    conn = sqlite3.connect("/proj/pipeline/shots.db")
    cursor = conn.execute(
        "SELECT shot_id, frame_start, frame_end FROM shots WHERE status='approved'"
    )
    rows = cursor.fetchall()
    conn.close()

    for idx, (shot_id, fs, fe) in enumerate(rows):
        item = item_holder.addWorkItem(index=idx)
        item.setStringAttrib("shot_id", shot_id)
        item.setIntAttrib("frame_start", fs)
        item.setIntAttrib("frame_end", fe)
        item.setIntAttrib("frame_count", fe - fs + 1)
        # Priority: shorter shots first so farm stays busy
        item.setIntAttrib("pdg_priority", -(fe - fs))
```

```python
# ── Directory-listing dynamic generation ─────────────────────────────────────
import pathlib, pdg

def generateTasks(item_holder, upstream_items, generation_type):
    scan_root = pathlib.Path("/proj/textures/source")
    texture_files = sorted(scan_root.rglob("*.exr"))  # sorted for determinism

    for idx, tex_path in enumerate(texture_files):
        item = item_holder.addWorkItem(index=idx)
        item.setStringAttrib("input_path", str(tex_path))
        item.setStringAttrib("output_path",
            str(tex_path.parent / f"{tex_path.stem}_processed.exr"))
        item.setStringAttrib("asset_name", tex_path.parent.name)
```

---

## Feedback Loops

```python
# ── feedbackbegin / feedbackend: iterative render refinement ─────────────────
# Network topology (text representation):
#   feedbackbegin → set_samples → ropfetch → pythonprocessor(eval) → feedbackend
#
# feedbackend "Stop Condition" parameter expression (Python, single line):
#   work_item.attrib("noise_level").value < 0.01 or pdg_iteration >= 6

# pythonprocessor inside loop: evaluate render quality, write noise metric
import pdg, json, subprocess

def cookTask(work_item):
    render_path = work_item.resultData[0].path   # EXR from upstream ropfetch
    iteration   = work_item.intAttrib("pdg_iteration", 0)

    # Run external noise analysis tool (replace with real tool)
    proc = subprocess.run(
        ["python", "/tools/measure_noise.py", render_path],
        capture_output=True, text=True, check=True
    )
    noise = float(proc.stdout.strip())

    work_item.setFloatAttrib("noise_level", noise)
    work_item.setIntAttrib("iteration", iteration)

    # Write checkpoint so we can resume if cook is interrupted
    checkpoint = {
        "iteration": iteration,
        "noise": noise,
        "render_path": render_path,
    }
    ckpt_path = f"/cache/feedback/iter_{iteration:03d}.json"
    with open(ckpt_path, "w", encoding="utf-8") as fh:
        json.dump(checkpoint, fh, sort_keys=True)
    work_item.addResultData(ckpt_path, "file/json", 0)
```

```python
# ── set_samples node (pythonprocessor): double samples each iteration ─────────
import pdg

def cookTask(work_item):
    iteration   = work_item.intAttrib("pdg_iteration", 0)
    base_samples = 16
    # Exponential ramp: 16 → 32 → 64 → 128 → 256 (capped at 512)
    samples = min(base_samples * (2 ** iteration), 512)
    work_item.setIntAttrib("karma_pixel_samples", samples)
    work_item.setFloatAttrib("karma_variance_threshold", 0.005 / (iteration + 1))
```

```python
# ── feedbackend stop condition (set as Python expression in parm) ─────────────
# Paste this into the feedbackend "Stop Condition" parameter field:
#
#   work_item.attrib("noise_level").value < 0.01 or pdg_iteration >= 6
#
# Equivalent guard script for pythonprocessor after feedbackend:
import pdg

def cookTask(work_item):
    noise     = work_item.floatAttrib("noise_level", 1.0)
    iteration = work_item.intAttrib("iteration", 0)
    converged = noise < 0.01 or iteration >= 6
    work_item.setBoolAttrib("converged", converged)
    if not converged:
        raise pdg.CookError(
            f"Iteration {iteration}: noise={noise:.4f} above threshold 0.01"
        )
```

---

## Partitioners

```python
# ── partitionbyattribute: group renders by shot ───────────────────────────────
# Node: partitionbyattribute
# Parameter "Attribute Name" = "shot_id"   (groups items with same shot_id)
# Downstream node sees ONE work item per partition; access members via:

import pdg

def cookTask(work_item):
    # work_item.partitionItems → list of member pdg.WorkItem objects
    for member in work_item.partitionItems:
        shot_id    = member.stringAttrib("shot_id", "")
        frame      = member.intAttrib("pdg_frame", 0)
        output_exr = member.resultData[0].path if member.resultData else ""
        print(f"  shot={shot_id}  frame={frame:04d}  exr={output_exr}")
```

```python
# ── pythonpartitioner: custom partitioning by sequence prefix ─────────────────
# The return value of this script becomes the partition key.
# Items with the same key land in the same partition.
import pdg

# "Partition Script" parameter of pythonpartitioner node:
def partitionByShot(work_item):
    shot_name = work_item.stringAttrib("shot_name", "")
    # e.g., "sq010_sh020" → partition key "sq010"
    sequence = shot_name.split("_")[0] if "_" in shot_name else shot_name
    return sequence
```

```python
# ── waitforall: collect all upstream items before final step ──────────────────
# Node: waitforall  (no parameters needed — collects everything)
# Use before: ffmpeg encode, email notify, final report generation

# Downstream pythonprocessor reading all collected outputs:
import pdg, pathlib

def cookTask(work_item):
    # All upstream result files are available via partitionItems
    exr_files = []
    for member in work_item.partitionItems:
        for result in member.resultData:
            if result.path.endswith(".exr"):
                exr_files.append(result.path)

    # Write manifest for downstream encoder
    manifest_path = "/cache/render/frame_manifest.txt"
    pathlib.Path(manifest_path).write_text(
        "\n".join(sorted(exr_files)),  # sorted for determinism
        encoding="utf-8"
    )
    work_item.addResultData(manifest_path, "file/text", 0)
```

```python
# ── partitionbycombination: cross-product wedge analysis ─────────────────────
# Groups items by all combinations of two attributes.
# Parameter "Attribute Names" = "material_id shot_id"
# Downstream item represents one (material, shot) pair.

import pdg, json

def cookTask(work_item):
    mat_id  = work_item.stringAttrib("material_id", "")
    shot_id = work_item.stringAttrib("shot_id", "")
    renders = [m.resultData[0].path for m in work_item.partitionItems
               if m.resultData]

    report = {"material": mat_id, "shot": shot_id, "renders": renders}
    out_path = f"/cache/comparison/{mat_id}_{shot_id}_report.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    work_item.addResultData(out_path, "file/json", 0)
```

---

## Scheduler Tuning

```python
# ── Local scheduler configuration via Python API ──────────────────────────────
import pdg, hou

def configure_local_scheduler(topnet_path="/obj/topnet1"):
    topnet = hou.node(topnet_path)
    if topnet is None:
        raise RuntimeError(f"Couldn't find TOPnet at {topnet_path}")

    # Find the local scheduler inside the topnet
    scheduler = topnet.node("localscheduler")
    if scheduler is None:
        scheduler = topnet.createNode("pdg::localscheduler", "localscheduler")

    # GPU renders: 1 concurrent job (GPU contention destroys throughput)
    scheduler.parm("maxproccount").set(1)

    # CPU sims / compositing: use all cores minus 2 for system responsiveness
    import os
    cpu_cores = os.cpu_count() or 8
    # scheduler.parm("maxproccount").set(max(1, cpu_cores - 2))  # CPU mode

    # Point temp dir at fast NVMe scratch (never a network drive)
    scheduler.parm("tempdirlocal").set("D:/pdg_scratch")

    # Enable verbose for debugging scheduler decisions
    scheduler.parm("verbose").set(False)   # flip to True when diagnosing

    return scheduler
```

```python
# ── HQueue scheduler configuration ───────────────────────────────────────────
import hou

def configure_hqueue_scheduler(topnet_path="/obj/topnet1",
                                hq_server="http://hq-server:5000"):
    topnet = hou.node(topnet_path)
    sched  = topnet.node("hqueuescheduler")
    if sched is None:
        sched = topnet.createNode("pdg::hqueuescheduler", "hqueuescheduler")

    sched.parm("hqserver").set(hq_server)
    # Path to hqclient binary on render nodes (must match farm OS)
    sched.parm("hqclient_path").set("/opt/hqueue/bin/hqclient")

    # Set as active scheduler for the TOPnet
    topnet.parm("topscheduler").set(sched.name())
    return sched
```

```python
# ── Deadline scheduler configuration ─────────────────────────────────────────
import hou

def configure_deadline_scheduler(topnet_path="/obj/topnet1",
                                  deadline_repo="//deadline-server/DeadlineRepository10"):
    topnet = hou.node(topnet_path)
    sched  = topnet.node("deadlinescheduler")
    if sched is None:
        sched = topnet.createNode("pdg::deadlinescheduler", "deadlinescheduler")

    sched.parm("deadlinerepo").set(deadline_repo)
    # Map PDG priority to Deadline priority (0=low, 100=high)
    sched.parm("jobpriority").setExpression("int(work_item.attrib('pdg_priority').value * 100)")
    # Group/pool from work item attributes for per-shot routing
    sched.parm("group").setExpression("work_item.attrib('deadline_group').value")
    sched.parm("pool").setExpression("work_item.attrib('deadline_pool').value")

    topnet.parm("topscheduler").set(sched.name())
    return sched
```

```python
# ── Per-work-item scheduler overrides via attributes ─────────────────────────
import pdg

def cookTask(work_item):
    # Set scheduler environment variables for farm nodes
    work_item.setStringAttrib("deadline_group", "houdini_gpu")
    work_item.setStringAttrib("deadline_pool", "shots")
    work_item.setIntAttrib("pdg_priority", 75)

    # Custom env vars passed to render node (HQueue and Deadline both support this)
    work_item.setStringAttrib("env_HIP", "/proj/shots/sq010/sh020/houdini")
    work_item.setStringAttrib("env_SHOT", "sq010_sh020")
    work_item.setStringAttrib("env_FRAME_RANGE", "1001-1120")
```

---

## Error Handling and Recovery

```python
# ── Work item state inspection via Python API ─────────────────────────────────
import pdg, hou

def inspect_cook_state(topnet_path="/obj/topnet1", node_name="ropfetch1"):
    topnet    = hou.node(topnet_path)
    tops_node = topnet.node(node_name)
    graph     = tops_node.getPDGGraphContext()

    # pdg.workItemState: Waiting=0, Cooking=1, Cooked=2, Failed=3, Cancelled=4
    STATE_NAMES = {
        pdg.workItemState.Waiting:   "Waiting",
        pdg.workItemState.Cooking:   "Cooking",
        pdg.workItemState.Cooked:    "Cooked",
        pdg.workItemState.Failed:    "Failed",
        pdg.workItemState.Cancelled: "Cancelled",
    }

    failed_items = []
    for item in graph.workItems:
        state_name = STATE_NAMES.get(item.state, "Unknown")
        if item.state == pdg.workItemState.Failed:
            error_msg   = item.stringAttrib("pdg_error", "")
            error_count = item.intAttrib("pdg_errorcount", 0)
            failed_items.append({
                "name":    item.name,
                "error":   error_msg,
                "retries": error_count,
            })
            print(f"FAILED [{error_count} retries]: {item.name} — {error_msg}")

    return failed_items
```

```python
# ── Error handling in pythonprocessor: safe file check ───────────────────────
import pdg, pathlib, json

def cookTask(work_item):
    input_path  = work_item.stringAttrib("input_path", "")
    output_path = work_item.stringAttrib("output_path", "")

    # Pre-flight: catch errors early before expensive work
    if not input_path:
        raise pdg.CookError("input_path attribute is empty — check upstream generator")

    p = pathlib.Path(input_path)
    if not p.exists():
        raise pdg.CookError(f"Couldn't find input file: {input_path}")
    if p.stat().st_size == 0:
        raise pdg.CookError(f"Input file is zero bytes: {input_path} — upstream cook may have failed")

    # Do the real work
    try:
        result = process_asset(input_path, output_path)   # your processing function
    except Exception as exc:
        # Re-raise as CookError so PDG records it cleanly and retries if maxretries > 0
        raise pdg.CookError(f"Processing failed for {input_path}: {exc}") from exc

    work_item.addResultData(output_path, "file/generic", 0)
```

```python
# ── Retry strategy: configure maxretries programmatically ────────────────────
import hou

def set_retry_policy(topnet_path="/obj/topnet1", node_name="ropfetch1",
                     max_retries=2, error_condition="continue"):
    node = hou.node(f"{topnet_path}/{node_name}")
    if node is None:
        raise RuntimeError(f"Couldn't find node {topnet_path}/{node_name}")

    # maxretries=2 good for farm jobs (transient network / disk errors)
    # maxretries=0 for CPU processing (same deterministic error will recur)
    node.parm("maxretries").set(max_retries)

    # errorcondition options: "continue", "warn", "error"
    # "continue" = mark failed, keep cooking other items (production default)
    # "error"    = stop entire cook on first failure (strict validation mode)
    node.parm("errorcondition").set(error_condition)
```

---

## Checkpoint and Resume

```python
# ── Checkpoint state: check which items are already cooked ───────────────────
import pdg, hou, json, pathlib

def get_checkpoint_status(topnet_path="/obj/topnet1"):
    """
    Returns dict: {item_name: {"cooked": bool, "checkpoint_file": str}}
    Cooked items are skipped on resume — PDG handles this automatically.
    """
    topnet = hou.node(topnet_path)
    status = {}

    for child in topnet.children():
        if not hasattr(child, "getPDGGraphContext"):
            continue
        try:
            graph = child.getPDGGraphContext()
        except Exception:
            continue

        for item in graph.workItems:
            ckpt_path = item.stringAttrib("pdg_checkpointfile", "")
            is_cooked = (item.state == pdg.workItemState.Cooked)
            status[item.name] = {
                "cooked":          is_cooked,
                "checkpoint_file": ckpt_path,
                "checkpoint_exists": pathlib.Path(ckpt_path).exists() if ckpt_path else False,
            }

    return status
```

```python
# ── Dirty specific node to force re-cook of a subset ─────────────────────────
import hou

def dirty_node_for_recook(topnet_path="/obj/topnet1", node_name="ropfetch1",
                           dirty_upstream=False):
    """
    Dirty a specific node so its items re-cook on next cook() call.
    Leaves already-cooked siblings untouched (essential for partial re-renders).
    """
    topnet = hou.node(topnet_path)
    node   = topnet.node(node_name)
    if node is None:
        raise RuntimeError(f"Couldn't find {topnet_path}/{node_name}")

    # dirtyAll() resets all work items on this node
    # dirtyUpstream=False keeps upstream caches intact
    node.dirtyAll(dirty_upstream=dirty_upstream)
    print(f"Dirtied {node_name} (upstream_dirty={dirty_upstream})")
```

```python
# ── Write per-item checkpoint file for crash recovery ────────────────────────
import pdg, json, pathlib, time

def cookTask(work_item):
    shot_id     = work_item.stringAttrib("shot_id", "unknown")
    frame       = work_item.intAttrib("pdg_frame", 0)
    checkpoint_dir = pathlib.Path(f"/cache/checkpoints/{shot_id}")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    ckpt_file = checkpoint_dir / f"frame_{frame:04d}.json"

    # Write checkpoint before expensive operation so we can detect partial runs
    state = {
        "shot_id": shot_id,
        "frame":   frame,
        "started": time.time(),
        "status":  "started",
    }
    ckpt_file.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
    work_item.setStringAttrib("pdg_checkpointfile", str(ckpt_file))

    # ... do expensive render work here ...

    # Update checkpoint on success
    state["status"]  = "complete"
    state["finished"] = time.time()
    ckpt_file.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    output_exr = f"/render/{shot_id}/frame.{frame:04d}.exr"
    work_item.addResultData(output_exr, "file/image", 0)
```

---

## Production Pipeline Patterns

```python
# ── Full render sequence pipeline (Python-driven setup) ───────────────────────
# Topology: filepattern → ropfetch → waitforall → imagemagick → ffmpegencodevideo
import hou

def build_render_sequence_topnet(scene_dir="/proj/hip", output_dir="/render/out"):
    """Build a complete render-sequence TOPS pipeline programmatically."""
    obj         = hou.node("/obj")
    topnet      = obj.createNode("topnet", "render_pipeline")

    # 1. Source HIP files
    file_pattern = topnet.createNode("pdg::filepattern", "hip_files")
    file_pattern.parm("pattern").set(f"{scene_dir}/*.hip")
    file_pattern.parm("fileattrib").set("hip_file")

    # 2. Render each HIP file
    rop_fetch = topnet.createNode("pdg::ropfetch", "render_frames")
    rop_fetch.parm("hipfile").setExpression("`@hip_file`")
    rop_fetch.parm("roppath").set("/out/karma_rop")
    rop_fetch.parm("maxretries").set(2)
    rop_fetch.parm("errorcondition").set("continue")  # don't halt on one bad frame
    rop_fetch.setFirstInput(file_pattern)

    # 3. Collect all frames before encoding
    wait = topnet.createNode("pdg::waitforall", "collect_frames")
    wait.setFirstInput(rop_fetch)

    # 4. Encode movie
    ffmpeg = topnet.createNode("pdg::ffmpegencodevideo", "encode_movie")
    ffmpeg.parm("outputfile").set(f"{output_dir}/preview.mp4")
    ffmpeg.parm("framerate").set(24)
    ffmpeg.setFirstInput(wait)

    topnet.layoutChildren()
    return topnet
```

```python
# ── Multi-shot render pipeline ────────────────────────────────────────────────
# Topology:
#   pythonprocessor(shot_list) → set_env → ropfetch → partitionbyattr → ffmpeg → waitforall → notify
import pdg, hou, json

def generate_shot_work_items(item_holder, upstream_items, generation_type):
    """Load shot list from production database and create one item per shot."""
    shots_file = "/proj/pipeline/approved_shots.json"
    with open(shots_file, encoding="utf-8") as fh:
        shots = json.load(fh)["shots"]

    for idx, shot in enumerate(shots):
        item = item_holder.addWorkItem(index=idx)
        item.setStringAttrib("shot_id",    shot["id"])
        item.setStringAttrib("hip_path",   shot["hip_path"])
        item.setIntAttrib("frame_start",   shot["frame_start"])
        item.setIntAttrib("frame_end",     shot["frame_end"])
        item.setStringAttrib("deadline_group", shot.get("gpu_group", "houdini_gpu"))
        item.setIntAttrib("pdg_priority",  shot.get("priority", 50))
```

```python
# ── Lookdev pipeline: texture wedge + comparison sheet ───────────────────────
# Topology: filepattern(textures) → wedge(variants) → ropfetch → partitionbyattr → imagemagick
import hou

def build_lookdev_topnet(texture_root="/proj/textures"):
    obj    = hou.node("/obj")
    topnet = obj.createNode("topnet", "lookdev_pipeline")

    # Source textures
    fp = topnet.createNode("pdg::filepattern", "textures")
    fp.parm("pattern").set(f"{texture_root}/**/*.exr")
    fp.parm("fileattrib").set("texture_path")

    # Wedge material variants
    wedge = topnet.createNode("pdg::wedge", "material_variants")
    wedge.parm("wedgecount").set(5)
    wedge.parm("wedgeattrib1").set("roughness")
    wedge.parm("wedgestart1").set(0.1)
    wedge.parm("wedgeend1").set(0.9)
    wedge.setFirstInput(fp)

    # Render turntable per variant
    rop = topnet.createNode("pdg::ropfetch", "turntable_render")
    rop.parm("roppath").set("/out/karma_turntable")
    rop.parm("maxretries").set(1)
    rop.setFirstInput(wedge)

    # Partition by material name for per-material comparison sheets
    part = topnet.createNode("pdg::partitionbyattribute", "by_material")
    part.parm("attrib").set("asset_name")
    part.setFirstInput(rop)

    # Comparison sheet per material
    magick = topnet.createNode("pdg::imagemagick", "comparison_sheet")
    magick.setFirstInput(part)

    topnet.layoutChildren()
    return topnet
```

```python
# ── Sim cache once, wedge render parameters ───────────────────────────────────
# Topology: ropfetch(sim) → waitforall → wedge(light/cam) → ropfetch(render) → ffmpeg
import hou

def build_sim_render_topnet():
    obj    = hou.node("/obj")
    topnet = obj.createNode("topnet", "sim_render_pipeline")

    # Sim cache (runs once)
    sim = topnet.createNode("pdg::ropfetch", "sim_cache")
    sim.parm("roppath").set("/out/pyro_sim")
    sim.parm("errorcondition").set("error")  # sim failure is fatal

    # Collect sim before wedging
    wait = topnet.createNode("pdg::waitforall", "wait_sim")
    wait.setFirstInput(sim)

    # Wedge lighting variations (no re-simulation)
    wedge = topnet.createNode("pdg::wedge", "lighting_wedge")
    wedge.parm("wedgecount").set(8)
    wedge.parm("wedgeattrib1").set("light_exposure")
    wedge.parm("wedgestart1").set(-1.0)
    wedge.parm("wedgeend1").set(2.0)
    wedge.setFirstInput(wait)

    # Render each lighting variant
    render = topnet.createNode("pdg::ropfetch", "beauty_render")
    render.parm("roppath").set("/out/karma_beauty")
    render.parm("maxretries").set(2)
    render.setFirstInput(wedge)

    # Encode per-variant movies
    ffmpeg = topnet.createNode("pdg::ffmpegencodevideo", "encode_variants")
    ffmpeg.setFirstInput(render)

    topnet.layoutChildren()
    return topnet
```

---

## Monitoring and Diagnostics

```python
# ── Cook stats: programmatic access to per-node timing ───────────────────────
import pdg, hou

def get_cook_stats(topnet_path="/obj/topnet1"):
    topnet = hou.node(topnet_path)
    report = {}

    for child in topnet.children():
        if not hasattr(child, "getPDGGraphContext"):
            continue
        try:
            ctx = child.getPDGGraphContext()
        except Exception:
            continue

        items      = list(ctx.workItems)
        cooked     = [i for i in items if i.state == pdg.workItemState.Cooked]
        failed     = [i for i in items if i.state == pdg.workItemState.Failed]
        cook_times = [i.cookDuration for i in cooked if hasattr(i, "cookDuration")]

        report[child.name()] = {
            "total":       len(items),
            "cooked":      len(cooked),
            "failed":      len(failed),
            "avg_cook_s":  sum(cook_times) / len(cook_times) if cook_times else 0.0,
            "max_cook_s":  max(cook_times) if cook_times else 0.0,
        }

    # Print sorted by average cook time (worst bottlenecks first)
    for node_name, stats in sorted(report.items(),
                                   key=lambda kv: kv[1]["avg_cook_s"], reverse=True):
        print(f"{node_name:30s}  total={stats['total']:4d}  "
              f"failed={stats['failed']:3d}  "
              f"avg={stats['avg_cook_s']:.2f}s  max={stats['max_cook_s']:.2f}s")

    return report
```

```python
# ── Dependency graph export for external analysis ─────────────────────────────
import pdg, hou, json, pathlib

def export_dependency_graph(topnet_path="/obj/topnet1",
                             output_path="/tmp/pdg_graph.json"):
    topnet = hou.node(topnet_path)
    graph  = topnet.getPDGGraphContext()

    # Serialize to JSON (Houdini 21 API)
    graph_json = graph.serializationJSON()
    pathlib.Path(output_path).write_text(
        json.dumps(json.loads(graph_json), indent=2, sort_keys=True),
        encoding="utf-8"
    )
    print(f"Dependency graph written to {output_path}")
    return output_path
```

```python
# ── Real-time monitoring: poll cook state during an async cook ────────────────
import pdg, hou, time

def monitor_cook(topnet_path="/obj/topnet1", poll_interval=2.0):
    topnet = hou.node(topnet_path)
    graph  = topnet.getPDGGraphContext()

    STATE_NAMES = {
        pdg.workItemState.Waiting:   "W",
        pdg.workItemState.Cooking:   "C",
        pdg.workItemState.Cooked:    "OK",
        pdg.workItemState.Failed:    "FAIL",
        pdg.workItemState.Cancelled: "X",
    }

    # cookAsynchronous() starts cook in background; monitorCook() polls
    topnet.cookAsynchronous()

    while graph.isCooking:
        items  = list(graph.workItems)
        counts = {}
        for item in items:
            key = STATE_NAMES.get(item.state, "?")
            counts[key] = counts.get(key, 0) + 1

        total = len(items)
        done  = counts.get("OK", 0) + counts.get("FAIL", 0)
        pct   = 100.0 * done / total if total else 0.0
        print(f"[{pct:5.1f}%]  "
              f"Cooked={counts.get('OK',0)}  "
              f"Failed={counts.get('FAIL',0)}  "
              f"Cooking={counts.get('C',0)}  "
              f"Waiting={counts.get('W',0)}")
        time.sleep(poll_interval)

    print("Cook complete.")
```

---

## PDG Attributes Reference

```python
# ── Built-in PDG attribute access patterns ────────────────────────────────────
import pdg

def demonstrate_pdg_attributes(work_item):
    # Built-in read-only attributes (set by PDG, not user)
    index     = work_item.intAttrib("pdg_index", 0)        # item index in node
    name      = work_item.stringAttrib("pdg_name", "")     # unique item name
    frame     = work_item.floatAttrib("pdg_frame", 0.0)    # associated frame
    iteration = work_item.intAttrib("pdg_iteration", 0)    # feedback loop count
    error_msg = work_item.stringAttrib("pdg_error", "")    # error string if failed
    err_count = work_item.intAttrib("pdg_errorcount", 0)   # retry count
    priority  = work_item.intAttrib("pdg_priority", 0)     # scheduling priority
    ckpt_file = work_item.stringAttrib("pdg_checkpointfile", "")

    # Result data (output files registered by this item)
    for result in work_item.resultData:
        print(f"  output: {result.path}  tag: {result.tag}  owned: {result.ownedByItem}")

    # Input result data (outputs from direct upstream items)
    for inp in work_item.inputResultData:
        print(f"  input:  {inp.path}  tag: {inp.tag}")

    return {
        "index": index, "name": name, "frame": frame,
        "iteration": iteration, "error": error_msg,
        "error_count": err_count, "priority": priority,
    }
```

```python
# ── Custom attribute CRUD: set, read, delete ──────────────────────────────────
import pdg

def demonstrate_custom_attributes(work_item):
    # ── SET ──────────────────────────────────────────────────────────────────
    work_item.setStringAttrib("shot_name",    "sq010_sh020")
    work_item.setIntAttrib("frame_start",     1001)
    work_item.setIntAttrib("frame_end",       1120)
    work_item.setFloatAttrib("noise_level",   0.045)
    work_item.setBoolAttrib("converged",      False)
    work_item.setStringAttrib("asset_path",   "/proj/assets/hero_char/hero_char.usd")

    # Array attributes (multiple values per attribute)
    work_item.setIntAttrib("aov_indices",     [0, 1, 3, 7], 0)  # index 0 = replace all

    # ── READ ─────────────────────────────────────────────────────────────────
    shot     = work_item.stringAttrib("shot_name", "")         # default if missing
    fs       = work_item.intAttrib("frame_start", 1001)
    noise    = work_item.floatAttrib("noise_level", 1.0)
    done     = work_item.boolAttrib("converged", False)

    # Check existence before reading to avoid KeyError
    if work_item.hasAttrib("custom_tag"):
        tag = work_item.stringAttrib("custom_tag", "")
    else:
        tag = "default"

    # ── ADD RESULT DATA ───────────────────────────────────────────────────────
    # tag format: "file/<subtype>" — used by downstream nodes to filter inputs
    work_item.addResultData("/render/sq010_sh020.1001.exr", "file/image", 0)
    work_item.addResultData("/cache/sq010_sh020_report.json", "file/json", 0)

    # addExpectedResultData: register before cook so scheduler knows output location
    work_item.addExpectedResultData("/render/sq010_sh020.1001.exr", "file/image")

    return {"shot": shot, "frames": (fs, work_item.intAttrib("frame_end", 1120)),
            "noise": noise, "converged": done, "tag": tag}
```

```python
# ── Performance optimization: pre-flight validation node ─────────────────────
# Add a lightweight pythonprocessor BEFORE expensive renders.
# Catches bad paths, missing files, invalid attrs early.
import pdg, pathlib, hou

def preflight_validate(work_item):
    """Validate all inputs before committing to expensive render."""
    errors = []

    hip_path   = work_item.stringAttrib("hip_path", "")
    rop_path   = work_item.stringAttrib("rop_path", "/out/karma")
    output_dir = work_item.stringAttrib("output_dir", "")

    if not hip_path:
        errors.append("hip_path attribute is empty")
    elif not pathlib.Path(hip_path).exists():
        errors.append(f"HIP file not found: {hip_path}")

    if not output_dir:
        errors.append("output_dir attribute is empty")
    else:
        out = pathlib.Path(output_dir)
        if not out.exists():
            try:
                out.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                errors.append(f"Couldn't create output dir {output_dir}: {e}")

    frame_start = work_item.intAttrib("frame_start", -1)
    frame_end   = work_item.intAttrib("frame_end", -1)
    if frame_start < 0 or frame_end < 0 or frame_end < frame_start:
        errors.append(f"Invalid frame range: {frame_start}-{frame_end}")

    if errors:
        # Fail fast — saves GPU time on the farm
        raise pdg.CookError("Pre-flight failed:\n" + "\n".join(f"  - {e}" for e in errors))

    # Stamp validation result so downstream can skip redundant checks
    work_item.setBoolAttrib("preflight_ok", True)
    print(f"Pre-flight OK: {work_item.name}")
```

---

## Common Issues

**All items fail simultaneously** — Scheduler not configured or not started. Verify a scheduler node exists inside the TOPnet and is set as the active scheduler (`topscheduler` parm on the topnet). For local scheduler, confirm `maxproccount` is at least 1.

**Items stuck in Waiting** — Unresolved dependencies or a cycle in the graph. Open the Task Graph pane and look for items with no upstream cooked items feeding them. Cycles appear as nodes with no valid cook path.

**Cook hangs indefinitely** — Deadlock in a feedback loop. Always set a maximum iteration count on `feedbackend`. Verify the stop condition expression is syntactically valid Python and can actually evaluate to True given expected attribute values.

**Output files missing** — `@pdg_output` not set, or `addResultData` / `addExpectedResultData` never called. Downstream nodes find inputs by scanning `resultData` — if it is empty the partition or waitforall sees nothing.

**Farm jobs fail with missing env** — Environment variables are not inherited on render nodes. Set all required env vars via work item attributes (prefix `env_`) and configure the scheduler to forward them. Never rely on the submitting machine's environment being present on the farm.

**Memory explosion during cook** — Too many items cooking concurrently. Reduce `maxproccount` on the scheduler. Add `partitionbyframe` stages to batch items and reduce live item count. For GPU renders, keep `maxproccount=1`.

**Slow generation phase** — Excessive dynamic generation with large fanout. Convert to static generation where item counts are predictable. Reduce upstream fanout by filtering earlier in the graph.

**Items cook out of order** — `@pdg_priority` not set, or all items have equal priority. Set higher integers for urgent items. For strict ordering, use explicit node dependencies rather than priority.

**Checkpoint resume re-cooks everything** — Checkpoint files are missing, moved, or the graph topology changed since the last cook (node renames invalidate checkpoints). Verify checkpoint files exist at the paths stored in `pdg_checkpointfile`. If topology changed, a full re-cook is unavoidable.

**pythonprocessor scope issues** — Nested functions defined inside `cookTask` cannot access variables from an outer `generateTasks` scope. Keep all logic inline or pass data through work item attributes rather than Python closures.
