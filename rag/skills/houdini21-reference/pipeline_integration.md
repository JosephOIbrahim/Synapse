# VFX Pipeline Integration

## Studio File Conventions

### Houdini Environment Variables
- `$HIP` — Directory containing the current .hip file
- `$HIPNAME` — Name of the current .hip file (without extension)
- `$HIPFILE` — Full path to the current .hip file
- `$JOB` — Project root directory (set in houdini.env or via pipeline)
- `$HOUDINI_PATH` — Search path for HDAs, scripts, otls

### Shot-Based File Structure
```
$JOB/
  shots/
    SH010/
      houdini/
        SH010_fx_v001.hip
        SH010_fx_v002.hip
      cache/
        bgeo/
          SH010_debris_v001.$F4.bgeo.sc
        vdb/
          SH010_pyro_v001.$F4.vdb
      render/
        beauty/
          SH010_beauty_v001.$F4.exr
        aov/
          SH010_N_v001.$F4.exr
  assets/
    characters/
      hero/
        hero_model_v003.usd
        hero_rig_v002.usd
    environments/
      city/
        city_layout_v001.usd
```

### Version Numbering
- Use `_v001`, `_v002` etc. (3-digit zero-padded)
- Increment version on every publish (never overwrite)
- WIP files: `_wip` suffix (not versioned)
- Frame padding: `$F4` for 4-digit (0001-9999)

### Cache File Formats
| Format | Use Case | Notes |
|--------|----------|-------|
| `.bgeo.sc` | SOP geometry (Blosc compressed) | Default for Houdini caches |
| `.vdb` | Volumes (pyro, FLIP surface) | OpenVDB format |
| `.abc` | Alembic (cross-app geometry) | Character animation export |
| `.usd/.usdc/.usda` | USD (scene description) | Layout, lighting, assembly |
| `.exr` | Renders (HDR, multi-channel) | Always EXR for production |
| `.rat` | Mantra textures (mipmapped) | Karma uses `.tex` or `.exr` |

## ShotGrid / Ftrack Integration

### Concepts
- **Project**: Top-level container for all shots and assets
- **Sequence**: Group of shots (SEQ010, SEQ020)
- **Shot**: Single camera cut (SH010, SH020)
- **Asset**: Reusable element (character, prop, environment)
- **Task**: Assignable work unit (anim, fx, light, comp)
- **Version**: Published output with review media
- **Status**: wtg (waiting), ip (in progress), rev (review), apr (approved)

### Publishing Workflow
1. Artist works in local WIP file (`SH010_fx_wip.hip`)
2. Save versioned file (`SH010_fx_v003.hip`)
3. Publish: export caches/renders to structured path
4. Register version in ShotGrid with thumbnail + review media
5. Submit for review (status: rev)
6. Supervisor approves/requests changes

### ShotGrid API Patterns (Python)
```python
# Typical publish script structure
import shotgun_api3
sg = shotgun_api3.Shotgun(url, script_name, api_key)
version = sg.create("Version", {
    "project": {"type": "Project", "id": proj_id},
    "entity": {"type": "Shot", "id": shot_id},
    "sg_task": {"type": "Task", "id": task_id},
    "code": "SH010_fx_v003",
    "sg_path_to_frames": "/render/SH010_beauty_v003.####.exr",
})
```

## Render Farm Submission

### Deadline (Thinkbox)
- Industry standard render farm manager
- Houdini submitter plugin: `Houdini > Render > Submit to Deadline`
- Key settings: frame range, priority, pool, group, chunk size
- Chunk size: 1 frame for simulations, 5-10 for renders
- Environment: passes Houdini env vars ($JOB, $HIP) to farm nodes

### Tractor (Pixar)
- Used at Pixar and some studios
- Job = Tasks + Commands in a dependency graph
- `tractor-blade` executes on each render node

### HQueue (SideFX)
- Built into Houdini, free
- Good for small studios or personal farms
- Runs from Houdini: Render > HQueue Simulation / HQueue Render
- Automatic frame distribution

### Farm Submission Best Practices
- Lock all texture/asset paths to absolute or $JOB-relative
- Pre-flight check: verify all dependencies resolve
- Use .bgeo.sc or .vdb for simulation caches (not .hip)
- Set appropriate priority: sim > render > comp
- Chunk simulations by 1 frame (they must be sequential)
- Chunk renders by 5-10 frames for efficiency

## ACES Color Management

### What is ACES
- Academy Color Encoding System
- Industry standard for color management in VFX
- Linear workflow with wide-gamut working space
- Ensures consistent color across software (Houdini, Nuke, Maya, DaVinci)

### ACES in Houdini
- Set via: Edit > Color Settings > OCIO Config
- Config file: typically `aces_1.2/config.ocio`
- Working space: `ACES - ACEScg` (linear, AP1 gamut)
- Display: `ACES/sRGB` or `ACES/Rec.709`

### Color Space Rules
| Asset Type | Color Space |
|------------|-------------|
| Diffuse/albedo textures | sRGB (input transform applied) |
| HDR environment maps | ACEScg (linear) |
| Normal maps | Raw/Utility (no transform) |
| Roughness/metalness | Raw/Utility (no transform) |
| Displacement maps | Raw/Utility (no transform) |
| Render output | ACEScg (EXR, linear) |
| Review media | sRGB or Rec.709 (display transform applied) |

### Common ACES Gotchas
- Textures in sRGB MUST have input transform applied (or colors are wrong)
- Renders must be saved as EXR in linear space (never sRGB)
- Display transform (ODT) applied in viewer/comp, NOT baked into EXR
- HDRIs should be in ACEScg, not scene-linear Rec.709

## Review Tools

### RV (Autodesk)
- Standard review tool at most studios
- Supports EXR, multi-channel, stereo, annotation
- Python API for custom tools and pipeline integration

### SyncSketch
- Web-based review tool
- Real-time drawing/annotation on frames
- Integration with ShotGrid for status updates

### Houdini MPlay
- Built-in image viewer
- Supports flipbook playback
- Can load EXR sequences with AOV channels
- Not used for client review (no annotation)

## Asset Management Patterns

### USD-Based Pipeline
```
/assets/
  hero_character/
    hero_character.usd          # Top-level asset (references below)
    model/
      hero_model_v003.usd       # Geometry
    material/
      hero_material_v002.usd    # MaterialX shaders
    rig/
      hero_rig_v002.usd         # KineFX or skeleton
```

### Asset Composition
- Assets published as self-contained USD files
- Shot files reference (not sublayer) assets
- Overrides via session layer or stronger opinion
- Variant sets for LOD (proxy/render) or look variations

### Naming Conventions
- lowercase_with_underscores (no spaces, no camelCase)
- Prefix with asset type: `char_hero`, `prop_sword`, `env_city`
- Version suffix: `_v001`
- Frame suffix: `.$F4` or `.####`

## File I/O Best Practices

### Cache Nodes
- `filecache` SOP: one-stop shop for geometry caching
- Set `file` to `$HIP/cache/$HIPNAME.$OS.$F4.bgeo.sc`
- Enable `Load from Disk` after caching for playback
- Use `Preroll` for simulation warm-up frames

### USD Layer Save
- `usd_rop` or `usdrender_rop` for writing USD layers
- Save lighting as separate layer: `$HIP/layers/lighting.usd`
- Strongest opinion wins (LIVRPS)

### Dependency Tracking
- Houdini's `opfullpath()` and `opinputpath()` for node references
- File SOP records source path in detail attributes
- USD references maintain original asset paths
- Always use relative paths ($HIP, $JOB) for portability
