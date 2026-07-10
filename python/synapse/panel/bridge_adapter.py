"""
Bridge Adapter -- Wrap handler.handle() in LosslessExecutionBridge.

Provides undo groups, thread safety, consent gates, and integrity
verification around existing tool dispatch without modifying handlers.py.

Phase 3 of the MOE wiring plan.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ── sys.path bridging ────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, "..", "..", ".."))  # panel->synapse->python->repo root (was 4x '..' = one level too high)
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
        get_process_bridge,
    )
    from shared.types import AgentID
    _BRIDGE_AVAILABLE = True
except ImportError:
    LosslessExecutionBridge = None  # type: ignore[assignment,misc]
    Operation = None  # type: ignore[assignment,misc]
    IntegrityBlock = None  # type: ignore[assignment,misc]
    GateLevel = None  # type: ignore[assignment,misc]
    OPERATION_GATES = {}  # type: ignore[assignment]
    get_process_bridge = None  # type: ignore[assignment]
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
    "synapse_sleep_pass": "sleep_pass",
    "synapse_project_setup": "set_parameter",
    # Undo/redo
    "houdini_undo": "set_parameter",
    "houdini_redo": "set_parameter",
    # Batch
    "synapse_batch": "build_from_manifest",
    "synapse_solaris_assemble_chain": "build_from_manifest",
    "synapse_solaris_build_graph": "build_from_manifest",
    "synapse_solaris_shotsetup_karma_xpu": "build_from_manifest",
    "synapse_matlib_bind": "build_from_manifest",
    "synapse_assess_render_ready": "inspect_geometry",
}

# ── Tools that write files to disk ───────────────────────────────
# R4 (shared/bridge.py Operation.gate_level): touches_disk elevates the
# gate to APPROVE. These writes happen outside the undo system.
_DISK_WRITING_TOOLS = frozenset({
    "synapse_solaris_shotsetup_karma_xpu",  # department .usd layer files
})

# ── Tool name → inferred AgentID ─────────────────────────────────
_TOOL_AGENT_MAP: dict[str, str] = {
    "houdini_execute_python": "BRAINSTEM",
    "houdini_execute_vex": "BRAINSTEM",
    "houdini_undo": "BRAINSTEM",
    "houdini_redo": "BRAINSTEM",
}


# ── Singleton bridge ─────────────────────────────────────────────
_bridge: Any = None


def _panel_consent(operation) -> bool:
    """Consent for ARTIST-INITIATED panel operations — allow, non-blocking.

    The artist typed the request into the panel and is watching it run, so their
    request IS the consent. Critically, this must NOT route through HumanGate's
    blocking poll (``_wait_for_decision``): that poll ``time.sleep``s on whatever
    thread calls it, which in the panel is the GUI/main thread — and the approval
    card it waits for can only be drawn BY that same thread. Result: deadlock,
    Houdini "(Not Responding)". Confirmed live: "make a box" -> execute_python
    (CRITICAL) froze the GUI exactly here.

    Every op is still undo-wrapped + integrity-verified by the bridge (fully
    reversible), and HumanGate still governs AUTONOMOUS / MCP operations, which
    use their own bridge instances — not this panel singleton.
    """
    return True


def get_bridge():
    """Get or create the panel's singleton LosslessExecutionBridge.

    Sourced from the PROCESS-WIDE accessor (shared.bridge.get_process_bridge)
    so the panel, the in-process /mcp adapter, and the live /synapse envelope
    all write ONE operation trail — a second in-process instance would make
    the §16 gc-scan read (agent_health._find_bridge_instance) nondeterministic.
    Order-independent: get_process_bridge() always constructs gate-less with
    an auto-approve callback, so whichever caller creates it first, panel ops
    never reach the GUI-freezing HumanGate poll.

    Consent is resolved by the non-blocking ``_panel_consent`` (artist-initiated
    = pre-consented), never the GUI-freezing HumanGate poll.
    """
    global _bridge
    if not _BRIDGE_AVAILABLE:
        return None
    if _bridge is None:
        _bridge = get_process_bridge()
        # Panel posture on the shared instance: non-blocking artist consent +
        # HumanGate off (the bridge otherwise prefers _gate over the callback).
        _bridge._consent_callback = _panel_consent
        _bridge._gate = None
    return _bridge


def is_read_only(tool_name: str) -> bool:
    """Check if a tool is read-only (should skip bridge)."""
    return tool_name in _READ_ONLY_TOOLS


# ── Inline-cost pre-flight (panel main-thread heads-up) ──────────
# A tool dispatched inline by the panel runs on Houdini's MAIN thread — the same
# thread that pumps the Qt event loop. We cannot move hou.* off it, so a heavy op
# (a big execute_python, a render/cook) freezes the GUI for its whole duration.
# Confirmed live (2026-06-27): a 127KB-dump execute_python ran inline >5000ms →
# heartbeat 10.19s, freeze_count=1, with no warning because hou NEEDS the main
# thread. Runtime is not cheaply predictable, but the *shapes* that froze us are:
# a long inline-code field, an oversized payload, or a known-slow cook/render
# tool. Flagging those up front makes the freeze attributable, not silent.
#
# This is a heads-up ONLY. estimate_inline_cost never blocks, never mutates the
# tool input, and callers must NOT alter the result on its strength.

# Inherently long main-thread tools (cook/render/batch) — flagged regardless of
# payload size.
_KNOWN_SLOW_TOOLS = frozenset({
    "houdini_render",
    "synapse_render_sequence", "synapse_autonomous_render",
    "synapse_safe_render", "synapse_render_progressively",
    "tops_batch_cook", "tops_cook_and_validate", "tops_multi_shot",
    "tops_render_sequence", "cops_batch_cook",
    "synapse_batch", "synapse_evolve_memory", "synapse_sleep_pass",
})

# Payload fields that carry inline source / arbitrary code (execute_python builds
# {"content": code}; execute_vex carries "vex"). Their length is the cheapest
# proxy for "this might run long on the main thread".
_CODE_FIELDS = ("code", "content", "vex", "snippet", "script")

# Length thresholds (chars). Tuned above a trivial "make a box" script (~100
# chars → no advisory) and well below the 127KB dump that stalled the loop.
PREFLIGHT_HEAVY_CODE_CHARS = 2000
PREFLIGHT_HEAVY_PAYLOAD_CHARS = 10000


def estimate_inline_cost(tool_name: str, tool_input: Any) -> tuple[bool, str]:
    """Cheap pre-flight estimate of whether an inline (main-thread) tool call is
    heavy enough to briefly freeze the Qt GUI.

    Pure string arithmetic — no I/O, no extra round-trip. Returns
    ``(is_heavy, advisory_message)``; ``is_heavy`` False ⇒ empty message.

    Advisory ONLY: hou.* has to run on the main thread regardless, so callers
    must not block or change the result based on this verdict.
    """
    payload = tool_input if isinstance(tool_input, dict) else {}

    # 1. Longest inline-code field (the execute_python/vex freeze contributor).
    code_len = 0
    for field_name in _CODE_FIELDS:
        val = payload.get(field_name)
        if isinstance(val, str) and len(val) > code_len:
            code_len = len(val)
    if code_len >= PREFLIGHT_HEAVY_CODE_CHARS:
        return True, (
            "{}: ~{} chars of inline code will run on Houdini's main thread and "
            "may briefly freeze the UI while it executes.".format(tool_name, code_len)
        )

    # 2. Oversized overall payload (large data blobs marshalled inline).
    try:
        payload_len = len(json.dumps(payload, default=str)) if payload else 0
    except Exception:
        payload_len = 0
    if payload_len >= PREFLIGHT_HEAVY_PAYLOAD_CHARS:
        return True, (
            "{}: large payload (~{} chars) runs inline on the main thread and "
            "may briefly freeze the UI.".format(tool_name, payload_len)
        )

    # 3. Known inherently-slow cook/render tools.
    if tool_name in _KNOWN_SLOW_TOOLS:
        return True, (
            "{} runs on the main thread and may briefly freeze the UI while it "
            "cooks/renders.".format(tool_name)
        )

    return False, ""


def _bridge_routed_cm():
    """Context manager marking the nested handler.handle() as bridge-routed
    (live-envelope suppression). nullcontext when the envelope module is
    unavailable — dispatch behavior is then exactly as before."""
    try:
        from synapse.server.integrity_envelope import bridge_routed
        return bridge_routed()
    except ImportError:
        return contextlib.nullcontext()


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
        # Suppress the live-path envelope for this NESTED handle() call: the
        # bridge's _finalize records this op, so a live block on top would
        # double-count in the shared process trail.
        with _bridge_routed_cm():
            return handler.handle(command)

    op_kwargs = {"node_path": node_path} if node_path else {}
    # R4: disk-writing tools carry touches_disk so the gate elevates to APPROVE.
    if tool_name in _DISK_WRITING_TOOLS:
        op_kwargs["touches_disk"] = True

    op = Operation(
        agent_id=agent_id,
        operation_type=op_type,
        summary="{}: {}".format(tool_name, str(payload)[:80]),
        fn=_dispatch,
        args=(),
        kwargs=op_kwargs,
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
            id=command.id,
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
