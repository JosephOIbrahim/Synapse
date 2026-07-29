# S1 — THE INVENTORY

**Leg** S1 · **Harness** FORENSIC-01 · **Run** 2026-07-27 · **Branch** `forensic/s1-tool-inventory`
**Model** `claude-opus-5[1m]` · **Mode** READ-ONLY, writes confined to `harness/notes/**`
**Governed by** `harness/AGENT_CONSTITUTION.md`

> **What does SYNAPSE actually DO today, per tool, mapped to a real artist task?**
> Not what it registers. Not what its docstring promises. What an artist could sit down and use
> this afternoon.

---

## 0 · The counts

```
WORKS         25
PARTIAL       90
SCAFFOLD       5
UNREACHABLE    3
UNKNOWN        5
              ---
              128   registered tools
```

> **Three numbers moved because controls were run, and that is the point.**
> `synapse_recall` was provisionally UNREACHABLE on a 1800s hang — re-run alone it returned
> fast, so the hang was concurrency-induced and the verdict was **withdrawn to PARTIAL**.
> `synapse_scout`'s control produced a **mechanism** instead of a hang. `synapse_metrics`
> went PARTIAL → WORKS once actually called. The verdicts that *didn't* move survived the
> same test, which is the only reason to trust them. See §3.

**Producer:** `harness/notes/forensic/_s1_classify.py` → `s1_classification.json`.
Every integer below traces to a script in `harness/notes/forensic/`. No number was hand-entered.

**Read the shape, not the total.** 90 of 128 are PARTIAL, and they are PARTIAL for one reason
repeated 90 times: *the code does real work and nothing has ever watched it do that work on a
host.* That is not 90 separate defects. It is one defect with 90 instances.

---

## 1 · First correction: it is 128 tools, not 120

The banner in `CLAUDE.md` says **120 MCP tools registered**. That is the size of `TOOL_DEFS`.
The surface an MCP client actually sees is **128**:

| Source | Count |
|---|---|
| `python/synapse/mcp/_tool_registry.py` `TOOL_DEFS` | 120 |
| `mcp_server.py:946` `_GROUP_INFO_TOOLS` (local knowledge, no Houdini) | 6 |
| `synapse_inspect_stage` (local dispatch branch, `mcp_server.py:927`) | 1 |
| `synapse_scout` (local dispatch branch, `mcp_server.py:936`) | 1 |
| **registered total** | **128** |

**Confirmed live.** This session's own MCP tool listing enumerates exactly 128 `mcp__synapse__*`
tools — 21 `cops_*`, 40 `houdini_*`, 50 `synapse_*`, 17 `tops_*`. Static census and live wire agree.

*Not a contradiction of the seed fact — the seed is right about `TOOL_DEFS` and right about the
banner. It is a drift note: the number that gets quoted is 8 short of the number that gets served,
and the classification surface is 128.*

Producer: `_s1_enumerate_tools.py` → `s1_tool_census.json`.

---

## 2 · The finding that governs every other verdict

`tests/conftest.py:132-135` plants a **canonical fake `hou`** into `sys.modules` at collection
time whenever a real one is not resident.

```python
if "hou" not in sys.modules:
    sys.modules["hou"] = _build_canonical_hou()
```

Three consequences, and they are large:

**1. `import hou` always succeeds under plain `pytest`.**
So `pytest.importorskip("hou")` — the idiom that *looks* like a live gate — gates nothing in this
suite. The Solaris conftest says so in writing (`tests/solaris/test_live_wiring.py:15-22`): *"a bare
`pytest.importorskip("hou")` is NOT a valid gate in this suite."*

**2. The only honest gate is a host-IDENTITY probe.** The planted fake carries
`__synapse_canonical__`; real Houdini does not.

**3. Measured against that gate:**

```
286   test files
101   build a mock hou
  2   use importorskip("hou")   <- gates nothing
  8   probe host identity
  5   are host-behaviour tests (the other 3 are the planter + 2 meta-guards)
```

**Five of 286 test files can disagree with the live host.**

