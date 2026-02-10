# Synapse Project Inventory

**Version:** 4.2.1 | **Protocol:** 4.0.0 | **Generated:** 2026-02-10

## Executive Summary

| Metric | Count |
|--------|-------|
| **Total Python files** | 92 |
| **Total lines of code** | ~22,000 |
| **MCP tools** | 34 |
| **Wire protocol commands** | 35 |
| **Total tests** | 563+ (484 core + 49 agent + 44 design, 5 skipped) |
| **RAG topics** | 13 |
| **Design icons** | 21 SVG (63 size variants) |
| **Parameter aliases** | 38+ |
| **Backwards-compat aliases** | 15+ |
| **Transport backends** | 2 (websockets primary, hwebserver optional) |
| **Python support** | 3.11, 3.14 |

---

## Repository Locations

| Component | Path |
|-----------|------|
| Core repository | `C:\Users\User\Synapse\` |
| Agent SDK | `C:\Users\User\.synapse\agent\` |
| Design system | `C:\Users\User\.synapse\design\` |
| Houdini integration | `C:\Users\User\.synapse\houdini\` |

---

## 1. Core Package (`python/synapse/`) — 44 files

### 1.1 Foundation (`core/`) — 8 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Lazy-load foundation modules | 20 |
| `protocol.py` | CommandType enum (35 types), SynapseCommand/Response dataclasses, wire format v4.0.0 | 350 |
| `aliases.py` | Parameter name aliasing (38+ mappings) | 180 |
| `determinism.py` | round_float, deterministic_uuid, kahan_sum, @deterministic decorator, DeterministicRandom | 420 |
| `audit.py` | AuditLog (hash-chain JSONL), AuditLevel/AuditCategory enums, daily rotation, tamper detection | 580 |
| `gates.py` | HumanGate (INFORM/REVIEW/APPROVE/CRITICAL), GateProposal, GateDecision | 550 |
| `crypto.py` | CryptoEngine (Fernet AES-128-CBC + HMAC-SHA256), optional encryption, key management | 420 |
| `queue.py` | DeterministicCommandQueue, ResponseDeliveryQueue | 180 |

### 1.2 Memory (`memory/`) — 5 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Memory layer public API | 30 |
| `models.py` | Memory, MemoryType, MemoryTier, MemoryLink, LinkType, MemoryQuery, MemorySearchResult | 350 |
| `store.py` | MemoryStore (JSONL + ReadWriteLock + async write buffer + search index), SynapseMemory | 900 |
| `context.py` | ShotContext, load/save/get/update context for project metadata | 350 |
| `markdown.py` | MarkdownSync (human-readable .md export), parse/render decisions | 480 |

### 1.3 Routing (`routing/`) — 6 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Routing layer public API | 40 |
| `parser.py` | CommandParser (regex Tier 0), 30+ patterns for common Houdini commands | 520 |
| `knowledge.py` | KnowledgeIndex (semantic Tier 1), RAG lookup from `rag/` dir | 380 |
| `recipes.py` | Recipe/RecipeStep/RecipeRegistry (multi-step sequences, Tier 0.5) | 340 |
| `cache.py` | ResponseCache (He2025 deterministic LRU with TTL) | 220 |
| `router.py` | TieredRouter, tier-pinning cache, speculative T0+T1 parallelism | 700 |

**Routing cascade:** Cache → Recipe → Tier 0 (regex) → Tier 1 (RAG) → Tier 2 (Haiku) → Tier 3 (agent)

### 1.4 Agent (`agent/`) — 4 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Agent layer public API | 20 |
| `protocol.py` | AgentTask, AgentPlan, AgentStep, StepStatus, PlanStatus, gate classification | 480 |
| `executor.py` | AgentExecutor (prepare→propose→execute→learn lifecycle), risk classification | 420 |
| `learning.py` | OutcomeTracker (feedback memories, outcome-based learning) | 180 |

### 1.5 Server (`server/`) — 8 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Server layer public API | 20 |
| `websocket.py` | SynapseServer (WebSocket daemon thread), client handling, command dispatch | 650 |
| `handlers.py` | CommandHandlerRegistry, **34 handlers**, coaching tone errors, `_suggest_parms()` | 2,100 |
| `resilience.py` | RateLimiter, CircuitBreaker, PortManager, Watchdog, BackpressureController, HealthMonitor | 1,250 |
| `introspection.py` | inspect_selection, inspect_scene, inspect_node_detail | 350 |
| `hwebserver_adapter.py` | Native C++ Houdini transport (Phase 3 alternative) | 280 |
| `api_adapter.py` | hwebserver.apiFunction adapters (16 endpoints) | 180 |
| `start_hwebserver.py` | hwebserver startup helper | 120 |

### 1.6 Session (`session/`) — 3 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | Session layer public API | 20 |
| `tracker.py` | SynapseBridge (singleton), SynapseSession, context cache (5s TTL) | 450 |
| `summary.py` | SessionSummary generation | 330 |

### 1.7 UI (`ui/`) — 7 files

| File | Purpose | ~LOC |
|------|---------|------|
| `__init__.py` | UI layer public API | 20 |
| `panel.py` | SynapsePanel (main Qt widget, 5 tabs) | 650 |
| `tabs/__init__.py` | Tab exports | 10 |
| `tabs/connection.py` | Connection tab (status, port, start/stop) | 180 |
| `tabs/context.py` | Context tab (shot metadata) | 90 |
| `tabs/decisions.py` | Decisions tab (history with reasoning) | 80 |
| `tabs/activity.py` | Activity tab (command log) | 70 |
| `tabs/search.py` | Search tab (memory queries) | 100 |

### 1.8 Package Root

| File | Purpose |
|------|---------|
| `python/synapse/__init__.py` | Lazy-loading via `__getattr__`, `*_AVAILABLE` feature flags |

---

## 2. MCP Server — 1 file, ~1,217 LOC

| File | Purpose |
|------|---------|
| `mcp_server.py` | Claude Desktop ←[stdio/JSON-RPC]→ mcp_server ←[WebSocket]→ Houdini |

### 34 MCP Tools

**Houdini Inspection (6):** `synapse_ping`, `synapse_health`, `houdini_scene_info`, `houdini_get_selection`, `houdini_get_parm`, `houdini_execute_python`

**Houdini Mutation (9):** `houdini_create_node`, `houdini_delete_node`, `houdini_connect_nodes`, `houdini_set_parm`, `houdini_set_keyframe`, `houdini_capture_viewport`, `houdini_reference_usd`, `houdini_render_settings`, `houdini_wedge`

**USD/Solaris (5):** `houdini_stage_info`, `houdini_get_usd_attribute`, `houdini_set_usd_attribute`, `houdini_create_usd_prim`, `houdini_modify_usd_prim`

**Materials (3):** `houdini_create_material`, `houdini_assign_material`, `houdini_read_material`

**Rendering (1):** `houdini_render`

**Introspection (3):** `synapse_inspect_selection`, `synapse_inspect_scene`, `synapse_inspect_node`

**Memory (6):** `synapse_context`, `synapse_search`, `synapse_recall`, `synapse_decide`, `synapse_add_memory`, `synapse_knowledge_lookup`

**Batch (1):** `synapse_batch`

### Timeout Configuration

| Category | Timeout |
|----------|---------|
| Default | 10.0s |
| execute_python, execute_vex, inspect_* | 30s |
| render, wedge | 120s |
| batch_commands | 60s |

---

## 3. Test Suite — 18 files, ~8,425 LOC

| File | Tests | Category |
|------|-------|----------|
| `test_routing.py` | ~323 | Parser, knowledge, recipes, cache, router cascade |
| `test_core.py` | ~45 | Protocol, determinism, audit, gates, crypto |
| `test_resilience.py` | ~40 | Rate limiter, circuit breaker, watchdog, backpressure |
| `test_knowledge.py` | ~35 | RAG, semantic index, topic coverage |
| `test_pipeline_efficiency.py` | 35 | RWLock, tier-pinning, T0+T1 parallel, batch, concurrent dispatch |
| `test_agent.py` | ~30 | Executor, learning, plan lifecycle |
| `test_render.py` | ~28 | Karma/Mantra pipeline, resolution, output |
| `test_introspection.py` | ~22 | Scene inspection, node detail |
| `test_materials.py` | 19 | MaterialX, shader binding |
| `test_tops_assembly.py` | ~18 | Wedging, parameter variation |
| `test_capture.py` | ~15 | Flipbook, viewport image |
| `test_guards.py` | ~15 | Gate levels, proposals |
| `test_keyframe_aov.py` | ~12 | Animation, AOV |
| `test_crypto.py` | ~25 | Encryption, He2025, kahan_sum |
| `test_load.py` | ~8 | Lazy-loading verification |
| `test_live_capture.py` | ~8 | Integration (skipped in CI) |
| `test_hwebserver_integration.py` | ~4 | Transport (skipped in CI) |
| `test_design_system.py` | 44 | Icons, tokens, styles |
| `conftest.py` | — | hou stub, backward-compat shims |

**Total:** 484 passed + 5 skipped (core) + 49 agent + 44 design = **563+ tests**

---

## 4. Agent SDK (`~/.synapse/agent/`) — 11 files, ~1,809 LOC

| File | Purpose | ~LOC |
|------|---------|------|
| `synapse_agent.py` | Entry point, Opus 4.6 agentic loop, max 30 turns | 420 |
| `synapse_ws.py` | WebSocket client (connection, message dispatch) | 280 |
| `synapse_tools.py` | 8 tool definitions for Claude tool_use | 350 |
| `synapse_hooks.py` | Safety hooks (pre-execution validation, undo protection) | 280 |
| `synapse_tone.py` | Coaching tone guide + validation | 220 |
| `CLAUDE.md` | Agent behavior guide | 340 |
| `requirements.txt` | anthropic>=0.75.0, websockets>=12.0, anyio>=4.0 | 3 |
| `tests/test_agent.py` | Agent loop tests | — |
| `tests/test_ws_client.py` | WebSocket client tests | — |
| `tests/test_tools.py` | Tool dispatch tests | — |
| `tests/test_hooks.py` | Safety hook tests | — |
| `tests/test_tone.py` | Voice validation tests | — |

**49 tests total**

---

## 5. Design System (`~/.synapse/design/`) — 4 files, ~1,038 LOC

| File | Purpose | ~LOC |
|------|---------|------|
| `tokens.py` | Design tokens (colors, typography, spacing, shadows) | 280 |
| `synapse_styles.py` | PySide2 Qt stylesheet generation | 320 |
| `generate_icons.py` | SVG icon generation (21 icons × 3 sizes) | 240 |
| `rasterize_icons.py` | SVG→PNG rasterization for Houdini | 198 |

**21 icons:** synapse, execute, inspect, verify, document, profile, construction, marks, etc.
**44 tests** in `test_design_system.py`

---

## 6. Houdini Integration (`~/.synapse/houdini/`)

| File | Purpose |
|------|---------|
| `python_panels/synapse.pypanel` | Primary panel definition (XML) |
| `python_panels/synapse_panel.pypanel` | Alternative panel config (XML) |
| `toolbar/synapse.shelf` | Shelf with quick-action buttons (XML) |
| `scripts/python/synapse_shelf.py` | Shelf script helpers (~160 LOC) |

---

## 7. RAG System (`rag/`) — 13 files

### Metadata

| File | Purpose |
|------|---------|
| `documentation/_metadata/semantic_index.json` | 13-topic keyword index (340+ triggers) |
| `documentation/_metadata/agent_relevance_map.json` | Agent→topic relevance scores |

### Reference Content (11 .md files, ~663 LOC)

| File | Topic |
|------|-------|
| `skills/houdini21-reference/sop_basics.md` | SOPs — geometry operations |
| `skills/houdini21-reference/solaris_nodes.md` | Solaris — USD/LOPs |
| `skills/houdini21-reference/solaris_parameters.md` | Solaris parameter names |
| `skills/houdini21-reference/rendering.md` | Karma, Mantra |
| `skills/houdini21-reference/lighting.md` | Area lights, domes, color |
| `skills/houdini21-reference/usd_operations.md` | USD composition, layer editing |
| `skills/houdini21-reference/pyro_fx.md` | Pyro simulation |
| `skills/houdini21-reference/rbd_simulation.md` | RBD simulation |
| `skills/houdini21-reference/flip_simulation.md` | FLIP simulation |
| `skills/houdini21-reference/tops_wedging.md` | TOPs, batch processing |
| `skills/houdini21-reference/scene_assembly.md` | References, layers |

---

## 8. Configuration & Documentation

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `.mcp.json` | Claude Code MCP project-level registration |
| `CLAUDE.md` | Development guidance for Claude Code (~400 lines) |
| `README.md` | User-facing documentation (~650 lines) |
| `TONE.md` | Coaching voice guide (~70 lines) |
| `LATENCY_PLAN.md` | Performance optimization roadmap (~250 lines) |
| `docs/He2025_CONSISTENCY_AUDIT.md` | He2025 alignment audit (93/100 score) |

---

## 9. Wire Protocol Commands (35)

**Node ops (4):** create_node, delete_node, modify_node, connect_nodes
**Parameters (2):** get_parm, set_parm
**Scene (3):** get_scene_info, get_selection, set_selection
**Execution (2):** execute_python, execute_vex
**USD (6):** create_usd_prim, modify_usd_prim, get_stage_info, get_usd_attribute, set_usd_attribute, reference_usd
**Rendering (5):** render, set_keyframe, render_settings, wedge, capture_viewport
**Materials (3):** create_material, assign_material, read_material
**Introspection (3):** inspect_selection, inspect_scene, inspect_node
**Memory (5):** context, search, add_memory, decide, recall
**Utility (3):** ping, get_health, knowledge_lookup
**Batch (1):** batch_commands

---

## 10. Storage Layout

```
$HIP/.synapse/           # Per-project memory
├── memory.jsonl         # Append-only log
├── index.json           # Search indices (by_type, by_tag, by_keyword)
├── context.md           # Human-editable shot context
├── decisions.md         # Decision log
└── tasks.md             # Task history

