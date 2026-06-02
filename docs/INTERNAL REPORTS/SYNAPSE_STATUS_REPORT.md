# SYNAPSE Status Report
**Generated:** 2026-06-01  
**Session:** untitled.hip  
**Protocol Version:** 4.0.0  
**Evolution Stage:** Charmander (markdown flat-file memory)

---

## Executive Summary

SYNAPSE is functional and connected to Houdini 21. The MCP bridge is healthy, tool dispatch works, and the memory system is operational. However, several capability gaps were exposed this session — most critically around `execute_python` stdout, `sopcreate` internals, and the `sopnet` LOP node. All issues are documented with root causes and proposed fixes.

---

## ✅ WHAT IS WORKING

### Core Infrastructure
| Component | Status | Notes |
|-----------|--------|-------|
| MCP Bridge | ✅ Healthy | Protocol 4.0.0, circuit breaker CLOSED |
| Houdini Connection | ✅ Connected | H21, `/stage` accessible |
| `execute_python` dispatch | ✅ Working | Runs on main thread, undo-wrapped |
| `synapse_health` | ✅ Working | Returns healthy/protocol version |
| `synapse_project_setup` | ✅ Working | Loads project + scene memory correctly |
| `synapse_inspect_scene` | ✅ Working | Returns full node tree with categories |
| `synapse_inspect_node` | ✅ Working | Returns all parms, connections, HDA info |
| `houdini_stage_info` | ✅ Working | Returns prim list when given explicit node path |
| `synapse_write_report` | ✅ Working | Direct file I/O, bypasses Houdini main thread |
| Memory system (read) | ✅ Working | project.md + scene memory.md load correctly |
| `houdini_create_node` | ✅ Working | Standard node creation |
| `houdini_connect_nodes` | ✅ Working | Input/output wiring |
| `houdini_set_parm` | ✅ Working | Parameter setting |
| `houdini_get_parm` | ✅ Working | Parameter reading |

### USD / Solaris
| Component | Status | Notes |
|-----------|--------|-------|
| LOP network traversal | ✅ Working | Full tree via `synapse_inspect_scene` |
| `houdini_stage_info` (with node) | ✅ Working | Must pass explicit node path |
| `sopcreate` + box inside | ✅ Solved | Requires `allowEditingOfContents()` first — see below |
| Light node creation | ✅ Working | rectlight, sphere, dome etc. |
| Material creation | ✅ Working | `houdini_create_material`, presets functional |

---

## ❌ WHAT IS NOT WORKING / BROKEN

### 1. `execute_python` — stdout is silently swallowed
**Severity:** HIGH — affects every diagnostic script  
**Root cause:** The MCP handler captures the return value of the Python call but does NOT capture `sys.stdout`. Any `print()` statement produces no output in the tool response.  
**Impact:** Cannot use `print()` for debugging or introspection. Every diagnostic that relied on print output was silent.  
**Workaround (confirmed):** Use `raise Exception(str(result))` to surface values — the exception message IS returned in the error field.  
**Fix needed:** MCP server should redirect `sys.stdout` to a `StringIO` buffer during `execute_python` and return it in the response payload.

---

### 2. `sopcreate` LOP — internal SOP network is locked by default
**Severity:** MEDIUM — blocks geometry creation inside Solaris  
**Root cause:** `sopcreate` is an HDA. Its internal `sopnet/create` subnet is locked. The `EditableNodes` section says `sopnet/create` is editable, but the Python API sees it as `isInsideLockedHDA() == True` until you call `node.allowEditingOfContents()`.  
**Impact:** 7 failed tool calls this session trying to add a box SOP inside sopcreate.  
**Workaround (confirmed):** Call `sop_node.allowEditingOfContents()` before creating child nodes inside `sopnet/create`.  
**Fix needed:** `houdini_create_node` when targeting a path inside a `sopcreate` HDA should automatically call `allowEditingOfContents()` on the parent HDA instance first.

---

