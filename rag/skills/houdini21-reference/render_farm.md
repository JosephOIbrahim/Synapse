# Render Farm Workflows

## Triggers

render farm, render sequence, batch render, render and validate, render orchestrator, per-frame validation, auto-fix, firefly fix, black frame, nan pixels, clipping fix, karma samples, pixel samples, exposure fix, scene classification, render tags, PDG render farm, TOPs render, ROP fetch, HQueue, local scheduler, sequence render, synapse_render_sequence, synapse_autonomous_render, render loop, render report, lighting law, intensity exposure

## Context

Synapse includes a local render-farm orchestrator that automates sequence rendering with per-frame OIIO validation, targeted auto-fixes, and cross-shot memory warmup. It complements PDG/TOPs by adding the validation-and-fix loop that PDG's acyclic graph cannot express natively.

## Code

### Scene Classification

```python
import hou

def classify_scene(stage_node_path="/stage"):
    """
    Analyze the USD stage and return a set of tags that describe the scene.
    Tags drive memory lookups and default render settings.
    """
    tags = set()
    stage = hou.node(stage_node_path).stage()  # returns pxr.Usd.Stage

    # Collect every prim path as a flat string for keyword matching
    all_paths = " ".join(str(p.GetPath()) for p in stage.Traverse())
    all_paths_lower = all_paths.lower()

    # Interior / outdoor classification based on USD prim path keywords
    interior_keywords = ("room", "interior", "indoor", "cave", "tunnel")
    outdoor_keywords  = ("outdoor", "exterior", "sky", "terrain")
    if any(kw in all_paths_lower for kw in interior_keywords):
        tags.add("interior")
    if any(kw in all_paths_lower for kw in outdoor_keywords):
        tags.add("outdoor")

    # Count light prims -- many_lights triggers extra samples
    from pxr import UsdLux
    light_count = sum(
        1 for p in stage.Traverse()
        if p.IsA(UsdLux.LightAPI)
    )
    if light_count >= 5:
        tags.add("many_lights")

    # Dome light / HDRI presence
    dome_types = ("DomeLight", "domelight", "dome_light")
    if any(dt in all_paths for dt in dome_types):
        tags.add("has_environment")

    # Volume / VDB presence
    volume_keywords = ("volume", "vdb", "fog", "smoke")
    if any(kw in all_paths_lower for kw in volume_keywords):
        tags.add("has_volumes")

    # High-poly detection by total prim count
    prim_count = sum(1 for _ in stage.Traverse())
    if prim_count >= 50_000:
        tags.add("high_poly")

    return tags


# --- Example usage ---
tags = classify_scene("/stage")
# tags -> {"interior", "many_lights", "has_environment"}
```

### Memory Warmup — Load Known-Good Settings

```python
def warmup_render_settings(tags, memory_store):
    """
    Query past render sessions for settings that matched the current scene tags.
    Returns a dict of overrides to apply before rendering starts.
    If memory has no relevant entries, returns safe defaults.
    """
    # Ask memory for entries tagged with the same scene classification
    results = memory_store.search(
        query="render settings karma samples exposure",
        tags=list(tags),
        limit=5
    )

    overrides = {}
    for entry in results:
        # Each memory entry has a 'data' dict with learned settings
        for key, value in entry.get("data", {}).items():
            # Later entries (more recent) take priority
            overrides[key] = value

    # Safe defaults when memory has nothing relevant
    defaults = {
        "karma_samples":          64,    # pixel samples per pixel
        "karma_maxpathdepth":      8,    # max ray bounce depth
        "karma_pixelfilterclamp": 10.0,  # clamp extreme firefly pixels
    }
    defaults.update(overrides)   # memory overrides win
    return defaults
```

### Validation Checks