- `tests/solaris/test_live_wiring.py`
- `tests/test_h22_cops_solver_live.py`
- `tests/test_h22_setdressing_live.py`
- `tests/test_guards.py`
- `tests/test_introspection.py`

Producer: `_s1_test_honesty.py` → `s1_test_honesty.json`. The script voids its own numbers if the
planting block ever leaves `conftest.py`.

**This is why 90 tools are PARTIAL.** A green suite of 4,873 tests is a real achievement in
API-shaping, payload contracts, and regression pinning. It is not evidence that a tool moves
Houdini. The brief's warning — *"no tool marked WORKS on the strength of a docstring or a passing
mock test"* — turns out to describe the default condition of the suite, not an edge case.

---

## 3 · UNREACHABLE — 4

The brief defines UNREACHABLE as *"registered but no path invokes it."* Taken literally the answer
is **zero**: all 120 registry `command_type`s have a live handler registration
(`_s1_reachability.py`, AST-walked, diffed both ways). The positive control fired — the same diff
found **7 dead handlers no tool reaches** (`assess_render_ready`, `get_help`, `matlib_bind`,
`route_chat`, `solaris_shotsetup_karma_xpu`, `tops_pause_cook`, `tops_resume_cook`), which proves
the check runs in both directions rather than passing vacuously.

So this leg uses the brief's **operative** sense — *cannot be reached to useful effect* — and each
row states which kind it is.

### `synapse_router_stats` — dead-return

Called live. Returned `{"error":"Router not initialized"}`.

The static reason is exact: `self._router` is constructed in **one** place —
`_handle_route_chat` (`handlers.py:1605-1608`) — and `route_chat` is one of the seven handlers **no
MCP tool dispatches to**. Only the Houdini panel sends it (`panel/chat_panel.py:799,903`). Reached
from `/mcp` alone, the attribute never exists and the tool is structurally incapable of returning
data.

*Collateral:* `synapse_metrics` guards on `hasattr(self,"_router")` at `handlers.py:1500` and
therefore always emits `router_stats=None` on this path — silently.

### `synapse_inspect_scene` — never-returns

Called live twice. First call (`max_depth=2`) ran **1800s** and was aborted by the MCP idle timeout.

**Then the control**, because a hang under concurrent dispatch proves nothing: re-run **alone**,
nothing else in flight, `max_depth=1`. It ran the full **1800s and was aborted with no response** —
identical to the first call — while `synapse_ping` answered instantly in the same session and the
bridge stayed healthy throughout.
**The concurrency explanation is refuted, and the isolated run did not merely block: it never
returned.** It does not terminate on a depth-1 walk or a depth-2 one.

**The product's own telemetry agrees, unprompted.** `synapse_metrics` returns
`synapse_panel_inline_slow_total{slowest_tool="synapse_inspect_scene"}` — SYNAPSE already knows
which tool is its slowest.

> **Correction, because it was load-bearing.** An earlier draft of this report called this a
> "9-node empty scene," on the strength of `synapse_live_metrics` (`total_nodes 9`, obj/sop/lop
> all 0). `synapse_metrics`, called later in the **same session**, reports
> `synapse_scene_nodes_total 16122` with 3 warnings. The two surfaces disagree by three orders of
> magnitude and this leg did not resolve which is right. **The "trivial scene" framing is
> withdrawn** — the walk may be large, which makes the `node.errors()` candidate below *more*
> plausible, not less. The hang stands; the rhetorical flourish about scene size does not.

This is the tool `synapse_group_scene` explicitly instructs the agent to call first: *"Always
inspect before mutating — use `synapse_inspect_node` or `synapse_inspect_scene` first."* The
documented entry point to every scene workflow does not return.

*Mechanism deliberately not root-caused here — that is S2's job. A candidate worth carrying:
`_node_issues` calls `node.errors()` (`introspection.py:184`) on every node it walks, which forces
cooks. Untested, so it stays a candidate.*

### `synapse_recall` — **verdict withdrawn**

