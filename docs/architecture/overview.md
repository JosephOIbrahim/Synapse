# Architecture Overview

## Data Flow

```
Claude Desktop/Code
    |  stdio / JSON-RPC
mcp_server.py  (43 tools, concurrent dispatch)
    |  WebSocket: ws://localhost:9999/synapse
SynapseServer  (daemon thread inside Houdini)
    |  CommandHandlerRegistry
hou.* Python API
    |
Houdini USD Stage / Solaris / Karma
```

## Package Layout

| Layer | Package | Responsibility |
|-------|---------|---------------|
| Foundation | `synapse.core` | Wire protocol, parameter aliases, determinism primitives, audit chain, human gates, encryption |
| Memory | `synapse.memory` | JSONL/SQLite store, data models, shot context, markdown sync |
| Routing | `synapse.routing` | 6-tier dispatch, regex parser, RAG knowledge, recipes, deterministic cache, epoch adaptation |
| Agent | `synapse.agent` | Prepare/propose/execute/learn lifecycle, task/plan/step protocol |
| Server | `synapse.server` | WebSocket server, command handlers, resilience stack, introspection, authentication |
| Session | `synapse.session` | SynapseBridge singleton, session summaries |
| UI | `synapse.ui` | Qt panel with 5 tabs (requires PySide2) |

## Routing Cascade

Cheapest-first, short-circuits on first match:

```
Cache(O(1)) -> Recipe(O(1)) -> Planner(O(1)) -> Tier0/regex(O(n)) -> Tier1/RAG(O(log n)) -> Tier2/Haiku(~5s) -> Tier3/Agent(~15s)
```

- **Tier pinning**: Same input + context maps to same tier (He2025 consistency)
- **Epoch adaptation**: Fixed-size epochs (100 commands), Kahan-summed success rates adjust thresholds
- **Speculative parallelism**: Tier 0 regex and Tier 1 RAG run concurrently

## Resilience Stack

- **RateLimiter**: Token bucket (500 TPS, 2000 burst)
- **CircuitBreaker**: CLOSED -> OPEN -> HALF_OPEN state machine
- **PortManager**: Automatic fallback ports
- **Watchdog**: Main thread freeze detection
- **BackpressureController**: 4-level throttling (NORMAL -> ELEVATED -> HIGH -> CRITICAL)
- **HealthMonitor**: Aggregates all components into single health status

## Determinism

Synapse adapts the core principle from [He2025] "Defeating Nondeterminism in LLM Inference" — same input must produce same output — at the **application layer** (not GPU kernels):

**Inspired by He2025:**
- `sort_keys=True` in all JSON serialization (canonical byte representation)
- Sorted iterations before aggregation (fixed reduction order)
- Fixed-size epochs, not time-based (batch-invariant adaptation)
- Tier pinning: same input + context maps to same routing tier

**General determinism (not from He2025):**
- `round_float()` for output precision (Decimal ROUND_HALF_UP)
- `kahan_sum()` for stable float aggregation (Kahan, 1965)
- `deterministic_uuid()` for content-based IDs (SHA-256)