```python
import subprocess, json, math

def validate_frame(image_path):
    """
    Run OIIO pixel analysis on a rendered EXR.
    Returns a dict: { check_name -> (passed: bool, detail: str) }.
    """
    results = {}

    # --- file_integrity: does the file exist and is it non-empty? ---
    import os
    exists = os.path.isfile(image_path) and os.path.getsize(image_path) > 0
    results["file_integrity"] = (exists, "" if exists else "File missing or zero-byte")
    if not exists:
        return results   # no point running pixel checks on a missing file

    # Use oiiotool (ships with Houdini at $HFS/bin/oiiotool.exe) to get stats
    oiiotool = r"C:\Program Files\Side Effects Software\Houdini 21.0.596\bin\oiiotool.exe"
    proc = subprocess.run(
        [oiiotool, image_path, "--stats"],
        capture_output=True, text=True
    )
    stats_text = proc.stdout + proc.stderr

    # Parse mean and max from oiiotool --stats output (simplified)
    # Real output has lines like: "Mean: 0.2143 0.1987 0.1654"
    mean_vals, max_vals = _parse_oiio_stats(stats_text)
    overall_mean = sum(mean_vals) / len(mean_vals) if mean_vals else 0.0
    overall_max  = max(max_vals)  if max_vals  else 0.0

    # --- black_frame: mean luminance below threshold ---
    BLACK_THRESHOLD = 0.001
    passed = overall_mean > BLACK_THRESHOLD
    results["black_frame"] = (passed, "" if passed else f"Mean={overall_mean:.5f}")

    # --- nan_check: any pixel is NaN or Inf ---
    nan_present = "nan" in stats_text.lower() or "inf" in stats_text.lower()
    results["nan_check"] = (not nan_present, "" if not nan_present else "NaN/Inf pixels detected")

    # --- clipping: max value exceeds 1.0 significantly (burned highlights) ---
    CLIP_THRESHOLD = 50.0   # EXR headroom is wide; this catches true burn
    passed = overall_max < CLIP_THRESHOLD
    results["clipping"] = (passed, "" if passed else f"Max={overall_max:.1f}")

    # --- underexposure: scene too dark but not black ---
    UNDER_THRESHOLD = 0.02
    passed = overall_mean >= UNDER_THRESHOLD
    results["underexposure"] = (passed, "" if passed else f"Mean={overall_mean:.5f}")

    # --- saturation (fireflies): isolated extremely bright pixels ---
    # Fireflies show up as max >> mean by a large ratio
    FIREFLY_RATIO = 500.0
    firefly = (overall_max / overall_mean) > FIREFLY_RATIO if overall_mean > 0 else False
    results["saturation"] = (not firefly, "" if not firefly else f"Max/Mean ratio={overall_max/overall_mean:.0f}")

    return results


def _parse_oiio_stats(text):
    """Extract mean and max float arrays from oiiotool --stats output."""
    mean_vals, max_vals = [], []
    for line in text.splitlines():
        line_lower = line.lower()
        if "mean:" in line_lower:
            mean_vals = [float(v) for v in line.split(":")[1].split() if _is_float(v)]
        if "max:" in line_lower:
            max_vals  = [float(v) for v in line.split(":")[1].split() if _is_float(v)]
    return mean_vals, max_vals

def _is_float(s):
    try: float(s); return True
    except ValueError: return False
```

### Auto-Fix Remedies

```python
def apply_fix(issue_name, karma_node, current_settings, memory_fixes=None):
    """
    Apply a targeted fix to the Karma LOP after a validation failure.
    memory_fixes (dict) -- overrides from past sessions take priority.
    Returns updated settings dict.
    """
    settings = dict(current_settings)

    # Memory-assisted fixes take priority over hardcoded defaults
    if memory_fixes and issue_name in memory_fixes:
        fix = memory_fixes[issue_name]
        for parm, value in fix.items():
            karma_node.parm(parm).set(value)
            settings[parm] = value
        return settings

    # --- Hardcoded default remedies ---

    if issue_name == "saturation":
        # Fireflies: double pixel samples, capped at 256
        current_samples = settings.get("karma_samples", 64)
        new_samples = min(current_samples * 2, 256)
        karma_node.parm("karma_samples").set(new_samples)
        settings["karma_samples"] = new_samples

    elif issue_name == "black_frame":
        # Missing lights or wrong camera -- bump exposure +2 stops
        # LIGHTING LAW: never touch intensity; exposure is the only brightness control
        exp_parm = karma_node.parm("xn__inputsexposure_vya")
        if exp_parm:
            new_exp = exp_parm.eval() + 2.0
            exp_parm.set(new_exp)
            karma_node.parm("xn__inputsexposure_control_wcb").set("set")
            settings["exposure"] = new_exp

    elif issue_name == "nan_check":
        # Shader errors produce NaN -- pixel filter clamp kills them
        karma_node.parm("karma_pixelfilterclamp").set(100.0)
        settings["karma_pixelfilterclamp"] = 100.0

    elif issue_name == "clipping":
        # Burned highlights -- reduce exposure by 1 stop
        exp_parm = karma_node.parm("xn__inputsexposure_vya")
        if exp_parm:
            new_exp = exp_parm.eval() - 1.0
            exp_parm.set(new_exp)
            karma_node.parm("xn__inputsexposure_control_wcb").set("set")
            settings["exposure"] = new_exp

    elif issue_name == "underexposure":
        # Too dark -- increase exposure by 1 stop
        exp_parm = karma_node.parm("xn__inputsexposure_vya")
        if exp_parm:
            new_exp = exp_parm.eval() + 1.0
            exp_parm.set(new_exp)
            karma_node.parm("xn__inputsexposure_control_wcb").set("set")
            settings["exposure"] = new_exp

    return settings
```

