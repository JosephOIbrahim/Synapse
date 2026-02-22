# VFX Pipeline Integration

## Triggers
pipeline, publish, shotgrid, ftrack, deadline, render farm, aces, hqueue,
version, cache, file structure, shot, asset management, usd pipeline

## Context
VFX pipeline integration in Houdini: file conventions, shot structure,
ShotGrid publishing, render farm submission, ACES color, cache management.
All code is Houdini Python.

## Code

```python
# Shot-based file structure and environment setup
import hou
import os

# Standard shot directory layout
SHOT_TEMPLATE = {
    "houdini":      "$JOB/shots/{shot}/houdini/",
    "cache_bgeo":   "$JOB/shots/{shot}/cache/bgeo/",
    "cache_vdb":    "$JOB/shots/{shot}/cache/vdb/",
    "render_beauty":"$JOB/shots/{shot}/render/beauty/",
    "render_aov":   "$JOB/shots/{shot}/render/aov/",
}

# Cache file formats
CACHE_FORMATS = {
    ".bgeo.sc": "SOP geometry (Blosc compressed) -- default for Houdini caches",
    ".vdb":     "Volumes (pyro, FLIP surface) -- OpenVDB format",
    ".abc":     "Alembic (cross-app geometry) -- character animation export",
    ".usd":     "USD scene description -- layout, lighting, assembly",
    ".exr":     "Renders (HDR, multi-channel) -- always EXR for production",
}

# Versioning convention: _v001, _v002 (3-digit zero-padded)
# Frame padding: $F4 for 4-digit (0001-9999)

def setup_shot_env(shot_name, job_path):
    """Set up environment variables for a shot."""
    hou.putenv("JOB", job_path)
    hou.putenv("SHOT", shot_name)

    # Create directories
    for key, template in SHOT_TEMPLATE.items():
        path = template.format(shot=shot_name)
        expanded = hou.expandString(path)
        os.makedirs(expanded, exist_ok=True)

    print(f"Shot environment: {shot_name}")
    print(f"  $JOB = {job_path}")
    for key, template in SHOT_TEMPLATE.items():
        print(f"  {key}: {template.format(shot=shot_name)}")


setup_shot_env("SH010", "D:/HOUDINI_PROJECTS_2025/show_01")
```

```python
# File cache setup with proper naming conventions
import hou

def create_versioned_cache(geo_path, source_node_name, cache_type="bgeo",
                           shot="SH010", version=1):
    """Create a properly versioned file cache node.
    cache_type: 'bgeo' for geometry, 'vdb' for volumes."""
    geo = hou.node(geo_path)
    source = geo.node(source_node_name)
    if not geo or not source:
        return

    cache = geo.createNode("filecache", f"{source_node_name}_cache")
    cache.setInput(0, source)

    ext = ".bgeo.sc" if cache_type == "bgeo" else ".vdb"
    version_str = f"v{version:03d}"

    # Standard naming: $JOB/shots/SHOT/cache/TYPE/SHOT_NAME_VERSION.$F4.ext
    output_path = (
        f"$JOB/shots/{shot}/cache/{cache_type}/"
        f"{shot}_{source_node_name}_{version_str}.$F4{ext}"
    )
    cache.parm("sopoutput").set(output_path)
    cache.parm("trange").set(1)  # Render Frame Range

    # Null output marker
    null = geo.createNode("null", f"OUT_{source_node_name}")
    null.setInput(0, cache)
    null.setDisplayFlag(True)
    null.setRenderFlag(True)

    geo.layoutChildren()
    print(f"Cache: {output_path}")
    return cache


create_versioned_cache("/obj/fx_geo", "pyro_sim", cache_type="vdb", shot="SH010", version=3)
```

```python
# ShotGrid publish script structure
import hou

def publish_version(sg, project_id, shot_id, task_id,
                    shot_name, department, version_num, frame_path):
    """Publish a version to ShotGrid.
    sg: shotgun_api3.Shotgun instance (already authenticated)."""
    code = f"{shot_name}_{department}_v{version_num:03d}"

    version = sg.create("Version", {
        "project": {"type": "Project", "id": project_id},
        "entity": {"type": "Shot", "id": shot_id},
        "sg_task": {"type": "Task", "id": task_id},
        "code": code,
        "sg_path_to_frames": frame_path,
        "sg_status_list": "rev",  # Submit for review
    })
    print(f"Published: {code} (Version ID: {version['id']})")
    return version


def generate_thumbnail(render_path, output_jpg, frame=1001):
    """Generate review thumbnail from EXR render.
    Uses iconvert from $HFS/bin/ for EXR-to-JPEG."""
    import subprocess
    hfs = hou.expandString("$HFS")
    iconvert = os.path.join(hfs, "bin", "iconvert.exe")

    exr_path = render_path.replace("$F4", f"{frame:04d}")
    expanded = hou.expandString(exr_path)

    subprocess.run([iconvert, expanded, output_jpg], check=True)
    print(f"Thumbnail: {output_jpg}")


# Usage:
# import shotgun_api3
# sg = shotgun_api3.Shotgun(url, script_name, api_key)
# publish_version(sg, 100, 200, 300, "SH010", "fx", 3,
#                 "/render/SH010_beauty_v003.####.exr")
```

