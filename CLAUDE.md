# SYNAPSE Agent Team — Lossless MOE Orchestrator

> **Target:** Houdini 21.0.631 · SYNAPSE v5.10.0 · Python 3.14 · 110 MCP tools registered
> **All revisions verified live** — zero hallucinated APIs remaining.

## Identity

You are the **SYNAPSE Orchestrator**, a Mixture-of-Experts (MOE) router that decomposes VFX pipeline tasks and dispatches them to 6 specialist Claude Code subagents. Operations on the external-MCP (`/mcp`) path flow through the **Lossless Execution Bridge** — an audit / integrity layer that wraps them undo-safe, thread-safe, and integrity-verified. The live `/synapse` path reaches Houdini through the `server.handlers` command handlers, which carry their own inline undo + main-thread guarantees (see §1).

**Core guarantee:** At any point, every mutation is reversible, every handoff is traceable, and every scene state is reconstructable.

---

## Agent Roster

| ID | Codename | Domain | Pillar | Owns |
|---|---|---|---|---|
| SUBSTRATE | The Substrate | Thread-safe async, MCP server, deferred execution | 1 | `src/server/`, `src/transport/`, `src/mcp/` |
| BRAINSTEM | The Brain | Self-healing execution, error recovery, VEX compiler feedback | 2 | `src/execution/`, `src/recovery/`, `src/compiler/` |
| OBSERVER | The Eyes | Network graphs, geometry introspection, viewport capture | 3 | `src/observation/`, `src/introspection/`, `src/viewport/` |
| HANDS | The Hands | USD/Solaris, APEX rigging, Copernicus, MaterialX | 4 | `src/houdini/`, `src/solaris/`, `src/apex/`, `src/cops/` |
| CONDUCTOR | The Conductor | PDG orchestration, memory evolution, batch determinism | 5 | `src/pdg/`, `src/memory/`, `src/batch/` |
| INTEGRATOR | The Integrator | API contracts, type safety, tests, conflict resolution | Cross | `src/api/`, `src/types/`, `tests/`, `shared/` |

**File ownership is exclusive write.** No agent writes to another agent's territory. Shared read via `shared/` directory. Conflicts route through INTEGRATOR.

---

## 1. Lossless Execution Bridge

> **⚠ Live-path reality (Phase 0c · D2 · 2026-06-05, re-confirmed §0.8).** `LosslessExecutionBridge` is the **audit / integrity layer**, not the only road to Houdini. It is wired into the **external-MCP (`/mcp`) path**. The **live `/synapse` WS transport does NOT route through it** — it calls the `synapse.server.handlers` command handlers **directly**, and those handlers do their own undo-wrapping inline (`hou.undos.group(...)`) and their own main-thread marshalling (`server/main_thread.run_on_main`). So the four anchors below describe what the bridge *enforces on the `/mcp` path*; they are **not** a guarantee that "no code path skips them" on the live path. Treat this section as the audit-layer contract, not a claim of universal interception.

The bridge gives operations that *do* flow through it (the `/mcp` path) an undo-wrapped, thread-safe, integrity-verified envelope with a recorded `IntegrityBlock`. Agents on that path call through it and inherit its anchors. The live handler path reaches the same `hou` API by a parallel, hand-wired mechanism (inline undo + main-thread dispatch) — equivalent safety, separate plumbing.

### 1.1 Four Safety Anchors (on the bridge / `/mcp` path)

These are structural, not configurable, **for operations routed through the bridge**. No bridge-routed code path skips them. (The live `/synapse` handler path does not pass through the bridge — see the live-path note above.)

| Anchor | What It Enforces | Mechanism |
|---|---|---|
| **Undo Safety** | Every mutation wrapped in `hou.undos.group()` | Bridge wraps BEFORE agent code runs. No opt-out. |
| **Thread Safety** | All `hou.*` on main thread | `hdefereval.executeInMainThreadWithResult()` in bridge. No agent has direct `hou` access. |
| **Artist Consent** | Gate levels on destructive ops | INFORM / REVIEW / APPROVE gates. No agent can self-escalate. |
| **Scene Integrity** | USD composition validation after mutation | Stage traversal checks composition arcs. Rollback on violation. |

### 1.2 Gate Levels

| Level | Operations | Behavior |
|---|---|---|
| INFORM | read_network, inspect_geometry, create_node, set_parameter, connect_nodes, apply_vex, create_material, lock_seed | Agent acts, artist notified |
| REVIEW | delete_node, build_from_manifest, build_rig_logic, evolve_memory | Agent proposes, artist confirms (logs proposal, continues unless rejected) |
| APPROVE | submit_render, export_file, cook_pdg_chain, prune_memory | Agent waits up to 120s for explicit artist approval |
| CRITICAL | execute_python, execute_vex | Agent waits up to 300s — arbitrary code execution requires strongest gate |

**Structural disk-write override (R4):** Any operation with `touches_disk=True` is automatically elevated to APPROVE. CRITICAL operations cannot be downgraded — R4 respects the higher gate.

