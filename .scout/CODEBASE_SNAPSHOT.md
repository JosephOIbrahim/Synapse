# SYNAPSE · CODEBASE SNAPSHOT — 2026-06-14

> **Scout run.** Read-only recon, fact-tagged. Disk wins over RAG/memory.
> **Fact tags:** `[path:line]` read · `[grep]` matched · `[V1]` ran live in Houdini · `[table]` read from the committed introspected `dir()` symbol table (`python/synapse/cognitive/tools/data/h21_symbol_table.json`) · `[ASSUMED]` not confirmed.
> **Live bridge was DOWN this run** (`ws://localhost:9999/synapse` handshake timeout) → **§8 live-runtime probes = `[NOT RUN]`**; the §8 symbol-table supplement (table-backed, not a live session) is in **§6 Part B**, and the owed live probes are listed in §8.
> Repo `C:\Users\User\SYNAPSE`, branch `master`. Houdini 21.0.671 graphical / hython 21.0.631 (separate site-packages, both embed python311). Produced by an 8-agent read-only scout workflow.

---

## §1 · IDENTITY & VERSION REALITY

### 1.1 Real repo version — converges on **5.14.0**

| Source | Value | Tag |
|---|---|---|
| `pyproject.toml` `[project].version` | `5.14.0` | [python\synapse… pyproject.toml:7] |
| `python/synapse/__init__.py` `__version__` | `5.14.0` | [python\synapse\__init__.py:61] |
| `python/synapse/__init__.py` docstring `Version:` | `5.14.0` | [python\synapse\__init__.py:17] |
| Latest git tag (by creator date) | `v5.14.0` | [grep] `git tag --sort=-creatordate` |
| `git describe --tags` | `v5.14.0-1-g86ef9bc` | [grep] |
| HEAD commit (live) | `86ef9bc docs(harness): add multi-provider LLM abstraction harness v1 — ARCHITECT dispatch` | [grep] `git log -1` |

**Drift vs. my brief:** the prompt's git-status snapshot named `c0cabd7 docs(release): v5.14.0` as HEAD; the live repo is **one commit ahead** at `86ef9bc` [grep]. `git describe` confirms `-1-g86ef9bc` (1 commit past the v5.14.0 tag). The version number itself is stable at 5.14.0 across all six on-disk sources — *no* version-string drift. (Note one stale literal: `mcp/server.py:110` falls back to `"5.8.0"` if `importlib.metadata` can't resolve `synapse-houdini` — dead fallback, not the live value [python\synapse\mcp\server.py:104-110].)

### 1.2 CLAUDE.md banner — "Python 3.14" is the live drift, NOT the version

`CLAUDE.md:3` banner asserts: **"Houdini 21.0.631 · SYNAPSE v5.14.0 · Python 3.14 · 112 MCP tools registered"** [C:\Users\User\SYNAPSE\CLAUDE.md:3].

- **v5.14.0** — confirmed (§1.1). Not drift.
- **112 MCP tools** — confirmed against the registry (§1.4). Not drift *for the registry count* — but ambiguous vs. the stdio surface (120) and the panel (110 per memory). See §1.4.
- **Python 3.14 — REFUTED on disk.** `__init__.py` vendors a `pydantic_core` `.cp311-win_amd64.pyd` and gates the vendor path to **exactly `version_info[:2] == (3, 11)` on Windows** because every current Houdini point release embeds Python 3.11 [python\synapse\__init__.py:34-57]. The module comment is explicit: *"stock Python 3.14 in particular — the 2684-test suite runs there"* — i.e. **3.14 is the standalone CI/test interpreter, NOT the Houdini runtime**. `pyproject.toml` `requires-python = ">=3.9"` and classifiers stop at `3.11` [pyproject.toml:14,22-24]; `[tool.mypy] python_version = "3.11"` [pyproject.toml:90]. The banner's "Python 3.14" describes the harness interpreter (I confirmed the host shell here is Python 3.14 — `literal_eval` traced to `C:\Python314\Lib\ast.py` [Bash]), **not** the embedded Houdini interpreter, which is **3.11**. Banner drift confirmed, matches the brief's suspicion.

### 1.3 Wire / WebSocket protocol version — **FOUR conflicting values**, write-only

The internal wire `protocol_version` (distinct from the MCP spec version) is stated inconsistently across the two ends of the same socket:

| Value | Where | Tag |
|---|---|---|
| **`4.0.0`** | `core/protocol.py:31` `PROTOCOL_VERSION` (the canonical server-side constant, imported by `__init__`, `websocket.py`, `handlers.py`, `hwebserver_adapter.py`, `api_adapter.py`, `agent/synapse_ws.py:36`) | [python\synapse\core\protocol.py:31], [grep] |
| **`5.4.0`** | `mcp_server.py:182` `PROTOCOL_VERSION = "5.4.0"`, stamped on every outbound command at `:330` | [mcp_server.py:182,330] |
| **`1.0.0`** | `core/protocol.py:235,280` — `from_json` default when the field is absent | [python\synapse\core\protocol.py:235,280] |
| **`5.4.0`** | `tests/test_inspect_live.py:83` `_LIVE_PROTOCOL_VERSION = "5.4.0"` (test mirrors the stdio side) | [grep] |

The two ends of the same WebSocket disagree (server `4.0.0` vs stdio bridge `5.4.0`). It is **write-only dead metadata** — `handlers.py` echoes it back but never validates an inbound value [grep handlers.py:679-695]; prior CTO reviews already flagged this as C33 / a DOC-1 pin candidate [docs\SYNAPSE_CTO_REVIEW_2026-06-09.md:126]. **Separate and coherent:** the MCP *spec* version `MCP_PROTOCOL_VERSION = "2025-06-18"` is single-sourced at `mcp/protocol.py:49` and echoed at `mcp/session.py:49` + `mcp/server.py:392` — that one is consistent [python\synapse\mcp\protocol.py:49].

### 1.4 The tool-count disagreement — every assertion, then the truth

**Authoritative count (computed from disk):** `TOOL_DEFS` is a list of 8-tuples at `_tool_registry.py:124` [python\synapse\mcp\_tool_registry.py:124]. An AST walk of the literal yields **112 entries, 112 unique names, 0 duplicates** [Bash, ast.parse]. This is the canonical "registry tool" count and the single source of truth — `mcp_server.py` imports it (`TOOL_DEFS as _REGISTRY_TOOL_DEFS`) rather than redefining it [mcp_server.py:446-447], and the panel command palette imports the same `TOOL_DEFS` [python\synapse\panel\command_palette.py:447].

Every count assertion found:

| # | Location | Asserts | Tag | Meaning |
|---|---|---|---|---|
| 1 | `CLAUDE.md:3` banner | **112** "MCP tools registered" | [CLAUDE.md:3] | = registry count ✓ |
| 2 | `README.md:29` mermaid | **112** "streams Claude + 112 tools" | [README.md:29] | = registry count ✓ |
| 3 | `README.md:304` panel row | **112** "Ctrl+K palette over 112 tools" | [README.md:304] | = registry count ✓ |
| 4 | `README.md:313` | **111** on WebSocket path **+ 1** ported (`synapse_inspect_stage`, README:312) **+ 6** group-info | [README.md:312-313] | 111+1 = **112** ✓ reconciles; +6 group-info excluded |
| 5 | `README.md:477` (SCOUT→FORGE) | "Registry **104 → 108**" | [README.md:477] | historical milestone, superseded |
| 6 | `README.md:510` (Solaris Compose) | "Registry **108 → 111**" | [README.md:510] | historical milestone → 111 |
| 7 | Panel "Ctrl+K palette (110 tools)" | **110** | [MEMORY — synapse-panel-redesign.md] | stale memory note, not on disk this run |
| 8 | `_tool_registry.py` `TOOL_DEFS` | **112** (AST count) | [python\synapse\mcp\_tool_registry.py:124] | **AUTHORITATIVE** |

**`doctor.py` does NOT assert a tool count** — I grepped it; it reports `synapse.__version__` + protocol version + symbol-table stamp, no tool tally [python\synapse\server\doctor.py:82-90]. So the "six-way" framing resolves to: **the registry is 112, and the live banner/README/mermaid all now agree at 112.** The historical 104/108/111 are milestone breadcrumbs in README prose, and 110 is a stale memory note — not live contradictions.

