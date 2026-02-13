# Solaris/LOP Node Types Reference

Comprehensive reference for Solaris (LOP context) node types in Houdini 21. Covers node types,
key parameter names (including the cryptic USD-mangled encodings), common workflows, and gotchas.

---

## Stage Management Nodes

### Stage Manager (`stagemanager`)
Top-level container for organizing the LOP graph. Provides a structured way to split work
into separate branches (geometry, lighting, materials) and merge them.

- Usually the entry point of a LOP network.
- Each branch can be cooked independently for faster iteration.

### Merge (`merge`)
Combines multiple LOP input streams into a single USD stage.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| (auto) | -- | -- | Inputs are merged in order; later inputs are stronger |

- **Workflow**: Wire geometry, lights, materials, and cameras as separate branches, then merge.
- **Gotcha**: If two inputs define the same prim path, the later (higher-numbered) input wins for conflicting attributes. This is sublayer-strength composition.

### Switch (`switch`)
Select one of multiple inputs to pass downstream.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Input Index | `input` | int | 0-based index of which input to pass through |

- Useful for toggling between lighting rigs, LOD levels, or render settings.
- Can be driven by expressions or channel references for automated switching.

### Null (`null`)
Pass-through node with no effect. Used as output markers and organizational anchors.

- **Convention**: Name your output null `OUTPUT` or `OUT` and set it as the display/render flag node.
- **Workflow**: Place nulls at branch endpoints before merge for clarity.
- Set the display flag (blue) on the null to mark it as the stage output for rendering.

### Configure Stage (`configurestage`)
Sets global stage metadata: up axis, meters per unit, default render settings.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Up Axis | `upaxis` | string | `"Y"` (default) or `"Z"` |
| Meters Per Unit | `metersperunit` | float | Scale factor (0.01 = cm, 1.0 = meters) |
| Start/End Frame | `startframe`, `endframe` | float | Stage time code range |
| FPS | `fps` | float | Frames per second |

---

## Geometry Nodes

### SOP Import (`sopimport`)
Imports SOP-level geometry into the USD stage as a Mesh prim.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| SOP Path | `soppath` | string | Path to SOP node (e.g., `/obj/geo1/OUT`) |
| Prim Path | `primpath` | string | Where to place in USD hierarchy (e.g., `/World/geo/mesh1`) |
| Path Prefix | `pathprefix` | string | Prefix added to all imported prim paths |
| Import Style | `importstyle` | menu | `"Flat"` or `"Hierarchy"` |
| Import at Frame | `importframe` | float | Which frame to cook the SOP at |
| Subset Groups | `subsetgroups` | string | SOP groups to import as GeomSubsets |

- **Workflow**: Model in SOPs, then bring into Solaris with `sopimport` for lighting/rendering.
- **Gotcha**: If the SOP has time-varying geometry (animated), set the import frame to `$F` to get per-frame data. Otherwise it imports a static frame.
- **Gotcha**: Attribute naming -- SOP `Cd` attribute maps to USD `displayColor`. SOP `N` maps to `normals`.
- Supports importing SOP groups as USD GeomSubsets for per-face material assignment.

### SOP Create (`sopcreate`)
Embeds a full SOP network inside a LOP node. The SOP network lives inside the LOP and outputs geometry directly to the USD stage.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Path | `primpath` | string | USD prim path for the output geometry |

- **Workflow**: Double-click to enter the embedded SOP network. Build geometry inside, then exit back to LOPs.
- Best for procedural geometry that only exists in the Solaris context (no separate SOP-level asset).
- The embedded SOP network has access to stage data via `lopinput` SOP nodes.

### Scene Import (`sceneimport`)
Imports an entire OBJ-level scene (geometry, lights, cameras) into USD in one step.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Objects | `objects` | string | Object-level path pattern (e.g., `/obj/*`) |
| Import Path Prefix | `importpathprefix` | string | USD path prefix (e.g., `/World`) |
| Display | `display` | menu | Import display, render, or both |

