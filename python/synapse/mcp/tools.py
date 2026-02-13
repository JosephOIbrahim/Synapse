"""
MCP Tool Registry

Maps all existing SYNAPSE command handlers to MCP tool definitions with
JSON Schema input schemas and MCP annotations. Provides dispatch_tool()
to bridge MCP tools/call requests to SynapseHandler.handle().

This module runs INSIDE Houdini (via hwebserver), so dispatch goes
directly through the handler — no WebSocket hop.
"""

import json
import time
from typing import Any

try:
    import orjson
    def _dumps_str(obj) -> str:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode()
except ImportError:
    def _dumps_str(obj) -> str:
        return json.dumps(obj, sort_keys=True)

from ..core.protocol import SynapseCommand


# =========================================================================
# Dispatch ID counter (He2025: sequential, not uuid4)
# =========================================================================

_call_counter = 0


def _next_call_id(tool_name: str) -> str:
    global _call_counter
    _call_counter += 1
    return f"mcp-{tool_name}-{_call_counter}"


# =========================================================================
# Payload builders (transform MCP arguments to handler payload)
# =========================================================================

def _passthrough(_args: dict) -> dict:
    return {}


def _identity(args: dict) -> dict:
    return dict(args)


def _execute_python_payload(args: dict) -> dict:
    p = {"content": args["code"]}
    if "dry_run" in args:
        p["dry_run"] = args["dry_run"]
    if "atomic" in args:
        p["atomic"] = args["atomic"]
    return p


def _stage_info_payload(args: dict) -> dict:
    p = {}
    if "node" in args:
        p["node"] = args["node"]
    return p


def _decide_payload(args: dict) -> dict:
    p = {"decision": args["decision"]}
    if "reasoning" in args:
        p["reasoning"] = args["reasoning"]
    if "alternatives" in args:
        alt = args["alternatives"]
        p["alternatives"] = (
            [a.strip() for a in alt.split(",") if a.strip()]
            if isinstance(alt, str) else alt
        )
    return p


def _add_memory_payload(args: dict) -> dict:
    p = {"content": args["content"]}
    if "memory_type" in args:
        p["memory_type"] = args["memory_type"]
    if "tags" in args:
        p["tags"] = args["tags"]
    return p


def _filter_keys(keys):
    """Return a payload builder that passes through only the specified keys."""
    def _builder(args: dict) -> dict:
        return {k: args[k] for k in keys if k in args}
    return _builder


# =========================================================================
# Tool definitions
# =========================================================================
# Each entry: (name, command_type, payload_builder, description,
#              inputSchema, read_only, destructive, idempotent)

_EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": []}

