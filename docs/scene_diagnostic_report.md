# SYNAPSE Scene Diagnostic Report
**Scene:** untitled.hip  
**Date:** 2026-06-01  
**Diagnosis run by:** SYNAPSE v4.0.0

---

## SYNAPSE System Status

| Component | Status | Notes |
|---|---|---|
| MCP / Houdini connection | ✅ HEALTHY | Protocol 4.0.0, responding fast |
| `execute_python` | ⚠️ PARTIAL | Executes correctly but **`print()` output is silently swallowed** — stdout is not returned to the AI. Workaround: `raise Exception(str(result))` to read values back. This is a critical diagnostic gap. |
| `houdini_stage_info` | ⚠️ UNRELIABLE | Fails unless a node path is explicitly provided AND that node is properly cooking a USD stage. Falls back gracefully but silent failures hide real stage state. |
| `synapse_live_metrics` | ❌ NOT RUNNING | "Metrics aggregator not running" — live telemetry offline. |
| `synapse_router_stats` | ❌ NOT RUNNING | "Router not initialized" — tier-cascade routing stats unavailable. |
| Memory system | ✅ OK | 178 entries, Charmander stage, project.md + memory.md writing correctly. |
| `synapse_write_report` | ✅ HEALTHY | File I/O confirmed working in this session. |
| Knowledge lookup | ✅ OK | Responding in ~61ms. |
| `houdini_create_node` (LOPs) | ⚠️ BROKEN | The `soppath` parameter doesn't exist on `sopcreate` nodes — tool tries to set it and fails with NoneType error. See sopcreate issue below. |

---

## Scene Problems Found

### 🔴 CRITICAL — No Camera on Stage

**What:** The USD stage (as seen from LIGHTS_OUT) contains zero Camera prims.  
**Impact:** Cannot render. Karma will error immediately with "no camera found."  
**Fix:** Add a `camera` LOP node to /stage and wire it into the chain before the lights.

---

### 🔴 CRITICAL — No Renderable Geometry on Stage

**What:** The display-flagged node is `LIGHTS_OUT` (the 3-point light rig). The chain is:  
`box2 (sopcreate) → key_light1 → fill_light → rim_light → LIGHTS_OUT`  

The box geometry (`/box2`) IS on the stage, but it has **no mesh children** — it's an empty Xform. The sopcreate node `box2` was created but never had a box SOP added to its internal network.  

The only working geometry is on `/stage/box1` (sopcreate, unlocked, has box SOP inside) — but **box1 is not wired into the LIGHTS_OUT chain**. It's a floating, disconnected island.  

**Impact:** Lights illuminate an empty box Xform. No visible geometry in render.  
**Fix:** Either wire box1 into the chain ahead of box2, or add a box SOP inside box2's create subnet.

---

### 🔴 CRITICAL — No ROP Node in /out

**What:** `/out` is completely empty — no usdrender ROP, no Karma node.  
**Impact:** No way to render via ROP. `synapse_safe_render` and `synapse_render_progressively` will fail with "no ROP found."  
**Fix:** Create a `usdrender` ROP in /out and point it at the LIGHTS_OUT display node.

---

### 🟡 MEDIUM — Orphaned / Duplicate Nodes

**What:** The following nodes are floating with no connections and no display flag:
- `/stage/box` — a bare `sopnet` LOP containing a box SOP. Not connected to anything.
- `/stage/key_light` — a duplicate light node (also named key_light), not wired into the chain. The actual key light in the chain is `key_light1`.
- `/stage/parm_probe` — a `light::2.0` node with no connections, apparently a leftover from parameter discovery during this session.
- `/stage/box1` — sopcreate with a working box inside, but completely disconnected from the render chain.
- `/obj/box_geo` — a legacy /obj geo node created as a workaround during session. Not connected to the LOP chain at all.

**Impact:** Clutter, confusion, potential USD opinion conflicts if accidentally connected.  
**Fix:** Delete `/stage/key_light`, `/stage/parm_probe`, `/stage/box`, and `/obj/box_geo`. Integrate box1 or box2 geometry properly.