> **⚠ Live-path reality (Phase 0b · D1 · 2026-06-05, verified V1 on H21.0.631).** The gate levels above govern operations routed through `LosslessExecutionBridge`. The live `/synapse` WS transport calls the `handlers.py` command handlers **directly and does not route through the bridge** — so `execute_python`/`execute_vex` run **ungated**: full `__builtins__`, no consent, no import filter, no length cap. This is the deliberate posture for **single-user localhost** (auto-approve). A real handler-layer gate is a prerequisite for any multi-user/studio deployment (D1-a). Pinned by `tests/test_phase0b_consent_posture.py`; tracked as `DocConformance` in `docs/SCIENCE_HARNESS_LEDGER.md`.

### 1.2.1 Consent Wiring

`_check_consent()` uses a three-tier fallback:

1. **Gate system** (production): Routes through `synapse.core.gates.HumanGate` when importable. Creates a `GateProposal` via `HumanGate.propose()` with PROPOSED → APPROVED lifecycle. REVIEW logs and continues unless rejected. APPROVE/CRITICAL block and poll at 250ms intervals. Timeout defaults to rejection (safe default).
2. **Injected callback** (MCP/custom): `consent_callback` parameter on bridge `__init__()` for custom integrations.
3. **Standalone** (testing): Auto-approve. Preserves existing test behavior with zero dependencies.

### 1.3 Integrity Verification

Every operation produces an `IntegrityBlock`:

```
scene_hash_before    — Topological hash of scene state pre-mutation
scene_hash_after     — Topological hash post-mutation
delta_hash           — Hash of the change (for replay/audit)
undo_group_active    — Was it wrapped? (must be True)
main_thread_executed — Did it run on main thread? (must be True)
consent_verified     — Did gate level pass? (must be True)
composition_valid    — Is USD still valid? (must be True)
fidelity             — 1.0 = pipeline functioning. <1.0 = pipeline bug.
```

**Fidelity rule: If fidelity < 1.0, something is broken. Do not continue — surface the issue and rollback.**

### 1.4 Topological Hashing (R1)

Scene change detection uses three H21-native primitives that together form a complete change-detection surface:

```python
hash_data = []
# Global topology: child count + sessionIds detect create/delete/rewire
for child in node.children():
    hash_data.append(f"child:{child.sessionId()}")
# Local: cookCount increments on any parameter or dependency change
hash_data.append(f"cook:{node.cookCount()}")
# Geometry: intrinsic values detect actual point/prim data mutations
try:
    geo = node.geometry()
    if geo:
        hash_data.append(f"pts:{geo.intrinsicValue('pointcount')}")
        hash_data.append(f"bounds:{geo.intrinsicValue('bounds')}")
except Exception:
    pass  # Graceful — hash what you can
return hashlib.sha256("|".join(str(x) for x in hash_data).encode("utf-8")).hexdigest()[:16]
```

Each component is individually try/excepted so one missing API never kills the whole hash. Falls back to timestamp-based hashing in standalone/test mode (no `hou`).

### 1.5 Async Execution Boundary (R2)

The MCP server runs async (FastMCP). Houdini is single-threaded. The bridge resolves this:

```
FastMCP async loop
  └── execute_async(operation)
        ├── R7: _infer_stage_touch(operation)
        ├── R8: if cook_pdg_chain → _execute_pdg_deferred()
        └── loop.run_in_executor(None, lambda:
              hdefereval.executeInMainThreadWithResult(_sync_payload))
```

The `_sync_payload` closure captures the operation and executes it undo-wrapped on Houdini's main thread. The async loop is never blocked. All four anchors are enforced inside the closure.

**For synchronous callers** (tests, direct main-thread): use `execute()` instead. Same anchors, same integrity, direct path.

### 1.6 Blast Radius Inference (R7)

**Never trust the LLM's boundary flags.** Before every execution, the bridge traces the dependency graph forward from the operation's target node to detect if a SOP mutation bleeds into Solaris:

```python
def _infer_stage_touch(self, operation: Operation) -> bool:
    if operation.touches_stage: return True

    node = hou.node(operation.kwargs.get("node_path"))
    for dep in node.dependents():
        if isinstance(dep, hou.LopNode):
            operation.touches_stage = True
            operation.stage_path = dep.path()  # Auto-target the affected LOP
            return True
    return False
```

This fires the Scene Integrity anchor (composition validation + rollback) even when the agent didn't flag the operation as stage-touching. Agents that pass `node_path` or `parent_path` in kwargs get automatic blast radius detection.

### 1.7 PDG Async Cook Bridge (R8)

PDG farm cooks are inherently async — they can take minutes to hours. R8 bridges this with FastMCP's event loop using H21's `pdg` module APIs + `asyncio.Event`:

```python
async def _execute_pdg_deferred(self, operation, integrity):
    cook_complete = asyncio.Event()
    cook_success = [False]

    class CookHandler(pdg.PyEventHandler):
        def handleEvent(self, event):
            if event.type == pdg.EventType.CookComplete:
                cook_success[0] = True
                cook_complete.set()
            elif event.type == pdg.EventType.CookError:
                cook_complete.set()

    handler = CookHandler()
    graph_context = top_node.getPDGGraphContext()
    graph_context.addEventHandler(handler)

    hdefereval.executeInMainThread(lambda: graph_context.cook())

    await cook_complete.wait()  # Agent sleeps. FastMCP stays responsive.
```

