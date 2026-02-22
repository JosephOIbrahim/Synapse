# MCP Tool Catalog

> **Auto-generated from `python/synapse/mcp/tools.py`** | 80 tools | Synapse v5.6.0
>
> Grouped by domain module. Safety annotations follow MCP spec:
> - **RO** = `readOnlyHint: true` (safe to call anytime)
> - **MUT** = mutates scene (`destructiveHint: true`)
> - **IDEM** = idempotent (`idempotentHint: true`, safe to retry)

---

## Scene / Node / Parameters (18 tools)

Core scene manipulation. Always inspect before mutating. One mutation per tool call.

| # | Tool | Safety | Description |
|---|------|--------|-------------|
| 1 | `synapse_ping` | RO IDEM | Check if Houdini/Synapse is connected and responding. |
| 2 | `synapse_health` | RO IDEM | Get system health status including resilience layer. |
| 3 | `houdini_scene_info` | RO IDEM | Get current Houdini scene info: HIP file path, current frame, FPS, and frame range. |
| 4 | `houdini_get_selection` | RO IDEM | Get the currently selected nodes in Houdini. |
| 5 | `houdini_create_node` | MUT | Create a new node in Houdini. Returns the path of the created node. |
| 6 | `houdini_delete_node` | MUT | Delete a node in Houdini by its path. |
| 7 | `houdini_connect_nodes` | MUT | Connect the output of one node to the input of another. |
| 8 | `houdini_get_parm` | RO IDEM | Read a parameter value from a Houdini node. |
| 9 | `houdini_set_parm` | MUT IDEM | Set a parameter value on a Houdini node. **USD note:** parameter names are encoded (e.g. `xn__inputsintensity_i0a` not `intensity`). Use `houdini_inspect_node` first. |
| 10 | `houdini_execute_python` | MUT | Execute Python code in Houdini's runtime. ONE mutation per call. Wrapped in undo group -- automatic rollback on failure. |
| 11 | `houdini_execute_vex` | MUT | Execute VEX code by creating an Attribute Wrangle node. |
| 12 | `synapse_inspect_selection` | RO IDEM | Inspect selected nodes: parameters, connections, geometry stats, input graph. |
| 13 | `synapse_inspect_scene` | RO IDEM | Bird's-eye scene overview: node tree, context breakdown, warnings, sticky notes. |
| 14 | `synapse_inspect_node` | RO IDEM | Deep-dive into a single node: all parameters, expressions, code, geometry, HDA info. |
| 15 | `houdini_network_explain` | RO IDEM | Walk a Houdini node network and produce a structured explanation: data flow order, detected workflow patterns, non-default parameter values. |
| 16 | `houdini_undo` | MUT | Undo the last Houdini operation. |
| 17 | `houdini_redo` | MUT | Redo the last undone Houdini operation. |
| 18 | `synapse_batch` | MUT | Execute multiple Synapse commands in a single round-trip. |

<details>
<summary>Parameter details</summary>

### synapse_ping
No parameters.

### synapse_health
No parameters.

### houdini_scene_info
No parameters.

### houdini_get_selection
No parameters.

### houdini_create_node
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `parent` | string | **yes** | Parent node path (e.g. `/obj`) |
| `type` | string | **yes** | Node type (e.g. `geo`, `null`) |
| `name` | string | no | Optional node name |

### houdini_delete_node
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | Full path of the node to delete |

### houdini_connect_nodes
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | **yes** | Source node path (output from) |
| `target` | string | **yes** | Target node path (input to) |
| `source_output` | integer | no | Source output index (default: 0) |
| `target_input` | integer | no | Target input index (default: 0) |

### houdini_get_parm
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | Node path |
| `parm` | string | **yes** | Parameter name |

### houdini_set_parm
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | Node path |
| `parm` | string | **yes** | Parameter name |
| `value` | any | **yes** | Value to set |

### houdini_execute_python
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | **yes** | Python code to execute |
| `dry_run` | boolean | no | Syntax-check only (default: false) |
| `atomic` | boolean | no | Wrap in undo group (default: true) |

### houdini_execute_vex
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `snippet` | string | **yes** | VEX code snippet |
| `run_over` | string | no | Points, Primitives, Vertices, or Detail |
| `input_node` | string | no | Optional input geometry node path |

