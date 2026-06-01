# SYNAPSE Recursive Self-Improvement (RSI) — Audit & Continuation Report

**Date:** 2026-05-31 · **Method:** 4 parallel read-only deep-dives (FORGE / §16 observability / render-farm / science-harness + memory synthesis), each grounded in `file:line`.

> **One-line finding:** SYNAPSE has **four** RSI systems. Every one has its *observe → analyze → record* half implemented (and often unit-tested), but the *apply → persist → compound* half is **dormant or unwired — usually behind a single small gap.** And the "what we learned / what we ruled out" knowledge is split across **six siloed stores** that should converge on the Moneta substrate. The loops are built; they are not yet **closed**.

---

## Maturity matrix

| System | Observe/Analyze | Persist | Apply/Close-loop | Verdict |
|---|---|---|---|---|
| **FORGE** (`forge/`) | ✅ classify/route/metrics (real) | ⚠️ corpus seeded once, not per-cycle | ❌ fix-gen/apply/re-verify is **prose** | Blueprint-driven, manual |
| **§16 Observability** (`shared/conductor_advisor.py`) | ✅ **live** (panel timer) | ❌ history dormant (0 non-test callers) | ❌ strictly advisory | Half-live readout |
| **Render-farm** (`server/render_diagnostics.py`) | ✅ rules-based diagnose→fix (real) | ⚠️ store exists, **unreachable** | ❌ learning gated behind a never-set attr | Rules loop, no compounding |
| **Science harness** (`python/synapse/science/`) | ✅ find→fix→reverify (real, ran live) | ⚠️ JSONL only; `deposit_fn=None` | n/a (records, by design) | Works; siloed |
| Router self-tuning (`shared/router.py`) | ✅ **live** in `route()` | ❌ in-memory only (dies with process) | ✅ auto-promotes (internal) | Live but ephemeral |

---

## 1. FORGE — "Factory for Optimized Recursive Growth Engine" (`forge/`)
**Real:** the data model + read/transform plumbing are genuine Python — `ScenarioResult`/`FailureCategory`/`CorpusEntry`/`CycleMetrics` (`forge/engine/schemas.py`), `classifier.classify_batch`, `corpus_manager.add_observation/evolve_all`, `metrics.compute_cycle_metrics`. MoE routing of scenarios → agents is real.

**Not real (the self-improvement half):** `orchestrator.py:172-177` increments `fixes_applied += 1  # Optimistic` and **discards the intent — no fix is generated, applied, or written**; `fixes_validated` is hardcoded `0` (`:214`). "Verify via re-run" exists only in `FORGE.md` prose. The corpus (`forge/corpus/`) was seeded by a **one-shot extractor** (`ingest_relay_solaris.py` — all entries `created_cycle: 0`); it does not demonstrably grow cycle-over-cycle, and `forge/corpus/patterns/` (the middle stage) doesn't exist on disk. **No runnable entry point** (no `__main__`/argparse/console-script; `forge cycle`/`forge run` are Claude-Code-interpreted prompts). No tests exercise `forge/engine`.

**Verdict:** blueprint-driven, partially-implemented, **manual**. **Gap to close:** an executable `fix-generate → apply atomically → re-run-verify` stage that sets `fixes_validated`. Until then it can classify and remember but cannot *improve*. (This is the only RSI system whose gap is large, not a one-liner.)

## 2. §16 Recursive Observability Loop (`shared/conductor_advisor.py` + `panel/agent_health.py`)
**Live half:** the Qt panel runs a `QTimer` → `_poll_server_health` → `_update_agent_health` → `get_agent_health()` → **`advise_from_bridge()`** (`panel/agent_health.py:129`), every poll, surfaced as HTML with warn/critical badges. So `analyze()` (bridge health + evolution drift + routing promotions) genuinely runs on a cadence and is shown to the artist. All eight data-flow links from the §16.1 diagram exist in code; the read-only guarantee is test-proven (`test_advisor_never_mutates_inputs`).

