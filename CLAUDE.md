# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Synapse is the AI-Houdini Bridge — a standalone package providing:
- **Server**: WebSocket bridge for real-time command transmission with production resilience
- **Memory**: Persistent project memory ($HIP/.synapse/)
- **Session**: Session tracking with auto-summary generation
- **UI**: Qt panel with tabs for connection, context, decisions, activity, and search

Extracted from Nexus (RadiantSuite) and Engram (Hyphae) into a self-contained package.

## Development Commands

```bash
# Run all tests (without Houdini)
python tests/test_resilience.py    # Resilience layer (33 tests)
python -m pytest tests/            # All tests

# Install for development
pip install -e ".[dev]"
```

## Architecture

```
python/synapse/
├── __init__.py         # Public API (SynapseServer, SynapseMemory, SynapseBridge)
├── core/               # Protocol, queue, parameter aliases
│   ├── protocol.py     # CommandType enum, SynapseCommand/Response, PROTOCOL_VERSION="4.0.0"
│   ├── queue.py        # DeterministicCommandQueue, ResponseDeliveryQueue
│   └── aliases.py      # Parameter name resolution
├── memory/             # Persistent project memory
│   ├── models.py       # Memory, MemoryType, MemoryTier, MemoryLink, MemoryQuery
│   ├── store.py        # MemoryStore (low-level), SynapseMemory (high-level API)
│   ├── context.py      # ShotContext helpers
│   └── markdown.py     # MarkdownSync, context.md/decisions.md/tasks.md
├── server/             # WebSocket server + resilience
│   ├── handlers.py     # CommandHandlerRegistry, SynapseHandler
│   ├── websocket.py    # SynapseServer (WebSocket implementation)
│   └── resilience.py   # RateLimiter, CircuitBreaker, PortManager, Watchdog, Backpressure
├── session/            # Session lifecycle
│   ├── tracker.py      # SynapseBridge (central integration), SynapseSession
│   └── summary.py      # Session summary generation
└── ui/                 # Qt panel (requires PySide6/PySide2)
    ├── panel.py        # SynapsePanel main widget
    └── tabs/           # Connection, Context, Decisions, Activity, Search
```

## Resilience Layer Components

```
RateLimiter      - Token bucket algorithm (global + per-client)
CircuitBreaker   - CLOSED → OPEN → HALF_OPEN state machine
PortManager      - Auto-failover across port range
Watchdog         - Main thread freeze detection (Synapse-Watchdog thread)
Backpressure     - NORMAL → ELEVATED → HIGH → CRITICAL load management
HealthMonitor    - Aggregate system health
```

## Storage Migration (3-tier)

Synapse supports automatic migration from legacy storage directories:
1. `.synapse/` — Current (preferred)
2. `.nexus/` — Nexus-era (auto-migrated)
3. `.engram/` — Engram-era (auto-migrated)

Migration copies files and leaves a `.migrated_to_synapse` marker.

## Backwards Compatibility

All legacy names are preserved as aliases:
- `NexusServer = SynapseServer`
- `NexusMemory = SynapseMemory`, `EngramMemory = SynapseMemory`
- `NexusBridge = SynapseBridge`, `EngramBridge = SynapseBridge`
- `get_nexus_memory() = get_synapse_memory()`, `get_engram() = get_synapse_memory()`

## WebSocket Protocol

**Default URL:** `ws://localhost:9999`
**Protocol Version:** `4.0.0`

**Command Types:**
- Node: `create_node`, `delete_node`, `connect_nodes`
- Parameters: `get_parm`, `set_parm`
- Memory: `memory_context`, `memory_search`, `memory_add`, `memory_decide`
- Utility: `ping`, `get_health`, `get_help`, `heartbeat`

## Testing Without Houdini

Tests must run **without Houdini** by importing modules directly:
```python
import importlib.util
spec = importlib.util.spec_from_file_location("resilience", "python/synapse/server/resilience.py")
resilience = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resilience)
```

## Error Classification (Circuit Breaker)

**User Errors** (do NOT trip circuit):
- ValueError, KeyError, AttributeError, TypeError, IndexError, NameError

**Service Errors** (DO trip circuit):
- TimeoutError, threading errors, Houdini crashes
