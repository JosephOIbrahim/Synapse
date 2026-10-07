"""F03: hda_package reports caller parms it could not find instead of dropping them.

Mock-based -- no Houdini required. Reuses test_hda's bootstrap and package mocks.
"""

from unittest.mock import patch

import test_hda
from test_hda import _handlers_hou, handler  # noqa: F401  (fixture)


def _package(handler, parms):
    mocks = test_hda.TestHdaPackageNodes._make_package_mocks(None)
    parent, subnet = mocks[0], mocks[1]
    create = subnet.createNode.side_effect

    def _create(node_type, node_name=None):
        node = create(node_type, node_name)
        node.parm.side_effect = lambda name: None if name == "bogus" else node.parm.return_value
        return node

    subnet.createNode.side_effect = _create
    with patch.object(_handlers_hou, "node", return_value=parent):
        with patch.object(_handlers_hou, "hda", create=True):
            return handler._handle_hda_package({
                "description": "Test tool",
                "name": "test_tool",
                "category": "Sop",
                "save_path": "/tmp/test.hda",
                "nodes": [{"type": "scatter", "name": "scatter1", "parms": parms}],
            })


def test_unknown_parm_is_reported(handler):
    result = _package(handler, {"bogus": 1, "npts": 5})
    assert result["parms_missed"] == ["scatter1.bogus"]
    assert any("scatter1.bogus" in w for w in result["warnings"])


def test_known_parms_report_nothing(handler):
    result = _package(handler, {"npts": 5})
    assert result["parms_missed"] == []
