<p align="center">
  <img src="assets/synapse_logo.png" alt="Synapse" width="300">
</p>

<p align="center"><b>AI-Houdini Bridge with Persistent Project Memory</b></p>

<p align="center">
  <a href="https://github.com/JosephOIbrahim/Synapse"><img src="https://img.shields.io/badge/version-4.2.1-blue.svg" alt="Version"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-323%20passing-brightgreen.svg" alt="Tests"></a>
  <a href="python/synapse/core/protocol.py"><img src="https://img.shields.io/badge/protocol-v4.0.0-orange.svg" alt="Protocol"></a>
</p>

---

## What is Synapse?

Synapse is a standalone bridge between AI assistants and SideFX Houdini. It provides a WebSocket wire protocol for real-time scene manipulation, persistent project memory that survives between sessions, and an agentic execution layer with human-in-the-loop safety gates. Every operation is deterministic, auditable, and production-resilient.

Extracted from [Nexus](https://github.com/JosephOIbrahim) (RadiantSuite) and Engram (Hyphae) into a self-contained package. Zero required dependencies.

## Key Features

- **Wire Protocol** -- Typed commands over WebSocket with parameter aliasing and deterministic queuing
- **Persistent Memory** -- Project memory stored at `$HIP/.synapse/` with search, decisions, context summaries, and markdown export
- **Agentic Execution** -- prepare / propose / execute / learn loop with automatic risk classification
- **Human-in-the-Loop Gates** -- Four levels (INFORM, REVIEW, APPROVE, CRITICAL) with batch approval workflows
- **Determinism** -- Fixed-precision rounding, content-based IDs, seeded RNG, `@deterministic` decorator
- **Tamper-Evident Audit** -- Append-only hash-chain log with daily JSONL rotation and chain verification
- **Production Resilience** -- Rate limiter, circuit breaker, port failover, watchdog, backpressure controller
- **Backwards Compatible** -- Full alias coverage for Nexus and Engram APIs; automatic storage migration
- **Houdini Optional** -- All tests run without Houdini; core library has zero required dependencies

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Run tests (no Houdini needed)
python -m pytest tests/ -v

# Optional: WebSocket server support
pip install -e ".[websocket]"
```

### Encryption (Optional)

Synapse supports optional Fernet (AES-128-CBC + HMAC-SHA256) encryption for all data at rest — memory, audit logs, gate proposals, and markdown files.

```bash
# Install encryption support
pip install -e ".[encryption]"
```

**Key management** (priority order):
1. `SYNAPSE_ENCRYPTION_KEY` environment variable (base64-encoded Fernet key)
2. `~/.synapse/encryption.key` file (auto-created with `0600` permissions)
3. Auto-generated on first use

```python
# Generate a key manually
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())

# Or set via environment
# export SYNAPSE_ENCRYPTION_KEY="your-base64-fernet-key"
```

Encryption is transparent: existing plaintext `.synapse/` directories load without migration. New writes are encrypted; reads auto-detect encrypted vs plaintext content.

```python
from synapse import SynapseMemory

memory = SynapseMemory()

# Record a decision
memory.decision(
    decision="Use three-point lighting setup",
    reasoning="Client requested classic Hollywood look",
    alternatives=["Natural lighting", "HDRI only"],
    tags=["lighting", "shot_010"],
)

# Search memory
results = memory.search("lighting setup")
for r in results:
    print(f"[{r.score:.0%}] {r.memory.summary}")
```

## Architecture

```
+---------------------------------------------------------------+
|                         Synapse v4.2.1                        |
+---------------------------------------------------------------+
|                                                               |
|  +-- UI Layer (Qt) ----------------------------------------+ |
|  |  SynapsePanel > Connection | Context | Decisions |       | |
|  |                  Activity  | Search                      | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +-- Agent Layer -------------------------------------------+ |
|  |  AgentExecutor: prepare -> propose -> execute -> learn   | |
|  |  AgentTask / AgentPlan / AgentStep / OutcomeTracker      | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +-- Session Layer -----------------------------------------+ |
|  |  SynapseBridge  |  SynapseSession  |  SessionSummary     | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +-- Memory Layer ------------------------------------------+ |
|  |  SynapseMemory  |  MemoryStore  |  MarkdownSync          | |
|  |  Memory / MemoryType / MemoryTier / MemoryQuery          | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +-- Server Layer ------------------------------------------+ |
|  |  SynapseServer (WebSocket)  |  CommandHandlerRegistry    | |
|  |  RateLimiter | CircuitBreaker | PortManager | Watchdog   | |
|  |  BackpressureController | HealthMonitor                  | |
|  +----------------------------------------------------------+ |
|                                                               |
|  +-- Core Layer (Foundation) -------------------------------+ |
|  |  protocol.py   Wire format, CommandType, aliases         | |
|  |  queue.py      DeterministicCommandQueue                 | |
|  |  determinism.py Fixed-precision, content IDs, seeded RNG | |
|  |  audit.py      Hash-chain append-only log                | |
|  |  gates.py      INFORM / REVIEW / APPROVE / CRITICAL      | |
|  +----------------------------------------------------------+ |
|                                                               |
+---------------------------------------------------------------+
```

**Core** provides the wire format, determinism primitives, tamper-evident audit, and human gates. **Memory** persists decisions, context, and actions to `$HIP/.synapse/` with markdown export. **Server** runs the WebSocket bridge with production resilience (rate limiting, circuit breaker, port failover, watchdog, backpressure). **Agent** orchestrates multi-step plans through the gate system with outcome-based learning. **Session** tracks lifecycle and generates summaries. **UI** provides the Houdini Qt panel.

## Usage

### Memory

```python
from synapse import SynapseMemory, MemoryType

