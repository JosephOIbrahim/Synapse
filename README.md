<p align="center">
  <img src="assets/synapse_logo.png" alt="Synapse" width="300">
</p>

<p align="center"><b>AI-Houdini Bridge with Persistent Project Memory</b></p>

<p align="center">
  <a href="https://github.com/JosephOIbrahim/Synapse"><img src="https://img.shields.io/badge/version-5.8.0-blue.svg" alt="Version"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-%3E%3D3.9-blue.svg" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-2%2C055%20passing-brightgreen.svg" alt="Tests"></a>
  <a href="python/synapse/core/protocol.py"><img src="https://img.shields.io/badge/protocol-v4.0.0-orange.svg" alt="Protocol"></a>
</p>

---

## What is Synapse?

Synapse lets an AI see, touch, and remember everything in your Houdini scene — it can read parameters, create and wire up nodes, run Python and VEX code, light and render with Karma, and manipulate USD stages, all through a real-time conversation. On top of that, it keeps a persistent project memory that remembers your decisions, tracks what happened across sessions, and gives the AI full context about your project every time you reconnect.

Built as a standalone package with zero required dependencies.

## Key Features

- **87 MCP Tools** -- Full Houdini control from Claude: nodes, parameters, USD, materials, lighting, rendering, viewport capture, TOPS/PDG, HDA creation
- **Persistent Memory** -- Project memory stored alongside your HIP file with search, decisions, and context summaries
- **Living Memory** -- Evolving per-project and per-scene markdown journals that grow with your work
- **Wire Protocol** -- Typed commands over WebSocket with parameter aliasing and deterministic queuing
- **Agentic Execution** -- prepare / propose / execute / learn loop with automatic risk classification
- **Human-in-the-Loop Gates** -- Four levels (INFORM, REVIEW, APPROVE, CRITICAL) with batch approval
- **VEX Execution** -- Run VEX wrangles directly from conversation
- **Production Resilience** -- Rate limiter, circuit breaker, port failover, watchdog, backpressure
- **Viewport + Render Capture** -- AI can see what you see via flipbook and Karma renders
- **RAG-Powered Routing** -- Knowledge lookup from Houdini documentation (48 built-in workflow recipes) plus 2,079 labeled VEX examples from [vex-corpus](https://github.com/JosephOIbrahim/vex-corpus)
- **Determinism** -- Canonical ordering and tier pinning ([He2025] inspired), plus fixed-precision rounding, content-based IDs, and Kahan summation
- **Houdini Optional** -- All 2,055 tests run without Houdini; core library has zero required dependencies

---

<br>

## Installation

There are two paths depending on how you want to use Synapse:

| Path | You want to... | Time |
|------|----------------|------|
| **A. Artist** | Talk to Houdini through Claude Desktop or Claude Code | ~5 min |
| **B. Developer** | Hack on Synapse itself, run tests, add features | ~5 min |

Most artists want **Path A**. If you just want to try it, start there.

<br>

---

### Path A: Connect Claude to Houdini (Artist Setup)

You'll end up with Claude talking directly to your Houdini scene. Four steps, nothing complicated.

<br>

#### Step 1 &mdash; Install Synapse

Open a terminal (Command Prompt, PowerShell, or Terminal) and run:

```bash
pip install synapse-houdini
```

That's it. One command. This installs Synapse and everything it needs.

> **Tip:** If `pip` isn't recognized, try `python -m pip install synapse-houdini` instead.
>
> **Still stuck?** Make sure Python 3.9 or newer is installed. Run `python --version` to check.

<br>

#### Step 2 &mdash; Start the server inside Houdini

Open Houdini, then open the **Python Shell** (Windows menu > Python Shell) and paste:

```python
from synapse.server.websocket import SynapseServer
server = SynapseServer(port=9999)
server.start()
```

You should see a message confirming the server started on port 9999.

> **You'll do this every time you open Houdini.** Later, you can add these lines to your Houdini startup script so it happens automatically.

<br>

#### Step 3 &mdash; Tell Claude about Synapse

Pick whichever Claude app you use:

<br>

**Claude Desktop** (the app most artists use)

Find your config file and open it in any text editor:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

> **Can't find it?** In Claude Desktop, go to Settings (gear icon) > Developer > Edit Config.

Paste this as the entire file contents:

```json
{
  "mcpServers": {
    "synapse": {
      "command": "python",
      "args": ["-m", "synapse.mcp_server"]
    }
  }
}
```

> **Already have other MCP servers?** Just add the `"synapse": { ... }` block inside your existing `"mcpServers"`.

Save the file and **restart Claude Desktop**. You'll see 43 new tools appear in the tool picker (the hammer icon).

<br>

**Claude Code** (terminal)

Run this once from any folder:

```bash
claude mcp add synapse -- python -m synapse.mcp_server
```

Done. The tools are available in every Claude Code session.

<br>

#### Step 4 &mdash; Try it

With Houdini open and the server running, say something to Claude:

> *"What's in my scene right now?"*

or

> *"Create a sphere and a distant light, then capture the viewport so I can see it."*

or

> *"Set up three-point lighting for my character."*

Claude will use Synapse to read your scene, create nodes, adjust parameters, and show you the result. Everything happens live inside your Houdini session.

<br>

---

### Path B: Developer Setup

For contributing, running tests, or building on top of Synapse.

<br>

#### Clone and install with all extras

```bash
git clone https://github.com/JosephOIbrahim/Synapse.git
cd Synapse
pip install -e ".[dev,websocket,mcp,routing,encryption]"
```

| Extra | What it adds |
|-------|-------------|
| `dev` | pytest, coverage, mypy |
| `websocket` | WebSocket server for Houdini bridge |
| `mcp` | MCP server for Claude integration |
| `routing` | LLM-powered routing tier (Anthropic API) |
| `encryption` | Fernet encryption for data at rest |
| `memory` | Cross-process file locking for scene memory |

<br>

#### Run the tests

```bash
python -m pytest tests/ -v
```

All 1,427 tests run without Houdini. No license needed.

<br>

#### Type checking

```bash
python -m mypy python/synapse/ --config-file pyproject.toml
```

Clean: 0 errors on 58 source files.

<br>

#### Houdini shelf + panel setup (optional)

If you want the toolbar and Qt panel inside Houdini, add to your `houdini.env`:

```
HOUDINI_PATH = "/path/to/Synapse/houdini;&"
```

This loads the shelf toolbar (7 tools including Project Setup, Inspect Selection, Inspect Scene, Health Check, Generate Docs) and the Python panel.

Then in Houdini: **Windows > Python Panel > Synapse**.

<br>

---

### Encryption (Optional)

Synapse supports optional Fernet (AES-128-CBC + HMAC-SHA256) encryption for all data at rest — memory, audit logs, gate proposals, and markdown files.

```bash
pip install synapse-houdini[encryption]
```

**Key management** (priority order):
1. `SYNAPSE_ENCRYPTION_KEY` environment variable (base64-encoded Fernet key)
2. `~/.synapse/encryption.key` file (auto-created with `0600` permissions)
3. Auto-generated on first use

Encryption is transparent: existing plaintext `.synapse/` directories load without migration. New writes are encrypted; reads auto-detect encrypted vs plaintext content.

<br>

---

### Troubleshooting

| Problem | Fix |
|---------|-----|
| `pip` not found | Use `python -m pip install synapse-houdini` instead of bare `pip` |
| `ModuleNotFoundError: synapse` | Make sure you ran `pip install synapse-houdini` first |
| Server won't start in Houdini | Make sure nothing else is using port 9999. You can change it: `SynapseServer(port=9998)` |
| Claude can't connect | Check that the server is running in Houdini *before* talking to Claude |
| Tools don't appear in Claude Desktop | Restart Claude Desktop after editing the config file |
| Wrong Python version | Synapse needs Python 3.9+. Run `python --version` to check |
| Already have MCP servers configured | Add `"synapse": { ... }` inside your existing `"mcpServers"` block &mdash; don't replace the whole file |

## Architecture

```
+---------------------------------------------------------------+
|                         Synapse v5.3.0                        |
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
| **Living Memory** | `project_setup`, `memory_write`, `memory_query`, `memory_status`, `evolve_memory` |
| **Utility** | `ping`, `get_health`, `get_help`, `heartbeat`, `backpressure` |

Parameter names are resolved through an alias system (38+ mappings). For example, `node`, `path`, and `node_path` all resolve to the canonical `node` parameter.

## Claude Integration (MCP)

Synapse includes an MCP server that bridges Claude to Houdini with 43 tools. See [Installation > Path A](#path-a--connect-claude-to-houdini) for setup steps.

```
Claude  <--[stdio/JSON-RPC]-->  mcp_server.py  <--[WebSocket]-->  Synapse (Houdini)
```

### Available MCP Tools (43)

| Category | Tools |
|----------|-------|
| **System** | `synapse_ping`, `synapse_health` |
| **Scene** | `houdini_scene_info`, `houdini_get_selection` |
| **Nodes** | `houdini_create_node`, `houdini_delete_node`, `houdini_connect_nodes` |
| **Parameters** | `houdini_get_parm`, `houdini_set_parm`, `houdini_set_keyframe` |
| **Execution** | `houdini_execute_python`, `houdini_execute_vex` |
| **USD / Solaris** | `houdini_stage_info`, `houdini_get_usd_attribute`, `houdini_set_usd_attribute`, `houdini_create_usd_prim`, `houdini_modify_usd_prim`, `houdini_reference_usd` |
| **Materials** | `houdini_create_material`, `houdini_assign_material`, `houdini_read_material` |
| **Rendering** | `houdini_render`, `houdini_render_settings`, `houdini_wedge`, `houdini_capture_viewport` |
| **Introspection** | `synapse_inspect_selection`, `synapse_inspect_scene`, `synapse_inspect_node` |
| **Memory** | `synapse_context`, `synapse_search`, `synapse_recall`, `synapse_decide`, `synapse_add_memory` |
| **Living Memory** | `synapse_project_setup`, `synapse_memory_write`, `synapse_memory_query`, `synapse_memory_status`, `synapse_evolve_memory` |
| **Knowledge** | `synapse_knowledge_lookup`, `synapse_list_recipes` |
| **Routing** | `synapse_router_stats`, `synapse_metrics` |
| **Batch** | `synapse_batch` |

### Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SYNAPSE_PORT` | `9999` | WebSocket port to connect to |

## Testing

```bash
# All 1,427 tests (no Houdini required)
python -m pytest tests/ -v

# Individual test modules
python -m pytest tests/test_core.py -v        # Determinism, audit, gates
python -m pytest tests/test_routing.py -v     # Routing cascade (323 tests)
python -m pytest tests/test_agent.py -v       # Agent protocol, executor, learning
python -m pytest tests/test_resilience.py -v  # Rate limiter, circuit breaker, watchdog
python -m pytest tests/test_render.py -v      # Karma/Mantra pipeline
python -m pytest tests/test_materials.py -v   # Material tools

# With coverage
python -m pytest tests/ --cov=synapse --cov-report=term-missing
```

All tests import modules directly and run without a Houdini license or environment.

### Live Tests (Inside Houdini)

Some features (viewport capture, hwebserver transport) require a graphical Houdini session. Run these from the Houdini Python Shell:

```python
# Viewport capture test (creates temp scene, captures, verifies, cleans up)
import runpy; runpy.run_path("tests/test_live_capture.py")

# hwebserver integration test
import runpy; runpy.run_path("tests/test_hwebserver_integration.py")
```

## Project Structure

```
Synapse/
├── pyproject.toml
├── LICENSE
├── CLAUDE.md
├── mcp_server.py                       # MCP server (Claude Code / Desktop bridge)
├── .mcp.json                            # Claude Code project-level MCP config
├── houdini/
│   ├── python_panels/
│   │   └── synapse_panel.pypanel    # Houdini Qt panel (5 tool buttons)
│   ├── scripts/python/
│   │   └── synapse_shelf.py         # Shelf callbacks (7 functions)
│   └── toolbar/
│       └── synapse.shelf            # Shelf toolbar (7 tools)
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
    ├── test_routing.py              # Routing engine tests (323 tests)
    ├── test_live_capture.py         # Viewport capture (run inside Houdini)
    └── test_hwebserver_integration.py # hwebserver transport (run inside Houdini)
```

## Status

Synapse is under active development. All layers are well-tested (1,427 unit tests, mypy clean on 58 source files). The WebSocket server and viewport capture have been validated in single-user VFX workflows. Use in production at your own discretion.

## Determinism Reference

Synapse's determinism primitives (`round_float`, `kahan_sum`, `deterministic_uuid`, `@deterministic` decorator) are inspired by [He2025] — "Defeating Nondeterminism in LLM Inference" by Horace He, Thinking Machines Lab. The key insight: batch invariance failure (not just floating-point non-associativity) is the primary source of nondeterminism. Synapse applies this at the application layer: fixed-precision rounding, content-based IDs, and Kahan compensated summation ensure reproducible state across sessions.

## Related Projects

- [**Orchestra**](https://github.com/JosephOIbrahim/Orchestra) -- Cognitive orchestration framework (v7.1.0, 1,500+ tests). Synapse is the Houdini bridge; Orchestra is the cognitive engine.
- [**vex-corpus**](https://github.com/JosephOIbrahim/vex-corpus) -- 2,513 labeled VEX code examples (5.3 MB JSONL) that feed Synapse's RAG knowledge layer. Covers 28 topics from 4 sources with difficulty ratings, topic classification, and function/attribute metadata. Synced via `sync_to_synapse.py` into 14 reference files.
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