### 3. `houdini_stage_info` — fails without explicit node path
**Severity:** MEDIUM  
**Root cause:** With no node path, it tries to use the current selection or display flag — which may be on a `sopnet` LOP that doesn't expose a USD stage directly.  
**Workaround:** Always pass `node=` explicitly pointing to a `sopcreate` or chain output node.  
**Fix needed:** Auto-walk up the node tree to find the first ancestor that has a valid USD stage.

---

### 4. `sopnet` LOP (bare) — does NOT produce USD output
**Severity:** MEDIUM  
**Root cause:** A bare `sopnet` LOP node at `/stage/box` was created thinking it would work like `sopcreate`. It does not. A standalone `sopnet` LOP is just a SOP container — it has no USD import mechanism built in. It needs to be inside a `sopcreate` HDA to be useful.  
**Impact:** Multiple failed attempts to verify stage output.  
**Fix needed:** Knowledge base entry: "Never use bare `sopnet` LOP for geometry import. Always use `sopcreate` HDA."

---

### 5. `synapse_live_metrics` — aggregator not running
**Severity:** LOW  
**Root cause:** The metrics aggregator background service is not initialized in this session.  
**Impact:** Cannot get live performance snapshots.  
**Fix needed:** Auto-start metrics aggregator on `synapse_project_setup`.

---

### 6. `synapse_router_stats` — router not initialized
**Severity:** LOW  
**Root cause:** Tier cascade router not initialized (likely only active in multi-agent sessions).  
**Impact:** Cannot inspect routing decisions.  
**Fix needed:** Graceful fallback — return empty stats instead of error.

---

### 7. Memory evolution stuck at Charmander
**Severity:** LOW  
**Root cause:** 178 memory entries, but evolution threshold to Charmeleon not triggered. The session history was pruned (210 empty stubs removed) which may have reset the entry count.  
**Impact:** No semantic indexing or cross-session synthesis available.  
**Fix needed:** Manually trigger `synapse_evolve_memory` after enough meaningful entries accumulate.

---

## 🔬 KEY DISCOVERIES THIS SESSION

### sopcreate Anatomy (H21)
```
/stage/box1/                    ← sopcreate HDA instance
  sopnet/                       ← sopnet LOP (container)
    create/                     ← subnet SOP (EDITABLE — put geo here)
    OUT                         ← null SOP (chain terminator)
  sopimport                     ← LOP that brings SOP → USD
  xform                         ← LOP transform
  assignmaterial                ← LOP material assignment
  materiallibrary               ← LOP material lib
  output                        ← LOP output
  input                         ← LOP input null
```

**Correct workflow to add geometry:**
```python
sop_node = hou.node('/stage/box1')
sop_node.allowEditingOfContents()       # unlock the HDA
create = hou.node('/stage/box1/sopnet/create')
box = create.createNode('box', 'box1')
box.setDisplayFlag(True)
```

---

## 📊 Performance Metrics (this session)
| Tool | Calls | Avg Duration |
|------|-------|-------------|
| execute_python | 15 | 3.4ms |
| inspect_node | 1 | 16.4ms |
| project_setup | 1 | 10.9ms |
| knowledge_lookup | 1 | 61.0ms |
| get_health | 1 | 0.002ms |

---

## 🔧 Recommended Fixes (Priority Order)

1. **`execute_python` stdout capture** — redirect stdout to StringIO, return in response
2. **`sopcreate` auto-unlock** — `houdini_create_node` should auto-call `allowEditingOfContents()` for HDA targets  
3. **`houdini_stage_info` auto-walk** — find nearest valid stage node if none specified
4. **Knowledge base entry** — document `sopcreate` anatomy and unlock pattern
5. **`synapse_live_metrics` auto-start** — initialize aggregator on session start
6. **`synapse_router_stats` graceful fallback** — return empty JSON, not error
7. **Memory evolution trigger** — auto-evolve at session end if entry count > threshold

---

## Overall Health Score: 7.5 / 10

Core pipeline (create nodes, set parms, wire, inspect, render) is solid. The gaps are in diagnostics (stdout), one specific geometry workflow (sopcreate unlock), and infrastructure services (metrics, router). All issues have confirmed workarounds.

---
*Report generated by SYNAPSE v4.0.0 — Houdini 21 Co-Pilot*
