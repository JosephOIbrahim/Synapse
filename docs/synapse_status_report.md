# SYNAPSE Status Report
**Date:** 2026-06-01  
**Session:** untitled.hip  
**Protocol Version:** 4.0.0  
**Evolution Stage:** Charmander (markdown / flat)

---

## EXECUTIVE SUMMARY

SYNAPSE is connected, healthy at the protocol level, and functional for most Houdini operations. However, there are several significant issues — one critical bug discovered live this session — that limit reliability for day-to-day artist use. This report documents what works, what is broken, and concrete improvement actions.

---

## ✅ WHAT IS WORKING

### Core Infrastructure
- **MCP Connection:** Healthy. Protocol v4.0.0, Houdini available, circuit breaker CLOSED (state 0).
- **execute_python:** Executes correctly. Undo group wrapping works. Atomic rollback on failure works.
- **synapse_write_report:** Works reliably (this file is proof). Operates on handler thread — does not block Houdini.
- **Node inspection tools:** `synapse_inspect_node`, `synapse_inspect_scene`, `houdini_network_explain` all functional.
- **Parameter read/write:** `houdini_get_parm`, `houdini_set_parm` work for standard nodes.
- **Memory system:** Project memory and scene memory load correctly. 178 entries in store. Session history consolidation working.
- **Health check:** `synapse_health` returns correctly.
- **Metrics (Prometheus):** `synapse_metrics` returns tool duration histograms correctly.

### USD / Solaris
- `houdini_stage_info` works when given an explicit node path.
- `houdini_query_prims` functional.
- Material creation, assignment, and reading tools functional.
- `houdini_create_material`, `houdini_create_textured_material` functional.
- `synapse_solaris_assemble_chain`, `synapse_solaris_build_graph` functional.

### Rendering
- `synapse_safe_render`, `synapse_render_progressively` functional.
- `houdini_capture_viewport` functional.
- TOPS render sequence pipeline functional.

### COPs
- COP network creation, node wiring, OpenCL tools all functional.

---

## ❌ WHAT IS BROKEN / FAILING

### 🔴 CRITICAL: `print()` output is silently swallowed in execute_python

**Severity:** Critical  
**Impact:** Every diagnostic script that uses `print()` returns empty results. This caused ~12 wasted tool calls this session trying to discover sopcreate's internal structure.

**Root cause:** The MCP handler captures stdout but does not surface it in the tool response `result` field. Only the string `"executed"` is returned.

**Workaround discovered:** Use `raise Exception(f"result: {value}")` — exceptions ARE returned in the error field and carry the message. This is hacky and forces every diagnostic into an "error" response.

**Fix needed:** The execute_python handler should capture `sys.stdout` output and return it in the `result` field alongside `"executed"`.

---

### 🔴 CRITICAL: `sopcreate` LOP — cannot add SOP geometry without workaround

**Severity:** Critical  
**Impact:** The primary tool for adding geometry to Solaris (`sopcreate`) fails silently when trying to populate it. The HDA is locked by default, so `createNode()` inside its SOP network throws "Cannot create a node inside a locked asset."

**Root cause:** `sopcreate` is an HDA. Its internal SOP network (`sopnet/create`) is locked. The agent's system prompt says to "use sopcreate for new geometry" but provides no guidance on how to unlock it first.

**Workaround discovered this session:**
1. Create `sopcreate` node.
2. Call `node.allowEditingOfContents()` to unlock the HDA instance.
3. Then `createNode()` inside `sopnet/create` works.

**Fix needed:** The `houdini_create_node` tool (or a new `houdini_sopcreate_geometry` tool) should automatically call `allowEditingOfContents()` when the parent is a sopcreate HDA. The system prompt should also document this pattern explicitly.

---

### 🟡 MEDIUM: `houdini_stage_info` fails without explicit node path

**Severity:** Medium  
**Impact:** `houdini_stage_info` with no arguments returns "No USD stage found" even when a display-flagged LOP node exists. It should auto-discover the display node in `/stage`.

**Observed:** Passing `node="/stage/box1"` explicitly works correctly (returned 3 prims including the Mesh).

**Fix needed:** Auto-discover the display-flagged node in `/stage` when no node argument is provided, same pattern used by other auto-discover tools.

---

