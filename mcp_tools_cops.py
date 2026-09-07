"""MCP Tool Group: Copernicus (COPs)

Knowledge preamble and tool manifest for modern Copernicus and legacy COP2 tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "COP TOOLS: This group contains modern Copernicus and legacy COP2 helpers. "
    "Confirm the running build, parent category, node types and ports before use. "
    "MODERN PROCEDURAL TEXTURES: cops_create_copnet creates a modern CopNet. "
    "cops_procedural_texture requires an editable modern Cop parent and configures "
    "a scalar noise output with a private resolution layer. Its checked parameters "
    "and wiring return configured=True, cooked=False; image evaluation is separate. "
    "LEGACY: cops_create_network creates a legacy COP2 container, which cannot be "
    "used as the modern procedural texture parent. Not all helpers in this group "
    "have migrated to Copernicus; verify each helper's supported context. "
    "cops_create_node and cops_connect use the supplied parent/nodes; discover "
    "the exact parameters and source/destination ports rather than guessing a chain. "
    "OBSERVATION: cops_read_layer_info reports available image metadata and cook "
    "issues; reading an image may evaluate it. cops_analyze_render requests a cook "
    "and reports metadata/issues, but does not measure pixel statistics such as "
    "black-pixel fraction, clipping or noise. Missing metadata or no cook errors "
    "does not prove valid pixels. Graph, image and rendered output need separate verification. "
    "PIPELINE: cops_to_materialx configures an op: texture reference on a supplied "
    "shader; this does not verify a Solaris material binding or a rendered result. "
    "cops_composite_aovs builds a compositing network from supplied EXR paths. "
    "cops_create_solver creates paired feedback nodes; cops_reaction_diffusion "
    "and cops_pixel_sort scaffold placeholder kernels, not verified simulations. "
    "cops_bake_textures scaffolds a bake setup without executing a bake. "
    "Cooks, renders and exports retain their own permission requirements. "
    "Undo grouping does not guarantee rollback. Check each operation's returned "
    "results and cleanup report; report partial state instead of assuming every "
    "helper removed its changes after failure."
)

# Tools in this group
TOOL_NAMES = [
    # Foundation
    "cops_create_network",
    "cops_create_copnet",
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
    "cops_create_copnet":       ("cops_create_copnet",       "identity"),
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
