"""F02: execute_vex must refuse an unresolvable input_node.

Before the fix a misspelled path fell back to a fresh /obj/synapse_vex_temp
container and ran the snippet on empty geometry; on a failed cook the temp
container was never cleaned up (cleanup is gated on ``not input_node``).
"""

import contextlib
from unittest.mock import MagicMock

import pytest

from synapse.core.errors import NodeNotFoundError
from synapse.server import handlers
from synapse.server import update_mode


def test_execute_vex_unresolvable_input_node_raises_before_create(monkeypatch):
    obj = MagicMock(name="obj")
    fake_hou = MagicMock(name="hou")
    fake_hou.node.side_effect = lambda p: obj if p == "/obj" else None

    monkeypatch.setattr(handlers, "hou", fake_hou, raising=False)
    monkeypatch.setattr(handlers, "HOU_AVAILABLE", True)
    monkeypatch.setattr(
        handlers, "run_on_main_observed",
        lambda fn, timeout=None, label=None: fn(),
    )
    monkeypatch.setattr(
        update_mode, "cook_sandwich",
        lambda label=None: contextlib.nullcontext(),
    )

    with pytest.raises(NodeNotFoundError):
        handlers.SynapseHandler._handle_execute_vex(
            MagicMock(),
            {"snippet": "@P.y += 1;", "input_node": "/obj/typo/x"},
        )

    obj.createNode.assert_not_called()
