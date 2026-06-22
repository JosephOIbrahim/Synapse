# H22 PREP — Inside-Out SDK Enhancement
**Document:** SDK-001  
**Label:** H22  
**Author:** SYNAPSE / Houdini AI Co-Pilot  
**Date:** 2026-06-22  
**Status:** Pre-Release Research  

---

## Executive Summary

Houdini 22 arrives in approximately one month. This document reviews the current SYNAPSE "inside-out" SDK architecture and proposes concrete enhancements to take full advantage of anticipated H22 changes — tighter USD composition, APEX maturity, and continued Karma XPU evolution — while hardening the SDK itself for the next generation of AI-driven pipeline tooling.

The "inside-out" framing means SYNAPSE operates *from within* Houdini rather than as an external orchestrator: it has direct access to `hou`, `loputils`, `pdg`, `cop2`, and the full Houdini Python API. This document is a first-principles review of how to deepen that advantage.

---

## 1. Current Architecture Baseline

### 1.1 Bridge Layer
- WebSocket bridge at `ws://localhost:9999` (pid-stamped, auto-reconnect)
- Protocol 4.0.0 over SYNAPSE 5.14.0
- Symbol table: 33,255 symbols, blake2b-verified against running H21.0.671 build
- All mutations wrapped in undo groups; atomic rollback on failure
- Scene hash before/after every operation — drift detection built in

### 1.2 Tool Surface (33 active tool groups)
The SDK currently exposes seven domain groups:
| Group | Coverage |
|---|---|
| Scene | Node CRUD, parameter I/O, VEX execution |
| USD/Solaris | Stage inspection, prim authoring, material binding |
| Render | Karma XPU/CPU, Mantra, progressive render, farm |
| TOPS/PDG | Wedge, batch cook, multi-shot, monitoring |
| Memory | Project/scene memory, evolution, knowledge lookup |
| COPs | Copernicus image processing, solvers, AOV compositing |
| HDA | Package, promote, version, help authoring |

### 1.3 Known Gaps (H21)
- No direct APEX rig introspection tools
- No DOP/simulation query surface
- No VDB I/O primitives
- COP OpenCL kernel scaffolds not fully cooked (placeholder status)
- Memory evolution still at Charmander stage (flat markdown, no graph)
- Bridge reconnect logic is passive (no proactive health pulse)

---

## 2. H22 Anticipated Changes and SDK Impact

*Based on SideFX roadmap signals, H21 release notes trajectory, and community beta feedback as of mid-2026.*

### 2.1 APEX — Full Rigging System Maturity
H22 is expected to ship APEX as the primary rigging system, deprecating the legacy KineFX wire-up workflow for most character pipelines.

**SDK Requirements:**
- `synapse_inspect_apex_graph` — walk an APEX graph, return node types, port connections, and parameter bindings
- `synapse_set_apex_parm` — set values on APEX parameter blocks (distinct from `hou.Parm`)
- `synapse_bake_apex_pose` — capture current pose as a USD SkelAnimation prim
- APEX graphs live in SOP context but write to USD via `AgentLayer` — bridge must handle the SOP→USD handoff cleanly
- The existing `houdini_execute_python` covers emergency cases but a typed APEX surface is needed for reliable LLM tool calls

**Priority:** Critical

### 2.2 Karma XPU — Expanded AOV and Light Path Expressions
H22 is expected to add full LPE (Light Path Expression) support to Karma XPU, closing the gap with CPU.

**SDK Requirements:**
- Extend `synapse_configure_render_passes` to accept LPE strings: `{"name": "coat_reflection", "lpe": "C<RS>O"}`
- Add `synapse_list_lpes` — enumerate valid LPE tokens for the current renderer
- `houdini_render_settings` needs LPE-aware parameter discovery (encoded parm names will change between H21 and H22)
- RenderVar prim schema may gain new attributes (`colorspace`, `driver`) — attribute writer must be version-aware

**Priority:** High