**The real surviving DOC-1 gap is the opposite of an undercount — the stdio bridge advertises MORE than 112.** `mcp_server.py list_tools()` returns: the 112 registry tools, **+ 6** `_GROUP_INFO_TOOLS` (`synapse_group_{scene,render,usd,tops,memory,cops}`), **+ `synapse_inspect_stage`** (the Dispatcher-routed inspector, "tool #44"), **+ `synapse_scout`** (the cognitive Dispatcher's phantom-API grounding tool) — **= 120 tools advertised over stdio** [mcp_server.py:728-764, 768-775]. Neither `synapse_inspect_stage` nor `synapse_scout` is in the 112-entry registry [Bash probe: both "NOT in registry"]; they are appended by `list_tools()` and dispatched via dedicated branches in `call_tool()` [mcp_server.py:787-792], not via `TOOL_DISPATCH`. So "112 registered" is true of the registry but **undercounts the stdio surface by 8**, and the 6 group-info tools are the ones README:313 correctly carves out as "don't need porting."

### 1.5 PySide — **PySide6 primary, PySide2 fallback**

Confirmed convention (read 3 examples): every Qt import site tries PySide6 first, falls back to PySide2 in an `except ImportError`:
- `run_panel.py:103-109` — `from PySide6 import QtWidgets` → except → `from PySide2` [run_panel.py:103-109].
- `houdini\python_panels\synapse_panel.pypanel:51-53` — same order [grep].
- `audit_panel.py:114-116` — same order [grep].

**One stale outlier:** `houdini\scripts\python\synapse_shelf.py:22` imports `from PySide2 import QtWidgets` directly (no PySide6 attempt) [grep], and `design\synapse_styles.py:5` comments "Houdini uses PySide2/Qt5" [grep] — both lag the PySide6-primary convention. README and architecture docs state PySide6-primary [README.md:705, docs\architecture\overview.md:27]. `INVENTORY.md:262` still says "panel (PySide2, 5 tabs)" — stale [grep]. Matches the brief's "PySide6 with PySide2 fallback."

### 1.6 Cross-checks against the brief's pre-verified facts
- Repo version 5.14.0 — confirmed independently (§1.1).
- Registry = `python/synapse/mcp/_tool_registry.py`, 1373 lines — confirmed; `TOOL_DEFS` at :124, build loop at :1337-1352, last line 1373 [python\synapse\mcp\_tool_registry.py:1373].
- Vendored anthropic + stack under `_vendor/` — confirmed; ABI-locked to cp311-win_amd64 [python\synapse\__init__.py:34-57].

---

## §2 · TREE & MODULE MAP

### Banner drift (verified on disk — flag loud)

- **Python 3.14 is wrong.** `pyproject.toml` declares `requires-python = ">=3.9"` and classifiers cap at 3.11 [pyproject.toml:requires-python / `Python :: 3.9/3.10/3.11`]. CLAUDE.md banner's "Python 3.14" is unsupported by disk; matches the known hython/Houdini embed-py311 reality. **[CONFIRMED DRIFT]**
- **`VERSION` file says `5.8.0`** [VERSION:1] but `python/synapse/__init__.py` says `Version: 5.14.0` [python/synapse/__init__.py:19]. The package `__init__` and CLAUDE.md banner agree (5.14.0); the root `VERSION` file is stale. **[CONFLICT]**
- **No `python/synapse/transport/` package exists.** The recon prompt's "transport" target is absent [grep: `ls python/synapse/transport/` → No such file]. Transport concerns live in `python/synapse/host/transport.py` [path] and `python/synapse/server/websocket.py` / `hwebserver_adapter.py` [path]. CLAUDE.md §Agent-Roster lists `src/transport/` — that path does not exist either. **[ON-PAPER]**
- **`~/.synapse/agent-sdk/` does not exist.** Only `~/.synapse/agent/` exists (a separate, older standalone agent harness: `synapse_agent.py`, `synapse_planner.py`, `synapse_ws.py`, `synapse_hooks.py`, `synapse_tools.py`, `synapse_checkpoint.py`, `synapse_tone.py`) [path: `~/.synapse/agent/`]. The in-tree autonomy SDK is `python/synapse/autonomy/` + `python/synapse/host/` instead. **[DRIFT vs §3 brief]**
- **Tool count "112"** is a banner claim; on disk the registry is `TOOL_DEFS: list[tuple]` [python/synapse/mcp/_tool_registry.py:124], 1373 lines [path]. Exact count not derived here (tuples, not greppable `name=`); 110/112 figures float across docs — treat as approximate. **[approx]**

### Directory tree (2 levels, tracked files; vendor/.git skipped)

Top-level dirs [grep: `git ls-files`]: `.claude .github FORGE_PRODUCTION SYNAPSE-asm-{handler,routing,tests,ui} SYNAPSE-fx-{cluster,crawler,ingest} _solaris_fix agent agents assets design docs forge host houdini packages python rag scripts shared spikes synapse synapse_labs_extraction_kit tests`.

Note two parallel "synapse" trees: the real package `python/synapse/` AND a top-level `synapse/` (docs/forge/hooks/mcp/tests/validation) plus a legacy top-level `agent/`. The `shared/` dir holds the CLAUDE.md-blueprint files (`bridge.py`, `evolution.py`, `router.py`, `types.py`, `conductor_advisor.py`, `constants.py`) [path: shared/].

Root scripts of note [grep]: `mcp_server.py` (stdio MCP bridge), `mcp_tools_{cops,memory,render,scene,tops,usd}.py`, `run_panel.py`, `install.py`, `audit_panel.py`, `host/introspect_runtime.py` (Spike-2.5 symbol-table generator).

### `python/synapse/*` subpackages (216 tracked .py, excl vendor) [grep]

`agent autonomy cognitive core host inspector mcp memory panel routing science server session ui` (+ `_vendor`). No `transport/`.

### panel package layout [path: ls python/synapse/panel/]

Loader/entry: `synapse_panel.py` (49KB, the redesigned unified surface, `createInterface()` entry) [python/synapse/panel/synapse_panel.py:1-10]; `.pypanel` thin loader `synapse_chat.pypanel`; `__init__.py`.
Runtime: `claude_worker.py`, `tool_executor.py`, `tool_bridge.py`, `tool_filter.py`, `tool_palette.py`, `chat_panel.py`, `chat_display.py`, `message_formatter.py`, `ws_bridge.py`, `bridge_adapter.py`, `worker_policy.py`.
Faces (Pentagram redesign): `face_work.py`, `face_review.py` (Converse face is in `synapse_panel.py`).
Gates/consent: `gate_widget.py`, `gate_stamp.py`, `session_integrity.py`, `routing_log.py`.
Design: `designsystem/` (`tokens.py`, `qss.py`, `components.py`, `motion.py`, `loader.py`, `fontload.py`, `fonts/`), plus legacy `styles.py`, `tokens.py`, `system_prompt.py`.
Feature views: `apex_explainer.py`, `apex_recipes.py`, `apex_trace.py`, `vex_tutor.py`, `recipe_book.py`, `render_preflight.py`, `scene_doctor.py`, `network_trace.py`, `dependency_map.py`, `performance_profiler.py`, `error_translator.py`, `explain_mode.py`, `prompt_to_hda.py`, `hda_controller.py`, `hda_views.py`, `command_palette.py`, `context_bar.py`, `cross_scene.py`, `save_shot.py`, `shot_login.py`, `session_journal.py`, `bookmarks.py`, `quick_actions.py`, `health_infographic.py`, `agent_health.py`, `agent_prompts.py`, `image_prep.py`, `dnd.py`, `exposure_seam.py`.

### Key module map (one line each, from docstring) [path:line]

**cognitive/** — the in-process, zero-`hou` LLM brain.
- `agent_loop.py` — Anthropic Agent SDK turn runner; routes `hou.ObjectWasDeleted` → `AgentToolError` so the LLM rewrites instead of retrying stale pointers [agent_loop.py:1-9].
- `dispatcher.py` — single zero-`hou` entry point for tool calls; Strangler-Fig boundary driven by either embedded SDK or the WS adapter [dispatcher.py:1-11].

**server/** (40 files) — the live `/synapse` WS handler stack.
- `handlers.py` — registry-based command-handler router for the WS server [handlers.py:1-6].
- `websocket.py` — WebSocket server for AI↔Houdini, real-time bidir + resilience [websocket.py:1-6].
- `bridge_endpoint.py` — self-healing port discovery; server publishes real bound port to a sidecar JSON, clients resolve it (falls back to 9999) [bridge_endpoint.py:1-13].
- `freeze_chain.py` — process-wide freeze-safety chain (D3); moves freeze authority off `SynapseServer` because hwebserver has no resilience layer [freeze_chain.py:1-12].
- `resilience.py` — RateLimiter/CircuitBreaker/PortManager/Backpressure/Watchdog [resilience.py:1-13].
- `main_thread.py` — `run_on_main`: deferred (non-blocking) main-thread exec with timeout via `hdefereval.executeDeferred()` + Event, avoiding the blocking-deadlock variant [main_thread.py:1-11].
- Handler mixins: `handlers_{node,render,usd,cops,material,memory,hda}.py`, `handlers_solaris_{assemble,compose,graph}.py`, plus `solaris_compose*.py`, `render_{farm,notify,diagnostics}.py`, `auth.py`, `rbac.py`, `guards.py`, `doctor.py`, `telemetry_dump.py`, `metrics.py`/`live_metrics.py` [grep].

**mcp/** — the external `/mcp` (Streamable-HTTP) surface.
- `server.py` — MCP JSON-RPC 2.0 over Streamable HTTP via `@hwebserver.urlHandler("/mcp")`; runs inside Houdini [server.py:1-13].
- `_tool_registry.py` — canonical single-source tool registry; `TOOL_DEFS: list[tuple]` consumed by both stdio bridge and HTTP transport [_tool_registry.py:1-12, :124].
- `protocol.py` — MCP JSON-RPC 2.0 message/error utilities, MCP 2025-06-18 [protocol.py:1-8]. Plus `tools.py`, `resources.py`, `session.py`.

**routing/** — the tiered prompt router (the §2-routing target).
- `router.py` — tiered dispatcher; cascade Cache→Recipe→Tier0→Tier1→Tier2→Tier3 [router.py:1-11].
- `parser.py` — Tier-0 regex NL→`SynapseCommand`, no LLM, <1ms, first-match-wins [parser.py:1-10].
- `knowledge.py` — Tier-1 in-memory knowledge index (RAG metadata + refs + memory), no LLM, <500ms, degrades gracefully [knowledge.py:1-12].
- `planner.py` — composite-intent workflow planner ("set up X with Y and Z") between Recipe and Tier-0; emits a list of `SynapseCommand`s [planner.py:1-12]. Plus `adaptation.py`, `cache.py`, `context_enrichment.py`, `hda_recipes.py`, `vex_diagnostics.py`.

**memory/** (17 files) — project memory + evolution.
- `store.py` — JSONL/markdown memory store at `$HIP/.synapse/` (memory.jsonl + index.json + context/decisions/tasks.md) [store.py:1-13].
- `agent_state.py` — agent.usd v2.0.0 execution-state schema via `pxr.Usd/Sdf` [agent_state.py:1-11].
- `moneta_runtime.py` — import-guarded Moneta engine access; soft dependency, builds pxr-free `MockUsdTarget` handle [moneta_runtime.py:1-12]. `moneta_store.py` — single-store backend replacing JSONL divergence [moneta_store.py:1-5].
- `evolution.py` — markdown→USD charmander→charizard evolution, **deprecated**/superseded by Moneta sleep-pass [evolution.py:1-13]. Plus `sqlite_store.py`, `shadow_store.py`, `ledger.py`, `patterns.py`, `embedding.py`, `seed_corpus.py`, `vex_capture.py`, `backfill.py`, `scene_memory.py`, `context.py`, `markdown.py`, `models.py`.

**host/** — in-process Agent-SDK daemon (the real "agent-sdk").
- `daemon.py` — in-process host of the Claude Agent SDK; background thread inside graphical Houdini, marshals dispatches to main thread; Phase-1 lifecycle with empty loop, Phase-2 populates turns [daemon.py:1-13].
- `transport.py` — in-process synchronous `execute_python` transport matching `inspector.transport.TransportFn` [transport.py:1-13]. Plus `main_thread_executor.py`, `tops_bridge.py`, `scene_load_bridge.py`, `turn_handle.py`, `auth.py`, `dialog_suppression.py`.

**autonomy/** — Plan→Validate→Execute→Evaluate→Report loop.
- `driver.py` — Autonomous Driver orchestrating the full render loop with checkpoint/resume, decision logging, gate approval, and auto re-planning to `max_iterations` [driver.py:1-7]. Plus `planner.py`, `validator.py`, `evaluator.py`, `predictor.py`, `models.py`.

**science/** — gated hypothesis-search harness. `loop.py` (`run_search`) [loop.py:1-13], `registry.py` (frozen `Record` champion/dead_end) [registry.py:1-13], plus `probe.py`, `registry.py`, `rungs.py`, `allocation.py`, `exposure.py`, `apex_probes.py`, `verified_claim.py`.

**core/** — neutral cross-cutting primitives. `gates.py` — `HumanGate` INFORM/REVIEW/APPROVE/CRITICAL [gates.py:1-12]; `floor_gate.py` — Tier-0 provenance hook both registries funnel through, lives in `core` to avoid a cognitive→server cycle [floor_gate.py:1-11]. Plus `aliases.py`, `audit.py`, `crypto.py`, `determinism.py`, `errors.py`, `logfile.py`, `protocol.py`, `queue.py`, `show_config.py`, `timeouts.py`.

**designsystem/** (under panel) — `tokens.py` is the single vendored token SoT reconciling the three divergent token sources the audit found (`design/tokens.py`, `~/.synapse/design`, `panel/tokens.py`), stdlib-only [panel/designsystem/tokens.py:1-12]. 13 designsystem files tracked [grep].

**Other in-package:** `inspector/` (scene-memory subsystem reading `/stage`) [inspector/__init__.py:1-6]; `session/` (tracking + summaries) [session/__init__.py:1-5]; `ui/` (Qt panel) [ui/__init__.py:1-4]; `agent/` (in-package agentic protocol: `executor.py`, `learning.py`, `sparse_router.py`, `task_synthesizer.py`, `specialist_modes.py`, `reasoning_context.py`) [agent/__init__.py:1-7].

---

## §3 · THE PANEL LAYER

**TL;DR — the single most load-bearing correction:** there are **two parallel panels** on disk, and the one Houdini actually registers is the **v9 face-based** `synapse_panel.py::SynapsePanel`, *not* the chat-stack `chat_panel.py::SynapseChatPanel`. The v9 re-layout's ground truth lives in `synapse_panel.py` + `panel/designsystem/`. The class names in the brief are mostly right but two are wrong (`MarkDat`→`MarkDot`; the panel class) and the face structure is **2 faces, not 3** (Review is a Work sub-state).

---

### 3.1 Registered entry point — which panel is LIVE

- The Houdini-registered panel is `houdini/python_panels/synapse_panel.pypanel` [path:/c/Users/User/SYNAPSE/houdini/python_panels/synapse_panel.pypanel:8]. Its loader calls `from synapse.panel.synapse_panel import onCreateInterface` and Houdini's `onCreateInterface()` entry (with `createInterface` alias) [synapse_panel.pypanel:41-61]. This is the **v9 redesigned panel** = `synapse_panel.py::SynapsePanel` [python/synapse/panel/synapse_panel.py:157].
- A **second** `.pypanel` exists *inside the package dir* (not the registered houdini dir): `python/synapse/panel/synapse_chat.pypanel`, which loads `from synapse.panel.chat_panel import SynapseChatPanel` via `createInterface()` [synapse_chat.pypanel:31-38]. This is the **older chat-mode-stack panel** [chat_panel.py:130]. [ASSUMED] it is legacy/superseded by the v9 panel — both are present on disk, only the v9 one sits in `houdini/python_panels/`.
- A **third** `SynapsePanel` exists at `python/synapse/ui/panel.py:47` (with `NexusPanel = SynapsePanel` alias :364), exported via `synapse.ui` / `synapse.__init__` [grep]. This is the legacy `synapse.ui` panel, distinct from the v9 `synapse.panel.synapse_panel.SynapsePanel`. **Name collision: `SynapsePanel` resolves to two different classes** depending on import path.

### 3.2 Class registry — confirmed/corrected names + files

| Brief name | Real name on disk | File:line | Role (one line) |
|---|---|---|---|
| ChatDisplay | **ChatDisplay** ✓ | `chat_display.py:39` | Read-only `QTextBrowser` rich-text chat transcript (code blocks, clickable node links, typing dots, font scaling) [chat_display.py:39-50] |
| GateWidget | **GateWidget** ✓ | `gate_widget.py:286` | Collapsible consent-gate proposal cards + integrity bar; thread-safe relays `_proposal_received`/`_decision_made`, public `decision_announced(operation,decision,level)` [gate_widget.py:286-299] |
| MarkDat | **MarkDot** ✗ (renamed) | `designsystem/components.py:128` | The SYNAPSE mark IS the status light — ring at rest, sweep while working, full disc done; single WARM note [components.py:128-135]. **No class named `MarkDat` exists** [grep]. (Markdown rendering is *not* a class — it's `message_formatter.py` helpers + `dnd.transcript_to_markdown` [dnd.py:101].) |
| ClaudeWorker | **ClaudeWorker** ✓ | `claude_worker.py:52` | `QThread` background worker; streams Claude API w/ tool-use loop; signals `token_received`/`stream_done`/`stream_error`/`tool_requested`/`tool_status` [claude_worker.py:52-67] |
| ToolExecutor | **ToolExecutor** ✓ | `tool_executor.py:218` | `QObject` that runs Synapse tool calls on Houdini's **main thread** (worker emits → AutoConnection slot) [tool_executor.py:218-224] |
| HealthInfographic | **HealthInfographic** ✓ | `health_infographic.py:52` | Compact painted observability chart; `set_data(health)` [health_infographic.py:52-53] |
| context bar / rail | **ContextChips** (chat panel) / `_build_rail` + `_build_context_ribbon` (v9) | `context_bar.py:588`; `synapse_panel.py:256,322` | Chat panel uses `ContextChips` [context_bar.py:588, imported chat_panel.py:39]; v9 panel builds its own persistent **rail** (`MarkDot`+wordmark+Stop) and a separate **context ribbon** [synapse_panel.py:256-329] |

The v9 panel composes the live runtime classes: it imports `ClaudeWorker` [synapse_panel.py:41], `ToolExecutor` [:45], `HealthInfographic` [:53], and `ChatDisplay` [:33] — each guarded (`= None` on ImportError) [synapse_panel.py:41-56]. So `ChatDisplay` is shared by **both** panels.

### 3.3 v9 main panel — `_build_ui`, faces, switching [synapse_panel.py]

- `SynapsePanel(QtWidgets.QWidget)` [synapse_panel.py:157]; `_build_ui` builds rail → divider → context ribbon → mode-bar → **the faces** [synapse_panel.py:241-254].
- **Faces are a `QStackedWidget`** built in `_build_faces` [synapse_panel.py:375-386]: it adds exactly **two** widgets — `_build_direct_face()` (index 0, idle/converse) and `_build_work_face()` (index 1) [:380-381].
- **The face map is `_FACE_INDEX = {"direct": 0, "work": 1}` — TWO faces, NOT three** [synapse_panel.py:355]. **There is no top-level "Review" face.** "Review" = the **`done` sub-state of the Work face**: `_build_work_face` holds an *inner* `QStackedWidget` (`_work_stack`) with `cook` (=`FaceWork`, index 0) and `done` (=`FaceReview`, via `_build_done_substate`, index 1) [synapse_panel.py:414-435].
- **Switching:** user pills only — `_set_face(face)` calls `self._faces.setCurrentIndex(self._FACE_INDEX[face])` [synapse_panel.py:574-582]; pills wired in `_build_mode_bar` (`pill.clicked → _set_face(f)`) [:357-371]. The Work sub-state switches via `setCurrentIndex(1 if state=='done' else 0)` [:471], driven by busy edges in `_set_busy` — **NO auto tab-switch** ("same-pane law"); the rail MarkDot is the only ready-result signal [synapse_panel.py:984-995].
- `FaceWork` [face_work.py:149] and `FaceReview` [face_review.py:201] are real widget classes, imported guarded [synapse_panel.py:59-65]; the gate lives on `FaceReview.gate` [synapse_panel.py:446].

### 3.4 Design system — TWO token sources (the trap)

There are **two `tokens.py` files**, and panel modules split between them:
- **`panel/designsystem/tokens.py`** — the **vendored single source of truth** [tokens header:1-13]. Used by the v9 panel: `from synapse.panel.designsystem import tokens as t` [synapse_panel.py:23], and by `health_infographic.py:21`, `fontload.py:23` (`from . import tokens`).
- **`panel/tokens.py`** — re-exports from the **external** `~/.synapse/design/tokens.py` with a hard-coded fallback [tokens.py:13-67]. Used by the chat panel + chat widgets: `from synapse.panel import tokens as t` [chat_panel.py:62, chat_display.py:24, quick_actions.py:101].

**designsystem/tokens.py — the values the v9 panel actually renders:**
- Accent / SIGNAL = `#8FB3D9` (muted light blue) [designsystem/tokens.py:22]. *(The OTHER token source, `panel/tokens.py`, has the OLD `SIGNAL="#00D4FF"` cyan in its fallback [panel/tokens.py:39], matching external `~/.synapse/design/tokens.py:21` = `#00D4FF` [grep].)*
- Text ramp (note: names are `TEXT_*`, not bare `PRIMARY/SECONDARY/...`): `TEXT_PRIMARY=#ADADAD` (body), `TEXT_SECONDARY=#8A8A8A`, `TEXT_TERTIARY=#7E7E7E`, `TEXT_BRIGHT=#C4C4C4`, `TEXT_ACCENT=SIGNAL`, `TEXT_DISABLED=#5A5A5A`, `TEXT_ON_ACCENT=#13212C` [designsystem/tokens.py:70-76].
- BODY type role: `("body": FONT_SANS_CSS, SIZE_BODY=13, weight 400, 0.0)` [designsystem/tokens.py:134,145]. Sizes: MICRO 13, SMALL 14, UI 20, BODY 13, TITLE 22, HERO 30 [:131-136]. (The `panel/tokens.py` fallback carries the **bug-prone 22-44** scale [panel/tokens.py:54-59].)
- Surface elevation: GROUND `#262626`, FIELD_INSET `#1E1E1E`, PANEL `#2E2E2E`, SURFACE `#3A3A3A`, RAISED `#565656`, BORDER `#262626`, BORDER_STRONG `#4C4C4C` [designsystem/tokens.py:47-56]. Status colors FIRE `#FF6B35`, GROW `#00E676`, WARN `#FFAB00`, ERROR `#FF3D71`, WARM `#FF7759` [:32-35,96].

**Fonts — ACTUALLY bundled:**
- `QFontDatabase.addApplicationFont` **is present**: `fontload.load_application_fonts()` calls `QtGui.QFontDatabase.addApplicationFont(path)` per file [designsystem/fontload.py:57]; the v9 panel calls it before applying the stylesheet [synapse_panel.py:167].
- `.ttf` files **are physically in the repo** [glob `designsystem/fonts/*.ttf`]: `SpaceGrotesk-Variable.ttf` (137KB), `SpaceMono-Regular.ttf` (99KB), `SpaceMono-Bold.ttf` (98KB) [designsystem/fonts/]. Expected families `("Space Grotesk","Space Mono")` [fontload.py:27]; missing-family sets `build_mismatch=True` and falls back to `FONT_*_FALLBACKS` [fontload.py:65-85]. `.qss` is generated by `designsystem/qss.py` (`qss.stylesheet(...)` [synapse_panel.py:171]).

### 3.5 Quick-action row + Stop button

**v9 panel (the registered one) — corrected labels:**
- Quick actions defined at module level: `_QUICK_ACTIONS = [("Explain", …), ("Fix", …), ("Optimize", …)]` [synapse_panel.py:72-75]. Rendered uppercased in `_build_act` via `self._verb(label.upper(), …→ self._send(prompt))` [synapse_panel.py:646-648]. **`BUILD HDA` is a SEPARATE 4th verb** — demoted from a former top-level face into a Direct-surface verb that calls `_set_direct_view("hda")` [synapse_panel.py:649-651]. So the live row is **EXPLAIN / FIX / OPTIMIZE / BUILD HDA** ✓ (matches brief) — plus `Aa` font-scale and `⌘K` palette verbs [:653-659].
- **Stop button:** `self._stop_btn = c.Button("Stop", variant="danger")` built in the **rail** [synapse_panel.py:309-313]; wired `clicked.connect(self._on_stop)` [:311]; starts disabled+hidden, **state-gated to "working" only** [:312-313, 984]. `_on_stop` calls `self._worker.abort()` and sets header to "Stopping…" — **honest/cooperative abort, does NOT claim idle** [synapse_panel.py:968-979]. (In-flight tool cancel — `tops_cancel_cook`/render cancel — is explicitly **deferred to the bridge-live pass** [synapse_panel.py:973-975].)

**Old chat panel (`chat_panel.py`) — for contrast:** quick actions are `Explain / Make HDA / Fix Error / Optimize / VEX Help` [quick_actions.py:14-62] (note "**Make HDA**", not "BUILD HDA"); its terminate button is labeled **"HALT"** (`self._halt_btn = QtWidgets.QPushButton("HALT")` → `_on_emergency_halt`) and emits `emergency_halt` over WS [chat_panel.py:591-596, 936-941].

### 3.6 Panel-layer maintenance liabilities (for the v9 re-layout)
1. **Dual token sources** [designsystem/tokens.py vs panel/tokens.py] — same names, different values (SIGNAL `#8FB3D9` vs `#00D4FF`; BODY 13 vs 26; UI scale 9-20 vs 22-44). The v9 panel and the chat panel render with *different* palettes/sizes. Any "fix the accent color" edit must target the *right* file or silently miss.
2. **Two live panels + a third `SynapsePanel` name** [synapse_panel.py:157, chat_panel.py:130, ui/panel.py:47] — `SynapsePanel` is ambiguous by import path.
3. **`panel/tokens.py` depends on an OFF-REPO path** `~/.synapse/design/tokens.py` [panel/tokens.py:13-15] — not in the repo, so its true live values aren't reproducible from a clean checkout; the in-file fallback (#00D4FF / 22-44) is what ships if that dir is absent.

---

## §4 · SAME-PANE PROBE (static — Spike 1 target)

**Verdict: Same-pane TAB switching IS wired today — but ONLY to a user pill click + an idle default. NO agent-state / busy / gate path ever switches the visible tab. And there is NO Houdini floating-panel / pane creation or pane-switching anywhere in the panel package — every `hou.ui.*` pane call is read-only network-editor introspection.** The "same-pane law" (artist-only tab moves; agent state drives a *sub-state* + rail mark) is implemented, not just documented.

### A. The two distinct switching layers (don't conflate them)

There are two unrelated meanings of "switch" in this package, and the Spike-1 question only concerns the first:

1. **Top-level FACE/TAB switch** — `QStackedWidget` `self._faces` with `_FACE_INDEX = {"direct":0,"work":1}` [synapse_panel.py:355,379]. The switch method is `_set_face(face, manual=True)` → `self._faces.setCurrentIndex(self._FACE_INDEX[face])` [synapse_panel.py:574,581].
2. **In-widget Qt sub-stacking** — `QStackedWidget.setCurrentIndex` / `QListWidget.setCurrentRow` / `QComboBox.setCurrentText` used to flip *content within* a tab. These are NOT Houdini panes and NOT top-level tab switches.

### B. Top-level tab switch — IS on a click handler, and ONLY a click handler

- **Caller 1 (click handler):** Each mode pill's `clicked` signal is bound to `_set_face`: `pill.clicked.connect(lambda _=False, f=face: self._set_face(f))` inside `_build_mode_bar` [synapse_panel.py:369]. The pills are "Direct" / "Work" [synapse_panel.py:366]. This is the literal Spike-1 target: a same-pane tab switch sitting on a button/tab activate handler. [path:synapse_panel.py:357-372]
- **Caller 2 (idle default, not a handler):** `self._set_face("direct")` called once during construction as the resting face [synapse_panel.py:254].
- **Caller 3 (indirect, via Direct's inner view):** `_set_direct_view(view)` ends with `self._set_face("direct")` [synapse_panel.py:566-571]; `_set_direct_view` is itself reached from the "BUILD HDA" overflow action `lambda _=False: self._set_direct_view("hda")` [synapse_panel.py:651] and from `_build_direct_face`'s default `self._set_direct_view("chat")` [synapse_panel.py:594]. So the only *user-driven* entry is the BUILD HDA menu action — still an activate handler, and it only ever forces Direct forward (never Work).
- **The contract is explicit in code, not just docs:** `_set_face` docstring — *"The *only* caller is a user pill click (and the explicit idle default); agent state never calls this"* [synapse_panel.py:574-578]; `_build_mode_bar` docstring — *"A pill click is the *only* thing that moves the visible tab — agent state never does (the same-pane law)"* [synapse_panel.py:358-360]; `_build_faces` — *"The controller never auto-switches between them"* [synapse_panel.py:378].

### C. Agent state drives a SUB-state, never the top-level tab — confirmed

The busy/gate/result machinery calls `_set_work_substate` (a sub-`QStackedWidget` `self._work_stack`, cook=0 / done=1 [synapse_panel.py:414,435,471]), never `_set_face`:
- `_set_busy` rising edge → `_set_work_substate("cook")`; falling edge → `_populate_review()` + `_set_work_substate("done")` [synapse_panel.py:993-999], with the inline comment *"state→Work-sub-state edges (NO tab switch — the same-pane law)… the RAIL MARK is the only ready-result signal"* [synapse_panel.py:988-992].
- `_on_gate_raised` (gate proposal arrived) → `_set_work_substate("done")` + header, docstring *"we never auto-switch the visible tab"* [synapse_panel.py:722-734].
- `_on_commit` → `_set_work_substate("done")`, *"never spawn or switch tabs"* [synapse_panel.py:520-530].
- `_set_work_substate` docstring itself: *"A content update WITHIN the Work tab — never a top-level tab switch (the same-pane law)"* [synapse_panel.py:464-467].

### D. Houdini pane creation / floating-panel / pane-switching — NONE in the package

Searched the panel package for `createFloatingPanel`, `createTab`, `findPaneTab`, `currentPaneTabs`, `floatingPanels`, `createPane`, `setCurrentTab` → **zero matches** [grep, python/synapse/panel]. Every `hou.ui.*` pane call present is **read-only network-editor introspection**, none on a switch path:
- `dnd.py:83` — `for pane in hou.ui.paneTabs()` inside the results-OUT node-placement helper; finds the active Network Editor to *place/select* a node, comment confirms *"network editor is native C++ (no Qt drop)… GUI-only"* [path:dnd.py:70-98].
- `context_bar.py:237` — `hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)` to *read* `editor.pwd().path()` for the breadcrumb/context bar [path:context_bar.py:235-243].
- `chat_panel.py:917` — inside `_on_node_clicked` (this IS a click handler): finds the Network Editor and calls `setCurrentNode` + `homeToSelection` to *navigate to a node in the existing pane* — it does **not** create or switch a pane [path:chat_panel.py:907-924].
- `network_trace.py:280`, `performance_profiler.py:234`, `scene_doctor.py:80`, `ws_bridge.py:69`, `synapse_panel.py:849` — all read the current Network Editor's `pwd()` to resolve a network path / build context. Read-only. [path:network_trace.py:280] [path:performance_profiler.py:234] [path:scene_doctor.py:80] [path:ws_bridge.py:69] [path:synapse_panel.py:849]
- `synapse_panel.py:1047-1077` — `_register_selection_cb` / `closeEvent` feature-detect `hou.ui.addSelectionCallback` / `removeSelectionCallback` to refresh a context line on selection change; pure read, with explicit headless-safe feature-detect [path:synapse_panel.py:1046-1080].

### E. In-widget Qt sub-stacking hits (NOT Houdini panes — listed for completeness)

These move content within a widget; none are pane operations:
- `command_palette.py:519,545` `setCurrentRow` (list nav) [grep]; `tool_palette.py:273,315` `setCurrentRow` (list nav) [grep]; `hda_views.py:78,127` `setCurrentText("SOP")` (combo default) [grep]; `chat_panel.py:710` `self._hda_stack.setCurrentIndex(0)` (HDA sub-stack) [grep]; `styles.py:681` `stacked_widget.setCurrentIndex(new_index)` — a generic opacity-fade `QStackedWidget` switch helper [path:styles.py:668-687]; `synapse_panel.py:570` `_converse_stack.setCurrentIndex` (Direct chat↔HDA inner view) [synapse_panel.py:566-571].

### F. Bottom line for Spike 1

Same-pane switching is wired and lives entirely in `synapse_panel.py`. The single user activate-handler that performs a top-level tab switch is the mode-bar pill click → `_set_face` [synapse_panel.py:369→574]. Everything agent-driven is deliberately routed to the Work *sub-state* + rail mark instead. There is no floating-panel/pane spawning to retrofit and no agent-side auto-switch to suppress — the architecture already enforces the same-pane invariant in code, pinned by the docstrings at [synapse_panel.py:358,378,464,574,722,988].

---

## §5 · SUBSTRATE & TRANSPORT

### 5.1 Transport topology — three server modules, one shared handler, zero bridge

There are **three** distinct server transports in `python/synapse/server/`, all converging on the **same** `SynapseHandler.handle()`:

| Transport | Module | Mechanism | Live? |
|---|---|---|---|
| **WS (pure-Python)** | `websocket.py` `SynapseServer` [websocket.py:93] | `websockets.sync.server.serve` on `:9999`, background thread, no asyncio (avoids Houdini's `haio.py`) [websocket.py:18,300-316] | testing/CI + fallback |
| **hwebserver WS (C++)** | `hwebserver_adapter.py` [hwebserver_adapter.py:1-20] | Houdini-native `hwebserver` module, `SynapseWS.receive()` → `SynapseHandler.handle()` [hwebserver_adapter.py:13-19,40,56] | **production inside Houdini** |
| **hwebserver HTTP /api** | `api_adapter.py` [api_adapter.py:1-13] | `@hwebserver.apiFunction("synapse")` HTTP-POST endpoints, hand-written per-command [api_adapter.py:113-435] | alt external path |

All three are `async`-free at the handler boundary — the only `async def` in the server tree is absent; the pure-Python WS server explicitly chose **sync** serve to dodge Houdini's asyncio [websocket.py:301]. The MCP client (`mcp_server.py`) is the only async actor; it connects out as a WS *client* to `ws://localhost:9999/synapse` [mcp_server.py:147,289-303]. [path:line]

The MCP client's `PROTOCOL_VERSION = "5.4.0"` [mcp_server.py:182] — note this is the *client* protocol string, distinct from the package version `v5.14.0` in the CLAUDE.md banner.

### 5.2 `hou.undos.group()` call-site count: **43**, all live-path

`grep -rc "hou.undos.group"` across `python/` + `shared/` = **43 total** [grep]. Distribution proves the undo-wrapping lives in the **hand-wired live handler layer**, NOT the bridge:

- `handlers_cops.py`:17 · `handlers_usd.py`:10 · `handlers_material.py`:3 · `handlers_solaris_compose.py`:3 · `handlers.py`:2 · `handlers_hda.py`:2 · `handlers_render.py`:2 · `handlers_solaris_graph.py`:1 · `handlers_tops/render_sequence.py`:1 · `solaris_compose.py`:1 · `panel/scene_doctor.py`:1 → **41 in the server/handler layer** [grep]
- `shared/bridge.py`:**2** — the bridge's own envelope [grep]

So 41/43 undo groups are inline in the live `server.handlers` path; the bridge owns only 2. This is the "parallel, hand-wired mechanism" the CLAUDE.md §1 live-path note describes — **confirmed on disk**. [grep]

### 5.3 `LosslessExecutionBridge` — defined in `shared/`, NOT called by any live transport

Defined in **`shared/bridge.py`** [grep]. Referenced in **92** lines across **23 files** [grep], but the non-test callers are exclusively the **panel** and tooling, never the WS/hwebserver transports:

- **`python/synapse/panel/bridge_adapter.py`** is the only production wrapper: `get_bridge()` constructs a singleton `LosslessExecutionBridge(consent_callback=_panel_consent)` [bridge_adapter.py:191-201], `execute_through_bridge()` wraps `handler.handle()` [bridge_adapter.py:2,213-219]. This is the **Houdini panel's** in-process path, not the WS server.
- `panel/agent_health.py`, `shared/conductor_advisor.py`, `scripts/freeze_trace.py` reference it for stats/observability.

**Trace of the live WS path** (`websocket.py` → handler):
`_handle_message` [websocket.py:562] → `self._handler.handle(command)` [websocket.py:674] → `handle()` [handlers.py:349] → `self._registry.invoke(cmd_type, payload, ctx=FloorContext(origin="handler"))` [handlers.py:386-389] → `CommandHandlerRegistry.invoke()` → `FloorGate.wrap(...)` [handlers.py:275] → the bound handler. **`LosslessExecutionBridge` appears nowhere in this chain.** `grep -rn "import.*bridge"` in `server/` returns only `from ..session.tracker import get_bridge` [websocket.py:64, handlers.py:345, hwebserver_adapter.py:58, api_adapter.py:56] — that is the **session/memory tracker bridge**, an unrelated `SessionBridge`, NOT `LosslessExecutionBridge`. [path:line]

**Plain statement: the live WS transport calls the handlers directly and never routes through `LosslessExecutionBridge`. The bridge is a panel/audit-layer artifact.** This confirms the CLAUDE.md §1 / §11.2 live-path reality note against disk. [path:line]

The only server-side touch of the bridge is `freeze_chain.py:163` `from shared.bridge import EmergencyProtocol` — and it only fires `if bridge is not None` [freeze_chain.py:160-161], with the code's own comment stating "No ACTIVE bridge — emergency halt skipped (escalation never constructs one)" [freeze_chain.py:172-173]. So on the live transport the emergency halt is **effectively a no-op** unless a panel bridge happens to be live. [path:line]

### 5.4 `execute_python` posture — UNGATED, full `__builtins__`, no consent, no length cap

**WS/hwebserver path** — `_handle_execute_python` [handlers.py:998]:
- Namespace: `exec_globals = {"hou": hou, "__builtins__": __builtins__}` [handlers.py:1028] — **full builtins, no import filter** [path:line].
- **No consent gate.** The only wrapper is `FloorGate`, and FloorGate's own docstring states it is "**Tier-0 only … provenance, not admission control. No halting, no consent gating**" [floor_gate.py:19-20]. [path:line]
- **No length cap** — `code` is taken verbatim from payload [handlers.py:1012], `compile()`d [handlers.py:1018], run. No `len(code)` check anywhere in the handler [path:line].
- Only safety: optional `atomic` (default True) wraps in `hou.undos.group("synapse_execute")` with smart rollback on coding-bug errors [handlers.py:1044-1062], and a 30s `_SLOW_TIMEOUT` main-thread marshal [handlers.py:1036,1074]. `gate_level`=CRITICAL from the bridge §1.2 table is **irrelevant here** — this path never sees the bridge.

**HTTP /api path** — `api_adapter.py:298` is even barer: `{"hou": hou, "__builtins__": __builtins__}` [api_adapter.py:306], `compile()` + `_run_in_namespace`, **no `atomic` flag, no undo group at all** [api_adapter.py:309-311]. [path:line]

`execute_python`/`execute_vex` are NOT in `_READ_ONLY_COMMANDS` [handlers.py:183-213] — so they take the C5 cross-client mutation lock [handlers.py:380-386] — but that is concurrency serialization, **not** a consent or capability gate. This matches the CLAUDE.md §1.2 live-path note (ungated, single-user-localhost auto-approve) — **confirmed on disk, [NOT RUN] live**. [path:line]

### 5.5 `memory.jsonl` — hot-path append is NOT atomic; only full-rewrite is

Path: `self.memory_file = self.storage_dir / "memory.jsonl"` [store.py:169] (writer: `python/synapse/memory/store.py`). [grep][path:line]

**Two write paths, asymmetric durability:**
- **Hot `add()` path → plain append.** `add()` buffers lines [store.py:518]; a background flusher thread drains via `with open(self.memory_file, 'a', encoding='utf-8') as f: f.write(...)` [store.py:260-261] — **plain `open('a')`, no tmp, no fsync, no os.replace, no per-write backup**. On failure it restores lines to the buffer [store.py:262-266] but the append itself is non-atomic. This is the common-case write. [path:line]
- **Rewrite `save()` path → atomic.** Triggered only by update/delete (`_needs_rewrite`) [store.py:242-248]; routes through `write_report(..., backups=1)` which the comment documents as "Atomic (tmp + fsync + os.replace) with one generational .bak" [store.py:480-483]. [path:line]

**C1-C3 answer: the answer is BOTH, split by path** — the durable tmp+fsync+os.replace+`.bak` story (C1/C3) holds for full rewrites, but the **hot append path is a plain `open('a')`** with no atomicity and no backup. A crash mid-flush can leave a torn final line. (Mitigations present: `_degraded_load` refuses truncating save on bad decrypt [store.py:186-189]; load tolerates malformed lines best-effort per the JSONL design [store.py:8].) [path:line]

### 5.6 `synapse_scout` wiring — present, registered via cognitive Dispatcher (NOT the tool registry)

Wired in **`mcp_server.py`**, on a **dedicated `call_tool` branch**, parallel to the Inspector — **not** through `TOOL_DISPATCH`/`_tool_registry.py`:

- Imported from `synapse.cognitive.tools.scout` [mcp_server.py:642-647].
- `_get_scout_dispatcher()` builds a `Dispatcher(is_testing=True, tools={"synapse_scout": _scout_tool}, schemas=...)` [mcp_server.py:686-691] — same cognitive `synapse.cognitive.dispatcher.Dispatcher` the Inspector uses [mcp_server.py:472-475].
- On first build it materializes the corpus from the repo `rag/` via `scout_ingest.ensure_corpus()` and repoints `_scout_module.RAG_ROOT`/`VEX_ROOT` at it [mcp_server.py:664-668] — the "never serve the thin `G:\` store" behavior.
- It stamps `EXPECTED_HOUDINI_VERSION = hou.applicationVersionString()` **only when `hou` is importable** (host side) [mcp_server.py:677-680]; the MCP server runs zero-`hou`, so this pin is typically **unset** there — the symbol-table integrity check still runs, just without a version pin [mcp_server.py:680].
- Listed in `list_tools()` [mcp_server.py:758-762], dispatched in `call_tool()` via `if name == _SCOUT_TOOL_NAME: return await _scout_call_tool(...)` [mcp_server.py:791-792], run off-loop via `asyncio.to_thread` [mcp_server.py:704]. [path:line]

**Membership authority** = the committed introspected symbol table `python/synapse/cognitive/tools/data/h21_symbol_table.json` (1.2MB, schema `scout_symbol_table/v1`, **`houdini_version: "21.0.671"`**, `symbol_count: 33255`, `truncated: false`) [table]. `scout.py` loads it via `_load_symbol_table()` and emits `exists_in_runtime = (sym in table_syms) if table_syms is not None else None` [scout.py:431-475] — exactly the §11.15 `dir()`-as-gate contract. A version mismatch vs `EXPECTED_HOUDINI_VERSION` marks the table **stale** [scout.py:444-448]. [path:line][table]

### 5.7 Seams & the biggest maintenance liabilities

1. **`__builtins__`-wide `exec` on the live path, no length cap — duplicated in 2 transports.** `handlers.py:1028` and `api_adapter.py:306` each independently build `{"hou":hou,"__builtins__":__builtins__}`. Two copies of the most dangerous primitive, neither gated. The §1.2 CRITICAL gate exists only on the bridge, which the live path never touches. **Top liability.** [path:line]

2. **The bridge↔live-path schism is structural, not a flag.** 41/43 undo groups are inline in handlers; the bridge's 4 anchors (consent, integrity, blast-radius, async PDG) apply **only** to the panel `bridge_adapter.py` path. Anyone reading CLAUDE.md §1 as "every mutation flows through the bridge" is wrong against disk — the doc's own live-path notes are the correct reading. Maintenance risk: two parallel safety mechanisms that must be kept in sync by hand. [path:line]

3. **Emergency halt is dead on the live transport.** `freeze_chain.py:160-173` only halts if a bridge is *already* active, and "escalation never constructs one" — the hwebserver stack has no resilience layer at all (`freeze_chain.py:156-158`). The kill switch is reachable only when the panel bridge happens to be live. [path:line]

4. **`memory.jsonl` hot append is non-atomic** (`store.py:260`) while the surrounding code/docs advertise tmp+fsync+os.replace durability — the atomic story is true only for the rare rewrite path. Torn-line risk on crash during the 2s/50-item background flush. [path:line]

5. **Scout's runtime-version pin silently no-ops in the MCP server** (`mcp_server.py:677-680`): the version-staleness guard depends on `hou`, which is absent there, so a symbol table built for a *different* Houdini build would still be trusted by the zero-`hou` MCP process (integrity hash checked, version not). The table on disk is `21.0.671` [table] — matches the graphical build, but nothing in the MCP path enforces that match. [path:line][table]

### 5.8 Banner-drift confirmation (Python version)

The symbol table records `houdini_version: 21.0.671` [table]. The CLAUDE.md banner claims **"Houdini 21.0.631 · Python 3.14 · 112 MCP tools"**. On disk: (a) the live introspected runtime authority says **21.0.671**, not 631 [table]; (b) I found **no on-disk evidence for Python 3.14** — H21 embeds CPython 3.11 (the known `python311` embed), and the repo's own memory notes flag this as banner drift. The "3.14" claim is **[NOT RUN] / unconfirmed on disk** and contradicts the H21 embed. Tool count (112) was not re-counted in this section (it belongs to the registry section). [table][ASSUMED for the 3.11 embed — not directly read this run]

---

## §6 · HARNESSES & DOCS ON DISK

Method: `git ls-files '*.md'` + `ls docs/` + `git status --porcelain` + targeted globs. Disk wins; tracked-vs-untracked is from `git status`.

### 6.A Specific-resolution table (the names the brief asked me to settle)

| Asked-for name | Verdict | Evidence |
|---|---|---|
| `FIELD_READINESS*` | **NEVER EXISTED as a file.** No disk match, no `git ls-files` match `[grep]`. The *phrase* lives only as the H1 title of the 3xs harness: `# SYNAPSE — FIELD-READINESS / HARDENING HARNESS` `[docs/SYNAPSE_3xs_HARDENING_HARNESS.md:1]`. "Field-readiness" is the lens, not a filename. |
| `*3xs_HARDENING* / *3XS*` | **EXISTS but UNTRACKED.** Exactly one: `docs/SYNAPSE_3xs_HARDENING_HARNESS.md` (20026 bytes, mtime Jun 14 16:23 — today). `git status` shows `?? docs/SYNAPSE_3xs_HARDENING_HARNESS.md` `[grep]`; `git ls-files '*3xs*' '*3XS*'` returns nothing `[grep]`; `git log --all` on the path returns no history `[grep]`. New, never committed. Self-describes as "ARCHITECT artifact. Design only, no implementation. Pre-FORGE" and reframes the Science Harness v3→v4→v5 under a facility-trust lens `[docs/SYNAPSE_3xs_HARDENING_HARNESS.md:5-7]`. Note the lowercase `3xs` (not `3XS`); the `*3XS*` pattern matches nothing `[grep]`. |
| `*CTO_REMEDIATION*` | **EXISTS, TRACKED.** `docs/SYNAPSE_CTO_REMEDIATION_HARNESS_v1.md` (16010 bytes, Jun 9). Tracked per `git ls-files` `[grep]`. Only `v1` exists. |
| `SCIENCE_HARNESS*` versions | **base + v3 + v4 + v5 exist; NO `_v1` / `_v2` file ever.** All tracked `[grep]`: `docs/SYNAPSE_SCIENCE_HARNESS.md` (base, Jun 2), `_v3.md` (Jun 5), `_v4.md` (Jun 5), `_v5.md` (Jun 8). `ls docs/*SCIENCE_HARNESS_v1*` / `*_v2*` → "no _v1 / _v2 files" `[grep]`. So the version line is **base, (gap), v3, v4, v5** — v1/v2 were folded into the unsuffixed base doc, never separate files. Plus two siblings: `SCIENCE_HARNESS_LEDGER.md` (83997 bytes — the live ledger, Jun 9) and `SCIENCE_HARNESS_PHASE0A_SPEC.md` (Jun 2), both tracked `[grep]`. |

### 6.B Harness / design docs at repo root

All tracked `[grep]`: `CLAUDE.md` (42620 B, Jun 11), `README.md` (68193 B, Jun 11), `DEMO_SCRIPT.md`, `INVENTORY.md`, `LATENCY_PLAN.md` (Jun 2), `TONE.md` `[path:ls]`. No untracked `.md` at root.

### 6.C Harness / design docs under `docs/` (the dense surface)

All tracked unless flagged. Sizes/dates from `ls -la docs/` `[path:ls]`:

- **Hardening family:** `SYNAPSE_3xs_HARDENING_HARNESS.md` **(UNTRACKED, Jun 14)** · `SYNAPSE_HARDENING_PRD.md` (Jun 5) · `HARDENING_RUN_2026-06-10.md` (12711 B, references base `d1abe21` v5.12.0, suite 3,415 green; M1→M2→M3 ledger) `[docs/HARDENING_RUN_2026-06-10.md:1-7]` · `SYNAPSE_VFX_PRODUCTION_HARDENING_2026-06-09.md` (23340 B; HEAD `ef58fa0` v5.12.0, fed the C1–C11+D3 remediation) `[docs/SYNAPSE_VFX_PRODUCTION_HARDENING_2026-06-09.md:1-6]`.
- **CTO family:** `SYNAPSE_CTO_REMEDIATION_HARNESS_v1.md` (Jun 9) · `SYNAPSE_CTO_REVIEW_2026-06-05.md` (112330 B — largest doc in repo) · `SYNAPSE_CTO_REVIEW_2026-06-09.md` (Jun 9).
- **Science family:** `SYNAPSE_SCIENCE_HARNESS.md` (base) · `_v3` · `_v4` (51781 B) · `_v5` · `SCIENCE_HARNESS_LEDGER.md` (83997 B) · `SCIENCE_HARNESS_PHASE0A_SPEC.md` · `SYNAPSE_SCIENCE_HARNESS_v5.md` · `SCIENCE_apex_verify_run_2026-06-02.md`.
- **RSI family:** `SYNAPSE_RSI_HARNESS.md` (39144 B) · `SYNAPSE_RSI_AUDIT.md` · plus `docs/rsi/{FORUM,RSI_CAPSULE,RSI_CHAMPION,RSI_DEADENDS,RSI_PLAN,SPEC}.md`.
- **Scout family:** `SYNAPSE_SCOUT_HARNESS_v1.md` (Jun 8) · `SYNAPSE_SCOUT_SPIKE_2.5_COVERAGE.md` (Jun 8) — the coverage doc for the symbol-table demotion (§8).
- **Panel / provider family:** `SYNAPSE_PANEL_HARNESS_v9.md` **(Jun 14 — today, tracked)** · `SYNAPSE_PANEL_REDESIGN_HARNESS.md` · `SYNAPSE_MULTI_PROVIDER_HARNESS_v1.md` **(Jun 14 — today, tracked)** · `design/SYNAPSE_PANEL_REDESIGN.md`.
- **Moneta family:** `MONETA_SYNAPSE_INTEGRATION_HARNESS.md` · `MONETA_SYNAPSE_HANDOFF_Mile2.md` · `MONETA_SYNAPSE_SHIP_REPORT.md` · `MONETA_FOLLOWUPS.md`.
- **RFC / spec:** `RFC_agent_usd_ledger.md` (Jun 6) · `RFC_allocation_exposure_schema.md` (Jun 8) · `FORGE_SPEC_apex_verify_harness.md` · `FORGE_SPEC_execute_python_fix.md` · `SYNAPSE_MOE_Blueprint.md`.
- **Tooling truth:** `MCP_TOOL_CATALOG.md` (37498 B, Jun 11) · `tools.md` · `verification_ledger.md`.
- **Studio:** `docs/studio/{DEPLOYMENT,DIAGNOSTICS,EGRESS,STUDIO_SPRINT,UPGRADE}.md`.
- **Sprint/spike trees:** `docs/sprint2/`, `docs/sprint3/` (incl. `spike_3_0_pdg_api_audit.md`, `CONTINUATION_INSIDE_OUT_TOPS.md`), `docs/tops/`, `docs/monitoring/`, `docs/mcp/`, `docs/plans/` (5 dated plans).
- **API docs mirror:** `docs/api/{core,memory,routing,server}/*.md` (incl. `routing/knowledge.md`, `routing/router.md`, `server/handlers.md`, `server/resilience.md`).

### 6.D `.scout/` (present, but NOT a docs dir)

`.scout/` exists `[path:ls]` and holds **scratch/recon artifacts, not harness docs**: `_pytest_*.txt` logs, `s1/s2/s3_*_recon.py` probe scripts, `_assemble_report.py`, `_commitmsg.txt`, `__pycache__/`, and a `scout-20260529-1045/` subdir. **No `.md` files in `.scout/`** `[grep]`. Untracked working dir (none of these appear in `git ls-files`).

### 6.E Untracked-md summary (the only drift surface)

`git status --porcelain | grep '^?? .*\.md'` returns exactly **one** file: `docs/SYNAPSE_3xs_HARDENING_HARNESS.md` `[grep]`. Everything else under root + `docs/` is tracked. The two Jun-14 panel/provider harnesses (`SYNAPSE_PANEL_HARNESS_v9.md`, `SYNAPSE_MULTI_PROVIDER_HARNESS_v1.md`) are already tracked despite today's mtime.

---

## §8 · SYMBOL-TABLE SUPPLEMENT (live bridge DOWN → committed `dir()` snapshot)

**Source of truth:** `python/synapse/cognitive/tools/data/h21_symbol_table.json` — a single-line 1,205,474-byte JSON `[path:1]` (`wc -l`=0 because it's one line, not empty). All membership below is `[table]` (committed introspected `dir()` snapshot). **The live bridge is DOWN this run (ws://localhost:9999 timeout), so live confirmation of every row is [NOT RUN] and owed.** On-disk snapshot ≠ live runtime.

### 8.A Build / version stamp `[path:1]`

```
schema:          scout_symbol_table/v1
houdini_version: 21.0.671
symbol_count:    33255   (meta == actual count of "symbols" list: 33255 — consistent)
blake2b:         ae7688f80a7076dc1c5b9fb3c05ab53d
truncated:       false
node_cap:        300000
depth:           {hou_pdg: 2, pxr: 1}
```
File mtime Jun 8 15:35 — same day as `SYNAPSE_SCOUT_SPIKE_2.5_COVERAGE.md`. **Stamped to H21.0.671** — matches the graphical Houdini, NOT hython 21.0.631. So the symbol authority is the 671 runtime.

### 8.B Three roots, not one `[table]`

The table is rooted on THREE top-level modules, not just `hou`: `hou` (14,053 symbols), **standalone `pdg`** (3,574), `pxr` (15,628). This is load-bearing for the phantom checks below — `hou.pdg` is correctly absent while the *standalone* `pdg` module is fully captured.

### 8.C Requested membership

| Symbol | Verdict | Note |
|---|---|---|
| `hou.pdg` | **ABSENT** `[table]` | Expected phantom — confirmed. PDG lives under standalone `pdg`, not `hou.pdg`. |
| `hou.secure` | **ABSENT** `[table]` | Expected phantom — confirmed. |
| `hou.lopNetworks` | **ABSENT** `[table]` | Expected phantom — confirmed (matches the R10 workaround that walks `hou.LopNetwork` from root instead). |
| `hou.updateGraphTick` | **ABSENT** `[table]` | Expected phantom — confirmed. |
| `hou.qt` | **ABSENT — 0 members** `[table]` | The table captures **zero** `hou.qt.*` symbols. So `styleSheet`/`color` under `hou.qt` are **not recorded** (cannot affirm or deny via this table). ⚠ **This is an introspection-depth artifact, NOT proof `hou.qt` is phantom** — see 8.D. `hou.ui` is likewise absent (0 members). |
| `hou.undos` | **PRESENT** `[table]` | But as a bare leaf with **0 children**. |
| `hou.undos.group` | **ABSENT** `[table]` | ⚠ **Absence here does NOT mean phantom.** `hou.undos` is a module-singleton whose function children were not introspected (so are `.add/.clear/.disabler/.isUndoEnabled` — all ABSENT). CLAUDE.md §12 and the live handler path both call `hou.undos.group(...)`; this table simply doesn't descend module-singleton callables. Live-confirm owed [NOT RUN]. |
| `hou.selectedNodes` | **PRESENT** `[table]` | Leaf, 0 children (it's a function; table records the name, not its signature). |
| `hou.frame` | **PRESENT** `[table]` | Plus `hou.setFrame`, `hou.frameToTime`, `hou.timeToFrame`, `hou.fps` all PRESENT. |
| `hou.playbar` | **PRESENT** `[table]` | Bare leaf (0 children). Related event enum `hou.playbarEvent.*` IS captured (11 members: FrameChanged, GlobalFrameRangeChanged, Started, Stopped, etc.). |

### 8.D The load-bearing caveat (why `undos.group`/`hou.qt` absence is benign)

The snapshot captures **class methods** but **not module-singleton function children**. Evidence `[table]`:
- `hou.Node.*` has **119** captured methods (allNodes, appendComment, …) — classes ARE descended.
- `hou.undos`, `hou.hmath`, `hou.text`, `hou.hipFile`, `hou.galleries`, `hou.styles` are all PRESENT as leaves with **0 children** — module-singletons are NOT descended into their callables.
- `hou.qt` / `hou.ui` are absent entirely — those submodules weren't enumerated at all.

**Consequence:** for this table, *leaf-presence is a positive signal but child-absence under a module-singleton is NOT a negative signal.* A real phantom (`hou.pdg`, `hou.secure`, `hou.lopNetworks`, `hou.updateGraphTick`) is absent **as a leaf at its own level**; `hou.undos.group` is absent only because its parent's methods weren't walked. Do not treat `hou.undos.group` or anything under `hou.qt` as phantom on this table's say-so — that's a live-runtime question, [NOT RUN] this session.

### 8.E Standalone `pdg` root sanity (the R8 surface) `[table]`

The PDG event-bridge symbols the bridge relies on are all PRESENT under the standalone root: `pdg.EventType`, `pdg.EventType.CookComplete`, `pdg.PyEventHandler`, `pdg.GraphContext`. So R8's API claims hold against the snapshot (live-confirm still [NOT RUN]).

---

## §7 · GIT STATE

### Current branch
`master` [grep: `git rev-parse --abbrev-ref HEAD` → `master`]. Matches the env banner and the git-status snapshot in the run header.

### Last 10 commits (`git log --oneline -10`) [grep]
```
86ef9bc docs(harness): add multi-provider LLM abstraction harness v1 — ARCHITECT dispatch
c0cabd7 docs(release): v5.14.0 -- studio-operable; README + mermaid truth pass
00f2719 feat(hardening): M3 final wave -- multiseat/egress docs (M3-D) + upgrade surface (M3-A); M3 COMPLETE
b614f80 feat(hardening): M3-E -- bounded autonomy: clamp, wall clock, reachable kill switch
939771d feat(hardening): M3 wave 1 -- env conformance (M3-B) + logs/doctor/telemetry (M3-C)
085fc82 docs(release): v5.13.0 -- production hardening M1+M2; README + mermaid truth pass
75993b9 feat(hardening): M2 wave 3 -- color-managed previews (M2-G); M2 COMPLETE
5bf9a3a feat(hardening): M2 wave 2 -- path policy (M2-D): tokens stay raw, frames stay targeted
5704dfe feat(hardening): M2 wave 1 -- show-config keystone (M2-I) + LOP display policy (M2-A)
ccd35ab docs: track the CTO review, Solaris/Copernicus scaffold report, and scene diagnostics (operator request)
```

**HEAD has moved past the CLAUDE.md/system-reminder snapshot.** The provided git-status snapshot listed `c0cabd7` as `HEAD`; live `HEAD` is now **`86ef9bc`** [grep], one commit ahead — a *docs-only* commit (`docs(harness): add multi-provider LLM abstraction harness v1 — ARCHITECT dispatch`). The top 6 commits are the M2/M3 hardening waves + v5.13/v5.14 releases referenced throughout CLAUDE.md.

### Uncommitted / untracked changes (`git status --porcelain`) [grep]
A single untracked file, no modified/staged/deleted tracked files:
```
?? docs/SYNAPSE_3xs_HARDENING_HARNESS.md
```
- 216 lines [grep: `wc -l`]. Header: *"SYNAPSE — FIELD-READINESS / HARDENING HARNESS … Status: ARCHITECT artifact. Design only, no implementation. Pre-FORGE."* [path:docs/SYNAPSE_3xs_HARDENING_HARNESS.md:1-5]. It is a **design doc, not code** — pairs thematically with the new `86ef9bc` "multi-provider LLM abstraction harness" ARCHITECT-dispatch commit (both ARCHITECT artifacts, both un-FORGED).

Working tree is otherwise **clean** of source changes — recon-safe; nothing of mine to revert.

### `.scout/` directory [path:.scout/ via `ls -la` + grep]
`.scout/` **exists on disk** but is **git-ignored** — `git ls-files .scout/` returns **0 tracked files** [grep], and `git check-ignore .scout/` confirms the ignore [grep]. Ignore source: `.gitignore:99-100` [path:.gitignore:99-100]:
```
# SCOUT reconnaissance artifacts (read-only investigation output)
.scout/
```

Top-level `.scout/` contents (untracked, prior-run scratch) [grep: `ls -la`]:
```
__pycache__/                  s1_api_probe.py (604B)     s2_lop_recon.py (2075B)
_assemble_report.py (7864B)   s1_repro.py (2913B)        s2_lop_recon2.py (2033B)
_commitmsg.txt (933B)         _insights.py (3231B)       s3_sopimport_recon.py (1808B)
_pytest_0a.txt (32228B)       _pytest_final.txt (34009B) s3_sopimport_recon2.py (1808B)
_pytest_final2.txt (33472B)   _pytest_int1.txt (34009B)  _pytest_out.txt (31691B)
scout-20260529-1045/          (subdir)
```
These are stale captures: pytest run-logs (`_pytest_*.txt`), API-recon probe scripts (`s1`/`s2`/`s3_*.py` — LOP/sopimport recon), a report assembler, and a `_commitmsg.txt`. Newest mtime `Jun 6` (`_commitmsg.txt`); most are `Jun 5`.

`.scout/scout-20260529-1045/` — a **prior CARTOGRAPHER/PROSPECTOR run** (dated 2026-05-29) [grep: `ls -la`]:
```
CANDIDATES.md (19465B)   CAPABILITY_MAP.md (22168B)  CAPSULE.md (990B)
CODEBASE_MAP.md (28735B) LEDGER.md (8173B, Jun 5)    OPPORTUNITIES.md (8981B)
PLAN.md (2360B)          RED_TEAM.md (41378B)        SCOPE.md (5606B)
TRACE.md (8868B)         VERIFICATION.md (4608B)     _probe_v1.py (2459B)  __pycache__/
```
This is exactly the artifact set this run produces (note the prior `CODEBASE_MAP.md`). It is **NOT version-controlled** — every file here is invisible to git. Implication: my run's `CODEBASE_MAP.md` will land in `.scout/` and likewise stay untracked by design.

---

## §8 · LIVE-RUNTIME PROBES — **[NOT RUN]**

The live Synapse bridge was unreachable this run (`ws://localhost:9999/synapse` timed out during handshake; the SessionStart "bridge connected" banner was stale). **No `[V1]` live-runtime facts could be gathered.** The committed introspected `dir()` symbol table was read instead as a static supplement — see **§6 Part B** (tagged `[table]`, NOT a live session).

**Owed live probes (run in a live H21.0.671 session):** `dir()`/`hasattr` for `hou.pdg`, `hou.secure`, `hou.lopNetworks`, `hou.updateGraphTick` (expected absent), `hou.qt` (+ `styleSheet`, `color`), `hou.undos.group`, and the selection/frame API (`hou.selectedNodes`, `hou.frame`, `hou.playbar`) the rail context needs.

---

## §9 · DRIFT & SURPRISES

The honest, deduplicated, severity-ordered list. Lead block = banner contradictions and live-vs-disk gaps a design pass will trip over first.

### A. Banner contradictions (the map lies about the runtime)

1. **`Python 3.14` is banner fiction for the embedded runtime.** `__init__.py:51-57` ABI-locks the vendored deps to **Python 3.11** (`cp311-win_amd64.pyd`, gated `version_info[:2]==(3,11) and platform=='win'`) for *every* Houdini point release [path:51-57]. 3.14 is only the standalone CI/host interpreter that runs the test suite and resolves pydantic from user-site. `pyproject.toml` requires-python `>=3.9` (classifiers cap 3.11) [pyproject], `.mypy_cache/3.11` corroborates [path]. **A design pass that assumes 3.14 language features inside Houdini will break on import.** [CLAUDE.md:3 vs path:__init__.py:51]

2. **Houdini build banner is wrong: `21.0.631` vs live `21.0.671`.** The committed introspected symbol table records `houdini_version: 21.0.671` (33255 symbols) [table] — verified on disk this run. The CLAUDE.md banner says 631. Graphical Houdini is 671; hython is a *separate* 631 site-packages. The "all revisions verified live on 21.0.596/21.0.671" claims across §15 are mixed-build breadcrumbs, not a single coherent runtime. [CLAUDE.md:3 vs table]

3. **Tool count "112" is the registry count, not the live surface — undercounts by 8.** `_tool_registry.py` AST-parses to exactly **112** tool defs (0 dups) [grep, prior recon] and README/mermaid/banner now agree at 112. But the **stdio bridge advertises 120**: 112 registry + 6 group-info + `synapse_inspect_stage` + `synapse_scout` [mcp_server.py:728-764]. The panel-memory "110" is a **stale note**, not a live contradiction. Caveat: a naive `grep -c` on the registry returns 5 (matches string literals, not the `TOOL_DEFS` tuples) — **do not count tools by grep; the 112 is AST-derived.** [grep]

### B. Live-vs-disk gaps — bridge is DOWN (ws://localhost:9999 timeout), so §8 runtime claims are [NOT RUN]

4. **The Lossless Execution Bridge is NOT on the live path — the doc's own warnings are the truth.** `LosslessExecutionBridge` is never imported by `websocket.py` / `hwebserver_adapter.py` / `api_adapter.py`; the live WS path calls `SynapseHandler.handle()` directly [handlers.py:386]. CLAUDE.md §1's headline "every mutation through the bridge" is **false on the live `/synapse` path** — only the §1 inline live-path notes are correct. **41 of 43 `hou.undos.group()` call-sites are hand-wired inline in `server/handlers*.py`; only 2 live in `shared/bridge.py`** [grep]. Undo safety is per-handler, not bridge-provided. [path:line]

5. **`execute_python` runs ungated with full `__builtins__`, no length cap, no consent — on BOTH transports.** WS handler [handlers.py:1028] and HTTP `/api` [api_adapter.py:306]. `FloorGate` is provenance-only — "no halting, no consent gating" [floor_gate.py:19-20]. This is the deliberate single-user-localhost posture (matches §1.2 live note), **but a design pass treating gate levels as enforced will be wrong.** [path:line]

6. **HTTP `/api execute_python` is strictly weaker than WS — no undo group, no atomic flag at all** [api_adapter.py:298-311]. The WS handler at least offers an optional atomic wrap; the HTTP path offers nothing. Two code-execution doors, unequal safety. [path:line]

7. **Emergency halt on the live transport is effectively a no-op.** `freeze_chain.py:160-173` only triggers `EmergencyProtocol` if a bridge is *already* active, and "escalation never constructs one"; the hwebserver stack has no resilience layer [freeze_chain.py:156-158]. Contradicts §1.8 / Safety Rule 11 "emergency halt is immediate." [path:line]

8. **memory.jsonl durability covers the wrong path.** The hot `add()` append is a plain `open('a')` — **not atomic** [store.py:260]. Only the rare update/delete rewrite uses tmp+fsync+os.replace+.bak [store.py:480-483]. The advertised durability protects the cold path, not the hot one. [path:line]

### C. Version / protocol scatter (write-only, never validated)

9. **Four conflicting protocol versions on one socket.** Wire `PROTOCOL_VERSION='5.4.0'` [mcp_server.py:182] vs canonical `core/protocol.py:31='4.0.0'` vs a `'1.0.0'` from_json default — all write-only, never validated against each other. [path:line]

10. **Root `VERSION` file is stale at `5.8.0`** [VERSION:1] while `__init__.py:17` says `5.14.0` [path:17]. Also a **dead fallback literal `5.8.0`** in `mcp_server.py:110` if importlib.metadata can't resolve the package — never the live value. [path:line]

11. **Git snapshot in the prompt is stale.** Live HEAD = `86ef9bc` ("multi-provider LLM abstraction harness v1"), **1 commit past** the prompt's `c0cabd7`/v5.14.0 tag [git]. `git describe` = `v5.14.0-1-g86ef9bc`. [git]

12. **Scout's version-staleness pin depends on `hou`, which is absent in the zero-hou MCP server** [mcp_server.py:677-680]. A mismatched-build table would still be trusted there — integrity hash is checked, build version is not. [path:line, table]

### D. On-paper / phantom targets (map describes things that don't exist on disk)

13. **`python/synapse/transport/` does not exist.** Transport lives in `host/transport.py` + `server/websocket.py`. The §2 "transport" ownership target and CLAUDE.md `src/transport/` are on-paper. [grep]

14. **`~/.synapse/agent-sdk/` does not exist** — only `~/.synapse/agent/` (legacy standalone harness). The in-tree SDK is `python/synapse/host/` + `autonomy/`. [path]

15. **Memory evolution (charmander→charizard) is self-documented DEPRECATED.** `memory/evolution.py:1-13` declares itself superseded by Moneta — yet CLAUDE.md §6 presents it as live. The whole Pokémon-evolution §6 is a documented-but-retired subsystem. [evolution.py:1-13]

16. **`host/daemon.py` Phase-1 ships an EMPTY agent loop** (lifecycle only) [daemon.py:1-13]. Autonomy/SDK execution wiring is unconfirmed — a design pass should not assume the daemon executes agent turns. [daemon.py:1-13]

17. **`synapse_scout` dispatches via a SECOND, parallel mechanism** — the cognitive Dispatcher on a dedicated `call_tool` branch [mcp_server.py:686-692,791], NOT through `_tool_registry.py` `TOOL_DISPATCH`. Two tool-dispatch paths coexist. [path:line]

### E. Panel surface — two panels, divergent everything (any UI design pass must disambiguate FIRST)

18. **The REGISTERED Houdini panel is the v9 faces panel, not the chat panel.** `synapse_panel.pypanel:45` loads `synapse_panel.py::SynapsePanel` (faces); the chat panel's `.pypanel` lives inside the package dir, unregistered. [path:synapse_panel.py:45]

19. **Faces are TWO, not three.** `_FACE_INDEX={'direct':0,'work':1}` [synapse_panel.py:355]. "Review" is the `done` sub-state of Work (FaceReview folded into an inner QStackedWidget), not a top-level face. **Agent state never switches the visible tab by design** — busy/gate/result drive `_set_work_substate`, not `_set_face` [synapse_panel.py:574-578,988-992]. The only user-driven Direct entry is the "BUILD HDA" overflow action [synapse_panel.py:651].

20. **Two design-token sources disagree hard.** designsystem SIGNAL=`#8FB3D9` (muted blue, v9 panel) vs panel/tokens.py + off-repo `~/.synapse/design` SIGNAL=`#00D4FF` (cyan, chat panel); BODY 13 vs 26; UI scale 9-20 vs 22-44 [designsystem/tokens.py:22]. Worse: **`panel/tokens.py:13` imports from OFF-REPO `~/.synapse/design/tokens.py`** — the chat-panel token path is **not reproducible from a clean checkout.** [path:line]

21. **Stop semantics differ across the two panels.** v9 rail = `Button('Stop', variant='danger')`, cooperative abort, state-gated [synapse_panel.py:309]. Old chat panel = "HALT" button firing `emergency_halt` over WS — and per item 7 that halt is a live no-op. Quick-actions also differ: v9 EXPLAIN/FIX/OPTIMIZE + BUILD HDA vs old Explain/Make HDA/Fix/Optimize/VEX Help [synapse_panel.py:649].

22. **Brief's `MarkDat` does not exist** — the real class is `MarkDot` (status-light widget) [designsystem/components.py:128]. No markdown-renderer class exists; markdown is helper functions in `message_formatter.py` / `dnd.py`.

23. **`houdini/scripts/python/synapse_shelf.py:22` imports PySide2 directly**, no PySide6-first attempt — lagging the PySide6-primary/PySide2-fallback convention used elsewhere. `INVENTORY.md:262` still says "PySide2, 5 tabs." [path:synapse_shelf.py:22]

24. **No Houdini pane/floating-panel surface exists at all** — ZERO `createFloatingPanel`/`createTab`/`findPaneTab`/`setCurrentTab` anywhere in `python/synapse/panel` [grep]. The one `hou.ui` pane call (`_on_node_clicked`) only navigates an *existing* Network Editor (setCurrentNode/homeToSelection), neither creates nor switches a pane [chat_panel.py:907-922]. **Spike-1 same-pane tab switch IS wired today** via `pill.clicked.connect → _set_face` [synapse_panel.py:369]. Fonts confirmed bundled: `QFontDatabase.addApplicationFont` + 3 physical .ttf in designsystem/fonts/ [designsystem/fontload.py:57].

---

## CAPSULE

**Where SYNAPSE actually is (2026-06-14, live bridge DOWN — all runtime claims this run are static-disk only).** SYNAPSE is a v5.14.0-tagged, **HEAD-at-86ef9bc** (one commit past the tag, into "multi-provider LLM abstraction harness v1") MOE-orchestrator + Houdini bridge. The code is real and large — 112 AST-counted MCP tools [grep], a 120-tool live stdio surface [mcp_server.py:728-764], a working v9 two-face Houdini panel, the cognitive Scout/Dispatcher path, and a vendored anthropic stack — but the CLAUDE.md blueprint is **aspirational in three load-bearing ways** that will mislead a design pass that trusts it. **TOP 3 THINGS TO KNOW BEFORE TRUSTING MEMORY: (1) The runtime is Python 3.11 / Houdini 21.0.671, NOT the banner's "3.14 / 21.0.631" — the vendor is ABI-locked to cp311 [__init__.py:51-57] and the symbol table reads 671 [table]; design for 3.11.** **(2) The Lossless Execution Bridge is an audit layer on the `/mcp` path ONLY — the live `/synapse` WS + HTTP `/api` paths bypass it entirely, run `execute_python` ungated with full builtins on both [handlers.py:1028, api_adapter.py:306], hand-wire undo in 41/43 handler sites [grep], and the "emergency halt" is a live no-op [freeze_chain.py:156-173]. Treat §1's universal-interception headline as false; the §1 inline live-path warnings are the real contract.** **(3) "Panel" is ambiguous and version-scatter is everywhere — the REGISTERED panel is v9 faces (`synapse_panel.py`, two faces not three), the chat panel is unregistered and pulls tokens from an off-repo `~/.synapse/design` dir that breaks a clean checkout [panel/tokens.py:13]; meanwhile VERSION file says 5.8.0, `__init__` says 5.14.0, and four protocol versions (5.4.0/4.0.0/1.0.0/+) sit unvalidated on one socket. Disambiguate which panel and pin the real version before designing anything.**