### synapse_inspect_selection
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `depth` | integer | no | Input traversal depth (default: 1) |

### synapse_inspect_scene
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `root` | string | no | Starting node path (default: `/`) |
| `max_depth` | integer | no | Traversal depth (default: 3) |
| `context_filter` | string | no | Filter by category (e.g. `Sop`) |

### synapse_inspect_node
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | Full node path |
| `include_code` | boolean | no | Include VEX/Python code (default: true) |
| `include_geometry` | boolean | no | Include geometry attributes (default: true) |
| `include_expressions` | boolean | no | Include expressions (default: true) |

### houdini_network_explain
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `root_path` | string | **yes** | Path to network root (e.g. `/obj/geo1`) |
| `depth` | integer | no | How deep to traverse subnets (default: 2, max: 5) |
| `detail_level` | string | no | `summary`, `standard`, or `detailed` (default: standard) |
| `include_parameters` | boolean | no | Include key non-default parameter values (default: true) |
| `include_expressions` | boolean | no | Include channel expressions (default: false) |
| `format` | string | no | `prose`, `structured`, or `help_card` (default: structured) |

### houdini_undo
No parameters.

### houdini_redo
No parameters.

### synapse_batch
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `commands` | array[object] | **yes** | Commands to execute |
| `atomic` | boolean | no | Wrap in undo group (default: true) |
| `stop_on_error` | boolean | no | Stop on first error (default: false) |

</details>

**RAG cross-references:** `common_attributes`, `chops`, `vex_reference`, `python_sop`, `node_types`

---

## Render / Viewport / Keyframe (10 tools)

Karma XPU/CPU, Mantra, and viewport capture. **Lighting Law:** intensity is ALWAYS 1.0 -- brightness controlled by exposure (stops).

| # | Tool | Safety | Description |
|---|------|--------|-------------|
| 1 | `houdini_capture_viewport` | RO IDEM | Capture the Houdini viewport as an image. |
| 2 | `houdini_render` | MUT | Render a frame using Karma XPU, Karma CPU, Mantra, or any ROP node. |
| 3 | `synapse_validate_frame` | RO IDEM | Validate a rendered frame for quality issues: black frames, NaN, clipping, fireflies. |
| 4 | `synapse_configure_render_passes` | MUT | Configure render passes (AOVs) for Karma. Presets: beauty, diffuse, specular, emission, normal, depth, position, albedo, crypto_material, crypto_object, motion, sss. |
| 5 | `houdini_set_keyframe` | MUT | Set a keyframe on a node parameter at a specific frame. |
| 6 | `houdini_render_settings` | MUT IDEM | Read and optionally modify render settings on a ROP or Karma node. |
| 7 | `synapse_render_sequence` | MUT | Render a frame range with per-frame validation, automatic issue diagnosis, and self-improving fixes. |
| 8 | `synapse_render_farm_status` | RO IDEM | Check progress of a running render farm job. |
| 9 | `synapse_autonomous_render` | MUT | Execute an autonomous render loop: plan, validate, execute via TOPS, evaluate quality, re-render if needed. |
| 10 | `synapse_validate_ordering` | RO IDEM | Walk a LOP network backwards detecting ambiguous merge points where input order affects USD opinion strength. |

<details>
<summary>Parameter details</summary>

### houdini_capture_viewport
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `width` | integer | no | Width in pixels |
| `height` | integer | no | Height in pixels |
| `format` | string | no | `jpeg` or `png` |

### houdini_render
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | ROP node path (auto-discovers if omitted) |
| `frame` | number | no | Frame to render |
| `width` | integer | no | Override resolution width |
| `height` | integer | no | Override resolution height |

