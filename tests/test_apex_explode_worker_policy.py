"""The panel worker may call synapse_add_explode_control, in standard mode only.

The tool is review-gated (``build_rig_logic``), and the worker refuses a
review-gated tool unless it sits on ``_WORKER_BUILDER_ALLOWLIST``. It is there
on the argument the camera trail is: one undo-grouped call, the host writes
the node's code, and the schema carries no code.

This file and the allowlist entry are one commit. Drop that commit and the
tool still exists; the worker is refused it, and these tests go with it.

Pure Python -- no hou.
"""
from __future__ import annotations

import pytest

from synapse.panel import worker_policy

TOOL = "synapse_add_explode_control"


@pytest.mark.parametrize("mode, allowed", [
    ("standard", True), ("unrestricted", True),
    ("demo", False), ("strict", False), ("proposal", False),
])
def test_the_worker_may_call_it_where_it_may_build_and_nowhere_else(mode, allowed):
    """Fails if the tool becomes callable in a mode that only reads, or stops
    being callable in the mode the panel ships in."""
    assert worker_policy.is_tool_allowed_for_worker(TOOL, profile=mode)[0] is allowed


def test_it_is_allowed_by_the_list_and_not_by_a_lighter_gate():
    """The gate stays review. Fails if the tool was let through by lowering
    its gate instead of by naming it on the list."""
    assert worker_policy._TOOL_INDEX[TOOL] == {"read_only": False, "gate": "review"}
    assert TOOL in worker_policy._WORKER_BUILDER_ALLOWLIST


def test_the_argument_for_the_list_still_holds():
    """The list is for calls whose code the host writes. Fails if the schema
    gains a field that could carry code, a node name or a direction."""
    from synapse.mcp._tool_registry import TOOL_JSON

    assert set(TOOL_JSON[TOOL]["inputSchema"]["properties"]) == {"node", "travel"}


def test_the_code_tools_stay_refused():
    """Fails if letting this builder through loosened arbitrary code."""
    for tool in ("houdini_execute_python", "houdini_execute_vex"):
        assert worker_policy.is_tool_allowed_for_worker(tool, profile="standard")[0] is False
