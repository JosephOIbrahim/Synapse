# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse is the AI-Houdini Bridge — a standalone package providing:
- **Server**: WebSocket bridge for real-time command transmission with production resilience
- **Memory**: Persistent project memory ($HIP/.synapse/)
- **Session**: Session tracking with auto-summary generation
- **UI**: Qt panel with tabs for connection, context, decisions, activity, and search

Extracted from Nexus (RadiantSuite) and Engram (Hyphae) into a self-contained package.
Hyphae core (determinism, audit, gates) absorbed in v4.1.0.
Agent execution layer added in v4.2.0.
Encryption layer + He2025 determinism fixes added in v4.2.1.

## Development Commands

```bash
# Run all tests (without Houdini) — 187 tests
python -m pytest tests/ -v

# Individual test modules
python -m pytest tests/test_core.py -v        # Determinism, audit, gates
python -m pytest tests/test_agent.py -v       # Agent protocol, executor, learning
python -m pytest tests/test_resilience.py -v  # Rate limiter, circuit breaker, watchdog
python -m pytest tests/test_crypto.py -v      # Encryption, kahan_sum, decorator fix

# Install for development
pip install -e ".[dev]"

# Optional dependencies
pip install -e ".[websocket]"    # WebSocket server support
pip install -e ".[encryption]"   # Fernet encryption for data at rest
```

---

## Complete Index

### Public API (from `__init__.py`)

| Category | Exports |
|----------|---------|
| **Protocol** | `CommandType`, `SynapseCommand`, `SynapseResponse`, `PROTOCOL_VERSION`, `DeterministicCommandQueue`, `ResponseDeliveryQueue`, `PARAM_ALIASES`, `resolve_param`, `resolve_param_with_default` |
| **Determinism** | `DeterministicConfig`, `deterministic_uuid`, `round_float`, `kahan_sum`, `deterministic` |
| **Audit** | `AuditLog`, `AuditLevel`, `AuditCategory`, `AuditEntry`, `audit_log` |
| **Gates** | `HumanGate`, `GateLevel`, `GateDecision`, `GateProposal`, `human_gate`, `propose_change` |
| **Memory** | `Memory`, `MemoryType`, `MemoryTier`, `MemoryLink`, `LinkType`, `MemoryQuery`, `MemorySearchResult`, `SynapseMemory`, `MemoryStore`, `get_synapse_memory`, `reset_synapse_memory`, `ShotContext`, `load_context`, `save_context`, `MarkdownSync`, `parse_decisions_md`, `render_decisions_md` |
| **Session** | `SynapseSession`, `SynapseBridge`, `get_bridge`, `reset_bridge` |
| **Agent** | `AgentTask`, `AgentPlan`, `AgentStep`, `StepStatus`, `PlanStatus`, `DEFAULT_GATE_LEVELS`, `classify_gate_level`, `AgentExecutor`, `OutcomeTracker` |
| **Server** (opt) | `SynapseServer`, `SynapseHandler`, `CommandHandlerRegistry`, `RateLimiter`, `CircuitBreaker`, `CircuitBreakerConfig`, `CircuitState`, `PortManager`, `Watchdog`, `BackpressureController`, `BackpressureLevel`, `HealthMonitor`, `HealthStatus`, `SERVER_AVAILABLE` |
| **Encryption** (opt) | `CryptoEngine`, `ENCRYPTION_AVAILABLE`, `get_crypto` |
| **UI** (opt) | `SynapsePanel`, `create_panel`, `UI_AVAILABLE` |
| **Compat** | `NexusMemory`, `EngramMemory`, `NexusServer`, `NexusHandler`, `NexusPanel`, `NexusBridge`, `EngramBridge`, `HyphaeAuditLog`, `HyphaeGate`, `get_nexus_memory`, `get_engram`, `reset_nexus_memory`, `reset_engram` |

---

### Core Layer