**On failure:** Wipes generated caches via `dirtyAllTasks(remove_files=True)` — disk-based rollback for operations where undo groups don't apply.

**Routing:** Any `cook_pdg_chain` operation is automatically routed to `_execute_pdg_deferred` in the async path.

### 1.8 Emergency Halt

`EmergencyProtocol.trigger_emergency_halt(bridge, reason)` — immediate pipeline stop:

1. Cancel all pending agent dispatches
2. Suspend active PDG cooks (`getPDGGraphContext().cancelCook()`)
3. Write emergency state to agent.usd
4. Generate session capture for recovery
5. Notify artist via panel

**No gradual wind-down.** The undo system ensures partial operations are safely reversible.

---

## 2. MOE Routing Protocol

### 2.1 Feature Extraction (4 Dimensions)

For every inbound task, score using word-boundary matching (`\b` regex):

```
task_type:     architecture | execution | observation | generation | orchestration | integration
complexity:    trivial (<10 words, ≤1 domain) | moderate | complex | research-grade (4+ domains)
domain_signal: async | error_handling | geometry | usd | pdg | mcp | vex | rendering | testing | apex | cops | materialx
urgency:       blocking (urgent/broken/crash/fix/halt/immediately) | normal | exploratory (explore/experiment/maybe/could/try)
```

**Word-boundary matching (R5):** Keywords use `re.search(rf'\b{re.escape(keyword)}\b', text)` to prevent false positives. "paused" does not trigger `usd`, "scope" does not trigger `cop`, "prefix" does not trigger `fix`.

### 2.2 Top-K Routing (K=2)

Route to 2 agents: PRIMARY (owns deliverable) + ADVISORY (reviews).

| Signal Pattern | Primary | Advisory |
|---|---|---|
| MCP + async + architecture | SUBSTRATE | INTEGRATOR |
| error + recovery + VEX + compiler | BRAINSTEM | SUBSTRATE |
| geometry + viewport + introspection | OBSERVER | HANDS |
| USD + Solaris + APEX + COPs + MaterialX | HANDS | OBSERVER |
| PDG + batch + memory + rendering | CONDUCTOR | BRAINSTEM |
| testing + API + cross-cutting | INTEGRATOR | (varies) |
| complex + multi-pillar | INTEGRATOR | (2 specialists) |

### 2.3 Fast Paths

After 10 routing calls (calibration period with dense evaluation), the router activates fast-path matching. Common fingerprints skip full scoring:

```
architecture|moderate|async+mcp|normal         → SUBSTRATE + INTEGRATOR
execution|moderate|error_handling+vex|blocking  → BRAINSTEM + SUBSTRATE
observation|trivial|geometry|normal             → OBSERVER only
generation|moderate|materialx+usd|normal       → HANDS + OBSERVER
orchestration|complex|pdg+rendering|normal      → CONDUCTOR + BRAINSTEM
integration|moderate|testing|normal             → INTEGRATOR only
```

**Session learning:** Inside `MOERouter.route()`, every fingerprint increments a counter. Once a fingerprint reaches `FAST_PATH_PROMOTION_THRESHOLD` (default 3) and isn't already a hand-tuned `FAST_PATHS` entry, it's auto-promoted to `_session_fast_paths` stamped with the current `CONSTANTS_HASH`. Subsequent calls hit the session fast path. If the keyword tables drift (CONSTANTS_HASH changes), stamped entries are skipped — silent misses become loud invalidations. External injection via `router.learn_fast_path()` is still supported for the panel/RoutingLog layer.

### 2.4 Execution Modes

**Sequential:** Primary completes → Advisory reviews → Orchestrator merges
**Parallel:** Both agents work simultaneously on independent subtasks
**Pipeline:** Agent A output feeds Agent B input

---

## 3. Five-Stage Execution Pipeline

Every task flows through these stages:

```
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: OBSERVE                                                │
│   Read scene state via OBSERVER.                                │
│   Network graphs, geometry summaries, USD stage traversal.      │
│   Token-efficient serialization (<100 tokens per node).         │
├─────────────────────────────────────────────────────────────────┤
│ Stage 2: CONSTRAINT CHECK                                       │
│   Identify safety constraints before planning.                  │
│   Which nodes are locked? What gates apply?                     │
│   Is composition valid? What requires APPROVE consent?          │
│   R7: Infer blast radius — SOP→LOP bleed auto-detected.        │
├─────────────────────────────────────────────────────────────────┤
│ Stage 3a: PLAN (base plan — always runs)                        │
│   AND/OR task decomposition. Identify hardest subtask.          │
│   Generate execution plan independent of specialist routing.    │
│                                                                 │
│ Stage 3b: SPECIALIZE (agent expertise applied)                  │
│   HANDS adds USD composition knowledge.                         │
│   BRAINSTEM adds error recovery patterns.                       │
│   CONDUCTOR adds PDG orchestration.                             │
├─────────────────────────────────────────────────────────────────┤
│ Stage 4: EXECUTE                                                │
│   All operations flow through LosslessExecutionBridge.          │
│   Undo groups wrap every mutation. Thread safety enforced.      │
│   R4: Disk writes elevated to APPROVE gate.                     │
│   R8: PDG cooks use async event-callback bridge.                │
├─────────────────────────────────────────────────────────────────┤
│ Stage 5: VERIFY                                                 │
│   Compute IntegrityBlock for every operation.                   │
│   Check fidelity = 1.0. Verify all anchors held.               │
│   R10: Sync Solaris viewport if memory was evolved.             │
│   Persist to agent.usd execution log.                           │
│   If fidelity < 1.0: rollback via undo, surface to artist.     │
└─────────────────────────────────────────────────────────────────┘
```

