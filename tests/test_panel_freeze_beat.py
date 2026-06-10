"""D3 wiring, panel leg — the v9 panel is the freeze chain's heartbeat source.

The panel rebuild removed the only server.heartbeat() caller, leaving the
freeze chain unarmed (C10). The v9 panel now runs a 1s QTimer beating the
process-wide freeze chain. These pins verify the beat method drives the chain
and that the timer wiring exists at panel construction.

PySide-gated like the other panel pins (runs under hython / wherever Qt or the
sibling stubs provide PySide6); the beat-method test needs no QApplication.
"""

import pytest

pytest.importorskip("PySide6")

from unittest.mock import MagicMock, patch

from synapse.panel.synapse_panel import SynapsePanel


def test_beat_method_drives_the_freeze_chain():
    fake = MagicMock()
    with patch("synapse.server.freeze_chain.beat") as beat:
        SynapsePanel._beat_freeze_chain(fake)
        beat.assert_called_once()


def test_beat_method_never_raises_without_server_package():
    fake = MagicMock()
    with patch("synapse.server.freeze_chain.beat", side_effect=RuntimeError("boom")):
        SynapsePanel._beat_freeze_chain(fake)   # swallowed — panel must survive


def test_panel_constructs_the_freeze_timer():
    # Source-level pin (no QApplication needed): the 1s timer + connect + start
    # exist in the panel constructor path.
    import inspect
    src = inspect.getsource(SynapsePanel)
    assert "_freeze_timer" in src
    assert "_beat_freeze_chain" in src
    assert "setInterval(1000)" in src
