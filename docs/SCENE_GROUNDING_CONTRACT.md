# G5 — SCENE-GROUNDING CONTRACT (frozen spec)

**`docs/SCENE_GROUNDING_CONTRACT.md`** · Repo: `C:\Users\User\SYNAPSE` · Grounded against HEAD `314acd6` (2026-07-10) / Houdini 21.0.671.
**Status: PROPOSAL — Leg-0 paper artifact (Mile 0.3).** This is MODE A paper: it specifies the four manifest tools; it does not build them. It becomes binding only when merged to main (the human gate, blueprint harness §2).

> **Governing gate:** the *build* of these tools is **MODE B** work — gated on `harness/state/drop.json` existing (blueprint harness §2 gate registry) plus a verbatim `h22-gatewarden` `ALLOW` block in the FORGE dispatch (§4). The **Michael Gold RFC** (gate row: *"any USD-schema write — off the critical path"*, `docs/H22_AGENT_HARNESS.md:60`) stays **OFF** this critical path — see §6. Merge-to-main is the human gate per artifact.
> **Relay leg:** this contract is authored in **Leg 0**. Its build is post-drop MODE B. The exact numbered leg for the G5 build is **[UNVERIFIED — the `SYNAPSE_H22_GAP_BLUEPRINT v2.0` doc that assigns G-gaps to numbered legs is not present in-repo; the blueprint harness (`docs/H22_AGENT_HARNESS.md`) names Leg 0 = paper, Leg 1 = human writes `drop.json`, and G1 port-waves = Leg 3, but does not assign a numbered leg to the G5 grounding build]**. See OPEN DECISION 3.

---

## OPEN DECISIONS (human rules these; the rest of the spec is complete without them)

1. **G-numbering collision — naming.** "G5" here is the **gap** number from the H22 gap-blueprint (scene-grounding). The **release-gate** table in `docs/reviews/synapse-h22-readiness-2026-07-10.md:490` *also* has a **"G5 — Lifecycle"** (runtime heartbeat survives panel close), and `harness/verify/checks.py:1976` + `harness/state/release_readiness_verdict.json` key it as `G5_lifecycle`. **These are two different axes on the same label.** Working assumption in this spec: "G5" = the grounding gap. Human decision: confirm the label, or rename one axis (e.g. gap → `GAP-5`) so no reader conflates the grounding contract with the lifecycle release gate.

2. **`error_manifest` scope vs the D-track.** The D-track (`harness/notes/spec-D-diagnostic-truth.md`, `ratified:false`) owns the **dynamic** cook axis — *"why did/will this recook?"*, callback runtime errors, dirty propagation. This spec's `error_manifest` is deliberately **static** (current error/warning state as it stands *now*, no perturbation). The two do not overlap by construction, but a human may prefer `error_manifest` to *defer entirely* to D once D ratifies, or to *feed* D's callback diagnosis. Working assumption: ship `error_manifest` static-only; it cites node error/warning state, never a cook replay. Human decision: confirm the static/dynamic split, or fold `error_manifest` under the D surface.

3. **Relay-leg assignment for the build.** See the header note. If the human wants the G5 build pinned to a numbered leg (vs. an ad-hoc MODE-B FORGE dispatch), that assignment is theirs to make against the source gap-blueprint.

4. **Default token budget value.** §3 sets a concrete default (`token_budget=1500` per call) and makes it a tunable parameter — that is a design call, made. What is *not* mine to set: whether the budget is enforced **per-call** (this spec) or **per-turn** across all manifest calls in one agent turn (a harness-level accounting change). Working assumption: per-call. Human decision if per-turn accounting is wanted.

---

## Mission

Give the agent **four read-only manifest tools** — `graph_manifest`, `attr_manifest`, `parm_manifest`, `error_manifest` — that answer *"what is in this scene, right now, at this axis"* under a **hard token budget** with an explicit **degradation ladder** (counts → names → typed samples). The differentiator vs. the shipped `synapse_inspect_*` tools is not new data — it is **bounded, honest data**: a manifest never blows the context window and never silently truncates; it degrades along a declared ladder and **stamps which tier it served**.

