# Connecting to SYNAPSE via MCP

SYNAPSE exposes a standard MCP (Model Context Protocol) endpoint that any MCP-compliant client can connect to -- Claude Code, Cursor, VS Code, Windsurf, Cline, or custom agents.

> **Using the Houdini panel?** Start with [installation](../getting-started/installation.md) and [your first session](../getting-started/quickstart.md). This page connects an **external** MCP client, which has different permissions from normal panel chat. See the [execution and permission map](../architecture/overview.md#execution-paths).

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
3. **You clicked the separate `Connect` button in the panel.** `Connect models` chooses an AI service; it does not start the bridge.

> The shelf tool opens the panel. The **Connect** button starts the local bridge and remains labeled **Connect**; read the connection status or run **Doctor** to check the result. The panel's local fallback is a separate path, used only when a tool request was definitely not sent through MCP.

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

**Use this file to discover the endpoint, then verify it responds.** A discovery file can be stale after a process exits; file presence alone does not prove a live connection.

### Verify it is up

```bash
curl -s -X POST http://localhost:9999/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test"}}}'
```

> ✅ **You should see** a JSON response containing `protocolVersion` and `capabilities`.
> **If you see** `Connection refused`, check the discovered endpoint, click **Connect**, then run **Doctor**.

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

> This adapter runs in the external client's Python. From the repository, install its tested dependency set with `python -m pip install -e ".[mcp]"`. This preserves the MCP version pin required by the adapter; an unpinned install can change its API. The in-Houdini panel does not require an external MCP client.

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

**Call `tools/list` on the connected endpoint** for its registered names,
descriptions and input schemas. The source authority is the
[tool registry](../../python/synapse/mcp/_tool_registry.py); the README's count is
checked against that registry. The stdio adapter adds local helper tools, so its
list need not have the same total as HTTP MCP. Tool availability does not imply
that normal panel chat permits every tool.

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

SYNAPSE assumes a **single-user, localhost** setup. Bearer authentication identifies
a client; it does not provide per-operation artist approval or sandbox executed
Python/VEX. External clients do not inherit the normal panel worker's restricted
tool policy. Both endpoints share the server port, so exposing it exposes both
surfaces. A shared or untrusted-network deployment needs additional isolation and
policy work. See the [current permission map](../architecture/overview.md#permission-and-undo-boundaries).

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

The HTTP handler supports SSE-formatted **short polling responses**, including
queued progress events; it does not hold a long-lived event stream open.
Clients must poll again for subsequent updates. See the
[GET handler and event queue](../../python/synapse/mcp/server.py).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| **"Connection refused"** | The endpoint is wrong or the bridge is unavailable | Check the discovered endpoint, click **Connect**, then run **Doctor**. |
| **Connected, but on the wrong port** | The server was started at another address/port, or the record is stale | Read the configured discovery file and verify the endpoint responds. |
| **Panel is open but nothing listens** | Opening the panel does not start the bridge | Use the separate **Connect** control. |
| **"Unknown session"** | `Mcp-Session-Id` header missing or expired | Send a new `initialize` request for a fresh session. |
| **"Method not found"** | Calling an unimplemented MCP method | Supported: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `resources/templates/list`, `ping`. |
| **`ModuleNotFoundError: mcp` / `websockets`** | Dependencies are missing in the stdio client's Python | From the repository, run `python -m pip install -e ".[mcp]"` in that environment. |
| **Tools timing out** | The client or host wait ended | Check the operation and [shared timeout table](../../python/synapse/core/timeouts.py). A timeout does not prove the action stopped; inspect before retrying a scene mutation. |
| **Stale version in `serverInfo`** | Installed package metadata is stale | Run `pip install -e .` from the SYNAPSE repo root to refresh it. |
