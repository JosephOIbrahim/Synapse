# H22 SYNAPSE REPORT — Inside-Out SDK Enhancements
**Prepared:** 2026-06-22 | **Target Release:** Houdini 22 | **Synapse Version:** 5.14.0 / Protocol 4.0.0

---

## Executive Summary

The "inside-out SDK" refers to the architecture by which Synapse reaches *into* Houdini from an external MCP server — rather than Houdini calling outward to a plugin. This document reviews the current model, identifies friction points exposed by H21 experience, and proposes concrete enhancements to make the bridge faster, safer, and more capable for H22.

---

## 1. Current Architecture (H21 Baseline)

```
Claude / LLM Client
      │  MCP JSON-RPC over stdio/HTTP
      ▼
Synapse MCP Server (Python, ws://localhost:9999)
      │  WebSocket  ←→  bridge.json (pid + endpoint)
      ▼
Houdini Bridge Process (hou module, main thread marshalling)
      │  hou.* calls, Python exec, VEX wrangle injection
      ▼
Houdini 21 Runtime
```

**Key constraints identified in H21:**
- All Houdini mutations MUST execute on the main thread → async bridge with queue/dispatch.
- `houdini_execute_python` wraps in an undo group but can deadlock if Houdini shows a modal dialog mid-cook.
- File I/O (`synapse_write_report`) was separated onto the handler thread precisely to survive main-thread blocks — this pattern should be extended.
- Symbol table (33 255 symbols, blake2b stamped) must match running Houdini version or tool calls silently degrade.

---

## 2. H22 API Surface Changes to Anticipate

### 2.1 APEX (Animation / Rigging)
H21 shipped APEX as a preview. H22 is expected to promote it to a first-class context. The SDK must add:

| Tool | Description |
|------|-------------|
| `apex_create_graph` | Create an APEX graph node in /obj |
| `apex_add_node` | Add a node inside an APEX graph |
| `apex_connect_ports` | Wire APEX ports |
| `apex_set_port_value` | Set a port's default value |
| `apex_promote_port` | Promote to HDA interface |
| `apex_inspect_graph` | Read graph topology and port values |

**Implementation note:** APEX graphs are not accessible via standard `hou.Node` parameter API — they use `hou.ApexGraph` objects. The bridge will need a dedicated APEX introspection path separate from the SOP parameter path.

### 2.2 KineFX 2 / Character Pipeline
Expected skeletal and muscle simulation improvements. SDK additions needed:
- `kinefx_bind_skin` — weight binding helper
- `kinefx_retarget` — animation retargeting between skeletons
- `kinefx_inspect_rig` — rig hierarchy dump

### 2.3 USD / Solaris Composition Improvements
H22 is expected to improve `UsdGeomSubset` support and USD 24.x compatibility. SDK impact:
- `houdini_query_prims` should expose `subset` as a filterable type.
- `houdini_manage_collection` should support `expandPrimsAndProperties` more reliably.
- Encoded parameter name table will need a re-stamp — **the blake2b symbol table must be regenerated on H22 build day.**

### 2.4 Copernicus GPU Compute
H22 may stabilise the Copernicus OpenCL API. Current `cops_set_opencl` is a scaffold. H22 target: fully cooked kernels with:
- `cops_cook_node` — explicit cook trigger with error surface
- `cops_get_pixel` — sample pixel value at UV coordinate
- `cops_write_image` — export COP layer to disk

---

## 3. Bridge Layer Enhancements

### 3.1 Non-Blocking Mutation Queue
**Problem:** Long-running Python mutations (e.g., RBD simulation setup, heavy APEX graph construction) block the bridge and starve health-check pings, causing timeout false-positives.

**Proposal:** Add a priority queue to the bridge with two lanes:
- `FAST` lane: parameter reads, pings, health checks — always pre-empt.
- `NORMAL` lane: mutations (node creation, parameter sets) — serialised.
- `SLOW` lane: long-running cooks (RBD, FLIP) — cancellable.

```python
# Proposed bridge API (internal)
class BridgeQueue:
    async def submit(self, fn, lane: Literal["FAST","NORMAL","SLOW"], timeout: float) -> Any: ...
    async def cancel_slow(self) -> None: ...
```

### 3.2 Undo Group Nesting Fix
**Problem (H21):** Nested undo groups (execute_python calling a tool that itself wraps in undo) cause inconsistent rollback depth. H22 should introduce a group-depth counter:

