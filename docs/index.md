# Synapse

**AI-Houdini Bridge** -- A standalone Python package that lets AI assistants control SideFX Houdini via WebSocket.

## What Synapse Does

- **37 MCP tools** for real-time Houdini scene manipulation
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

- Python 3.9+
- SideFX Houdini 19.5+ (for runtime; tests run without Houdini)
- No required dependencies (stdlib only)

## Optional Dependencies

| Feature | Package | Install |
|---------|---------|---------|
| WebSocket server | `websockets` | `pip install synapse[websocket]` |
| MCP bridge | `mcp`, `websockets` | `pip install synapse[mcp]` |
| LLM routing (Tier 2) | `anthropic` | `pip install synapse[routing]` |
| Encryption | `cryptography` | `pip install synapse[encryption]` |
| Development | `pytest`, `pytest-cov` | `pip install synapse[dev]` |
