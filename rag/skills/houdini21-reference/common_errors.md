# Common Houdini Errors and Solutions

## Node and Path Errors

### 1. "Cook error" on MaterialLibrary child nodes
**Symptom**: `createNode()` returns None when creating shader inside materiallibrary
**Cause**: MaterialLibrary internal subnet doesn't exist until first cook
**Fix**: Call `matlib.cook(force=True)` before `createNode()` on children

### 2. "Unable to find node" / Node path doesn't exist
**Symptom**: `hou.node("/path")` returns None
**Cause**: Wrong path, node deleted, or context mismatch (SOP vs LOP)
**Fix**: Check path with `hou.node("/obj").children()` or `hou.node("/stage").children()`

### 3. Node type not found / "No operator type"
**Symptom**: `createNode("nodetype")` fails
**Cause**: Misspelled node type, or HDA not installed
**Fix**: Check available types with `hou.nodeType(hou.sopNodeTypeCategory(), "nodetype")`. Common misspellings: `attribwrangle` (not `attributewrangle`), `copytopoints` (not `copy_to_points`)

## Parameter Errors

### 4. "Parameter not found" on USD/LOP nodes
**Symptom**: `node.parm("intensity")` returns None on a light LOP
**Cause**: USD parameters use encoded names (e.g. `xn__inputsintensity_i0a`)
**Fix**: Use Synapse's USD alias resolution or check `node.parms()` for actual names. Common mappings: `intensity` -> `xn__inputsintensity_i0a`, `exposure` -> `xn__inputsexposure_vya`

### 5. "Keyframe won't set" or "Channel not created"
**Symptom**: `setKeyframe()` has no effect
**Cause**: Parameter is controlled by expression, or is locked
**Fix**: Delete expression first: `parm.deleteAllKeyframes()`, then set keyframe. Check locked: `parm.isLocked()`

### 6. Parm tuple mismatch
**Symptom**: Setting a color or position fails silently
**Cause**: Using `setParms()` with single value on a tuple parm (tx/ty/tz, color r/g/b)
**Fix**: Use `parmTuple()` for vector parms: `node.parmTuple("t").set((1, 2, 3))`

## Render Errors

### 7. "Render output is black" or "No camera found"
**Symptom**: Karma renders a black frame
**Cause**: Camera not assigned, wrong camera path format, or empty stage
**Fix**: Ensure camera uses USD prim path (`/cameras/cam1`), not node path. Check `loppath` on usdrender ROP. Verify lights exist with exposure > 0.

### 8. "Permission denied" on render output
**Symptom**: Render fails with file write error
**Cause**: Output directory doesn't exist or path has spaces without quotes
**Fix**: Create output directory first. Use `$HIP/render/` as base path.

### 9. Fireflies (bright pixel artifacts)
**Symptom**: Random bright pixels in render
**Cause**: Intensity > 1.0 (Lighting Law violation), roughness = 0.0, or insufficient samples
**Fix**: Keep intensity at 1.0, use exposure for brightness. Set minimum roughness 0.001. Increase samples to 128+.

### 10. Render takes forever / hangs
**Symptom**: Render never completes or is extremely slow
**Cause**: Too many bounces, huge resolution, unoptimized volumes
**Fix**: Lower diffuse bounces to 2, specular to 4 for preview. Use variance pixel oracle. Check for invisible volumes still scattering light.

## VEX Errors

### 11. "Syntax error" in VEX wrangle
**Symptom**: Node turns red with syntax error
**Cause**: Missing semicolons, wrong type prefix, undeclared variable
**Fix**: VEX requires semicolons on every statement. Check type prefix: `f@` for float, `v@` for vector, `i@` for int, `s@` for string.

### 12. "Read-only" attribute error
**Symptom**: Can't write to `@ptnum`, `@numpt`, or `@Frame`
**Cause**: These are read-only context variables
**Fix**: Create a new attribute instead: `i@my_ptnum = @ptnum;`

### 13. VEX wrangle doesn't affect geometry
**Symptom**: Code runs but nothing changes
**Cause**: Wrong "Run Over" mode (points vs prims vs detail), or writing to wrong attribute
**Fix**: Check `class` parm matches intent. For per-point ops, use "Points". For aggregate, use "Detail".

### 14. Point cloud returns no results
**Symptom**: `pcfind()` or `pcopen()` returns empty
**Cause**: Radius too small, wrong input number, or no points in range
**Fix**: Increase search radius. Ensure second input has points. Check `pcfind(1, ...)` if searching second input.

## Simulation Errors

### 15. "Maximum recursion depth exceeded"
**Symptom**: Python crash in execute_python or simulation evaluation
**Cause**: Circular node references or recursive expression
**Fix**: Check for circular connections with `node.inputConnections()`. Break the cycle.

### 16. Simulation explodes on frame 1
**Symptom**: RBD pieces or FLIP particles fly apart instantly
**Cause**: Overlapping geometry, missing ground plane, or extreme initial velocity
**Fix**: Add gap between pieces. Enable ground plane. Check initial velocity values. Increase substeps to 2-4.

### 17. Pyro container clips simulation
**Symptom**: Smoke/fire hits an invisible wall and stops
**Cause**: Resize container padding too low
**Fix**: Increase `resize_padding` to 0.5+. Check "Container" tab in pyro solver.

### 18. Simulation drifts or behaves unstably
**Symptom**: Objects slowly drift, jitter, or gain energy
**Cause**: Insufficient substeps for speed, floating-point issues at large scales
**Fix**: Increase substeps. Work at reasonable scale (1 unit = 1 meter). Check for external forces.

## Viewport and Display Errors

### 19. Viewport shows nothing after node creation
**Symptom**: Node created but geometry not visible
**Cause**: Display flag not set, or node has errors
**Fix**: Set display flag: `node.setDisplayFlag(True)` and `node.setRenderFlag(True)`. In LOPs, the last node with display flag is the displayed stage.

### 20. "Couldn't find a match for pattern"
**Symptom**: Material assign or edit node affects nothing
**Cause**: `primpattern` doesn't match any prims on stage
**Fix**: Check stage with `get_stage_info` to see available prim paths. Use wildcards: `/World/geo/*`

### 21. "SOP sphere has no rows/cols" (in LOPs)
**Symptom**: Setting rows/cols on a Solaris sphere fails
**Cause**: LOP sphere != SOP sphere. Different parameter sets.
**Fix**: Solaris sphere uses `xn__inputsradius_i0a`. For detail control, use SOP sphere + sopimport.

## File and Cache Errors

### 22. Cache files missing frames
**Symptom**: Playback skips or shows frame 1 geometry
**Cause**: Cache interrupted, wrong frame range, or `$F4` padding mismatch
**Fix**: Verify frame padding matches (`$F4` = 4-digit). Re-cache missing range. Check `filecache` mode is "Write" during sim, "Read" for playback.

### 23. USD reference can't find file
**Symptom**: "Could not open layer" error on reference node
**Cause**: Absolute path on different machine, or `$HIP` not set
**Fix**: Use relative paths or `$HIP/assets/`. Verify file exists at the resolved path.

### 24. Bgeo.sc files are huge
**Symptom**: Cache fills disk rapidly
**Cause**: Caching unnecessary attributes (rest, shop_materialpath, etc.)
**Fix**: Use `attribdelete` before filecache to strip unneeded attributes. Keep only what rendering/downstream needs.
