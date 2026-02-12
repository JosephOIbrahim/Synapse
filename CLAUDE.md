# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse v5.2.0 is an AI-Houdini Bridge — a standalone Python package (zero required dependencies) that lets AI assistants control SideFX Houdini via WebSocket. It exposes 43 MCP tools to Claude Desktop/Code for real-time scene manipulation, persistent project memory, adaptive tiered LLM routing, and viewport/render capture.

Two repos make up the full system:
- **`C:\Users\User\Synapse\`** — Core server, protocol, handlers, memory, routing, MCP bridge
- **`C:\Users\User\.synapse\`** — Agent SDK (autonomous co-pilot), design system (tokens/icons/styles), Houdini shelf/panel integration, installer

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
Claude Desktop/Code
    |  stdio / JSON-RPC
mcp_server.py  (43 tools, concurrent dispatch via _pending dict + _recv_loop)
    |  WebSocket: ws://localhost:9999/synapse
SynapseServer  (daemon thread inside Houdini)
    |  CommandHandlerRegistry (handlers.py)
hou.* Python API
    |
Houdini USD Stage / Solaris / Karma
```

### Core Package Layout (`python/synapse/`)

| Layer | Directory | Responsibility |
|-------|-----------|---------------|
| Foundation | `core/` | Wire protocol (`protocol.py`), parameter aliases (`aliases.py`), determinism (`determinism.py`), audit chain (`audit.py`), human gates (`gates.py`), encryption (`crypto.py`), command queue (`queue.py`) |
| Memory | `memory/` | JSONL store (`store.py`) or SQLite store (`sqlite_store.py`, via `SYNAPSE_MEMORY_BACKEND=sqlite`), data models (`models.py`), shot context (`context.py`), markdown export (`markdown.py`), **Living Memory**: scene memory (`scene_memory.py`), agent state USD (`agent_state.py`), evolution system (`evolution.py`) |
| Routing | `routing/` | Tiered LLM dispatch (`router.py`), regex parser (`parser.py`), RAG knowledge (`knowledge.py`), recipes (`recipes.py`), deterministic cache (`cache.py`), workflow planner (`planner.py`), epoch-based tier adaptation (`adaptation.py`) |
| Agent | `agent/` | prepare/propose/execute/learn lifecycle (`executor.py`), task/plan/step protocol (`protocol.py`), outcome tracking (`learning.py`) |
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

| Backend | Module | Latency | Use Case |
|---------|--------|---------|----------|
| `websockets` | `server/websocket.py` | ~0.2ms warm ping | Primary — reads, pings, everything |
| `hwebserver` | `server/hwebserver_adapter.py` | ~2s floor (main event loop) | Optional — only for hou.* mutations |

Both share the same handler layer. Decision: websockets is primary; hwebserver's 2s floor per message outweighs its benefits.

### Authentication (`server/auth.py`)

Optional API key authentication for both transports. Key sources (checked in order):
1. `SYNAPSE_API_KEY` environment variable
2. `~/.synapse/auth.key` file (first non-empty, non-comment line)
3. No key configured -> auth disabled (backward compat)

When enabled, first WebSocket message must be an `authenticate` command with `{"payload": {"key": "..."}}`. Uses `hmac.compare_digest` for constant-time comparison. Auth handshake integrated into both `websocket.py` and `hwebserver_adapter.py`.

### MCP Server (`mcp_server.py`)

38 tools. Key operational details:
- **Concurrent dispatch**: `_pending` dict + `_recv_loop` coroutine — no blocking lock, true parallel tool calls
- **Timeouts**: Default 10s. Overrides: execute_python/execute_vex/capture_viewport/inspect_* at 30s, render/wedge at 120s, batch at 60s
- **JSON**: Uses `orjson` (fast, sort_keys via `OPT_SORT_KEYS`) when available, falls back to stdlib `json`
- **Warmup**: Pre-connect in `main()` reduces first-call latency
- **Retry**: `MAX_RETRIES=2`, `RETRY_DELAY=0.3`, auto-retry on connection drop
- **Connection**: `open_timeout=3.0`, `ping_interval=None`, `compression=None` (localhost optimization)

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

## Adding New Functionality

### Adding a new MCP tool

1. Add `CommandType` variant in `core/protocol.py`
2. Add handler method `_handle_<name>` in `server/handlers.py` and register it in `SynapseHandler._register_handlers()`
3. Add parameter aliases in `core/aliases.py` if the tool has new parameter names
4. Add `Tool(...)` entry to `list_tools()` and dispatch case to `call_tool()` in `mcp_server.py` (uses `Server.list_tools()`/`Server.call_tool()` decorators, not `@mcp.tool()`)
5. Add timeout override to `_SLOW_COMMANDS` in `mcp_server.py` if >10s expected
6. Write tests — bootstrap a `hou` stub inline via `sys.modules`, import handlers via `importlib`, patch `_handlers_hou` (not `sys.modules["hou"]`)

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

39 registered handlers: `ping`, `get_health`, `get_help`, `create_node`, `delete_node`, `connect_nodes`, `get_parm`, `set_parm`, `get_scene_info`, `get_selection`, `execute_python`, `execute_vex`, `get_stage_info`, `get_usd_attribute`, `set_usd_attribute`, `create_usd_prim`, `modify_usd_prim`, `capture_viewport`, `render`, `wedge`, `reference_usd`, `set_keyframe`, `render_settings`, `create_material`, `assign_material`, `read_material`, `knowledge_lookup`, `inspect_selection`, `inspect_scene`, `inspect_node`, `batch_commands`, `get_metrics`, `router_stats`, `list_recipes`, `context`, `search`, `add_memory`, `decide`, `recall`

Parameter names resolve through `aliases.py` (38+ mappings) — e.g., `node`, `path`, `node_path` all resolve to canonical `node`.

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
- **MCP tool registration**: Uses `@server.list_tools()` returning `Tool(...)` list + `@server.call_tool()` dispatcher — NOT the `@mcp.tool()` decorator pattern. All 38 tools defined in one `list_tools()` function with a single `call_tool()` switch
- **SYNAPSE_PATH env var**: Controls WebSocket path segment (default `/synapse`). `SYNAPSE_PORT` controls port (default `9999`). Full URL: `ws://localhost:{SYNAPSE_PORT}{SYNAPSE_PATH}`
- **orjson optional**: `protocol.py` and `mcp_server.py` use `orjson` for fast JSON with `OPT_SORT_KEYS` when installed, auto-fallback to stdlib `json`