**Why this is a distinct deliverable.** The shipped inspectors (`synapse_inspect_scene/_node/_selection/_stage`) are *deep dumps* with *ad-hoc* caps (50 selected nodes, "skip sampling on large geometry", `max_depth=3`). They have no unified token budget and no ladder: on a large scene `inspect_scene`'s recursive `network_tree` is unbounded, and `inspect_node` returns *all* parameters/expressions/code/geometry with no ceiling. The manifests add the **budget-as-contract** the grounding gate needs, split across four orthogonal read axes so the agent asks for exactly the axis it needs at exactly the fidelity the budget allows.

---

## Definition of Done (the whole gate, before any per-deliverable table)

G5 is **done** when all of the following hold. Each is a check a reviewer can run without design judgement.

- **DoD-1 — Four tools exist on the cognitive-Dispatcher seam.** `graph_manifest`, `attr_manifest`, `parm_manifest`, `error_manifest` are wired **exactly as the fourth, exemplar inspector `synapse_inspect_stage` is wired** — **not** as `python/synapse/mcp/_tool_registry.py` `TOOL_DEFS` tuples. Per manifest that means: (a) a `Tool(name, description, inputSchema)` descriptor added to `list_tools()` (`mcp_server.py:762-766`, the inspect_stage precedent); (b) a dedicated `call_tool()` branch that routes to a cognitive `Dispatcher` (`mcp_server.py:800-801`); and (c) an entry in that `Dispatcher(tools={...})` dict (`mcp_server.py:569-571`, `tools={_INSPECTOR_TOOL_NAME: _inspect_stage_tool}`). `synapse_inspect_stage` is **not** in `_tool_registry.py` (grep at `314acd6` returns nothing) — the three other inspectors are `_tool_registry.py` tuples resolved by `dispatch_tool` → `handler.handle()` on the command-handler path (`mcp/tools.py:85-128`), a **different seam** that the manifests must not use (it forces a `hou`-touching command handler, violating DoD-4). Read-only / non-destructive / idempotent is **structural** — the tool function performs zero mutation — not a tuple flag; identical to inspect_stage, which advertises no destructive hint and never routes through the mutating bridge path.
- **DoD-2 — Budget is honored.** Every manifest accepts a `token_budget` parameter and its serialized return never exceeds it, measured by the repo's own estimator idiom `len(json.dumps(payload)) // 4` (the exact idiom shipped at `shared/types.py:227`, `GeoSummary.token_estimate`). No manifest returns an over-budget payload; if the highest tier would exceed budget, it degrades (DoD-3), never truncates mid-structure.
- **DoD-3 — Ladder is declared and honest.** Every return carries `served_tier ∈ {"samples","names","counts"}` and a `dropped` summary (what the served tier omitted — both vs. the tier above it and, within the served tier, any elements beyond the hard element cap). The manifest picks the **richest tier it can fully build within budget and cap** and reports it. A `counts`-only or capped-`names` degradation is a valid, correct answer — never an error.
- **DoD-4 — Thread posture holds.** No manifest calls `hou.*` off Houdini's main thread. `hou.*` traversal runs through the host main-thread executor seam (the Dispatcher's `main_thread_executor`, per `python/synapse/cognitive/tools/__init__.py`); the cognitive tool function is pure-Python, zero-`hou`. This is the Spike 3.1 lesson applied — §4.
- **DoD-5 — Zero USD-schema dependency.** No manifest reads or writes any `synapse:*` USD attribute schema, and none blocks on the Michael Gold RFC. `graph_manifest` / `attr_manifest` / `parm_manifest` / `error_manifest` all ship against the live `hou.*` surface that exists at HEAD `314acd6` (§6). The Michael Gold RFC row can stay unratified forever and G5 still ships.
- **DoD-6 — Symbol provenance is clean.** Every `hou.*` symbol a manifest emits is either **V1** (verified in shipped code this session — §5 evidence table) or **V0** (probe at runbook step 9 — never asserted as fact, per CLAUDE.md safety rule 15). The `phantom_clean` guardrail passes.
- **DoD-7 — Tests + suite floor.** New tests (`tests/test_grounding_manifests.py`, style of `tests/test_inspect_mock.py` / `test_inspect_node_default.py`) pin: budget-never-exceeded, ladder-degradation-under-shrinking-budget, tier-stamp-present, one happy path per manifest. Full `python -m pytest tests/` at or above `harness/verify/suite_baseline.json` floor. No fake-`hou` planted at module level (`synapse-test-fake-residency` trap).

