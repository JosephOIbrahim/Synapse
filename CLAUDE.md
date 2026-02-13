# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse v5.3.0 is an AI-Houdini Bridge — a standalone Python package (zero required dependencies) that lets AI assistants control SideFX Houdini via WebSocket. It exposes 43 MCP tools to Claude Desktop/Code for real-time scene manipulation, persistent project memory, adaptive tiered LLM routing, and viewport/render capture.

Two repos make up the full system:
- **`C:\Users\User\Synapse\`** — Core server, protocol, handlers, memory, routing, MCP bridge
- **`C:\Users\User\.synapse\`** — Agent SDK (autonomous co-pilot), design system (tokens/icons/styles), Houdini shelf/panel integration, installer

---

## Sprint Orchestrator — Auto-Detecting

> **How this works:** On every session start, check the filesystem gates below to determine
> which sprint is active. No manual status flipping required — the codebase IS the state.

### Step 1: Check MCP Sprint Gates

Verify ALL of the following files exist in the repo:

```
synapse/mcp/server.py          — MCP endpoint handler with /mcp route
synapse/mcp/tools.py           — Tool registry mapping to existing handlers
synapse/mcp/session.py         — Session manager
synapse/mcp/protocol.py        — JSON-RPC utilities
docs/mcp/SETUP.md              — User-facing connection instructions
tests/test_mcp_protocol.py     — MCP protocol tests (must exist AND pass)
```

**Run this check:**
```bash
# All 6 must exist. If ANY is missing, MCP Sprint is active.
ls synapse/mcp/server.py synapse/mcp/tools.py synapse/mcp/session.py \
   synapse/mcp/protocol.py docs/mcp/SETUP.md tests/test_mcp_protocol.py
```

### Step 2: Route to Active Sprint

```
IF any MCP gate file is missing:
    → ACTIVE SPRINT: MCP Protocol Conformance
    → Read: docs/mcp/SYNAPSE_MCP_SPRINT.md
    → TOPS status: PARKED (do NOT touch TOPS/PDG files)

ELSE IF MCP gates pass BUT tops tools not registered:
    (Check: grep -l "tops_cook_node\|tops_get_work_items" synapse/mcp/tools.py → no match)
    → ACTIVE SPRINT: TOPS/PDG Integration
    → Read: docs/tops/TOPS_SPRINT.md
    → Read: docs/tops/PARKING_SNAPSHOT.md (resume context)
    → Agent orchestration: ~/.claude/agent.md

ELSE (both MCP and TOPS gates pass):
    → NO ACTIVE SPRINT — normal development mode
    → All new functionality follows "Adding New Functionality" below
```

---

### Sprint A: MCP Protocol Conformance

**Activates when:** Any MCP gate file is missing.

> **Goal:** Add MCP Streamable HTTP transport to SYNAPSE, making it a universal MCP server
> that any compliant client (Claude Code, Cursor, VS Code, Windsurf, etc.) can connect to
> via `claude mcp add --transport http synapse http://localhost:PORT/mcp`.
>
> **Why now:** MCP is a force-multiplier. Every tool, resource, and feature SYNAPSE exposes
> becomes available to the entire AI tooling ecosystem — not just our WebSocket clients.
> Every subsequent feature (including TOPS) benefits immediately.
>
> **Protocol Target:** MCP 2025-06-18 (Streamable HTTP, JSON-RPC 2.0)

#### MCP Sprint Phases

| Phase | Scope | Gate Files |
|-------|-------|------------|
| **Phase 1 — MVP** | `/mcp` endpoint, JSON-RPC router, `initialize`, `tools/list`, `tools/call`, session management | `server.py`, `tools.py`, `session.py`, `protocol.py` |
| **Phase 2 — Resources & Prompts** | `resources/list`, `resources/read`, scene state exposure, prompt templates | `SETUP.md`, `test_mcp_protocol.py` |
| **Phase 3 — Polish** | `list_changed` notifications, SSE stream, `resources/subscribe`, auth, rate limiting | (no new gate files — completes MCP sprint) |

**Before starting any phase, read `docs/mcp/SYNAPSE_MCP_SPRINT.md`** for full implementation
reference including code examples, the complete JSON-RPC router, tool registry pattern,
FastMCP SDK integration options, and protocol details.

#### MCP Sprint Rules

1. **The MCP layer is a protocol adapter** — it sits on top of existing handlers and safety middleware. It does NOT replace them.
2. **Existing endpoints are untouched** — WebSocket transport, REST adapter, and all current functionality continue to work.
3. **New files go in `synapse/mcp/`** — see File Organization below. Do not scatter MCP protocol code across existing modules.
4. **All tool calls route through existing `handlers.py`** — the MCP dispatch layer translates JSON-RPC into existing SYNAPSE commands. Safety middleware (atomic scripts, idempotent guards, undo-groups) is enforced by the handlers, never bypassed.
5. **Test without Houdini** — MCP protocol tests follow the same `hou` stub pattern as existing tests.

#### TOPS — PARKED During MCP Sprint