- **Workflow**: Quick way to bring a legacy OBJ-based scene into Solaris for USD rendering.
- Imports cameras and lights as their USD equivalents.
- **Gotcha**: Does not import SOP-level materials -- you need to reassign materials in LOPs.

### Sphere, Cube, Cone, Cylinder, Capsule (USD Primitives)
Create basic USD geometric shapes directly in LOPs.

| Node Type | Description | Default Prim Path |
|-----------|-------------|-------------------|
| `sphere` | USD Sphere | `/$OS` (node name) |
| `cube` | USD Cube | `/$OS` |
| `cone` | USD Cone | `/$OS` |
| `cylinder` | USD Cylinder | `/$OS` |
| `capsule` | USD Capsule | `/$OS` |

- These are lightweight USD shapes, not SOP geometry.
- Transform via an `edit` node downstream (set `tx`, `ty`, `tz`, `rx`, `ry`, `rz`, `sx`, `sy`, `sz`).
- **IMPORTANT**: There is NO `grid` or `plane` LOP node. Use a `cube` with `sy=0.01` for ground planes.

---

## Material Nodes

### Material Library (`materiallibrary`)
Container node that holds shader networks. Creates USD Material prims.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Material Path Prefix | `matpathprefix` | string | USD path prefix (e.g., `/materials`) |
| Material Name | `matname1` | string | Name of first material |

- **Workflow**: Create the node, dive inside to build shader graphs using MaterialX nodes.
- Inside the Material Library, create `mtlxstandard_surface` as the main shader, connect `mtlximage` nodes for textures, and wire to the material output.
- **CRITICAL GOTCHA**: After creating a `materiallibrary` node via Python, call `matlib.cook(force=True)` before creating child shader nodes. Without cooking, the internal subnet does not exist and `createNode()` returns `None`.

### Assign Material (`assignmaterial`)
Binds a material to geometry prims via pattern matching.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Pattern | `primpattern1` | string | Target prim USD path (e.g., `/World/geo/mesh1`) |
| Material Path | `matspecpath1` | string | Material USD path (e.g., `/materials/chrome`) |
| Number of Assignments | `nummaterials` | int | How many pattern/material pairs |

- Multiple assignments supported: increment suffix (`primpattern2`, `matspecpath2`, etc.).
- Supports wildcards: `/World/geo/*` assigns to all children.
- **Gotcha**: Pattern must match actual USD prim paths, not Houdini node paths. Verify paths with `houdini_stage_info` before assigning.

### Material Linker (`materiallinker`)
Advanced material assignment using collections and binding strength.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Collection Path | `collectionpath` | string | USD collection prim |
| Material Path | `materialpath` | string | Material to bind |
| Binding Strength | `bindingstrength` | menu | `"weakerThanDescendants"` or `"strongerThanDescendants"` |

- For complex scenes where simple pattern matching is insufficient.
- Collection-based binding can target arbitrary prim sets.

### MaterialX Standard Surface (`mtlxstandard_surface`)
The primary PBR shader for Karma. Created inside a Material Library.

| Parameter | Encoded Name | Type | Range |
|-----------|-------------|------|-------|
| Base Color R/G/B | `base_colorr`, `base_colorg`, `base_colorb` | float | 0-1 |
| Base Weight | `base` | float | 0-1 |
| Metalness | `metalness` | float | 0-1 |
| Specular Weight | `specular` | float | 0-1 |
| Specular Roughness | `specular_roughness` | float | 0-1 |
| Specular IOR | `specular_IOR` | float | 1.0-3.0 |
| Coat Weight | `coat` | float | 0-1 |
| Coat Roughness | `coat_roughness` | float | 0-1 |
| Transmission | `transmission` | float | 0-1 |
| Subsurface | `subsurface` | float | 0-1 |
| Emission Weight | `emission` | float | 0+ |
| Emission Color R/G/B | `emission_colorr`, `emission_colorg`, `emission_colorb` | float | 0-1 |
| Sheen | `sheen` | float | 0-1 |
| Opacity | `opacity` | float | 0-1 |
| Normal | `normal` | vector3 | tangent-space |

---

## Light Nodes

