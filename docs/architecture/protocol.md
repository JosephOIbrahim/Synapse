# Wire Protocol

## Transport

Default: `ws://localhost:9999/synapse`

Protocol version: `4.0.0`

## Message Format

### Request (Client -> Server)

```json
{
  "type": "create_node",
  "id": "req-001",
  "payload": {
    "parent": "/obj",
    "type": "geo",
    "name": "my_geo"
  },
  "sequence": 1
}
```

### Response (Server -> Client)

```json
{
  "type": "create_node",
  "id": "req-001",
  "status": "ok",
  "data": {
    "path": "/obj/my_geo"
  },
  "sequence": 1
}
```

## Command Types

35 command types are supported. See `synapse.core.protocol.CommandType` for the full enumeration.

### Scene Operations
`create_node`, `delete_node`, `connect_nodes`, `get_parm`, `set_parm`, `get_scene_info`, `get_selection`

### Code Execution
`execute_python`, `execute_vex`

### USD Operations
`create_usd_prim`, `modify_usd_prim`, `get_usd_attribute`, `set_usd_attribute`, `get_stage_info`

### Rendering
`capture_viewport`, `render`, `set_keyframe`, `render_settings`, `wedge`

### Assets
`reference_usd`, `create_material`, `assign_material`, `read_material`

### Knowledge
`knowledge_lookup`

### Inspection
`inspect_selection`, `inspect_scene`, `inspect_node`

### Memory
`context`, `search`, `add_memory`, `decide`, `recall`

### System
`batch_commands`, `ping`, `get_health`

## Parameter Aliases

Parameter names resolve through `synapse.core.aliases` (38+ mappings). For example, `node`, `path`, and `node_path` all resolve to the canonical `node` parameter.

## API

See [Protocol API Reference](../api/core/protocol.md) for full class documentation.