Provisionally UNREACHABLE on a 1800s hang. Then the control: re-run **alone**, it returned
**fast**, with real content — the RAG augmentation fired correctly, confidence 0.8125, correct
punycode parm names including `xn__inputsintensity_i0a`. **The hang was concurrency-induced and
the UNREACHABLE verdict is withdrawn.** Reclassified PARTIAL.

What the control found instead is more interesting than the hang: the live response carries
`{"error":"Memory not available","found":false}` beside `"knowledge_found":true`. **The RAG seam
works; the memory lookup it exists to augment does not** — in a session where
`synapse_memory_status` reported `entries_total 19` and `synapse_context` returned 23 memories.
*Three memory tools, three different answers about whether memory exists.*

### `synapse_scout` — dead-return, **mechanism found**

Ran 1800s, aborted. Then re-run **alone**, single trivial symbol query (`k=2`). It blocked past
120s — and then **returned an error**:

```json
{"error":"ProgrammingError",
 "message":"SQLite objects created in a thread can only be used in that same thread.
            The object was created in thread id 51668 and this is thread id 65704."}
```

**Scout does not hang forever. It is slow and then fails on SQLite thread affinity** — its
retrieval store's connection is created on one thread and used on another.

The control was run only to rule out concurrency. It produced the mechanism instead. This is the
one hang in this leg that is no longer a mystery handed to S2.

Worth naming plainly: **`CLAUDE.md` rule 15 makes scout the mandatory pre-flight before emitting
any unfamiliar `hou.*`/`pdg.*`/`pxr.*` call** — the front-line defence against this project's
self-declared #1 failure class, phantom APIs. It fails on a threading bug.

Worth naming plainly: **`CLAUDE.md` rule 15 makes scout the mandatory pre-flight before emitting
any unfamiliar `hou.*`/`pdg.*`/`pxr.*` call.** The project's own anti-phantom defence did not answer.

---

## 4 · SCAFFOLD — 5

Builds structure, never executes. The brief named three and asked for the others.

| Tool | Status |
|---|---|
| `cops_reaction_diffusion` | self-reported — named in brief |
| `cops_pixel_sort` | self-reported — named in brief |
| `cops_bake_textures` | self-reported — named in brief |
| **`cops_growth_propagation`** | **found this leg** |
| **`cops_procedural_texture`** | **found this leg** |

A fourth self-reporting marker turned up in `cops_create_copnet`, but reading it clears the tool:
its docstring is honest that it performs no cook, and its *name* promises only the network — which
it delivers. Classified WORKS. **Self-report is a lead, not a verdict.**

Producer for the marker scan: `_s1_evidence_index.py` (`self_reported_scaffold`).

---

## 5 · WORKS — 24, and what that word is doing

Every WORKS row carries either a live call made this session or a live-gated test that cannot pass
against the fake.

### 5a · Exercised live through the bridge (Houdini 22.0.368, this session)

`synapse_ping` · `synapse_health` · `synapse_doctor` · `houdini_scene_info` ·
`synapse_memory_status` · `synapse_list_recipes` · `synapse_context` · `synapse_knowledge_lookup` ·
`synapse_group_scene` (+5 sibling group tools, derived — same dict-lookup path)

Two deserve individual mention.

**`synapse_doctor` is the best-behaved tool in the inventory.** It ran 10 checks and reported
**7 ok / 2 fail / 1 skipped** — surfacing its own bad news unprompted: an install-stamp divergence
(tree says 5.35.1, stamp says 5.23.0) and `MonetaMemory` not registered with the USD runtime. Law 3
honoured on a live run. Most tools in this repo would have returned a summary.

**`synapse_list_recipes` returned 62 real recipes** — camera bodies with actual sensor dimensions
for 8 cinema cameras, three-point lighting with a 4:1 ratio, destruction and vellum chains,
turntables with AOVs. This is the most substantial and most undersold asset in the product, and it
is not a tool so much as a library.

### 5b · The Solaris family — the one family with honest evidence

`synapse_solaris_component_builder` · `synapse_solaris_scene_template` ·
`synapse_solaris_set_purpose` · `synapse_solaris_import_megascans`

The brief notes these five were UNREACHABLE for an entire phase with passing tests. **What happened
next is the most important engineering fact in this inventory:** the mock fixtures were *deleted*.