#### `core/protocol.py` (174 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `CommandType` | Enum | Command types with `ENGRAM_*` backwards compat |
| `SynapseCommand` | dataclass | Command with `to_json()`, `from_json()`, `normalized_type()` |
| `SynapseResponse` | dataclass | Response with `to_json()`, `from_json()` |
| `normalize_command_type()` | function | Convert old command names to new |
| `PROTOCOL_VERSION` | const | `"4.0.0"` |
| `HEARTBEAT_INTERVAL` | const | `30.0` |
| `COMMAND_TIMEOUT` | const | `60.0` |

#### `core/queue.py` (89 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `DeterministicCommandQueue` | class | Thread-safe FIFO command queue |
| `ResponseDeliveryQueue` | class | Thread-safe response delivery queue |

#### `core/aliases.py` (99 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `PARAM_ALIASES` | dict | 38+ parameter name mappings |
| `resolve_param()` | function | Resolve parameter using aliasing |
| `resolve_param_with_default()` | function | Resolve with default value |

#### `core/determinism.py` (368 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `DeterministicConfig` | dataclass | Global config: `float_precision=6`, `strict_mode=True`, `global_seed=42` |
| `DeterministicOperation` | dataclass | Base class for reproducible ops with metadata |
| `DeterministicRandom` | class | Seeded LCG PRNG: `random()`, `uniform()`, `randint()`, `choice()`, `shuffle()` |
| `round_float()` | function | Decimal ROUND_HALF_UP fixed-precision rounding |
| `round_vector()` | function | Round all vector components |
| `round_color()` | function | Round color with color-specific precision |
| `kahan_sum()` | function | Compensated summation (O(1) float error) |
| `deterministic_uuid()` | function | Content-based 16-char hex ID |
| `deterministic_sort()` | function | Stable deterministic sort |
| `deterministic_dict_items()` | function | Sorted dict items |
| `@deterministic` | decorator | Auto-rounds float args (positional + keyword) |

#### `core/audit.py` (402 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `AuditLevel` | Enum | DEBUG, INFO, WARNING, ERROR, CRITICAL, AGENT_ACTION, HUMAN_DECISION, GATE_APPROVAL, GATE_REJECTION |
| `AuditCategory` | Enum | LIGHTING, MATERIAL, ENVIRONMENT, AOV, RENDER, PIPELINE, GATE, SYSTEM, SYNAPSE, ENGRAM |
| `AuditEntry` | dataclass | Hash-chain entry with `_compute_hash()`, `to_dict()`, `from_dict()` |
| `AuditLog` | singleton | `log()`, `log_agent_action()`, `log_human_decision()`, `verify_chain()`, `get_entries()` |
| `audit_log()` | function | Get global instance |

#### `core/gates.py` (579 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `GateLevel` | Enum | INFORM, REVIEW, APPROVE, CRITICAL |
| `GateDecision` | Enum | PENDING, APPROVED, REJECTED, MODIFIED, DEFERRED |
| `GateProposal` | dataclass | Proposed action with `to_dict()`, `to_human_summary()` |
| `GateBatch` | dataclass | Batch of proposals for review |
| `HumanGate` | singleton | `propose()`, `decide()`, `decide_batch()`, `approve_all()`, `reject_all()` |
| `human_gate()` | function | Get global instance |
| `propose_change()` | function | Convenience wrapper |

#### `core/crypto.py` (143 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `CryptoEngine` | singleton | Fernet AES-128-CBC + HMAC-SHA256 encryption |
| `encrypt_line()` | method | Encrypt single JSONL line |
| `decrypt_line()` | method | Decrypt line (plaintext passthrough) |
| `encrypt_file_content()` | method | Encrypt entire file |
| `decrypt_file_content()` | method | Decrypt file (plaintext passthrough) |
| `get_crypto()` | function | Get engine or None |
| `MAGIC_PREFIX` | const | `"SYNAPSE_ENC_V1:"` |
| `ENCRYPTION_AVAILABLE` | bool | Whether `cryptography` is installed |

---

### Memory Layer

