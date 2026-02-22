# Quick Start

## 1. Start the Synapse Server

Inside Houdini's Python Shell:

```python
from synapse.server import SynapseServer
server = SynapseServer(port=9999)
server.start()
```

Or use the Synapse shelf tool in Houdini.

## 2. Connect via MCP

Add to your Claude Desktop config (`claude_desktop_config.json`):

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

## 3. Use Tools

Once connected, Claude can use Synapse tools:

- **Scene**: `houdini_scene_info`, `houdini_get_selection`
- **Nodes**: `houdini_create_node`, `houdini_delete_node`, `houdini_connect_nodes`
- **Parameters**: `houdini_get_parm`, `houdini_set_parm`
- **USD**: `houdini_create_usd_prim`, `houdini_set_usd_attribute`, `houdini_get_usd_attribute`
- **Materials**: `houdini_create_material`, `houdini_assign_material`, `houdini_read_material`
- **Render**: `houdini_render`, `houdini_capture_viewport`, `houdini_render_settings`
- **Memory**: `synapse_context`, `synapse_search`, `synapse_add_memory`, `synapse_decide`
- **Knowledge**: `synapse_knowledge_lookup`
- **Inspection**: `synapse_inspect_scene`, `synapse_inspect_node`, `synapse_inspect_selection`

## 4. Authentication (Optional)

Set an API key via environment variable:

```bash
export SYNAPSE_API_KEY="your-secret-key"
```

Or create `~/.synapse/auth.key`:

```
# Lines starting with # are comments
your-secret-key
```

When enabled, the first WebSocket message must be an `authenticate` command.