**While MCP sprint is active, TOPS is frozen:**

- Do NOT modify any TOPS/PDG files as part of MCP work
- Do NOT refactor TOPS-related code during this sprint
- If MCP implementation reveals a natural interface point for TOPS, document it in `docs/mcp/TOPS_INTEGRATION_POINTS.md` but do not implement
- All TOPS-related branches remain as-is — no rebasing, no merging

**On first run of MCP sprint:** Scan the codebase for any TOPS/PDG work-in-progress. Write a parking snapshot to `docs/tops/PARKING_SNAPSHOT.md` capturing: where it was, what was being worked on, immediate next action, and blockers. This snapshot is consumed at TOPS sprint resumption.

---

### Sprint B: TOPS/PDG Integration

**Activates when:** All MCP gate files exist AND TOPS tools are not yet registered in `mcp/tools.py`.

> **Goal:** Add PDG/TOPs integration to SYNAPSE, exposing distributed cooking, wedging,
> dependency management, and scheduler control as MCP tools. Every TOPS capability is
> registered in the MCP tool registry from day one — no separate API, no retrofit.
>
> **Prerequisite:** MCP Protocol Sprint must be complete (verified by filesystem gates above).

#### On TOPS Sprint Activation

1. **Read `docs/tops/TOPS_SPRINT.md`** — full implementation reference with tool schemas, handler patterns, PDG API surface, and phased plan
2. **Read `docs/tops/PARKING_SNAPSHOT.md`** — resume context from when TOPS was parked
3. **Read `docs/mcp/TOPS_INTEGRATION_POINTS.md`** (if it exists) — integration hints noted during MCP sprint
4. **Load `~/.claude/agent.md`** — agent orchestration directives for TOPS sub-tasks (`C:\Users\User\.claude\agent.md`)

#### TOPS Sprint Phases

| Phase | Scope | Verification |
|-------|-------|-------------|
| **Phase 1 — Core Tools** | `tops_get_work_items`, `tops_get_dependency_graph`, `tops_get_cook_stats`, `tops_cook_node`, `tops_generate_items` | Tools appear in `tools/list` from MCP client |
| **Phase 2 — Scheduler & Control** | `tops_configure_scheduler`, `tops_cancel_cook`, `tops_dirty_node`, TOPS resources | Scheduler configurable via MCP, cook cancellable |
| **Phase 3 — Advanced** | Wedge setup, batch cook, work item queries, cook progress notifications | End-to-end PDG workflow from MCP client |

#### TOPS Sprint Rules

1. **All TOPS tools register as MCP tools from the start** — use the `mcp/tools.py` registry pattern. No separate API.
2. **Handlers go in `handlers.py`** alongside existing handlers — follow the exact same pattern.
3. **Safety middleware applies automatically** — TOPS handlers inherit atomic scripts, idempotent guards, undo-groups.
4. **Stub `pdg` module in tests** — same pattern as `hou` stubs. `import pdg` only works inside Houdini.
5. **Both MCP registries stay in sync** — `mcp_server.py` (stdio) and `mcp/tools.py` (Streamable HTTP).

#### TOPS Sprint Completion Gate

Sprint B is complete when `grep -c "tops_" synapse/mcp/tools.py` returns 5+ (core tools registered)
AND `python -m pytest tests/test_tops.py -v` passes.

#### Agent Orchestration

TOPS work can be decomposed into agent sub-tasks. See `.claude/agent.md` for directives
on how to structure TOPS implementation as agent work items. See `~/.claude/agent.md`
(`C:\Users\User\.claude\agent.md`).

---

### Sprint Queue (Future)

When both Sprint A and Sprint B are complete, the orchestrator enters normal development mode.
Potential future sprints can be added here with their own filesystem gates:

```
Sprint C: Agent SDK v2 (autonomous VFX co-pilot improvements)
Sprint D: Studio deployment (multi-user auth, remote access, RBAC)
Sprint E: Real-time monitoring (live scene metrics dashboard)
```

To add a new sprint: define filesystem gates, write a sprint doc in `docs/`, add a gate
check block above, and the orchestrator picks it up automatically.

---

## Source vs. Deployed Files

**Always edit the repo source — never the deployed copies.** The installer (`~/.synapse/install.py`) copies from source to Houdini prefs. Editing deployed files directly causes drift that gets overwritten on next install.

| What | Source (edit here) | Deployed (never edit) |
|------|-------------------|----------------------|
| Core server | `SYNAPSE/python/synapse/` | `site-packages/synapse/` |
| Shelf/panel | `~/.synapse/houdini/` | `~/houdini21.0/` |
| Design system | `~/.synapse/design/` | (not deployed) |
| Agent SDK | `~/.synapse/agent/` | (not deployed) |

After editing source files, remind the user to redeploy if needed (`python ~/.synapse/install.py --verify`).

## Development Commands

