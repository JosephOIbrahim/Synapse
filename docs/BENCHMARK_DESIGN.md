# G6 — BENCHMARK DESIGN (frozen spec, MODE A paper)

**`docs/BENCHMARK_DESIGN.md`** · Repo: `C:\Users\User\SYNAPSE` · Grounded against HEAD `314acd6` (v5.22.0) / Houdini 21.0.671. All paths repo-relative.

**Status: PROPOSAL.** This is the design of the meter, not the meter. Per the harness rule (`docs/H22_AGENT_HARNESS.md` §5): *"G6 benchmark execution (workflow to be authored only after `docs/BENCHMARK_DESIGN.md` survives crucible — write the spec before the meter)."* Nothing here executes until this document survives adversarial review and a human merges it.

**Governing gate:** **G6** (benchmark design), with sub-clause **G6b** (the telemetry/cognitive-state boundary, §4). **Relay leg:** authored in **Leg 0, Mile 0.3** (the fourth Phase-0 spec, alongside PORT_WAVE_MANIFEST / PREFLIGHT_GATE / SCENE_GROUNDING_CONTRACT). The *meter itself* is off the automated relay — benchmark **execution** is human-driven (Mile-5-adjacent), gated behind this spec's crucible survival.

---

## OPEN DECISIONS (human rulings — the rest of the spec is complete without them)

These are policy/scope trades the harness must not invent. Each carries a recommendation; none is resolved here.

