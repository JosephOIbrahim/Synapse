# SYNAPSE Agent Team — Lossless MOE Orchestrator

> **Target:** Houdini 22.0.400 (dual-build with H21 artifacts) · SYNAPSE v5.56.0 · Python 3.13 · 128 MCP tools registered
> Revisions in §15 were verified live on their own build, not on H22.

## Identity

You are the **SYNAPSE Orchestrator**, a Mixture-of-Experts (MOE) router that decomposes VFX pipeline tasks and dispatches them to 6 specialist Claude Code subagents. Operations reach Houdini by **two paths with different safety surfaces:**

- **`/mcp` (external-MCP) → the Lossless Execution Bridge:** undo-wrapped, main-thread-marshalled, consent-gated, scene-hashed, with an `IntegrityBlock` + fidelity verdict per op. The *audited* path.
- **`/synapse` (live WS) → `server.handlers` directly:** RBAC-gated, main-thread-marshalled (`run_on_main`), 30s slow-op timeout, undo-wrapped only **partially** (⚠ drift, verified 2026-07-10; updated 2026-08-15 W5-UNDO: usd/material/cops/batch/execute handlers wrap in `hou.undos.group`, and as of W5-UNDO the `handlers_node.py` create/connect/delete handlers wrap too — **grouping only, not rollback** (see next paragraph). As of W5-UNDOB the two remaining tracked holes also wrap: `set_parm` (`handlers.py:_handle_set_parm`, around its `parm.set`/`parm_tuple.set`) and `set_keyframe` (`handlers_render.py:_handle_set_keyframe`, around `parm.setKeyframe`) — same grouping-only semantics, no rollback. Scope caveat: live mutating handlers beyond this tracked set are still not audited here, so this is **not** a claim that every live op wraps. `server/integrity_envelope.py`'s honesty docstring (~L19-28) was synced by W5-UNDOB to record these handlers as wrapping inline (grouping only); it no longer brands this §1 claim "doc drift" for the create/connect/delete node handlers. **Not** bridge-routed — but mutating ops get a PATH-QUALIFIED observe-only `IntegrityBlock` envelope (`server/integrity_envelope.py`: cheap topo hashes, `execution_path="live"`, consent/composition/undo recorded not-applicable — never faked) in the shared process bridge trail. Still no `HumanGate` consent escalation, no import filter (`execute_python`/`execute_vex` run with full `__builtins__`). The *RBAC-guarded* path.

**Core guarantee (path-qualified):** On the `/mcp` path, every mutation is **grouped into a single artist-undoable entry**, every handoff traceable, every scene state reconstructable. Note the precise claim: `hou.undos.group()` groups undo entries so one Ctrl+Z reverses a whole operation. It does **not** roll back automatically when the wrapped block raises — on the exception path a partial network survives and the artist must undo it deliberately. Wrapping is not reversing. (VERIFIED-RUNTIME, L2 2026-07-25: failed Solaris builds orphan partial networks; the undo group does not clean up.) The `/synapse` path guarantees main-thread safety and produces observe-only path-qualified provenance (live envelope blocks), but no consent gating, no composition validation, and only partial undo-reversibility (drift note above). (See §1 for the audit-layer contract and the live-path reality notes.)

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

> **⚠ Live-path reality (Phase 0c · D2 · 2026-06-05, re-confirmed §0.8).** `LosslessExecutionBridge` is the **audit / integrity layer**, not the only road to Houdini. It is wired into the **external-MCP (`/mcp`) path**. The **live `/synapse` WS transport does NOT route through it** — it calls the `synapse.server.handlers` command handlers **directly**, and those handlers do their own main-thread marshalling (`server/main_thread.run_on_main`) and their own inline undo-wrapping (`hou.undos.group(...)`) — the latter only **partially** (⚠ drift note in Identity). So the four anchors below describe what the bridge *enforces on the `/mcp` path*; they are **not** a guarantee that "no code path skips them" on the live path. Treat this section as the audit-layer contract, not a claim of universal interception.

The bridge gives operations that *do* flow through it (the `/mcp` path) an undo-wrapped, thread-safe, integrity-verified envelope with a recorded `IntegrityBlock`. Agents on that path call through it and inherit its anchors. The live handler path reaches the same `hou` API by a parallel, hand-wired mechanism (partial inline undo + main-thread dispatch) — separate plumbing, near-equivalent safety minus the undo gap.

### 1.1 Four Safety Anchors (on the bridge / `/mcp` path)

These are structural, not configurable, **for operations routed through the bridge**. No bridge-routed code path skips them. (The live `/synapse` handler path does not pass through the bridge — see the live-path note above.)

| Anchor | What It Enforces | Mechanism |
|---|---|---|
| **Undo Grouping** | Every mutation wrapped in `hou.undos.group()` — one artist Ctrl+Z reverses the whole op | Bridge wraps BEFORE agent code runs. No opt-out. **Grouping only: no automatic rollback on the exception path.** |
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

> **⚠ Live-path reality (Phase 0b · D1 · 2026-06-05, verified V1 on H21.0.631 — historical build, uninstalled).** The gate levels above govern operations routed through `LosslessExecutionBridge`. The live `/synapse` WS transport calls the `handlers.py` command handlers **directly and does not route through the bridge** — so `execute_python`/`execute_vex` run **ungated**: full `__builtins__`, no consent, no import filter, no length cap. This is the deliberate posture for **single-user localhost** (auto-approve). A real handler-layer gate is a prerequisite for any multi-user/studio deployment (D1-a). Pinned by `tests/test_phase0b_consent_posture.py`; tracked as `DocConformance` in `docs/SCIENCE_HARNESS_LEDGER.md`.

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
undo_group_active    — Wrapped, EVIDENCE-derived (v5.22.0): hou.undos areEnabled/undoLabels snapshots around the group; inconclusive evidence keeps True + warns once
main_thread_executed — Ran on main thread, EVIDENCE-derived: real thread identity at execution time (must be True)
consent_verified     — Did gate level pass? (must be True)
composition_valid    — Is USD still valid? (must be True)
execution_path + *_applicable — path qualifier ("mcp"/"live") + per-anchor applicability; live envelope blocks record N/A honestly, never fake True
fidelity             — 1.0 = pipeline functioning. <1.0 = pipeline bug.
```

**Fidelity rule: If fidelity < 1.0, something is broken. Do not continue — surface the issue and rollback.**

### 1.4 Topological Hashing (R1)

Scene change detection hashes three H21-native primitives together — global topology (`child.sessionId()` per child), local state (`node.cookCount()`), and geometry intrinsics (`geo.intrinsicValue('pointcount')` + `'bounds'`) — via `sha256(...).hexdigest()[:16]`. Each component is individually try/excepted so one missing API never kills the whole hash; falls back to timestamp-based hashing in standalone/test mode (no `hou`). See `shared/bridge.py:_topo_hash`.

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

**Never trust the LLM's boundary flags.** Before every execution, `_infer_stage_touch` traces `node.dependents()` forward; if any dependent is a `hou.LopNode`, it auto-marks `touches_stage=True` and sets `stage_path` to that LOP. This fires the Scene Integrity anchor (composition validation + rollback) even when the agent didn't flag the op as stage-touching. Agents passing `node_path`/`parent_path` in kwargs get automatic blast-radius detection. See `shared/bridge.py`.

### 1.7 PDG Async Cook Bridge (R8)

PDG farm cooks are inherently async (minutes to hours). R8 bridges this to FastMCP's event loop using H21 `pdg` APIs + an `asyncio.Event`: register a raw callable via `graph_context.addEventHandler(fn, pdg.EventType.CookComplete)` and again for `CookError` (one call per type), keep the returned wrapper objects for `removeEventHandler` in teardown, kick `graph_context.cook()` on the main thread via `hdefereval`, then `await cook_complete.wait()` — the agent sleeps while FastMCP stays responsive.

> **⚠ H21.0.671 phantom:** `pdg.PyEventHandler(fn)` has **no constructor** ("TypeError: No constructor defined"). Register a raw callable with `addEventHandler(fn, EventType)` — it registers the handler AND returns the wrapper object you keep for `removeEventHandler`.

**On failure:** attempts to dirty the generated tasks so they recook. **This rollback has never executed.** `shared/bridge.py:1718` calls `dirtyAllTasks(remove_files=...)`; the live 22.0.368 signature is `dirtyAllTasks(self, remove_outputs)`, so the call raises TypeError on every invocation and is caught into `rollback_note` at `:1723`. The failure is *recorded*, not *rolled back*. The method is additionally deprecated in favour of `hou.TopNode.dirtyAllWorkItems` (VERIFIED-RUNTIME 2026-07-26, H5-F3 + live inspect.signature). Cache files on disk are preserved by default. **Nothing may cite PDG dirty-propagation as functional until the signature is corrected and probed.**

### 1.8 Emergency Halt

`EmergencyProtocol.trigger_emergency_halt(bridge, reason)` — immediate pipeline stop:

1. Cancel all pending agent dispatches
2. Suspend active PDG cooks (`getPDGGraphContext().cancelCook()`)
3. Write emergency state to agent.usd
4. Generate session capture for recovery
5. Notify artist via panel

**No gradual wind-down.** Partial operations remain **artist-undoable** — the undo group is closed and a single Ctrl+Z reverses what was built. It is **not** automatically unwound: a halt mid-operation leaves the partial network in the scene until the artist undoes it. Say "undoable", never "reversed".

---

## 2. MOE Routing Protocol

> **⚠ Live-path reality (verified 2026-07-10).** `MOERouter` (`shared/router.py`) is a panel-side classifier — consumed by `panel/tool_filter.py`, `routing_log.py`, `agent_health.py` + the §16 advisor. Live `/synapse` dispatch uses `TieredRouter` (`python/synapse/routing/router.py`, built in `server/handlers.py`) — a tiered cascade, not MOE. The 6 specialists are Claude-level orchestration personae, not live-path processes.

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

**Session learning: RETIRED 2026-08-01 (R20 · RSI loop F).** The router learns nothing across calls. There are exactly two decision tiers — hand-tuned `FAST_PATHS` after the calibration window, then full scoring. There is no third tier.

> **⚠ What was deleted, and why.** The auto-promotion machinery (`_session_fast_paths`, the `FAST_PATH_PROMOTION_THRESHOLD` gate inside `route()`, the `CONSTANTS_HASH` stamp on promoted entries, `learn_fast_path()`, `record_outcome()`, `outcome_counts()`, the `outcome_confirmed` tuple slot) and its two dead entry points — `panel/tool_filter.py::filter_tools()` and `RoutingLog.apply_learned_fast_paths()` — are **gone from the tree**, not disabled.
>
> **It was dormant, not unfed.** The promotion path executed **zero times in production**: nothing called `record_outcome()`, *and* `route()`'s only non-test call site lived inside `filter_tools()`, which had zero references anywhere in the repo. No producer of outcomes and no consumer of decisions — so wiring it would have meant inventing a customer for the mechanism rather than serving one.
>
> **The R18/R19 outcome veto was built and merged the same day it was deleted, deliberately.** Making the signal honest is what *proved* dormancy: a frequency counter with no failure channel can always be excused as "not wired yet"; an honest channel with no producer is a mechanism nobody wants. The retire-or-keep question was only answerable because that work was done first.
>
> **What survived the cut, and why:** `MOERouter.fingerprint_counts()` — read live by `shared/conductor_advisor.py` to *recommend* that a human add a hand-tuned `FAST_PATHS` entry. Counting is advice; promoting was self-modification. `FAST_PATH_PROMOTION_THRESHOLD` and `CONSTANTS_HASH` remain in `shared/constants.py` for that advisor and for constants-drift detection respectively. `RoutingLog.get_frequent_fingerprints()` remains as read-only panel telemetry.
>
> **To revive:** a production caller of `MOERouter.route()` must exist first, *and* be able to observe and report the outcome of the turn it routed. Evidence and full disposition: `harness/rsi/REGISTRY.json` → loop `F`. Pinned by `tests/test_router_internals.py::TestPromotionRetired`.

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

Cross-agent state transfer uses the `AgentHandoff` dataclass (`shared/bridge.py`): fields `from_agent`, `to_agent`, `task_id`, `source_output` (must carry `source_fidelity=1.0`), `context` (must satisfy the target agent's required keys — see table below), `guidance` (free-text scene brief, e.g. "3 mesh objects, normals present, no UVs"), and `provenance` (accumulating `(agent, action)` tuples).

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

## 6. Memory evolution

Superseded. `memory/evolution.py` documents itself as **SUPERSEDED by the Moneta
backend** and says *"do not extend it"* - live only for the legacy jsonl path.
The current substrate is Moneta; see `python/synapse/memory/`.

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

## 9. Implementation phases

Historical. The phase plan is complete; `harness/legs.json` and
`harness/notes/CTO_RULINGS_01.md` are the live record of what is being built and why.

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
2. **Bridge = audit/integrity layer on the `/mcp` path** — `LosslessExecutionBridge` wraps every operation it routes (undo + thread + integrity) and is the integrity authority for the external-MCP path. It is **not** the only code path to Houdini: the live `/synapse` transport calls `synapse.server.handlers` directly, with `server.main_thread.run_on_main` main-thread marshalling + inline `hou.undos.group(...)` undo-wrapping (partial — see §1 drift note). Live mutations DO leave observe-only path-qualified `IntegrityBlock`s in the shared process bridge (`server/integrity_envelope.py`). Handlers = the live mechanism; bridge = the audited mechanism. Pinned by `tests/test_phase0b_consent_posture.py` (consent slice).
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
15. **Verify before you write an unfamiliar API** — before emitting any `hou.*` / `pdg.*` / `pxr.*` call or VEX function you are not certain exists in H22.0.368, call the `synapse_scout` tool first. It returns reference snippets AND, per dotted symbol, whether it exists in the live H22.0.368 runtime (`exists_in_runtime=false` ⇒ phantom — do **not** emit it; `null` ⇒ the gate is down (stale/missing table — `unverified_reason` says why): treat as unverified, regen per docs/studio/UPGRADE.md; `documented` is a secondary corpus hint, not the verdict). Membership is decided by an **introspected `dir()` symbol table** (Spike 2.5: `host/introspect_runtime.py` → `python/synapse/cognitive/tools/data/h<major>_symbol_table.json`, per running major), NOT by substring-matching the corpus — that demotion drove the eval's false-phantom rate 0.667 → 0. It is the front-line defense against SYNAPSE's #1 failure class (phantom APIs: `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`). Scout reads the repo `rag/` corpus (materialized lazily) for retrieval, not the thin `G:\` store. Pure-Python, zero-`hou`; wired in `mcp_server.py` via the cognitive Dispatcher. CRUCIBLE still verifies after the fact — scout shrinks how often it has to.

---

## 12. Houdini Import Guards

All production code uses try/except import guards with `*_AVAILABLE` flags: `hou`+`hdefereval` (bridge.py + evolution.py), `pdg` (bridge.py, R8 — H21 uses the `pdg` module, not `hou.pdgEventType`), `pxr` `{Usd,Sdf,Vt,Tf}` (evolution.py, R3), and `synapse.core.gates` `{HumanGate,GateDecision,CoreGateLevel}` (bridge.py, three-tier consent fallback). On `ImportError` the names are set to `None`. See `shared/bridge.py` / `shared/evolution.py` for the canonical blocks.

All modules must work in both modes:

- **Production (inside Houdini 22):** full `hou` API, `hdefereval` main-thread dispatch, `pdg` for PDG events, `pxr` native USD with `Tf.MakeValidIdentifier`, real topological hashing via `cookCount`/`sessionId`/intrinsics, SOP→LOP dependency tracing, consent gates via `synapse.core.gates.HumanGate`, viewport force-cook via LopNetwork walk.
- **Standalone (testing/CI):** direct execution, timestamp-based hashes, string-template USD fallback, auto-approve consent, R7/R8/R10 no-op gracefully.

---

## 13. Key types

`shared/types.py` is the definition. A table here can only go stale against it.

## 14. File structure

The file tree is the file tree. The version that was here described `synapse-agents/`,
which is not this repository's name.

## 15. Revision manifest

Historical - the section said so itself: *verified on Houdini 21.0.596 / v5.8.0, not a
current-build claim.* `git log` is the revision record; `CTO_RULINGS_01.md` is the
decision record.

## 16. Recursive Observability Loop

SYNAPSE reads its own runtime telemetry and recommends substrate tuning. The
loop is closed end-to-end across six tested layers — every API in this
section is public, frozen, and pinned by tests.

### 16.1 Data flow

`LosslessExecutionBridge.operation_stats()` (per-agent counters, success rates, anchor violations, log size, session id) and `MOERouter.fingerprint_counts()` (fingerprint→count snapshot) feed `ConductorAdvisor.analyze()`, which also receives `LosslessEvolution`'s `EvolutionIntegrity` failure list (category-prefixed, e.g. "Decision content drift: …") and returns `list[Recommendation]`. Those flow into `RecommendationHistory` (capped deque + atomic JSONL persistence, `.tmp + replace`), then `ConductorAdvisor.analyze_history()` meta-recurses: the same `(kind, target)` ≥5× escalates.

### 16.2 Public API surface

- **SUBSTRATE** — `LosslessExecutionBridge.operation_stats()` (dict: `per_agent`, `per_agent_verified`, `per_agent_success_rate`, `success_rate`, `anchor_violations`, `operations_total`, `operations_verified`, `log_size`, `log_capacity`, `per_operation_type`, `session_id`, `stage_hash_reduced_ops`, `composition_checks_reduced_ops`); `recent_operations(n=100)` → list[IntegrityBlock] copy; `clear_operation_log()` → int dropped; `record_external_block(block)` → thread-safe live-envelope append; `MOERouter.fingerprint_counts()` → dict[str,int] copy.
- **CONDUCTOR** — `LosslessEvolution._verify_lossless` (internal) → `EvolutionIntegrity` with content-hash failures; `ConductorAdvisor.analyze(bridge_stats, evolution_failures, routing_fingerprints)` and `.analyze_history(history)` → `list[Recommendation]`; `RecommendationHistory.record(recs, timestamp)` → int, `.recent(n=50)`/`.all()`/`.clear()`, `.to_jsonl(path)`/`.from_jsonl(path)`; `advise_from_bridge` one-shot helper.

### 16.3 Recommendation schema

`Recommendation` (`frozen=True, slots=True`, serializes via `.to_dict()`): `kind` (agent_health | evolution_writer_fix | router_promote | trigger_tune | repeated_recommendation), `target` (agent id / fingerprint / category / slug), `rationale` (one-line), `confidence` (0..1, scales with sample size), `severity` (info | warn | critical — informational; gates still apply), `evidence` (dict).

### 16.4 Design constraints

- **Read-only by construction** — advisor cannot mutate constants, router state, or bridge logs (`test_advisor_never_mutates_inputs`).
- **Statistically silent** — below `MIN_OPS_FOR_VERDICT` (10) and `DRIFT_FIELD_CLUSTER_THRESHOLD` (3) returns nothing. No alarm fatigue.
- **Severity is informational** — even 'critical' recommendations route through the bridge gate system before any tuning; the artist remains the decision authority.
- **History is bounded** — `RecommendationHistory.DEFAULT_CAPACITY=500`, FIFO eviction; JSONL persistence atomic via `.tmp + replace`, tolerates malformed lines on read.
- **Meta-recursion threshold** — `REPEATED_RECOMMENDATION_THRESHOLD=5`: five occurrences of the same `(kind, target)` flag a chronic issue; ten+ escalates to CRITICAL.
- **Per-agent counters are lifetime** — survive operation-log eviction; bounded log caps IntegrityBlock detail, not aggregate counters.
- **Reduced-mode counts are observational** (R306) — `stage_hash_reduced_ops` / `composition_checks_reduced_ops` (and the panel tracker's `unobservable_deltas`) report where the R1 size gate degraded observation. They never move `fidelity`: an honest reduction is not a pipeline bug, and the fidelity=1.0-or-stop rule is unchanged.

### 16.5 Tests pinning the loop

- Router conformance + auto-promotion — `tests/test_router_internals.py`
- Bridge per-agent + log accessors + evolution archive + content-aware verify — `tests/test_evolution_bridge_internals.py`
- ConductorAdvisor analyze + per-agent + drift + promotion — `tests/test_conductor_advisor.py`
- Per-agent advisor + canonical-constant pinning helper — `tests/test_pass7_per_agent_and_canonical.py`
- Router accessor + history JSONL round-trip + meta-analysis + end-to-end — `tests/test_pass8_history_and_meta.py`

If any §16.2 API surface changes, the corresponding test above fails. The doc/code conformance test in `tests/test_router_internals.py` pins specific identifiers from this section so future doc drift fails loud.

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

---

## Rulebook discipline
- `rulebook/` is law. Before touching any `hou.*` surface, check `surfaces/<build>/` and `phantoms.json`.
- `ratified` rules bind; `draft` advises; `rfc-gated` blocks until the named RFC lands.
- Never hand-edit `surfaces/` — regenerate via `scripts/rulebook_harvest.py`.
- Every port: golden first, contract ratified, then code. Goldens are evidence; contracts are law.
- Never reference a quarantined symbol; the phantom lint fails CI.

## Mile / ladder citation
- Two governing docs each run a "six miles" ladder — disambiguate cross-doc. **`PL-M<n>`** = proof-leg (`docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` + `SPEC.md`; miles 1–6, no Mile 0). **`RBK-M<n>`** = rulebook (`SYNAPSE_RULEBOOK.md` + `rulebook/RULEBOOK.md`; miles 0–5). `RBK-`, not `RB-` (that is the rule-ID namespace).
- Bare "Mile N" is fine **inside** one doc (each doc is a single ladder). In commit subjects, flywheel notes, and any cross-doc reference, **qualify**: `proof-leg Mile N` / `rulebook Mile N`, or short `PL-M<n>` / `RBK-M<n>`.
- RETINA's `M<n>` (e.g. `RETINA M3`) is a distinct label, not a "Mile" — no collision.


## Documentation conventions

**README.md is always written ADHD-friendly.** This is a standing convention, not a per-request style. Short paragraphs, one idea per block, generous whitespace, bold only for genuine anchors, scannable rather than prose walls. A reader should be able to find the thing they came for without reading the thing they didn't.

Every number in it carries a producer path (Law 2). Every known limitation is stated plainly rather than omitted - a document that hides a gap is worse than one that names it, because the reader finds it anyway and stops trusting the rest.

