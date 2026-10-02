"""The Spatial control: read the shot from the panel, with no model turn.

D6 / R-10, R-11 (Joe, 2026-10-02). A click on the footer's Spatial control, or
``/spatial`` in the composer, measures how the shot's camera moves and how close
it comes to the scene, and draws the path as one guide curve. It runs the SAME
tool the model calls, ``synapse_spatial_trail``, so the change is the same one
undo step with the same integrity record, and the answer is the sentence the
tool composed from measured fields. No tokens, and no wording of a model's own
around the numbers.

This module is the part with no Qt and no ``hou`` in it: the words the panel
shows, and the default call. ``synapse_panel`` owns the threading and the
widgets. Everything here is importable on stock CI.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

#: The one tool a click runs. It is on the worker's builder allowlist
#: (worker_policy) on the same argument: one undo-grouped call, no code in.
TOOL = "synapse_spatial_trail"

#: Jev 0.87 over naming "spatial intelligence" (the copy rule: say what the
#: artist gets, in the host's vocabulary).
TOOLTIP = ("Read the camera's move through the scene and draw its path in the "
           "viewport. No model call. One undo step.")

#: The authorship line under the answer. A model did not write this sentence.
SIGNED = "SYNAPSE's camera-path tool · no model request"

#: Shown when a click arrives while a task is running. The trail writes one
#: node; its undo step would land inside that turn's and REVERT would refuse.
BUSY = "A task is still running. Wait for it to finish, or stop it, then read the shot."
RUNNING = "Still reading the shot."

#: The click, as the model's history holds it (one ask-and-answer pair).
HISTORY_ASK = "Read the shot."
#: The model trusts its history. After an artist undo it may still say the path
#: is there (seen in the recorded GUI test of 2026-10-02), so the answer line
#: says when it was true.
HISTORY_NOTE = (" (Answered by the panel with no model call. It describes the "
                "scene when it ran; an undo or a later edit is not reflected here.)")

_TOOL_HINT = re.compile(r"\s*\(pass against=\w+\)")


def answer_text(result: Dict[str, Any]) -> str:
    """The panel's answer, composed from the tool's own fields only.

    The first sentence is the tool's ``outcome``. What the clearance left out
    follows when there is any, then how to reverse the build when one happened.
    """
    parts = [str(result.get("outcome") or "").strip()]
    clearance = result.get("clearance") or {}
    left_out = [_TOOL_HINT.sub("", str(item)) for item in clearance.get("not_measured") or ()]
    if left_out:
        parts.append("Not measured: %s." % "; ".join(left_out))
    undo = (result.get("undo") or {}).get("artist")
    if undo:
        parts.append(str(undo).rstrip(".") + ".")
    return "\n\n".join(part for part in parts if part)


def changed_scene(result: Dict[str, Any]) -> bool:
    """True when the call wrote to the scene: a trail created or redrawn. An
    unchanged trail leaves nothing on the undo stack, so it earns no receipt."""
    return (result.get("trail") or {}).get("status") in ("created", "updated")


def error_text(error: Optional[str]) -> str:
    """What the panel says when nothing was drawn: the tool's own reason. An
    UNKNOWN move arrives here as 'No trail drawn: <why it cannot be read>'."""
    reason = (error or "").strip() or "the tool returned no result"
    return "Spatial: %s" % reason


def call_trail() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Run the trail tool from OFF the Qt thread. Returns ``(result, error)``.

    The panel's own executor, on the path the worker falls back to: because the
    caller is not Houdini's main thread, the handler is marshalled onto it by
    the deferred route with the tool's timeout, and runs through the execution
    bridge. Never call this on the main thread.
    """
    from synapse.panel.tool_executor import ToolExecutor, ToolRequest

    request = ToolRequest(tool_use_id="panel-spatial", tool_name=TOOL, tool_input={})
    ToolExecutor().execute_tool_off_main(request)
    if request.error:
        return None, str(request.error)
    if not isinstance(request.result, dict):
        return None, None
    return request.result, None
