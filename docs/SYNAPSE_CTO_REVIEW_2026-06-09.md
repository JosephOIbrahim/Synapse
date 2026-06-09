# SYNAPSE — CTO Codebase Review v2

**Date:** 2026-06-09
**HEAD:** `83f098b` (scout Spike 2.5)
**Scope:** A *delta + blind-spot* review. The 2026-06-05 review (`docs/SYNAPSE_CTO_REVIEW_2026-06-05.md`) covered 8 dimensions and produced `docs/SYNAPSE_HARDENING_PRD.md`. This pass (a) reconciles that PRD against today's code, (b) probes the 8 areas v1 explicitly declared unprobed, and (c) focuses on the two themes the brief mandated: **latency reduction** and **artist usability**.
**No code was changed.** This is a read-only review and a prioritized change backlog. On your approval I'll execute the P0/P1 set.

---

## How this was produced (calibrate trust accordingly)

A multi-agent workflow: **8 dimension reviewers** (PRD-reconciliation, latency hot-path, autonomous-loop safety + egress, multi-client concurrency + safety wiring, render/TOPS live path, durability/DR, artist usability, DX + supply-chain), each grounding findings in `file:line` they opened. Each finding then went to an **adversarial verifier** instructed to *refute* it.

**Three honesty caveats — read before acting:**

1. **The run was interrupted by your monthly spend limit** (`claude.ai/settings/usage`) partway through verification. **All 8 reviews completed; 24 of ~46 findings were adversarially verified; ~22 were not.** This report harvests the completed transcripts directly (no additional spend). Each finding below is tagged **[VERIFIED]**, **[VERIFIED↓ downgraded]**, **[REFUTED]**, or **[UNVERIFIED — verifier cut off]**. Treat UNVERIFIED findings as well-evidenced leads, not adjudicated facts.
2. **Live runtime was only partially exercised.** Houdini is running but the Synapse WS server was not started, so `synapse_ping`/`_health`/`_metrics` failed — no live transport telemetry. I *did* get direct in-process measurements via hython 21.0.671 (below).
3. **The completeness critic never ran** (it was past the crash point). I wrote §6 myself from the v1 blind-spot list + these findings.

**Live measurements I took directly (hython 21.0.671, in-process):**
- `mcp_server` cold import: **0.81 s**, 110 tools registered.
- `SynapseHandler` construction: **1.1 ms**.
- `get_scene_info` handler (read): **0.01 ms** median.
- `create_node` handler called **directly**: **8.6 ms** median / 92 ms max.
- The "~2 s mutation floor" the latency roadmap rests on does **not** appear when handlers are called directly — it lives in the `executeDeferred` dispatch hop. (See L1.)

---

## 1. Bottom line

**The 06-05 PRD's hard security/correctness slice is substantially shipped — and it shows.** Since that review, the bridge defects (S1 double-undo, S2 LOP-stage hash, S3 blast-radius `outputs()`, INT-1 async consent, INT-3 fail-closed), SEC-0 (the `os` NameError that broke DNS-rebinding defense), the D1/D2 posture decisions, and DOC-1 single-sourcing all landed with live-recon evidence and test pins — most within 48 h of the review. The conformance-test discipline did its job: the system is now honest about what it enforces.

**What remains is no longer a "docs lie about safety" story — it's three concrete clusters:**

