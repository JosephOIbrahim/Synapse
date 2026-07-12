# PORT WAVE MANIFEST — frozen spec (G1)

**`docs/PORT_WAVE_MANIFEST.md`** · Repo: `C:\Users\User\SYNAPSE` (branch per orchestrator). All paths repo-relative.
**Status: PROPOSAL — MODE A paper.** This is the Leg-0 design artifact that makes `h22-port-wave` (G1) executable. It becomes binding only when a human **merges it to main** (the harness playbook's Leg-0 gate) AND `harness/state/drop.json` exists (MODE B). Until both, every wave dispatch REFUSES at the gate — verified: `.claude/workflows/h22-port-wave.js:4` whenToUse = "MODE B only (drop.json exists) and docs/PORT_WAVE_MANIFEST.md is merged."

**Governing gate:** merge-to-main, **per wave, human** (`docs/H22_AGENT_HARNESS.md:55` gate registry — "Merge-to-main | no file — always human, per commit" — whose §2 header states that table "renders blueprint §8 made mechanical"; `docs/H22_AGENT_HARNESS.md:73` port-wave exit = "merge the worktree"). No agent — gatewarden, forge, assayer, crucible — merges. The workflow returns `MERGE_READY`; the human merges. `[The blueprint is now committed at docs/SYNAPSE_H22_GAP_BLUEPRINT.md §8 (gate registry: "Merge-to-main | Every wave, every doc PR | Human, per commit"); the playbook cited above mechanizes it.]`
**Relay leg:** **Leg 3** (opened by `harness/state/drop.json`, which arms Legs 2–3 — `docs/H22_AGENT_HARNESS.md:53`), designated **first priority** by dispatch. `[VERIFIED against docs/SYNAPSE_H22_GAP_BLUEPRINT.md §7 Leg 3 ("Priority: G1 port waves → G4 MCP surface → G5 grounding tools → G9 gate → G6 numbers …") — the blueprint is now committed and confirms G1 port waves are Leg-3 first priority.]`

**Grounding (this dispatch, read-only):** HEAD `314acd6` (v5.22.0, 2026-07-10) · registry `python/synapse/mcp/_tool_registry.py` sha256[:16] `7487530001bea004` · target build per `CLAUDE.md` = Houdini 21.0.631 (the live H22 drop build is unknown until `drop.json` is written — that is Leg 1).

---

## OPEN DECISIONS (human rules; the rest of this manifest is complete either way)

**OD-1 — Wave granularity vs. the workflow's `wave` arg (naming + workflow scope).**
The `h22-port-wave` workflow accepts `wave` ∈ {scene, usd, render, tops, cops, memory} and does **one forge dispatch + one atomic commit per family** (`.claude/workflows/h22-port-wave.js:8`, forge instruction ":24-29" — "one atomic commit in the worktree"). But the brief targets **10–15 tools per wave**, and five of six families exceed 15 (scene 22, usd 20, tops 18, cops 21, memory 21 — derived below). Options:
- **(a) Family-sized waves.** Accept up to 22 tools in one commit; treat the ≤15 batches below as review checkpoints only. Zero workflow change. Cost: a 22-tool diff is hard to red-team in one crucible pass.
- **(b) Sub-waves + extend the enum.** Split into `scene-1/scene-2/…` and add those strings to the workflow's `wave` enum. Reviewable slices. Cost: a code edit to `.claude/workflows/h22-port-wave.js` — **outside scribe's write scope**; the human or forge must make it.
- **(c) Idempotent re-run.** Keep the family arg; the manifest instructs forge to port only the **next unported batch** and re-run the wave per batch. Cost: forge must detect already-ported tools each run (fresh worktree per dispatch has no memory of prior batches unless it reads the merged main).
- **Recommended: (b).** One commit of 22 tools defeats the "different agent reviews than builds" separation the harness is built on. The batch table below is authored so (b) is a drop-in: each sub-wave id is already assigned.

**OD-2 — Port target semantics: wrap the WS handler, or reimplement it?**
The port pattern (Inspector/Scout, verified at `mcp_server.py:461-635` / `:638-719`) moves a tool's **orchestration** into a cognitive Dispatcher tool with an **injected transport closure**; the Inspector's closure still does an `execute_python` WS round-trip into the Houdini process — the actual `hou` work is **not** reimplemented in the (hou-less) mcp_server process. For the bulk registry tools whose WS command handler already does the real `hou` work (`python/synapse/server/handlers*.py`), "port to Dispatcher" is ambiguous:
- **(a) Wrap.** The Dispatcher tool is a thin cognitive wrapper; the existing WS handler stays the execution primitive; only the `mcp_server.py` dispatch branch retires. Lowest risk; consistent with the workflow's "do not invent a new pattern."
- **(b) Reimplement.** Handler logic is re-authored as an in-process cognitive tool; the WS handler is eventually retired too. Larger scope; risks the exact "behavior drift" the crucible hostile pass hunts for (`.claude/workflows/h22-port-wave.js:51-56`).
- **Recommended: (a).** Flagged because it materially changes both wave scope and the adapter-retirement criteria (§Adapter Retirement below assumes (a); if (b) is chosen, the handler files join the retirement targets).

**OD-3 — Tools that must NOT become in-process Dispatcher tools.**
`synapse_propose_graph` / `synapse_instantiate_graph` route through the WS deliberately: propose's validator is a **live `hou` oracle** and both share the Houdini process's one `ProposalStore` (`mcp_server.py:722-730` — "No special-casing… they flow through TOOL_DISPATCH → send_command → WS like every other host tool"). `houdini_undo` / `houdini_redo` are pure transport verbs. Porting these to an in-process tool would break them. Options: **(a)** exclude from the port (leave on WS, document the exception); **(b)** port as pass-through cognitive tools that still round-trip (matches Inspector). **Recommended: (b)** — uniform surface, no lost behavior — but the choice is the architect's. These 4 tools are tagged `⚑OD-3` in the batch table.

---

## Definition of Done (track level)

The port wave is DONE when **all 115 legacy-WS-path registry tools** are reachable through the cognitive Dispatcher via the documented Strangler-Fig pattern, with **zero behavior drift**, and every legacy `mcp_server.py` dispatch branch that a wave supersedes is retired per the criteria below — proven wave-by-wave, each wave a human-merged commit. Concretely, the track is done when:

1. **Inventory closed.** Every tool in `TOOL_DEFS` (derived count **115**, §Inventory) belongs to exactly one merged wave. No tool ported twice; none left on the pure legacy path except any `⚑OD-3` exceptions the human rules to keep there.
2. **Parity proven per tool.** For each ported tool a **basic-pass** test asserts *same args → same effect + same response envelope* against the legacy WS path (§DoD-per-wave, "basic").
3. **Hostile-pass clean per wave.** Crucible returns `mergeReady:true` with empty `showstoppers` (`.claude/workflows/h22-port-wave.js:59`) — no envelope loss (consent/undo/provenance), no dropped error path, no test-theater.
4. **Guardrails intact every wave.** `phantom_clean` and `suite_baseline` (the two relevant standing guardrails — verified `harness/tasks.json` guardrails.checks = `['scout_no_apex_corpus','no_rigging_drift','provenance_not_bypassed','phantom_clean','suite_baseline']`) stay GREEN; the full `pytest tests/` sits at floor.
5. **Adapters retired.** When a family's tools are all Dispatcher-registered, the corresponding legacy branch in `mcp_server.py::call_tool()` is removed per §Adapter Retirement — not before.

**Floor of record:** `harness/verify/suite_baseline.json` = **passed 4118 / failed 0 / skipped 87** (commit stamp "178798d + D-track graft + crucible remediation", generated 2026-07-07). `check_suite_baseline` reads this **at merge-base(master,HEAD)**, so each wave's floor is whatever HEAD carries — a wave cannot lower its own bar. `[Note: an older memory pin cites 4086; the committed baseline is 4118 — 4118 is the verified number.]`

---

## Ground truth (verified this dispatch — do not re-litigate)

- **The registry is the single source of truth for BOTH transports.** `mcp_server.py:452` (stdio bridge) and `python/synapse/mcp/tools.py:24,39-42` (Streamable HTTP) both import `TOOL_DEFS`/`TOOL_DISPATCH`/`TOOL_JSON` from `python/synapse/mcp/_tool_registry.py`. A port that changes dispatch must keep both transports coherent, or one silently regresses.
- **The legacy path is `TOOL_DISPATCH → send_command → WS → synapse.server.handlers*`.** `mcp_server.py::call_tool()` (`:791-853`) dispatches: group-info tools → local; `synapse_inspect_stage` → Dispatcher; `synapse_scout` → Dispatcher; **everything else → `TOOL_DISPATCH[name]` → `send_command(cmd_type, payload)`** over the WebSocket to the in-Houdini command handlers.
- **The port pattern already exists twice — it is the reference, not a new invention.** Inspector (`mcp_server.py:461-635`, "Sprint 3 Spike 1 — the Strangler Fig port", registered as `synapse.cognitive.tools.inspect_stage`) and Scout (`mcp_server.py:638-719`, `synapse.cognitive.tools.scout`). Both route through `synapse.cognitive.dispatcher.Dispatcher` (`python/synapse/cognitive/dispatcher.py`, 13.6 KB). The Inspector comment pins the acceptance contract: "**the error envelope shape is preserved byte-for-byte** by mapping AgentToolError back to the {error, message, target_path} dict." That byte-for-byte-envelope rule is the DoD spine.
- **Prior-art port targets already sit in `python/synapse/cognitive/tools/`:** `inspect_stage.py`, `scout.py`, `write_report.py`, `propose_graph.py`, `api_delta.py`. The wiring state of `write_report.py`/`propose_graph.py` (whether the live tool routes through them yet, or still through the WS handler via `_identity`) is `[UNVERIFIED — grep the live call_tool/registry dispatch for these two; the registry still maps them via _identity → WS]`. Treat them as *partial precedent*, not proof the tool is ported.
- **Neither Inspector nor Scout is in `TOOL_DEFS`** — they are appended separately in `list_tools()` (`mcp_server.py:762-775`). So the 115 registry tools are exactly the *un-ported* legacy-path set; the two reference tools are not double-counted.
- **Guardrails run every sprint for free.** `phantom_clean` (`harness/verify/checks.py:425`) AST-scans the sprint's **added** `.py` lines for `hou.*` symbols absent from the introspected symbol table, scoped to `git diff` vs merge-base(master,HEAD); `ok:False` short-circuits to a repair ticket **before** the Evaluator. Port waves inherit it — do NOT add wave-specific checks to `guardrails.checks`.

---

## Inventory — derived, not trusted

**Do not trust "104."** Derived live this dispatch from `_tool_registry.py::TOOL_DEFS` (import + `len`, plus the six `mcp_tools_*.py` group manifests):

| Fact | Derived value | How |
|---|---|---|
| `TOOL_DEFS` entries | **115** | `len(TOOL_DEFS)`, unique names, 0 duplicates |
| Families (scene/usd/render/tops/cops/memory) partition | **exact** | union of 6 group `TOOL_NAMES` = 115, no overlap, no ungrouped tool |
| read-only / write / destructive split | **38 / 10 / 67** | registry flags (cols 6–8) |
| MCP surface total (listed) | 123 | 115 registry + 6 group-info + Inspector + Scout |
| Already Dispatcher-ported (NOT to re-port) | 2 | Inspector, Scout (not in `TOOL_DEFS`) |
| Local-only (never had a WS handler) | 6 | `_GROUP_INFO_TOOLS` |

**115 ≠ 104.** The delta of 11 is unexplained by any derived subset above; **104 is the blueprint's own headline figure** (`docs/SYNAPSE_H22_GAP_BLUEPRINT.md` §4 row 4 / G1: "104 tools on the legacy path") — a count the live registry now derives as **115**, so the delta is expected blueprint-vs-current-registry drift. `[104 matches none of {115 registry, 123 listed, 113 = 115−undo/redo, 111 = 115−4 OD-3}, consistent with the blueprint's rounded/earlier figure. Re-derive any time with: python -c "import importlib.util as u; s=u.spec_from_file_location('r','python/synapse/mcp/_tool_registry.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print(len(m.TOOL_DEFS))".]` CLAUDE.md's own header ("115 MCP tools registered") agrees with the derived 115.

Per-family counts (authoritative, from `mcp_tools_<family>.py::TOOL_NAMES`): **scene 22 · usd 20 · render 13 · tops 18 · cops 21 · memory 21 = 115.**

---

## Wave plan — families in dispatch order, sub-batched to ≤15

Order per brief: **scene → usd → render → tops → cops → memory.** Each oversized family is split into ≤15-tool sub-waves (OD-1 option (b) assumed; under (a) the sub-ids are review checkpoints). Within a family, **low-blast read/introspect tools lead** (cheapest parity goldens, best pilot); destructive/orchestration tools follow. Command-type column is the `TOOL_DISPATCH` target = the WS handler the port must preserve. `[RO]`=read-only, `[W]`=write non-destructive, `[D]`=destructive.

### Wave `scene-1` — utility + read/introspect (11)
`synapse_ping`[RO] · `synapse_health`[RO] · `synapse_doctor`[W] · `houdini_scene_info`[RO] · `houdini_get_selection`[RO] · `houdini_get_parm`[RO] · `synapse_inspect_selection`[RO] · `synapse_inspect_scene`[RO] · `synapse_inspect_node`[RO] · `houdini_network_explain`[RO] · `synapse_write_report`[W]
> **Pilot wave.** All read-only/file-only → parity goldens are pure assertion, no scene mutation. `synapse_write_report` has prior art at `cognitive/tools/write_report.py`. Prove the pattern here before any destructive port.

### Wave `scene-2` — mutation + graph-synth (11)
`houdini_create_node`[D] · `houdini_delete_node`[D] · `houdini_connect_nodes`[D] · `houdini_set_parm`[D] · `houdini_execute_python`[D] · `houdini_execute_vex`[D] · `houdini_undo`[D]⚑OD-3 · `houdini_redo`[D]⚑OD-3 · `synapse_batch`[D] · `synapse_propose_graph`[RO]⚑OD-3 · `synapse_instantiate_graph`[D]⚑OD-3
> **Highest-risk wave in the whole track.** `execute_python`/`execute_vex` are the CRITICAL-gate tools; the port MUST carry the consent/undo/provenance envelope unchanged (crucible will hunt exactly this). `propose_graph`/`instantiate_graph` are `⚑OD-3` (live-`hou`-oracle, shared ProposalStore — must keep the WS round-trip). Consider deferring `scene-2` until every other wave is green.

### Wave `usd-1` — prim + attribute core (10)
`houdini_stage_info`[RO] · `houdini_get_usd_attribute`[RO] · `houdini_query_prims`[RO] · `houdini_set_usd_attribute`[D] · `houdini_set_usd_primvar`[D] · `houdini_create_usd_prim`[D] · `houdini_modify_usd_prim`[D] · `houdini_manage_variant_set`[D] · `houdini_manage_collection`[D] · `houdini_reference_usd`[D]

### Wave `usd-2` — assembly + material + solaris (10)
`houdini_read_material`[RO] · `houdini_set_payload_loadstate`[D] · `houdini_create_point_instancer`[D] · `houdini_configure_light_linking`[D] · `houdini_create_textured_material`[D] · `houdini_create_material`[D] · `houdini_assign_material`[D] · `houdini_shot_render_ready`[D] · `synapse_solaris_assemble_chain`[W] · `synapse_solaris_build_graph`[W]
> **Trap (usd):** parm names on USD/Solaris nodes are punycode-encoded (`xn__…`) and the hand-maintained encoding map is majority-phantom on 21.0.671 (`harness/notes/verified_usdlux_encodings_21.0.671.json`). A port must not "clean up" those encodings — pass them through byte-for-byte. `shot_render_ready` is a composite orchestrator (calls material→assemble→render) — its parity golden must NOT trigger a real render (see render trap).

### Wave `render` — viewport, render, farm, validate (13)
`houdini_capture_viewport`[RO] · `synapse_validate_frame`[RO] · `synapse_render_farm_status`[RO] · `synapse_validate_ordering`[RO] · `houdini_render`[D] · `synapse_configure_render_passes`[D] · `houdini_set_keyframe`[D] · `houdini_render_settings`[D] · `synapse_render_sequence`[D] · `synapse_render_farm_cancel`[D] · `synapse_autonomous_render`[D] · `synapse_safe_render`[D] · `synapse_render_progressively`[D]
> **Trap (render) — binding:** **no golden may perform a real render.** Houdini Indie silently no-ops `husk` headless (`usdrender_rop.render()` writes nothing, no error — `harness/notes` / memory). Parity goldens assert the *dispatch + envelope* (ROP resolution, payload marshalling, response shape), never pixels. `houdini_render`/`houdini_capture_viewport` return `ImageContent` via a special branch in `call_tool()` (`mcp_server.py:817-842`) — that image-content path is itself a legacy adapter the port must reproduce (see §Adapter Retirement).

### Wave `tops-1` — read/query + core cook (9)
`tops_get_work_items`[RO] · `tops_get_dependency_graph`[RO] · `tops_get_cook_stats`[RO] · `tops_query_items`[RO] · `tops_diagnose`[RO] · `tops_pipeline_status`[RO] · `houdini_wedge`[D] · `tops_cook_node`[D] · `tops_generate_items`[D]

### Wave `tops-2` — control + orchestration (9)
`tops_configure_scheduler`[D] · `tops_cancel_cook`[D] · `tops_dirty_node`[D] · `tops_setup_wedge`[D] · `tops_batch_cook`[D] · `tops_cook_and_validate`[D] · `tops_monitor_stream`[W] · `tops_render_sequence`[D] · `tops_multi_shot`[D]
> **Trap (tops) — binding:** `hou.pdg.*` is a **quarantined phantom class** (`hou.pdg` does not resolve on 21.0.671; the live module is `pdg`). The TOPs port must not introduce any `hou.pdg.*` reference, and must not touch `python/synapse/server/handlers_tops/`. **No automated guard fires on that surface during a port wave** — `tops_path_untouched` is a per-D-**task** verify (attached at `harness/tasks.json:969/989/1014/1038/1062`, catalogued in `checks_vocabulary` at `:56`; spec `harness/notes/spec-D-diagnostic-truth.md:41` = "git-diff guard: no D sprint modifies `handlers_tops/`"). It is **not** one of the five standing guardrails `run.ts` runs every sprint (verified `harness/tasks.json` guardrails.checks = `['scout_no_apex_corpus','no_rigging_drift','provenance_not_bypassed','phantom_clean','suite_baseline']`), and `h22-port-wave` is a `.claude/workflows/*.js` workflow — not a `tasks.json` task — so it attaches no per-task checks. During `tops-1`/`tops-2` the only defenses of `handlers_tops/` are this manifest's `tops-*` DoD rider (§DoD-per-wave) and crucible's hostile pass; hardening it into an automated guard (adding `tops_path_untouched` to the port-wave guard set) is a workflow/tasks edit outside this manifest's scope — a human/forge change. PDG events fire on a **worker** thread (not main) — any callback the port relies on inherits that constraint. `tops_render_sequence`/`tops_multi_shot` inherit the render no-render trap.

### Wave `cops-1` — foundation + pipeline (11)
`cops_read_layer_info`[RO] · `cops_analyze_render`[RO] · `cops_create_network`[D] · `cops_create_copnet`[D] · `cops_create_node`[D] · `cops_connect`[D] · `cops_set_opencl`[D] · `cops_to_materialx`[D] · `cops_composite_aovs`[D] · `cops_slap_comp`[D] · `cops_create_solver`[D]

### Wave `cops-2` — procedural + advanced (10)
`cops_temporal_analysis`[RO] · `cops_procedural_texture`[D] · `cops_growth_propagation`[D] · `cops_reaction_diffusion`[D]† · `cops_pixel_sort`[D]† · `cops_stylize`[D] · `cops_wetmap`[D] · `cops_bake_textures`[D]† · `cops_stamp_scatter`[D] · `cops_batch_cook`[D]
> **Trap (cops):** `†` = SCAFFOLD tools whose live behavior is a placeholder (`reaction_diffusion`/`pixel_sort` = "placeholder #define-only kernel; node not cooked"; `bake_textures` = "creates placeholder map nodes; does NOT bake"). The parity golden asserts the **scaffold** contract, not a real cook — porting must not "fix" the scaffold into a cook (that is a separate, ratified feature, not a port).

### Wave `memory-1` — memory read/write core (11)
`synapse_knowledge_lookup`[RO] · `synapse_context`[RO] · `synapse_search`[RO] · `synapse_recall`[RO] · `synapse_memory_query`[RO] · `synapse_memory_status`[RO] · `synapse_decide`[W] · `synapse_add_memory`[W] · `synapse_project_setup`[W] · `synapse_memory_write`[W] · `synapse_evolve_memory`[W]

### Wave `memory-2` — metrics/recipes + HDA + consolidation (10)
`synapse_metrics`[RO] · `synapse_router_stats`[RO] · `synapse_list_recipes`[RO] · `synapse_live_metrics`[RO] · `houdini_hda_list`[RO] · `synapse_sleep_pass`[D] · `houdini_hda_create`[D] · `houdini_hda_promote_parm`[D] · `houdini_hda_set_help`[D] · `houdini_hda_package`[D]
> **Trap (memory):** `synapse_sleep_pass` is the sole destructive memory op (APPROVE-gated Moneta prune) — the port must preserve the gate and the prune-audit envelope. The three-store split-brain (jsonl vs Moneta vs USD) is a *studio-readiness* finding (S.4), NOT a port concern — do not "fix" recall provenance inside a port.

**Wave total:** 11 + 11 + 10 + 10 + 13 + 9 + 9 + 11 + 10 + 11 + 10 = **115.** 11 sub-waves; every sub-wave ≤ 15; smallest 9 (tops tails).

---

## DoD per deliverable (per wave)

Every wave — whether family-sized (OD-1a) or sub-wave (OD-1b) — passes the **same four gates**, in this order. A wave that fails any gate is `NEEDS_REPAIR`; the human never merges it.

| Gate | What proves it | Owner (workflow phase) | Pass criterion |
|---|---|---|---|
| **1. Basic pass** | A parity test per ported tool: **same args → same command_type + payload built + response envelope** as the legacy `TOOL_DISPATCH` path. Read-only tools: assert the envelope on a fixture stage. Destructive tools: assert the *dispatch + undo/consent/provenance envelope*, not live scene state (goldens stay render-free and cook-free per the family traps). | forge (Build) | Every tool in the wave has a green parity test; `pytest tests/` collects them. |
| **2. Assay (V1 symbol probe)** | Every `hou.*`/`pdg.*`/`pxr.*` symbol the wave's diff **introduces or newly relies on** is probed against the live runtime (bridge first, hython fallback with build-mismatch flag). | assayer (Assay) | PASS per symbol; any QUARANTINE = the symbol is absent → it does not ship. No unprobed symbol asserted as fact. |
| **3. Hostile pass** | Crucible red-teams the worktree diff it did **not** build: behavior drift (same args → same effect?), consent/undo/provenance envelope loss, dropped legacy error paths, test-theater (pins the mock not the contract). | crucible (Attack) | `mergeReady:true` AND `showstoppers:[]` (`.claude/workflows/h22-port-wave.js:59`). |
| **4. Guardrails + floor** | `phantom_clean` GREEN (no phantom `hou.*` on added lines) AND `suite_baseline` GREEN (full `pytest tests/` ≥ the HEAD floor, currently 4118/0/87). | run.ts standing guardrails | Both GREEN; `ok:None` (gate-down) is a WARN, not a pass — a wave does not merge on a downed phantom gate. |

**Commit shape:** one atomic commit per wave in an isolated worktree (`isolation:'worktree'`, `.claude/workflows/h22-port-wave.js:28`), message `feat(mcp): <wave-id> port <family> tools legacy-WS→Dispatcher`. No `git push`, no merge — the worktree is handed to the human.

**Wave-specific DoD riders** (in addition to the four gates):
- `scene-2`: consent-gate parity for `execute_python`/`execute_vex` is a **showstopper if lost** — the CRITICAL gate + `__builtins__` posture must survive the port byte-for-byte (single-user-localhost posture stays a documented choice, not a silent removal).
- `usd-2`: punycode parm encodings pass through unchanged; `shot_render_ready` golden asserts orchestration order, not pixels.
- `render`, `tops-2` (render/multi-shot): **no real render in any golden** — hard rule.
- `tops-*`: zero `hou.pdg.*`; zero edits under `handlers_tops/`.
- `cops-2`: scaffold tools keep scaffold semantics.

---

## Adapter retirement — criteria for legacy `mcp_server.py` branches (OD-2 = (a) assumed)

`call_tool()` (`mcp_server.py:791-853`) has four legacy dispatch surfaces. A branch is retired **only when every tool it served is Dispatcher-registered and its behavior is reproduced byte-for-byte** — never on a schedule, never speculatively. Retirement is itself a diff that passes the four DoD gates.

| Legacy surface | Location | Retirement criterion | Retire after |
|---|---|---|---|
| **`TOOL_DISPATCH` fallback** (`send_command` for all 115) | `mcp_server.py:807-814` | All 115 registry tools are Dispatcher-registered AND parity-proven; `TOOL_DISPATCH` no longer referenced by `call_tool()`. Registry `TOOL_DISPATCH`/`send_command` stay for the HTTP transport until it is ported too (both transports import from the registry — do not orphan `python/synapse/mcp/tools.py`). | the LAST family wave merges |
| **Image-content special-case** (`ImageContent` for `houdini_capture_viewport`/`houdini_render`) | `mcp_server.py:817-842` | The two image tools' Dispatcher ports reproduce the base64/`ImageContent` + metadata envelope; a parity test pins the image response shape. | the `render` wave merges |
| **Group-info branch** (`_GROUP_INFO_TOOLS`, 6 local knowledge tools) | `mcp_server.py:795-796, 781-788` | Only if the 6 group-knowledge tools move to Dispatcher-registered local tools (they never had a WS handler — lowest priority; may be left as-is). Retirement is **optional**, not required for track DoD. | out of scope unless the human rules it in |
| **Inspector / Scout branches** | `mcp_server.py:800-805` | **Already ported — do not retire.** These are the reference pattern; they stay until the whole `call_tool()` collapses to a single `Dispatcher.execute()`, at which point they fold in with the rest. | end state only |

**Retirement is reversible-safe:** because both transports read the same registry, a retired branch leaves `TOOL_DEFS`/`TOOL_JSON` intact (tool *definitions* never move — only *dispatch* moves). If a port regresses, reverting the branch removal restores the legacy path with zero definition change. `[UNVERIFIED — whether `python/synapse/mcp/tools.py` (HTTP transport) needs a parallel port; it consumes the same `TOOL_DISPATCH`, so retiring the stdio branch without porting the HTTP path would leave HTTP on the legacy path. Confirm HTTP-transport scope with the architect before retiring `TOOL_DISPATCH`.]`

---

## Non-goals (explicit)

- **Not reimplementing the WS command handlers.** Under OD-2(a) the handlers in `python/synapse/server/handlers*.py` stay the execution primitive. Rewriting them is a separate, un-ratified track. (If the human rules OD-2(b), this non-goal is lifted for the affected handlers only.)
- **Not touching `harness/state/drop.json`, `flywheel_queue.json`, or any `ratified` flag.** Those are human writes; this manifest only *depends on* drop.json existing.
- **Not editing the `wave` enum in `.claude/workflows/h22-port-wave.js`.** That is a workflow code change (OD-1b) the human/forge makes, outside scribe's write scope.
- **Not fixing findings that a wave surfaces but does not own:** the memory split-brain (S.4), consent-at-dispatch (S.2), RBAC (S.3) are studio-readiness track items — a port preserves the current behavior, it does not improve security posture.
- **Not touching `handlers_tops/`** — protected during the port by this manifest's `tops-*` DoD rider + crucible, **not** by an automated guard (`tops_path_untouched` is a per-D-task check that does not run in a port wave; see §Wave `tops-1`/`tops-2` trap) — and **not un-quarantining `hou.pdg.*`**.
- **No render, no cook, no APEX/KineFX/rigging** in any golden or ported tool — rigging scope is structurally refused regardless of who asks (`docs/H22_AGENT_HARNESS.md:140`).
- **Not changing tool *definitions*** (`TOOL_DEFS` names, schemas, flags). The port moves *dispatch*, not contract. A schema change is a different PR with a different gate.

---

*Authored MODE A, HEAD `314acd6`. This manifest is a Leg-0 paper artifact — merge-to-main is the human gate that makes it binding, and MODE B (`drop.json`) is the second precondition before any wave runs.*