All lights obey the **Lighting Law**: intensity is ALWAYS 1.0 (never change it). Brightness
is controlled exclusively by **exposure** (logarithmic, in stops). This applies to ALL PBR
renderers (Karma, Arnold, RenderMan, V-Ray).

### Light Parameter Encoding (All Light Types)

USD attribute names are encoded into Houdini parameter names. These encodings are NOT intuitive.

| Attribute | Encoded Houdini Parm | Type | Notes |
|-----------|---------------------|------|-------|
| `inputs:intensity` | `xn__inputsintensity_i0a` | float | **Always 1.0** |
| `inputs:exposure` | `xn__inputsexposure_vya` | float | Brightness in stops |
| Exposure Control | `xn__inputsexposure_control_wcb` | string | Must be `"set"` to enable |
| `inputs:color` | `xn__inputscolor_kya` | vec3 | Light color RGB |
| `inputs:enableColorTemperature` | `xn__inputsenablecolortemperature_r5a` | bool | Use Kelvin temp |
| `inputs:colorTemperature` | `xn__inputscolortemperature_u5a` | float | Kelvin (e.g., 6500) |
| `inputs:texture:file` | `xn__inputstexturefile_i1a` | string | HDRI path (dome light) |

All lights also use standard transform parameters: `tx`, `ty`, `tz`, `rx`, `ry`, `rz`.

### Dome Light (`domelight`)
Environment/HDRI light that surrounds the entire scene.

| Parameter | Name | Notes |
|-----------|------|-------|
| Texture File | `xn__inputstexturefile_i1a` | HDRI map path (.exr, .hdr) |
| Texture Format | `xn__inputstextureformat_i7a` | `"automatic"`, `"latlong"`, `"mirroredBall"` |

- **Workflow**: Set HDRI file, exposure to 0-2 for ambient base, use as environment fill.
- **Gotcha**: Without an HDRI texture, the dome light emits uniform white light.
- Rotation (`ry`) rotates the HDRI environment.

### Distant Light (`distantlight`)
Parallel rays from a single direction. Simulates sun or directional light.

| Parameter | Name | Notes |
|-----------|------|-------|
| Angle | `xn__inputsangle_06a` | Angular diameter in degrees (0.53 = sun) |

- **Workflow**: Key light or sun. Set `rx` for elevation, `ry` for azimuth.
- Larger angle = softer shadows (like an overcast day).
- Position (`tx`, `ty`, `tz`) does not affect a distant light; only rotation matters.

### Rect Light (`rectlight`)
Rectangular area light.

| Parameter | Name | Notes |
|-----------|------|-------|
| Width | `xn__inputswidth_e5a` | Rectangle width |
| Height | `xn__inputsheight_k5a` | Rectangle height |
| Normalize | `xn__inputsnormalize_ida` | Keep brightness constant as size changes |

- **Workflow**: Soft fill light, window light, practical light simulation.
- Larger area = softer shadows. Enable normalize to prevent brightness changes when resizing.

### Sphere Light (`spherelight`)
Point/sphere light source.

| Parameter | Name | Notes |
|-----------|------|-------|
| Radius | `xn__inputsradius_o5a` | Sphere radius (0 = point light) |
| Treat As Point | `xn__inputstreataspointlight_control_cjb` | Force point light behavior |

- **Workflow**: Practical light sources (bulbs, candles, lamps).
- Radius > 0 produces soft shadows; radius = 0 produces hard point-light shadows.

### Disk Light (`disklight`)
Circular area light.

| Parameter | Name | Notes |
|-----------|------|-------|
| Radius | `xn__inputsradius_o5a` | Disk radius |

- **Workflow**: Spotlight-like soft source, stage light simulation.

### Cylinder Light (`cylinderlight`)
Tube/cylinder-shaped area light.

| Parameter | Name | Notes |
|-----------|------|-------|
| Length | `xn__inputslength_i5a` | Tube length |
| Radius | `xn__inputsradius_o5a` | Tube radius |

- **Workflow**: Fluorescent tubes, neon lights, linear light strips.

---

