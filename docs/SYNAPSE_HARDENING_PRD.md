# PRD — SYNAPSE Hardening & Trust-Alignment

**Status:** DRAFT — for review
**Owner:** Joseph Ibrahim (sole maintainer)
**Date:** 2026-06-05
**Source:** CTO codebase review (multi-agent workflow `w46nxfiu3` — 8 dimension readers → adversarial crucible verification → synthesis + completeness critic; ~1.58M tokens, 18 agents).
**Verification basis:** Findings are **code-verified at `file:line`** (read/grep against the working tree). They are **not** live-runtime or penetration-verified — the WebSocket bridge was down this session, so security findings describe what the *code does*, not an executed exploit. Findings marked *partial* below were downgraded by the verifier and are flagged.

---

## 1. Summary

The review's one-line verdict: **SYNAPSE is more robust than a skeptic would fear and less governed than its own docs assert — and that gap is the exposure.** The live request path (dict-dispatched handlers, real circuit-breaker taxonomy, inline undo + main-thread marshalling) genuinely delivers reversibility and thread-safety. But it delivers them **through a different mechanism than CLAUDE.md documents**, and the documented central safety layer — `LosslessExecutionBridge` with its four "structural" anchors — **is absent from every live transport**. The consent gate that *should* govern arbitrary code execution exists only inside that unused bridge, and the one path that does wire the bridge explicitly sets `_gate = None`.

This PRD does **not** add features. It aligns the running system with its safety claims — by making the claims true where they must be (code execution, integrity), or changing the claims where enforcement isn't warranted (single-user localhost) — and closes the highest-leverage durability/test/RSI gaps the review verified.

## 2. Problem statement

**The through-line: documentation asserts structural guarantees the running code delivers by accident, partially, or not at all** — concentrated exactly on the load-bearing safety claims:

- "`LosslessExecutionBridge` is the only code path to Houdini / cannot be bypassed" → bypassed on every live transport; the live path produces **no** `IntegrityBlock` and computes **no** `fidelity`.
- "`execute_python`/`execute_vex` are CRITICAL-gated consent ops" → **ungated on both live transports**; the handler execs caller code with full `__builtins__`, no consent, no import filter, no length cap.
- "Consent enforced via `HumanGate`" → the only bridge-wired path sets `_gate = None` and `_panel_consent → True`.
- "Memory persistence is atomic (`.tmp + replace`)" → the *primary* store does a truncating full rewrite (the atomic claim is real only for the advisor telemetry — scope-confusion, but the data-loss risk is real).
- "Evolution is lossless or aborted" → the reachable evolver overwrites live markdown and drops parameters, and the tool that triggers it is dead-on-arrival.
- "Zero hallucinated APIs / verified live" → no emit-time enforcement mechanism exists; it's prose backed by manual recon + mocked tests.

The safety *substance* often still holds — but a single refactor could silently remove a guarantee everyone believes is structural, and the next engineer (or the solo author in six months) would trust an absent layer.

## 3. Goals / Non-goals

**Goals**
- G1. **No live transport executes arbitrary code without the consent posture the docs claim** — either enforce it, or stop claiming it. (Doc/code consent-gap → zero.)
- G2. **Every "verified"/"structural" safety claim in CLAUDE.md is either true on the live path or rewritten** to describe the real mechanism.
- G3. **No zero-persistence or non-atomic safety/memory store** that can lose accreted knowledge on a single crash.
- G4. **A live (hython) CI tier exists** that exercises the Houdini boundary the mocked suite cannot.
- G5. **Every RSI store has a persistence path**; stale audit guidance is retired so no done work is redone.

**Non-goals**
- N1. Panel/UI redesign or new artist features (UI was already redesigned twice; velocity is over-weighted there).
- N2. Studio multi-tenant productization beyond fixing the transport-drift authz gaps.
- N3. Rewriting the handler dispatch path — it's a confirmed strength; protect it.

