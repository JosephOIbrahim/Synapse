# SYNAPSE — CTO Codebase Review

> **Standalone report — safe to share with another reviewer (e.g. Claude Desktop).** It carries its own context; you do not need the codebase open to read it, though every finding cites `file:line` so claims are checkable if the repo is shared.

**Date:** 2026-06-05  
**Subject:** SYNAPSE — a Houdini 21 VFX-pipeline orchestrator that exposes ~110 MCP tools to LLM agents over a WebSocket/stdio bridge. Headlined by a *Lossless Execution Bridge* (undo/thread/consent/integrity safety anchors), an MOE router, a Pokémon-style memory-evolution system, and several recursive-self-improvement (RSI) loops. Solo-developed; ~1,430 Python files, 138 test files, 305 markdown docs.  
**Companion artifact:** a remediation PRD derived from this report — `docs/SYNAPSE_HARDENING_PRD.md`.

## How this review was produced (so you can calibrate trust)

A multi-agent review: **8 dimension specialists** (architecture, substrate-correctness, test-strategy, rsi-closure, security, api-hygiene, memory-provenance, release-velocity) each mapped findings grounded in concrete `file:line` evidence. An adversarial **crucible verifier** then independently opened each cited location and marked every finding **CONFIRMED**, **PARTIAL** (real but overstated/mislocated), or **REFUTED**. A synthesis pass produced the executive assessment; a completeness critic enumerated what the review itself did *not* probe.