### Per-Frame Render-Validate-Fix Loop

```python
import os, time

MAX_RETRIES = 3   # max re-renders per frame before giving up

def render_frame_with_validation(frame, rop_node, karma_node, output_template, settings, memory_fixes=None):
    """
    Render one frame, validate it, and fix+retry up to MAX_RETRIES times.
    output_template: string with {frame} placeholder, e.g. '/out/renders/beauty.{frame:04d}.exr'
    Returns dict with frame result metadata.
    """
    hou.setFrame(frame)
    result = {"frame": frame, "attempts": 0, "issues": [], "fixes": [], "passed": False}

    for attempt in range(1, MAX_RETRIES + 1):
        result["attempts"] = attempt
        t0 = time.time()

        # --- Render ---
        rop_node.parm("soho_foreground").set(1)   # synchronous -- wait for file write
        rop_node.render(frame_range=(frame, frame, 1))
        elapsed = time.time() - t0

        # --- Validate ---
        image_path = output_template.format(frame=frame)
        checks = validate_frame(image_path)

        failed_checks = [name for name, (passed, _) in checks.items() if not passed]

        if not failed_checks:
            result["passed"]  = True
            result["elapsed"] = elapsed
            break   # frame is good -- advance to next

        # --- Fix ---
        for issue in failed_checks:
            result["issues"].append(issue)
            settings = apply_fix(issue, karma_node, settings, memory_fixes)
            result["fixes"].append(issue)

    return result


def render_sequence(start, end, rop_path, karma_path, output_template, memory_store=None):
    """
    Full sequence render with per-frame validate-fix loop and final report.
    """
    rop_node   = hou.node(rop_path)
    karma_node = hou.node(karma_path)

    # Classify scene and warm up settings from memory
    tags     = classify_scene()
    settings = warmup_render_settings(tags, memory_store) if memory_store else {}

    # Apply warmup settings to Karma LOP
    if "karma_samples" in settings:
        karma_node.parm("karma_samples").set(settings["karma_samples"])
    if "karma_maxpathdepth" in settings:
        karma_node.parm("karma_maxpathdepth").set(settings["karma_maxpathdepth"])
    if "karma_pixelfilterclamp" in settings:
        karma_node.parm("karma_pixelfilterclamp").set(settings["karma_pixelfilterclamp"])

    report = {"frames": [], "tags": list(tags), "settings_used": settings}

    for frame in range(start, end + 1):
        frame_result = render_frame_with_validation(
            frame, rop_node, karma_node, output_template, settings
        )
        report["frames"].append(frame_result)
        status = "OK" if frame_result["passed"] else "FAILED"
        print(f"  Frame {frame:04d}: {status} | attempts={frame_result['attempts']} | issues={frame_result['issues']}")

    # Save learned settings back to memory
    if memory_store and any(r["passed"] for r in report["frames"]):
        memory_store.add(
            content="render_farm learned settings",
            tags=list(tags) + ["render_settings"],
            data=settings
        )

    return report
```

### Key Karma Render Settings