`tests/solaris/conftest.py:11-21` cites Constitution Law 1 by name and removes them. What replaced
them gates on host identity, skips honestly off-host, and executes under hython 22.0.368. That
tier then **found `F7` — `set_purpose` reporting success having set nothing** — and `F9` —
`import_megascans` raising `PermissionError` on every invocation. Both repaired.

The mock said green while the tool set nothing. Deleting the mock is what found it.

*`SR1.json` receipt: green, suite 4841 → 4873 passed, 0 failed, **+9 skipped** — those skips are
this live tier correctly standing down off-host.*

### 5c · COPs primitives (agent-classified, unrefuted)

`cops_create_network` · `cops_create_copnet` · `cops_create_node` · `cops_connect` ·
`cops_set_opencl` · `cops_read_layer_info`

Backed by live hython instantiation probes on 22.0.368 recorded in
`docs/reviews/h22-cop-audit-verification.md`. **Carried unrefuted** — see §8.

---

## 6 · The second axis — which of these would an artist reach for?

This is the part that matters. A tool can work perfectly and serve nothing.

### WORKS and PARTIAL, grouped by what the artist is actually doing

| Artist task | WORKS | PARTIAL | Would reach for | Thin? |
|---|---:|---:|---:|---|
| scene-assembly | 7 | 18 | 25 | — |
| **agent-internal** | **12** | 13 | 1 | *inverted* |
| debugging | 1 | 16 | 15 | **thin** |
| look-dev | 3 | 9 | 12 | — |
| **rendering** | **0** | 13 | 12 | **thin** |
| **caching** | **0** | 8 | 8 | **thin** |
| **lighting** | **0** | 4 | 4 | **thinnest** |
| pipeline-admin | 1 | 7 | 7 | **thin** |
| **comp** | **0** | 2 | 1 | **thinnest** |

### The one-sentence version

> **Half of everything that WORKS (12 of 24) is a tool the agent uses to orient itself, and exactly
> one of those 25 agent-internal tools is something an artist would ever reach for.**

Read the WORKS column down the artist-facing rows: **rendering 0, lighting 0, caching 0, comp 0.**

SYNAPSE can reliably tell you what frame you are on, what it remembers, whether it is healthy, and
what recipes exist. Those are proven. **Every tool that would put an image on screen or a light in
a scene is unproven on a host.**

That is not the same as broken — 13 rendering tools and 4 lighting tools contain real, careful,
often *good* code. `houdini_render`'s bounded wrapper has poll tokens, single-flight, and a cold-XPU
kernel-cache refusal, and its docstring is unusually honest that the UI still freezes on Indie.
`houdini_set_parm` rejects NaN/Inf before they reach Houdini and corrupt a parm — that detail only
comes from having been burned. `houdini_assign_material` validates the prim pattern against the
real upstream stage and warns when it matches nothing.

**It means nobody has watched any of it work.**

### Where the artist value actually concentrates

Three things, and only three, look like they would save a working artist real time:

1. **`synapse_solaris_scene_template` / `component_builder` / `import_megascans`** — live-proven,
   and the closest thing in the product to *twenty minutes off every shot setup*.
2. **The 62 recipes** — real domain knowledge, correct lighting law, real sensor data.
3. **`synapse_solaris_assemble_chain`** — auto-wiring unwired LOP nodes into canonical order. This
   is the single highest-leverage tool in the inventory *and it has no host evidence at all*
   (3 tests, mock/registration only, not in the live tier). **The most valuable claim in the product
   is the least verified.**

### Where an artist would not reach, honestly

`cops_reaction_diffusion` is a Gray-Scott solver. `cops_growth_propagation` is DLA. `cops_pixel_sort`
is a motion-design effect. All three are SCAFFOLD, and even repaired, a lighting TD on a deadline
has never wanted one. They are five entries on a feature list and zero minutes saved.

---

## 7 · Notable individual findings