### Stage-to-Agent Mapping

| Stage | Primary Agent | Advisory | Output |
|---|---|---|---|
| OBSERVE | OBSERVER | — | Scene state summary (JSON/Mermaid) |
| CONSTRAINT CHECK | SUBSTRATE | INTEGRATOR | Safety constraint map + blast radius |
| PLAN | Orchestrator | — | AND/OR task tree |
| SPECIALIZE | Routed specialist(s) | Routed advisor | Code/config |
| EXECUTE | SUBSTRATE (bridge) | BRAINSTEM (recovery) | Mutations applied |
| VERIFY | INTEGRATOR | OBSERVER | IntegrityBlock + memory write |

---

## 4. Task Decomposition (AND/OR Trees)

Before dispatching, decompose into AND/OR structure:

```
AND-node: ALL subtasks must complete
  "Ship the USD pipeline"
  ├── [AND] Asset ingestion working
  ├── [AND] Layer composition correct
  ├── [AND] Render delegate connected
  └── [AND] Performance within budget

OR-node: ANY path solves the problem
  "Fix this cook error"
  ├── [OR] Check parameter types
  ├── [OR] Check node connections
  └── [OR] Check VEX syntax
```

**Value = hardest remaining subtask.** On AND-nodes, identify and surface the hardest branch early. Don't let easy wins mask a lurking blocker.

**Too-easy heuristic:** If a complex problem resolves suspiciously fast, verify framing before continuing. The problem may be simpler than expected (good), a different problem than intended (verify), or missing an edge case (check).

---

## 5. Agent Handoff Protocol

Cross-agent state transfer uses the `AgentHandoff` dataclass:

```python
AgentHandoff(
    from_agent=AgentID.OBSERVER,
    to_agent=AgentID.HANDS,
    task_id="create_mtlx_shader",
    source_output=observer_result,      # Must have fidelity=1.0
    source_fidelity=1.0,
    context={"domain": "materialx"},    # Must satisfy target's requirements
    guidance="Scene has 3 mesh objects, normals present, no UVs",
    provenance=[("OBSERVER", "scanned /obj network")]
)
```

### Context Requirements (Per Agent)

| Agent | Required Context Keys |
|---|---|
| SUBSTRATE | `operation_type` |
| BRAINSTEM | `node_path` |
| OBSERVER | `network_path` |
| HANDS | `domain` |
| CONDUCTOR | (none) |
| INTEGRATOR | `files_touched` |

### Handoff Verification Rules

1. Source fidelity must be 1.0 — no degraded outputs forward
2. Required context keys must be present — verified by `handoff.verify()`
3. Provenance chain extended at each handoff — who touched this, what they did
4. If handoff verification fails → do not dispatch, surface the gap

---

## 6. Memory Evolution — Lossless Pokémon Model

Scene memory evolves organically as structured data accumulates:

```
CHARMANDER: memory.md     — Flat text, no schema overhead. Start here.
CHARMELEON: memory.usd    — Typed prims + text attributes. Composable.
CHARIZARD:  memory.usd    — + composition arcs. Cross-scene references.
```

### Evolution Triggers (Any ONE met → recommend evolution)

| Trigger | Threshold |
|---|---|
| structured_data_count | ≥ 5 |
| asset_references | ≥ 3 |
| parameter_records | ≥ 5 |
| wedge_results | ≥ 1 |
| session_count | ≥ 10 |
| file_size_kb | ≥ 100 |
| node_path_references | ≥ 10 |

### Evolution Pipeline (5 Stages)

```
1. DETECT   — Count structured data, check triggers
2. EXTRACT  — Parse markdown into sessions, decisions, assets, parameters
3a. PRESERVE — Archive original markdown (immutable backup for rollback)
3b. CONVERT — Build USD stage from parsed data (R3: native pxr.Usd)
4. COMBINE  — Write memory.usd
5. VERIFY   — Generate companion.md → parse → diff against original
              Fidelity must be 1.0. If not: delete USD, preserve original, rollback.
              R10: Force-cook any LOP nodes referencing evolved USD.
```

### Native OpenUSD Generation (R3)

Evolution uses `pxr.Usd.Stage.CreateInMemory()` — no string templates:

> **⚠ Idiom-vs-code divergence (verified 2026-06-06).** The `Tf.MakeValidIdentifier` line below is
> the *intended* idiom, not the live code. `evolution.py` imports only `from pxr import Usd, Sdf`
> (no `Tf`) and `agent_state.py` hand-rolls `_safe_prim_name(...)`. Neither memory module calls
> `Tf.MakeValidIdentifier` today. Reconciling on ONE sanitizer is RFC decision **D-3**
> (`docs/RFC_agent_usd_ledger.md`). The §12 import guard, §12 production list, and R3 manifest row
> carry the same aspirational `Tf` claim — treat them as the target, not as verified-live code.

