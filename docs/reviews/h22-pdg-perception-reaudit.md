# H22 pdg Perception Re-Audit — Runbook Step 8

**Artifact:** `docs/reviews/h22-pdg-perception-reaudit.md` (persisted by the drop-week orchestrator from the ASSAYER dispatch report, 2026-07-16)
**Role:** ASSAYER (V1 hard gate) — Spike 3.0-style `dir()` audit of the `pdg` surface on H22

**Probe path:** HYTHON FALLBACK — bridge ws://localhost:9999 unreachable (`socket.connect` timed out). Probed via `$HYTHON` = `C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe`.
**Probed build (verbatim `hou.applicationVersionString()`):** `"22.0.368"` · Python `3.13.10` · `pdg` from `C:\PROGRA~1/SIDEEF~1/HOUDIN~1.368/houdini/python3.13libs\pdg\__init__.py`
**Status qualifier:** headless PASS = PROVISIONAL per protocol; no build mismatch to flag (probed build == the H22 drop target; no live bridge exists this session, H21 uninstalled).

**Baseline correction:** `harness/notes/mile2_*` artifacts are the graph-oracle/nodetype introspection (Spike 2.5), NOT pdg. The actual pdg dir() baseline is `docs/sprint3/spike_3_0_pdg_api_audit.md` (Spike 3.0, 21.0.671, py 3.11.7) + the Spike 3.3 event-recon memory. Diffed against those.

## Counts

- **4/4 H21 behavioral truths → VERIFIED on 22.0.368** (provisional-headless)
- **16 surfaces probed: 10 resolved / 6 phantom — resolution map IDENTICAL to H21**
- **QUARANTINE: 0** · probe errors: 0
- Real API drift: 2 removals on `pdg.Scheduler` (zero repo references — no SYNAPSE breakage)

## The re-tested truths (verbatim outputs)

1. **`pdg.PyEventHandler(fn)` has no constructor — STILL TRUE.**
   Probe: `pdg.PyEventHandler(lambda e: None)` → `TypeError: _pdg.PyEventHandler: No constructor defined!`
   Subclass trampoline `class _H(pdg.PyEventHandler): ... ; _H()` → `TypeError: _H: No constructor defined!`
2. **Raw-callable registration is the working form — STILL TRUE.**
   `wrapper = gc.addEventHandler(cb, pdg.EventType.All)` → `wrapper_type: "PyEventHandler"`, `isinstance(wrapper, pdg.PyEventHandler): true`; `gc.removeEventHandler(wrapper)` → OK; `gc.removeEventHandler(cb)` (raw callable, negative control) → `TypeError: removeEventHandler(): incompatible function arguments. ... (self: _pdg.EventEmitter, arg0: PYPDG_EventHandler)` — same as H21.
3. **Events fire on a WORKER thread — STILL TRUE.** 10 events during `gen.cookWorkItems(block=True)` on a scratch `/obj/assay_topnet/assay_gen` (genericgenerator): `events_all_off_main: true`, `is_main_seen: [false]`, threads `Dummy-2..Dummy-11`. Topnet destroyed after.
4. **`event.workItemId`, NOT `event.workItem` — STILL TRUE.** `has_workItem_attr: false`, `has_workItemId_attr: true`; live `dir(event)` = `context, currentState, dependencyId, lastState, message, node, type, workItemId, workItemIds` — byte-identical 9-attr shape to the H21 recon. `workItemId` = `-1` on non-item events, real int (`1`) on `WorkItemAdd`.

## dir() diff vs Spike 3.0 baseline (21.0.671 → 22.0.368)

| Surface | H21 | H22 | Delta |
|---|---|---|---|
| `pdg` module | 235 | 235 | + `curPlatform` (function), `serviceSchedulerType` (type); − `ServiceClientLogType` (capitalized dup removed; lowercase `serviceClientLogType` still present), − `parms` **lazy-import artifact, NOT removed** — `import pdg.parms` resolves fine |
| `pdg.Scheduler` | 102 | 101 | **REAL REMOVALS: `onWorkItemFileResult`, `onWorkItemSetAttribute`** (+ `platform`); `onWorkItemAddOutput` still present. Repo-wide grep for both removed names + `ServiceClientLogType` + `pdg.parms` = **0 hits** → nothing in SYNAPSE breaks |
| `pdg.WorkItem` | 172 | 176 | + `geometryAttribValue`, `setGeometryAttrib`, `scriptDir`, `workingDir`; 0 removed |
| `pdg.GraphContext` | 68 | 69 | + `schedulerForTypeName` |
| `pdg.SchedulerType` | 6 | 7 | + `isPrivate` |
| `pdg.PyEventHandler` / `EventHandler` | 4 / 3 | 4 / 3 | unchanged |
| `pdg.EventType` | 53 members | 53 + `name`/`value` | all 53 H21 member values IDENTICAL (`All`=43, `CookComplete`=14, `CookError`=12…); `name`/`value` are pybind enum property accessors, not new event types |

**Phantoms still phantom (all NOT RESOLVABLE, same as H21):** `hou.pdg`, `hou.pdg.scheduler`, `hou.pdg.workItem`, `hou.pdg.GraphContext`, `pdg.PyEventCallback`, `hou.pdgEventType`. Still live: `hou.topNodeTypeCategory`, `TopNode.getPDGGraphContext()`, `cookWorkItems(block=True)`, `gc` live immediately on fresh topnet child.

**Cook-semantics note:** static genericgenerator cook again fired NO `WorkItemStateChange`/`CookedSuccess` — sequence was `SchedulerAdded×3, NodeFirstCook, CookStart, WorkItemAdd, WorkItemAddList, NodeGenerated, NodeCooked, CookComplete` — H21's "static items signal completion via NodeCooked + CookComplete" gotcha holds on H22.

**Verdict for the event bridges:** the R8 / `tops_bridge` raw-callable pattern and the CLAUDE.md PyEventHandler phantom-constructor warning are CONFIRMED valid on 22.0.368 (extend the warning's tag from "H21.0.671 phantom" to include 22.0.368). Trustable on H22, subject to live-bridge reconfirmation when one is up.
