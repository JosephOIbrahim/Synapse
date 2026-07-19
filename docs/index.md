# Synapse

**An AI copilot inside Houdini** -- the agent loop runs in Houdini's own Python interpreter and turns plain English into real nodes in your live scene, dispatching tools as direct in-process `hou` calls. External MCP / WebSocket clients can also connect on the same machine (SYNAPSE assumes a single-user, localhost posture).

## What Synapse Does

- **115 MCP tools** for real-time Houdini scene manipulation
- **6-tier routing cascade** (cheapest-first: Cache -> Recipe -> Regex -> RAG -> Haiku -> Agent)
- **Persistent project memory** with JSONL or SQLite backends
- **He2025 determinism** -- same inputs produce same routing decisions
- **Adaptive tier routing** -- learns from outcomes while preserving consistency
- **Production resilience** -- rate limiting, circuit breaker, backpressure, graceful shutdown

## Quick Links

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)
- [Architecture Overview](architecture/overview.md)
- [API Reference](api/core/protocol.md)

## Requirements

- **SideFX Houdini 22.0.368** — the verified live target (H21.0.671 artifacts retained for dual-build). At runtime SYNAPSE uses Houdini's **embedded Python (3.13.10 on H22)**, not a system Python.
- Python 3.9+ only for running the test suite outside Houdini.
- **No `pip install` for the artist path.** The Anthropic SDK stack is vendored into `python/synapse/_vendor/` (cp311 + cp313 win_amd64 natives), so it is active inside Houdini's embedded Python. Outside Houdini, on a Python with no matching ABI, the vendor tree is inactive and a real pip-installed SDK is used instead.

## Optional Dependencies

The distribution is named **`synapse-houdini`** and is installed from a local checkout, not from PyPI. Extras:

| Feature | Package | Install |
|---------|---------|---------|
| WebSocket server (legacy transport) | `websockets` | `pip install -e ".[websocket]"` |
| External stdio MCP bridge | `mcp`, `websockets` | `pip install -e ".[mcp]"` |
| LLM routing (Tier 2) | `anthropic` | `pip install -e ".[routing]"` |
| Encryption | `cryptography` | `pip install -e ".[encryption]"` |
| Development / tests | `pytest`, `pytest-cov` | `pip install -e ".[dev]"` |

> None of these are needed for the in-Houdini panel — it rides Houdini's built-in `hwebserver` and the vendored SDK. They apply to the developer and external-MCP-client paths.
