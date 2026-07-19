# Connecting to SYNAPSE via MCP

SYNAPSE exposes a standard MCP (Model Context Protocol) endpoint that any MCP-compliant client can connect to -- Claude Code, Cursor, VS Code, Windsurf, Cline, or custom agents.

> **You do not need this page to use SYNAPSE.** The artist path -- panel in Houdini, type "make a box" -- needs no MCP client and no `pip install`. See [README ▸ Install](../../README.md#-install--5-minutes). This page is for connecting an **external** MCP client to a running Houdini.

**Protocol:** MCP 2025-06-18 (Streamable HTTP transport)
**Endpoint:** `http://localhost:9999/mcp`
**Method:** `POST` with JSON-RPC 2.0 body

## One server, two paths

There is **one** server, not two. SYNAPSE registers both surfaces as handlers on the **same Houdini `hwebserver` instance**, so a single `start_hwebserver()` call brings up both on **one port**:

| Path | Handler | Registered at | Used by |
|---|---|---|---|
| `/synapse` | WebSocket | `server/hwebserver_adapter.py` (`@hwebserver.webSocket("/synapse")`) | `mcp_server.py` stdio bridge, direct WS clients |
| `/mcp` | HTTP POST | `python/synapse/mcp/server.py` (`@hwebserver.urlHandler("/mcp")`) | Streamable-HTTP MCP clients -- Claude Code, Cursor, etc. |

The default port is **9999**. `start_hwebserver(port=...)` binds the port you ask for and does **not** auto-fall-back to another one -- if 9999 is already held, startup fails rather than silently moving. The real bound port is published to a discovery sidecar (below), so clients should read it rather than assume.

## Prerequisites

1. **Houdini is running.**
2. **The SYNAPSE panel is open** -- New Pane Tab ▸ **Synapse**.
3. **You clicked `Connect` in the panel footer.**

> ⚠️ **The bridge never starts automatically.** Not on Houdini launch, not from the shelf button (the shelf tool only *opens the panel* -- it starts no server), not when the panel loads. The footer **Connect** button is the one-click way to start it; it is idempotent and safe to click anytime. Once it is up the button reads **Bridge ✓**.

*Headless / no panel?* Run this in Houdini's Python Shell instead:

```python
from synapse.server.hwebserver_adapter import start_hwebserver
start_hwebserver(port=9999)
```

### Finding the port

When the server starts it writes the real bound endpoint to `~/.synapse/bridge.json` (override the location with `$SYNAPSE_BRIDGE_FILE`):

```json
{"host": "localhost", "port": 9999, "pid": 12345}
```

**Read this file rather than hardcoding a port.** It is the authoritative answer to "where is SYNAPSE listening right now", and its absence means the server is not running on this machine.

### Verify it is up

```bash
curl -s -X POST http://localhost:9999/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test"}}}'
```

> ✅ **You should see** a JSON response containing `protocolVersion` and `capabilities`.
> **If you see** `Connection refused` -- the bridge is not up. Click **Connect** in the panel footer.

*Status: the `/mcp`-on-9999 wiring is confirmed by reading the registration code (`mcp/server.py:685` + `hwebserver_adapter.py:273`). **Verify live** with the curl above before depending on it in a studio setup.*

## Claude Code

Add to your MCP server configuration (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "synapse": {
      "type": "streamableHttp",
      "url": "http://localhost:9999/mcp"
    }
  }
}
```

Claude Code will auto-discover all SYNAPSE tools on connection.

### Alternative: the stdio bridge

This repo ships a working stdio config at [`.mcp.json`](../../.mcp.json) -- it runs `mcp_server.py` from the **repo root**, which connects out to the same WebSocket (`/synapse`) surface:

```json
{
  "mcpServers": {
    "synapse": {
      "type": "stdio",
      "command": "python",
      "args": ["mcp_server.py"],
      "env": {}
    }
  }
}
```

> ⚠️ **This path needs two pip installs:** `pip install mcp websockets`. Neither is vendored (`python/synapse/_vendor/` carries the Anthropic SDK stack only), and this bridge runs in *your* Python, not Houdini's. The in-Houdini panel path needs neither.

Run it from the repo root (the `args` path is relative), or give an absolute path to `mcp_server.py`.

## Cursor / VS Code / Other MCP Clients

Most MCP clients support Streamable HTTP transport. Point them at:

```
URL:       http://localhost:9999/mcp
Transport: Streamable HTTP
```

Consult your client's documentation for the exact configuration format.

## Custom Agents (Python)

```python
import json
import requests

BASE = "http://localhost:9999/mcp"

# 1. Initialize
resp = requests.post(BASE, json={
    "jsonrpc": "2.0", "id": 1,
    "method": "initialize",
    "params": {"clientInfo": {"name": "my-agent", "version": "1.0"}}
})
session_id = resp.headers["Mcp-Session-Id"]
headers = {"Mcp-Session-Id": session_id, "Content-Type": "application/json"}

# 2. List tools
resp = requests.post(BASE, headers=headers, json={
    "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}
})
tools = resp.json()["result"]["tools"]
print(f"{len(tools)} tools available")