### 🟡 MEDIUM: `synapse_live_metrics` — metrics aggregator not running

**Severity:** Medium  
**Impact:** `synapse_live_metrics` returns `{"error": "Metrics aggregator not running"}`. Live monitoring of cook progress, frame status, and system load is unavailable.

**Fix needed:** The metrics aggregator should auto-start with the MCP server, or `synapse_live_metrics` should fall back gracefully to the Prometheus snapshot from `synapse_metrics`.

---

### 🟡 MEDIUM: `synapse_router_stats` — router not initialized

**Severity:** Medium  
**Impact:** `synapse_router_stats` returns `{"error": "Router not initialized"}`. Tier cascade routing statistics are unavailable.

**Fix needed:** Either initialize the router at startup or suppress this tool if routing is not in use, rather than exposing a broken endpoint.

---

### 🟠 LOW-MEDIUM: Memory evolution stuck at Charmander

**Severity:** Low-Medium  
**Impact:** Project memory is at "Charmander" (flat markdown) after many sessions. The system has 178 memory entries but has never evolved to Charmeleon or Charizard. Consolidation and semantic indexing are not running.

**Observed:** 210 empty session-end markers were pruned in a previous pass, indicating the evolution system ran once but did not advance stage.

**Fix needed:** Review evolution trigger conditions. With 178 entries, the system should have evolved. Manual trigger via `synapse_evolve_memory` should be tested.

---

### 🟠 LOW: Pending internal reports never saved

**Severity:** Low  
**Impact:** From a previous session, four agentic execution reports (TOPS, SOLARIS, COPERNICUS, APEX) were drafted but never written to disk because `execute_python` timed out repeatedly. They remain as a memory note only.

**Fix needed:** Retry the write using `synapse_write_report` (which runs on the handler thread, not Houdini's main thread, and is immune to Houdini lockup).

---

## 📊 PERFORMANCE METRICS (this session)

| Tool | Calls | Avg Duration |
|------|-------|-------------|
| execute_python | 15 | ~3.4ms |
| inspect_node | 1 | 16.4ms |
| knowledge_lookup | 1 | 61ms |
| project_setup | 1 | 10.9ms |
| get_health | 1 | <1ms |

All tool calls completed under 100ms. No timeouts this session. Circuit breaker remained closed throughout.

---

## 🔧 IMPROVEMENT RECOMMENDATIONS (Priority Order)

### P0 — Fix immediately
1. **Capture print() stdout in execute_python responses.** This is the single highest-leverage fix. It would have cut this session's tool call count by ~50%.

### P1 — Fix soon
2. **Auto-call `allowEditingOfContents()` when targeting sopcreate internals.** Or create a dedicated `houdini_add_sop_to_sopcreate(lop_path, sop_type)` tool.
3. **Auto-discover display node in `houdini_stage_info`.** Should work with zero arguments when a display flag is set in `/stage`.

### P2 — Fix in next release
4. **Auto-start metrics aggregator** or provide graceful fallback in `synapse_live_metrics`.
5. **Initialize router at startup** or remove `synapse_router_stats` from the tool surface if routing is not in use.
6. **Trigger memory evolution** — 178 entries with no advancement past Charmander suggests the evolution threshold or trigger logic needs review.

### P3 — Nice to have
7. **Document sopcreate unlock pattern** in the system prompt's "Canonical Chain Order" section.
8. **Retry pending internal reports** using `synapse_write_report`.
9. **Add a `houdini_sopcreate_geometry` composite tool** that wraps the full create → unlock → add SOP → wire pattern in a single call.

---

## SCENE STATE AT TIME OF REPORT

- **File:** untitled.hip
- **Network:** /stage
- **Nodes:** 25 total (19 LOP, 5 SOP, 1 Manager)
- **Active geometry:** `/stage/box1` — sopcreate with box mesh, USD prim at `/box1/mesh_0` (Mesh), no material assigned.
- **Stray nodes:** `/stage/box` (sopnet with box1 SOP, orphaned — not wired), `/stage/box2` (second sopcreate, empty).
- **/obj:** `box_geo` geo object with box1 SOP created during debugging (can be cleaned up).

---

*Report generated by SYNAPSE / Claude. Session integrity fidelity: 1.0. All anchors held.*