### synapse_validate_frame
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image_path` | string | **yes** | Path to rendered image |
| `checks` | array[string] | no | Checks to run (default: all) |
| `thresholds` | object | no | Threshold overrides |

### synapse_configure_render_passes
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after |
| `passes` | array[string] | **yes** | List of pass names (e.g. `['beauty', 'diffuse', 'normal']`) |
| `clear_existing` | boolean | no | Clear existing render vars before adding (default: false) |

### houdini_set_keyframe
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | Node path |
| `parm` | string | **yes** | Parameter name |
| `value` | number | **yes** | Value to set |
| `frame` | number | no | Frame number |

### houdini_render_settings
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | ROP or render settings node path |
| `settings` | object | no | Optional overrides |

### synapse_render_sequence
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `rop` | string | no | ROP node path (auto-discovers if omitted) |
| `start_frame` | integer | **yes** | First frame to render |
| `end_frame` | integer | **yes** | Last frame to render (inclusive) |
| `step` | integer | no | Frame step (default: 1) |
| `auto_fix` | boolean | no | Auto-diagnose and fix issues (default: true) |
| `max_retries` | integer | no | Max retries per frame (default: 3) |

### synapse_render_farm_status
No parameters.

### synapse_autonomous_render
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `intent` | string | **yes** | What to render (e.g. `render frames 1-48`) |
| `max_iterations` | integer | no | Max re-render attempts (default: 3) |
| `quality_threshold` | number | no | Minimum quality score 0.0-1.0 (default: 0.85) |

### synapse_validate_ordering
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | Starting node path (auto-discovers if omitted) |
| `max_depth` | integer | no | Maximum traversal depth (default: 50) |

</details>

**RAG cross-references:** `camera_setup`, `camera_workflow_reference`, `lighting`, `render_settings`, `karma_renderer`

---

## USD / Solaris / Materials (14 tools)

Stage inspection, prim creation, material assignment. **USD parameter names are encoded** (e.g. `xn__inputsintensity_i0a` not `intensity`). Always inspect first.

| # | Tool | Safety | Description |
|---|------|--------|-------------|
| 1 | `houdini_stage_info` | RO IDEM | Get USD stage information: prim list and types. |
| 2 | `houdini_get_usd_attribute` | RO IDEM | Read a USD attribute value from a prim on the stage. |
| 3 | `houdini_set_usd_attribute` | MUT | Set a USD attribute on a prim. |
| 4 | `houdini_create_usd_prim` | MUT | Create a USD prim on the stage. |
| 5 | `houdini_modify_usd_prim` | MUT | Modify USD prim metadata: kind, purpose, or active state. |
| 6 | `houdini_reference_usd` | MUT | Import a USD file via reference, payload, or sublayer. Sublayer is most Karma-compatible. |
| 7 | `houdini_query_prims` | RO | Query USD stage prims with filtering by type, purpose, and name pattern. |
| 8 | `houdini_manage_variant_set` | MUT IDEM | Manage USD variant sets: list, create, or select variants. |
| 9 | `houdini_manage_collection` | MUT IDEM | Manage USD collections for light linking, material assignment, and grouping. |
| 10 | `houdini_configure_light_linking` | MUT | Configure light linking between lights and geometry via USD collections. |
| 11 | `houdini_create_textured_material` | MUT | Create a production MaterialX material with texture file inputs. Handles UDIM and UV wiring. |
| 12 | `houdini_create_material` | MUT | Create a material with base color, metalness, roughness, opacity, emission, subsurface. |
| 13 | `houdini_assign_material` | MUT | Assign a material to geometry prims. |
| 14 | `houdini_read_material` | RO IDEM | Read what material is assigned to a prim and its shader settings. |

<details>
<summary>Parameter details</summary>

### houdini_stage_info
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | Optional LOP node path |

### houdini_get_usd_attribute
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node path (optional) |
| `prim_path` | string | **yes** | USD prim path |
| `attribute_name` | string | **yes** | USD attribute name |

### houdini_set_usd_attribute
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after (optional) |
| `prim_path` | string | **yes** | USD prim path |
| `attribute_name` | string | **yes** | USD attribute name |
| `value` | any | **yes** | Value to set |

### houdini_create_usd_prim
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after (optional) |
| `prim_path` | string | **yes** | USD prim path to create |
| `prim_type` | string | no | USD prim type (default: Xform) |

### houdini_modify_usd_prim
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after (optional) |
| `prim_path` | string | **yes** | USD prim path |
| `kind` | string | no | Model kind |
| `purpose` | string | no | Prim purpose |
| `active` | boolean | no | Whether the prim is active |

### houdini_reference_usd
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | **yes** | Path to USD file |
| `prim_path` | string | no | Target prim path (default: /) |
| `mode` | string | no | `reference` (default), `payload`, or `sublayer` |
| `parent` | string | no | Parent LOP network path |

### houdini_query_prims
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node path |
| `root_path` | string | no | USD prim path to start from (default: /) |
| `prim_type` | string | no | Filter by USD type (e.g. `Mesh`, `DomeLight`) |
| `purpose` | string | no | Filter by purpose (e.g. `default`, `render`) |
| `name_pattern` | string | no | Regex or substring filter on prim name |
| `max_depth` | integer | no | Max traversal depth (default: 10) |
| `limit` | integer | no | Max prims to return (default: 100) |

### houdini_manage_variant_set
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node path |
| `prim_path` | string | **yes** | USD prim path |
| `action` | string | no | `list`, `create`, or `select` (default: list) |
| `variant_set` | string | no | Variant set name (required for create/select) |
| `variants` | array[string] | no | Variant names to create |
| `variant` | string | no | Variant to select |

### houdini_manage_collection
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node path |
| `prim_path` | string | **yes** | USD prim path |
| `action` | string | no | `list`, `create`, `add`, or `remove` (default: list) |
| `collection_name` | string | no | Collection name (required for create/add/remove) |
| `paths` | array[string] | no | Prim paths to include |
| `exclude_paths` | array[string] | no | Prim paths to exclude (create only) |
| `expansion_rule` | string | no | `expandPrims`, `expandPrimsAndProperties`, or `explicitOnly` |

### houdini_configure_light_linking
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node path |
| `light_path` | string | **yes** | USD prim path of the light |
| `action` | string | no | `include`, `exclude`, `shadow_include`, `shadow_exclude`, or `reset` |
| `geo_paths` | array[string] | no | Geometry prim paths to include/exclude |

### houdini_create_textured_material
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after |
| `name` | string | no | Material name (default: textured_material) |
| `diffuse_map` | string | no | Path to diffuse/albedo texture |
| `roughness_map` | string | no | Path to roughness texture |
| `metalness_map` | string | no | Path to metalness texture |
| `normal_map` | string | no | Path to normal map |
| `displacement_map` | string | no | Path to displacement map |
| `opacity_map` | string | no | Path to opacity/alpha texture |
| `roughness` | number | no | Scalar roughness fallback (0-1) |
| `metalness` | number | no | Scalar metalness fallback (0-1) |
| `geo_pattern` | string | no | Geometry prim pattern to auto-assign |

### houdini_create_material
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after |
| `name` | string | no | Material name |
| `shader_type` | string | no | Shader type (default: mtlxstandard_surface) |
| `base_color` | array[number] | no | [r, g, b] 0-1 |
| `metalness` | number | no | Metalness 0-1 |
| `roughness` | number | no | Roughness 0-1 |
| `opacity` | number | no | Opacity 0-1 (1=fully opaque) |
| `emission` | number | no | Emission weight 0-1 |
| `emission_color` | array[number] | no | Emission color [r, g, b] 0-1 |
| `subsurface` | number | no | Subsurface scattering weight 0-1 |
| `subsurface_color` | array[number] | no | Subsurface color [r, g, b] 0-1 |

### houdini_assign_material
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node to wire after |
| `prim_pattern` | string | **yes** | Geometry prim path or pattern |
| `material_path` | string | **yes** | USD material path |

### houdini_read_material
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | no | LOP node (optional) |
| `prim_path` | string | **yes** | USD prim to inspect |

</details>

**RAG cross-references:** `usd_basics`, `materials`, `solaris_lops`, `lighting`, `composition_arcs`

---

## TOPS / PDG (18 tools)

Pipeline orchestration for batch processing, wedging, and distributed rendering.

| # | Tool | Safety | Description |
|---|------|--------|-------------|
| 1 | `houdini_wedge` | MUT | Run a TOPs/PDG wedge to explore parameter variations. |
| 2 | `tops_get_work_items` | RO IDEM | Get work items from a TOP node with optional state filtering. |
| 3 | `tops_get_dependency_graph` | RO IDEM | Get the dependency graph for a TOP network: nodes, types, work item counts, and edges. |
| 4 | `tops_get_cook_stats` | RO IDEM | Get cook statistics: work item counts by state and cook times. |
| 5 | `tops_cook_node` | MUT | Cook a TOP node. Supports blocking/non-blocking and generate-only modes. |
| 6 | `tops_generate_items` | MUT | Generate work items for a TOP node without cooking. Preview what a node will produce. |
| 7 | `tops_configure_scheduler` | MUT IDEM | Configure the scheduler: type, max concurrent, working directory. |
| 8 | `tops_cancel_cook` | MUT | Cancel an active cook on a TOP node or network. |
| 9 | `tops_dirty_node` | MUT IDEM | Dirty a TOP node to clear cached results. |
| 10 | `tops_setup_wedge` | MUT | Set up a Wedge TOP node for parameter variation exploration. |
| 11 | `tops_batch_cook` | MUT | Cook multiple TOP nodes in sequence with aggregate stats. |
| 12 | `tops_query_items` | RO IDEM | Query work items by attribute value with filter operators (eq, gt, lt, gte, lte, contains, regex). |
| 13 | `tops_cook_and_validate` | MUT | Cook with automatic retry on failure. Self-healing: cook -> validate -> dirty -> retry. |
| 14 | `tops_diagnose` | RO IDEM | Diagnose failures: inspect failed items, scheduler config, upstream deps, and suggestions. |
| 15 | `tops_pipeline_status` | RO IDEM | Full health check for a TOP network: per-node status, aggregate stats, issues. |
| 16 | `tops_monitor_stream` | -- | Start, stop, or check status of event-driven TOPS cook monitoring. Push-based alternative to polling. |
| 17 | `tops_render_sequence` | MUT | Render a frame sequence via TOPS/PDG. Single-call interface for "render frames 1-48". Idempotent -- reuses existing network. |
| 18 | `tops_multi_shot` | MUT | Create a TOPS network for multi-shot rendering with per-shot work items and partitioned results. |

<details>
<summary>Parameter details</summary>

### houdini_wedge
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP network or wedge node path |
| `parm` | string | no | Parameter to wedge |
| `values` | array[number] | no | Values to wedge over |

### tops_get_work_items
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `state_filter` | string | no | all, cooked, failed, cooking, scheduled, uncooked, cancelled |
| `include_attributes` | boolean | no | Include work item attributes (default: true) |
| `limit` | integer | no | Max items to return (default: 100) |

### tops_get_dependency_graph
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topnet_path` | string | **yes** | TOP network path |
| `depth` | integer | no | Traversal depth (-1 for full) |

