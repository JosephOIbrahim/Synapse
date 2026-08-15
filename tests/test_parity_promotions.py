"""Parity-audit promotions (F1 + F2, 2026-08-14): the Solaris compose trio
and the TOPS pause/resume pair moved from WS-only handlers into TOOL_DEFS.

Pinned here so a future registry edit cannot silently un-promote them:
the panel's bridge_adapter aliases (promotion-staged in the parity-audit
fix) only resolve while these registry entries exist.
"""

from synapse.mcp import _tool_registry as reg

_PROMOTED = {
    "synapse_solaris_shotsetup_karma_xpu": "solaris_shotsetup_karma_xpu",
    "synapse_matlib_bind": "matlib_bind",
    "synapse_assess_render_ready": "assess_render_ready",
    "tops_pause_cook": "tops_pause_cook",
    "tops_resume_cook": "tops_resume_cook",
}


def test_promoted_tools_registered():
    names = {t[0]: t[1] for t in reg.TOOL_DEFS}
    for tool_name, ws_command in _PROMOTED.items():
        assert tool_name in names, (
            f"{tool_name} missing from TOOL_DEFS — parity promotion regressed; "
            f"ws handler {ws_command!r} (server/handlers.py) is WS-only again."
        )
        assert names[tool_name] == ws_command


def test_promoted_ws_commands_have_handlers():
    """The ws_command each entry dispatches to must be a real WS registration."""
    from synapse.server.handlers import SynapseHandler
    handler = SynapseHandler()
    for tool_name, ws_command in _PROMOTED.items():
        assert handler._registry.has(ws_command), (
            f"{tool_name} dispatches to {ws_command!r} but no WS handler is "
            "registered for it."
        )


def test_assess_render_ready_is_read_only_in_both_sets():
    """assess_render_ready is read-only at transport AND bridge layers —
    it must not land in read_only divergent set (mutating-to-bridge class)."""
    from synapse.mcp import server as mcp_server
    from synapse.panel import bridge_adapter
    assert "synapse_assess_render_ready" in mcp_server._READ_ONLY_TOOLS
    assert "synapse_assess_render_ready" in bridge_adapter._READ_ONLY_TOOLS


def test_shotsetup_keeps_disk_elevation():
    """Shotsetup writes dept .usd layer files — the R4 touches_disk elevation
    must survive promotion so the gate stays APPROVE."""
    from synapse.panel import bridge_adapter
    assert "synapse_solaris_shotsetup_karma_xpu" in bridge_adapter._DISK_WRITING_TOOLS