## 4. Decisions required before/within build (review these first)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| **D1** *(this week)* | Consent posture for `execute_python`/`execute_vex` on live transports | **(a)** Gate at the handler layer (real enforcement; adds a consent round-trip + latency). **(b)** Keep no-auth/auto-approve for single-user localhost and **change the docs** to stop advertising an enforced CRITICAL gate. | **(b) for single-user localhost** today (honest, zero-friction), **(a) required** the moment any studio-lan/vpn/multi-client mode is real. Do not ship the current state where docs promise a gate no transport provides. |
| **D2** *(architectural)* | Fate of `LosslessExecutionBridge` | **(a)** Promote it to the actual live path and *measure* the anchors (not assert `=True`). **(b)** Retire it to integrity/undo-audit-only and rewrite CLAUDE.md §1's "only code path / cannot bypass." | Decide explicitly. **(b)** is cheaper and honest; **(a)** is the bigger bet that makes the original vision real. |
| **D3** | Moneta convergence (two-tier: immutable falsifiability + decaying) | Commit / defer | Defer to LATER, but decide so the six siloed stores stop multiplying. |
| **D4** | FORGE self-improvement | Build the generate→apply→verify stage, or **stop reporting `fixes_validated`** as a metric | Stop reporting the metric until the stage exists (it hardcodes `0` / `# Optimistic`). |

## 5. Success metrics

- M1. `execute_python`/`execute_vex` consent behavior is **identical between docs and code** on all live transports (verified by a test + a doc-conformance assertion).
- M2. No live transport raises before `validate_origin()` (the `os` NameError is fixed and regression-tested).
- M3. The S1 fix is in `git HEAD`; every CLAUDE.md "✅ Verified H21" bridge claim matches committed code.
- M4. ≥1 hython-backed CI job gates the bridge composition-rollback path (today: zero coverage — every CI test takes the `_execute_direct` mock path).
- M5. `memory.jsonl` and `agent.usd` writes are crash-atomic (temp + `os.replace`); a kill -9 mid-write cannot truncate.
- M6. Every RSI store persists across restart; `SYNAPSE_RSI_AUDIT.md` carries a "superseded" banner.
- M7. Single source of truth for version string and tool count; doc-conformance extended from identifiers to **values and magnitudes**.

## 6. Requirements

Priority = build order. **P0 = this week, ≤1 day each, security/correctness.** P1 = this month. P2 = this quarter / architectural. Evidence is `file:line` from the verified review.

### P0 — NOW

| ID | Requirement | Evidence | Acceptance |
|---|---|---|---|
| **SEC-0** | Add `import os` to `hwebserver_adapter.py` — `os.environ.get()` at `:108` raises `NameError` *before* `validate_origin()` at `:109`, so the DNS-rebinding defense is broken on the production transport. | `hwebserver_adapter.py:22-25,108-109` | `connect()` runs origin validation without NameError; regression test asserts a disallowed origin is rejected. |
| **GIT-0** | Commit the S1 double-undo fix (working-tree only) and un-stamp CLAUDE.md's bridge "✅ Verified H21" until re-verified. A `git checkout` today reintroduces the double-undo. | `shared/bridge.py:449-469` (uncommitted) vs `git HEAD`; `CLAUDE.md:797,10,42` | Fix in `HEAD`; CLAUDE.md status matches committed code. *(Note: `SYNAPSE_SCIENCE_HARNESS_v3.md` already correctly marks S1 OPEN — only CLAUDE.md over-claims.)* |
| **DEC-0** | Execute **D1**: make the `execute_python`/`execute_vex` consent posture and the docs agree. | `handlers.py:916-973,1504`; `bridge_adapter.py:166-181`; `constants.py:99` | Either a handler-layer gate exists, or CLAUDE.md §1.2/§11.5 no longer claim one. A test pins the chosen behavior. |
| **RSI-S** | Pass `deposit_fn=<moneta writer>` at the science entrypoint — `registry.record()` already deposits when it's non-None; today falsifiability records never reach the queryable substrate. | `science/registry.py:26,86-87`; `run_apex_verify.py:82`; `test_science_harness.py:323` | Dead-ends/champions persist to Moneta; recall/RAG can surface them. |
| **RSI-F** | Persist the router's `_session_fast_paths` (`to_jsonl`/`from_jsonl`, mirroring `RecommendationHistory`) — the only zero-persistence RSI store, dies every restart. | `router.py:80`; `test_pass8:147-180` | Learned fast-paths survive a process restart. |
| **DOC-RSI** | Mark `SYNAPSE_RSI_AUDIT.md` superseded. Its two highest-ROI claims (observability dormant; render-memory never set) are **already fixed** in live code — acting on the stale doc would redo done work. | `panel/agent_health.py:269-349`; `handlers_render.py:880-882` | Audit doc carries a superseded/curated banner pointing here. |

### P1 — NEXT