---

### 🟡 MEDIUM — sopcreate `allowEditingOfContents()` Workaround Required

**What:** The `sopcreate` LOP is a locked HDA. Its internal SOP network (`sopnet/create`) cannot be written to directly until `node.allowEditingOfContents()` is called. The SYNAPSE tool `houdini_create_node` does not know to do this — so any attempt to programmatically add SOPs inside a sopcreate fails silently or with a "locked asset" error.  
**Impact:** Creating geometry in Solaris via the AI requires a Python workaround every time.  
**Fix (immediate):** Always call `allowEditingOfContents()` before creating nodes inside sopcreate. Document this in the recipe system.  
**Fix (long-term):** Add a dedicated `solaris_create_geometry` tool that handles the unlock pattern automatically.

---

### 🟡 MEDIUM — `execute_python` stdout not returned

**What:** `print()` statements in `houdini_execute_python` are executed correctly but output is never returned in the tool response. The AI cannot read back values this way.  
**Workaround in use:** `raise Exception(str(value))` — which forces the output through the error channel where it IS returned.  
**Impact:** Every diagnostic/introspection script requires ugly workarounds. Makes Python-based queries fragile and verbose.  
**Fix:** The MCP handler should capture stdout and include it in the `result` field of the response.

---

### 🟢 LOW — Light Chain Starts from box2, Not From a Merge

**What:** The light rig chain uses `box2` as its first input:  
`box2 → key_light1 → fill_light → rim_light → LIGHTS_OUT`  

This means the geometry and lights are entangled in a single linear chain. If the geometry changes, the entire light chain must be rewired.  
**Best practice:** Use a `merge` LOP to combine geometry and lights as separate streams:  
`box_geo → merge ← lights_merge → OUTPUT`  
**Impact:** Low for now. Will become painful when the scene grows.

---

### 🟢 LOW — No Material Assigned to Geometry

**What:** The box mesh (`/box1/mesh_0` from box1, or `/box2` empty from box2) has no material assigned.  
**Impact:** Renders with Karma's default grey. Not a blocker, but not useful for lookdev.  
**Fix:** Assign a basic MaterialX material to the geometry.

---

### 🟢 LOW — fill_light exposure is a non-round number (-0.585)

**What:** fill_light exposure = -0.5849999785423279. This is a floating-point artefact — intended value was -0.585 (exactly 3:1 key:fill ratio in stops).  
**Impact:** Cosmetic only. Exposure is effectively correct.  
**Fix:** Set to a clean -0.585 or -1.0 for a cleaner 3:1 or 8:1 ratio.

---

## Proposed Fix Plan (Priority Order)

| # | Fix | Effort |
|---|---|---|
| 1 | Delete orphaned nodes (key_light, parm_probe, /stage/box, /obj/box_geo) | 2 min |
| 2 | Wire box1 (working geometry) into the chain before key_light1 | 5 min |
| 3 | Add a Camera LOP to the chain | 2 min |
| 4 | Create a usdrender ROP in /out | 2 min |
| 5 | Assign a basic material to the box | 3 min |
| 6 | Restructure to merge topology (geo stream + lights stream) | 10 min |

**Total estimated fix time: ~25 minutes (or one SYNAPSE command)**

---

## SYNAPSE Self-Improvement Notes

1. **`houdini_create_node` inside sopcreate** — needs unlock step baked in.
2. **`execute_python` stdout** — MCP handler should return captured stdout.
3. **`synapse_live_metrics` + `synapse_router_stats`** — these subsystems are not initializing. Should either auto-start or gracefully report "not available" rather than erroring.
4. **`houdini_stage_info` without a node path** — should auto-detect the display-flagged LOP rather than failing.
5. **sopcreate geometry creation** — a dedicated recipe `solaris_add_sop_geometry(type, parent_lop)` would prevent the 10-tool debugging loop seen this session.
