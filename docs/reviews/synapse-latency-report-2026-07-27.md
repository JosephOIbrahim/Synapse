# SYNAPSE Latency Report — 7.27.2026

**Baseline:** SYNAPSE v5.40.0 · Houdini 22.0.368 (Python 3.13.10 / USD 0.26.5)
**Report type:** First-principles ledger (where the time actually goes, ranked)
**Grounding:** committed code (cited `file:line`, re-verified today where load-bearing) + prior measurements (v5.16.0/v5.17.0 investigations, 2026-02-08 hwebserver A/B) + the 2026-07-17 latency report (`docs/reviews/synapse-latency-report-2026-07-17.md`), whose evidence tags carry forward.

> **⚠ Still no fresh live run.** The live WS bridge was **DOWN at report time** (ws://localhost:9999/synapse handshake timeout, ×2) — and the SessionStart hook reported it *connected*, which is itself a finding (F6). Tags: **COMMITTED** (verifiable by reading the file now), **PRIOR** (real earlier measurement, all on H21 unless noted), **INFERENCE** (structural reasoning). The §7-17 one-command live re-measure is **still owed** and remains the single highest-value next measurement.

---

## 1. First principles: the five places a request can spend time

Every SYNAPSE request, on any path, decomposes into exactly five cost bins. Everything below hangs off this ledger.

| Bin | What it is | Measured class | Tag |
|---|---|---|---|
| **T1 — LLM turn** | provider TLS + prefill + time-to-first-token + full generation, ×(number of round-trips) | **seconds per turn, ~95% of a step's wall clock** | PRIOR `[CHANGELOG.md:293, v5.17.0]` |
| **T2 — Transport hop** | WS send/recv, JSON parse, MCP stdio hop | ms class on websockets; the disputed ~2 s floor was an **hwebserver** property `[PRIOR — LATENCY_PLAN.md:193-199]`, unmeasured on H22 | PRIOR / INFERENCE |
| **T3 — Main-thread wait** | `run_on_main` enqueue → `executeDeferred` wake → slot on Houdini's one thread; 10 s default timeout | ms when main thread is free; **unbounded-feeling when it is not** — this is the queue where all contention lands | COMMITTED `[main_thread.py:20, 204, 311]` |
| **T4 — Houdini op** | the actual `hou.*` work inside the marshal | **1–70 ms** per op; ~5–20 ms per `createNode` | PRIOR `[CHANGELOG.md:293; LATENCY_PLAN.md:25]` |
| **T5 — Provenance/disk** | FloorGate record (~3.5 ms median, fsync off-thread), agent.usd receipt (tens of ms, best-effort), audit append (no fsync) | ms class, deliberately kept off the hot path | COMMITTED + PRIOR `[floor_gate.py:413; audit.py:339]` |

**The first-principles verdict is unchanged and now twice-derived: T1 dominates by one to two orders of magnitude.** A 5-node Solaris build spends *tens of milliseconds* in Houdini (T3+T4+T5) and *multiple seconds per LLM round-trip* (T1). Latency work that does not reduce **turn count** or improve **perceived progress during a turn** is working on the wrong bin.

---

## 2. Where the most latency is experienced — ranked

### #1 — Turn count on imperative build paths (T1 × N)

The wall-clock killer. Imperative node-by-node building costs O(N) LLM turns; the 2026-06-25 post-mortem measured an imperative Solaris build burning **25 sequential turns without finishing** `[PRIOR — docs/LATENCY_SOLARIS_REVIEW.md]`. The declarative collapse (propose_graph → instantiate_graph = **2 round-trips independent of N**, one marshal, one undo group `[COMMITTED — handlers_graph_synth.py; graph_builder.py:131-160]`) is banked **for Solaris only**. COPs, TOPS, and rig builds still burn O(N) turns and can hit the 25-iteration cap `[COMMITTED — claude_worker.py:34]`. **Biggest remaining lever: extend declarative coverage per-domain.**

### #2 — Invisible waiting inside a single turn (perceived T1)

Tool-first turns emit no text tokens — the user sees a bouncing toy, not progress `[COMMITTED — synapse_panel.py:1646-1653]`; thinking blocks emit nothing `[COMMITTED — anthropic_provider.py:255-257]`. The build path — exactly where turns multiply — has the weakest perceived-latency story. A silent 3-turn build *feels* broken at 1 ms/op. Fix direction unchanged from 7-17 F1: step ledger + thinking heartbeat.

### #3 — Main-thread contention and the serial connection loop (T3)

Two structural facts compound here, both re-verified on today's tree:

- **The per-connection message loop is strictly serial** — `for message in websocket:` → `self._handle_message(...)` `[COMMITTED, verified today — websocket.py:471-484]`. A long-running op queues every later message on that connection **including cancellation**. This is the mechanism behind "cancel is unreachable" (open item, marshal-deadlock memo).
- **`run_on_main` waits up to 10 s default** `[COMMITTED — main_thread.py:20, 311]` and raises on timeout — bounded, good — but a busy main thread (cooking, rendering) makes *every* queued op pay the full wait serially behind #1's loop.
- The render path was the historical worst case (`node.render()` inside an **untimeout** vendor marshal froze Houdini); the bounded-render fix landed 2026-07-18 — mitigation shipped, freeze class closed for the 6 render tools, but the serial-loop cancel gap above still applies to everything else.

### #4 — Cold start / first-connect (one-time T1+T2)

Cold-start was crushed (MCP 25 s → <2 s `[PRIOR — commits 0d82175, 04c8d0b]`), but first-connect context load still ranged **~70–5250 ms** `[PRIOR — LATENCY_PLAN.md:32]` and prompt-cache warmth is per-conversation. One-time per session; hide it, don't optimize it.

### #5 — The unresolved transport floor (T2, H22-unmeasured)

The 2026-02-08 A/B measured a **~2070 ms hwebserver dispatch floor** vs the v5.17.0 finding of 1–70 ms inner-op cost — different spans, never reconciled live, and **every PRIOR number is an H21 number**. H22 makes the A/B legitimately re-testable (7-17 report U7). Websockets stays primary until a fresh A/B shows the floor gone.

### Refuted — do not re-propose

**Batching for latency is a phantom** (7-17 F5, adversarially refuted at PR #28): the worker already multiplexes N tool calls from one assistant turn into **one** round-trip `[COMMITTED — claude_worker.py:139-185]`; `synapse_batch` exists for atomicity, not speed.

---

## 3. Findings new since 2026-07-17

- **F6 — The "connected" signal lies, and that is a latency incident class.** SessionStart reported the bridge connected; two pings timed out. Every workflow that trusts the stale signal pays a full timeout+diagnosis cycle before real work starts. The ping-first discipline (memory: `synapse-bridge-verification`) should be mechanical: the hook should ping, not read state.
- **F7 — Serial WS loop verified at the current line** (`websocket.py:471`). Prior note cited the same line from an older tree; today's read confirms it survives — the cancel-unreachable gap is live, not historical.
- **F8 — Render freeze class mitigated** (bounded-render fix, 2026-07-18 + `scripts/render_watch.ps1`) — downgrades the worst historical T3 case from "freezes Houdini" to "bounded wait". The 7-17 U6 gate anchor was already flagged stale; this reinforces re-stating it before trusting the gate.

---

## 4. Instrumentation state (unchanged — the blind spots still blind)

The dominant term is still unmeasurable from inside: **LLM turn count is log-only** `[claude_worker.py:190-196]`, **provider stream time is untimed**, **no percentiles anywhere** (avg+max only), transport is invisible (all timers start inside the handler). The four U1–U4 instruments from the 7-17 report remain the unlock-everything-else work and none have landed. Full map: 7-17 report §5.

---

## 5. What to do, in order

1. **Bring the bridge up and run the 7-17 §7 re-measure** (ping ×20 → read op → create op → 2-RT build → pull `synapse_metrics` reading `dispatch_wait` **and** `main_thread_direct` together). One session; resolves the only open measurement dispute on this engine.
2. **Land U1–U4 instrumentation** (TTFT histogram, turns-per-build counter, LLM-stream timer, percentiles) — you cannot tune T1 while T1 is a grep.
3. **Extend declarative build coverage** to the next-highest-turn domain (COPs or TOPS) — the only lever that removes whole seconds per item.
4. **Ship perceived-latency on tool-first turns** (step ledger + thinking heartbeat) — the highest felt-latency win per unit effort.
5. **Fix the SessionStart connected-check to ping** — cheap, removes a recurring false-start cost.
6. Leave U5/U6/U7 parked behind their numeric reopen-gates; re-state the U6 anchor first.

---

## 6. Closing

From first principles, SYNAPSE's latency is not a Houdini problem and not a transport problem — Houdini-side work is milliseconds and provably batched into single marshals. It is a **conversation-shape problem**: seconds-per-turn multiplied by turn count, experienced through a UI that goes silent exactly when turns multiply, on a main thread whose contention queues serially behind a loop that can't be interrupted. The three levers, in order of seconds saved: fewer turns, visible turns, interruptible queue. Everything else is tuning the 5%.
