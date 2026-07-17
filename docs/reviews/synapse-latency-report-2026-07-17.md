# SYNAPSE Latency Report — 2026-07-17

**Baseline:** SYNAPSE v5.28.0 · Houdini 22.0.368 (Python 3.13.10 / USD 0.26.5)
**Report type:** Evaluation (findings-first)
**Grounding:** committed in-repo instrumentation (cited `file:line`) + prior latency-refactor measurements (v5.16.0 / v5.17.0 investigations; 2026-02-08 hwebserver A/B).

> **⚠ No fresh live run.** The live WS bridge was **DOWN** at report time (HTTP 400, Houdini restarted). Every number below is tagged **COMMITTED** (in-repo constant/instrument), **PRIOR** (a real earlier measurement), or **INFERENCE** (structural reasoning from code). **Zero figures are fresh-measured today.** A live re-measure is a **one-command follow-up** — see §7. Read this as *the observability + leverage map, verifiable by code read*, not as a fresh benchmark.

> **⚠ Substrate note.** Every PRIOR number was measured on **H21** (21.0.671 / Python 3.11). This baseline is **H22**. Whether SideFX changed hwebserver dispatch, cook cost, or USD-write cost in H22 is **UNMEASURED** — which is exactly why the live re-measure is owed on this engine, not just "when convenient."

---

## 1. TL;DR

The latency you *feel* is almost entirely the **LLM/engine turn** — prior live measurement put it at **~95% of each step's wall clock**, with the actual Houdini operations running **1–70 ms** `[PRIOR — CHANGELOG.md:293, v5.17.0]`. This **reframes the long-assumed "~2 s Houdini floor"**: the 2 s was dominated by the per-round-trip LLM turn (and, on one transport, a measured hwebserver dispatch floor) — though **one committed A/B remains unresolved** (`create_node` = 2531 ms on the *websockets* transport with **no LLM in that benchmark loop**, `LATENCY_PLAN.md:198`), which is exactly what the live re-measure settles (§3a). Either way the real lever is **cutting round-trip / turn COUNT and improving PERCEIVED latency** (streaming, warm sessions), *not* shaving dispatch microseconds. **Batching is a proven latency phantom** — the panel worker already multiplexes N tool calls from one assistant turn into a single round-trip `[COMMITTED — claude_worker.py:139-185]`, and a `synapse_batch` tool already ships for *atomicity* (`system_prompt.py:78`), so a batch tool buys correctness, never felt speed; do not build one *for latency*.

---

## 2. Source tags

| Tag | Meaning |
|---|---|
| **COMMITTED** | An in-repo constant, instrument, or code path — verifiable by reading the file right now. |
| **PRIOR** | A real measurement from an earlier session (v5.16.0 / v5.17.0 investigations, or the 2026-02-08 hwebserver A/B). Not re-measured today. |
| **INFERENCE** | Structural reasoning from the code (e.g. round-trip counts, per-call read counts). Not a timed value. |

---

## 3. The measured breakdown

### (a) A single CHAT TURN

Path: panel send → `ClaudeWorker._conversation_loop` → `AnthropicProvider.stream()` (raw SSE) → optional tool dispatch → loop back.

> **Path correction (load-bearing):** the panel chat turn runs the **streaming** worker (`claude_worker._conversation_loop` → `provider.stream()`, `claude_worker.py:149`). It does **not** go through `cognitive/agent_loop.py::run_turn` — that non-streaming runner is the MCP `Dispatcher` / autonomous path. Only the streaming path is on the CHAT axis.

| Stage | Contribution | Tag | Where |
|---|---|---|---|
| Build system prompt (live scene reads) + spawn `ClaudeWorker` QThread | sub-ms – few ms | INFERENCE | `synapse_panel.py:1591-1620` |
| `provider.resolve_key()` (env / `hou.secure` read, no network) | ~0 | INFERENCE | `claude_worker.py:118` |
| **Provider streaming API call** — TLS + upload + server time-to-first-token + full token generation | **DOMINANT (~95% of the step)** | **PRIOR** | `anthropic_provider.py:107-147`; `[CHANGELOG.md:293]` |
| Per-tool dispatch — MCP-first localhost HTTP → hwebserver → main-thread → `hou.*` | **1–70 ms op** *(or the disputed ~2 s hwebserver dispatch floor — unresolved, see below)* | COMMITTED / PRIOR | `tool_executor.py:463-492`; `system_prompt.py:76` |
| Loop-back: append `tool_results`, `provider.stream()` **again** (post-tool synthesis) | **another full LLM turn** — the multiplier | INFERENCE + PRIOR | `claude_worker.py:145-186` |

