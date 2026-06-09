"""C8 (CTO Remediation Mile 2) — honest Stop button.

Before C8, _on_stop() aborted the worker then immediately flipped the rail to
'Standing by' (_set_busy(False)) — claiming idle while Houdini kept cooking the
in-flight tool. C8 keeps the busy state, shows 'Stopping — waiting on <tool>…',
and lets the worker's real completion (stream_done/error → _on_done/_on_error)
reset to idle.

PySide-gated: the panel module imports PySide6/2 at top, so this skips in stock
CI and runs under hython (offscreen). The logic is exercised by calling the
unbound _on_stop with a fake self — no full panel construction needed.
"""

import pytest

pytest.importorskip("PySide6")  # panel imports PySide6 (PySide2 fallback) at module top

from unittest.mock import MagicMock

from synapse.panel.synapse_panel import SynapsePanel


def test_stop_holds_busy_says_stopping_and_does_not_lie_idle():
    fake = MagicMock()
    fake._worker = MagicMock()
    fake._last_tool = "tops_cook_node"

    SynapsePanel._on_stop(fake)

    fake._worker.abort.assert_called_once()                 # the loop is aborted
    fake._stop_btn.setEnabled.assert_called_once_with(False)  # press registered
    # Header says we're stopping and names the in-flight tool.
    state, text = fake._set_header.call_args[0]
    assert state == "working" and "Stopping" in text and "tops_cook_node" in text
    # The dishonest immediate idle-flip is GONE — busy stays until real completion.
    fake._set_busy.assert_not_called()


def test_stop_without_known_tool_is_still_honest():
    fake = MagicMock()
    fake._worker = MagicMock()
    fake._last_tool = None

    SynapsePanel._on_stop(fake)

    _, text = fake._set_header.call_args[0]
    assert "Stopping" in text                                # generic but still honest
    fake._set_busy.assert_not_called()


def test_tool_status_tracks_running_tool():
    fake = MagicMock()
    fake._last_tool = None
    fake._work_face = None
    fake._review_face = None
    SynapsePanel._on_tool_status(fake, "tops_render_sequence", "running", "")
    assert fake._last_tool == "tops_render_sequence"
    # a non-running phase does not overwrite the tracked in-flight tool
    SynapsePanel._on_tool_status(fake, "something_else", "done", "")
    assert fake._last_tool == "tops_render_sequence"
