# Jev on SYNAPSE: where a typed judgment earns its call

Date: 2026-09-20 · HEAD 21ead081 (v5.77.0) · authored by the CTO seat (Fable 5.1) on Joe's word

**Question asked.** What are the most impactful changes Jev (TypeSafe's System One model) can make in this repo?

**How it was answered.** Live TypeSafe docs read first (primitives, confidence, jev-1.13 jaggedness, seven cookbooks). Then one dynamic workflow: 8 read-only cartographers over 8 seams, one triage, one crucible attack per finalist, one docs-fit reshape per survivor, one completeness critic. 30 agents, 806 tool calls, 38 candidates found, 94 rejected as not Jev-shaped, 12 finalists, 8 survived attack, 4 broken. Separately, the ten guards already shipped under `harness/jev/` were graded offline, and the ROUTE guard was re-run with every tier word scrubbed from the mission text.

Producer paths: workflow result `%TEMP%\claude\...\tasks\wafal9tff.output`; guard grade `python harness/jev/jev_grade.py`; leak-free probe ledger `harness/jev/ledger/leakprobe-bp4.shadow.route.jsonl`, `leakprobe-bp8.shadow.route.jsonl`.

---

## 0. The answer in one screen

**Rank 0 is a ruling, not a build.** Six of the twelve finalists, including the one with the strongest artist evidence, put Jev on the product path. Invariant 5 in `harness/jev/README.md:44` says verbatim that nothing under `panel/` or `synapse/` imports Jev. Every product item below is blocked on that one decision. It is Joe's to make, and this report does not make it.

**Shippable today, invariant 5 intact (build-time, in this order):**

1. **Gate-table lint** (`harness/verify/gate_table_agreement.py` + `harness/jev/jev_gates.py`). Six hand-maintained risk tables disagree with each other right now. The deterministic half needs no key and closes real artist blockers U1 and U4. Jev judges only the residual.
2. **Recall-quality oracle** (`harness/jev/jev_recall_oracle.py`). The one function that decides whether a memory is returned has not been touched since 2026-05-31 and nobody can measure it. This oracle is the precondition for every retrieval item below.
3. **CTO SYNTH triage** (`harness/jev/jev_cto.py`). Confirmed findings vanish between VERIFY and BACKLOG. Accounting rule in code first, then Jev dedup per (finding, candidate) pair.
4. **Stale-leg classifier, shadow only** (`harness/jev/jev_stall.py`). Per-leg stall signal is missing in `orchestrate.ps1` today. Code classifies dead / blocked-on-prompt / receipt-exists; Jev sees only the residual.
5. **Scout shadow reranker** inside `scout_eval`. Measure fanout recall for the six conceptual queries first, then grade one Noul per hit.

**Blocked on rank 0 (product path, each with a zero-Jev phase that ships regardless):**

6. **Tool-loop drift nudge** in `claude_worker.py`. Layer A is code only and ships now. Layer B is Jev, off by default, 500 ms hard timeout.
7. **Build-shape hint before the first LLM turn.** Two zero-Jev fixes first, then shadow ledger, then the hint.
8. **Worker denial → consent card.** Phase 1 is no Jev at all: the brake carve-out and an approval card. Phase 2 is Jev labelling the card.

**Broken as proposed, kept as pure-code work:** tool-result verify head, Tier-1 relevance gate, phantom-teaching at ingest, drafted-call usage triage. Their surviving shapes are in section 4.

**Fix the guards that already exist before adding more.** SCREEN has never once said CLEAR and it said REFEREE on the only BROKEN leg. ROUTE has never once chosen the cheap tier on a live `tier: auto` mission. Details in section 2.

---

## 1. What Jev is, in this repo's terms

Jev returns typed answers with calibrated probabilities. Three primitives: Choice (one of a set, max 255), Score (2 to 10 ordered levels, threshold crossing only), Noul (probability that a yes/no condition holds, no confidence field). Many independent questions run in one request over one state. Code owns every decision.

| Fact | Value | Producer |
|---|---|---|
| Model | jev-1.13.0 (alias jev-latest) | docs.typesafe.ai/models |
| Price | $0.042 per million input tokens, output free | docs.typesafe.ai/models |
| Limits | 64k context, 32k state, 1,200 req/min | docs.typesafe.ai/models |
| Latency seen here | 330 to 575 ms median per guard | `harness/jev/ledger/*.jsonl` `latency_ms` |

**What it is not for** (jev-1.13 jaggedness page, and `JEV_BLUEPRINT.md` sec. 7): counting, arithmetic, numeric comparison, dates, hex values, interpolation between Score levels, double negatives, multi-hop reasoning, generation, and anything a regex, symbol table or catalogue answers. It does not treat state as hostile, so artist free text in state is a real exposure.

**The pattern every survivor shares:** code first, Jev in the grey band. Exact-repeat hash before the loop Noul. Symbol table before the usage Noul. Regex telemetry filter before the kind Noul. Allowlisted brakes before the denial Noul. This is also what keeps the bill at fractions of a cent.

---

## 2. The ten guards already shipped: what the evidence says

The blueprint says "its verdicts are recorded, not trusted". Here is what the record shows.

### SCREEN has never shrunk a CRUX read

`python harness/jev/jev_grade.py` replays the ledgered answers under the current policy and four candidates. Zero new Jev calls.

| Policy | n | BROKEN → FLAG | BROKEN → CLEAR (miss) | SOUND → CLEAR | SOUND → REFEREE |
|---|---|---|---|---|---|
| current | 8 | 0 | 0 | 0 | 7 |
| flag-on-contradiction | 8 | **1** | 0 | 0 | 7 |
| clear-conf-0.7 | 8 | 0 | 0 | 1 | 6 |

Reading: under the shipped policy every leg gets a full referee read, so the guard has not saved a token, and the one BROKEN leg (BP4-RULINGS) was not flagged. The `flag-on-contradiction` candidate (`self_contradiction >= 0.6 and crux_need >= 1.5`) is the only one that catches it. n is small. This is evidence for a ruling, not a ruling, but the policy text edit is a one-line diff in `questions.json`.

### ROUTE agrees with authors, and never chooses cheap live

Shadow over authored waves: bp4 7/7, bp8 3/3 at confidence 0.96 to 1.00. Live bp7, the only wave that used `tier: auto`: 6 of 6 missions rounded up to `reasoning` at confidence 0.16 to 0.57. Producer: `harness/jev/ledger/bp4.shadow.route.jsonl`, `bp8.shadow.route.jsonl`, `bp7.route.jsonl`.

**Leak check.** Most mission `note` fields open with a literal `Tier: mechanical (Haiku 4.5)` sentence, and `note` is in the ROUTE state. So the shadow agreement could have been Jev reading the answer off the page. The probe scrubbed every tier and model word from the mission text and re-ran the same guard and policy:

| Wave | Leak-free agreement | Confidence range |
|---|---|---|
| bp4 | 8/8 | 0.96 to 1.00 |
| bp8 | 4/4 | 1.00 |

Producer: `harness/jev/ledger/leakprobe-bp4.shadow.route.jsonl`, `leakprobe-bp8.shadow.route.jsonl` (new files, nothing existing changed). The judgment is real. The open question is why live `auto` missions come back uncertain: the bp7 missions were product-touching (memory, panel, router, transport), so low confidence may be the honest answer, and the round-up is the policy working. Ship a `--scrub` flag in the shadow CLI so this stays checkable.

### The rest

SHAPE shadow is n=4 and the helm card already calls it a smoke test. TEAM and EDGE have never seen a positive case. INCIDENT has no confidence floor in code. DRIFT is shadow only. `harness/jev/tests/` pins the fail-closed behaviour but lives outside `pyproject` testpaths and `ci.yml`, so the pin holds only on a local run. That last one is a five-line fix.

---

## 3. The eight survivors

Each entry: the decision, what decides it today, the pain on record, the surviving shape after attack, the questions as reshaped for jev-1.13, the shadow plan, and the cost. Ranks are post-verdict.

### 3.1 Gate-table drift lint · harness · SOUND-WITH-NITS · effort 2

**Decision.** What risk class a registered tool belongs to. Six hand-maintained tables answer it independently: `OPERATION_GATES` (`shared/constants.py:79-103`), `_TOOL_TO_OPERATION` (`panel/bridge_adapter.py:77-107`), the bridge read-only set, RBAC (`server/rbac.py`), `ENVELOPE_SKIP`, and the `(read_only, destructive, idempotent)` triple per `TOOL_DEFS` row that becomes the MCP annotations external clients act on (`_tool_registry.py:125-127`, `:1780-1791`). Their defaults disagree: missing row is REVIEW on the bridge (`bridge.py:769`) but `set_parameter`/inform on the panel adapter (`bridge_adapter.py:406`).

**Pain on record.** `harness/notes/closeout-2026-09-15/artist_findings.json` U1: the three brakes (`synapse_render_stop`, `synapse_render_farm_cancel`, `synapse_emergency_halt`) sit in the DENIED 36, so the artist "can watch a render they cannot start and cannot kill". U3: `houdini_hda_package` denied while the shipped button prompt names it. U4: six Solaris composites denied although the exemption rationale applies verbatim. The critic verified live that four tools carry `readOnlyHint=True` while the bridge's hand-set read-only list omits them.

**Surviving shape.** Split in two. (a) Deterministic, no key, CI-safe: `harness/verify/gate_table_agreement.py` beside `readonly_hint_agreement.py`. Every non-read-only `TOOL_DEFS` name must be in `_TOOL_TO_OPERATION` (16 missing today, including the three brakes and five U4 composites). Every mapped op must be in `OPERATION_GATES` or a declared exception. Cross-membership printed per tool. Ratchet on the count. (b) Jev, build-time: `harness/jev/jev_gates.py` runs six Nouls over the ~75 mapped non-read-only tools, one tool per request, output a review note under `harness/notes/`, never a table edit. Advise, never promote (CLAUDE.md sec. 2.3 loop F).

**Questions (all Noul, one request per tool, state = name, command, description, input schema keys, first paragraph of the handler docstring; no derived gate in state, it anchors the model on the answer under test):** `describes_effect`, `effect_disk_write`, `effect_destroys_existing`, `effect_launches_work`, `is_brake`, `runs_arbitrary_code`.

**Shadow plan.** Run over all 91 non-read-only tools. Answer keys exist: `is_brake` positives are the DECLARED set in `readonly_hint_agreement.py:40-44` plus `rbac.py:74-77` plus `tops_cancel_cook`, `tops_pause_cook`, `synapse_farm_cancel` (6 positives). `runs_arbitrary_code` positives are `execute_python`, `execute_vex`, the COPs OpenCL tools. Pass is recall 6/6 on brakes with at most 2 false positives.

**Cost.** 91 requests × ~900 tokens ≈ $0.003 per full run. Per handler PR ≈ $0.0001.

### 3.2 Recall-quality oracle · harness · SOUND-WITH-NITS · effort 2

**Decision.** Did this release's recall stack get better or worse on a fixed query set? Today: nobody can say except by scratchpad scripts (`docs/reviews/synapse-review-2026-09-18.md:557,587,593`).

**Pain on record.** Review :541: the keyword scorer "that decides every returned result has not been touched since 2026-05-31 ... six waves of memory work went past the one function". Review :555: `'do I a to in on it up at'` scores 0.90 against the Solaris v3 decision; `'how do I set up a karma render'` scores 0.70 against three superseded Solaris decisions at ranks 1 to 3. The refuter reproduced every number.

**Surviving shape.** Build-time oracle over the live stack, not the mirror. Copy `<storage_dir>/.moneta/` to scratch, open `MonetaBackedStore.from_storage_dir(scratch)` (distinct storage URI, no lock collision), point `SYNAPSE_LOG_DIR` at scratch so 'Vector recall:' lines never reach `~/.synapse/logs` (memory: pytest pollutes the production log). Replay two entry points separately: `search(MemoryQuery(...))` (chat Tier-1) and `recall(q, kinds, limit)` (typed lookup). Pre-label telemetry rows by content-prefix regex in code. Send Jev only the residual pairs with `scorer_score` and `cosine` stripped from state. Precision@k, answer@1 and the IMPROVED/FLAT/REGRESSED line are computed in code.

**Question (Choice, one per returned hit, state = one query + that hit's text and kind):** `rel_{i}` with options `answers` / `on_topic` / `shared_words_only` / `unrelated` / `cannot_tell`, with the review's own headline case written into the criteria (a Solaris recipe returned for a Karma query is `shared_words_only`, not `on_topic`).

**Shadow plan.** The answer key is the review's pinned probe outcomes (:555-593): stopword query → no hit may be `answers` or `on_topic`; banana bread → all `unrelated`; karma render → the three Solaris decisions must not be `answers`; 'Create a Solaris Network' → `mem_9e0826890122` must be `answers`.

**Cost.** ~$0.0004 per run at 15 queries; ~$0.01 at 300.

### 3.3 CTO SYNTH triage guard · harness · SOUND-WITH-NITS · effort 2

**Decision.** At SYNTH, which confirmed findings duplicate an open backlog item, which gate each gets, and whether the closure predicate reads the surface the action changes. Today: one Opus call at effort high (`.claude/workflows/cto-review.js:111-125`); `check_backlog.py:52-59` catches only truncation.

**Pain on record.** `harness/cto/BACKLOG.json` item M1: a confirmed finding vanished between VERIFY and BACKLOG and the run paid to re-derive it. `LEDGER.md:5` crank 1: 61 confirmed / 0 refuted / 10 opened, unauditable.

**Surviving shape.** Code first: an accounting rule where every CONFIRMED/UPGRADED/DOWNGRADED verdict and every refuter 'missed' maps to an opened id, a merged id, or a written scope-out, or PERSIST fails with the count. `policy_touch` is a regex over the action text. Each new closure predicate is run once now. Then Jev: mechanical prefilter to at most 3 candidate open items, one request per finding. A merge at ≥ 0.70 attaches evidence AND appends the finding's predicate to the item's list, so a wrong merge never loses a measurement. Gate is demote-only and never persisted when Jev is absent (the crucible caught that the original would have written a flipped gate to `BACKLOG.json`, which `SPEC.md:44` forbids).

**Questions (one request per finding):** `dup_{i}` Noul per candidate ("same surface AND same wrong behaviour"), `gate` Choice over `auto` / `crux` / `joe` with the three ladder definitions copied verbatim into criteria, `human_step` Noul, `predicate_surface` Noul.

**Shadow plan.** `harness/cto/runs/2026-09-05/report.json` holds 56 CONFIRMED + 5 DOWNGRADED + 23 missed raw findings and the 10 items Opus merged them into. Replay and compare merges.

**Cost.** 61 to 84 requests × ~2.3k tokens ≈ $0.006 to $0.008 per crank, 5 to 10 s wall at concurrency 8.

### 3.4 Stale-leg transcript classifier · harness · SOUND-WITH-NITS · effort 3 · shadow only

**Decision.** When a dispatched leg has written nothing for `StaleMinutes` (40, `harness/orchestrate.ps1:13`), what is it doing: slow work, blocked on a dialog, looping on one error, finished without a receipt, or dead.

**Pain on record.** `orchestrate.ps1:683-685`: trust dialog, "silent, indefinite, indistinguishable from slow work. Cost 13 minutes on 2026-07-26." `:689-694`: "It thought for 2.5 hours and produced nothing." `:437-440`: H3b ran 18 minutes with the board reading 'ready'. Memory blackbox-crash-harness: five silent deaths.

**What the crucible found.** The STALE check at `:973-981` is global, not per leg: `Get-LastProgress` returns the newest jsonl across every project dir matching 'SYNAPSE', including Joe's own interactive session. Three of four stall classes are code-detectable. Fix `:454-457` where pid-dead plus `settings.local.json` reads 'running'.

**Surviving shape.** `harness/jev/jev_stall.py`, inert unless `SYNAPSE_JEV_STALL=shadow`. Code first: make the settle-path resolver recursive over `subagents/**` and `workflows/**` for a per-leg last-write; pre-class dead (pid), blocked (open `tool_use` with no `tool_result` older than 10 min), receipt-exists. Jev only when past StaleMinutes, pid alive, no open tool_use, no receipt, and ≥ 3 new semantic events since the last judgment. Code groups error results by normalized exception type and asks one question per pair it found (never "count the repeats").

**Questions:** `same_retry_{k}` Noul per pair, `test_loop_{k}` Noul per pair, `claims_done` Noul over the final text.

**Shadow plan.** The eight finished bp7/bp8 leg transcripts under `~/.claude/projects/C--Users-User-SYNAPSE--claude-worktrees-<leg>/` paired with receipt presence and the verdict files. No 'on' mode until ≥ 10 shadow rows are graded.

**Cost.** ~$0.00006 per call, cadence-gated.

### 3.5 Scout shadow reranker · product surface is the stdio MCP path only · SOUND-WITH-NITS · effort 2

**Decision.** Which of the RRF-fused candidates become the k=6 snippets the LLM is told to prefer (`python/synapse/cognitive/tools/scout.py:1040-1067`). Today: rank order, no relevance judgment.

**Pain on record.** `harness/notes/receipts/W5-DENSE_eval.md:14-15`: a blind merge regressed conceptual recall 0.833 → 0.667. `:36-41`: shipped conceptual hit-rate 5/6, standing miss `materialx_shaders` for 'build a layered shader network for a hero asset'.

**What the crucible found.** The panel cannot call scout; only the stdio MCP server reaches it. The cited main-thread hazard is a phantom. Two of the three proposed questions are deterministic or unused. State was undercounted about 3×: the real fanout is up to ~72 near-duplicate datasheets, the exact jaggedness-7 shape.

**Surviving shape.** ONE question, `hit_addresses_query_{i}` (Noul), over the RRF top-24 only, each hit carrying `{i, type, context, snippet ≤ 480 chars}` with score, source, domain and id stripped (score leaks RRF position into the judgment). Drop below threshold, stable-sort by (p desc, RRF rank asc), fall back to unchanged RRF if fewer than 2 survive. Phase 1 lives in `scout_eval` and `harness/jev/jev_scout_shadow.py` only. First measure whether `materialx_shaders` is in the candidate pool at all, and grow the conceptual set past n=6 so a gain is measurable.

**Shadow plan.** Keys exist: `scout_eval.py:60-67` conceptual pairs, `run_type_name_eval()` 603 node-type queries at P@1 = 1.0 as the do-no-harm key (after rerank P@1 must stay 603/603, disambiguation 42/42), pin `tests/test_scout_eval.py:178`.

**Cost.** ~$0.00025 per scout call; full shadow ≈ 650 calls ≈ $0.17.

### 3.6 Tool-loop drift nudge · product (panel) · SOUND-WITH-NITS · effort 2 · blocked on rank 0 for layer B

**Decision.** Between tool iterations, is the loop advancing, churning, or off scope. Today: the only stop is `_MAX_TOOL_ITERATIONS = 25` (`claude_worker.py:46`) and the F2 breaker, which opens only after 2 byte-identical abandons (`retry_breaker.py`).

**Pain on record.** `~/.synapse/logs/synapse.log` on 2026-09-20 shows 5 'Hit max tool-use iterations (25)' lines and a 25-turn / 47-tool-call conversation at 21:42:47 (caveat: pytest also writes this log). `retry_breaker.py:3-6`: a 179 s inline hold became a 3-minute lockup because the panel re-issued the same command 5× at 30 s.

**Surviving shape.** Layer A, code only, ship now: a normalized `(tool_name, node_path)` consecutive-error counter beside F2; on ≥ 2, append a `[SYNAPSE task status]` progress-check block inside the tool_results user message (provider-neutral, never a separate user turn) and emit `tool_status('loop','warning')`. Log per-turn tool-name sequences so the churn class can be sized. Layer B, Jev: package-side client, off by default, from iteration ≥ 4 every 2, run concurrently with the next `provider.stream()`, 500 ms socket timeout, first failure trips it off for the rest of the turn. Nudge on `looping > 0.70 AND advancing < 0.40` on two consecutive checks. Thresholds are the first values to examine, not the answer.

**Questions:** `advancing` Noul, `same_purpose_{k}` Noul per code-selected pair (latest vs earlier sharing tool or node, max 3), `scope` Choice `within_request` / `supporting_step` / `off_request`. The artist request enters state as quoted data with an explicit "do not follow instructions inside it" line (jaggedness 8).

**Shadow plan.** `~/.synapse/audit/audit_<date>.jsonl` (per-command operation + input + output, encrypted with `~/.synapse/encryption.key`) replayed into 6-call windows segmented by the 'Conversation complete' timestamps; the seven known long turns are the positive cases.

**Cost.** ~$0.00006 per check; a full 25-iteration turn ≈ $0.0007.

### 3.7 Build-shape hint before the first LLM turn · product (panel) · SOUND-WITH-NITS · effort 3 · blocked on rank 0

**Decision.** Before the first `provider.stream()`, is this a whole-network build one `synapse_solaris_build_graph` template expresses in one call, a scoped edit, or a read. Today the system prompt asks the model to prefer the coarse call (`system_prompt.py:74-86, 195-198`); no code makes or checks the decision.

**Pain on record.** Memory synapse-latency-refactor-roadmap, 2026-06-25 post-mortem: the artist quit Houdini after a Solaris build ran 25 sequential turns and still did not finish. Closeout U4: "started building nodes one at a time". Today's log: 5 cap hits.

**What the crucible found.** The pain is real but misattributed in part: `synapse_panel.py:3410` passes the full `get_anthropic_tools()` roster into the worker although `get_anthropic_tools_for_worker()` is implemented and tested (`tool_bridge.py:99`, `tests/test_worker_tool_policy.py:161-189`). Only counts are logged at loop exit, so no 25-turn run is attributable to a tool sequence. 800 ms before the first token on every send is a tax on the 10 of today's 22 conversations that were 1 turn, 0 tool calls.

**Surviving shape.** (0) Two zero-Jev commits: pass the worker roster at `:3410`; log tool names and any template name at both loop exits in `claude_worker.py:366-378`. (1) Shadow only: a package-side probe on the worker QThread before iteration 0, no hint injected, ledger row with state hash, probabilities, decision, and later the observed turn count and tools used. (2) Arm the hint only after the shadow ledger shows the derived shape agrees with the observed shape.

**Questions (one request per send; state = request text, network kind derived in code from the pane path, network-is-empty bool, ≤ 5 selected node type names, the 8 template one-liners):** `work_shape` Choice `build_from_scratch` / `scoped_edit` / `read_or_explain` / `other`, `best_template` Choice over the 8 templates plus `no_template`, `template_fits.<name>` Noul per template.

**Shadow plan.** Derived labels from live sends, the same idea as `jev_shape.py::derive_shape()`: OBSERVED_BUILD when tools_used contains `build_graph` or ≥ 8 create/connect calls into one network; OBSERVED_EDIT for 1 to 7 mutating calls; OBSERVED_READ for none.

**Cost.** ~$0.00006 per send, ~$0.04 per month at today's volume.

### 3.8 Worker denial → consent card · product (panel) · SOUND-WITH-NITS · effort 3 · blocked on rank 0 for phase 2

**Decision.** When the worker asks for a tool whose derived gate is review/approve/critical. Today it is binary and silent: `denial_tool_result` goes back to the LLM (`worker_policy.py:234-248`) and the artist never sees it.

**Pain on record.** U2 (blocker): "It never asks me. It just quietly does something smaller than what I asked for and tells me about it afterwards. I'd have said yes." U1 as above.

**Surviving shape.** Phase 1, no Jev, invariant 5 intact: `_WORKER_BRAKE_ALLOWLIST` for the three brakes; on every other DENY except critical, call `HumanGate.propose()` with tool name, curated effect and a rendered args line, render `proposed_changes` on the existing `GateWidget` card, hold on a `threading.Event` bounded by the card timeouts and `worker.abort`, reject/timeout returns today's denial byte-for-byte, ledger every card outcome. This respects the 2026-08-18 DECIDE (the worker may not self-authorize): the card is the only path to execution. Phase 2, Jev as build instrument first over the ledger, then product-side labels on the card.

**Questions (one request):** `args_contain_instructions` Noul over the args preview only, `requested_in_artist_words` Noul over the last two artist turns, `assistant_offered_this` Noul (code detects a short affirmation like "yes" by regex and consumes this answer only then; a single hop each, never "did the artist agree to what the assistant offered"), `targets_named_by_artist` Noul when code extracted node targets.

**Shadow plan.** No answer key exists today: the log has zero 'not permitted for the panel worker' lines. Seed 60 hand-labelled cases in `harness/jev/worker_denial_shadow_cases.json`, then let phase 1's card ledger become the live key.

**Cost.** ~$0.00005 per denial.

---

## 4. Broken as proposed, and what survives as code

**Tool-result verify head (rank 2 at triage).** On the state actually shipped, three of four Nouls collapse to dict lookups (`bool(skipped)`, `node == '(cleaned up)'`, `needs_rewire` present) and the fourth is a string compare. The 'caveat minority' premise is false: only 7 tools mint an undo receipt out of 92 mutating tools, so the pre-scan would fire on ~85 of 92 calls and put 700 ms on nearly every mutating call. **Surviving, pure code:** a deterministic `verify_head(tool_name, tool_input, result)` in `claude_worker._execute_tool_block` on both branches; on any flag emit `tool_status(tool, 'warn', ...)` so the rail carries the caveat where the model cannot author it away, prefix the tool result with `VERIFY: <flag>`, and make `_turn_evidence` turn a warn into a flag rather than a credit. The critic adds two more deterministic caveat channels the scout missed: `retina.honesty.*` strings prefixed `inconclusive:` and the detached-farm marker.

**Tier-1 relevance gate (rank 3 at triage).** `TieredRouter.route()` is reached only via the `route_chat` WS command, whose sole sender is the legacy `chat_panel.py`, loaded by an uninstalled `synapse_chat.pypanel`. The shipped panel chats through `ClaudeWorker` and never sends it; the 2026-08-01 scrape recorded `routing.total_requests = 0`. Breaking invariant 5 to gate a tier that serves zero production turns is cost without fire. Two of the three measured pain cases are data defects. **Surviving:** tokenize the query before `memory.search` at `knowledge.py:818`; carry supersession as data (`superseded_by` on the record); the Jev-shaped residue lives in `handlers_memory.py::_augment_with_knowledge`, which is live, and goes shadow-only through the recall oracle (3.2).

**Phantom-teaching at sweep and ingest (rank 6 at triage).** The ingest half would drop whole reference files from the served store on a FIX verdict (entries are one per `.md`, `scout_ingest.py:103-131`), erasing every KEEP warning in the file, the SPEC's named worst failure, with no human gate. The corpus pain is already closed (`LOG.md` FIX-R2, punycode regex-pinned by `tests/test_corpus_encoding_conformance.py`). **Surviving:** sweep-only classifier inside PHANTOM SWEEP over the grey band, replacing the 30-group crucible cap by sending only REFEREE hits to the crucible; zero edits landed without human forge dispatch.

**Drafted-call usage triage (rank 9 at triage).** Both headline cases (`dirtyAllTasks(remove_files=)`, `pdg.PyEventHandler(fn)`) are catalogue lookups against the shipped help zips: `hom.zip hou/TopNode.txt` L110 carries the literal `::dirtyAllTasks(self, remove_outputs)`, and `harness/notes/h7_readjudicate.py` already has a control-passed reader for it. **Surviving, pure code:** extend the H7 reader with an AST walk over kwarg names and arity per `hou./pdg./pxr.` call in `python/synapse` and `shared/`; fix `checks.py:1785` so `check_farm_headless` goes RED on the live `bridge.py:2377` bug; one Noul only for prose-only pages with no signature line (~26 rows).

---

## 5. Cut at triage, with the reason

19 candidates were cut before attack. The recurring reasons: no measured pain (`tier2-command-escalation-check`, `complexity-skips-haiku`, `vex-error-category-choice`, `render-fix-root-cause-choice`, `vex-symptom-nl-classification`); the deciding facts are code booleans (`memory-kind-and-worth-reclassification`, `ci-failure-flake-classify`, `execute-python-scope-check`); zero producers and zero consumers on master (`pgdrm-blocked-tokens-producer`); low frequency behind the DENY list (`autonomy-intent-gate`); adds ~450 ms to the sub-millisecond instant tier, the largest relative regression of the set (`recipe-plan-fit-gate`); covered by a surviving item (`superseded-decision-and-meaning-dedupe-audit`, `turn-transcript-grader`, `tool-error-triage-before-feedback`). The full list with reasons is in the workflow result under `triage.cut`.

The scouts rejected 94 more decision points as not Jev-shaped. That number is the useful one: the repo is unusually disciplined about keeping existence, thresholds and hashes out of any model's hands.

---

## 6. What the critic found missing

- **The external-agent surface has no rail at all.** Every product finalist hooks `panel/claude_worker.py`. The stdio path (`mcp_server.py call_tool → send_command → WS handlers`) and the in-Houdini HTTP path (`mcp/tools.py dispatch_tool`) carry no worker DENY list, no F2 breaker, no loop hook. This is the surface this very session drives Houdini through. The cut rationale for `tool-error-next-step-triage` ("covered by the shipped exact-key breaker") is half true: that breaker is panel-only.
- **Test vacuity at PR time.** Three memory entries record measured pain from tests that pass for the wrong reason (control pinned to the brief's figure, gate-width classes). No candidate. A `predicate_surface`-style Noul over (test, claim) at review time is the shape; it was not scouted.
- **Jev's own tests are outside CI.** `pyproject` testpaths and `ci.yml` never run `harness/jev/tests/`.
- **CLAUDE.md drift in the always-loaded doc.** The status table says "Consent Gate Wiring ✅ Wired to panel" (`CLAUDE.md:459`) while section 1.2.1 says the gate is never reached in production. No test pins it. Every agent reads this on every leg.
- **MEMORY.md has a stale row.** The solaris-harden entry says PR #48 is unmerged; the critic reports `gh` shows MERGED 2026-07-22.

---

## 7. Plain code bugs surfaced on the way (queue independently of Jev)

- `shared/bridge.py:2377` calls `dirtyAllTasks(remove_files=...)`; the live signature is `remove_outputs`, so PDG rollback raises on every call (CLAUDE.md 1.7 already says so; `checks.py:1785` does not go RED on it).
- `render_farm` records `parm_name=''`, so the learn loop is inert.
- `error_translator.translate_tool_error` has zero callers.
- The `SynapseServiceError` branch never trips the circuit breaker.
- `tier3_async` returns a handle nobody polls; Tier 3 is memory-blind.
- Four `TOOL_DEFS` rows carry `readOnlyHint=True` while the bridge read-only list omits them.
- `synapse_panel.py:3410` passes the full tool roster to the worker instead of `get_anthropic_tools_for_worker()`.
- `orchestrate.ps1:454-457`: pid dead plus `settings.local.json` present reads as 'running'.

---

## 8. If Jev goes on the product path: the one adapter

The triage found that every product finalist violates invariant 5 in the same five ways, so the ruling is one decision, not six. If Joe says yes, the shape is:

- A package-side client under `python/synapse/` (never an import of `harness/jev`), questions as data in a JSON file beside it, `TYPESAFE_API_KEY` resolved once via the `providers/base.py resolve_key` pattern and never logged.
- A hard timeout (500 to 800 ms) that never raises and returns None on any failure; offline is byte-identical to today.
- `SYNAPSE_JEV=off` honoured in-product.
- Ledger under `~/.synapse/`, never `synapse.log` and never `harness/jev/ledger`.
- Never inside a `run_on_main` or `main_thread_exec` closure. `dispatcher.py:267` marshals every production tool through the main thread; a network call placed there re-creates the marshal-deadlock class (memory: synapse-marshal-deadlock-class). The call runs on the worker or daemon thread after the marshal returns.
- Shadow ledger graded before any threshold flips. No Jev answer ever grants consent, names a model, or writes a scene.

Latency is asymmetric: the Houdini chat turn already has a ~2 s floor (memory: latency scale-ledger), so 500 ms on an LLM-tier turn is tolerable; the same 500 ms on the sub-millisecond instant tier is the largest relative regression, which is why the recipe gate was cut.

---

## 9. Cost, all items together

| Item | Per call | Per day at today's volume |
|---|---|---|
| Gate-table lint | $0.003 per full run | per PR |
| Recall oracle | $0.0004 to $0.01 per run | per release |
| CTO SYNTH triage | $0.006 to $0.008 per crank | per crank |
| Stale-leg | $0.00006 | cadence-gated |
| Scout rerank | $0.00025 | $0.17 per full shadow |
| Loop drift | $0.00006 per check | $0.70 at 1,000 long turns |
| Build shape | $0.00006 per send | $0.0013 |
| Denial card | $0.00005 per denial | negligible |

Producer: TypeSafe pricing page × token estimates in each finalist's `cost_note`. Cost is not the constraint anywhere. Latency and the invariant are.

---

## 10. Suggested first three moves

1. **Edit `questions.json` SCREEN policy to `flag-on-contradiction`** and add `--scrub` to the ROUTE shadow CLI. One text diff, one flag. The guards already shipped start earning their calls.
2. **Ship the deterministic half of the gate-table lint** with the 16 missing `_TOOL_TO_OPERATION` rows listed by name. Closes U1 and U4's arithmetic half with no key. Add `harness/jev/tests` to CI in the same commit.
3. **Build the recall oracle** against the review's pinned probes. It is the answer key every retrieval item needs, and it turns the 2026-09-18 review's tense from "will" into a number.

Then the rank 0 ruling, with the loop-drift layer A and the denial card's phase 1 shipping either way because neither needs Jev.