# 3. Call a tool
resp = requests.post(BASE, headers=headers, json={
    "jsonrpc": "2.0", "id": 3,
    "method": "tools/call",
    "params": {"name": "houdini_scene_info", "arguments": {}}
})
print(resp.json()["result"])
```

## Session Management

SYNAPSE uses the `Mcp-Session-Id` header for session tracking:

- The `initialize` response includes an `Mcp-Session-Id` header
- All subsequent requests must include this header
- Sessions are lightweight -- no heavy state, just client identification
- To end a session, send `DELETE /mcp` with the session header

## Available Tools

SYNAPSE registers **115 tools**. By name prefix:

| Prefix | Tools | Covers |
|---|---|---|
| `houdini_` | 40 | scene, nodes, parms, execution, USD/Solaris, materials, HDAs, render, undo/redo |
| `synapse_` | 37 | memory, introspection, propose/validate/build, render orchestration, health, diagnostics |
| `cops_` | 21 | Copernicus -- networks, solvers, procedural texture, stylize, AOV comp, MaterialX |
| `tops_` | 17 | PDG -- cook, wedge, work items, schedulers, dependency graph, multi-shot |

**Call `tools/list` for the authoritative list** with descriptions and input schemas -- that is generated from the live registry and can never drift from it. A per-tool reference lives in [`docs/tools.md`](../tools.md).

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SYNAPSE_PORT` | `9999` | hwebserver port -- serves **both** `/synapse` (WS) and `/mcp` (HTTP) |
| `SYNAPSE_PATH` | `/synapse` | WebSocket path (MCP always uses `/mcp`) |
| `SYNAPSE_BRIDGE_FILE` | `~/.synapse/bridge.json` | Where the real bound endpoint is published for discovery |
| `SYNAPSE_API_KEY` | (none) | API key for both WebSocket and MCP Bearer token auth |
| `SYNAPSE_DEPLOY_MODE` | `local` | Origin-validation posture for `/mcp` (DNS-rebinding protection) |

> There is **no** separate MCP port setting. `/mcp` rides the single hwebserver port above.

## Authentication

MCP Bearer token authentication is opt-in. When `SYNAPSE_API_KEY` is set (or `~/.synapse/auth.key` exists), the `/mcp` endpoint requires an `Authorization: Bearer <token>` header on all requests. Without a key configured, auth is disabled (backward compatible).

SYNAPSE assumes a **single-user, localhost** posture, and that assumption is load-bearing for safety: on the live `/synapse` handler path `execute_python` / `execute_vex` run **ungated** — no per-command permission check (see CLAUDE.md §1.2) — so keeping both the WebSocket (`/synapse`) and MCP HTTP (`/mcp`) surfaces on a single-user local machine is what contains arbitrary code execution. Do **not** expose either surface to an untrusted network. Because both surfaces share one port, opening that one port exposes **both** — there is no configuration in which you can publish `/mcp` while keeping `/synapse` private. A multi-user / studio-LAN / VPN deployment requires a handler-layer auth gate (tracked as **SEC-1** in `docs/SCIENCE_HARNESS_LEDGER.md`), which is **not yet shipped**; the Bearer-token auth above gates `/mcp` when `SYNAPSE_API_KEY` is set, but does not by itself make `execute_python` safe on a shared host.

```bash
# Set API key via environment variable
export SYNAPSE_API_KEY="your-secret-key"

# Or create a key file
echo "your-secret-key" > ~/.synapse/auth.key
```

MCP clients that support auth headers can pass the token. For Claude Code, configure via `.claude/settings.json`:

```json
{
  "mcpServers": {
    "synapse": {
      "type": "streamableHttp",
      "url": "http://localhost:9999/mcp",
      "headers": {
        "Authorization": "Bearer your-secret-key"
      }
    }
  }
}
```

## SSE Streaming

SSE (Server-Sent Events) streaming is not yet supported. Houdini's hwebserver uses a C++ request-response model that doesn't support long-lived streaming connections. Use `resources/read` polling as an alternative for real-time data.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **"Connection refused"** | The bridge isn't running -- it never auto-starts | Click **Connect** in the SYNAPSE panel footer. Headless: `from synapse.server.hwebserver_adapter import start_hwebserver; start_hwebserver(port=9999)` in Houdini's Python Shell. |
| **Connected, but on the wrong port** | Something else held 9999, or the server was started with a different `port=` | Read `~/.synapse/bridge.json` for the real bound endpoint and point your client there. No file = not running. |
| **Panel is open but nothing listens** | Opening the panel is not starting the bridge | The footer **Connect** button starts it. The shelf tool only opens the panel -- it starts no server. |
| **"Unknown session"** | `Mcp-Session-Id` header missing or expired | Send a new `initialize` request for a fresh session. |
| **"Method not found"** | Calling an unimplemented MCP method | Supported: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `resources/templates/list`, `ping`. |
| **`ModuleNotFoundError: mcp` / `websockets`** | The stdio bridge's two deps aren't installed | `pip install mcp websockets`. Only the stdio path needs them -- the in-Houdini panel does not. |
| **Tools timing out** | Render and wedge operations take minutes | Default timeout is 10s for most tools, 30s for execution/introspection, 120s for render/wedge. Raise your client's timeout. |
| **Stale version in `serverInfo`** | Installed package metadata is stale | Run `pip install -e .` from the SYNAPSE repo root to refresh it. |