## Camera Nodes

### Camera (`camera`)
Creates a USD Camera prim.

| Parameter | USD Name | Type | Default | Notes |
|-----------|----------|------|---------|-------|
| Focal Length | `focalLength` | float | 50.0 | In mm. Lower = wider FOV |
| Horizontal Aperture | `horizontalAperture` | float | 36.0 | Sensor width mm (36 = full frame) |
| Vertical Aperture | `verticalAperture` | float | 24.0 | Sensor height mm |
| F-Stop | `fStop` | float | 0.0 | 0 = no DOF. Lower = shallower DOF |
| Focus Distance | `focusDistance` | float | 0.0 | In scene units. 0 = auto |
| Near Clip | `clippingRange[0]` | float | 0.1 | Minimum render distance |
| Far Clip | `clippingRange[1]` | float | 10000.0 | Maximum render distance |
| Position | `tx`, `ty`, `tz` | float | 0,0,0 | Camera position |
| Rotation | `rx`, `ry`, `rz` | float | 0,0,0 | Camera orientation (degrees) |

- **Gotcha**: Karma requires the camera as a USD prim path (`/cameras/render_cam`), NOT a Houdini node path (`/stage/render_cam`).
- **Workflow**: Create camera, position with `tx/ty/tz` and `rx/ry/rz`, then reference the USD prim path in render settings.

### Render Product (`renderproduct`)
Defines a render output (image file, resolution, AOVs).

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Product Name | `productname` | string | Output file path |
| Product Type | `producttype` | menu | `"raster"` (image) or `"deep"` |
| Resolution | `resx`, `resy` | int | Image resolution |
| Camera | `camera` | string | USD camera prim path |

- **Workflow**: Use for multi-output setups (main beauty + AOV passes to separate files).
- Wire into a Render Settings node.

### Render Settings (`rendersettings`)
Defines render delegate settings (which renderer, quality parameters).

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Render Delegate | `renderer` | string | `"BRAY_HdKarma"`, `"HdPrmanLoaderRendererPlugin"`, etc. |
| Camera | `camera` | string | USD camera prim path |
| Resolution | `resx`, `resy` | int | Override resolution |

- **Workflow**: Connects to Render Product nodes. Defines the render delegate and global quality settings.
- Can be used instead of or alongside `karmarenderproperties`.

---

## Render Nodes

### Karma Render Properties (`karmarenderproperties`)
Sets Karma-specific quality parameters as USD render settings on the stage.

| Parameter | Encoded Name | Default | Notes |
|-----------|-------------|---------|-------|
| Max Ray Samples | `karma:global:pathtracedsamples` | 64 | Production: 128-256 |
| Min Ray Samples | `karma:global:minpathtracedsamples` | 1 | Production: 16 |
| Pixel Oracle | `karma:global:pixeloracle` | `uniform` | `variance` for adaptive |
| Convergence Threshold | `karma:global:convergencethreshold` | 0.01 | Lower = cleaner |
| Max Diffuse Bounces | `karma:global:diffuselimit` | 2 | Production: 4-6 |
| Max Specular Bounces | `karma:global:reflectlimit` | 4 | Production: 6-8 |
| Volume Step Rate | `karma:global:volumesteprate` | 0.25 | Volumes: 0.5-1.0 |
| Enable Denoiser | `karma:global:enabledenoise` | 0 | 1 = OIDN denoiser |
| Shutter Open | `karma:global:shutteropen` | -0.25 | Motion blur start |
| Shutter Close | `karma:global:shutterclose` | 0.25 | Motion blur end |
| Engine | `engine` | -- | `"xpu"` (GPU) or `"cpu"` |

- **Workflow**: Place in LOP graph before the output null. Affects all renders from this stage.
- For preview: 16-32 samples, `uniform` oracle. For production: 128+ samples, `variance` oracle.