```bash
# Install for development
pip install -e ".[dev]"
pip install -e ".[dev,websocket,mcp,routing,encryption]"   # all optional features

# Run all core tests (~825 tests, no Houdini required)
python -m pytest tests/ -v

# Type checking (mypy, 0 errors on 49 source files)
python -m mypy python/synapse/ --config-file pyproject.toml

# Build API docs (MkDocs + mkdocstrings)
python -m mkdocs build

# Key test files
python -m pytest tests/test_routing.py -v              # Routing cascade (~323 tests)
python -m pytest tests/test_pipeline_efficiency.py -v   # RWLock, tier-pinning, batch, concurrent (35 tests)
python -m pytest tests/test_materials.py -v             # Material tools (19 tests)
python -m pytest tests/test_render.py -v                # Karma/Mantra pipeline
python -m pytest tests/test_introspection.py -v         # Scene inspection
python -m pytest tests/test_core.py -v                  # Determinism, audit, gates
python -m pytest tests/test_agent.py -v                 # Agent protocol, executor
python -m pytest tests/test_resilience.py -v            # Rate limiter, circuit breaker
python -m pytest tests/test_auth.py -v                  # Authentication (21 tests)
python -m pytest tests/test_stress.py -v                # Load/stress testing (24 tests)
python -m pytest tests/test_integration_pipeline.py -v  # Integration pipeline (20 tests)
python -m pytest tests/test_sqlite_store.py -v          # SQLite memory backend (40 tests)
python -m pytest tests/test_mcp_protocol.py -v          # MCP Streamable HTTP protocol (NEW)

# Single test
python -m pytest tests/test_routing.py::test_routing_benchmark -v

# Agent SDK tests (from .synapse/agent/)
python -m pytest C:\Users\User\.synapse\agent\tests\ -v    # 49 tests

# Design system tests (from .synapse/)
python -m pytest C:\Users\User\.synapse\tests\test_design_system.py -v   # 44 tests

# Coverage
python -m pytest tests/ --cov=synapse --cov-report=term-missing
```

**CI**: GitHub Actions on Python 3.11 + 3.14, runs `python -m pytest tests/ -v --tb=short`.

## Architecture

### Data Flow (MCP to Houdini)

```
ANY MCP Client (Claude Code, Cursor, VS Code, Windsurf, custom agents)
    |  Streamable HTTP: POST/GET http://localhost:PORT/mcp
    |  JSON-RPC 2.0 + Mcp-Session-Id headers
    |
MCP Protocol Layer  (synapse/mcp/ — NEW)
    |  Session mgmt, tool/resource/prompt dispatch
    |  Translates JSON-RPC ↔ SYNAPSE commands
    |
    ├─── tools/call ──────┐
    ├─── resources/read ──┤
    └─── prompts/get ─────┤
                          |
Claude Desktop/Code       |  (existing stdio path preserved)
    |  stdio / JSON-RPC   |
mcp_server.py  (43 tools) |
    |                     |
    ├─────────────────────┘
    |  WebSocket: ws://localhost:9999/synapse
SynapseServer  (daemon thread inside Houdini)
    |  CommandHandlerRegistry (handlers.py)
hou.* Python API
    |
Houdini USD Stage / Solaris / Karma
```

Both MCP Streamable HTTP and the existing WebSocket/stdio paths converge at the same handler layer. The MCP protocol layer adds no new safety logic — it delegates entirely to existing handlers which enforce atomic scripts, idempotent guards, and undo-group transactions.

### Core Package Layout (`python/synapse/`)

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| Foundation | `core/` | Wire protocol (`protocol.py`), parameter aliases (`aliases.py`), determinism (`determinism.py`), audit chain (`audit.py`), human gates (`gates.py`), encryption (`crypto.py`), command queue (`queue.py`) |
| Memory | `memory/` | JSONL store (`store.py`) or SQLite store (`sqlite_store.py`, via `SYNAPSE_MEMORY_BACKEND=sqlite`), data models (`models.py`), shot context (`context.py`), markdown export (`markdown.py`), **Living Memory**: scene memory (`scene_memory.py`), agent state USD (`agent_state.py`), evolution system (`evolution.py`) |
| Routing | `routing/` | Tiered LLM dispatch (`router.py`), regex parser (`parser.py`), RAG knowledge (`knowledge.py`), recipes (`recipes.py`), deterministic cache (`cache.py`), workflow planner (`planner.py`), epoch-based tier adaptation (`adaptation.py`) |
| Agent | `agent/` | prepare/propose/execute/learn lifecycle (`executor.py`), task/plan/step protocol (`protocol.py`), outcome tracking (`learning.py`) |
| **MCP** | **`mcp/`** | **MCP Streamable HTTP protocol layer (NEW). `server.py` (endpoint handler, JSON-RPC router), `session.py` (session manager), `tools.py` (tool registry mapping to existing handlers), `resources.py` (scene state resources), `prompts.py` (reusable workflow prompts), `protocol.py` (JSON-RPC utilities, error codes), `types.py` (type definitions, schemas)** |
| Server | `server/` | WebSocket server (`websocket.py`), 39 command handlers (`handlers.py`), resilience stack (`resilience.py`), scene introspection (`introspection.py`), hwebserver adapter (`hwebserver_adapter.py`), REST adapter (`api_adapter.py`), guard functions (`guards.py`), authentication (`auth.py`), Prometheus metrics (`metrics.py`) |
| Session | `session/` | SynapseBridge singleton hub (`tracker.py`), session summaries (`summary.py`) |
| UI | `ui/` | Qt panel with 5 tabs (`panel.py`), tab widgets in `tabs/` |

