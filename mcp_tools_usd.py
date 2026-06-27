"""MCP Tool Group: USD / Solaris / Materials

Knowledge preamble and tool manifest for USD scene assembly tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "USD TOOLS: Stage inspection, prim creation, attribute manipulation, "
    "material assignment, and scene assembly. "
    "CRITICAL: only NATIVE USD attributes on lights/cameras/xforms are encoded "
    "(e.g. intensity -> xn__inputsintensity_i0a, color -> xn__inputscolor_kya, "
    "exposure -> xn__inputsexposure_vya); resolve those via USD_PARM_ALIASES "
    "(synapse.core.aliases) or inspect the parm first. MaterialX shader inputs, "
    "by contrast, use PLAIN names (base_color, metalness, specular_roughness, ...) "
    "-- never encode mtlx shader parms. "
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
    "houdini_set_usd_primvar",
    "houdini_create_usd_prim",
    "houdini_modify_usd_prim",
    "houdini_reference_usd",
    "houdini_set_payload_loadstate",
    "houdini_create_point_instancer",
    "houdini_shot_render_ready",
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
    "houdini_set_usd_primvar":      ("set_usd_primvar",        "filter_keys:node,prim_path,primvar_name,type,interpolation,value,element_size,indices"),
    "houdini_create_usd_prim":      ("create_usd_prim",        "filter_keys:node,prim_path,prim_type"),
    "houdini_modify_usd_prim":      ("modify_usd_prim",        "filter_keys:node,prim_path,kind,purpose,active,instanceable"),
    "houdini_reference_usd":        ("reference_usd",          "identity"),
    "houdini_set_payload_loadstate": ("set_payload_loadstate",  "identity"),
    "houdini_create_point_instancer": ("create_point_instancer", "identity"),
    "houdini_shot_render_ready":    ("shot_render_ready",      "identity"),
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