| ID | Requirement | Evidence | Acceptance |
|---|---|---|---|
| **SEC-1** | Add per-command RBAC to the hwebserver transport and decouple RBAC enablement from deploy mode. Today hwebserver never calls `check_permission`; an authenticated VIEWER can call `execute_python`. Fixes must land on **both** transports (already drifted). | `hwebserver_adapter.py:54,135-212` vs `websocket.py:540-553`; `rbac.py:185-186` | Both transports enforce per-command roles; a VIEWER token is denied `execute_python` on both. |
| **MEM-1** | Fix or remove `synapse_evolve_memory` — dead-on-arrival: imports `evolve_to_charmeleon` (defined nowhere → `ImportError` every call) and gates on a `target=='charmeleon'` branch `check_evolution` never returns. If kept, point it at the **lossless** `shared/evolution.py`, not the markdown-overwriting `memory/evolution.py`. | `handlers_memory.py:238,250`; `memory/evolution.py:109,214,337` | Tool runs end-to-end or is removed; no ImportError; no live-markdown overwrite; parameters preserved. |
| **MEM-2** | Make `memory.jsonl` writes crash-atomic (temp + `os.replace`), mirroring the advisor's existing pattern. Today `save()` is a truncating full rewrite — a crash mid-save corrupts/truncates accreted memory. | `store.py:366-393,243` | A kill mid-save leaves the prior file intact; test simulates partial write. |
| **INT-1** | Make the consent wait async (`await asyncio.sleep` in `_wait_for_decision`, matching the PDG path) so one gated op can't stall the FastMCP event loop up to 300s. | `bridge.py:491,770-782` vs `:663` | A pending CRITICAL op does not block other MCP requests. |
| **TEST-1** | One hython bridge integration test behind the existing `SYNAPSE_INTEGRATION` gate: drive `bridge.execute()` through `_execute_houdini` with a composition failure and assert single-`performUndo` rollback. The path has **zero** coverage today. *(The `.scout/s1_repro.py` harness from this session is a ready starting point.)* | `bridge.py:_execute_houdini`; `ci.yml:49` | Live job runs and asserts single clean rollback; wired into CI matrix. |
| **TEST-2** | Add a global registry→handler parity test (iterate every `TOOL_DEFS` cmd_type, assert `_registry.has(cmd)`) and a stdio-vs-HTTP tool-count parity assertion (stdio advertises 117, HTTP 110). | `test_mcp_protocol.py:337-356`; `mcp_server.py:628-662`; `mcp/tools.py:52-58` | A tool with no handler fails CI, not call-time; transports report equal tool sets. |

### P2 — LATER (this quarter / architectural)

| ID | Requirement | Evidence | Acceptance |
|---|---|---|---|
| **ARC-1** | Execute **D2**: either make `LosslessExecutionBridge` the live path and *measure* `undo_group_active`/`main_thread_executed` (today asserted `=True` before the group opens), or retire it to audit-only and rewrite CLAUDE.md §1. | `bridge.py:5-6,430-431,514-515`; `IntegrityBlock` grep in `server/` = 0 files | Doc's central guarantee matches running code; anchors measured, not self-certified. |
| **ARC-2** | Converge the two WebSocket servers onto a single resilience-policy layer (hwebserver has rate-limiter + backpressure only — no watchdog, no circuit breaker). | `websocket.py:146-173` vs `hwebserver_adapter.py:274-276,289` | One resilience policy; fixes written once. |
| **INT-2** | S2: hash the composed LOP stage (not SOP intrinsics + cookCount) so integrity isn't blind on the Solaris path. S3: trace `outputs()` as well as `dependents()` in `_infer_stage_touch` to catch SOP→LOP-Import bleed. | `bridge.py:283-321,791`; `_infer_stage_touch` | `delta_hash` detects LOP stage-content change; SOP→LOP-Import wiring flagged. |
| **INT-3** | Make `_verify_composition` fail **closed** (currently returns `True` on any exception → `composition_valid=True` having validated nothing). | `bridge.py:831-837,88` | An exception in validation yields a failure, not a false pass. |
| **MEM-3** | Two-tier Moneta (Line C): immutable falsifiability tier + decaying tier, so never-decay dead-ends converge onto the unified substrate without the decay model eating them. | RSI audit §"synthesis"; `moneta_store.py` | Falsifiability records pinned; recommendations decay. |
| **RSI-E** | Execute **D4**: build FORGE's generate→apply→verify stage or stop emitting self-improvement metrics. | `forge/engine/orchestrator.py:172,214` | `fixes_validated` reflects reality, or the metric is removed. |
| **DOC-1** | Single source of truth for version (CLAUDE.md `v5.8.0` vs `pyproject.toml 5.10.0`) and tool count (43/104/108/110/111/117 across docs). Extend `_conformance.py` from identifier-presence to **values and magnitudes** (line counts stale 18–44%; §16.4 threshold values unguarded). | `CLAUDE.md:3`; `pyproject.toml:7`; `_conformance.py:57,74` | One version string; conformance fails on value/magnitude drift; STATUS table reflects shipped Phases 4/5/6. |

