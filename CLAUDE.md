# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse is the AI-Houdini Bridge — a standalone Python package (zero required dependencies) bridging AI assistants to SideFX Houdini via WebSocket. Core capabilities: real-time scene manipulation, persistent project memory, tiered LLM routing, and an MCP server exposing 34 tools to Claude Desktop/Code.

Lineage: Extracted from Nexus (RadiantSuite) + Engram (Hyphae) → self-contained package. Hyphae core (determinism, audit, gates) absorbed in v4.1.0. Agent layer v4.2.0. Encryption + He2025 determinism v4.2.1.

## Development Commands

```bash
# Run all tests (~563 tests, no Houdini required)
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_routing.py -v      # Routing cascade (~323 tests)
python -m pytest tests/test_materials.py -v     # Material tools (19 tests)
python -m pytest tests/test_render.py -v        # Render pipeline
python -m pytest tests/test_introspection.py -v # Scene inspection
python -m pytest tests/test_core.py -v          # Determinism, audit, gates
python -m pytest tests/test_agent.py -v         # Agent protocol, executor
python -m pytest tests/test_resilience.py -v    # Rate limiter, circuit breaker
python -m pytest tests/test_crypto.py -v        # Encryption, kahan_sum
python -m pytest tests/test_pipeline_efficiency.py -v  # Pipeline efficiency (35 tests)

# Single test
python -m pytest tests/test_routing.py::test_routing_benchmark -v

# Install for development
pip install -e ".[dev]"

# With optional features
pip install -e ".[dev,websocket,mcp]"
```

**CI**: GitHub Actions on Python 3.11 + 3.14, runs `python -m pytest tests/ -v --tb=short`.

## Architecture

```
python/synapse/
├── core/               # Foundation: protocol, determinism, audit, gates, crypto, aliases
├── routing/            # Tiered LLM dispatch: cache → regex → RAG → Haiku → agent
├── memory/             # Persistent storage: JSONL store, markdown sync, shot context
├── agent/              # Agentic execution: task→plan→step lifecycle, outcome tracking
├── server/             # WebSocket bridge + resilience + introspection + materials
├── session/            # Session tracking (SynapseBridge hub), summaries
└── ui/                 # Qt panel (5 tabs: connection, context, decisions, activity, search)

mcp_server.py           # MCP bridge: Claude Desktop ←[stdio]→ mcp_server ←[WebSocket]→ Houdini
houdini/                # .pypanel for Houdini integration
rag/                    # Knowledge base: 13 topics, semantic index, reference files
```

### Key Data Flows

**MCP Tool Call**: Claude → stdio/JSON-RPC → `mcp_server.py` → WebSocket → `SynapseServer` → `handlers.py` → `hou.*` → response

**Routing Cascade** (tiered, cheapest-first):
```
Cache(O(1)) → Recipe(O(1)) → Tier0/regex(O(n)) → Tier1/RAG(O(log n)) → Tier2/Haiku(~5s) → Tier3/Agent(~15s)
```

**Memory Persistence**: `MemoryStore` → async write buffer (2s flush / 50-item cap / atexit flush) → `$HIP/.synapse/memory.jsonl` + `index.json`

### Transport Backends

| Backend | Module | Use Case |
|---------|--------|----------|
| `websockets` | `server/websocket.py` | Primary — lower latency for reads/pings |
| `hwebserver` | `server/hwebserver_adapter.py` | Houdini's native C++ server — better for `hou.*` mutations |

hwebserver routes through Houdini's main event loop (~2s floor per message). websockets wins for everything except hou.* mutations. Both share the same handler layer.

## Testing Patterns

**No Houdini required**: All tests import modules directly via `importlib.util.spec_from_file_location`, bypassing the `hou` dependency.

**Patching `hou`**: Handler tests patch `handlers_mod.hou` (the module-level reference inside handlers.py), NOT `sys.modules["hou"]`. Patching sys.modules breaks object identity across test files.

```python
# Correct pattern for handler tests
_handlers_hou = handlers_mod.hou
with patch.object(_handlers_hou, "node", return_value=mock_node):
    ...

# For attributes that don't exist on the stub
with patch.object(hou, "flipbook", create=True):
    ...
```

**test_guards.py ordering**: Replaces `sys.modules["hou"]` — has save/restore teardown to avoid polluting other test files.

**Error message assertions**: Use `"Couldn't find"` (not `"not found"`) — matches the coaching tone convention.