```python
def apply_karma_render_settings(karma_node, preset="production"):
    """
    Apply standard Karma XPU render settings.

    LIGHTING LAW (never violate):
      - Light intensity is ALWAYS 1.0
      - Brightness is controlled ONLY via exposure (in stops)
      - Key:fill 3:1  =  log2(3)  =  1.585 stops difference
      - Key:fill 4:1  =  log2(4)  =  2.0   stops difference
    """

    presets = {
        "draft": {
            "karma_samples":          16,    # pixel samples -- low for fast previews
            "karma_maxpathdepth":      4,    # ray bounce depth -- 4 is minimal GI
            "karma_pixelfilterclamp": 10.0,  # clamp fireflies early
        },
        "production": {
            "karma_samples":         128,    # production quality
            "karma_maxpathdepth":      8,    # full GI, SSS-capable
            "karma_pixelfilterclamp": 10.0,  # keep clamped even in production
        },
        "beauty": {
            "karma_samples":         256,    # maximum -- use for hero frames only
            "karma_maxpathdepth":     12,    # deep GI for complex materials
            "karma_pixelfilterclamp": 50.0,  # slightly relaxed for accurate caustics
        },
    }

    cfg = presets.get(preset, presets["production"])
    for parm_name, value in cfg.items():
        parm = karma_node.parm(parm_name)
        if parm:
            parm.set(value)

    # Exposure parm uses an encoded USD attribute name (Houdini 21 convention)
    # xn__inputsexposure_vya  ->  inputs:exposure
    # xn__inputsexposure_control_wcb = "set"  (enable the override)
    exp_parm     = karma_node.parm("xn__inputsexposure_vya")
    exp_ctrl     = karma_node.parm("xn__inputsexposure_control_wcb")
    intensity_parm = karma_node.parm("xn__inputsintensity_i0a")

    if exp_parm and exp_ctrl:
        exp_parm.set(0.0)       # 0 stops = neutral; artist adjusts from here
        exp_ctrl.set("set")     # required to activate the override

    if intensity_parm:
        intensity_parm.set(1.0)  # ALWAYS 1.0 -- Lighting Law
```

### PDG / TOPs Render Farm

```python
def build_tops_render_farm(tops_net_path, rop_path, frame_start, frame_end):
    """
    Create a minimal TOPs network that distributes per-frame renders
    via the Local Scheduler.  For HQueue, swap the scheduler type below.

    PDG is acyclic -- it cannot express the validate-fix loop.
    Use Synapse's render_sequence() for that loop; use TOPs for raw
    distribution across machines.
    """
    net = hou.node(tops_net_path)
    if net is None:
        raise ValueError(f"TOPs network not found: {tops_net_path}")

    # --- ROP Fetch wraps a render ROP as a TOP work item ---
    rop_fetch = net.createNode("ropfetch", "render_frames")
    rop_fetch.parm("roppath").set(rop_path)

    # Generate one work item per frame
    rop_fetch.parm("framegeneration").set("perframe")       # one item = one frame
    rop_fetch.parm("startframe").set(frame_start)
    rop_fetch.parm("endframe").set(frame_end)
    rop_fetch.parm("increment").set(1)

    # --- Local Scheduler: concurrent renders on this machine ---
    scheduler = net.createNode("localscheduler", "local_farm")
    # How many frames to render simultaneously (leave headroom for Houdini)
    scheduler.parm("maxprocsmenu").set(2)   # 2 concurrent Karma processes

    # Connect ROP Fetch output to scheduler (scheduler node is context, not wired)
    # In TOPs, the scheduler is selected per-node via "schedulerpath" parm
    rop_fetch.parm("pdg_schedulerpath").set(scheduler.path())

    return rop_fetch, scheduler


def cook_tops_network(tops_rop_fetch_node):
    """
    Cook the TOPs network and block until all work items finish.
    Returns tuple: (total_items, failed_items).
    """
    import pdg

    graph = tops_rop_fetch_node.getPDGGraphContext()
    graph.cookWorkItems(block=True)   # block=True: synchronous, waits for completion

    all_items    = graph.workItems
    failed_items = [item for item in all_items if item.state == pdg.workItemState.CookedFail]

    print(f"TOPs complete: {len(all_items)} items, {len(failed_items)} failed")
    for item in failed_items:
        print(f"  FAILED item: {item.name} -- check $PDG_TEMP/{item.name}.log")

    return len(all_items), len(failed_items)


def hqueue_scheduler_setup(net_path, hqueue_server="hqueue-server:5000", client_list=None):
    """
    Create an HQueue Scheduler node for distributed farm rendering.
    client_list: list of hostnames, e.g. ["render01", "render02", "render03"]
    """
    net = hou.node(net_path)
    scheduler = net.createNode("hqueuescheduler", "hqueue_farm")

    # Point at the HQueue server
    scheduler.parm("hq_server").set(hqueue_server)

    # Assign to specific client machines (leave blank to use any available)
    if client_list:
        scheduler.parm("hq_clients").set(" ".join(client_list))

    # Job priority (1-10, higher = processed first)
    scheduler.parm("hq_priority").set(5)

    return scheduler
```