### Render Geometry Settings (`rendergeometrysettings`)
Apply render-time geometry properties to prims (subdivision, displacement, visibility).

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Pattern | `primpattern` | string | USD prim path pattern |
| Subdivision Scheme | `karma:object:subdivscheme` | string | `"catmullClark"`, `"loop"`, `"none"` |
| Dicing Quality | `karma:object:dicingquality` | float | 1.0 = standard, higher = finer |
| Displacement Bound | `karma:object:displacementbound` | float | Must be >= max displacement |
| Render Visibility | `karma:object:rendervisibility` | string | Camera, shadow, diffuse, etc. |
| Xform Motion Samples | `karma:object:xform_motionsamples` | int | 2+ for motion blur |
| Geo Motion Samples | `karma:object:geo_motionsamples` | int | 2+ for deformation blur |

- **Workflow**: Apply after geometry import to control subdivision and displacement per-object.
- **Gotcha**: `displacementbound` must be set correctly or geometry clips. Too large wastes memory.

### USD Render ROP (`usdrender_rop` in /stage, `usdrender` in /out)
The render driver that cooks the LOP stage and delegates to a render engine.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| LOP Path | `loppath` | string | Path to LOP display node (e.g., `/stage/OUT`) |
| Renderer | `renderer` | string | `BRAY_HdKarma` for Karma |
| Override Camera | `override_camera` | string | USD prim path (e.g., `/cameras/render_cam`) |
| Override Resolution | `override_res` | string | `""`, `"scale"`, `"specific"` (**string, not int!**) |
| Width | `res_user1` | int | Resolution width (when `override_res="specific"`) |
| Height | `res_user2` | int | Resolution height |
| Output Image | `outputimage` | string | Render output file path |

- **Gotcha**: `override_res` is a string menu, not an integer. Use `"specific"` to enable custom resolution.
- **Gotcha**: `rop.render(output_file=...)` does NOT work for usdrender ROPs. Set `outputimage` parm directly.
- **Gotcha**: ROPs in `/out` need `loppath` set to a valid LOP node. The Synapse handler auto-discovers the display node in `/stage`.

### Karma ROP (in /out)
Native Karma render driver (alternative to the generic `usdrender` ROP).

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Picture | `picture` | string | Output file path |
| Camera | `camera` | string | USD prim path |
| Engine | `engine` | string | `"xpu"` (GPU) or `"cpu"` |
| Resolution X | `resolutionx` | int | Width pixels |
| Resolution Y | `resolutiony` | int | Height pixels |

- Karma XPU is GPU-accelerated and is the default for most work.
- Use Karma CPU for nested dielectrics, complex SSS, or volumes with many scattering events.
- **Gotcha**: Karma XPU has a 10-15 second delay between `render()` returning and the file being fully flushed to disk.

---

## Layout and Scene Structure Nodes

### Edit (`edit`)
Transform, modify attributes, or set metadata on existing USD prims.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Pattern | `primpattern` | string | USD prim path or pattern |
| Translate | `tx`, `ty`, `tz` | float | Translation |
| Rotate | `rx`, `ry`, `rz` | float | Rotation in degrees |
| Scale | `sx`, `sy`, `sz` | float | Scale |

- **Workflow**: Primary node for positioning, rotating, and scaling prims after creation.
- Handles the full USD xform stack correctly (translate, rotateXYZ, scale in proper order).
- **Gotcha**: Do NOT set `xformOp:translate` directly via USD attribute. Use `edit` instead -- it manages the xformOpOrder properly.

### Edit Properties (`editproperties`)
Set arbitrary USD attributes and metadata on prims without using a Python LOP.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Pattern | `primpattern` | string | Target prim paths |
| Properties | (dynamic) | varies | Add attribute name/value pairs |

- **Workflow**: Set custom attributes, visibility, purpose, or any USD metadata.
- More user-friendly than a Python LOP for simple attribute edits.

### Configure Primitives (`configureprimitive`)
Set prim-level metadata: kind, purpose, active state, instanceable flag.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Prim Pattern | `primpattern` | string | Target prims |
| Kind | `kind` | menu | `"component"`, `"group"`, `"assembly"`, `"subcomponent"` |
| Purpose | `purpose` | menu | `"default"`, `"render"`, `"proxy"`, `"guide"` |
| Active | `active` | bool | Deactivated prims are invisible to traversal |
| Instanceable | `instanceable` | bool | Enable native USD instancing |