**Dominant term: the provider streaming API call (the LLM turn).** Everything Houdini-side per tool is 1–70 ms; the turn is seconds.

**Perceived vs wall latency (streaming):** for **text** responses, the user sees progress at **time-to-first-token** — the first SSE `text_delta` flips `_streaming_started`, kills the "thinking" toy, and streams into the transcript `[COMMITTED — synapse_panel.py:1622]`. **Two gaps where streaming does NOT hide latency:** (1) **tool-first / build turns** open straight into a `tool_use` block with *no* text tokens — the user sees a bouncing toy + status chips, not streamed prose `[COMMITTED — synapse_panel.py:1646-1653; claude_worker.py:235]`; (2) **thinking blocks emit nothing** — extended-thinking time is invisible latency before first visible token `[COMMITTED — anthropic_provider.py:255-257]`.

**hwebserver-floor tension (flagged honestly):** the panel's default tool path is MCP-over-localhost to hwebserver. The 2026-02-08 test measured a **~2 s hwebserver main-event-loop dispatch floor** (warm ping 2070 ms, create_node 2082 ms) `[PRIOR — LATENCY_PLAN.md:193-199]`. The later v5.17.0 investigation put ops at **1–70 ms** `[PRIOR — CHANGELOG.md:293]` — but that measured the inner main-thread `fn()` cost, a **different span** than hwebserver's enqueue→dispatch overhead. Which floor a given panel tool call actually pays is exactly what the live re-measure resolves via the `dispatch_wait` vs `main_thread_direct` histograms.

### (b) A NETWORK CREATION (propose → validate → build)

> **Round-trip count (load-bearing):** building an N-node network is **2 WS / main-thread round-trips total — one `propose_graph`, one `instantiate_graph` — independent of N.** The N creates + E wires are batched into a **single** `run_on_main` marshal inside a **single** `hou.undos.group`. It is **not** one round-trip per node. This path is the built realization of the "call-count" lever.

| Contributor | Cost class | Tag | Where |
|---|---|---|---|
| **RT-1 LLM turn** — model emits `propose_graph` (full N-node decl) | **seconds — DOMINANT** | PRIOR + INFERENCE | `handlers_graph_synth.py:38-69` |
| RT-1 WS dispatch + `executeDeferred` wake | ms (small when main thread free) | COMMITTED (wake UNMEASURED on this path) | `main_thread.py:204` |
| RT-1 `validate()` ×1 — ~15–20 in-process `hou.nodeType`/`node` reads (O(N+E)) | sub-ms each; single-digit ms total | INFERENCE + PRIOR | `graph_validator.py`, `graph_oracle.py` |
| RT-1 `store.put` (in-mem dict) | µs | COMMITTED | `proposal_store.py:16` |
| RT-1 FloorGate provenance write (propose is **not** read-only) | sub-ms + `os.replace`; fsync off-thread | COMMITTED | `handlers.py:190`, `floor_gate.py:386` |
| **RT-2 LLM turn** — model emits `instantiate_graph` | **seconds — DOMINANT** | PRIOR + INFERENCE | `handlers_graph_synth.py:71-93` |
| RT-2 **TOCTOU re-validate** ×1 (same ~15–20 reads **again**) | single-digit ms | COMMITTED (runs) / INFERENCE (count) | `graph_builder.py:112-113` |
| RT-2 N × `createNode` inside **one** undo group (5 shown) | **~5–20 ms/node** → a 5-node build ≈ **25–100 ms** Houdini-side (heavier LOPs sit at the top of the 1–70 ms band) | PRIOR (`createNode() ~5–20ms`, LATENCY_PLAN.md:25) + INFERENCE (×N extrapolation) / count COMMITTED | `graph_builder.py:131-160` |
| RT-2 parm set+readback, E × `setInput`, E × conn readback | sub-ms each | PRIOR + INFERENCE | `graph_builder.py:144-160` |
| RT-2 agent.usd provenance receipt (USD write, best-effort, never blocks) | tens-of-ms | COMMITTED (fires) / INFERENCE (cost) | `graph_synth_runtime.py:96` |
| RT-2 FloorGate mutating record for `instantiate_graph` | ~3.5 ms median (fsync now off dispatch thread) | PRIOR + COMMITTED | `floor_gate.py:413` |
| C5 process-wide mutation lock | ~0 uncontended (single-user) | COMMITTED (exists) / INFERENCE (uncontended) | `handlers.py:~223` |