## 7. Deferred — needs separate review/PRD (completeness critic)

The CTO review covered 8 dimensions but **did not probe these**. They are recorded, not dropped; several are higher-stakes than parts of §6 and should be scoped as follow-ups. **Do not assume these are safe.**

| Area | Why it needs its own review |
|---|---|
| **Autonomous LLM worker path** (`panel/claude_worker.py`, `cognitive/agent_loop.py`) | The worker loops API calls "until Claude stops requesting tools" armed with the **full unfiltered** tool cache (incl. `houdini_execute_python`) through the **same neutered-consent** bridge singleton. An LLM — not a human — can autonomously emit arbitrary in-DCC Python with auto-approved consent. The human RCE path was reviewed; this one wasn't. *(The other loop via `dispatcher` is safely scoped to inspect+write_report.)* |
| **Multi-client concurrency** on the single Houdini main thread | No max-client cap or global dispatch semaphore. Two clients (panel LLM worker + a Claude Desktop stdio client) interleaving mutations: are undo groups still well-nested? Does the `len`-based `decision_NNNN` counter race? No concurrent-client test exists. |
| **`EmergencyProtocol` is a dead safety feature** | `trigger_emergency_halt` is documented as a core guarantee (CLAUDE.md §1.8 / Safety Rule 11) but is **defined once and called nowhere**; the Watchdog that detects 5s freezes doesn't wire into it. Same "documented-but-unreachable" class as the bridge. |
| **Render-farm / TOPS live-path rollback** | The R8 PDG rollback was verified *in the bridge* — but live TOPS cooks run through `handlers_tops/` on the bridge-less transport, so the documented `dirtyAllTasks` rollback almost certainly doesn't apply. Subprocess egress (`iconvert`, toast) looked contained but unverified. |
| **Supply-chain** (22MB vendored Anthropic SDK + transitive deps) | Pinned `anthropic`, `pydantic_core` (compiled), `httpx`, `certifi`, etc., checked in and force-un-ignored. No CVE/dependency scanning in CI; manual-bump maintenance burden; an egress TLS client for a tool that also opens a localhost RCE port. |
| **Data egress / privacy** | What scene data, asset paths, and `memory.jsonl` decision records get serialized into Anthropic API prompts? No data-classification, redaction, or opt-out. For studio-lan/vpn modes, client content leaves the network to a third-party API, undocumented. |
| **Disaster recovery** beyond single-write atomicity | No backup/snapshot-rotation for `memory.jsonl`, `agent.usd`, or `.synapse/science/*.jsonl`. One corrupting crash or bad evolution destroys all accreted memory with no recovery point. "Lossless" is per-operation undo, not across disk corruption. |
| **Performance / scale envelope** | No load test, latency budget, or memory-growth bound. JSONL grows forever (evolution is detection-only); no perf regression guard in CI — the very latency the "latency-finish" PR chased ships unguarded. |

## 8. Risks & dependencies

- **R1.** Several P0 items touch the security boundary; D1 must be decided *before* SEC-/DEC- work or it churns.
- **R2.** Bus factor = 1. The conformance/canonical-pin tests are the de-facto reviewer — extend them (DOC-1) rather than rely on a second human.
- **R3.** Findings are code-verified, **not** live-runtime-verified (bridge was down). Before claiming any security item "fixed," re-verify against a running build (`synapse_ping` first — the SessionStart banner is stale) or hython.
- **R4.** Fixes that touch transports (SEC-1, ARC-2) must land on **both** WebSocket servers — they have already drifted.

## 9. Appendix — provenance

- Review run: workflow `w46nxfiu3`, dimensions: architecture, substrate-correctness, test-strategy, rsi-closure, security, api-hygiene, memory-provenance, release-velocity.
- Each finding was produced by a dimension reader and independently confirmed/refuted by an adversarial `crucible` verifier opening the cited `file:line`. Findings the verifier *refuted* are excluded; findings marked *partial* are flagged inline.
- This PRD is a derivative artifact; the authoritative finding set is the workflow result. No code was changed by the review.
