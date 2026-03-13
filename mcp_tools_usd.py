"""MCP Tool Group: USD / Solaris / Materials

Knowledge preamble and tool manifest for USD scene assembly tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "USD TOOLS: Stage inspection, prim creation, attribute manipulation, "
    "material assignment, and scene assembly. "
    "CRITICAL: USD parameter names are encoded -- xn__inputsintensity_i0a "
    "(not 'intensity'), xn__inputscolor_vya (not 'color'), "
    "xn__inputsexposure_vya (not 'exposure'). Always inspect first. "
    "COMPOSITION: Stronger opinions win. Layer order matters in sublayers "
    "and merges -- use synapse_validate_ordering before rendering. "
    "MATERIALS: matlib.cook(force=True) MUST be called before createNode() "
    "on shader children. MaterialX standard_surface is the default shader. "
    "SOLARIS CHAIN: Always create LOP nodes in /stage, never /obj. "
    "Canonical order: SOPCreate \u2192 MaterialLibrary \u2192 AssignMaterial \u2192 "
    "Camera \u2192 Lights \u2192 RenderProperties \u2192 OUTPUT null. Wire linearly "
    "with setInput(0, prev). Use sopcreate (not sopimport) for new geometry."
)

# Tools in this group
TOOL_NAMES = [
    "houdini_stage_info",
    "houdini_get_usd_attribute",
    "houdini_set_usd_attribute",
    "houdini_create_usd_prim",
    "houdini_modify_usd_prim",
    "houdini_reference_usd",
    "houdini_query_prims",
    "houdini_manage_variant_set",
    "houdini_manage_collection",
    "houdini_configure_light_linking",
    "houdini_create_textured_material",
    "houdini_create_material",
    "houdini_assign_material",
    "houdini_read_material",
    "synapse_solaris_assemble_chain",
    "synapse_solaris_build_graph",
]

# Dispatch entries for this group
DISPATCH_KEYS = {
    "houdini_stage_info":           ("get_stage_info",          "stage_info_payload"),
    "houdini_get_usd_attribute":    ("get_usd_attribute",       "filter_keys:node,prim_path,attribute_name"),
    "houdini_set_usd_attribute":    ("set_usd_attribute",       "filter_keys:node,prim_path,attribute_name,value"),
    "houdini_create_usd_prim":      ("create_usd_prim",        "filter_keys:node,prim_path,prim_type"),
    "houdini_modify_usd_prim":      ("modify_usd_prim",        "filter_keys:node,prim_path,kind,purpose,active"),
    "houdini_reference_usd":        ("reference_usd",          "identity"),
    "houdini_query_prims":          ("query_prims",            "identity"),
    "houdini_manage_variant_set":   ("manage_variant_set",     "identity"),
    "houdini_manage_collection":    ("manage_collection",      "identity"),
    "houdini_configure_light_linking": ("configure_light_linking", "identity"),
    "houdini_create_textured_material": ("create_textured_material", "identity"),
    "houdini_create_material":      ("create_material",        "identity"),
    "houdini_assign_material":      ("assign_material",        "identity"),
    "houdini_read_material":        ("read_material",          "identity"),
    "synapse_solaris_assemble_chain": ("solaris_assemble_chain", "identity"),
    "synapse_solaris_build_graph":    ("solaris_build_graph",    "identity"),
}
