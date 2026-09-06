"""Readable labels for observed worker/tool events, never inferred reasoning."""
_TOOLS = {
    "synapse_ping": "Check the Houdini connection",
    "houdini_get_scene_info": "Read scene context",
    "houdini_create_node": "Create a node",
    "houdini_set_parameter": "Set a parameter",
    "network_explain": "Read the network",
    "houdini_undo": "Undo the last change",
    "capture_viewport": "Capture the viewport",
    "synapse_recall": "Recall saved context",
}


def tool_label(name):
    text = str(name or "tool")
    return _TOOLS.get(text, text.removeprefix("houdini_").replace("_", " ").capitalize())


def tool_status(name, phase):
    prefix = {"running": "Running", "done": "Finished", "ok": "Finished",
              "error": "Failed", "failed": "Failed"}.get(phase, "Status")
    return "%s: %s" % (prefix, tool_label(name))
