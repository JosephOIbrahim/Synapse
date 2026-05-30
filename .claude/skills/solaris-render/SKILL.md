# Solaris Scene Rendering Pipeline

Progressive validation pipeline for creating and rendering Solaris scenes via the SYNAPSE MCP connection to Houdini. Do NOT skip stages.

## Stage 1: Scene Setup
- Create scene geometry and light rig
- After creation, query the stage and confirm all expected prims exist at correct paths
- List any missing prims before proceeding
- Wire nodes in correct order: geometry -> merge -> materials -> camera -> render_settings -> karma

### USD layering gotchas (verified 21.0.671, 2026-05-30)
- **`sublayer` LOP ordering is the OPPOSITE of raw USD.** It composes `filepathN`
  (highest index) as the STRONGEST layer — whereas raw `subLayerPaths` index 0 is
  strongest. To make a `render` department layer win, fill **weakest-first**
  (`filepath1=layout … filepath5=render`).
- **`node.editableStage()` is `None` outside an active Python-LOP cook.** It is not a
  general authoring surface. Author via LOP nodes + parms, read via `node.stage()`,
  and write USD attrs via a **pythonscript-LOP** (where `editableStage()` IS valid
  in-cook). A pythonscript `subLayerPaths` edit does NOT compose downstream — use a
  real `sublayer` LOP + files instead.

## Stage 2: Material Assignment
- Assign materials to geometry using exact USD prim paths (NOT wildcard patterns)
- After assignment, validate by querying each prim's material binding
- Print: prim path + bound material for every assigned prim
- Fix mismatches before proceeding
- Use material library nodes with subnets (not separate matlib + assign)

## Stage 3: Render Output Config
- Set up render product and output path
- Set `picture` on the Karma LOP AND `outputimage` on the ROP
- Validate the output directory exists and is writable
- Print the resolved output path

## Stage 4: Test Render
- Execute a minimal-resolution render: max 256x256, no SSS, no displacement, low samples (4-8)
- Wait for completion with a 60-second timeout
- Do NOT use `soho_foreground=1` for heavy scenes (blocks Houdini entirely)
- If Houdini becomes unresponsive, report failure and STOP — do NOT attempt higher quality
- Use `iconvert.exe` from `$HFS/bin/` for EXR-to-JPEG preview conversion

### License gotcha — husk no-ops on Houdini Indie (verified 21.0.671, 2026-05-30)
On a **Houdini Indie** license (`hou.licenseCategory() == licenseCategoryType.Indie`),
the standalone USD render path — **husk**, driven by `usdrender_rop.render()` —
**silently no-ops**: it returns with zero errors/warnings and writes no file.
- Never trust a clean `render()` return as proof of output — **poll for the file**.
- To verify a render on Indie, use **Karma interactive** (the viewport delegate) via a
  flipbook; `handlers_render.py` already falls back to exactly this. See
  `scripts/verify_compose_render.py` for the [REAL] check (a file lands at the
  configured path **and** the bound material renders its true color, not default gray
  — magenta reads as R≈B≫G).
- The `productName` parm on `karmarendersettings` does **not** author the
  `UsdRenderProduct.productName` attribute — author it via a pythonscript-LOP, then
  confirm with `assess_render_ready` (its output_path clause catches a missing path).

## Stage 5: Full Render
- Only if Stage 4 succeeds, increase to target resolution and quality
- Scale incrementally: enable expensive features (SSS, denoiser) one at a time
- Monitor for completion
- Report final output path and render time

## Lighting Law (Never Violate)
- Intensity is ALWAYS 1.0 — brightness controlled by EXPOSURE (logarithmic stops)
- Key:fill ratio 3:1 = 1.585 stops; 4:1 = 2.0 stops
- Use color temperature for warmth (5500K key, 7500K cool rim)
- Dome light exposure typically -0.5 to -1.0 when using HDRI

## Arguments

The user should describe the scene after invoking this skill:
- `/solaris-render A rubber toy on a wooden table with studio lighting`