#### `memory/models.py` (314 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `MemoryType` | Enum | CONTEXT, DECISION, TASK, ACTION, NOTE, REFERENCE, FEEDBACK, ERROR, SUMMARY |
| `MemoryTier` | Enum | CONVERSATION, SHOT, SEQUENCE, SHOW |
| `LinkType` | Enum | RELATED, SUPPORTS, CONTRADICTS, SUPERSEDES, DEPENDS_ON, CAUSED_BY, IMPLEMENTS |
| `MemoryLink` | dataclass | Link between two memories |
| `Memory` | dataclass | Core memory unit with `add_link()`, `to_dict()`, `to_markdown()` |
| `MemoryQuery` | dataclass | Search parameters |
| `MemorySearchResult` | dataclass | Result with relevance score |

#### `memory/store.py` (748 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `MemoryStore` | class | Low-level CRUD: `add()`, `get()`, `update()`, `delete()`, `search()`, `save()` |
| `SynapseMemory` | class | High-level API: `note()`, `decision()`, `action()`, `search()`, `save()` |
| `get_synapse_memory()` | function | Global instance |
| `NexusMemory`, `EngramMemory` | alias | Backwards compat |

#### `memory/context.py` (66 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `get_current_context()` | function | Load ShotContext from storage |
| `update_context()` | function | Update context fields |

#### `memory/markdown.py` (490 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `MarkdownSync` | class | Two-way sync: `read_context()`, `write_context()`, `sync_decisions()`, `append_decision()`, `get_context_for_ai()` |
| `ParsedDecision` | dataclass | Decision parsed from markdown |
| `ShotContext` | dataclass | Parsed context.md |
| `parse_decisions_md()` | function | Parse decisions.md |
| `render_decisions_md()` | function | Render decisions as markdown |
| `load_context()`, `save_context()` | function | Context file I/O |

---

### Agent Layer

#### `agent/protocol.py` (332 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `StepStatus` | Enum | PENDING, APPROVED, EXECUTING, COMPLETED, FAILED, SKIPPED |
| `PlanStatus` | Enum | DRAFT, PROPOSED, APPROVED, EXECUTING, COMPLETED, FAILED, REJECTED |
| `AgentStep` | dataclass | Single action with `to_command()`, gate-level classification |
| `AgentTask` | dataclass | Goal + context populated from memory search |
| `AgentPlan` | dataclass | Ordered steps with `progress()`, `to_summary()` |
| `classify_gate_level()` | function | Auto-classify risk: reads->INFORM, creates->REVIEW, deletes->APPROVE, execute->CRITICAL |
| `DEFAULT_GATE_LEVELS` | dict | Command-to-gate-level mappings |

#### `agent/executor.py` (307 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `AgentExecutor` | class | Four-phase loop: `prepare()` -> `propose()` -> `execute()` -> `record_outcome()` |

#### `agent/learning.py` (195 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `OutcomeTracker` | class | `record()`, `get_relevant()`, `get_rejections()`, `success_rate()` |

---

### Server Layer

#### `server/handlers.py` (504 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `CommandHandlerRegistry` | class | Handler registry with `register()`, `get()`, `has()` |
| `SynapseHandler` | class | Main handler with methods for all command types |

#### `server/websocket.py` (430 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `SynapseServer` | class | WebSocket server: `start()`, `stop()`, `heartbeat()`, `get_health()` |

#### `server/resilience.py` (858 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `RateLimiter` | class | Token bucket (global + per-client): `acquire()`, `get_stats()` |
| `CircuitState` | Enum | CLOSED, OPEN, HALF_OPEN |
| `CircuitBreakerConfig` | dataclass | failure_threshold=5, timeout=30s |
| `CircuitBreaker` | class | State machine: `can_execute()`, `record_success()`, `record_failure()` |
| `PortHealth` | dataclass | Port health status |
| `PortManager` | class | Auto-failover: `get_active_port()`, `should_failover()` |
| `Watchdog` | class | Freeze detection: `start()`, `stop()`, `heartbeat()` |
| `BackpressureLevel` | Enum | NORMAL, ELEVATED, HIGH, CRITICAL |
| `BackpressureController` | class | Load management: `evaluate()`, `should_accept()` |
| `HealthStatus` | dataclass | Overall system health |
| `HealthMonitor` | class | Aggregate: `check()`, `to_dict()` |