---

## Ground truth (verified this session — do not re-litigate)

- **The shipped introspection surface is four tools, all read-only — but on TWO different registration seams.** Three are `_tool_registry.py` `TOOL_DEFS` tuples whose `handler` is a **string** command name, resolved by `dispatch_tool` → `SynapseCommand` → `handler.handle()` on the `hou`-touching command-handler path (`mcp/tools.py:85-128`). The fourth, `synapse_inspect_stage`, is **not in `_tool_registry.py` at all** (grep returns nothing at `314acd6`) — it is a bespoke cognitive-**Dispatcher** branch in `mcp_server.py`. **The manifests copy the fourth seam, not the first three.**
  - `synapse_inspect_selection` (`_tool_registry.py:817`) → `inspect_selection(depth=1)` → `{count, nodes, topology}`; caps at **50** selected nodes (`introspection.py:259`).
  - `synapse_inspect_scene` (`_tool_registry.py:824`) → `inspect_scene(root='/', max_depth=3, context_filter=None)` → `{overview:{node_count, contexts}, network_tree:[…recursive…], issues, artist_notes}`. **`network_tree` has no total-node ceiling** — the `_walk` recursion is bounded only by `max_depth` and materializes the whole tree, so a wide scene at depth 3 is unbounded (`introspection.py:305-366`).
  - `synapse_inspect_node` (`_tool_registry.py:833`) → `inspect_node_detail(node, include_code=True, include_geometry, include_expressions)` → deep single-node dump of **all** parameters, expressions, code, geometry (`introspection.py:369`).
  - `synapse_inspect_stage` — the Dispatcher-ported one, **not a `_tool_registry.py` row**. The pure-Python tool is `python/synapse/cognitive/tools/inspect_stage.py` → `StageAST` payload, schema `1.0.0`, flat `/stage` AST with per-node `usd_prim_paths`, `error_state`, flags, `key_parms`. It is wired in `mcp_server.py` as a `list_tools()` `Tool` (`:762-766`) + a `call_tool()` branch (`:800-801`) + a lazy `Dispatcher(tools={_INSPECTOR_TOOL_NAME: _inspect_stage_tool})` singleton (`:536-573`, dict at `:569-571`). **This is the exact wiring the manifests copy**: pure-Python cognitive tool, zero-`hou`, transport injected at boot.
- **Ad-hoc budgeting already exists but is not a contract.** `_geometry_summary` samples attribute values up to `max_samples` and **skips sampling entirely on large geometry** (`introspection.py:110-112`, `sample_status="skipped (large geometry)"`). This is the *seed* of the ladder — but it is one tool's private heuristic, not a declared, stamped, budget-driven tier. The manifests generalize it into a first-class contract.
- **A token-estimate idiom already ships.** `shared/types.py:225-227` — `GeoSummary.token_estimate()` returns `len(json.dumps(asdict(self))) // 4`. `GeoSummary`'s docstring target is **"<100 tokens"** (`shared/types.py:211`). The manifests **reuse this idiom** — no `tiktoken`, no new dependency (`no new dependencies` is a Spike-3.1-class invariant).
- **`GeoSummary` already models the attr axis.** `shared/types.py:210-223` carries `point_count/prim_count/vertex_count`, `point_attribs/prim_attribs/detail_attribs` (name→type dicts), `bounds`, `groups`, `has_normals`, `has_uvs`. `attr_manifest` builds on this dataclass. **Note:** `GeoSummary` has **no `vertex_attribs` field** — a vertex-attribute inventory is *new* surface (see §5 V0 tag).
- **Error/warning state is a live `hou` read, already exercised.** `_node_issues` calls `node.warnings()` and `node.errors()` (`introspection.py:180,184`). `error_manifest` reads exactly these — it does **not** replay a cook (that is the D-track, `spec-D-diagnostic-truth.md`).
- **Thread lesson is on the record.** `docs/sprint3/spike_3_1_design.md §2.8` ("Threading model") + the `tops_bridge.py` module docstring (`python/synapse/host/tops_bridge.py:25-30`, "PDG event callbacks may fire on a non-main thread"): PDG event callbacks may fire on **any** thread; **`hou.*` must not be called off the main thread**; cross-thread hand-off uses a thread-safe primitive (`queue.Queue`, `threading.Event`). §4 applies this to the manifests.