memory = SynapseMemory()

# Add typed memories
memory.note("Switched to Arnold renderer", tags=["render"])
memory.action("Created key light", node_paths=["/obj/key_light"])
memory.decision(
    decision="Use ACES color space",
    reasoning="Studio standard for color management",
    alternatives=["sRGB", "Linear"],
)

# Search
results = memory.search("color space", limit=10)

# Get all decisions
decisions = memory.get_decisions()

# Context summary (useful for feeding to AI)
summary = memory.get_context_summary()

# Persist to disk
memory.save()
```

### Agent Execution

The flagship feature. Agents follow a four-phase loop: **prepare** (gather context from memory), **propose** (define steps, route through gates), **execute** (run commands or dry-run), **learn** (record outcomes as feedback memories).

```python
from synapse import AgentExecutor, AgentStep, SynapseMemory, HumanGate

# No command_fn = dry-run mode (no Houdini needed)
executor = AgentExecutor(
    memory=SynapseMemory(),
    gate=HumanGate.get_instance(),
)

# Phase 1: Prepare (searches memory for relevant context)
task = executor.prepare(
    goal="Set up three-point lighting for shot_010",
    sequence_id="shot_010",
    category="lighting",
    agent_id="claude",
)

# Phase 2: Propose (define steps, auto-classify gate levels)
plan = executor.propose(
    task=task,
    steps=[
        AgentStep(
            step_id="",
            action="create_node",        # Auto-classified: REVIEW
            description="Create key light",
            payload={"type": "arealight", "name": "key_light"},
            gate_level=None,
            reasoning="Primary illumination source",
            confidence=0.9,
        ),
        AgentStep(
            step_id="",
            action="set_parm",            # Auto-classified: REVIEW
            description="Set intensity to 1000",
            payload={"node": "/obj/key_light", "parm": "light_intensity", "value": 1000.0},
            gate_level=None,
            reasoning="Standard key light intensity",
            confidence=0.85,
        ),
    ],
    reasoning="Classic three-point lighting setup",
)

# Phase 3: Execute
if plan.status.value == "approved":
    completed = executor.execute(plan)
    print(completed.to_summary())

# Phase 4: Learn
executor.record_outcome(plan, success=True, feedback="Client approved")
```

### Human-in-the-Loop Gates

Every agent action is classified by risk level. Reads auto-approve; creates batch for review; deletes require explicit approval; code execution requires full stop.

```python
from synapse import HumanGate
from synapse.core.audit import AuditCategory
from synapse.core.gates import GateLevel, GateDecision

gate = HumanGate.get_instance()

# Agent proposes a change
proposal = gate.propose(
    operation="delete_node",
    description="Remove unused bounce light",
    sequence_id="shot_010",
    category=AuditCategory.LIGHTING,
    level=GateLevel.APPROVE,          # Deletion = explicit approval
    proposed_changes={"node": "/obj/bounce_light"},
    reasoning="Light contributes <1% to final render",
    confidence=0.7,
    agent_id="claude",
)

# Human decides
gate.decide(
    proposal_id=proposal.proposal_id,
    decision=GateDecision.APPROVED,
    user_id="artist_joe",
    notes="Confirmed, bounce light was a holdover from previous setup",
)

# Or batch approve an entire sequence
gate.approve_all("shot_010", user_id="artist_joe")
```

**Gate levels and auto-classification:**

| Level | Behavior | Example commands |
|-------|----------|-----------------|
| `INFORM` | Auto-approve, log only | `get_parm`, `get_scene_info` |
| `REVIEW` | Batch for later review | `create_node`, `set_parm` |
| `APPROVE` | Block until approved | `delete_node`, `connect_nodes` |
| `CRITICAL` | Full stop, confirm twice | `execute_python`, `execute_vex` |

### Determinism

Fixed-precision arithmetic and content-based identifiers ensure reproducible workflows.

```python
from synapse.core.determinism import (
    round_float,
    deterministic_uuid,
    DeterministicRandom,
    deterministic,
)

