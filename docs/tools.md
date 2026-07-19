# MCP Tools Reference

SYNAPSE registers **115 tools**, live-counted from the tool registry (`python/synapse/mcp/_tool_registry.py`) at **v5.32.1**. Each maps to a command type in the wire protocol.

> **`tools/list` is the authoritative source.** It is generated from the live registry and can never drift. This page is a scannable mirror of it — descriptions are truncated for width; call `tools/list` for full text and input schemas.

**How to reach them:** in-Houdini via the SYNAPSE panel (no setup), or from an external MCP client — see [`docs/mcp/SETUP.md`](mcp/SETUP.md).

| Prefix | Tools | Domain |
|---|---|---|
| `houdini_` | 40 | scene, nodes, parms, execution, USD/Solaris, materials, HDAs, render, undo/redo |
| `synapse_` | 37 | memory, introspection, propose/validate/build, render orchestration, health |
| `cops_` | 21 | Copernicus — networks, solvers, procedural texture, stylize, AOV comp, MaterialX |
| `tops_` | 17 | PDG — cook, wedge, work items, schedulers, dependency graph, multi-shot |

---

## Houdini — scene, nodes, USD/Solaris, materials, HDAs, render

**40 tools.**

| Tool | Description |
|---|---|
| `houdini_assign_material` | Assign a material to geometry prims. |
| `houdini_capture_viewport` | Capture the Houdini viewport as an image. |
| `houdini_configure_light_linking` | Configure light linking between lights and geometry via USD collections. Control which geometry a light ill… |
| `houdini_connect_nodes` | Connect the output of one node to the input of another. |
| `houdini_create_material` | Create a material with a shader in the LOP network. Supports presets (glass, mirror, rough_metal, polished_… |
| `houdini_create_node` | Create a new node in Houdini. Returns the path of the created node. |
| `houdini_create_point_instancer` | Author a UsdGeom.PointInstancer: scatter prototype prims across positions. Minimal valid setup -- defines t… |
| `houdini_create_textured_material` | Create a production MaterialX material with texture file inputs. Supports diffuse, roughness, metalness, no… |
| `houdini_create_usd_prim` | Create a USD prim on the stage. |
| `houdini_delete_node` | Delete a node in Houdini by its path. |
| `houdini_execute_python` | Execute Python code in Houdini's runtime environment. ONE mutation per call. Wrapped in undo group -- autom… |
| `houdini_execute_vex` | Execute VEX code by creating an Attribute Wrangle node. |
| `houdini_get_parm` | Read a parameter value from a Houdini node. |
| `houdini_get_selection` | Get the currently selected nodes in Houdini. |
| `houdini_get_usd_attribute` | Read a USD attribute value from a prim on the stage. |
| `houdini_hda_create` | Convert a subnet into a Houdini Digital Asset (HDA). Sets metadata (author, version), installs the .hda fil… |
| `houdini_hda_list` | List all Synapse-authored HDAs currently loaded in Houdini. Scans loaded HDA files for definitions with aut… |
| `houdini_hda_package` | High-level HDA orchestrator: create subnet, convert to HDA, promote parameters, set help -- all in one call… |
| `houdini_hda_promote_parm` | Promote an internal node parameter to the HDA's top-level interface. Idempotent -- re-promoting updates rat… |
| `houdini_hda_set_help` | Set help documentation on an HDA. Generates Houdini wiki markup from structured inputs: summary, descriptio… |
| `houdini_manage_collection` | Manage USD collections on a prim for light linking, material assignment, and grouping. Use 'list' to see ex… |
| `houdini_manage_variant_set` | Manage USD variant sets on a prim: list, create, or select variants. Use 'list' to see existing variant set… |
| `houdini_modify_usd_prim` | Modify USD prim metadata: kind, purpose, active state, or instanceable flag. |
| `houdini_network_explain` | Walk a Houdini node network and produce a structured explanation: data flow order, detected workflow patter… |
| `houdini_query_prims` | Query USD stage prims with filtering by type, purpose, and name pattern. Returns matching prims with their… |
| `houdini_read_material` | Read what material is assigned to a prim and its shader settings. |
| `houdini_redo` | Redo the last undone Houdini operation. Steps forward one undo level. |
| `houdini_reference_usd` | Import a USD file into the stage via reference, payload, or sublayer. Payload mode uses deferred loading fo… |
| `houdini_render` | Render a frame using Karma XPU, Karma CPU, Mantra, or any ROP node. An explicit frame renders AND polls at… |
| `houdini_render_settings` | Read and optionally modify render settings on a ROP or Karma node. |
| `houdini_scene_info` | Get current Houdini scene info: HIP file path, current frame, FPS, and frame range. |
| `houdini_set_keyframe` | Set a keyframe on a node parameter at a specific frame. |
| `houdini_set_parm` | Set a parameter value on a Houdini node. For USD/Solaris nodes, parameter names are encoded (e.g. xn__input… |
| `houdini_set_payload_loadstate` | Control USD payload load state and prim activation. Load/unload a payload by prim path and/or toggle the pr… |
| `houdini_set_usd_attribute` | Set a USD attribute on a prim. |
| `houdini_set_usd_primvar` | Author a UsdGeom primvar on a prim via UsdGeomPrimvarsAPI -- carries an interpolation token (constant/unifo… |
| `houdini_shot_render_ready` | Composite orchestrator: get a shot render-ready in one call. Runs create_textured_material -> solaris_assem… |
| `houdini_stage_info` | Get USD stage information: prim list and types. |
| `houdini_undo` | Undo the last Houdini operation. Steps back one undo level. |
| `houdini_wedge` | Run a TOPs/PDG wedge to explore parameter variations. |

## SYNAPSE — memory, introspection, propose/validate/build, orchestration

**37 tools.**

| Tool | Description |
|---|---|
| `synapse_add_memory` | Add a memory entry to the project. |
| `synapse_autonomous_render` | Execute an autonomous render loop: plan the render from intent, validate the scene, execute via TOPS, evalu… |
| `synapse_batch` | Execute multiple Synapse commands in a single round-trip. |
| `synapse_configure_render_passes` | Configure render passes (AOVs) for Karma. Creates RenderVar prims for compositing. Presets: beauty, diffuse… |
| `synapse_context` | Get project context from Synapse memory. |
| `synapse_decide` | Record a decision in project memory with reasoning. |
| `synapse_doctor` | Run SYNAPSE install/ops diagnostics: log file, telemetry freshness, encryption-key fingerprint, symbol-tabl… |
| `synapse_evolve_memory` | Manually trigger memory evolution. |
| `synapse_health` | Get system health status including resilience layer. |
| `synapse_inspect_node` | Deep-dive into a single node: all parameters, expressions, code, geometry, HDA info. |
| `synapse_inspect_scene` | Bird's-eye scene overview: node tree, context breakdown, warnings, sticky notes. |
| `synapse_inspect_selection` | Inspect selected nodes: parameters, connections, geometry stats, input graph. |
| `synapse_instantiate_graph` | Instantiate a VALIDATED graph proposal (parked by synapse_propose_graph) into the live scene, atomically. R… |
| `synapse_knowledge_lookup` | Look up Houdini knowledge: parameter names, node types, workflow guides. |
| `synapse_list_recipes` | List all available recipes with names, descriptions, and trigger patterns. |
| `synapse_live_metrics` | Get live metrics snapshot: scene health, routing, resilience, sessions. Pass history_count > 0 for historic… |
| `synapse_memory_query` | Query scene or project memory. |
| `synapse_memory_status` | Get memory system status: evolution stage, file sizes, session count. |
| `synapse_memory_write` | Write a memory entry to scene or project memory. |
| `synapse_metrics` | Get Synapse metrics in Prometheus text format. |
| `synapse_ping` | Check if Houdini/Synapse is connected and responding. |
| `synapse_project_setup` | Call this FIRST in every session. Returns project memory, scene memory, agent state, and evolution stage. W… |
| `synapse_propose_graph` | Validate a declarative graph proposal against the LIVE Houdini runtime and park it (if VALID) for later ins… |
| `synapse_recall` | Recall relevant memories for a given context or question. |
| `synapse_render_farm_cancel` | Request cancellation of the running render-farm sequence and/or autonomous render loop. Signal semantics: t… |
| `synapse_render_farm_status` | Check progress of a running render farm job: running state, scene tags, current frame. |
| `synapse_render_progressively` | Progressive 3-pass render: test (256x256, 4 samples) -> preview (720p, 16 samples) -> production (user sett… |
| `synapse_render_sequence` | Render a frame range with per-frame validation, automatic issue diagnosis, and self-improving fixes. Learns… |
| `synapse_router_stats` | Get tier cascade routing statistics. |
| `synapse_safe_render` | Render with pre-flight validation. Checks camera, materials, and output path before rendering. Auto-forces… |
| `synapse_search` | Search project memory for relevant entries. |
| `synapse_sleep_pass` | Run Moneta consolidation/decay (the Moneta memory backend). DESTRUCTIVE: permanently prunes unprotected mem… |
| `synapse_solaris_assemble_chain` | Auto-wire unwired LOP nodes in /stage into the canonical Solaris chain. Three modes: 'all' scans for unwire… |
| `synapse_solaris_build_graph` | Build a Solaris LOP network with arbitrary topology: merge nodes, sublayer stacks, parallel streams. Specif… |
| `synapse_validate_frame` | Validate a rendered frame for quality issues: black frames, NaN, clipping, fireflies. |
| `synapse_validate_ordering` | Walk a LOP network backwards from the render node, detecting ambiguous merge points where input order affec… |
| `synapse_write_report` | Write a UTF-8 report/file to the local reports directory ($SYNAPSE_REPORTS_DIR, else <repo>/docs). Pure fil… |

## Copernicus (COPs) — image processing

**21 tools.**

| Tool | Description |
|---|---|
| `cops_analyze_render` | Analyze rendered image in COPs: black pixels, dynamic range, clipping, noise. |
| `cops_bake_textures` | UV texture baking SCAFFOLD: creates placeholder map nodes; does NOT bake or write files. |
| `cops_batch_cook` | Batch-cook multiple COP nodes sequentially. |
| `cops_composite_aovs` | Build a COP network to composite Karma AOV layers from EXR renders. |
| `cops_connect` | Connect two COP nodes together. |
| `cops_create_copnet` | Create a modern Copernicus 'copnet' network (H21 Copernicus, distinct from legacy cop2net). |
| `cops_create_network` | Create a COP2 network container for Copernicus image processing. |
| `cops_create_node` | Create a COP node inside a COP network. |
| `cops_create_solver` | Create Block Begin/End solver pair for iterative COP processing. |
| `cops_growth_propagation` | DLA-style growth solver: iterative dilate/blur/threshold from seed mask. |
| `cops_pixel_sort` | Pixel-sort scaffold by luminance/hue (placeholder kernel; node not cooked). |
| `cops_procedural_texture` | Generate procedural texture: noise (perlin/worley/simplex), ramp, tiling. |
| `cops_reaction_diffusion` | Gray-Scott reaction-diffusion solver SCAFFOLD (placeholder #define-only kernel; node not cooked). |
| `cops_read_layer_info` | Read layer info from a COP node: resolution, data type, channels, cook status. |
| `cops_set_opencl` | Set OpenCL kernel code on a COP node for GPU-accelerated processing. |
| `cops_slap_comp` | Configure live viewport compositing overlay using COP output. |
| `cops_stamp_scatter` | Stamp image scattering with randomized transform per instance. |
| `cops_stylize` | NPR stylization: toon, risograph, posterize, edge detect. |
| `cops_temporal_analysis` | Temporal coherence analysis: flicker, frame diff, consistency check. |
| `cops_to_materialx` | Connect COP output to MaterialX shader via op: path for live procedural textures. |
| `cops_wetmap` | Wetmap effect: temporal decay from SOP velocity/collision in UV space. |

## TOPs / PDG — cook orchestration

**17 tools.**

| Tool | Description |
|---|---|
| `tops_batch_cook` | Cook multiple TOP nodes in sequence, collecting per-node results and aggregate stats. |
| `tops_cancel_cook` | Cancel an active cook on a TOP node or network. |
| `tops_configure_scheduler` | Configure the local scheduler for a TOP network: max concurrent, working directory. Localscheduler-only --… |
| `tops_cook_and_validate` | Cook a TOP node with automatic retry on failure. Self-healing: cook -> validate -> dirty -> retry. |
| `tops_cook_node` | Cook a TOP node. Supports blocking/non-blocking and generate-only modes. |
| `tops_diagnose` | Diagnose failures on a TOP node: inspect failed items, scheduler config, upstream deps, and suggestions. |
| `tops_dirty_node` | Dirty a TOP node to clear cached results. Optionally dirty upstream nodes too. |
| `tops_generate_items` | Generate work items for a TOP node without cooking. Preview what a node will produce. |
| `tops_get_cook_stats` | Get cook statistics for a TOP node or network: work item counts by state and cook times. |
| `tops_get_dependency_graph` | Get the dependency graph for a TOP network: nodes, types, work item counts, and edges. |
| `tops_get_work_items` | Get work items from a TOP node with optional state filtering. |
| `tops_monitor_stream` | Start, stop, or check status of event-driven TOPS cook monitoring. Push-based alternative to polling -- reg… |
| `tops_multi_shot` | Create a TOPS network for multi-shot rendering. Accepts a list of shot definitions (name, frame range, came… |
| `tops_pipeline_status` | Full health check for a TOP network: per-node status, aggregate stats, issues, and suggestions. |
| `tops_query_items` | Query work items by attribute value with filter operators (eq, gt, lt, gte, lte, contains, regex). |
| `tops_render_sequence` | Render a frame sequence via TOPS/PDG. Single-call interface for 'render frames 1-48'. Validates stage, crea… |
| `tops_setup_wedge` | Set up a Wedge TOP node for parameter variation exploration. |
---

## Scaffolds are labelled

Tools whose description says **SCAFFOLD** or *placeholder* create node structure but do not perform the full operation (e.g. `cops_bake_textures` writes no files; `cops_reaction_diffusion` emits a placeholder kernel). They self-report rather than faking success — that is deliberate. Read the description before depending on one.

## Regenerating this page

Counts here are read from the registry, not maintained by hand. To re-derive them:

```bash
python -c "import sys; sys.path.insert(0,'python'); from synapse.mcp._tool_registry import TOOL_DEFS; print(len(TOOL_DEFS))"
```

Historical snapshots (kept for the record, explicitly stale): [`docs/MCP_TOOL_CATALOG.md`](MCP_TOOL_CATALOG.md), [`INVENTORY.md`](../INVENTORY.md).
