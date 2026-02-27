"""System prompt builder for the SYNAPSE Houdini panel.

Assembles a complete system prompt for the Anthropic API, including
identity, tone guide, tool usage guidance, and live scene context.
"""

import os

# ---------------------------------------------------------------------------
# Tone guide loader (cached)
# ---------------------------------------------------------------------------

_tone_cache: str | None = None
_tone_loaded: bool = False


def _load_tone() -> str | None:
    """Load TONE.md content. Searches multiple paths, caches after first load."""
    global _tone_cache, _tone_loaded
    if _tone_loaded:
        return _tone_cache

    # Derive repo root from this file's location:
    # python/synapse/panel/system_prompt.py -> 4 levels up
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.normpath(os.path.join(_this_dir, "..", "..", "..", ".."))

    search_paths = [
        os.path.join(repo_root, "TONE.md"),
        "C:/Users/User/SYNAPSE/TONE.md",
        os.path.expanduser("~/.synapse/TONE.md"),
    ]

    for path in search_paths:
        try:
            with open(path, encoding="utf-8") as f:
                _tone_cache = f.read().strip()
                break
        except (OSError, IOError):
            continue

    _tone_loaded = True
    return _tone_cache


# ---------------------------------------------------------------------------
# Prompt sections
# ---------------------------------------------------------------------------

_IDENTITY = """\
You are SYNAPSE, an AI co-pilot embedded directly inside Houdini 21. You have \
FULL access to Houdini through MCP tools -- you can create nodes, set \
parameters, wire networks, build materials, configure renders, and inspect \
the scene.

CRITICAL: When an artist asks you to BUILD, CREATE, or SET UP something, \
USE YOUR TOOLS IMMEDIATELY. Do not describe the steps. Do not list \
instructions. Execute the work directly and confirm what you built. \
Artists expect action, not documentation.

You are a senior VFX artist and technical partner. You know Houdini \
inside-out -- SOPs, LOPs, Solaris, Karma, VEX, APEX, PDG, MaterialX, \
and USD. You work WITH the artist, not above them."""

_TOOL_GUIDANCE = """\
## Tool Usage Rules

- When asked to create, build, set up, or make something: USE TOOLS \
immediately. Act first, explain briefly after.
- When asked to explain, teach, or describe a concept: respond with text.
- After creating nodes: briefly confirm what was built and where.
- If a tool call fails: explain what happened in plain language and \
suggest a fix. Never dump raw errors.
- Chain multiple tool calls for complex requests (e.g., create node, \
set parameters, connect, set display flag).
- Use houdini_inspect_node to discover parameter names before setting \
them -- especially for USD/Solaris nodes with encoded parameter names \
like xn__inputsintensity_i0a.
- Always set the display flag (and render flag where applicable) on \
the last node in a chain.
- For Solaris networks: prefer creating standard LOP nodes over \
execute_python when possible."""


def _format_scene_context(context: dict) -> str:
    """Format the live scene context block."""
    network = context.get("network", "/obj")
    selection = context.get("selection", [])
    frame = context.get("frame", 1)
    hip = context.get("hip", "untitled.hip")

    lines = ["## Current Scene Context", ""]
    lines.append(f"- Network: {network}")

    if selection:
        if len(selection) <= 5:
            lines.append(f"- Selected: {', '.join(selection)}")
        else:
            shown = ", ".join(selection[:5])
            lines.append(f"- Selected: {shown} (+{len(selection) - 5} more)")
    else:
        lines.append("- Selected: (none)")

    lines.append(f"- Frame: {frame}")
    lines.append(f"- File: {hip}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_system_prompt(context: dict) -> str:
    """Build the complete system prompt for the Anthropic API.

    Args:
        context: Dict with keys:
            network  (str)  -- current network path, e.g. "/stage"
            selection (list) -- selected node paths
            frame    (int)  -- current frame number
            hip      (str)  -- hip file path or name

    Returns:
        Complete system prompt string.
    """
    sections = [_IDENTITY]

    tone = _load_tone()
    if tone:
        sections.append(tone)

    sections.append(_TOOL_GUIDANCE)
    sections.append(_format_scene_context(context))

    return "\n\n".join(sections)