# Fixed-precision rounding (Decimal ROUND_HALF_UP)
value = 0.1 + 0.2               # 0.30000000000000004
rounded = round_float(value)     # 0.3

# Content-based UUIDs (same input = same ID, always)
id_a = deterministic_uuid("shot_010:key_light")
id_b = deterministic_uuid("shot_010:key_light")
assert id_a == id_b

# Seeded RNG (reproducible sequences)
rng = DeterministicRandom(seed=42)
rng.uniform(0.0, 1.0)   # Same result every run
rng.shuffle([1, 2, 3])  # Same order every run

# Decorator: auto-rounds float arguments
@deterministic
def place_light(x: float, y: float, z: float):
    return (x, y, z)
```

### Resilience

Production-grade stability for long-running Houdini sessions.

```python
from synapse.server.resilience import (
    RateLimiter,
    CircuitBreaker,
    CircuitBreakerConfig,
    Watchdog,
    BackpressureController,
    HealthMonitor,
)

# Token-bucket rate limiter (global + per-client)
limiter = RateLimiter(tokens_per_second=50.0, bucket_size=100)
allowed, info = limiter.acquire(client_id="claude")

# Circuit breaker (trips on service errors, ignores user errors)
breaker = CircuitBreaker("houdini", CircuitBreakerConfig(
    failure_threshold=5,
    timeout_seconds=60.0,
))
result = breaker.call(some_houdini_function, arg1, arg2)

# Watchdog (detects main thread freezes)
dog = Watchdog(timeout_seconds=30.0)
dog.start()
dog.pet()   # Call periodically from main thread

# Backpressure (NORMAL -> ELEVATED -> HIGH -> CRITICAL)
bp = BackpressureController()
bp.report_metric(queue_size=50, processing_time=0.2)
should_throttle, details = bp.should_throttle()

# Aggregate health
monitor = HealthMonitor()
monitor.update("websocket", healthy=True)
monitor.update("houdini", healthy=True)
report = monitor.get_report()
```

### Audit Trail

Tamper-evident, append-only logging with cryptographic hash chain.

```python
from synapse.core.audit import audit_log, AuditLevel, AuditCategory

log = audit_log()

# Log an agent action
log.log_agent_action(
    operation="create_light",
    message="Created key light at /obj/key_light",
    agent_id="claude",
    category=AuditCategory.LIGHTING,
    sequence_id="shot_010",
)

# Log a human decision
log.log_human_decision(
    operation="approve_plan",
    message="Approved lighting setup",
    user_id="artist_joe",
    category=AuditCategory.GATE,
)

# Query entries
entries = log.get_entries(category=AuditCategory.LIGHTING, limit=20)

# Verify chain integrity (detect tampering)
valid, failed_at = log.verify_chain()
assert valid, f"Chain broken at entry {failed_at}"
```

## Wire Protocol

Default endpoint: `ws://localhost:9999` | Protocol version: `4.0.0`

Commands are JSON messages with `type`, `id`, `payload`, `sequence`, and `timestamp` fields.

| Category | Commands |
|----------|----------|
| **Node** | `create_node`, `delete_node`, `modify_node`, `connect_nodes` |
| **Parameters** | `get_parm`, `set_parm` |
| **Scene** | `get_scene_info`, `get_selection`, `set_selection` |
| **Execution** | `execute_python`, `execute_vex` |
| **USD/Solaris** | `create_usd_prim`, `modify_usd_prim`, `get_stage_info`, `set_usd_attribute`, `get_usd_attribute` |
| **Memory** | `context`, `search`, `add_memory`, `decide`, `recall` |
| **Utility** | `ping`, `get_health`, `get_help`, `heartbeat`, `backpressure` |

Parameter names are resolved through an alias system (38+ mappings). For example, `node`, `path`, and `node_path` all resolve to the canonical `node` parameter.

Legacy `ENGRAM_*` command names (e.g., `engram_context`) are automatically normalized to their current equivalents.

## Testing

```bash
# All tests (no Houdini required)
python -m pytest tests/ -v

# Individual test modules
python -m pytest tests/test_core.py -v        # Determinism, audit, gates
python -m pytest tests/test_agent.py -v       # Agent protocol, executor, learning
python -m pytest tests/test_resilience.py -v  # Rate limiter, circuit breaker, watchdog

# With coverage
python -m pytest tests/ --cov=synapse --cov-report=term-missing
```