**Encoding**: Any test writing files with special characters (em-dashes, etc.) must use `encoding="utf-8"` on Windows (cp1252 breaks).

## Key Conventions

**Coaching tone**: Error messages say "Couldn't find node" not "Node not found". Always offer a next step. Smart suggestions via `_suggest_parms(node, name)` provide substring-matched alternatives.

**He2025 determinism**: `round_float()` is for OUTPUT only — never apply to internal timing. `sort_keys=True` in all JSON serialization. `@deterministic` decorator auto-rounds float args.

**Lazy loading**: Heavy modules (routing, server, UI) lazy-loaded via `__getattr__` in `__init__.py`. Optional deps use try/except with `*_AVAILABLE` flags.

**Thread safety**: `ReadWriteLock` (writer-priority) for `MemoryStore`, `threading.Lock()` for tier-pin cache, `threading.Event()` for background loading in `store.py`.

**Backwards compatibility**: All legacy names preserved as aliases — `NexusServer`, `EngramMemory`, `HyphaeAuditLog`, etc. Storage migration from `.nexus/`/`.engram/` to `.synapse/` is automatic.

**Singletons**: `AuditLog`, `HumanGate`, `SynapseBridge`, `CryptoEngine` — accessed via `audit_log()`, `human_gate()`, `get_bridge()`, `get_crypto()`.

## Wire Protocol

**Default**: `ws://localhost:9999/synapse` | **Version**: `4.0.0`

Command types: `create_node`, `delete_node`, `connect_nodes`, `get_parm`, `set_parm`, `get_scene_info`, `get_selection`, `execute_python`, `execute_vex`, `create_usd_prim`, `modify_usd_prim`, `get_usd_attribute`, `set_usd_attribute`, `get_stage_info`, `capture_viewport`, `render`, `set_keyframe`, `render_settings`, `wedge`, `reference_usd`, `create_material`, `assign_material`, `read_material`, `knowledge_lookup`, `inspect_selection`, `inspect_scene`, `inspect_node`, `batch_commands`, `context`, `search`, `add_memory`, `decide`, `recall`, `ping`, `get_health`

## MCP Server (`mcp_server.py`)

34 tools bridging Claude to Houdini. Key config:
- `COMMAND_TIMEOUT=10.0` (default), `_SLOW_COMMANDS` override: execute/inspect → 30s, render/wedge → 120s, batch → 60s
- Concurrent dispatch: `_pending` dict + `_recv_loop` enables true parallel MCP tool calls (no `_cmd_lock`)
- Warmup pre-connect in `main()` reduces first-call latency
- `MAX_RETRIES=2`, `RETRY_DELAY=0.3`, auto-retry on connection drop
- `open_timeout=3.0` (hwebserver handshake ~2s), `ping_interval=None`, `compression=None` (localhost)

## Error Classification

**User errors** (do NOT trip circuit breaker): `ValueError`, `KeyError`, `AttributeError`, `TypeError`, `IndexError`, `NameError`

**Service errors** (DO trip circuit breaker): `TimeoutError`, threading errors, Houdini crashes

## Storage Layout

```
$HIP/.synapse/           # Per-project memory
├── memory.jsonl         # Append-only log
├── index.json           # Search indices (by_type, by_tag, by_keyword)
├── context.md           # Human-editable shot context
├── decisions.md         # Decision log
└── tasks.md             # Task history

~/.synapse/              # Global (audit, gates, keys)
├── audit/               # Daily JSONL audit logs
├── gates/               # Gate proposals
└── encryption.key       # Auto-generated Fernet key
```

## Gotchas

- **matlib.cook(force=True)**: MUST cook materiallibrary before `createNode()` on shader child — without cook, internal subnet doesn't exist
- **Render `output_file` kwarg**: Doesn't work for usdrender ROPs — set `outputimage` or `picture` parm directly
- **usdrender `loppath`**: ROPs in `/out` need `loppath` set to a LOP node — handler auto-discovers display node in `/stage`
- **Karma camera**: Must use USD prim path (`/cameras/render_cam`), not Houdini node path
- **`override_res`**: String menu `""` / `"scale"` / `"specific"` — not int
- **Viewport capture**: Must use Flipbook API with `hdefereval.executeInMainThreadWithResult()` — `QWidget.grab()` returns black for OpenGL
- **`.pypanel` imports**: NEVER nuke `sys.modules` — use `hou.session` guard for one-time import
- **RAG Path import**: Handler uses `from pathlib import Path as _Path` (inline) — global `Path` not available in handlers.py
