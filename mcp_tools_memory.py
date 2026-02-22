"""MCP Tool Group: Memory / Knowledge / HDA / Metrics

Knowledge preamble and tool manifest for memory and project intelligence tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "MEMORY TOOLS: Project memory, scene memory, and knowledge lookup. "
    "START EVERY SESSION with synapse_project_setup -- this loads project history, "
    "decisions, and scene context. Without it, you have no memory of past work. "
    "MEMORY EVOLUTION: Charmander (markdown) -> Charmeleon (indexed) -> Charizard (USD). "
    "Use synapse_memory_write to record decisions and experiments. "
    "Use synapse_knowledge_lookup before guessing parameter names or node types. "
    "HDA TOOLS: Create, promote parameters, set help, and package HDAs. "
    "hda_package is the high-level orchestrator -- one call to create a full HDA."
)

# Tools in this group
TOOL_NAMES = [
    "synapse_knowledge_lookup",
    "synapse_context",
    "synapse_search",
    "synapse_recall",
    "synapse_decide",
    "synapse_add_memory",
    "synapse_project_setup",
    "synapse_memory_write",
    "synapse_memory_query",
    "synapse_memory_status",
    "synapse_evolve_memory",
    "synapse_metrics",
    "synapse_router_stats",
    "synapse_list_recipes",
    "synapse_live_metrics",
    "houdini_hda_create",
    "houdini_hda_promote_parm",
    "houdini_hda_set_help",
    "houdini_hda_package",
    "houdini_hda_list",
]

# Dispatch entries for this group
DISPATCH_KEYS = {
    "synapse_knowledge_lookup": ("knowledge_lookup", "filter_keys:query"),
    "synapse_context":          ("context",          "passthrough"),
    "synapse_search":           ("search",           "filter_keys:query"),
    "synapse_recall":           ("recall",           "filter_keys:query"),
    "synapse_decide":           ("decide",           "decide_payload"),
    "synapse_add_memory":       ("add_memory",       "add_memory_payload"),
    "synapse_project_setup":    ("project_setup",    "identity"),
    "synapse_memory_write":     ("memory_write",     "identity"),
    "synapse_memory_query":     ("memory_query",     "identity"),
    "synapse_memory_status":    ("memory_status",    "passthrough"),
    "synapse_evolve_memory":    ("evolve_memory",    "passthrough"),
    "synapse_metrics":          ("get_metrics",      "passthrough"),
    "synapse_router_stats":     ("router_stats",     "passthrough"),
    "synapse_list_recipes":     ("list_recipes",     "passthrough"),
    "synapse_live_metrics":     ("get_live_metrics", "identity"),
    "houdini_hda_create":       ("hda_create",       "identity"),
    "houdini_hda_promote_parm": ("hda_promote_parm", "identity"),
    "houdini_hda_set_help":     ("hda_set_help",     "identity"),
    "houdini_hda_package":      ("hda_package",      "identity"),
    "houdini_hda_list":         ("hda_list",         "passthrough"),
}
