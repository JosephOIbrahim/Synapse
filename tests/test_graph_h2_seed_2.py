"""F02: _handle_hda_set_help must not call definition.sections().

The result was never used, and a raising sections() aborted the handler
before addSection ran.
"""

from unittest.mock import MagicMock, patch

from test_hda import _handlers_hou, _make_hda_node, handlers_mod


def test_set_help_does_not_read_sections():
    handler = handlers_mod.SynapseHandler()
    handler._bridge = MagicMock()
    hda_node, definition, _ = _make_hda_node()
    definition.sections.side_effect = RuntimeError("boom")

    with patch.object(_handlers_hou, "node", return_value=hda_node):
        result = handler._handle_hda_set_help({
            "hda_path": "/obj/geo1/my_hda",
            "summary": "Point Scatter",
            "description": "Scatters points randomly on surfaces.",
        })

    assert result["status"] == "ok"
    definition.sections.assert_not_called()
    definition.addSection.assert_called_once()
    assert definition.addSection.call_args[0][0] == "HelpText"