### Routing Cascade (cheapest-first)

```
Cache(O(1)) -> Recipe(O(1)) -> Planner(O(1)) -> Tier0/regex(O(n)) -> Tier1/RAG(O(log n)) -> Tier2/Haiku(~5s) -> Tier3/Agent(~15s)
```

- **Tier pinning** (He2025 consistency): Same input+context maps to same tier on subsequent calls. LRU cache, max 1,000 pins, stale pins fall through.
- **Speculative T0+T1 parallelism**: Module-level `ThreadPoolExecutor(max_workers=2)` runs Tier 0 regex and Tier 1 knowledge lookup concurrently.
- **Tier 1 result threading**: `route()` runs `knowledge.lookup()` once, threads the result to all higher tiers to avoid redundant lookups.

### Transport Backends

| Backend | Module | Transport | Latency | Use Case |
|---------|--------|-----------|---------|----------|
| `websockets` | `server/websocket.py` | WebSocket | ~0.2ms warm ping | Primary — reads, pings, everything |
| `hwebserver` | `server/hwebserver_adapter.py` | HTTP (Houdini native) | ~2s floor (main event loop) | Optional — only for hou.* mutations |
| **`mcp`** | **`mcp/server.py`** | **Streamable HTTP (MCP)** | **TBD** | **Universal MCP client access (Claude Code, Cursor, VS Code, etc.)** |

WebSocket remains the primary internal transport. The MCP Streamable HTTP endpoint is additive — it provides a standardized protocol interface that any MCP-compliant client can use. Both share the same handler layer.

### Authentication (`server/auth.py`)

Optional API key authentication for both transports. Key sources (checked in order):
1. `SYNAPSE_API_KEY` environment variable
2. `~/.synapse/auth.key` file (first non-empty, non-comment line)
3. No key configured -> auth disabled (backward compat)

When enabled, first WebSocket message must be an `authenticate` command with `{"payload": {"key": "..."}}`. Uses `hmac.compare_digest` for constant-time comparison. Auth handshake integrated into both `websocket.py` and `hwebserver_adapter.py`.

**MCP auth (Phase 3):** Bearer token authentication via `Authorization: Bearer <token>` header on the `/mcp` endpoint. Opt-in for remote/studio deployments. Not required for localhost connections. Implemented as a `TokenVerifier` that delegates to the existing `auth.py` key validation.

### MCP Server — Existing stdio Bridge (`mcp_server.py`)

38 tools. Key operational details:
- **Concurrent dispatch**: `_pending` dict + `_recv_loop` coroutine — no blocking lock, true parallel tool calls
- **Timeouts**: Default 10s. Overrides: execute_python/execute_vex/capture_viewport/inspect_* at 30s, render/wedge at 120s, batch at 60s
- **JSON**: Uses `orjson` (fast, sort_keys via `OPT_SORT_KEYS`) when available, falls back to stdlib `json`
- **Warmup**: Pre-connect in `main()` reduces first-call latency
- **Retry**: `MAX_RETRIES=2`, `RETRY_DELAY=0.3`, auto-retry on connection drop
- **Connection**: `open_timeout=3.0`, `ping_interval=None`, `compression=None` (localhost optimization)

This existing stdio MCP bridge (`mcp_server.py`) is preserved as-is. The new MCP Streamable HTTP layer (`synapse/mcp/`) is a separate, additive transport — not a replacement.

### MCP Protocol Layer — Streamable HTTP (NEW)

This is the active sprint work. The MCP protocol layer lives in `synapse/mcp/` and provides a JSON-RPC 2.0 endpoint at `/mcp` on the hwebserver.

#### Endpoint Behavior

```
POST /mcp   →  Client sends JSON-RPC request or notification
               Response: application/json (single result) or text/event-stream (streaming)
GET  /mcp   →  Opens optional SSE stream for server→client messages (Phase 3)
```

#### Session Lifecycle

1. Client POSTs `initialize` with `clientInfo` and `protocolVersion`
2. Server responds with capabilities, serverInfo, and `Mcp-Session-Id` header
3. Client sends `notifications/initialized` (server returns 202 Accepted)
4. Session is live — client can call `tools/list`, `tools/call`, `resources/read`, etc.
5. Session ends when client disconnects or sends `notifications/cancelled`

#### Initialize Response

```python
{
    "protocolVersion": "2025-06-18",
    "capabilities": {
        "tools": {"listChanged": True},
        "resources": {"subscribe": False, "listChanged": False},
    },
    "serverInfo": {
        "name": "synapse",
        "version": "5.3.0"
    },
    "instructions": (
        "SYNAPSE is a bridge between AI agents and SideFX Houdini. "
        "All mutations go through safety middleware enforcing atomic scripts, "
        "idempotent guards, and undo-group transactions. "
        "Tools marked destructiveHint=True modify the Houdini scene."
    )
}
```