- **Workflow**: Mark prims as `component` kind for asset browsers. Set `purpose=proxy` for viewport stand-ins.
- `kind=component` is required for assets to be recognized in many USD pipelines.
- `instanceable=True` enables GPU instancing for identical referenced assets.

### Layout (`layout`)
Interactive placement of USD assets in the viewport.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| USD Files | `files` | string | Paths to USD files to scatter |
| Brush Size | `brushsize` | float | Scatter radius |
| Scale Range | `scalemin`, `scalemax` | float | Random scale range |

- **Workflow**: Paint/scatter USD assets interactively in the viewport. Used for environment dressing.
- Supports brush-based placement, snapping to surfaces, random rotation and scale.

### Instancer (`instancer`)
Create USD point instances from a point source.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Point Source | `pointsource` | string | SOP or LOP path providing instance points |
| Prototype Source | `protosource` | menu | Where prototypes come from |
| Prototype Paths | `protopath1` | string | USD paths of prototype prims |

- **Workflow**: Scatter thousands of instances (trees, rocks, crowd agents) from point clouds.
- Much faster than individual references -- uses USD native PointInstancer.
- Point attributes control per-instance transforms: `orient`, `scale`, `pscale`, `instanceId`.

### Reference (`reference`)
Import external USD files as references under a target prim path.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| File Path | `filepath1` | string | Path to .usd/.usdc/.usda |
| Prim Path | `primpath` | string | Target prim (e.g., `/World/building`) |
| Reference Type | `reftype` | menu | `"Reference"` or `"Payload"` |

- References are always loaded. Payloads can be deferred for heavy assets.
- Referenced content can be overridden by stronger composition arcs (Local, Inherit, Variant).

### Sublayer (`sublayer`)
Merge an entire USD layer into the current stage.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| File Path | `filepath1` | string | Path to USD file |
| Layer Position | `position` | menu | Strongest or weakest sublayer |

- **Workflow**: Layer lighting rigs, animation caches, or department overrides on top of a base stage.
- Later sublayers (strongest position) win on attribute conflicts.

### Component Output (`componentoutput`)
Package geometry, materials, and variants into a self-contained USD asset.

| Parameter | Name | Type | Notes |
|-----------|------|------|-------|
| Output File | `lopoutput` | string | Output .usd file path |
| Component Name | `componentname` | string | Root prim name |
| Thumbnail | `thumbnail` | bool | Generate thumbnail image |

- **Workflow**: Final step when publishing an asset. Creates a properly structured component with materials embedded.
- Automatically sets `kind=component` on the root prim.
- Can generate variant sets from multiple input branches (e.g., LODs, material variations).

---

## Common Parameter Names Across Nodes

Many Solaris nodes share parameter naming patterns. This table covers the most frequently used ones.

### Transform Parameters (shared by edit, lights, cameras)

| Purpose | Parm Names | Notes |
|---------|-----------|-------|
| Translation | `tx`, `ty`, `tz` | World-space position |
| Rotation | `rx`, `ry`, `rz` | Degrees, XYZ order |
| Scale | `sx`, `sy`, `sz` | Uniform: set all three equal |

### Prim Targeting (shared by edit, assign material, render geometry settings, configure primitives)

| Purpose | Parm Name | Notes |
|---------|-----------|-------|
| Prim Pattern | `primpattern` | USD prim path or glob pattern (e.g., `/World/geo/*`) |

### USD Path Parameters

| Purpose | Parm Name | Used By |
|---------|-----------|---------|
| SOP Path | `soppath` | sopimport, sopcreate |
| File Path | `filepath1` | reference, sublayer |
| Material Path | `matspecpath1` | assignmaterial |
| Camera Path | `camera`, `override_camera` | rendersettings, usdrender ROP |
| LOP Path | `loppath` | usdrender ROP (in /out) |

### Light Encoded Parameters (all light types)

