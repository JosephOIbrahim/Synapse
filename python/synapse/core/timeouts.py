"""
Synapse per-command timeout budgets — the ONE canonical table (C7).

Before C7 this table lived only in the external stdio client (mcp_server.py),
while the panel hardcoded 30/35 s for every tool — so any panel-initiated tool
slower than ~35 s (render 120 s, sequences 600 s) timed out client-side, was
reported failed, and the fall-through RE-DISPATCHED the same mutation while the
first was still executing inside Houdini. Every client must budget from here.

Zero-`hou`, zero-Qt — importable by the stdio client, the panel, and tests.
"""

from __future__ import annotations

# Default for anything not listed below (fast reads, parm sets, pings).
COMMAND_TIMEOUT = 10.0

SLOW_COMMANDS = {
    "execute_python": 30.0, "execute_vex": 30.0, "capture_viewport": 30.0,
    "render": 120.0, "wedge": 120.0, "validate_frame": 30.0,
    "render_sequence": 600.0,
    "inspect_selection": 30.0, "inspect_scene": 30.0, "inspect_node": 30.0,
    "network_explain": 30.0,
    "batch_commands": 60.0,
    # TOPS/PDG commands -- PDG graph context initialization (getPDGGraphContext,
    # getPDGNode) can block Houdini's main thread for 5-15s on first access.
    # All tops_ commands need at least 60s to survive this cold-start stall.
    "tops_get_work_items": 60.0,
    "tops_get_dependency_graph": 60.0,
    "tops_get_cook_stats": 60.0,
    "tops_cook_node": 120.0,
    "tops_generate_items": 60.0,
    "tops_configure_scheduler": 30.0,
    "tops_cancel_cook": 30.0,
    "tops_dirty_node": 60.0,
    "tops_batch_cook": 300.0,
    "tops_setup_wedge": 30.0,
    "tops_query_items": 60.0,
    "tops_cook_and_validate": 600.0,
    "tops_diagnose": 60.0,
    "tops_pipeline_status": 60.0,
    "tops_monitor_stream": 30.0,
    "tops_render_sequence": 600.0,
    "tops_multi_shot": 600.0,
    "autonomous_render": 600.0,
    "safe_render": 120.0,
    "render_progressively": 120.0,
    "hda_package": 120.0,
    # Solaris graph builds -- a Karma render-ready build_graph/assemble_chain
    # routinely exceeds the 10s default (the handlers themselves marshal at 30s);
    # the client must match or it false-fails a SUCCESSFUL one-shot build and the
    # model reverts to the slow 25-turn imperative path (the convergence lever).
    "solaris_build_graph": 30.0,
    "solaris_assemble_chain": 30.0,
    # Copernicus (COPs) -- solvers and batch need longer timeouts
    "cops_reaction_diffusion": 60.0,
    "cops_growth_propagation": 60.0,
    "cops_temporal_analysis": 60.0,
    "cops_batch_cook": 120.0,
    "cops_composite_aovs": 60.0,
    "cops_bake_textures": 60.0,
    "cops_wetmap": 60.0,
}

# MCP tool names whose command type isn't recoverable by prefix-stripping alone.
_TOOL_ALIASES = {
    "synapse_batch": "batch_commands",
    "houdini_capture_viewport": "capture_viewport",  # covered by stripping; kept explicit
}

_STRIP_PREFIXES = ("houdini_", "synapse_")


def timeout_for(name: str, default: float = COMMAND_TIMEOUT) -> float:
    """Budget for a command type OR an MCP tool name.

    The table keys on command types ("render"); MCP tool names carry a prefix
    ("houdini_render", "synapse_render_sequence"). Lookup order: exact → alias →
    prefix-stripped. Unknown names get the fast default.
    """
    if name in SLOW_COMMANDS:
        return SLOW_COMMANDS[name]
    alias = _TOOL_ALIASES.get(name)
    if alias is not None and alias in SLOW_COMMANDS:
        return SLOW_COMMANDS[alias]
    for prefix in _STRIP_PREFIXES:
        if name.startswith(prefix):
            stripped = name[len(prefix):]
            if stripped in SLOW_COMMANDS:
                return SLOW_COMMANDS[stripped]
    return default
