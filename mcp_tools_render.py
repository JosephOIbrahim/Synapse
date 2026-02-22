"""MCP Tool Group: Render / Viewport / Keyframe

Knowledge preamble and tool manifest for rendering tools.
Imported by mcp_server.py for knowledge-enriched tool grouping.
"""

# Domain knowledge for agents consuming these tools
GROUP_KNOWLEDGE = (
    "RENDER TOOLS: Karma XPU/CPU, Mantra, and viewport capture. "
    "LIGHTING LAW: Intensity is ALWAYS 1.0 -- brightness controlled by "
    "exposure (logarithmic, in stops). Key:fill ratio 3:1 = 1.585 stops. "
    "PROGRESSIVE VALIDATION: Start at 256x256 with 4-8 pixel samples. "
    "Confirm output before scaling up. Never use soho_foreground=1 for "
    "heavy scenes -- it blocks the WebSocket server. "
    "Set 'picture' on Karma LOP AND 'outputimage' on the ROP. "
    "Karma camera must use USD prim path (/cameras/render_cam), not node path."
)

# Tools in this group
TOOL_NAMES = [
    "houdini_capture_viewport",
    "houdini_render",
    "synapse_validate_frame",
    "synapse_configure_render_passes",
    "houdini_set_keyframe",
    "houdini_render_settings",
    "synapse_render_sequence",
    "synapse_render_farm_status",
    "synapse_autonomous_render",
    "synapse_validate_ordering",
]

# Dispatch entries for this group
DISPATCH_KEYS = {
    "houdini_capture_viewport": ("capture_viewport", "identity"),
    "houdini_render":           ("render",           "identity"),
    "synapse_validate_frame":   ("validate_frame",   "identity"),
    "synapse_configure_render_passes": ("configure_render_passes", "identity"),
    "houdini_set_keyframe":     ("set_keyframe",     "identity"),
    "houdini_render_settings":  ("render_settings",  "identity"),
    "synapse_render_sequence":    ("render_sequence",      "identity"),
    "synapse_render_farm_status": ("render_farm_status",   "passthrough"),
    "synapse_autonomous_render":  ("autonomous_render",    "identity"),
    "synapse_validate_ordering":  ("solaris_validate_ordering", "identity"),
}