```python
_undo_depth = 0

@contextmanager
def undo_group(label: str):
    global _undo_depth
    if _undo_depth == 0:
        hou.undos.group(label).__enter__()
    _undo_depth += 1
    try:
        yield
    finally:
        _undo_depth -= 1
        if _undo_depth == 0:
            hou.undos.group(label).__exit__(None, None, None)
```

### 3.3 Scene Hash Delta Tracking
The integrity block already computes `scene_hash_before` / `scene_hash_after`. H22 should:
- Surface hash deltas in tool responses so the LLM can detect unexpected side-effects.
- Store the last 10 scene hashes in a ring buffer for fast "did anything change?" polling.
- Expose `synapse_diff_scene` tool: returns the structural diff between two hash states.

### 3.4 Streaming Tool Responses
Currently all tool calls return a single JSON blob. For long operations (render, simulation, large Python scripts), H22 should stream incremental progress tokens back over the MCP transport:

```
{"type":"progress","pct":0.0,"message":"Starting cook..."}
{"type":"progress","pct":0.35,"message":"Frame 5/48 done"}
{"type":"result","data":{...}}
```

This requires MCP protocol 4.1+ with streaming support — track the spec.

### 3.5 File I/O Thread Safety (Expand the `synapse_write_report` Pattern)
`synapse_write_report` already bypasses Houdini's main thread. This pattern should be extended to:
- `synapse_read_file` — read UTF-8 files without touching Houdini
- `synapse_list_dir` — directory listing
- `synapse_copy_file` — asset copy/move

All file operations should be thread-safe and never marshal to the main thread.

---

## 4. Symbol Table Maintenance

The H21 symbol table contains **33 255 symbols** (blake2b `ae7688f80a7076dc1c5b9fb3c05ab53d`).

**H22 Checklist:**
- [ ] Re-generate symbol table on first H22 beta drop.
- [ ] Diff against H21 table — log new symbols, removed symbols, type-changed symbols.
- [ ] Update encoded parameter name mappings for all LOP nodes (these change with each USD schema version).
- [ ] Run `synapse_doctor` to confirm blake2b match before shipping.
- [ ] Add symbol table version to `synapse_health` response for at-a-glance confirmation.

---

## 5. HDA Integration Depth

### 5.1 HDA Event Hooks
Currently Synapse can create and promote parameters on HDAs but cannot react to HDA-level events. H22 should add:
- `hda_on_created` callback — fire Synapse tool when an HDA instance is dropped into the scene.
- `hda_on_parm_changed` — watch a parameter and trigger an LLM reasoning step when it changes.

### 5.2 HDA Version Management
- `houdini_hda_version_bump` — increment semver, archive previous definition.
- `houdini_hda_diff` — compare parameter interfaces between two versions.
- `houdini_hda_publish` — copy .hda to a designated pipeline library path.

### 5.3 Component Builder Automation
H22 should expose a `houdini_component_builder_setup` tool that:
1. Creates a Component Builder LOP.
2. Wires geometry, material library, and variant sets.
3. Writes render/proxy/guide purpose layers automatically.
4. Exports a self-contained `.usd` asset.

---

## 6. Performance Targets (H22)

| Metric | H21 Baseline | H22 Target |
|--------|-------------|------------|
| Tool round-trip latency (simple parm read) | ~25ms | <10ms |
| Node creation (single node) | ~80ms | <40ms |
| execute_python (10-node chain) | ~400ms | <200ms |
| Symbol table lookup | ~2ms | <1ms (cached) |
| Scene hash computation | ~15ms | <5ms (incremental) |

---

## 7. Recommended H22 Pre-Release Actions

1. **Subscribe to SideFX H22 beta programme** — request API change notes, especially for APEX, KineFX, and USD schema updates.
2. **Freeze the H21 symbol table** as a reference artefact before H22 overwrites it.
3. **Build a test matrix** — one integration test per tool call. Run against H21, then H22 beta; flag regressions.
4. **Audit encoded parameter names** — every `xn__*` parm name is schema-version-dependent. Build an auto-regeneration script.
5. **Review undo group depth** — trace all paths where `execute_python` is called recursively.
6. **Draft APEX tools** — even as stubs — so they appear in `synapse_list_recipes` on H22 day one.

---

*End of document. See companion reports: H22_llm_support.md and H22_codebase_review.md*