```python
stage = Usd.Stage.CreateInMemory()
root_prim = stage.DefinePrim("/SYNAPSE", "Xform")
stage.SetDefaultPrim(root_prim)

# Safe prim names regardless of LLM-generated input (H21: Tf, not Sdf.Path)
safe_id = Tf.MakeValidIdentifier(session.id)
sess_prim = stage.DefinePrim(f"/SYNAPSE/memory/sessions/{safe_id}", "Xform")

# Native type handling auto-escapes VEX slashes, quotes, linebreaks
sess_prim.CreateAttribute("synapse:narrative", Sdf.ValueTypeNames.String).Set(text)

# Arrays without manual quoting
sess_prim.CreateAttribute("synapse:decisions", Sdf.ValueTypeNames.StringArray).Set(
    Vt.StringArray(decisions)
)

# Syntactically perfect USDA output
return stage.GetRootLayer().ExportToString()
```

**Fallback:** String-template generation available for environments without `pxr` (testing only).

### Solaris Viewport Sync (R10)

After successful evolution, force-cook any LOP nodes that reference the evolved USD file. H21 doesn't have `hou.lopNetworks()`, so we walk from root collecting `hou.LopNetwork` instances:

```python
def _sync_solaris_viewport(self, memory_path: str):
    def _find_lop_networks(parent):
        """Walk node tree collecting LopNetwork instances."""
        found = []
        for child in parent.children():
            if isinstance(child, hou.LopNetwork):
                found.append(child)
            found.extend(_find_lop_networks(child))
        return found

    for lop_net in _find_lop_networks(hou.node("/")):
        for node in lop_net.children():
            if node.type().name() in ("sublayer", "reference"):
                file_parm = node.parm("filepath1")
                if file_parm and memory_path in file_parm.evalAsString():
                    node.cook(force=True)
```

This ensures the Solaris viewport immediately reflects evolved memory data without requiring manual recook. Best-effort — never blocks evolution success.

### Three-Tier Memory Hierarchy

```
Behavior (global)  — How SYNAPSE operates across all projects
Project ($JOB)     — Decisions, conventions, team preferences per project
Scene ($HIP)       — Session logs, parameters, assets for this specific scene
```

### agent.usd Schema (v2.0.0)

Always USD from day one. Tracks execution state:

```
/SYNAPSE/agent/
    status, current_plan, dispatched_agents
/SYNAPSE/agent/integrity/
    session_fidelity, operations_total, operations_verified, anchor_violations
/SYNAPSE/agent/routing_log/
    decision_NNNN → fingerprint, primary_agent, advisory_agent, method, timestamp
/SYNAPSE/agent/handoff_chain/
    handoff_NNNN → from_agent, to_agent, task_id, fidelity_at_handoff
/SYNAPSE/memory/
    sessions/, decisions/, assets/, parameters/, wedges/
```

---

## 7. Dispatch Format

When routing to a subagent:

```
@AGENT_ID
TASK: {one-line summary}
CONTEXT: {relevant state, files, prior agent outputs}
CONSTRAINT: {time budget, token budget, scope limits}
DELIVERABLE: {exact expected output format}
DEPENDS_ON: {other agent outputs this needs, or "none"}
INTEGRITY: {required fidelity level, gate constraints}
```

---

## 8. Merge Protocol

After agents complete:

1. Collect all deliverables with IntegrityBlocks
2. Verify fidelity = 1.0 on every result — reject degraded outputs
3. Check for file ownership conflicts (same file modified by 2 agents)
4. If conflict → INTEGRATOR resolves via provenance chain
5. If clean → merge and present unified result
6. Run cross-agent verification (INTEGRATOR reviews interfaces)
7. Persist session state to agent.usd

---

## 9. Implementation Phases

### Phase 1: Lossless Execution Bridge (Foundation)

**Owner:** SUBSTRATE (primary), INTEGRATOR (advisory)
**Files:** `shared/bridge.py` ✅ (644 lines)
**Exit gate:** 100 random operations, ALL fidelity = 1.0.

### Phase 2: Agent Handoff Protocol

**Owner:** INTEGRATOR (primary), SUBSTRATE (advisory)
**Files:** `shared/bridge.py` AgentHandoff ✅, `shared/provenance.py`
**Exit gate:** 5-agent relay with complete provenance chain, no context dropped.

### Phase 3: Memory Evolution with Integrity

**Owner:** CONDUCTOR (primary), INTEGRATOR (advisory)
**Files:** `shared/evolution.py` ✅ (593 lines)
**Exit gate:** 10-session markdown → USD → companion → parse → diff = fidelity 1.0.

### Phase 4: agent.usd Schema Upgrade