1. **Memory durability is the real exposure now** (it was rated below the bridge in v1; it shouldn't be). The live `memory.jsonl` is Fernet-encrypted under a **single unescrowed key**, loaded with **silent warn-and-skip**, and rewritten by a **truncating in-place save** with **no backup** — a chain in which one stale key env-var or a missing `cryptography` package **silently and permanently destroys months of accreted memory** on the next write. The atomic primitive to fix it (`write_report`) already ships and is wired to the *new* ledger — just not to the oldest, highest-value artifact. **This is the headline finding.**

2. **Safety wiring went dead in the panel rebuild.** The freeze-detection → backpressure → emergency-halt chain is inert because the v9 panel no longer calls `server.heartbeat()` (the only thing that arms the Watchdog). `EmergencyProtocol.trigger_emergency_halt` remains defined-once/called-nowhere. The built-and-tested autonomous-worker **allowlist** (`worker_policy.py`) is bypassed on the only live path (`enforce_worker_policy=False`, full 110-tool cache). These are *documented* guarantees that are not running.

3. **The expensive paths (render/TOPS) and the multi-client case are structurally unfinished** on lifecycle control: a timed-out main-thread dispatch leaves a **zombie mutation** that executes later while the client was told to retry; the panel's **Stop button stops listening but not the work**; render/cook handlers **block the main thread** polling files; and the documented R8 rollback never runs on the bridge-less live cook path.

**Net:** v1's "more robust than feared, less governed than documented" gap has *closed on the bridge/security axis*. The governance gap migrated to **durability, dead safety wiring, and long-running-op lifecycle** — plus a genuinely **removable ~2 s latency floor** that's currently written off as intrinsic.

---

## 2. What changed since 2026-06-05 (PRD reconciliation)

19 PRD requirements + risk rows, reconciled against HEAD. **7 DONE, 4 PARTIAL, 8 OPEN** (verifier-confirmed where cited).

### DONE (verified)
| ID | Item | Evidence |
|---|---|---|
| SEC-0 | `import os` in hwebserver → origin validation runs | `d70bd0f`; `hwebserver_adapter.py:24,110-111`; `test_phase0c_sec0_hwebserver_os.py` |
| GIT-0 | S1 double-undo fix committed + re-verified live | `26a5132`; `bridge.py:474-489`; Ledger:88 `S1_VERDICT=SINGLE_UNDO_CLEAN` (631+671) |
| DEC-0 | D1 executed — consent posture & docs agree (ungated single-user localhost) | `ed5adee`+`c54d592`; `test_phase0b_consent_posture.py:28,40` |
| INT-1 | Async consent wait — gated op no longer stalls FastMCP loop | `8e3b309`; `bridge.py:515,800-856`; `test_phase0c_int1_async_consent.py` |
| INT-2 | S2 (hash composed LOP stage) + S3 (trace `outputs()`) | `1128b99`+`8576f2c`; `bridge.py:314-330,379`; live recon Ledger:116 |
| INT-3 | `_verify_composition` fails **closed** | `294cbc4`; `bridge.py:907-917`; `test_phase0c_int3_fail_closed.py` |
| DOC-1 | Single-source version + tool count; value-level conformance | `60af892`+`e0fe0ef`; `pyproject.toml:7`==`CLAUDE.md:3`; `test_phase0c_doc1_*` |

### PARTIAL
| ID | Item | What's left |
|---|---|---|
| MEM-1 | `synapse_evolve_memory` revived (`ad4f52e`) | Still points at markdown-overwriting `memory/evolution.py` (not lossless `shared/evolution.py`); companion `open(...,'w')` truncates `memory.md` with no round-trip diff first |
| TEST-1 | hython bridge rollback test | Live verification done + Ledger-recorded, but **no hython CI job** — path regresses silently between manual runs |
| TEST-2 | Tool-count parity DONE (`e0fe0ef`) | Registry→handler parity test still missing — a `TOOL_DEFS` cmd with no handler fails at call time, not CI |
| ARC-1 | D2 doc rewrite DONE (`c54d592`, bridge = audit-only) | Anchors still self-certified literals (`bridge.py:430-431,538-539` stamp `=True`, not measured) |

### OPEN (carried forward into this report's backlog)
`RSI-S` (deposit_fn unwired at science entrypoint), `RSI-F` (router fast-path persistence — but legitimately deprioritized: `MOERouter.route()` has no live caller per `c676999`), `DOC-RSI` (RSI audit not bannered superseded), `SEC-1` (hwebserver has **zero** `check_permission` — a VIEWER can call `execute_python`), `MEM-2` (memory.jsonl still truncating rewrite — **now the top correctness risk**), `MEM-3`/`RSI-E` (deferred-as-decided), `ARC-2` (two WS servers, divergent resilience — drift already bit SEC-0), **EmergencyProtocol** (`bridge.py:987-1005`, called only by its test).

> **Naming trap flagged by the reviewer:** `e6c6a91` "Track C" is the **science-harness allocation gate**, *not* "Line C" Moneta two-tier convergence (MEM-3). Don't let the shipped Track C commit be mistaken for closing MEM-3.

---

## 3. Prioritized change backlog (the deliverable)

Severity is post-verification. Effort: S ≤ ½ day, M ≤ 2 days, L > 2 days. **Tag** = verification status. "PRD" notes overlap with the 06-05 backlog.

### P0 — data-loss risk, now
| # | Change | Tag | Effort | Where |
|---|---|---|---|---|
| **C1** | **Guard degraded memory load.** In `MemoryStore._load`, count `SYNAPSE_ENC_V1:`-prefixed lines that fail to decrypt; if >0, set a `degraded_load` flag that **refuses `save()`/rewrite** and quarantine-copies `memory.jsonl` aside first (the `moneta_store._quarantine_if_corrupt` pattern is already in-repo). Stops a wrong/missing key from converting a recoverable file into a permanent wipe on the next update. | **[VERIFIED]** | S | `core/crypto.py:113-119`; `memory/store.py:285-300,366-377` |

### P1 — material reliability / correctness / latency
| # | Change | Tag | Effort | Where |
|---|---|---|---|---|
| **C2** | **Route `MemoryStore.save()` through the existing atomic primitive** (`write_report`: tmp+fsync+`os.replace`, `backups=1`). The fix is already written, tested, and proven on the ledger — the highest-write-rate artifact is the only one left truncating. *(= PRD MEM-2.)* | **[VERIFIED]** | S | `memory/store.py:366-393` ← `cognitive/tools/write_report.py:83-148` |
| **C3** | **Escrow the Fernet key.** On generation, write `encryption.key.bak` + a one-time "back this up" log; stamp a key fingerprint (`sha256[:8]`) into `index.json` and refuse rewrite-saves on fingerprint mismatch (ties into C1). One 44-byte lost file currently = every project's memory unrecoverable. | **[VERIFIED]** | S | `core/crypto.py:77-102` |
| **C4** | **Kill zombie mutations.** In `run_on_main`, add a per-call `abandoned` flag set under a small lock on `wait()` timeout; `_on_main` checks it and returns without calling `fn()`. Drop "Try again in a moment" for mutating ops (or include the command id) so a retried `create_node`/`execute_python` can't double-apply. | **[VERIFIED↓ P0→P1]** | S | `server/main_thread.py:95-113`; `handlers.py:364-365` |
| **C5** | **Serialize cross-client mutations.** One module-level `threading.Lock` acquired in `SynapseHandler.handle()` for non-read-only commands, skipped on the main thread (already event-loop-serialized). ~10 lines, covers both WS transports. Two clients are live today (panel worker + stdio). *Do not build a queue* (batching is refuted). | **[VERIFIED]** | S | `handlers.py:644`; `websocket.py:331-336`; `hwebserver_adapter.py:211` |
| **C6** | **Investigate & likely remove the ~2 s latency floor.** Stamp `t_enqueue` in `run_on_main` and `t_start` in `_on_main`; export `dispatch_wait_ms` as a second histogram. If it tracks the panel's 2000 ms `_ctx_timer` (strongly indicated — my direct probe shows the handler itself is 8.6 ms), add a thread-safe event-loop wake (`QCoreApplication.postEvent`) after `executeDeferred`. This is the **single largest removable per-call latency in the system**, currently written off by PR #28 as unreachable. | **[UNVERIFIED]** + my live data corroborates | M | `main_thread.py:105-107`; `handlers.py:353-361`; `panel/synapse_panel.py:191-200` |
| **C7** | **Fix panel tool-dispatch timeouts + double-execution.** Share `_SLOW_COMMANDS` into a common module; use per-tool timeouts in the panel HTTP client and Qt wait. On timeout, return a tool-result error ("still running in Houdini — do not retry") instead of `None`, so the worker never re-dispatches a mutation that's still executing. Today: 30/35 s budgets against 120-600 s tools, falling through to re-submit. | **[VERIFIED]** | M | `panel/claude_worker.py:32,222-258`; `panel/tool_executor.py:120,363-368`; `mcp_server.py:186-225` |
| **C8** | **Make Stop honest.** Keep busy-state until the worker thread actually finishes (`worker.finished → _set_busy(False)`), show "Stopping — waiting for current tool…", and best-effort dispatch `tops_cancel_cook`/render cancel when the running tool is `tops_*`/`render*`. Today Stop flips to "Standing by" while Houdini keeps mutating. | **[VERIFIED]** | S | `panel/synapse_panel.py:932-936`; `panel/claude_worker.py:82-84,256` |
| **C9** | **`tops_cook_node` crashes its own error path** — `logger` is undefined at `cook.py:69`, so every PDG cook failure raises `NameError` instead of returning the structured error. One-line import + a failure-path unit test. | **[UNVERIFIED]** high-conf | S | `handlers_tops/cook.py:6-19,69` |
| **C10** | **Re-arm the freeze-safety chain** (or delete the claims). Add a 1 s `QTimer` in the v9 panel calling `server.heartbeat()` (restores Watchdog + backpressure exactly as the legacy panel did); make `_on_freeze` act after a sustained freeze. The panel rebuild removed the only heartbeat source — three documented resilience layers are inert. | **[UNVERIFIED]** | S | `panel/synapse_panel.py` (no heartbeat); `resilience.py:543-575`; `websocket.py:682-707` |
| **C11** | **Move blocking IO off Houdini's main thread.** Split `_render_on_main`: keep only `hou.*` (parm setup + `node.render`) on the main thread; do the up-to-15 s output-file poll + `iconvert` subprocess on the WS handler thread (pure file IO, zero `hou`). Every render currently freezes the UI and the whole `run_on_main` pipeline for the flush+convert window. | **[UNVERIFIED]** | M | `handlers_render.py:342-379,434` |

### P2 — usability / reliability with clear payoff
| # | Change | Tag | Effort |
|---|---|---|---|
| **C12** | **Wire the autonomous-worker allowlist on the live path** — pass `get_anthropic_tools_for_worker()` + `enforce_worker_policy=True` (both built in `66ea293`, both dead in prod), or add a per-call confirm widget for >INFORM tools. 25-iteration unattended loop currently has the full 110-tool cache incl. `execute_python`. *(Facts [VERIFIED]; severity downgraded — consistent with the documented single-user-localhost posture, but the control exists and isn't used.)* | **[VERIFIED↓]** | M |
| **C13** | **`scripts/synapse_doctor.py`** — one PASS/FAIL health command (package json present, API key resolvable, `import synapse`+handler importable, bridge sidecar fresh + WS ping, vendored anthropic intact). Reuses existing primitives. First line of README troubleshooting. | **[VERIFIED]** | S |
| **C14** | **README → v9 truth.** Docs still sell three faces + state→face controller + "it asks first"; v9 ships two tabs + same-pane law + no interactive gate. First-touch artists hunt a Review tab that's gone and expect prompts that won't come. *(Also fix tests badge 3168→3377, `INVENTORY.md` "~1,012 tests".)* | **[VERIFIED]** | S |
| **C15** | **Per-call session identity.** Add `session_id` param to `handle()` (both transports already know it); deprecate the last-connector-wins `set_session_id`. Fix the unlocked `_ws_id` read in hwebserver connect. Today provenance misattributes one client's mutations to the other's session. | **[VERIFIED↓ P1→P2]** | S |
| **C16** | **Surface the husk-on-Indie no-op + wire `tops_render_sequence` validation.** Always run `_validate_rendered_frames` when `output_dir` is known; flag `frames_found==0 && CookedSuccess` as the known Indie silent no-op. An overnight TOPS sequence can "succeed" with zero frames on disk. | **[UNVERIFIED]** | M |
| **C17** | **Wire `render_farm` cancel + real progress.** `RenderFarmOrchestrator.cancel()` has zero callers; the progress callback targets `_broadcast`, which doesn't exist (always `None`). Add a `render_farm_cancel` handler; implement/remove the dead broadcast. | **[UNVERIFIED]** | S |
| **C18** | **Wrap auto-fix render-setting mutations in an undo group + restore.** `_handle_render_settings` does raw `p.set(v)` with no `hou.undos.group`; the farm applies remedies before frame 1 and never restores `initial_settings`. Violates "every mutation reversible" on the most expensive path. | **[UNVERIFIED]** | M |
| **C19** | **Document + gate data egress.** Spell out in CLAUDE.md exactly which scene/selection/memory fields leave to api.anthropic.com; add a redaction/opt-out hook in `build_system_prompt` and a per-tool-result filter in `claude_worker` before `json.dumps`. | **[VERIFIED]** | M |
| **C20** | **Surface determinate cook progress.** `FaceWork.set_cook(done,total)` has zero production callers — the Work face only ever pulses. Have the 4 s health timer poll `tops_get_cook_stats` during `tops_*`/`render*` and call `set_cook`. | **[VERIFIED]** | S |
| **C21** | **Wire the orphaned error translator.** `error_translator.py` (532 lines, coaching tone) has zero importers; chat shows raw API JSON. Two call sites: `_on_error` and the tool-error branch. | **[VERIFIED]** | S |
| **C22** | **Honest connection badge.** Split the in-process-`hou` "connected · Houdini" into measured states (API key present, handler importable, bridge port live) on the existing 4 s timer; the bare-`pass` except means it never reverts. | **[VERIFIED↓]** | S |
| **C23** | **Fix tool-selection guidance.** `houdini_set_parm` description points at non-existent `houdini_inspect_node` (it's `synapse_inspect_node`); six render tools have no when-NOT-to-use lines; `cops_create_network` doesn't say "legacy — prefer `cops_create_copnet`." Add a registry test that every referenced tool name exists. | **[VERIFIED]** | S |
| **C24** | **Port the main-thread stall fast-fail to hwebserver** (the *production* transport lacks `is_main_thread_stalled`; `_backpressure` is constructed but never read). 10-line port from `websocket.py:624-640`. | **[UNVERIFIED]** | S |
| **C25** | **CI: enable coverage + a hou-free perf smoke + a PySide panel lane.** `pytest-cov` is configured but never invoked; 48 panel pins + the G3 audit gate run zero times in CI; no perf regression guard exists. Add `--cov-fail-under`, a `tests/test_perf_smoke.py` (standalone `SynapseServer`, p95 ceilings), and a `windows-latest`+3.11 lane (activates the vendor ABI tests *and* hosts the PySide job). | **[UNVERIFIED]** | M |
| **C26** | **Moneta durability (latent until the flag flips).** Register `atexit close()`, snapshot every N deposits under the adapter RLock, and make `save()` return ok/error instead of swallowing snapshot failures. | **[VERIFIED]** | S |
| **C27** | **Anchor the memory store path.** It falls back to `cwd/untitled.hip` and `$HOUDINI_TEMP_DIR` — the real 977 KB store lives in a home-dir folder literally named `untitled.hip`, invisible to backups; three divergent stores exist. Anchor unsaved projects to one fixed root; migrate on first hip save. | **[VERIFIED]** | M |

### P3 — hygiene
| # | Change | Tag |
|---|---|---|
| **C28** | TTL-throttle scout's freshness recompute (~5 s monotonic cache) — it re-stats 118 rag/ files every call (~5-25 ms). | **[VERIFIED]** |
| **C29** | Kill the 741→fixable warnings: add `SQLiteStore.close()` (155 ResourceWarnings), gate the `asyncio` policy call behind `<(3,16)`, add a `filterwarnings` block. | **[UNVERIFIED]** |
| **C30** | Repo hygiene: delete the Windows-reserved `nul` file, the merged `.patch`, the superseded pentagram HTML, 11 `docs/*.txt` recon dumps; commit the 4 substantive untracked docs; `git rm --cached` the tracked `_*.py` so the ignore rule tells the truth. | **[UNVERIFIED]** |
| **C31** | Remove `DeterministicCommandQueue` (constructed, never enqueued; its always-0 `size()` feeds backpressure + live-metrics — two telemetry surfaces report a queue that isn't there). | **[VERIFIED]** |
| **C32** | Track + surface torn-line skip count in memory status (today silent, then permanently dropped on rewrite). | **[VERIFIED]** |
| **C33** | Single-source `protocol_version` (`mcp_server.py:182`="5.4.0" vs `core/protocol.py:31`="4.0.0"; write-only, no inbound validation) — natural next pin for the DOC-1 conformance harness. | **[UNVERIFIED]** |
| **C34** | Lazy-import scout's numpy/faiss (paid before the stdio server accepts; ~few-hundred-ms cold-start tax). Measure with `-X importtime`. | **[UNVERIFIED]** |
| **C35** | Defer the dormant RSI loop-closures honestly: `DOC-RSI` banner (cheapest), `RSI-S` deposit_fn; leave `RSI-F` parked (no live `MOERouter` caller). | from PRD recon |

---

## 4. What the adversarial pass caught (verifier working as designed)

- **REFUTED — 1:** "Worker dispatches MCP-first → undo/integrity is off the hot path" (P3). False: the `/mcp` server runs in the **same Houdini process** (hwebserver), so undo-wrapping/IntegrityBlock are *not* bypassed. The only accurate part (MCP-first dispatch order) doesn't carry the claimed consequence. Excluded.
- **DOWNGRADED — 5:** zombie mutation P0→P1 (real, but requires a main-thread stall to trigger); worker-allowlist-dead P1→P2 (consistent with documented posture); session-clobber P1→P2; connection-badge and unbounded-growth severities trimmed. All remain real.
- **CONFIRMED — 18**, including the P0 crypto chain (every step reproduced in current code).

This is the discipline working: a finding that couldn't survive an open-the-file refutation was dropped, not shipped.

---

## 5. Load-bearing strengths (keep and protect)

1. **The 06-05 PRD got executed.** A solo maintainer closed the entire bridge/security correctness slice with live recon + test pins in days. The conformance harness (now value-level, DOC-1) is doing the reviewer's job.
2. **The new artifacts are genuinely durable** — ledger records, Moneta snapshots, RecommendationHistory all use tmp+fsync+`os.replace` + generational `.bak`. The durability *pattern* is in-repo and proven; it just hasn't reached the oldest artifact (C2).
3. **Undo nesting is correct under interleaving** — every group opens and closes inside one deferred payload, and `hdefereval` serializes the main thread, so single-command atomicity and per-client FIFO hold. The gap is *cross-client sequence* coherence (C5), not mutation integrity.
4. **The agent_loop (dispatcher) path is tight** — registers only `inspect_stage`, honors cooperative cancel at three checkpoints. The exposed autonomous surface is the *panel worker* (C12), not this one.
5. **Handler compute is fast** (8.6 ms for create_node, 0.01 ms for reads) — the latency budget is in dispatch/wake and blocking IO, both addressable (C6, C11), not in the handlers.

---

## 6. Residual blind spots (the critic never ran — written by hand)

This review still did **not** probe, and a CTO should know these exist:

- **APEX / KineFX / rigging handlers** — `handlers_apex*`, kinefx paths: never examined for correctness or graph-mutation reversibility.
- **COPs/Copernicus live path** (`handlers_cops.py`, ~20 `cops_*` tools) — touched only via the one undo-nesting spot-check; the OpenCL/solver tools are unreviewed.
- **USD/Solaris stage authoring handlers** beyond the bridge's integrity hash — `houdini_modify_usd_prim`, variant/collection/payload tools: composition-arc correctness unprobed.
- **The `science/` harness and FORGE** beyond the RSI-S/RSI-E reconciliation rows — allocation/exposure gate internals (`e6c6a91`) not audited.
- **Auth/RBAC token lifecycle** — v1 verified the primitives; neither pass audited token issuance, rotation, or the `SYNAPSE_DEPLOY_MODE` coupling end-to-end (SEC-1 is still OPEN).
- **`autonomous_render`'s running-loop branch** (`handlers.py:1625-1638`) — flagged as a guaranteed 600 s hang *if the parked hwebserver path is revived*; not exercised because that path is parked.
- **Subprocess egress completeness** — `iconvert` (list-args, timed) and the PowerShell toast (XML-sanitized, but `render_notify.py:131-134` interpolates body into a double-quoted here-string where `$()` is live — latent, not exploitable with current fixed callers). Acceptable for localhost; re-check before any non-local mode.
- **Two unverified-but-high-impact findings the spend limit cut:** C9 (`tops` NameError), C11 (render main-thread block), C16 (husk-Indie), C10 (freeze chain), C24 (hwebserver stall), C25 (CI gaps). Re-run verification when budget allows.

---

## 7. Recommended sequence

1. **This week (P0+top P1, all S-effort, ~2 days):** C1 → C2 → C3 (the memory-loss chain, fix as one unit) → C4 → C5 → C8 → C9. These are small, verified, and close the genuine data-loss + correctness exposure.
2. **Next (the latency + render lifecycle):** C6 (measure first — it may be the biggest single UX win in the system), C7, C11, C13, C14.
3. **Then:** the P2 usability cluster (C12, C19-C23) and the CI gaps (C25) — high artist-trust payoff, low architectural risk.
4. **Decide explicitly** (don't let them rot): EmergencyProtocol — wire to the re-armed Watchdog (C10) or give §1.8 the same live-path-reality banner the bridge got. SEC-1 — required before any non-local deploy mode.

**No code was changed by this review.** Say the word and I'll execute the P0/P1 set (C1-C11) under the same ARCHITECT→FORGE→CRUCIBLE discipline, smallest-version-first, suite-green-per-step.

---

*Provenance: workflow `wf_30327bc1-5ca` — 8 dimension reviews (all complete) + 24/46 adversarial verdicts (run truncated by monthly spend limit; remainder harvested from transcripts and tagged UNVERIFIED). HEAD `83f098b`. Live in-process probes via hython 21.0.671. GATE 6 (scout Spike 2.5) independently verified green: false_phantom_rate 0.0 / true_phantom_recall 1.0 / suite 3377 passed. Harvest artifacts: `<transcript-dir>/_reviews.md`, `_verdicts.md`.*
