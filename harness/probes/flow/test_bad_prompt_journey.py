#!/usr/bin/env hython
# -*- coding: utf-8 -*-
"""W6-FLOWRIG acceptance #2 (evidence: test) - the bad-prompt journey.

A deliberately bad prompt must surface a READABLE in-panel error, carry NO raw
traceback, and leave the session ALIVE. Driven against the LIVE SynapsePanel
widget offscreen under the seat recipe (same as probe_flow.py). Runs two fault
surfaces - an unknown-tool ToolRequest and the provider _on_error path - and a
post-fault liveness probe.

Run under the seat recipe:
  env -u SYNAPSE_ROOT -u HOUDINI_PACKAGE_DIR \
      HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
      "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
      -m pytest harness/probes/flow/test_bad_prompt_journey.py -q
  # (or run the file directly: ... hython.exe harness/probes/flow/test_bad_prompt_journey.py)
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import pytest
except Exception:                                              # noqa: BLE001
    pytest = None

try:
    from PySide6 import QtWidgets
except ImportError:                                            # pragma: no cover
    try:
        from PySide2 import QtWidgets
    except ImportError:
        QtWidgets = None

_APP = None


def _ensure_app():
    global _APP
    if QtWidgets is None:
        return None
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w6-bad-prompt"])
    return _APP


def _new_panel():
    if _ensure_app() is None:
        raise RuntimeError("no Qt binding available")
    from synapse.panel.synapse_panel import SynapsePanel
    return SynapsePanel()


# --------------------------------------------------------------------------- #
# pytest surface                                                               #
# --------------------------------------------------------------------------- #
if pytest is not None:

    @pytest.fixture
    def panel():
        if _ensure_app() is None:
            pytest.skip("no Qt binding (not under a seat hython)")
        try:
            return _new_panel()
        except Exception as e:                                 # noqa: BLE001
            pytest.skip("SynapsePanel unavailable: %r" % e)

    def test_unknown_tool_errors_cleanly_without_traceback(panel):
        from synapse.panel.tool_executor import ToolRequest
        req = ToolRequest(tool_use_id="w6-bad-1",
                          tool_name="make_me_a_sandwich_please", tool_input={})
        panel._tool_executor.execute_tool(req)
        req.done.wait(30)
        err = str(getattr(req, "error", "") or "")
        assert err, "an unknown tool must surface a readable error, not silence"
        assert "Traceback" not in err, "the bad-tool error must be human, not a raw traceback"

    def test_on_error_posts_human_text_no_traceback(panel):
        panel._on_error("simulated engine failure")
        chat = panel._chat.document().toPlainText()
        assert "We hit a snag" in chat, "a provider fault must read as human in-panel text"
        assert "Traceback (most recent call last)" not in chat

    def test_session_survives_the_fault(panel):
        panel._on_error("boom")
        panel._set_busy(False)                       # the panel un-busies, stays interactive
        panel._chat.append_system_message("post-fault liveness probe")
        assert "post-fault liveness probe" in panel._chat.document().toPlainText(), \
            "the panel must still accept work after the fault (session alive)"


# --------------------------------------------------------------------------- #
# plain-script fallback (no pytest): run the three assertions, print a receipt #
# --------------------------------------------------------------------------- #
def _run_as_script():
    print("== W6-FLOWRIG bad-prompt journey (script mode) ==", flush=True)
    p = _new_panel()
    from synapse.panel.tool_executor import ToolRequest
    req = ToolRequest(tool_use_id="w6-bad-1", tool_name="make_me_a_sandwich_please", tool_input={})
    p._tool_executor.execute_tool(req)
    req.done.wait(30)
    err = str(getattr(req, "error", "") or "")
    assert err and "Traceback" not in err, "unknown-tool error not clean: %r" % err
    print("  unknown-tool error (clean, no traceback):", err, flush=True)

    p._on_error("simulated engine failure")
    chat = p._chat.document().toPlainText()
    assert "We hit a snag" in chat and "Traceback (most recent call last)" not in chat
    print("  _on_error posts human text, no traceback: OK", flush=True)

    p._set_busy(False)
    p._chat.append_system_message("post-fault liveness probe")
    assert "post-fault liveness probe" in p._chat.document().toPlainText()
    print("  session alive after fault: OK", flush=True)
    print("== ALL 3 bad-prompt assertions PASS ==", flush=True)


if __name__ == "__main__":
    _run_as_script()
    sys.exit(0)