**Owner:** HANDS (primary), CONDUCTOR (advisory)
**Files:** `python/synapse/memory/agent_state.py` (USDA generated inline — there is **no** `agent_schema.usda` file)
**Status:** Schema BUILT + test-pinned (`tests/test_agent_state.py`). Remaining work is **wiring** — the provenance writers (`log_routing_decision`/`log_handoff`/`log_integrity`/`write_verification`/`create_task`) have no live callers yet. See `docs/RFC_agent_usd_ledger.md`.
**Exit gate:** agent.usd round-trips with zero data loss.

### Phase 5: Lossless Router Integration

**Owner:** INTEGRATOR (primary), SUBSTRATE (advisory)
**Files:** `shared/router.py` ✅ (271 lines)
**Exit gate:** 50 tasks routed, history reconstructed, replay deterministic.

### Phase 6: End-to-End Integration

**Owner:** ALL agents, orchestrated by INTEGRATOR
**Files:** `src/pipeline.py`, `tests/test_pipeline_e2e.py`
**Exit gate:** Complex multi-agent task with all verifications passing. Undo restores scene to pre-session state.

---

## 10. Session State

Track across the session:

```
+-- ORCHESTRATOR STATE -----------------------------------------+
| Active Task: {current}                                        |
| Pipeline Stage: {observe|constraint|plan|specialize|execute|verify} |
| Agents Dispatched: {list with status}                         |
| AND/OR Tree: {current decomposition}                          |
| Hardest Subtask: {blocker}                                    |
| Completed: {list with fidelity scores}                        |
| Handoff Chain: {provenance}                                   |
| Session Fidelity: {min of all operation fidelities}           |
| Memory Stage: {charmander|charmeleon|charizard}               |
+---------------------------------------------------------------+
```

---

## 11. Safety Rules

1. **Never let two agents write the same file** — route through INTEGRATOR
2. **Bridge = audit/integrity layer on the `/mcp` path** — `LosslessExecutionBridge` wraps every operation it routes (undo + thread + integrity) and is the integrity authority for the external-MCP path. It is **not** the only code path to Houdini: the live `/synapse` transport calls `synapse.server.handlers` directly, with inline `hou.undos.group(...)` undo-wrapping + `server.main_thread.run_on_main` main-thread marshalling. Handlers = the live mechanism; bridge = the audited mechanism. Pinned by `tests/test_phase0b_consent_posture.py` (consent slice).
3. **All hou.* calls via hdefereval** — SUBSTRATE's async boundary, no direct access
4. **Gate levels enforced structurally** — disk writes auto-elevate to APPROVE, code execution requires CRITICAL (R4)
5. **Consent gates are real — on the bridge path only** — REVIEW/APPROVE/CRITICAL route through `synapse.core.gates.HumanGate` with timeout-to-rejection *when an operation goes through `LosslessExecutionBridge`*. The live `/synapse` handler path does **not** route through the bridge, so `execute_python`/`execute_vex` are **ungated** (single-user-localhost auto-approve — see §1.2 live-path note; D1). Pinned by `tests/test_phase0b_consent_posture.py`.
6. **Fidelity = 1.0 or stop** — any degradation surfaces immediately, rollback via undo
7. **Tests must pass before merge** — INTEGRATOR gates all deliverables
8. **Handoffs carry provenance** — every cross-agent transfer is traceable and verifiable
9. **Scene hash before AND after** — H21 topological hashing via cookCount + sessionId + geo intrinsics (R1)
10. **Memory evolution is lossless or aborted** — companion round-trip must match original
11. **Emergency halt is immediate** — no gradual wind-down, undo system handles partial state
12. **Never trust LLM boundary flags** — blast radius inferred from dependency graph (R7)
13. **PDG cooks don't block FastMCP** — `pdg.PyEventHandler` bridge keeps server responsive (R8)
14. **Evolved memory syncs viewport** — LOP nodes referencing USD force-cooked via LopNetwork walk (R10)

---

## 12. Houdini Import Guards

All production code uses try/except import guards:

```python
# Houdini API — bridge.py
_HOU_AVAILABLE = False
try:
    import hou
    import hdefereval
    _HOU_AVAILABLE = True
except ImportError:
    hou = None
    hdefereval = None

# PDG API — bridge.py (R8: H21 uses pdg module, not hou.pdgEventType)
_PDG_AVAILABLE = False
try:
    import pdg
    _PDG_AVAILABLE = True
except ImportError:
    pdg = None

# OpenUSD API — evolution.py (R3: H21 uses Tf.MakeValidIdentifier)
_PXR_AVAILABLE = False
try:
    from pxr import Usd, Sdf, Vt, Tf
    _PXR_AVAILABLE = True
except ImportError:
    Usd = Sdf = Vt = Tf = None

# Consent gate system — bridge.py (three-tier fallback)
_GATES_AVAILABLE = False
try:
    from synapse.core.gates import HumanGate, GateDecision, CoreGateLevel
    _GATES_AVAILABLE = True
except ImportError:
    HumanGate = GateDecision = CoreGateLevel = None

# Houdini API — evolution.py (R10: viewport sync)
_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None
```

All modules must work in both modes:

- **Production (inside Houdini 21):** Full `hou` API, `hdefereval` main-thread dispatch, `pdg` module for PDG events, `pxr` native USD with `Tf.MakeValidIdentifier`, real topological hashing via `cookCount`/`sessionId`/intrinsics, SOP→LOP dependency tracing, consent gates via `synapse.core.gates.HumanGate`, viewport force-cook via LopNetwork walk
- **Standalone (testing/CI):** Direct execution, timestamp-based hashes, string-template USD fallback, auto-approve consent, R7/R8/R10 no-op gracefully

---

## 13. Key Type Definitions

All agents import from `shared/types.py` (INTEGRATOR owns write access):

| Type | Purpose |
|---|---|
| `AgentID` | Enum: SUBSTRATE, BRAINSTEM, OBSERVER, HANDS, CONDUCTOR, INTEGRATOR |
| `ExecutionResult` | Universal return type with `.ok()` / `.fail()` + integrity field |
| `TaskSpec` | Inter-agent dispatch specification |
| `NodeManifest` | Declarative network builder (parent + NodeSpec list) |
| `GeoSummary` | Token-efficient geometry metadata (<100 tokens) |
| `RoutingFeatures` | 4-dimension feature vector with `.fingerprint()` for fast-path |
| `ChainSpec` | PDG chain specification for multi-step orchestration |
| `FILE_OWNERSHIP` | Dict mapping file paths → owning AgentID |

---

## 14. File Structure

```
synapse-agents/
├── CLAUDE.md                      # This file — orchestrator blueprint
├── README.md                      # Project overview
├── run_team.py                    # Python orchestrator entry point
├── agents/
│   ├── SUBSTRATE.md               # Pillar 1: Async architecture
│   ├── BRAINSTEM.md               # Pillar 2: Self-healing execution
│   ├── OBSERVER.md                # Pillar 3: Semantic observability
│   ├── HANDS.md                   # Pillar 4: H21 native paradigms
│   ├── CONDUCTOR.md               # Pillar 5: PDG orchestration + memory
│   └── INTEGRATOR.md              # Cross-cutting: API, tests, CI
├── shared/
│   ├── __init__.py
│   ├── types.py                   # Canonical type definitions (250 lines)
│   ├── bridge.py                  # Lossless Execution Bridge (644 lines)
│   ├── evolution.py               # Memory evolution pipeline (593 lines)
│   └── router.py                  # MOE sparse routing engine (271 lines)
├── scripts/
│   ├── dispatch.sh                # Single task dispatch
│   └── run_full_team.sh           # Full team parallel execution
├── tasks/
│   └── templates.yaml             # Pre-defined task decompositions
├── tests/                         # Generated by INTEGRATOR
└── results/                       # Execution outputs
```

---

## 15. Revision Manifest

All revisions verified live on Houdini 21.0.596 / SYNAPSE v5.8.0.

| Rev | What Changed | Where | H21 API | Commit |
|---|---|---|---|---|
| R1 | Topological scene hashing | `bridge.py` | `cookCount()` + `sessionId()` + geo intrinsics | 128229d |
| R2 | Async→sync execution boundary | `bridge.py` | `hdefereval.executeInMainThreadWithResult()` | original |
| R3 | Native OpenUSD generation | `evolution.py` | `pxr.Usd.Stage.CreateInMemory()` + `Tf.MakeValidIdentifier()` | e71fbfe |
| R4 | Structural disk-write gate override | `bridge.py` | `Operation.gate_level` property (CRITICAL-aware) | original |
| R5 | Word-boundary feature extraction | `router.py` | `re.search(rf'\b...\b')` | original |
| R7 | Blast radius inference | `bridge.py` | `hou.LopNode` isinstance + `node.dependents()` | original |
| R8 | PDG async cook bridge | `bridge.py` | `pdg.EventType` + `pdg.PyEventHandler` + `pdg.GraphContext` | 3ae4737 |
| R10 | Solaris viewport sync | `evolution.py` | `hou.LopNetwork` isinstance walk from root | 3ae4737 |

---

## 16. Recursive Observability Loop

SYNAPSE reads its own runtime telemetry and recommends substrate tuning. The
loop is closed end-to-end across six tested layers — every API in this
section is public, frozen, and pinned by tests.

### 16.1 Data flow

```
LosslessExecutionBridge.operation_stats()      ──┐
  per-agent counters, success rates, anchor      │
  violations, log size, session id               │
                                                 │
MOERouter.fingerprint_counts()                 ──┤
  fingerprint → call-count snapshot              │
                                                 ▼
LosslessEvolution → EvolutionIntegrity         ──→  ConductorAdvisor.analyze()
  failure list with category prefixes               returns list[Recommendation]
  ("Decision content drift: …" etc)
                                                     │
                                                     ▼
                                                RecommendationHistory
                                                  capped deque + JSONL
                                                  persistence (.tmp + replace)
                                                     │
                                                     ▼
                                                ConductorAdvisor.analyze_history()
                                                  meta-recursion: same
                                                  (kind, target) ≥5×
                                                  → escalate
```

### 16.2 Public API surface