#### Tool Registry — Mapping Existing Handlers

Every existing SYNAPSE command handler maps 1:1 to an MCP tool. The `synapse/mcp/tools.py` module builds `tools/list` output from handler introspection and dispatches `tools/call` to the handler registry.

Tool definitions include JSON Schema `inputSchema` and MCP `annotations`:

```python
{
    "name": "execute_vex",
    "description": "Execute VEX code on a wrangle node through SYNAPSE safety middleware.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "VEX source code"},
            "node_path": {"type": "string", "description": "Full path to wrangle node"},
            "run_over": {
                "type": "string",
                "enum": ["Points", "Vertices", "Primitives", "Detail"],
                "default": "Points"
            }
        },
        "required": ["code", "node_path"]
    },
    "annotations": {
        "title": "Execute VEX Code",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False
    }
}
```

**Annotation rules:** Use `readOnlyHint: True` for all read/inspect/get operations. Use `destructiveHint: True` for anything that modifies the scene. Use `idempotentHint: True` for set operations where repeat calls produce the same result. MCP clients use these for UI gating and safety decisions.

#### Tool Dispatch — Bridge to Handlers

```python
async def dispatch_tool(tool_name: str, arguments: dict) -> dict:
    """Bridge MCP tools/call to existing SYNAPSE handlers.
    Safety middleware is enforced by the handlers — NOT bypassed."""
    handler = HANDLER_REGISTRY.get(tool_name)
    if not handler:
        raise MCPError(-32602, f"Unknown tool: {tool_name}")
    try:
        result = await handler(arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(result) if isinstance(result, dict) else str(result)}]
        }
    except SynapseError as e:
        return {"content": [{"type": "text", "text": f"Error: {e.message}"}], "isError": True}
```

**CRITICAL:** `dispatch_tool` implements zero safety logic. It delegates to existing handlers which already enforce atomic scripts, idempotent guards, and undo-group transactions. The MCP layer is a thin protocol translation.

#### Resources — Scene State Exposure

Resources provide read-only browseable data. These map to existing introspection capabilities:

| URI | Description | Backed By |
|-----|-------------|-----------|
| `houdini://scene/info` | Hip file, frame range, FPS, statistics | `get_scene_info` handler |
| `houdini://scene/tree` | Full node hierarchy | `inspect_scene` handler |
| `houdini://node/{path}/parameters` | All parameter values for a node | `get_parm` / `inspect_node` |
| `houdini://node/{path}/attributes` | Geometry attribute metadata + samples | `inspect_node` handler |
| `houdini://node/{path}/cook-stats` | Cook time, memory, dependencies | `get_metrics` handler |
| `houdini://stage/info` | USD stage summary | `get_stage_info` handler |

URIs with `{path}` are resource templates — the client fills in the parameter.

#### Prompts — Reusable Workflows (Phase 2)

| Prompt | Description |
|--------|-------------|
| `vex_debug` | Inspect wrangle inputs, run code, check outputs |
| `lighting_setup` | Standard 3-point rig with proper exposure values |
| `scene_audit` | Check for unnamed nodes, missing textures, heavy geo |
| `render_validation` | Progressive render pipeline (low → high quality) |

#### JSON-RPC Error Codes

| Code | Meaning | When |
|------|---------|------|
| -32700 | Parse error | Invalid JSON |
| -32600 | Invalid Request | Missing jsonrpc/method |
| -32601 | Method not found | Unknown MCP method |
| -32602 | Invalid params | Bad tool arguments |
| -32603 | Internal error | Houdini crash, unexpected exception |
| -32001 | Safety guard rejection | Middleware blocked operation |
| -32002 | Node not found | Houdini path doesn't exist |
| -32003 | Cook error | Houdini cook failed |
| -32004 | Session invalid | Bad/expired Mcp-Session-Id |

#### File Organization

```
synapse/
├── mcp/                          # NEW — all MCP protocol code
│   ├── __init__.py
│   ├── server.py                 # Endpoint handler, JSON-RPC router, hwebserver registration
│   ├── session.py                # Session manager (create, track, destroy)
│   ├── tools.py                  # Tool registry (maps to existing handlers in handlers.py)
│   ├── resources.py              # Resource definitions and readers
│   ├── prompts.py                # Prompt templates (Phase 2)
│   ├── protocol.py               # JSON-RPC utilities, error codes, response builders
│   └── types.py                  # Type definitions, schemas
├── docs/
│   ├── mcp/
│   │   ├── SETUP.md              # User-facing MCP connection guide
│   │   └── TOPS_INTEGRATION_POINTS.md  # Notes for TOPS resumption (append-only)
│   └── tops/
│       └── PARKING_SNAPSHOT.md   # TOPS state at time of parking
```

#### Connecting Claude Code

Once the endpoint is running:

```bash
# One-time setup
claude mcp add --transport http synapse http://localhost:PORT/mcp

# Verify
claude mcp list
# Inside Claude Code session:
/mcp

# For team projects, add .mcp.json at repo root:
# { "synapse": { "type": "http", "url": "http://localhost:PORT/mcp" } }
```

#### Security

- **Localhost binding only** by default (`127.0.0.1`, not `0.0.0.0`). Claude Code runs locally.
- **No auth for local** — MCP spec permits authless localhost. Bearer token auth is opt-in (Phase 3) for remote/studio deployment.
- **Origin validation** — validate `Origin` header per MCP spec to mitigate DNS rebinding.
- **Cloud context awareness** — Claude Code sends tool results to Anthropic's API. Scene data (node names, attribute values) transits cloud infrastructure. Document this for users with proprietary scenes.

#### SDK vs. Manual Implementation

Two approaches available:

**Option A — Python MCP SDK (`pip install mcp`):** Handles all protocol plumbing (JSON-RPC, sessions, capabilities). Use `from mcp.server.fastmcp import FastMCP` with `@mcp.tool()` decorators. Trade-off: introduces an external dependency and its own HTTP server — evaluate whether it integrates cleanly with hwebserver or conflicts.

**Option B — Manual implementation:** Build the JSON-RPC router directly on hwebserver. More control, zero new dependencies, but more boilerplate.

**Recommended:** Try the SDK first. If hwebserver integration is clean, use it. If not, fall back to manual. Either way, the dispatch layer delegates to existing handlers — the protocol plumbing is the only variable.

### `.synapse` Companion Repos

**Agent SDK** (`~/.synapse/agent/`): Autonomous VFX co-pilot powered by Claude Opus 4.6. Standard Anthropic tool-use message loop (NOT a separate agent framework). 8 tools via direct WebSocket to Synapse. Safety: atomic mutations, idempotent guards, undo-group rollback. 49 tests.

**Design System** (`~/.synapse/design/`): Pentagram-style monochromatic design. `tokens.py` (colors, typography, spacing — stdlib-only), `generate_icons.py` (21 SVGs from construction rules), `synapse_styles.py` (Qt stylesheet generator). Primary accent: SIGNAL cyan `#00D4FF`.

**Houdini Integration** (`~/.synapse/houdini/`): `synapse.shelf` (5 toolbar tools), `synapse_shelf.py` (shelf callbacks — inspect, health check, docs), `synapse_panel.pypanel` (PySide2 panel with status polling).

**Installer** (`~/.synapse/install.py`): Auto-detects Houdini prefs dir, copies shelf/panel/icons. Flags: `--dry-run`, `--verify`, `--uninstall`.

## Testing Patterns

**No Houdini required**: All tests import modules via `importlib.util.spec_from_file_location`, bypassing the `hou` dependency. There is no shared `conftest.py` — each test file creates its own minimal `hou` stub inline via `sys.modules["hou"] = mock_hou`. Some test files (e.g., `test_guards.py`, `test_keyframe_aov.py`) save and restore the original `sys.modules["hou"]` in teardown to prevent cross-test pollution.

**Patching `hou` in handler tests**: Always patch the module-level reference inside handlers.py, NOT `sys.modules["hou"]`. Patching sys.modules breaks object identity across test files.

```python
# Correct — patch the handlers module's hou reference
_handlers_hou = handlers_mod.hou
with patch.object(_handlers_hou, "node", return_value=mock_node):
    ...

# For attributes missing from the stub
with patch.object(hou, "flipbook", create=True):
    ...
```

**test_guards.py ordering**: Replaces `sys.modules["hou"]` entirely — has save/restore teardown to prevent pollution. `test_render.py` captures `_handlers_hou = handlers_mod.hou` to patch the correct object.

**Error assertions**: Use `"Couldn't find"` (not `"not found"`) — matches coaching tone convention.

**Windows encoding**: Any test writing files with em-dashes or special chars must use `encoding="utf-8"` (cp1252 breaks).

**MCP protocol tests**: Test the JSON-RPC router, session management, tool dispatch, and resource reading without Houdini. Mock the handler registry to return canned responses. Verify correct error codes, header handling (`Mcp-Session-Id`, `MCP-Protocol-Version`), and content-type negotiation. Follow the same stub pattern as existing tests.

## Adding New Functionality

### Adding a new MCP tool

