"""MCP Tool Group: TOPS / PDG

Knowledge preamble and tool manifest for PDG pipeline tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "TOPS/PDG TOOLS: Pipeline orchestration for batch processing, wedging, "
    "and distributed rendering. "
    "WORKFLOW: Generate work items first (tops_generate_items or tops_setup_wedge), "
    "then cook (tops_cook_node). Use tops_pipeline_status for health checks, "
    "tops_diagnose for failure analysis. "
    "SELF-HEALING: tops_cook_and_validate auto-retries on failure with dirty+recook. "
    "RENDERING: tops_render_sequence creates a full frame sequence pipeline. "
    "tops_multi_shot handles multi-camera/multi-shot renders. "
    "MONITORING: tops_monitor_stream provides push-based event callbacks."
)

# Tools in this group
TOOL_NAMES = [
    "houdini_wedge",
    "tops_get_work_items",
    "tops_get_dependency_graph",
    "tops_get_cook_stats",
    "tops_cook_node",
    "tops_generate_items",
    "tops_configure_scheduler",
    "tops_cancel_cook",
    "tops_dirty_node",
    "tops_setup_wedge",
    "tops_batch_cook",
    "tops_query_items",
    "tops_cook_and_validate",
    "tops_diagnose",
    "tops_pipeline_status",
    "tops_monitor_stream",
    "tops_render_sequence",
    "tops_multi_shot",
]

# Dispatch entries for this group
DISPATCH_KEYS = {
    "houdini_wedge":              ("wedge",                    "identity"),
    "tops_get_work_items":        ("tops_get_work_items",      "identity"),
    "tops_get_dependency_graph":  ("tops_get_dependency_graph", "identity"),
    "tops_get_cook_stats":        ("tops_get_cook_stats",      "identity"),
    "tops_cook_node":             ("tops_cook_node",           "identity"),
    "tops_generate_items":        ("tops_generate_items",      "identity"),
    "tops_configure_scheduler":   ("tops_configure_scheduler", "identity"),
    "tops_cancel_cook":           ("tops_cancel_cook",         "identity"),
    "tops_dirty_node":            ("tops_dirty_node",          "identity"),
    "tops_setup_wedge":           ("tops_setup_wedge",         "identity"),
    "tops_batch_cook":            ("tops_batch_cook",          "identity"),
    "tops_query_items":           ("tops_query_items",         "identity"),
    "tops_cook_and_validate":     ("tops_cook_and_validate",   "identity"),
    "tops_diagnose":              ("tops_diagnose",            "identity"),
    "tops_pipeline_status":       ("tops_pipeline_status",     "identity"),
    "tops_monitor_stream":        ("tops_monitor_stream",      "identity"),
    "tops_render_sequence":       ("tops_render_sequence",     "identity"),
    "tops_multi_shot":            ("tops_multi_shot",          "identity"),
}