---

### Session Layer

#### `session/tracker.py` (535 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `SynapseSession` | dataclass | Single session with `duration_seconds()`, `to_summary()` |
| `SynapseBridge` | singleton | Central integration: `start_session()`, `end_session()`, `log_action()`, `log_decision()`, memory command handlers |

#### `session/summary.py` (88 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `generate_session_summary()` | function | Human-readable summary |
| `format_session_for_ai()` | function | Compact format for AI |

---

### UI Layer

#### `ui/panel.py` (276 lines)
| Symbol | Type | Description |
|--------|------|-------------|
| `SynapsePanel(QWidget)` | class | Main tabbed panel |
| `create_panel()` | function | Factory to create and show panel |

#### `ui/tabs/` (5 files, ~813 lines)
| Tab | File | Description |
|-----|------|-------------|
| `ConnectionTab` | `connection.py` (199 lines) | Server status, start/stop |
| `ContextTab` | `context.py` (185 lines) | Context.md editor |
| `DecisionsTab` | `decisions.py` (195 lines) | Decision log viewer |
| `ActivityTab` | `activity.py` (103 lines) | Activity feed |
| `SearchTab` | `search.py` (131 lines) | Memory search |

---

### Tests

| File | Lines | Tests | Coverage |
|------|-------|-------|----------|
| `test_core.py` | 696 | ~80 | Determinism, audit, gates |
| `test_agent.py` | 880 | ~74 | Protocol, executor, learning |
| `test_crypto.py` | 348 | ~29 | Encryption, kahan_sum, decorator fix |
| `test_resilience.py` | 879 | ~33 | Rate limiter, circuit breaker, watchdog, backpressure |
| **Total** | **2,803** | **187** | |

---

## Architecture

```
python/synapse/
├── __init__.py         # Public API surface (294 lines)
├── core/               # Protocol, queue, parameter aliases, foundation
│   ├── protocol.py     # CommandType enum, SynapseCommand/Response, PROTOCOL_VERSION="4.0.0"
│   ├── queue.py        # DeterministicCommandQueue, ResponseDeliveryQueue
│   ├── aliases.py      # Parameter name resolution (38+ aliases)
│   ├── determinism.py  # Fixed-precision, content IDs, seeded RNG, kahan_sum
│   ├── audit.py        # Hash-chain append-only audit log
│   ├── gates.py        # Human-in-the-loop gate system
│   └── crypto.py       # Optional Fernet encryption (AES-128-CBC + HMAC-SHA256)
├── memory/
│   ├── models.py       # Memory, MemoryType, MemoryTier, MemoryQuery
│   ├── store.py        # SynapseMemory high-level API
│   ├── context.py      # ShotContext helpers
│   └── markdown.py     # MarkdownSync (human-readable export)
├── agent/
│   ├── protocol.py     # AgentTask, AgentPlan, AgentStep
│   ├── executor.py     # prepare -> propose -> execute -> learn
│   └── learning.py     # OutcomeTracker (feedback memories)
├── server/
│   ├── websocket.py    # SynapseServer (WebSocket)
│   ├── handlers.py     # CommandHandlerRegistry
│   └── resilience.py   # RateLimiter, CircuitBreaker, Watchdog, ...
├── session/
│   ├── tracker.py      # SynapseBridge, SynapseSession
│   └── summary.py      # Session summary generation
└── ui/
    ├── panel.py        # SynapsePanel (Qt)
    └── tabs/           # Connection, Context, Decisions, Activity, Search
```

## Storage Layout