| Purpose | Encoded Name | Plain Name |
|---------|-------------|------------|
| Intensity | `xn__inputsintensity_i0a` | Always 1.0 |
| Exposure | `xn__inputsexposure_vya` | Brightness in stops |
| Exposure Control | `xn__inputsexposure_control_wcb` | Must be `"set"` |
| Color | `xn__inputscolor_kya` | RGB vec3 |
| Color Temp Enable | `xn__inputsenablecolortemperature_r5a` | bool |
| Color Temperature | `xn__inputscolortemperature_u5a` | Kelvin float |
| Texture File | `xn__inputstexturefile_i1a` | HDRI path (dome) |

### Karma Render Quality Parameters

| Purpose | Encoded Name | Typical Values |
|---------|-------------|----------------|
| Max Samples | `karma:global:pathtracedsamples` | Preview: 16-32, Production: 128-256 |
| Min Samples | `karma:global:minpathtracedsamples` | Preview: 1, Production: 16 |
| Pixel Oracle | `karma:global:pixeloracle` | `"uniform"` or `"variance"` |
| Convergence | `karma:global:convergencethreshold` | 0.01-0.001 |
| Diffuse Bounces | `karma:global:diffuselimit` | Preview: 1-2, Production: 4-6 |
| Specular Bounces | `karma:global:reflectlimit` | Preview: 2-4, Production: 6-8 |
| Volume Step | `karma:global:volumesteprate` | Preview: 0.1, Production: 0.5-1.0 |
| Denoiser | `karma:global:enabledenoise` | 0 = off, 1 = OIDN |

---

## Common Workflows

### Minimal Scene Setup (Geometry + Light + Camera + Render)

```
sopimport (geometry) --\
                        \
domelight (environment) ---> merge --> karmarenderproperties --> null (OUTPUT)
                        /
camera ----------------/
```

1. `sopimport` brings SOP geometry to USD.
2. `domelight` provides environment lighting.
3. `camera` defines the render viewpoint.
4. `merge` combines all branches.
5. `karmarenderproperties` sets quality.
6. `null` named `OUTPUT` is set as display flag.
7. Render via a `usdrender` ROP in `/out` pointing `loppath` at the output null.

### Material Assignment Workflow

```
sopimport --> materiallibrary --> assignmaterial --> merge (with lights/camera)
```

1. Import geometry.
2. Create Material Library with shaders inside.
3. Assign Material binds shader to geometry prims.
4. Merge into the main stage.

### Asset Publishing (Component Output)

```
sopimport --> materiallibrary --> assignmaterial --> configureprimitive (kind=component) --> componentoutput
```

### Progressive Render Validation

1. Test at 256x256, 4-8 samples, no displacement, no SSS.
2. Confirm output exists and is not black.
3. Scale to 1280x720, 32-64 samples.
4. Final at 1920x1080, 128+ samples, enable denoiser.

---

## Gotchas Summary

| Issue | Solution |
|-------|----------|
| `materiallibrary` child `createNode()` returns `None` | Call `matlib.cook(force=True)` first |
| `rop.render(output_file=...)` does nothing | Set `outputimage` or `picture` parm directly |
| Camera not found in render | Use USD prim path (`/cameras/cam`), not node path (`/stage/cam`) |
| `override_res` not working | It is a string: `""`, `"scale"`, `"specific"` -- not int |
| No `grid`/`plane` LOP node | Use `cube` with `sy=0.01` |
| Transforms not applying | Use `edit` node, not direct USD `xformOp:translate` attribute set |
| Black render | Check: camera assigned, loppath set, lights exist with exposure > 0 |
| `soho_foreground=1` hangs Houdini | Never use foreground rendering for heavy scenes |
| Material not showing | Verify prim pattern matches actual USD paths (use `stage_info` to check) |
| Displacement clipping | Set `karma:object:displacementbound` >= max displacement value |
| Karma XPU file missing after render | Wait 10-15 seconds -- XPU has delayed file flush |
| Encoded light parm wrong name | Use exact encoding: `xn__inputsexposure_vya`, not `intensity` or `exposure` (Synapse aliases handle this automatically) |