### 2.3 USD Composition — Stronger Layer Stack API
SideFX has been progressively exposing more of the OpenUSD layer stack through LOPs. H22 likely adds:
- Native `EditTarget` switching in LOPs
- Stronger anonymous layer management
- Possible `UsdNotice` bindings for live stage observation

**SDK Requirements:**
- `synapse_set_edit_target` — switch the active USD edit target layer in a LOP network
- `synapse_list_layers` — enumerate all layers in the composition stack with strength order
- `synapse_flatten_layer` — flatten a specific layer to a new USD file (useful for asset publish)
- Memory system should record layer stack state as part of scene snapshots
- `synapse_validate_ordering` already exists but should be extended to report layer identity, not just merge topology

**Priority:** High

### 2.4 Copernicus — COP2 Full Deprecation
H22 is likely to complete the migration from `cop2` context to the new Copernicus `copnet`. The legacy COP2 API (`hou.CopNode`) will still exist but may not receive new node types.

**SDK Requirements:**
- All `cops_*` tools must target `copnet` context by default (already done for `cops_create_copnet`)
- `cops_create_network` (legacy cop2net) should emit a deprecation warning and redirect
- OpenCL kernel tools must be validated against H22 Copernicus node parameter names
- `cops_to_materialx` live link must be tested — the `op:` path scheme may change if Copernicus moves to a new internal cache model
- Solver nodes (block begin/end) have different parameter layouts in copnet vs cop2 — version branch required

**Priority:** Medium-High

### 2.5 PDG/TOPs — Expanded Scheduler Surface
H22 is expected to add native cloud scheduler bindings and an improved work item attribute schema.

**SDK Requirements:**
- `tops_configure_scheduler` currently hard-rejects non-local schedulers — this guard should become a warning with a pass-through mode for H22 cloud scheduler
- `tops_query_items` attribute schema needs to handle typed arrays (H22 PDG may add `pdg.attribType.FloatArray`)
- `tops_monitor_stream` event callbacks should handle new H22 PDG event types without crashing

**Priority:** Medium

---

## 3. SDK Architecture Enhancements

### 3.1 Symbol Table Versioning
**Current state:** Single symbol table, blake2b-verified at startup.  
**Problem:** When H22 ships, 33,255 symbols will partially invalidate. Parm names on USD nodes (already encoded) will change for new node types. Kernel will fail silently on stale names.

**Proposal:**
- Ship a `symbol_table_h21.json` and `symbol_table_h22.json`
- On startup, `synapse_doctor` reads `hou.applicationVersionString()` and selects the correct table
- Add a `synapse_rescan_symbols` tool that rebuilds the table live from running Houdini — runs in background, ~2s
- Expose `symbol_table.build_stamp` in `synapse_health` response

### 3.2 Undo Group Granularity
**Current state:** Each tool call is one undo group.  
**Problem:** Multi-step operations (e.g., `houdini_shot_render_ready` which calls 3 sub-tools) create 3 separate undo entries. Artist hits Ctrl+Z once and gets a half-built scene.

**Proposal:**
- Add `session_undo_group` concept: a named undo block that spans multiple tool calls
- `synapse_begin_undo_group(name)` / `synapse_end_undo_group()`
- Composite tools (shot_render_ready, hda_package, solaris_build_graph) should auto-wrap
- Protocol 4.x addition — backward compatible (older clients ignore the markers)

### 3.3 Scene Hash Drift Detection → Active Repair
**Current state:** Scene hash is computed before/after every operation. If hash differs from expected, it's logged but no action is taken.  
**Proposal:**
- Promote drift detection to an active signal: if hash drift is detected on a read operation (not a write), emit a `scene_drift` warning in the response
- Add `synapse_reconcile_drift` — compares current scene state to last known memory snapshot and reports what changed outside of SYNAPSE operations (artist edited manually, etc.)
- This is critical for H22 where APEX graphs may be edited by the artist between AI calls