---

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. The four manifests — one read axis each

Each manifest is a pure-Python cognitive tool `def <name>(**kwargs) -> Dict[str, Any]` (the Dispatcher contract, `cognitive/tools/__init__.py`), returning a JSON-serializable dict. All four share the **common envelope** (§2) and the **degradation ladder** (§3).

| Tool | Read axis | Answers | Generalizes |
|---|---|---|---|
| `graph_manifest` | **Topology** — nodes, types, wiring, per-context counts | "what is wired to what, and how big is this network" | `inspect_scene` (tree) + `inspect_selection` (topology) |
| `attr_manifest` | **Geometry attributes** — point/prim/vertex/detail attrs, names, types, sizes, typed samples | "what attributes does this geo carry, and what do they look like" | `_geometry_summary` / `GeoSummary` |
| `parm_manifest` | **Parameters** — names, types, values, non-default, expressions | "what parameters does this node/subtree expose and which are touched" | `inspect_node_detail` (parm dump) + `_modified_parms` |
| `error_manifest` | **Error/warning state** (static) | "what is currently erroring or warning across this subtree" | `_node_issues` + `inspect_scene.issues` |

**Inputs (frozen field names; builder may add optional fields, may not rename these):**

- `graph_manifest(root="/", max_depth=3, context_filter=None, token_budget=1500)` — `root`/`max_depth`/`context_filter` mirror `inspect_scene` exactly so the agent's mental model transfers.
- `attr_manifest(node, classes=("point","prim","detail"), max_samples=4, token_budget=1500)` — `classes` selects attribute owners; `"vertex"` is opt-in (V0, §5).
- `parm_manifest(node, depth=0, non_default_only=True, include_expressions=True, token_budget=1500)` — `depth=0` = the node itself; `>0` recurses children. `non_default_only=True` is the default because *touched* parms are the grounding signal.
- `error_manifest(root="/", max_depth=3, severity=("error","warning"), token_budget=1500)`.

`token_budget` default `1500` is a design choice (OPEN DECISION 4 governs per-call vs per-turn), tunable by the builder within the ladder contract.

### 2. Common return envelope (frozen)

Every manifest returns, at minimum:

```
{
  "manifest": "graph" | "attr" | "parm" | "error",
  "root": "<hou path or selection sentinel>",
  "served_tier": "samples" | "names" | "counts",
  "token_budget": <int>,
  "token_estimate": <int>,          # len(json.dumps(payload)) // 4, MUST be <= token_budget
  "counts": { ... },                # ALWAYS present — the floor tier is never dropped
  "dropped": { ... },               # what the served tier omitted vs. the tier above; {} at top tier
  "data": [ ... ]                   # names or typed samples per served_tier; absent at "counts" tier
}
```

`counts` is **always** populated (it is the floor and the cheapest true answer). `data` carries names (`served_tier="names"`) or typed samples (`served_tier="samples"`). `dropped` names the delta — a budget step-down, e.g. `{"reason":"budget","attrs_named":40,"attrs_sampled":0,"omitted_sample_classes":["prim","detail"]}`, **or** a within-tier element-cap step-down, e.g. `{"reason":"element_cap","names_included":50000,"total":128000,"omitted":78000}`. `dropped.reason ∈ {"budget","element_cap","node_cap","budget_below_floor"}` (§3).

### 3. The degradation ladder (the deliverable's spine)