### Render Report Generation

```python
import datetime

def generate_report(report, output_path):
    """
    Write a Markdown render report.  Send a Windows toast notification on completion.
    """
    now   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Render Farm Report  {now}",
        f"",
        f"**Scene tags:** {', '.join(report['tags'])}",
        f"**Settings used:** {report['settings_used']}",
        f"",
        f"## Per-Frame Results",
        f"",
        f"| Frame | Status | Attempts | Issues | Fixes |",
        f"|-------|--------|----------|--------|-------|",
    ]
    total   = len(report["frames"])
    passed  = sum(1 for r in report["frames"] if r["passed"])
    failed  = total - passed

    for r in report["frames"]:
        status = "PASS" if r["passed"] else "FAIL"
        issues = ", ".join(r["issues"]) or "—"
        fixes  = ", ".join(r["fixes"])  or "—"
        lines.append(f"| {r['frame']:04d} | {status} | {r['attempts']} | {issues} | {fixes} |")

    lines += [
        f"",
        f"## Summary",
        f"",
        f"- Total frames: {total}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
    ]

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    # Windows toast notification (no third-party libs required)
    _toast(f"Render complete: {passed}/{total} frames passed", output_path)

    return output_path


def _toast(message, report_path):
    """Send a Windows 10/11 toast notification via PowerShell."""
    import subprocess
    ps_script = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
    $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
    $xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('Synapse Render Farm')) | Out-Null
    $xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{message}')) | Out-Null
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Synapse').Show($toast)
    """
    subprocess.run(
        ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
        creationflags=0x08000000   # CREATE_NO_WINDOW
    )
```

### Lighting Law Enforcement

```python
def enforce_lighting_law(stage_node_path="/stage"):
    """
    Scan every light prim in the USD stage and enforce:
      - intensity == 1.0  (ALWAYS -- Lighting Law)
      - exposure sets brightness (in stops, logarithmic)

    Key:fill ratios to stop differences:
      3:1  -> log2(3) = 1.585 stops  (key is 1.585 stops brighter than fill)
      4:1  -> log2(4) = 2.0   stops
    """
    import math
    from pxr import UsdLux, Gf

    stage = hou.node(stage_node_path).stage()
    violations = []

    for prim in stage.Traverse():
        light = UsdLux.LightAPI(prim)
        if not light:
            continue

        intensity_attr = light.GetIntensityAttr()
        if intensity_attr:
            val = intensity_attr.Get()
            if val is not None and abs(val - 1.0) > 1e-4:
                violations.append((str(prim.GetPath()), "intensity", val))
                # Fix: reset to 1.0
                intensity_attr.Set(1.0)

    if violations:
        print("Lighting Law violations found and corrected:")
        for path, attr, bad_val in violations:
            print(f"  {path}.{attr} was {bad_val:.4f} -> reset to 1.0")
    else:
        print("Lighting Law: all light intensities are 1.0. OK.")

    return violations


def stops_to_ratio(stops):
    """Convert an exposure stop difference to a key:fill intensity ratio."""
    import math
    return math.pow(2, stops)   # e.g. 1.585 stops -> 3.0 ratio


def ratio_to_stops(ratio):
    """Convert a key:fill ratio to an exposure stop difference."""
    import math
    return math.log2(ratio)     # e.g. ratio=4 -> 2.0 stops
```

## Expected Output