~/.synapse/              # Global (audit, gates, keys)
├── audit/               # Daily JSONL audit logs (hash-chain)
├── gates/               # Gate proposals (timestamped, immutable)
└── encryption.key       # Auto-generated Fernet key
```

---

## 11. Backwards Compatibility

| Legacy Name | Current Name |
|-------------|-------------|
| `NexusMemory` | `SynapseMemory` |
| `EngramMemory` | `SynapseMemory` |
| `NexusServer` | `SynapseServer` |
| `NexusSession` | `SynapseSession` |
| `NexusBridge` | `SynapseBridge` |
| `EngramBridge` | `SynapseBridge` |
| `HyphaeAuditLog` | `AuditLog` |
| `HyphaeGate` | `HumanGate` |
| `.nexus/` directory | auto-migrated to `.synapse/` |
| `.engram/` directory | auto-migrated to `.synapse/` |

---

## 12. Dependencies

**Core:** Zero required (stdlib only)

| Optional Feature | Package | Min Version |
|-----------------|---------|-------------|
| WebSocket server | websockets | >=11.0 |
| Encryption | cryptography | >=41.0.0 |
| MCP server | mcp | >=1.0.0 |
| Routing (LLM) | anthropic | >=0.40.0 |
| Fast JSON | orjson | auto-detected |
| Agent SDK | anthropic | >=0.75.0 |
| Development | pytest | >=7.0 |

---

## 13. Performance Benchmarks

| Operation | Latency |
|-----------|---------|
| Ping (warm) | 0.2ms |
| get_scene_info | 2.0ms |
| get_parm | 1-3ms |
| context (memory) | 0.9ms |
| create_node | 20-65ms |
| delete_node | 5-20ms |
| render (Karma 512x) | 2-5s |
| First connect (MCP) | 50-200ms |
