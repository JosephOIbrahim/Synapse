# SYNAPSE — Deep Self-Review

Date: 2026-08-02 · Houdini 22.0.397 · Protocol 4.0.0
Scope: live tool schema (110+ tools), 62 recipes, resilience/metrics layer, memory system, panel/bridge UX.

---

## 1. Honest UX feedback — what's actually good, what hurts

### What genuinely works
- **Coarse-call discipline.** "One coarse call over N granular calls" is load-bearing. `synapse_solaris_build_graph` (template = full render-ready graph in one cook), `synapse_batch` (one round-trip + one undo group), `tops_render_sequence` (validates stage → creates/reuses TOPnet → generates → cooks, idempotent). These are the best DX in the system because they respect the real cost model: round-trips dominate, Houdini ops are 1–70ms.
- **Phantom-API paranoia is justified and pays off.** Punycode-encoded USD params (`xn__inputsintensity_i0a`), "never guess, inspect first," `houdini_inspect_node` before `set_parm`. Raw createNode/execute_python is named as the #1 failure mode and the design actively steers around it.
- **Honest-scoped controls.** `synapse_emergency_halt` explicitly says what it does NOT stop (background renders, TOPnets outside /obj). `synapse_render_stop` documents the Mantra partial-EXR residue and refuses to kill by wildcard. Tools that admit their limits are rare and valuable.
- **Resilience layer is real, not decorative.** Circuit breaker (state 0 = closed), dispatch wait p50 ~58ms / max 0.22ms main-thread hold, abandoned-payload counter at 0. The C4 abandoned-payload metric existing at all means someone got bitten and fixed it.
- **Voice Guide.** "Lead with what's working," "errors are collaborative," "never dump raw errors," "match energy." This is a genuine differentiator vs. every other MCP server that LARPs as a CLI.

