# Synapse Codebase Inventory

**Version:** 5.4.0 | **Protocol:** v4.0.0 (WS) / v5.0.0 (MCP bridge) / MCP 2025-06-18 (HTTP)
**Location:** `C:/Users/User/Synapse/` | **License:** MIT
**Updated:** 2026-02-15

---

## Architecture

```
Claude Desktop/Code (stdio) --> mcp_server.py (43 tools, v2 latency)
                                     |
ANY MCP Client (HTTP) ---------> synapse/mcp/ (Streamable HTTP)
                                     |
                              WebSocket ws://localhost:9999/synapse
                                     |
                              SynapseServer (daemon thread in Houdini)
                                     |
                              hou.* Python API --> Houdini USD Stage / Karma XPU
```

**Routing cascade (cheapest-first):**
```
Cache(O(1)) -> Recipe(O(1)) -> Planner(O(1)) -> Tier0/regex -> Tier1/RAG -> Tier2/Haiku -> Tier3/Agent
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Python source files | 67 |
| Source lines | ~25,500 |
| Test files | 40 |
| Test lines | ~18,900 |
| Tests | ~1,012 |
| MCP tools (stdio) | 43 |
| MCP tools (HTTP) | In mcp/tools.py |
| Command handlers | 39 |
| Recipes | 21 (11 basic + 10 production) |
| RAG knowledge files | 94 |
| Documentation files | 43 |
| SVG icons | 18 |
| Houdini shelf tools | 7 |
| UI tabs | 5 |

---

## Package Layout (python/synapse/)

### Core (9 files, ~2,240 lines)
| File | Lines | Role |
|------|-------|------|
| `protocol.py` | 222 | CommandType enum, SynapseCommand/Response wire format |
| `aliases.py` | 224 | Parameter name resolution (38+ mappings) |
| `audit.py` | 404 | Hash-chain append-only audit log, tamper detection |
| `determinism.py` | 367 | round_float, deterministic_uuid, kahan_sum, @deterministic |
| `gates.py` | 578 | Human-in-the-loop (INFORM/REVIEW/APPROVE/CRITICAL) |
| `queue.py` | 93 | DeterministicCommandQueue (He2025 batch invariance) |
| `crypto.py` | 142 | Fernet encryption (AES-128-CBC + HMAC-SHA256) |
| `errors.py` | 91 | Exception hierarchy |

### Server (23 files, ~9,720 lines)
| File | Lines | Role |
|------|-------|------|
| `handlers.py` | 1,004 | CommandHandlerRegistry (39 handlers, main dispatch) |
| `handlers_render.py` | 2,158 | Karma/Mantra/viewport pipeline (largest file) |
| `handlers_usd.py` | 352 | USD/Solaris handlers |
| `handlers_node.py` | 132 | Node CRUD handlers |
| `handlers_memory.py` | 187 | Memory handlers |
| `websocket.py` | 654 | SynapseServer (WebSocket transport) |
| `resilience.py` | 885 | RateLimiter, CircuitBreaker, Watchdog |
| `introspection.py` | 417 | inspect_scene, inspect_node, inspect_selection |
| `render_farm.py` | 514 | Render farm orchestration |
| `render_diagnostics.py` | 368 | Frame validation (black, NaN, clipping, fireflies) |
| `render_notify.py` | 310 | Render completion notifications |
| `auth.py` | 123 | API key auth (hmac.compare_digest) |
| `rbac.py` | 209 | Role-based access control |
| `sessions.py` | 397 | Multi-user session management |
| `guards.py` | 215 | Safety guard functions |
| `live_metrics.py` | 386 | Live metrics aggregator |
| `dashboard.py` | 326 | Embedded web dashboard |
| `metrics.py` | 122 | Prometheus metrics |
| `api_adapter.py` | 455 | REST adapter (optional) |
| `hwebserver_adapter.py` | 313 | Houdini native HTTP transport |
| `main_thread.py` | 70 | Main thread dispatcher for hou.* mutations |
| `start_hwebserver.py` | 51 | hwebserver startup |

### Routing (9 files, ~5,300 lines)
| File | Lines | Role |
|------|-------|------|
| `router.py` | 886 | TieredRouter (6-tier cascade, tier pinning, speculative T0+T1) |
| `recipes.py` | 1,993 | RecipeRegistry (21 recipes) |
| `planner.py` | 613 | Workflow planner with modifier composition |
| `knowledge.py` | 456 | KnowledgeIndex (inverted keyword RAG) |
| `vex_diagnostics.py` | 593 | VEX error analysis and suggestions |
| `parser.py` | 345 | CommandParser (regex, Tier 0) |
| `cache.py` | 185 | ResponseCache (deterministic LRU, per-tier TTL) |
| `adaptation.py` | 183 | Epoch-based tier adaptation (He2025) |

### Memory (10 files, ~4,250 lines)
| File | Lines | Role |
|------|-------|------|
| `store.py` | 949 | SynapseMemory (JSONL, ReadWriteLock, async write buffer) |
| `scene_memory.py` | 843 | Living Memory (scene-aware persistence) |
| `sqlite_store.py` | 733 | SQLite backend (SYNAPSE_MEMORY_BACKEND=sqlite) |
| `evolution.py` | 408 | Charmander -> Charmeleon -> Charizard evolution |
| `markdown.py` | 489 | MarkdownSync (context.md, decisions.md) |
| `models.py` | 313 | Memory, MemoryType, MemoryTier, MemoryQuery |
| `agent_state.py` | 253 | Agent state USD prims |
| `patterns.py` | 120 | Memory pattern matching |
| `context.py` | 65 | ShotContext helpers |

### MCP Layer (6 files, ~1,570 lines) -- Streamable HTTP
| File | Lines | Role |
|------|-------|------|
| `server.py` | 416 | /mcp endpoint, JSON-RPC 2.0 router |
| `tools.py` | 717 | Tool registry mapping to existing handlers |
| `resources.py` | 183 | Scene state resources (houdini://scene/*) |
| `protocol.py` | 155 | JSON-RPC utilities, error codes |
| `session.py` | 89 | MCP session manager (Mcp-Session-Id) |

### Agent (4 files, ~880 lines)
| File | Lines | Role |
|------|-------|------|
| `executor.py` | 309 | prepare -> propose -> execute -> learn lifecycle |
| `protocol.py` | 331 | AgentTask, AgentPlan, AgentStep |
| `learning.py` | 194 | OutcomeTracker (feedback memories) |

### Session (3 files, ~720 lines)
| File | Lines | Role |
|------|-------|------|
| `tracker.py` | 599 | SynapseBridge singleton hub |
| `summary.py` | 87 | Session summary generation |

### UI (8 files, ~1,350 lines)
- `panel.py` (385) -- SynapsePanel (Qt, 5 tabs)
- `tabs/` -- connection, context, decisions, activity, search

---

## MCP Bridge (mcp_server.py) -- 1,931 lines, 43 tools

stdio JSON-RPC bridge spawned by Claude Desktop/Code. Connects to Houdini via WebSocket.

### Tool Categories

| Category | Count | Tools |
|----------|-------|-------|
| System | 2 | ping, health |
| Scene | 2 | scene_info, get_selection |
| Nodes | 3 | create_node, delete_node, connect_nodes |
| Params | 3 | get_parm, set_parm, set_keyframe |
| Execution | 2 | execute_python, execute_vex |
| USD/Solaris | 6 | stage_info, get/set_usd_attribute, create/modify_usd_prim, reference_usd |
| Materials | 3 | create_material, assign_material, read_material |
| Rendering | 4 | render, render_settings, wedge, capture_viewport |
| Render Farm | 3 | render_sequence, render_farm_status, validate_frame |
| TOPS/PDG | 14 | cook_node, get_work_items, dependency_graph, cook_stats, generate_items, configure_scheduler, cancel_cook, dirty_node, setup_wedge, batch_cook, query_items, cook_and_validate, diagnose, pipeline_status |
| Introspection | 3 | inspect_selection, inspect_scene, inspect_node |
| Memory | 5 | context, search, recall, decide, add_memory |
| Living Memory | 5 | project_setup, memory_write, memory_query, memory_status, evolve_memory |
| Knowledge | 3 | knowledge_lookup, list_recipes, live_metrics |
| Routing | 2 | router_stats, metrics |
| Batch | 1 | batch |

### v2 Latency Optimizations (2026-02-15)
- **Auth skip:** saves ~2s when no key configured (check key first, skip recv wait)
- **orjson bytes passthrough:** _dumps returns bytes, websockets sends directly, .decode() only at TextContent
- **Lock-free fast path:** volatile _is_connected() check before acquiring _ws_lock
- **asyncio.wait():** replaces wait_for(), avoids internal task creation
- **Recv task lifecycle:** explicit cancel prevents race condition hangs
- **Fire-and-forget warmup:** server accepts tools immediately
- **max_size=None:** no frame size validation on localhost

### Timeout Tiers
| Category | Timeout |
|----------|---------|
| Default | 10s |
| execute_python/vex, inspect_*, capture_viewport | 30s |
| render, wedge, render_sequence | 120s |
| batch | 60s |

---

## Test Suite (40 files, ~18,900 lines, ~1,012 tests)

### Major Test Files
| File | Focus |
|------|-------|
| `test_routing.py` (1,376) | Routing cascade (~323 tests) |
| `test_tops.py` (1,531) | TOPS/PDG integration |
| `test_v5_features.py` (1,035) | v5 feature validation |
| `test_resilience.py` (874) | Rate limiter, circuit breaker |
| `test_agent.py` (879) | Agent protocol, executor |
| `test_scene_memory.py` (809) | Living Memory |
| `test_guards.py` (769) | Safety guards |
| `test_core.py` (695) | Determinism, audit, gates |
| `test_mcp_protocol.py` (669) | MCP Streamable HTTP |
| `test_pipeline_efficiency.py` (622) | RWLock, tier-pinning, batch (35 tests) |
| `test_sqlite_store.py` (589) | SQLite memory (40 tests) |
| `test_introspection.py` (556) | Scene inspection |
| `test_stress.py` (553) | Load/stress (24 tests) |
| `test_materials.py` (530) | Material tools (19 tests) |
| `test_frame_validator.py` (532) | Render validation |
| `test_integration_pipeline.py` (488) | Integration (20 tests) |
| `test_auth.py` (371) | Authentication (21 tests) |

---

## Key Design Principles

### Determinism (He2025-inspired)
- `sort_keys=True` in ALL JSON serialization (orjson + stdlib)
- Content-based UUIDs via deterministic_uuid() (SHA-256)
- round_float() for OUTPUT only (Decimal, ROUND_HALF_UP)
- kahan_sum() for stable float aggregation
- Response queue sorted by (sequence, id) -- batch invariance
- Timestamp preservation: 0.0 sentinel in deserialization
- Epoch adaptation: fixed epoch SIZE (not time-based)

### Safety Stack
- Atomic scripts: all mutations in undo groups
- Idempotent guards: repeat calls = same result
- Human gates: INFORM / REVIEW / APPROVE / CRITICAL
- Circuit breaker: trips on service errors only
- Rate limiter: token bucket per transport
- Auto-rollback: NameError/SyntaxError/TypeError in execute_python

### Coaching Tone
- "Couldn't find" not "not found"
- "We hit a snag" not "error"
- Always offer next step
- _suggest_parms() provides fuzzy alternatives

### Lighting Law (VFX Domain -- Never Violate)
- Intensity ALWAYS 1.0 -- brightness via exposure (stops)
- Key:fill 3:1 = 1.585 stops, 4:1 = 2.0 stops
- USD parms: `xn__inputsexposure_vya` (value), `xn__inputsexposure_control_wcb` = "set"

---

## Sprint Roadmap (Auto-Detected via Filesystem Gates)

| Sprint | Status | What |
|--------|--------|------|
| A: MCP Protocol | Done | Streamable HTTP, JSON-RPC 2.0, /mcp endpoint |
| B: TOPS/PDG | Done | 14 TOPS tools, PDG scheduler, wedge, batch cook |
| C: Agent SDK v2 | Next | Multi-goal planner, checkpoint/resume, self-heal |
| D: Studio Deploy | Queued | RBAC, multi-user sessions, remote access |
| E: Monitoring | Queued | Live metrics dashboard, alerts, Prometheus |

---

## Companion Repos

### ~/.synapse/ (Agent SDK + Design + Houdini)
- **agent/** -- Autonomous VFX co-pilot (Claude Opus 4.6, 8 tools, 49 tests)
- **design/** -- Pentagram-style system (tokens, 18 SVGs, Qt styles, accent: #00D4FF)
- **houdini/** -- Shelf (7 tools) + panel (PySide2, 5 tabs)
- **install.py** -- Auto-detect Houdini prefs, deploy shelf/panel/icons

### RAG Knowledge (rag/)
- 94 markdown files (documentation/ + skills/houdini21-reference/)
- 28 Houdini topics, 400+ semantic triggers
- VEX/Python examples with difficulty ratings

---

## Storage Layout

```
$HIP/.synapse/           # Per-project memory
  memory.jsonl           # Append-only log (2s flush / 50-item cap)
  index.json             # Search indices
  context.md             # Human-editable shot context
  decisions.md           # Decision log

