"""Transport classification for detached render jobs; no Houdini imports."""

FARM_READ_COMMANDS = frozenset({
    "farm_inspect", "farm_capabilities", "farm_jobs", "farm_job",
})
FARM_CONTROL_COMMANDS = frozenset({"farm_prepare", "farm_submit", "farm_cancel"})
FARM_CONTROL_TOOLS = frozenset("synapse_" + name for name in FARM_CONTROL_COMMANDS)
FARM_READ_TOOLS = frozenset("synapse_" + name for name in FARM_READ_COMMANDS)


def is_farm_control(tool_name):
    return tool_name in FARM_CONTROL_TOOLS