**Dormant half:** `RecommendationHistory`, `record()`, `to_jsonl/from_jsonl`, and `analyze_history()` **meta-recursion** have **zero non-test callers**. The panel computes recs fresh each poll and throws them away — nothing persists, nothing reloads, no `(kind,target) ≥5× → escalate` ever fires in production. **Strictly advisory:** there is no recommendation → action edge anywhere (the router's auto-promotion is independent of the advisor).

**Verdict:** ~60% — a live advisory *readout*, not a closed loop. **Gap to close (small):** give the panel/daemon one module-level `RecommendationHistory`, call `record()` + `to_jsonl()` in `_update_agent_health`, `from_jsonl()` at start, and feed `analyze_history()` into the display. That one wiring change activates the entire dormant, already-tested lower half.

## 3. Render-farm "self-improvement" (`server/render_diagnostics.py`, `render_farm.py`)
**Real:** a deterministic rules table — `ISSUE_REMEDIES` (`render_diagnostics.py:55-132`) maps each validation failure (saturation/black_frame/nan/clipping) to priority-ordered `Remedy` objects; `diagnose_issues()` picks the top; `render_farm.render_sequence` applies it via `set_render_settings` and re-renders (≤3 retries). Auto-fix is **on by default**. This works, self-contained.

**Coded-but-dead (the learning):** the cross-session store IS built — `record_fix_outcome()` writes `MemoryType.FEEDBACK` to the memory JSONL, `query_known_fixes()`/`_warmup_from_memory()` read it back. **But the live tool never reaches it:** `_handle_render_sequence` injects memory only `if hasattr(self, '_memory') and self._memory is not None` (`handlers_render.py:858`), and **`SynapseHandler.__init__` never sets `self._memory`** → always `False` → every render runs with `memory=None`, starting from the same static table. Zero compounding, in practice.

**Verdict:** a solid rules-based auto-retry loop wearing a "self-improving AI" jacket. **Gap to close (one line):** in `_handle_render_sequence`, replace the always-false `hasattr` guard with `get_synapse_memory()` (exactly as `_handle_autonomous_render` already does at `handlers.py:1397`). Then record→JSONL→warmup compounds across renders and sessions.

## 4. Science harness (`python/synapse/science/`) + router self-tuning
The harness's find→fix→reverify is genuine RSI: `probe()` (pure, never-raises), the dead-end `Registry` (dedup by `(surface,kind)`, never overwrites a verdict, injectable `deposit_fn`), `run_search` (skip-known/no-rewalk + second-seed gate). It **ran live** (`.synapse/science/apex_registry.jsonl` exists). The MOE router auto-promotes hot fingerprints to `_session_fast_paths` **live inside `route()`** — but in-memory only, dying with the process (the *only* RSI store with zero persistence; the §16 advisor exists precisely to ask a human to hand-promote them into the durable `FAST_PATHS`).

---

## The synthesis: six siloed "what we learned" stores

| Store | Persists at | Decay/consolidation |
|---|---|---|
| FORGE corpus | `forge/corpus/{observations,rules}/*.json` + manifest | promotion only |
| §16 RecommendationHistory | caller JSONL (ring, cap 500) | FIFO |
| Render learned-fixes | the **SynapseMemory store** (FEEDBACK) | inherits backend |
| Science dead-end registry | `.synapse/science/apex_registry.jsonl` | none |
| Moneta + JSONL memory | `.synapse/memory.jsonl` or `.moneta/{snapshot,wal}` | Moneta: decay/consolidation/protected_floor/PruneAudit |
| Router `_session_fast_paths` | **in-memory only** | dies with process |

Only render-fixes ride the unified memory layer; the other five are bespoke JSONL append-logs each re-implementing a subset (dedup, ring buffer, atomic write) of what **Moneta already provides** (decay, consolidation, durability via snapshot+WAL, protected-floor pinning, lossless `PruneAudit`, vector recall). The science registry even has the convergence hook — its `deposit_fn` is documented as "the Moneta/`synapse_write_report` injection point" but is wired to `None`.

**Convergence is the architectural north star** — one durable substrate gives every RSI loop free decay/consolidation, lossless prune-auditing, **vector recall across *all* learned knowledge** (today a render fix can't find a relevant FORGE rule), and one backup surface. **The one real caveat:** falsifiability records (dead-ends, confirmed-absent APIs) must **never decay and never be overwritten** — which conflicts with Moneta's decaying + append/consolidate model. So unification needs **two tiers**: a *protected-immutable* tier for falsifiability/FORGE-rules, and a *decaying* tier for recommendations/render-fixes.

---

## Recommended path to "continue" (ROI-ordered)

1. **Render-farm learning — 1 line, highest ROI.** Wire `get_synapse_memory()` into `_handle_render_sequence` (mirror `_handle_autonomous_render`). Instantly turns the static rules loop into one that compounds learned fixes across renders/sessions. Fully-built code, currently unreachable.
2. **§16 meta-recursion — small wiring.** Add a persistent `RecommendationHistory` to the panel poll (`record`/`to_jsonl`/`from_jsonl`/`analyze_history`). Activates the dormant, already-tested escalation half — a live *loop*, not a readout.
3. **Science registry → Moneta — 1 line.** Pass a `deposit_fn` at the `run_apex_verify` entrypoint so dead-ends/champions persist into the durable substrate (protected tier).
4. **Persist the router's learned fast-paths.** The only zero-persistence RSI store; back `_session_fast_paths` with the substrate so routing knowledge survives restarts.
5. **FORGE — the real build.** Implement the executable `fix-generate → apply → re-run-verify` stage so `fixes_validated` reflects reality and the corpus grows per-cycle. This is the one large item.
6. **Unify on a two-tier Moneta RSI substrate** (protected-immutable + decaying). Keep the well-factored pure-Python *logic* layers; make their *persistence* pluggable onto Moneta. The architecture already anticipates this (`deposit_fn`, `SYNAPSE_MEMORY_BACKEND`); the work is finishing the wiring + adding the protected-immutable tier.

**Theme:** items 1–4 are each ~one wiring change that *closes a loop already 90% built*. They are the cheapest, highest-leverage RSI work in the repo. Item 5 is the genuine engineering. Item 6 is the architecture that makes all of them compound together.