**Dominant term: the 2 LLM turns (one per round-trip).** Everything Houdini-side for the whole 5-node build sums to roughly **tens of ms** (N×createNode + validation×2 + the agent.usd write) — one to two orders of magnitude under a *single* LLM turn. Total wall clock ≈ **2 LLM turns + 2 `executeDeferred` wakes + tens-of-ms of main-thread work.**

**Contrast (why this path exists):** imperative node-by-node building is O(N) tool calls = **O(N) LLM turns**. The 2026-06-25 post-mortem measured an imperative Solaris build burning **25 sequential turns and still not finishing** `[PRIOR — docs/LATENCY_SOLARIS_REVIEW.md]`. propose/instantiate collapses that to **2**. The saving is entirely in round-trip/turn count, **not** in Houdini op cost.

---

## 4. Findings (leverage-ordered)

### F1 — Perceived latency on the BUILD path is the highest untapped lever

- **Leverage:** HIGHEST. Since the LLM turn dominates wall clock and can't be shrunk from inside SYNAPSE, the biggest *felt* win is making the unavoidable wait *legible*.
- **What's weak/missing:** text streaming already gives time-to-first-token for prose `[COMMITTED — synapse_panel.py:1622]`, but the **build path — the exact path with the most LLM turns — has the weakest perceived-latency story.** Tool-first turns emit no text tokens (bouncing toy + status chips only) `[COMMITTED — synapse_panel.py:1646-1653]`, and thinking blocks emit nothing `[COMMITTED — anthropic_provider.py:255-257]`.
- **Why it matters:** the multi-turn build is where users wait longest and see the least. A silent 3-turn build *feels* broken even when every op is 1 ms.
- **Operator impact:** "is it stuck?" anxiety precisely when the system is working hardest.
- **Fix direction:** surface pre-first-token progress on tool-first turns — stream a one-line plan/intent token before the first `tool_use`, and/or promote the per-tool status chips into a visible step ledger ("step 2 of 5: creating karma settings"). Emit a lightweight "thinking…" heartbeat while `thinking_delta` accumulates.

### F2 — Turn-COUNT reduction is the real wall-clock lever — banked, but partial

- **Leverage:** HIGH (this is where actual seconds are saved).
- **What's weak/missing:** the declarative collapse (imperative 25 turns → 1 via `synapse_solaris_build_graph`, plus propose/instantiate → 2 round-trips) is **banked for Solaris** `[PRIOR — docs/LATENCY_SOLARIS_REVIEW.md; COMMITTED — handlers_graph_synth.py]`, but it's **per-domain**. Other imperative build flows still burn O(N) turns.
- **Why it matters:** each avoided turn removes ~one full LLM turn (~95% of a step) from the wall clock — the single largest per-item saving available.
- **Operator impact:** a COPs / TOPS / rig build with no declarative equivalent is still slow *and* can hit the 25-iteration cap `[COMMITTED — claude_worker.py:34, 199-204]`.
- **Fix direction:** extend declarative/Tier-0-recipe coverage to the next-highest-turn domains; keep the system-prompt guidance that steers the model toward single declarative calls `[COMMITTED — system_prompt.py:74-83]`. Prompt-caching already softens turns 2..N of any multi-tool build (18.7k-token tool block → cache reads) `[COMMITTED — anthropic_provider.py:52-71; PRIOR — docs/LATENCY_SOLARIS_REVIEW.md:209]`.

### F3 — Warm-session / cold-start posture