# Compact tool definitions — expanded into full MCP Tool JSON by get_tools()
_TOOL_DEFS: list[tuple] = [
    # -- Utility --
    ("synapse_ping", "ping", _passthrough,
     "Check if Houdini/Synapse is connected and responding.",
     _EMPTY_SCHEMA, True, False, True),
    ("synapse_health", "get_health", _passthrough,
     "Get system health status including resilience layer.",
     _EMPTY_SCHEMA, True, False, True),

    # -- Scene --
    ("houdini_scene_info", "get_scene_info", _passthrough,
     "Get current Houdini scene info: HIP file path, current frame, FPS, and frame range.",
     _EMPTY_SCHEMA, True, False, True),
    ("houdini_get_selection", "get_selection", _passthrough,
     "Get the currently selected nodes in Houdini.",
     _EMPTY_SCHEMA, True, False, True),

    # -- Node operations --
    ("houdini_create_node", "create_node", _identity,
     "Create a new node in Houdini. Returns the path of the created node.",
     {"type": "object", "properties": {
         "parent": {"type": "string", "description": "Parent node path (e.g. '/obj')"},
         "type": {"type": "string", "description": "Node type (e.g. 'geo', 'null')"},
         "name": {"type": "string", "description": "Optional node name"},
     }, "required": ["parent", "type"]},
     False, True, False),

    ("houdini_delete_node", "delete_node",
     lambda a: {"node": a["node"]},
     "Delete a node in Houdini by its path.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Full path of the node to delete"},
     }, "required": ["node"]},
     False, True, False),

    ("houdini_connect_nodes", "connect_nodes", _identity,
     "Connect the output of one node to the input of another.",
     {"type": "object", "properties": {
         "source": {"type": "string", "description": "Source node path (output from)"},
         "target": {"type": "string", "description": "Target node path (input to)"},
         "source_output": {"type": "integer", "description": "Source output index (default: 0)"},
         "target_input": {"type": "integer", "description": "Target input index (default: 0)"},
     }, "required": ["source", "target"]},
     False, True, False),

    # -- Parameters --
    ("houdini_get_parm", "get_parm",
     lambda a: {"node": a["node"], "parm": a["parm"]},
     "Read a parameter value from a Houdini node.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Node path"},
         "parm": {"type": "string", "description": "Parameter name"},
     }, "required": ["node", "parm"]},
     True, False, True),

    ("houdini_set_parm", "set_parm",
     lambda a: {"node": a["node"], "parm": a["parm"], "value": a["value"]},
     "Set a parameter value on a Houdini node.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Node path"},
         "parm": {"type": "string", "description": "Parameter name"},
         "value": {"description": "Value to set"},
     }, "required": ["node", "parm", "value"]},
     False, True, True),

    # -- Execution --
    ("houdini_execute_python", "execute_python", _execute_python_payload,
     "Execute Python code in Houdini's runtime environment.",
     {"type": "object", "properties": {
         "code": {"type": "string", "description": "Python code to execute"},
         "dry_run": {"type": "boolean", "description": "Syntax-check only (default: false)"},
         "atomic": {"type": "boolean", "description": "Wrap in undo group (default: true)"},
     }, "required": ["code"]},
     False, True, False),

    ("houdini_execute_vex", "execute_vex", _identity,
     "Execute VEX code by creating an Attribute Wrangle node.",
     {"type": "object", "properties": {
         "snippet": {"type": "string", "description": "VEX code snippet"},
         "run_over": {"type": "string", "description": "Points, Primitives, Vertices, or Detail"},
         "input_node": {"type": "string", "description": "Optional input geometry node path"},
     }, "required": ["snippet"]},
     False, True, False),

    # -- USD/Solaris --
    ("houdini_stage_info", "get_stage_info", _stage_info_payload,
     "Get USD stage information: prim list and types.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Optional LOP node path"},
     }, "required": []},
     True, False, True),

    ("houdini_get_usd_attribute", "get_usd_attribute",
     _filter_keys(("node", "prim_path", "attribute_name")),
     "Read a USD attribute value from a prim on the stage.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node path (optional)"},
         "prim_path": {"type": "string", "description": "USD prim path"},
         "attribute_name": {"type": "string", "description": "USD attribute name"},
     }, "required": ["prim_path", "attribute_name"]},
     True, False, True),

    ("houdini_set_usd_attribute", "set_usd_attribute",
     _filter_keys(("node", "prim_path", "attribute_name", "value")),
     "Set a USD attribute on a prim.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node to wire after (optional)"},
         "prim_path": {"type": "string", "description": "USD prim path"},
         "attribute_name": {"type": "string", "description": "USD attribute name"},
         "value": {"description": "Value to set"},
     }, "required": ["prim_path", "attribute_name", "value"]},
     False, True, False),

    ("houdini_create_usd_prim", "create_usd_prim",
     _filter_keys(("node", "prim_path", "prim_type")),
     "Create a USD prim on the stage.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node to wire after (optional)"},
         "prim_path": {"type": "string", "description": "USD prim path to create"},
         "prim_type": {"type": "string", "description": "USD prim type (default: Xform)"},
     }, "required": ["prim_path"]},
     False, True, False),

    ("houdini_modify_usd_prim", "modify_usd_prim",
     _filter_keys(("node", "prim_path", "kind", "purpose", "active")),
     "Modify USD prim metadata: kind, purpose, or active state.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node to wire after (optional)"},
         "prim_path": {"type": "string", "description": "USD prim path"},
         "kind": {"type": "string", "description": "Model kind"},
         "purpose": {"type": "string", "description": "Prim purpose"},
         "active": {"type": "boolean", "description": "Whether the prim is active"},
     }, "required": ["prim_path"]},
     False, True, False),

    # -- Viewport / Render --
    ("houdini_capture_viewport", "capture_viewport", _identity,
     "Capture the Houdini viewport as an image.",
     {"type": "object", "properties": {
         "width": {"type": "integer", "description": "Width in pixels"},
         "height": {"type": "integer", "description": "Height in pixels"},
         "format": {"type": "string", "enum": ["jpeg", "png"], "description": "Image format"},
     }, "required": []},
     True, False, True),

    ("houdini_render", "render", _identity,
     "Render a frame using Karma XPU, Karma CPU, Mantra, or any ROP node.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "ROP node path (auto-discovers if omitted)"},
         "frame": {"type": "number", "description": "Frame to render"},
         "width": {"type": "integer", "description": "Override resolution width"},
         "height": {"type": "integer", "description": "Override resolution height"},
     }},
     False, True, False),

    ("synapse_validate_frame", "validate_frame", _identity,
     "Validate a rendered frame for quality issues: black frames, NaN, clipping, fireflies.",
     {"type": "object", "properties": {
         "image_path": {"type": "string", "description": "Path to rendered image"},
         "checks": {"type": "array", "items": {"type": "string"}, "description": "Checks to run (default: all)"},
         "thresholds": {"type": "object", "description": "Threshold overrides"},
     }, "required": ["image_path"]},
     True, False, True),

    # -- Keyframe / Render Settings --
    ("houdini_set_keyframe", "set_keyframe", _identity,
     "Set a keyframe on a node parameter at a specific frame.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Node path"},
         "parm": {"type": "string", "description": "Parameter name"},
         "value": {"type": "number", "description": "Value to set"},
         "frame": {"type": "number", "description": "Frame number"},
     }, "required": ["node", "parm", "value"]},
     False, True, False),

    ("houdini_render_settings", "render_settings", _identity,
     "Read and optionally modify render settings on a ROP or Karma node.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "ROP or render settings node path"},
         "settings": {"type": "object", "description": "Optional overrides"},
     }, "required": ["node"]},
     False, True, True),

    # -- TOPs / PDG --
    ("houdini_wedge", "wedge", _identity,
     "Run a TOPs/PDG wedge to explore parameter variations.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP network or wedge node path"},
         "parm": {"type": "string", "description": "Parameter to wedge"},
         "values": {"type": "array", "items": {"type": "number"}, "description": "Values to wedge over"},
     }, "required": ["node"]},
     False, True, False),

    # -- TOPS / PDG (Phase 1) --
    ("tops_get_work_items", "tops_get_work_items", _identity,
     "Get work items from a TOP node with optional state filtering.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "state_filter": {"type": "string", "description": "Filter by state: all, cooked, failed, cooking, scheduled, uncooked, cancelled (default: all)"},
         "include_attributes": {"type": "boolean", "description": "Include work item attributes (default: true)"},
         "limit": {"type": "integer", "description": "Max items to return (default: 100)"},
     }, "required": ["node"]},
     True, False, True),

    ("tops_get_dependency_graph", "tops_get_dependency_graph", _identity,
     "Get the dependency graph for a TOP network: nodes, types, work item counts, and edges.",
     {"type": "object", "properties": {
         "topnet_path": {"type": "string", "description": "TOP network path"},
         "depth": {"type": "integer", "description": "Traversal depth (-1 for full, default: -1)"},
     }, "required": ["topnet_path"]},
     True, False, True),

    ("tops_get_cook_stats", "tops_get_cook_stats", _identity,
     "Get cook statistics for a TOP node or network: work item counts by state and cook times.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node or network path"},
     }, "required": ["node"]},
     True, False, True),

    ("tops_cook_node", "tops_cook_node", _identity,
     "Cook a TOP node. Supports blocking/non-blocking and generate-only modes.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "generate_only": {"type": "boolean", "description": "Generate work items only, don't cook (default: false)"},
         "blocking": {"type": "boolean", "description": "Wait for cook to complete (default: true)"},
         "top_down": {"type": "boolean", "description": "Cook upstream nodes first (default: true)"},
     }, "required": ["node"]},
     False, True, False),

    ("tops_generate_items", "tops_generate_items", _identity,
     "Generate work items for a TOP node without cooking. Preview what a node will produce.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
     }, "required": ["node"]},
     False, True, False),

    # -- TOPS / PDG (Phase 2: Scheduler & Control) --
    ("tops_configure_scheduler", "tops_configure_scheduler", _identity,
     "Configure the scheduler for a TOP network: type, max concurrent, working directory.",
     {"type": "object", "properties": {
         "topnet_path": {"type": "string", "description": "TOP network path"},
         "scheduler_type": {"type": "string", "description": "Scheduler type (default: local)"},
         "max_concurrent": {"type": "integer", "description": "Max concurrent processes"},
         "working_dir": {"type": "string", "description": "PDG working directory"},
     }, "required": ["topnet_path"]},
     False, True, True),

    ("tops_cancel_cook", "tops_cancel_cook", _identity,
     "Cancel an active cook on a TOP node or network.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node or network path"},
     }, "required": ["node"]},
     False, True, False),

    ("tops_dirty_node", "tops_dirty_node", _identity,
     "Dirty a TOP node to clear cached results. Optionally dirty upstream nodes too.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "dirty_upstream": {"type": "boolean", "description": "Also dirty upstream nodes (default: false)"},
     }, "required": ["node"]},
     False, True, True),

    # -- TOPS / PDG (Phase 3: Advanced) --
    ("tops_setup_wedge", "tops_setup_wedge", _identity,
     "Set up a Wedge TOP node for parameter variation exploration.",
     {"type": "object", "properties": {
         "topnet_path": {"type": "string", "description": "TOP network path"},
         "wedge_name": {"type": "string", "description": "Name for the wedge node (default: wedge1)"},
         "attributes": {"type": "array", "items": {"type": "object"}, "description": "List of {name, type, start, end, steps}"},
     }, "required": ["topnet_path", "attributes"]},
     False, True, False),

    ("tops_batch_cook", "tops_batch_cook", _identity,
     "Cook multiple TOP nodes in sequence, collecting per-node results and aggregate stats.",
     {"type": "object", "properties": {
         "node_paths": {"type": "array", "items": {"type": "string"}, "description": "List of TOP node paths to cook"},
         "blocking": {"type": "boolean", "description": "Wait for each cook (default: true)"},
         "stop_on_error": {"type": "boolean", "description": "Stop on first error (default: true)"},
     }, "required": ["node_paths"]},
     False, True, False),

    ("tops_query_items", "tops_query_items", _identity,
     "Query work items by attribute value with filter operators (eq, gt, lt, gte, lte, contains, regex).",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "query_attribute": {"type": "string", "description": "Attribute name to filter on"},
         "filter_op": {"type": "string", "enum": ["eq", "gt", "lt", "gte", "lte", "contains", "regex"], "description": "Filter operator (default: eq)"},
         "filter_value": {"description": "Value to match against"},
     }, "required": ["node", "query_attribute", "filter_value"]},
     True, False, True),

    # -- TOPS / PDG (Phase 4: Autonomous Operations) --
    ("tops_cook_and_validate", "tops_cook_and_validate", _identity,
     "Cook a TOP node with automatic retry on failure. Self-healing: cook -> validate -> dirty -> retry.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "max_retries": {"type": "integer", "description": "Max retry attempts on failure (default: 0)"},
         "validate_states": {"type": "boolean", "description": "Check work item states after cook (default: true)"},
     }, "required": ["node"]},
     False, True, False),

    ("tops_diagnose", "tops_diagnose", _identity,
     "Diagnose failures on a TOP node: inspect failed items, scheduler config, upstream deps, and suggestions.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "TOP node path"},
         "include_scheduler": {"type": "boolean", "description": "Include scheduler info (default: true)"},
         "include_dependencies": {"type": "boolean", "description": "Include upstream dependency check (default: true)"},
     }, "required": ["node"]},
     True, False, True),

    ("tops_pipeline_status", "tops_pipeline_status", _identity,
     "Full health check for a TOP network: per-node status, aggregate stats, issues, and suggestions.",
     {"type": "object", "properties": {
         "topnet_path": {"type": "string", "description": "TOP network path"},
         "include_items": {"type": "boolean", "description": "Include per-node work items (default: false)"},
     }, "required": ["topnet_path"]},
     True, False, True),

    # -- USD Scene Assembly --
    ("houdini_reference_usd", "reference_usd", _identity,
     "Import a USD file into the stage via reference or sublayer.",
     {"type": "object", "properties": {
         "file": {"type": "string", "description": "Path to USD file"},
         "prim_path": {"type": "string", "description": "Target prim path (default: /)"},
         "mode": {"type": "string", "enum": ["reference", "sublayer"], "description": "Import mode"},
         "parent": {"type": "string", "description": "Parent LOP network path"},
     }, "required": ["file"]},
     False, True, False),

    # -- Materials --
    ("houdini_create_material", "create_material", _identity,
     "Create a material with a shader in the LOP network.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node to wire after (optional)"},
         "name": {"type": "string", "description": "Material name"},
         "shader_type": {"type": "string", "description": "Shader type (default: mtlxstandard_surface)"},
         "base_color": {"type": "array", "items": {"type": "number"}, "description": "[r, g, b] 0-1"},
         "metalness": {"type": "number", "description": "Metalness 0-1"},
         "roughness": {"type": "number", "description": "Roughness 0-1"},
     }, "required": []},
     False, True, False),

    ("houdini_assign_material", "assign_material", _identity,
     "Assign a material to geometry prims.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node to wire after (optional)"},
         "prim_pattern": {"type": "string", "description": "Geometry prim path or pattern"},
         "material_path": {"type": "string", "description": "USD material path"},
     }, "required": ["prim_pattern", "material_path"]},
     False, True, False),

    ("houdini_read_material", "read_material", _identity,
     "Read what material is assigned to a prim and its shader settings.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "LOP node (optional)"},
         "prim_path": {"type": "string", "description": "USD prim to inspect"},
     }, "required": ["prim_path"]},
     True, False, True),

    # -- Knowledge / RAG --
    ("synapse_knowledge_lookup", "knowledge_lookup",
     lambda a: {"query": a["query"]},
     "Look up Houdini knowledge: parameter names, node types, workflow guides.",
     {"type": "object", "properties": {
         "query": {"type": "string", "description": "Natural language query"},
     }, "required": ["query"]},
     True, False, True),

    # -- Introspection --
    ("synapse_inspect_selection", "inspect_selection", _identity,
     "Inspect selected nodes: parameters, connections, geometry stats, input graph.",
     {"type": "object", "properties": {
         "depth": {"type": "integer", "description": "Input traversal depth (default: 1)"},
     }, "required": []},
     True, False, True),

    ("synapse_inspect_scene", "inspect_scene", _identity,
     "Bird's-eye scene overview: node tree, context breakdown, warnings, sticky notes.",
     {"type": "object", "properties": {
         "root": {"type": "string", "description": "Starting node path (default: '/')"},
         "max_depth": {"type": "integer", "description": "Traversal depth (default: 3)"},
         "context_filter": {"type": "string", "description": "Filter by category (e.g. 'Sop')"},
     }, "required": []},
     True, False, True),

    ("synapse_inspect_node", "inspect_node", _identity,
     "Deep-dive into a single node: all parameters, expressions, code, geometry, HDA info.",
     {"type": "object", "properties": {
         "node": {"type": "string", "description": "Full node path"},
         "include_code": {"type": "boolean", "description": "Include VEX/Python code (default: true)"},
         "include_geometry": {"type": "boolean", "description": "Include geometry attributes (default: true)"},
         "include_expressions": {"type": "boolean", "description": "Include expressions (default: true)"},
     }, "required": ["node"]},
     True, False, True),

    # -- Memory --
    ("synapse_context", "context", _passthrough,
     "Get project context from Synapse memory.",
     _EMPTY_SCHEMA, True, False, True),

    ("synapse_search", "search",
     lambda a: {"query": a["query"]},
     "Search project memory for relevant entries.",
     {"type": "object", "properties": {
         "query": {"type": "string", "description": "Search query"},
     }, "required": ["query"]},
     True, False, True),

    ("synapse_recall", "recall",
     lambda a: {"query": a["query"]},
     "Recall relevant memories for a given context or question.",
     {"type": "object", "properties": {
         "query": {"type": "string", "description": "Context or question"},
     }, "required": ["query"]},
     True, False, True),

    ("synapse_decide", "decide", _decide_payload,
     "Record a decision in project memory with reasoning.",
     {"type": "object", "properties": {
         "decision": {"type": "string", "description": "The decision made"},
         "reasoning": {"type": "string", "description": "Why this decision was made"},
         "alternatives": {"type": "string", "description": "Alternatives considered"},
     }, "required": ["decision"]},
     False, False, False),

    ("synapse_add_memory", "add_memory", _add_memory_payload,
     "Add a memory entry to the project.",
     {"type": "object", "properties": {
         "content": {"type": "string", "description": "Memory content to store"},
         "memory_type": {"type": "string", "description": "Type (note, context, reference, task)"},
         "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags"},
     }, "required": ["content"]},
     False, False, True),

    # -- Scene Memory (Living Memory) --
    ("synapse_project_setup", "project_setup", _identity,
     "Initialize or load SYNAPSE project structure for the current scene.",
     {"type": "object", "properties": {
         "force_refresh": {"type": "boolean", "description": "Force re-read (default: false)"},
     }},
     False, False, True),

    ("synapse_memory_write", "memory_write", _identity,
     "Write a memory entry to scene or project memory.",
     {"type": "object", "properties": {
         "entry_type": {"type": "string", "description": "Type of memory entry"},
         "content": {"type": "object", "description": "Entry content"},
         "scope": {"type": "string", "enum": ["scene", "project", "both"], "description": "Where to write"},
     }, "required": ["entry_type", "content"]},
     False, False, False),

    ("synapse_memory_query", "memory_query", _identity,
     "Query scene or project memory.",
     {"type": "object", "properties": {
         "query": {"type": "string", "description": "Search query"},
         "scope": {"type": "string", "enum": ["scene", "project", "all"]},
         "type_filter": {"type": "string"},
     }, "required": ["query"]},
     True, False, True),

    ("synapse_memory_status", "memory_status", _passthrough,
     "Get memory system status: evolution stage, file sizes, session count.",
     _EMPTY_SCHEMA, True, False, True),

    ("synapse_evolve_memory", "evolve_memory", _passthrough,
     "Manually trigger memory evolution.",
     {"type": "object", "properties": {
         "scope": {"type": "string", "enum": ["scene", "project"]},
         "target_stage": {"type": "string", "enum": ["charmeleon", "charizard"]},
         "dry_run": {"type": "boolean", "description": "Preview without evolving (default: true)"},
     }},
     False, False, False),

    # -- Batch --
    ("synapse_batch", "batch_commands", _identity,
     "Execute multiple Synapse commands in a single round-trip.",
     {"type": "object", "properties": {
         "commands": {"type": "array", "items": {"type": "object"}, "description": "Commands to execute"},
         "atomic": {"type": "boolean", "description": "Wrap in undo group (default: true)"},
         "stop_on_error": {"type": "boolean", "description": "Stop on first error (default: false)"},
     }, "required": ["commands"]},
     False, True, False),

    # -- Metrics / Stats --
    ("synapse_metrics", "get_metrics", _passthrough,
     "Get Synapse metrics in Prometheus text format.",
     _EMPTY_SCHEMA, True, False, True),

    ("synapse_router_stats", "router_stats", _passthrough,
     "Get tier cascade routing statistics.",
     _EMPTY_SCHEMA, True, False, True),

    ("synapse_list_recipes", "list_recipes", _passthrough,
     "List all available recipes with names, descriptions, and trigger patterns.",
     _EMPTY_SCHEMA, True, False, True),
]


