"""MCP Tool Group: Copernicus (COPs)

Knowledge preamble and tool manifest for Houdini 21 Copernicus image processing tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "COPERNICUS (COPs) TOOLS: GPU-accelerated image processing in Houdini 21. "
    "FOUNDATION: cops_create_network creates a COP2 container, cops_create_node "
    "adds COP nodes, cops_connect wires them, cops_set_opencl sets GPU kernels, "
    "cops_read_layer_info queries resolution/channels. "
    "PIPELINE: cops_to_materialx connects COP output as MaterialX texture via op: path. "
    "cops_composite_aovs builds AOV compositing from Karma EXR renders. "
    "cops_analyze_render checks quality (black pixels, clipping, noise). "
    "cops_slap_comp sets up live viewport overlay. "
    "PROCEDURAL: cops_create_solver creates Block Begin/End feedback loops. "
    "cops_procedural_texture generates noise textures. "
    "cops_growth_propagation and cops_reaction_diffusion run iterative simulations. "
    "cops_pixel_sort and cops_stylize apply motion design effects. "
    "ADVANCED: cops_wetmap creates temporal decay maps. cops_bake_textures sets up "
    "UV baking. cops_temporal_analysis checks frame coherence. "
    "cops_stamp_scatter distributes stamp images. cops_batch_cook batch-processes COP nodes. "
    "ALL mutations wrap in hou.undos.group for safe rollback."
)

# Tools in this group
TOOL_NAMES = [
    # Foundation
    "cops_create_network",
    "cops_create_node",
    "cops_connect",
    "cops_set_opencl",
    "cops_read_layer_info",
    # Pipeline
    "cops_to_materialx",
    "cops_composite_aovs",
    "cops_analyze_render",
    "cops_slap_comp",
    # Procedural
    "cops_create_solver",
    "cops_procedural_texture",
    "cops_growth_propagation",
    "cops_reaction_diffusion",
    "cops_pixel_sort",
    "cops_stylize",
    # Advanced
    "cops_wetmap",
    "cops_bake_textures",
    "cops_temporal_analysis",
    "cops_stamp_scatter",
    "cops_batch_cook",
]

# Dispatch entries for this group
DISPATCH_KEYS = {
    "cops_create_network":      ("cops_create_network",      "identity"),
    "cops_create_node":         ("cops_create_node",         "identity"),
    "cops_connect":             ("cops_connect",             "identity"),
    "cops_set_opencl":          ("cops_set_opencl",          "identity"),
    "cops_read_layer_info":     ("cops_read_layer_info",     "identity"),
    "cops_to_materialx":        ("cops_to_materialx",        "identity"),
    "cops_composite_aovs":      ("cops_composite_aovs",      "identity"),
    "cops_analyze_render":      ("cops_analyze_render",       "identity"),
    "cops_slap_comp":           ("cops_slap_comp",           "identity"),
    "cops_create_solver":       ("cops_create_solver",       "identity"),
    "cops_procedural_texture":  ("cops_procedural_texture",  "identity"),
    "cops_growth_propagation":  ("cops_growth_propagation",  "identity"),
    "cops_reaction_diffusion":  ("cops_reaction_diffusion",  "identity"),
    "cops_pixel_sort":          ("cops_pixel_sort",          "identity"),
    "cops_stylize":             ("cops_stylize",             "identity"),
    "cops_wetmap":              ("cops_wetmap",              "identity"),
    "cops_bake_textures":       ("cops_bake_textures",       "identity"),
    "cops_temporal_analysis":   ("cops_temporal_analysis",   "identity"),
    "cops_stamp_scatter":       ("cops_stamp_scatter",       "identity"),
    "cops_batch_cook":          ("cops_batch_cook",          "identity"),
}