- **Leverage:** MEDIUM-HIGH (one-time-per-session, but large).
- **What's weak/missing:** cold-start was already crushed (MCP cold-start 25 s → <2 s; 2 s auth dead-wait eliminated) `[PRIOR — commits 0d82175, 04c8d0b]`, but first-connect context load still ranges **~70–5250 ms** `[PRIOR — LATENCY_PLAN.md:32]`, and prompt-cache warmth is per-conversation.
- **Why it matters:** the first turn of a session pays connection setup + full prefill that later turns don't.
- **Operator impact:** the first request of the day feels sluggish; later ones snap.
- **Fix direction:** keep services warm (persistent WS, pre-warmed prompt cache); treat first-connect context load as a one-time cost to hide behind a session-open spinner, not optimize on the hot path.

### F4 — Instrumentation blind spots (a latency investigation cannot see the dominant term)

- **Leverage:** MEDIUM (it's the meta-lever — you can't tune what you can't see).
- **What's weak/missing:** **the dominant cost — sequential LLM turn count — is log-only, not a metric** `[COMMITTED — claude_worker.py:190-196]`. **LLM stream time is untimed** (no timer wraps any provider stream). **End-to-end/transport latency is unmeasured in-process** — every timer starts *inside* the handler or *inside* `run_on_main`; the MCP stdio hop, JSON-RPC parse, WS send/recv, and connection setup are invisible. **No percentiles anywhere** — only `avg_ms` + `max_ms` `[COMMITTED — metrics.py:72; router.py:936]`.
- **Why it matters:** a client-perceived slowdown living in transport/reconnect or in a turn-count blowup is **not queryable** from `synapse_metrics` — you'd have to grep logs.
- **Operator impact:** "why was that slow?" has no self-serve answer; every latency question needs a live re-run.
- **Fix direction:** add a **time-to-first-token** histogram, an **LLM-stream-duration** timer, and promote the **turns-per-build** log line to a counter/histogram. Add p50/p95/p99 (the bucketed histograms already support Prometheus quantiles; the panel-inline summary and router avg+max do not). Full map in §5.

### F5 — Batching is REFUTED — name it so nobody re-proposes it

- **Leverage:** NONE (anti-finding).
- **What's refuted:** a batch-tool "selection discipline" latency win was **adversarially refuted** at the PR #28 finish line `[PRIOR — LATENCY_PLAN.md:260-271]`. The mechanism: the worker's conversation loop **already** streams one API response, processes **every** `tool_use` block, and collects all results into a **single** `tool_results` message for the next call `[COMMITTED — claude_worker.py:139-185]`. So **N tool calls from one assistant turn = ONE LLM round-trip already.** A batch tool would only collapse the 20–65 ms localhost hops *under* the LLM-turn cost — invisible on the felt-latency axis.
- **Fix direction:** the batch tool **already exists** — `synapse_batch` (`system_prompt.py:78`: "runs an ordered list of commands in ONE round-trip and ONE undo group"). Its real value is **atomicity + correctness (one undo group), not latency** — do not expect it to move the felt-latency needle, and do not build a second one. If latency is the goal, the lever is turn-count (F2), not hop-count.

### F6 — Attribution hazards inside the existing timers

- **Leverage:** LOW-MEDIUM (correctness of any future read).
- **What's weak/missing:** two dispatch paths cross-contaminate unless you read **both** histograms — worker-path waits land in `dispatch_wait`, inline/main-thread land in `main_thread_direct`, and observe-only envelope captures deliberately opt out of both `[COMMITTED — main_thread.py:223-227]`. A naive read of `dispatch_waits` alone shows `count=0` on the dominant panel path and misattributes the floor. **Batch sub-ops collapse to one sample** under `batch_commands` `[COMMITTED — handlers.py:397-400]`. **The stall detector is a counter, not a timer** — it tracks *consecutive* timeouts, never *how long* the main thread was blocked `[COMMITTED — main_thread.py:142-166]`. **Scene-collect skips are silent** — a too-busy main thread returns empty `SceneMetrics` at debug-log only `[COMMITTED — live_metrics.py:253-260]`.
- **Why it matters:** a future live investigation can draw the wrong conclusion from a partial read.
- **Fix direction:** when re-measuring, always read `dispatch_wait` **and** `main_thread_direct` together (§7); treat `panel_inline_stats()` as the authoritative panel-path timer.

---

## 5. What's instrumented vs blind

### Instrumented (COMMITTED — wired, correct, but empty until the bridge is live)

| Surface | Times | Exposure |
|---|---|---|
| **Per-tool duration** | whole handler (incl. C5 lock + envelope hashes), bucketed | `synapse_tool_duration_ms` `[metrics.py:100]` |
| **Dispatch wait (C6/T1)** | `run_on_main` enqueue→callback wake, **worker path only**, bucketed | `synapse_dispatch_wait_ms` `[metrics.py:120]` |
| **Main-thread direct** | inner `fn()` on inline/main-thread path, bucketed | `synapse_main_thread_direct_ms` `[metrics.py:137]` |
| **Scene-hash (R1)** | topological-hash cost on stage-touching ops, bucketed | `synapse_scene_hash_ms` `[metrics.py:155]` |
| **Panel inline (Qt slot)** | panel main-thread dispatch; count/sum/max + slow-count >1000 ms — **no buckets** | summary `synapse_panel_inline_ms` `[metrics.py:170]` |
| **Router tier latency** | per-tier route resolution; **deque maxlen=1000/tier** | `avg_ms`/`max_ms` via `synapse_router_stats` `[router.py:928]` |
| **Node cook time** | Houdini-native `node.cookTime()` | panel profiler only — **not** in Prometheus `[performance_profiler.py:177]` |
| **Offline benchmark** | end-to-end create/mutation median, ≥50 calls | `_benchmark_latency.py` (manual) |
| **Telemetry flush** | snapshots the above every 60 s → `telemetry.json` (atomic) | the **post-mortem** surface `[telemetry_dump.py:99]` |

### Blind (a latency investigation CANNOT see this today)

- **The dominant term — sequential LLM turn count — is log-only** `[claude_worker.py:190-196]`.
- **LLM / provider stream time is untimed** (no timer around any provider `stream()`).
- **End-to-end / transport latency** (MCP stdio hop, JSON-RPC parse, WS send/recv, connection setup) — every timer starts *inside* the handler.
- **No p50/p95/p99 anywhere** — only `avg_ms` + `max_ms`; panel-inline has no buckets, router exposes only avg+max.
- **Router capped at 1000 samples/tier** — long-run averages unrecoverable `[router.py:921]`.
- **Batch sub-op latency** collapses to one sample `[handlers.py:397-400]`.
- **Stall duration** — the detector counts timeouts, never times the block `[main_thread.py:142-166]`.
- **Scene-collect skips** (main-thread-too-busy — itself a latency signal) are debug-log only `[live_metrics.py:253-260]`.
- **Audit durability** was traded for latency — the per-command audit write is a bare append with **no fsync** `[audit.py:339-340]`; only the 60 s telemetry snapshot fsyncs.

---

## 6. Prioritized upgrade path

Each item carries an **acceptance check** (how you'd know it worked). The three parked items respect the existing **numeric reopen-gates** `[COMMITTED — LATENCY_PLAN.md:285-305]` — do not build one until its gate fires on **real** session data (≥50 measured calls).

### New instrumentation (unlocks every future decision — do first)

| # | Item | Acceptance check |
|---|---|---|
| U1 | **Time-to-first-token histogram** (perceived-latency instrument) | TTFT histogram present in `synapse_metrics`; median TTFT queryable per session |
| U2 | **Turns-per-build counter/histogram** (promote the log-only line) | an imperative 25-turn build vs a 1-turn declarative call is queryable from a metric, not a grep |
| U3 | **LLM-stream-duration timer** (per-provider) | stream wall-time appears in `telemetry.json`; sum confirms the ~95% share live |
| U4 | **p50/p95/p99** on panel-inline + router surfaces | percentiles derivable for all timing surfaces, not just the bucketed four |

### Parked behind numeric reopen-gates (build only when the gate fires)

| # | Item | Reopen gate | Acceptance check | H22 / Dispatcher / RETINA movement |
|---|---|---|---|---|
| U5 | **3b — dirty-flag inspect cache** | `inspect_node`/`inspect_scene` p95 **>250 ms** over a real session **AND** a top-3 `sum_ms` tool | after build, that p95 drops below 250 ms with cache hits on the repeat path | none |
| U6 | **Mile 5 — async render dispatch** | render-tool p95 **>2000 ms** OR `_benchmark_latency.py` median **>2000 ms** | render tool no longer blocks the main thread; freeze detector stays quiet during a render | **⚠ anchor is STALE** — the "~2 s floor" this gate cites was refuted (1–70 ms, v5.17.0); **re-state the anchor before trusting the gate**. RETINA adds per-frame render-path work → may nudge this gate, nothing else |
| U7 | **hwebserver migration (Phase 3)** | read-mix p95 **>5 ms** over a real session **AND** a fresh hwebserver A/B re-measures its prior ~2070 ms ping floor as **<5 ms** | websockets stays primary until SideFX removes the dispatch floor; A/B proves the floor gone | **H22 is the legitimate reason to re-run the A/B** — the ~2070 ms floor was an H21 hwebserver property, UNMEASURED on H22 |

### Cross-cutting movement flags

- **H22** — invalidates *every* prior number (new engine / Python 3.13 / USD 0.26.5). Makes the hwebserver A/B (U7) legitimately re-testable. **The live re-measure is owed on this engine.**
- **Dispatcher (port-wave)** — a strangler-fig retiring the `mcp_server.py` dispatch *branch*; the WS handler stays the execution primitive and the **localhost WS hop remains** `[INFERENCE — docs/PORT_WAVE_MANIFEST.md:30,56]`. Changes *where routing is decided*, not the round-trip cost U7 measures. **Net gate movement: negligible.**
- **RETINA** — orthogonal to transport latency; a render-observation/receipt tier (husk `--postframe-script` sentinel, file-truth). Adds work on the *render* path, touching at most the U6 render-tool gate. **No material movement** on read-mix or dispatch-hop gates.

---

## 7. How to re-measure live (reproducible)

When the WS bridge is back up, this sequence produces fresh numbers and resolves the one open question (which floor the panel tool path pays):

1. **`synapse_ping` ×20** — the WS + main-thread dispatch floor (warm server-side ping was ~0.2 ms `[PRIOR — LATENCY_PLAN.md:195]`; the question is transport + wake).
2. **A read op** — `synapse_scene_info` (or `synapse_inspect_node`) — the read-path latency and the U7 read-mix.
3. **A create op** — `houdini_create_node` — a single mutation through the full dispatch path.
4. **A 5-node build** — `synapse_propose_graph` → (validate happens inside) → `synapse_instantiate_graph` — the **2-round-trip** path; confirm N-node collapse to one marshal.
5. **Pull `synapse_metrics`** — read the Prometheus histograms **together**: `synapse_tool_duration_ms`, **`synapse_dispatch_wait_ms` AND `synapse_main_thread_direct_ms`** (both — see F6), `synapse_scene_hash_ms`. Then **`synapse_live_metrics`** for the ring snapshot.
6. **Optional regression gate** — run `_benchmark_latency.py` for the ≥50-call median that anchors U5/U6/U7.
7. **Resolve the floor** — compare `dispatch_wait` vs `main_thread_direct`: if the panel path shows `dispatch_wait count=0`, its cost lives in `main_thread_direct` (the 1–70 ms class), confirming the v5.17.0 finding over the 2026-02-08 hwebserver floor on this transport.

---

## 8. Closing

The numbers here are **committed or prior, not fresh-live** — the bridge was down (HTTP 400) at report time, so nothing was measured today. The honest map: **the LLM/engine turn dominates both a chat turn and a network build** (prior-measured ~95%), Houdini ops are 1–70 ms, and the "~2 s Houdini floor" is **refuted**. Leverage lives in **perceived latency (streaming the build path), turn-COUNT reduction (already banked for Solaris, extend it), and warm services** — **not** in batching, which the worker's existing multiplexing makes a **proven phantom**. This is **paper only**: the single action item is the §7 live re-measure on H22, which re-anchors the stale Mile-5 gate and settles the hwebserver-floor question the two prior measurements bracket.