# =========================================================================
# Indexed lookup tables (built once at import time)
# =========================================================================

# tool_name -> (command_type, payload_builder)
_TOOL_DISPATCH: dict[str, tuple[str, Any]] = {}

# tool_name -> full MCP tool definition dict
_TOOL_JSON: dict[str, dict] = {}

for _def in _TOOL_DEFS:
    _name, _cmd, _builder, _desc, _schema, _ro, _destr, _idemp = _def
    _TOOL_DISPATCH[_name] = (_cmd, _builder)
    _TOOL_JSON[_name] = {
        "name": _name,
        "description": _desc,
        "inputSchema": _schema,
        "annotations": {
            "title": _name.replace("_", " ").replace("houdini ", "").replace("synapse ", "").title(),
            "readOnlyHint": _ro,
            "destructiveHint": _destr,
            "idempotentHint": _idemp,
            "openWorldHint": False,
        },
    }


# =========================================================================
# Public API
# =========================================================================

def get_tools() -> list[dict]:
    """Return all MCP tool definitions for tools/list response.

    Returns a list sorted by name (He2025 determinism).
    """
    return sorted(_TOOL_JSON.values(), key=lambda t: t["name"])


def get_tool_names() -> list[str]:
    """Return sorted list of all registered tool names."""
    return sorted(_TOOL_DISPATCH.keys())


def has_tool(name: str) -> bool:
    """Check if a tool name is registered."""
    return name in _TOOL_DISPATCH


def dispatch_tool(handler, tool_name: str, arguments: dict) -> dict:
    """Dispatch an MCP tools/call request to SynapseHandler.

    Args:
        handler: SynapseHandler instance.
        tool_name: MCP tool name (e.g. 'houdini_create_node').
        arguments: MCP tool arguments dict.

    Returns:
        MCP result dict with 'content' list and optional 'isError'.
    """
    entry = _TOOL_DISPATCH.get(tool_name)
    if entry is None:
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }

    cmd_type, payload_fn = entry
    payload = payload_fn(arguments)

    # Create a SynapseCommand and dispatch through the handler
    command = SynapseCommand(
        type=cmd_type,
        id=_next_call_id(tool_name),
        payload=payload,
    )
    response = handler.handle(command)

    if response.success:
        data = response.data
        text = _dumps_str(data) if isinstance(data, dict) else str(data or "")
        return {"content": [{"type": "text", "text": text}]}
    else:
        return {
            "content": [{"type": "text", "text": response.error or "Unknown error"}],
            "isError": True,
        }
