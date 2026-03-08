"""
MOE Tool Filter -- Classify artist messages and filter tools by domain.

Uses shared/router.py (extract_features, MOERouter) to classify artist
messages into agent domains, then filters the 108-tool list down to
domain-relevant subsets. Falls back to full tool list on any error.

Phase 1 of the MOE wiring plan.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
# shared/ lives at repo root, production code at python/synapse/.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Import MOE router (graceful fallback) ────────────────────────
_ROUTER_AVAILABLE = False
try:
    from shared.router import extract_features, MOERouter, RoutingDecision
    from shared.types import AgentID, DomainSignal
    _ROUTER_AVAILABLE = True
except ImportError:
    extract_features = None  # type: ignore[assignment]
    MOERouter = None  # type: ignore[assignment]
    RoutingDecision = None  # type: ignore[assignment]
    AgentID = None  # type: ignore[assignment]
    DomainSignal = None  # type: ignore[assignment]


# ── Singleton router instance ────────────────────────────────────
_router: Any = None


def _get_router():
    global _router
    if _router is None and _ROUTER_AVAILABLE:
        _router = MOERouter()
    return _router


# ── Base tools (always included regardless of routing) ───────────
_BASE_TOOLS = frozenset({
    "synapse_ping",
    "synapse_health",
    "synapse_context",
    "houdini_scene_info",
    "houdini_get_selection",
    "houdini_get_parm",
    "houdini_undo",
    "houdini_redo",
    "synapse_inspect_node",
    "synapse_inspect_selection",
    "synapse_inspect_scene",
    "synapse_knowledge_lookup",
    "synapse_search",
    "synapse_recall",
    "synapse_decide",
    "synapse_add_memory",
    "synapse_memory_query",
    "synapse_memory_status",
    "synapse_metrics",
    "synapse_list_recipes",
})


# ── Agent → Tool Domain Mapping ─────────────────────────────────
# Maps each AgentID to a set of tool name prefixes and exact names.
# INTEGRATOR gets all tools (fallback for complex/research queries).

_AGENT_TOOL_MAP: dict[str, frozenset[str]] = {
    "OBSERVER": frozenset({
        # Read/inspect tools
        "houdini_scene_info", "houdini_get_selection", "houdini_get_parm",
        "houdini_capture_viewport", "houdini_stage_info",
        "houdini_get_usd_attribute", "houdini_network_explain",
        "houdini_query_prims", "houdini_read_material",
        "synapse_inspect_node", "synapse_inspect_selection",
        "synapse_inspect_scene", "synapse_validate_ordering",
        "cops_read_layer_info", "cops_analyze_render",
        "tops_get_work_items", "tops_get_dependency_graph",
        "tops_get_cook_stats", "tops_pipeline_status",
        "tops_query_items", "tops_diagnose",
    }),
    "HANDS": frozenset({
        # USD/Solaris/material/APEX/COPs tools
        "houdini_create_node", "houdini_delete_node", "houdini_connect_nodes",
        "houdini_set_parm", "houdini_set_keyframe",
        "houdini_stage_info", "houdini_get_usd_attribute",
        "houdini_set_usd_attribute", "houdini_create_usd_prim",
        "houdini_modify_usd_prim", "houdini_reference_usd",
        "houdini_query_prims", "houdini_manage_variant_set",
        "houdini_manage_collection", "houdini_configure_light_linking",
        "houdini_create_textured_material", "houdini_create_material",
        "houdini_assign_material", "houdini_read_material",
        "synapse_validate_ordering", "synapse_solaris_assemble_chain",
        "houdini_render_settings", "houdini_render",
        "houdini_capture_viewport",
        "houdini_hda_create", "houdini_hda_promote_parm",
        "houdini_hda_set_help", "houdini_hda_package", "houdini_hda_list",
        # COPs tools
        "cops_create_network", "cops_create_node", "cops_connect",
        "cops_set_opencl", "cops_read_layer_info", "cops_to_materialx",
        "cops_composite_aovs", "cops_analyze_render", "cops_slap_comp",
        "cops_create_solver", "cops_procedural_texture",
        "cops_growth_propagation", "cops_reaction_diffusion",
        "cops_pixel_sort", "cops_stylize", "cops_wetmap",
        "cops_bake_textures", "cops_temporal_analysis",
        "cops_stamp_scatter", "cops_batch_cook",
    }),
    "CONDUCTOR": frozenset({
        # PDG/render/batch tools
        "tops_get_work_items", "tops_get_dependency_graph",
        "tops_get_cook_stats", "tops_cook_node", "tops_generate_items",
        "tops_configure_scheduler", "tops_cancel_cook", "tops_dirty_node",
        "tops_setup_wedge", "tops_batch_cook", "tops_query_items",
        "tops_cook_and_validate", "tops_diagnose", "tops_pipeline_status",
        "tops_monitor_stream", "tops_render_sequence", "tops_multi_shot",
        "houdini_render", "houdini_render_settings", "houdini_wedge",
        "synapse_render_sequence", "synapse_render_farm_status",
        "synapse_autonomous_render", "synapse_safe_render",
        "synapse_render_progressively", "synapse_live_metrics",
        "synapse_validate_frame", "synapse_configure_render_passes",
        "synapse_batch",
    }),
    "BRAINSTEM": frozenset({
        # Execution/recovery tools
        "houdini_execute_python", "houdini_execute_vex",
        "houdini_create_node", "houdini_delete_node",
        "houdini_connect_nodes", "houdini_set_parm",
        "houdini_undo", "houdini_redo",
        "synapse_batch",
    }),
    "SUBSTRATE": frozenset({
        # Core node/network manipulation tools
        "houdini_create_node", "houdini_delete_node",
        "houdini_connect_nodes", "houdini_set_parm",
        "houdini_get_parm", "houdini_set_keyframe",
        "houdini_network_explain",
        "synapse_project_setup", "synapse_memory_write",
        "synapse_evolve_memory", "synapse_router_stats",
    }),
}


def filter_tools(
    user_text: str,
    all_tools: list[dict],
) -> tuple[list[dict], Any]:
    """Classify artist message and filter tools to domain-relevant subset.

    Args:
        user_text: The artist's message text.
        all_tools: Full list of Anthropic-format tool dicts.

    Returns:
        (filtered_tools, routing_decision) -- routing_decision is None
        if routing is unavailable or fails.
    """
    if not _ROUTER_AVAILABLE or not user_text:
        return all_tools, None

    try:
        router = _get_router()
        if router is None:
            return all_tools, None

        features = extract_features(user_text)
        decision = router.route(features)

        # INTEGRATOR or research-grade → all tools
        if (decision.primary == AgentID.INTEGRATOR
                or features.complexity.value == "research_grade"):
            return all_tools, decision

        # Build allowed tool names from primary + advisory agents
        allowed = set(_BASE_TOOLS)
        primary_tools = _AGENT_TOOL_MAP.get(decision.primary.value, frozenset())
        allowed.update(primary_tools)

        if decision.advisory:
            advisory_tools = _AGENT_TOOL_MAP.get(decision.advisory.value, frozenset())
            allowed.update(advisory_tools)

        # Also include group knowledge tools (synapse_group_*)
        allowed.update(
            t["name"] for t in all_tools if t["name"].startswith("synapse_group_")
        )

        # Filter
        filtered = [t for t in all_tools if t["name"] in allowed]

        # Safety: if filtering removed too many tools (< 15), use full list
        if len(filtered) < 15:
            logger.debug(
                "MOE filter too aggressive (%d tools), using full list",
                len(filtered),
            )
            return all_tools, decision

        logger.debug(
            "MOE routed to %s (+%s): %d/%d tools",
            decision.primary.value,
            decision.advisory.value if decision.advisory else "none",
            len(filtered),
            len(all_tools),
        )
        return filtered, decision

    except Exception:
        logger.debug("MOE routing failed, using full tool list", exc_info=True)
        return all_tools, None
