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

_SOLARIS_CONTEXT_GUIDANCE = """\
## Solaris / LOP Context

You are currently inside a Solaris (LOP) network. Key rules:

- **Use sublayer** LOP nodes to bring geometry into the stage (not \
assetreference -- assetreference is invisible to Karma).
- Use **Asset Reference** nodes only for viewport-only work or production geo.
- Wire order in merge: geometry first, then lights, then referenced assets.
- **Material library** with multiple subnets is preferred over separate \
matlib + assign nodes. Assign geo paths directly in matlib (geopath1, \
geopath2) -- no separate assign nodes needed.
- Material prim patterns must match exact USD prim paths \
(e.g. /rubbertoy/geo/shape, NOT /rubbertoy/*).
- Always use **HDRI on dome light** for lighting. Dome light exposure \
~0.25 for studio HDRI.
- Key light: enable color temperature for natural warmth, exposure ~1.0.
- **Intensity is always 1.0** -- control brightness via exposure only \
(Lighting Law).
- Clean chain: merge -> matlib -> camera -> render_settings -> karma.
- Karma LOP feeds usdrender ROP in /out. Set picture on Karma LOP AND \
outputimage on ROP.
- Set soho_foreground=1 on usdrender ROP for synchronous file write.
- Use houdini_inspect_node to discover encoded parameter names \
(e.g. xn__inputsintensity_i0a, xn__inputsexposure_vya).
- Houdini ships test assets at $HFS/houdini/usd/assets/ (rubbertoy, pig, etc.)."""

_OBJ_CONTEXT_GUIDANCE = """\
## OBJ / SOP Context

You are currently at the OBJ or SOP level. Key rules:

- Prefer creating standard SOP nodes and wiring networks over \
execute_python when possible.
- Set the display flag (blue) on the last node the artist should see.
- Set the render flag (purple) on the node that should be rendered.
- Use Merge SOPs to combine geometry streams.
- For procedural setups: use Attribute Wrangle for VEX, not \
Point/Primitive SOPs (deprecated workflow).
- When modifying geometry attributes, inspect the node first to \
discover available attributes and their types."""


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


def _solaris_context_block(context: dict) -> str | None:
    """Return context-aware guidance based on the current network type.

    Returns Solaris guidance when inside a LOP network, OBJ/SOP guidance
    when at the object or geometry level, or None for other contexts.
    """
    network = context.get("network", "/obj")
    network_lower = network.lower()

    if "/stage" in network_lower or "/lop" in network_lower:
        return _SOLARIS_CONTEXT_GUIDANCE
    if network_lower in ("/", "/obj") or "/obj/" in network_lower:
        return _OBJ_CONTEXT_GUIDANCE
    return None


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

    ctx_guidance = _solaris_context_block(context)
    if ctx_guidance:
        sections.append(ctx_guidance)

    return "\n\n".join(sections)