```python
# Render farm submission helpers
import hou

FARM_SETTINGS = {
    "simulation": {"chunk_size": 1, "priority": 80, "note": "Sequential -- must be 1 frame chunks"},
    "render":     {"chunk_size": 10, "priority": 50, "note": "Can parallelize across frames"},
    "comp":       {"chunk_size": 20, "priority": 30, "note": "Lightweight, large chunks ok"},
}

def preflight_check(rop_path):
    """Pre-flight validation before farm submission."""
    rop = hou.node(rop_path)
    if not rop:
        print(f"ROP not found: {rop_path}")
        return False

    issues = []

    # Check output path is set
    for parm_name in ["outputimage", "sopoutput", "picture"]:
        p = rop.parm(parm_name)
        if p and p.eval() == "":
            issues.append(f"Empty output path: {parm_name}")

    # Check frame range
    trange = rop.evalParm("trange") if rop.parm("trange") else 0
    if trange == 0:
        issues.append("Frame range set to 'Render Current Frame' -- set to 'Render Frame Range'")

    # Check for absolute or $JOB-relative paths
    for parm_name in ["outputimage", "sopoutput"]:
        p = rop.parm(parm_name)
        if p:
            val = p.rawValue()
            if val and not val.startswith("$") and not val.startswith("/") and ":" not in val:
                issues.append(f"Relative path in {parm_name}: {val} -- use $JOB or $HIP prefix")

    if issues:
        print(f"Pre-flight FAILED ({len(issues)} issues):")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("Pre-flight PASSED")
        return True


preflight_check("/out/karma_render")
```

```python
# ACES color management configuration
import hou

ACES_COLOR_SPACES = {
    "diffuse_texture": "sRGB",           # Input transform applied
    "hdr_environment": "ACEScg",          # Linear, wide gamut
    "normal_map":      "Utility - Raw",   # No transform
    "roughness_map":   "Utility - Raw",   # No transform
    "displacement":    "Utility - Raw",   # No transform
    "render_output":   "ACEScg",          # EXR, linear
    "review_media":    "sRGB",            # Display transform applied
}

def configure_aces(config_path="$OCIO"):
    """Verify ACES configuration.
    Working space: ACES - ACEScg (linear, AP1 gamut).
    Display: ACES/sRGB or ACES/Rec.709."""
    ocio_path = hou.expandString(config_path)
    print(f"OCIO config: {ocio_path}")
    print("Working space: ACEScg (linear)")
    print("\nColor space assignments:")
    for asset_type, space in ACES_COLOR_SPACES.items():
        print(f"  {asset_type}: {space}")
    print("\nRules:")
    print("  - Textures in sRGB MUST have input transform applied")
    print("  - Renders saved as EXR in linear space (never sRGB)")
    print("  - Display transform (ODT) in viewer/comp, NOT baked into EXR")
    print("  - HDRIs should be ACEScg, not scene-linear Rec.709")


configure_aces()
```

```python
# USD-based asset management
import hou

def setup_usd_asset_structure(asset_name, asset_type="prop", job_path=None):
    """Create USD asset directory structure.
    asset_type: 'char', 'prop', 'env'
    Publishes as self-contained USD files."""
    if not job_path:
        job_path = hou.expandString("$JOB")

    prefix = f"{asset_type}_{asset_name}"
    base = f"{job_path}/assets/{asset_type}/{asset_name}"

    structure = {
        "root":     f"{base}/{prefix}.usd",
        "model":    f"{base}/model/{prefix}_model_v001.usd",
        "material": f"{base}/material/{prefix}_material_v001.usd",
        "rig":      f"{base}/rig/{prefix}_rig_v001.usd",
    }

    import os
    for key, path in structure.items():
        os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"USD asset structure: {prefix}")
    for key, path in structure.items():
        print(f"  {key}: {path}")

    # Naming conventions:
    # lowercase_with_underscores (no spaces, no camelCase)
    # Prefix with asset type: char_hero, prop_sword, env_city
    # Version suffix: _v001
    # Frame suffix: .$F4
    return structure


setup_usd_asset_structure("sword", asset_type="prop")
```

## Common Mistakes
- Relative paths in cache/render output -- always use $JOB or $HIP prefix for farm portability
- Overwriting versions instead of incrementing -- never reuse version numbers
- Chunking simulations > 1 frame -- simulations must be sequential (chunk=1)
- Saving renders as sRGB -- always save as linear EXR for compositing
- Missing $OCIO environment variable -- ACES requires it for all color-aware nodes
- Using .bgeo instead of .bgeo.sc -- Blosc compression is 3-5x smaller, same read speed