### What hurts
- **The very first call in a session can fail silently-ish.** `synapse_project_setup` — the tool the system prompt says to call FIRST — returned `Bridge: Integrity check failed: fidelity=0.0` on a fresh boot while ping/health/context all succeeded. So the mandated entry point is also the most brittle (it reads memory files that don't exist yet, computes a hash over nothing, and reports 0.0 fidelity as a failure). Cold-start is exactly when you can least afford a scary error.
- **Tool sprawl taxes the model, not the artist.** ~110 tools in schema + 62 regex-triggered recipes means a large fraction of every prompt is tool definitions. Several are near-duplicates (see §3). The routing layer ("tier cascade") returned `Router not initialized` in this session, so the thing meant to tame sprawl wasn't even up.
- **Scaffold-level tools masquerade as features.** `cops_reaction_diffusion` and `cops_pixel_sort` are *labelled* "SCAFFOLD / placeholder kernel; node not cooked" in their own descriptions. Shipping placeholders at the top level of the tool list degrades trust in the neighboring, real tools. (At least the honesty is in the docstring — but the artist shouldn't have to read docstrings to learn a "reaction-diffusion solver" doesn't simulate.)
- **Recipe triggers are regexes over English.** 62 recipes × fragile anchored regex means "set me up a three point light" matches, "throw a 3-point rig on this" doesn't. It's a slot-filling CLI wearing a chat costume. Fine as a fast-path, but they're presented as primary coverage.
- **Memory is opt-in and currently empty.** evolution_stage "none", 0 entries, 0 sessions — after an install. The whole self-improving story (§5) is dormant until something writes. Nothing in the base flow writes aggressively enough.

---

## 2. What is genuinely novel

Ranked by "haven't seen this done properly elsewhere":

1. **Mandated coarse orchestration with an atomic undo contract.** Lots of MCP wrappers expose `create_node`. Very few expose `solaris_build_graph(template=multi_asset_merge)` that is *the* blessed path, re-validates against the live runtime, builds in ONE undo group, and names raw node-by-node creation as an anti-pattern in the system prompt. Treating the LLM's latency/cook cost model as a first-class design constraint is the most novel thing here.
2. **Proposal → validate against a live oracle → instantiate (TOCTOU-guarded).** `synapse_propose_graph` grounds every node type/parm against the live H21 runtime (a "live hou oracle"), parks it, and `synapse_instantiate_graph` re-validates at build time to catch time-of-check/time-of-use drift. That's a real distributed-systems idea correctly applied to "LLM hallucinated API" — the strongest anti-hallucination pattern in the toolset.
3. **Honest partial-failure semantics.** `render_stop`'s "Mantra leaves a structurally valid, pixel-empty .exr + orphaned checkpoint; a file-exists check will pass it" is unusual candor about a nasty edge. Most tools pretend kills are clean.
4. **Resilience telemetry aimed at the actual failure mode.** `dispatch_wait_ms` (enqueue-to-start) and `main_thread_hold_ms` + abandoned counter measure exactly how an MCP bridge dies inside a DCC (main-thread starvation during cook/modal), not generic HTTP latency.
5. **A Voice Guide as system-prompt law.** Personality-as-contract with anti-patterns ("never say 'just'," "errors are 'we'"). Gimmicky on paper; in practice it stops the failure mode where the tool makes the artist feel dumb.
6. **Recipes as a compiled tier.** 62 trigger→step-graph recipes are a genuine fast-path that skips LLM planning for known tasks — cost and latency win when the router is up.

---

## 3. What to remove for bloat

Cut or merge — each of these costs schema tokens + model confusion every single call:

- **Near-duplicate render triggers.** `safe_render`, `render_progressively`, `render_sequence`, `render_validate_frame`, `render_preview`, `setup_render_farm`, `turntable_render`, `render_turntable_production`, `camera_match_turntable` — nine ways to render. Collapse into two: `render` (with `mode: preview|progressive|sequence` and validation flags) and `turntable` (with `quality: preview|production`). The progressive/safe distinctions are *options*, not separate tools.
- **COP placeholders.** Remove from the default schema (keep behind a `--labs` flag): `cops_reaction_diffusion`, `cops_pixel_sort`, `cops_bake_textures` ("creates placeholder map nodes; does NOT bake"), `cops_growth_propagation` if it's still a dilate/blur loop pretending to be DLA. A placeholder that creates an uncooked node is worse than no tool.
- **Duplicate HDA scaffolding.** `hda_scaffold`, `hda_generate`, `lop_hda_scaffold`, `karma_quality_hda`, plus the generic `houdini_hda_package`/`hda_create`/`promote_parm`/`set_help`. Keep the generic 4 + `hda_generate` (the one with real VEX templates); delete the three narrow scaffolds or express them as `hda_generate` presets.
- **Redundant inspect trio.** `synapse_inspect_node`, `synapse_inspect_selection`, `houdini_inspect_node`-style discovery, `synapse_network_explain`. Keep `inspect_node` (with opt-in geometry) and `network_explain`; fold selection into `inspect_node(node=selection)`.
- **Memory split-brain.** There are *two* memory APIs: `synapse_add_memory`/`search`/`recall`/`decide`/`context` AND `memory_write`/`memory_query`/`memory_status`/`evolve`/`sleep_pass`. That's 11 memory tools for what should be 3 (`write`, `query`, `status`). Remove or merge — this is the single most confusing overlap in the schema.
- **Dead-tier tools surfaced at top level.** `synapse_router_stats` errored "not initialized"; `tops_configure_scheduler` rejects everything except `local`. Don't expose controls for subsystems that are off.
- **The six `[TOOL GROUP]` meta-tools** exist only to echo the system prompt. If groups matter, put them in the protocol, not the schema.

Net cut: ~20 tools and ~15 recipes → noticeably smaller per-call context, less model drift.

---

## 4. What to push farther

1. **The live-oracle validation loop (propose/instantiate).** Today it guards graph building. Extend the same "ground against the live runtime, then act" pattern to: (a) `set_parm` on USD nodes (auto-inspect punycode instead of telling the caller to), (b) VEX snippets (compile-check against real input geometry before creating the wrangle — `houdini_execute_vex` already creates a node, so have it dry-run first), (c) recipe steps (validate the whole recipe against the scene before step 1). This becomes SYNAPSE's identity: *the tool that never hallucinates Houdini.*
2. **Memory as the product, not a subsystem.** It starts empty and stays empty. Make it earn the "self-improving" claim: auto-write a decision on every successful recipe run ("lookdev_scene → 4 nodes, 190ms"), auto-recall on recipe trigger to bias parameters, decay noise via the existing `sleep_pass`. The Moneta backend gate is fine; the *write path* needs to be default-on.
3. **Topology templates.** `build_graph` templates cover 7 patterns. Add the ones artists actually rebuild every shot: `asset_lookdev` (component builder + mtlx + key/fill/rim + karma props), `plate_comp` (sopimport → camera projection → cryptomatte → COP comp), `crowd_layout` (point instancer + variant selector + collection per hero/BG split). Templates are where the coarse-call philosophy compounds.
4. **Recipes as graphs, not regexes.** Keep the 30 highest-value (lighting rigs, turntables, lookdev, tops sweeps, component builder) and convert from "regex → steps" to "declarative mini-proposals validated by the live oracle" — i.e., recipes ride the propose/instantiate machinery. Delete the rest.
5. **Viewport/diagnostics loop.** `validate_frame` + `capture_viewport` + `render_farm_status` + `live_metrics` are strong. Add an autonomous "fix-forward" that uses `tops_diagnose` output to mutate one parameter and re-render — the `autonomous_render` tool gestures at this but should be the centerpiece.

---

## 5. What is "RSI scaffolding" in SYNAPSE, from first principles

**RSI = recursive self-improvement.** The term is borrowed from AI-capability discourse ("an agent that improves itself"), but in SYNAPSE it means something specific and much more modest:

> *The system stores the artifacts of its own work in a form that makes its next work better — and it is built so those artifacts accumulate instead of evaporating.*

From first principles, an LLM-in-a-DCC is **stateless across calls and across sessions.** Every call starts from zero: no memory of the scene it built yesterday, the parameter that fixed the fireflies, the HDA it shipped. Left alone, an agent is a goldfish with great tools. RSI scaffolding is everything SYNAPSE builds **around** the stateless model to (a) *capture* work product, (b) *recall* it at the right time, and (c) *compound* it into future runs — the "recursive" being: the system's own outputs become inputs that improve its own outputs.

Concretely, the scaffolding has four layers in SYNAPSE:

1. **The stores (what accumulates).** Project memory + scene memory (Moneta or jsonl backend), agent state, decisions, recipes-run history. This is the "improvement substrate." Measured live right now: 0 entries, evolution stage "none" — i.e., the scaffold is built but the flywheel hasn't turned.
2. **The capture hooks (how work gets remembered).** `add_memory`, `decide`, `memory_write`, plus implicit capture: per-tool duration histograms, dispatch/hold telemetry, failed-cook diagnostics. RSI only works if capture is *default and cheap* — this is the layer that most needs strengthening (§4.2), because today it's opt-in and the store sits empty.
3. **The recall/bias layer (how memory changes behavior).** `recall`, `search`, `context`, recipe-trigger → known-good-parameter bias (the `render_sequence` "learns from each render to start smarter" claim). The recursion closes *here*: output N influences run N+1.
4. **The evolution mechanics (how it compacts and compounds).** `evolve_memory` (charmander→charmeleon→charizard stages — compaction tiers), `sleep_pass` (Moneta consolidation/decay: prune the unprotected, keep the load-bearing, with an audit). This is what prevents RSI from becoming "infinite hoard" — compounding requires *forgetting* too.

**Why "scaffolding" and not "RSI" itself?** Because none of this is autonomous self-modification — the model can't rewrite its own weights or its own code. It can only rewrite its *context*: memory, recipes, templates, HDAs, telemetry. RSI scaffolding is the fixed structure (stores, hooks, recall, decay, live-oracle validation, coarse-call laws) that makes those context-rewrites accumulate usefully instead of chaotically. The improvement is *within* the scaffold; the scaffold itself is hand-built.

**The honest gap, from this very session:** the scaffolding is more complete than its contents. The stores are empty, the evolution stage is "none," the router (the recall fast-path) wasn't initialized, and the mandated first call threw the integrity error. So today SYNAPSE has built the *bicycle for the mind* but the artist still has to pedal the memory flywheel manually. Pushing §4.2 — default-on capture, automatic decision-writing on recipe success, recall-driven parameter bias — is the difference between "RSI scaffolding exists" and "RSI actually compounds."

---

*Method note: grounded against the live bridge — health/metrics/context/recipe-list pulled this session. Memory and router were cold; `project_setup` and `doctor` hit the fidelity-0 integrity path. Findings about tool overlap and placeholders come from the live schema and recipe registry, not from repo source.*