```
$HIP/.synapse/                        # Per-project (memory)
├── memory.jsonl                      # Append-only memory log
├── index.json                        # Search index
├── context.md                        # Human-editable context
├── decisions.md                      # Decision log
└── tasks.md                          # Task history

~/.synapse/                           # Global (audit, gates, keys)
├── audit/audit_YYYY-MM-DD.jsonl      # Daily audit logs
├── gates/proposals_YYYY-MM-DD.jsonl  # Gate proposals
└── encryption.key                    # Auto-generated Fernet key (0600)
```

## Design Patterns

| Pattern | Where |
|---------|-------|
| **Singleton** | AuditLog, HumanGate, SynapseBridge, CryptoEngine |
| **State Machine** | CircuitBreaker (CLOSED -> OPEN -> HALF_OPEN) |
| **Observer** | Callbacks in AuditLog, HumanGate, MemoryStore |
| **Command** | SynapseCommand / SynapseResponse protocol |
| **Decorator** | `@deterministic` for reproducibility |
| **Strategy** | BackpressureController evaluation |
| **Template Method** | DeterministicOperation base class |
| **Token Bucket** | RateLimiter (global + per-client) |

## WebSocket Protocol

**Default URL:** `ws://localhost:9999` (websocket.py) or `ws://localhost:9999/synapse` (hwebserver)
**Protocol Version:** `4.0.0`

**Command Types:**
- Node: `create_node`, `delete_node`, `connect_nodes`
- Parameters: `get_parm`, `set_parm`
- Scene: `get_scene_info`, `get_selection`, `set_selection`
- Execution: `execute_python`, `execute_vex`
- USD/Solaris: `create_usd_prim`, `modify_usd_prim`, `get_stage_info`
- Memory: `context`, `search`, `add_memory`, `decide`, `recall`
- Utility: `ping`, `get_health`, `get_help`, `heartbeat`, `backpressure`

## Transport Backends

Synapse supports two transport backends selected by environment:

| Backend | Module | When to Use | Env Config |
|---------|--------|------------|------------|
| `websockets` | `server/websocket.py` | Testing without Houdini, CI, standalone | `SYNAPSE_PATH=""` (default) |
| `hwebserver` | `server/hwebserver_adapter.py` | Production inside Houdini | `SYNAPSE_PATH="/synapse"` |

**hwebserver** is Houdini's native C++ WebSocket server. It eliminates the Python
`websockets` package overhead (~5-15ms/msg) by running handlers directly in Houdini's
multi-threaded server with GIL access.

**Starting hwebserver (inside Houdini):**
```python
from synapse.server.hwebserver_adapter import start_hwebserver
start_hwebserver(port=9999)
```

**MCP configuration for hwebserver:**
```json
{
  "mcpServers": {
    "synapse": {
      "command": "python",
      "args": ["C:/Users/User/Synapse/mcp_server.py"],
      "env": {
        "SYNAPSE_PORT": "9999",
        "SYNAPSE_PATH": "/synapse"
      }
    }
  }
}
```

**Integration test (inside Houdini):**
```bash
hython tests/test_hwebserver_integration.py
```

## Backwards Compatibility

All legacy names are preserved as aliases:
- `NexusServer = SynapseServer`
- `NexusMemory = SynapseMemory`, `EngramMemory = SynapseMemory`
- `NexusBridge = SynapseBridge`, `EngramBridge = SynapseBridge`
- `get_nexus_memory() = get_synapse_memory()`, `get_engram() = get_synapse_memory()`
- `HyphaeAuditLog = AuditLog`, `HyphaeGate = HumanGate`

Storage migration is automatic: `.nexus/` and `.engram/` directories are copied to `.synapse/` on first access.

## Error Classification (Circuit Breaker)

**User Errors** (do NOT trip circuit):
- ValueError, KeyError, AttributeError, TypeError, IndexError, NameError

**Service Errors** (DO trip circuit):
- TimeoutError, threading errors, Houdini crashes

## Testing Without Houdini

Tests must run **without Houdini** by importing modules directly:
```python
import importlib.util
spec = importlib.util.spec_from_file_location("resilience", "python/synapse/server/resilience.py")
resilience = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resilience)
```