**Verification basis — important:** findings are **code-verified** (the source at `file:line` says what's claimed) but **NOT live-runtime or penetration-verified** — the live Houdini bridge was down during the review, so security findings describe what the code *does*, not an executed exploit. Treat REFUTED findings as excluded and PARTIAL findings as caveated. This is the project's own 'Floor' discipline (verify before asserting) turned on the project. **Engage critically — this review can itself be wrong; the `file:line` citations are there so you can check.**

---

# Part I — Executive Assessment

# SYNAPSE Codebase Assessment — CTO Final Report

## 1. Bottom line

SYNAPSE is a **genuinely well-architected request pipeline with a safety story that does not match its documentation**. The live path is clean: dict-dispatched handlers, a real circuit-breaker error taxonomy, inline undo-wrapping and main-thread marshalling that *substantively* deliver the reversibility and thread-safety guarantees — just through a different mechanism than the docs claim. The single biggest structural strength is the **MOE router + conformance-test discipline**: pure-Python, drift-pinned, and the de-facto stand-in for a missing human reviewer. The single biggest risk is that the **`LosslessExecutionBridge` — the document's central safety promise — is absent from every live transport**, so the four "structural" anchors (undo/thread/consent/integrity, with `fidelity=1.0`) are computed *nowhere* on the path real clients use, and the one place the bridge *is* wired explicitly neuters its consent gate. Net: the system is more robust than a skeptic would fear and less governed than its own docs assert — and that gap is itself the exposure.

## 2. Load-bearing strengths (keep and protect)

1. **Clean dict-dispatched request path with a real error taxonomy.** `handlers.py:303` `handle()` does registry lookup + `normalize_command_type()` fallback; `handlers.py:345-368` separates user/value errors (no circuit-breaker trip) from service errors, and `websocket.py:645-654` trips the breaker only on genuine service faults. A bad-input LLM cannot open the breaker. This is the maintainability backbone — protect it.

2. **Undo + thread safety are actually enforced inline on the live path.** 37 `hou.undos.group()` sites across 8 server files; mutating handlers wrap `hou.*` in an `_on_main` closure via `run_on_main()` (`handlers_node.py:51-117`). The safety guarantee holds — *via the handlers, not the bridge*. Keep this, and document it as the real mechanism.

3. **The MOE router is the strongest-tested subsystem and has no V0/V1 gap.** Pure Python, zero `hou`; `test_router_internals.py` pins fixes plus a doc-vs-code conformance check. This is the model the rest of the codebase should follow.

4. **Conformance / canonical-pinning test infrastructure.** `tests/_conformance.py:36` `assert_value_in_all_files` (built after three real drift bugs across passes 3/5/6) and the §16 identifier pins fail loud on renames. With bus factor = 1, this *is* the reviewer.

5. **The Inspector is a clean Strangler Fig with a real V0/V1 split.** `mcp_server.py:464-472` routes through `cognitive.dispatcher.Dispatcher` with per-call stdout capture; `test_inspect_mock.py` and `test_inspect_live.py` share one golden across mock and live tiers. This is the template for closing the live-test gap everywhere else.

*(Also genuinely strong but not in the top 5: constant-time auth primitives with `hmac.compare_digest`, `validate_origin()` DNS-rebinding defense, content-aware lossless verification in `shared/evolution.py`, and the writer-priority `ReadWriteLock` in the JSONL store.)*

## 3. Risks, ranked by severity × leverage

| Risk | Severity | Evidence (file:line) | Why it matters at scale |
|---|---|---|---|
| **Default localhost mode requires NO auth — any local process gets in-DCC RCE** | **Critical** | `auth.py:55-85`, `websocket.py:343-349,420`, `sessions.py:305-313` | Out-of-the-box `auth_required=False`; the handshake block is skipped and the message loop dispatches any localhost client. Combined with the next row, any local process → arbitrary Python in Houdini. |
| **`execute_python`/`execute_vex` (mapped CRITICAL in CLAUDE.md) is NOT gated on any live transport** | **Critical** | `handlers.py:916-973,1504`, `websocket.py:623`, `hwebserver_adapter.py:211`, `constants.py:99` | Both live transports call `handle()` directly; `_handle_execute_python` execs caller code with full `__builtins__` (file IO, subprocess), no consent poll, no import filter, no length cap. The CRITICAL gate exists only inside the bridge, which the live path never touches. |
| **The one bridge-wired path explicitly disables its own consent gate** | **High** | `bridge_adapter.py:166-181,193-197`, `mcp/tools.py:120-124` | `_panel_consent` returns `True` unconditionally and `get_bridge()` sets `_bridge._gate = None`. MCP tools share the *same* neutered singleton. So even the "gated" path auto-approves CRITICAL ops. The deadlock rationale is legitimate; the security outcome is that **no live path enforces code-exec consent**. |
| **RBAC entirely absent from the hwebserver transport (the native/primary studio server)** | **High** | `hwebserver_adapter.py:54,135-212` vs `websocket.py:540-553` | hwebserver never imports `check_permission`; auth-at-connect only, no per-command role check. An authenticated VIEWER can call `execute_python`. Fixes must be applied to *both* transports — they've already drifted. |
| **`LosslessExecutionBridge` is absent from the live request path; "only code path / cannot bypass" is false** | **High** | `bridge.py:5-6` (claim) vs `hwebserver_adapter.py:211`, `websocket.py:560,623`, `handlers.py:303-343`; `IntegrityBlock` fields grep in `server/` = 0 files | The live path produces no `IntegrityBlock` and computes no `fidelity`. The headline "lossless/integrity-verified" guarantee is documentation, not running code. The handlers happen to hold undo/thread safety, but the integrity-verification anchor does not exist on the live path. |
| **`os` never imported in hwebserver — `connect()` raises `NameError` before origin validation** | **High** | `hwebserver_adapter.py:22-25,108-109` | `os.environ.get(...)` at :108 throws `NameError` before `validate_origin` at :109 runs. The DNS-rebinding defense is **broken as written** on the production transport. (Correctness bug, trivial fix, high blast radius.) |
| **The S1 double-undo fix is UNCOMMITTED working-tree state; docs mark the bridge "✅ Verified H21"** | **High** | `shared/bridge.py:449-469` + `git show HEAD` still has inner `performUndo()`; `CLAUDE.md:797,10,42` | A fresh clone / `git checkout` reintroduces the double-undo. *Caveat (Floor-honest): only CLAUDE.md over-claims — `SYNAPSE_SCIENCE_HARNESS_v3.md:86,233,271` correctly marks S1 OPEN.* **Commit it or it isn't real.** |
| **S2: scene hash never hashes the composed LOP stage — integrity signal blind on the Solaris path** | **High (latent)** | `bridge.py:283-321` (hash body), `:791` (only `.stage()` call) | For a LOP target, `node.geometry()` is None/caught and the hash collapses to child-count + cookCount. `delta_hash` cannot detect that stage *content* changed — the headline Solaris use case has degraded change detection. |
| **`undo_group_active` & `main_thread_executed` are asserted as literals, never measured** | Medium | `bridge.py:430-431,514-515,406-407,582-583` | 2 of 4 anchors are self-certified `= True` at method top, before the undo group opens. `IntegrityBlock` proves the bridge *believes* it ran safely, not that it did. Erodes the integrity claim's meaning even where the bridge runs. |
| **S4: consent gate blocks the FastMCP event loop for up to 300s** | Medium | `bridge.py:491,770-782` vs async-correct `:663` | `_check_consent` runs synchronously on the event-loop thread; CRITICAL polls a blocking `time.sleep` loop to 300s. The PDG path uses `await asyncio.sleep` correctly — the author knows the pattern but didn't apply it. One gated op stalls the whole MCP server. |
| **`_verify_composition` fails OPEN — returns `True` on any exception** | Low | `bridge.py:831-837`, `:88` (default `True`) | Any pxr/traversal throw → anchor reports `composition_valid=True` having validated nothing → `fidelity=1.0`. The Scene Integrity anchor fails open, not closed. |
| **Bridge best-effort: silently degrades to direct dispatch on ImportError** | Medium | `mcp/tools.py:119-128`, `tool_executor.py:315-326`, `bridge_adapter.py:227-230` | A "structural guarantee" wrapped in `try/except ImportError: handler.handle()` is not structural. Made *more* likely by the `sys.path.insert` hack (`bridge_adapter.py:20-23`, comment records the path math was already wrong once). |
| **MCP `synapse_evolve_memory` is dead-on-arrival** | High (correctness) | `handlers_memory.py:238,250`; `evolution.py:109,214` | Imports `evolve_to_charmeleon` (defined nowhere → `ImportError` on every call) and gates on `target=='charmeleon'` which `check_evolution` never returns. The tool cannot run, and the path it *would* hit is the non-lossless evolver that overwrites live markdown (`evolution.py:337`, `open(...,'w')`) and drops parameters. |
| **Live JSONL evolution is detection-only — logs "should evolve," never evolves** | Medium | `store.py:426-443` | `_check_evolution` only `logger.info(...)`; no `evolve_to_*` call site exists in production. Charmander→Charmeleon never fires in normal operation; the only manual trigger is the broken tool above. The Pokémon model is effectively unexecuted. |
| **Non-atomic `memory.jsonl` rewrite — crash mid-save truncates memory** | High (data-loss) | `store.py:366-393,243`; no `os.replace`/`.tmp` in `memory/` | Plain truncating `open(...,'w')` full rewrite, no temp+rename. *Floor-honest: CLAUDE.md §16.4's "atomic .tmp+replace" claim is scoped to `RecommendationHistory` (where it IS atomic-on-rename), not the primary store — so it's scope-confusion, not a flat lie. The underlying data-loss risk is real.* |
| **Two divergent WebSocket servers; production backend has the weaker resilience set** | Low | `websocket.py:146-173` vs `hwebserver_adapter.py:274-276,289` | Production (hwebserver) has rate-limiter + backpressure only — "no watchdog, no circuit breaker." Every resilience fix must be written twice and has already drifted. |
| **Wire `protocol_version` is write-only dead metadata stated in 3 conflicting values** | Medium | `mcp_server.py:148` (`5.4.0`) vs `core/protocol.py:31` (`4.0.0`); `handlers.py:303-337` never reads it | The two ends of the same WebSocket disagree and nothing validates it. Inert today; a silent compat trap the day the wire format changes. |
| **No global registry→handler parity test; transports not at tool parity** | Medium | `test_mcp_protocol.py:337-356` (registry-internal only); stdio 117 vs HTTP 110 (`mcp_server.py:628-662`, `mcp/tools.py:52-58`) | A registry tool with an unregistered handler passes the parity test and fails only at call time. HTTP clients silently see 7 fewer tools than stdio. |

## 4. Prioritized roadmap

### NOW (this week — each ≤1 day)

- **Fix the `os` `NameError` in `hwebserver_adapter.py`** (add `import os`). One line; it currently *breaks the DNS-rebinding defense on the production transport*. Security-correctness, highest leverage-per-character.
- **Commit the S1 double-undo fix.** It exists only in the working tree; a `git checkout` reintroduces the double-undo. `git add shared/bridge.py && commit`. Then flip `CLAUDE.md:797` off "Verified" until re-verified.
- **Make a default-localhost consent decision and align docs to it.** Either (a) keep no-auth/auto-approve and *change the docs* (`bridge_adapter.py:178`, CLAUDE.md §1.2.1/§11.5) to stop advertising enforced CRITICAL consent, or (b) gate `execute_python`/`execute_vex` at the handler layer. Today the docs promise a gate that **no shipped transport provides** — that doc/code gap is the real exposure. Pick one this week.
- **RSI one-line loop-closures** (both against already-tested code):
  - **Line S:** pass `deposit_fn=<moneta writer>` at `run_apex_verify.py:82` — `registry.py:86-87` already calls it when non-None; `test_science_harness.py:323` proves the path. Falsifiability records reach the queryable substrate.
  - **Line F:** add `to_jsonl`/`from_jsonl` around `router.py:80` `_session_fast_paths`, mirroring `RecommendationHistory` (`test_pass8:147-180`). Learned fast-paths currently die on every restart — the only zero-persistence RSI store.
- **Stop trusting the stale RSI audit doc.** Its two highest-ROI claims (observability dormant, render-memory never set) are *already fixed* in live code (`agent_health.py:269-349`, `handlers_render.py:880-882`). Mark `SYNAPSE_RSI_AUDIT.md` superseded so nobody redoes done work.

### NEXT (this month)

- **Add RBAC to hwebserver** (import + call `check_permission`) and decouple RBAC enablement from deploy mode (`rbac.py:185-186`) so an authenticated single-key WS deployment isn't authorization-free.
- **Fix or remove `synapse_evolve_memory`** — it's dead-on-arrival (`ImportError` + unreachable branch). If kept, point it at the lossless `shared/evolution.py` path, not the markdown-overwriting `memory/evolution.py`.
- **Make `memory.jsonl` writes atomic** (temp + `os.replace`), mirroring the advisor's existing pattern. Highest data-integrity ROI in the memory layer.
- **Make the consent wait async** (`await asyncio.sleep` in `_wait_for_decision`, matching the PDG path) so a gated op can't stall the MCP server for 300s.
- **Close the live-test gap with one bridge integration test** behind the existing `SYNAPSE_INTEGRATION` gate: drive `bridge.execute()` through `_execute_houdini` with a composition-failure that returns `False` and assert single-`performUndo` rollback. Today that path has **zero** coverage; every CI test takes `_execute_direct`.
- **Add a global registry→handler parity test** that iterates every `TOOL_DEFS` cmd_type asserting `_registry.has(cmd)`, and a transport tool-count parity assertion (stdio vs HTTP).

### LATER (this quarter / architectural)

- **Resolve the "two bridges, one name" architecture.** Either make `LosslessExecutionBridge` the actual live path (and measure the anchors instead of asserting `=True`), or formally retire the bridge as integrity/undo-audit-only and rewrite CLAUDE.md §1's "only code path / cannot bypass" framing. Right now the doc's central guarantee is fictional on the live path.
- **Converge the two WebSocket servers** to a single resilience-policy layer so fixes aren't written twice.
- **Hash the composed LOP stage** (S2) so the integrity signal isn't blind on the headline Solaris path; trace `outputs()` as well as `dependents()` in `_infer_stage_touch` (S3) to catch SOP→LOP-Import bleed.
- **Two-tier Moneta (Line C):** immutable falsifiability tier + decaying tier, so never-decay dead-ends can converge onto the unified substrate without the decay model eating them.
- **FORGE (Line E)** is the one RSI item needing real engineering, not wiring: `orchestrator.py:177` `fixes_applied += 1  # Optimistic` with no generate/apply/verify stage and `fixes_validated=0` hardcoded (`:214`). Build the verify stage or stop reporting self-improvement metrics.

## 5. The tech-debt theme

**The through-line is documentation that asserts structural guarantees the running code delivers by accident, partially, or not at all.** The bridge "cannot be bypassed" (it's bypassed on every live transport); consent is "enforced via HumanGate" (the only wired path sets `_gate=None`); memory persistence is "atomic" (the primary store does a truncating rewrite); evolution is "lossless or aborted" (the reachable path overwrites markdown and drops parameters — and is dead-on-arrival anyway); APIs are "verified live, zero hallucinated" (no emit-time mechanism exists, only prose). The *safety substance often still holds* — undo and thread-safety are genuinely enforced inline — but through a **different mechanism than documented**, which means the next engineer (or the solo author six months out) could trust an absent layer and a single refactor would silently remove a guarantee everyone believes is structural. The debt isn't bad code; it's a **growing delta between the blueprint and the building**, concentrated exactly on the load-bearing safety claims.

## 6. Organizational / process

This is a **bus-factor-1 project** (100% single-author across 200 commits; the casing variant is the same person) where the **conformance/canonical-pin tests are a deliberate, intelligent substitute for a human reviewer** — a genuine mitigation, not a gap to paper over. But the test surface has a structural blind spot: **every CI-collected test is V0** — `ci.yml:49` runs on ubuntu-latest with no Houdini, and the only host-touching tests self-skip, so the safety-critical Houdini boundary (undo-wrap, composition-rollback, blast-radius, viewport-sync) is verified entirely against author-assumed mocks where *the mock is the spec*; the Inspector's mock-to-live golden is the lone exception and covers only itself. **Doc:code volume is an asset that has started to rot**: line-counts are stale 18-44%, the version banner is two minors behind (`v5.8.0` vs `5.10.0`), tool counts disagree across six values (43/104/108/110/111/117), and the STATUS table even *understates* completion (Phases 4/5/6 shipped but still marked 🔶). Most tellingly, **velocity is skewed to the UI**: the Houdini panel was redesigned end-to-end *twice* (PR #21 and PR #27), 31 of the last 200 commits carry panel/ui scope, while the three substrate phases sit unbuilt — which matches the project's own stated "framework edits = avoidance" pattern, now expressed at the panel layer. The fix is cheap and already half-built: add one live/hython CI tier behind the existing `SYNAPSE_INTEGRATION` gate, add lint/type-check (no `ruff`/`mypy` runs today, so `hou`-API typos surface only at Houdini runtime), and treat the doc-conformance harness — the project's best idea — as the thing to *extend to magnitudes and values*, not just identifiers.

---

# Part II — Full verified findings by dimension

Every finding below was adversarially verified. `kind` ∈ {bug, risk, gap, tech-debt, strength-caveat}. Sorted by severity within each dimension.

## architecture

**Confirmed strengths:**

- Live request path is genuinely clean and dict-dispatched, not if/elif: handlers.py:303 handle() does self._registry.get(cmd_type) with a normalize_command_type() fallback at :316-320, then calls handler(command.payload). Confirmed maintainable.
- Circuit-breaker error taxonomy is real and well-designed: handlers.py:345-368 separates SynapseUserError/ValueError (returned, no CB trip) from SynapseServiceError; websocket.py:633 records success only, and :645-654 trips CB only on is_service_error(e) or main-thread timeout. A bad-input LLM cannot open the breaker. Confirmed.
- Undo safety IS enforced inline on the live path despite the bridge being absent: 37 hou.undos.group occurrences across 8 server files (handlers_cops 17, handlers_usd 10, handlers_material 3, handlers_hda 2, handlers.py 2 incl. execute at :965, handlers_render/solaris_graph/render_sequence 1 each). The safety guarantee substantively holds via a different mechanism than documented. Confirmed.
- Thread safety on the live path is real: mutating handlers wrap hou.* in an _on_main closure dispatched via run_on_main(), e.g. handlers_node.py:51-117 _handle_create_node. The async/main-thread boundary is respected by the handlers themselves. Confirmed (run_on_main from main_thread.py).
- hwebserver_adapter.py is a deliberate, well-reasoned production choice: docstring lines 4-6 cite eliminating the Python websockets daemon thread, haio.py conflicts, and watchdog false positives; the dual-backend split (websocket.py for CI/standalone with full resilience, hwebserver for production) is defensible. Confirmed.
- MCP transport hardening is real: origin validation for DNS-rebinding protection (hwebserver_adapter.py:109 validate_origin, mcp/server.py:687), opt-in bearer-token auth gated on key presence (mcp/server.py:664-680), and main-thread-stall fast-fail to avoid 30s blocking (websocket.py:603-619). Confirmed.
- The Inspector tool is a clean Strangler Fig: mcp_server.py:464-472 routes synapse_inspect_stage through synapse.cognitive.dispatcher.Dispatcher while preserving the prior error-envelope contract, with per-call stdout capture (_inspector_wrap_stdout_capture at :501) rather than a shared module buffer. Confirmed.

**Findings:**

### [HIGH · risk] LosslessExecutionBridge is absent from the live request path; the 'only code path / cannot bypass' claim is false for the production server
- **Verdict:** CONFIRMED
- **Evidence:** bridge.py:5-6 docstring asserts 'Every agent operation passes through this bridge... Agents cannot bypass this layer.' Live path: hwebserver_adapter.py:211 and websocket.py:535/560/623 all call self._handler.handle(command) directly. handlers.py:303-343 handle() does a registry lookup and calls handler(command.payload) with no bridge involvement. Grep for IntegrityBlock fields (undo_group_active/main_thread_executed/consent_verified/composition_valid/fidelity) across python/synapse/server/ returns ZERO files. The live path produces no IntegrityBlock and computes no fidelity. Confirmed.
- **Verifier opened:** shared/bridge.py:5-6; hwebserver_adapter.py:211; websocket.py:560,623; handlers.py:303-343; grep IntegrityBlock fields in server/ = no files

> **Addendum 2026-07-10 (v5.22.0):** partially overtaken — the live path now records path-qualified, observe-only IntegrityBlocks (`python/synapse/server/integrity_envelope.py`: `execution_path="live"`, per-anchor applicability flags never faked, shared process trail via `record_external_block()`). The finding's core (live ops don't route through the bridge's consent/undo anchors) remains true and is now documented honestly in CLAUDE.md §1/§11.

### [HIGH · risk] execute_python/execute_vex run on the live path with no per-operation consent gate despite CLAUDE.md mapping them to CRITICAL
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md maps execute_python/execute_vex to CRITICAL (300s approval wait). Live path: handlers.py:916 _handle_execute_python is invoked by handle() -> registry, wrapped only in 'with hou.undos.group("synapse_execute")' (:965) plus a _ROLLBACK_ERRORS coding-bug rollback heuristic. No HumanGate / APPROVE / CRITICAL poll exists anywhere in this path. Arbitrary Python/VEX over the MCP WebSocket is gated only by optional connection-time bearer auth, not per-op consent. Confirmed.
- **Verifier opened:** handlers.py:916-973 (undos.group at :965, _ROLLBACK_ERRORS rollback); no HumanGate in handle() path

### [HIGH · gap] Bridge is wired only into a second MCP transport (/mcp HTTP via mcp/tools.py), not the live /synapse WebSocket the documented stdio bridge uses
- **Verdict:** PARTIAL
- **Evidence:** Core claim holds: root mcp_server.py is the Claude Desktop stdio bridge (docstring :19-20 'Claude Desktop <-stdio-> mcp_server.py <-WebSocket-> Synapse'); its send_command (:316) forwards over WebSocket to the bridge-less /synapse handler.handle(). The OTHER server, mcp/server.py, routes dispatch_tool -> mcp/tools.py:124 execute_through_bridge (with the bridge). start_hwebserver.py imports ONLY hwebserver_adapter (/synapse), never synapse.mcp; no file in python/synapse/server/ imports synapse.mcp.server. BUT the 'import side-effect the documented startup never triggers' sub-claim is OVERSTATED: synapse/mcp/__init__.py:18-19 imports .server (registering @hwebserver.urlHandler('/mcp')) whenever the synapse.mcp package loads, and mcp_server.py:446 imports synapse.mcp._tool_registry, which runs that __init__. So /mcp registration is not as dormant as stated when mcp_server.py runs in-process. Net: bridge-wrapped path is real but disjoint from the live /synapse client path; liveness caveat partly refuted.
- **Verifier opened:** mcp_server.py:19-20,316,446; mcp/server.py:659; mcp/tools.py:124; synapse/mcp/__init__.py:18-19; start_hwebserver.py:31; grep synapse.mcp in server/ = no matches

### [MEDIUM · tech-debt] Two unrelated objects both named 'bridge': handler-path get_bridge() is the session/memory tracker (SynapseBridge), not the safety bridge
- **Verdict:** CONFIRMED
- **Evidence:** handlers.py:296-301 _get_bridge() does 'from ..session.tracker import get_bridge'. session/tracker.py:591 'def get_bridge() -> SynapseBridge' (aka NexusBridge, the memory/session logger). handlers_node.py:109 bridge=self._get_bridge() is used only at :111-113 to append to session.nodes_created. The real LosslessExecutionBridge is in panel/bridge_adapter.py:184 get_bridge(). hwebserver_adapter.py:57 imports the tracker get_bridge. Same name, opposite guarantees. Confirmed.
- **Verifier opened:** handlers.py:296-301; session/tracker.py:591; handlers_node.py:109-113; panel/bridge_adapter.py:184; hwebserver_adapter.py:57

### [MEDIUM · risk] Where the bridge IS called it is best-effort and silently degrades to direct dispatch on ImportError
- **Verdict:** CONFIRMED
- **Evidence:** mcp/tools.py:119-128 wraps 'from synapse.panel.bridge_adapter import execute_through_bridge' in try/except ImportError: response = handler.handle(command). tool_executor.py:315-326 has the identical pattern. bridge_adapter.py:26-43 sets _BRIDGE_AVAILABLE=False on ImportError, and execute_through_bridge :227-230 returns handler.handle(command) directly when bridge is None. A structural guarantee that vanishes on import failure is not structural. Confirmed.
- **Verifier opened:** mcp/tools.py:119-128; panel/tool_executor.py:315-326; panel/bridge_adapter.py:26-43,227-230

### [MEDIUM · tech-debt] shared/ <-> python/synapse/ coupling relies on a runtime sys.path.insert hack with a comment recording a prior path bug
- **Verdict:** CONFIRMED
- **Evidence:** bridge_adapter.py:20-23 computes _REPO_ROOT via os.path.join(_THIS_DIR,'..','..','..') + sys.path.insert(0, _REPO_ROOT) so panel code can 'from shared.bridge import ...'. Inline comment at :21 reads 'panel->synapse->python->repo root (was 4x .. = one level too high)' — documents the path math was wrong once. mcp_server.py:444-445 does a parallel sys.path.insert for 'python'. shared/ is bolted on at runtime, making import success cwd/environment-sensitive — exactly what makes the ImportError fallback fire. Confirmed.
- **Verifier opened:** panel/bridge_adapter.py:20-23 (comment at :21); mcp_server.py:444-445

### [MEDIUM · gap] The one live bridge user (panel) disables its own consent gate; APPROVE/CRITICAL gating is auto-approved
- **Verdict:** CONFIRMED
- **Evidence:** bridge_adapter.py:193-197 get_bridge() constructs LosslessExecutionBridge(consent_callback=_panel_consent) then sets _bridge._gate = None. _panel_consent (:166-181) unconditionally 'return True'. The docstring justifies it (artist-initiated pre-consent; HumanGate's blocking poll deadlocks the GUI thread — a documented real bug). Net effect confirmed: CLAUDE.md gate levels (REVIEW/APPROVE/CRITICAL, execute_python=CRITICAL) do NOT gate panel-initiated ops; they auto-approve. The consent anchor is off for the only live bridge path. Confirmed.
- **Verifier opened:** panel/bridge_adapter.py:166-181 (_panel_consent return True), :193-197 (_gate=None)

### [MEDIUM · risk] In-tree handler docstrings misdescribe the wiring, contradicting other in-tree docs on a load-bearing safety claim
- **Verdict:** CONFIRMED
- **Evidence:** solaris_compose.py:9-13 docstring claims mutations are 'dispatched through panel.bridge_adapter.execute_through_bridge -> LosslessExecutionBridge, which supplies the undo group, integrity anchors and consent gate' and 'does NOT wrap undo itself'. handlers_solaris_compose.py:8-9 repeats 'Dispatched through the bridge'. README.md:554 also claims 'bridge_adapter.py routes every mutation through LosslessExecutionBridge'. But these handlers run on the bridge-less /synapse path. docs/MONETA_SYNAPSE_SHIP_REPORT.md:110-111 candidly admits a related primitive is 'Not load-bearing yet (no prod caller invokes...)'. The docs contradict each other; a future change could trust an absent bridge (note: solaris compose handlers risk being undo-UNWRAPPED if they truly skip self-wrapping per their docstring). Confirmed.
- **Verifier opened:** solaris_compose.py:9-13; handlers_solaris_compose.py:8-9; README.md:554; docs/MONETA_SYNAPSE_SHIP_REPORT.md:108-111

### [LOW · tech-debt] Two divergent WebSocket server implementations duplicate auth/session/dispatch with resilience drift; production backend has the weaker set
- **Verdict:** CONFIRMED
- **Evidence:** websocket.py SynapseServer (:146-173) wires rate_limiter + circuit_breaker + watchdog + backpressure + health_monitor. hwebserver_adapter.py SynapseWS has rate_limiter + backpressure only (start_hwebserver :274-276; docstring :289 'no watchdog, no circuit breaker'). Both re-implement heartbeat fast-path (websocket.py:516 vs hwebserver_adapter.py:172), ping/health bypass, and lazy session creation independently. Production backend (hwebserver) carries the weaker resilience set; fixes must be applied twice. Confirmed.
- **Verifier opened:** websocket.py:146-173,516; hwebserver_adapter.py:172,274-276,289


## substrate-correctness

**Confirmed strengths:**

- S1 double-undo IS genuinely fixed in the working tree: at both sites (shared/bridge.py:449-459 _execute_houdini, :531-537 _sync_payload) the inner hou.undos.performUndo() is deleted, the code raises RuntimeError, and only the single outer except (463-469 / 541-547) calls performUndo once. git diff confirms the 2 deletions. CONFIRMED.
- The async->sync boundary (R2) is real: execute_async wraps hdefereval.executeInMainThreadWithResult in asyncio.wait_for(..., timeout=120.0) at bridge.py:551-567, so a stalled main thread surfaces as execution_timeout. CONFIRMED.
- The R8 PDG bridge is high-quality: threading.Event (bridge.py:608, with explicit comment that asyncio.Event is not thread-safe), await asyncio.sleep(0.25) poll (662-663), executeGraph wrapped so cook errors propagate (650-657), and removeEventHandler in a finally block (669-674). CONFIRMED.
- _verify_composition (bridge.py:784-837) does real USD work when pxr+hou present: traverses the stage (801), checks prim validity/activity (802-806), detects self-referencing cycles (814-819), resolves layers via Sdf.Layer.Find/FindOrOpen (822-824). CONFIRMED.
- Consent gating is structurally sound: gate_level (bridge.py:160-169) enforces R4 disk-write override to APPROVE and never downgrades CRITICAL; _wait_for_decision defaults timeout to rejection (781-782, safe default); constants.py:99-100 assign execute_python/execute_vex => critical. CONFIRMED.

**Findings:**

### [HIGH · gap] S2: _compute_scene_hash never hashes the composed LOP stage — integrity signal blind on Solaris path
- **Verdict:** CONFIRMED
- **Evidence:** _compute_scene_hash (bridge.py:283-321) uses only node.children()/sessionId()/cookCount() (290-294), node.cookCount() (300), and node.geometry() intrinsics (305-310). grep confirms the ONLY .stage() call in the file is line 791 inside _verify_composition — never in the hash. For a LOP hash_target (set via operation.stage_path at 396/503), node.geometry() returns None or raises and is caught (311), so the hash collapses to children-count + cookCount. delta_hash for a stage/render recipe cannot detect that stage CONTENT changed. The headline Solaris path has a degraded change-detection signal. Line numbers cited (283-321, 791, 396/503, 311) all verified accurate.
- **Verifier opened:** shared/bridge.py:283-321 (hash body), :791 (only .stage()), :396/:503 (hash_target)

### [HIGH · risk] The S1 'fix' is UNCOMMITTED working-tree state, not banked — and docs describe it as live-verified done
- **Verdict:** PARTIAL
- **Evidence:** CORE CLAIM CONFIRMED: git blame -L 449,470 shows the S1 comment block (451-456) as 'Not Committed Yet 2026-06-05'. git diff shared/bridge.py = 10 insertions / 2 deletions, all unstaged (git status: ' M', not staged). git show HEAD:shared/bridge.py lines 451 STILL contains the inner `hou.undos.performUndo()` double-undo. A git checkout / fresh clone reintroduces it. CLAUDE.md:797 marks the bridge '✅ Verified H21' and CLAUDE.md:10/42 present rollback as a live guarantee. OVERSTATED on one point: the finding says SYNAPSE_SCIENCE_HARNESS_v3.md 'treat[s] the rollback as fixed/verified' — it does the OPPOSITE. v3 lines 86, 233, 271-272 explicitly mark S1 as OPEN (holds=false), 'a Phase-0c target, not a current guarantee.' So only CLAUDE.md (not the harness doc) over-claims.
- **Verifier opened:** shared/bridge.py:449-469 + git blame/diff/show HEAD; CLAUDE.md:797,10,42; SYNAPSE_SCIENCE_HARNESS_v3.md:86,233,271

### [HIGH · gap] S3: _infer_stage_touch traces only dependents(), never outputs() — SOP->LOP-via-SOP-Import is a false negative
- **Verdict:** PARTIAL
- **Evidence:** CORE CLAIM CONFIRMED: the recursive _trace at bridge.py:355 iterates `n.dependents()` exclusively; outputs() is never called anywhere in _infer_stage_touch (343-368). dependents() returns parameter/expression references, not wired data outputs, so a SOP chain feeding a SOP Import LOP (connected via outputs()+path parm) is missed. MISLOCATED test attribution: the finding blames conftest.py:112-114 (where MockNode.dependents() returns self._outputs, same as outputs()). That conflation is REAL in conftest, BUT tests/test_blast_radius.py does NOT use the conftest MockNode — it builds standalone MagicMocks (lines 106-127) with dependents.return_value set explicitly and never tests outputs(). So the green test is V0-equivalent (mock implements the assumed semantics) — the finding's conclusion holds — but via test_blast_radius.py's own mocks, not conftest:112-114.
- **Verifier opened:** shared/bridge.py:355 (dependents only); tests/conftest.py:109-113; tests/test_blast_radius.py:106-127

### [MEDIUM · risk] undo_group_active and main_thread_executed are ASSERTED as literals, never MEASURED
- **Verdict:** CONFIRMED
- **Evidence:** bridge.py:430-431 (_execute_houdini) and :514-515 (_sync_payload) and :406-407 (_execute_direct) and :582-583 (_execute_pdg_deferred) all hardcode integrity.main_thread_executed=True and integrity.undo_group_active=True at the TOP of the method, before the undo group opens (436/519) and with no main-thread guarantee check. fidelity (107-114) reads these booleans via anchors_hold (98-105) as if observed. No code path flips them False from a real check (only consent_verified and composition_valid are derived from actual checks). So 2 of 4 anchors are self-certified: the IntegrityBlock proves the bridge BELIEVES it ran undo-wrapped on the main thread, not that it DID.
- **Verifier opened:** shared/bridge.py:430-431, :514-515, :406-407, :582-583 (literal assigns); :98-114 (anchors_hold/fidelity read-back)

### [MEDIUM · bug] S4: consent gate blocks the FastMCP event loop for the full APPROVE/CRITICAL timeout (up to 300s)
- **Verdict:** CONFIRMED
- **Evidence:** execute_async calls self._check_consent(operation) synchronously on the event-loop thread at bridge.py:491 (before any executor dispatch). For CRITICAL this reaches _check_consent_gate (743) -> _wait_for_decision (766) which does a blocking `_time.sleep(GATE_POLL_INTERVAL)` loop (780) up to GATE_TIMEOUT_CRITICAL=300.0 (constants.py:72). Only _sync_payload is sent to run_in_executor (553-556); the consent wait is NOT. The PDG path correctly uses `await asyncio.sleep(0.25)` (663), proving the author knows the async-correct pattern but did not apply it to the gate. A gated op stalls the entire MCP server for up to 300s. All cited lines verified.
- **Verifier opened:** shared/bridge.py:491 (sync _check_consent in async path), :770-782 (blocking time.sleep), :663 (async sleep in PDG); constants.py:72

### [MEDIUM · gap] No test exercises the actual composition-failure rollback path — rollback anchor untested end-to-end
- **Verdict:** CONFIRMED
- **Evidence:** tests/test_composition_validation.py: EVERY test asserts `is True` (lines 32,38-40,62-63,78,84,91,113,124,137,150,169) — only graceful-return-True branches. No test sets _verify_composition to return False AND drives execute/execute_async with touches_stage=True to exercise the raise->single-performUndo path. grep across tests/ for a _verify_composition False-return driving the execute path found none. tests/test_undo_redo.py tests the MCP undo/redo HANDLER (docstring line 2-4, _make_hou_stub), not the bridge rollback. The 'transaction-wrapped rollback' Tier-1 invariant has zero executing coverage of its failure branch.
- **Verifier opened:** tests/test_composition_validation.py:27-169 (all assert True); tests/test_undo_redo.py:1-40 (handler, not bridge)

### [MEDIUM · risk] Empty-group edge: outer except performUndo() can pop the artist's PRIOR action when fn raises before mutating
- **Verdict:** PARTIAL
- **Evidence:** STRUCTURE CONFIRMED: bridge.py:463-467 (and :541-545) call hou.undos.performUndo() unconditionally inside `except Exception`, wrapped in its own try/except-pass. If operation.fn raises before recording any undoable change, the `with hou.undos.group()` (436/519) closes and performUndo() fires with no guard (no scene_hash_before==after comparison, no undo-depth check). The behavioral claim — that H21 pops the most-recent PRIOR action on an empty group — is UNVERIFIED (the finding itself flags 'could not live-probe H21 empty-group push semantics'). It is a genuine structural risk but rests on unconfirmed H21 undo-stack behavior, so it stays a hypothesis, not asserted behavior. Rated 'partial' for that reason.
- **Verifier opened:** shared/bridge.py:463-467 and :541-545 (unconditional performUndo); :436/:519 (group open)

### [LOW · risk] _verify_composition returns True on ANY exception — composition-anchor fails OPEN
- **Verdict:** CONFIRMED
- **Evidence:** bridge.py:831-837: broad `except Exception` logs a warning (832-836) and `return True  # Defensive — validation is best-effort` (837). Any pxr/stage-traversal throw (API drift, malformed layer, permission) makes the Scene Integrity anchor report composition_valid even though it validated nothing. Combined with the IntegrityBlock default composition_valid=True (line 88), a stage that was never validated still yields anchors_hold=True and fidelity=1.0. The anchor fails OPEN, not closed. All cited lines verified.
- **Verifier opened:** shared/bridge.py:831-837 (except->return True), :88 (composition_valid default True)


## test-strategy

**Confirmed strengths:**

- The MOE router is genuinely the strongest-tested subsystem and has no V0/V1 gap (shared/router.py is pure Python, zero hou; test_router_internals.py:1-40 pins R11-R17 fixes + a doc-vs-code conformance check). CONFIRMED.
- The Inspector is the one place implementing a real V0/V1 split: test_inspect_mock.py asserts the parser against the recorded golden (len==8 at :55, node_type=='reference::2.0' at :82) while test_inspect_live.py replays the same extraction against a live host, skipping cleanly when no transport is configured (:259). Mock and live tiers share one golden. CONFIRMED.
- tests/_conformance.py:36 provides assert_value_in_all_files, used by test_router_internals.py:13 to pin canonical names ('charmander') across constants.py/scene_memory.py/CLAUDE.md with a single failure message naming every out-of-sync file; the module docstring (:4) attributes three drift bugs caught across passes 3/5/6. CONFIRMED.
- The PySide-stub-leakage trap is actively defended: test_panel_faces.py:62 verifies QtWidgets.QApplication is a genuine PySide type (isinstance type AND 'PySide' in __module__) before trusting _HAVE_QT, so a leaked MagicMock/ModuleType stub cannot flip the suite green-in-CI/broken-alone. CONFIRMED.
- Consent-gate routing has dense behavior-level coverage in test_consent_timeout.py: INFORM auto-approves without calling the callback (:179-190, asserts len(called)==0), rejection yields error_type=='consent_required' (:238), and R4 disk-write-elevation / CRITICAL-cannot-downgrade are pinned (:88-106). Pure Python so trustworthy. CONFIRMED.
- test_cognitive_boundary.py:41 greps the synapse.cognitive.* tree for 'import hou'/'from hou' (regex at :35) and fails the test if any file matches, enforcing the host-agnostic boundary on every CI run rather than relying on reviewer vigilance. CONFIRMED.

**Findings:**

### [HIGH · gap] No live/hython tier in default CI - every CI-collected test is V0 (asserts against author-assumed mock semantics, not the real H21 API)
- **Verdict:** CONFIRMED
- **Evidence:** ci.yml:49 runs the suite on ubuntu-latest with no Houdini; the only host-touching tests self-skip. The Inspector golden is the sole mock-to-real-scene tie and covers only the Inspector. The bridge/handlers/blast-radius have no equivalent. CONFIRMED. One mislocation: the finding cites test_solaris_compose_tools.py as an 'allow_module_level skip' but it actually uses importorskip('pxr') mid-function at :120, not a module-level skip - immaterial to the core claim.
- **Verifier opened:** .github/workflows/ci.yml:49 (python -m pytest tests/ on ubuntu-latest); test_e2e_tops.py:25-29 (module skip unless SYNAPSE_INTEGRATION); test_inspect_live.py:259 (runtime transport-absence skip); test_live_capture.py:48 (importorskip 'hou')

### [HIGH · gap] The bridge's production undo-wrap + composition-validation + rollback path (_execute_houdini) is NEVER exercised by any test
- **Verdict:** CONFIRMED
- **Evidence:** In CI, bridge.execute() always takes _execute_direct (:403-425) which has no undo group, no _verify_composition, no performUndo. The handler-layer undo tests (test_introspection.py:546-571 'synapse_execute', test_mcp_roundtrip.py:509) are a different code path, not the bridge's. The safety-critical undo-wrapped, rollback-on-composition-failure path has zero automated coverage. CONFIRMED.
- **Verifier opened:** shared/bridge.py:398-401 (branch: _HOU_AVAILABLE -> _execute_houdini else _execute_direct), :427-469 (_execute_houdini with hou.undos.group at :436, _verify_composition at :450, performUndo at :465); grep across tests/ for _execute_houdini = 0 hits; only test_blast_radius.py + test_composition_validation.py patch shared.bridge._HOU_AVAILABLE=True and they call _infer_stage_touch/_verify_composition directly, never bridge.execute()

### [HIGH · gap] test_composition_validation.py cannot catch a composition-validation regression - every assertion is `is True` and there is no failure-path test
- **Verdict:** CONFIRMED
- **Evidence:** There is no test where a prim fails IsValid()/IsActive() so _verify_composition returns False and the bridge raises 'USD Composition violation' + rolls back (bridge.py:450,457). The Scene Integrity anchor's failure path - the reason the anchor exists - is unverified. CONFIRMED.
- **Verifier opened:** tests/test_composition_validation.py:27-169 (all 14 tests assert ... is True); standalone branches guarded by `if not _HOU_AVAILABLE:` at :31,37,76,83; patched-hou tests :101-169 only construct valid/empty/missing-stage mocks (e.g. :157-159 IsValid/IsActive return True)

### [HIGH · gap] execute_python (the CRITICAL-gated arbitrary-code path) has no execution-path test - only its gate LEVEL is asserted
- **Verdict:** PARTIAL
- **Evidence:** The claim 'No CI-collected test drives an actual execute_python through the handler to confirm code runs, errors surface, or output is captured against a real interpreter' is REFUTED in its strong form: test_host_layer.py and test_introspection.py both execute real code through handler-layer adapters and verify output/error capture in CI. What remains true: the BRIDGE's CRITICAL-gate + execution end-to-end is only verified at the gate-routing layer (test_consent_timeout asserts level only); the over-WebSocket e2e (test_e2e_tops.py:103) is integration-gated. PARTIAL - real but overstated; handler-level execution IS covered.
- **Verifier opened:** test_consent_timeout.py:73,100,146,224 (gate-level + callback-invocation only); test_e2e_tops.py:95-103 (live WS, skips unless SYNAPSE_INTEGRATION); BUT test_host_layer.py:343-374 (transport.execute_python runs real CPython exec, asserts stdout capture :353, empty :363, ValueError propagation :374) and test_introspection.py:518-571 (_handle_execute_python runs real code, asserts result['executed'] is True)

### [MEDIUM · risk] 38 test files inject a `hou` stub into sys.modules with divergent semantics; first-loader-wins guards make per-test behavior order-dependent
- **Verdict:** CONFIRMED
- **Evidence:** 38-file count is exact. First-loader-wins guards confirmed (test_live_metrics.py:49, test_main_thread.py:23). Stubs are non-equivalent (MagicMock auto-creates any attribute, so a typo'd API call never fails, vs ModuleType with hand-set attrs vs conftest._MockNode). No autouse fixture restores sys.modules['hou'] between modules. Latent false-green/flakiness surface. CONFIRMED.
- **Verifier opened:** grep `sys.modules['hou'] =` = exactly 38 files; test_live_metrics.py:43-50 (root=MagicMock auto-creating attrs, guarded by `if 'hou' not in sys.modules`); test_main_thread.py:23-26 (ModuleType stub, same guard); conftest.py:241 (the only autouse fixture is _inspector_cleanup_transport, resets Inspector transport, NOT sys.modules['hou'])

### [MEDIUM · risk] Blast-radius (R7) and viewport-sync (R10) tests pin assumed H21 API shapes against MagicMock - the mock IS the spec
- **Verdict:** CONFIRMED
- **Evidence:** Both tests construct the mock whose isinstance/dependents()/class behavior the author defines, then assert the code matches the mock - if H21's node.dependents() or isinstance(dep, hou.LopNode) resolves differently in the real host, the green tests still pass while production fails. No golden/live counterpart for either, unlike the Inspector. V0 tests masquerading as API-contract verification. CONFIRMED.
- **Verifier opened:** test_blast_radius.py:104-127 (author defines LopNode=type(...), lop_node.__class__=LopNode at :113, dependents.return_value=[lop_node] at :115, then asserts _infer_stage_touch behaves accordingly); test_viewport_sync.py:65-84 (mock_hou.LopNetwork=type('LopNetwork',...) same pattern for _sync_solaris_viewport)

### [MEDIUM · strength-caveat] High green-count (~2996 test functions / 125 files) overstates real coverage of the safety-critical Houdini boundary
- **Verdict:** CONFIRMED
- **Evidence:** test_main_thread.py:36 simulates hdefereval main-thread dispatch with a daemon threading.Thread - the opposite of the real single-threaded Qt-pumped semantics. With the undo-wrap (F2), composition-rollback (F3), and blast-radius (F6) all behind author-assumed mocks, the high test count buys confidence in pure-Python logic (router, gates, memory) but little in the Houdini-facing anchors the 'lossless' claim rests on. CONFIRMED.
- **Verifier opened:** test_main_thread.py:34-37 (_mock_executeDeferred runs fn on a raw threading.Thread, NOT H21's single-threaded Qt-pumped main-thread queue); combined with confirmed Findings 2/3/6 (undo/composition/blast-radius all mock-backed)

### [LOW · tech-debt] manual_e2e_forge.py and manual_render_test.py are not collected by pytest and never run in CI
- **Verdict:** CONFIRMED
- **Evidence:** Both files lack the test_ prefix so pytest's python_files glob excludes them; they run only if a human invokes them by hand. Invisible to the CI gate from a regression-protection standpoint. CONFIRMED.
- **Verifier opened:** pyproject.toml:83 (python_files = ['test_*.py']); glob tests/manual_*.py returns tests/manual_render_test.py + tests/manual_e2e_forge.py (no test_ prefix)

### [LOW · tech-debt] The `live` pytest marker is declared but gates nothing - addopts has no `-m "not live"`
- **Verdict:** PARTIAL
- **Evidence:** The marker is decorative - addopts has no -m filter, so live tests skip only because the host/transport is absent, not because of the marker. CONFIRMED. Nuance the finding missed: the actual e2e module uses the 'integration' marker, not 'live', and 'integration' is not even declared in pyproject.toml markers (only 'live' is). So the finding is right that markers don't gate, but slightly mislabels which marker the e2e suite uses. PARTIAL.
- **Verifier opened:** pyproject.toml:84 (addopts = '-v --tb=short', no -m); :85-87 (only the 'live' marker declared); test_e2e_tops.py:31 uses pytestmark = pytest.mark.integration (NOT 'live') and self-skips at :25-29; test_inspect_live.py:259 skips at runtime via transport absence


## rsi-closure

**Confirmed strengths:**

- CONFIRMED: Two of six RSI loops (Line R render-farm, Line O observability) are genuinely closed at L2 in live code. Verified handlers_render.py:880-882 sets self._render_farm._memory = get_synapse_memory(); agent_health.py:279/326/328/334 wires from_jsonl/record/to_jsonl/analyze_history driven by synapse_panel.py:541 (_update_health -> poll_agent_health). tests/rsi/eval_line_r_closure.py exists on disk (6433 bytes). CAVEAT: the strength cites _handle_autonomous_render at handlers.py:1387 but the actual get_synapse_memory() resolution is at handlers.py:1441-1442 (the :1387/:1397 line numbers in both the strength and the original audit are stale); the pattern is real, the line is mislocated.
- CONFIRMED: Disciplined falsifiable governance layer. RSI_CHAMPION.md:12-28 defines the per-loop state machine (dormant -> claim-OK -> wired -> L1 -> L2 CLOSED -> L3 -> L4) with the RESTART-AWARE PROMOTION rule (L2 replicated on a second fresh process before it counts) and the monotonic 'no notch given back' ratchet with a dated promotion log (:64-85). This is rigorous self-accounting.
- CONFIRMED: Pure-logic layers are clean and test-pinned so closure is wiring not rewrite. conductor_advisor.py KIND_ROUTER_PROMOTE rec (:296-324) is read-only/advisory; science registry.py:66-89 dedups by (surface,kind), returns False on dup (no overwrite, no deposit, :73-74), with a clean deposit_fn injection seam (:26, :86-87); router auto-promotion is live inside route() (:147-157) and CONSTANTS_HASH-stamped (:156).
- CONFIRMED: Dormant lower halves are real, already-tested code. test_pass8_history_and_meta.py exercises from_jsonl/to_jsonl/analyze_history (:147,:152,:159,:172,:180,:209); test_area4_observability.py has 10 test functions (grep -c = 10); science deposit_fn path covered at test_science_harness.py:323 and :666. The remaining closures are genuinely small wiring changes against covered code.

**Findings:**

### [HIGH · gap] FORGE (Line E) self-improvement half is still prose: fixes_applied is optimistic and fixes_validated is hardcoded zero
- **Verdict:** CONFIRMED
- **Evidence:** orchestrator.py:177 'fixes_applied += 1  # Optimistic — verification step catches failures' with the comment at :174-175 stating Claude Code would generate the fix 'For now, we track the intent' — no fix generated/applied/written. orchestrator.py:214 passes fixes_validated=0 hardcoded; grep confirms :214 is the ONLY place the orchestrator sets it and there is NO verify/re-run/apply/generate-fix stage anywhere in orchestrator.py. No __main__/argparse/main entrypoint exists. The live artifact forge/metrics/cycles.json shows fixes_validated:0 across all three recorded cycles — the gap manifests in real run data. Fully open; the audit's one large gap.
- **Verifier opened:** forge/engine/orchestrator.py:172-177,214; forge/metrics/cycles.json:27,133,211 (all fixes_validated:0); grep: no verify/apply/main in orchestrator.py

### [MEDIUM · gap] The RSI audit doc is materially stale: its two highest-ROI claims (#2 observability dormant, #3 render-memory never set) are already FIXED in live code
- **Verdict:** CONFIRMED
- **Evidence:** Audit dated 2026-05-31 (SYNAPSE_RSI_AUDIT.md:3). Line 14 asserts §16 history has 'zero non-test callers'; line 38 asserts render learning is gated behind a never-set self._memory. Both now false: agent_health.py:269-349 wires a persistent RecommendationHistory (from_jsonl:279, record:326, to_jsonl:328, analyze_history:334) driven by synapse_panel.py:541; handlers_render.py:880-882 sets self._render_farm._memory = get_synapse_memory(). RSI_CHAMPION.md:64-85 logs both closures dated 2026-06-01 (one day after audit). A reader trusting the audit verbatim would redo completed work. Minor: the citation path was 'agent_health.py' but the real path is python/synapse/panel/agent_health.py; line ranges hold.
- **Verifier opened:** docs/SYNAPSE_RSI_AUDIT.md:3,14,38; python/synapse/panel/agent_health.py:269-349; python/synapse/server/handlers_render.py:875-884; python/synapse/panel/synapse_panel.py:533-544; docs/rsi/RSI_CHAMPION.md:64-85

### [MEDIUM · tech-debt] Router learned fast-paths (Line F) are the only zero-persistence RSI store — knowledge dies with the process
- **Verdict:** CONFIRMED
- **Evidence:** router.py:80 declares _session_fast_paths as an in-memory dict; populated live in route() at :155 and via learn_fast_path at :205. grep for to_jsonl/from_jsonl/persist/jsonl in router.py returns NOTHING (exit 1). Auto-promotion is live (router.py:147-157) but every restart cold-starts. conductor_advisor.py:296-324 KIND_ROUTER_PROMOTE only ASKS a human (rationale :315-319 'consider promoting to a canonical entry', severity SEVERITY_INFO) to hand-edit constants.FAST_PATHS — no automatic durability. Every cited line confirmed exact.
- **Verifier opened:** shared/router.py:80,147-157,201-207; grep to_jsonl|from_jsonl|persist|jsonl router.py = no match; shared/conductor_advisor.py:296-324

### [MEDIUM · gap] Science registry (Line S) records dead-ends/champions to local JSONL only — deposit_fn=None at the entrypoint, never reaching the durable substrate
- **Verdict:** CONFIRMED
- **Evidence:** run_apex_verify.py:82 constructs Registry(jsonl_path=jsonl_path) with NO deposit_fn -> defaults to None (registry.py:26 'deposit_fn=None'). registry.py:86-87 deposits to the durable layer only 'if self._deposit_fn is not None'. The deposit_fn path is exercised solely in tests (test_science_harness.py:323,666). Live artifact .synapse/science/apex_registry.jsonl exists (plus apex_corrected_/apex_seed2_ files — it ran). Falsifiability knowledge stays siloed, not vector-recallable. Every cited line confirmed exact.
- **Verifier opened:** scripts/run_apex_verify.py:82; python/synapse/science/registry.py:26,86-87; tests/test_science_harness.py:323,666; .synapse/science/apex_registry.jsonl present

### [MEDIUM · tech-debt] Six siloed 'what we learned' stores persist; the two-tier Moneta convergence (Line C) is unbuilt — only render-fixes ride the unified memory layer
- **Verdict:** CONFIRMED
- **Evidence:** Independent persistence paths confirmed: forge/corpus/*.json (manifest.json + observations/CE-*.json present), RecommendationHistory JSONL at ~/.synapse/agent_health_history.jsonl (history_path() agent_health.py:266), render FEEDBACK rides SynapseMemory (handlers_render.py:882), .synapse/science/apex_registry.jsonl, memory.jsonl/Moneta, router in-memory. moneta_store.py exposes protected_floor (:155, a single decay-resistance scalar — '_protected_floor if _is_protected else 0.0' at :271) but NO protected-immutable-vs-decaying two-tier RSI tiering is wired. The audit's caveat (falsifiability records must never decay, conflicting with Moneta's decay model) is real; convergence genuinely needs two tiers, neither built.
- **Verifier opened:** forge/corpus/manifest.json + observations/*.json; python/synapse/panel/agent_health.py:266; python/synapse/memory/moneta_store.py:12,35,155,271 (protected_floor is single-tier scalar, no immutable tier)

### [LOW · strength-caveat] Closed loops O and R have no production-accumulated artifact yet — closure is proven by eval, not by field telemetry
- **Verdict:** CONFIRMED
- **Evidence:** ~/.synapse/ contains memory.jsonl, agent/, gates/, etc. but NO agent_health_history.jsonl (ls exit 2, file absent) — the Line O ring buffer never accumulated in the field. Wiring requires a running Houdini panel poll (synapse_panel.py:541) to accumulate. Restart-survival rests on tests/rsi/eval_line_r_closure.py (present) and test_area4_observability.py (10 tests) rather than observed multi-session data. The throttle RECORD_INTERVAL_SEC=60.0 (agent_health.py:254, confirmed exact) means the 5x meta-recursion escalation needs ~5 real minutes of live polling — never demonstrated outside the eval harness. Fair caveat, correctly rated low.
- **Verifier opened:** ~/.synapse/agent_health_history.jsonl absent (ls exit 2); python/synapse/panel/agent_health.py:254 RECORD_INTERVAL_SEC=60.0; tests/rsi/eval_line_r_closure.py present

### [INFO · gap] Cheapest real closure remaining: Line S (one-line deposit_fn at run_apex_verify) and Line F (back _session_fast_paths with JSONL) — both ~1-3 lines against tested code
- **Verdict:** CONFIRMED
- **Evidence:** Line S seam exists: registry.py:86-87 already calls deposit_fn when non-None; run_apex_verify.py:82 just omits it; test_science_harness.py:323 proves the path works — passing deposit_fn=<moneta writer> is a one-line change. Line F: to_jsonl/from_jsonl around router.py:80 _session_fast_paths mirroring RecommendationHistory's existing JSONL pattern (test_pass8_history_and_meta.py:147,152). Both are low-activation wiring against verified code. FORGE (E) remains the only item needing genuine engineering (no verify stage exists, confirmed in finding #2), not wiring. Assessment holds.
- **Verifier opened:** scripts/run_apex_verify.py:82; python/synapse/science/registry.py:86-87; shared/router.py:80; tests/test_pass8_history_and_meta.py:147-180 (JSONL round-trip pattern to mirror)


## security

**Confirmed strengths:**

- Auth primitives are constant-time and never log raw keys: authenticate() uses hmac.compare_digest (auth.py:119), lookup_user_by_key() uses compare_digest over SHA-256 hashes (sessions.py:284), hash_key_for_log truncates a SHA-256 (auth.py:122-124). Opened and confirmed.
- validate_origin() is a real DNS-rebinding defense with fail-safe defaults: studio mode + no allowlist REJECTS (auth.py:169), non-localhost on local mode REJECTS (auth.py:162-163), and it is called on both transports (websocket.py:338, hwebserver_adapter.py:109). Confirmed.
- RBAC matrix is well-designed: deny-overrides-allow (rbac.py:131-134), explicit VIEWER deny set blocking execute_python/execute_vex/delete_node (rbac.py:102-104), non-cumulative allow sets, constant role hierarchy (rbac.py:190-195). Sound model IF enforced. Confirmed.
- DeployConfig.__post_init__ wires sane studio defaults: studio-lan/vpn force auth_required=True and bind 0.0.0.0 only when escalating from 127.0.0.1 (sessions.py:316-326), studio-vpn forces tls_enabled=True; create_tls_context pins TLS 1.2 minimum (sessions.py:396). Confirmed.
- Auth failures are audit-logged at AuditLevel.WARNING on the WS path (websocket.py:378-386). Confirmed.
- Defense-in-depth is partially real: an execute_python through the panel/MCP bridge is still undo-wrapped and integrity-verified (bridge.execute at bridge_adapter.py:267; docstring bridge_adapter.py:177) even though consent is neutered, so the op stays reversible. Confirmed.

**Findings:**

### [HIGH · risk] Default localhost mode requires NO authentication — any local process can connect to port 9999
- **Verdict:** CONFIRMED
- **Evidence:** auth.py:55-85: get_auth_key() returns None when neither SYNAPSE_API_KEY env (line 66) nor ~/.synapse/auth.key (line 74) is set. websocket.py:344-347: auth_required = auth_key is not None OR deploy_config.auth_required. DeployConfig defaults mode='local', auth_required=False (sessions.py:305,308). So out-of-the-box auth_required is False, the handshake block at websocket.py:349 is skipped, and the for-message loop at line 420 dispatches any localhost client. The project's own audit confirms it verbatim at docs/plans/2026-02-10-synapse-professional-audit.md:219.
- **Verifier opened:** auth.py:55-85; websocket.py:343-349,420; sessions.py:305-313; docs/plans/2026-02-10-synapse-professional-audit.md:219

### [HIGH · risk] execute_python (CRITICAL gate per CLAUDE.md) is NOT gated on any live transport — arbitrary Python in Houdini with zero consent
- **Verdict:** CONFIRMED
- **Evidence:** Both live transports call _handler.handle(command) directly with no bridge: websocket.py:623 and hwebserver_adapter.py:211. handlers.py _handle_execute_python compiles (handlers.py:936) and execs caller code via _run_compiled (handlers.py:967/982 -> exec at handlers.py:1504) with no consent step. The CRITICAL gate exists only inside LosslessExecutionBridge (poll at bridge.py:765), and the execute_python->critical mapping is in constants.py:99 (converted to GateLevel at bridge.py:142). Net: a default no-auth localhost client gets full in-DCC RCE with no approval prompt. Minor mislocation: finding cites the gate dict at bridge.py:142, but the literal mapping is constants.py:99 — bridge.py:142 only converts it. Substance holds.
- **Verifier opened:** websocket.py:623; hwebserver_adapter.py:211; handlers.py:936,967,982,1504; constants.py:99; bridge.py:142,765

### [HIGH · risk] The one path that DOES use the bridge (MCP/panel) explicitly neuters the consent gate
- **Verdict:** CONFIRMED
- **Evidence:** bridge_adapter.py:166-181 _panel_consent unconditionally returns True; get_bridge() at bridge_adapter.py:194-197 constructs the singleton with consent_callback=_panel_consent then sets _bridge._gate = None, disabling HumanGate. mcp/tools.py:120-124 routes non-read-only tools (including houdini_execute_python, mapped to execute_python at bridge_adapter.py:75) through execute_through_bridge -> get_bridge() -> the SAME neutered singleton. So even on the bridge path CRITICAL ops auto-approve. The deadlock rationale (GUI thread sleeping on a card it must draw, bridge_adapter.py:170-175) is legitimate engineering; the security outcome is that no live path enforces code-exec consent.
- **Verifier opened:** bridge_adapter.py:166-198,75; mcp/tools.py:120-124

### [HIGH · gap] RBAC is entirely absent from the hwebserver transport (the native/primary studio server)
- **Verdict:** CONFIRMED
- **Evidence:** hwebserver_adapter.py:54 imports only get_auth_key/authenticate/validate_origin from .auth and never imports check_permission or is_rbac_enabled (no rbac import anywhere in the file). receive() (lines 135-212) does auth handshake then dispatches straight to handler.handle() at line 211 with no per-command role check and no SessionManager. By contrast websocket.py:540-553 enforces check_permission. So a studio on hwebserver gets auth-at-connect but NO per-command authorization — an authenticated VIEWER could call execute_python. Confirmed.
- **Verifier opened:** hwebserver_adapter.py:54,135-212; websocket.py:540-553

### [MEDIUM · bug] CLAUDE.md / code drift: doc claims MCP ops use a separate gated bridge; they use the neutered panel singleton
- **Verdict:** CONFIRMED
- **Evidence:** bridge_adapter.py:178 comment asserts 'HumanGate still governs AUTONOMOUS / MCP operations, which use their own bridge instances — not this panel singleton.' Repo-wide grep shows the ONLY LosslessExecutionBridge(...) instantiation in python/synapse is the panel singleton at bridge_adapter.py:194 (agent_health.py:32 merely imports the class for typing); there is NO HumanGate(...) instantiation anywhere in the package. mcp/tools.py:121 imports execute_through_bridge from synapse.panel.bridge_adapter, so the MCP path shares the exact panel singleton with _gate=None. The CLAUDE.md §1.2.1 'APPROVE/CRITICAL block and poll' guarantee does not hold on the shipped MCP path. Confirmed.
- **Verifier opened:** bridge_adapter.py:178,194,197; agent_health.py:32; grep LosslessExecutionBridge(/HumanGate( across python/synapse

### [MEDIUM · bug] NameError in hwebserver origin validation — connect() references os.environ but os is never imported
- **Verdict:** CONFIRMED
- **Evidence:** hwebserver_adapter.py:108 calls os.environ.get('SYNAPSE_DEPLOY_MODE','local') inside connect(), but module imports (lines 22-25) are only json, logging, threading, typing — there is no 'import os' and no later os import anywhere in the file. This raises NameError before validate_origin runs (line 109), breaking the DNS-rebinding defense on this transport as written. (Finding cites os.environ at line 108 and validate_origin at 109 — exact.) Confirmed.
- **Verifier opened:** hwebserver_adapter.py:22-25,108-109

### [MEDIUM · risk] RBAC is bound to deploy mode, not auth — an authenticated single-key WS deployment runs with no authorization
- **Verdict:** CONFIRMED
- **Evidence:** is_rbac_enabled() returns mode != 'local' (rbac.py:185-186). websocket.py:540 gates the RBAC check on 'is_rbac_enabled() and self._session_manager', and _session_manager is only created when mode != 'local' (websocket.py:128-132). A user who sets only SYNAPSE_API_KEY (auth on) but leaves mode='local' gets authentication but check_permission is never called. The shared-key auth path (websocket.py:364) creates no user session, so even if mode were studio, role lookup needs a users.json directory (websocket.py:398). Confirmed.
- **Verifier opened:** rbac.py:185-186; websocket.py:128-132,364,398,540

### [MEDIUM · risk] No TLS on the localhost/LAN default and no payload size or code-content restriction on execute_python
- **Verdict:** CONFIRMED
- **Evidence:** TLS context is only built when tls_enabled (websocket.py:138-144), which __post_init__ forces only for studio-vpn (sessions.py:322-326); studio-lan binds 0.0.0.0 (sessions.py:318-321) with plaintext WebSocket and a single shared key. _handle_execute_python builds exec_globals = {'hou': hou, '__builtins__': __builtins__} (handlers.py:946) and execs with full builtins (file IO, subprocess) and no import filter, sandbox, or length cap. Confirmed.
- **Verifier opened:** websocket.py:138-144; sessions.py:318-326; handlers.py:946,1504

### [LOW · risk] Auth-required studio handshake reads exactly one message with no timeout, enabling trivial connection-slot exhaustion
- **Verdict:** CONFIRMED
- **Evidence:** websocket.py:359 auth_msg = json.loads(next(iter([websocket.recv()]))) blocks on a single recv with no read deadline; the server sets ping_interval=None and ping_timeout=None (websocket.py:273-274), so there is no protocol keepalive to reap a silent pre-auth client. The rate limiter is acquired only at websocket.py:569, AFTER the auth handshake completes, so there is no pre-auth rate limiting. A client that connects and never sends the auth frame holds a sync_serve thread-pool slot indefinitely. Low likelihood for a personal tool, real for LAN exposure. Confirmed.
- **Verifier opened:** websocket.py:273-274,359,569

### [INFO · strength-caveat] Personal-tool framing is acceptable, but the gap between documented and actual consent posture is the real exposure
- **Verdict:** CONFIRMED
- **Evidence:** For a solo dev on a trusted workstation (the stated context), no-auth localhost + auto-approved execute_python is a defensible convenience trade — and the audit doc itself frames it that way (docs/plans/2026-02-10-synapse-professional-audit.md:219 'For a personal tool this is fine'). The verified exposure is the doc/code gap: bridge_adapter.py:178 and CLAUDE.md §1.2.1/§11.5 advertise enforced CRITICAL consent + HumanGate routing that NO shipped transport provides (WS/hwebserver bypass the bridge; the panel/MCP bridge has _gate=None). A studio enabling studio-lan on the strength of those docs would wrongly believe code execution is gated and per-role authorized — on hwebserver it is neither. Treat the consent layer as integrity/undo only, not access control. Confirmed.
- **Verifier opened:** bridge_adapter.py:178,197; docs/plans/2026-02-10-synapse-professional-audit.md:219; hwebserver_adapter.py:54,211


## api-hygiene

**Confirmed strengths:**

- Single source of truth for the tool surface is real: _tool_registry.py:124 defines all 110 tools as 8-tuples in one TOOL_DEFS list; both transports import it (mcp_server.py:446 stdio, mcp/tools.py:24-43 HTTP); TOOL_DISPATCH/TOOL_JSON/TOOLS_LIST_CACHE/TOOL_NAMES are built once at import (_tool_registry.py:1318-1338). Verified by hython: 110 tuples, 110 unique names, zero dupes.
- The per-tool annotation triplet (readOnlyHint/destructiveHint/idempotentHint) at _tool_registry.py:1325-1331 is load-bearing, not decorative: the panel IA is generated from it (docs/design/SYNAPSE_PANEL_REDESIGN.md:35 says the capability surface is 'generated from that metadata, not hand-curated').
- Internal-consistency is pinned by a test: test_mcp_protocol.py:337-356 asserts len(TOOL_DEFS)==len(TOOL_DISPATCH)==len(TOOL_JSON), get_tools()/get_tool_names() length match, every tool findable via has_tool, and no duplicate names. Per-domain handler-registration tests exist too (test_cops.py:798 '21 COPs', test_hda.py:803 '5 HDA', test_e2e_sprint.py:432-439).
- Payload-builder indirection is a tidy abstraction: _passthrough/_identity/_filter_keys helpers (_tool_registry.py:49-99) decouple MCP arg shapes from handler payloads; _network_explain_payload renames root_path->node at _tool_registry.py:104 (strength cited :102 — the function starts at :102, rename line is :104).
- Defensive getattr(hou, ...) guards are the de-facto safety net at host/auth.py:78, host/daemon.py:318, host/dialog_suppression.py:121, panel/chat_panel.py:304 — all four cited sites verified. Per-callsite, paired with try/except import guards.
- MCP spec-version handling is correct and consistent: MCP_PROTOCOL_VERSION='2025-06-18' pinned at mcp/protocol.py:49 and session.py:49, echoed in initialize at server.py:392, pinned by test_mcp_protocol.py:372. This MCP-layer version is coherent and distinct from the internal wire protocol_version.

**Findings:**

### [HIGH · gap] 'Zero hallucinated APIs' is aspirational prose, NOT an enforced emit-time mechanism
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md:4 states 'All revisions verified live — zero hallucinated APIs remaining.' Grep for hasattr(hou/getattr(hou in python/synapse/mcp returns ZERO hits; grep for 'hallucinat' across all production python returns ZERO. forge/engine/schemas.py:37 HALLUCINATED_API is an offline science-harness FailureCategory enum (scenario-failure taxonomy), unrelated to the live registry. Nothing structurally blocks adding a tool whose handler calls a non-existent hou API; the only runtime backstop is the per-callsite getattr guards (host/*, panel/chat_panel.py:304) + pytest.
- **Verifier opened:** CLAUDE.md:4; forge/engine/schemas.py:25-37; grep hasattr(hou/getattr(hou over python/synapse/mcp (0 hits)

### [MEDIUM · risk] No inbound protocol_version validation — the version field is write-only dead metadata
- **Verdict:** CONFIRMED
- **Evidence:** SynapseHandler.handle() (handlers.py:303-337) dispatches purely on command.type (self._registry.get(cmd_type) at :316), never reading protocol_version. Grep for protocol_version!=/version_mismatch/unsupported protocol across python/ returns only vendored httpx/httpcore. The only reads (protocol.py:235/280) parse the field into the dataclass with default '1.0.0' but never compare it. So the 5.4.0-vs-4.0.0 mismatch is inert today, but there is no version-compat guard if the wire format ever changes.
- **Verifier opened:** python/synapse/server/handlers.py:303-337; python/synapse/core/protocol.py:235,280

### [MEDIUM · tech-debt] Product/build version drift: CLAUDE.md header is stale vs every other source
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md:3 and :680 state 'Houdini 21.0.596 / SYNAPSE v5.8.0', but pyproject.toml:7 and python/synapse/__init__.py:61 both say version='5.10.0', and README.md (:23/:199/:227/:301) + audit_panel.py:6 target build 21.0.671. The orchestrator blueprint is two minor versions and one point-build behind reality. (Finding wrote pyproject.toml:8 — version is on :7; off by one line.)
- **Verifier opened:** CLAUDE.md:3,680; pyproject.toml:7; python/synapse/__init__.py:61; README.md:199,227,301; audit_panel.py:6

### [MEDIUM · gap] The two transports are NOT at tool parity despite the docstring claiming they are
- **Verdict:** CONFIRMED
- **Evidence:** _tool_registry.py:4 docstring: 'Both transports import from this module' and :11 'Both transports pick it up automatically.' But stdio list_tools() (mcp_server.py:628-662) advertises 110 registry tools + 6 _GROUP_INFO_TOOLS (:646-651) + 1 synapse_inspect_stage (:656-660) = 117, while HTTP get_tools() (mcp/tools.py:52-58) returns TOOLS_LIST_CACHE built only from the 110 TOOL_DEFS. test_tool_registry_parity (test_mcp_protocol.py:337-356) only checks the 110-tool registry, so it cannot catch the divergence: an HTTP client sees 7 fewer tools than a stdio client.
- **Verifier opened:** python/synapse/mcp/_tool_registry.py:4-11; mcp_server.py:628-662; python/synapse/mcp/tools.py:52-58; tests/test_mcp_protocol.py:337-356

### [MEDIUM · gap] No GLOBAL registry-to-handler parity test — coverage is per-domain and can rot
- **Verdict:** CONFIRMED
- **Evidence:** Handler-registration is verified piecemeal: test_cops.py:880-900 filters TOOL_DEFS to the cops_ prefix (domain subset, count==21); test_hda.py:803 '5 HDA'; every _registry.has() call is a hardcoded single command (test_v5_features.py:316/575/579/593; test_e2e_sprint.py:439 iterates a 5-element hardcoded list; test_multi_shot.py:304; test_network_explain.py:393; test_routing.py:1477). NO test iterates every TOOL_DEFS cmd_type asserting SynapseHandler._registry.has(cmd). A registry tool with an unregistered handler passes test_tool_registry_parity (registry-internal only) and fails only at call time.
- **Verifier opened:** tests/test_cops.py:880-900; tests/test_v5_features.py:316,575,579,593; tests/test_e2e_sprint.py:432-439; tests/test_mcp_protocol.py:337-356

### [MEDIUM · risk] CommandType enum is not the source of truth and silently under-covers the live surface
- **Verdict:** PARTIAL
- **Evidence:** Core claim CONFIRMED: registry dispatches on raw command_type strings (handlers.py:316 registry.get(command.type)); a hython diff shows 30 of 110 registry command_types are absent from the CommandType enum (core/protocol.py:34-173) — incl. 'render' (_tool_registry.py:285), 'knowledge_lookup', 'configure_render_passes', all 'inspect_*', 'write_report', 'capture_viewport', 'wedge', etc. A typo'd registry cmd_type yields a runtime 'I don't recognize the command' (handlers.py:326). BUT several of the finding's named examples are WRONG: SAFE_RENDER (:138), RENDER_PROGRESSIVELY (:139), and SOLARIS_VALIDATE_ORDERING (:74) DO exist in the enum — they just aren't backed by registry TOOL_DEFS. So the finding over-states the example set while the under-coverage thesis itself holds.
- **Verifier opened:** python/synapse/server/handlers.py:316,326; python/synapse/core/protocol.py:34-173; _tool_registry.py:285; hython enum-vs-registry diff (30 missing)

### [LOW · tech-debt] Internal wire protocol_version is stated with THREE conflicting values across live code paths
- **Verdict:** CONFIRMED
- **Evidence:** mcp_server.py:148 PROTOCOL_VERSION='5.4.0', sent on every command at :330. Server side is '4.0.0': core/protocol.py:31, agent/synapse_ws.py:36, and echoed by handlers.py:618/626/632/634, websocket.py (354/374/393/416/525), hwebserver_adapter.py:126/150/159/178, api_adapter.py:119/128/136. The two ends of the same WebSocket disagree. (Bonus 4th value: from_json defaults to '1.0.0' at protocol.py:235/280 when the field is absent.)
- **Verifier opened:** mcp_server.py:148,330; python/synapse/core/protocol.py:31; agent/synapse_ws.py:36; python/synapse/server/handlers.py:618-634

### [LOW · tech-debt] Documented tool counts are inconsistent across docs (43 / 104 / 108 / 110 / 111 / 117)
- **Verdict:** CONFIRMED
- **Evidence:** Actual registry = 110 (hython-verified). CLAUDE.md:3 '108 MCP tools registered'; README.md:301 'over 110 tools'; README.md:310 '111' narrating '104 -> 108 -> 111'; README.md:320 '104 -> 108'; README.md:353 '108 -> 111'; forge/FORGE.md:352 '43 tools as of v24.x'; pyproject.toml:8 '110+ tools'. None state the 117 actually advertised over stdio. Every value in the finding's set is reproduced.
- **Verifier opened:** CLAUDE.md:3; README.md:301,310,320,353; forge/FORGE.md:352; pyproject.toml:8; hython count=110

### [LOW · tech-debt] Inspector tool (#44) bypasses TOOL_DISPATCH with a bespoke parallel code path
- **Verdict:** CONFIRMED
- **Evidence:** synapse_inspect_stage is hand-wired in mcp_server.py:474-625: own schema _INSPECTOR_TOOL_SCHEMA (:480-498), own _inspector_call_tool branch dispatched at :685-686, lazy Dispatcher singleton (:526-563), stdout-capture wrapping (:501-517). It is NOT in TOOL_DEFS, so it is invisible to TOOL_DISPATCH, to test_tool_registry_parity, and to the HTTP get_tools(). One tool living outside the single-source-of-truth undermines the registry docstring's 'both transports pick it up automatically' invariant.
- **Verifier opened:** mcp_server.py:452-498,526-563,656-660,685-686; python/synapse/mcp/tools.py:52-58 (HTTP excludes it)

### [INFO · tech-debt] Group-info pseudo-tools share the tool namespace but carry no schema/handler contract
- **Verdict:** CONFIRMED
- **Evidence:** _GROUP_INFO_TOOLS (mcp_server.py:666-673) registers 6 names (synapse_group_scene/render/usd/tops/memory/cops) as MCP Tools in list_tools() with empty inputSchema (:650) that return a knowledge blob in call_tool() (:680-681). They appear callable to the LLM but are local string preambles, not registry entries — no read_only/destructive annotations, no parity test, and only served over stdio (not in TOOLS_LIST_CACHE/HTTP). Minor surface-pollution / inconsistent contract.
- **Verifier opened:** mcp_server.py:646-651,666-673,680-681; python/synapse/mcp/tools.py:52-58


## memory-provenance

**Confirmed strengths:**

- shared/evolution.py implements genuine content-aware lossless verification: _decision_hash/_asset_hash/_parameter_hash (lines 714-735) hash slug+choice+reasoning+date+alternatives / name+path+notes+variants / slug+node+name+before+after+result, _verify_lossless (737-778) does per-item slug-keyed hash diffs catching content drift not just count, fidelity is binary 1.0-or-0.0 (line 777), and rollback (375-386, E3 fix) removes only the failed USD while preserving the immutable pre-evolution archive. CONFIRMED at the cited lines.
- The science falsifiability Registry (science/registry.py) is append-only with first-write-wins dedup keyed on (surface, kind): record() (66-89) returns False with no write/deposit/append when key in self._index (73-74); malformed JSONL rows are tolerated on load (42-64). CONFIRMED: dead-ends cannot be silently overwritten.
- MonetaBackedStore maps DECISION-type / SHOW-tier / 'gate'-source to protected via _is_protected (260-265), raises the per-handle protected quota to 100_000 (_PROTECTED_QUOTA line 175) to avoid silent demotion of the 101st pin, and on protected-deposit failure falls back to an unprotected re-deposit rather than dropping the memory (275-284). CONFIRMED at cited lines.
- run_sleep_pass() (moneta_store.py:349-405) snapshots entity-ids+payloads+types BEFORE the prune, diffs survivors AFTER, emits a PruneAudit with raw payloads for forensics, and logs any prune at WARNING (395-399). The single destructive op is auditable, not silent. CONFIRMED.
- Moneta default-OFF posture is safe: SYNAPSE_MEMORY_BACKEND defaults to 'jsonl' (store.py:698); moneta and shadow both fall back to MemoryStore(jsonl) with a logged warning on any import/construction failure (705-723); corrupt Moneta snapshots are quarantined via rename-aside (_quarantine_if_corrupt, 225-256) rather than crashing or being discarded. CONFIRMED.
- MonetaBackedStore serializes all engine access through an RLock (line 169) with a documented FC4 single-writer rationale (162-168), and _iter_memories (289-297) materializes rows under the lock to give each read an atomic point-in-time snapshot while running JSON deserialization lock-free. CONFIRMED concurrency design.
- The JSONL MemoryStore uses a writer-priority ReadWriteLock (store.py:59-135: new readers queue behind a waiting writer via _writer_waiting at 114/126-129) to prevent writer starvation, and an atexit-registered _shutdown_flush (registered line 202, drains buffer at 267-270) so buffered adds survive a clean interpreter exit. CONFIRMED.

**Findings:**

### [HIGH · bug] MCP synapse_evolve_memory tool is dead-on-arrival: imports an undefined function and checks an impossible branch
- **Verdict:** CONFIRMED
- **Evidence:** handlers_memory.py:238 imports evolve_to_charmeleon, which is defined NOWHERE (grep 'def evolve_to_charmeleon' across python/ and shared/ returns zero; only evolvers are evolve_to_structured at python/synapse/memory/evolution.py:214 and shared/evolution.py:332). The import is function-local inside _handle_evolve_memory, so every call (including the default dry_run=True path) raises ImportError before reaching line 247. Independently, the evolve branch at line 250 gates on status['target']=='charmeleon' but check_evolution (evolution.py:109) returns target='structured' if triggers_met else None — never 'charmeleon' — so the branch is unreachable dead code even if the import resolved. Tool cannot run.
- **Verifier opened:** handlers_memory.py:238,250; python/synapse/memory/evolution.py:109,214; grep 'def evolve_to_charmeleon' empty across python/ shared/

### [HIGH · risk] Two divergent evolution implementations; the production MCP path points at the NON-lossless one
- **Verdict:** CONFIRMED
- **Evidence:** Confirmed but partly moot due to Finding 1. python/synapse/memory/evolution.py:evolve_to_structured (214-284) has no lossless verification: it writes USD (267), archives original (270-273), then generate_companion_md (276) which at line 337 does open(md_path,'w') OVERWRITING the live markdown. The companion (287-338) emits ONLY sessions (date+narrative, 308-318) and decisions (choice+reasoning, 320-335) — it drops parameters from the companion entirely, plus blockers, decision alternatives, asset variants. The MCP handler imports from this module (handlers_memory.py:238), so CLAUDE.md Rule 10 'lossless or aborted' does not hold on the artist-triggered path. Caveat: that path is currently unreachable (Finding 1's ImportError), so the data-loss is latent-until-the-import-is-fixed, not actively firing.
- **Verifier opened:** python/synapse/memory/evolution.py:214-284, 287-338 (esp. 337 open 'w'); handlers_memory.py:238; contrast shared/evolution.py:375-389

### [HIGH · risk] CLAUDE.md claims atomic (.tmp+replace) JSONL persistence for memory; no atomic write exists in the memory store or evolution
- **Verdict:** PARTIAL
- **Evidence:** The atomicity claim is correctly refuted for the primary memory store: grep os.replace/.tmp/os.rename across python/synapse/memory/ and shared/evolution.py = ZERO. MemoryStore.save() (store.py:366-393) is a plain truncating open(memory_file,'w') full rewrite (372); _flush_writes on the update/delete path calls that same non-atomic save() (243). A crash mid-save corrupts/truncates memory.jsonl with no temp+rename guard. The only .tmp+replace is in shared/conductor_advisor.py:to_jsonl (429 .tmp, 435 tmp.replace) whose docstring honestly says 'Atomic-ish' (425). Downgraded to PARTIAL on a precision point: CLAUDE.md 16.4's 'JSONL persistence is atomic via .tmp+replace' is scoped to RecommendationHistory (the advisor telemetry, where it IS atomic-on-rename), NOT to the primary memory store — so it is a scope-confusion / mislocated claim rather than a flatly false one. The underlying risk (non-atomic memory.jsonl rewrite) is real and high. Note: even the advisor write has no fsync, so it is atomic-on-rename but not crash-durable.
- **Verifier opened:** store.py:366-393,243; grep os.replace/.tmp in memory/ + shared/evolution.py = ZERO; shared/conductor_advisor.py:425,429,435

### [MEDIUM · gap] Phase 2 provenance module (shared/provenance.py) does not exist; provenance is a per-handoff in-memory list, never durably written
- **Verdict:** CONFIRMED
- **Evidence:** shared/provenance.py is MISSING (ls returns no such file; CLAUDE.md Phase 2 lists it as a deliverable). AgentHandoff.provenance is a list[tuple[str,str]] (bridge.py:891) mutated only in memory by extend_provenance (901-902). agent_state.log_handoff (456-482) persists from_agent/to_agent/task_id/fidelity_at_handoff/timestamp (473-479) to agent.usd but authors NO provenance-chain attribute. The chain is verified at handoff time (verify(), 893-899) but never durably recorded on disk.
- **Verifier opened:** ls shared/provenance.py = MISSING; shared/bridge.py:891,901-902; python/synapse/memory/agent_state.py:456-482

### [MEDIUM · gap] Live JSONL evolution is detection-only — it logs 'should evolve' but never evolves
- **Verdict:** CONFIRMED
- **Evidence:** MemoryStore._check_evolution (store.py:426-443) is the only automatic trigger, fired every _EVOLUTION_CHECK_INTERVAL=10 adds (line 164, gate at 421). It calls the read-only check_evolution and on should_evolve only logger.info('Memory evolution triggered...') (436-441) — it never calls any evolve_to_* function. Grep for live (non-def, non-.pyc) calls to evolve_to_structured in python/synapse returns zero source hits. So normal operation accumulates flat JSONL forever; the Charmander->Charmeleon transition only happens via the manual MCP tool, which is itself broken (Finding 1). The Pokemon evolution model is effectively never executed in production.
- **Verifier opened:** store.py:164,421,426-443; grep evolve_to_structured python/synapse = only def + .pyc, no live call site

### [MEDIUM · tech-debt] agent.usd routing-log/handoff/session-history every-write opens, mutates, and Save()s the entire stage with no atomicity or locking
- **Verdict:** CONFIRMED
- **Evidence:** Every agent_state writer does Usd.Stage.Open(path) -> mutate -> stage.GetRootLayer().Save() with no lock and no temp-write: log_routing_decision (def 399, Open 409, Save 425), log_handoff (Open 465, Save 481), log_integrity (def 325, Open 337, Save 364), log_session (def 550, Open 555, Save 579), create_task (231, Save 244), update_task_status (247, Save 272). The decision_NNNN counter via _counter_suffix uses len(matching children) (50-55, idx=len at 54) which is non-atomic under concurrency; concurrent async-MCP writers racing the same agent.usd read-modify-write clobber counters, and a crash during Save can leave a partial USD. Contradicts the Phase 4/5 framing of agent.usd as the durable provenance store.
- **Verifier opened:** python/synapse/memory/agent_state.py:50-55, 399/409/425, 465/481, 325/337/364, 550/555/579, 231/244, 247/272

### [MEDIUM · risk] Moneta save() durability is best-effort and silently swallows snapshot failures
- **Verdict:** CONFIRMED
- **Evidence:** MonetaBackedStore.save() (moneta_store.py:339-348) calls dur.snapshot_ecs(self._handle.ecs) inside try/except that on failure only logger.warning('Moneta snapshot on save() failed: %s') and returns (346-347) — in-memory engine state is not persisted and the caller gets no error/exception. The snapshot daemon is deliberately NOT started (from_storage_dir docstring 190-192, FC4 race), so durability depends entirely on these synchronous save() calls succeeding. Whether snapshot_ecs is internally atomic is in the external Moneta package and was correctly hedged as unverifiable from this repo.
- **Verifier opened:** python/synapse/memory/moneta_store.py:339-348 (esp. 346-347), 190-192 docstring

### [LOW · tech-debt] Science/falsifiability registry JSONL append is non-atomic and best-effort; a write failure is silently swallowed
- **Verdict:** CONFIRMED
- **Evidence:** Registry.record (science/registry.py:66-89) appends with open(self._jsonl_path,'a') inside try/except OSError: pass (79-84). The in-memory index and ordered list are updated (76-77) BEFORE and regardless of whether the disk append succeeds, so a verdict can exist in-process but never be persisted, with no signal. No fsync, no temp+rename. The dedup model prevents overwrite of an already-persisted record, but the durability of the FIRST write of a never-decay dead-end is not guaranteed.
- **Verifier opened:** python/synapse/science/registry.py:66-89 (esp. 76-77 then 79-84)

### [LOW · gap] Science registry deposit_fn is unwired at the live entrypoint — falsifiability records never reach Moneta
- **Verdict:** CONFIRMED
- **Evidence:** Registry.__init__ accepts deposit_fn (registry.py:26, used at 86-87 as 'the Moneta / synapse_write_report injection point'). grep deposit_fn across python/synapse shows it appears ONLY in registry.py itself — no caller ever passes one. loop.py (the science driver) receives registry as a parameter (line 9) and calls registry.record (72) but never constructs it with a deposit_fn; no production call site in python/synapse constructs the science Registry with a deposit_fn at all. So confirmed-absent/champion verdicts persist only to local .jsonl and are never deposited into the queryable substrate (recall/RAG can't see them) — the recall-seam gap, located at the registry layer. (Partial reliance on auto-memory notes, but the code grep substantiates the unwired state.)
- **Verifier opened:** python/synapse/science/registry.py:26,86-87; loop.py:4,9,72; grep deposit_fn = registry.py only

### [LOW · risk] MonetaBackedStore breaks the MemoryStore contract: update/delete/clear raise instead of degrading
- **Verdict:** CONFIRMED
- **Evidence:** update (moneta_store.py:416-420), delete (422-426), clear (428+) all raise MonetaUpdateNotSupported. Fine in shadow mode (ShadowMemoryStore isolates via _shadow_write). But if SYNAPSE_MEMORY_BACKEND=moneta is set PRIMARY, any caller doing memory.update()/delete() (consolidation, correction of a wrong memory) hard-fails — the Moneta backend is read+append only with no targeted-correction path. A real limitation for a memory that records revisable decisions. Correctly rated low given Moneta is default-OFF.
- **Verifier opened:** python/synapse/memory/moneta_store.py:416,422,428

### [INFO · strength-caveat] Session-narrative content drift is explicitly excluded from the lossless guarantee
- **Verdict:** CONFIRMED
- **Evidence:** shared/evolution.py:_verify_lossless checks session COUNT only (743-746) with the comment 'text content drift is allowed because the companion summarizes — sessions are narrative, not structured'. Decisions/assets/parameters get per-item content-hash diffs (748-773) but sessions do not. In the shared/ path the narrative still round-trips (companion emits session.text), but the GUARANTEE is documented as count-only; combined with the non-lossless python/synapse/memory companion (which drops parameters and emits only date+narrative), 'lossless' for session narratives is weaker than the Pokemon model implies. Fair strength-caveat on the otherwise-solid shared/evolution.py.
- **Verifier opened:** shared/evolution.py:741-746; contrast 748-773 (decisions/assets/params hashed)

### [INFO · tech-debt] get_context_summary recent_activity can still duplicate headings despite the H-4 summary fix
- **Verdict:** CONFIRMED
- **Evidence:** store.py:823-826 documents H-4: empty summary auto-derives from the first content line, producing duplicate headings for templated session summaries, and asks callers to pass an explicit summary. get_context_summary renders recent activity as '- [{type_name}] {m.summary}' (line 977). decision() (884-915) and action() (917-937) both call self.add(...) with NO summary= argument, so their summary falls back to the auto-derived first content line. The de-dup was applied only at the session-summary write site, not enforced at the model level — the duplicate-heading class remains latent for action/decision memories rendered via recent activity.
- **Verifier opened:** python/synapse/memory/store.py:823-826, 955-978 (render at 977), 884-915 decision(), 917-937 action()


## release-velocity

**Confirmed strengths:**

- Doc-conformance tests are REAL and wired into the CI gate. Opened tests/test_router_internals.py:296-327 (TestClaudeMdConformance: pins FAST_PATH_PROMOTION_THRESHOLD/CONSTANTS_HASH/ROUTER_CALIBRATION_PERIOD==10) and tests/test_pass7_per_agent_and_canonical.py:313-407 (pins all 11 §16 public-API identifiers + 4 Recommendation kinds + 3 threshold NAMES + §16 title). These genuinely fail loud on identifier renames — a real drift tripwire.
- Reusable canonical-pinning infrastructure is mature and evidence-driven. tests/_conformance.py:1-91 docstring (lines 4-7) explicitly states it was built after three manually-caught drift bugs across passes 3/5/6; assert_value_in_all_files emits one consolidated failure naming every out-of-sync file. Confirmed at lines 36-91.
- §16.4 advisor threshold VALUES are in sync today and §15 manifest is honest. shared/conductor_advisor.py:95/100/105/376 define exactly MIN_OPS_FOR_VERDICT=10 / DRIFT_FIELD_CLUSTER_THRESHOLD=3 / REPEATED_RECOMMENDATION_THRESHOLD=5 / DEFAULT_CAPACITY=500. §15 commit hashes 128229d, e71fbfe, 3ae4737 all resolve to real commits (git cat-file -t = commit).
- Branch-per-feature hygiene is real and clean. git branch shows feat/latency-finish, feat/panel-pentagram, feat/vex-corpus-rag, forge/routing, forge/ui, chore/amd-library-capture; conventional-commit subjects throughout (fix(ci):, docs(readme):, feat(panel):); visible PR workflow up to #28.
- CI runs the FULL suite on a Python 3.11 + 3.14 matrix. .github/workflows/ci.yml:13 (matrix) + :49 (python -m pytest tests/ -v --tb=short) — the doc-conformance tests run on every push to master and every PR, so the tripwire is gated, not ad-hoc.

**Findings:**

### [MEDIUM · tech-debt] CLAUDE.md line-count annotations are stale by 18-44% across 6 assertions; conformance tests pin identifiers but NOT magnitudes
- **Verdict:** CONFIRMED
- **Evidence:** wc -l: shared/bridge.py=925 (doc 644, +44%), shared/evolution.py=778 (doc 593, +31%), shared/router.py=321 (doc 271, +18%). Stale numbers at CLAUDE.md:501,513,525 (Phase files) AND 664-666 (file-structure block) — each appears twice. tests/_conformance.py:57,74 uses pattern.search(text) string-presence only, so no test guards the magnitude. Genuine doc:code drift.
- **Verifier opened:** Opened CLAUDE.md:501,513,525,664-666 + tests/_conformance.py:36-91; ran wc -l on all three modules.

### [MEDIUM · tech-debt] CLAUDE.md version banner is 2 minor releases stale; tool count disagrees across docs (108 vs 110 vs 111)
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md:3 = 'SYNAPSE v5.8.0 ... 108 MCP tools'; pyproject.toml:7 version='5.10.0'. README has THREE distinct live counts: 110 (lines 29,301), 111 (line 310), 108 (lines 320,338,353). git: CLAUDE.md last edited 2026-04-09, README 2026-06-02 — the banner is the most-drifted, first-trusted line.
- **Verifier opened:** Opened CLAUDE.md:3,680 + pyproject.toml:7 + README.md lines 29/301/310/320/338/353; git log -1 dates on both files.

### [MEDIUM · risk] Velocity heavily skewed to panel/UI; the same Houdini panel was redesigned end-to-end TWICE
- **Verdict:** CONFIRMED
- **Evidence:** Last 200 commits: 31 carry (panel)/(ui) subject scope; 115 file-touches hit panel/pypanel/designsystem. Two distinct, both-shipped redesign briefs: docs/design/SYNAPSE_PANEL_REDESIGN.md ('First-principles redesign', PR #21 via 6d391ca) and docs/SYNAPSE_PANEL_REDESIGN_HARNESS.md ('Pentagram pass', PR #27 via feat/panel-pentagram). Doc heads confirm they are genuinely separate briefs. Competes with the 3 Phase-4/5/6 substrate items still marked 🔶 — matches CLAUDE.md's own 'framework edits = avoidance' pattern at the UI layer.
- **Verifier opened:** git log -200 scope+name-only counts; opened head -3 of both redesign docs; confirmed PR #21 and #27 merge commits.

### [MEDIUM · risk] Bus factor = 1, hard. Single human committer across entire history
- **Verdict:** CONFIRMED
- **Evidence:** git log -200 --format=%an: 180 'Joseph Ibrahim' + 20 'joseph ibrahim' (casing variant, same person) = 100% single-author. No independent reviewer; the doc-conformance + canonical-pin tests are the de-facto reviewer (a smart mitigation), but a single absence stalls the project.
- **Verifier opened:** git log -200 --format=%an | sort | uniq -c → 180+20.

### [LOW · gap] Conformance tests catch identifier renames but not signature/return-shape/value drift; §16.2 keys and §16.4 threshold VALUES are unguarded
- **Verdict:** CONFIRMED
- **Evidence:** tests/_conformance.py:57,74 asserts only literal-string presence in both doc and module. The threshold test (test_pass7:391-399) pins the NAMES MIN_OPS_FOR_VERDICT/DRIFT_FIELD_CLUSTER_THRESHOLD/REPEATED_RECOMMENDATION_THRESHOLD — never their values 10/3/5. If conductor_advisor.py:95-105 changed a value or operation_stats() dropped a key, the name-presence tests still pass. Values match today (verified 10/3/5/500), so the gap is latent not active.
- **Verifier opened:** Opened tests/_conformance.py:36-91, tests/test_pass7_per_agent_and_canonical.py:391-399, shared/conductor_advisor.py:95,100,105,376.

### [LOW · tech-debt] CLAUDE.md STATUS table still marks Phases 4/5/6 unbuilt (🔶) while agent.usd schema/router-integration shipped in git
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md:808-810 mark 'agent.usd Schema|🔶 Phase 4', 'Routing Log Persistence|🔶 Phase 5', 'E2E Pipeline Orchestrator|🔶 Phase 6'. git log: d31bbae 'feat(agent-state): upgrade agent.usd schema to v2.0.0' and d1ad901 'feat(moe): wire MOE infrastructure into production request pipeline' both exist and resolve. Status table understates completion (inverse drift, still misleading).
- **Verifier opened:** Opened CLAUDE.md:805-811; git cat-file -t d31bbae/d1ad901 = commit; grepped git log for agent.usd/wire MOE.

### [LOW · gap] No lint/type-check/coverage gate in CI; only pytest
- **Verdict:** CONFIRMED
- **Evidence:** .github/workflows/ci.yml has exactly one test step at line 49 (python -m pytest tests/ -v --tb=short). No ruff/flake8/mypy/pyright, no coverage threshold, no doc-link/badge checker. Given heavy try/except import guards for hou (CLAUDE.md §12), hou-API typos surface only at Houdini runtime. Badge confirms no auto-sync: README:16 says tests-3168 but pytest --collect-only reports 3213 collected (45-test drift).
- **Verifier opened:** Opened .github/workflows/ci.yml:1-49; ran pytest --collect-only (3213) vs README.md:16 badge (3168).

### [LOW · strength-caveat] 'Verified live / zero hallucinated APIs' masthead is stronger than the test surface can back
- **Verdict:** CONFIRMED
- **Evidence:** CLAUDE.md carries 8 'verified live'/'Verified H21' assertions (lines 4,680,797,798,799,805,806,807) plus masthead 'zero hallucinated APIs remaining'. §15 commit hashes check out and conformance tests are real, so design rigor is genuine — but no CI test asserts a hou API actually resolves on H21 (verification was manual hython recon per memory notes). Doc volume is mostly an asset (153-file rag corpus + signed-off specs); only the absolute 'zero hallucinated' framing exceeds what CI can falsify.
- **Verifier opened:** grep -cE 'verified live|Verified H21' CLAUDE.md = 8; opened the 8 match lines; confirmed ci.yml has no hou-resolution test.

### [INFO · tech-debt] Untracked workspace clutter at repo root, including a near-duplicate of a tracked doc
- **Verdict:** PARTIAL
- **Evidence:** Core claim holds and is now WORSE than cited: finding says 3 untracked root files (accurate at the git-status snapshot), but live git status now shows 5 (SYNAPSE_PANEL_REDESIGN_HARNESS.md, SYNAPSE_SCIENCE_HARNESS_v3.md, mile1_rail_markdot.patch, phase0_0_probe.py, synapse_panel_pentagram_v3.html). git check-ignore exits 1 (none ignored) — confirmed. Root SYNAPSE_PANEL_REDESIGN_HARNESS.md is a near-byte-duplicate of tracked docs/SYNAPSE_PANEL_REDESIGN_HARNESS.md (head content character-identical; diff flags only line-ending differences). 'partial' solely because the count is now 5 not 3, not because the claim is wrong.
- **Verifier opened:** git status --porcelain (5 ??), git check-ignore (exit 1), diff head -5 root vs docs/ copy, ls docs/SYNAPSE_PANEL_REDESIGN_HARNESS.md.


---

# Part III — Deferred / unprobed areas (completeness critic)

The review covered 8 dimensions but did **not** probe the following. They are recorded, not dismissed — several are higher-stakes than parts of Part II and each warrants its own review. **Do not assume these are safe.**

### Autonomous LLM-in-the-loop execution path (panel/claude_worker.py + cognitive/agent_loop.py) — the agent that DRIVES the tools was never reviewed
All 8 dimensions reviewed the tool surface and transports, but none probed the loop where Claude itself selects and dispatches tools. claude_worker.py:_conversation_loop repeats API calls 'until Claude stops requesting tools' (claude_worker.py:123-157) and is armed with get_anthropic_tools() (tool_bridge.py:82-89), which returns the FULL unfiltered _TOOLS_CACHE — including houdini_execute_python — with no read-only/destructive allowlist. Those tool calls execute through the same panel bridge singleton whose consent gate is neutered (_gate=None, _panel_consent->True). Net unprobed risk: an LLM, not a human, can autonomously emit arbitrary in-DCC Python in an unbounded-by-content loop with auto-approved consent. The security dimension verified the human RCE path but never the autonomous one. (Note: the OTHER loop, cognitive/agent_loop.py via dispatcher, is safely scoped — it only registers inspect_stage + write_report. The panel worker is the exposed one. This asymmetry itself went unexamined.)

### Concurrency correctness under multiple simultaneous MCP clients hitting one single-threaded Houdini main thread
main_thread.py uses non-blocking hdefereval.executeDeferred() + a per-call threading.Event (main_thread.py:5-6,93) with a _stall_lock that only guards stall-detection, NOT mutation serialization or ordering. Neither websocket.py nor hwebserver_adapter.py imposes a max-client cap or a global dispatch semaphore (grep for max_clients/Semaphore = none). The substrate-correctness dimension verified the async->sync boundary for ONE operation but never asked: if two clients (e.g. the panel LLM worker AND a Claude Desktop stdio client) interleave mutations, are undo groups still well-nested, do scene_hash_before/after stay coherent, does the decision_NNNN counter (len-based, agent_state.py:50-55, already flagged non-atomic) race? There is no concurrent-client test anywhere. The 'thread safety' anchor was verified for single-caller correctness, not for multi-client interleaving on the shared main thread.

### EmergencyProtocol / emergency-halt is a dead safety feature — declared, documented as a core guarantee, zero callers
CLAUDE.md §1.8 and Safety Rule 11 present trigger_emergency_halt as a load-bearing 'immediate pipeline stop' (cancel dispatches, suspend PDG cooks, write emergency state, generate recovery capture). grep across python/ and shared/ shows trigger_emergency_halt is defined ONCE (bridge.py:911) and invoked NOWHERE. No watchdog freeze, no fidelity<1.0 detection, no signal handler, and no resilience.py Watchdog (which DOES detect 5s main-thread freezes) wires into it. The architecture dimension catalogued the bridge's anchors but never checked whether the documented panic button is actually connected to anything. It is not — a class of 'documented-but-unreachable safety mechanism' that parallels the bridge-absence finding but was missed entirely.

### Render-farm / TOPS-PDG live execution path correctness and its subprocess egress
There is a substantial render subsystem — render_farm.py, handlers_render.py, render_notify.py, render_diagnostics.py, and a 7-file handlers_tops/ package (cook/wedge/work_items/render_sequence/diagnostics) — that no dimension examined for correctness despite it being the most resource-expensive and longest-running path. Specific unprobed items: (1) handlers_render.py:368 and render_notify.py:137 spawn subprocess (iconvert, PowerShell toast) — list-args, not shell=True, and the toast template XML-sanitizes title/body, so injection looks contained, but no test or review verified the sanitization is complete or that husk/iconvert paths are validated. (2) The R8 PDG async-cook bridge was verified in shared/bridge.py, but the LIVE TOPS cook path runs through handlers_tops/cook.py on the bridge-less /synapse transport — so the documented pdg.PyEventHandler / dirtyAllTasks rollback safety almost certainly does NOT apply to production TOPS cooks, exactly as the SOP undo-wrap does not. No dimension confirmed whether live PDG cooks have ANY rollback. (3) autonomous_render (handlers.py:1387) is an LLM-driven re-render loop (max_iterations default 3) that was named in the RSI dimension only for its memory wiring, never for its execution safety.

### Supply-chain / dependency posture of the 22MB vendored Anthropic SDK + transitive deps
python/synapse/_vendor/ ships pinned copies of anthropic-0.96.0, pydantic, pydantic_core (compiled), httpx, httpcore, h11, certifi, jiter, etc. — 22MB checked into the repo and force-un-ignored in .gitignore. No dimension assessed: pinned-version CVE exposure, the maintenance burden of manual vendor bumps (no Dependabot/renovate, and the release-velocity dimension confirmed CI has no dependency or security scanning), or the trust boundary of bundling a network-egress HTTP client + TLS root bundle (certifi-2026.2.25) that the daemon imports. For a tool that opens a localhost RCE port AND makes outbound TLS calls to api.anthropic.com, the egress dependency stack is a security-relevant surface that went entirely unreviewed.

### Data egress / privacy: what scene, memory, and project content is serialized into Anthropic API prompts
The security dimension scoped itself to the inbound localhost port and consent gating, never the OUTBOUND direction. agent_loop.py and claude_worker.py build prompts that can include system context, recalled memory, and scene/tool-result payloads (agent_loop.py:101-225 system/user prompt assembly; tool_results fed back each turn). For a studio deployment (studio-lan/vpn modes the security dim treated as in-scope), client scene data, asset paths, and memory.jsonl decision records would leave the network to a third-party API. No data-classification, redaction, opt-out, or 'what leaves the building' analysis exists in any dimension — and CLAUDE.md's privacy posture on prompt content is undocumented.

### Disaster recovery & artifact durability beyond single-write atomicity
The memory-provenance dimension correctly flagged non-atomic individual writes to memory.jsonl and agent.usd, but stopped at the single-write level. The broader DR story is unexamined: there is no backup, snapshot-rotation, or generational copy of memory.jsonl, agent.usd, or the .synapse/science/*.jsonl falsifiability records (grep for backup/.bak/rotate/shutil.copy in memory/ = none). Combined with the already-confirmed truncating full-rewrite save() and the Moneta save() that silently swallows snapshot failures, a single corrupting crash or bad evolution destroys the entire accumulated memory with no recovery point. The 'lossless' brand is about per-operation reversibility via undo; nobody asked about lossless-ness across a disk-corruption or accidental-delete event, which for an accreting memory substrate is the higher-stakes durability question.

### Performance / scale envelope — no load, latency-budget, or memory-growth bounds were measured anywhere
Every dimension is correctness- or safety-oriented; none established the operating envelope. Unanswered, unmeasured: how does the bridge-less handler path latency-degrade as memory.jsonl grows unbounded (live JSONL evolution is detection-only per memory dim, so it grows FOREVER); what is the main-thread dispatch throughput ceiling; how large can a single scene_hash traversal get on a heavy scene before the 120s execute_async timeout (bridge.py:551) trips on legitimately-slow cooks rather than stalls; what is the IntegrityBlock log memory footprint at log_capacity. The release-velocity dimension noted CI has no coverage gate, but no dimension noted CI has no perf/regression benchmark and no documented SLO — so any latency regression (the very thing the 'latency-finish' PR #28 chased) ships unguarded.

---

# Part IV — Remediation at a glance

Full requirements, acceptance criteria, and priorities are in the companion PRD (`docs/SYNAPSE_HARDENING_PRD.md`). The spine:

**Decisions needed first:**
- **D1 (this week):** `execute_python`/`execute_vex` consent — enforce a real handler-layer gate, or keep auto-approve for single-user localhost and delete the doc claim. (Today the docs promise a gate no live transport provides.)
- **D2 (architectural):** make `LosslessExecutionBridge` the real live path (and *measure* its anchors), or retire it to audit-only and rewrite the 'only code path / cannot bypass' framing.
- **D3:** Moneta two-tier convergence (immutable falsifiability + decaying) — commit or defer.
- **D4:** FORGE — build the generate→apply→verify stage, or stop reporting `fixes_validated`.

**P0 (this week, ≤1 day each):** fix the `os` `NameError` that breaks origin validation on the production transport; commit the (currently working-tree-only) S1 undo fix; execute D1; two one-line RSI loop-closures (science `deposit_fn`, persist router fast-paths); mark the stale RSI audit superseded.

**P1 (this month):** RBAC on the hwebserver transport; fix/remove the dead `synapse_evolve_memory` tool; atomic `memory.jsonl` writes; async consent wait; first hython integration test; registry→handler + transport tool-count parity tests.

**P2 (this quarter):** resolve the two-bridges/one-name architecture; converge the two WebSocket servers; S2 (hash the LOP stage) + S3 (trace outputs()); two-tier Moneta; FORGE verify stage; single-source version/tool-count + conformance on values not just identifiers.

---

*Provenance: multi-agent review workflow `w46nxfiu3` (18 agents, adversarial verification). No code was changed by the review. Findings are a derivative artifact; refuted findings are excluded, partial findings flagged.*