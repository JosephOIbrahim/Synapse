# Spike 3.3 — "First Event Live" dir() Recon

> ```
> ┌────────────────────────────────────────────────────────────────────────┐
> │  STATUS: PRESTAGE — DESIGN-ONLY · ZERO BUILD                            │
> │  Live-confirmed on Houdini 21.0.671 Indie this session.                 │
> │  No production code edited · no node created · no cook triggered here.  │
> │  Build starts at M1. The prestage is M0 (dir() re-confirm + staged      │
> │  experiments designed, not executed).                                   │
> └────────────────────────────────────────────────────────────────────────┘
> ```

**Spike 3.3 exit gate (verbatim):**

> *"A real PDG cook fires at least one workitem.complete event onto the perception queue. Agent loop pulls the event from the queue and acknowledges it (no reasoning required at this gate — just wire continuity)."*

Supplementary (CONTINUATION doc lines 382–385): end-to-end timing from `cookComplete` to agent perception **< 50ms**.

### TL;DR

- **The event model in the scaffold is broken three ways** and all three are documented-not-fixed here (fix lands at M1). The two most dangerous are silent-data bugs found this prestage: **BUG A** — the bridge reads `event.workItem`, a phantom attribute that is **not on the live `pdg.Event` surface**, so every work-item payload field is silently empty at first-event-live; and **BUG B** — the bridge has no path to `workitem.complete` because **there is no `EventType.WorkItemComplete`** member, so the gate event is never even derived. **BUG C** (`pdg.Node.path()` is also phantom; only `.name` exists) is functionally mitigated by a fallback but mis-ordered.
- **The marshalling design and the agent-loop drain both had latent contradictions against the live daemon shape**, now resolved in this artifact: the perception queue's bounded-vs-unbounded story is reconciled (one policy, with three distinct drop reasons kept separable), the asyncio `call_soon_threadsafe` path is demoted to a clearly-labeled FUTURE note because the live daemon is `threading.Queue` + blocking `get()` (no event loop exists), and the agent-loop pull is promoted from a one-line design item to an explicit M2/M4 build item because **the live request loop has no idle yield point to drain a perception queue** (`daemon.py:640-647` blocks on `_request_queue.get(timeout=0.25)`).
- **The <50ms gate is bounded by the daemon's request-poll cadence, not by in-process speed.** `_REQUEST_POLL_INTERVAL_SECONDS = 0.25` (read from `daemon.py:84` this prestage) — a perception event arriving while the daemon is parked in the blocking `get()` waits up to 250ms. The latency budget must be derived from this constant (drain perception on every wake including `queue.Empty` timeouts, and lower the poll interval if 250ms worst-case is unacceptable). It is **not** "sub-ms" until that wiring lands.
- **A live scratch cook was executed this session (operator-authorized, after this doc's first synthesis) and RESOLVED the one unknowable-from-`dir()` crux — see §0.** PDG event handlers fire on a **WORKER thread**, not main. The same run caught **BUG D**: `pdg.PyEventHandler(callback)` has *no constructor* (and subclassing it also fails), so the scaffold's handler factory **hard-crashes on the first `warm()`** — the working registration is a raw callable passed to `addEventHandler` (which returns the wrapper).

---

## Headline findings

> ```
> ┌─ BUG A — event.workItem PHANTOM (HIGH, scaffold) ───────────────────────┐
> │  tops_bridge.py:521  work_item = getattr(event, "workItem", None)        │
> │  "workItem" is NOT on the live pdg.Event surface → always None on a      │
> │  real event → work_item_id / frame / state / outputs / cookDuration /   │
> │  node_path all SILENTLY EMPTY at first-event-live. The bridge emits a    │
> │  hollow event and nothing downstream notices. This is SF-4 (silent      │
> │  failure) embodied. Fix = M1 rewrite against event.workItemId(s) +      │
> │  event.currentState, resolving the WorkItem from the context.           │
> │                                                                          │
> ├─ BUG B — workitem.complete is UNDERIVED (HIGH, scaffold) ───────────────┤
> │  There is NO pdg.EventType.WorkItemComplete member. The bridge never    │
> │  reads event.currentState, so "done" is never detected and the GATE     │
> │  EVENT NEVER FIRES — silently. Fix = derive complete from               │
> │  WorkItemStateChange(5) AND currentState in {CookedSuccess(5),          │
> │  CookedCache(6)}. Mind the value-collision: EventType.WorkItemStateChange│
> │  == 5 and workItemState.CookedSuccess == 5 are DIFFERENT enums.         │
> │                                                                          │
> ├─ BUG C — pdg.Node.path() PHANTOM (LOW, scaffold, mitigated) ────────────┤
> │  pdg.Node exposes .name (PROPERTY, not callable); it has NO .path().    │
> │  _read_node_path (tops_bridge.py:565-590) tries .path() first; the      │
> │  attempt raises and the .name fallback catches it — functionally        │
> │  mitigated, but the canonical accessor is mis-ordered. Pin .name first. │
> └──────────────────────────────────────────────────────────────────────────┘
> ```

All three are **documented, not fixed** in this prestage. Build (and the fixes) begin at M1. **A fourth — BUG D, a hard crash (not a silent bug) — was caught by the live experiment executed after this doc's first synthesis; see §0.**

---

## 0. Live experiment results — thread-of-delivery RESOLVED + BUG D (executed this session)

> ```
> ┌────────────────────────────────────────────────────────────────────────┐
> │  A real scratch cook WAS executed this session, with explicit operator  │
> │  authorization, AFTER this doc's first synthesis — to resolve the one   │
> │  crux that dir() cannot answer. Scratch topnet + genericgenerator,      │
> │  handler registered, cooked, DESTROYED after (zero residue, verified).  │
> │  This section is AUTHORITATIVE: where it conflicts with a STAGED/OPEN    │
> │  claim below (esp. §1.1, §2.5A, §3, §4.2, §4.4, checklist #5), THIS      │
> │  section — measured on live events — wins.                              │
> └────────────────────────────────────────────────────────────────────────┘
> ```

### 0.1 Resolved-live (upgrades from STAGED/OPEN)

| # | Question (was OPEN/STAGED) | Answer (measured on live events) | Supersedes |
|---|---|---|---|
| 1 | Thread-of-delivery: main vs worker? | **WORKER thread.** Every one of 19 events fired on a non-main `Dummy-N` thread (`is_main=False`) while the main thread blocked in `cookWorkItems(block=True)`. Confirms Branch 2; the exact opposite of hipFile (main). The design holds unchanged — handler stays `pdg.*`-only + wrapped non-blocking enqueue — but the worker-thread answer makes that thread-safety **mandatory, not precautionary**. | §4.2, §4.4, checklist #5 |
| 2 | Handler registration API | **`wrapper = gc.addEventHandler(raw_callable, pdg.EventType.X)`** — pass a PLAIN function; it RETURNS a `pdg.PyEventHandler`. `pdg.EventType.All` registers every type in one call. `gc` is live immediately on a fresh topnet child (no generate/cook needed first). | §1.1, §5 hop-1 |
| 3 | Handler removal API (the §2.5A leak) | **`gc.removeEventHandler(wrapper)`** with the RETURNED wrapper (NOT the callable — `removeEventHandler` wants a `PYPDG_EventHandler`; passing the raw fn raises). Verified: handler count 2→1. **Register-ONCE-on-`All` + remove-the-wrapper sidesteps the 7-type-loop leak entirely** — the recommended M1 shape. (The gc also carries Houdini's own handler — never `removeAllEventHandlers` blindly.) | §2.5A |
| 4 | `event` shape on REAL events (not just dir) | `has_workItem_attr=False` on **every** live event (BUG A confirmed on real data); `event.node.name='gen'` works, cook-level events `node=None` (BUG C); `event.workItemId` = 1/2/3 for items, `-1` for cook-level. | §1.2 (confirms) |

### 0.2 BUG D (CRITICAL, scaffold) — handler construction hard-crashes

`tops_bridge.py:484` does `return pdg.PyEventHandler(on_pdg_event)`. **Live: `pdg.PyEventHandler(fn)` raises `TypeError: _pdg.PyEventHandler: No constructor defined!`** — and `class H(pdg.PyEventHandler): def handleEvent(self, e): ...; H()` raises the **same**. So `_make_event_handler` throws on the **first `warm()` call**: unlike A/B (silent), this registers **zero** events and aborts subscription. **Fix (M1):** register the raw callable directly — `wrapper = gc.addEventHandler(self._on_pdg_event, pdg.EventType.All)` — store `wrapper` in the `Subscription`, and `gc.removeEventHandler(wrapper)` in `cool()`. **Cross-cutting flag (out of 3.3 scope, but file it):** the R8 `CookHandler(pdg.PyEventHandler)` subclass in `shared/bridge.py` (CLAUDE.md §1.7) uses the same construction pattern and is **suspect** — it likely never instantiated live; verify separately.

### 0.3 Static-item "complete" nuance (refines BUG B / §3)

The scratch cook used a **static `genericgenerator`** and fired **NO `WorkItemStateChange` and NO `CookedSuccess`**. Full captured sequence (EVT.All, 3 items): `NodeCreate, SchedulerAdded×3, NodeFirstCook, CookStart, WorkItemAdd×3 (wid 1/2/3), WorkItemAddList, NodeGenerated, NodeCooked, CookComplete, WorkItemRemove×3 (currentState=Dirty), WorkItemRemoveList, NodeRemove, SchedulerRemoved`. So §3's derivation (`WorkItemStateChange` + `currentState==CookedSuccess`) fires **only for items processed by a real cooking node** — **the M4/M5 gate demo MUST use a real processor** (`ropfetch`/`pythonscript` over N frames), not a static generator, or the derived `workitem.complete` never fires. Node-level completion is signalled by `NodeCooked`/`CookComplete`; per-item completion by `WorkItemStateChange→CookedSuccess` only under a real processor.

### 0.4 Still genuinely STAGED (need the gate cook with a real processor)

The `currentState==CookedSuccess` value at a real success transition (checklist #6); `cookDuration` unit (#8); per-frame complete in the 5-frame demo (M5); the <50ms latency-vs-poll measurement (§5.2); daemon instantiation + drain (M2/M3). The `pdg.WorkItem` class surface + the id→WorkItem resolver (M0 #2/#3) remain `dir()`-probeable-now and were deliberately **not** run (still M0, no cook).

---

## 1. PDG event recon — what's confirmed vs what to live-check

Every `pdg.*` surface the in-process `TopsEventBridge` wiring leans on, scored against THIS session's `dir()` probe (Houdini 21.0.671 Indie).

- **CONFIRMED-live** = introspected on a real instance/enum/class this session.
- **STAGED-live-check** = exists, but its *runtime value/behavior* only resolves under a real cook (the Spike 3.3 gate).
- **DESIGN** = a wiring decision, not an API fact.

### 1.1 Recon checklist

| Item | Status | Evidence / How |
|---|---|---|
| `pdg.Event` is the event object (no `hou.pdgEventType`, no `pdg.PyEventCallback`) | CONFIRMED-live | Standalone `pdg` is authoritative; instance surface probed this session (§1.2). |
| `event.type` (raw `pdg.EventType` int) | CONFIRMED-live | In probed surface. Bridge re-filters on this for defense-in-depth. |
| `event.currentState` (`pdg.workItemState` post-transition) | CONFIRMED-live | In surface. **The field BUG B depends on** — bridge does not read it today. |
| `event.lastState` (prior `pdg.workItemState`) | CONFIRMED-live | In surface. Lets the bridge see the *transition*, not just the landing state. |
| `event.workItemId` → `int` | CONFIRMED-live | In surface. Real id accessor for a single-item event. |
| `event.workItemIds` → `list` | CONFIRMED-live | In surface. Batch/multi-item events. |
| `event.node` → `pdg.Node` | CONFIRMED-live | In surface. Source TOP node for the event. |
| `event.message` → `str` | CONFIRMED-live | In surface. Carries cook error/warning text. |
| `event.context` → `pdg.GraphContext` | CONFIRMED-live | In surface. |
| `event.dependencyId` | CONFIRMED-live | In surface. Not used by the gate path. |
| `pdg.Node.name` (property, **not** callable) | CONFIRMED-live | `Node_path_like=['name']`; **no `.path()` method exists**. Pin canonical id = `.name`. |
| `pdg.EventType.{CookStart=38, CookComplete=14, CookError=12, CookWarning=13, WorkItemAdd=1, WorkItemStateChange=5, WorkItemResult=35}` | CONFIRMED-live | Re-confirmed this session, zero drift from 2026-04-26 audit. The 7 surfaced types. |
| `pdg.workItemState.{CookedSuccess=5, CookedCache=6, CookedFail=7, CookedCancel=8, … Dirty=9}` enum | CONFIRMED-live | Full enum probed (`Undefined=0…Dirty=9`). The "done" terminal states are 5 and 6. |
| `pdg.GraphContext.{addEventHandler, removeEventHandler, removeAllEventHandlers, eventHandlers, hasEventHandler, supportedEventTypes, waitAllEvents}` | CONFIRMED-live | Method set probed this session. `addEventHandler(handler, type)` per surfaced type (R8 pattern). **Note: NO `workItemById` / id→WorkItem resolver in this list** — see §1.5 and the M0 resolver probe. |
| `top_node.getPDGGraphContext()` (acquire artist's live context) | CONFIRMED-live (prior audit) | R8 precedent; the warm() path. Distinct from `pdg.GraphContext()` (fresh headless graph). |
| ~~`pdg.PyEventHandler(callback)` construction~~ | **PHANTOM-construction — BUG D (§0)** | **Live: `pdg.PyEventHandler(fn)` raises `TypeError: No constructor defined`; subclassing fails identically.** Scaffold's `tops_bridge.py:484` THROWS on first `warm()`. Correct API: `wrapper = gc.addEventHandler(raw_callable, EventType.All)` (returns the wrapper); detach via `removeEventHandler(wrapper)`. |
| `pdg.Scheduler.runOnMainThread(wait, fn, …)` | CONFIRMED-live but **REJECTED** | Marshals a function *onto* main (blocks with `wait=True`). We want the **opposite** — non-blocking enqueue to the daemon loop. Noted-and-rejected, not used. |
| **`event.workItem`** | **PHANTOM — do not reference** | **NOT in the probed surface. `getattr(event,"workItem",None)` always returns `None` on a live event (BUG A).** |
| `"workitem.complete"` as a `pdg.EventType` | **PHANTOM — derive instead** | No `WorkItemComplete` member exists. Derive from `WorkItemStateChange(5)` + `currentState in {CookedSuccess(5), CookedCache(6)}` (BUG B). |
| `pdg.WorkItem` attribute surface (`.frame` / outputs / `.cookDuration` / `.id` / `.state` / `.node`) | **STAGED → resolve to CONFIRMED-live (surface) at M0** | The scaffold currently guesses these names off the phantom `event.workItem`. The real `pdg.WorkItem` **class** is `dir()`-probeable NOW (M0, no cook). Only the **values** need a cook. See M0 probe (b). |
| `workItemId(int)` → `WorkItem` **resolver method** | **STAGED → resolve to CONFIRMED-live (surface) at M0** | The probed `GraphContext` method list has **no** `workItemById`. The resolver is currently an **unidentified guess**. `dir()`-probe `event.node` / context for `workItemById` / `workItems` at M0 before relying on it. See §1.5. |
| Callback thread (main vs cook/scheduler worker) during a real cook | STAGED-live-check | Spike 2.4 deadlock crux. Not introspectable from `dir()` — needs a live cook. STAGE only (do-not-run). |
| `event.currentState` / `lastState` *value* during a real `CookedSuccess` transition | STAGED-live-check | Enum exists; the actual value-at-fire only resolves under cook. The Spike 3.3 gate event. |
| `cookDuration` numeric unit (s vs ms) | STAGED-live-check | Not value-introspectable; one print during a controlled ~1s cook resolves it. Resolver method itself must be M0-probed (§1.5). |
| Perception callback supplier + perception queue + agent-loop drain | DESIGN (build, M2/M4) | Daemon only EXPORTS the bridges today (`host/__init__.py`); does not instantiate them. Spike 3.3 wiring. |

### 1.2 Corrected `pdg.Event` model (replaces the phantom)

The live instance surface is exactly:

```
['context', 'currentState', 'dependencyId', 'lastState',
 'message', 'node', 'type', 'workItemId', 'workItemIds']
```

Read map for the bridge rewrite (`_build_tops_event` against the REAL surface — **design only, do not build here**):

| TopsEvent field | Read from (real) | NOT (phantom) |
|---|---|---|
| `pdg_event_type_int` | `event.type` | — |
| `top_node_path` / `node_path` | `event.node.name` (property) | ~~`event.node.path()`~~, ~~`event.workItem.node.path()`~~ |
| `work_item_id` | `event.workItemId` (int) — **or iterate `event.workItemIds`** (batch, §1.4) | ~~`event.workItem.id`~~ |
| work-item done? | `event.type == WorkItemStateChange(5)` **and** `event.currentState in {CookedSuccess(5), CookedCache(6)}` | ~~`EventType.WorkItemComplete`~~ |
| `error_message` | `event.message` | — |

Frame / outputs / `cookDuration` are **not** carried on the event. They must be re-sourced from the `pdg.WorkItem` resolved via `event.workItemId` against the context — and **both the WorkItem attribute names AND the resolver method are M0 dir()-probes**, not gate-cook items (§1.5). Only the *values* are STAGED-live-check.

> **Value-collision warning (do not conflate):** `EventType.WorkItemStateChange == 5` AND `workItemState.CookedSuccess == 5` share the integer `5` across two *different* enums. The "5" you match on `event.type` is an `EventType`; the "5" you match on `event.currentState` is a `workItemState`. **Match the field, never the bare int.** Conflating them is the single most likely first-event-live regression.

### 1.3 The three scaffold bugs (documented, fix = M1)

**BUG A — `event.workItem` phantom (HIGH).**
- *Where:* `tops_bridge.py:521` — `work_item = getattr(event, "workItem", None)`.
- *Symptom:* `"workItem"` is not in the live `pdg.Event` surface, so this is **always `None`** on a real event. Line 522's `if work_item is None:` short-circuits → every work-item payload field (`work_item_id`, `work_item_frame`, `work_item_state`, `work_item_outputs`, `cookDuration`, `node_path`) is **silently empty at first-event-live** (SF-4). The bridge emits a hollow event and nothing downstream notices.
- *Fix (M1, NOT here):* rewrite `_build_tops_event` against `event.workItemId` / `event.workItemIds` + `event.currentState`, resolving the `pdg.WorkItem` from the context. **Critical:** the M1 rewrite must code against **M0-probed real `pdg.WorkItem` attribute names** (`_read_outputs`/`_safe_float_attr` at `tops_bridge.py:535-540,551` currently reach for `.frame` / `.expectedResultData` / `.cookDuration` — guessed off the phantom; verify which survive on the real class before M1 rewrites against them, else BUG A's fix re-introduces a fresh SF-4 on guessed WorkItem attrs).

**BUG B — `workitem.complete` is underived (HIGH).** See §3 for the full derivation. There is no `EventType.WorkItemComplete`; the bridge never reads `event.currentState`, so the gate event is never fired. Fix = M1.

**BUG C — `pdg.Node.name`, not `.path()` (LOW, mitigated).**
- *Where:* `_read_node_path` at `tops_bridge.py:565-590` tries `getattr(node, "path", …)` / `.path()` first; `warm()` at `:265` calls `top_node.path()` — but that is a **`hou` node** (which *does* have `.path()` — fine). The bug is only on the **`pdg.Node`** path.
- *Symptom:* `pdg.Node` exposes `.name` (property) and has **no `.path()`** — the `.path()` attempt raises, the fallback catches it. Functionally mitigated, but the canonical accessor is mis-ordered.
- *Pin:* canonical `pdg.Node` id = `.name` (property access, **not** a call). The current fallback at `:584-587` reads `name_attr() if callable(name_attr) else name_attr` — it handles both property and method. The M1 rewrite should reorder to `.name` first AND the M4 staged probe must **empirically confirm `.name` is non-callable** (see §1.6 snippet 5 — this closes the loop on the property pin rather than asserting it).

### 1.4 Batch work items — `event.workItemIds` (the batch failure class)

A batched mapper/partitioner fires **one** `WorkItemStateChange` carrying `workItemIds=[many]` with `workItemId` possibly `0`/unset. The single-item predicate in §3 keys off `event.workItemId` (singular) and would either emit one hollow complete with an ambiguous id, or be miscounted as a single frame in the 5-frame demo.

- **`isBatch` is NOT in the confirmed `pdg.Event` surface** — the *only* discriminator available is `len(event.workItemIds)`.
- **M1 batch rule (DESIGN — decide explicitly):** *if `event.workItemIds` is non-empty, the event represents a batch → emit one `workitem.complete` per id in `workItemIds`* (or one aggregate carrying an `ids` list — your choice, but **DECIDE** and pin it). The §3 predicate and §4 acceptance must reflect the chosen count.
- **M1 STANDALONE acceptance:** synthetic `WorkItemStateChange` with `workItemIds=[a,b,c]` + `currentState=CookedSuccess` yields the chosen count deterministically.
- **M4/M5 STAGED live-check:** cook a graph with a batched/partitioned TOP and dir()-probe a live batch event to confirm whether `currentState` / `workItemId` are meaningful when `workItemIds` is populated (the prestage probe used a single-item assumption). **OR** explicitly park batch as an out-of-scope coverage edge for the gate, documented alongside the AfterMerge gap (§2.3).

### 1.5 The id→WorkItem resolver is itself unprobed (gate-critical for enrichment)

The draft asserts frame/outputs/cookDuration are "re-sourced from the `pdg.WorkItem` resolved via `event.workItemId` against the context" — but the dir()-confirmed `GraphContext` surface (`addEventHandler / removeEventHandler / removeAllEventHandlers / eventHandlers / hasEventHandler / supportedEventTypes / waitAllEvents`) contains **NO `workItemById` or graph-lookup-by-id method**. The resolution path is an **unsubstantiated guess**. So the cookDuration/frame/outputs STAGED-live-checks are **not runnable as written** — there is currently no confirmed API to get from an `int` id to a `WorkItem` object.

- **M0 resolver probe (no cook, hard acceptance):** dir()-probe candidates `event.node.workItemById` / `event.node.workItems` / `event.context.graph().workItemById` (all UNVERIFIED — must be dir-confirmed at M0). **Acceptance:** *dir() shows a confirmed int-id → WorkItem accessor; else `outputs` / `frame` / `cookDuration` are DROPPED from M5 scope* — which changes M5's narration ("two outputs at /render/v001") from stretch to **possibly-impossible**, and that must be stated honestly, not glossed.
- Reclassify the WorkItem **attribute surface** and the **resolver method** from STAGED-live-check to **CONFIRMED-live (surface)** once probed at M0; only the *values* stay STAGED for the cook.

### 1.6 Read-only `dir()` probe snippets (STAGE — do not run in prestage)

These are non-mutating introspections. Thread + value probes only resolve under a real cook (the gate); they are staged inside the bridge callback, never executed in the prestage. The **WorkItem-class and resolver probes (7,8) are M0 — runnable NOW, no cook.**

```python
# STAGED at M4 — drop inside the PyEventHandler callback during the live gate cook.
# Read-only: prints only, zero mutation, no node/cook creation.

# (1) Thread identity at fire — the Spike 2.4 deadlock crux.
import threading
print("[3.3-probe] thread_is_main=",
      threading.current_thread() is threading.main_thread(),
      "name=", threading.current_thread().name)

# (2) Re-confirm the live event surface matches the prestage probe.
print("[3.3-probe] event.dir=", [a for a in dir(event) if not a.startswith("_")])

# (3) The derived-complete gate (BUG B): EventType + workItemState by FIELD.
import pdg
print("[3.3-probe] type=", int(event.type),
      "is_state_change=", event.type == pdg.EventType.WorkItemStateChange,  # ==5
      "currentState=", int(event.currentState),
      "is_done=", event.currentState in (pdg.workItemState.CookedSuccess,    # 5
                                         pdg.workItemState.CookedCache))      # 6

# (4) Real id accessors (replacing the workItem phantom) + batch discriminator.
print("[3.3-probe] workItemId=", event.workItemId,
      "workItemIds=", list(event.workItemIds),
      "is_batch=", len(list(event.workItemIds)) > 0)

# (5) Canonical node id = .name PROPERTY (NOT callable, NOT .path()).
n = event.node
print("[3.3-probe] node.name=", getattr(n, "name", None),
      "has_path_method=", callable(getattr(n, "path", None)),   # expect False
      "name_is_callable=", callable(getattr(n, "name", None)))  # expect False — pins BUG C

# (6) cookDuration unit sanity — resolve WorkItem from context (resolver from M0 probe 8).
#     Expected ~1.0 if seconds during a controlled 1s cook; ~1000 if ms.
print("[3.3-probe-cookDuration] resolve via the M0-confirmed id->WorkItem resolver "
      "during gate cook — value not introspectable pre-cook")

# ── M0 (NO COOK) — runnable in the prestage-adjacent recon, statically resolvable now ──

# (7) M0: real pdg.WorkItem CLASS attribute surface — confirm the accessor NAMES
#     the M1 rewrite will code against (the scaffold guessed .frame/.expectedResultData/
#     .cookDuration/.id/.state/.node off the phantom event.workItem). Class-level dir,
#     no instance, no cook.
import pdg
print("[3.3-M0] WorkItem.dir=", [a for a in dir(pdg.WorkItem) if not a.startswith("_")])

# (8) M0: the int-id -> WorkItem RESOLVER. The GraphContext method list has NONE.
#     Probe the candidate carriers; acceptance = at least one resolver is confirmed,
#     else outputs/frame/cookDuration drop from M5 scope.
print("[3.3-M0] GraphContext.dir=", [a for a in dir(pdg.GraphContext) if not a.startswith("_")])
print("[3.3-M0] Node.dir=", [a for a in dir(pdg.Node) if not a.startswith("_")])
# candidates to confirm: node.workItemById / node.workItems / context.graph().workItemById
```

> **Gate reminder:** the spike passes when a real cook fires ≥1 *derived* `workitem.complete` (a `WorkItemStateChange` with `currentState` in {CookedSuccess, CookedCache}) onto the perception queue and the agent loop pulls + acknowledges it. The thread-identity probe (1) is the load-bearing unknown — everything else here is CONFIRMED-live (or M0-resolvable) and only needs value confirmation.

---

## 2. Scene-load recon — integration confirmation

The hipFile side is already Mile-4-audited. This section pins what is CONFIRMED-live at the scene-load boundary versus the STAGED-live-check items the Spike 3.3 cook gate still has to prove, then surfaces the **DESIGN** decisions (AfterMerge gap, handler-leak, double-warm) that must be made/checked before the build pass.

### 2.1 Mile-4-audited — CONFIRMED-live (do not re-prove)

| Item | Status | Evidence / How |
|---|---|---|
| hipFile callbacks fire on MAIN thread | CONFIRMED-live | Mile-4 audit captured `is_main_thread=True` (thread_id 35700) for all hipFile events → no `hdefereval` marshal in the AfterLoad handler; main→main dispatch would be cargo-cult. **Scope note:** the audit traced the **AfterLoad** sequence specifically — see §2.4 (AfterMerge main-thread is asserted, not proven). |
| File→Open event sequence | CONFIRMED-live | Audit observed `BeforeLoad → BeforeClear → AfterClear → AfterLoad` (AfterClear 13:02:23 → AfterLoad 13:02:25). |
| `hou.hipFileEventType` member set | CONFIRMED-live | `dir()` this session: `AfterClear, AfterLoad, AfterMerge, AfterSave, BeforeClear, BeforeLoad, BeforeMerge, BeforeSave`. |
| Filter on `AfterLoad` only is correct | CONFIRMED-live | `AfterClear` fires mid-load against empty state — warming there would warm zero topnets; `AfterLoad` is the only post-populated trigger. |
| `addEventCallback` returns `None`, no dedup | CONFIRMED-live | Audit §1.2 / §4.1: returns `None`; double-add registers twice FIFO → cleanup is callback-identity based + explicit `_subscribed: bool` guard (`scene_load_bridge.py:137`) for idempotency. |
| `warm_all()` scene-walk shape | CONFIRMED-live (API) | `hou.node('/').allSubChildren()` filtered by `hou.topNodeTypeCategory()` (`tops_bridge.py:346-348`) — all four surfaces RESOLVED in Spike 3.0 audit. |

### 2.2 Spike 3.3 integration live-checks — STAGED (do-not-run in prestage)

Wire-continuity claims that only a real graphical File→Open + cook can confirm. STAGE the assertions; the build pass executes them.

| Item | Status | How to confirm (Spike 3.3, staged) |
|---|---|---|
| Real File→Open fires the registered `AfterLoad` callback | STAGED-live-check | Joe-at-GUI opens a `.hip` with ≥1 topnet; assert the bound-method callback is invoked exactly once on main thread (mock fired it; live never has). |
| AfterLoad handler runs `cool_all() → warm_all()` on the live event | STAGED-live-check | Instrument `reload_count()` → expect +1 per AfterLoad; expect 0 increments for the preceding AfterClear. |
| `warm_all()` discovers LIVE topnets on a real scene | STAGED-live-check | After open, assert `active_subscriptions()` length == number of topnets actually in the scene (mock used FakePDG; live `getPDGGraphContext()` must return a real context per topnet). |
| `getPDGGraphContext()` returns a usable live context (not a fresh headless graph) | STAGED-live-check | Per-topnet `top_node.getPDGGraphContext()` must be the artist's live context; confirm `addEventHandler` lands on the cooked graph. |
| Idempotency under repeated real loads | STAGED-live-check | Open → open again → assert subscription count stays == topnet count (3× AfterLoad on 2-topnet → exactly 2 subs). **NOTE:** this exercises the SceneLoadBridge cool-first path; it does NOT test `warm()` called twice without an intervening cool — see §2.6. |
| End-to-end auto-warm with no menu action | STAGED-live-check | Daemon-side `SceneLoadBridge.subscribe()` wired at boot; opening the scene auto-warms with zero artist action. |
| Teardown leaves no callback / subscription residue | STAGED-live-check | `unsubscribe()` → assert hipFile callback list empty AND `active_subscriptions() == ()` AND `is_subscribed() == False`. **NOTE:** this stages the `daemon.stop()` path only — NOT the mid-load cool-on-dead-context path, which is the more dangerous one (§2.5). |

> **Wiring dependency:** §2.2 is only reachable once the daemon actually instantiates `SceneLoadBridge` and calls `subscribe()` at boot + `unsubscribe()` in `stop()`. Today `host/__init__.py` **only EXPORTS** the bridges — instantiation is Spike 3.3 wiring (M3), not done.

### 2.3 The AfterMerge gap — DESIGN decision (recommend: defer)

`hou.hipFileEventType` confirms an **`AfterMerge`** member that SceneLoadBridge does **not** subscribe (it filters `AfterLoad` only). File→Merge lands new topnets into the live session, but no AfterLoad fires for a merge — so **topnets brought in via Merge are silently never auto-warmed**. The agent's perception channel is blind to any PDG cook in a merged-in topnet.

| Aspect | Status | Detail |
|---|---|---|
| `AfterMerge` exists and is unsubscribed | CONFIRMED-live | `dir(hou.hipFileEventType)` includes `AfterMerge`; handler filters `AfterLoad` only. |
| Merge-introduced topnets are not warmed | DESIGN | No AfterLoad on merge → `warm_all()` never re-runs → merged topnet has no PDG subscription → its cooks never reach the perception queue. |

**Decision options (pick ONE for the build pass):**

| Option | Behavior | Trade-off |
|---|---|---|
| **(1) Subscribe `AfterMerge` → same `cool_all() → warm_all()`** | Merge re-warms the whole scene like a load. | Simplest, reuses the proven AfterLoad path; cost is a full scene re-walk on every merge (large-scene perf risk). **PRECONDITION:** if picked, the AfterMerge handler MUST assert main-thread identity before any `hou.*` call (§2.4). |
| **(2) AfterMerge → incremental warm of new topnets only** | Diff topnet set, warm only the delta. | No redundant re-walk; cost is new delta-tracking state the bridge does not have today. Same main-thread precondition as (1). |
| **(3) Defer — `AfterMerge` stays unsubscribed (documented gap)** | Merge-introduced topnets require manual re-warm or save+reopen. | Zero new code, keeps Spike 3.3 tight on the File→Open gate; cost is a real perception blind spot that MUST be in the risk register, not implicit. |

**Recommendation: (3) defer with documented gap** — keeps the gate narrow (File→Open + one cook). Park (1) as the cheap follow-up. **BUT** the gap's two underlying claims are currently *asserted, not observed*, and one cheap M4 live-check converts them to fact:

> **M4 STAGED live-check (Joe-at-GUI, piggyback on the gate session):** File→Merge a `.hip` containing a topnet. (a) Record the actual hipFile event sequence — expected `BeforeMerge → … → AfterMerge` (the "AfterMerge also emits BeforeMerge ahead of it, so a future subscription has a clean filter point" claim is currently an **unverified ordering assertion** — the Mile-4 audit captured File→Open, not File→Merge). (b) Assert `reload_count()` does **NOT** increment — proving merged topnets are truly un-warmed, i.e. the blind spot is real and bounded. This converts the asserted gap into an observed fact before it gets cited as a design premise for Spike 3.5. Add the blind spot to the risk register with the **observed** sequence attached, not the inferred one.

> **Rejected naive path:** do **not** subscribe `BeforeMerge` / `BeforeClear` / `AfterClear` as warm triggers. They fire against pre-merge or empty state and would warm a stale/zero topnet set — the same failure mode the `AfterLoad`-only filter already guards against.

### 2.4 AfterMerge main-thread assumption — assert, don't inherit

The reused warm path (`warm_all()` → `hou.node('/').allSubChildren()`, `hou.topNodeTypeCategory()`, `node.getPDGGraphContext()` — all `hou.*` / cook-touching) is only thread-safe if AfterMerge fires on the **main** thread. The Mile-4 audit confirmed AfterLoad on main, but **AfterMerge on main is asserted, not proven** — both are hipFile events, but that is not a guarantee.

> **FIX (precondition on options 1/2):** if `AfterMerge` is ever subscribed, add a one-line thread-identity assert in the AfterMerge handler (the same `threading.current_thread() is threading.main_thread()` check staged for the PDG handler) **before any `hou.*` call** — do not assume AfterMerge inherits AfterLoad's main-thread guarantee. Note it as a precondition in the risk-register line. Keeping the recommendation at option (3) for Spike 3.3 makes this **non-blocking** for the gate.

### 2.5 Handler-leak failure classes (two HIGH live-checks the draft omitted)

These are the reviewer's explicit failure classes. Both are **build-relevant findings that belong in the M1/M3 fix list**, not just the prestage register.

**(A) `removeEventHandler` removal-arity is UNVERIFIED on the live API.**
The bridge registers the **same** handler instance against all 7 surfaced event types in a loop (`tops_bridge.py:291-294`: `for event_type_int in sorted(...): graph_context.addEventHandler(handler, event_type_enum)`), but `cool()` calls `graph_context.removeEventHandler(handler)` exactly **ONCE** (`tops_bridge.py:378-380`). The TERMINATION property's "removable with no leak" is GREEN in unit tests **only because** `FakeGraphContext.removeEventHandler` (`test_tops_bridge.py:115-119`) models *whole-handler* removal (strips every `(h,et)` tuple). **If the live `pdg` API removes per-`(handler,type)` registration, `cool()` leaks 6 of 7 registrations per topnet**, and on scene clear those leaked handlers point at a destroyed graph context.

> **STAGED live-check at M4 (piggyback on the gate cook, before destroying the scratch topnet):** after one `warm()` registers the handler against all 7 types, call `gc.eventHandlers()` (dir-confirmed accessor) to count registrations → `cool()` once → call `gc.eventHandlers()` again. **ACCEPTANCE: post-cool count == 0.** If the live API removes per-type, the count is nonzero and `cool()` MUST loop `removeEventHandler` once per registered type (or call `removeAllEventHandlers(handler)` if it accepts a handler arg). Add to the M1/M3 fix list.

**(B) Handler-leak on SCENE CLEAR (graph context destroyed while still subscribed) is ASSUMED-SAFE, not STAGED.**
`SceneLoadBridge._on_after_load` (`scene_load_bridge.py:214-237`) calls `tops_bridge.cool_all()` **after** AfterLoad fires — but by then `BeforeClear → AfterClear` already destroyed the PRIOR scene's graph contexts (the bridge's own comment at `:215-218` acknowledges this). `cool()` at that point calls `removeEventHandler` on a graph_context whose underlying C++ object **may be dead**. The code swallows the exception (`tops_bridge.py:381-386`) so it "works" — but it is never staged that a real File→Open with a previously-warmed topnet does not crash/segfault/hang when `cool_all()` touches the dead context. The teardown row in §2.2 only stages the `daemon.stop()` path, NOT this mid-load cool-stale-on-dead-context path — the more dangerous one (dead pointer, not just residue).

> **STAGED live-check (Joe-at-GUI, M3/M4):** warm topnet in scene A → File→Open scene B → assert (i) process survives, no crash, (ii) the AfterLoad-driven `cool_all()` either succeeds or swallows cleanly, (iii) `active_subscriptions() == ()` afterward, zero stale subs, no orphaned handler fires from a dead context. **Document the live behavior of `removeEventHandler`-on-destroyed-context: does it raise a catchable Python exception, or crash the interpreter?** If it can crash rather than raise, `cool()` MUST guard with a liveness check (`hasEventHandler` — dir-confirmed, currently unused) BEFORE `removeEventHandler`.

### 2.6 `warm()` is NOT idempotent — double-registration (MEDIUM)

The double-registration dedup is covered for `SceneLoadBridge` (`_subscribed` guard + `cool_all → warm_all` per AfterLoad) but **NOT for `TopsEventBridge.warm()` itself**. `warm()` has no dedup guard: calling it twice on the same topnet (a future code path, or `warm_all()` running while a manual `warm()` already subscribed that topnet) **unconditionally appends a second Subscription** (`tops_bridge.py:307-316`) and registers the handler twice per type. `pdg.GraphContext.addEventHandler` dedup semantics are dir-confirmed to *exist as a method* but are **unprobed**. Result: double events for one cook → the 5-frame demo could show 10 acks, or the ack counter double-counts. The §2.2 idempotency row tests the SceneLoadBridge path (which cools first); it never tests `warm()` twice without an intervening cool.

> **FIX — DESIGN decision + STANDALONE test:** either (a) `warm()` checks `active_subscriptions()` for an existing sub on the same `top_node_path` and returns it (dedup), OR (b) document that `warm()` is intentionally **not** idempotent and SceneLoadBridge's cool-all-first contract is the ONLY safe caller. **STAGED live-check:** use `hasEventHandler` (dir-confirmed) to probe whether `addEventHandler(handler, type)` called twice with the same handler+type fires the callback once or twice on a real cook (assert-then-skip). **ACCEPTANCE: one cook → exactly one `workitem.complete` per work item regardless of accidental double-warm.**

---

## 3. The `workitem.complete` semantic (BUG B fix-design)

There is **no `pdg.EventType.WorkItemComplete`** on the live surface. The confirmed `pdg.EventType` members are `WorkItemAdd=1, WorkItemStateChange=5, CookError=12, CookWarning=13, CookComplete=14, WorkItemResult=35, CookStart=38`. "Completion" is therefore **derived**, not subscribed: it is a `WorkItemStateChange(5)` event whose `event.currentState` lands in the terminal-success set. The bridge today never reads `event.currentState` — that is the gate-blocking gap.

| Derivation rule | Live evidence |
|---|---|
| Subscribe to `WorkItemStateChange` (`EventType` value **5**) | `pdg.EventType.WorkItemStateChange==5`, already in `_SURFACED_EVENT_TYPES` (`tops_bridge.py:88,100`). |
| Read `event.currentState` (a `pdg.workItemState`), **not** `event.type` | `pdg.Event` surface includes `currentState`, `lastState` (dir-confirmed); bridge reads neither today. |
| `complete := currentState in {CookedSuccess(5), CookedCache(6)}` | `pdg.workItemState.CookedSuccess==5`, `CookedCache==6`. |
| Terminal-but-NOT-complete: `CookedFail(7)`, `CookedCancel(8)` → route to error/cancel, never emit `workitem.complete` | `pdg.workItemState.CookedFail==7`, `CookedCancel==8`. |
| In-flight (drop for completion): `Uncooked(1) Waiting(2) Scheduled(3) Cooking(4) Dirty(9)` | enum values dir-confirmed. |

**Completion predicate (design pseudocode, not for build) — single-item path; batch per §1.4:**

```
is_complete(event):
    if int(event.type) != EventType.WorkItemStateChange:   # must be a state-change
        return False
    cs = event.currentState                                 # pdg.workItemState
    return cs in (workItemState.CookedSuccess, workItemState.CookedCache)
    # COMMENT IN BUILD: do NOT write int(event.type) == 5 against a state —
    # EventType.WorkItemStateChange(5) and workItemState.CookedSuccess(5) are
    # different enums sharing the integer 5. Match the field.
```

`tops.workitem.complete` is **synthesized inside the handler** from a `WorkItemStateChange` event — not a new subscription. `tops.workitem.state_change` may still surface for non-terminal transitions if the consumer wants them; the gate only requires the derived complete.

> **Live caveat (§0.3):** a **static** generator cook fires NO `WorkItemStateChange`/`CookedSuccess` at all (completion is `NodeCooked`/`CookComplete` only). This derivation therefore fires **only for items processed by a real cooking node** — the M4/M5 gate demo MUST use a real processor (`ropfetch`/`pythonscript`), not a static `genericgenerator`, or no derived `workitem.complete` ever fires.

**Payload re-sourcing map (BUG A — design only):**

| TopsEvent field | Old (phantom) source | Confirmed live source (design) | Status |
|---|---|---|---|
| `work_item_id` | `event.workItem.id` | `event.workItemId` (int) | DESIGN |
| `work_item_state` | `event.workItem.state` | `event.currentState` (`pdg.workItemState`) | DESIGN |
| (completion gate) | — | `currentState in {CookedSuccess, CookedCache}` | DESIGN |
| `node_path` | `event.workItem.node.path()` | `event.node.name` (property — `pdg.Node` has **no** `.path()`) | CONFIRMED-live (accessor) |
| `error_message` | `event.workItem.*` | `event.message` | CONFIRMED-live |
| `work_item_frame` / `_outputs` / `_cook_duration_seconds` | `event.workItem.frame` / `.expectedResultData` / `.cookDuration` | **not on `pdg.Event`** — resolve the `pdg.WorkItem` from `event.workItemId` via the **M0-confirmed resolver** (§1.5); attribute names **M0-confirmed** (§1.3) | STAGED-live-check (value); surface = CONFIRMED-live after M0 |

**Gate-critical fields** (`id`, `currentState`, `node.name`, derived-complete) are fully sourced from the dir()-confirmed `pdg.Event` surface. Frame/outputs/cookDuration are enrichment — STAGED for the live cook, **and contingent on the M0 resolver probe landing** (§1.5). The demo's "frame number + output path" line is a 3.3-**stretch**, not the gate.

---

## 4. Threading & Marshalling Design + Thread-of-Delivery Experiment

**Scope:** the Spike 2.4-deadlock crux of Spike 3.3, DESIGN-ONLY. (1) stages the throwaway probe that resolves *which thread a `pdg.PyEventHandler` callback fires on during a real cook*, and (2) specifies a marshalling primitive from the PDG event thread to the daemon agent loop that **cannot re-introduce the 2.4 deadlock — regardless of the probe's outcome**.

### 4.1 The deadlock invariant we must not break

Spike 2.4's fix (`turn_handle.py`, confirmed live) made `submit_turn` non-blocking: the caller posts an `_AgentRequest` onto `daemon._request_queue` and gets a `TurnHandle` back immediately; the daemon thread is the sole writer and calls `handle._set_result(...)` when the turn completes. The handle's docstring pins the rule (line 138): *"Never call with `timeout=None` from the Houdini main thread in GUI mode — that re-introduces the Spike 2.4 deadlock."*

**The perception channel inherits this verbatim.** The PDG handler is a *producer*; the daemon agent loop is the *consumer*. The producer must never block waiting on the consumer, and must never touch `hou.*` / `hdefereval` / a main-thread marshal.

| Invariant | Status | Evidence / How |
|---|---|---|
| Handler does `pdg.*` reads ONLY — no `hou.*`, no `hdefereval` | DESIGN | `pdg.*` property reads are thread-agnostic-safe; `hou.*` is not. |
| Handler enqueues non-blocking; never waits on the consumer | DESIGN | Mirror of 2.4; `turn_handle.py:138` rule generalized to the event thread. |
| Daemon consumer pulls from its own queue (never pushed-into synchronously) | CONFIRMED-live | `daemon.py:178` `_request_queue = queue.Queue()`; daemon thread pulls via short-timeout `get()` at `daemon.py:642` — perception channel mirrors this shape. |
| No `hdefereval` in the delivery path | DESIGN | hdefereval is main→main on the SceneLoad path (cargo-cult there per Mile-4 audit); on the PDG path it is the deadlock vector — banned in the handler. |

### 4.2 Thread-of-delivery probe — RESOLVED LIVE this session (§0.1)

> **RESOLVED (§0.1):** the experiment below was **executed** this session (operator-authorized). **Answer: PDG handlers fire on a WORKER thread** (`Dummy-N`, `is_main=False` for all 19 events) — Branch 2. The probe design is retained for re-confirmation during the *real-processor* gate cook (this session's run used a static generator); the marshalling design is unchanged and the worker-thread answer makes its thread-safety mandatory.

**Question (now ANSWERED — worker thread):** does a `pdg.PyEventHandler` callback fire on the **main thread** or a **cook/scheduler worker thread** during a real cook? Resolved live → **worker**; re-confirm at the gate cook with a real processor.

| Step | Action | API (dir()-confirmed) |
|---|---|---|
| 1 | Capture baseline: `main = threading.main_thread()` | stdlib |
| 2 | Create scratch topnet + one trivial generator | STAGED — node creation is the cook gate, not prestage |
| 3 | Acquire live context: `gc = top_node.getPDGGraphContext()` | CONFIRMED-live (R8 instance method) |
| 4 | Register probe handler against `WorkItemStateChange(5)` | CONFIRMED-live — `addEventHandler` in method list |
| 5 | In `handleEvent` record `current_thread().name`, `is_main`, `event.type`, `event.currentState`, `event.workItemId` | CONFIRMED-live — exact `pdg.Event` surface; **no `event.workItem`** |
| 6 | Cook the tiny graph; append observations to an in-memory list | STAGED — the gate cook |
| 7 | `gc.removeEventHandler(h)` then destroy scratch topnet | CONFIRMED-live — `removeEventHandler` in method list |
| 8 | Print `[spike-3.3-thread] handler fired on '<name>' is_main=<bool>` | DESIGN |

**Probe purity:** reads `pdg.*` only, appends to a plain list — no `hou.*`, no queue, no marshal. Destroyed after read. Mark `# DO-NOT-RUN-IN-PRESTAGE — requires live cook (Spike 3.3 gate)`.

**Secondary captures piggybacked on the same cook:** `currentState == CookedSuccess(5)/CookedCache(6)` (BUG B gate), `cookDuration` magnitude (~1.0 ⇒ seconds; ~1000 ⇒ ms — resolved via the M0 resolver, NOT `event.workItem`), and `pdg.Node.name`-property-vs-`.path()` (BUG C pin). Also the **handler-leak count** (§2.5 A) and the **batch `workItemIds` shape** (§1.4).

### 4.3 Marshalling primitive — perception queue (CONTRADICTION RESOLVED)

> **RESOLVED CONTRADICTION (was HIGH).** The draft simultaneously specified the perception queue as **BOUNDED** ("pick bounded, never block the cook thread"; SF-3/SF-7 "bounded put with drop-count") AND claimed the delivery primitive `put_nowait` "never blocks because it is an **UNBOUNDED** `queue.Queue`." These are mutually exclusive: a **bounded** `queue.Queue.put_nowait()` raises `queue.Full` at capacity — it does **not** silently drop. As written, `queue.Full` would propagate out of the "non-blocking" enqueue: on a worker-thread fire an unhandled exception in a `pdg.PyEventHandler` can disrupt/wedge the cook; on a main-thread fire it is swallowed by the bridge's existing `try/except` at `tops_bridge.py:474-482` (counted as a callback drop). Either way the "never disrupts the cook" invariant (SF-7) was resting on an **unstated** `try/except`.

**Decision — BOUNDED queue with an explicit, wrapped overflow handler (option 2 of the fix).** Rationale: bounded gives backpressure visibility and a hard memory ceiling under an event flood (a 5-frame cook fires up to 5 state-changes per work item plus Add/Result — dozens of events fast). The overflow is **counted, never silent, never escapes to the cook thread**:

```python
# Inside perception_callback (NEW M2 code) — the put is ALWAYS wrapped.
try:
    perception_queue.put_nowait(tops_event)          # bounded queue.Queue(maxsize=N)
except queue.Full:
    bridge._increment_dropped(reason="overflow")     # counted, categorized, swallowed
    # drop-NEWEST policy: the just-arrived event is discarded so the agent always
    # sees the OLDEST committed continuity. (drop-oldest is the documented alternative
    # — pick drop-NEWEST and pin it.)
```

- The **single delivery primitive for Spike 3.3 is `queue.Queue.put_nowait`** against the existing synchronous daemon loop. The Lossless BOUNDED COST row and this section now **agree**: the queue is BOUNDED, the put is **wrapped**, overflow is counted.
- **Three distinct drop reasons `dropped_event_count()` MUST keep separable** (extending the SF-4 split): (i) **filtered** — allowlist rejected the event type at the bridge boundary; (ii) **construction-failed** — `_build_tops_event` raised (`tops_bridge.py:464-471`); (iii) **overflow** — bounded `put_nowait` hit `queue.Full` (NEW). An empty/dropped payload must be *visible by reason*, never a silent empty success.
- **DURABILITY wording reconciled:** not "no drop on the happy path" but **"no drop below capacity N; overflow is counted, never silent."**

**Acceptance for the overflow path (NEW):**
- **M2 STANDALONE:** fill the bounded queue to capacity, fire one more event through the callback → assert (a) `queue.Full` is caught **inside** `perception_callback` (never escapes to the cook thread), (b) `dropped_event_count()` increments, (c) the drop is categorized `overflow`, distinct from `filtered` / `construction-failed`.
- **M5 STAGED:** 5-frame cook → assert no `queue.Full` reached the cook thread and the agent observed either all events or a counted-drop set.

### 4.4 `call_soon_threadsafe` — DEMOTED to a FUTURE/CONDITIONAL note (was a co-equal branch)

> **PHANTOM-RISK RESOLVED (was MEDIUM).** The draft presented `loop.call_soon_threadsafe(loop_local_put, ev)` as a co-equal "asyncio branch" of the build. **The live daemon is NOT asyncio:** `daemon.py:178` is plain `threading` + `queue.Queue`, and the consumer at `daemon.py:640-647` is a synchronous `_request_queue.get(timeout=...)` blocking-thread loop. **There is no event-loop object in the daemon to call `call_soon_threadsafe` on.** Presenting it as a build branch risks the build pass reaching for a `loop` handle that does not exist (it would have to be invented), and `call_soon_threadsafe` (schedules a callback ON the loop thread) is a *different shape* from `put_nowait` (hands data to any consumer). For the 3.3 gate the asyncio path is **dead code dressed as a live option.**

> **FUTURE / CONDITIONAL note (NOT a Spike 3.3 build branch):** *IF the daemon loop is ever converted to asyncio — it is NOT today; `daemon.py:178`/`640` is `threading.Queue` + blocking `get()` — then `call_soon_threadsafe` would replace `put_nowait` as the foreign-thread→loop enqueue.* For Spike 3.3 the single primitive is `queue.Queue.put_nowait` against the existing synchronous daemon loop.

**Both-thread-outcome table (the handler code is identical either way):**

| | **Branch 1 — handler fires on MAIN thread** | **Branch 2 — handler fires on WORKER (cook/scheduler) thread** |
|---|---|---|
| Delivery call | `put_nowait(ev)` wrapped in `try/except queue.Full` | `put_nowait(ev)` wrapped in `try/except queue.Full` |
| Why non-blocking is mandatory | Main MUST stay free to pump Qt for any in-flight `hdefereval`. A blocking put here = 2.4 deadlock reborn. | A worker block stalls the cook coordinator and can wedge the cook. |
| `hou.*` in handler? | NO — even "legal" main-thread `hou.*` risks re-entrancy mid-cook; handler stays `pdg.*`-only. | NO — `hou.*` off-main is unsafe by Houdini's threading model. |
| Consumer (daemon loop) | unchanged — drain + ack (§5) | unchanged |

**Decision rule once the probe lands:** the *handler code is identical* in both outcomes. The probe outcome only changes whether a *future* spike that wants the agent to mutate the scene in response would need a main-thread hop. At the 3.3 gate the agent only *acknowledges*, so no hop is needed either way — recording the thread identity now de-risks that future hop.

**Why not `pdg.Scheduler.runOnMainThread`:** it EXISTS (`runOnMainThread(self, wait, function, *args, **kwargs)`) but it is the *wrong* primitive — it marshals a function *onto* main (and with `wait=True` blocks). We want the opposite: a non-blocking enqueue onto the daemon loop. Noted-and-rejected. Keep `hdefereval` as the main-thread executor per Strangler Fig; the perception path uses neither marshal.

### 4.5 Worker-thread ack-counter thread-safety (MEDIUM — newly flagged)

`put_nowait` and `queue.Queue` are thread-safe from any producer thread — but the **surrounding counters and the "ack" bookkeeping are the unguarded surface.** `_increment_dropped` (`tops_bridge.py:616-618`) takes `self._lock`, but the NEW M2 `perception_callback` supplier (producer) and the NEW M2/M4 agent-loop drain (consumer) will touch the perception queue and an ack-counter from **two different threads** (cook/worker producing, daemon consuming). The threading design proves the *handler* is `pdg.*`-only + non-blocking; it never audits whether the NEW ack state is thread-safe, nor whether `reload_count()` / `dropped_event_count()` read from the GUI panel race the worker-thread writes.

> **FIX — DESIGN constraint + STANDALONE test:** the ack counter and any "last-acked" state live **ONLY on the daemon consumer thread** (single-writer, mirroring the `TurnHandle` sole-writer invariant). The producer side does `put_nowait` + nothing else. **STANDALONE acceptance:** spawn N worker threads doing `put_nowait` while the daemon drains → assert `total_acked + total_dropped == total_produced` (no lost/double-counted ack).

---

## 5. First-Event-Live wire plan — the gate hop-chain

Real cook fires → handler derives complete → TopsEvent → perception_callback → daemon perception queue → agent loop **drains + acks**. Each hop, where it lives, what is new for 3.3:

| # | Hop | Lives in | Mechanism (live-confirmed) | 3.3 status |
|---|---|---|---|---|
| 1 | Real PDG cook emits events | Houdini `pdg` runtime | `pdg.GraphContext.addEventHandler(handler, EventType)` already registered by `warm()` (`tops_bridge.py:293`) | CONFIRMED-live (registration) |
| 2 | Handler fires, derives completion | `tops_bridge.py` `on_pdg_event` (`:446`) | filter `event.type`; if `WorkItemStateChange`, read `event.currentState`; emit synthetic `tops.workitem.complete` when `CookedSuccess/CookedCache` | DESIGN (BUG A+B rewrite, M1) |
| 3 | Build typed `TopsEvent` | `tops_bridge.py` `_build_tops_event` (`:486`) | re-sourced per §3 — `event.workItemId`, `event.node.name`, `event.message` | DESIGN (M1) |
| 4 | Invoke `perception_callback(tops_event)` | `tops_bridge.py:475` | already swallows callback exceptions so a cook is never disrupted (`:476-482`) | CONFIRMED-live (contract) |
| 5 | Callback marshals onto perception queue | **new** `perception_callback` supplier wired at daemon boot | **wrapped** `queue.Queue.put_nowait(tops_event)` (NOT `Scheduler.runOnMainThread`; bounded queue + counted overflow, §4.3) | DESIGN (M2 wiring) |
| 6 | Daemon holds the perception queue | **new** `daemon.py` field beside `_request_queue` (`daemon.py:178`) | `daemon.py` today has **zero** Bridge/perception refs — greenfield | DESIGN (M2) |
| 7 | Agent loop drains + acks | **new** perception-drain in `_thread_main` (`daemon.py:640-647`) | drain on the `queue.Empty` cycle of the request loop (§5.1) — NOT a one-liner | DESIGN (**M2/M4 build item**) |
| 8 | Bridge instantiation + lifecycle | **new** at `SynapseDaemon` boot / `stop()` (`daemon.py:271`) | `host/__init__.py` only **exports** the bridges — boot calls `warm_all()`, `stop()` calls `cool_all()` (leak guard, §2.5) | DESIGN (M3) |

### 5.1 The agent-loop drain point — PROMOTED to an explicit build item (was a one-liner)

> **STRUCTURAL FIX (was HIGH).** The draft treated perception-queue interleaving as a one-line DESIGN item ("non-blocking `perception_queue.get_nowait()` interleaved with `_request_queue.get(timeout=...)`"). **The live daemon loop structurally cannot drain it as written.** `daemon.py:640-647` is a strict request/response loop: `_request_queue.get(timeout=_REQUEST_POLL_INTERVAL_SECONDS)` then `_process_request(request)`, and `_process_request` (`daemon.py:655+`) calls `run_turn()` which **BLOCKS** for the full duration of an agent turn (one or more Anthropic API round-trips + tool dispatches). There is **no idle yield point** where a bare `get_nowait()` would run unless a `submit_turn` request happens to arrive. The verbatim gate ("Agent loop pulls the event from the queue and acknowledges it") is therefore **NOT satisfiable by "the existing loop shape"** — it requires editing `_thread_main`, which is daemon-territory build the prestage under-scoped to a one-liner.

**Concrete M2/M4 design:** in `_thread_main`, when `_request_queue.get(timeout=...)` raises `queue.Empty` (`daemon.py:645-646`), **drain the perception queue before `continue`:**

```python
while not self._cancel_event.is_set():
    try:
        request = self._request_queue.get(timeout=_REQUEST_POLL_INTERVAL_SECONDS)
    except queue.Empty:
        # NEW (M2/M4): drain perception on every wake, including timeouts.
        while True:
            try:
                ev = self._perception_queue.get_nowait()
            except queue.Empty:
                break
            self._ack_perception(ev)   # log + counter++ on the DAEMON thread only (§4.5)
        continue
    self._process_request(request)
```

**ACCEPTANCE (STAGED M4):** with NO `submit_turn` in flight, a real cook's `workitem.complete` is acked within `< _REQUEST_POLL_INTERVAL_SECONDS`; with a `submit_turn` in flight, events arriving mid-turn are acked at the next `Empty` cycle (**bounded staleness == one turn duration — surface this as a known limit**).

### 5.2 The <50ms latency budget is bounded by the poll cadence — NOT "sub-ms"

> **LATENCY FIX (was MEDIUM).** `_REQUEST_POLL_INTERVAL_SECONDS = 0.25` — **read from `daemon.py:84` this prestage** (no longer a STAGED guess). The drain in §5.1 only runs once per request-poll wake, so a perception event arriving while the daemon is parked in the blocking `get()` waits **up to 250ms** before being drained. End-to-end latency is bounded by the poll interval the thread is parked in, **not by in-process speed.** The "sub-ms in-process expected" assertion cannot stand against this cadence as wired.

**To satisfy the <50ms gate, pick and pin one (verify at M4):**
- **(a)** Drain `perception_queue` in a tight inner loop on **every** wake including `queue.Empty` timeouts (§5.1 — cheap, but worst-case latency is still bounded by the interval the thread is parked in).
- **(b) Lower `_REQUEST_POLL_INTERVAL_SECONDS`** so worst-case perception latency < 50ms (e.g. ≤ 0.04s). The current value (0.25s = 250ms) does **NOT** support the <50ms gate as-is. This is the recommended lever.
- **(c)** Use a single shared queue both producers push to with a typed discriminator.

**The <50ms gate must be derived from the actual poll cadence, not asserted.** The latency check at M4 (timestamp delta hop 4 `time.monotonic()` at `tops_bridge.py:500` vs hop 7 pull) must report the *measured* value against the *chosen* poll interval, and the staleness-during-a-turn limit (§5.1) must be surfaced as a known boundary — a perception event landing during a long agent turn violates <50ms by design until/unless a separate consumer thread is added (out of 3.3 scope).

### 5.3 SF-8 split-scope-exec guard — make it a checkable M3 constraint

The split-scope-exec risk (`exec(code, G, L)`, `G≠L` → top-level names invisible inside the script's nested functions) is real (per MEMORY note). The daemon does **not** yet instantiate the bridges — so whether M3's instantiation happens via a normal `from synapse.host import SceneLoadBridge` import inside daemon code (safe) vs. via `houdini_execute_python` pushing a bootstrap script (SF-8 territory) is an **OPEN wiring decision**, not yet resolved.

> **FIX — explicit M3 acceptance line (turns the guard from prose into a build constraint):** *`SceneLoadBridge` / `TopsEventBridge` are instantiated via direct module import inside `SynapseDaemon.start()` (normal module scope), NOT via any exec'd bootstrap — verified by grepping the M3 diff for `houdini_execute_python` in the boot path == 0 matches.*

---

## 6. Lossless Properties + Failure-Class Register

Scope: the in-process TOPS perception channel (`TopsEventBridge` + `SceneLoadBridge` + the Spike 3.3 perception queue / agent-loop drain). This is a **read-only observation channel** — it surfaces `pdg.Event` data to the cognitive layer; it never mutates the scene.

### 6.1 Six Lossless Properties → perception channel

| Property | Maps to (this channel) | Status | Evidence / How |
|---|---|---|---|
| **TERMINATION** | Handlers removable; daemon `stop()` must call `cool_all()` + `removeEventCallback`. | STAGED-live-check | `tops_bridge.py:299/378` `removeEventHandler` present; **removal-arity (one call detaches all 7 type-regs?) UNVERIFIED — see §2.5 A**. `pdg.GraphContext.removeEventHandler`/`removeAllEventHandlers` confirmed live. Wiring `cool_all()` into `SynapseDaemon.stop()` is Spike 3.3 (M3). |
| **OBSERVABILITY** | 7-type allowlist re-filtered on `event.type`; typed `TopsEvent.to_dict()`; `reload_count()` / `dropped_event_count()`. | CONFIRMED-live (enums) / STAGED-live-check (payload) | `pdg.EventType` re-confirmed zero-drift. **Payload is currently BLIND** — SF-4: `event.workItem` phantom → id/frame/state/outputs silently empty. Real surface: `workItemId`/`workItemIds`/`currentState`/`lastState`/`node`/`message`/`type`. |
| **DURABILITY** | Event survives handler → bounded `queue.Queue` → agent-loop drain+ack, non-blocking. **No drop below capacity N; overflow is counted, never silent** (§4.3 — reconciled). | STAGED-live-check | Perception queue + supplier + agent-loop drain are Spike 3.3 wiring (M2/M4). Marshal = wrapped non-blocking `put_nowait` to the daemon loop — NOT `runOnMainThread` (SF-7). |
| **BOUNDED COST** | **BOUNDED** perception queue (maxsize N) + `dropped_event_count()` backpressure with **three separable reasons** (filtered / construction-failed / overflow); a raising `perception_callback` is swallowed and counted; per-event work is `pdg.*` property reads only. | CONFIRMED-live (drop path) / DESIGN (queue bound + overflow policy) | `tops_bridge.py:419` `dropped_event_count`; `:464-471` construction-drop; `:474-482` callback-drop. Queue is BOUNDED with **drop-NEWEST + count** (§4.3) — agrees with the Threading section; no unbounded claim remains. |
| **PROVENANCE** | Each `TopsEvent` self-describing: `pdg_event_type_int` + human string + `top_node_path` + `monotonic()` timestamp + (once SF-4 fixed) `work_item_id`/`frame`/`state`/`outputs`. `node_path` pinned to `pdg.Node.name`. | STAGED-live-check | `pdg.Node` has `.name` property, **no `.path()`** (probe). `_read_node_path` fallback works but must pin `.name` (BUG C) and **empirically confirm `.name` non-callable** at M4 (§1.6 snippet 5). |
| **REVERSIBILITY** | Trivially satisfied: observation is **read-only**. Zero `hou.*` mutations, no nodes, no cook triggered. Undo groups / scene-integrity anchors N/A — no mutation. | CONFIRMED-live (by construction) | Handler calls only `pdg.*` reads. PRESTAGE constraint (zero build / no cook) holds by design. |

### 6.2 Failure-class register

| Code | Failure class | Instance in this channel | Guard |
|---|---|---|---|
| **SF-1** | Phantom API | Avoided phantoms: `hou.pdg`, `hou.pdg.scheduler`, `hou.pdg.workItem`, `hou.pdg.GraphContext`, `hou.pdgEventType`, `pdg.PyEventCallback`, `event.workItem`. **Live bugs:** BUG A (`tops_bridge.py:521`), BUG B (no `WorkItemComplete` enum), BUG C (`pdg.Node.path()`). **Latent:** guessed `pdg.WorkItem` accessors + unprobed id→WorkItem resolver (§1.3, §1.5) — risk that the M1 BUG A fix swaps one phantom for another. | Pin every reference to a `dir()`-confirmed surface. **M0-probe `pdg.WorkItem` class + the resolver BEFORE M1 codes against them.** Real event surface only. (DO NOT fix A/B/C here — Spike 3.3 build.) |
| **SF-4** | Silent failure (no error, wrong/empty data) | **The defining instance.** BUG A returns `None` on every live event → fields silently empty at first-event-live. Compounded by BUG B: no `WorkItemComplete` → "done" never detected → gate event never fires, silently. | Rewrite against the real surface (M1). **Three separable drop reasons** `dropped_event_count()` must distinguish: filtered / construction-failed / **overflow** (§4.3). Live assertion at first cook: if a CookComplete fires but zero derived `workitem.complete` reached the queue → **loud fail, not empty success.** |
| **SF-7 / SF-3** | Deadlock (Spike 2.4 reintroduction) | Risk: agent loop blocking on a result while main is parked (the 2.4 topology), or marshalling the event the wrong way (`runOnMainThread` pushes work TO main — re-parks it). **Newly surfaced:** an *unwrapped* bounded `put_nowait` letting `queue.Full` escape into a worker-thread cook (§4.3). | Marshal = **wrapped, non-blocking, enqueue-only** to the daemon loop (`put_nowait` inside `try/except queue.Full`). NOT `runOnMainThread`. Agent-loop drain uses the `TurnHandle` sole-writer pattern, **off** the main thread. **OPEN (the gate, STAGE):** which thread does `pdg.PyEventHandler` fire on during a real cook? Stage the experiment (§4.2); either way the handler stays `pdg.*`-only + wrapped non-blocking enqueue, so the answer cannot reintroduce the deadlock. |
| **SF-8** | Split-scope exec (`exec(code, G, L)`, `G≠L`) | Applies only if handlers are injected into the daemon via an exec'd script. A top-level `pdg.PyEventHandler` subclass would be invisible to nested helpers under split-scope exec. **Status: OPEN wiring decision** — daemon does not yet instantiate the bridges. | **Preferred guard, now a CHECKABLE M3 constraint (§5.3):** instantiate the bridges via direct module import inside `SynapseDaemon.start()` (normal scope), NOT via any exec'd bootstrap — verified by grepping the M3 boot-path diff for `houdini_execute_python` == 0 matches. If exec is ever used: `run()`-wrapper or `globals()` republish. |

---

## 7. Spike 3.3 mile decomposition

> **PRESTAGE SCOPE:** design-only. **ZERO build here.** No production code, no node creation, no cook. The Mile breakdown is the *plan*; **build starts at M1.** M0 is live `dir()` re-confirm + the resolver/WorkItem probes (runnable now) + **staged** experiments (designed, not executed).

| Mile | Goal | Build? |
|---|---|---|
| **M0** | Live `dir()` re-confirm; **probe `pdg.WorkItem` class + id→WorkItem resolver (no cook)**; read `_REQUEST_POLL_INTERVAL_SECONDS`; STAGE the thread-of-delivery experiment | **NO BUILD** (recon + staged design) |
| **M1** | Fix the event model — BUG A (phantom `workItem`), BUG B (derive `workitem.complete`), BUG C (pin `.name`); **batch rule (§1.4)** | **BUILD STARTS HERE** |
| **M2** | Wire `perception_callback` → daemon **bounded** perception queue (wrapped non-blocking enqueue); **agent-loop drain in `_thread_main` (§5.1)**; ack-counter single-writer (§4.5) | BUILD |
| **M3** | Daemon instantiates `SceneLoadBridge` (**direct import, SF-8 check §5.3**) + auto `warm_all()` on `AfterLoad`; `cool_all()` in `stop()`; scene-clear cool-on-dead-context check (§2.5 B) | BUILD |
| **M4** | First real cook fires a derived `workitem.complete`; agent loop drains + acks; **handler-leak count, thread-of-delivery, cookDuration unit, latency-vs-poll all resolved here** | BUILD (**the gate cook**) |
| **M5** | 5-frame demo — five `workitem.complete` events, agent narrates; overflow flood check (§4.3) | BUILD (demo shape) |

**M0 acceptance:** `dir()` for `pdg.Event` / `pdg.Node` / `pdg.EventType` / `pdg.workItemState` / `pdg.GraphContext` re-printed verbatim and matching §1; **`dir(pdg.WorkItem)` confirms the real attribute names** the M1 rewrite will use (else BUG A's fix re-introduces SF-4 on guessed attrs); **the id→WorkItem resolver is confirmed** (else outputs/frame/cookDuration drop from M5 scope — §1.5); `_REQUEST_POLL_INTERVAL_SECONDS` value read from source (= 0.25 today, §5.2); the thread-of-delivery experiment exists as a written, runnable-at-M4 script touching **only** `pdg.*` reads + `threading` (zero `hou.*`, zero cook).

**M1 acceptance:** STANDALONE (mock `pdg`) proves (a) `WorkItemStateChange`+`currentState=CookedSuccess` → exactly one `workitem.complete`; (b) `CookedFail`/`Cooking` → none; (c) `CookedCache` → complete; (d) `workItemIds=[a,b,c]`+`CookedSuccess` → the chosen batch count deterministically (§1.4); (e) node path via `.name`, no `.path()` call; (f) no code path references `event.workItem`. Test count strictly increases; headless import without `hou`/`pdg` still succeeds.

**M2 acceptance:** STANDALONE — a faked `WorkItemStateChange→CookedSuccess` lands as one item on the queue via wrapped `put_nowait`; a callback that raises increments `dropped_event_count` and leaves the cook path untouched; **overflow test** (queue at capacity + one more) → `queue.Full` caught inside the callback, counted as `overflow`, distinct from `filtered`/`construction-failed`; **worker-thread test** (N producers + daemon drain) → `acked + dropped == produced`; no `hou.*` touched on the callback thread.

**M3 acceptance:** STANDALONE — firing mock `AfterLoad` 3× on a 2-topnet scene → exactly 2 subscriptions; mock `AfterClear` → zero; `daemon.stop()` empties active subscriptions; **SF-8 grep check** (0 `houdini_execute_python` in boot path). **Live (Joe-at-GUI):** File→Open auto-warms with no menu action; **scene-clear cool-on-dead-context survives** (§2.5 B).

**M4 acceptance (THE GATE):** one real cook → ≥1 `workitem.complete` on the queue; agent terminal logs the ack (frame id + node `.name`); **thread-of-delivery recorded** (main vs worker); **handler-leak count post-cool == 0** (§2.5 A); `cookDuration` unit pinned; **measured latency reported against the chosen poll interval** (< 50ms only if §5.2 lever applied).

**M5 acceptance:** five distinct `workitem.complete` events in order, no loss/reorder; agent narration reflects five frames + durations + output paths **sourced from the real surface** (output narration is **stretch, contingent on the §1.5 resolver landing**); flood produces no `queue.Full` on the cook thread.

---

## 8. Live-check checklist for the Spike 3.3 live session

Single consolidated table. **M0 items are runnable now (no cook).** Everything else needs the gate cook / Joe-at-GUI.

| # | Live-check | Mile | Type | Acceptance |
|---|---|---|---|---|
| 1 | Re-print `dir()` for `pdg.Event` / `Node` / `EventType` / `workItemState` / `GraphContext` | M0 | dir (no cook) | Matches §1 verbatim, zero drift |
| 2 | `dir(pdg.WorkItem)` — confirm real `.frame`/outputs/`.cookDuration`/`.id`/`.state`/`.node` names | M0 | dir (no cook) | M1 codes against confirmed names, not guesses (§1.3) |
| 3 | id→WorkItem resolver: dir() `event.node` / context for `workItemById`/`workItems` | M0 | dir (no cook) | A resolver is confirmed, else outputs/frame/cookDuration drop from M5 (§1.5) |
| 4 | Read `_REQUEST_POLL_INTERVAL_SECONDS` from source | M0 | source read | Value pinned (= 0.25 today); latency budget derived from it (§5.2) |
| 5 | Thread-of-delivery: `pdg.PyEventHandler` fires main vs worker | M4 | live cook | Thread identity recorded; handler stays `pdg.*`-only + wrapped enqueue (§4.2) |
| 6 | `event.currentState == CookedSuccess(5)`/`CookedCache(6)` at a real success transition | M4 | live cook | Derived `workitem.complete` fires; no int-vs-enum conflation (§3) |
| 7 | `node_path` non-empty, sourced from `event.node.name`; **`.name` non-callable** | M4 | live cook | BUG A regression guard + BUG C property pin empirically confirmed (§1.6 #5) |
| 8 | `cookDuration` numeric unit (s vs ms) via the confirmed resolver | M4 | live cook | ~1.0 ⇒ seconds; one-line `*1000` fix if ms |
| 9 | **Handler-leak arity:** `gc.eventHandlers()` count before warm → after `cool()` | M4 | live cook | post-cool count == 0; else loop `removeEventHandler` per type (§2.5 A) |
| 10 | **Scene-clear cool-on-dead-context:** warm scene A → File→Open scene B | M3/M4 | Joe-at-GUI | process survives; `active_subscriptions()==()`; document raise-vs-crash (§2.5 B) |
| 11 | **`warm()` double-call** via `hasEventHandler` probe | M3 | live cook | one cook → exactly one complete per work item, even on double-warm (§2.6) |
| 12 | Failure/cancel never counted complete: observe `CookedFail(7)`/`CookedCancel(8)` | M4 | live cook | zero `workitem.complete` emitted for it (§3) |
| 13 | **Overflow flood:** fill bounded queue, fire one more | M2/M5 | standalone + live cook | `queue.Full` caught in callback, counted `overflow`, never reaches cook thread (§4.3) |
| 14 | **Latency vs poll cadence:** hop-4 → hop-7 `monotonic()` delta | M4 | live cook | measured against chosen interval; <50ms only if §5.2 lever applied |
| 15 | Real File→Open fires `AfterLoad`; `reload_count()` +1 (0 for AfterClear) | M3/M4 | Joe-at-GUI | callback invoked once on main; counts match (§2.2) |
| 16 | `warm_all()` discovers live topnets; `active_subscriptions()` == topnet count | M4 | Joe-at-GUI | live `getPDGGraphContext()` returns real context per topnet (§2.2) |
| 17 | Idempotency: open → open again → sub count stays == topnet count | M4 | Joe-at-GUI | 3× AfterLoad on 2-topnet → exactly 2 subs (§2.2) |
| 18 | Teardown: `unsubscribe()`/`daemon.stop()` → zero residue | M3 | Joe-at-GUI | hipFile callback list empty; `active_subscriptions()==()`; `is_subscribed()==False` |
| 19 | **AfterMerge gap (observe, don't fix):** File→Merge a `.hip` with a topnet | M4 | Joe-at-GUI | record `BeforeMerge→…→AfterMerge` sequence; assert `reload_count()` does NOT increment (§2.3) |
| 20 | **Batch event:** cook a batched/partitioned TOP (or park as documented edge) | M4/M5 | live cook | dir() a live batch event; chosen batch count is deterministic (§1.4) |
| 21 | End-to-end gate: ≥1 `workitem.complete` on queue; agent drains + acks | M4 | live cook | the verbatim gate — wire continuity, no reasoning |

---

## 9. What this prestage did NOT do (build boundary)

- **No production code was edited.** BUG A (`tops_bridge.py:521`), BUG B (no `currentState` read), and BUG C (`.path()`-first at `:578-584`) are **documented, not fixed.** Their fix lands at **M1** — the first line of build.
- **No node was created and no cook was triggered.** Every STAGED-live-check is a *designed, runnable-at-M4* assertion, not an executed one. The thread-of-delivery probe, the handler-leak count, the cookDuration unit, the latency measurement, and all batch/flood/scene-clear checks are written-but-unrun.
- **The two M0 dir()-only probes** (`pdg.WorkItem` class surface; the id→WorkItem resolver) are statically resolvable without a cook and are the *only* live introspection this prestage authorizes running before M1 — and even those touch `pdg.*` reads only, zero `hou.*`, zero mutation.
- **No daemon wiring was added.** The perception queue, the `perception_callback` supplier, the agent-loop drain in `_thread_main`, and bridge instantiation are all greenfield design (M2/M3/M4). `host/__init__.py` still only *exports* the bridges.
- **The AfterMerge gap, the batch path, and the asyncio variant are explicitly out of the gate.** AfterMerge is recommended-deferred (option 3) with a live-check to confirm the blind spot is real; batch is decided-at-M1 / observed-at-M4 or parked; the asyncio `call_soon_threadsafe` path is a FUTURE note, not a build branch (the live daemon is `threading.Queue` + blocking `get()`).