```
# Render sequence /out/usdrender1, frames 1001-1010, output /render/beauty.####.exr

Scene tags: ['interior', 'many_lights', 'has_environment']
Settings from memory warmup: {'karma_samples': 128, 'karma_maxpathdepth': 8, 'karma_pixelfilterclamp': 10.0}
  Frame 1001: OK       | attempts=1 | issues=— | fixes=—
  Frame 1002: OK       | attempts=1 | issues=— | fixes=—
  Frame 1003: FAILED   | attempts=3 | issues=saturation | fixes=saturation (samples 128->256)
  Frame 1004: OK       | attempts=1 | issues=— | fixes=—
  ...
  Frame 1010: OK       | attempts=2 | issues=underexposure | fixes=underexposure (+1 stop)

Summary: 10 frames, 9 passed, 1 failed
Report written to: /render/reports/render_report_2026-02-19.md
```

## Expected Scene Graph

For a correctly configured Karma/usdrender pipeline the relevant prim and node hierarchy is:

```
/stage
  /cameras
    /render_cam               (Camera LOP)
  /lights
    /dome                     (DomeLight -- intensity=1.0, exposure set via xn__inputsexposure_vya)
    /key                      (SphereLight -- intensity=1.0, exposure=1.0)
    /fill                     (SphereLight -- intensity=1.0, exposure=-0.585 for 3:1 ratio)
  /geo
    /hero_asset               (geometry prims)
  /materials
    /matlib
      /hero_shader            (MaterialX or VOP shader)

/out
  /usdrender1                 (usdrender ROP)
    loppath   -> /stage/karma1
    outputimage -> /render/beauty.####.exr
    soho_foreground = 1        (synchronous write -- required for validate-fix loop)

/stage
  /karma1                     (Karma LOP, camera=/cameras/render_cam)
    karma_samples = 128
    karma_maxpathdepth = 8
    karma_pixelfilterclamp = 10.0
    xn__inputsexposure_vya = 0.0      (neutral; artist adjusts)
    xn__inputsexposure_control_wcb = "set"
    xn__inputsintensity_i0a = 1.0     (ALWAYS 1.0 -- Lighting Law)
```

## Common Mistakes

```python
# MISTAKE 1: setting light intensity > 1.0 to control brightness
# This violates the Lighting Law and causes wildly different results
# across renderers (Karma, Arnold, RenderMan).
bad_light.parm("xn__inputsintensity_i0a").set(10.0)   # WRONG

# CORRECT: keep intensity at 1.0, use exposure stops
good_light.parm("xn__inputsintensity_i0a").set(1.0)         # always 1.0
good_light.parm("xn__inputsexposure_vya").set(2.0)          # +2 stops = 4x brighter
good_light.parm("xn__inputsexposure_control_wcb").set("set")  # activate override


# MISTAKE 2: forgetting soho_foreground=1 on the usdrender ROP
# Default is 0 (async). The render starts but the function returns immediately.
# The validate step then checks for a file that doesn't exist yet and fails.
rop_node.parm("soho_foreground").set(0)   # WRONG for validate-fix loops
rop_node.render()                          # returns before EXR is written

# CORRECT: synchronous render
rop_node.parm("soho_foreground").set(1)   # wait for file write to complete
rop_node.render()                          # EXR exists when this returns


# MISTAKE 3: using a wildcard material assignment path
# The prim pattern must exactly match the USD prim path.
# Wildcards (/**) can silently assign to the wrong prims.
matlib.parm("geopath1").set("/**")              # WRONG -- too broad
matlib.parm("geopath1").set("/geo/hero_asset")  # CORRECT -- exact path


# MISTAKE 4: building the TOPs network but forgetting to set the scheduler
# Without a scheduler node, TOPs falls back to the default and may not
# distribute correctly across machines.
rop_fetch.parm("pdg_schedulerpath").set("")      # WRONG -- uses default scheduler
rop_fetch.parm("pdg_schedulerpath").set(scheduler.path())  # CORRECT


# MISTAKE 5: assigning the camera using the Houdini node path instead of USD prim path
karma_node.parm("camera").set("/obj/cam1")            # WRONG -- Houdini path
karma_node.parm("camera").set("/cameras/render_cam")  # CORRECT -- USD prim path


# MISTAKE 6: not cooking the material library before creating shader children
# Without cook(), the internal subnet does not exist and createNode() returns None.
matlib = hou.node("/stage/materiallibrary1")
# matlib.createNode("mtlxstandard_surface", "hero_mat")  # WRONG -- returns None

matlib.cook(force=True)                              # required first
shader = matlib.createNode("mtlxstandard_surface", "hero_mat")  # now works
```