Three tiers, richest first — but **built bottom-up, never top-down.** The manifest does **not** serialize the richest tier and measure-then-discard: on a wide scene that would first materialize the entire structure (the exact unbounded traversal this spec faults `inspect_scene`'s `network_tree` for — `introspection.py:305-366`, `_walk` bounded only by `max_depth`, no node ceiling), bounding the *return* size but not the *traversal cost or peak memory*. Instead it **guards before work**, the way `_geometry_summary` does (`is_large = pt_count > _LARGE_GEO_THRESHOLD` at `introspection.py:98` gates sampling *before* any sample array is built, `:110`) — not measure-then-discard *after*. The build order is:

1. **`counts` (floor — built first, always).** A single **cheap aggregate walk** accumulates aggregate **integers only** — node_count per context; attr counts per class; parm count + non-default count; error/warning counts per severity — **never materializing a names or samples record.** This is the only full traversal, and it costs O(1) memory per element (counters, not records). It is itself bounded by a hard **node/element-visit cap** — `MANIFEST_ELEMENT_CAP`, default `50_000`, a builder-tunable constant in the spirit of `_LARGE_GEO_THRESHOLD=1_000_000` (`introspection.py:79`); if the walk hits the cap it stops and stamps `dropped.reason="node_cap"` with the partial-vs-total it could confirm. `counts` fits any realistic budget; if even `counts` exceeds `token_budget`, the manifest returns `counts` anyway with `dropped.reason="budget_below_floor"` (honest over-floor signal — the agent asked for less than the truth costs).
2. **`names` (added only while budget AND cap remain).** Starting from `counts`, the manifest appends name/path/key strings **one element at a time, in a deterministic order**, re-checking the running `len(json.dumps(payload)) // 4` estimate against `token_budget` after each append, and **stopping the instant the next name would exceed budget OR the element cap is reached.** It never builds the full name list up front, so a wide scene never fully materializes here. If it stopped early it stamps `dropped` (`{"reason":"budget"|"element_cap","names_included":N,"total":T,"omitted":T-N}`) and stays at `served_tier="names"` — a **capped-but-complete** tier (see the reconciled rule below).
3. **`samples` (added only while budget AND cap remain).** The same incremental discipline applied to typed samples per already-named element (attribute values / parm values / error messages), sample cap = `max_samples` (attr) or a per-axis default. The large-element guard mirrors `_geometry_summary`'s **pre-count skip** — decided *before* a sample is read, recorded as a **tier step-down**, never a silent skip. Stops the instant the next sample would exceed budget or the cap is reached; stamps `dropped`.

The manifest serves the **richest tier it could fully build within budget and cap**, and stamps `served_tier`. Because names and samples are grown incrementally under the cap and the only full walk accumulates integers, **peak memory and traversal-materialization are bounded by `MANIFEST_ELEMENT_CAP`, not by scene size** — that is the differentiator the Mission promises ("bounded reads the agent can afford to call every turn").

**Rule (frozen, reconciled): the ladder degrades whole tiers AND bounds every rich tier to a hard, deterministically-ordered element cap; within the served tier, every *included* element is complete.** No half-serialized element, no truncated array presented as whole. "Whole tiers, never partial" now reads: the served tier is **complete for the capped element set it includes** — the cap (and any budget step-down) is always named in `dropped`, never a silent truncation. A `counts`-only or capped-`names` answer is a correct, honest answer, never an error. This is the same truth discipline as `spec-D`'s "a claim the catalog can't back is a finding, not a footnote."

### 4. Thread posture (the Spike 3.1 lesson, applied)

**Cited lesson:** `docs/sprint3/spike_3_1_design.md §2.8` and the `TopsEventBridge` docstring (`python/synapse/host/tops_bridge.py`, per the design at `:98-103`): *"PDG event callbacks may fire on a non-main thread… The bridge's internal handler is thread-safe (no `hou.*` calls inside the handler)… The cognitive layer must use a thread-safe delivery primitive."* And `§2.8`: *"`hou.*` calls inside the bridge: only allowed in `warm_all()` … on the calling thread — typically main thread. Nowhere inside the event handler."*

**Applied to the manifests (frozen):**

- A manifest's `hou.*` traversal (`node.geometry()`, `node.children()`, `node.parms()`, `node.errors()`, …) runs **on Houdini's main thread only**, marshalled through the host `main_thread_executor` seam the Dispatcher already injects (`cognitive/tools/__init__.py` example). The cognitive tool function itself is pure-Python, zero-`hou` — identical to `inspect_stage.py` (which composes a script and hands it to an injected transport, never importing `hou`). This keeps the cognitive-boundary lint (`tests/test_cognitive_boundary.py`) green.
- **A manifest MUST NOT be invoked from inside a PDG/scene event callback thread.** If a future consumer wants `error_manifest` to fire *in response to* a cook-error event (a `TopsEvent`), the event handler drops a request onto a thread-safe queue (`queue.Queue.put_nowait`, per Spike 3.1 §2.8) and the **main-thread executor** services the manifest — the handler thread never calls the manifest directly, because the manifest reads `hou.*`.
- The manifests hold **no** long-lived subscription and register **no** event handler — they are one-shot reads. The Spike 3.1 cleanup/idempotency contract (handler-identity teardown) therefore does not apply; the *thread-safety* half does.

### 5. Symbol provenance (V0/V1 — DoD-6)

Per CLAUDE.md safety rule 15 and the blueprint's provenance tiers, **no unprobed `hou.*` symbol is asserted as fact.** The manifests are built almost entirely from symbols already exercised in shipped `introspection.py`, so those are **V1** (verified in shipped code, this session). Anything new is **V0 — probe at runbook step 9** (never emit before the probe).

| Symbol | Tier | Evidence / action |
|---|---|---|
| `hou.node(path)`, `node.path()`, `node.name()`, `node.children()`, `node.type().category().name()` | **V1** | `introspection.py:293,318,341-343,347,310` |
| `hou.selectedNodes()`, `node.inputs()` | **V1** | `introspection.py:255,271` |
| `node.geometry()`, `geo.points()`, `geo.prims()` | **V1** | `introspection.py:90,96,97` |
| `attr.name()`, `attr.dataType()`, `attr.size()`, `attr.strings()`, `attr.floatListData()` | **V1** | `introspection.py:104-124` |
| `node.warnings()`, `node.errors()` | **V1** | `introspection.py:180,184` — the whole of `error_manifest` |
| `node.stickyNotes()` | **V1** | `introspection.py:330` (graph_manifest artist-notes, optional) |
| point/prim/detail attribute accessors (the `attrs` iterables feeding `_attr_info`) | **V1 (category)** | `introspection.py:100-130` + `GeoSummary.{point,prim,detail}_attribs` (`shared/types.py:216-218`) |
| **vertex** attribute accessor (e.g. `geo.vertexAttribs()`) | **V0** | No `vertex_attribs` field on `GeoSummary`; not exercised in `introspection.py`. `attr_manifest(classes=…"vertex")` **must probe before emit** (runbook step 9). |
| parm accessors beyond `_modified_parms`'s set — specifically `parm.isAtDefault()`, `parm.expression()`, `parm.keyframes()`, `parm.rawValue()` | **V0** | `inspect_node_detail` (`introspection.py:369`) was not read line-by-line this session; `_modified_parms` is referenced (`:261`) but its accessor set is unconfirmed here. `parm_manifest` **must confirm each accessor** against the shipped parm reader (or probe) before emit. |
| `hou.topNodeTypeCategory()` and any TOPs-specific traversal | **out of scope** | manifests do not special-case TOPs; TOPs perception is Spike 3.x / D-track. |

### 6. Non-dependency on USD schema — the Michael Gold RFC stays off the critical path (frozen)

The Michael Gold RFC gate row (`docs/H22_AGENT_HARNESS.md:60`) governs *"any USD-schema write."* **No manifest writes or requires a USD schema.**

- `graph_manifest`, `parm_manifest`, `error_manifest` read the **node graph / parameter / error** surface — pure `hou.Node`/`hou.Parm` reads, no USD at all.
- `attr_manifest` reads **`hou.Geometry` attributes** — SOP-level intrinsics, not USD prim schema.
- For `/stage` grounding, the manifests report USD structure that **already exists on the live stage** (the same data `synapse_inspect_stage` surfaces as `usd_prim_paths` on a `StageAST`) — a **read** of authored composition, never a write of new `synapse:*` schema. The RFC's subject (authoring new schema) is never touched.

**Consequence (frozen):** the Michael Gold RFC can remain unratified indefinitely and G5 still ships and passes DoD-1…DoD-7. Any builder tempted to "just add a `synapse:*` attribute so the manifest can round-trip provenance" is **out of scope** — that is RFC territory, off this critical path (§ Non-goals).

### 7. Placement + registration (frozen)

- **Implementation:** four modules under `python/synapse/cognitive/tools/` (e.g. `graph_manifest.py`, …), each exporting the pure-Python `<name>(**kwargs)` function **and** an `<NAME>_MANIFEST_SCHEMA` (Anthropic tool-use schema), mirroring `inspect_stage.py`'s `INSPECT_STAGE_SCHEMA` + `inspect_stage` pair. Zero `hou` in the import graph.
- **Registration (mirror `synapse_inspect_stage`, NOT a `_tool_registry.py` tuple):** for each manifest add (a) a `Tool(name, description, inputSchema)` descriptor to `list_tools()` (`mcp_server.py:762-766`), (b) a dedicated `call_tool()` branch that hands the call to a cognitive `Dispatcher` (`mcp_server.py:800-801`), and (c) an entry in that `Dispatcher(tools={...})` dict (`mcp_server.py:569-571`). This is the exact seam `synapse_inspect_stage` uses; it is **not** in `_tool_registry.py` (grep returns nothing at `314acd6`), so the manifests add **no** `_tool_registry.py` rows and no `(…, True, False, True)` tuple. Read-only / non-destructive / idempotent is structural (the tool function never mutates), matching inspect_stage — dispatched by its own `call_tool` branch, never the mutating bridge path. `hou.*` reaches Houdini's main thread through that Dispatcher/transport seam (inspect_stage's configured `execute_python` round-trip runs inside Houdini's main thread), satisfying DoD-4 with zero `hou` in the cognitive import graph.
- **Shared budget/ladder helper:** one small pure-Python module (e.g. `cognitive/tools/_manifest_budget.py`) holding the `//4` estimator (reused from the `shared/types.py:227` idiom — do not re-derive), the three-tier serializer, and the envelope builder. All four manifests call it. **Do not** duplicate the ladder four times.

---

## What exists vs. what the manifests add

| Concern | Shipped `synapse_inspect_*` | What a manifest adds |
|---|---|---|
| Topology overview | `inspect_scene` recursive tree, `max_depth`-bounded, **no node ceiling** | `graph_manifest`: same traversal, **token-budgeted**, degrades tree → names → counts |
| Selection topology | `inspect_selection`, cap 50, full per-node detail | folded into `graph_manifest` (selection sentinel `root`), budget-bounded |
| Geometry attrs | `_geometry_summary` / `GeoSummary`, ad-hoc `max_samples`, silent large-geo skip | `attr_manifest`: **declared** sample tier, large-geo skip becomes a **stamped tier step-down**, adds vertex class (V0) |
| Parameters | `inspect_node` full dump, no ceiling | `parm_manifest`: `non_default_only` default, budget-bounded, subtree `depth` |
| Errors | `_node_issues` + `inspect_scene.issues` (incidental) | `error_manifest`: **first-class** severity-filtered static error/warn manifest, budgeted |
| Token discipline | one dataclass targets "<100 tokens"; tools otherwise unbounded | **budget-as-contract** on every call + honest degradation ladder + served-tier stamp |
| USD schema | `inspect_stage` reads authored stage | **unchanged** — manifests read, never author; RFC off critical path (§6) |

**The manifests do not replace the inspectors.** Deep single-node debugging still wants `inspect_node`'s full dump; the manifests are the *grounding* layer — bounded reads the agent can afford to call every turn.

---

## DoD-per-deliverable

| # | Deliverable | Done when |
|---|---|---|
| 1 | `graph_manifest` | registered read-only; budget honored; ladder tree→names→counts stamped; V1 symbols only (or V0 probed); mirrors `inspect_scene` params |
| 2 | `attr_manifest` | registered read-only; budget honored; ladder samples→names→counts; large-geo skip is a stamped step-down; `"vertex"` class gated behind a V0 probe |
| 3 | `parm_manifest` | registered read-only; budget honored; `non_default_only` default; each parm accessor V1-confirmed or V0-probed before emit |
| 4 | `error_manifest` | registered read-only; budget honored; static `errors()`/`warnings()` only (no cook replay — D-track boundary held); severity filter works |
| 5 | `_manifest_budget` helper | single source of the `//4` estimator (reused from `shared/types.py:227`), three-tier serializer, envelope builder; no duplicated ladder |
| 6 | `tests/test_grounding_manifests.py` | budget-never-exceeded; ladder-degrades-under-shrinking-budget; tier-stamp present; one happy path per manifest; no module-level fake-`hou` |
| 7 | Dispatcher registration + schemas | four `list_tools()` `Tool(...)` descriptors + four `call_tool()` branches + four `Dispatcher(tools={...})` entries, mirroring `synapse_inspect_stage` (`mcp_server.py:762-766/800-801/569-571`) — **no** `_tool_registry.py` rows; four `_MANIFEST_SCHEMA` objects kept in sync with signatures |

Each deliverable is one FORGE sprint gated by its own tests; no manifest ships before its budget + ladder tests are green. Suite floor (`harness/verify/suite_baseline.json`) holds throughout.

---

## Non-goals (explicit)

- **No USD-schema authoring.** No `synapse:*` attribute writes; no dependency on the Michael Gold RFC. Grounding *reads*; it never authors composition. (§6.)
- **No dynamic cook/diagnostic truth.** No perturbation, no recook prediction, no callback replay, no `cookCount`/`needsToCook`/`isTimeDependent` — that is the D-track (`spec-D-diagnostic-truth.md`). `error_manifest` is static error/warn state only. (OPEN DECISION 2.)
- **No new transport, no new panel surface, no event subscription.** Manifests are one-shot reads on the existing Dispatcher/registry seam. No `TopsEventBridge` wiring, no long-lived handler (the Spike 3.1 *cleanup* contract does not apply; only its thread-safety half does). (§4.)
- **No replacement of the shipped inspectors.** `inspect_scene/_node/_selection/_stage` stay as-is; the manifests are additive. No edits to `introspection.py`'s existing functions beyond optionally *reading* its helpers.
- **No rigging / KineFX / APEX scope.** Structurally refused (blueprint §6.1) regardless of who asks.
- **No `tiktoken` / new dependency.** Budget estimation reuses the `len(json.dumps(...)) // 4` idiom already in `shared/types.py`.
- **No per-turn budget accounting** unless the human rules it in (OPEN DECISION 4) — this spec is per-call.

---

## Style & traps (binding)

- **Truth contract, always:** a manifest that degrades says so (`served_tier` + `dropped`); it never presents a truncated structure as complete. Honest-false ethos, same as `checks.py`.
- **Reuse, don't rebuild:** the estimator (`shared/types.py:227`), the traversal idioms (`introspection.py`), the port pattern (`inspect_stage.py`), the `GeoSummary` attr model (`shared/types.py:210`). Building a fifth token counter or a parallel inspector is scope creep — redirect.
- **Verify-before-emit:** every V0 symbol in §5 is probed at runbook step 9 before a line of it is emitted (CLAUDE.md rule 15; `phantom_clean` catches it after the fact — get it right before).
- **Cognitive boundary:** zero `hou` under `synapse/cognitive/**`; `hou.*` lives behind the injected main-thread executor. `tests/test_cognitive_boundary.py` must stay green.
- **MODE A now:** this is paper. The build is MODE B, gated on `drop.json` + a gatewarden `ALLOW`. No source is written under this spec until that gate opens.

---

*Leg-0 paper artifact, assembled under MODE A against HEAD `314acd6` / H21.0.671. Merge-to-main is the human gate that makes it binding.*