### 3.4 Typed Tool Returns
**Current state:** Tool returns are mostly untyped JSON blobs.  
**Problem:** LLM reasoning over tool results is brittle when schema varies per node type.

**Proposal:**
- Define response schemas for each tool category (OpenAPI 3.1 style)
- `houdini_get_parm` returns `{"node": str, "parm": str, "value": any, "type": "float|int|string|vector|ramp", "animated": bool}`
- `houdini_stage_info` returns typed prim list with `{"path": str, "type": str, "active": bool, "purpose": str, "has_payload": bool}`
- Typed returns dramatically improve multi-step reasoning chains — the LLM can pattern-match on `"type": "DomeLight"` rather than parsing a string

### 3.5 Proactive Bridge Health Pulse
**Current state:** Bridge reconnects passively when a call fails.  
**Proposal:**
- Add a 30s keepalive ping from the bridge server to the Houdini process
- If 3 pings fail, the bridge auto-restarts and logs a `bridge_restart` event
- `synapse_health` should return `last_ping_age_seconds` so the LLM can detect a stale connection before attempting mutations

---

## 4. New Tools Proposed for H22

| Tool | Domain | Priority |
|---|---|---|
| `synapse_inspect_apex_graph` | APEX | Critical |
| `synapse_set_apex_parm` | APEX | Critical |
| `synapse_bake_apex_pose` | APEX | High |
| `synapse_set_edit_target` | USD | High |
| `synapse_list_layers` | USD | High |
| `synapse_flatten_layer` | USD | High |
| `synapse_configure_render_passes` LPE extension | Karma | High |
| `synapse_list_lpes` | Karma | Medium |
| `synapse_rescan_symbols` | Core | High |
| `synapse_begin_undo_group` / `end_undo_group` | Core | High |
| `synapse_reconcile_drift` | Core | Medium |
| `houdini_dop_query` | DOPs | Medium |
| `houdini_vdb_info` | VDB | Medium |
| `tops_configure_scheduler` cloud pass-through | PDG | Medium |

---

## 5. Deprecation Plan

### H21 Tools to Sunset in H22 SDK
- `cops_create_network` (cop2net) → redirect to `cops_create_copnet` with warning
- `synapse_solaris_assemble_chain` default node order should insert APEX agent node slot
- `houdini_render` mantra path should emit soft deprecation (Mantra is maintenance-only in H22)

### Parameter Name Migration
All encoded USD parameter names (e.g., `xn__inputsintensity_i0a`) should be re-verified at H22 launch. A migration script should auto-update any stored scene memory that references old encoded names.

---

## 6. Testing Strategy for H22 Launch

1. **Symbol table diff** — run `synapse_rescan_symbols` against H22 beta and diff against H21 table. Flag all changed/removed names.
2. **Regression suite** — run canonical Solaris chain build (SOPCreate → Material → Camera → Light → Karma → OUTPUT) against H22 and verify output USD
3. **APEX smoke test** — create a simple APEX rig, call `synapse_inspect_apex_graph`, verify port enumeration
4. **Karma XPU LPE test** — configure a LPE-based render var, render a single frame, validate AOV output
5. **Copernicus copnet test** — build a procedural texture network in `copnet`, connect to MaterialX, verify `op:` live link still resolves
6. **Memory evolution test** — run 10-session simulation, verify Charmander→Charmeleon evolution triggers correctly under H22

---

## 7. Recommended Priorities (Next 30 Days)

| Week | Action |
|---|---|
| Week 1 | Obtain H22 beta access. Run symbol table diff. File issues against changed encoded parm names. |
| Week 2 | Build `synapse_inspect_apex_graph` and `synapse_set_apex_parm` prototypes. |
| Week 3 | Extend `synapse_configure_render_passes` for LPE. Validate Copernicus copnet tool compatibility. |
| Week 4 | Regression test full tool surface. Update `symbol_table_h22.json`. Write migration notes for studio pipelines. |

---

*End of document SDK-001*