### tops_get_cook_stats
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node or network path |

### tops_cook_node
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `generate_only` | boolean | no | Generate work items only (default: false) |
| `blocking` | boolean | no | Wait for cook to complete (default: true) |
| `top_down` | boolean | no | Cook upstream nodes first (default: true) |

### tops_generate_items
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |

### tops_configure_scheduler
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topnet_path` | string | **yes** | TOP network path |
| `scheduler_type` | string | no | Scheduler type (default: local) |
| `max_concurrent` | integer | no | Max concurrent processes |
| `working_dir` | string | no | PDG working directory |

### tops_cancel_cook
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node or network path |

### tops_dirty_node
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `dirty_upstream` | boolean | no | Also dirty upstream nodes (default: false) |

### tops_setup_wedge
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topnet_path` | string | **yes** | TOP network path |
| `wedge_name` | string | no | Name for the wedge node (default: wedge1) |
| `attributes` | array[object] | **yes** | List of {name, type, start, end, steps} |

### tops_batch_cook
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node_paths` | array[string] | **yes** | List of TOP node paths to cook |
| `blocking` | boolean | no | Wait for each cook (default: true) |
| `stop_on_error` | boolean | no | Stop on first error (default: true) |

### tops_query_items
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `query_attribute` | string | **yes** | Attribute name to filter on |
| `filter_op` | string | no | eq, gt, lt, gte, lte, contains, regex (default: eq) |
| `filter_value` | any | **yes** | Value to match against |

### tops_cook_and_validate
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `max_retries` | integer | no | Max retry attempts (default: 0) |
| `validate_states` | boolean | no | Check work item states after cook (default: true) |

### tops_diagnose
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node path |
| `include_scheduler` | boolean | no | Include scheduler info (default: true) |
| `include_dependencies` | boolean | no | Include upstream dependency check (default: true) |

### tops_pipeline_status
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `topnet_path` | string | **yes** | TOP network path |
| `include_items` | boolean | no | Include per-node work items (default: false) |

### tops_monitor_stream
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `node` | string | **yes** | TOP node or network path to monitor |
| `action` | string | no | `start`, `stop`, or `status` (default: start) |
| `monitor_id` | string | no | Monitor ID (required for stop/status) |

### tops_render_sequence
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `start_frame` | integer | **yes** | First frame to render |
| `end_frame` | integer | **yes** | Last frame to render (inclusive) |
| `step` | integer | no | Frame step (default: 1) |
| `camera` | string | no | Camera USD prim path |
| `output_dir` | string | no | Output directory |
| `output_prefix` | string | no | Filename prefix (default: render) |
| `rop_node` | string | no | ROP node path (auto-discovers if omitted) |
| `topnet_path` | string | no | Existing TOP network to reuse |
| `pixel_samples` | integer | no | Override pixel samples |
| `resolution` | array[integer] | no | Override [width, height] |
| `blocking` | boolean | no | Wait for cook (default: false) |

### tops_multi_shot
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `shots` | array[object] | **yes** | Shot definitions: {name, frame_start, frame_end, camera, overrides} |
| `topnet_path` | string | no | Existing TOP network to reuse |
| `renderer` | string | no | Renderer (default: karma_xpu) |
| `output_dir` | string | no | Base output directory |
| `camera_pattern` | string | no | Camera path template |
| `rop_node` | string | no | ROP node path |
| `blocking` | boolean | no | Wait for cook (default: false) |
| `encode_movie` | boolean | no | Add ffmpeg encode per shot (default: false) |

</details>

**RAG cross-references:** `tops_pdg`, `wedging`, `render_settings`, `scheduling`

---

## Memory / Knowledge / HDA / Metrics (20 tools)

Project memory, scene memory, knowledge lookup, HDA authoring, and system metrics.

| # | Tool | Safety | Description |
|---|------|--------|-------------|
| 1 | `synapse_knowledge_lookup` | RO IDEM | Look up Houdini knowledge: parameter names, node types, workflow guides. |
| 2 | `synapse_context` | RO IDEM | Get project context from Synapse memory. |
| 3 | `synapse_search` | RO IDEM | Search project memory for relevant entries. |
| 4 | `synapse_recall` | RO IDEM | Recall relevant memories for a given context or question. |
| 5 | `synapse_decide` | -- | Record a decision in project memory with reasoning. |
| 6 | `synapse_add_memory` | IDEM | Add a memory entry to the project. |
| 7 | `synapse_project_setup` | IDEM | **Call this FIRST in every session.** Returns project memory, scene memory, agent state, and evolution stage. |
| 8 | `synapse_memory_write` | -- | Write a memory entry to scene or project memory. |
| 9 | `synapse_memory_query` | RO IDEM | Query scene or project memory. |
| 10 | `synapse_memory_status` | RO IDEM | Get memory system status: evolution stage, file sizes, session count. |
| 11 | `synapse_evolve_memory` | -- | Manually trigger memory evolution. |
| 12 | `synapse_metrics` | RO IDEM | Get Synapse metrics in Prometheus text format. |
| 13 | `synapse_router_stats` | RO IDEM | Get tier cascade routing statistics. |
| 14 | `synapse_list_recipes` | RO IDEM | List all available recipes with names, descriptions, and trigger patterns. |
| 15 | `synapse_live_metrics` | RO IDEM | Get live metrics snapshot: scene health, routing, resilience, sessions. |
| 16 | `houdini_hda_create` | MUT | Convert a subnet into a Houdini Digital Asset (HDA). |
| 17 | `houdini_hda_promote_parm` | MUT IDEM | Promote an internal parameter to HDA top-level interface. Idempotent. |
| 18 | `houdini_hda_set_help` | MUT IDEM | Set help documentation on an HDA. |
| 19 | `houdini_hda_package` | MUT | High-level HDA orchestrator: create subnet, convert, promote, set help -- all in one call. |
| 20 | `houdini_hda_list` | RO | List all Synapse-authored HDAs currently loaded in Houdini. |

<details>
<summary>Parameter details</summary>

### synapse_knowledge_lookup
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **yes** | Natural language query |

### synapse_context
No parameters.

### synapse_search
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **yes** | Search query |

### synapse_recall
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **yes** | Context or question |

### synapse_decide
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `decision` | string | **yes** | The decision made |
| `reasoning` | string | no | Why this decision was made |
| `alternatives` | string | no | Alternatives considered |

### synapse_add_memory
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | **yes** | Memory content to store |
| `memory_type` | string | no | Type (note, context, reference, task) |
| `tags` | array[string] | no | Tags |

### synapse_project_setup
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `force_refresh` | boolean | no | Force re-read (default: false) |

### synapse_memory_write
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entry_type` | string | **yes** | Type of memory entry |
| `content` | object | **yes** | Entry content |
| `scope` | string | no | `scene`, `project`, or `both` |

