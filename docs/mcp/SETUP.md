# Connecting to SYNAPSE via MCP

SYNAPSE exposes a standard MCP (Model Context Protocol) endpoint that any MCP-compliant client can connect to -- Claude Code, Cursor, VS Code, Windsurf, Cline, or custom agents.

**Protocol:** MCP 2025-06-18 (Streamable HTTP transport)
**Endpoint:** `http://localhost:9999/mcp`
**Method:** `POST` with JSON-RPC 2.0 body

## Prerequisites

1. **Houdini must be running** with SYNAPSE started (shelf button or startup script)
2. The hwebserver must be active on port 9999 (default)

To verify SYNAPSE is running, open a terminal:

```bash
curl -s -X POST http://localhost:9999/mcp \
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
      "url": "http://localhost:9999/mcp"
    }
  }
}
```

Claude Code will auto-discover all 44 SYNAPSE tools on connection.

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

SYNAPSE exposes 44 tools across these categories:

| Category | Tools | Examples |
|----------|-------|---------|
| Scene | 2 | `houdini_scene_info`, `houdini_get_selection` |
| Nodes | 3 | `houdini_create_node`, `houdini_delete_node`, `houdini_connect_nodes` |
| Parameters | 2 | `houdini_get_parm`, `houdini_set_parm` |
| Execution | 2 | `houdini_execute_python`, `houdini_execute_vex` |
| USD/Solaris | 5 | `houdini_stage_info`, `houdini_create_usd_prim`, `houdini_set_usd_attribute` |
| Materials | 3 | `houdini_create_material`, `houdini_assign_material`, `houdini_read_material` |
| Render | 4 | `houdini_render`, `houdini_capture_viewport`, `synapse_validate_frame` |
| Introspection | 3 | `synapse_inspect_scene`, `synapse_inspect_node`, `synapse_inspect_selection` |
| Memory | 7 | `synapse_context`, `synapse_search`, `synapse_recall`, `synapse_decide` |
| Knowledge | 1 | `synapse_knowledge_lookup` |
| System | 7 | `synapse_ping`, `synapse_health`, `synapse_batch`, `synapse_metrics` |

Use `tools/list` to get the full list with descriptions and input schemas.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SYNAPSE_PORT` | `9999` | Server port |
| `SYNAPSE_PATH` | `/synapse` | WebSocket path (MCP always uses `/mcp`) |
| `SYNAPSE_API_KEY` | (none) | API key for WebSocket auth (MCP sessions do not require auth in Phase 1) |

## Troubleshooting

**"Connection refused"** -- Houdini isn't running or SYNAPSE hasn't started. Open Houdini and click the SYNAPSE shelf button, or run `from synapse.server.start_hwebserver import main; main()` in Houdini's Python Shell.

**"Unknown session"** -- Your `Mcp-Session-Id` header is missing or expired. Send a new `initialize` request to get a fresh session.

**"Method not found"** -- You're calling an MCP method that isn't implemented yet. Phase 1 supports: `initialize`, `tools/list`, `tools/call`, `ping`. Resources and prompts are Phase 2.

**Tools timing out** -- Render and wedge operations can take minutes. Default timeout is 10s for most tools, 30s for execution/introspection, 120s for render/wedge. Adjust your client's timeout accordingly.