**`houdini_undo` and `houdini_redo` do not marshal to the main thread.** Neither calls
`run_on_main`, unlike essentially every sibling handler (`handlers.py:882`; the `redo` case found by
the batch-3 reader). Undo grouping is the product's headline safety claim — *"every action
reversible and recorded"* — and its two entry points are both unproven on the host and
unmarshalled.

**`houdini_create_node` is the most-tested tool in the product (32 tests) and has no
host-behaviour evidence.** 14 of the 32 build a mock; none carries the host-identity gate. If one
tool deserved a live test, it is the one every other tool is built on.

**Ten tools have zero tests naming them anywhere:** `houdini_configure_light_linking`,
`houdini_create_point_instancer`, `houdini_manage_collection`, `houdini_manage_variant_set`,
`houdini_reference_usd`, `houdini_set_payload_loadstate`, `houdini_shot_render_ready`,
`synapse_configure_render_passes`, `synapse_live_metrics`, `synapse_memory_write`.

`synapse_configure_render_passes` is the sharpest of these: a genuinely useful 17-entry AOV preset
table, emitted as generated Python that calls `editableStage()` — which returns `None` outside a LOP
cook — with **no test anywhere**.

**`synapse_live_metrics` returns real data and took over 120s to do it.** A metrics call that
outlives the question is not a metrics call.

**`synapse_write_report` is the one handler explicitly designed around this leg's failure mode** —
pure file I/O, deliberately *off* the main thread, so it survives a blocked one. Someone understood
the problem; the fix is confined to one tool.

---

## 8 · What this leg did not establish

Stated plainly, because a document that hides a gap is worse than one that names it.

**The adversarial refutation pass never ran.** The 8-agent fan-out died on a session token limit
after 2 of 10 agents completed. Those 2 produced 31 carried verdicts; the crucible pass that would
have attacked every WORKS and PARTIAL claim in them **never executed**. Their verdicts are tagged
`agent-b1/b3 (UNREFUTED)` in `s1_classification.json` and were **not** upgraded on the way in.

**5 tools are UNKNOWN** for the same reason — nothing reached them:
`cops_stamp_scatter`, `cops_stylize`, `cops_temporal_analysis`, `cops_to_materialx`, `cops_wetmap`.
*What is needed:* open each handler and its callees, decide whether it produces the artefact its
name promises, and check whether any test naming it escapes the fake `hou`.

**82 of 128 tools mutate and were deliberately not exercised.** This leg is read-only against the
artist's live session. Only read-only tools were called.

**The live scene was empty** — `untitled.hip`, 9 nodes, no USD stage, no TOP network. That bounds
what any live probe could reach: `houdini_stage_info` could only prove its refusal path, and all 17
TOPS tools had nothing to run against.

**All three hangs are now controlled** — and the control changed an answer. `synapse_recall`
returned fast in isolation and its UNREACHABLE verdict was **withdrawn**; `synapse_inspect_scene`
and `synapse_scout` both blocked again under the same test and stand. *The one number that moved in
this report moved because a control was run, which is the only reason to trust the ones that
didn't.*

**No suite evidence is claimed.** This leg ran read-only; per Constitution Article V it cannot
claim suite evidence and does not.

---

## 9 · Artifacts

| File | What it holds |
|---|---|
| `s1_classification.json` | all 128 verdicts — class, tier, provenance, evidence, anchor, artist task |
| `s1_tool_census.json` | the 128 registered tools + source of each |
| `s1_reachability.json` | command_type ↔ handler diff, both directions, 7 dead handlers |
| `s1_evidence_index.json` | per-tool handler sites, cook/build/scaffold tells, test inventory |
| `s1_test_honesty.json` | the fake-`hou` measurement |
| `s1_handler_digest.txt` | source of the 88 handlers read for this leg |
| `_s1_*.py` | the producers — every integer above traces to one |

---

## 10 · The sentence

> SYNAPSE registers 128 tools, and the 24 that are proven are mostly the ones it uses to talk to
> itself. Every tool that would put an image on screen — 13 rendering, 4 lighting, 2 comp — is
> unproven on a host, not because the code is bad but because 5 of 286 test files are capable of
> disagreeing with Houdini.