- **OD-1 — Publication policy (IP hygiene).** The brief says results publish through README with methodology. What form: (a) absolute numbers (ms, token counts, turn counts), (b) ratios/factors only (e.g. "grounding uses N× fewer tokens/task"), or (c) absolute latency + *ratio-only* token results (token absolutes reveal the grounding recipe's shape). Publishing absolute token counts of the grounding recipe partially discloses the method — a claim-surface/IP call that belongs to the human/CTO, consistent with the v5.22.0 "honest envelope" posture. **Recommended: (c)** — latency is a fair-and-square infra number worth showing in full; token results ship as ratios + turns-to-green, with the raw recipe held. SCRIBE cannot write `README.md` (charter); the README section is authored by `h22-docsurgeon` from the contract in §5.
- **OD-2 — Fairness bar for the token-track baseline.** "Naive serialization recipe" can be a *strawman* (dump the whole node network / full USDA into the prompt, raw) or a *steelman* (a reasonable competitor: whole-node-parameter JSON dump as a Houdini-native-MCP-style tool would emit, no degradation ladder, no manifest budgeting). A strawman wins cheaply and reads as marketing; a steelman is credible. **Recommended: steelman** — define the baseline as "every node's full parm/attr set serialized to JSON, no token budget, no summarization," which is the honest floor a naive integration actually hits. The exact competitor definition is frozen by whoever rules OD-2 so the number can't be re-litigated later.
- **OD-3 — Complex-tier fixture + flagship-demo publication.** The proposed T3 complex fixture is `cinema::camera_rig` (§3, Tier T3). It is **built procedurally** by `rebuild_with_subhdas.py` / `g6_check.py`, not shipped as an `.hda`/`.otl` asset (verified: no `otls/`/`hda/` asset found this session). Ruling needed: (a) confirm `cinema::camera_rig` reproduces headless from the committed builder and adopt it as T3, or (b) pick a committed, headless-loadable fixture instead. Separately: is the Shot-010 memory scenario (§3, memory track) also published as a **recorded flagship demo** (video/gif in README), or measured-only? **Recommended:** (a) adopt the rig *iff* the builder reproduces it under hython at execution time (else fall back to a committed `.hip`); publish Shot-010 as both a pass/fail benchmark *and* the recorded demo — it is the single clearest "composition beats append-log" story SYNAPSE has.
- **OD-4 — Memory-track control: substrate + fairness bar (mirrors OD-2).** D7's discriminating story is "composition answers Shot-010; a flat append-log cannot." Stating that as a *comparative benchmark* needs a control that is actually built and actually fair — and no such control exists in the repo today: `FloorGate` is Tier-0 **provenance, not admission control** (`python/synapse/core/floor_gate.py:19`); it is not a queryable memory-reconstruction engine, so the failing control must be BUILT, not pointed at. Two shapes, exactly parallel to OD-2: **(a) comparative** — build a control and freeze its fairness bar. *Strawman* = a deliberately-crippled log reader (wins cheaply, reads as marketing — the same hazard OD-2 rejects). *Steelman* = a competent last-write-wins / point-in-time-revert reconstruction over the **same** append-only provenance log (`.synapse/provenance/` via `resolve_provenance_dir()`), the honest floor a naive integration hits — it still cannot separate the Shot-010 lookdev-revert from the entangled density edit, which is precisely *why* composition wins. **(b) capability-only** — drop the control entirely; make Shot-010 a pure composition gate: pass iff the composed stage carries Shot-010 lookdev AND current density, with no comparative claim published. **Recommended: (a) steelman** — the comparison is the whole point of the flagship demo and a fair steelman is credible; fall back to (b) if a fair control cannot be built under the execution budget. Whoever rules OD-4 freezes the control definition (or its removal) so the claim can't be re-litigated. Until ruled, D7's capability gate stands alone and the comparative verdict is withheld.

---

## Mission

Design three benchmark tracks — **latency**, **token efficiency**, **memory composition** — that turn SYNAPSE's three load-bearing claims into numbers a skeptic can reproduce. Extend the two benchmark scripts that already exist (`_benchmark_api.py`, `_benchmark_latency.py`); do **not** rebuild them. Each track names its op set / task set, its fixtures, its meter, and its acceptance oracle, so that the execution workflow authored after this spec has zero design decisions left to make. Results publish through `README.md` with a stated methodology so the numbers are checkable, not marketing.

## Definition of Done (this spec)

This paper deliverable is DONE when:

1. **All three tracks are executable-from-paper** — a builder can stand up the meter with no further design decision: op set / task set enumerated, fixtures named and grounded to real repo artifacts (or explicitly tagged for verification), meter defined, acceptance oracle deterministic and render-free.
2. **"Extend, never rebuild" is honored on paper** — the latency track is specified as *additions to* `_benchmark_api.py` / `_benchmark_latency.py` (op-set alignment + an in-process baseline arm), never a new harness; the token track is specified as *additions to* the live `run_turn` agent loop (a usage-capture field on `AgentTurnResult`) plus a small new usage reader and A/B runner, never a from-scratch model loop. Any track that adds a genuinely-new reader (token accounting) says so and proves no existing seam was skipped — the `run_turn`/`Dispatcher` agent-loop seam is named and extended, not bypassed.
3. **Every cited path/symbol/count is first-hand verified this session or tagged** — no count copied from CLAUDE.md or LATENCY_PLAN.md without a local re-check; unverifiable items carry `[UNVERIFIED — …]`; no unprobed `hou.*` asserted as fact.
4. **The G6b boundary sentence appears verbatim** (§4) and is wired to real substrate files (telemetry side + cognitive-state side both named).
5. **Every human-only decision is in OPEN DECISIONS**, not silently ruled in prose.
6. **The spec survives crucible** — every blocker closed or moved to OPEN DECISIONS (the Leg-0 exit gate, `docs/H22_AGENT_HARNESS.md` §6, golden G2).

## Ground truth (verified this session — do not re-litigate)

- **The in-process dispatch seam is `SynapseHandler.handle(command: SynapseCommand) -> SynapseResponse`** at `python/synapse/server/handlers.py:356` (spec-D cited `:353`; drifted — the live line is 356, verified by Read). This is the zero-transport call every transport ultimately reaches; it is the latency track's floor arm.
- **The two transports the meters exercise are both hwebserver-backed (C++):** the **HTTP round-trip** path is `python/synapse/server/api_adapter.py` (`hwebserver.apiFunction`, `POST /api`, port **8008**) — already exercised by `_benchmark_api.py`. The **WebSocket** path is `python/synapse/server/hwebserver_adapter.py` (`hwebserver.WebSocket`, port **9999**) — exercised by `_benchmark_latency.py`. Both require `hwebserver`, i.e. live Houdini; both fall back / are absent standalone.
- **Prior latency data exists and is the left side of the A/B** (`LATENCY_PLAN.md`, dated 2026-02-08, verified by Read): hwebserver carries a **~2 s main-event-loop dispatch floor** (`ping` warm ≈ 2070 ms vs websockets 0.2 ms; `create_node` ≈ 2082 ms). The finish-line check and three numeric **reopen-gates** (3b inspect-cache @250 ms p95, Mile-5 async-render @2000 ms p95, hwebserver-migration @5 ms read-mix p95) are already anchored to `_benchmark_latency.py` output. G6 does not re-derive these — it re-measures against them.
- **The token-grounding surface that exists today** is the `synapse_inspect_*` tool family — `synapse_inspect_node`, `synapse_inspect_scene`, `synapse_inspect_selection`, `synapse_inspect_stage` (verified by grep) — plus the token-budgeted `GeoSummary` type (`shared/types.py:210`, "<100 tokens per node"). The four read-only **`*_manifest` tools** (`graph_manifest` / `attr_manifest` / `parm_manifest` / `error_manifest`) named in the sibling spec `docs/SCENE_GROUNDING_CONTRACT.md` **do not exist in code yet** (grep: zero hits) — the token track grounds on the *shipped* `inspect_*` surface and treats the manifests as a forward dependency, never as built.
- **Memory recall uses an inverted keyword/tag/type index, not a vector store** — `MemoryStore._index` (`python/synapse/memory/store.py:174`) with `by_type`/`by_tag`/`by_keyword` sets, consumed by `search()` (`:617`). This is first-hand confirmation for the G6b "No vector store" clause: it is a statement of fact about the substrate, not an aspiration.
- **The composition substrate the memory track needs is real** — `shared/evolution.py` (**778 lines** this session; CLAUDE.md §File-Structure says 593 — stale, cite 778) evolves flat markdown → typed USD → **COMPOSED** ("memory.usd + composition arcs (cross-scene, sublayered)", `evolution.py:9`) via native `Usd.Stage.CreateInMemory()` (`:480`). This is the Charizard tier of §6 in CLAUDE.md.
- **The telemetry (sidecar) side is `FloorGate`** — `python/synapse/core/floor_gate.py`, Tier-0 provenance, "provenance, not admission control" (`:19`), append-only records under `resolve_provenance_dir()` → `$SYNAPSE_PROVENANCE_DIR` else `<repo-root>/.synapse/provenance` (`:109–122`).
- **Naming collision — flag for builders:** `g6_check.py` at repo root is an unrelated **HDA expression-propagation** check for `cinema::camera_rig`. It is **not** the G6 benchmark and shares only the token "G6". The execution workflow must not overwrite or extend it.
- **The token track extends the live `run_turn` agent loop — it is NOT a from-scratch meter.** The earlier survey grepped `python/synapse/**` (excl. `_vendor`) for token-*accumulation* strings (`input_tokens|output_tokens|count_tokens|usage.`) and found only `panel/error_translator.py` — accurate, but scoped to accumulators and therefore blind to the seam that actually produces usage. Re-surveyed this session against the **agent-loop seam**: `python/synapse/cognitive/agent_loop.py:173` `run_turn()` is a **live multi-iteration Anthropic turn runner** (wired via `synapse.host.daemon._process_request` → `run_turn`, `daemon.py:722`; the inspect-tool `Dispatcher` is built in `mcp_server.py._get_inspector_dispatcher`, `:569`) that already (a) drives a real model through `client.messages.create` (`agent_loop.py:232`), (b) dispatches `synapse_inspect_*` through `synapse.cognitive.dispatcher.Dispatcher` (`synapse_inspect_stage` registered at `daemon.py:410`), (c) counts model turns as `AgentTurnResult.iterations` (`agent_loop.py:110`), and (d) holds the response object carrying `.usage` at the `create` yield — **but discards usage**: `_extract_text_blocks(response.content)` (`:247`) keeps only text; `response.stop_reason` is read (`:250`), `response.usage` never is. So the token meter is a *new usage reader over an existing loop*, not a new loop: it adds a `usage` field to `AgentTurnResult` and captures `response.usage` between `agent_loop.py:232` and `:247`. There is no token *accumulator* to extend; there IS a model-turn loop to extend — skipping it would rebuild `run_turn` from scratch, the exact sin the mission forbids. Cost/token metering was previously deferred (see the multi-provider memory note); this reader closes it.

---

## FROZEN CONTRACT (critics may attack; builders may NOT change)

### 1. Latency track — `_benchmark_api.py` + `_benchmark_latency.py` (extend, never rebuild)

**Claim under test:** SYNAPSE's dispatch overhead over the raw handler is bounded and known, and the transport choice (in-process vs hwebserver HTTP) is a measured trade, not a guess.

**Three measurement arms, one identical op set:**

```
                op(cmd)                         measured wall-clock, ms
  ┌──────────────────────────────────────────────────────────────────┐
  │  L0  in-process        SynapseHandler.handle(SynapseCommand)       │  ← NEW arm (the floor)
  │                        no socket, same process, same thread        │
  ├──────────────────────────────────────────────────────────────────┤
  │  L1  hwebserver HTTP    POST /api  (api_adapter.py, :8008)          │  ← _benchmark_api.py (exists)
  ├──────────────────────────────────────────────────────────────────┤
  │  L2  hwebserver WS      ws://…:9999 (hwebserver_adapter.py)         │  ← _benchmark_latency.py (exists)
  └──────────────────────────────────────────────────────────────────┘
   headline comparison  = L0 vs L1  (brief: "in-process dispatch vs hwebserver HTTP round-trip")
   context arm          = L2 (WS) — already measured; kept for the reopen-gate cross-check
```

- **Identical op set (frozen).** The union both scripts already share, aligned so all arms run the same list: `ping`, `get_health`, `get_scene_info`, `get_selection`, `get_parm`, `set_parm`, `execute_python (2+2)`, `execute_python (hou.applicationVersionString)`. Aligning the op set between the two scripts (they currently differ slightly — `_benchmark_latency.py` adds `heartbeat` + `create+delete`) is the first, mechanical deliverable. The op set is a mix of reads (cheap, expose transport overhead) and one mutation class (`set_parm`, exposes the ~2 s floor).
- **The L0 addition.** Add a `--in-process` mode (or a sibling `benchmark(...)` call) to **each** script that constructs a `SynapseHandler`, builds a `SynapseCommand` per op, and times `handler.handle(cmd)` directly — no `urllib`, no `websockets`. Same warmup/iterations/statistics machinery already in both files (`WARMUP`, `ITERATIONS`, `statistics.mean/median`, p95). This arm runs inside hython/Houdini (it touches `hou`), same as the transport arms.
- **Cold + warm, defined.** **Cold** = the first measured call of a fresh process/connection (first `handle`, first HTTP connect, first WS open) — reported as a single-shot number, not averaged. **Warm** = the existing post-`WARMUP` steady-state (avg/med/p95/min/max over `ITERATIONS`). Both scripts already separate warmup from measured; the extension names the first measured call as the cold sample and reports it beside the warm distribution. Cold is where the LATENCY_PLAN "first connect ~70–5250 ms" and connection-context cost live.
- **Reproduce, don't re-derive, the reopen-gates.** Publish the L1/L2 warm read-mix p95 against the three numeric gates already frozen in `LATENCY_PLAN.md` (§"Finish Line + Reopen Gates"). A gate that fires on real data reopens its parked work item — the benchmark is the trigger, per the existing contract. No new instrumentation: numbers read off the script output + `synapse_metrics` histogram buckets that already exist.
- **Meter honesty.** ms via `time.perf_counter()` (already used). No `hou.*` symbol beyond the verified `SynapseHandler.handle`; the L0 arm asserts nothing unprobed.

### 2. Token track — new small meter over the shipped grounding surface

**Claim under test:** SYNAPSE's grounded scene reads (token-budgeted `inspect_*` + `GeoSummary`, degradation ladder) reach a correct result in fewer tokens and fewer turns than a naive full-serialization recipe — and the gap widens with scene size.

- **Identical task set, two recipes.** For each task, run it twice: **(A) SYNAPSE grounding** — the agent reads scene state through the shipped `synapse_inspect_*` tools + `GeoSummary` (and, once merged, the G5 `*_manifest` degradation ladder — forward dependency, not required for v1); **(B) naive serialization** — the agent is handed the whole relevant node network serialized to JSON with no token budget and no summarization (the exact competitor is frozen by **OD-2**). Same task, same success oracle, same model.
- **Three metrics.** `tokens/turn` (per model turn, mean + distribution — from the per-iteration `response.usage`), `tokens/task` (sum of per-turn usage to reach green), `turns-to-green` (model turns until the acceptance oracle passes = `AgentTurnResult.iterations` under the oracle-driven outer loop). The discriminating metric is `tokens/task` at the top tier, where naive serialization blows the context budget.
- **Three scene tiers (frozen shape, fixtures per OD-3):**
  - **T1 — trivial SOP:** ≤5 nodes, the C.0 golden species `Sop/{box,scatter}` (the same species spec-C/spec-D use). The grounding floor — where naive and grounded are close.
  - **T2 — moderate LOP lookdev:** a Solaris stage `Lop/{sphere, materiallibrary, reference}`; this is also where the memory-track Shot-010 scenario lives. The middle — grounding starts to separate.
  - **T3 — complex expression-wired rig:** `cinema::camera_rig` — ~5 internal nodes + 4 sub-HDAs, dozens of expression-wired parms (enumerated in `g6_check.py`). The stress tier — naive serialization overflows; the degradation ladder earns its place. **Fixture reproducibility is OD-3** (procedural, no shipped `.hda`).
- **The token meter — extend `run_turn`, do NOT rebuild it.** The usage reader is a small addition to the *existing* agent loop, not a new one (verified §Ground-truth): add a `usage` field to `AgentTurnResult` (`agent_loop.py:110`) and capture `response.usage` between the `client.messages.create` yield (`agent_loop.py:232`) and the text-only `_extract_text_blocks` (`:247`), accumulating `input_tokens + output_tokens` per iteration. **Field path verified this session** against the vendored SDK — `Message.usage` (`python/synapse/_vendor/anthropic/types/message.py:112`) → `Usage.input_tokens` / `Usage.output_tokens` (`_vendor/anthropic/types/usage.py:26,29`): the standard Messages-API shape the live `anthropic.Anthropic` client returns (no local tokenizer estimate). The **A/B recipe runner** drives `run_turn(client, dispatcher, prompt)` twice per task: recipe A with a `Dispatcher` registered on the shipped `synapse_inspect_*` tools, recipe B with a `Dispatcher` registered on the naive full-serialization tool (competitor frozen by **OD-2**) — same client, same model, same oracle, differing only in the tool surface the agent grounds through. `turns-to-green` = `AgentTurnResult.iterations` under an oracle-driven outer loop (run the deterministic state oracle after the turn; if not green and the budget allows, continue and sum iterations).
- **Acceptance oracle = deterministic, render-free.** Each task carries a post-condition check on scene/stage state (the C-track golden pattern: assert the resulting nodes/parms/attrs, never a rendered pixel — Indie husk no-ops headless, spec-D binding trap). "Green" = the oracle passes. The per-task oracle is authored at build time from this contract; the *mechanism* (deterministic state assertion) is frozen here.

### 3. Memory track — the **Shot-010** benchmark (named benchmark + flagship demo)

**Claim under test:** SYNAPSE can answer a query that is *only* answerable by **composition over an append-only history** — not by replaying or last-write-wins over a lexical log. This is the moat the sidecar boundary (§4) formalizes.

- **The scenario, verbatim as the benchmark name — "Shot-010":** the scene has evolved through an append-only history in which **lookdev** was changed several times and **point-cloud density** was changed several times, interleaved. "Shot 010" names a specific prior *layout* state. The query:

  > **"revert lookdev to Shot 010 layout, keep current point-cloud density"**

- **Why it discriminates (fixture-design rationale, not a benchmarked verdict).** The query is *authored* to require composition: reverting to the Shot-010 point-in-time under a replay / last-write-wins substrate also reverts the density, because both edits are entangled in one timeline. Only **composition** — treating lookdev and density as *separable opinions/layers* that compose, so the lookdev opinion is swapped back to the Shot-010 layer while the current density opinion stays on top — answers it. That is exactly the `evolution.py` COMPOSED (Charizard) tier: `memory.usd` + composition arcs, `Usd.Stage.CreateInMemory()`. This paragraph justifies *why the fixture is built this way*; whether a comparative control is also *built and measured* to fail — and how it is made fair — is **OD-4**, not asserted here as a benchmark result.
- **Meter = binary capability, render-free.** Pass iff the resulting composed stage carries **Shot-010 lookdev AND current density** simultaneously, asserted by a deterministic post-condition on the composed stage (no render). This is a capability gate, not a distribution — it either composes or it doesn't, and it stands alone (always required). The comparative one-line verdict ("composition answered it / append-log could not") is published **only** if **OD-4** rules for a built, fair control (option a); under option (b) the meter reports the capability pass alone, with no comparative claim.
- **Flagship demo.** The same scenario doubles as the public demonstration of the differentiator (recording is OD-3). It is the single clearest "receipts + composition beat a flat log" story in the repo.

### 4. The sidecar boundary — **G6b** (verbatim)

The memory track's result rests on one architectural distinction, stated once, verbatim, and wired to real files:

> **telemetry (lexical, sidecar) records what happened; cognitive state (USD, substrate) records what is true. No vector store.**

- **Telemetry, lexical, sidecar** = the Tier-0 append-only provenance stream: `FloorGate` (`python/synapse/core/floor_gate.py`) writing atomic records under `.synapse/provenance/` (`resolve_provenance_dir()`, `:109–122`). It records *what happened* — the ordered sequence of edits. It is audit, never admission control (`:19`).
- **Cognitive state, USD, substrate** = the composed truth: `agent.usd` / `memory.usd` built by `evolution.py` (COMPOSED tier, composition arcs). It records *what is true* — the current, composed layout you can revert-by-layer.
- **No vector store** = a verified fact about recall, not a slogan: memory search is an inverted keyword/tag/type index (`store.py:174`, `search()` `:617`), and scout's membership authority is an introspected `dir()` symbol table (CLAUDE.md §11), not embeddings. The Shot-010 answer would be *impossible* for a vector-similarity recall over the log — proximity is not composition. G6b is why the memory track measures composition, not retrieval.

### 5. Publication contract — README + methodology (docsurgeon-authored)

Results publish through `README.md` (SCRIBE may not write README; this is the contract `h22-docsurgeon` implements, subject to OD-1):

- A **"Benchmarks"** section (candidate home: near the existing latency line at README `:207` / "Project status" `:299` — exact placement is docsurgeon's editorial call) carrying, per track: the claim, the fixtures, the meter, and the result in the OD-1-ruled form (latency in full; token as ratios + turns-to-green; Shot-010 as pass + demo link).
- A **methodology** paragraph per track: op set / task set, warmup/iteration counts, cold-vs-warm definition, the acceptance oracle, and a pointer to the executable meter (the two extended scripts + the token/memory runners) so a reader can reproduce. Honest-envelope posture: state the ~2 s hwebserver floor and the reopen-gates as *findings*, not hidden.
- **No number in the README that the meter did not produce.** Every published figure traces to a script run over a real session (≥50 measured calls for latency, per the existing finish-line rule).

---

## DoD per deliverable

| # | Deliverable | Done when (acceptance) | Verified by | Gate |
|---|---|---|---|---|
| D1 | **Op-set alignment** across `_benchmark_api.py` + `_benchmark_latency.py` | Both scripts run the identical frozen op set (§1); no op measured in only one | Diff of the two scripts; a run of each prints the same op names | G6 |
| D2 | **L0 in-process arm** added to both scripts | `--in-process` (or sibling call) times `SynapseHandler.handle(cmd)` directly, no socket; same stats machinery | Run under hython prints L0 row beside L1/L2 | G6 |
| D3 | **Cold + warm reporting** | First measured call reported as cold single-shot; warm = post-`WARMUP` avg/med/p95/min/max | Script output shows both columns per op per arm | G6 |
| D4 | **Reopen-gate cross-check** | L1/L2 read-mix warm p95 published against the 3 frozen `LATENCY_PLAN.md` gates | Numbers appear in README methodology; a fired gate names its parked item | G6 |
| D5 | **Token meter + 3-tier task set** | Usage reader added to `run_turn`/`AgentTurnResult` (capture `response.usage` at `agent_loop.py:232`; do NOT rebuild the loop); T1/T2/T3 fixtures stood up; A/B recipes drive `run_turn` twice per task; `tokens/turn`, `tokens/task`, `turns-to-green` (= `AgentTurnResult.iterations`) emitted | Runner output per tier per recipe; oracle passes define "green" | G6 |
| D6 | **Naive-serialization baseline** | Competitor frozen per OD-2; same task, same oracle, same model as recipe A | Side-by-side numbers per tier | G6 (blocks on OD-2) |
| D7 | **Shot-010 memory benchmark** | Append-only history + Shot-010 layout fixture; query resolves to Shot-010 lookdev + current density on the composed stage; render-free post-condition (capability gate — always required). Comparative "append-log control fails" clause per **OD-4**: built + fair under (a), dropped under (b) | Pass/fail capability verdict; comparative control only if OD-4 rules (a) | G6 (comparative claim blocks on OD-4) |
| D8 | **G6b boundary** | Verbatim sentence present; telemetry file + cognitive-state file both named; "no vector store" traced to `store.py` | This spec §4 (already met) | **G6b** |
| D9 | **README publication contract** | Benchmarks section + per-track methodology authored by docsurgeon in the OD-1-ruled form; every number traces to a meter run | README diff; docsurgeon report | G6 (blocks on OD-1) |

## Non-goals (explicit)

- **Not** a rebuild of `_benchmark_api.py` / `_benchmark_latency.py`, nor of `python/synapse/routing/`, nor of any shipped `synapse_inspect_*` tool. Additive extension only.
- **Not** a render benchmark. No golden or oracle renders a pixel (Indie husk no-ops headless — spec-D binding trap). All acceptance is scene/stage-state assertion.
- **Not** a new transport, panel surface, or MCP tool. The L0 arm calls the existing `handle` seam; the token track reads the existing tools.
- **Not** a new agent loop. The token track *extends* the live `run_turn`/`AgentTurnResult` seam (`agent_loop.py:173`) with a usage field — it does not rebuild a model-turn runner. A builder standing up a fresh loop has skipped an existing seam (a DoD #2 violation); STOP and reuse `run_turn`.
- **Not** the `*_manifest` grounding tools — those are the sibling G5 spec (`docs/SCENE_GROUNDING_CONTRACT.md`); the token track uses them if merged, requires only `inspect_*` for v1.
- **Not** the meter's execution. This spec is the design; the execution workflow is authored only after crucible survival + human merge (harness §5).
- **Not** a vector-store retrieval benchmark. G6b forecloses it: recall is lexical + composition, by design.
- **Not** rigging/APEX/materials scope — the T3 fixture is *read* for grounding cost, never authored; no rigging tool is invoked.
- **Does not touch** `g6_check.py` (the unrelated HDA propagation check that collides on the name "G6").

## Deliverable split (for builders, post-merge — execution workflow only)

- **Latency builder:** D1–D4 — extend the two scripts in place; align op set; add L0; cold/warm columns; gate cross-check. Runs under hython.
- **Token builder:** D5–D6 — extend `run_turn`/`AgentTurnResult` with a usage field (capture `response.usage` at `agent_loop.py:232`; do NOT stand up a new agent loop — `run_turn` already drives the model + dispatches `inspect_*` via `Dispatcher`), the three-tier fixtures (OD-3 for T3), the A/B recipe runner over `run_turn`, the deterministic oracles.
- **Memory builder:** D7 — the Shot-010 fixture (append-only history + named layout) and the composed-stage capability post-condition. The append-log control is built ONLY if OD-4 rules for option (a) — using the substrate + fairness bar OD-4 freezes; under option (b) there is no control to build.
- **Docsurgeon:** D9 — the README Benchmarks section + methodology, in the OD-1-ruled form, no untraceable numbers.

Each builder: read the real files named in your row FIRST; keep to "extend, never rebuild"; if the frozen contract proves impossible against the live code, STOP and report the conflict (house rule) rather than improvise.