### synapse_memory_query
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | **yes** | Search query |
| `scope` | string | no | `scene`, `project`, or `all` |
| `type_filter` | string | no | Filter by type |

### synapse_memory_status
No parameters.

### synapse_evolve_memory
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scope` | string | no | `scene` or `project` |
| `target_stage` | string | no | `charmeleon` or `charizard` |
| `dry_run` | boolean | no | Preview without evolving (default: true) |

### synapse_metrics
No parameters.

### synapse_router_stats
No parameters.

### synapse_list_recipes
No parameters.

### synapse_live_metrics
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `history_count` | integer | no | Historical snapshots to return (0 = latest) |

### houdini_hda_create
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `subnet_path` | string | **yes** | Path to subnet node to convert |
| `operator_name` | string | **yes** | Internal operator type name |
| `operator_label` | string | **yes** | Human-readable label |
| `category` | string | **yes** | `Sop`, `Object`, `Driver`, `Lop`, or `Top` |
| `version` | string | no | SemVer version (default: 1.0.0) |
| `save_path` | string | **yes** | File path to save the .hda file |
| `min_inputs` | integer | no | Minimum inputs (default: 0) |
| `max_inputs` | integer | no | Maximum inputs (default: 1) |
| `icon` | string | no | Optional icon name |

### houdini_hda_promote_parm
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hda_path` | string | **yes** | Path to the HDA instance node |
| `internal_node` | string | **yes** | Relative path to internal node |
| `parm_name` | string | **yes** | Parameter name on the internal node |
| `label` | string | no | Optional label override |
| `folder` | string | no | Optional folder/tab name |
| `callback` | string | no | Optional Python callback script |
| `conditions` | object | no | Optional visibility conditions |

