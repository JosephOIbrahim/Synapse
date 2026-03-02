"""MCP Tool Group: Scene / Node / Parameters

Knowledge preamble and tool manifest for scene manipulation tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "SCENE TOOLS: Manipulate the Houdini node graph. "
    "Always inspect before mutating -- use synapse_inspect_node or "
    "synapse_inspect_scene first. One mutation per tool call. "
    "Parameter names on USD/Solaris nodes use encoded format "
    "(e.g. xn__inputsintensity_i0a not 'intensity'). "
    "Use houdini_get_parm to read, houdini_set_parm to write. "
    "execute_python wraps in undo group -- automatic rollback on failure. "
    "CONTEXT AWARENESS: When creating Solaris/LOP node types (lights, cameras, "
    "materials, render settings), parent MUST be /stage."
)

# Tools in this group
TOOL_NAMES = [
    "synapse_ping",
    "synapse_health",
    "houdini_scene_info",
    "houdini_get_selection",
    "houdini_create_node",
    "houdini_delete_node",
    "houdini_connect_nodes",
    "houdini_get_parm",
    "houdini_set_parm",
    "houdini_execute_python",
    "houdini_execute_vex",
    "synapse_inspect_selection",
    "synapse_inspect_scene",
    "synapse_inspect_node",
    "houdini_network_explain",
    "houdini_undo",
    "houdini_redo",
    "synapse_batch",
]

# Dispatch entries for this group
# Map: tool_name -> (synapse_command_type, payload_builder_name)
# Resolved to callables by mcp_server.py at import time.
DISPATCH_KEYS = {
    "synapse_ping":          ("ping",            "passthrough"),
    "synapse_health":        ("get_health",      "passthrough"),
    "houdini_scene_info":    ("get_scene_info",  "passthrough"),
    "houdini_get_selection": ("get_selection",    "passthrough"),
    "houdini_create_node":   ("create_node",     "identity"),
    "houdini_delete_node":   ("delete_node",     "filter_keys:node"),
    "houdini_connect_nodes": ("connect_nodes",   "identity"),
    "houdini_get_parm":      ("get_parm",        "filter_keys:node,parm"),
    "houdini_set_parm":      ("set_parm",        "filter_keys:node,parm,value"),
    "houdini_execute_python":("execute_python",  "execute_python_payload"),
    "houdini_execute_vex":   ("execute_vex",     "identity"),
    "synapse_inspect_selection": ("inspect_selection", "identity"),
    "synapse_inspect_scene":    ("inspect_scene",     "identity"),
    "synapse_inspect_node":     ("inspect_node",      "identity"),
    "houdini_network_explain":  ("network_explain",   "network_explain"),
    "houdini_undo":             ("undo",              "passthrough"),
    "houdini_redo":             ("redo",              "passthrough"),
    "synapse_batch":            ("batch_commands",    "identity"),
}