1. Add `CommandType` variant in `core/protocol.py`
2. Add handler method `_handle_<name>` in `server/handlers.py` and register it in `SynapseHandler._register_handlers()`
3. Add parameter aliases in `core/aliases.py` if the tool has new parameter names
4. Add `Tool(...)` entry to `list_tools()` and dispatch case to `call_tool()` in `mcp_server.py` (uses `Server.list_tools()`/`Server.call_tool()` decorators, not `@mcp.tool()` decorator pattern). All 38 tools defined in one `list_tools()` function with a single `call_tool()` switch
5. **Add MCP tool definition in `mcp/tools.py`** — include `inputSchema` (JSON Schema for arguments) and `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). The tool dispatches to the same handler registered in step 2.
6. Add timeout override to `_SLOW_COMMANDS` in `mcp_server.py` if >10s expected
7. Write tests — bootstrap a `hou` stub inline via `sys.modules`, import handlers via `importlib`, patch `_handlers_hou` (not `sys.modules["hou"]`). **Also write a test in `test_mcp_protocol.py`** verifying the tool appears in `tools/list` and `tools/call` dispatches correctly.

**Going forward, steps 5 and 7 (MCP registration + MCP test) are mandatory for all new tools.** The MCP tool registry is now the standard way to expose SYNAPSE functionality to external clients.

### Adding a routing recipe

Add to `routing/recipes.py` in the `_register_builtins()` method. 21 recipes (11 basic + 10 production). Recipes are Tier 0.5 — pattern-matched before regex, return multi-step command sequences. For complex workflows, use `execute_python` steps. For dynamic composition with modifiers ("set up X with Y and Z"), add workflow templates to `routing/planner.py`.

### Adding RAG knowledge

Add/edit files in `rag/skills/houdini21-reference/*.md` (26 files, ~3,900 lines). Update topic triggers in `rag/documentation/_metadata/semantic_index.json` (28 topics, 400+ triggers).

## Key Conventions

**Coaching tone**: Error messages say "Couldn't find node" not "Node not found". Always offer next step. `_suggest_parms(node, name)` provides substring-matched alternatives. See `TONE.md` for the full voice guide.

**He2025 determinism**: `round_float()` for OUTPUT only — never internal timing. `sort_keys=True` in all JSON serialization (both stdlib `json.dumps` and `orjson.OPT_SORT_KEYS`). `@deterministic` decorator auto-rounds float args. `kahan_sum()` for stable aggregation. Content-based UUIDs via `deterministic_uuid()`. Epoch-based adaptation uses fixed epoch SIZE (not time-based) per He2025.

**Lazy loading**: `__init__.py` uses `__getattr__` to defer routing/server/UI imports. Optional deps use try/except with `*_AVAILABLE` flags. Keeps Houdini startup fast.

**Thread safety**: `ReadWriteLock` (writer-priority) in `MemoryStore`. `threading.Lock()` for tier-pin cache. `threading.Event()` for background store loading. `_log_executor` ThreadPoolExecutor(2) for fire-and-forget memory logging.

**Backwards compat**: All legacy names preserved — `NexusServer`, `EngramMemory`, `HyphaeAuditLog`, etc. Storage auto-migrates from `.nexus/`/`.engram/` to `.synapse/`.

**Singletons**: `AuditLog`, `HumanGate`, `SynapseBridge`, `CryptoEngine` — accessed via `audit_log()`, `human_gate()`, `get_bridge()`, `get_crypto()`.

**Error classification**: User errors (`ValueError`, `KeyError`, `AttributeError`, `TypeError`, `IndexError`, `NameError`) do NOT trip circuit breaker. Service errors (`TimeoutError`, threading errors, Houdini crashes) DO trip it.

**Rollback errors in execute_python**: `_ROLLBACK_ERRORS = (NameError, SyntaxError, TypeError, AttributeError, IndexError)` trigger auto-undo. Operational errors (RuntimeError, hou.OperationFailed) do NOT — earlier mutations may be valid.

## Lighting Law (Critical Domain Knowledge)

**Intensity is ALWAYS 1.0 (or below)**. Brightness is controlled by **exposure** (logarithmic, in stops). This applies to ALL PBR renderers (Karma, Arnold, RenderMan, V-Ray).

- Key:fill ratio 3:1 = 1.585 stops difference (`log2(3)`)
- Key:fill ratio 4:1 = 2.0 stops difference (`log2(4)`)
- USD exposure parm: `xn__inputsexposure_vya` (value), `xn__inputsexposure_control_wcb` = `"set"` (enable)
- USD intensity parm: `xn__inputsintensity_i0a` — always 1.0

## Rendering Guidelines

When building or rendering Solaris scenes via MCP, follow a progressive validation pipeline — never jump straight to production settings:

1. **Validate stage first**: After creating geometry, lights, and materials, query the stage to confirm all expected prims exist at correct paths. Use exact prim paths for material assignments (not wildcard patterns like `/**` unless verified).
2. **Test render at low quality**: Start with 256x256 resolution, low pixel samples (4-8), no SSS, no displacement, no denoiser. Confirm the render completes and produces output before scaling up.
3. **Scale incrementally**: Increase resolution and samples in steps. Enable expensive features (SSS, subsurface scattering, denoiser) one at a time.
4. **Never use foreground rendering for heavy scenes**: `soho_foreground=1` blocks Houdini entirely — if the render is slow, the WebSocket server becomes unresponsive and the user must force-kill Houdini.
5. **Verify output paths**: Set `picture` on the Karma LOP AND `outputimage` on the ROP. Check the output directory exists. Use `iconvert.exe` from `$HFS/bin/` for EXR-to-JPEG conversion.

## Wire Protocol

Default: `ws://localhost:9999/synapse` | Version: `4.0.0`
MCP endpoint: `http://localhost:PORT/mcp` | Protocol: MCP 2025-06-18 (Streamable HTTP)

39 registered handlers: `ping`, `get_health`, `get_help`, `create_node`, `delete_node`, `connect_nodes`, `get_parm`, `set_parm`, `get_scene_info`, `get_selection`, `execute_python`, `execute_vex`, `get_stage_info`, `get_usd_attribute`, `set_usd_attribute`, `create_usd_prim`, `modify_usd_prim`, `capture_viewport`, `render`, `wedge`, `reference_usd`, `set_keyframe`, `render_settings`, `create_material`, `assign_material`, `read_material`, `knowledge_lookup`, `inspect_selection`, `inspect_scene`, `inspect_node`, `batch_commands`, `get_metrics`, `router_stats`, `list_recipes`, `context`, `search`, `add_memory`, `decide`, `recall`

All 39 handlers are accessible through both the WebSocket transport and the MCP Streamable HTTP transport. Parameter names resolve through `aliases.py` (38+ mappings) — e.g., `node`, `path`, `node_path` all resolve to canonical `node`.

## Storage Layout

```
$HIP/.synapse/           # Per-project memory
  memory.jsonl           # Append-only log (async write buffer: 2s flush / 50-item cap / atexit flush)
  index.json             # Search indices (by_type, by_tag, by_keyword)
  context.md             # Human-editable shot context
  decisions.md           # Decision log
  tasks.md               # Task history

~/.synapse/              # Global
  audit/                 # Daily JSONL audit logs (hash-chain, tamper-evident)
  gates/                 # Gate proposals (timestamped, immutable)
  encryption.key         # Auto-generated Fernet key (AES-128-CBC + HMAC-SHA256)
  agent/                 # Autonomous agent SDK (synapse_agent.py entry point)
  design/                # Design tokens, icon generator, Qt styles
  houdini/               # Shelf, panel, callbacks for Houdini integration
  install.py             # Houdini prefs installer
```

## Gotchas

- **matlib.cook(force=True)**: MUST cook materiallibrary before `createNode()` on shader child — without cook, internal subnet doesn't exist and createNode returns None
- **Render output_file kwarg**: Doesn't work for usdrender ROPs — set `outputimage` or `picture` parm directly
- **usdrender loppath**: ROPs in `/out` need `loppath` set to a LOP node — handler auto-discovers display node in `/stage`
- **Karma camera**: Must use USD prim path (`/cameras/render_cam`), not Houdini node path
- **override_res**: String menu `""` / `"scale"` / `"specific"` — not int
- **Viewport capture**: Must use Flipbook API with `hdefereval.executeInMainThreadWithResult()` — `QWidget.grab()` returns black for OpenGL; `executeDeferred()` is fire-and-forget and won't block
- **.pypanel imports**: NEVER nuke `sys.modules` — use `hou.session` guard for one-time import
- **RAG Path import**: Handler uses `from pathlib import Path as _Path` (inline) — global `Path` not available in handlers.py
- **MCP execute_python**: MCP param is `code`, but Synapse handler resolves `content` — payload builder in mcp_server.py maps it
- **SVG icon generation**: XML forbids `--` inside comments; use `|` separator
- **synapse_shelf.py**: Security hooks block `parm.eval()` patterns; use `node.evalParm("parm_name")` method instead
- **Agent SDK websockets**: Must import at module level (not inside connect()) — patch target is `synapse_ws.websockets`
- **Zombie servers**: Multiple SynapseServer instances can linger in Houdini; use `gc.get_objects()` + `_actual_port` to find the active one
- **MCP tool registration (stdio bridge)**: Uses `@server.list_tools()` returning `Tool(...)` list + `@server.call_tool()` dispatcher — NOT the `@mcp.tool()` decorator pattern. All 38 tools defined in one `list_tools()` function with a single `call_tool()` switch
- **MCP tool registration (Streamable HTTP)**: Uses the tool registry in `mcp/tools.py` which maps to the same handlers. Both registries must stay in sync — when adding a tool to `mcp_server.py`, also add it to `mcp/tools.py`
- **MCP session headers**: `Mcp-Session-Id` must be returned on the `initialize` response and included by the client on all subsequent requests. hwebserver header access may require case-insensitive lookup
- **MCP notifications return 202**: `notifications/initialized` and other notification methods return HTTP 202 Accepted with empty body — NOT 200 with a JSON-RPC response
- **MCP protocol version header**: Clients may send `MCP-Protocol-Version` header. If present and unsupported, respond with 400 Bad Request per spec
- **SYNAPSE_PATH env var**: Controls WebSocket path segment (default `/synapse`). `SYNAPSE_PORT` controls port (default `9999`). Full URL: `ws://localhost:{SYNAPSE_PORT}{SYNAPSE_PATH}`
- **orjson optional**: `protocol.py` and `mcp_server.py` use `orjson` for fast JSON with `OPT_SORT_KEYS` when installed, auto-fallback to stdlib `json`