### houdini_hda_set_help
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hda_path` | string | **yes** | Path to the HDA instance node |
| `summary` | string | no | Short summary |
| `description` | string | no | Full description (wiki markup) |
| `parameters_help` | object | no | {parm_name: help_text} |
| `tips` | array[string] | no | List of tips |
| `author` | string | no | Author name |

### houdini_hda_package
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `description` | string | **yes** | What the HDA should do |
| `name` | string | **yes** | Operator name |
| `category` | string | **yes** | `Sop`, `Object`, `Driver`, `Lop`, or `Top` |
| `save_path` | string | **yes** | File path to save .hda |
| `inputs` | array[string] | no | Input descriptions |
| `promoted_parms` | array[object] | no | List of {node, parm, label} dicts |
| `nodes` | array[object] | no | Internal nodes to create |
| `connections` | array[array] | no | Connection triples: [src, dst, input_idx] |

### houdini_hda_list
No parameters.

</details>

**RAG cross-references:** `hda_creation`, `memory_evolution`, `knowledge_base`

---

## Summary

| Group | Tools | Read-Only | Mutating | Idempotent |
|-------|-------|-----------|----------|------------|
| Scene / Node / Parameters | 18 | 10 | 8 | 13 |
| Render / Viewport / Keyframe | 10 | 4 | 6 | 5 |
| USD / Solaris / Materials | 14 | 4 | 10 | 5 |
| TOPS / PDG | 18 | 6 | 12 | 7 |
| Memory / Knowledge / HDA / Metrics | 20 | 10 | 5 | 13 |
| **Total** | **80** | **34** | **41** | **43** |

### Safety Legend

- **RO** (`readOnlyHint: true`): Safe to call without modifying the scene. Use freely for inspection.
- **MUT** (`destructiveHint: true`): Modifies the Houdini scene. Wrapped in undo group where applicable.
- **IDEM** (`idempotentHint: true`): Calling multiple times with the same arguments produces the same result. Safe to retry.
- **--**: No special safety annotations. May write to memory or monitoring systems but does not modify the Houdini scene.
