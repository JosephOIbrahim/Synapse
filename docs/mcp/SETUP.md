# Connecting to SYNAPSE via MCP

SYNAPSE exposes a standard MCP (Model Context Protocol) endpoint that any MCP-compliant client can connect to -- Claude Code, Cursor, VS Code, Windsurf, Cline, or custom agents.

**Protocol:** MCP 2025-06-18 (Streamable HTTP transport)
**Endpoint:** `http://localhost:8008/mcp`
**Method:** `POST` with JSON-RPC 2.0 body

## Prerequisites

1. **Houdini must be running** with SYNAPSE started (shelf button or startup script)
2. SYNAPSE runs two servers simultaneously:
   - **WebSocket** on port 9999 (primary transport for `mcp_server.py` stdio bridge and direct WS clients)
   - **MCP HTTP** on port 8008 (Streamable HTTP for direct MCP clients -- Claude Code, Cursor, etc.)
3. Clicking the **Synapse** shelf button starts both servers automatically

To verify SYNAPSE is running, open a terminal:

```bash
curl -s -X POST http://localhost:8008/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"clientInfo":{"name":"test"}}}'
```

You should get back a JSON response with `protocolVersion` and `capabilities`.

## Claude Code

Add to your MCP server configuration (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "synapse": {
      "type": "streamableHttp",
      "url": "http://localhost:8008/mcp"
    }
  }
}
```

Claude Code will auto-discover all SYNAPSE tools on connection.

## Cursor / VS Code / Other MCP Clients

Most MCP clients support Streamable HTTP transport. Point them at:

```
URL:       http://localhost:8008/mcp
Transport: Streamable HTTP
```

Consult your client's documentation for the exact configuration format.

## Custom Agents (Python)

```python
import json
import requests

BASE = "http://localhost:8008/mcp"

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

SYNAPSE exposes 49 tools across these categories:

| Category | Tools | Examples |
|----------|-------|---------|
| Scene | 2 | `houdini_scene_info`, `houdini_get_selection` |
| Nodes | 3 | `houdini_create_node`, `houdini_delete_node`, `houdini_connect_nodes` |
| Parameters | 2 | `houdini_get_parm`, `houdini_set_parm` |
| Execution | 2 | `houdini_execute_python`, `houdini_execute_vex` |
| USD/Solaris | 5 | `houdini_stage_info`, `houdini_create_usd_prim`, `houdini_set_usd_attribute` |
| Materials | 3 | `houdini_create_material`, `houdini_assign_material`, `houdini_read_material` |
| Render | 4 | `houdini_render`, `houdini_capture_viewport`, `synapse_validate_frame` |
| TOPS/PDG | 6 | `houdini_wedge`, `tops_get_work_items`, `tops_cook_node` |
| Introspection | 3 | `synapse_inspect_scene`, `synapse_inspect_node`, `synapse_inspect_selection` |
| Memory | 7 | `synapse_context`, `synapse_search`, `synapse_recall`, `synapse_decide` |
| Knowledge | 1 | `synapse_knowledge_lookup` |
| System | 7 | `synapse_ping`, `synapse_health`, `synapse_batch`, `synapse_metrics` |

Use `tools/list` to get the full list with descriptions and input schemas.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SYNAPSE_PORT` | `9999` | WebSocket server port |
| `SYNAPSE_MCP_PORT` | `8008` | MCP HTTP server port |
| `SYNAPSE_PATH` | `/synapse` | WebSocket path (MCP always uses `/mcp`) |
| `SYNAPSE_API_KEY` | (none) | API key for both WebSocket and MCP Bearer token auth |

## Authentication

MCP Bearer token authentication is opt-in. When `SYNAPSE_API_KEY` is set (or `~/.synapse/auth.key` exists), the `/mcp` endpoint requires an `Authorization: Bearer <token>` header on all requests. Without a key configured, auth is disabled (backward compatible).

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
      "url": "http://localhost:8008/mcp",
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

**"Connection refused"** -- Houdini isn't running or SYNAPSE hasn't started. Open Houdini and click the SYNAPSE shelf button, or run `from synapse.server.start_hwebserver import main; main()` in Houdini's Python Shell.

**"Unknown session"** -- Your `Mcp-Session-Id` header is missing or expired. Send a new `initialize` request to get a fresh session.

**"Method not found"** -- You're calling an MCP method that isn't implemented yet. Supported methods: `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `resources/templates/list`, `ping`.

**Tools timing out** -- Render and wedge operations can take minutes. Default timeout is 10s for most tools, 30s for execution/introspection, 120s for render/wedge. Adjust your client's timeout accordingly.

**Stale version in `serverInfo`** -- If the version string in the `initialize` response is outdated, the installed package metadata may be stale. Run `pip install -e .` from the SYNAPSE repo root to refresh it.