| Component | Method | Returns | Owner |
|---|---|---|---|
| `LosslessExecutionBridge` | `operation_stats()` | dict with `per_agent`, `per_agent_verified`, `per_agent_success_rate`, `success_rate`, `anchor_violations`, `operations_total`, `operations_verified`, `log_size`, `log_capacity`, `per_operation_type`, `session_id` | SUBSTRATE |
| `LosslessExecutionBridge` | `recent_operations(n=100)` | list[IntegrityBlock] copy | SUBSTRATE |
| `LosslessExecutionBridge` | `clear_operation_log()` | int dropped | SUBSTRATE |
| `MOERouter` | `fingerprint_counts()` | dict[str, int] copy | SUBSTRATE |
| `LosslessEvolution._verify_lossless` | (internal) | EvolutionIntegrity with content-hash failures | CONDUCTOR |
| `ConductorAdvisor` | `analyze(bridge_stats, evolution_failures, routing_fingerprints)` | list[Recommendation] | CONDUCTOR |
| `ConductorAdvisor` | `analyze_history(history)` | list[Recommendation] meta | CONDUCTOR |
| `RecommendationHistory` | `record(recs, timestamp)` | int recorded | CONDUCTOR |
| `RecommendationHistory` | `recent(n=50)` / `all()` / `clear()` | list[HistoryEntry] / int | CONDUCTOR |
| `RecommendationHistory` | `to_jsonl(path)` / `from_jsonl(path)` | int / RecommendationHistory | CONDUCTOR |
| `advise_from_bridge` | one-shot helper | list[Recommendation] | CONDUCTOR |

### 16.3 Recommendation schema

`Recommendation` is `frozen=True, slots=True` and serializes via `.to_dict()`:

```
kind        — agent_health | evolution_writer_fix | router_promote |
              trigger_tune | repeated_recommendation
target      — subject identifier (agent id, fingerprint, category, slug)
rationale   — one-line human explanation
confidence  — 0..1 (scales with sample size)
severity    — info | warn | critical (informational; gates still apply)
evidence    — dict of supporting facts
```

### 16.4 Design constraints

- **Read-only by construction.** The advisor cannot mutate constants, router
  state, or bridge logs. Verified by `test_advisor_never_mutates_inputs`.
- **Statistically silent.** Below `MIN_OPS_FOR_VERDICT` (10) and
  `DRIFT_FIELD_CLUSTER_THRESHOLD` (3) the advisor returns nothing. No alarm
  fatigue.
- **Severity is informational.** Even 'critical' recommendations route
  through the bridge gate system before any tuning is applied. The artist
  remains the decision authority.
- **History is bounded.** `RecommendationHistory.DEFAULT_CAPACITY=500` —
  oldest entries drop FIFO. JSONL persistence is atomic via `.tmp + replace`
  and tolerates malformed lines on read (best-effort recovery).
- **Meta-recursion threshold.** `REPEATED_RECOMMENDATION_THRESHOLD=5` —
  five occurrences of the same `(kind, target)` flag a chronic issue. Ten+
  escalates to CRITICAL.
- **Per-agent counters are lifetime.** They survive operation log eviction;
  bounded log only caps the IntegrityBlock detail, not the aggregate
  counters.

### 16.5 Tests pinning the loop

| Pin | File |
|---|---|
| Router conformance + auto-promotion | `tests/test_router_internals.py` |
| Bridge per-agent + log accessors + evolution archive + content-aware verify | `tests/test_evolution_bridge_internals.py` |
| ConductorAdvisor analyze + per-agent + drift + promotion | `tests/test_conductor_advisor.py` |
| Per-agent advisor + canonical-constant pinning helper | `tests/test_pass7_per_agent_and_canonical.py` |
| Router accessor + history JSONL round-trip + meta-analysis + end-to-end | `tests/test_pass8_history_and_meta.py` |

If any of the API surface in §16.2 changes, the corresponding test in §16.5
fails. The doc/code conformance test in `tests/test_router_internals.py`
pins specific identifiers from this section so future doc drift fails loud.

---

### Current Status

| Component | Status | File | Lines |
|---|---|---|---|
| Lossless Execution Bridge | ✅ Verified H21 | `shared/bridge.py` | ~700 |
| Memory Evolution Pipeline | ✅ Verified H21 | `shared/evolution.py` | ~600 |
| MOE Sparse Router | ✅ Verified H21 | `shared/router.py` | 271 |
| Shared Type System | ✅ Done | `shared/types.py` | 250 |
| Agent Definitions | ✅ Done | `agents/*.md` | 6 files |
| Consent Gate Wiring | ✅ Wired to panel | `shared/bridge.py` | (in bridge) |
| Handoff Protocol | ✅ Done | `shared/bridge.py` | (in bridge) |
| Emergency Halt | ✅ Done | `shared/bridge.py` | (in bridge) |
| Blast Radius Inference | ✅ Verified H21 | `shared/bridge.py` | (in bridge) |
| PDG Async Cook Bridge | ✅ Verified H21 | `shared/bridge.py` | (in bridge) |
| Viewport Sync | ✅ Verified H21 | `shared/evolution.py` | (in evolution) |
| agent.usd Schema | ✅ Built (SCHEMA_VERSION 2.0.0) · ⚠ provenance writers dormant | `python/synapse/memory/agent_state.py` | ~688 |
| Routing Log Persistence | 🔶 Phase 5 | — | — |
| E2E Pipeline Orchestrator | 🔶 Phase 6 | — | — |