All tests import modules directly and run without a Houdini license or environment.

## Project Structure

```
Synapse/
├── pyproject.toml
├── LICENSE
├── CLAUDE.md
├── houdini/
│   └── python_panels/
│       └── synapse.pypanel          # Houdini Qt panel definition
├── python/synapse/
│   ├── __init__.py                  # Public API surface
│   ├── core/
│   │   ├── protocol.py              # CommandType, SynapseCommand/Response
│   │   ├── queue.py                 # DeterministicCommandQueue
│   │   ├── aliases.py               # Parameter name resolution (38+ aliases)
│   │   ├── determinism.py           # Fixed-precision, content IDs, seeded RNG
│   │   ├── audit.py                 # Hash-chain append-only audit log
│   │   └── gates.py                 # Human-in-the-loop gate system
│   ├── memory/
│   │   ├── models.py                # Memory, MemoryType, MemoryTier, MemoryQuery
│   │   ├── store.py                 # SynapseMemory high-level API
│   │   ├── context.py               # ShotContext helpers
│   │   └── markdown.py              # MarkdownSync (human-readable export)
│   ├── routing/
│   │   ├── __init__.py              # Public routing API
│   │   ├── router.py                # TieredRouter (Cache→Recipe→Regex→Knowledge→LLM→Agent)
│   │   ├── parser.py                # CommandParser (regex patterns, first-match-wins)
│   │   ├── knowledge.py             # KnowledgeIndex (inverted keyword search from RAG)
│   │   ├── recipes.py               # RecipeRegistry (multi-step command sequences)
│   │   └── cache.py                 # ResponseCache (deterministic LRU with TTL)
│   ├── agent/
│   │   ├── protocol.py              # AgentTask, AgentPlan, AgentStep
│   │   ├── executor.py              # prepare -> propose -> execute -> learn
│   │   └── learning.py              # OutcomeTracker (feedback memories)
│   ├── server/
│   │   ├── websocket.py             # SynapseServer (WebSocket)
│   │   ├── handlers.py              # CommandHandlerRegistry
│   │   └── resilience.py            # RateLimiter, CircuitBreaker, Watchdog, ...
│   ├── session/
│   │   ├── tracker.py               # SynapseBridge, SynapseSession
│   │   └── summary.py               # Session summary generation
│   └── ui/
│       ├── panel.py                 # SynapsePanel (Qt)
│       └── tabs/                    # Connection, Context, Decisions, Activity, Search
└── tests/
    ├── test_core.py                 # Foundation layer tests
    ├── test_agent.py                # Agent layer tests
    ├── test_resilience.py           # Resilience layer tests
    ├── test_crypto.py               # Encryption layer tests
    └── test_routing.py              # Routing engine tests (323 tests)
```

## Backwards Compatibility

Synapse consolidates what were previously separate packages (Nexus, Engram, Hyphae). All legacy names are preserved as aliases:

| Legacy | Current |
|--------|---------|
| `NexusServer` | `SynapseServer` |
| `NexusMemory`, `EngramMemory` | `SynapseMemory` |
| `NexusBridge`, `EngramBridge` | `SynapseBridge` |
| `get_nexus_memory()`, `get_engram()` | `get_synapse_memory()` |
| `HyphaeAuditLog` | `AuditLog` |
| `HyphaeGate` | `HumanGate` |
| `NexusPanel` | `SynapsePanel` |

**Storage migration** is automatic. On first access, Synapse checks for `.nexus/` and `.engram/` directories, copies their contents to `.synapse/`, and leaves a `.migrated_to_synapse` marker.

**Command protocol** aliases are also preserved: `engram_context` normalizes to `context`, `engram_search` to `search`, and so on.

## Related Projects

- [**Orchestra**](https://github.com/JosephOIbrahim/Orchestra) -- Cognitive orchestration framework (v7.1.0, 1,500+ tests). Synapse is the Houdini bridge; Orchestra is the cognitive engine.
- **Cognitive Substrate** -- Theoretical foundation for deterministic state composition.

## Patent Notice

Certain methods and systems implemented in this software are the subject of a
pending patent application. "Patent Pending" applies to, but is not limited to:

- Tiered cognitive routing cascade with confidence-based tier forwarding
- Persistent memory tier architecture with cross-tier linking
- Deterministic state composition using priority-ordered resolution semantics
- Agentic execution loop with gate-integrated outcome learning

Use of this software under the MIT License does not grant any rights under
the patent application(s). See [LICENSE](LICENSE) for details.

## License

MIT License. Copyright (c) 2025-2026 Joe Ibrahim.