~/.synapse/              # Global
  audit/                 # Daily JSONL audit logs (hash-chain)
  gates/                 # Gate proposals (immutable)
  encryption.key         # Fernet key (auto-generated)
```

---

## Dependencies

**Core:** Zero required (stdlib only)

| Feature | Package | Version |
|---------|---------|---------|
| WebSocket | websockets | >=11.0 |
| Encryption | cryptography | >=41.0.0 |
| MCP | mcp | >=1.0.0 |
| LLM routing | anthropic | >=0.40.0 |
| Fast JSON | orjson | auto-detected |
| Dev/test | pytest | >=7.0 |

```bash
pip install -e ".[dev,websocket,mcp,routing,encryption]"
python -m pytest tests/ -v   # ~1,012 tests
```

---

## Platform

- Windows 11 Pro for Workstations
- AMD Threadripper PRO 7965WX (24C/48T)
- NVIDIA RTX 4090 (24GB VRAM)
- 128GB DDR5
- Python 3.14
- Houdini Indie (Solaris / Karma XPU)
- CI: GitHub Actions (Python 3.11 + 3.14)

---

## Performance

| Operation | Latency |
|-----------|---------|
| Ping (warm) | ~0.2ms |
| get_scene_info | ~2ms |
| get_parm | 1-3ms |
| create_node | 20-65ms |
| context (memory) | ~0.9ms |
| render (Karma 512x) | 2-5s |
| First connect (v2) | 50-200ms (was 2s+ in v1) |
