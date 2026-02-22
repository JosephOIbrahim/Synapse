# MCP Tools Reference

Synapse exposes 37 MCP tools to Claude Desktop/Code. Each tool maps to a command type in the wire protocol.

## Scene Operations

| Tool | Description |
|------|-------------|
| `houdini_scene_info` | Get HIP file path, frame, FPS, frame range |
| `houdini_get_selection` | Get currently selected nodes |
| `houdini_create_node` | Create a new node |
| `houdini_delete_node` | Delete a node by path |
| `houdini_connect_nodes` | Connect output of one node to input of another |
| `houdini_get_parm` | Read a parameter value |
| `houdini_set_parm` | Set a parameter value |
| `houdini_set_keyframe` | Set a keyframe on a parameter |

## Code Execution

| Tool | Description |
|------|-------------|
| `houdini_execute_python` | Execute Python code in Houdini's runtime |
| `houdini_execute_vex` | Execute VEX code via attribwrangle |

## USD / Solaris

| Tool | Description |
|------|-------------|
| `houdini_stage_info` | Get USD prim list and types |
| `houdini_create_usd_prim` | Create a USD prim on the stage |
| `houdini_modify_usd_prim` | Modify prim metadata (kind, purpose, active) |
| `houdini_get_usd_attribute` | Read a USD attribute value |
| `houdini_set_usd_attribute` | Set a USD attribute value |
| `houdini_reference_usd` | Import a USD file via reference or sublayer |

## Materials

| Tool | Description |
|------|-------------|
| `houdini_create_material` | Create a material with shader |
| `houdini_assign_material` | Assign material to geometry |
| `houdini_read_material` | Read material assignments and settings |

## Rendering

| Tool | Description |
|------|-------------|
| `houdini_render` | Render a frame (Karma XPU/CPU, Mantra) |
| `houdini_capture_viewport` | Capture viewport as image |
| `houdini_render_settings` | Read/modify render settings |
| `houdini_wedge` | Run TOPs/PDG parameter wedge |

## Memory

| Tool | Description |
|------|-------------|
| `synapse_context` | Get project context from memory |
| `synapse_search` | Search project memory |
| `synapse_recall` | Recall relevant memories for context |
| `synapse_add_memory` | Add a memory entry |
| `synapse_decide` | Record a decision with reasoning |

## Knowledge

| Tool | Description |
|------|-------------|
| `synapse_knowledge_lookup` | Look up Houdini knowledge via RAG |

## Inspection

| Tool | Description |
|------|-------------|
| `synapse_inspect_scene` | Bird's-eye view of the scene |
| `synapse_inspect_node` | Deep-dive into a single node |
| `synapse_inspect_selection` | Inspect currently selected nodes |

## System

| Tool | Description |
|------|-------------|
| `synapse_ping` | Health check |
| `synapse_health` | System health with resilience status |
| `synapse_metrics` | Prometheus-format metrics |
| `synapse_router_stats` | Routing cascade statistics |
| `synapse_list_recipes` | Available recipe patterns |
| `synapse_batch` | Execute multiple commands in one round-trip |

## Timeouts

| Category | Timeout |
|----------|---------|
| Default | 10s |
| Execute (Python/VEX), Inspect | 30s |
| Batch | 60s |
| Render, Wedge | 120s |
