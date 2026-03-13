"""
Bridge Adapter -- Wrap handler.handle() in LosslessExecutionBridge.

Provides undo groups, thread safety, consent gates, and integrity
verification around existing tool dispatch without modifying handlers.py.

Phase 3 of the MOE wiring plan.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ── Import bridge (graceful fallback) ────────────────────────────
_BRIDGE_AVAILABLE = False
try:
    from shared.bridge import (
        LosslessExecutionBridge,
        Operation,
        IntegrityBlock,
        GateLevel,
        OPERATION_GATES,
    )
    from shared.types import AgentID
    _BRIDGE_AVAILABLE = True
except ImportError:
    LosslessExecutionBridge = None  # type: ignore[assignment,misc]
    Operation = None  # type: ignore[assignment,misc]
    IntegrityBlock = None  # type: ignore[assignment,misc]
    GateLevel = None  # type: ignore[assignment,misc]
    OPERATION_GATES = {}  # type: ignore[assignment]
    AgentID = None  # type: ignore[assignment,misc]


# ── Read-only tools (skip bridge entirely for speed) ─────────────
_READ_ONLY_TOOLS = frozenset({
    "synapse_ping", "synapse_health", "synapse_context",
    "houdini_scene_info", "houdini_get_selection", "houdini_get_parm",
    "houdini_stage_info", "houdini_get_usd_attribute",
    "houdini_capture_viewport", "houdini_network_explain",
    "houdini_query_prims", "houdini_read_material",
    "houdini_hda_list",
    "synapse_inspect_node", "synapse_inspect_selection",
    "synapse_inspect_scene", "synapse_knowledge_lookup",
    "synapse_search", "synapse_recall", "synapse_memory_query",
    "synapse_memory_status", "synapse_metrics", "synapse_router_stats",
    "synapse_list_recipes", "synapse_render_farm_status",
    "synapse_validate_ordering", "synapse_live_metrics",
    "cops_read_layer_info", "cops_analyze_render",
    "tops_get_work_items", "tops_get_dependency_graph",
    "tops_get_cook_stats", "tops_pipeline_status",
    "tops_query_items", "tops_diagnose",
})

# ── MCP tool name → bridge operation type mapping ────────────────
_TOOL_TO_OPERATION: dict[str, str] = {
    # Node operations
    "houdini_create_node": "create_node",
    "houdini_delete_node": "delete_node",
    "houdini_connect_nodes": "connect_nodes",
    "houdini_set_parm": "set_parameter",
    "houdini_set_keyframe": "set_parameter",
    # Execution
    "houdini_execute_python": "execute_python",
    "houdini_execute_vex": "execute_vex",
    # USD
    "houdini_set_usd_attribute": "set_parameter",
    "houdini_create_usd_prim": "create_node",
    "houdini_modify_usd_prim": "set_parameter",
    "houdini_reference_usd": "set_parameter",
    "houdini_manage_variant_set": "set_parameter",
    "houdini_manage_collection": "set_parameter",
    "houdini_configure_light_linking": "set_parameter",
    # Materials
    "houdini_create_textured_material": "create_material",
    "houdini_create_material": "create_material",
    "houdini_assign_material": "set_parameter",
    # Render
    "houdini_render": "submit_render",
    "houdini_render_settings": "set_parameter",
    "houdini_wedge": "set_parameter",
    "synapse_render_sequence": "submit_render",
    "synapse_autonomous_render": "submit_render",
    "synapse_safe_render": "submit_render",
    "synapse_render_progressively": "submit_render",
    "synapse_configure_render_passes": "set_parameter",
    "synapse_validate_frame": "set_parameter",
    # PDG
    "tops_cook_node": "set_parameter",
    "tops_generate_items": "set_parameter",
    "tops_configure_scheduler": "set_parameter",
    "tops_cancel_cook": "set_parameter",
    "tops_dirty_node": "set_parameter",
    "tops_setup_wedge": "set_parameter",
    "tops_batch_cook": "cook_pdg_chain",
    "tops_cook_and_validate": "cook_pdg_chain",
    "tops_render_sequence": "submit_render",
    "tops_multi_shot": "cook_pdg_chain",
    # COPs
    "cops_create_network": "create_node",
    "cops_create_node": "create_node",
    "cops_connect": "connect_nodes",
    "cops_set_opencl": "set_parameter",
    "cops_to_materialx": "set_parameter",
    "cops_composite_aovs": "set_parameter",
    "cops_slap_comp": "set_parameter",
    "cops_create_solver": "create_node",
    "cops_procedural_texture": "create_node",
    "cops_growth_propagation": "create_node",
    "cops_reaction_diffusion": "create_node",
    "cops_pixel_sort": "create_node",
    "cops_stylize": "set_parameter",
    "cops_wetmap": "create_node",
    "cops_bake_textures": "export_file",
    "cops_temporal_analysis": "set_parameter",
    "cops_stamp_scatter": "create_node",
    "cops_batch_cook": "cook_pdg_chain",
    # HDA
    "houdini_hda_create": "create_node",
    "houdini_hda_promote_parm": "set_parameter",
    "houdini_hda_set_help": "set_parameter",
    "houdini_hda_package": "export_file",
    # Memory
    "synapse_decide": "set_parameter",
    "synapse_add_memory": "set_parameter",
    "synapse_memory_write": "set_parameter",
    "synapse_evolve_memory": "evolve_memory",
    "synapse_project_setup": "set_parameter",
    # Undo/redo
    "houdini_undo": "set_parameter",
    "houdini_redo": "set_parameter",
    # Batch
    "synapse_batch": "build_from_manifest",
    "synapse_solaris_assemble_chain": "build_from_manifest",
    "synapse_solaris_build_graph": "build_from_manifest",
}

# ── Tool name → inferred AgentID ─────────────────────────────────
_TOOL_AGENT_MAP: dict[str, str] = {
    "houdini_execute_python": "BRAINSTEM",
    "houdini_execute_vex": "BRAINSTEM",
    "houdini_undo": "BRAINSTEM",
    "houdini_redo": "BRAINSTEM",
}


# ── Singleton bridge ─────────────────────────────────────────────
_bridge: Any = None


def get_bridge():
    """Get or create the singleton LosslessExecutionBridge."""
    global _bridge
    if not _BRIDGE_AVAILABLE:
        return None
    if _bridge is None:
        _bridge = LosslessExecutionBridge()
    return _bridge


def is_read_only(tool_name: str) -> bool:
    """Check if a tool is read-only (should skip bridge)."""
    return tool_name in _READ_ONLY_TOOLS


def execute_through_bridge(
    tool_name: str,
    handler,
    command,
    routing_agent: str | None = None,
) -> Any:
    """Execute a tool call through the LosslessExecutionBridge.

    Args:
        tool_name: MCP tool name.
        handler: SynapseHandler instance.
        command: SynapseCommand to dispatch.
        routing_agent: Optional agent ID from MOE routing.

    Returns:
        SynapseResponse from handler.handle(), with IntegrityBlock
        attached to the response data if bridge is available.

    Raises:
        Same exceptions as handler.handle().
    """
    bridge = get_bridge()
    if bridge is None:
        # Bridge unavailable -- direct dispatch
        return handler.handle(command)

    # Determine operation type and agent
    op_type = _TOOL_TO_OPERATION.get(tool_name, "set_parameter")
    agent_str = routing_agent or _TOOL_AGENT_MAP.get(tool_name, "HANDS")

    try:
        agent_id = AgentID(agent_str)
    except (ValueError, KeyError):
        agent_id = AgentID.HANDS

    # Extract node_path from command payload for blast radius inference
    payload = command.payload if hasattr(command, "payload") else {}
    node_path = ""
    if isinstance(payload, dict):
        node_path = (
            payload.get("node", "")
            or payload.get("parent", "")
            or payload.get("path", "")
            or payload.get("source", "")
        )

    # Wrap handler.handle so the bridge can pass kwargs without
    # breaking the handler signature. kwargs carry bridge metadata
    # (node_path for blast radius inference), not handler params.
    def _dispatch(*_args, **_kwargs):
        return handler.handle(command)

    op = Operation(
        agent_id=agent_id,
        operation_type=op_type,
        summary="{}: {}".format(tool_name, str(payload)[:80]),
        fn=_dispatch,
        args=(),
        kwargs={"node_path": node_path} if node_path else {},
    )

    result = bridge.execute(op)

    # The bridge wraps the handler response in ExecutionResult.
    # Extract the original SynapseResponse if it succeeded.
    if result.success and result.result is not None:
        response = result.result
        # Attach integrity info to the response data
        if hasattr(response, "data") and result.integrity is not None:
            if isinstance(response.data, dict):
                response.data["_integrity"] = result.integrity.to_dict()
            elif response.data is None:
                response.data = {"_integrity": result.integrity.to_dict()}
        return response

    # Bridge execution failed -- construct a failure response
    # Import SynapseResponse lazily to avoid circular imports
    try:
        from synapse.core.protocol import SynapseResponse
        integrity_dict = result.integrity.to_dict() if result.integrity else {}
        return SynapseResponse(
            success=False,
            error="Bridge: {}".format(result.error or "Unknown error"),
            data={"_integrity": integrity_dict},
        )
    except ImportError:
        # Can't construct SynapseResponse -- re-raise as RuntimeError
        raise RuntimeError(
            "Bridge execution failed: {}".format(result.error)
        )


def get_session_report() -> dict | None:
    """Get the bridge session report, or None if bridge unavailable."""
    bridge = get_bridge()
    if bridge is None:
        return None
    return bridge.session_report()
